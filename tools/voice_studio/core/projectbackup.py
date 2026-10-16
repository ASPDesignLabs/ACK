# SPDX-License-Identifier: GPL-3.0-or-later
"""Backup now (plan task VS-6.1, decision P17): one checked archive of the precious part of a project, kept outside it, and an additive way back.

**What it holds** (the precious kinds of plan P11, as core/areas.py lists them): the project's own record and consent note; the recordings (Freeform Studio's own rule for what of a take
is worth keeping: the raw audio, the notes and the person's edits and their earlier versions, not the decoded copies it can make again); the ACK recording packages in the project's
`incoming` folder; the record of training rounds and each round's settings file; the saved points that are kept (the chosen round's and the one before it, only when whole); and the
finished voice zip files. **It leaves out** the rebuildable and the disposable: the working files and training sets, older saved points, the trainer's logs, the test sounds, the tool's
programs and the starting voices, and every earlier backup.

**How it is written.** One plain `.tar` (nothing in it compresses: audio, saved points and zips are already dense), a new file every time, with a `MANIFEST.json` as its last member listing every
file's path, size and checksum. It is written under a `.partial` name, read back from the disk **in full** and compared with the manifest, and only then given its real name; a backup that
does not read back correctly is thrown away and says so. Nothing earlier is ever replaced, pruned or removed. A file that changed while it was being read stops the backup (nothing is
kept of it) so that what is in an archive is whole and as it was at one moment of reading, never a mixture.

**Where.** A folder the person names. It must not be inside any project. It is judged for room before anything is written, a folder that looks cloud-synced is flagged in Freeform Studio's
words, and the tool says whether it is on the same drive as the project (a copy on the same drive protects against a mistake, not against a drive that fails).

**The way back** is additive, like every restore in this tool: a file the project does not have is added; one that is already there and identical is skipped; one that is there and differs
is left exactly as it is and listed (the backup still holds its copy). A project that is not there at all is made again from the backup. Every name in an archive is checked against the few
shapes a backup holds before anything is written, so a damaged or hostile archive cannot write outside the project. Nothing in this file uses the network.

Decisions here; the words are in core/backup_flow.py and the text catalog.
"""
from __future__ import annotations

import errno
import hashlib
import io
import json
import os
import re
import stat
import tarfile
import time
import zlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from freeform_studio import backup as ffbackup
from freeform_studio.locking import exclusive
from freeform_studio.privacy import private_umask, sync_warning
from freeform_studio.storage import atomic_write_json

from . import ackimport, commands, rounds as rd, voicefile as vf
from .diskbudget import DEFAULT_TABLE, MIB, Level, check_step, floors_for
from .paths import DataHome, ProjectPaths
from .scratch import PROJECT_ID

SCHEMA = 1
MANIFEST = "MANIFEST.json"
STATE_FILE = "backups.json"                       # under the tool's state folder: when each project was last backed up, and where
LOCK = ".backup.lock"
STALE_LOCK_S = 6 * 3600
SLACK = 64 * MIB                                  # room beyond the archive's own size that a destination must have
REMOTE_MARGIN = 256 * MIB                         # on another drive than the project, what must be left after the archive
HEADER = 512                                      # a tar header and its padding unit
MAX_MEMBERS = 500_000
MAX_MEMBER_BYTES = 64 * 1024 ** 3
SMALL = 16 * MIB                                  # files up to this size are read whole, so what is hashed is exactly what is stored
CHUNK = 1 << 20
NAME_RE = re.compile(r"^ack-project-backup-(?P<project>[a-z0-9][a-z0-9-]{0,63})-(?P<stamp>\d{8}-\d{6})(?:-(?P<n>\d{1,3}))?\.tar\Z")
PARTS = ("record", "recordings", "packages", "rounds", "saved_points", "exports")      # what a backup holds, each with words in the text catalog under `backup.part.<id>`
PART_AREA = {"record": "record", "recordings": "recordings", "packages": "recordings", "rounds": "rounds", "saved_points": "rounds", "exports": "exports"}
LEFT_OUT = ("scratch", "listening", "older_saved_points", "saved_points")                # what a backup does not hold, with words under `backup.left_out.<id>`
ERROR_CODES = ("bad_destination", "inside_project", "not_a_folder", "nothing_to_back_up", "no_room", "busy", "write_failed", "changed", "not_read_back", "no_such_backup", "damaged",
               "not_a_backup", "unsafe", "job_running", "not_a_project", "exists_elsewhere")                                  # each has words in the text catalog
SAVED_POINT = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.=-]{0,119}\.ckpt\Z")
CONFIG_FILE = re.compile(r"round-\d{3,6}\.json\Z")


class BackupError(Exception):
    """`code` is one of ERROR_CODES; `detail` is a short fact for Show details, never the contents of a file; `problems` are lines to list under it."""

    def __init__(self, code: str, detail: str = "", problems: Sequence[str] = ()):
        super().__init__(code + (": " + detail if detail else ""))
        self.code = code
        self.detail = detail
        self.problems = tuple(problems)


# ---------------------------------------------------------------- which names a backup holds

@dataclass(frozen=True)
class Member:
    part: str                     # one of PARTS
    dest: str                     # where it belongs in the project


def _plain(name: str) -> Optional[List[str]]:
    """The parts of an archive name, or None when it could mean anything but a name inside the archive."""
    if not name or "\\" in name or "\0" in name or name.startswith("/") or len(name) > 400:
        return None
    parts = name.split("/")
    if any(p in ("", ".", "..") for p in parts):
        return None
    return parts


def member_target(paths: ProjectPaths, name: str) -> Optional[Member]:
    """Where a name inside an archive belongs in a project, or None when it is not one of the few shapes a backup holds. Works on the text alone, so a name that tries to leave
    the project (`..`, an absolute path, a backslash) is None and nothing is ever written for it."""
    parts = _plain(name)
    if parts is None:
        return None
    if parts[0] == "project" and len(parts) == 2:
        for here in (paths.project_json, paths.previous_json):                          # the file names are ProjectPaths', so there is one place that says them
            if parts[1] == os.path.basename(here):
                return Member("record", here)
        return None
    if parts[0] == "recordings":
        if len(parts) in (4, 5) and parts[1] == "takes" and ffbackup.TAKE_ID_RE.match(parts[2]) and ffbackup._allowed(parts[3:]):
            return Member("recordings", str(ffbackup.takes_dir(Path(paths.recordings), ackimport.LANGUAGE).joinpath(*parts[2:])))
        if len(parts) == 3 and parts[1] == "incoming" and ackimport.NAME_RE.match(parts[2]):
            return Member("packages", str(ackimport.incoming_dir(Path(paths.recordings)) / parts[2]))
        return None
    if parts[0] == "rounds":
        if len(parts) == 2:
            for here in (paths.rounds_file, paths.rounds_previous):
                if parts[1] == os.path.basename(here):
                    return Member("rounds", here)
            return None
        if len(parts) == 3 and parts[1] == "config" and CONFIG_FILE.match(parts[2]):
            return Member("rounds", paths.round_configs + "/" + parts[2])
        if len(parts) == 6 and parts[1:3] == ["run", "lightning_logs"] and re.fullmatch(r"version_\d{1,6}", parts[3]) and parts[4] == "checkpoints" and SAVED_POINT.match(parts[5]):
            return Member("saved_points", "%s/lightning_logs/%s/checkpoints/%s" % (paths.run, parts[3], parts[5]))
        return None
    if parts[0] == "exports" and len(parts) == 3 and commands.SAFE_NAME.match(parts[1]) and parts[2] == parts[1] + ".zip":
        return Member("exports", "%s/%s/%s" % (paths.exports, parts[1], parts[2]))
    return None


# ---------------------------------------------------------------- what would be held

@dataclass(frozen=True)
class Item:
    part: str
    name: str                     # inside the archive
    source: str
    size: int
    mtime_ns: int


@dataclass(frozen=True)
class Skipped:
    name: str
    reason: str                   # "not_whole", "not_a_file" or "unreadable"


def _regular(path: str) -> Optional[os.stat_result]:
    try:
        info = os.lstat(path)
    except OSError:
        return None
    return info if stat.S_ISREG(info.st_mode) else None


def _listdir(path: str) -> List[str]:
    try:
        return sorted(os.listdir(path))
    except OSError:
        return []


def collect(paths: ProjectPaths, record: Optional[rd.Record] = None, saved_points: bool = True) -> Tuple[Tuple[Item, ...], Tuple[Skipped, ...]]:
    """Everything a backup of this project holds, in a fixed order, and what was left out because it was not a plain whole file. Reads the disk (names, sizes, times); changes nothing.
    Raises rounds.RoundsError when the record of rounds is damaged: a backup is exactly when a damaged record must be noticed, not copied over a good one."""
    record = rd.load(paths) if record is None else record
    items: List[Item] = []
    skipped: List[Skipped] = []

    def add(part: str, name: str, source: str) -> None:
        info = _regular(source)
        if info is None:
            if os.path.lexists(source):
                skipped.append(Skipped(name, "not_a_file"))
            return
        items.append(Item(part, name, source, info.st_size, info.st_mtime_ns))

    for here in (paths.project_json, paths.previous_json):
        add("record", "project/" + os.path.basename(here), here)
    for source, name, _size, _mtime in ffbackup.collect(Path(paths.recordings), ackimport.LANGUAGE):
        add("recordings", "recordings/" + name, str(source))
    incoming = str(ackimport.incoming_dir(Path(paths.recordings)))
    for entry in _listdir(incoming):
        if ackimport.NAME_RE.match(entry):
            add("packages", "recordings/incoming/" + entry, incoming + "/" + entry)
    for here in (paths.rounds_file, paths.rounds_previous):
        add("rounds", "rounds/" + os.path.basename(here), here)
    for entry in _listdir(paths.round_configs):
        if CONFIG_FILE.match(entry):
            add("rounds", "rounds/config/" + entry, paths.round_configs + "/" + entry)
    if saved_points:
        for _number, f in rd.retention(paths, record).keep:
            name = "rounds/run/lightning_logs/version_%d/checkpoints/%s" % (f.version, f.name)
            target = member_target(paths, name)
            if target is None or target.dest != f.path:
                skipped.append(Skipped(name, "not_a_file"))
            elif not rd.checkpoint_complete(f.path):
                skipped.append(Skipped(name, "not_whole"))
            else:
                add("saved_points", name, f.path)
    for folder, zip_path, _size in vf.existing_voice_files(paths):
        add("exports", "exports/%s/%s.zip" % (folder, folder), zip_path)
    items.sort(key=lambda i: (PARTS.index(i.part), i.name))
    return tuple(items), tuple(skipped)


def fingerprint(items: Sequence[Item]) -> str:
    """Equal when the same files, of the same sizes, were last changed at the same times: what the nudge compares to say a project has changed since its last backup."""
    digest = hashlib.sha256()
    for item in items:
        digest.update(("%s\0%d\0%d\n" % (item.name, item.size, item.mtime_ns)).encode("utf-8"))
    return digest.hexdigest()


def archive_size(items: Sequence[Item]) -> int:
    """About how many bytes the archive will be: each file padded to the tar block with its header, the manifest, and the end marker. A slight over-estimate, never an under one."""
    body = sum(HEADER + ((i.size + HEADER - 1) // HEADER) * HEADER for i in items)
    manifest = 4096 + 400 * len(items)
    return body + HEADER + ((manifest + HEADER - 1) // HEADER) * HEADER + 2 * HEADER + 10 * HEADER


# ---------------------------------------------------------------- the plan

@dataclass(frozen=True)
class PartTotal:
    part: str
    files: int
    bytes: int


@dataclass(frozen=True)
class LeftOut:
    id: str                       # one of LEFT_OUT
    bytes: int


@dataclass(frozen=True)
class BackupPlan:
    project_id: str
    destination: str
    items: Tuple[Item, ...]
    parts: Tuple[PartTotal, ...]
    skipped: Tuple[Skipped, ...]
    left_out: Tuple[LeftOut, ...]
    source_bytes: int
    need_bytes: int
    free_bytes: Optional[int]
    room: Level
    same_drive: bool
    sync_warning: Optional[str]
    fingerprint: str
    saved_points: bool


def _tree_bytes(path: str) -> int:
    total = 0
    for base, _folders, files in os.walk(path, followlinks=False):
        for name in files:
            try:
                total += os.lstat(os.path.join(base, name)).st_size
            except OSError:
                pass
    return total


def check_destination(paths: ProjectPaths, home: DataHome, destination: str) -> str:
    """The destination as a clean absolute path, or a BackupError: it must be a folder (or a place one can be made), and not inside any project (a backup of a project is kept
    outside every project, so deleting a project can never take its backup with it)."""
    if not destination or not os.path.isabs(destination):
        raise BackupError("bad_destination", "the folder must be given in full")
    clean = os.path.normpath(destination)
    real = os.path.realpath(clean)
    for root in (paths.root, home.projects):
        if real == os.path.realpath(root) or real.startswith(os.path.realpath(root) + os.sep):
            raise BackupError("inside_project", clean)
    if os.path.lexists(clean) and (os.path.islink(clean) or not os.path.isdir(clean)):
        raise BackupError("not_a_folder", clean)
    probe = clean
    while not os.path.lexists(probe) and probe != os.path.dirname(probe):
        probe = os.path.dirname(probe)
    if not os.path.isdir(probe):
        raise BackupError("not_a_folder", probe)
    return clean


def nearest_existing(path: str) -> str:
    probe = path
    while not os.path.lexists(probe) and probe != os.path.dirname(probe):
        probe = os.path.dirname(probe)
    return probe


def same_drive(a: str, b: str) -> bool:
    try:
        return os.stat(a).st_dev == os.stat(b).st_dev
    except OSError:
        return False


def judge_room(free: Optional[int], need: int, on_project_drive: bool) -> Level:
    """On the project's own drive the usual floors apply (a backup must not push it below what the recorder needs). Anywhere else the archive and a margin must fit; there is no 'tight'."""
    if on_project_drive:
        return check_step(free, need, floors_for(DEFAULT_TABLE, holds_recordings=True))
    if free is None:
        return Level.ENOUGH
    return Level.ENOUGH if free >= need + REMOTE_MARGIN else Level.NOT_ENOUGH


def plan_backup(paths: ProjectPaths, home: DataHome, project_id: str, destination: str, free_bytes: Optional[int], record: Optional[rd.Record] = None,
                saved_points: bool = True) -> BackupPlan:
    """What a backup would do. Changes nothing. Refuses, with a code, when it cannot honestly be done: a destination inside a project or not a folder, or nothing to back up."""
    clean = check_destination(paths, home, destination)
    record = rd.load(paths) if record is None else record
    items, skipped = collect(paths, record, saved_points)
    if not items:
        raise BackupError("nothing_to_back_up")
    totals = {part: [0, 0] for part in PARTS}
    for item in items:
        totals[item.part][0] += 1
        totals[item.part][1] += item.size
    parts = tuple(PartTotal(part, files, size) for part, (files, size) in totals.items() if files)
    left: List[LeftOut] = []
    for area, folder in (("scratch", paths.default_scratch), ("listening", paths.listening)):
        size = _tree_bytes(folder) if os.path.isdir(folder) and not os.path.islink(folder) else 0
        if size:
            left.append(LeftOut(area, size))
    retention = rd.retention(paths, record)
    spare = sum(f.size for _n, f in retention.spare)
    if spare:
        left.append(LeftOut("older_saved_points", spare))
    if not saved_points:
        kept = sum(f.size for _n, f in retention.keep)
        if kept:
            left.append(LeftOut("saved_points", kept))
    need = archive_size(items) + SLACK
    probe = nearest_existing(clean)
    shared = same_drive(paths.root, probe)
    return BackupPlan(project_id, clean, items, parts, skipped, tuple(left), sum(i.size for i in items), need, free_bytes, judge_room(free_bytes, need, shared), shared,
                      sync_warning(Path(clean), "The backup folder"), fingerprint(items), saved_points)


# ---------------------------------------------------------------- making one

@dataclass(frozen=True)
class BackupMade:
    path: str
    name: str
    files: int
    source_bytes: int
    archive_bytes: int
    parts: Tuple[PartTotal, ...]
    skipped: Tuple[Skipped, ...]
    fingerprint: str
    created: str


class _Hashing:
    def __init__(self, handle, digest) -> None:
        self._handle, self._digest, self.count = handle, digest, 0

    def read(self, n: int = -1) -> bytes:
        data = self._handle.read(n)
        self._digest.update(data)
        self.count += len(data)
        return data


def _stamp_name(project_id: str, folder: str, now: datetime) -> str:
    base = "ack-project-backup-%s-%s" % (project_id, now.strftime("%Y%m%d-%H%M%S"))
    name, n = base + ".tar", 1
    while os.path.lexists(os.path.join(folder, name)) or os.path.lexists(os.path.join(folder, name + ".partial")):
        n += 1
        name = "%s-%d.tar" % (base, n)
    return name


def _open_regular(path: str) -> Tuple[int, os.stat_result]:
    """The file opened for reading without following a link, and what it is, so a file swapped for a link or a folder after it was listed is refused."""
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode):
            raise BackupError("changed", os.path.basename(path))
        return fd, info
    except BaseException:
        os.close(fd)
        raise


def _write_archive(partial: str, items: Sequence[Item], project_id: str, now: datetime, progress: Optional[Callable[[str, int, int], None]]) -> Dict[str, object]:
    entries: List[Dict[str, object]] = []
    total = sum(i.size for i in items)
    done = 0
    with open(partial, "xb") as out, tarfile.open(fileobj=out, mode="w") as tar:
        for item in items:
            try:
                fd, info = _open_regular(item.source)
            except OSError as exc:
                raise BackupError("changed", "%s (%s)" % (item.name, exc.strerror or type(exc).__name__))
            try:
                with os.fdopen(fd, "rb") as handle:
                    digest = hashlib.sha256()
                    tarinfo = tarfile.TarInfo(item.name)
                    tarinfo.mode, tarinfo.mtime, tarinfo.size = 0o600, info.st_mtime_ns // 1_000_000_000, info.st_size
                    if info.st_size <= SMALL:
                        data = handle.read()
                        if len(data) != info.st_size:
                            raise BackupError("changed", item.name)
                        digest.update(data)
                        tar.addfile(tarinfo, io.BytesIO(data))
                    else:
                        reader = _Hashing(handle, digest)
                        tar.addfile(tarinfo, reader)
                        if reader.count != info.st_size or handle.read(1):
                            raise BackupError("changed", item.name)
            except BackupError:
                raise
            except (tarfile.TarError, OSError) as exc:
                if isinstance(exc, OSError) and exc.errno in (errno.ENOSPC, errno.EDQUOT):
                    raise BackupError("no_room", item.name)
                now_on_disk = _regular(item.source)
                shrunk = now_on_disk is None or now_on_disk.st_size != info.st_size                  # a short read is a file that changed, not a drive that failed
                raise BackupError("changed" if shrunk or isinstance(exc, tarfile.TarError) else "write_failed", "%s (%s)" % (item.name, getattr(exc, "strerror", None) or type(exc).__name__))
            after = _regular(item.source)
            if after is None or after.st_size != info.st_size or after.st_mtime_ns != info.st_mtime_ns:
                raise BackupError("changed", item.name)                                    # it was written to while it was read: what was read is not one moment of it
            entries.append({"path": item.name, "part": item.part, "size": info.st_size, "sha256": digest.hexdigest()})
            done += info.st_size
            if progress is not None:
                progress(item.part, done, total)
        manifest = {"schema": SCHEMA, "app": "ack-voice-studio", "project": project_id, "created": now.isoformat(timespec="seconds"), "files": entries}
        blob = json.dumps(manifest, indent=1).encode("utf-8")
        tarinfo = tarfile.TarInfo(MANIFEST)
        tarinfo.size, tarinfo.mode, tarinfo.mtime = len(blob), 0o600, int(time.time())
        tar.addfile(tarinfo, io.BytesIO(blob))
    return manifest


def create(plan: BackupPlan, paths: ProjectPaths, now: Optional[datetime] = None, progress: Optional[Callable[[str, int, int], None]] = None) -> BackupMade:
    """Make the backup the plan described, from the files as they are now. Written as `.partial`, read back in full and compared, then given its real name; any failure removes the
    partial and raises BackupError, leaving every earlier backup and the project exactly as they were."""
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    items, skipped = collect(paths, None, plan.saved_points)
    if not items:
        raise BackupError("nothing_to_back_up")
    folder = plan.destination
    try:
        with private_umask():
            os.makedirs(folder, exist_ok=True)
    except OSError as exc:
        raise BackupError("write_failed", exc.strerror or type(exc).__name__)
    with exclusive(Path(folder) / LOCK, STALE_LOCK_S, lambda p: BackupError("busy", str(p))):
        name = _stamp_name(plan.project_id, folder, now)
        partial = os.path.join(folder, name + ".partial")
        final = os.path.join(folder, name)
        try:
            with private_umask():
                _write_archive(partial, items, plan.project_id, now, progress)
            problems, _manifest = verify(partial, check_names=True)
            if problems:
                raise BackupError("not_read_back", "", problems[:5])
            os.replace(partial, final)
        except BaseException as exc:
            try:
                os.unlink(partial)
            except OSError:
                pass
            if isinstance(exc, OSError):
                if exc.errno in (errno.ENOSPC, errno.EDQUOT):
                    raise BackupError("no_room", folder)
                raise BackupError("write_failed", exc.strerror or type(exc).__name__)
            raise
        totals = {part: [0, 0] for part in PARTS}
        for item in items:
            totals[item.part][0] += 1
            totals[item.part][1] += item.size
        parts = tuple(PartTotal(part, files, size) for part, (files, size) in totals.items() if files)
        made = BackupMade(final, name, len(items), sum(i.size for i in items), os.stat(final).st_size, parts, skipped, fingerprint(items), now.isoformat(timespec="seconds"))
        try:
            with private_umask():
                atomic_write_json(Path(final + ".json"), {"schema": SCHEMA, "project": plan.project_id, "created": made.created, "files": made.files, "source_bytes": made.source_bytes,
                                                           "archive_bytes": made.archive_bytes, "parts": {p.part: [p.files, p.bytes] for p in parts}, "fingerprint": made.fingerprint})
        except OSError:
            pass                                                                            # the archive is whole and listed by its name; only its note could not be written
        return made


# ---------------------------------------------------------------- checking one

def verify(path: str, check_names: bool = True) -> Tuple[List[str], Optional[Dict[str, object]]]:
    """Read the whole archive back. (problems, manifest): no problems means every file is exactly as the manifest says and every name is one a backup holds."""
    problems: List[str] = []
    manifest: Optional[Dict[str, object]] = None
    seen: Dict[str, Tuple[int, str]] = {}
    shape = ProjectPaths("/verify/project")
    try:
        with tarfile.open(path, "r:") as tar:
            count = 0
            for member in tar:
                count += 1
                if count > MAX_MEMBERS:
                    problems.append("it holds more files than a backup can")
                    break
                if not member.isfile():
                    problems.append("%s: not an ordinary file" % member.name[:120])
                    continue
                if member.size > MAX_MEMBER_BYTES:
                    problems.append("%s: larger than a backup holds" % member.name[:120])
                    continue
                handle = tar.extractfile(member)
                if handle is None:
                    problems.append("%s: cannot be read" % member.name[:120])
                    continue
                digest, total = hashlib.sha256(), 0
                blob = bytearray() if member.name == MANIFEST else None
                for chunk in iter(lambda: handle.read(CHUNK), b""):
                    digest.update(chunk)
                    total += len(chunk)
                    if blob is not None:
                        blob.extend(chunk)
                        if len(blob) > 64 * MIB:
                            break
                if member.name == MANIFEST:
                    try:
                        manifest = json.loads(bytes(blob).decode("utf-8"))
                    except (ValueError, UnicodeDecodeError, RecursionError):
                        problems.append("the manifest is damaged")
                elif member.name in seen:
                    problems.append("%s: appears more than once" % member.name[:120])
                else:
                    if check_names and member_target(shape, member.name) is None:
                        problems.append("%s: not something a backup holds" % member.name[:120])
                    seen[member.name] = (total, digest.hexdigest())
    except (tarfile.TarError, EOFError, OSError, ValueError, zlib.error) as exc:
        return ["it cannot be read all the way through (%s)" % type(exc).__name__], None
    if manifest is None:
        problems.append("it has no manifest, so it cannot be checked")
        return problems, None
    if not isinstance(manifest, dict) or manifest.get("schema") != SCHEMA or not isinstance(manifest.get("files"), list):
        problems.append("the manifest is not one this version reads")
        return problems, None
    if not isinstance(manifest.get("project"), str) or not PROJECT_ID.match(manifest["project"]):
        problems.append("the manifest does not name a project this tool can make")
    listed: Dict[str, dict] = {}
    for entry in manifest["files"]:
        if not isinstance(entry, dict) or not isinstance(entry.get("path"), str) or not isinstance(entry.get("size"), int) or not isinstance(entry.get("sha256"), str):
            problems.append("the manifest has an entry that is not understood")
        elif entry["path"] in listed:
            problems.append("%s: listed more than once" % entry["path"][:120])
        else:
            listed[entry["path"]] = entry
    for name, entry in listed.items():
        got = seen.get(name)
        if got is None:
            problems.append("%s: listed but missing" % name[:120])
        elif got != (entry["size"], entry["sha256"]):
            problems.append("%s: does not match its checksum" % name[:120])
    for name in seen:
        if name not in listed:
            problems.append("%s: in the archive but not in its manifest" % name[:120])
    return problems, manifest


# ---------------------------------------------------------------- listing

def list_backups(folder: str, project_id: Optional[str] = None) -> List[Dict[str, object]]:
    """The backups in a folder, newest first, from the names this tool gives and the small note beside each. Looks only."""
    found: List[Dict[str, object]] = []
    for entry in _listdir(folder):
        match = NAME_RE.match(entry)
        path = os.path.join(folder, entry)
        if not match or (project_id and match.group("project") != project_id) or _regular(path) is None:
            continue
        try:
            with open(path + ".json", encoding="utf-8") as handle:
                note = json.load(handle)
        except (OSError, ValueError, RecursionError):
            note = {}
        if not isinstance(note, dict):
            note = {}
        created = note.get("created") if isinstance(note.get("created"), str) else datetime.strptime(match.group("stamp"), "%Y%m%d-%H%M%S").isoformat(timespec="seconds")
        found.append({"name": entry, "path": path, "project": match.group("project"), "created": created, "size": os.lstat(path).st_size,
                      "files": note.get("files") if isinstance(note.get("files"), int) else None})
    return sorted(found, key=lambda b: (str(b["created"]), str(b["name"])), reverse=True)


# ---------------------------------------------------------------- when each project was last backed up (per computer, never in a backup)

def _state_path(home: DataHome) -> str:
    return home.state + "/" + STATE_FILE


def read_state(home: DataHome) -> Dict[str, dict]:
    try:
        with open(_state_path(home), encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError, RecursionError):
        return {}
    projects = data.get("projects") if isinstance(data, dict) else None
    if not isinstance(projects, dict):
        return {}
    return {k: v for k, v in projects.items() if isinstance(k, str) and PROJECT_ID.match(k) and isinstance(v, dict)}


def record_backup(home: DataHome, made: BackupMade, project_id: str, destination: str) -> None:
    """Note that this project was just backed up, where, and what it looked like. A note that cannot be written is not an error: the backup is whole."""
    state = read_state(home)
    state[project_id] = {"created": made.created, "file": made.name, "folder": destination, "fingerprint": made.fingerprint}
    try:
        with private_umask():
            os.makedirs(home.state, exist_ok=True)
            atomic_write_json(Path(_state_path(home)), {"schema": SCHEMA, "projects": state})
    except OSError:
        pass


NEVER, CHANGED, CURRENT = "never", "changed", "current"


@dataclass(frozen=True)
class Standing:
    state: str                    # NEVER, CHANGED or CURRENT
    last: str                     # when the last backup was made ("" for NEVER)
    folder: str


def standing(home: DataHome, paths: ProjectPaths, project_id: str, record: Optional[rd.Record] = None) -> Standing:
    """Whether this project has been backed up, and whether anything precious has changed since. Looks only. A project with nothing to back up yet reads as CURRENT (nothing to lose)."""
    items, _skipped = collect(paths, record, True)
    if not items:
        return Standing(CURRENT, "", "")
    last = read_state(home).get(project_id)
    if not last:
        return Standing(NEVER, "", "")
    created, folder = last.get("created"), last.get("folder")
    return Standing(CURRENT if last.get("fingerprint") == fingerprint(items) else CHANGED, created if isinstance(created, str) else "", folder if isinstance(folder, str) else "")


# ---------------------------------------------------------------- the way back (additive)

@dataclass(frozen=True)
class Planned:
    name: str
    part: str
    size: int
    dest: str
    sha256: str


@dataclass(frozen=True)
class RestorePlan:
    archive: str
    project_id: str
    root: str
    new_project: bool                 # the project is not there at all: it is made again from the backup
    created: str                      # when the backup was made
    add: Tuple[Planned, ...]
    same: int                         # already there and identical
    conflicts: Tuple[str, ...]        # already there and different: left exactly as they are
    bytes_to_add: int
    free_bytes: Optional[int]
    room: Level


@dataclass(frozen=True)
class RestoreResult:
    added: int
    bytes: int
    conflicts: Tuple[str, ...]        # found different at the moment of writing, so left alone
    failed: Tuple[Tuple[str, str], ...]   # (name, the system's reason): not added


def _sha256_of(path: str) -> Optional[str]:
    digest = hashlib.sha256()
    try:
        with open(path, "rb") as handle:
            for chunk in iter(lambda: handle.read(CHUNK), b""):
                digest.update(chunk)
    except OSError:
        return None
    return digest.hexdigest()


def plan_restore(home: DataHome, archive: str, free_bytes: Optional[int]) -> RestorePlan:
    """What putting a backup back would do. Reads the whole archive and the project's files; changes nothing. Refuses, with a code, an archive that is not whole, one that is not a
    backup of this tool, a project folder that is a link or not a project, and a project with a task running."""
    if _regular(archive) is None:
        raise BackupError("no_such_backup", os.path.basename(archive))
    problems, manifest = verify(archive, check_names=True)
    if problems or manifest is None:
        raise BackupError("damaged", "", problems[:5])
    project_id = str(manifest["project"])
    paths = ProjectPaths(home.projects + "/" + project_id)
    entries = [e for e in manifest["files"] if isinstance(e, dict)]                          # verify() has already shown each is well formed
    if os.path.islink(paths.root) or (os.path.lexists(paths.root) and not os.path.isdir(paths.root)):
        raise BackupError("not_a_project", project_id)
    new_project = not os.path.lexists(paths.root) or (os.path.isdir(paths.root) and not _listdir(paths.root))        # an empty folder is what a restore that stopped at its first file leaves
    if new_project:
        if not any(e["path"] == "project/" + os.path.basename(paths.project_json) for e in entries):
            raise BackupError("not_a_backup", "it holds no project record")
    else:
        if _regular(paths.project_json) is None:
            raise BackupError("not_a_project", project_id)
        from . import jobs                                                                      # not at the top: only a restore into a project asks what is running
        if any(j.spec.project == project_id and j.status in jobs.ACTIVE for j in jobs.list_jobs(home.jobs).jobs):
            raise BackupError("job_running", project_id)
    add: List[Planned] = []
    conflicts: List[str] = []
    same = 0
    for entry in entries:
        target = member_target(paths, entry["path"])
        if target is None:
            raise BackupError("unsafe", entry["path"][:120])
        info = None if new_project else (os.lstat(target.dest) if os.path.lexists(target.dest) else None)
        if info is None:
            add.append(Planned(entry["path"], target.part, entry["size"], target.dest, entry["sha256"]))
        elif stat.S_ISREG(info.st_mode) and info.st_size == entry["size"] and _sha256_of(target.dest) == entry["sha256"]:
            same += 1
        else:
            conflicts.append(entry["path"])
    add.sort(key=lambda p: (PARTS.index(p.part), p.name))
    to_add = sum(p.size for p in add)
    need = to_add + SLACK
    room = judge_room(free_bytes, need, True) if add else Level.ENOUGH
    created = manifest.get("created")
    return RestorePlan(archive, project_id, paths.root, new_project, created if isinstance(created, str) else "", tuple(add), same, tuple(conflicts), to_add, free_bytes, room)


def restore(home: DataHome, plan: RestorePlan, progress: Optional[Callable[[str, int, int], None]] = None) -> RestoreResult:
    """Do what the plan said, and no more: add the files that are not there. A file that has appeared since is left alone and counted as a conflict. The project's record is written first, so
    a restore that stops half way leaves a project that is listed and can be restored again (adding what is still missing). The archive is read as it is, so a change to it since the plan stops this."""
    paths = ProjectPaths(plan.root)
    if plan.room is Level.NOT_ENOUGH:
        raise BackupError("no_room", plan.root)
    again = plan_restore(home, plan.archive, plan.free_bytes)
    if again.add != plan.add or again.conflicts != plan.conflicts or again.new_project != plan.new_project:
        raise BackupError("changed", plan.project_id)
    added = 0
    written = 0
    conflicts: List[str] = []
    failed: List[Tuple[str, str]] = []
    total = plan.bytes_to_add
    try:
        with private_umask():
            os.makedirs(home.projects, exist_ok=True)
            with tarfile.open(plan.archive, "r:") as tar:
                members = {m.name: m for m in tar if m.isfile()}

                def put(item: Planned) -> None:
                    nonlocal added, written
                    member = members.get(item.name)
                    if member is None:
                        failed.append((item.name, "it is not in the archive any more"))
                        return
                    try:
                        outcome = _write_one(tar, member, item)
                    except OSError as exc:
                        failed.append((item.name, exc.strerror or type(exc).__name__))
                        return
                    if outcome == "added":
                        added += 1
                        written += item.size
                    elif outcome == "there":
                        conflicts.append(item.name)
                    else:
                        failed.append((item.name, outcome))
                    if progress is not None:
                        progress(item.part, written, total)

                for item in (i for i in plan.add if i.part == "record"):                 # first, outside the lock: the project is listed from here on, even if the rest stops
                    put(item)
                with rd.exclusive(paths):
                    for item in (i for i in plan.add if i.part != "record"):
                        put(item)
    except (tarfile.TarError, EOFError, zlib.error) as exc:
        raise BackupError("damaged", type(exc).__name__)
    except rd.RoundsError as exc:
        raise BackupError("busy", exc.code)
    except OSError as exc:
        raise BackupError("write_failed", exc.strerror or type(exc).__name__)
    return RestoreResult(added, written, tuple(conflicts), tuple(failed))


def _write_one(tar: tarfile.TarFile, member: tarfile.TarInfo, item: Planned) -> str:
    """Put one file in place without ever replacing one: written beside it, checked against the manifest as it is written, then linked into its name (which fails if the name has appeared
    meanwhile). "added", "there" (a file is in the way, left alone), or a short reason it was not added."""
    folder = os.path.dirname(item.dest)
    os.makedirs(folder, mode=0o700, exist_ok=True)
    if os.path.lexists(item.dest):
        return "there"
    source = tar.extractfile(member)
    if source is None:
        return "it cannot be read from the archive"
    fd, temp = _temp_in(folder)
    try:
        digest, count = hashlib.sha256(), 0
        with os.fdopen(fd, "wb") as out:
            for chunk in iter(lambda: source.read(CHUNK), b""):
                digest.update(chunk)
                count += len(chunk)
                out.write(chunk)
            out.flush()
            os.fsync(out.fileno())
        if count != item.size or digest.hexdigest() != item.sha256:
            return "it did not read back as the backup says"
        try:
            os.link(temp, item.dest)
        except FileExistsError:
            return "there"
        except OSError as exc:
            if exc.errno not in (errno.EPERM, errno.ENOTSUP, errno.EOPNOTSUPP, errno.EXDEV, errno.EMLINK, errno.ENOSYS):
                raise
            if os.path.lexists(item.dest):                    # a file system with no links (a Windows folder): the check and the move are as close together as they can be
                return "there"
            os.replace(temp, item.dest)
        return "added"
    finally:
        try:
            os.unlink(temp)
        except OSError:
            pass


def _temp_in(folder: str) -> Tuple[int, str]:
    import tempfile
    return tempfile.mkstemp(prefix=".restore-", suffix=".part", dir=folder)
