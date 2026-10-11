# SPDX-License-Identifier: GPL-3.0-or-later
"""The disk budget (plan P11, decisions D24 and D26): what the path will need, whether there is room, and what may be freed.

Pure arithmetic over a table of sizes. Nothing here reads a disk or says a word: callers hand in free space (core/preflight.py reads it) and
turn the verdicts into sentences from the text catalog.

**Every number in `DEFAULT_TABLE` is provisional.** Each carries its basis: "listing" (a size a host shows), "freeform" (Freeform Studio's own
figure), "computed" (arithmetic from a format), or "guess". The spike on a real GPU (plan task VS-0.2) replaces them with "measured" ones, and
the screens say the estimate is rough until every figure is measured.

Three kinds of file (P11): PRECIOUS (never removed by the tool), REBUILDABLE (can be made again from precious ones) and DISPOSABLE. Four
roles say which drive a line lands on, so scratch can be on another drive (D24): TOOL (the tool's own folder), PROJECT (the person's project
folder), SCRATCH, BACKUP (where backups are written).
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict, FrozenSet, Iterable, List, Mapping, Optional, Sequence, Tuple

MIB = 1024 * 1024
GIB = 1024 * MIB

RECORDER_FLOOR = 500 * MIB          # Freeform Studio refuses new audio below this (its --min-free-mb default); training must stop well above it
STOP_SLACK = 256 * MIB
MIN_PEOPLE_AT_START = 2             # D26: the start estimate always leaves room for at least two people
MIN_PLAN_HOURS = 0.5
PROTECTED_CHECKPOINTS = 2           # the chosen round's checkpoint and the one before it (going back needs it)


class Kind(Enum):
    PRECIOUS = "precious"
    REBUILDABLE = "rebuildable"
    DISPOSABLE = "disposable"
    TOOL = "tool"


class Role(Enum):
    TOOL = "tool"
    PROJECT = "project"
    SCRATCH = "scratch"
    BACKUP = "backup"


class Level(Enum):
    ENOUGH = "enough"
    TIGHT = "tight"                 # can go on after a warning
    NOT_ENOUGH = "not_enough"       # the step does not start; nothing is changed


class Watch(Enum):
    FINE = "fine"
    LOW = "low"                     # a quiet banner and a silent notification
    STOP = "stop"                   # stop the job gracefully, now, while a stop can still be written


@dataclass(frozen=True)
class SizeTable:
    tool_environments: int          # the Python environments (torch and the rest), installed
    tool_download_cache: int        # pip's cache of what it downloaded (offered for clean-up after the build)
    recording_per_hour: int         # the raw take and its decoded copies
    dataset_per_hour: int           # the training clips
    training_cache_per_hour: int    # what the trainer caches from them
    checkpoint: int                 # one training checkpoint
    checkpoints_per_round: int
    rounds: int                     # rounds budgeted for one person
    margin: int                     # spare room that must remain on every drive
    bases: Mapping[str, str]

    @property
    def all_measured(self) -> bool:
        return all(basis == "measured" for basis in self.bases.values())


DEFAULT_TABLE = SizeTable(
    tool_environments=8 * GIB, tool_download_cache=4 * GIB,
    recording_per_hour=400 * MIB,                       # freeform_studio/health.py HOUR_MB: an hour of recording once decoded for review
    dataset_per_hour=22050 * 2 * 3600,                  # 22,050 Hz, mono, 16-bit, one hour: 158,760,000 bytes
    training_cache_per_hour=1 * GIB,
    checkpoint=846_000_000,                             # the size Hugging Face shows for the two starting voices' checkpoints; a trainer checkpoint on disk is the same 807 MiB (measured 2026-10-11)
    checkpoints_per_round=6, rounds=4, margin=5 * GIB,  # measured: a round's folder keeps the five best by mel loss and last.ckpt, 4.84 GB, however short the round
    bases={"tool_environments": "guess", "tool_download_cache": "guess", "recording_per_hour": "freeform", "dataset_per_hour": "computed",
           "training_cache_per_hour": "guess", "checkpoint": "measured", "checkpoints_per_round": "measured", "rounds": "guess", "margin": "guess"})


@dataclass(frozen=True)
class Line:
    key: str
    role: Role
    kind: Kind
    bytes: int


@dataclass(frozen=True)
class DriveMap:
    """Which drive each role lands on. Drives are named by anything stable (a mount point, a device id); by default everything is on one."""
    tool: str = "home"
    project: str = "home"
    scratch: str = "home"
    backup: str = "home"

    def of(self, role: Role) -> str:
        return getattr(self, role.value)


# ---------------------------------------------------------------- what a plan needs

def person_lines(table: SizeTable, hours: float, rounds: Optional[int] = None) -> List[Line]:
    """One person's project: recordings and the protected checkpoints on the project drive; dataset, cache and the older checkpoints on scratch;
    one backup copy of the precious part."""
    hours = max(float(hours), MIN_PLAN_HOURS)
    rounds = table.rounds if rounds is None else rounds
    recordings = int(hours * table.recording_per_hour)
    protected = PROTECTED_CHECKPOINTS * table.checkpoint
    older = max(0, rounds * table.checkpoints_per_round - PROTECTED_CHECKPOINTS) * table.checkpoint
    return [
        Line("person.recordings", Role.PROJECT, Kind.PRECIOUS, recordings),
        Line("person.checkpoints_kept", Role.PROJECT, Kind.PRECIOUS, protected),
        Line("person.dataset", Role.SCRATCH, Kind.REBUILDABLE, int(hours * table.dataset_per_hour)),
        Line("person.cache", Role.SCRATCH, Kind.REBUILDABLE, int(hours * table.training_cache_per_hour)),
        Line("person.checkpoints_older", Role.SCRATCH, Kind.DISPOSABLE, older),
        Line("person.backup_copy", Role.BACKUP, Kind.PRECIOUS, recordings + protected),
    ]


def start_lines(table: SizeTable, downloads: Sequence[Tuple[str, int]], people: int, hours: float, rounds: Optional[int] = None) -> List[Line]:
    """The tool, everything to be downloaded (id and size, from the registry), and `people` projects."""
    lines = [Line("tool.environments", Role.TOOL, Kind.TOOL, table.tool_environments),
             Line("tool.download_cache", Role.TOOL, Kind.DISPOSABLE, table.tool_download_cache)]
    lines += [Line("download." + item_id, Role.TOOL, Kind.TOOL, size) for item_id, size in downloads]
    for _ in range(max(people, 0)):
        lines += person_lines(table, hours, rounds)
    return lines


def need_by_drive(lines: Iterable[Line], drives: DriveMap, margin: int) -> Dict[str, int]:
    """Total per drive, plus the safety margin on every drive that is used at all."""
    totals: Dict[str, int] = {}
    for line in lines:
        if line.bytes > 0:
            totals[drives.of(line.role)] = totals.get(drives.of(line.role), 0) + line.bytes
    return {drive: total + margin for drive, total in totals.items()}


@dataclass(frozen=True)
class Verdict:
    level: Level
    need: Dict[str, int]                    # the full plan, per drive, margin included
    need_tight: Dict[str, int]              # everything to download, one person at the planned size
    need_minimum: Dict[str, int]            # the smallest voice, one person at the smallest plan
    free: Dict[str, Optional[int]]
    short_by: Dict[str, int]                # per drive, how much is missing to reach "enough" (0 if it is there)
    suggest_drop_voice: bool                # it would fit with one starting voice fewer
    unknown_drives: Tuple[str, ...]         # drives whose free space could not be read: not judged
    rough: bool                             # the table still has numbers nobody measured


def judge_start(table: SizeTable, downloads: Sequence[Tuple[str, int]], hours: float, drives: DriveMap, free: Mapping[str, Optional[int]],
                people: int = MIN_PEOPLE_AT_START) -> Verdict:
    """D26. ENOUGH covers the full plan. TIGHT covers what has to be downloaded and one person (continue after a warning), or at least the
    smallest voice and the smallest plan. Below that is NOT_ENOUGH. The worst drive decides."""
    people = max(people, MIN_PEOPLE_AT_START)
    full = need_by_drive(start_lines(table, downloads, people, hours), drives, table.margin)
    one = need_by_drive(start_lines(table, downloads, 1, hours), drives, table.margin)
    # a starting voice is the only download a person may decline: the minimum keeps every other download and the smallest voice
    voices = [d for d in downloads if d[0].startswith("voice-")]
    keep = [d for d in downloads if not d[0].startswith("voice-")] + ([min(voices, key=lambda d: d[1])] if voices else [])
    minimum = need_by_drive(start_lines(table, keep, 1, MIN_PLAN_HOURS, rounds=1), drives, table.margin)

    unknown = tuple(sorted(d for d in full if free.get(d) is None))
    level, short, drop = Level.ENOUGH, {}, False
    for drive, need in full.items():
        have = free.get(drive)
        if have is None:
            continue
        short[drive] = max(0, need - have)
        if have >= need:
            continue
        if have >= one.get(drive, 0):
            here = Level.TIGHT
        elif have >= minimum.get(drive, 0):
            here, drop = Level.TIGHT, drop or len(voices) > 1
        else:
            here = Level.NOT_ENOUGH
        if here is Level.NOT_ENOUGH or level is Level.ENOUGH:
            level = here
    return Verdict(level, full, one, minimum, dict(free), short, drop, unknown, not table.all_measured)


# ---------------------------------------------------------------- while a job runs, and before a step

@dataclass(frozen=True)
class Floors:
    recorder: int       # below this Freeform Studio refuses new audio (0 on a drive that holds no recordings)
    stop: int           # below this a running job is stopped gracefully
    low: int            # below this the person is warned


def floors_for(table: SizeTable, holds_recordings: bool) -> Floors:
    """Training stops strictly above the recorder's floor, with room for what a stop writes (one checkpoint), so a full disk can end a round
    but never costs a recording."""
    recorder = RECORDER_FLOOR if holds_recordings else 0
    stop = recorder + table.checkpoint + STOP_SLACK
    return Floors(recorder, stop, stop + 2 * table.checkpoint)


def watch(free: Optional[int], floors: Floors) -> Watch:
    """A drive that cannot be read is not judged: the caller says so, and the job is not stopped on a guess."""
    if free is None or free >= floors.low:
        return Watch.FINE
    return Watch.STOP if free < floors.stop else Watch.LOW


def check_step(free: Optional[int], need: int, floors: Floors) -> Level:
    """Before a step that writes `need` bytes: OK if the room left afterwards stays above the low floor, TIGHT if only above the stop floor."""
    if free is None:
        return Level.ENOUGH
    left = free - need
    if left >= floors.low:
        return Level.ENOUGH
    return Level.TIGHT if left >= floors.stop else Level.NOT_ENOUGH


# ---------------------------------------------------------------- what may be freed

@dataclass(frozen=True)
class CleanupItem:
    key: str
    kind: Kind
    bytes: int
    protected: bool = False


def protected_rounds(rounds_done: int, chosen: Optional[int]) -> FrozenSet[int]:
    """Round numbers (from 1) whose checkpoints are never offered: the chosen round and the one before it, or the latest two if none is chosen."""
    anchor = chosen if chosen is not None else rounds_done
    return frozenset(n for n in (anchor, anchor - 1) if 1 <= n <= max(rounds_done, anchor))


def checkpoint_item(round_number: int, size: int, rounds_done: int, chosen: Optional[int]) -> CleanupItem:
    keep = round_number in protected_rounds(rounds_done, chosen)
    return CleanupItem("checkpoint.round%d" % round_number, Kind.PRECIOUS if keep else Kind.DISPOSABLE, size, protected=keep)


def reclaimable(items: Iterable[CleanupItem]) -> List[CleanupItem]:
    """What *Free up space* may list: disposable first, then rebuildable, larger first. Precious, tool and protected items are never listed."""
    order = {Kind.DISPOSABLE: 0, Kind.REBUILDABLE: 1}
    ok = [i for i in items if i.kind in order and not i.protected and i.bytes > 0]
    return sorted(ok, key=lambda i: (order[i.kind], -i.bytes, i.key))


def pick_to_free(items: Iterable[CleanupItem], need: int) -> Tuple[List[CleanupItem], bool]:
    """A suggestion only (the person ticks what to remove): the fewest, in the order above, that frees `need`. The flag says whether it is enough."""
    picked: List[CleanupItem] = []
    freed = 0
    for item in reclaimable(items):
        if freed >= need:
            break
        picked.append(item)
        freed += item.bytes
    return picked, freed >= need


# ---------------------------------------------------------------- showing a size

def size_parts(n: int) -> Tuple[str, str]:
    """(number, unit) in decimal units, as drives and hosts label them, always with Latin digits and a plain point: ("846", "MB"), ("1.7", "GB")."""
    units = ("B", "KB", "MB", "GB", "TB")
    value, i = float(max(n, 0)), 0
    while value >= 999.5 and i < len(units) - 1:
        value /= 1000
        i += 1
    text = ("%.1f" % value) if (i > 0 and value < 9.95) else "%d" % round(value)
    return text, units[i]
