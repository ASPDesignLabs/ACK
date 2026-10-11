# SPDX-License-Identifier: GPL-3.0-or-later
"""Pin ACK Voice Studio's downloads (the speech model and the starting voices) to exact files: address at a fixed revision, size and SHA-256.

For maintainers only. It is NOT part of the app (tools/voice_studio never imports it, and the app never runs it): it asks the host's public listing
what is in each repository, so it needs a network. Run it on a computer that can reach huggingface.co, then commit what it writes.

    python3 tools/voice_studio_maint/make_pins.py list datasets/rhasspy/piper-checkpoints en/en_US/mike     # look first: what is in a folder at the newest revision
    python3 tools/voice_studio_maint/make_pins.py pin --out pins.json                              # read tools/voice_studio_maint/pins/wanted.json, write entries
    python3 tools/voice_studio_maint/make_pins.py merge pins.json                                  # put them into tools/voice_studio/data/sources.json

What `pin` does for each wanted file, and why:

* A repository is `org/name` for a model and `datasets/org/name` for a dataset (the starting voices' checkpoints are in a dataset).
* The branch name (`main`) is turned into the **commit** it points at right now, and every address names that commit, so the file cannot change under the pin.
* The listing gives each large file's SHA-256 and size (the host stores large files by their SHA-256). It is asked a second way too (the headers of the download
  address), and the two must agree. A small file has no SHA-256 in the listing, so it is downloaded and hashed here, and its size must match the listing.
* A pattern that matches more than one file is not guessed at: it prints the candidates and stops, and you choose with `--pick ID=FILENAME`.
* Nothing is written unless every file is covered. `merge` only replaces or adds the entries it is given and keeps everything else in the registry as it is.

The app checks every download against these pins (core/fetch.py), so a wrong pin cannot install anything: it makes the download fail.
"""
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Tuple

HOST = "https://huggingface.co"
HERE = Path(__file__).resolve().parent
WANTED = HERE / "pins" / "wanted.json"
REGISTRY = HERE.parent / "voice_studio" / "data" / "sources.json"
SHA256 = re.compile(r"^[0-9a-f]{64}$")
COMMIT = re.compile(r"^[0-9a-f]{40}$")
SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
SAFE_FILENAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._=+-]{0,149}$")          # the same rule as core/registry.py
USER_AGENT = "ack-voice-studio-pin-maker"
CHUNK = 1 << 20


class PinError(Exception):
    pass


class NeedsChoice(PinError):
    def __init__(self, spec_id: str, pattern: str, candidates: Sequence["Entry"]):
        super().__init__("%s: %r matches %d files; choose one with --pick %s=FILENAME" % (spec_id, pattern, len(candidates), spec_id))
        self.spec_id, self.pattern, self.candidates = spec_id, pattern, tuple(candidates)


@dataclass(frozen=True)
class Entry:
    path: str
    size: int
    lfs_sha256: Optional[str]            # set for a large file: the host's own SHA-256 of its content

    @property
    def name(self) -> str:
        return self.path.rsplit("/", 1)[-1]


# ---------------------------------------------------------------- reading the host's listing

def parse_tree(text: str) -> List[Entry]:
    """The files in a listing (folders are skipped). Raises PinError, quoting what was received, if it is not the shape the host documents."""
    try:
        data = json.loads(text)
    except ValueError as exc:
        raise PinError("the listing is not JSON (%s): %r" % (exc, text[:120]))
    if not isinstance(data, list):
        raise PinError("the listing is not a list: %r" % (text[:200],))
    files: List[Entry] = []
    for raw in data:
        if not isinstance(raw, dict) or not isinstance(raw.get("type"), str) or not isinstance(raw.get("path"), str):
            raise PinError("an entry in the listing has no type or path: %r" % (raw,))
        if raw["type"] != "file":
            continue
        size = raw.get("size")
        if not isinstance(size, int) or isinstance(size, bool) or size <= 0:
            raise PinError("%s has no usable size: %r" % (raw["path"], size))
        lfs = raw.get("lfs")
        oid = None
        if lfs is not None:
            oid = lfs.get("oid") if isinstance(lfs, dict) else None
            if not isinstance(oid, str) or not SHA256.match(oid):
                raise PinError("%s: the large-file entry has no SHA-256: %r" % (raw["path"], lfs))
            if isinstance(lfs.get("size"), int) and lfs["size"] != size:
                raise PinError("%s: the listing gives two sizes (%d and %d)" % (raw["path"], size, lfs["size"]))
        files.append(Entry(raw["path"], size, oid))
    return files


def folders(text: str) -> List[str]:
    """The names of the folders in a listing (for looking around; nothing is ever pinned from a folder)."""
    try:
        data = json.loads(text)
    except ValueError:
        return []
    return sorted(e["path"] for e in data if isinstance(e, dict) and e.get("type") == "directory" and isinstance(e.get("path"), str)) if isinstance(data, list) else []


def next_page(link_header: Optional[str]) -> Optional[str]:
    """The address of the next page of a listing, from the `Link` header, or None."""
    for part in (link_header or "").split(","):
        match = re.match(r'\s*<([^>]+)>\s*;\s*rel="next"\s*$', part)
        if match:
            return match.group(1)
    return None


# ---------------------------------------------------------------- choosing files

def select(entries: Sequence[Entry], directory: str, pattern: str) -> List[Entry]:
    """The files directly inside `directory` whose name matches `pattern` (a shell pattern, case-sensitive), sorted by name."""
    prefix = directory.strip("/") + "/" if directory.strip("/") else ""
    found = [e for e in entries if e.path.startswith(prefix) and "/" not in e.path[len(prefix):] and fnmatch.fnmatchcase(e.name, pattern)]
    return sorted(found, key=lambda e: e.path)


def slug_part(filename: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", filename.lower()).strip("-")


def item_id(spec: dict, entry: Entry) -> str:
    result = spec["id"] + ("-" + slug_part(entry.name) if spec.get("id_per_file") else "")
    if not SLUG.match(result):
        raise PinError("%s: %r is not a usable id" % (spec["id"], result))
    return result


def quoted(path: str) -> str:
    return urllib.parse.quote(path, safe="/=+-._")


def api_base(repo: str) -> str:
    """The listing address of a repository. A dataset is written `datasets/org/name` (that is also how its download addresses begin); a model is `org/name`."""
    return "%s/api/%s" % (HOST, repo if repo.startswith("datasets/") else "models/" + repo)


def address(repo: str, commit: str, path: str) -> str:
    return "%s/%s/resolve/%s/%s" % (HOST, repo, commit, quoted(path))


def build_item(spec: dict, entry: Entry, commit: str, sha256: str, size: int) -> dict:
    if not COMMIT.match(commit):
        raise PinError("%s: %r is not a commit" % (spec["id"], commit))
    if not SHA256.match(sha256) or size <= 0:
        raise PinError("%s: bad checksum or size" % entry.path)
    if not SAFE_FILENAME.match(entry.name) or ".." in entry.name:
        raise PinError("%s: the registry would refuse this file name" % entry.name)
    if any(part in ("", ".", "..") for part in entry.path.split("/")):
        raise PinError("%s: a path with an empty, . or .. part is not written" % entry.path)
    approx = size if spec.get("id_per_file") or not spec.get("approx_size_bytes") else spec["approx_size_bytes"]       # a voice keeps the round number the host shows
    item = {"id": item_id(spec, entry), "kind": spec["kind"], "why_key": spec["why_key"], "license_id": spec["license_id"], "approx_size_bytes": approx}
    if spec.get("folder"):
        item["folder"] = spec["folder"]
    if spec.get("pages"):
        item["pages"] = dict(spec["pages"])          # pages to read before the download: a re-pin must not drop them, because merge_registry replaces a whole entry
    item.update({"filename": entry.name, "url": address(spec["repo"], commit, entry.path), "revision": commit, "size_bytes": size, "sha256": sha256})
    return item


# ---------------------------------------------------------------- asking the host (the only part that needs a network)

class Hub:
    """The host's public listing and download addresses. Tests hand in a stand-in with the same methods."""

    def get(self, url: str):
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            return urllib.request.urlopen(request, timeout=60)
        except urllib.error.HTTPError as exc:
            raise PinError("%s answered %d" % (url, exc.code))
        except (urllib.error.URLError, OSError) as exc:
            raise PinError("could not reach %s (%s)" % (url, getattr(exc, "reason", exc)))

    def commit(self, repo: str, revision: str) -> str:
        with self.get("%s/revision/%s" % (api_base(repo), urllib.parse.quote(revision, safe=""))) as reply:
            data = json.loads(reply.read().decode("utf-8"))
        sha = data.get("sha") if isinstance(data, dict) else None
        if not isinstance(sha, str) or not COMMIT.match(sha):
            raise PinError("%s at %s: the host gave no commit: %r" % (repo, revision, str(data)[:200]))
        return sha

    def tree(self, repo: str, commit: str, directory: str) -> str:
        url: Optional[str] = "%s/tree/%s%s" % (api_base(repo), commit, "/" + quoted(directory.strip("/")) if directory.strip("/") else "")
        pages: List[dict] = []
        while url:
            with self.get(url) as reply:
                pages.extend(json.loads(reply.read().decode("utf-8")))
                url = next_page(reply.headers.get("Link"))
        return json.dumps(pages)

    def linked(self, repo: str, commit: str, path: str) -> Dict[str, str]:
        """The headers of the download address itself, without following where it leads: the host states the content's SHA-256 and size there."""
        class Stop(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *args, **kwargs):
                return None
        opener = urllib.request.build_opener(Stop)
        request = urllib.request.Request(address(repo, commit, path), method="HEAD", headers={"User-Agent": USER_AGENT})
        try:
            reply = opener.open(request, timeout=60)
            headers = reply.headers
        except urllib.error.HTTPError as exc:
            headers = exc.headers
            if exc.code not in (301, 302, 303, 307, 308):
                raise PinError("%s answered %d" % (address(repo, commit, path), exc.code))
        except (urllib.error.URLError, OSError) as exc:
            raise PinError("could not reach the host (%s)" % (getattr(exc, "reason", exc),))
        return {k.lower(): v for k, v in headers.items()}

    def hash_of(self, repo: str, commit: str, path: str) -> Tuple[str, int]:
        digest, total = hashlib.sha256(), 0
        with self.get(address(repo, commit, path)) as reply:
            for block in iter(lambda: reply.read(CHUNK), b""):
                digest.update(block)
                total += len(block)
        return digest.hexdigest(), total


# ---------------------------------------------------------------- one wanted thing

def cross_check(entry: Entry, headers: Dict[str, str]) -> str:
    """"agreed", or "not stated" when the host did not give its own SHA-256 there; raises PinError when the two views disagree."""
    stated = headers.get("x-linked-etag", "").strip()
    if stated.startswith("W/"):
        stated = stated[2:]
    stated = stated.strip('"').lower()
    size = headers.get("x-linked-size", "").strip()
    if not stated and not size:
        return "not stated"
    if stated and stated != entry.lfs_sha256:
        raise PinError("%s: the listing says SHA-256 %s but the download address says %s" % (entry.path, entry.lfs_sha256, stated))
    if size and size != str(entry.size):
        raise PinError("%s: the listing says %d bytes but the download address says %s" % (entry.path, entry.size, size))
    return "agreed"


@dataclass(frozen=True)
class Pinned:
    item: dict
    how: str                     # where the checksum came from, for the report


def pin_spec(spec: dict, hub, picks: Dict[str, str]) -> List[Pinned]:
    commit = hub.commit(spec["repo"], spec.get("revision", "main"))
    entries = parse_tree(hub.tree(spec["repo"], commit, spec.get("directory", "")))
    chosen: List[Entry] = []
    for pattern in spec["files"]:
        found = select(entries, spec.get("directory", ""), pattern)
        if spec["id"] in picks:
            found = [e for e in found if e.name == picks[spec["id"]]]
        if not found:
            if pattern in spec.get("optional", []):
                continue
            raise PinError("%s: nothing named %r in %s at %s; the folder holds: %s" % (
                spec["id"], pattern, spec.get("directory") or "the top", commit[:10], ", ".join(e.name for e in entries[:20]) or "no files"))
        if len(found) > 1 and not spec.get("id_per_file"):
            raise NeedsChoice(spec["id"], pattern, found)           # a model of several files takes every match; a single file is never guessed
        chosen.extend(found)
    if not chosen:
        raise PinError("%s: no files were chosen" % spec["id"])
    if not spec.get("id_per_file") and len(chosen) != 1:
        raise PinError("%s: it names one file but %d were chosen" % (spec["id"], len(chosen)))
    pinned: List[Pinned] = []
    for entry in chosen:
        if entry.lfs_sha256:
            how = "listing, %s by the download address" % cross_check(entry, hub.linked(spec["repo"], commit, entry.path))
            sha, size = entry.lfs_sha256, entry.size
        else:
            sha, size = hub.hash_of(spec["repo"], commit, entry.path)
            if size != entry.size:
                raise PinError("%s: downloaded %d bytes but the listing says %d" % (entry.path, size, entry.size))
            how = "downloaded and hashed here"
        pinned.append(Pinned(build_item(spec, entry, commit, sha, size), how))
    return pinned


# ---------------------------------------------------------------- the registry

def merge_registry(registry_text: str, items: Sequence[dict], drop: Iterable[str] = ()) -> str:
    """The registry with `items` put in: an entry with the same id is replaced where it stands, a new one goes at the end, and the ids in `drop` are removed.
    Everything else is left exactly as it was."""
    data = json.loads(registry_text)
    if not isinstance(data, dict) or not isinstance(data.get("items"), list):
        raise PinError("the registry is not in the shape this expects")
    dropped = set(drop)
    new = {i["id"]: i for i in items}
    if len(new) != len(items):
        raise PinError("two of the new entries have the same id")
    result: List[dict] = []
    placed = set()
    for old in data["items"]:
        if old.get("id") in new:
            result.append(new[old["id"]])
            placed.add(old["id"])
        elif old.get("id") not in dropped:
            result.append(old)
    result.extend(i for i in items if i["id"] not in placed)
    data["items"] = result
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


# ---------------------------------------------------------------- the command line

def load_wanted(text: str) -> List[dict]:
    data = json.loads(text)
    if not isinstance(data, dict) or data.get("schema") != 1 or not isinstance(data.get("specs"), list):
        raise PinError("the list of wanted files is not in the shape this expects")
    seen = set()
    for spec in data["specs"]:
        for needed in ("id", "kind", "why_key", "license_id", "repo", "files"):
            if needed not in spec:
                raise PinError("a wanted entry has no %r: %r" % (needed, spec.get("id")))
        if spec["id"] in seen:
            raise PinError("%s is listed twice" % spec["id"])
        seen.add(spec["id"])
    return data["specs"]


def run_pin(args, hub, say: Callable[[str], None]) -> int:
    specs = load_wanted(Path(args.wanted).read_text(encoding="utf-8"))
    if args.only:
        unknown = sorted(set(args.only) - {s["id"] for s in specs})
        if unknown:
            raise PinError("not in the wanted list: " + ", ".join(unknown))
        specs = [s for s in specs if s["id"] in args.only]
    picks = dict(p.split("=", 1) for p in args.pick)
    items: List[dict] = []
    dropped: List[str] = []
    try:
        for spec in specs:
            say("%s  (%s at %s)" % (spec["id"], spec["repo"], spec.get("revision", "main")))
            for pinned in pin_spec(spec, hub, picks):
                item = pinned.item
                say("  %-48s %12d bytes  sha256 %s...  [%s]" % (item["id"], item["size_bytes"], item["sha256"][:16], pinned.how))
                items.append(item)
            dropped.extend(spec.get("replaces", []))
    except NeedsChoice as choice:
        say("")
        say("Cannot choose by itself. The candidates for %s (%r):" % (choice.spec_id, choice.pattern))
        for entry in choice.candidates:
            say("  %-60s %12d bytes" % (entry.name, entry.size))
        say("Run again with  --pick %s=FILENAME  using one of those." % choice.spec_id)
        return 3
    if not items:
        raise PinError("nothing was pinned")
    Path(args.out).write_text(json.dumps({"schema": 1, "items": items, "drop": dropped}, indent=2) + "\n", encoding="utf-8")
    say("")
    say("Wrote %d entries to %s. Next: merge them into the registry with  make_pins.py merge %s" % (len(items), args.out, args.out))
    return 0


def run_list(args, hub, say: Callable[[str], None]) -> int:
    commit = hub.commit(args.repo, args.revision)
    say("%s at %s (%s)" % (args.repo, args.revision, commit))
    text = hub.tree(args.repo, commit, args.path)
    entries = parse_tree(text)
    for folder in folders(text):
        say("  %-70s %14s" % (folder + "/", "folder"))
    for entry in sorted(entries, key=lambda e: e.path):
        say("  %-70s %14d bytes  %s" % (entry.path, entry.size, "large file" if entry.lfs_sha256 else "small file"))
    if not entries and not folders(text):
        say("  (nothing directly in %s)" % (args.path or "the top"))
    return 0


def run_merge(args, say: Callable[[str], None]) -> int:
    pins = json.loads(Path(args.pins).read_text(encoding="utf-8"))
    if not isinstance(pins, dict) or pins.get("schema") != 1 or not isinstance(pins.get("items"), list):
        raise PinError("%s is not a file this wrote" % args.pins)
    registry_path = Path(args.registry)
    merged = merge_registry(registry_path.read_text(encoding="utf-8"), pins["items"], pins.get("drop", []))
    registry_path.write_text(merged, encoding="utf-8")
    say("Put %d entries into %s (removed: %s)." % (len(pins["items"]), registry_path, ", ".join(pins.get("drop", [])) or "none"))
    return 0


def main(argv: Optional[Sequence[str]] = None, hub=None, say: Callable[[str], None] = print) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    sub = parser.add_subparsers(dest="command", required=True)
    lst = sub.add_parser("list", help="look at what a folder of a repository holds")
    lst.add_argument("repo")
    lst.add_argument("path", nargs="?", default="")
    lst.add_argument("--revision", default="main")
    pin = sub.add_parser("pin", help="pin everything in the wanted list")
    pin.add_argument("--wanted", default=str(WANTED))
    pin.add_argument("--out", required=True)
    pin.add_argument("--only", nargs="*", default=[])
    pin.add_argument("--pick", nargs="*", default=[], metavar="ID=FILENAME")
    merge = sub.add_parser("merge", help="put pinned entries into the registry")
    merge.add_argument("pins")
    merge.add_argument("--registry", default=str(REGISTRY))
    args = parser.parse_args(argv)
    try:
        if args.command == "merge":
            return run_merge(args, say)
        hub = hub or Hub()
        return run_list(args, hub, say) if args.command == "list" else run_pin(args, hub, say)
    except PinError as error:
        say("Nothing was written. " + str(error))
        return 1


if __name__ == "__main__":
    sys.exit(main())
