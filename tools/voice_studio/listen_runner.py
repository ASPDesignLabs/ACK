# SPDX-License-Identifier: GPL-3.0-or-later
"""python -m voice_studio.listen_runner JOB.json: say a few sentences with a voice the way the phone will, and write each one as a sound file (plan task VS-5.4).

core/listen.py runs this with the studio programs' own Python, which is the one place sherpa-onnx is installed; it is the same engine, at the same version, that ACK
uses on the phone. The job file says which voice (the model, the list of sounds core/phonemes.py made, the folder of pronunciation data), which sentences, and where to
write. The sentences go in the file, never on the command line, so they do not show in a list of running programs.

It says what it is doing as one JSON object per line on standard output and **never prints a sentence**, not even in an error: a person may have typed it, and what they wrote
stays out of every log. Exit codes: 0 done (a clip that came out silent is reported, not hidden), 1 something could not be done, 3 sherpa-onnx is not installed here.
Only the standard library is imported at the top, so the rules around it can be tested without sherpa-onnx.
"""
from __future__ import annotations

import array
import json
import math
import os
import sys
import time
import wave
from typing import Callable, List, Optional, Sequence

MAX_SENTENCES = 8
MAX_SENTENCE_CHARS = 300
MAX_JOB_BYTES = 64 * 1024
SPEAKER, SPEED = 0, 1.0              # what ACK passes: `engine.generate(text = text)` takes the library's own defaults (tests/test_vs_phonemes_contract.py reads that line)
SILENT_BELOW = 1e-4                  # a peak this low (about -80 dB) is silence
EXIT_OK, EXIT_PROBLEM, EXIT_NO_ENGINE = 0, 1, 3
JOB_KEYS = ("model", "tokens", "data_dir", "out_dir", "sentences")


class JobError(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def emit(event: dict) -> None:
    print(json.dumps(event, sort_keys=True), flush=True)


def real_engine(model: str, tokens: str, data_dir: str, threads: int):
    """sherpa-onnx's text-to-speech, set up as ACK sets it up on the phone: the voice's model, its list of sounds and the pronunciation data, on the processor."""
    import sherpa_onnx as so                      # not at the top: the tests of this file's rules run without it
    config = so.OfflineTtsConfig(model=so.OfflineTtsModelConfig(vits=so.OfflineTtsVitsModelConfig(model=model, tokens=tokens, data_dir=data_dir),
                                                                num_threads=threads, debug=False, provider="cpu"))
    return so.OfflineTts(config)


def read_job(path: str) -> dict:
    try:
        if os.path.getsize(path) > MAX_JOB_BYTES:
            raise JobError("bad_job")
        with open(path, encoding="utf-8") as handle:
            job = json.load(handle)
    except (OSError, ValueError, RecursionError):
        raise JobError("bad_job")
    if not isinstance(job, dict) or any(key not in job for key in JOB_KEYS):
        raise JobError("bad_job")
    for key in ("model", "tokens", "data_dir", "out_dir"):
        if not isinstance(job[key], str) or not os.path.isabs(job[key]):
            raise JobError("bad_job")
    sentences = job["sentences"]
    if not (isinstance(sentences, list) and 1 <= len(sentences) <= MAX_SENTENCES
            and all(isinstance(s, str) and 1 <= len(s) <= MAX_SENTENCE_CHARS and s.strip() for s in sentences)):
        raise JobError("bad_job")
    if not (os.path.isfile(job["model"]) and os.path.isfile(job["tokens"]) and os.path.isdir(job["data_dir"]) and os.path.isdir(job["out_dir"])):
        raise JobError("bad_job")
    return job


def pcm16(samples: Sequence[float]) -> bytes:
    data = array.array("h", (max(-32768, min(32767, int(round(v * 32767)))) for v in samples))
    if sys.byteorder == "big":
        data.byteswap()
    return data.tobytes()


def levels(samples: Sequence[float]) -> tuple:
    if not len(samples):
        return 0.0, 0.0
    peak = max(abs(v) for v in samples)
    return math.sqrt(math.fsum(v * v for v in samples) / len(samples)), peak


def write_wav(path: str, samples: Sequence[float], rate: int) -> None:
    with open(path, "xb") as handle:                              # never over a file that is there
        with wave.open(handle, "wb") as out:
            out.setnchannels(1)
            out.setsampwidth(2)
            out.setframerate(rate)
            out.writeframes(pcm16(samples))


def run(job: dict, engine_factory: Callable = real_engine, threads: int = 2) -> int:
    started = time.monotonic()
    try:
        engine = engine_factory(job["model"], job["tokens"], job["data_dir"], threads)
    except ImportError:
        emit({"event": "error", "code": "no_engine"})
        return EXIT_NO_ENGINE
    except Exception as error:                                    # a message could hold a sentence's words, so only the kind of error is said
        emit({"event": "error", "code": "load_failed", "kind": type(error).__name__})
        return EXIT_PROBLEM
    emit({"event": "loaded", "seconds": round(time.monotonic() - started, 2), "sample_rate": int(getattr(engine, "sample_rate", 0) or 0)})
    made: List[str] = []
    for number, sentence in enumerate(job["sentences"], 1):
        began = time.monotonic()
        try:
            audio = engine.generate(sentence, sid=SPEAKER, speed=SPEED)
            samples, rate = list(audio.samples), int(audio.sample_rate)
        except Exception as error:
            emit({"event": "error", "code": "speak_failed", "n": number, "kind": type(error).__name__})
            return EXIT_PROBLEM
        took = time.monotonic() - began
        name = "clip-%d.wav" % number
        try:
            write_wav(os.path.join(job["out_dir"], name), samples, rate)
        except FileExistsError:
            emit({"event": "error", "code": "exists", "n": number})
            return EXIT_PROBLEM
        except (OSError, wave.Error, OverflowError):
            emit({"event": "error", "code": "write_failed", "n": number})
            return EXIT_PROBLEM
        rms, peak = levels(samples)
        made.append(name)
        emit({"event": "clip", "n": number, "file": name, "seconds": round(len(samples) / rate, 2) if rate else 0.0, "sample_rate": rate, "made_in": round(took, 2),
              "rms": round(rms, 4), "peak": round(peak, 4), "silent": peak < SILENT_BELOW})
    emit({"event": "done", "clips": len(made)})
    return EXIT_OK


def main(argv: Optional[Sequence[str]] = None, engine_factory: Callable = real_engine) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    os.umask(0o077)                                               # what is written here is the person's own: readable by them only
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
