# SPDX-License-Identifier: GPL-3.0-or-later
"""The registry of everything the guided setup may download (data/sources.json), and the rules an entry must meet to be fetched.

An entry is either **unpinned** (no address yet; it can be listed and sized for the disk estimate but never fetched) or **fully pinned**:
an https address on an allowed host, a file name, the revision the address points at, the exact size and the SHA-256 of the file. Nothing
is half pinned, so a fetch can always be checked against what was agreed. Plan decisions D11 and D27.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse

SCHEMA = 1
KINDS = ("voice", "model", "file")
ALLOWED_HOSTS = ("huggingface.co", "github.com")        # where a registry address may point; a download may be redirected to a CDN over https
SAFE_FILENAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._=+-]{0,149}$")
SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
MAX_FILE_BYTES = 8 * 2**30                              # a hostile or mistaken entry cannot ask for more than this
DEFAULT_PATH = Path(__file__).resolve().parent.parent / "data" / "sources.json"

PIN_FIELDS = ("url", "filename", "revision", "size_bytes", "sha256")


class RegistryError(Exception):
    pass


@dataclass(frozen=True)
class Item:
    id: str
    kind: str
    why_key: str                                  # text catalog key: one plain line on why this is downloaded
    license_id: str                               # key into the license texts shown before a download
    approx_size_bytes: Optional[int] = None       # what the host shows; used for the disk estimate, never to verify a download
    url: Optional[str] = None
    filename: Optional[str] = None
    revision: Optional[str] = None
    size_bytes: Optional[int] = None
    sha256: Optional[str] = None

    @property
    def any_pin_field(self) -> bool:
        return any(getattr(self, f) is not None for f in PIN_FIELDS)

    def pin_problems(self) -> List[str]:
        """Why this entry cannot be fetched, as short codes. An empty list means it is fully pinned."""
        if not self.any_pin_field:
            return ["unpinned"]
        problems = ["missing_" + f for f in PIN_FIELDS if getattr(self, f) is None]
        if self.url is not None:
            parsed = urlparse(self.url)
            if parsed.scheme != "https":
                problems.append("url_not_https")
            if (parsed.hostname or "") not in ALLOWED_HOSTS:
                problems.append("url_host_not_allowed")
            if parsed.username or parsed.password:
                problems.append("url_has_credentials")
            if self.revision is not None and self.revision not in self.url:
                problems.append("revision_not_in_url")
        if self.filename is not None and (not SAFE_FILENAME.match(self.filename) or ".." in self.filename):
            problems.append("unsafe_filename")
        if self.size_bytes is not None and not (0 < self.size_bytes <= MAX_FILE_BYTES):
            problems.append("size_out_of_range")
        if self.sha256 is not None and not SHA256.match(self.sha256):
            problems.append("bad_sha256")
        return problems

    @property
    def pinned(self) -> bool:
        return not self.pin_problems()

    @property
    def size_for_budget(self) -> Optional[int]:
        """The size the disk estimate uses: the exact one once pinned, otherwise what the host shows."""
        return self.size_bytes if self.size_bytes is not None else self.approx_size_bytes


@dataclass(frozen=True)
class Registry:
    items: Tuple[Item, ...]

    def get(self, item_id: str) -> Item:
        for item in self.items:
            if item.id == item_id:
                return item
        raise KeyError(item_id)


def _optional(raw: dict, key: str, kind: type) -> Optional[object]:
    value = raw.get(key)
    if value is None:
        return None
    if not isinstance(value, kind) or isinstance(value, bool):
        raise RegistryError("%s: %r is not a %s" % (raw.get("id", "?"), key, kind.__name__))
    return value


def parse_registry(text: str) -> Registry:
    try:
        data = json.loads(text)
    except ValueError as exc:
        raise RegistryError("not valid JSON: %s" % exc)
    if not isinstance(data, dict) or data.get("schema") != SCHEMA or not isinstance(data.get("items"), list):
        raise RegistryError("not a registry this version understands")
    items: List[Item] = []
    seen = set()
    for raw in data["items"]:
        if not isinstance(raw, dict):
            raise RegistryError("an entry is not an object")
        item_id, kind = raw.get("id"), raw.get("kind")
        if not isinstance(item_id, str) or not SLUG.match(item_id):
            raise RegistryError("bad id %r" % (item_id,))
        if item_id in seen:
            raise RegistryError("%s is listed twice" % item_id)
        seen.add(item_id)
        if kind not in KINDS:
            raise RegistryError("%s: unknown kind %r" % (item_id, kind))
        for needed in ("why_key", "license_id"):
            if not isinstance(raw.get(needed), str) or not raw[needed]:
                raise RegistryError("%s: %s is missing" % (item_id, needed))
        if not SLUG.match(raw["license_id"]):
            raise RegistryError("%s: bad license_id" % item_id)
        item = Item(item_id, kind, raw["why_key"], raw["license_id"], _optional(raw, "approx_size_bytes", int),
                    _optional(raw, "url", str), _optional(raw, "filename", str), _optional(raw, "revision", str),
                    _optional(raw, "size_bytes", int), _optional(raw, "sha256", str))
        if item.any_pin_field and item.pin_problems():
            raise RegistryError("%s is half pinned or wrongly pinned: %s" % (item_id, ", ".join(item.pin_problems())))
        items.append(item)
    return Registry(tuple(items))


def load_registry(path: Optional[Path] = None) -> Registry:
    path = Path(path) if path else DEFAULT_PATH
    try:
        return parse_registry(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise RegistryError("cannot read %s: %s" % (path.name, exc.strerror or exc))
