# SPDX-License-Identifier: GPL-3.0-or-later
"""Move a project's scratch to another place (plan task VS-6.5, decision P20): copy it, check the copy, switch to it, and only then offer to remove the old one.

Scratch is where a project keeps its training sets and each round's working files (core/paths.py `ScratchPaths`). The training sets cannot yet be rebuilt by this tool, so a move
must carry them whole. The order is the only safety: the new place is made and filled first (every file is read back and compared with what was read from the old place, a copy
that does not match is deleted and reported), the whole copy is checked against the old place again, and **only then** is the project's record changed to point at the new place
(`project.json` is replaced atomically and the old one kept as `project.json.previous`). Until that last step the project still uses the old place, so anything that goes wrong
costs only disk space and time, and running the move again carries on: a file that is already there and identical is not copied again. The old place is never touched by the move;
`remove_old` is a separate step the person says yes to, and it removes only a folder this tool made (a place whose marker names this project, or the default folder inside the project).

The records of rounds name training sets and rounds, never a path in scratch, so they need no change. Moving is refused while any task for the project is running, and the check is
made again just before the switch. (A round started in the last few milliseconds between that check and the switch is a known gap.)

Plain Python with no words; the words are in the text catalog under `scratchmove.*`.
"""
from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from typing import Callable, List, Optional, Sequence, Tuple

from . import jobs, profiles
from .project import Project, ProjectError, save_project, with_scratch_place
from .paths import ProjectPaths
from .scratch import MARKER_NAME, SCRATCH_DIRNAME, MarkerState, check_marker, create_scratch, scratch_dir_for

ERROR_CODES = ("job_running", "changed", "source_missing", "target_in_the_way", "copy_failed", "differs", "not_saved")      # each has words in the text catalog
CHUNK = 1 << 20
PARTIAL = ".partial"


class MoveError(Exception):
    """`code` is one of ERROR_CODES; `detail` is a short fact for Show details."""

    def __init__(self, code: str, detail: str = ""):
        super().__init__(code + (": " + detail if detail else ""))
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class FileEntry:
    rel: str
    size: int


@dataclass(frozen=True)
class Tree:
    files: Tuple[FileEntry, ...]                # every plain file, in order, without the marker at the top
    dirs: Tuple[str, ...]                       # every folder (relative), so empty ones are made too
    skipped: Tuple[str, ...]                    # links and other things that are not plain files or folders: not copied, not followed

    @property
    def bytes(self) -> int:
        return sum(f.size for f in self.files)

    @property
    def fingerprint(self) -> str:
        text = "\n".join(["%s|%d" % (f.rel, f.size) for f in self.files] + ["d|" + d for d in self.dirs] + ["s|" + s for s in self.skipped])
        return hashlib.sha256(text.encode("utf-8")).hexdigest()


def read_tree(root: str) -> Tree:
    """Everything under `root`, never following a link. Raises OSError when a folder cannot be read."""
    files: List[FileEntry] = []
    dirs: List[str] = []
    skipped: List[str] = []
    stack = [""]
    while stack:
        rel = stack.pop()
        here = root + ("/" + rel if rel else "")
        with os.scandir(here) as scan:
            entries = list(scan)                # the lists are sorted at the end, so the order here does not matter
        for entry in entries:
            child = (rel + "/" if rel else "") + entry.name
            if not rel and entry.name == MARKER_NAME:
                continue
            if entry.is_dir(follow_symlinks=False):
                dirs.append(child)
                stack.append(child)
            elif entry.is_file(follow_symlinks=False):
                files.append(FileEntry(child, entry.stat(follow_symlinks=False).st_size))
            else:
                skipped.append(child)                       # a link (never followed), a pipe, a device
    return Tree(tuple(sorted(files, key=lambda f: f.rel)), tuple(sorted(dirs)), tuple(sorted(skipped)))


@dataclass(frozen=True)
class Plan:
    project_id: str
    source: str                                 # the scratch folder now
    target: str                                 # the scratch folder it would become
    target_place: str                           # the place that holds it, or "" for the default folder inside the project
    tree: Tree
    blocked: str                                # "job_running" when a task for the project is starting, running or stopping, else ""


def task_blocks(jobs_root: str, project_id: str) -> bool:
    return any(j.spec.project == project_id and j.status in jobs.ACTIVE for j in jobs.list_jobs(jobs_root).jobs)


def plan(project: Project, paths: ProjectPaths, source: str, target: str, target_place: str, jobs_root: str) -> Plan:
    """What a move would copy, worked out without writing anything. Raises MoveError('source_missing') when the old place cannot be read."""
    if source == paths.default_scratch and not os.path.lexists(source):
        tree = Tree((), (), ())                 # a default scratch that was never made holds nothing
    else:
        try:
            tree = read_tree(source)
        except OSError as exc:
            raise MoveError("source_missing", exc.strerror or type(exc).__name__)
    return Plan(project.id, source, target, target_place, tree, "job_running" if task_blocks(jobs_root, project.id) else "")


def prepare_target(plan_: Plan) -> None:
    """Make the new scratch folder: with its marker inside a chosen place, or the plain folder inside the project. An earlier folder of this project is reused (the copy skips what is already there
    and identical). Raises MoveError('target_in_the_way') when a chosen place holds another project's folder or files that are not a scratch."""
    try:
        if plan_.target_place:
            create_scratch(plan_.target_place, plan_.project_id)
        else:
            os.makedirs(plan_.target, mode=0o700, exist_ok=True)          # the folder inside the project is always this project's own: what is left in it is reused, like a chosen place's
    except ValueError as exc:
        raise MoveError("target_in_the_way", str(exc))
    except OSError as exc:
        raise MoveError("copy_failed", exc.strerror or type(exc).__name__)


def _hash_of(path: str) -> Tuple[str, int]:
    digest, size = hashlib.sha256(), 0
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(CHUNK), b""):
            digest.update(block)
            size += len(block)
    return digest.hexdigest(), size


def _copy_file(source: str, target: str, entry: FileEntry) -> bool:
    """Copy one file and check it. True when a copy was made, False when an identical file was already there. The new file is written under another name, read back, and only then put in place."""
    if os.path.isfile(target) and not os.path.islink(target) and os.path.getsize(target) == entry.size:
        if _hash_of(target)[0] == _hash_of(source)[0]:
            return False
    partial = target + PARTIAL
    digest, size = hashlib.sha256(), 0
    try:
        fd = os.open(partial, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with open(source, "rb") as src, os.fdopen(fd, "wb") as out:
            for block in iter(lambda: src.read(CHUNK), b""):
                digest.update(block)
                size += len(block)
                out.write(block)
            out.flush()
            os.fsync(out.fileno())
    except OSError as exc:
        _quietly_remove(partial)
        raise MoveError("copy_failed", "%s: %s" % (entry.rel, exc.strerror or type(exc).__name__))
    if size != entry.size:
        _quietly_remove(partial)
        raise MoveError("changed", entry.rel)
    try:
        written, written_size = _hash_of(partial)
    except OSError as exc:
        _quietly_remove(partial)
        raise MoveError("copy_failed", "%s: %s" % (entry.rel, exc.strerror or type(exc).__name__))
    if written != digest.hexdigest() or written_size != size:
        _quietly_remove(partial)
        raise MoveError("differs", entry.rel)
    try:
        os.replace(partial, target)
    except OSError as exc:
        _quietly_remove(partial)
        raise MoveError("copy_failed", "%s: %s" % (entry.rel, exc.strerror or type(exc).__name__))
    return True


def _quietly_remove(path: str) -> None:
    try:
        os.unlink(path)
    except OSError:
        pass


@dataclass(frozen=True)
class Copied:
    copied: int                                 # files written now
    already: int                                # files that were already there and identical
    bytes: int


def copy_tree(plan_: Plan, on_file: Optional[Callable[[int, int, str], None]] = None) -> Copied:
    """Copy what the plan lists into the new folder. Stops at the first file that cannot be copied or does not read back the same (MoveError); what was copied stays, and a new try
    skips it. `on_file(done, total, rel)` is called after each file."""
    for rel in plan_.tree.dirs:
        try:
            os.makedirs(plan_.target + "/" + rel, mode=0o700, exist_ok=True)
        except OSError as exc:
            raise MoveError("copy_failed", "%s: %s" % (rel, exc.strerror or type(exc).__name__))
    copied = already = moved = 0
    total = len(plan_.tree.files)
    for index, entry in enumerate(plan_.tree.files, 1):
        if _copy_file(plan_.source + "/" + entry.rel, plan_.target + "/" + entry.rel, entry):
            copied += 1
            moved += entry.size
        else:
            already += 1
        if on_file:
            on_file(index, total, entry.rel)
    return Copied(copied, already, moved)


def check_copy(plan_: Plan) -> None:
    """The last look before the switch: the old place is still exactly what the plan listed, and every file of it is in the new place with its size. Raises MoveError('changed') or
    MoveError('differs')."""
    if not os.path.lexists(plan_.source) and plan_.tree == Tree((), (), ()):
        now = plan_.tree                        # a default scratch that was never made, still not there
    else:
        try:
            now = read_tree(plan_.source)
        except OSError as exc:
            raise MoveError("source_missing", exc.strerror or type(exc).__name__)
    if now.fingerprint != plan_.tree.fingerprint:
        raise MoveError("changed", "")
    for entry in plan_.tree.files:
        path = plan_.target + "/" + entry.rel
        if os.path.islink(path) or not os.path.isfile(path) or os.path.getsize(path) != entry.size:
            raise MoveError("differs", entry.rel)
    for rel in plan_.tree.dirs:
        if not os.path.isdir(plan_.target + "/" + rel):
            raise MoveError("differs", rel)


def switch(project: Project, paths: ProjectPaths, plan_: Plan, jobs_root: str) -> Project:
    """Point the project at the new place. Checks again that no task for it is running. Raises MoveError('job_running') or MoveError('not_saved'); on either the project is as it was."""
    if task_blocks(jobs_root, project.id):
        raise MoveError("job_running", "")
    moved = with_scratch_place(project, plan_.target_place)
    try:
        save_project(paths, moved)
    except OSError as exc:
        raise MoveError("not_saved", exc.strerror or type(exc).__name__)
    except ProjectError as exc:
        raise MoveError("not_saved", exc.code)
    return moved


# ---------------------------------------------------------------- the old place

@dataclass(frozen=True)
class OldPlace:
    folder: str                                 # what would be removed
    contents_only: bool                         # the default folder inside the project stays (empty); a chosen place's folder goes
    bytes: int
    files: int


def old_place(before: Project, paths: ProjectPaths) -> Optional[OldPlace]:
    """What is left behind in the place the project used before, if it is something this tool made and can still be found: the default folder inside the project, or the folder in a chosen
    place whose marker names this project. None when there is nothing to offer."""
    if before.scratch.place:
        try:
            folder = scratch_dir_for(before.scratch.place, before.id)
        except ValueError:
            return None
        try:
            with open(folder + "/" + MARKER_NAME, encoding="utf-8") as handle:
                state = check_marker(handle.read(), before.id)
        except OSError:
            return None
        if state is not MarkerState.OK or os.path.islink(folder):           # a marker that could be read means the folder is one
            return None
        size, files = profiles.measure(folder)
        return OldPlace(folder, False, size, files)
    folder = paths.default_scratch
    if os.path.islink(folder) or not os.path.isdir(folder) or not os.listdir(folder):
        return None
    size, files = profiles.measure(folder)
    return OldPlace(folder, True, size, files)


@dataclass(frozen=True)
class Removal:
    bytes: int
    failed: Tuple[Tuple[str, str], ...]


def remove_old(place: OldPlace, project: Project, jobs_root: str, remove_tree: Callable[[str, List[Tuple[str, str]]], None] = profiles.remove_tree) -> Removal:
    """Remove the old place that `old_place` named. Raises MoveError('job_running') when a task for the project has started since. In a chosen place only the project's own folder goes (and
    the folder that holds it when it is then empty), never the place itself."""
    if task_blocks(jobs_root, project.id):
        raise MoveError("job_running", "")
    failed: List[Tuple[str, str]] = []
    if place.contents_only:
        for name in sorted(os.listdir(place.folder)):
            remove_tree(place.folder + "/" + name, failed)
    else:
        remove_tree(place.folder, failed)
        if os.path.basename(os.path.dirname(place.folder)) == SCRATCH_DIRNAME:           # it is not removed while anything is left in it
            try:
                os.rmdir(os.path.dirname(place.folder))
            except OSError:
                pass
    return Removal(0 if failed else place.bytes, tuple(failed))
