# SPDX-License-Identifier: GPL-3.0-or-later
"""Bringing in recordings from a Freeform Studio folder that was set up by hand before (plan task VS-3.4, decision D13).

The order is fixed and every step but the last two only reads:

    survey      look at what is there and count it                                 (reads)
    room        will the backup and the copy fit, with the usual floors left       (reads)
    backup      a checked backup of the old recordings, read back before it counts (writes only into the backup folder)
    preview     what copying would add, what is already there, what differs        (reads)
    copy        put the backup's recordings into the project, adding only          (writes only into the project)
    verify      every file in the backup is in the project, byte for byte          (reads)

The old folder is never changed: no step writes into it, moves anything out of it or deletes from it. The copy is made *from the checked backup*, so
what lands in the project is exactly what was checked. Copying only ever adds (Freeform Studio's own restore): a recording the project already has is
skipped when identical, and when a file differs the old copy is kept beside it in `restored-conflicts/`, so nothing is lost either way. Old backups in the
folder are never pruned by this step.

Not done here, on purpose: the old datasets and trained checkpoints are listed by core/legacy.py for the person to see, but are not copied (a
checkpoint is a gigabyte each and where rounds keep them is decided with the rounds engine), and the old training environment is reused only when a lock
exists to compare it against (plan task VS-0.2).
"""
from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Tuple

from freeform_studio import backup as ffbackup
from freeform_studio.privacy import private_umask, sync_warning

from .diskbudget import DEFAULT_TABLE, Level, SizeTable, check_step, floors_for
from .text import size_text

ERROR_CODES = ("no_recordings", "same_place", "no_room", "backup_failed", "copy_failed", "verify_failed")       # each has words in the text catalog
DECODED_BYTES_PER_HOUR = 48000 * 2 * 3600       # freeform_studio/audio.py: the decoded copy is 48 kHz, mono, 16-bit
BACKUP_SLACK = 50 * 1024 * 1024                 # backup.create wants this much more than 1.05 times the files
CHUNK = 1 << 20


class CopyInError(Exception):
    """`code` is one of ERROR_CODES; `detail` is Freeform Studio's own sentence or a short fact for Show details."""

    def __init__(self, code: str, detail: str = "", problems: Tuple[str, ...] = ()):
        super().__init__(code + (": " + detail if detail else ""))
        self.code = code
        self.detail = detail
        self.problems = tuple(problems)


# ---------------------------------------------------------------- 1. looking

@dataclass(frozen=True)
class OldRecordings:
    output_dir: str
    code: str                       # the language folder, "en-US"
    takes: int
    files: int                      # what a backup holds
    bytes: int
    hours: float                    # total length, from each recording's own notes (0 where they do not say)
    unfinished: int                 # recordings not finished being listened to; they are copied as they are


def _read_duration(path: Path) -> float:
    import json
    try:
        value = json.loads(path.read_text(encoding="utf-8")).get("duration")
    except (OSError, ValueError, AttributeError):
        return 0.0
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0 else 0.0


def _status(path: Path) -> str:
    import json
    try:
        return str(json.loads(path.read_text(encoding="utf-8")).get("status", ""))
    except (OSError, ValueError, AttributeError):
        return ""


def survey(output_dir: str) -> List[OldRecordings]:
    """One entry for every language folder under `<output>/_freeform` that holds recordings. Reads only."""
    root = Path(output_dir) / "_freeform"
    found: List[OldRecordings] = []
    try:
        codes = sorted(p.name for p in root.iterdir() if p.is_dir())            # a language folder that is a link is followed: it is only read
    except OSError:
        return found
    for code in codes:
        files = ffbackup.collect(Path(output_dir), code)
        if not files:
            continue
        take_names = sorted({name.split("/")[1] for _, name, _, _ in files})
        takes_root = ffbackup.takes_dir(Path(output_dir), code)
        seconds = sum(_read_duration(takes_root / t / "take.json") for t in take_names)
        unfinished = sum(1 for t in take_names if _status(takes_root / t / "take.json") != "ready")
        found.append(OldRecordings(str(output_dir), code, len(take_names), len(files), sum(size for _, _, size, _ in files), round(seconds / 3600.0, 3), unfinished))
    return found


def found_line(found: OldRecordings, catalog) -> str:
    """"Found 12 recordings (1.2 GB, about 3.5 hours) in /home/…": what the person is shown before anything is done."""
    return catalog.count("copyin.found", found.takes, size=size_text(found.bytes), hours=("%.1f" % found.hours).rstrip("0").rstrip(".") or "0", where=found.output_dir)


def same_place(source: str, destination: str) -> bool:
    """True when the two folders are the same, or one is inside the other: copying then would feed a folder into itself."""
    a, b = os.path.realpath(source), os.path.realpath(destination)
    return a == b or a.startswith(b.rstrip("/") + "/") or b.startswith(a.rstrip("/") + "/")


def backup_warning(backup_dir: str) -> Optional[str]:
    """Freeform Studio's sentence when the folder looks cloud-synced, else None. The recordings are personal data."""
    return sync_warning(backup_dir, "The backup folder")


# ---------------------------------------------------------------- 2. room

@dataclass(frozen=True)
class RoomVerdict:
    level: Level
    need: Dict[str, int]                        # per place: "backup", "project" (one key, "project", when they share a drive)
    free: Dict[str, Optional[int]]
    short_by: Dict[str, int]


def room_check(found: OldRecordings, free: Mapping[str, Optional[int]], *, same_drive: bool = False, table: SizeTable = DEFAULT_TABLE) -> RoomVerdict:
    """Will the backup and the copy fit? The backup needs what the recordings weigh (a little more, as Freeform Studio asks); the project needs them again plus the decoded
    copies it rebuilds. `free` has "backup" and "project"; with `same_drive` the two are judged together on "project". A place that cannot be read is not judged."""
    backup_need = int(found.bytes * 1.05) + BACKUP_SLACK
    project_need = found.bytes + int(found.hours * DECODED_BYTES_PER_HOUR)
    needs = {"project": backup_need + project_need} if same_drive else {"backup": backup_need, "project": project_need}
    worst, short = Level.ENOUGH, {}
    for place, need in needs.items():
        have = free.get(place)
        floors = floors_for(table, holds_recordings=(place == "project"))
        level = check_step(have, need, floors)
        short[place] = 0 if have is None else max(0, need + floors.low - have)
        if level is Level.NOT_ENOUGH or (level is Level.TIGHT and worst is Level.ENOUGH):
            worst = level
    return RoomVerdict(worst, needs, {p: free.get(p) for p in needs}, short)


def require_room(verdict: RoomVerdict) -> None:
    """The step does not start when the room is not enough (nothing has been written yet). A tight fit goes on after the person has been told."""
    if verdict.level is Level.NOT_ENOUGH:
        raise CopyInError("no_room", ", ".join("%s: %d bytes short" % (place, short) for place, short in sorted(verdict.short_by.items()) if short))


# ---------------------------------------------------------------- 3. the checked backup

@dataclass(frozen=True)
class BackupInfo:
    path: str
    takes: int
    files: int
    archive_bytes: int


def make_backup(found: OldRecordings, backup_dir: str) -> BackupInfo:
    """A fresh backup of the old recordings, read back and checked twice (once by Freeform Studio as it is made, once here). Nothing is pruned, and nothing is
    written into the old folder."""
    with private_umask():
        try:
            made = ffbackup.create(Path(found.output_dir), found.code, Path(backup_dir), force=True, keep=0)
        except (ffbackup.BackupError, OSError) as exc:
            raise CopyInError("backup_failed", str(exc))
    if made.path is None:
        raise CopyInError("no_recordings", made.reason)
    problems, _manifest = ffbackup.verify(made.path)
    if problems:
        raise CopyInError("backup_failed", "the backup did not read back correctly", tuple(problems[:5]))
    return BackupInfo(str(made.path), made.takes, made.files, made.archive_bytes)


# ---------------------------------------------------------------- 4. looking at what copying would do, 5. copying, 6. checking

@dataclass(frozen=True)
class CopyPlan:
    to_add: int                         # files the project does not have
    same: int                           # files it already has, identical
    differ: int                         # files it has that are different: the old copy is kept beside them
    takes: Tuple[str, ...]              # recordings that gain files (their decoded audio needs rebuilding afterwards)


def preview_copy(archive: str, project_recordings: str, code: str) -> CopyPlan:
    try:
        report = ffbackup.restore(Path(archive), Path(project_recordings), code, dry_run=True)
    except (ffbackup.BackupError, OSError) as exc:
        raise CopyInError("copy_failed", str(exc))
    return CopyPlan(len(report.restored), len(report.same), len(report.conflicts), tuple(report.takes))


@dataclass(frozen=True)
class CopyResult:
    added: int
    same: int
    kept_aside: int                     # files that differed: the old copy is in `aside_dir`
    aside_dir: Optional[str]
    takes: Tuple[str, ...]              # recordings that gained files; run the repair job for these
    checked: int                        # files in the backup, each found byte for byte in the project (or beside it)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(CHUNK), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_copy(archive: str, project_recordings: str, code: str, aside_dir: Optional[str]) -> int:
    """Every file the backup lists is in the project with the same checksum (or, where the project already had a different one, beside it). Returns how many;
    raises CopyInError("verify_failed") listing what is missing or different."""
    problems, manifest = ffbackup.verify(Path(archive))
    if problems or manifest is None:
        raise CopyInError("verify_failed", "the backup cannot be read back", tuple(problems[:5]))
    takes_root = ffbackup.takes_dir(Path(project_recordings), code)
    aside = Path(aside_dir) if aside_dir else None
    bad: List[str] = []
    for entry in manifest["files"]:
        parts = entry["path"].split("/")[1:]
        placed = takes_root.joinpath(*parts)
        good = placed.is_file() and _sha256(placed) == entry["sha256"]
        if not good and aside is not None:
            beside = aside.joinpath(*parts)
            good = beside.is_file() and _sha256(beside) == entry["sha256"]
        if not good:
            bad.append(entry["path"])
    if bad:
        raise CopyInError("verify_failed", "%d file(s) are missing or different" % len(bad), tuple(bad[:5]))
    return len(manifest["files"])


def copy_in(found: OldRecordings, archive: str, project_recordings: str) -> CopyResult:
    """Put the checked backup's recordings into the project (adding only), then check them. The caller has shown `preview_copy` and been told yes."""
    if same_place(found.output_dir, project_recordings):
        raise CopyInError("same_place", os.path.basename(project_recordings.rstrip("/")))
    with private_umask():
        try:
            report = ffbackup.restore(Path(archive), Path(project_recordings), found.code)
        except (ffbackup.BackupError, OSError) as exc:
            raise CopyInError("copy_failed", str(exc))
    checked = verify_copy(archive, project_recordings, found.code, report.conflicts_dir)
    return CopyResult(len(report.restored), len(report.same), len(report.conflicts), report.conflicts_dir, tuple(report.takes), checked)
