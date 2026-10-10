# SPDX-License-Identifier: GPL-3.0-or-later
"""How far along the recording is, and what to do next (plan task VS-3.7).

Pure decisions over facts that already exist: the dataset builder's preview (core/joblines.py reads it), the plan's hours, and the free room on the
drives. Nothing here reads a recording or runs a program, so the same numbers can be shown on any screen and tested without any audio.

Rules worth knowing:
- "Usable" minutes are the pieces the training set would really hold today (the dataset builder's own rules and audio checks), not everything that was
  said. A person is told about both: what is usable, and why the rest was left out.
- The target is the project's planned hours, taken as minutes of usable speech. It is a guide, never a gate: nothing here stops anyone going on.
- The next step is a suggestion. Nothing starts by itself.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Mapping, Optional, Tuple

from .diskbudget import DEFAULT_TABLE, DriveMap, Level, Line, SizeTable, check_step, floors_for, need_by_drive, person_lines
from .joblines import DatasetSummary, advice_for

WAITING_STATUSES = ("finishing", "queued", "transcribing")       # Freeform Studio's process.WAITING: a recording that is not finished being listened to
FAILED_STATUS = "error"
NEXT_STEPS = ("record_first", "finish_recordings", "record_more", "review", "build_training_set")       # each has words in the text catalog
REVIEWABLE = ("flagged", "not_approved", "tagged", "cuts_word")        # joblines.REASON_KINDS that a person can clear by looking at the piece
RESULTS_WITH_NUMBERS = ("built", "dry_run", "nothing_qualified", "no_takes_folder")


@dataclass(frozen=True)
class DiskNote:
    level: Level
    need: Dict[str, int]                        # per drive, what the rest of the plan will still write
    free: Dict[str, Optional[int]]
    short_by: Dict[str, int]                    # per drive, how much is missing to reach "enough" (0 if it is there)


@dataclass(frozen=True)
class Progress:
    minutes: float                              # usable speech now
    target_minutes: float
    fraction: float                             # minutes / target, never above 1
    pieces: int
    takes: int
    takes_waiting: int                          # still being listened to
    takes_failed: int
    takes_other: int                            # still being recorded or imported
    left_out: int
    reasons: Tuple[Tuple[str, int], ...]        # (joblines.REASON_KINDS member, how many), most first
    flags: Tuple[Tuple[str, int], ...]          # quality notes on the pieces left out, most first
    advice: Optional[str]                       # "short", "comfortable" or None (joblines.ADVICE_CODES)
    next_step: str                              # one of NEXT_STEPS
    disk: Optional[DiskNote]


def takes_by_state(summary: DatasetSummary) -> Tuple[int, int, int]:
    """(waiting, failed, other) among the recordings the dataset builder skipped because they are not finished."""
    waiting = sum(1 for _, status in summary.skipped_takes if status in WAITING_STATUSES)
    failed = sum(1 for _, status in summary.skipped_takes if status == FAILED_STATUS)
    return waiting, failed, len(summary.skipped_takes) - waiting - failed


def rest_of_plan(table: SizeTable, target_hours: float, minutes_done: float) -> list:
    """What the plan has yet to write: the recordings still to come (the part already recorded is already on the disk), and everything else in full."""
    lines = person_lines(table, target_hours)
    remaining_hours = max(0.0, target_hours - minutes_done / 60.0)
    return [Line(l.key, l.role, l.kind, int(remaining_hours * table.recording_per_hour)) if l.key == "person.recordings" else l for l in lines]


def disk_note(table: SizeTable, target_hours: float, minutes_done: float, custom_scratch: bool, free: Mapping[str, Optional[int]]) -> DiskNote:
    drives = DriveMap(tool="project", project="project", scratch="scratch" if custom_scratch else "project", backup="project")
    lines = rest_of_plan(table, target_hours, minutes_done)
    need = need_by_drive(lines, drives, 0)
    worst, short = Level.ENOUGH, {}
    for drive, bytes_needed in need.items():
        have = free.get(drive)
        floors = floors_for(table, holds_recordings=(drive == "project"))
        level = check_step(have, bytes_needed, floors)
        short[drive] = 0 if have is None else max(0, bytes_needed + floors.low - have)
        if level is Level.NOT_ENOUGH or (level is Level.TIGHT and worst is Level.ENOUGH):
            worst = level
    return DiskNote(worst, need, {d: free.get(d) for d in need}, short)


def next_step(takes: int, waiting: int, minutes: float, target: float, reasons: Tuple[Tuple[str, int], ...]) -> str:
    if takes == 0:
        return "record_first"
    if waiting > 0:
        return "finish_recordings"
    if minutes < target:
        return "record_more"
    if any(kind in REVIEWABLE and count > 0 for kind, count in reasons):
        return "review"
    return "build_training_set"


def assess(summary: DatasetSummary, planned_hours: float, *, free: Optional[Mapping[str, Optional[int]]] = None, custom_scratch: bool = False,
           table: SizeTable = DEFAULT_TABLE) -> Optional[Progress]:
    """The picture from the dataset builder's preview, or None when the preview was not about numbers (a refusal or a failed check)."""
    if summary.result not in RESULTS_WITH_NUMBERS:
        return None
    target_hours = max(float(planned_hours), 0.0)
    target = target_hours * 60.0
    usable = summary.minutes if summary.pieces else 0.0
    waiting, failed, other = takes_by_state(summary)
    takes = summary.takes
    fraction = 0.0 if target <= 0 else min(1.0, usable / target)
    disk = disk_note(table, target_hours, usable, custom_scratch, free) if free is not None else None
    return Progress(usable, target, fraction, summary.pieces, takes, waiting, failed, other, summary.left_out, summary.reasons, summary.flags,
                    advice_for(usable, summary.pieces), next_step(takes, waiting, usable, target, summary.reasons), disk)


def minutes_text(minutes: float) -> str:
    """A number of minutes for a sentence: whole minutes from ten up, one decimal place below that, no trailing ".0"."""
    if minutes >= 10:
        return str(int(minutes + 0.5))                      # half up, always: 10.5 reads 11 and 11.5 reads 12
    text = "%.1f" % minutes
    return text[:-2] if text.endswith(".0") else text


def lines(progress: Progress, catalog) -> Tuple[str, ...]:
    """The sentences a screen shows, in order: how far along, what is still waiting or failed, the length advice, the room (only when it is short), the next step."""
    out = [catalog.t("progress.minutes", minutes=minutes_text(progress.minutes), target=minutes_text(progress.target_minutes))]
    for key, count in (("progress.takes.waiting", progress.takes_waiting), ("progress.takes.failed", progress.takes_failed), ("progress.takes.other", progress.takes_other)):
        if count:
            out.append(catalog.count(key, count))
    if progress.advice:
        out.append(catalog.t("dataset.advice." + progress.advice))
    if progress.disk is not None and progress.disk.level is not Level.ENOUGH:
        out.append(catalog.t("budget.level." + progress.disk.level.value))
    out.append(catalog.t("progress.next." + progress.next_step))
    return tuple(out)
