#!/usr/bin/env python3
"""Splits multi-sentence piper-recording-studio takes into per-sentence
training examples.

Longer, paragraph-style prompts are easier to read aloud in one
comfortable take (fewer stop/start taps between rounds), but VITS
training doesn't handle very long individual utterances well -- both
batch padding and (especially) the monotonic alignment step scale
badly with utterance length, risking an out-of-memory crash on an 8GB
card. This script keeps the ergonomic win from reading longer passages
while producing short, training-friendly utterances: it re-splits each
recorded take back into individual sentence-level (wav, text) pairs,
using silence detection to find the natural pauses between sentences
and matching each resulting audio segment, in order, against the
sentences of the original prompt text.

Matches piper-recording-studio's own output layout exactly:
    <input-dir>/<prompt-group>/<id>.wav   (or .webm)
    <input-dir>/<prompt-group>/<id>.txt   (the full prompt text read in that take)

Requires:
    pip install pydub
    ffmpeg on PATH (needed to decode .webm takes; a plain .wav take
    doesn't strictly need it, but install it anyway -- the training
    guide's own export step already asks for it)

Usage:
    python3 split_long_takes.py \\
        --input-dir ~/piper-recording-studio/output/en-US \\
        --output-dir ~/piper/my-dataset-split

    # Tune silence detection without writing anything, if segment
    # counts don't match sentence counts on the first pass:
    python3 split_long_takes.py --input-dir ... --output-dir ... --dry-run

Recordings shorter than --min-duration are assumed to already be
single-sentence takes -- copied straight through (resampled to Piper's
expected 22050 Hz mono 16-bit) with their existing text, untouched.
Anything where the number of detected speech segments doesn't match
the number of sentences in that take's prompt text is left out of
metadata.csv and copied instead into <output-dir>/needs_review/, so a
bad silence-detection guess never silently corrupts the training set --
it just isn't included until you've looked at it.
"""

import argparse
import csv
import logging
import re
import shutil
import sys
from pathlib import Path
from typing import List, Tuple

try:
    from pydub import AudioSegment
    from pydub.silence import detect_nonsilent
except ImportError:
    print("Missing dependency. Run: pip install pydub", file=sys.stderr)
    sys.exit(1)

_LOGGER = logging.getLogger("split_long_takes")

TARGET_SAMPLE_RATE = 22050
_SENTENCE_SPLIT_RE = re.compile(r'(?<=[.!?])[\'"’”]?\s+(?=[A-Z0-9"‘“])')


def split_sentences(text: str) -> List[str]:
    """Splits prompt text into sentences.

    Deliberately simple (regex on sentence-final punctuation followed
    by whitespace and a capital letter or opening quote) rather than a
    full NLP sentence tokenizer -- good enough for prompt text written
    with clean, unabbreviated punctuation, which is what these training
    prompts use. Trailing closing quotes/apostrophes after the
    punctuation are allowed, so a dialogue line ending "...like that."
    still splits correctly.
    """
    text = text.strip()
    if not text:
        return []
    parts = _SENTENCE_SPLIT_RE.split(text)
    return [p.strip() for p in parts if p.strip()]


def find_speech_segments(
    audio: AudioSegment,
    min_silence_len: int,
    silence_thresh: float,
    keep_silence: int,
) -> List[Tuple[int, int]]:
    """Returns (start_ms, end_ms) for each detected speech segment, in order."""
    raw_segments = detect_nonsilent(
        audio,
        min_silence_len=min_silence_len,
        silence_thresh=silence_thresh,
        seek_step=10,
    )
    return [
        (max(0, start - keep_silence), min(len(audio), end + keep_silence))
        for start, end in raw_segments
    ]


def normalize_audio(audio: AudioSegment) -> AudioSegment:
    return audio.set_frame_rate(TARGET_SAMPLE_RATE).set_channels(1).set_sample_width(2)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--input-dir", required=True, type=Path, help="piper-recording-studio output/<lang-code> directory")
    parser.add_argument("--output-dir", required=True, type=Path, help="Where to write wav/ and metadata.csv")
    parser.add_argument("--min-duration", type=float, default=12.0, help="Seconds; takes shorter than this are copied through unsplit (default: 12)")
    parser.add_argument("--min-silence-len", type=int, default=400, help="Milliseconds of quiet to count as a sentence gap (default: 400)")
    parser.add_argument("--silence-thresh", type=float, default=-40.0, help="dBFS below which audio counts as silence (default: -40.0; raise toward 0 -- e.g. -35 -- if it's under-splitting in a noisy room, lower -- e.g. -45 -- if it's over-splitting on breaths)")
    parser.add_argument("--keep-silence", type=int, default=150, help="Milliseconds of padding kept on each side of a split segment (default: 150)")
    parser.add_argument("--dry-run", action="store_true", help="Report sentence/segment count matches without writing any files")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    input_dir: Path = args.input_dir.expanduser()
    output_dir: Path = args.output_dir.expanduser()
    wav_dir = output_dir / "wav"
    review_dir = output_dir / "needs_review"

    if not args.dry_run:
        wav_dir.mkdir(parents=True, exist_ok=True)
        review_dir.mkdir(parents=True, exist_ok=True)

    metadata_rows: List[Tuple[str, str]] = []
    split_count = 0
    passthrough_count = 0
    review_count = 0

    audio_paths = sorted(
        p for p in input_dir.rglob("*")
        if p.suffix.lower() in (".wav", ".webm") and p.with_suffix(".txt").exists()
    )

    if not audio_paths:
        _LOGGER.warning("No matching audio+text pairs found under %s", input_dir)
        return

    for audio_path in audio_paths:
        text_path = audio_path.with_suffix(".txt")
        prompt_text = text_path.read_text(encoding="utf-8").strip()
        group = audio_path.parent.name
        base_name = f"{group}_{audio_path.stem}"

        try:
            audio = AudioSegment.from_file(audio_path)
        except Exception as e:
            _LOGGER.error("Could not decode %s: %s -- is ffmpeg installed and on PATH?", audio_path, e)
            continue

        duration_s = len(audio) / 1000.0

        if duration_s < args.min_duration:
            _LOGGER.info("PASSTHROUGH  %-45s  %.1fs (single sentence)", audio_path.name, duration_s)
            if not args.dry_run:
                out_name = f"{base_name}.wav"
                normalize_audio(audio).export(wav_dir / out_name, format="wav")
                metadata_rows.append((out_name, prompt_text))
            passthrough_count += 1
            continue

        sentences = split_sentences(prompt_text)
        segments = find_speech_segments(
            audio,
            min_silence_len=args.min_silence_len,
            silence_thresh=args.silence_thresh,
            keep_silence=args.keep_silence,
        )

        if len(segments) != len(sentences):
            _LOGGER.warning(
                "MISMATCH     %-45s  %d sentence(s) vs %d detected segment(s) -- sent to needs_review/",
                audio_path.name, len(sentences), len(segments),
            )
            if not args.dry_run:
                review_audio = review_dir / f"{base_name}{audio_path.suffix}"
                review_text = review_dir / f"{base_name}.txt"
                shutil.copy2(audio_path, review_audio)
                review_text.write_text(prompt_text, encoding="utf-8")
            review_count += 1
            continue

        _LOGGER.info("SPLIT        %-45s  %.1fs -> %d sentences", audio_path.name, duration_s, len(sentences))
        if not args.dry_run:
            for i, (sentence, (start_ms, end_ms)) in enumerate(zip(sentences, segments)):
                clip = normalize_audio(audio[start_ms:end_ms])
                out_name = f"{base_name}_{i:02d}.wav"
                clip.export(wav_dir / out_name, format="wav")
                metadata_rows.append((out_name, sentence))
        split_count += 1

    if not args.dry_run and metadata_rows:
        metadata_path = output_dir / "metadata.csv"
        with open(metadata_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f, delimiter="|", lineterminator="\n")
            for filename, text in metadata_rows:
                writer.writerow([filename, text])
        _LOGGER.info("\nWrote %d utterances to %s", len(metadata_rows), metadata_path)

    _LOGGER.info(
        "\n%d take(s) split, %d short take(s) passed through, %d take(s) need manual review%s",
        split_count, passthrough_count, review_count,
        " (dry run -- nothing written)" if args.dry_run else "",
    )
    if review_count:
        _LOGGER.info("Review the files in %s, then re-run with adjusted --min-silence-len/--silence-thresh, or split those specific ones by hand.", review_dir)


if __name__ == "__main__":
    main()
