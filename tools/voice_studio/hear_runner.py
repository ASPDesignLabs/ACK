# SPDX-License-Identifier: GPL-3.0-or-later
"""python -m voice_studio.hear_runner JOB.json: write down what is said in a few short sound files, with the listening model (plan task VS-5.5).

core/listen.py runs this with the studio programs' own Python, after the sound files of a voice were made, so a person can read whether the words came out. The job file names the
folder of the listening model and the sound files; it holds **no sentence** (this program is never told what the voice was asked to say), and what it prints is what it heard.

It never reaches the network: the model is loaded from the folder given and nothing else (`local_files_only`, and Hugging Face's libraries switched to offline mode). It reads only plain
mono 16-bit sound files, as listen_runner.py writes them, and makes them 16 kHz for the model with a plain average between neighbouring samples. Exit codes: 0 done, 1 something could not be
done, 3 the listening program is not installed here. Only the standard library is imported at the top, so the rules around it are tested without the listening program.
"""
from __future__ import annotations

import array
import json
import os
import sys
import time
import wave
from typing import Callable, List, Optional, Sequence

MAX_CLIPS = 8
MAX_CLIP_SECONDS = 120
MAX_JOB_BYTES = 64 * 1024
TARGET_RATE = 16000
EXIT_OK, EXIT_PROBLEM, EXIT_NO_ENGINE = 0, 1, 3
OFFLINE = {"HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1", "HF_HUB_DISABLE_TELEMETRY": "1", "DO_NOT_TRACK": "1"}


class JobError(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def emit(event: dict) -> None:
    print(json.dumps(event, sort_keys=True), flush=True)


def real_engine(model_dir: str):
    """The listening model on the processor, from this folder only. English: the model that is pinned is the English one."""
    from faster_whisper import WhisperModel                 # not at the top: the tests of this file's rules run without it
    import numpy as np
    model = WhisperModel(model_dir, device="cpu", compute_type="int8", local_files_only=True)

    class Hearer:
        def transcribe(self, samples: Sequence[float]) -> str:
            segments, _info = model.transcribe(np.asarray(samples, dtype=np.float32), language="en", beam_size=1, condition_on_previous_text=False)
            return " ".join(part.text.strip() for part in segments).strip()
    return Hearer()


def read_job(path: str) -> dict:
    try:
        if os.path.getsize(path) > MAX_JOB_BYTES:
            raise JobError("bad_job")
        with open(path, encoding="utf-8") as handle:
            job = json.load(handle)
    except (OSError, ValueError, RecursionError):
        raise JobError("bad_job")
    if not isinstance(job, dict) or sorted(job) != ["clips", "model_dir"]:
        raise JobError("bad_job")
    model_dir, clips = job["model_dir"], job["clips"]
    if not (isinstance(model_dir, str) and os.path.isabs(model_dir) and os.path.isdir(model_dir)):
        raise JobError("bad_job")
    if not (isinstance(clips, list) and 1 <= len(clips) <= MAX_CLIPS and all(isinstance(c, str) and os.path.isabs(c) and os.path.isfile(c) and not os.path.islink(c) for c in clips)):
        raise JobError("bad_job")
    return job


def read_wav(path: str) -> tuple:
    """(samples as numbers between -1 and 1, the rate) of a mono 16-bit sound file; JobError("unreadable") for anything else or anything too long."""
    try:
        with wave.open(path, "rb") as source:
            if source.getnchannels() != 1 or source.getsampwidth() != 2 or not 8000 <= source.getframerate() <= 96000:
                raise JobError("unreadable")
            rate, frames = source.getframerate(), source.getnframes()
            if frames > rate * MAX_CLIP_SECONDS:
                raise JobError("unreadable")
            data = array.array("h")
            data.frombytes(source.readframes(frames))
    except (OSError, wave.Error, EOFError):
        raise JobError("unreadable")
    if sys.byteorder == "big":
        data.byteswap()
    return [v / 32768.0 for v in data], rate


def resample(samples: Sequence[float], rate: int, target: int = TARGET_RATE) -> List[float]:
    """The same sound at another rate, each new sample the weighted average of the two old ones on either side of its moment."""
    if rate == target or not samples:
        return list(samples)
    count = max(1, int(len(samples) * target / rate))
    last = len(samples) - 1
    step = rate / target
    out = []
    for i in range(count):
        position = i * step
        low = min(int(position), last)
        high = min(low + 1, last)
        fraction = position - low
        out.append(samples[low] * (1.0 - fraction) + samples[high] * fraction)
    return out


def run(job: dict, engine_factory: Callable = real_engine) -> int:
    started = time.monotonic()
    try:
        engine = engine_factory(job["model_dir"])
    except ImportError:
        emit({"event": "error", "code": "no_engine"})
        return EXIT_NO_ENGINE
    except Exception as error:
        emit({"event": "error", "code": "load_failed", "kind": type(error).__name__})
        return EXIT_PROBLEM
    emit({"event": "loaded", "seconds": round(time.monotonic() - started, 2)})
    for number, path in enumerate(job["clips"], 1):
        try:
            samples, rate = read_wav(path)
        except JobError:
            emit({"event": "error", "code": "unreadable", "n": number})
            return EXIT_PROBLEM
        try:
            text = engine.transcribe(resample(samples, rate))
        except Exception as error:
            emit({"event": "error", "code": "hear_failed", "n": number, "kind": type(error).__name__})
            return EXIT_PROBLEM
        emit({"event": "heard", "n": number, "text": str(text)})
    emit({"event": "done", "clips": len(job["clips"])})
    return EXIT_OK


def main(argv: Optional[Sequence[str]] = None, engine_factory: Callable = real_engine) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    os.umask(0o077)
    for name, value in OFFLINE.items():
        os.environ[name] = value                              # forced, not defaulted: a stray HF_HUB_OFFLINE=0 must not undo it
    if len(args) != 1:
        emit({"event": "error", "code": "bad_job"})
        return EXIT_PROBLEM
    try:
        job = read_job(args[0])
    except JobError as error:
        emit({"event": "error", "code": error.code})
        return EXIT_PROBLEM
    return run(job, engine_factory)


if __name__ == "__main__":
    sys.exit(main())
