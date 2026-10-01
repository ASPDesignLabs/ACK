"""Rebuild what can be rebuilt from a recording's raw audio: the decoded 48 kHz copy and the waveform data.

    python -m freeform_studio.repair              # every finished recording that is missing them
    python -m freeform_studio.repair --take ID    # just one

These are not backed up (they are bigger than the recording and fully determined by it), so a restored recording, or one
whose decoded copy was deleted to save space, needs them rebuilt before it can be reviewed. The server does this by itself
when it starts. Nothing here ever touches the raw audio or your edits.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .audio import FfmpegError, compute_peaks, decode_to_wav, find_ffmpeg, wav_info
from .storage import TAKE_ID_RE, atomic_write_bytes, atomic_write_json, read_json

RAW_RE = re.compile(r"^raw\.(webm|ogg|m4a|wav)$")
REPAIRABLE = ("ready", "decoded")      # recordings that aren't mid-way through some other job


def raw_file(take_dir: Path) -> Optional[Path]:
    for p in sorted(take_dir.glob("raw.*")):
        if RAW_RE.match(p.name) and p.is_file():
            return p
    return None


def _json(path: Path):
    try:
        return read_json(path, None)
    except (ValueError, OSError):
        return None


def derived_missing(take_dir: Path) -> bool:
    peaks = _json(take_dir / "peaks.json")
    if not (take_dir / "audio.wav").exists() or not isinstance(peaks, dict):
        return True
    return any(not (take_dir / f"peaks_{n}.bin").exists() for n in peaks.get("levels", []))


def needs_repair(take_dir: Path) -> bool:
    take = _json(take_dir / "take.json")
    return bool(isinstance(take, dict) and take.get("status") in REPAIRABLE and raw_file(take_dir) and derived_missing(take_dir))


def write_derived(take_dir: Path, raw: Path) -> Tuple[int, int]:
    """Decode `raw` to audio.wav and write the waveform levels. Returns (frames, sample rate)."""
    wav = take_dir / "audio.wav"
    decode_to_wav(raw, wav)
    frames, rate = wav_info(wav)
    peaks = compute_peaks(wav)
    for spp, data in peaks.items():
        atomic_write_bytes(take_dir / f"peaks_{spp}.bin", data)
    atomic_write_json(take_dir / "peaks.json", {"sample_rate": rate, "frames": frames, "levels": sorted(peaks)})
    return frames, rate


def why(err: Exception) -> str:
    """The one line of an ffmpeg complaint that says what is wrong (the rest is file names and offsets)."""
    lines = [ln.strip() for ln in str(err).splitlines() if ln.strip()]
    return lines[-1] if lines else "unknown problem"


def rebuild_missing(output_dir: Path, code: str, take_ids: Optional[List[str]] = None,
                    failures: Optional[Dict[str, str]] = None) -> List[str]:
    """Rebuild for every finished recording that needs it (or just `take_ids`). Returns the ones rebuilt.

    A recording whose raw audio can't be decoded is a problem with that recording alone: with `failures` given it is noted
    there (id -> why) and the others carry on; without it the error is raised. A missing ffmpeg affects every recording, so
    it is raised either way, before anything is attempted."""
    root = Path(output_dir) / "_freeform" / code / "takes"
    fixed: List[str] = []
    if not root.is_dir():
        return fixed
    todo = [d for d in sorted(root.iterdir()) if d.is_dir() and TAKE_ID_RE.match(d.name)
            and (take_ids is None or d.name in take_ids) and needs_repair(d)]
    if todo:
        find_ffmpeg()
    for take_dir in todo:
        try:
            write_derived(take_dir, raw_file(take_dir))  # type: ignore[arg-type]
        except FfmpegError as err:
            if failures is None:
                raise
            failures[take_dir.name] = why(err)
            continue
        fixed.append(take_dir.name)
    return fixed


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--output", default="~/piper-recording-studio/output", help="piper-recording-studio's output folder")
    ap.add_argument("--code", default="en-US")
    ap.add_argument("--take", action="append", metavar="ID", help="only this recording (can be repeated)")
    args = ap.parse_args(argv)
    failures: Dict[str, str] = {}
    try:
        fixed = rebuild_missing(Path(args.output).expanduser(), args.code, args.take, failures)
    except FfmpegError as err:
        print(f"\nCan't continue: {err}\n", file=sys.stderr)
        return 2
    if fixed:
        print(f"\nRebuilt the decoded audio for {len(fixed)} recording(s).")
    elif not failures:
        print("\nNothing needed rebuilding.")
    for t in fixed:
        print(f"  {t}")
    if failures:
        print(f"\n{len(failures)} recording(s) could not be rebuilt. Their raw audio can't be decoded, so nothing about them was changed:")
        for t, reason in failures.items():
            print(f"  {t}: {reason}")
    print()
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
