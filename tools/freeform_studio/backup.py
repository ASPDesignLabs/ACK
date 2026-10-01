"""Back up what you can't get back: your raw recordings and every decision you've made about them.

    python -m freeform_studio.backup                  # back up now (does nothing if nothing changed since the last one)
    python -m freeform_studio.backup --list           # your backups, newest first
    python -m freeform_studio.backup --verify FILE    # re-read a backup and check every file against its checksum
    python -m freeform_studio.backup --restore FILE   # put a backup's recordings back (adds only; see below)

A backup is one .tar.gz holding, for every recording: the raw audio exactly as received, take.json, edit.json (your
decisions), asr.json, and the saved earlier versions of your edits, transcripts and reference text. The decoded copy and
waveforms are left out because they are rebuilt from the raw audio (the exported training clips likewise, from the edits).
Every file is checksummed as it is written, and the finished archive is read back and checked before it counts.

Restoring never overwrites: recordings you don't have are added, identical files are skipped, and a file that differs is
left alone, with the backup's copy put under <output>/_freeform/<code>/restored-conflicts/ so nothing is lost either way.
Old backups are only ever deleted by the retention rule (the newest --keep, plus one per week for twelve weeks), and only
files this tool named; --keep 0 never deletes anything.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import io
import json
import logging
import os
import re
import shutil
import sys
import tarfile
import time
import zlib
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple

from . import __version__
from .locking import exclusive
from .storage import TAKE_ID_RE, atomic_write_bytes, atomic_write_json

_LOG = logging.getLogger(__name__)
SCHEMA = 1
MANIFEST = "MANIFEST.json"
STATE = "state.json"
LOCK = ".backup.lock"
STALE_LOCK_S = 6 * 3600
SMALL = 16 * 1024 * 1024            # files up to this size are read whole, so what is hashed is exactly what is stored
MAX_TOTAL = 400 * 1024 ** 3         # a sanity ceiling for a restore, not a practical limit
NAME_RE = re.compile(r"^freeform-backup-(?P<code>[A-Za-z0-9_-]+)-(?P<stamp>\d{8}-\d{6})(?:-\d+)?\.tar\.gz$")
RAW_RE = re.compile(r"^raw\.(webm|ogg|m4a|wav)$")
PART_RE = re.compile(r"^\d{6}\.bin$")
HIST_NAME_RE = re.compile(r"^[A-Za-z0-9._-]{1,120}$")
TOP_FILES = {"take.json", "edit.json", "asr.json"}
HISTORY_DIRS = {"edit_history", "asr_history", "reference_history"}
DEFAULT_DIR = "~/backups/freeform-studio"


class BackupError(Exception):
    """A problem to tell the person about in plain words."""


class BackupBusy(BackupError):
    """Another backup is already running."""


def takes_dir(output_dir: Path, code: str) -> Path:
    return Path(output_dir) / "_freeform" / code / "takes"


# ---------------------------------------------------------------------------- what goes in
def _allowed(parts: List[str]) -> bool:
    """Is `parts` (the path inside one take's folder) something a backup holds or restores?"""
    if len(parts) == 1:
        return parts[0] in TOP_FILES or bool(RAW_RE.match(parts[0]))
    if len(parts) == 2:
        if parts[0] in HISTORY_DIRS:
            return bool(HIST_NAME_RE.match(parts[1])) and not parts[1].startswith(".")
        return parts[0] == "parts" and bool(PART_RE.match(parts[1]))
    return False


def collect(output_dir: Path, code: str) -> List[Tuple[Path, str, int, int]]:
    """(path, name inside the archive, size, mtime_ns) for everything worth keeping, in a stable order."""
    root = takes_dir(output_dir, code)
    out: List[Tuple[Path, str, int, int]] = []
    if not root.is_dir():
        return out
    for take in sorted(d for d in root.iterdir() if d.is_dir() and not d.is_symlink() and TAKE_ID_RE.match(d.name)):
        found: List[List[str]] = []
        for p in sorted(take.iterdir()):
            if p.is_symlink():
                continue
            if p.is_file():
                found.append([p.name])
            elif p.is_dir() and (p.name in HISTORY_DIRS or p.name == "parts"):
                found.extend([p.name, q.name] for q in sorted(p.iterdir()) if q.is_file() and not q.is_symlink())
        has_raw = any(len(parts) == 1 and RAW_RE.match(parts[0]) for parts in found)
        for parts in found:
            if not _allowed(parts) or (parts[0] == "parts" and has_raw):   # loose parts are only needed until the audio is assembled
                continue
            path = take.joinpath(*parts)
            try:
                st = path.stat()
            except OSError:
                continue
            out.append((path, "takes/" + take.name + "/" + "/".join(parts), st.st_size, st.st_mtime_ns))
    return out


def fingerprint(files: List[Tuple[Path, str, int, int]]) -> str:
    h = hashlib.sha1()
    for _path, name, size, mtime in files:
        h.update(f"{name}\0{size}\0{mtime}\n".encode())
    return h.hexdigest()


# ---------------------------------------------------------------------------- making one
@dataclass
class BackupResult:
    path: Optional[Path] = None
    skipped: bool = False
    reason: str = ""
    takes: int = 0
    files: int = 0
    archive_bytes: int = 0
    pruned: List[str] = field(default_factory=list)


def _read_state(backup_dir: Path) -> Dict[str, Any]:
    try:
        doc = json.loads((backup_dir / STATE).read_text(encoding="utf-8"))
        return doc if isinstance(doc, dict) else {}
    except (OSError, ValueError):
        return {}


def _stamp_name(code: str, backup_dir: Path, now: datetime) -> str:
    base = f"freeform-backup-{code}-{now:%Y%m%d-%H%M%S}"
    name, n = f"{base}.tar.gz", 1
    while (backup_dir / name).exists():
        n += 1
        name = f"{base}-{n}.tar.gz"
    return name


def _check_destination(output_dir: Path, backup_dir: Path) -> None:
    out_root = (Path(output_dir) / "_freeform").resolve()
    dest = backup_dir.resolve()
    if dest == out_root or out_root in dest.parents:
        raise BackupError(f"The backup folder {backup_dir} is inside your recordings folder, so it would back itself up. Choose another one.")


def create(output_dir: Path, code: str, backup_dir: Path, force: bool = False, keep: int = 30, now: Optional[datetime] = None) -> BackupResult:
    """Make a backup. Returns what happened; raises BackupError if it couldn't be done safely."""
    output_dir, backup_dir = Path(output_dir), Path(backup_dir).expanduser()
    _check_destination(output_dir, backup_dir)
    now = now or datetime.now()
    if not collect(output_dir, code):
        return BackupResult(skipped=True, reason="There are no recordings to back up yet.")   # and no folder is made for nothing
    with exclusive(backup_dir / LOCK, STALE_LOCK_S, lambda p: BackupBusy(f"Another backup is running. If it crashed, delete {p} and try again.")):
        files = collect(output_dir, code)
        fp = fingerprint(files)
        state = _read_state(backup_dir)
        last = backup_dir / str(state.get("file", ""))
        if not force and state.get("fingerprint") == fp and state.get("file") and last.is_file():
            return BackupResult(skipped=True, path=last, reason=f"Nothing has changed since the last backup ({last.name}).")
        total = sum(f[2] for f in files)
        probe = backup_dir
        while not probe.exists() and probe != probe.parent:
            probe = probe.parent
        free = shutil.disk_usage(probe).free
        if free < total * 1.05 + 50 * 1024 * 1024:
            raise BackupError(f"Not enough room for a backup in {backup_dir}: it needs about {total / 1024 ** 2:.0f} MB and "
                              f"{free / 1024 ** 2:.0f} MB is free. Free some space or choose another folder with --backup-dir.")
        backup_dir.mkdir(parents=True, exist_ok=True)
        name = _stamp_name(code, backup_dir, now)
        partial = backup_dir / (name + ".partial")
        try:
            manifest = _write_archive(partial, files, code, fp, now)
            problems, _ = verify(partial)
            if problems:
                raise BackupError("The backup was written but did not read back correctly, so it was thrown away: " + "; ".join(problems[:3]))
            final = backup_dir / name
            os.replace(partial, final)
        except BaseException:
            partial.unlink(missing_ok=True)
            raise
        takes = len({f[1].split("/")[1] for f in files})
        side = {"created": now.isoformat(timespec="seconds"), "code": code, "takes": takes, "files": len(files),
                "source_bytes": total, "archive_bytes": final.stat().st_size, "fingerprint": fp, "version": __version__}
        atomic_write_json(backup_dir / (name + ".json"), side)
        atomic_write_json(backup_dir / STATE, {"fingerprint": fp, "file": name, "created": side["created"]})
        result = BackupResult(path=final, takes=takes, files=len(files), archive_bytes=side["archive_bytes"])
        if keep > 0:
            result.pruned = prune(backup_dir, code, keep_recent=keep)
        return result


def _write_archive(path: Path, files: List[Tuple[Path, str, int, int]], code: str, fp: str, now: datetime) -> Dict[str, Any]:
    entries: List[Dict[str, Any]] = []
    with tarfile.open(path, "w:gz", compresslevel=6) as tar:
        for src, name, size, mtime in files:
            info = tarfile.TarInfo(name)
            info.mode, info.mtime = 0o644, mtime // 1_000_000_000
            h = hashlib.sha256()
            if size <= SMALL:
                data = src.read_bytes()
                h.update(data)
                info.size = len(data)
                tar.addfile(info, io.BytesIO(data))
                entries.append({"path": name, "size": len(data), "sha256": h.hexdigest()})
            else:
                with open(src, "rb") as f:
                    info.size = os.fstat(f.fileno()).st_size   # raw recordings never change once assembled
                    tar.addfile(info, _Hashing(f, h))
                entries.append({"path": name, "size": info.size, "sha256": h.hexdigest()})
        manifest = {"schema": SCHEMA, "created": now.isoformat(timespec="seconds"), "code": code, "version": __version__,
                    "fingerprint": fp, "files": entries}
        blob = json.dumps(manifest, indent=1).encode("utf-8")
        info = tarfile.TarInfo(MANIFEST)
        info.size, info.mode, info.mtime = len(blob), 0o644, int(time.time())
        tar.addfile(info, io.BytesIO(blob))
    return manifest


class _Hashing:
    def __init__(self, f, h) -> None:
        self._f, self._h = f, h

    def read(self, n: int = -1) -> bytes:
        data = self._f.read(n)
        self._h.update(data)
        return data


# ---------------------------------------------------------------------------- checking one
def _members(tar: tarfile.TarFile) -> Iterator[tarfile.TarInfo]:
    yield from tar


def verify(path: Path) -> Tuple[List[str], Optional[Dict[str, Any]]]:
    """Read the whole archive back. Returns (problems, manifest); no problems means every file is exactly as recorded."""
    problems: List[str] = []
    manifest: Optional[Dict[str, Any]] = None
    seen: Dict[str, Tuple[int, str]] = {}
    try:
        with tarfile.open(path, "r:gz") as tar:
            for m in _members(tar):
                if not m.isfile():
                    problems.append(f"{m.name}: not an ordinary file")
                    continue
                f = tar.extractfile(m)
                if f is None:
                    problems.append(f"{m.name}: cannot be read")
                    continue
                h, n = hashlib.sha256(), 0
                blob = bytearray() if m.name == MANIFEST else None
                for chunk in iter(lambda: f.read(1024 * 1024), b""):
                    h.update(chunk)
                    n += len(chunk)
                    if blob is not None:
                        blob.extend(chunk)
                if m.name == MANIFEST:
                    try:
                        manifest = json.loads(bytes(blob).decode("utf-8"))
                    except (ValueError, UnicodeDecodeError):
                        problems.append("the manifest is damaged")
                elif m.name in seen:
                    problems.append(f"{m.name}: appears more than once")
                else:
                    seen[m.name] = (n, h.hexdigest())
    except (tarfile.TarError, EOFError, OSError, ValueError, zlib.error) as err:
        return [f"the archive cannot be read all the way through ({type(err).__name__}: {err})"], None
    if manifest is None:
        problems.append("it has no manifest, so it can't be checked")
        return problems, None
    listed = {e.get("path"): e for e in manifest.get("files", []) if isinstance(e, dict)}
    for name, e in listed.items():
        got = seen.get(name)
        if got is None:
            problems.append(f"{name}: listed but missing")
        elif got != (e.get("size"), e.get("sha256")):
            problems.append(f"{name}: does not match its checksum")
    for name in seen:
        if name not in listed:
            problems.append(f"{name}: in the archive but not in its manifest")
    return problems, manifest


# ---------------------------------------------------------------------------- listing and retention
def list_backups(backup_dir: Path, code: Optional[str] = None) -> List[Dict[str, Any]]:
    backup_dir = Path(backup_dir).expanduser()
    out: List[Dict[str, Any]] = []
    if not backup_dir.is_dir():
        return out
    for p in backup_dir.iterdir():
        m = NAME_RE.match(p.name)
        if not m or not p.is_file() or (code and m.group("code") != code):
            continue
        try:
            side = json.loads((backup_dir / (p.name + ".json")).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            side = {}
        created = side.get("created") or datetime.strptime(m.group("stamp"), "%Y%m%d-%H%M%S").isoformat(timespec="seconds")
        out.append({"name": p.name, "path": str(p), "created": created, "size": p.stat().st_size,
                    "takes": side.get("takes"), "files": side.get("files"), "code": m.group("code")})
    return sorted(out, key=lambda b: (b["created"], b["name"]), reverse=True)


def prune(backup_dir: Path, code: str, keep_recent: int = 30, keep_weekly: int = 12) -> List[str]:
    """Delete old backups, but only ones this tool named: keep the newest `keep_recent`, and past those one per week for
    `keep_weekly` weeks. Returns the names removed."""
    backups = list_backups(backup_dir, code)
    keep = {b["name"] for b in backups[:keep_recent]}
    weeks: Dict[Tuple[int, int], str] = {}
    for b in backups[keep_recent:]:
        iso = datetime.fromisoformat(b["created"]).isocalendar()
        weeks.setdefault((iso[0], iso[1]), b["name"])             # the newest of that week, since the list is newest first
    for week in sorted(weeks, reverse=True)[:keep_weekly]:
        keep.add(weeks[week])
    removed = []
    for b in backups:
        if b["name"] not in keep:
            for suffix in ("", ".json"):
                (Path(backup_dir).expanduser() / (b["name"] + suffix)).unlink(missing_ok=True)
            removed.append(b["name"])
    return removed


def status(backup_dir: Optional[Path], code: str, takes_present: bool) -> Dict[str, Any]:
    """What the pages show about backups."""
    if backup_dir is None:
        return {"enabled": False, "dir": None, "count": 0, "last": None, "takes_present": takes_present}
    backups = list_backups(backup_dir, code)
    return {"enabled": True, "dir": str(Path(backup_dir).expanduser()), "count": len(backups), "last": backups[0] if backups else None,
            "takes_present": takes_present}


# ---------------------------------------------------------------------------- restoring one
@dataclass
class RestoreReport:
    restored: List[str] = field(default_factory=list)
    same: List[str] = field(default_factory=list)
    conflicts: List[str] = field(default_factory=list)
    takes: List[str] = field(default_factory=list)          # recordings that gained files, for rebuilding their decoded audio
    conflicts_dir: Optional[str] = None


def _destination(rel: str) -> Optional[List[str]]:
    """The path parts inside the takes folder for an archive name, or None if the name isn't one a backup holds."""
    parts = rel.split("/")
    if len(parts) < 3 or parts[0] != "takes" or not TAKE_ID_RE.match(parts[1]) or any(p in ("", ".", "..") for p in parts) or "\\" in rel:
        return None
    return parts[1:] if _allowed(parts[2:]) else None


def restore(archive: Path, output_dir: Path, code: str, dry_run: bool = False, now: Optional[datetime] = None) -> RestoreReport:
    archive = Path(archive).expanduser()
    problems, manifest = verify(archive)
    if problems:
        raise BackupError("This backup can't be trusted, so nothing was restored: " + "; ".join(problems[:4]))
    entries = {e["path"]: e for e in manifest["files"]}
    if sum(e["size"] for e in entries.values()) > MAX_TOTAL:
        raise BackupError("This backup claims to hold an implausible amount of data, so nothing was restored.")
    bad = [name for name in entries if _destination(name) is None]
    if bad:
        raise BackupError(f"This backup holds files that don't belong in a recordings folder ({bad[0]}), so nothing was restored.")
    root = takes_dir(output_dir, code)
    stamp = (now or datetime.now()).strftime("%Y%m%d-%H%M%S")
    aside = Path(output_dir) / "_freeform" / code / "restored-conflicts" / stamp
    report = RestoreReport()
    plan: Dict[str, Tuple[str, Path]] = {}
    for name, e in sorted(entries.items()):
        dest = root.joinpath(*_destination(name))
        if not dest.exists():
            plan[name] = ("restore", dest)
        elif _sha256(dest) == e["sha256"]:
            plan[name] = ("same", dest)
        else:
            plan[name] = ("conflict", aside.joinpath(*_destination(name)))
    for name, (what, _dest) in plan.items():
        {"restore": report.restored, "same": report.same, "conflict": report.conflicts}[what].append(name)
    report.takes = sorted({n.split("/")[1] for n in report.restored if _destination(n)[1] != "parts"})
    if report.conflicts:
        report.conflicts_dir = str(aside)
    if dry_run:
        return report
    with tarfile.open(archive, "r:gz") as tar:
        for m in _members(tar):
            what_dest = plan.get(m.name)
            if what_dest is None or what_dest[0] == "same":
                continue
            _, dest = what_dest
            f = tar.extractfile(m)
            want = entries[m.name]["sha256"]
            dest.parent.mkdir(parents=True, exist_ok=True)
            if m.size <= SMALL:
                data = f.read()
                if hashlib.sha256(data).hexdigest() != want:
                    raise BackupError(f"{m.name} changed while it was being restored; stopped. Nothing already in place was altered.")
                atomic_write_bytes(dest, data)
            else:
                tmp = dest.with_name(dest.name + ".restoring")
                h = hashlib.sha256()
                try:
                    with open(tmp, "wb") as out:
                        for chunk in iter(lambda: f.read(1024 * 1024), b""):
                            h.update(chunk)
                            out.write(chunk)
                        out.flush()
                        os.fsync(out.fileno())
                    if h.hexdigest() != want:
                        raise BackupError(f"{m.name} changed while it was being restored; stopped. Nothing already in place was altered.")
                    os.replace(tmp, dest)
                finally:
                    tmp.unlink(missing_ok=True)
    return report


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------------------- automatic backups for the server
class BackupScheduler:
    """Backs up on a timer while the server runs, but only when something has changed (so an idle PC writes nothing)."""

    def __init__(self, cfg: Any, has_recordings: Any) -> None:
        self.cfg = cfg
        self._has_recordings = has_recordings
        self.running = False
        self.error: Optional[str] = None
        self._task: Optional["asyncio.Task[None]"] = None

    @property
    def enabled(self) -> bool:
        return self.cfg.backup_dir is not None

    @property
    def automatic(self) -> bool:
        return self.enabled and self.cfg.backup_every_hours > 0

    async def start(self) -> None:
        if self.automatic:
            self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass
            self._task = None

    async def run_now(self, force: bool = False) -> BackupResult:
        if not self.enabled:
            raise BackupError("Backups aren't set up. Start the server with --backup-dir to choose where they go.")
        self.running = True
        try:
            result = await asyncio.to_thread(create, self.cfg.output_dir, self.cfg.code, self.cfg.backup_dir, force, self.cfg.backup_keep)
            self.error = None
            return result
        except BackupError as err:
            self.error = str(err)
            raise
        except OSError as err:
            self.error = f"Couldn't write the backup: {err}"
            raise BackupError(self.error) from err
        finally:
            self.running = False

    async def _loop(self) -> None:
        await asyncio.sleep(max(0.0, self.cfg.backup_first_delay_s))
        while True:
            try:
                result = await self.run_now()
                if not result.skipped:
                    _LOG.info("backed up %s recordings to %s", result.takes, result.path)
            except BackupBusy:
                pass                                       # someone is backing up by hand: try again next time
            except BackupError as err:
                _LOG.warning("automatic backup failed: %s", err)
            await asyncio.sleep(self.cfg.backup_every_hours * 3600)

    def status(self) -> Dict[str, Any]:
        doc = status(self.cfg.backup_dir, self.cfg.code, bool(self._has_recordings()))
        doc.update({"auto": {"enabled": self.automatic, "every_hours": self.cfg.backup_every_hours}, "running": self.running, "error": self.error})
        last = doc.get("last")
        if last:
            doc["age_hours"] = round(max(0.0, (datetime.now() - datetime.fromisoformat(last["created"])).total_seconds() / 3600), 1)
        return doc


# ---------------------------------------------------------------------------- command line
def _mb(n: float) -> str:
    return f"{n / 1024 ** 2:.1f} MB"


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--output", default="~/piper-recording-studio/output", help="piper-recording-studio's output folder")
    ap.add_argument("--code", default="en-US")
    ap.add_argument("--backup-dir", default=DEFAULT_DIR, help="where backups are kept (default: %(default)s)")
    ap.add_argument("--force", action="store_true", help="back up even if nothing has changed")
    ap.add_argument("--keep", type=int, default=30, help="how many recent backups to keep (more are kept weekly); 0 never deletes (default: 30)")
    ap.add_argument("--list", action="store_true", help="list backups")
    ap.add_argument("--verify", metavar="FILE", help="check a backup file against its checksums")
    ap.add_argument("--restore", metavar="FILE", help="add a backup's recordings back (never overwrites)")
    ap.add_argument("--dry-run", action="store_true", help="with --restore: show what would happen and write nothing")
    args = ap.parse_args(argv)
    output, backup_dir = Path(args.output).expanduser(), Path(args.backup_dir).expanduser()
    try:
        if args.list:
            rows = list_backups(backup_dir, args.code)
            print(f"\nBackups in {backup_dir}:" if rows else f"\nNo backups in {backup_dir} yet.")
            for b in rows:
                print(f"  {b['created']}  {_mb(b['size']):>10}  {b['takes'] if b['takes'] is not None else '?'} recordings  {b['name']}")
            print()
            return 0
        if args.verify:
            problems, manifest = verify(Path(args.verify).expanduser())
            if problems:
                print("\nThis backup has problems:")
                for p in problems[:20]:
                    print("  PROBLEM", p)
                print()
                return 1
            print(f"\nOK: {len(manifest['files'])} files, every one matches its checksum.\n")
            return 0
        if args.restore:
            report = restore(Path(args.restore), output, args.code, dry_run=args.dry_run)
            print(f"\n{'DRY RUN, nothing written. ' if args.dry_run else ''}From {args.restore}:")
            print(f"  added: {len(report.restored)} files    already identical: {len(report.same)}    different (left alone): {len(report.conflicts)}")
            if report.conflicts:
                print(f"  The backup's copy of those {len(report.conflicts)} files is in {report.conflicts_dir}; yours were not changed.")
            problem = False
            if not args.dry_run and report.takes:
                from .audio import FfmpegError
                from .repair import rebuild_missing
                failures: Dict[str, str] = {}
                try:
                    fixed = rebuild_missing(output, args.code, report.takes, failures)
                    print(f"  rebuilt the decoded audio for {len(fixed)} recording(s) so they can be reviewed again")
                except FfmpegError as err:
                    problem = True
                    print(f"  could not rebuild the decoded audio: {err}")
                    print("  Install what it says, then run: python -m freeform_studio.repair")
                for tid, reason in failures.items():
                    problem = True
                    print(f"  could not rebuild {tid}: {reason}")
                if problem:
                    print("  The restore itself worked and every file is back. Recordings that couldn't be rebuilt can't be reviewed")
                    print("  until the problem is fixed (or their raw audio is replaced); run python -m freeform_studio.repair to try again.")
            print()
            return 1 if problem else 0
        result = create(output, args.code, backup_dir, force=args.force, keep=args.keep)
    except BackupError as err:
        print(f"\nCan't continue: {err}\n", file=sys.stderr)
        return 2
    if result.skipped:
        print(f"\n{result.reason}\n")
        return 0
    print(f"\nBacked up {result.takes} recordings ({result.files} files) to {result.path}  ({_mb(result.archive_bytes)}), and read it back to check it.")
    if result.pruned:
        print(f"Removed {len(result.pruned)} older backup(s) beyond what is kept: {', '.join(result.pruned)}")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
