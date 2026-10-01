# SPDX-License-Identifier: GPL-3.0-or-later
"""On-disk take storage. Every write is atomic; raw audio is never modified once assembled."""
from __future__ import annotations

import json
import os
import re
import secrets
import shutil
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

TAKE_ID_RE = re.compile(r"^t\d{8}-\d{6}-[0-9a-f]{4}$")
_MIME_EXT = {"audio/webm": "webm", "audio/ogg": "ogg", "audio/mp4": "m4a", "audio/wav": "wav"}
SCHEMA = 1


class InvalidTakeId(ValueError):
    pass


class NoChunks(Exception):
    pass


class ChunkGap(Exception):
    def __init__(self, missing: List[int]):
        super().__init__(f"missing chunks: {missing[:10]}")
        self.missing = missing


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def new_take_id() -> str:
    return "t" + datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S") + "-" + secrets.token_hex(2)


def ext_for_mime(mime: str) -> str:
    base = (mime or "").split(";")[0].strip().lower()
    return _MIME_EXT.get(base, "webm")


def atomic_write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.tmp{os.getpid()}-{threading.get_ident()}")
    with open(tmp, "wb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def atomic_write_json(path: Path, obj: Any) -> None:
    atomic_write_bytes(path, (json.dumps(obj, ensure_ascii=False, indent=1) + "\n").encode("utf-8"))


def read_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default


class TakeStore:
    def __init__(self, takes_dir: Path):
        self.dir = Path(takes_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    @property
    def lock(self) -> "threading.RLock":
        return self._lock

    # -- paths ---------------------------------------------------------------
    def path(self, take_id: str, *parts: str) -> Path:
        if not TAKE_ID_RE.match(take_id or ""):
            raise InvalidTakeId(take_id)
        return self.dir.joinpath(take_id, *parts)

    # -- take.json -----------------------------------------------------------
    def create(self, fields: Dict[str, Any]) -> Dict[str, Any]:
        take_id = new_take_id()
        doc = {
            "schema": SCHEMA,
            "id": take_id,
            "created": now_iso(),
            "label": "",
            "status": "recording",
            "error": None,
            "progress": 0.0,
            "reference_text": "",
            "client": {},
            "mime": "audio/webm",
            "duration": None,
            "sample_rate": None,
            "chunks": {"count": 0, "bytes": 0, "missing": []},
            "asr": None,
        }
        doc.update(fields)
        with self._lock:
            self.path(take_id, "parts").mkdir(parents=True, exist_ok=True)
            atomic_write_json(self.path(take_id, "take.json"), doc)
        return doc

    def get(self, take_id: str) -> Optional[Dict[str, Any]]:
        return read_json(self.path(take_id, "take.json"))

    def update(self, take_id: str, **fields: Any) -> Dict[str, Any]:
        with self._lock:
            doc = self.get(take_id)
            if doc is None:
                raise FileNotFoundError(take_id)
            doc.update(fields)
            atomic_write_json(self.path(take_id, "take.json"), doc)
            return doc

    def ids(self) -> List[str]:
        return sorted((p.name for p in self.dir.iterdir() if p.is_dir() and TAKE_ID_RE.match(p.name)), reverse=True)

    def list(self) -> List[Dict[str, Any]]:
        out = []
        for take_id in self.ids():
            doc = self.get(take_id)
            if doc is None:
                continue
            edit = read_json(self.path(take_id, "edit.json"))
            segs = (edit or {}).get("segments", [])
            doc = dict(doc)
            doc["counts"] = {
                "segments": len(segs),
                "approved": sum(1 for s in segs if s.get("status") == "approved"),
                "dropped": sum(1 for s in segs if s.get("status") == "dropped"),
            }
            out.append(doc)
        return out

    # -- json side files -----------------------------------------------------
    def read(self, take_id: str, name: str, default: Any = None) -> Any:
        return read_json(self.path(take_id, name), default)

    def write(self, take_id: str, name: str, obj: Any) -> None:
        with self._lock:
            atomic_write_json(self.path(take_id, name), obj)

    def archive(self, take_id: str, name: str, subdir: str, tag: str) -> Optional[Path]:
        """Copy an existing side file into <subdir>/ before it is replaced. Returns the copy, or None."""
        src = self.path(take_id, name)
        if not src.exists():
            return None
        dst = self.path(take_id, subdir, f"{src.stem}-{tag}{src.suffix}")
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        return dst

    def prune(self, take_id: str, subdir: str, keep: int) -> None:
        d = self.path(take_id, subdir)
        if not d.is_dir():
            return
        files = sorted(d.iterdir(), key=lambda p: p.stat().st_mtime)
        for p in files[:-keep] if keep > 0 else files:
            p.unlink(missing_ok=True)

    def prune_thinned(self, take_id: str, subdir: str, recent: int = 30, bucket_s: int = 1800, cap: int = 100) -> None:
        """Keep the newest `recent` snapshots, then one per `bucket_s` of age beyond that (up to `cap` in all), so a long
        editing session still leaves restore points from hours ago. Snapshots taken before a risky operation are
        never pruned."""
        d = self.path(take_id, subdir)
        if not d.is_dir():
            return
        files = sorted(d.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
        keep = {p for p in files if any(tag in p.name for tag in ("pre-regen", "before-restore"))}
        keep.update(files[:recent])
        buckets = {int(p.stat().st_mtime // bucket_s) for p in keep}
        for p in files[recent:]:
            b = int(p.stat().st_mtime // bucket_s)
            if b not in buckets and len(keep) < cap:
                keep.add(p)
                buckets.add(b)
        for p in files:
            if p not in keep:
                p.unlink(missing_ok=True)

    # -- chunk upload --------------------------------------------------------
    def write_chunk(self, take_id: str, n: int, data: bytes) -> None:
        # One file per index: retries and duplicates just overwrite, order never matters.
        atomic_write_bytes(self.path(take_id, "parts", f"{n:06d}.bin"), data)

    def received(self, take_id: str) -> List[int]:
        parts = self.path(take_id, "parts")
        if not parts.is_dir():
            return []
        return sorted(int(p.stem) for p in parts.glob("*.bin") if p.stem.isdigit())

    def assemble(self, take_id: str, ext: str = "webm", salvage: bool = False) -> Dict[str, Any]:
        got = self.received(take_id)
        if not got:
            raise NoChunks()
        have = set(got)
        missing = [i for i in range(got[-1] + 1) if i not in have]
        if missing and not salvage:
            raise ChunkGap(missing)
        use = list(range(missing[0])) if missing else list(range(got[-1] + 1))
        if not use:
            raise NoChunks()
        dst = self.path(take_id, f"raw.{ext}")
        tmp = dst.with_name(dst.name + ".tmp")
        total = 0
        with open(tmp, "wb") as out:
            for i in use:
                data = self.path(take_id, "parts", f"{i:06d}.bin").read_bytes()
                out.write(data)
                total += len(data)
            out.flush()
            os.fsync(out.fileno())
        os.replace(tmp, dst)
        return {"count": len(use), "bytes": total, "missing": missing, "file": dst.name}

    def remove_parts(self, take_id: str) -> None:
        shutil.rmtree(self.path(take_id, "parts"), ignore_errors=True)
