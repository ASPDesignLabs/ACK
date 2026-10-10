# SPDX-License-Identifier: GPL-3.0-or-later
"""Bringing an ACK recording package into a project (plan task VS-2.4).

What the person chooses is only ever read. It is copied into the project's own `incoming` folder (the same place Freeform Studio's Review page uses, which
no backup sweeps up and no program deletes), the copy is checked byte for byte against the original, and everything after that is done from the copy:
every audio file is checked against its checksum, the plan is made, and only then are the recordings added. A package that fails a check changes
nothing except the copy this step made, which it removes (it is ours, and the original is untouched). Adding is additive and can be repeated: a session
that is already in is recognised and skipped.

The checking and adding are Freeform Studio's own (freeform_studio/ack_package.py, ack_import.py) so the two cannot disagree; this file adds the copy, the
room check, the plain data the screens need, and one error vocabulary. Nothing here uses the network.
"""
from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional, Sequence, Tuple

from freeform_studio.ack_import import Created, ImportProblem, NotEnoughRoom, Plan, apply_import, make_plan
from freeform_studio.ack_package import PackageError, open_package
from freeform_studio.config import Config
from freeform_studio.health import free_mb
from freeform_studio.privacy import private_umask, sync_warning

NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._ -]{0,100}\.zip$")      # the same rule the Review page uses for a package in the incoming folder
ZIP_STARTS = (b"PK\x03\x04", b"PK\x05\x06")
MAX_PACKAGE_BYTES = 4 * 1024 ** 3                                        # more than a package from ACK can be
CHUNK = 1 << 20
LANGUAGE = "en-US"                                                       # the folder name Freeform Studio files recordings under; one language for now
ERROR_CODES = ("not_a_file", "not_a_zip", "too_big", "unreadable", "no_room", "copy_failed", "package", "problem")      # each has words in the text catalog
Progress = Callable[[str, int, int], None]                                # (stage, done, total): stage is "copy" or "check"


class AckImportError(Exception):
    """`code` is one of ERROR_CODES. `detail` is Freeform Studio's own sentence or a short fact; `problems` are the lines it lists under it."""

    def __init__(self, code: str, detail: str = "", problems: Sequence[str] = ()):
        super().__init__(code + (": " + detail if detail else ""))
        self.code = code
        self.detail = detail
        self.problems = tuple(problems)


@dataclass(frozen=True)
class SessionInfo:
    id: str
    mode: str                           # "script" or "free"
    label: str
    clips: int                          # clips in a script session; 0 for free speech
    seconds: float
    state: str                          # "new", "already" (in the project), "aborted" (an earlier add was cut short; it will be redone)
    take_id: Optional[str]              # the recording it became, when it is already in


@dataclass(frozen=True)
class PackageSummary:
    name: str                           # the copy's name in the project
    created: str
    app_version: str
    sessions: Tuple[SessionInfo, ...]
    audio_files: int
    package_bytes: int
    warnings: Tuple[str, ...]           # Freeform Studio's own notes about the package, in English
    to_add: int                         # sessions that will be added
    minutes_total: float
    minutes_new: float
    need_mb: float                      # what adding needs, with the decoded copies
    free_mb: float
    min_free_mb: float
    enough_room: bool
    sync_warning: Optional[str]         # the recordings folder looks cloud-synced, in Freeform Studio's words


@dataclass
class Prepared:
    source: str                         # what the person chose; never changed
    copy: Path                          # the checked copy inside the project
    copy_was_new: bool
    plan: Plan
    summary: PackageSummary


# ---------------------------------------------------------------- the copy

def safe_name(source: str) -> str:
    """A file name that the incoming folder accepts, as close to the original as it can be."""
    base = os.path.basename(source.rstrip("/")) or "package.zip"
    stem = base[:-4] if base.lower().endswith(".zip") else base
    cleaned = re.sub(r"[^A-Za-z0-9._ -]+", "-", stem).strip(" .-_") or "ack-package"
    candidate = cleaned[:96] + ".zip"
    return candidate if NAME_RE.match(candidate) else "ack-package.zip"


def incoming_dir(recordings: Path, code: str = LANGUAGE) -> Path:
    return Config(output_dir=Path(recordings), code=code).root / "incoming"


def _sha256(path: Path) -> Tuple[str, int]:
    digest, size = hashlib.sha256(), 0
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(CHUNK), b""):
            digest.update(block)
            size += len(block)
    return digest.hexdigest(), size


def _free_mb(path: Path) -> float:
    probe = Path(path)
    while not probe.exists() and probe != probe.parent:
        probe = probe.parent
    return free_mb(probe)


def _copy_in(source: Path, folder: Path, progress: Optional[Progress]) -> Tuple[Path, bool]:
    """Copy `source` into `folder` under a safe name. A copy already there that is byte for byte the same is reused; a different file of that name is
    never replaced, the new copy gets a numbered name. Returns (the copy, whether this call made it)."""
    size = source.stat().st_size
    if size > MAX_PACKAGE_BYTES:
        raise AckImportError("too_big", str(size))
    with open(source, "rb") as handle:
        head = handle.read(4)
    if head not in ZIP_STARTS:
        raise AckImportError("not_a_zip")
    wanted = safe_name(str(source))
    stem = wanted[:-4]
    source_sha, _ = _sha256(source)
    folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    n = 1
    while True:
        name = wanted if n == 1 else "%s-%d.zip" % (stem, n)
        final = folder / name
        if not final.exists() and not final.is_symlink():
            break
        if final.is_file() and not final.is_symlink() and _sha256(final)[0] == source_sha:
            return final, False                                           # the very same package is already here
        n += 1
        if n > 99:
            raise AckImportError("copy_failed", "too many packages with the same name")
    room = _free_mb(folder)
    min_free = Config(output_dir=folder).min_free_mb
    if room < min_free + size / (1024 * 1024):
        raise AckImportError("no_room", "%.0f MB free, %.0f MB needed" % (room, min_free + size / (1024 * 1024)))
    part = final.with_name(final.name + ".part")
    digest, done = hashlib.sha256(), 0
    try:
        fd = os.open(str(part), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with open(source, "rb") as src, os.fdopen(fd, "wb") as out:
            for block in iter(lambda: src.read(CHUNK), b""):
                out.write(block)
                digest.update(block)
                done += len(block)
                if progress:
                    progress("copy", done, size)
            out.flush()
            os.fsync(out.fileno())
        if done != size or digest.hexdigest() != source_sha or _sha256(part)[0] != source_sha:
            raise AckImportError("copy_failed", "the copy does not match the original")
        os.replace(str(part), str(final))
    except OSError as exc:
        _remove_quietly(part)
        raise AckImportError("copy_failed", exc.strerror or type(exc).__name__)
    except AckImportError:
        _remove_quietly(part)
        raise
    return final, True


def _remove_quietly(path: Path) -> None:
    try:
        path.unlink()
    except OSError:
        pass


# ---------------------------------------------------------------- looking, then adding

def _summarise(copy: Path, pkg, plan: Plan) -> PackageSummary:
    info = pkg.summary()
    sessions = tuple(SessionInfo(s.id, s.mode, s.label, s.clips, s.seconds, s.state, s.take_id) for s in plan.sessions)
    new = [s for s in plan.sessions if s.state in ("new", "aborted")]
    return PackageSummary(
        name=copy.name, created=info["created"], app_version=info["app_version"], sessions=sessions, audio_files=len(pkg.wav), package_bytes=info["bytes"],
        warnings=tuple(pkg.warnings), to_add=len(new), minutes_total=round(sum(s.seconds for s in plan.sessions) / 60, 2),
        minutes_new=round(sum(s.seconds for s in new) / 60, 2), need_mb=round(plan.need_mb, 1), free_mb=round(plan.free_mb, 1),
        min_free_mb=float(plan.min_free_mb), enough_room=plan.enough_room, sync_warning=sync_warning(plan.output, "Your recordings folder"))


def prepare(source: str, recordings: Path, code: str = LANGUAGE, progress: Optional[Progress] = None, only: Optional[Sequence[str]] = None) -> Prepared:
    """Copy the chosen package into the project, check it completely and make the plan. Adds no recording. Raises AckImportError.

    If the package fails a check, the copy this call made is removed (the original is untouched and nothing else was written)."""
    source_path = Path(source).expanduser()
    try:
        is_file = source_path.is_file()
    except OSError as exc:
        raise AckImportError("unreadable", exc.strerror or type(exc).__name__)
    if not is_file:
        raise AckImportError("not_a_file", source_path.name)
    recordings = Path(recordings)
    with private_umask():
        try:
            copy, was_new = _copy_in(source_path, incoming_dir(recordings, code), progress)
        except OSError as exc:
            raise AckImportError("unreadable", exc.strerror or type(exc).__name__)
        try:
            pkg = open_package(copy, progress=(lambda done, total: progress("check", done, total)) if progress else None)
            plan = make_plan(pkg, recordings, code, list(only) if only else None)
        except PackageError as exc:
            if was_new:
                _remove_quietly(copy)
            raise AckImportError("package", str(exc), exc.problems)
        except ImportProblem as exc:
            if was_new:
                _remove_quietly(copy)
            raise AckImportError("problem", str(exc))
    return Prepared(str(source_path), copy, was_new, plan, _summarise(copy, pkg, plan))


def add(prepared: Prepared, progress: Optional[Callable[[str], None]] = None) -> List[Created]:
    """Add the recordings the plan lists. Only ever adds; a session already in is skipped. If there is not room, nothing is written."""
    with private_umask():
        try:
            return apply_import(prepared.plan, progress)
        except NotEnoughRoom as exc:
            raise AckImportError("no_room", str(exc))
        except ImportProblem as exc:
            raise AckImportError("problem", str(exc))
        except OSError as exc:
            raise AckImportError("copy_failed", exc.strerror or type(exc).__name__)
