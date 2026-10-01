# SPDX-License-Identifier: GPL-3.0-or-later
"""Try the transcriber on one audio file, exactly as the server would.

    python -m freeform_studio.models fetch small.en       # once: downloads the model (asks first)
    python -m freeform_studio.asr_smoke ~/some-recording.webm --model small.en --device cpu

Like the server, this loads the model from this computer only and never uses the internet; it tells you if the model
isn't there yet. Nothing is written except a temporary decoded copy, which is removed afterwards.
"""
from __future__ import annotations

import argparse
import sys
import tempfile
import time
from pathlib import Path

from .asr import AsrOptions, EngineError, FakeEngine, FasterWhisperEngine
from .audio import decode_to_wav, wav_info
from .pipeline import propose_segments
from .privacy import apply_offline_defaults
from .segmenter import SegOptions


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("audio", type=Path)
    p.add_argument("--engine", choices=["faster-whisper", "fake"], default="faster-whisper")
    p.add_argument("--model", default="small.en")
    p.add_argument("--device", choices=["cpu", "cuda", "auto"], default="cpu")
    p.add_argument("--compute-type", default="auto")
    p.add_argument("--language", default="en")
    p.add_argument("--prompt", default="", help="hint text: names, jargon, or a style like 'Um, so, uh, yeah.'")
    p.add_argument("--reference", default="", help="(fake engine only) text to spread across detected speech")
    p.add_argument("--allow-download", action="store_true",
                   help="let this run download a missing model itself (off by default; see python -m freeform_studio.models fetch)")
    args = p.parse_args(argv)
    apply_offline_defaults(args.allow_download)   # before anything imports the Hugging Face libraries

    if not args.audio.exists():
        p.error(f"not found: {args.audio}")
    with tempfile.TemporaryDirectory() as tmp:
        wav = Path(tmp) / "audio.wav"
        decode_to_wav(args.audio, wav)
        frames, rate = wav_info(wav)
        duration = frames / rate
        print(f"audio: {duration:.1f}s   engine: {args.engine}/{args.model} on {args.device}")
        if args.engine == "fake":
            engine = FakeEngine(args.model)
        else:
            ct = args.compute_type if args.compute_type != "auto" else ("float16" if args.device == "cuda" else "int8")
            engine = FasterWhisperEngine(args.model, device=args.device, compute_type=ct,
                                         local_files_only=not args.allow_download)
            print("loading model from this computer...")
        t0 = time.monotonic()
        try:
            result = engine.transcribe(wav, AsrOptions(language=args.language, initial_prompt=args.prompt,
                                                       reference_text=args.reference),
                                       progress=lambda f: print(f"\r  transcribing {f * 100:3.0f}%", end="", flush=True))
        except EngineError as e:
            print(f"\n{e}", file=sys.stderr)
            return 1
        print()
        took = time.monotonic() - t0
        segments, refine_stats = propose_segments(result, wav, duration, SegOptions())

    print(f"\ntranscribed in {took:.1f}s ({duration / max(took, 0.01):.1f}x realtime)\n")
    for seg in result["segments"]:
        low = [w for w in seg["words"] if w["p"] < 0.5]
        print(f"  [{seg['start']:6.2f} - {seg['end']:6.2f}] {seg['text']}" + (f"   ({len(low)} shaky word(s))" if low else ""))

    fixed = refine_stats["moved"] + refine_stats["trimmed"]
    print(f"\nHow the review screen would propose to cut it "
          f"({fixed} word timing(s) corrected against the audio):\n")
    for s in segments:
        flags = f"   flags: {', '.join(s['flags'])}" if s["flags"] else ""
        print(f"  {s['id']} [{s['start']:6.2f} - {s['end']:6.2f}] ({s['end'] - s['start']:4.1f}s) {s['text']}{flags}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
