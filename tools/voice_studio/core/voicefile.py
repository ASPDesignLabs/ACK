# SPDX-License-Identifier: GPL-3.0-or-later
"""Make my voice file from the chosen round (plan task VS-5.2): the five steps of checklist section J as one command, in a new folder, with nothing existing changed.

In order: export the chosen round's saved point to a model file; copy that round's settings file next to it under the exact name ACK needs; prepare the model for the phone
with the repository's own patcher (which keeps the original beside it); make the zip ACK takes; read the zip back as the phone would. Everything is written into **one new
folder** under the project's `exports` (named from the project, the round and the time, so no two runs share one). Nothing that was there is replaced, changed or removed, and
nothing is removed when a step fails: the folder is left as it is, with what was made, for the person to look at.

Refuses before it writes anything: no chosen round, a round still running (it would compete for the same memory and disk), a chosen round whose saved point is missing or not
whole (it says so instead of exporting another file), no settings file for that round, and not enough room. Nothing here says a word; core/voicefile_flow.py does.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional, Sequence, Tuple

from . import commands, rounds as rd, voicezip
from .diskbudget import DEFAULT_TABLE, Level, check_step, floors_for
from .envbuild import EnvPaths
from .paths import ProjectPaths
from .system import CommandResult, System

VOICE_NAME = commands.VOICE_NAME
STAGES = ("export", "settings", "patch", "zip", "check")                       # each has words in the text catalog
ERROR_CODES = ("no_chosen_round", "no_such_round", "round_running", "saved_point_missing", "saved_point_damaged", "no_settings", "no_room", "exists", "export_failed", "patch_failed",
               "zip_not_ok")                                                    # each has words in the text catalog
EXPORT_TIMEOUT_S = 900.0
PATCH_TIMEOUT_S = 300.0
NEED_BYTES = 3 * voicezip.MAX_MODEL_BYTES + 2 * voicezip.MAX_CONFIG_BYTES      # the model, its untouched copy and the zip, at the largest size ACK takes: an upper bound, not a guess about this model
TAIL_LINES = 6
TAIL_CHARS = 600


class VoiceFileError(Exception):
    """`code` is one of ERROR_CODES; `detail` is a short fact for Show details; `folder` is the new folder when one had been made (it is left as it is)."""

    def __init__(self, code: str, detail: str = "", folder: str = "", stage: str = ""):
        super().__init__(code + (": " + detail if detail else ""))
        self.code = code
        self.detail = detail
        self.folder = folder
        self.stage = stage


@dataclass(frozen=True)
class VoicePlan:
    round: int
    trained_minutes: int
    checkpoint: str
    checkpoint_bytes: int
    settings: str
    folder: str
    model: str
    model_config: str
    zip_path: str
    need_bytes: int
    free_bytes: Optional[int]
    room: Level


@dataclass(frozen=True)
class Made:
    folder: str
    model: str
    model_config: str
    zip_path: str
    zip_bytes: int
    model_sha256: str
    config_sha256: str
    skipped_symbols: Tuple[str, ...]


def voice_folder_name(project_id: str, number: int, stamp: str) -> str:
    """`voice-check-round-003-20261011-130000` from a time stamp such as 2026-10-11T13:00:00Z: a new name every time, so a run never lands in an earlier one's folder."""
    digits = "".join(c for c in stamp if c.isdigit())
    if len(digits) < 14 or not commands.SAFE_NAME.match(project_id) or number < 1:
        raise commands.CommandError("bad_value", "stamp")
    return "%s-round-%03d-%s-%s" % (project_id, number, digits[:8], digits[8:14])


def settings_file(paths: ProjectPaths, number: int) -> str:
    """The settings file the trainer wrote for that round (core/rounds.py::plan_round names it)."""
    return "%s/round-%03d.json" % (paths.round_configs, number)


@dataclass(frozen=True)
class PickedRound:
    number: int
    trained_minutes: int
    checkpoint: str
    checkpoint_bytes: int
    settings: str


def pick_round(paths: ProjectPaths, record: rd.Record, number: Optional[int] = None) -> PickedRound:
    """The round a voice is made from: the chosen one, or the one with this number. Refuses, with a code, when a voice cannot honestly be made from it: a round is still training
    (the export would compete with it for memory and disk), no such round, its saved point missing or cut short, or no settings file. Never falls back to another round or file."""
    running = rd.active(record)
    if running is not None:
        raise VoiceFileError("round_running", str(running.number))
    if number is None:
        pick = rd.chosen(record)
        if pick is None:
            raise VoiceFileError("no_chosen_round")
    else:
        pick = next((r for r in record.rounds if r.number == number), None)
        if pick is None:
            raise VoiceFileError("no_such_round", str(number))
    status = rd.checkpoint_status(paths, pick)
    if status == "damaged":
        raise VoiceFileError("saved_point_damaged", str(pick.number))
    if status != "ok":
        raise VoiceFileError("saved_point_missing", str(pick.number))
    checkpoint = rd.checkpoint_file(paths, pick) or ""
    settings = settings_file(paths, pick.number)
    if not os.path.isfile(settings) or os.path.islink(settings):
        raise VoiceFileError("no_settings", str(pick.number))
    return PickedRound(pick.number, rd.trained_minutes(record, pick.number), checkpoint, os.stat(checkpoint).st_size, settings)


def plan_voice(paths: ProjectPaths, record: rd.Record, project_id: str, stamp: str, free_bytes: Optional[int]) -> VoicePlan:
    """What making the voice file would do. Changes nothing. Refuses, with a code, when it cannot be done honestly."""
    pick = pick_round(paths, record)
    folder = "%s/%s" % (paths.exports, voice_folder_name(project_id, pick.number, stamp))
    room = check_step(free_bytes, NEED_BYTES, floors_for(DEFAULT_TABLE, holds_recordings=True))
    if room is Level.NOT_ENOUGH:
        raise VoiceFileError("no_room", "%d free, %d needed" % (free_bytes or 0, NEED_BYTES))
    return VoicePlan(round=pick.number, trained_minutes=pick.trained_minutes, checkpoint=pick.checkpoint, checkpoint_bytes=pick.checkpoint_bytes,
                     settings=pick.settings, folder=folder, model="%s/%s.onnx" % (folder, VOICE_NAME), model_config="%s/%s.onnx.json" % (folder, VOICE_NAME),
                     zip_path="%s/%s.zip" % (folder, os.path.basename(folder)), need_bytes=NEED_BYTES, free_bytes=free_bytes, room=room)


def _tail(done: Optional[CommandResult]) -> str:
    """The last few lines the program said, for Show details; nothing when it could not be run at all."""
    if done is None:
        return ""
    lines = [l.rstrip() for l in (done.stderr + "\n" + done.stdout).splitlines() if l.strip()]
    return " | ".join(lines[-TAIL_LINES:])[-TAIL_CHARS:]


def prepare_voice(folder: str, checkpoint: str, settings: str, model: str, training: EnvPaths, tools_dir: str, system: System, tell: Callable[[str], None]) -> None:
    """The first three steps of making a voice, in a folder that already exists and is new: export the saved point to a model file, give it its settings file under the
    exact name, and prepare it for the phone with the patcher (which keeps the original beside it). Any failure raises VoiceFileError; the folder is left as it is."""
    tell("export")
    export = commands.export_command(training, checkpoint, folder)
    done = system.run(export.argv, timeout=EXPORT_TIMEOUT_S, cwd=export.cwd)
    if done is None or done.returncode != 0 or not os.path.isfile(model):
        raise VoiceFileError("export_failed", _tail(done), folder, "export")
    tell("settings")
    commands.copy_config(settings, model)
    tell("patch")
    patch = commands.patch_command(training.python, tools_dir, model)
    done = system.run(patch.argv, timeout=PATCH_TIMEOUT_S, cwd=patch.cwd)
    if done is None or done.returncode != 0:
        raise VoiceFileError("patch_failed", _tail(done), folder, "patch")


def make_voice(plan: VoicePlan, training: EnvPaths, tools_dir: str, system: System, stage: Optional[Callable[[str], None]] = None) -> Made:
    """Do the five steps. `stage` is told the name of each one just before it starts (the screen says it). Any failure raises VoiceFileError (or, from the zip, voicezip.VoiceZipError); the new folder is left as it is."""
    tell = stage or (lambda _name: None)
    try:
        os.makedirs(os.path.dirname(plan.folder), mode=0o700, exist_ok=True)
        os.mkdir(plan.folder, 0o700)
    except FileExistsError:
        raise VoiceFileError("exists", os.path.basename(plan.folder))
    except OSError as exc:
        raise VoiceFileError("exists", exc.strerror or type(exc).__name__)
    here = plan.folder
    prepare_voice(here, plan.checkpoint, plan.settings, plan.model, training, tools_dir, system, tell)
    tell("zip")
    report = voicezip.write_voice_zip(Path(plan.model), Path(plan.model_config), Path(plan.zip_path))          # raises voicezip.VoiceZipError, with its own words; the folder is left as it is
    tell("check")
    left = voicezip.verify_voice_zip(Path(plan.zip_path))
    if left:
        raise VoiceFileError("zip_not_ok", ",".join(left), here, "check")
    return Made(here, plan.model, plan.model_config, plan.zip_path, report.zip_bytes, report.model_sha256, report.config_sha256, report.skipped_symbols)


def existing_voice_files(paths: ProjectPaths) -> Tuple[Tuple[str, str, int], ...]:
    """(folder name, zip path, zip bytes) for every folder under `exports` that holds a zip made by this command. Reads the disk; nothing else."""
    found = []
    try:
        names = sorted(os.listdir(paths.exports))
    except OSError:
        return ()
    for name in names:
        folder = "%s/%s" % (paths.exports, name)
        zip_path = "%s/%s.zip" % (folder, name)
        if os.path.isdir(folder) and not os.path.islink(folder) and os.path.isfile(zip_path) and not os.path.islink(zip_path):
            found.append((name, zip_path, os.stat(zip_path).st_size))
    return tuple(found)
