# SPDX-License-Identifier: GPL-3.0-or-later
"""Free up space (plan task VS-4.7, decision P11): what could be removed, shown with its size, and removed only when asked for exactly that.

Four kinds of thing are ever offered, all made by a round of this project (or from one) and all of the kinds P11 calls disposable or rebuildable:

* **a round's spare saved files** (core/rounds.py::classify): every checkpoint file of a round that has ended, except the chosen round's `last.ckpt` and the `last.ckpt` of the
  round it continued from (going back needs that one). A round that is neither of those is offered whole, `last.ckpt` included, and the offer says so, because once it is
  gone that round cannot be chosen any more;
* **a round's working folder** in scratch (the trainer's cache), of a round that has ended: every round uses a new one, so an old one is never read again;
* **a listening's test clips**, and **the voice made for hearing a round**, kept in the project's `listening` folder (core/listen.py; decision D43). Both are offered one listening at a time,
  as exactly the files a listening makes (the sound files, the list of sounds and the job files; or the three files of the voice copy), never anything else that might be in that folder, and a
  folder left empty is removed with the last of them. The voice copy is large; the clips are small; either can be made again. A listening more than `OLD_AFTER_DAYS` (30) days old is marked
  old: it gets a notice that it should be removed, and `--old` takes all of them at once. **Nothing is ever removed because it is old**; only what the person asked for, after being shown it.

Never offered, and never removable from here: recordings, transcripts, the project file and the consent note, backups, finished exports (and the voice files in them), the files of the round that is running
(and its working folder), files in a folder no round claims, links, the starting voices, and the `version_N` folders themselves (the trainer numbers its next folder from them,
so removing one could make a later round reuse a number). What is removed is **only what the person was shown**: the removal takes the lock that keeps a round from beginning,
works out the offers again, and refuses (removing nothing) if they are not the same as the ones that were shown. Paths are never taken from what a person types.

Nothing here says a word; core/rounds_flow.py does.
"""
from __future__ import annotations

import os
import shutil
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Sequence, Tuple

from . import commands, listen, rounds as rd
from .paths import ProjectPaths, ScratchPaths

KINDS = ("files", "folder", "copy", "clips")                   # a round's spare saved files, a round's working folder, the voice made for hearing a round, a listening's test clips
RELATIONS = ("chosen", "before", "other")                      # how the round stands to the chosen one: it is, it is what the chosen one continued from, or neither
OLD_AFTER_DAYS = 30                                            # a listening this many days old, or older, is marked old: noticed and offered, never removed on its own
ERROR_CODES = ("changed", "nothing_to_remove", "unknown_choice")    # each has words in the text catalog


class FreeError(Exception):
    def __init__(self, code: str, detail: str = ""):
        super().__init__(code + (": " + detail if detail else ""))
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class Offer:
    number: int                       # what the person types to choose it: 1, 2, 3 ... in the order shown
    kind: str                         # one of KINDS
    round: int
    relation: str                     # one of RELATIONS
    includes_saved_point: bool        # a "files" offer that takes the round's `last.ckpt` too: the round could not be chosen afterwards
    paths: Tuple[str, ...]            # the files, or the one folder
    bytes: int
    source: str = ""                  # a "copy" or "clips" offer: the folder of the round or voice file the listening was made from (`round-003`, or the voice file's folder name)
    when: str = ""                    # a "copy" or "clips" offer: when the listening was made, such as 2026-10-11 12:00 UTC
    old: bool = field(default=False, compare=False)    # a "copy" or "clips" offer made OLD_AFTER_DAYS or more ago; time passing is not a change to the list, so it is left out of the comparison


@dataclass(frozen=True)
class Plan:
    offers: Tuple[Offer, ...]
    kept: Tuple[Tuple[int, rd.CheckpointFile], ...]      # (round, file): kept for sure, shown so the person sees what is not on the list
    busy: int                                            # files of the running round, never touched
    unclaimed: int                                       # files in a folder no round claims, never touched

    @property
    def old_listenings(self) -> int:
        """How many listenings (each is a voice copy, test clips, or both) are marked old."""
        return len({(o.source, o.when) for o in self.offers if o.old})

    @property
    def fingerprint(self) -> Tuple:
        """Everything the person was shown about each offer (its number, kind, round, relation, whether it takes a saved point, its files and its size). Equal fingerprints mean the same list."""
        return tuple(self.offers)


def _size_of_folder(path: str) -> int:
    total = 0
    for base, _folders, files in os.walk(path, followlinks=False):
        for name in files:
            try:
                total += os.lstat(os.path.join(base, name)).st_size
            except OSError:
                pass
    return total


def _relation(record: rd.Record, number: int) -> str:
    pick = rd.chosen(record)
    if pick is not None and number == pick.number:
        return "chosen"
    if pick is not None and pick.parent and number == pick.parent:
        return "before"
    return "other"


def _listenings(paths: ProjectPaths) -> List[Tuple[str, str, str]]:
    """(source, run, folder) of every listening in the project's `listening` folder, in name order. Only folders (never links) with the names this tool gives are looked at."""
    found: List[Tuple[str, str, str]] = []
    root = paths.listening
    if not os.path.isdir(root) or os.path.islink(root):
        return found
    try:
        sources = sorted(os.listdir(root))
    except OSError:
        return found
    for source in sources:
        folder = "%s/%s" % (root, source)
        if not commands.SAFE_NAME.match(source) or os.path.islink(folder) or not os.path.isdir(folder):
            continue
        try:
            runs = sorted(os.listdir(folder))
        except OSError:
            continue
        for run in runs:
            where = "%s/%s" % (folder, run)
            if listen.RUN_FOLDER.match(run) and not os.path.islink(where) and os.path.isdir(where):
                found.append((source, run, where))
    return found


def _made_at(run: str) -> Optional[datetime]:
    """The time in a listening's folder name (UTC), or None when it is not a real time."""
    found = listen.RUN_FOLDER.match(run)
    if not found:
        return None
    date, time = found.groups()
    try:
        return datetime(int(date[:4]), int(date[4:6]), int(date[6:]), int(time[:2]), int(time[2:4]), int(time[4:]), tzinfo=timezone.utc)
    except ValueError:
        return None


def is_old(run: str, now: Optional[datetime] = None) -> bool:
    """Whether a listening made at the time in this folder name is OLD_AFTER_DAYS or more old. A time in the future (the clock was changed) is not old."""
    made = _made_at(run)
    if made is None:
        return False
    current = datetime.now(timezone.utc) if now is None else (now if now.tzinfo is not None else now.replace(tzinfo=timezone.utc))
    return current - made >= timedelta(days=OLD_AFTER_DAYS)


def old_count(paths: ProjectPaths, now: Optional[datetime] = None) -> int:
    """How many listenings in this project are marked old and still have something that could be removed. Looks only."""
    return sum(1 for _source, run, folder in _listenings(paths) if is_old(run, now) and (_listening_files(folder, "copy") or _listening_files(folder, "clips")))


def _when(run: str) -> str:
    """`heard-20261011-120000` -> `2026-10-11 12:00 UTC` (the time in the name is UTC)."""
    found = listen.RUN_FOLDER.match(run)
    if not found:
        return ""
    date, time = found.groups()
    return "%s-%s-%s %s:%s UTC" % (date[:4], date[4:6], date[6:], time[:2], time[2:4])


def _listening_files(folder: str, kind: str) -> List[Tuple[str, int]]:
    """(path, size) of the plain files of one kind in a listening's folder: exactly the three files of the voice copy, or exactly the small files a listening makes. Nothing else is ever listed."""
    names = listen.VOICE_COPY_NAMES if kind == "copy" else None
    try:
        entries = sorted(os.listdir(folder))
    except OSError:
        return []
    found = []
    for name in entries:
        if (name in names) if names is not None else listen.CLIP_FILES.match(name) is not None:
            path = "%s/%s" % (folder, name)
            try:
                if os.path.isfile(path) and not os.path.islink(path):
                    found.append((path, os.lstat(path).st_size))
            except OSError:
                continue
    return found


def plan(paths: ProjectPaths, scratch: ScratchPaths, record: rd.Record, now: Optional[datetime] = None) -> Plan:
    """What could be removed right now. Reads the disk and changes nothing. `now` is only used to mark listenings that are old."""
    kept = rd.retention(paths, record)
    by_round = {}
    for number, file in kept.spare:
        by_round.setdefault(number, []).append(file)
    # (group, round, kind, takes the saved point, paths, size, source, when): the saved files first, then the working folders, then the large voice copies, then the small test clips
    rows: List[Tuple[int, int, str, bool, Tuple[str, ...], int, str, str, bool]] = []
    for number in sorted(by_round):
        files = sorted(by_round[number], key=lambda f: (f.version, f.name))
        rows.append((0, number, "files", any(f.name == rd.LAST for f in files), tuple(f.path for f in files), sum(f.size for f in files), "", "", False))
    for r in record.rounds:
        if r.state in rd.ACTIVE_STATES:
            continue
        folder = rd.cache_dir_for(scratch, r.dataset, r.number)
        if os.path.isdir(folder) and not os.path.islink(folder):
            rows.append((1, r.number, "folder", False, (folder,), _size_of_folder(folder), "", "", False))
    for source, run, folder in _listenings(paths):
        number = listen.round_of_source(source)
        for group, kind in ((2, "copy"), (3, "clips")):
            files = _listening_files(folder, kind)
            if files:
                rows.append((group, number, kind, False, tuple(path for path, _size in files), sum(size for _path, size in files), source, _when(run), is_old(run, now)))
    rows.sort(key=lambda row: (row[0], row[1]))                      # a stable sort: listenings of one round stay in the order of their folders' names, which is their time
    offers = tuple(Offer(i + 1, kind, number, _relation(record, number), includes, files, size, source, when, old)
                   for i, (_g, number, kind, includes, files, size, source, when, old) in enumerate(rows))
    return Plan(offers, kept.keep, len(kept.busy), len(kept.unclaimed))


@dataclass(frozen=True)
class Result:
    removed_files: int
    removed_folders: int
    removed_bytes: int
    failed: Tuple[Tuple[str, str], ...]      # (path, the system's reason): left where they were
    removed_heard: int = 0                   # test clips and voice copies from listening (not counted in removed_files)


def _under(path: str, folder: str) -> bool:
    return os.path.realpath(path).startswith(os.path.realpath(folder) + os.sep)


def _may_remove_listening_file(paths: ProjectPaths, path: str, kind: str) -> bool:
    """Whether this is, right now, a plain file with one of the exact names a listening of this kind makes, at exactly `<listening>/<source>/<run>/<name>` and nowhere else."""
    if os.path.islink(paths.listening) or os.path.islink(path) or not os.path.isfile(path) or not _under(path, paths.listening):
        return False
    parts = os.path.relpath(os.path.realpath(path), os.path.realpath(paths.listening)).split(os.sep)
    if len(parts) != 3:
        return False
    source, run, name = parts
    named = name in listen.VOICE_COPY_NAMES if kind == "copy" else listen.CLIP_FILES.match(name) is not None
    return named and commands.SAFE_NAME.match(source) is not None and listen.RUN_FOLDER.match(run) is not None


def _remove_if_empty(paths: ProjectPaths, folder: str) -> None:
    """Take away a listening's folder, or its source's, once nothing is left in it. A folder with anything else in it is left as it is."""
    if os.path.islink(folder) or not os.path.isdir(folder) or not _under(folder, paths.listening):
        return
    try:
        os.rmdir(folder)
    except OSError:
        pass


def remove(paths: ProjectPaths, scratch: ScratchPaths, shown: Plan, wanted: Sequence[int]) -> Result:
    """Remove the offers with these numbers from the list that was shown. Takes the lock, works the list out again and refuses, removing nothing, if it is not the one shown."""
    chosen = sorted(set(wanted))
    if not chosen:
        raise FreeError("nothing_to_remove")
    if any(n not in {o.number for o in shown.offers} for n in chosen):
        raise FreeError("unknown_choice", ",".join(str(n) for n in chosen))
    with rd.exclusive(paths):
        record = rd.load(paths)
        fresh = plan(paths, scratch, record)
        if fresh.fingerprint != shown.fingerprint:
            raise FreeError("changed")
        keep = {f.path for _n, f in fresh.kept}
        files = folders = size = heard = 0
        failed: List[Tuple[str, str]] = []
        for offer in fresh.offers:
            if offer.number not in chosen:
                continue
            if offer.kind == "files":
                for path in offer.paths:
                    if path in keep or os.path.islink(path) or not os.path.isfile(path) or not _under(path, paths.run + "/lightning_logs") or not path.endswith(".ckpt"):
                        failed.append((path, "not a file this may remove"))
                        continue
                    try:
                        gone = os.lstat(path).st_size
                        os.unlink(path)
                    except OSError as exc:
                        failed.append((path, exc.strerror or type(exc).__name__))
                        continue
                    files += 1
                    size += gone
            elif offer.kind in ("copy", "clips"):
                for path in offer.paths:
                    if not _may_remove_listening_file(paths, path, offer.kind):
                        failed.append((path, "not a file this may remove"))
                        continue
                    try:
                        gone = os.lstat(path).st_size
                        os.unlink(path)
                    except OSError as exc:
                        failed.append((path, exc.strerror or type(exc).__name__))
                        continue
                    heard += 1                                   # counted on its own: the "files" count is the saved files of rounds
                    size += gone
                run = os.path.dirname(offer.paths[0])
                _remove_if_empty(paths, run)
                _remove_if_empty(paths, os.path.dirname(run))
            else:
                folder = offer.paths[0]
                if os.path.islink(folder) or not os.path.isdir(folder) or not _under(folder, scratch.caches):
                    failed.append((folder, "not a folder this may remove"))
                    continue
                problems: List[Tuple[str, str]] = []
                gone = _size_of_folder(folder)
                if sys.version_info >= (3, 12):
                    shutil.rmtree(folder, onexc=lambda _f, p, exc: problems.append((p, getattr(exc, "strerror", None) or type(exc).__name__)))
                else:
                    shutil.rmtree(folder, onerror=lambda _f, p, info: problems.append((p, getattr(info[1], "strerror", None) or type(info[1]).__name__)))
                if problems:
                    failed.extend(problems)
                if not os.path.exists(folder):
                    folders += 1
                    size += gone
                else:
                    size += max(0, gone - _size_of_folder(folder))
        return Result(files, folders, size, tuple(failed), heard)
