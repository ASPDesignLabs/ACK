# SPDX-License-Identifier: GPL-3.0-or-later
"""Write the approved pieces of your recordings into the recorder's own folder layout.

    python -m freeform_studio.export              # shows what would change, then asks before writing
    python -m freeform_studio.export --dry-run    # shows what would change and writes nothing

Each approved piece becomes <output>/<code>/freeform/<take>_<piece>.wav plus a matching .txt, exactly like a
prompted recording (<group>/<id>.wav + <id>.txt), so the same checks, backups and split_long_takes.py work on it. The
folder also holds a `.presplit` marker (the splitter then copies these clips through instead of trying to split them) and
manifest.json (where every clip came from).

Nothing is ever deleted. A clip that stops qualifying (you dropped it, un-approved it, tagged it, changed its cut points)
or is replaced by a newer version is moved to <output>/_freeform/<code>/retired/<date-time>/, outside the folder the
splitter reads. Running it again only touches what changed. Your recordings are never modified.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Set

from .build_dataset import Candidate, Policy, render_take, scan
from .locking import exclusive
from .storage import atomic_write_bytes, atomic_write_json, read_json
from .privacy import private_umask

GROUP = "freeform"
MARKER = ".presplit"
MANIFEST = "manifest.json"
LOCK = ".export.lock"
STEM_RE = re.compile(r"^t\d{8}-\d{6}-[0-9a-f]{4}_s\d{3,6}$")   # the only file names this tool ever writes, or replaces
SCHEMA = 1
STALE_LOCK_S = 3600
MARKER_TEXT = ("Finished single-utterance clips written by Freeform Studio.\n"
               "split_long_takes.py copies the audio in this folder through without trying to split it.\n")


class ExportError(Exception):
    """A problem to tell the person about in plain words."""


class ExportBusy(ExportError):
    """Another export is already running."""


def export_folder(output_dir: Path, code: str) -> Path:
    return Path(output_dir) / code / GROUP


def retired_root(output_dir: Path, code: str) -> Path:
    return Path(output_dir) / "_freeform" / code / "retired"


def default_policy(normalize: bool = True) -> Policy:
    """What qualifies: approved pieces only, with every other safeguard build_dataset applies."""
    return Policy(include="approved", normalize=normalize)


def _signature(c: Candidate, p: Policy, audio_bytes: int) -> str:
    key = json.dumps([round(c.start, 3), round(c.end, 3), c.text, p.normalize, p.peak_db, p.max_gain_db, p.fade_s,
                      p.min_rms_db, audio_bytes], ensure_ascii=False)
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]


def read_manifest(folder: Path) -> Dict[str, Any]:
    """The manifest, or an empty one if it is missing or damaged (the clips themselves are the real record)."""
    try:
        doc = read_json(folder / MANIFEST, None)
    except (ValueError, OSError):
        doc = None
    items = doc.get("items") if isinstance(doc, dict) else None
    if not isinstance(items, dict):
        return {"schema": SCHEMA, "items": {}}
    clean = {stem: info for stem, info in items.items()
             if isinstance(stem, str) and isinstance(info, dict) and isinstance(info.get("take"), str) and isinstance(info.get("sig"), str)}
    return {"schema": SCHEMA, "items": clean}


@dataclass
class Plan:
    code: str
    folder: Path
    new: List[Dict[str, Any]] = field(default_factory=list)
    update: List[Dict[str, Any]] = field(default_factory=list)
    same: List[Dict[str, Any]] = field(default_factory=list)
    retire: List[Dict[str, Any]] = field(default_factory=list)
    left_out: List[Dict[str, Any]] = field(default_factory=list)       # approved, but not exportable, with the reason
    skipped_takes: List[Any] = field(default_factory=list)
    settings: Dict[str, Any] = field(default_factory=dict)
    retired_into: Optional[str] = None

    @property
    def changes(self) -> int:
        return len(self.new) + len(self.update) + len(self.retire)

    def counts(self) -> Dict[str, int]:
        return {"new": len(self.new), "updated": len(self.update), "unchanged": len(self.same),
                "retired": len(self.retire), "left_out": len(self.left_out)}

    def seconds_after(self) -> float:
        return sum(i["seconds"] for i in self.new + self.update + self.same)

    def report(self, limit: int = 40) -> Dict[str, Any]:
        by_reason: Dict[str, int] = {}
        for e in self.left_out:
            key = "flagged" if e["reason"].startswith("flagged:") else e["reason"].split(" (")[0]
            by_reason[key] = by_reason.get(key, 0) + 1
        brief = lambda items: [{"stem": i["stem"], "seconds": i["seconds"], "text": i["text"]} for i in items[:limit]]
        return {"code": self.code, "folder": str(self.folder), "folder_name": f"{self.code}/{GROUP}", "counts": self.counts(),
                "minutes_after": round(self.seconds_after() / 60.0, 1), "seconds_after": round(self.seconds_after(), 1), "new": brief(self.new), "updated": brief(self.update),
                "retire": [{"stem": r["stem"], "why": r["why"], "text": r.get("text", "")} for r in self.retire[:limit]],
                "left_out": [{"take": e["take"], "seg": e["seg"], "reason": e["reason"], "text": e["text"], "seconds": e["seconds"]}
                             for e in self.left_out[:limit]],
                "left_out_by_reason": dict(sorted(by_reason.items(), key=lambda kv: -kv[1])),
                "skipped_takes": [{"take": t, "status": s} for t, s in self.skipped_takes], "retired_into": self.retired_into}


def make_plan(output_dir: Path, code: str, take_ids: Optional[List[str]] = None, policy: Optional[Policy] = None,
              render_to: Optional[Path] = None) -> Plan:
    """What an export would do. With `render_to`, the new and changed clips are also written there (and only there)."""
    output_dir = Path(output_dir)
    policy = policy or default_policy()
    takes = output_dir / "_freeform" / code / "takes"
    if not takes.is_dir():
        raise ExportError(f"There is no recordings folder at {takes}. Check the output folder and language code.")
    included, excluded, stats = scan(takes, policy, only=set(take_ids) if take_ids else None, prefix="")
    folder = export_folder(output_dir, code)
    _refuse_foreign_folder(folder)
    manifest = read_manifest(folder)["items"]
    plan = Plan(code=code, folder=folder, skipped_takes=list(stats["skipped_takes"]),
                settings={"normalize": policy.normalize, "peak_db": policy.peak_db, "sample_rate": 22050})
    reasons = {(e["take"], e["seg"]): e for e in excluded}
    plan.left_out = [e for e in excluded if e.get("status") == "approved"]

    qualified = {}
    for c in included:
        if STEM_RE.match(c.name):
            qualified[c.name] = c
        else:
            plan.left_out.append({"take": c.take_id, "seg": c.seg_id, "seconds": round(c.end - c.start, 2), "text": c.text,
                                  "reason": "its recording's folder name isn't one this tool makes", "status": "approved"})
    needs: List[Candidate] = []
    for stem, c in qualified.items():
        audio = takes / c.take_id / "audio.wav"
        sig = _signature(c, policy, audio.stat().st_size if audio.exists() else 0)
        item = {"stem": stem, "take": c.take_id, "seg": c.seg_id, "start": round(c.start, 3), "end": round(c.end, 3),
                "seconds": round(c.end - c.start, 3), "text": c.text, "sig": sig, "gain_db": None}
        have = (folder / f"{stem}.wav").exists() and (folder / f"{stem}.txt").exists()
        known = manifest.get(stem)
        if known and known["sig"] == sig and have:
            item["gain_db"] = known.get("gain_db")
            plan.same.append(item)
            continue
        item["_candidate"] = c
        (plan.update if (known or have) else plan.new).append(item)   # files already there are archived first, never overwritten blind
        needs.append(c)

    # Audio checks (silence, clipping) and, when asked, the real cut-and-convert of what needs writing
    rendered: Dict[str, Dict[str, Any]] = {}
    by_take: Dict[str, List[Candidate]] = {}
    for c in needs:
        by_take.setdefault(c.take_id, []).append(c)
    for take_id, clips in by_take.items():
        ok, bad = render_take(takes / take_id, clips, render_to if render_to is not None else folder, policy, write=render_to is not None)
        for r in ok:
            rendered[Path(r["file"]).stem] = r
        for b in bad:
            plan.left_out.append({**b, "status": "approved"})
    for group in (plan.new, plan.update):
        for item in list(group):
            r = rendered.get(item["stem"])
            if r is None:
                group.remove(item)
            else:
                item["gain_db"] = r.get("gain_db")

    # Clips that no longer qualify (only for takes that were read, so a take being re-transcribed is never emptied)
    scanned = set(stats["scanned"])
    for stem, info in manifest.items():
        if info["take"] in scanned and stem not in qualified:
            why = (reasons.get((info["take"], info.get("seg"))) or {}).get("reason") or "the piece no longer exists"
            plan.retire.append({"stem": stem, "why": why, "text": info.get("text", "")})
    for item in plan.new + plan.update:
        item.pop("_candidate", None)
    return plan


def _refuse_foreign_folder(folder: Path) -> None:
    """Never take over a folder that already holds someone else's recordings: the marker would change how they are split."""
    if not folder.is_dir() or (folder / MARKER).exists() or (folder / MANIFEST).exists():
        return
    foreign = lambda p: p.suffix.lower() in (".wav", ".webm", ".txt") and not STEM_RE.match(p.stem)   # not named the way this tool names clips
    if any(foreign(p) for p in folder.iterdir() if p.is_file()):
        raise ExportError(f"{folder} already exists and holds recordings that this tool didn't write. It won't mix its clips in with "
                          f"them (they would stop being split into sentences). Rename or move that folder first.")


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return None


@contextmanager
def _locked(folder: Path) -> Iterator[None]:
    with exclusive(folder / LOCK, STALE_LOCK_S, lambda path: ExportBusy(f"Another export is running. If it crashed, delete {path} and try again.")):
        yield


def apply(output_dir: Path, code: str, take_ids: Optional[List[str]] = None, policy: Optional[Policy] = None) -> Plan:
    """Do the export. Returns the plan that was carried out."""
    output_dir = Path(output_dir)
    policy = policy or default_policy()
    folder = export_folder(output_dir, code)
    with _locked(folder):
        tmp = Path(tempfile.mkdtemp(prefix=".tmp-export-", dir=folder))
        try:
            plan = make_plan(output_dir, code, take_ids, policy, render_to=tmp)
            manifest = read_manifest(folder)
            items = manifest["items"]
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            aside = retired_root(output_dir, code) / stamp
            moved: Dict[str, str] = {}

            def put_aside(stem: str, why: str) -> None:
                aside.mkdir(parents=True, exist_ok=True)
                for ext in (".wav", ".txt"):
                    src = folder / f"{stem}{ext}"
                    if src.exists():
                        shutil.move(str(src), str(aside / src.name))
                moved[stem] = why
                items.pop(stem, None)

            for r in plan.retire:
                put_aside(r["stem"], r["why"])
            for item in plan.update:
                put_aside(item["stem"], "replaced by a newer version")
            damaged = folder / MANIFEST
            if damaged.exists() and not isinstance(_load_json(damaged), dict):
                aside.mkdir(parents=True, exist_ok=True)
                shutil.copy2(damaged, aside / "manifest.damaged.json")      # keep what was there before it is replaced
                plan.retired_into = str(aside)
            if moved:
                atomic_write_json(aside / "index.json", moved)
                plan.retired_into = str(aside)
                atomic_write_json(folder / MANIFEST, {"schema": SCHEMA, "items": items})   # never name a file the manifest says is here but isn't

            atomic_write_bytes(folder / MARKER, MARKER_TEXT.encode("utf-8"))
            written = 0
            for item in plan.new + plan.update:
                stem = item["stem"]
                os.replace(tmp / f"{stem}.wav", folder / f"{stem}.wav")
                atomic_write_bytes(folder / f"{stem}.txt", (item["text"] + "\n").encode("utf-8"))
                items[stem] = {"take": item["take"], "seg": item["seg"], "start": item["start"], "end": item["end"],
                               "seconds": item["seconds"], "text": item["text"], "sig": item["sig"], "gain_db": item["gain_db"],
                               "exported": datetime.now().isoformat(timespec="seconds")}
                written += 1
                if written % 25 == 0:
                    atomic_write_json(folder / MANIFEST, {"schema": SCHEMA, "items": items})
            for item in plan.same:
                items.setdefault(item["stem"], {"take": item["take"], "seg": item["seg"], "start": item["start"], "end": item["end"],
                                                "seconds": item["seconds"], "text": item["text"], "sig": item["sig"], "gain_db": item.get("gain_db")})
            atomic_write_json(folder / MANIFEST, {"schema": SCHEMA, "code": code, "updated": datetime.now().isoformat(timespec="seconds"),
                                                   "settings": plan.settings, "items": items})
            return plan
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------------------- command line
def _print_plan(plan: Plan, dry_run: bool) -> None:
    r = plan.report(limit=8)
    c = r["counts"]
    print(f"\n{'DRY RUN, nothing written. ' if dry_run else ''}Export folder: {plan.folder}")
    print(f"  new: {c['new']}    replaced by a newer version: {c['updated']}    unchanged: {c['unchanged']}    "
          f"no longer qualify (moved aside, not deleted): {c['retired']}")
    print(f"  after this the folder holds {r['minutes_after']} minutes of speech")
    for label, rows in (("new", r["new"]), ("replaced", r["updated"])):
        for row in rows:
            print(f"      {label}: [{row['seconds']:.1f}s] {row['text'][:80]}")
    for row in r["retire"]:
        print(f"      moved aside ({row['why']}): {row['text'][:70]}")
    if c["left_out"]:
        print(f"  APPROVED BUT LEFT OUT: {c['left_out']}")
        for reason, n in r["left_out_by_reason"].items():
            print(f"      {n:4d}  {reason}")
    for t in r["skipped_takes"]:
        print(f"  skipped recording {t['take']} ({t['status']}): only finished recordings are used")
    print()


def main(argv: Optional[List[str]] = None) -> int:
    with private_umask():   # files this command creates are readable by you alone
        return _main(argv)


def _main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--output", default="~/piper-recording-studio/output", help="piper-recording-studio's output folder")
    ap.add_argument("--code", default="en-US")
    ap.add_argument("--take", action="append", metavar="ID", help="only this recording (can be repeated); default: all")
    ap.add_argument("--no-normalize", action="store_true", help="keep each clip's original loudness")
    ap.add_argument("--dry-run", action="store_true", help="show what would change and write nothing")
    ap.add_argument("--yes", action="store_true", help="don't ask before writing")
    args = ap.parse_args(argv)
    output = Path(args.output).expanduser()
    policy = default_policy(normalize=not args.no_normalize)
    try:
        plan = make_plan(output, args.code, args.take, policy)
        _print_plan(plan, args.dry_run)
        if args.dry_run:
            return 0
        if plan.changes == 0:
            print("Already up to date. Nothing to write.\n")
            return 0
        if not args.yes:
            if not sys.stdin.isatty():
                print("Not at a terminal, so it won't write without being told to: add --yes (or use --dry-run to look).\n", file=sys.stderr)
                return 2
            if input("Write these changes? [y/N] ").strip().lower() not in ("y", "yes"):
                print("Nothing written.\n")
                return 0
        done = apply(output, args.code, args.take, policy)
    except ExportError as err:
        print(f"\nCan't continue: {err}\n", file=sys.stderr)
        return 2
    c = done.counts()
    print(f"Wrote {c['new']} new, replaced {c['updated']}, moved {c['retired']} aside"
          + (f" (kept in {done.retired_into})" if done.retired_into else "") + f".\nFolder: {done.folder}\n")
    print("Next: build the training set the way you always do. The folder is a group like any other, so for example\n"
          f"  python3 ~/tools/split_long_takes.py --input-dir {output / args.code} --output-dir ~/piper/my-dataset-split\n"
          "copies these clips through unsplit alongside your prompted recordings.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
