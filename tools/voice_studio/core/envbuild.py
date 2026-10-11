# SPDX-License-Identifier: GPL-3.0-or-later
"""Building a Python environment from its lock (plan task VS-1.9, decisions D11 and D27).

The promises, each held by a test:

* **Nothing is built from an unpinned list.** The lock must carry checksums and match the checksum the environment list names; the trainer's
  source must be the pinned archive from the registry. Installing uses pip's hash-checking mode with wheels only.
* **An environment the tool did not make is never touched.** Each build goes in its own folder named for what it is built from; a folder
  with no record of ours is refused, one from a newer version is refused, and a damaged record is reported and left alone. A different lock
  or source makes a new folder next to the old one; nothing is deleted.
* **Safe to run again, and to resume.** Every step is checked against the record *and* against the folder itself, so a deleted piece is
  rebuilt and a good one is kept. A step that failed is the first one tried next time.
* **Only one build at a time** per environment (a lock file holding the process that owns it, checked the way job.py checks a runner).
* **Fixes are made by wrapper.** A launcher starts a module after the documented workarounds, so no program file is edited. A change to a
  source file is shown, needs a yes, keeps the original first, and is checked before it is trusted.
* **Nothing is installed without the agreement the person gave by name.** Commands that reach the network go through core/fetch.py and are
  refused unless the agreement covers them; this module starts no program of its own.
"""
from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import shutil
import tarfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from . import fetch
from .consent import ConsentRecord
from .envspec import EnvSpec, NativePart, Pin, SourcePatch, lock_digest, normalise_name, parse_lock
from .jobs import OFFLINE_ENV, boot_id, parse_proc_starttime, process_alive, read_json, read_text_file, utc_stamp, write_json
from .paths import DataHome
from .registry import Item, Registry
from .system import CommandResult, System

SCHEMA = 1
BUILDER_VERSION = 1
RECORD_NAME = "ack-env.json"
BUILD_LOCK_NAME = ".build.lock"
LOG_NAME = "build.log"
LOCK_COPY_NAME = "lock.txt"
LAUNCHER_NAME = "ack_run.py"
UNPACK_MARKER = ".ack-unpacked"
NATIVE_WORK = "native-work"            # where a native part is built; made fresh for each build and removed afterwards
BACKUP_SUFFIX = ".before-ack-patch"
ROOM_MARGIN_BYTES = 1 << 30            # PROVISIONAL (plan P11): spare room that must remain after the environment is built
RESUME_NEED_BYTES = 256 << 20          # what a resumed build that only has small steps left needs
MAX_UNPACK_BYTES = 1 << 30             # a hostile or mistaken archive cannot ask for more than this
MAX_UNPACK_FILES = 50_000
TAIL_LINES = 12                        # how much of a failed command's output is kept with the error
STEP_TIMEOUT_S = {"venv": 600.0, "native_build": 3600.0, "probe": 600.0, "verify": 120.0}

# Each has words in the text catalog (env.error.<code>.what / .changed / .next).
ERROR_CODES = ("not_pinned", "lock_missing", "lock_changed", "lock_invalid", "python_old", "python_new", "not_ours", "newer_record", "damaged_record", "busy",
               "no_room", "consent", "source_fetch", "unpack_unsafe", "unpack_failed", "venv_failed", "pip_failed", "native_failed",
               "patch_declined", "patch_changed", "native_changed", "launcher_failed", "self_test_failed", "write_failed")
STEP_IDS = ("source_unpack", "patches", "venv", "pip_lock", "pip_source", "native_build", "wrapper")      # the recorded steps, in order
ACTION_IDS = ("room", "source_fetch") + STEP_IDS + ("self_test",)                                         # everything the screens can name
INSPECTION_STATES = ("absent", "ready", "needs_work", "failed", "not_ours", "damaged", "newer", "not_buildable")


class EnvError(Exception):
    """`code` is one of ERROR_CODES. `detail` is short and technical (shown under Show details); `tail` is the end of a failed command's output."""

    def __init__(self, code: str, detail: str = "", tail: Sequence[str] = ()):
        super().__init__(code + (": " + detail if detail else ""))
        self.code = code
        self.detail = detail
        self.tail = tuple(tail)


@dataclass(frozen=True)
class Event:
    kind: str                       # "start", "done", "kept", "skipped", "line"
    step: str                       # one of ACTION_IDS, or a probe id for "skipped"
    text: str = ""


@dataclass(frozen=True)
class PatchProposal:
    """What the person is shown before a source file is changed."""
    env_id: str
    patch: SourcePatch
    path: str
    before: str                     # the lines around the change, as they are now
    after: str                      # and as they would be


def _no_events(event: Event) -> None:
    return None


def _never(proposal: PatchProposal) -> bool:
    return False


def _read_lock_file(spec: EnvSpec) -> bytes:
    return spec.lock_path.read_bytes()


def _read_native_file(native: NativePart) -> bytes:
    return native.path.read_bytes()


@dataclass
class Context:
    system: System
    home: DataHome
    registry: Registry
    consent: Optional[ConsentRecord]
    gpu_ok: bool = False                                              # a usable graphics card was found (preflight); without it the card probes are skipped
    confirm_patch: Callable[[PatchProposal], bool] = _never           # the person's yes to a source change; the default is no
    on_event: Callable[[Event], None] = _no_events
    fetcher: Callable = fetch.fetch
    networked: Callable = fetch.run_networked
    read_lock: Callable[[EnvSpec], bytes] = _read_lock_file
    read_native: Callable[[NativePart], bytes] = _read_native_file
    now: Callable[[], datetime] = lambda: datetime.now(timezone.utc)


@dataclass(frozen=True)
class BuildResult:
    ok: bool
    env_dir: str = ""
    error: Optional[EnvError] = None
    did: Tuple[str, ...] = ()                       # steps run this time
    kept: Tuple[str, ...] = ()                      # steps already done and still good
    skipped: Tuple[str, ...] = ()                   # probes not run (no usable graphics card)


@dataclass(frozen=True)
class EnvPaths:
    env_dir: str

    @property
    def venv(self) -> str:
        return self.env_dir + "/venv"

    @property
    def python(self) -> str:
        return self.venv + "/bin/python"

    @property
    def source(self) -> str:
        return self.env_dir + "/source"

    @property
    def launcher(self) -> str:
        return self.env_dir + "/" + LAUNCHER_NAME

    @property
    def record(self) -> str:
        return self.env_dir + "/" + RECORD_NAME

    @property
    def log(self) -> str:
        return self.env_dir + "/" + LOG_NAME


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: str) -> Optional[str]:
    digest = hashlib.sha256()
    try:
        with open(path, "rb") as handle:
            for block in iter(lambda: handle.read(1 << 20), b""):
                digest.update(block)
    except OSError:
        return None
    return digest.hexdigest()


# ---------------------------------------------------------------- what an environment is called

def fingerprint(spec: EnvSpec, lock_sha: str, source: Optional[Item], python_minor: Tuple[int, int]) -> str:
    """What makes a new folder necessary: the Python it runs on, the lock, the source archive and the source patches. The launcher's workarounds
    are not here (they are rewritten in place), but a change to the source tree is: a patch removed from the list must not stay applied."""
    data = {"builder": BUILDER_VERSION, "id": spec.id, "python": "%d.%d" % python_minor, "lock": lock_sha,
            "source": source.sha256 if source is not None else None,
            "install": bool(spec.source and spec.source.install), "dist": spec.source.dist if spec.source else None,
            "native": spec.source.native_build if spec.source else None,
            "patches": [[p.id, p.file, sha256_bytes(p.old.encode()), sha256_bytes(p.new.encode())] for p in spec.patches]}
    if spec.native is not None:
        data["native_part"] = [spec.native.sha256, spec.native.module, spec.native.into]
    return sha256_bytes(json.dumps(data, sort_keys=True).encode())


def env_dir_name(spec: EnvSpec, fp: str) -> str:
    return "%s-%s" % (spec.id, fp[:10])


# ---------------------------------------------------------------- the record (files are the state)

def _blank_record(spec: EnvSpec, fp: str, python_minor: Tuple[int, int], stamp: str) -> dict:
    return {"schema": SCHEMA, "builder": BUILDER_VERSION, "id": spec.id, "fingerprint": fp, "python": "%d.%d" % python_minor, "created_at": stamp,
            "updated_at": stamp, "state": "building", "steps": {}, "patches": {}}


def read_record(env_dir: str) -> Tuple[Optional[dict], str]:
    """(the record, "") or (None, why): "absent" (no record), "newer", "damaged". Never raises."""
    path = env_dir + "/" + RECORD_NAME
    if not os.path.exists(path):
        return None, "absent"
    data = read_json(path)
    if not isinstance(data, dict) or not isinstance(data.get("steps"), dict) or not isinstance(data.get("patches"), dict) \
            or not isinstance(data.get("id"), str) or not isinstance(data.get("fingerprint"), str):
        return None, "damaged"
    if not isinstance(data.get("schema"), int) or isinstance(data.get("schema"), bool):
        return None, "damaged"
    if data["schema"] > SCHEMA:
        return None, "newer"
    return data, ""


def _save_record(env_dir: str, record: dict, stamp: str) -> None:
    record["updated_at"] = stamp
    try:
        write_json(env_dir + "/" + RECORD_NAME, record)
    except OSError as exc:
        raise EnvError("write_failed", exc.strerror or type(exc).__name__)


# ---------------------------------------------------------------- one build at a time

def _acquire(env_dir: str) -> str:
    """Create the build lock, or take over one whose owner is gone. Returns its path. Raises EnvError("busy").

    The lock is written to a private file first and then linked into place, so another build never sees a lock that is half written (an
    unreadable lock counts as left behind). Known limit: two builds that both find the same stale lock in the same instant can both take over."""
    path = env_dir + "/" + BUILD_LOCK_NAME
    mine = {"pid": os.getpid(), "starttime": parse_proc_starttime(read_text_file("/proc/self/stat")), "boot": boot_id()}
    temp = "%s.%d.tmp" % (path, os.getpid())
    try:
        fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(mine, handle)
    except OSError as exc:
        raise EnvError("write_failed", exc.strerror or type(exc).__name__)
    try:
        for _ in range(2):
            try:
                os.link(temp, path)                              # all or nothing: fails if a lock is already there
                return path
            except FileExistsError:
                held = read_json(path)
                if isinstance(held, dict) and process_alive(held.get("pid"), held.get("starttime"), str(held.get("boot", ""))):
                    raise EnvError("busy", "process %s" % held.get("pid"))
                try:
                    os.unlink(path)                              # its owner is gone (or the file is unreadable): the lock is stale
                except FileNotFoundError:
                    pass
            except OSError:
                return _acquire_without_links(path, mine)        # a drive that cannot make hard links
        raise EnvError("busy", "could not take the lock")
    finally:
        try:
            os.unlink(temp)
        except OSError:
            pass


def _acquire_without_links(path: str, mine: dict) -> str:
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        raise EnvError("busy", "another build holds the lock")
    except OSError as exc:
        raise EnvError("write_failed", exc.strerror or type(exc).__name__)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(mine, handle)
    return path


def _release(path: str) -> None:
    try:
        os.unlink(path)
    except OSError:
        pass


# ---------------------------------------------------------------- the log

class _Log:
    """Everything the commands print, kept in the environment folder (owner only) and passed on line by line."""

    def __init__(self, path: str, step: str, on_event: Callable[[Event], None]):
        self.path, self.step, self.on_event, self.tail = path, step, on_event, []

    def line(self, text: str) -> None:
        self.tail = (self.tail + [text])[-TAIL_LINES:]
        try:
            fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
            with os.fdopen(fd, "a", encoding="utf-8", errors="replace") as handle:
                handle.write(text + "\n")
        except OSError:
            pass
        self.on_event(Event("line", self.step, text))

    def result(self, result: Optional[CommandResult]) -> None:
        if result is None:
            return
        for text in (result.stdout + result.stderr).splitlines():
            self.line(text)


# ---------------------------------------------------------------- unpacking the source archive safely

def _inside(root: str, path: str) -> bool:
    root = os.path.realpath(root)
    path = os.path.realpath(path)
    return path == root or path.startswith(root + os.sep)


def unpack_archive(archive: Path, dest: Path, marker_text: str) -> None:
    """Unpack a .tar.gz into `dest`, dropping the one top folder the archive has. Nothing outside `dest` can be written: names with `..` or an
    absolute start, devices, hard links and links that leave the folder are refused, and the size and file count are capped. `dest` appears
    only when everything is in place (it is built as `dest.part` and renamed), so a stopped unpack leaves nothing that looks finished."""
    dest = Path(dest)
    part = dest.with_name(dest.name + ".part")
    if dest.exists() or dest.is_symlink():
        raise EnvError("unpack_failed", "a folder is already in the way")
    if part.is_symlink() or part.is_file():
        part.unlink()                                                  # a leftover of ours from an unpack that was stopped
    elif part.is_dir():
        shutil.rmtree(part, ignore_errors=True)
    try:
        with tarfile.open(str(archive), "r:gz") as tar:
            members = tar.getmembers()
            _check_members(members)
            part.mkdir(mode=0o700)
            root = str(part)
            for member in members:
                relative = _strip_top(member.name)
                if relative is None:
                    continue
                target = os.path.join(root, *relative.parts)
                if not _inside(root, os.path.dirname(target)):
                    raise EnvError("unpack_unsafe", "%s leaves the folder" % member.name)
                if member.isdir():
                    os.makedirs(target, mode=0o755, exist_ok=True)
                elif member.isreg():
                    os.makedirs(os.path.dirname(target), mode=0o755, exist_ok=True)
                    source = tar.extractfile(member)
                    if source is None:
                        raise EnvError("unpack_failed", "%s cannot be read" % member.name)
                    with source, open(target, "xb") as out:
                        shutil.copyfileobj(source, out, 1 << 20)
                    os.chmod(target, 0o755 if member.mode & 0o100 else 0o644)
                elif member.issym():
                    os.makedirs(os.path.dirname(target), mode=0o755, exist_ok=True)
                    link_target = os.path.join(os.path.dirname(target), member.linkname)
                    if os.path.isabs(member.linkname) or not _inside(root, link_target):
                        raise EnvError("unpack_unsafe", "%s points outside the folder" % member.name)
                    os.symlink(member.linkname, target)
            (part / UNPACK_MARKER).write_text(marker_text, encoding="utf-8")
        os.replace(str(part), str(dest))
    except EnvError:
        shutil.rmtree(part, ignore_errors=True)
        raise
    except (tarfile.TarError, EOFError, OSError, UnicodeError) as exc:
        shutil.rmtree(part, ignore_errors=True)
        raise EnvError("unpack_failed", getattr(exc, "strerror", None) or type(exc).__name__)


def _strip_top(name: str) -> Optional[PurePosixPath]:
    parts = PurePosixPath(name).parts
    return PurePosixPath(*parts[1:]) if len(parts) > 1 else None


def _check_members(members: Sequence[tarfile.TarInfo]) -> None:
    if not members:
        raise EnvError("unpack_failed", "the archive is empty")
    if len(members) > MAX_UNPACK_FILES:
        raise EnvError("unpack_unsafe", "too many files")
    total, tops = 0, set()
    for member in members:
        name = member.name
        path = PurePosixPath(name)
        if not name or "\x00" in name or "\\" in name or path.is_absolute() or ".." in path.parts:
            raise EnvError("unpack_unsafe", "unsafe name %r" % name[:80])
        if not (member.isreg() or member.isdir() or member.issym()):
            raise EnvError("unpack_unsafe", "%s is not an ordinary file, folder or link" % name[:80])
        if member.issym() and (not member.linkname or "\x00" in member.linkname):
            raise EnvError("unpack_unsafe", "%s has no usable link target" % name[:80])
        total += max(member.size, 0)
        if total > MAX_UNPACK_BYTES:
            raise EnvError("unpack_unsafe", "too large")
        if path.parts:
            tops.add(path.parts[0])
    if len(tops) != 1:
        raise EnvError("unpack_unsafe", "the archive does not have one top folder")


# ---------------------------------------------------------------- the checks that run inside a finished environment

_VERIFY_CODE = r'''
import json, re, sys
import importlib.metadata as md
want = json.loads(sys.argv[1])
have = {}
for d in md.distributions():
    name = d.metadata["Name"]
    if name:
        have[re.sub(r"[-_.]+", "-", name).lower()] = d.version
try:
    from pip._vendor.packaging.markers import Marker
    from pip._vendor.packaging.version import Version
except Exception:
    Marker = Version = None
def same(a, b):
    try:
        return Version(a) == Version(b) if Version is not None else a == b
    except Exception:
        return a == b
bad = []
for name, version, marker in want["pins"]:
    if marker:
        if Marker is None:
            continue
        try:
            if not Marker(marker).evaluate():
                continue
        except Exception:
            continue
    if name not in have:
        bad.append("missing " + name)
    elif not same(have[name], version):
        bad.append("version %s %s" % (name, have[name]))
for name in want["dists"]:
    if name not in have:
        bad.append("missing " + name)
print(json.dumps(bad))
'''

_MINOR_CODE = "import sys; print('%d.%d' % sys.version_info[:2]); print(int(sys.prefix != sys.base_prefix))"


def launcher_text(spec: EnvSpec) -> str:
    """The launcher: starts a module in this environment after the documented workarounds. No program file is edited."""
    lines = ["# Made by ACK Voice Studio. It runs the workarounds below, then starts the module named first on its command line.",
             "# Run it with this environment's own Python:   <environment>/venv/bin/python ack_run.py <module> <arguments>",
             "import runpy", "import sys", ""]
    lines += list(spec.prelude)
    lines += ["", "module = sys.argv[1]", "sys.argv = sys.argv[1:]", 'runpy.run_module(module, run_name="__main__", alter_sys=True)', ""]
    return "\n".join(lines)


# ---------------------------------------------------------------- the build

@dataclass
class _Plan:
    spec: EnvSpec
    ctx: Context
    paths: EnvPaths
    lock_bytes: bytes
    lock_sha: str
    pins: List[Pin]
    item: Optional[Item]
    minor: Tuple[int, int]
    record: dict = field(default_factory=dict)


def _atomic_write(path: str, data: bytes) -> None:
    temp = "%s.tmp-%d" % (path, os.getpid())
    try:
        fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
    except OSError as exc:
        try:
            os.unlink(temp)
        except OSError:
            pass
        raise EnvError("write_failed", exc.strerror or type(exc).__name__)


def _resolve(spec: EnvSpec, ctx: Context) -> Tuple[bytes, str, List[Pin], Optional[Item], Tuple[int, int]]:
    """Everything that must be true before a folder is even named. Raises EnvError."""
    problems = spec.pin_problems(ctx.registry)
    if problems:
        raise EnvError("not_pinned", ",".join(problems))
    try:
        lock_bytes = ctx.read_lock(spec)
    except OSError as exc:
        raise EnvError("lock_missing", spec.lock_filename if not exc.strerror else "%s: %s" % (spec.lock_filename, exc.strerror))
    sha = lock_digest(lock_bytes)
    if sha != spec.lock_sha256:
        raise EnvError("lock_changed", spec.lock_filename)
    try:
        pins, lock_problems = parse_lock(lock_bytes.decode("utf-8"))
    except UnicodeDecodeError:
        raise EnvError("lock_invalid", "not text")
    if lock_problems:
        raise EnvError("lock_invalid", lock_problems[0])
    version = ctx.system.python_version()
    minor = (version[0], version[1])
    if minor < spec.python_min:
        raise EnvError("python_old", "%d.%d" % minor)
    if spec.python_max is not None and minor > spec.python_max:
        raise EnvError("python_new", "%d.%d" % minor)
    item = ctx.registry.get(spec.source.item_id) if spec.source is not None else None
    return lock_bytes, sha, pins, item, minor


def environment_dir(spec: EnvSpec, ctx: Context) -> str:
    """Where this environment lives (or will). Raises EnvError if it cannot be built from what is listed."""
    _, sha, _, item, minor = _resolve(spec, ctx)
    return "%s/%s" % (ctx.home.environments, env_dir_name(spec, fingerprint(spec, sha, item, minor)))


def _claim(plan_dir: str, spec: EnvSpec, fp: str, minor: Tuple[int, int], ctx: Context) -> dict:
    """The record of the folder, making the folder and the record when it is new. Refuses anything that is not ours."""
    stamp = utc_stamp(ctx.now())
    if os.path.lexists(plan_dir):
        record, why = read_record(plan_dir)
        if record is None:
            if why == "absent":
                raise EnvError("not_ours", plan_dir)
            if why == "newer":
                raise EnvError("newer_record", plan_dir)
            raise EnvError("damaged_record", plan_dir)
        if record["id"] != spec.id or record["fingerprint"] != fp:
            raise EnvError("damaged_record", "the record does not match the folder")
        return record
    parent = os.path.dirname(plan_dir)
    try:
        os.makedirs(parent, mode=0o700, exist_ok=True)
        os.mkdir(plan_dir, 0o700)
    except FileExistsError:
        raise EnvError("busy", "another build just started")
    except OSError as exc:
        raise EnvError("write_failed", exc.strerror or type(exc).__name__)
    record = _blank_record(spec, fp, minor, stamp)
    _save_record(plan_dir, record, stamp)
    return record


def _free_bytes(system: System, path: str) -> Optional[int]:
    probe = path
    while probe and not system.exists(probe) and probe != os.path.dirname(probe):
        probe = os.path.dirname(probe)
    usage = system.disk_free(probe)
    return usage[1] if usage else None


def build(spec: EnvSpec, ctx: Context) -> BuildResult:
    """Make the environment, or finish making it, or find it already made. Never raises for a problem with the environment: the answer says."""
    try:
        lock_bytes, lock_sha, pins, item, minor = _resolve(spec, ctx)
    except EnvError as error:
        return BuildResult(False, "", error)
    fp = fingerprint(spec, lock_sha, item, minor)
    env_dir = "%s/%s" % (ctx.home.environments, env_dir_name(spec, fp))
    paths = EnvPaths(env_dir)
    try:
        record = _claim(env_dir, spec, fp, minor, ctx)
        lock_path = _acquire(env_dir)
    except EnvError as error:
        return BuildResult(False, env_dir, error)
    plan = _Plan(spec, ctx, paths, lock_bytes, lock_sha, pins, item, minor, record)
    did: List[str] = []
    kept: List[str] = []
    skipped: List[str] = []
    try:
        steps = _steps(plan)
        pending = [s for s in steps if not _is_done(plan, s)]
        if pending:
            _check_room(plan, [s.id for s in pending])
        for step in steps:
            if step not in pending:
                kept.append(step.id)
                ctx.on_event(Event("kept", step.id))
                continue
            ctx.on_event(Event("start", step.id))
            step.run(plan)
            plan.record["steps"][step.id] = {"at": utc_stamp(ctx.now()), "input": step.input(plan)}
            plan.record["state"] = "building"
            plan.record.pop("failed", None)
            _save_record(env_dir, plan.record, utc_stamp(ctx.now()))
            did.append(step.id)
            ctx.on_event(Event("done", step.id))
        ctx.on_event(Event("start", "self_test"))
        skipped = _self_test(plan)
        plan.record["state"] = "ready"
        plan.record["self_test"] = {"at": utc_stamp(ctx.now()), "skipped": skipped}
        plan.record.pop("failed", None)
        _save_record(env_dir, plan.record, utc_stamp(ctx.now()))
        ctx.on_event(Event("done", "self_test"))
        return BuildResult(True, env_dir, None, tuple(did), tuple(kept), tuple(skipped))
    except (EnvError, OSError) as caught:
        error = caught if isinstance(caught, EnvError) else EnvError("write_failed", caught.strerror or type(caught).__name__)
        plan.record["state"] = "failed"
        plan.record["failed"] = {"code": error.code, "detail": error.detail[:200], "at": utc_stamp(ctx.now())}
        try:
            _save_record(env_dir, plan.record, utc_stamp(ctx.now()))
        except EnvError:
            pass
        return BuildResult(False, env_dir, error, tuple(did), tuple(kept), tuple(skipped))
    finally:
        _release(lock_path)


def _check_room(plan: _Plan, pending: Sequence[str]) -> None:
    heavy = any(s in pending for s in ("venv", "pip_lock", "pip_source", "source_unpack"))
    need = (plan.spec.approx_size_bytes if heavy else RESUME_NEED_BYTES) + ROOM_MARGIN_BYTES
    plan.ctx.on_event(Event("start", "room"))
    free = _free_bytes(plan.ctx.system, plan.paths.env_dir)
    if free is not None and free < need:
        raise EnvError("no_room", "%d free, %d needed" % (free, need))
    plan.ctx.on_event(Event("done", "room"))


# ---------------------------------------------------------------- the steps

@dataclass(frozen=True)
class _Step:
    id: str
    input: Callable[[_Plan], str]          # what the step depends on; a changed input makes it run again
    verify: Callable[[_Plan], bool]        # is the result still there and good, whatever the record says
    run: Callable[[_Plan], None]


def _steps(plan: _Plan) -> List[_Step]:
    steps = []
    if plan.spec.source is not None:
        steps.append(_Step("source_unpack", lambda p: p.item.sha256, _verify_unpack, _run_unpack))
        if plan.spec.patches:
            steps.append(_Step("patches", _patches_input, _verify_patches, _run_patches))
    steps.append(_Step("venv", lambda p: "%d.%d" % p.minor, _verify_venv, _run_venv))
    steps.append(_Step("pip_lock", lambda p: p.lock_sha, _verify_lock_installed, _run_pip_lock))
    if plan.spec.source is not None and plan.spec.source.install:
        steps.append(_Step("pip_source", lambda p: p.item.sha256 + p.lock_sha, _verify_source_installed, _run_pip_source))
    if plan.spec.source is not None and plan.spec.source.native_build:
        steps.append(_Step("native_build", lambda p: p.item.sha256 + "%d.%d" % p.minor, _verify_native, _run_native))
    elif plan.spec.native is not None:
        steps.append(_Step("native_build", _native_part_input, _verify_native_part, _run_native_part))
    steps.append(_Step("wrapper", lambda p: sha256_bytes(launcher_text(p.spec).encode()), _verify_wrapper, _run_wrapper))
    return steps


def _is_done(plan: _Plan, step: _Step) -> bool:
    entry = plan.record["steps"].get(step.id)
    if not isinstance(entry, dict) or entry.get("input") != step.input(plan):
        return False
    return step.verify(plan)


def _python(plan: _Plan, code: str, *args: str, timeout: float = STEP_TIMEOUT_S["verify"]) -> Optional[CommandResult]:
    """Run a small check inside the environment. It writes nothing (no compiled-code files)."""
    return plan.ctx.system.run([plan.paths.python, "-c", code, *args], timeout=timeout, cwd=plan.paths.env_dir, env={"PYTHONDONTWRITEBYTECODE": "1"})


# -- unpack

def _verify_unpack(plan: _Plan) -> bool:
    marker = read_text_file(plan.paths.source + "/" + UNPACK_MARKER)
    return os.path.isdir(plan.paths.source) and marker == plan.item.sha256


def _run_unpack(plan: _Plan) -> None:
    ctx = plan.ctx
    ctx.on_event(Event("start", "source_fetch"))
    try:
        archive = ctx.fetcher(plan.item, Path(ctx.home.downloads), ctx.consent)
    except fetch.FetchError as error:
        raise EnvError("consent" if error.code == "consent" else "source_fetch", error.code if error.code != "consent" else plan.item.id)
    ctx.on_event(Event("done", "source_fetch"))
    unpack_archive(Path(archive), Path(plan.paths.source), plan.item.sha256)


# -- patches

def _patch_path(plan: _Plan, patch: SourcePatch) -> str:
    return plan.paths.source + "/" + patch.file


def _patches_input(plan: _Plan) -> str:
    return sha256_bytes(json.dumps([[p.id, p.file, p.old, p.new] for p in plan.spec.patches]).encode())


def _verify_patches(plan: _Plan) -> bool:
    for patch in plan.spec.patches:
        entry = plan.record["patches"].get(patch.id)
        current = sha256_file(_patch_path(plan, patch))
        if not isinstance(entry, dict) or current != entry.get("after"):
            return False
    return True


def _context_lines(text: str, start: int, end: int, around: int = 2) -> str:
    lines = text.splitlines()
    first = text.count("\n", 0, start)
    last = text.count("\n", 0, end)
    return "\n".join(lines[max(0, first - around):last + around + 1])


def _run_patches(plan: _Plan) -> None:
    for patch in plan.spec.patches:
        path = _patch_path(plan, patch)
        entry = plan.record["patches"].get(patch.id)
        current = sha256_file(path)
        if isinstance(entry, dict) and current == entry.get("after"):
            continue                                                   # already made
        try:
            original = Path(path).read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            raise EnvError("patch_changed", patch.file)
        if isinstance(entry, dict) and current not in (entry.get("before"),):
            raise EnvError("patch_changed", patch.file)               # changed by something else since: never overwrite it
        if original.count(patch.old) != 1:
            raise EnvError("patch_changed", patch.file)
        index = original.index(patch.old)
        changed = original[:index] + patch.new + original[index + len(patch.old):]
        proposal = PatchProposal(plan.spec.id, patch, path, _context_lines(original, index, index + len(patch.old)),
                                 _context_lines(changed, index, index + len(patch.new)))
        if not plan.ctx.confirm_patch(proposal):
            raise EnvError("patch_declined", patch.id)
        backup = _backup_name(path)
        try:
            shutil.copy2(path, backup, follow_symlinks=False)
            mode = os.stat(path).st_mode & 0o777
            temp = path + ".ack-tmp"
            with open(temp, "w", encoding="utf-8") as handle:
                handle.write(changed)
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(temp, mode)
            os.replace(temp, path)
        except OSError as exc:
            raise EnvError("write_failed", exc.strerror or type(exc).__name__)
        plan.record["patches"][patch.id] = {"file": patch.file, "before": sha256_bytes(original.encode()), "after": sha256_bytes(changed.encode()),
                                            "backup": os.path.basename(backup)}
        _save_record(plan.paths.env_dir, plan.record, utc_stamp(plan.ctx.now()))


def _backup_name(path: str) -> str:
    """Next to the file, named so it cannot clobber an earlier backup."""
    name = path + BACKUP_SUFFIX
    number = 1
    while os.path.lexists(name):
        number += 1
        name = "%s%s.%d" % (path, BACKUP_SUFFIX, number)
    return name


# -- the Python environment

def _verify_venv(plan: _Plan) -> bool:
    if not os.path.exists(plan.paths.python):
        return False
    result = _python(plan, _MINOR_CODE)
    if result is None or result.returncode != 0:
        return False
    lines = result.stdout.split()
    return lines == ["%d.%d" % plan.minor, "1"]


def _run_venv(plan: _Plan) -> None:
    exe = plan.ctx.system.python_executable()
    log = _Log(plan.paths.log, "venv", plan.ctx.on_event)
    result = plan.ctx.system.run([exe, "-m", "venv", plan.paths.venv], timeout=STEP_TIMEOUT_S["venv"], cwd=plan.paths.env_dir)
    log.result(result)
    if result is None or result.returncode != 0:
        raise EnvError("venv_failed", "could not run" if result is None else "exit %d" % result.returncode, log.tail)


def _wanted(plan: _Plan, pins: bool, dist: bool) -> str:
    """What the check inside the environment is asked about: the locked packages, and/or the trainer's own distribution."""
    dists = [plan.spec.source.dist] if dist and plan.spec.source and plan.spec.source.dist else []
    return json.dumps({"pins": [[p.name, p.version, p.marker] for p in plan.pins] if pins else [],
                       "dists": [normalise_name(d) for d in dists]})


def _problems_inside(plan: _Plan, pins: bool, dist: bool) -> Optional[List[str]]:
    result = _python(plan, _VERIFY_CODE, _wanted(plan, pins, dist))
    if result is None or result.returncode != 0:
        return None
    try:
        found = json.loads(result.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return None
    return found if isinstance(found, list) else None


def _verify_lock_installed(plan: _Plan) -> bool:
    return os.path.exists(plan.paths.python) and _problems_inside(plan, True, False) == []


def _networked(plan: _Plan, step: str, argv: Sequence[str]) -> None:
    log = _Log(plan.paths.log, step, plan.ctx.on_event)
    try:
        result = plan.ctx.networked(plan.ctx.consent, list(argv), ["pip:" + plan.spec.id], cwd=Path(plan.paths.env_dir), on_line=log.line)
    except fetch.FetchError as error:
        raise EnvError("consent" if error.code == "consent" else "pip_failed", "pip:" + plan.spec.id if error.code == "consent" else error.code, log.tail)
    if result.returncode != 0:
        raise EnvError("pip_failed", "exit %d" % result.returncode, log.tail)


def _run_pip_lock(plan: _Plan) -> None:
    lock_copy = plan.paths.env_dir + "/" + LOCK_COPY_NAME
    _atomic_write(lock_copy, plan.lock_bytes)                       # the exact bytes that were checked, kept as a record of what was installed
    _networked(plan, "pip_lock", [plan.paths.python, "-m", "pip", "install", "--require-hashes", "--only-binary=:all:", "--no-deps",
                                  "--disable-pip-version-check", "--no-input", "-r", lock_copy])


def _verify_source_installed(plan: _Plan) -> bool:
    return os.path.exists(plan.paths.python) and _problems_inside(plan, False, True) == []


def _run_pip_source(plan: _Plan) -> None:
    _networked(plan, "pip_source", [plan.paths.python, "-m", "pip", "install", "--no-deps", "--no-build-isolation", "--no-index",
                                    "--disable-pip-version-check", "--no-input", "-e", plan.paths.source])


# -- the native part

def _artifact_matches(plan: _Plan) -> List[str]:
    pattern = plan.spec.source.native_artifact
    directory, _, name = pattern.rpartition("/")
    base = plan.paths.source + ("/" + directory if directory else "")
    try:
        return sorted(n for n in os.listdir(base) if fnmatch.fnmatchcase(n, name))
    except OSError:
        return []


def _verify_native(plan: _Plan) -> bool:
    return bool(_artifact_matches(plan))


def _run_native(plan: _Plan) -> None:
    system = plan.ctx.system
    log = _Log(plan.paths.log, "native_build", plan.ctx.on_event)
    path = plan.paths.venv + "/bin" + os.pathsep + system.environ().get("PATH", "")      # the environment's own tools first: a missing one is the usual failure
    result = system.run(["bash", plan.spec.source.native_build], timeout=STEP_TIMEOUT_S["native_build"], cwd=plan.paths.source,
                        env={"PATH": path, "VIRTUAL_ENV": plan.paths.venv})
    log.result(result)
    if result is None or result.returncode != 0:
        raise EnvError("native_failed", "could not run" if result is None else "exit %d" % result.returncode, log.tail)
    if not _artifact_matches(plan):
        raise EnvError("native_failed", "nothing was built", log.tail)


# -- a native part built from a file shipped with the tool

_PACKAGES_CODE = "import sysconfig; print(sysconfig.get_paths()['platlib'])"


def _packages_dir(plan: _Plan) -> Optional[str]:
    """Where the environment keeps its installed packages, asked of the environment itself; None when it cannot say or it says somewhere outside."""
    result = _python(plan, _PACKAGES_CODE)
    if result is None or result.returncode != 0 or not result.stdout.strip():
        return None
    folder = result.stdout.strip().splitlines()[-1]
    inside = plan.paths.venv + "/"
    if ".." in folder.split("/") or not (folder + "/").startswith(inside):          # inside is absolute, so a relative answer fails this too
        return None
    return folder


def _native_part_input(plan: _Plan) -> str:
    native = plan.spec.native
    return "%s|%s|%s|%d.%d|%s" % (native.sha256, native.module, native.into, plan.minor[0], plan.minor[1], plan.lock_sha)


def _native_matches(folder: str, native: NativePart) -> List[str]:
    try:
        return sorted(n for n in os.listdir(folder) if fnmatch.fnmatchcase(n, native.artifact))
    except OSError:
        return []


def _verify_native_part(plan: _Plan) -> bool:
    packages = _packages_dir(plan)
    return packages is not None and bool(_native_matches(packages + "/" + plan.spec.native.into, plan.spec.native))


def _run_native_part(plan: _Plan) -> None:
    """Build the shipped source with Cython and the computer's C compiler, then put the one compiled file where the installed package looks for
    it. The source is checked against its pinned checksum first; the work happens in a folder of its own inside the environment, removed after."""
    native, system, ctx = plan.spec.native, plan.ctx.system, plan.ctx
    try:
        source = ctx.read_native(native)
    except OSError as exc:
        raise EnvError("native_changed", "%s: %s" % (native.file, exc.strerror or "cannot be read"))
    if sha256_bytes(source) != native.sha256:
        raise EnvError("native_changed", native.file)
    log = _Log(plan.paths.log, "native_build", ctx.on_event)
    work = plan.paths.env_dir + "/" + NATIVE_WORK
    shutil.rmtree(work, ignore_errors=True)
    try:
        os.makedirs(work, mode=0o700)
        _atomic_write("%s/%s.pyx" % (work, native.module), source)
        path = plan.paths.venv + "/bin" + os.pathsep + system.environ().get("PATH", "")      # the environment's own tools first, the computer's compiler after
        result = system.run([plan.paths.python, "-m", "Cython.Build.Cythonize", "-i", native.module + ".pyx"], timeout=STEP_TIMEOUT_S["native_build"],
                            cwd=work, env={"PATH": path, "VIRTUAL_ENV": plan.paths.venv, "PYTHONDONTWRITEBYTECODE": "1"})
        log.result(result)
        if result is None or result.returncode != 0:
            raise EnvError("native_failed", "could not run" if result is None else "exit %d" % result.returncode, log.tail)
        built = _native_matches(work, native)
        if not built:
            raise EnvError("native_failed", "nothing was built", log.tail)
        packages = _packages_dir(plan)
        if packages is None:
            raise EnvError("native_failed", "the environment did not say where its packages are", log.tail)
        target_dir = packages + "/" + native.into
        try:
            os.makedirs(target_dir, exist_ok=True)
            with open("%s/%s" % (work, built[0]), "rb") as handle:
                _atomic_write("%s/%s" % (target_dir, built[0]), handle.read())
        except OSError as exc:
            raise EnvError("write_failed", exc.strerror or type(exc).__name__)
    finally:
        shutil.rmtree(work, ignore_errors=True)


# -- the launcher

def _verify_wrapper(plan: _Plan) -> bool:
    return sha256_file(plan.paths.launcher) == sha256_bytes(launcher_text(plan.spec).encode())


def _run_wrapper(plan: _Plan) -> None:
    _atomic_write(plan.paths.launcher, launcher_text(plan.spec).encode())


# ---------------------------------------------------------------- the self-test

def _self_test(plan: _Plan) -> List[str]:
    """Run each probe in the finished environment. Returns the probes skipped because they need a graphics card the computer does not have."""
    system, ctx = plan.ctx.system, plan.ctx
    skipped: List[str] = []
    env = dict(OFFLINE_ENV)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    log = _Log(plan.paths.log, "self_test", ctx.on_event)
    if plan.spec.prelude:
        result = system.run([plan.paths.python, plan.paths.launcher, "platform"], timeout=STEP_TIMEOUT_S["probe"], cwd=plan.paths.env_dir, env=env)
        log.result(result)
        if result is None or result.returncode != 0:
            raise EnvError("launcher_failed", "could not run" if result is None else "exit %d" % result.returncode, log.tail)
    for probe in plan.spec.probes:
        if probe.needs_gpu and not ctx.gpu_ok:
            skipped.append(probe.id)
            ctx.on_event(Event("skipped", probe.id))
            continue
        result = system.run([plan.paths.python, "-c", probe.code], timeout=STEP_TIMEOUT_S["probe"], cwd=plan.paths.env_dir, env=env)
        log.result(result)
        if result is None or result.returncode != 0:
            raise EnvError("self_test_failed", probe.id, log.tail)
    return skipped


# ---------------------------------------------------------------- looking without changing anything

@dataclass(frozen=True)
class Inspection:
    state: str                       # "absent", "ready", "needs_work", "failed", "not_ours", "damaged", "newer", "not_buildable"
    env_dir: str = ""
    stale: Tuple[str, ...] = ()      # steps that would run again
    error: Optional[EnvError] = None


def inspect(spec: EnvSpec, ctx: Context) -> Inspection:
    """What a build would find, without changing anything (no folder made, no lock taken, no command that writes run)."""
    try:
        lock_bytes, lock_sha, pins, item, minor = _resolve(spec, ctx)
    except EnvError as error:
        return Inspection("not_buildable", "", (), error)
    fp = fingerprint(spec, lock_sha, item, minor)
    env_dir = "%s/%s" % (ctx.home.environments, env_dir_name(spec, fp))
    if not os.path.lexists(env_dir):
        return Inspection("absent", env_dir)
    record, why = read_record(env_dir)
    if record is None:
        return Inspection({"absent": "not_ours", "newer": "newer"}.get(why, "damaged"), env_dir)
    if record["id"] != spec.id or record["fingerprint"] != fp:
        return Inspection("damaged", env_dir)
    plan = _Plan(spec, ctx, EnvPaths(env_dir), lock_bytes, lock_sha, pins, item, minor, record)
    stale = tuple(s.id for s in _steps(plan) if not _is_done(plan, s))
    if stale:
        return Inspection("failed" if record.get("state") == "failed" else "needs_work", env_dir, stale)
    return Inspection("ready" if record.get("state") == "ready" else "needs_work", env_dir)
