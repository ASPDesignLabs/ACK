"""Turn your takes into a Piper training dataset: a folder with wav/ and metadata.csv.

    python -m freeform_studio.build_dataset                  # uses the defaults below
    python -m freeform_studio.build_dataset --dry-run        # show what would happen, write nothing

Reads the takes under <output>/_freeform/<code>/takes/ and never changes them. It writes a NEW dataset folder (and
refuses to touch one that already exists), so you can build as many variations as you like and compare.

Which pieces go in (--include):
  clean     (default) pieces you approved, plus pieces the recognizer was confident about. Anything flagged (shaky words,
            [tags], symbols, possible mis-hearing) stays out unless you allow that flag.
  approved  only pieces you approved in review.
  all       everything you didn't drop, flags ignored. Use with care.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import re
import shutil
import subprocess
import sys
import wave
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np

from .audio import find_ffmpeg
from .storage import read_json

TARGET_SR = 22050
CLIP_SAMPLES = 5
LENGTH_FLAGS = {"too_short", "too_long"}  # measured directly instead, against --min-seconds/--max-seconds
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")
# split_long_takes.py names a clip from the export folder "freeform_<recording>_<piece>.wav" (group name + file name)
EXPORTED_RE = re.compile(r"^freeform_(t\d{8}-\d{6}-[0-9a-f]{4}_s\d{3,6})\.wav$")


@dataclass
class Policy:
    include: str = "clean"
    allow: Set[str] = field(default_factory=lambda: {"has_digits"})
    exclude_tags: Set[str] = field(default_factory=lambda: {"laugh", "cough", "noise", "unclear"})
    min_s: float = 1.0
    max_s: float = 11.5
    normalize: bool = True
    peak_db: float = -3.0
    max_gain_db: float = 12.0
    min_rms_db: float = -50.0
    fade_s: float = 0.008


@dataclass
class Candidate:
    take_id: str
    seg_id: str
    index: int
    start: float
    end: float
    text: str
    status: str
    prefix: str = "ff_"

    @property
    def name(self) -> str:
        return f"{self.prefix}{self.take_id}_{self.seg_id}"


def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").replace(" ", " ")).strip()


def parse_allow(text: Optional[str]) -> Set[str]:
    """`--allow` as a set of flag names. "none" means accept no flagged piece at all (not even the default, has_digits)."""
    text = (text or "has_digits").strip()
    if text.lower() == "none":
        return set()
    return {a.strip() for a in text.split(",") if a.strip()}


def why_excluded(seg: Dict[str, Any], p: Policy) -> Optional[str]:
    """A plain-language reason this piece is left out, or None if it qualifies (audio checks come later)."""
    status = seg.get("status", "pending")
    text = clean_text(seg.get("text", ""))
    dur = float(seg.get("end", 0)) - float(seg.get("start", 0))
    if status == "dropped":
        return "you dropped it"
    if not text:
        return "no text"
    if "|" in text or _CONTROL.search(text):
        return "text has a character that would break the training file"
    if dur < p.min_s:
        return f"too short ({dur:.1f}s)"
    if dur > p.max_s:
        return f"too long ({dur:.1f}s)"
    tagged = set(seg.get("tags", [])) & p.exclude_tags
    if tagged:  # an explicit judgement by a person, so it applies even to approved pieces
        return "tagged: " + ", ".join(sorted(tagged))
    if "cuts_word" in (seg.get("flags") or []) and "cuts_word" not in p.allow:
        # approval doesn't override this one: the audio and the text disagree, which is what hurts training most
        return "a cut point falls inside a word (move it in Review, or pass --allow cuts_word)"
    if status == "approved":
        return None  # a person looked at it: flags no longer matter
    if p.include == "approved":
        return "not approved yet"
    if p.include == "clean":
        blocking = set(seg.get("flags", [])) - p.allow - LENGTH_FLAGS
        if blocking:
            return "flagged: " + ", ".join(sorted(blocking))
    return None


def scan(takes_dir: Path, p: Policy, only: Optional[Set[str]] = None, prefix: str = "ff_") -> Tuple[List[Candidate], List[Dict[str, Any]], Dict[str, Any]]:
    """Which pieces qualify under policy `p`. `only` limits it to those takes; `scanned` lists the finished takes that were read."""
    included: List[Candidate] = []
    excluded: List[Dict[str, Any]] = []
    stats: Dict[str, Any] = {"takes": 0, "skipped_takes": [], "segments": 0, "scanned": []}
    if not takes_dir.is_dir():
        return included, excluded, stats
    for take_dir in sorted(d for d in takes_dir.iterdir() if d.is_dir()):
        if only is not None and take_dir.name not in only:
            continue
        stats["takes"] += 1
        take = read_json(take_dir / "take.json")
        edit = read_json(take_dir / "edit.json")
        if not take or take.get("status") != "ready" or not edit or not (take_dir / "audio.wav").exists():
            stats["skipped_takes"].append((take_dir.name, (take or {}).get("status", "unreadable")))
            continue
        stats["scanned"].append(take_dir.name)
        for i, seg in enumerate(edit.get("segments", [])):
            stats["segments"] += 1
            reason = why_excluded(seg, p)
            text = clean_text(seg.get("text", ""))
            if reason:
                excluded.append({"take": take_dir.name, "seg": seg.get("id"), "seconds": round(float(seg["end"]) - float(seg["start"]), 2),
                                 "reason": reason, "text": text, "status": seg.get("status", "pending")})
            else:
                included.append(Candidate(take_dir.name, seg["id"], i, float(seg["start"]), float(seg["end"]), text,
                                          seg.get("status", "pending"), prefix))
    return included, excluded, stats


# ---------------------------------------------------------------------------- rendering
def _db(x: float) -> float:
    return 20.0 * math.log10(max(x, 1e-9))


def render_take(take_dir: Path, clips: List[Candidate], wav_dir: Path, p: Policy, workers: int = 4, write: bool = True) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Cut the clips out of one take's audio. Returns (rendered, excluded-for-audio-reasons)."""
    with wave.open(str(take_dir / "audio.wav"), "rb") as w:
        rate, n = w.getframerate(), w.getnframes()
        audio = np.frombuffer(w.readframes(n), dtype="<i2")
    ffmpeg = find_ffmpeg()
    rendered: List[Dict[str, Any]] = []
    excluded: List[Dict[str, Any]] = []

    def one(c: Candidate) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
        x = audio[int(c.start * rate):int(c.end * rate)].astype(np.float32) / 32768.0
        bad = lambda why: (None, {"take": c.take_id, "seg": c.seg_id, "seconds": round(c.end - c.start, 2), "reason": why, "text": c.text,
                                  "status": c.status})
        if len(x) < rate * 0.2:
            return bad("audio is empty")
        peak = float(np.abs(x).max())
        if int(np.count_nonzero(np.abs(x) >= 0.999)) >= CLIP_SAMPLES:  # one stray sample is normal; a run of them is distortion
            return bad("the recording clips (hits the maximum level repeatedly)")
        if _db(float(np.sqrt(np.mean(x * x)))) < p.min_rms_db:
            return bad("too quiet to use")
        gain_db = 0.0
        if p.normalize:
            gain_db = min(p.max_gain_db, p.peak_db - _db(peak))
            x = x * (10 ** (gain_db / 20.0))
        nf = min(int(p.fade_s * rate), len(x) // 2)
        if nf > 1:  # a few milliseconds of fade so cuts never click
            ramp = np.linspace(0.0, 1.0, nf, dtype=np.float32)
            x[:nf] *= ramp
            x[-nf:] *= ramp[::-1]
        out = wav_dir / f"{c.name}.wav"
        if not write:  # dry run: every check above has run, nothing is written
            return {"file": out.name, "take": c.take_id, "seg": c.seg_id, "index": c.index, "start": c.start, "end": c.end,
                    "seconds": round(c.end - c.start, 3), "text": c.text, "status": c.status, "gain_db": round(gain_db, 1)}, None
        pcm = np.clip(x * 32767.0, -32768, 32767).astype("<i2").tobytes()
        proc = subprocess.run([ffmpeg, "-y", "-loglevel", "error", "-f", "s16le", "-ar", str(rate), "-ac", "1", "-i", "pipe:0",
                               "-ar", str(TARGET_SR), "-ac", "1", "-c:a", "pcm_s16le", str(out)],
                              input=pcm, capture_output=True)
        if proc.returncode != 0:
            return bad("audio conversion failed")
        return {"file": out.name, "take": c.take_id, "seg": c.seg_id, "index": c.index, "start": c.start, "end": c.end,
                "seconds": round(c.end - c.start, 3), "text": c.text, "status": c.status, "gain_db": round(gain_db, 1)}, None

    with ThreadPoolExecutor(max_workers=workers) as pool:
        for ok, bad in pool.map(one, clips):
            (rendered if ok else excluded).append(ok or bad)  # type: ignore[arg-type]
    return rendered, excluded


# ---------------------------------------------------------------------------- merging existing datasets
def read_dataset(folder: Path) -> Tuple[List[Tuple[Path, str]], List[str]]:
    """(wav path, text) rows of an existing dataset folder (wav/ + metadata.csv), plus human-readable warnings."""
    rows: List[Tuple[Path, str]] = []
    warns: List[str] = []
    meta = folder / "metadata.csv"
    if not meta.is_file():
        return rows, [f"{folder}: no metadata.csv"]
    wavs = folder / "wav" if (folder / "wav").is_dir() else folder
    with open(meta, "r", encoding="utf-8") as f:  # same way piper1-gpl opens it
        for row in csv.reader(f, delimiter="|"):
            if len(row) < 2:
                continue
            path = wavs / row[0]
            if not path.exists():
                path = wavs / f"{row[0]}.wav"
            if not path.exists():
                warns.append(f"{folder.name}: missing audio {row[0]}")
                continue
            try:
                with wave.open(str(path), "rb") as w:
                    ok = (w.getframerate(), w.getnchannels(), w.getsampwidth()) == (TARGET_SR, 1, 2)
            except (wave.Error, EOFError):
                ok = False
            if not ok:
                warns.append(f"{folder.name}: {row[0]} is not 22050 Hz mono 16-bit, skipped")
                continue
            rows.append((path, clean_text(row[-1])))
    return rows, warns


# ---------------------------------------------------------------------------- the whole job
def build(args: argparse.Namespace) -> int:
    policy = Policy(include=args.include, allow=parse_allow(args.allow),
                    exclude_tags=set() if args.exclude_tags == "none" else {t for t in args.exclude_tags.split(",") if t},
                    min_s=args.min_seconds, max_s=args.max_seconds, normalize=not args.no_normalize)
    takes_dir = Path(args.output).expanduser() / "_freeform" / args.code / "takes"
    out = Path(args.out).expanduser() if args.out else Path("~/piper").expanduser() / f"freeform-dataset-{datetime.now():%Y%m%d-%H%M%S}"
    if out.exists() and any(out.iterdir()) and not args.dry_run:
        print(f"\nCan't continue: {out} already exists and isn't empty. This tool never overwrites a dataset; "
              f"choose a new name with --out.\n", file=sys.stderr)
        return 2

    chosen, excluded, stats = scan(takes_dir, policy)
    if not takes_dir.is_dir():
        print(f"\nCan't continue: no takes folder at {takes_dir}. Check --output and --code.\n", file=sys.stderr)
        return 2

    also_rows: List[Tuple[Path, str]] = []
    warnings: List[str] = []
    already: Dict[str, str] = {}      # pieces that an --also dataset already holds (made from an export), by recording_piece
    for folder in args.also or []:
        rows, w = read_dataset(Path(folder).expanduser())
        also_rows.extend(rows)
        warnings.extend(w)
        for path, _text in rows:
            m = EXPORTED_RE.search(path.name)
            if m:
                already.setdefault(m.group(1), Path(folder).expanduser().name)
    if already:
        keep = []
        for c in chosen:
            where = already.get(f"{c.take_id}_{c.seg_id}")
            if where is None:
                keep.append(c)
            else:
                excluded.append({"take": c.take_id, "seg": c.seg_id, "seconds": round(c.end - c.start, 2), "status": c.status, "text": c.text,
                                 "reason": f"already in {where} (from an earlier export; re-export and rebuild that dataset to refresh it)"})
        chosen = keep

    rendered: List[Dict[str, Any]] = []
    wav_dir = out / "wav"
    made_dirs = False
    if chosen:
        if not args.dry_run:
            made_dirs = not out.exists()
            wav_dir.mkdir(parents=True, exist_ok=True)
        by_take: Dict[str, List[Candidate]] = {}
        for c in chosen:
            by_take.setdefault(c.take_id, []).append(c)
        for take_id, clips in by_take.items():
            r, bad = render_take(takes_dir / take_id, clips, wav_dir, policy, write=not args.dry_run)
            rendered.extend(r)
            excluded.extend(bad)
    rendered.sort(key=lambda r: (r["take"], r["index"]))

    # merged-in rows keep their own audio; give each a name that cannot collide
    merged: List[Dict[str, Any]] = []
    used = {r["file"] for r in rendered}
    for k, (path, text) in enumerate(also_rows):
        name = path.name if path.name not in used else f"m{k:05d}_{path.name}"
        used.add(name)
        if not args.dry_run:
            (out / "wav").mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, out / "wav" / name)
        merged.append({"file": name, "text": text, "seconds": None})

    report(args, policy, stats, rendered, merged, excluded, warnings, out)
    if args.dry_run:
        return 0
    if not rendered and not merged:
        if made_dirs:  # only ever remove folders this run created, and only if empty
            for d in (out / "wav", out):
                try:
                    d.rmdir()
                except OSError:
                    pass
        print("Nothing qualified, so no dataset was written. See the list above for why.\n")
        return 1

    with open(out / "metadata.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter="|", lineterminator="\n")
        for r in rendered + merged:
            w.writerow([r["file"], r["text"]])
    (out / "manifest.json").write_text(json.dumps({"built": datetime.now().isoformat(timespec="seconds"), "policy": {
        "include": policy.include, "allow": sorted(policy.allow), "min_seconds": policy.min_s, "max_seconds": policy.max_s,
        "normalize": policy.normalize, "peak_db": policy.peak_db}, "clips": rendered, "merged": merged}, indent=1, ensure_ascii=False))
    with open(out / "excluded.txt", "w", encoding="utf-8") as f:
        for e in excluded:
            f.write(f"{e['reason']}\t{e['take']}/{e['seg']}\t{e['seconds']}s\t{e['text']}\n")
    problems = validate(out)
    if problems:
        print("Checks on the finished dataset found problems:")
        for line in problems[:20]:
            print("  PROBLEM", line)
        return 1
    print(f"Checked like the trainer reads it: {len(rendered) + len(merged)} rows, every wav present and 22050 Hz mono.\n")
    print_training_command(out)
    return 0


def validate(folder: Path) -> List[str]:
    """The same checks training would trip on, done up front."""
    problems: List[str] = []
    seen: Set[str] = set()
    with open(folder / "metadata.csv", "r", encoding="utf-8") as f:
        for n, row in enumerate(csv.reader(f, delimiter="|"), 1):
            if len(row) != 2:
                problems.append(f"row {n}: expected 2 columns, found {len(row)}")
                continue
            if row[0] in seen:
                problems.append(f"row {n}: {row[0]} appears twice")
            seen.add(row[0])
            if not row[1].strip():
                problems.append(f"row {n}: empty text")
            p = folder / "wav" / row[0]
            if not p.exists():
                problems.append(f"row {n}: {row[0]} is missing")
                continue
            with wave.open(str(p), "rb") as w:
                if (w.getframerate(), w.getnchannels(), w.getsampwidth()) != (TARGET_SR, 1, 2):
                    problems.append(f"row {n}: {row[0]} is not 22050 Hz mono 16-bit")
    return problems


def report(args: argparse.Namespace, p: Policy, stats: Dict[str, Any], rendered: List[Dict[str, Any]],
           merged: List[Dict[str, Any]], excluded: List[Dict[str, Any]], warnings: List[str], out: Path) -> None:
    secs = sorted(r["seconds"] for r in rendered if r.get("seconds"))
    total_min = sum(secs) / 60.0
    print()
    print(f"{'DRY RUN, nothing written. ' if args.dry_run else ''}Dataset: {out}")
    print(f"  takes found: {stats['takes']}    pieces considered: {stats['segments']}    policy: include={p.include}"
          f", allow={','.join(sorted(p.allow)) or 'nothing'}")
    for name, status in stats["skipped_takes"]:
        print(f"  skipped take {name} ({status}): only finished takes are used")
    print(f"  INCLUDED: {_pieces(len(rendered))}, {total_min:.1f} minutes of speech" +
          (f", {secs[0]:.1f}s to {secs[-1]:.1f}s, median {secs[len(secs) // 2]:.1f}s" if secs else ""))
    if merged:
        print(f"  MERGED IN from other datasets: {len(merged)} rows")
    by_reason: Dict[str, int] = {}
    for e in excluded:
        key = "flagged" if e["reason"].startswith("flagged:") else e["reason"].split(" (")[0]
        by_reason[key] = by_reason.get(key, 0) + 1
    if excluded:
        print(f"  LEFT OUT: {_pieces(len(excluded))}")
        for key, count in sorted(by_reason.items(), key=lambda kv: -kv[1]):
            print(f"      {count:4d}  {key}")
        flagged = {}
        for e in excluded:
            if e["reason"].startswith("flagged:"):
                for fl in e["reason"][len("flagged: "):].split(", "):
                    flagged[fl] = flagged.get(fl, 0) + 1
        if flagged:
            print("      of the flagged ones, by flag: " + ", ".join(f"{k} {v}" for k, v in sorted(flagged.items(), key=lambda kv: -kv[1])))
            print("      Read them in excluded.txt. If the text is right, bring a kind back with e.g. --allow low_confidence")
        show = args.show_excluded
        if show:
            print(f"  examples of what was left out (first {min(show, len(excluded))}):")
            for e in excluded[:show]:
                print(f"      [{e['reason']}] {e['text'][:90]}")
    for w in warnings[:10]:
        print(f"  WARNING {w}")
    if total_min < 10 and rendered:
        print("  NOTE: under about 10 minutes of speech tends to give an uneven voice; 30+ minutes is a comfortable target.")
    print()


def _pieces(n: int) -> str:
    return f"{n} piece" + ("" if n == 1 else "s")


def print_training_command(out: Path) -> None:
    name = out.name
    print("Train on it (from your piper1-gpl environment), with a NEW cache folder since this is new audio:\n")
    print(f"""  python3 -m piper.train fit \\
    --data.voice_name "my_voice" \\
    --data.csv_path {out}/metadata.csv \\
    --data.audio_dir {out}/wav \\
    --model.sample_rate 22050 \\
    --data.espeak_voice "en-us" \\
    --data.cache_dir ~/piper/my-training/cache-{name} \\
    --data.config_path ~/piper/my-training/config.json \\
    --data.batch_size 12 \\
    --data.num_workers 4 \\
    --trainer.check_val_every_n_epoch 10 \\
    --trainer.log_every_n_steps 1 \\
    --ckpt_path ~/piper/checkpoints/base.ckpt
""")
    print("Notes on that command:")
    print("  - To CONTINUE a voice you already trained, point --ckpt_path at your own newest")
    print("    lightning_logs/version_N/checkpoints/last.ckpt instead of base.ckpt (base.ckpt starts over).")
    print("  - Batch size 12 suits an 8 GB card. If it still runs out of memory, try 8. On a bigger card you can try 16 or")
    print("    more; if training turns very slow (tens of seconds per step), the batch is probably too big for your memory.")
    print("  - This dataset is small, so an epoch is only a few steps. Checking quality every 10 epochs (instead of every")
    print("    one) keeps most of the time on training, and --trainer.log_every_n_steps 1 keeps the loss curves readable.")
    print("    If your trainer says it doesn't know one of these options, leave that line out.\n")


def main(argv: Optional[list] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--output", default="~/piper-recording-studio/output", help="piper-recording-studio's output folder")
    ap.add_argument("--code", default="en-US")
    ap.add_argument("--out", help="where to write the dataset (default: ~/piper/freeform-dataset-<date-time>)")
    ap.add_argument("--include", choices=["clean", "approved", "all"], default="clean")
    ap.add_argument("--allow", default="has_digits", help="comma-separated flags to accept anyway, e.g. low_confidence,has_digits; 'none' accepts no flagged piece, not even has_digits")
    ap.add_argument("--exclude-tags", default="laugh,cough,noise,unclear",
                    help="pieces you tagged with any of these are left out, even if approved; 'none' to disable")
    ap.add_argument("--min-seconds", type=float, default=1.0)
    ap.add_argument("--max-seconds", type=float, default=11.5, help="longer pieces risk running out of GPU memory")
    ap.add_argument("--also", action="append", metavar="DATASET", help="also include an existing dataset folder "
                    "(wav/ + metadata.csv), e.g. ~/piper/my-dataset-split; can be repeated")
    ap.add_argument("--no-normalize", action="store_true", help="keep each clip's original loudness")
    ap.add_argument("--show-excluded", type=int, default=10, help="how many left-out examples to print (0 = none)")
    ap.add_argument("--dry-run", action="store_true", help="show the plan and write nothing")
    return build(ap.parse_args(argv))


if __name__ == "__main__":
    sys.exit(main())
