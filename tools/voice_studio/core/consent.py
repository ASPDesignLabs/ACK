# SPDX-License-Identifier: GPL-3.0-or-later
"""A record of what the person agreed to download, for exactly those files.

Consent names each item and, for a registry file, the very address, size and checksum that were shown. If the registry later points at a
different file under the same name, the old consent does not cover it. Ids with no file behind them ("apt:git", "pip:lock") are consented to
by name alone. The record is a small JSON file only its owner can read.
"""
from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional, Tuple

from .registry import Item

SCHEMA = 1


@dataclass(frozen=True)
class ConsentEntry:
    id: str
    url: Optional[str] = None
    size_bytes: Optional[int] = None
    sha256: Optional[str] = None


@dataclass(frozen=True)
class ConsentRecord:
    entries: Tuple[ConsentEntry, ...]
    given_at: str

    def covers(self, item: Item) -> bool:
        """True only for a pinned item whose address, size and checksum are those that were consented to."""
        return item.pinned and ConsentEntry(item.id, item.url, item.size_bytes, item.sha256) in self.entries

    def covers_id(self, item_id: str) -> bool:
        return ConsentEntry(item_id) in self.entries


def make_consent(items: Iterable[Item], extra_ids: Iterable[str] = (), now: Optional[datetime] = None) -> ConsentRecord:
    entries = [ConsentEntry(i.id, i.url, i.size_bytes, i.sha256) for i in items if i.pinned]
    entries += [ConsentEntry(x) for x in extra_ids]
    stamp = (now or datetime.now(timezone.utc)).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return ConsentRecord(tuple(entries), stamp)


def merge_consent(old: Optional[ConsentRecord], new: ConsentRecord) -> ConsentRecord:
    """Add a new agreement to the saved one. An id in both takes the new entry (the registry may now point at a different file, and only what was
    shown this time is agreed to); everything else already agreed to stays. Agreeing to a longer list never forgets an earlier yes."""
    if old is None:
        return new
    newer = {e.id for e in new.entries}
    return ConsentRecord(tuple(e for e in old.entries if e.id not in newer) + new.entries, new.given_at)


def save_consent(path: Path, record: ConsentRecord) -> None:
    """Atomic: a crash leaves the old record or the new one. Created owner-only."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    body = json.dumps({"schema": SCHEMA, "given_at": record.given_at,
                       "entries": [{"id": e.id, "url": e.url, "size_bytes": e.size_bytes, "sha256": e.sha256} for e in record.entries]}, indent=2)
    fd, temp = tempfile.mkstemp(dir=str(path.parent), prefix=".consent-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(body + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temp, 0o600)
        os.replace(temp, path)
    except BaseException:
        try:
            os.unlink(temp)
        except OSError:
            pass
        raise


def load_consent(path: Path) -> Optional[ConsentRecord]:
    """The saved record, or None if there is none or it is damaged. Never raises: a damaged record simply means nothing is consented to."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if data.get("schema") != SCHEMA:
            return None
        entries = []
        for raw in data["entries"]:
            size = raw.get("size_bytes")
            if not isinstance(raw["id"], str) or (size is not None and (not isinstance(size, int) or isinstance(size, bool))):
                return None
            entries.append(ConsentEntry(raw["id"], raw.get("url"), size, raw.get("sha256")))
        return ConsentRecord(tuple(entries), str(data["given_at"]))
    except (OSError, ValueError, KeyError, TypeError, AttributeError, RecursionError):        # RecursionError: a file nested far too deep is damaged too
        return None
