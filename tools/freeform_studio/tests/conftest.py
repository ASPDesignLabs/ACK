import shutil
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # tools/ -> import freeform_studio

needs_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")


def make_wav(path: Path, seconds: float, bursts, rate: int = 48000, f0: float = 200.0, amp: float = 0.5) -> Path:
    """Sine bursts (start_s, end_s) on digital silence, mono 16-bit."""
    t = np.arange(int(seconds * rate)) / rate
    mask = np.zeros_like(t)
    for a, b in bursts:
        mask[(t >= a) & (t < b)] = 1.0
    samples = (np.sin(2 * np.pi * f0 * t) * mask * amp * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(samples.tobytes())
    return path


def make_live_webm(wav: Path, out: Path) -> Path:
    """Chrome-MediaRecorder-style webm: opus, no duration in the header."""
    subprocess.run(["ffmpeg", "-nostdin", "-y", "-loglevel", "error", "-i", str(wav), "-c:a", "libopus",
                    "-f", "webm", "-live", "1", str(out)], check=True)
    return out


@pytest.fixture
def out_dir(tmp_path):
    d = tmp_path / "output"
    d.mkdir()
    return d
