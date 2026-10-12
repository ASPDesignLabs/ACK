# SPDX-License-Identifier: GPL-3.0-or-later
"""Helpers for the recordings tests: real audio files made with the standard library, folders of each kind of voice data, a recordings folder with takes written by hand,
and a stand-in for the studio programs that runs Freeform Studio's real processor with its fake listener so a whole job can run for real."""
import json
import math
import os
import shutil
import stat
import struct
import sys
import wave
from pathlib import Path

import pytest

from voice_studio.core.envbuild import EnvPaths
from voice_studio.core.system import CommandResult

needs_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None, reason="ffmpeg is not installed")

TEXTS = ["The tide came in slowly.", "It rained all day long.", "Gulls circled over the pier.", "We walked along the shore.", "The lamp was left on."]
STUDIO_WRAPPER = '''#!%s
import os, sys
args = sys.argv[1:]
if args[:2] == ["-m", "freeform_studio.process"]:
    args += ["--asr-engine", "fake"]
os.execv(sys.executable, [sys.executable] + args)
'''


def tone_wav(path, seconds=2.2, bursts=((0.3, 1.9),), f0=200.0, rate=48000, amp=0.5):
    """Sine bursts (start_s, end_s) on digital silence, mono 16-bit."""
    os.makedirs(os.path.dirname(str(path)), exist_ok=True)
    frames = bytearray()
    for n in range(int(seconds * rate)):
        t = n / rate
        on = any(a <= t < b for a, b in bursts)
        frames += struct.pack("<h", int(math.sin(2 * math.pi * f0 * t) * amp * 32767) if on else 0)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(bytes(frames))
    return path


def pairs_folder(tmp_path, count=3, name="voice"):
    root = tmp_path / name
    for i in range(count):
        tone_wav(root / ("%03d.wav" % (i + 1)), f0=200.0 + 17 * i)
        (root / ("%03d.txt" % (i + 1))).write_text(TEXTS[i % len(TEXTS)] + "\n", encoding="utf-8")
    return root


def table_folder(tmp_path, count=3, name="tabled"):
    root = tmp_path / name
    rows = []
    for i in range(count):
        tone_wav(root / "wavs" / ("%03d.wav" % (i + 1)), f0=210.0 + 13 * i)
        rows.append("%03d|%s|%s" % (i + 1, TEXTS[i % len(TEXTS)], TEXTS[i % len(TEXTS)].lower()))
    (root / "metadata.csv").write_text("\n".join(rows) + "\n", encoding="utf-8")
    return root


def audio_folder(tmp_path, count=2, name="plain"):
    root = tmp_path / name
    for i in range(count):
        tone_wav(root / ("clip%d.wav" % (i + 1)), f0=230.0 + 11 * i)
    return root


def write_take(recordings, take_id, *, status="ready", duration=60.0, label="A recording", client=None, raw=None):
    """A recording's folder with its notes, written by hand (`raw` writes those exact bytes instead)."""
    folder = os.path.join(str(recordings), "_freeform", "en-US", "takes", take_id)
    os.makedirs(os.path.join(folder, "parts"), exist_ok=True)
    notes = os.path.join(folder, "take.json")
    if raw is not None:
        with open(notes, "wb") as handle:
            handle.write(raw)
    else:
        with open(notes, "w", encoding="utf-8") as handle:
            json.dump({"schema": 1, "id": take_id, "status": status, "duration": duration, "label": label, "client": client or {}}, handle)
    return folder


def studio_env(tmp_path, name="studio-fake"):
    """The studio programs, as far as the tests need them: the environment's own python is a small program that runs this machine's python and asks Freeform Studio's processor to use its fake listener."""
    env = tmp_path / "environments" / name
    binary = env / "venv" / "bin"
    binary.mkdir(parents=True)
    wrapper = binary / "python"
    wrapper.write_text(STUDIO_WRAPPER % sys.executable)
    wrapper.chmod(wrapper.stat().st_mode | stat.S_IXUSR)
    return EnvPaths(str(env))


def make_package(tmp_path, name="p.zip"):
    """A real ACK package, written the way ACK writes one (Freeform Studio's own test builder, which needs numpy)."""
    pytest.importorskip("numpy", reason="the package builder needs numpy (it is installed with Freeform Studio's environment)")
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "freeform_studio" / "tests"))
    from ack_package_builder import ClipSpec, PackageBuilder             # noqa: E402
    builder = PackageBuilder()
    builder.script_session([ClipSpec(TEXTS[0], speech=2.0), ClipSpec(TEXTS[1], speech=3.0), ClipSpec(TEXTS[2], speech=1.5)])
    builder.free_session([(0.4, 3.0), (0.5, 7.0), (0.4, 4.0)], topic="my morning")
    folder = tmp_path / "phone"
    folder.mkdir(parents=True, exist_ok=True)
    return builder.write(folder / name)


def builder_lines(pieces=2, minutes=1.5, left=None, reasons=None, flags=None, result="dry_run", skipped=(), warnings=(), problems=(), out="/x/dataset-1"):
    """What the dataset builder prints with --json: one closing line."""
    reasons = {"you dropped it": 1} if reasons is None else reasons
    left_out = {"pieces": sum(reasons.values()) if left is None else left, "by_reason": reasons, "by_flag": {"noisy": 1} if flags is None else flags}
    body = {"result": result, "out": out, "takes": 1, "pieces_considered": pieces + left_out["pieces"], "skipped_takes": [list(x) for x in skipped],
            "included": {"pieces": pieces, "minutes": minutes, "shortest": 2.0, "median": 3.0, "longest": 4.0}, "left_out": left_out, "merged": 0,
            "warnings": list(warnings), "problems": list(problems)}
    return "unrelated line\n" + json.dumps(body) + "\n"


class Runner:
    """A stand-in for System.run for the dataset builder: it remembers every call and answers a preview and a build from what it was given. A build that answers with a
    function can write the folder the way the real builder does."""

    def __init__(self, preview=None, build=None):
        self.calls = []
        self.preview = CommandResult(0, builder_lines()) if preview is None else preview
        self.build = build

    def run(self, argv, timeout=15.0, cwd=None, env=None):
        self.calls.append({"argv": tuple(argv), "timeout": timeout, "cwd": cwd})
        reply = self.preview if "--dry-run" in argv else self.build
        return reply(argv) if callable(reply) else reply

    @property
    def previews(self):
        return [c for c in self.calls if "--dry-run" in c["argv"]]

    @property
    def builds(self):
        return [c for c in self.calls if "--dry-run" not in c["argv"]]


def write_dataset(argv, rows=2):
    """What the real builder leaves: metadata.csv and a wav folder, in the folder named by --out. Returns the closing line as a finished build prints it."""
    out = argv[argv.index("--out") + 1]
    os.makedirs(os.path.join(out, "wav"))
    with open(os.path.join(out, "metadata.csv"), "w", encoding="utf-8") as handle:
        for n in range(rows):
            handle.write("c%d.wav|%s\n" % (n, TEXTS[n % len(TEXTS)]))
            tone_wav(os.path.join(out, "wav", "c%d.wav" % n), rate=22050)
    return CommandResult(0, builder_lines(pieces=rows, result="built", out=out))


class Starter:
    """A stand-in for jobs.start_job: it remembers what it was asked to start and hands back something with an id."""

    class Started:
        id = "20261011-123000-process-abcd"

    def __init__(self, error=None):
        self.calls = []
        self.error = error

    def __call__(self, jobs_root, spec, now=None):
        self.calls.append((jobs_root, spec, now))
        if self.error:
            raise self.error
        return self.Started()
