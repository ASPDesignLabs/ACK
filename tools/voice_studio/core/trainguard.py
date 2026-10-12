# SPDX-License-Identifier: GPL-3.0-or-later
"""Automatic settings and guards for a training round (plan task VS-4.3; decisions P8 and P11, findings F13, F24 and F25).

Pure rules over numbers the caller reads (core/rounds_flow.py does the reading): which batch size the graphics card can take, how often the trainer should save
a check, whether the graphics card has the room that batch needs right now, how much disk a round writes and whether the drives have it, and which floors a
running round is stopped at (core/jobs.py does the watching, in the detached runner, so it works with the window closed).

**Every number here is provisional, and says on what basis.** "measured" is one real run on one card (the developer's RTX 4060, 8 GiB: batch 12 peaked at 7,418 to
7,793 MiB of 8,188, with about 2.1 GiB of that used by other programs, F12 and F24); "guess" is arithmetic from that, flagged so the screen can say so.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Mapping, Optional, Sequence, Tuple

from .commands import BATCH_SIZE, CHECK_VAL_EVERY_N_EPOCH, SAMPLE_RATE
from .diskbudget import DriveMap, Level, Line, Role, SizeTable, Kind, check_step, floors_for
from .preflight import find_smi
from .system import System

# ---------------------------------------------------------------- the batch size

BATCH_TABLE = ((8000, 12, "measured"), (6000, 8, "guess"), (4000, 4, "guess"))       # (the card's memory in MiB or more, the batch, on what basis)
MIN_GPU_MIB = BATCH_TABLE[-1][0]
BASES = ("measured", "guess", "unknown")                                             # the ways a batch can be known; each has words in the text catalog. A card below the table has none: "too_small"


@dataclass(frozen=True)
class BatchChoice:
    batch: Optional[int]          # None: this card is too small to train on
    basis: str                    # one of BASES


def batch_for(total_mib: Optional[int]) -> BatchChoice:
    """The batch for a card with this much memory in all. An unreadable amount keeps the batch that was measured; below the smallest row there is no batch to offer."""
    if total_mib is None:
        return BatchChoice(BATCH_SIZE, "unknown")
    for floor, batch, basis in BATCH_TABLE:
        if total_mib >= floor:
            return BatchChoice(batch, basis)
    return BatchChoice(None, "too_small")


# ---------------------------------------------------------------- how often to save a check

SECONDS_PER_STEP_AT_12 = 0.52         # measured: 1.85 to 1.92 steps a second at batch 12 on the RTX 4060 (F24); scaled with the batch for any other
CHECK_TARGET_S = 120                  # about one check every two minutes of training: a round loses at most the time since its last check (F25)
MAX_CHECK_EVERY = CHECK_VAL_EVERY_N_EPOCH


def steps_per_epoch(clips: int, batch: int) -> int:
    """The trainer drops a last short batch: 23 clips at batch 12 is one step an epoch, and a set of 24 to 35 is two (F13, F25)."""
    return max(1, clips // max(1, batch))


def check_every(clips: int, batch: int) -> int:
    """A whole number of epochs, from 1 to 10: a short epoch (a small set) checks every 10 as before, a long one (a real set) checks sooner so that a round that ends
    at its time limit has lost about two minutes at most, not several."""
    epoch_s = steps_per_epoch(clips, batch) * SECONDS_PER_STEP_AT_12 * max(1, batch) / 12
    return max(1, min(MAX_CHECK_EVERY, int(CHECK_TARGET_S / epoch_s + 0.5)))


def lost_seconds(clips: int, batch: int, every: int) -> float:
    """The most a round can lose at its end: the time of `every` epochs."""
    return every * steps_per_epoch(clips, batch) * SECONDS_PER_STEP_AT_12 * max(1, batch) / 12


# ---------------------------------------------------------------- the graphics card's room

GPU_BASE_MIB = 1200                   # GUESS: what training holds whatever the batch (the model, the optimiser, the workspace)
GPU_PER_ITEM_MIB = 380                # GUESS: and for each clip in a batch; with the base this gives 5,760 MiB at batch 12, the measured peak less the 2.1 GiB other programs used
GPU_TIGHT_PERCENT = 90                # between this share of the need and the need is a warning, not a refusal


def gpu_need_mib(batch: int) -> int:
    return GPU_BASE_MIB + GPU_PER_ITEM_MIB * batch


@dataclass(frozen=True)
class GpuRoom:
    level: Level
    free_mib: Optional[int]       # None: the card's memory use could not be read, so nothing is judged
    need_mib: int


def judge_gpu_room(total_mib: Optional[int], used_mib: Optional[int], batch: int) -> GpuRoom:
    """Is there room on the card right now for this batch? Other programs may be holding some (the Windows desktop on WSL, a browser, a speech model left loaded)."""
    need = gpu_need_mib(batch)
    if total_mib is None or used_mib is None:
        return GpuRoom(Level.ENOUGH, None, need)
    free = max(0, total_mib - used_mib)
    if free >= need:
        return GpuRoom(Level.ENOUGH, free, need)
    if free * 100 >= need * GPU_TIGHT_PERCENT:
        return GpuRoom(Level.TIGHT, free, need)
    return GpuRoom(Level.NOT_ENOUGH, free, need)


@dataclass(frozen=True)
class GpuMemory:
    total_mib: int
    used_mib: int


def parse_gpu_memory(stdout: str) -> Optional[GpuMemory]:
    """Output of: nvidia-smi --query-gpu=name,memory.used,memory.total --format=csv,noheader,nounits. The card with the most memory, as the preflight picks."""
    best: Optional[GpuMemory] = None
    for line in stdout.splitlines():
        parts = [p.strip() for p in line.rsplit(",", 2)]
        if len(parts) != 3 or not (re.fullmatch(r"\d+", parts[1]) and re.fullmatch(r"\d+", parts[2])):
            continue
        card = GpuMemory(int(parts[2]), int(parts[1]))
        if best is None or card.total_mib > best.total_mib:
            best = card
    return best


def read_gpu_memory(system: System) -> Optional[GpuMemory]:
    """Ask the driver; None when there is no driver, it fails, or it says something unreadable. Only looks."""
    smi = find_smi(system)
    if smi is None:
        return None
    result = system.run([smi, "--query-gpu=name,memory.used,memory.total", "--format=csv,noheader,nounits"])
    if result is None or result.returncode != 0:
        return None
    return parse_gpu_memory(result.stdout)


# ---------------------------------------------------------------- the disk a round writes

CACHE_FALLBACK_HOURS = 0.5            # a training set is never judged as smaller than this when its size is worked out (the floor of the plan, MIN_PLAN_HOURS)


def hours_of_speech(wav_bytes: int) -> float:
    """The length of a training set from the size of its wav files (22,050 Hz, mono, 16 bits: 158,760,000 bytes an hour)."""
    return max(0, wav_bytes) / (SAMPLE_RATE * 2 * 3600)


def round_lines(table: SizeTable, hours: float) -> Tuple[Line, ...]:
    """What one round writes: the saved files in the project's run folder (the last one and the five best), and the trainer's working folder in scratch."""
    return (Line("round.checkpoints", Role.PROJECT, Kind.DISPOSABLE, table.checkpoints_per_round * table.checkpoint),
            Line("round.cache", Role.SCRATCH, Kind.REBUILDABLE, int(max(hours, CACHE_FALLBACK_HOURS) * table.training_cache_per_hour)))


@dataclass(frozen=True)
class DriveVerdict:
    drive: str
    need: int
    free: Optional[int]
    level: Level
    short_by: int                 # how much more has to be free for the step to be comfortable (0 if it is)


@dataclass(frozen=True)
class DiskCheck:
    level: Level
    drives: Tuple[DriveVerdict, ...]


_ORDER = {Level.ENOUGH: 0, Level.TIGHT: 1, Level.NOT_ENOUGH: 2}


def judge_round_disk(table: SizeTable, hours: float, drives: DriveMap, free: Mapping[str, Optional[int]]) -> DiskCheck:
    """Before a round starts (P11): each drive that will be written to must stay above its floors afterwards. The drive that holds recordings is held to a higher floor than
    Freeform Studio's own, so a round can end on a full disk but never costs a recording. A drive whose free space cannot be read is not judged (and the answer says so)."""
    needs: dict = {}
    for line in round_lines(table, hours):
        if line.bytes > 0:
            needs[drives.of(line.role)] = needs.get(drives.of(line.role), 0) + line.bytes
    verdicts = []
    for drive in sorted(needs):
        have = free.get(drive)
        floors = floors_for(table, holds_recordings=(drive == drives.of(Role.PROJECT)))
        level = check_step(have, needs[drive], floors)
        comfortable = floors.low + needs[drive]
        verdicts.append(DriveVerdict(drive, needs[drive], have, level, 0 if have is None else max(0, comfortable - have)))
    worst = max((v.level for v in verdicts), key=lambda l: _ORDER[l], default=Level.ENOUGH)
    return DiskCheck(worst, tuple(verdicts))


# ---------------------------------------------------------------- what a running round is watched against

def watches(table: SizeTable, project_run: str, scratch: str, drives: DriveMap) -> Tuple[Tuple[str, int], ...]:
    """(a folder on each drive the round writes to, the free space below which the round is asked to stop). The runner reads these from the job's file, so the guard
    works with the window closed. When scratch is on the project's drive there is one watch, at the higher floor."""
    project_floor = floors_for(table, holds_recordings=True).stop
    found = [(project_run, project_floor)]
    if drives.of(Role.SCRATCH) != drives.of(Role.PROJECT):
        found.append((scratch, floors_for(table, holds_recordings=False).stop))
    return tuple(found)
