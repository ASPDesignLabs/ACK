# SPDX-License-Identifier: GPL-3.0-or-later
"""Uninstall (plan task VS-6.3, decision P19): take the tool's programs and downloaded files off the disk, and nothing else.

**What it removes**, all of it made by this tool and made again by setup: the Python environments in `tool/environments` (every set of programs and every older copy of one, but only a folder
that carries this tool's own record, core/envbuild.py), and the downloaded files in `tool/downloads` (the programs' archives and the listening model). **What it never touches:** a project, a
recording, a round, a finished voice file, a backup (`core/areas.py` marks these precious, and removal is only ever done to what that list calls the tool's own, kind `TOOL`), the starting voices
(`tool/downloads/voices`: a kept copy that may not be downloadable again, plan D27), and the small notes in `state/` (what was agreed to, the window's choices). A folder there that is not one
of ours is counted and left alone, never listed as something to remove.

**What it cannot do for itself:** remove the folder this program runs from (the tool's own files, `ack-tools` after the one command), and take the entry out of the applications list or the
Windows Start menu (the window's own `--remove-launcher` does that, including the Windows side and the `sudo` line that WSL needs). The front says both and gives the commands.

It looks first (`plan`) and removes only what was shown (`remove`): the list is worked out again just before and a changed list removes nothing. Never while any task is running (a training
round runs from the programs it began with). A link is removed as a link and never followed.

Plain Python with no words; the words are in the text catalog under `uninstall.*`.
"""
from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from typing import Callable, List, Optional, Sequence, Tuple

from . import areas, envbuild, jobs, profiles
from .diskbudget import Kind
from .envspec import EnvSpec
from .paths import DataHome
from .project import list_projects
from .refresh import COPY_NAME

PROGRAMS, DOWNLOADS = "programs", "downloads"
KINDS = (PROGRAMS, DOWNLOADS)                   # each has words in the text catalog under uninstall.kind.<id>
ERROR_CODES = ("job_running", "changed")        # each has words in the text catalog
KEPT_VOICES = "voices"                          # the folder under tool/downloads that is never removed
KEPT = ("backups", "voices", "state")           # what is kept and named when it is there; each has words in the text catalog under uninstall.kept.<id>
MAX_ENTRIES = 500                               # a folder of more than this many entries is not something this tool made: the rest are left alone


class UninstallError(Exception):
    """`code` is one of ERROR_CODES."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class Piece:
    kind: str                                   # one of KINDS
    path: str
    bytes: int
    files: int


@dataclass(frozen=True)
class Plan:
    pieces: Tuple[Piece, ...]                   # in the order they are removed: the programs, then the downloads
    left_alone: int                             # entries in the tool's own folders that this tool did not make (or cannot tell, or is building right now): never touched
    projects: int                               # how many projects are kept
    kept: Tuple[Tuple[str, str], ...]           # (id from KEPT, its folder) for each that is there and has something in it
    blocked: str                                # "job_running" when a task is starting, running or stopping
    fingerprint: str

    @property
    def total_bytes(self) -> int:
        return sum(p.bytes for p in self.pieces)

    @property
    def total_files(self) -> int:
        return sum(p.files for p in self.pieces)


def _names(folder: str) -> List[str]:
    try:
        return sorted(os.listdir(folder))
    except OSError:
        return []


def _is_ours(name: str, folder: str, ids: Sequence[str]) -> bool:
    """A set of programs this tool made: a real folder (not a link) named from its own record, of a set of programs this tool can build, and not being built this moment."""
    match = COPY_NAME.match(name)
    if match is None or match.group("id") not in ids or os.path.islink(folder) or not os.path.isdir(folder):
        return False
    record, _why = envbuild.read_record(folder)
    if record is None or record["id"] != match.group("id") or record["fingerprint"][:10] != match.group("fp"):
        return False
    return not os.path.lexists(folder + "/" + envbuild.BUILD_LOCK_NAME)


def _fingerprint(pieces: Sequence[Piece]) -> str:
    return hashlib.sha256("\n".join("%s|%s|%d|%d" % (p.kind, p.path, p.bytes, p.files) for p in pieces).encode("utf-8")).hexdigest()


def _task_running(home: DataHome) -> bool:
    return any(job.status in jobs.ACTIVE for job in jobs.list_jobs(home.jobs).jobs)


def plan(home: DataHome, specs: Sequence[EnvSpec]) -> Plan:
    """Everything an uninstall would remove, worked out without removing anything."""
    ids = [spec.id for spec in specs]
    pieces: List[Piece] = []
    left = 0
    names = _names(home.environments)
    for name in names[:MAX_ENTRIES]:
        folder = home.environments + "/" + name
        if not _is_ours(name, folder, ids):
            left += 1
            continue
        size, files = profiles.measure(folder)
        pieces.append(Piece(PROGRAMS, folder, size, files))
    left += max(0, len(names) - MAX_ENTRIES)
    names = _names(home.downloads)
    for name in names[:MAX_ENTRIES]:
        path = home.downloads + "/" + name
        if name == KEPT_VOICES:
            continue
        if os.path.islink(path):
            left += 1
            continue
        size, files = profiles.measure(path)
        pieces.append(Piece(DOWNLOADS, path, size, files))
    left += max(0, len(names) - MAX_ENTRIES)
    own = {os.path.basename(home.environments), os.path.basename(home.downloads)}
    left += sum(1 for name in _names(home.tool) if name not in own)
    folders = {"backups": home.backups, "voices": home.voices, "state": home.state}
    kept = tuple((name, folders[name]) for name in KEPT if not os.path.islink(folders[name]) and _names(folders[name]))
    return Plan(tuple(pieces), left, len(list_projects(home.projects).projects), kept, "job_running" if _task_running(home) else "", _fingerprint(pieces))


@dataclass(frozen=True)
class Result:
    removed: Tuple[Piece, ...]
    failed: Tuple[Tuple[str, str], ...]         # (path, the system's reason)

    @property
    def bytes(self) -> int:
        return sum(p.bytes for p in self.removed)


def _in_tool_area(home: DataHome, piece: Piece) -> bool:
    """The piece is a direct child of the programs' or the downloads' folder, in a place the areas list calls the tool's own, and is not the kept starting voices."""
    area = areas.home_area(areas.first_part(home.root, piece.path))
    return (area is not None and area.kind is Kind.TOOL and os.path.dirname(piece.path) in (home.environments, home.downloads)
            and os.path.basename(piece.path) != KEPT_VOICES)


def remove(home: DataHome, specs: Sequence[EnvSpec], shown: Plan, remove_tree: Callable[[str, List[Tuple[str, str]]], None] = profiles.remove_tree) -> Result:
    """Remove what `shown` listed, after working it out again. Raises `job_running` when a task has started since and `changed` (removing nothing) when what is there now is not what
    was shown. A piece that cannot be removed is reported and the rest still go: each is a whole folder or file of its own."""
    fresh = plan(home, specs)
    if fresh.blocked:
        raise UninstallError("job_running")
    if fresh.fingerprint != shown.fingerprint:
        raise UninstallError("changed")
    done: List[Piece] = []
    failed: List[Tuple[str, str]] = []
    for piece in fresh.pieces:
        if not _in_tool_area(home, piece):
            failed.append((piece.path, "it is not in the tool's own folder"))
            continue
        before = len(failed)
        remove_tree(piece.path, failed)
        if len(failed) == before and not os.path.lexists(piece.path):
            done.append(piece)
    for folder in (home.environments, home.downloads, home.tool):          # a folder left empty goes too; one with anything in it stays
        try:
            os.rmdir(folder)
        except OSError:
            pass
    return Result(tuple(done), tuple(failed))
