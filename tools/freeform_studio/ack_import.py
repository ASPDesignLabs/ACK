# SPDX-License-Identifier: GPL-3.0-or-later
"""Brings an ACK training-capture package into Freeform Studio.

    python -m freeform_studio.ack_import ~/Downloads/ack-training-20261002-193000.zip --dry-run   # look, write nothing
    python -m freeform_studio.ack_import ~/Downloads/ack-training-20261002-193000.zip             # shows the plan, then asks

Each session in the package becomes ONE recording ("take") in Freeform Studio, ready for the same steps a recording made in the
browser goes through: decoding, listening for speech, transcribing, proposing pieces, review, export. A script session's clips are
joined in order with a short gap into that recording, and the words ACK showed for each clip travel with it; a free-speech session
is the whole recording, with the phone's suggested cut points kept as hints.

Safe by design: the package is checked completely first (every file against its checksum) and a package that fails changes nothing.
Importing only ever adds. A session that was already imported is recognised and skipped, so running this twice is harmless. The
audio inside the package is never modified. Nothing here uses the network.
"""
from __future__ import annotations

import argparse
import shutil
import struct
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from .ack_package import Package, PackageError, open_package
from .config import Config
from .health import free_mb
from .privacy import private_umask, sync_warning
from .storage import TAKE_ID_RE, TakeStore, now_iso, read_json

GAP_S = 0.4                   # quiet put between a script session's clips when they are joined (format document, section 9)
PART_BYTES = 8 * 1024 * 1024  # audio is stored the way the phone page uploads it: in parts of this size, joined when finishing
REFERENCE_MAX = 20000         # the most reference text a recording holds (the review page's own limit)
MAX_WAV_DATA = 0xFFFFFFFF - 64


class ImportProblem(Exception):
    """Something that stops the import, in words a person can act on."""


class NotEnoughRoom(ImportProblem):
    """The disk is too full to take the recordings. Nothing was written."""


@dataclass
class SessionPlan:
    id: str
    mode: str
    label: str
    clips: int
    seconds: float
    audio_bytes: int
    state: str                  # "new" | "already" | "aborted" (a leftover from an import that was cut short)
    take_id: Optional[str] = None
    need_mb: float = 0.0


@dataclass
class Plan:
    package: Package
    output: Path
    code: str
    takes_dir: Path
    sessions: List[SessionPlan]
    free_mb: float
    min_free_mb: float

    @property
    def to_import(self) -> List[SessionPlan]:
        return [s for s in self.sessions if s.state in ("new", "aborted")]

    @property
    def need_mb(self) -> float:
        return sum(s.need_mb for s in self.to_import)

    @property
    def enough_room(self) -> bool:
        return self.free_mb - self.need_mb >= self.min_free_mb


@dataclass
class Created:
    session: str
    take_id: str
    seconds: float


# ---------------------------------------------------------------------------------------------------- planning (writes nothing)
def _existing(takes_dir: Path) -> Dict[str, Tuple[str, str]]:
    """session id -> (take id, status) for takes that came from ACK."""
    found: Dict[str, Tuple[str, str]] = {}
    if not takes_dir.is_dir():
        return found
    for d in sorted(takes_dir.iterdir()):
        if not d.is_dir() or not TAKE_ID_RE.match(d.name):
            continue
        try:
            doc = read_json(d / "take.json") or {}
        except (OSError, ValueError):
            continue
        sid = (doc.get("client") or {}).get("ack_session")
        if sid:
            found[sid] = (d.name, doc.get("status", ""))
    return found


def _joined_frames(session: Dict[str, Any], pkg: Package) -> int:
    rate = session["audio"]["sample_rate"]
    if session["mode"] == "free":
        return pkg.wav[session["recording"]["file"]].frames
    clips = session["clips"]
    return sum(pkg.wav[c["file"]].frames for c in clips) + int(round(GAP_S * rate)) * (len(clips) - 1)


def make_plan(pkg: Package, output: Path, code: str, only: Optional[Sequence[str]] = None) -> Plan:
    cfg = Config(output_dir=output, code=code)
    existing = _existing(cfg.takes_dir)
    chosen = set(only) if only else None
    if chosen:
        unknown = sorted(chosen - {s["id"] for s in pkg.sessions})
        if unknown:
            raise ImportProblem("This package has no session " + ", ".join(unknown) + ". Sessions it has: "
                                + ", ".join(s["id"] for s in pkg.sessions))
    sessions: List[SessionPlan] = []
    for s in pkg.sessions:
        if chosen and s["id"] not in chosen:
            continue
        rate = s["audio"]["sample_rate"]
        frames = _joined_frames(s, pkg)
        if frames * 2 > MAX_WAV_DATA:
            raise ImportProblem(f"Session {s['id']} is too long to import as one recording ({frames / rate / 3600:.1f} hours). "
                                "Export it from ACK in smaller sessions.")
        hit = existing.get(s["id"])
        state = "new" if hit is None else ("aborted" if hit[1] == "importing" else "already")
        # room needed while the server finishes it: the joined audio, a second copy while it is assembled, and the decoded copy
        need = (frames * 2 * 2 + (frames / rate) * 48000 * 2) / (1024 * 1024)
        sessions.append(SessionPlan(
            id=s["id"], mode=s["mode"], label=s.get("label") or "", clips=len(s["clips"]) if s["mode"] == "script" else 0,
            seconds=frames / rate, audio_bytes=frames * 2, state=state, take_id=hit[0] if hit else None,
            need_mb=need if state != "already" else 0.0))
    return Plan(package=pkg, output=output, code=code, takes_dir=cfg.takes_dir, sessions=sessions,
                free_mb=free_mb(output if output.exists() else output.parent if output.parent.exists() else Path.home()),
                min_free_mb=float(cfg.min_free_mb))


# ---------------------------------------------------------------------------------------------------- writing
def wav_header(rate: int, data_size: int) -> bytes:
    return (b"RIFF" + struct.pack("<I", 36 + data_size) + b"WAVE" + b"fmt " + struct.pack("<IHHIIHH", 16, 1, 1, rate, rate * 2, 2, 16)
            + b"data" + struct.pack("<I", data_size))


class PartWriter:
    """Writes audio into a take's parts/ folder in fixed-size pieces, each one written whole before the next begins."""

    def __init__(self, store: TakeStore, take_id: str):
        self.store, self.take_id = store, take_id
        self.n = 0
        self.buf = bytearray()
        self.total = 0

    def write(self, data: bytes) -> None:
        self.buf += data
        self.total += len(data)
        while len(self.buf) >= PART_BYTES:
            self._flush(PART_BYTES)

    def _flush(self, size: int) -> None:
        self.store.write_chunk(self.take_id, self.n, bytes(self.buf[:size]))
        del self.buf[:size]
        self.n += 1

    def close(self) -> None:
        if self.buf:
            self._flush(len(self.buf))


def _copy_pcm(pkg: Package, name: str, writer: PartWriter, skip_header: bool = True) -> None:
    info = pkg.wav[name]
    with pkg.open_file(name) as f:
        if skip_header:
            f.read(info.data_offset)
        remaining = info.frames * 2
        while remaining:
            block = f.read(min(1 << 20, remaining))
            if not block:
                raise ImportProblem(f"{name} ended early while it was being copied; run the import again.")
            writer.write(block)
            remaining -= len(block)


def _write_audio(pkg: Package, s: Dict[str, Any], writer: PartWriter) -> List[Tuple[int, int]]:
    """Put a session's audio into the take. Returns each clip's (start frame, end frame) in the joined recording."""
    rate = s["audio"]["sample_rate"]
    if s["mode"] == "free":
        name = s["recording"]["file"]
        with pkg.open_file(name) as f:                 # already one complete WAV file: copied as it is
            while True:
                block = f.read(1 << 20)
                if not block:
                    break
                writer.write(block)
        return []
    clips = s["clips"]
    gap = int(round(GAP_S * rate))
    frames = _joined_frames(s, pkg)
    writer.write(wav_header(rate, frames * 2))
    layout: List[Tuple[int, int]] = []
    pos = 0
    for k, c in enumerate(clips):
        if k:
            writer.write(b"\x00" * (gap * 2))
            pos += gap
        n = pkg.wav[c["file"]].frames
        layout.append((pos, pos + n))
        _copy_pcm(pkg, c["file"], writer)
        pos += n
    return layout


def _reference_text(clips: List[Dict[str, Any]]) -> Tuple[str, int]:
    """The cards' words, one per line, as many as the review page's limit allows. Returns (text, how many clips are in it)."""
    out, used, size = [], 0, 0
    for c in clips:
        add = len(c["text"]) + (1 if out else 0)
        if size + add > REFERENCE_MAX:
            break
        out.append(c["text"])
        size += add
        used += 1
    return "\n".join(out), used


def _notes(pkg: Package, s: Dict[str, Any], layout: List[Tuple[int, int]], ref_clips: int) -> Dict[str, Any]:
    rate = s["audio"]["sample_rate"]
    notes: Dict[str, Any] = {
        "schema": 1, "mode": s["mode"], "session": s["id"], "package_created": pkg.manifest["created"],
        "app_version": pkg.manifest["app"].get("version", ""), "sample_rate": rate, "gap_s": GAP_S if s["mode"] == "script" else None,
        "label": s.get("label") or "", "started": s["started"], "ended": s["ended"],
        "audio_source": s["audio"]["source"], "source_requested": s["audio"]["source_requested"],
        "noise_floor_dbfs": s.get("noise_floor_dbfs"), "threshold_dbfs": s["threshold_dbfs"]}
    if s["mode"] == "script":
        notes["script"] = s["script"]
        notes["reference_clips"] = ref_clips
        notes["clips"] = [{
            "index": c["index"], "card": c["card"], "attempt": c["attempt"], "text": c["text"], "recorded": c["recorded"],
            "start_frame": a, "end_frame": b, "start_s": round(a / rate, 3), "end_s": round(b / rate, 3), "duration_s": c["duration_s"],
            "speech": c.get("speech"), "metrics": c["metrics"], "flags": list(c.get("flags") or [])}
            for c, (a, b) in zip(s["clips"], layout)]
    else:
        rec = s["recording"]
        notes["topic"] = s.get("topic") or ""
        notes["recording"] = {"duration_s": rec["duration_s"], "metrics": rec["metrics"]}
        notes["proposed_segments"] = rec.get("proposed_segments") or []
    return notes


def _client(pkg: Package, s: Dict[str, Any]) -> Dict[str, Any]:
    c: Dict[str, Any] = {
        "source": "ack", "ack_session": s["id"], "ack_mode": s["mode"], "ack_started": s["started"],
        "ack_package": pkg.manifest["created"], "ack_app": pkg.manifest["app"].get("version", "")[:40],
        "ack_audio_source": s["audio"]["source"], "ack_rate": s["audio"]["sample_rate"]}
    if s["audio"]["source"] != s["audio"]["source_requested"]:
        c["ack_source_requested"] = s["audio"]["source_requested"]
    model = (s.get("device") or {}).get("model")
    if model:
        c["ack_device"] = model[:60]
    return c


def _move_aside(plan: Plan, take_id: str) -> Path:
    dest_root = plan.takes_dir.parent / "retired" / "aborted-imports"
    dest_root.mkdir(parents=True, exist_ok=True)
    dest, n = dest_root / take_id, 1
    while dest.exists():
        n += 1
        dest = dest_root / f"{take_id}-{n}"
    shutil.move(str(plan.takes_dir / take_id), str(dest))
    return dest


def apply_import(plan: Plan, progress: Optional[Callable[[str], None]] = None) -> List[Created]:
    """Create one recording per session that still needs importing. A recording becomes visible to the server only once all its
    audio and notes are on disk (its status changes from "importing" to "finishing" in one atomic step)."""
    say = progress or (lambda _msg: None)
    pkg = plan.package
    if not plan.enough_room:
        raise NotEnoughRoom(f"There is not enough free space: this needs about {plan.need_mb:.0f} MB and keeping {plan.min_free_mb:.0f} MB spare, "
                            f"but only {plan.free_mb:.0f} MB is free. Free some up and run the import again; nothing was written.")
    store = TakeStore(plan.takes_dir)
    done: List[Created] = []
    for sp in plan.to_import:
        s = pkg.session(sp.id)
        if sp.state == "aborted" and sp.take_id:
            moved = _move_aside(plan, sp.take_id)
            say(f"  {sp.id}: an earlier import was cut short; its leftovers were moved to {moved}")
        say(f"  {sp.id}: importing {sp.clips or 'the whole'} {'clips' if sp.clips else 'recording'}, {sp.seconds / 60:.1f} min ...")
        if s["mode"] == "script":
            reference, ref_clips = _reference_text(s["clips"])
        else:
            reference, ref_clips = "", 0
        label = (s.get("label") or f"ACK {s['started'][:16].replace('T', ' ')}")[:120]
        take = store.create({"label": label, "status": "importing", "reference_text": reference, "mime": "audio/wav",
                             "client": _client(pkg, s), "imported_from": pkg.path.name, "imported_at": now_iso()})
        take_id = take["id"]
        writer = PartWriter(store, take_id)
        layout = _write_audio(pkg, s, writer)
        writer.close()
        store.write(take_id, "ack_clips.json", _notes(pkg, s, layout, ref_clips))
        store.update(take_id, status="finishing", error=None)          # from here the server picks it up
        done.append(Created(session=sp.id, take_id=take_id, seconds=sp.seconds))
    return done


# ---------------------------------------------------------------------------------------------------- the command
def _hms(seconds: float) -> str:
    m, s = divmod(int(round(seconds)), 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def print_plan(plan: Plan, dry_run: bool) -> None:
    pkg = plan.package
    summary = pkg.summary()
    print(f"\nPackage: {pkg.path.name}  (made {pkg.manifest['created']} by ACK {summary['app_version'] or '?'})")
    print(f"  Checked: {len(pkg.wav)} audio file(s), {summary['bytes'] / 1024 / 1024:.1f} MB, every checksum matches.")
    for w in pkg.warnings:
        print(f"  Note: {w}")
    print()
    words = {"new": "will be added", "already": "already imported, skipped", "aborted": "an earlier import was cut short; it will be redone"}
    for s in plan.sessions:
        what = f"{s.clips} clips" if s.mode == "script" else "free speech"
        extra = f' "{s.label}"' if s.label else ""
        print(f"  {s.id}  {s.mode:<6} {what:<10} {_hms(s.seconds):>8}{extra}  -> {words[s.state]}"
              + (f" (recording {s.take_id})" if s.state == "already" else ""))
    n = len(plan.to_import)
    if n:
        print(f"\n{'Would add' if dry_run else 'Will add'} {n} recording(s) to {plan.takes_dir}.")
        print(f"Needs about {plan.need_mb:.0f} MB; {plan.free_mb:.0f} MB is free."
              + ("" if plan.enough_room else "  THAT IS NOT ENOUGH: free some space first."))
    else:
        print("\nNothing new to add.")
    warn = sync_warning(plan.output, "Your recordings folder")
    if warn:
        print("\nNote: " + warn)
    print()


def main(argv: Optional[List[str]] = None) -> int:
    with private_umask():   # files this command creates are readable by you alone
        return _main(argv)


def _main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="freeform_studio.ack_import", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("package", help="the .zip file saved by ACK")
    ap.add_argument("--output", default="~/piper-recording-studio/output", help="piper-recording-studio's output folder")
    ap.add_argument("--code", default="en-US")
    ap.add_argument("--session", action="append", metavar="ID", help="only this session (can be repeated); default: all")
    ap.add_argument("--dry-run", action="store_true", help="check the package and show what would be added; write nothing")
    ap.add_argument("--yes", action="store_true", help="don't ask before writing")
    args = ap.parse_args(argv)
    output = Path(args.output).expanduser()
    last = [-1]

    def progress(done: int, total: int) -> None:
        pct = int(100 * done / max(total, 1))
        if sys.stdout.isatty() and pct != last[0]:
            last[0] = pct
            print(f"\r  checking the audio ... {pct}%", end="", flush=True)

    try:
        print("Checking the package ...")
        pkg = open_package(args.package, progress=progress)
        if sys.stdout.isatty():
            print("\r" + " " * 40 + "\r", end="")
        plan = make_plan(pkg, output, args.code, args.session)
        print_plan(plan, args.dry_run)
        if args.dry_run:
            return 0
        if not plan.to_import:
            print("Everything in this package is already imported. Nothing to do.\n")
            return 0
        if not args.yes:
            if not sys.stdin.isatty():
                print("Not at a terminal, so it won't write without being told to: add --yes (or use --dry-run to look).\n", file=sys.stderr)
                return 2
            if input("Add these recordings? [y/N] ").strip().lower() not in ("y", "yes"):
                print("Nothing written.\n")
                return 0
        created = apply_import(plan, progress=print)
    except (PackageError, ImportProblem) as err:
        print(f"\nCan't continue: {err}\n", file=sys.stderr)
        return 2
    print(f"\nAdded {len(created)} recording(s) to {plan.takes_dir}.")
    print("Next: start Freeform Studio (or restart it if it is already running). It decodes, listens for speech and transcribes\n"
          "each new recording by itself, then they appear in the Review page. Your package file was not changed; keep it until\n"
          "you have a backup of the imported recordings.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
