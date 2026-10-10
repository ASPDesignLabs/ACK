# SPDX-License-Identifier: GPL-3.0-or-later
"""The exact commands for each step of making a voice, built as lists of words (never a shell line), checked before they are handed to the job supervisor.

These are the commands docs/VOICE_TRAINING_GUIDE.md has people copy by hand, in one place and with the guide's rules enforced: the dataset is always a new folder, the
training cache is always a new folder (a cache from other audio silently trains on the old audio), `--data.audio_dir` is exactly the `wav/` folder, training starts from a
`.ckpt` file, and the finished model is always patched for the phone. Each environment's own Python and launcher are used (core/envbuild.py), so a fix lives in the launcher
and no command carries a workaround.

Numbers marked PROVISIONAL are the guide's, from one 8 GB card; the spike on a real GPU (plan task VS-0.2) replaces them with a table by memory.
This file builds and checks; it starts nothing and reads no output. Starting is core/jobs.py.
"""
from __future__ import annotations

import os
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Tuple

from .envbuild import EnvPaths
from .jobs import JobSpec

ERROR_CODES = ("bad_path", "exists", "dataset_incomplete", "cache_exists", "bad_checkpoint", "bad_value")        # each has words in the text catalog
CODE = "en-US"
VOICE_NAME = "my_voice"
ESPEAK_VOICE = "en-us"
SAMPLE_RATE = 22050
BATCH_SIZE = 12                 # PROVISIONAL: the guide's, for an 8 GB card (VS-0.2 gives a table by memory)
NUM_WORKERS = 4                 # PROVISIONAL
CHECK_VAL_EVERY_N_EPOCH = 10   # PROVISIONAL
ROUND_MINUTES = 25              # PROVISIONAL (decision D12)
SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
CHECKPOINT_DIR = re.compile(r"^version_(\d+)$")


class CommandError(Exception):
    """`code` is one of ERROR_CODES; `detail` is a short fact (a path or a name) for Show details."""

    def __init__(self, code: str, detail: str = ""):
        super().__init__(code + (": " + detail if detail else ""))
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class Command:
    kind: str                           # the job kind: process, dataset, train, export, patch
    argv: Tuple[str, ...]
    cwd: str
    gpu: bool = False                   # holds the graphics card while it runs (only one such job at a time)
    env: Tuple[Tuple[str, str], ...] = ()

    def job(self, project_id: str, force_grace_s: float = 10.0) -> JobSpec:
        return JobSpec(self.kind, project_id, self.argv, self.cwd, dict(self.env), self.gpu, force_grace_s)


def _absolute(path: object, what: str) -> str:
    text = str(path)
    if not text.startswith("/") or "\x00" in text or "\n" in text:
        raise CommandError("bad_path", what)
    return os.path.normpath(text)


# ---------------------------------------------------------------- listening to what was recorded, then making the dataset

def process_command(studio: EnvPaths, tools_dir: str, recordings: str, asr_model: str, device: str = "cpu") -> Command:
    """Finish the recordings that are waiting (decode, listen, cut) with Freeform Studio's own processor. On the graphics card only when asked; then it holds it."""
    if device not in ("cpu", "cuda"):
        raise CommandError("bad_value", "device")
    argv = (studio.python, "-m", "freeform_studio.process", "--output", _absolute(recordings, "recordings"), "--code", CODE, "--asr-model", asr_model,
            "--asr-device", device, "--json")
    return Command("process", argv, _absolute(tools_dir, "tools"), gpu=(device == "cuda"))


def dataset_command(studio: EnvPaths, tools_dir: str, recordings: str, out_dir: str, *, dry_run: bool = False) -> Command:
    """Build a new dataset folder (or preview one). A folder that already holds anything is refused here, as Freeform Studio refuses it, so the person is told before a job starts."""
    out = _absolute(out_dir, "dataset")
    if not dry_run and os.path.lexists(out) and (not os.path.isdir(out) or os.listdir(out)):
        raise CommandError("exists", os.path.basename(out))
    argv = [studio.python, "-m", "freeform_studio.build_dataset", "--output", _absolute(recordings, "recordings"), "--code", CODE, "--out", out, "--json"]
    if dry_run:
        argv.append("--dry-run")
    return Command("dataset", tuple(argv), _absolute(tools_dir, "tools"))


def dataset_folder_name(stamp: str) -> str:
    """`dataset-20261010-120000` from a time stamp such as 2026-10-10T12:00:00Z; a new name every time, so a dataset is never overwritten and each has its own cache."""
    digits = re.sub(r"\D", "", stamp)
    if len(digits) < 14:
        raise CommandError("bad_value", "stamp")
    return "dataset-%s-%s" % (digits[:8], digits[8:14])


def check_dataset(folder: str) -> int:
    """The number of rows in a finished dataset, or CommandError("dataset_incomplete"): `metadata.csv` and a `wav/` folder holding every file it names."""
    meta, wav = os.path.join(folder, "metadata.csv"), os.path.join(folder, "wav")
    if not os.path.isfile(meta) or not os.path.isdir(wav):
        raise CommandError("dataset_incomplete", os.path.basename(folder))
    rows = 0
    with open(meta, encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            name = line.split("|", 1)[0]
            if not name or "/" in name or not os.path.isfile(os.path.join(wav, name)):
                raise CommandError("dataset_incomplete", name or "empty name")
            rows += 1
    if rows == 0:
        raise CommandError("dataset_incomplete", "no rows")
    return rows


# ---------------------------------------------------------------- one training round

def train_command(training: EnvPaths, dataset: str, run_dir: str, cache_dir: str, config_path: str, checkpoint: str, *, minutes: int = ROUND_MINUTES,
                  batch_size: int = BATCH_SIZE, workers: int = NUM_WORKERS, check_every: int = CHECK_VAL_EVERY_N_EPOCH) -> Command:
    """One round: train from `checkpoint` for about `minutes`, then stop. Holds the graphics card. Starts from the base voice the first time and from the latest of the
    person's own checkpoints after that (the caller chooses which), never the base again by accident."""
    for number, name in ((minutes, "minutes"), (batch_size, "batch_size"), (workers, "workers"), (check_every, "check_every")):
        if isinstance(number, bool) or not isinstance(number, int) or number < 1:
            raise CommandError("bad_value", name)
    dataset, run_dir, cache_dir = _absolute(dataset, "dataset"), _absolute(run_dir, "run"), _absolute(cache_dir, "cache")
    config_path, checkpoint = _absolute(config_path, "config"), _absolute(checkpoint, "checkpoint")
    check_dataset(dataset)
    if os.path.lexists(cache_dir):
        raise CommandError("cache_exists", os.path.basename(cache_dir))                  # a cache from other audio trains on the old audio without a word
    if not checkpoint.endswith(".ckpt") or not os.path.isfile(checkpoint):
        raise CommandError("bad_checkpoint", os.path.basename(checkpoint))
    hours, rest = divmod(minutes, 60)
    argv = (training.python, training.launcher, "piper.train", "fit",
            "--data.voice_name", VOICE_NAME, "--data.csv_path", dataset + "/metadata.csv", "--data.audio_dir", dataset + "/wav",
            "--model.sample_rate", str(SAMPLE_RATE), "--data.espeak_voice", ESPEAK_VOICE, "--data.cache_dir", cache_dir, "--data.config_path", config_path,
            "--data.batch_size", str(batch_size), "--data.num_workers", str(workers), "--trainer.check_val_every_n_epoch", str(check_every),
            "--trainer.log_every_n_steps", "1", "--trainer.max_time", "00:%02d:%02d:00" % (hours, rest), "--ckpt_path", checkpoint)
    return Command("train", argv, run_dir, gpu=True)


@dataclass(frozen=True)
class Checkpoint:
    version: int
    path: str
    size: int
    mtime: float


def find_checkpoints(run_dir: str) -> List[Checkpoint]:
    """The `last.ckpt` of every `lightning_logs/version_N` under a run folder, oldest version first. Reads the disk; nothing else."""
    base = os.path.join(run_dir, "lightning_logs")
    found: List[Checkpoint] = []
    try:
        names = os.listdir(base)
    except OSError:
        return found
    for name in names:
        match = CHECKPOINT_DIR.match(name)
        path = os.path.join(base, name, "checkpoints", "last.ckpt")
        if match and os.path.isfile(path):
            info = os.stat(path)
            found.append(Checkpoint(int(match.group(1)), path, info.st_size, info.st_mtime))
    return sorted(found, key=lambda c: c.version)


def latest_checkpoint(run_dir: str) -> Optional[Checkpoint]:
    return (find_checkpoints(run_dir) or [None])[-1]


# ---------------------------------------------------------------- listening: make the model, give it its settings, prepare it for the phone

def export_command(training: EnvPaths, checkpoint: str, out_dir: str, name: str = VOICE_NAME) -> Command:
    """Export a checkpoint to a model file. The workaround for the newer exporter lives in the launcher, not here."""
    if not SAFE_NAME.match(name):
        raise CommandError("bad_value", "name")
    checkpoint = _absolute(checkpoint, "checkpoint")
    out = _absolute(out_dir, "export")
    if not checkpoint.endswith(".ckpt") or not os.path.isfile(checkpoint):
        raise CommandError("bad_checkpoint", os.path.basename(checkpoint))
    target = "%s/%s.onnx" % (out, name)
    if os.path.lexists(target):
        raise CommandError("exists", name + ".onnx")
    argv = (training.python, training.launcher, "piper.train.export_onnx", "--checkpoint", checkpoint, "--output-file", target)
    return Command("export", argv, out)


def config_name(model_path: str) -> str:
    """The settings file sits next to the model and is named exactly `<model>.onnx.json` (guide section 5); getting this name wrong stops the next steps."""
    if not model_path.endswith(".onnx"):
        raise CommandError("bad_path", os.path.basename(model_path))
    return model_path + ".json"


def copy_config(config_path: str, model_path: str) -> str:
    """Copy the config training wrote next to the model, under the exact name. Never replaces a file that is there. Returns the new path."""
    source, target = _absolute(config_path, "config"), config_name(_absolute(model_path, "model"))
    if os.path.lexists(target):
        raise CommandError("exists", os.path.basename(target))
    if not os.path.isfile(source):
        raise CommandError("bad_path", os.path.basename(source))
    temp = target + ".part"
    shutil.copyfile(source, temp)
    os.chmod(temp, 0o600)
    os.replace(temp, target)
    return target


def patch_command(python: str, tools_dir: str, model_path: str) -> Command:
    """Prepare the model for the phone with the repository's own patcher (it keeps the original beside it and is safe to run twice)."""
    model = _absolute(model_path, "model")
    config = config_name(model)
    script = os.path.join(_absolute(tools_dir, "tools"), "patch_voice_for_sherpa_onnx.py")
    if not os.path.isfile(script):
        raise CommandError("bad_path", "patch_voice_for_sherpa_onnx.py")
    return Command("patch", (python, script, model, config), os.path.dirname(model))
