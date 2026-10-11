# SPDX-License-Identifier: GPL-3.0-or-later
"""Free up space (plan task VS-4.7, decision P11): what could be removed, shown with its size, and removed only when asked for exactly that.

Two kinds of thing are ever offered, both made by a round of this project and both of the kinds P11 calls disposable or rebuildable:

* **a round's spare saved files** (core/rounds.py::classify): every checkpoint file of a round that has ended, except the chosen round's `last.ckpt` and the `last.ckpt` of the
  round it continued from (going back needs that one). A round that is neither of those is offered whole, `last.ckpt` included, and the offer says so, because once it is
  gone that round cannot be chosen any more;
* **a round's working folder** in scratch (the trainer's cache), of a round that has ended: every round uses a new one, so an old one is never read again.

Never offered, and never removable from here: recordings, transcripts, the project file and the consent note, backups, finished exports, the files of the round that is running
(and its working folder), files in a folder no round claims, links, the starting voices, and the `version_N` folders themselves (the trainer numbers its next folder from them,
so removing one could make a later round reuse a number). What is removed is **only what the person was shown**: the removal takes the lock that keeps a round from beginning,
works out the offers again, and refuses (removing nothing) if they are not the same as the ones that were shown. Paths are never taken from what a person types.

Nothing here says a word; core/rounds_flow.py does.
"""
from __future__ import annotations

import os
import shutil
import sys
from dataclasses import dataclass
from typing import List, Sequence, Tuple

from . import rounds as rd
from .paths import ProjectPaths, ScratchPaths

KINDS = ("files", "folder")                                    # a round's spare saved files, a round's working folder
RELATIONS = ("chosen", "before", "other")                      # how the round stands to the chosen one: it is, it is what the chosen one continued from, or neither
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


@dataclass(frozen=True)
class Plan:
    offers: Tuple[Offer, ...]
    kept: Tuple[Tuple[int, rd.CheckpointFile], ...]      # (round, file): kept for sure, shown so the person sees what is not on the list
    busy: int                                            # files of the running round, never touched
    unclaimed: int                                       # files in a folder no round claims, never touched

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


def plan(paths: ProjectPaths, scratch: ScratchPaths, record: rd.Record) -> Plan:
    """What could be removed right now. Reads the disk and changes nothing."""
    kept = rd.retention(paths, record)
    by_round = {}
    for number, file in kept.spare:
        by_round.setdefault(number, []).append(file)
    rows: List[Tuple[int, int, str, int, bool, Tuple[str, ...], int]] = []
    for number in sorted(by_round):
        files = sorted(by_round[number], key=lambda f: (f.version, f.name))
        rows.append((0, number, "files", number, any(f.name == rd.LAST for f in files), tuple(f.path for f in files), sum(f.size for f in files)))
    for r in record.rounds:
        if r.state in rd.ACTIVE_STATES:
            continue
        folder = rd.cache_dir_for(scratch, r.dataset, r.number)
        if os.path.isdir(folder) and not os.path.islink(folder):
            rows.append((1, r.number, "folder", r.number, False, (folder,), _size_of_folder(folder)))
    rows.sort(key=lambda row: (row[0], row[1]))
    offers = tuple(Offer(i + 1, kind, number, _relation(record, number), includes, files, size) for i, (_k, _n, kind, number, includes, files, size) in enumerate(rows))
    return Plan(offers, kept.keep, len(kept.busy), len(kept.unclaimed))


@dataclass(frozen=True)
class Result:
    removed_files: int
    removed_folders: int
    removed_bytes: int
    failed: Tuple[Tuple[str, str], ...]      # (path, the system's reason): left where they were


def _under(path: str, folder: str) -> bool:
    return os.path.realpath(path).startswith(os.path.realpath(folder) + os.sep)


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
        files = folders = size = 0
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
        return Result(files, folders, size, tuple(failed))
