"""ffmpeg decode, waveform peaks, and a simple energy envelope. Pure stdlib + numpy."""
from __future__ import annotations

import shutil
import subprocess
import wave
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

import numpy as np

WORK_RATE = 48000
PEAK_LEVELS = (512, 2048, 8192)  # samples per peak pair


class FfmpegError(RuntimeError):
    pass


def find_ffmpeg() -> str:
    exe = shutil.which("ffmpeg")
    if not exe:
        raise FfmpegError("ffmpeg not found on PATH (sudo apt install ffmpeg)")
    return exe


def decode_to_wav(src: Path, dst: Path, sample_rate: int = WORK_RATE) -> None:
    """Decode any audio to mono 16-bit PCM wav. Written to a temp name first, then moved into place."""
    tmp = dst.with_name(dst.name + ".tmp.wav")
    cmd = [find_ffmpeg(), "-nostdin", "-y", "-loglevel", "error", "-i", str(src),
           "-vn", "-ac", "1", "-ar", str(sample_rate), "-c:a", "pcm_s16le", str(tmp)]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0 or not tmp.exists():
        tmp.unlink(missing_ok=True)
        raise FfmpegError((proc.stderr or "ffmpeg failed").strip()[-400:])
    tmp.replace(dst)


def wav_info(path: Path) -> Tuple[int, int]:
    """(frames, sample_rate)"""
    with wave.open(str(path), "rb") as w:
        return w.getnframes(), w.getframerate()


def iter_blocks(path: Path, block_frames: int):
    with wave.open(str(path), "rb") as w:
        if w.getsampwidth() != 2 or w.getnchannels() != 1:
            raise FfmpegError("expected mono 16-bit wav")
        while True:
            raw = w.readframes(block_frames)
            if not raw:
                return
            yield np.frombuffer(raw, dtype="<i2")


def compute_peaks(path: Path, levels: Sequence[int] = PEAK_LEVELS) -> Dict[int, bytes]:
    """Per level: interleaved int8 (min, max) pairs, one pair per `spp` samples."""
    top = max(levels)
    block = top * 64  # multiple of every level, so only the final block has a remainder
    mins: Dict[int, List[np.ndarray]] = {spp: [] for spp in levels}
    maxs: Dict[int, List[np.ndarray]] = {spp: [] for spp in levels}
    for samples in iter_blocks(path, block):
        for spp in levels:
            full = len(samples) // spp
            if full:
                view = samples[: full * spp].reshape(full, spp)
                mins[spp].append((view.min(axis=1) >> 8).astype(np.int8))
                maxs[spp].append((view.max(axis=1) >> 8).astype(np.int8))
            tail = samples[full * spp:]
            if len(tail):
                mins[spp].append(np.array([tail.min() >> 8], dtype=np.int8))
                maxs[spp].append(np.array([tail.max() >> 8], dtype=np.int8))
    out: Dict[int, bytes] = {}
    for spp in levels:
        if not mins[spp]:
            out[spp] = b""
            continue
        lo = np.concatenate(mins[spp])
        hi = np.concatenate(maxs[spp])
        inter = np.empty(len(lo) * 2, dtype=np.int8)
        inter[0::2] = lo
        inter[1::2] = hi
        out[spp] = inter.tobytes()
    return out


def rms_envelope(path: Path, hop_s: float = 0.01) -> Tuple[np.ndarray, float]:
    """RMS level in dBFS per hop. Returns (levels_db, hop_seconds)."""
    _frames, rate = wav_info(path)
    hop = max(1, int(round(rate * hop_s)))
    block = hop * 2000
    chunks = []
    carry = np.zeros(0, dtype=np.float32)
    for samples in iter_blocks(path, block):
        x = np.concatenate([carry, samples.astype(np.float32)])
        full = len(x) // hop
        if full:
            frames = x[: full * hop].reshape(full, hop)
            chunks.append(np.sqrt((frames ** 2).mean(axis=1)))
        carry = x[full * hop:]
    if len(carry):
        chunks.append(np.array([np.sqrt((carry ** 2).mean())], dtype=np.float32))
    if not chunks:
        return np.zeros(0, dtype=np.float32), hop / rate
    rms = np.concatenate(chunks)
    db = 20.0 * np.log10(np.maximum(rms, 1e-9) / 32768.0)
    return db.astype(np.float32), hop / rate


def voiced_regions(db: np.ndarray, hop_s: float, thresh_db: float = -45.0,
                   min_silence_s: float = 0.3, min_len_s: float = 0.2) -> List[Tuple[float, float]]:
    """(start_s, end_s) spans whose level is above `thresh_db`, with short gaps bridged."""
    above = db > thresh_db
    regions: List[List[int]] = []
    start = None
    for i, on in enumerate(above):
        if on and start is None:
            start = i
        elif not on and start is not None:
            regions.append([start, i])
            start = None
    if start is not None:
        regions.append([start, len(above)])
    gap = int(round(min_silence_s / hop_s))
    merged: List[List[int]] = []
    for r in regions:
        if merged and r[0] - merged[-1][1] < gap:
            merged[-1][1] = r[1]
        else:
            merged.append(r)
    minlen = int(round(min_len_s / hop_s))
    return [(a * hop_s, b * hop_s) for a, b in merged if b - a >= minlen]
