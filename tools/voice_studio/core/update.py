# SPDX-License-Identifier: GPL-3.0-or-later
"""Updating the tool (plan task VS-6.2, decisions D11, P4 and P21): look at the releases of ACK, fetch one into a new folder beside this copy, check it, and say what is different.

Nothing here runs by itself and nothing here replaces the copy that is running. Looking at the releases is one `git ls-remote --tags` and fetching one is one `git clone --depth 1`, both
started through the download module (core/fetch.py `run_networked`, the only door to the network) and only after the person said yes to the very command that was shown. The new copy goes in
a **new folder** that must not exist yet, so this copy, and everything in it that the person changed, is never touched; the person starts the new one by hand (and the guided setup
then builds only the programs whose list changed, beside the old ones, and checks each before it counts). After the fetch the copy is checked: the commit it holds is the commit the
release was listed with, and it is a copy of this tool. If either is not true, the folder this program made is removed again and nothing else is.

What a release is, is its git tag. Tags that look like a number with dots (`v1.2`, `1.2.3`) are ordered; any other tag is listed and cannot be called newer. Whether this copy is at a release
is read from the files of its `.git` folder (no program is started for that): a copy that is not at a release cannot be compared, and is told so.

Plain Python with no words and no network library; the words are in the text catalog under `update.*`.
"""
from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Tuple

from . import fetch, profiles
from .consent import ConsentRecord
from .system import CommandResult

ERROR_CODES = ("no_git", "unreachable", "unknown_release", "bad_name", "folder_exists", "no_room", "differs", "not_a_release")      # each has words in the text catalog
LIST_ID, GET_ID = "update:list", "update:get"                  # what the person agrees to, by name, for the download module
RELEASE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}\Z")
HEX_COMMIT = re.compile(r"^[0-9a-f]{40}\Z")
VERSION_LINE = re.compile(r'^__version__\s*=\s*"([^"\n]{1,40})"\s*$', re.M)
ROOM_BYTES = 500 * 10**6                                      # PROVISIONAL: a shallow copy of the whole project is usually under 100 MB; this much must be free beside this copy
PACKAGE_FILE = "tools/voice_studio/__init__.py"
COMPARED_ROOTS = ("tools/voice_studio", "tools/freeform_studio")
DOC_PREFIXES = ("docs/VOICE_STUDIO", "docs/ACK_Voice_Studio")
CATEGORIES = ("programs", "downloads", "words", "recordings", "code", "docs")      # each has words in the text catalog under update.part.<id>
MAX_FILE_BYTES = 64 * 2**20                                   # a file bigger than this in a release is not hashed (and counts as changed when its size differs)

Networked = Callable[..., CommandResult]


class UpdateError(Exception):
    """`code` is one of ERROR_CODES; `detail` is a short fact for Show details."""

    def __init__(self, code: str, detail: str = ""):
        super().__init__(code + (": " + detail if detail else ""))
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class Release:
    name: str
    commit: str


# ---------------------------------------------------------------- the releases

def parse_releases(text: str) -> Tuple[Release, ...]:
    """The tags `git ls-remote --tags` listed: a name and the commit it points at (for an annotated tag, the commit behind it). A name that is not safe to pass on or to make a folder from is left out."""
    seen: Dict[str, str] = {}
    peeled: Dict[str, str] = {}
    for line in text.splitlines():
        parts = line.split("\t")
        if len(parts) != 2 or not HEX_COMMIT.match(parts[0]) or not parts[1].startswith("refs/tags/"):
            continue
        name = parts[1][len("refs/tags/"):]
        if name.endswith("^{}"):
            peeled[name[:-3]] = parts[0]
        else:
            seen[name] = parts[0]
    found = {name: peeled.get(name, commit) for name, commit in seen.items() if RELEASE_NAME.match(name)}
    return tuple(Release(name, found[name]) for name in found)


def version_key(name: str) -> Optional[Tuple[int, ...]]:
    """`v1.2.3` and `1.2.3` as (1, 2, 3); a name that is not a number with dots has no order."""
    text = name[1:] if name[:1] in ("v", "V") else name
    parts = text.split(".")
    if not all(part.isascii() and part.isdigit() and len(part) <= 9 for part in parts):
        return None
    return tuple(int(part) for part in parts)


def sort_releases(releases: Iterable[Release]) -> Tuple[Release, ...]:
    """Newest first for the numbered ones, then the others by name."""
    items = tuple(releases)
    numbered = sorted((r for r in items if version_key(r.name) is not None), key=lambda r: (version_key(r.name), r.name), reverse=True)
    others = sorted((r for r in items if version_key(r.name) is None), key=lambda r: r.name)
    return tuple(numbered) + tuple(others)


def head_commit(repo: str) -> Optional[str]:
    """The commit a copy is at, read from its `.git` files (HEAD, then the branch's file or packed-refs). None when it is not a plain git copy or cannot be read."""
    git = repo + "/.git"
    try:
        with open(git + "/HEAD", encoding="utf-8") as handle:
            head = handle.read().strip()
        if HEX_COMMIT.match(head):
            return head
        if not head.startswith("ref: refs/") or ".." in head:
            return None
        ref = head[len("ref: "):]
        try:
            with open(git + "/" + ref, encoding="utf-8") as handle:
                value = handle.read().strip()
            return value if HEX_COMMIT.match(value) else None
        except FileNotFoundError:
            pass
        with open(git + "/packed-refs", encoding="utf-8") as handle:
            for line in handle:
                parts = line.split()
                if len(parts) == 2 and parts[1] == ref and HEX_COMMIT.match(parts[0]):
                    return parts[0]
    except (OSError, UnicodeDecodeError):
        return None
    return None


def release_at(releases: Sequence[Release], commit: Optional[str]) -> Optional[Release]:
    """The release this commit is, if it is one (when two tags name it, the newest)."""
    return next((r for r in sort_releases(releases) if r.commit == commit), None)


def newer_than(releases: Sequence[Release], current: Optional[Release]) -> Tuple[Release, ...]:
    """The releases that are newer than `current`: only the numbered ones can be said to be, and only when `current` is a numbered release itself."""
    key = version_key(current.name) if current else None
    if key is None:
        return ()
    return tuple(r for r in sort_releases(releases) if (version_key(r.name) or ()) > key)


def read_version(root: str) -> Optional[str]:
    try:
        with open(root.rstrip("/") + "/" + PACKAGE_FILE, encoding="utf-8") as handle:
            found = VERSION_LINE.search(handle.read(20000))
    except (OSError, UnicodeDecodeError):
        return None
    return found.group(1) if found else None


# ---------------------------------------------------------------- asking github, through the download module

def _tail(result: CommandResult) -> str:
    lines = [line.strip() for line in (result.stdout or "").splitlines() if line.strip()]
    return lines[-1][:200] if lines else "exit %d" % result.returncode


def list_releases(networked: Networked, consent: Optional[ConsentRecord], url: str) -> Tuple[Release, ...]:
    """One `git ls-remote --tags`. Raises UpdateError('unreachable') when it cannot be done (no connection, a refused request, git missing)."""
    try:
        result = networked(consent, ["git", "ls-remote", "--tags", url], [LIST_ID])
    except fetch.FetchError as exc:
        raise UpdateError("unreachable", exc.detail or exc.code)
    if result.returncode != 0:
        raise UpdateError("unreachable", _tail(result))
    return parse_releases(result.stdout or "")


def folder_name(code_folder: str, release: str) -> str:
    """Where a release goes by default: beside this copy, with the release's name on the end."""
    safe = re.sub(r"[^A-Za-z0-9._-]", "-", release)
    return code_folder.rstrip("/") + "-" + safe


def check_destination(dest: str, free: Optional[int]) -> None:
    """Raises UpdateError('folder_exists') when anything is at the path (a link too), and UpdateError('no_room') when it is known that ROOM_BYTES are not free."""
    if os.path.lexists(dest):
        raise UpdateError("folder_exists", dest)
    if free is not None and free < ROOM_BYTES:
        raise UpdateError("no_room", str(free))


@dataclass(frozen=True)
class Fetched:
    release: Release
    folder: str
    version: Optional[str]


def _remove_made(dest: str, remove_tree: Callable[[str, List[Tuple[str, str]]], None]) -> None:
    """Remove what the clone made at `dest` (a link there is unlinked, never followed; a path with nothing at it is not an error). `get_release` has checked that nothing was there before."""
    remove_tree(dest, [])


def get_release(networked: Networked, consent: Optional[ConsentRecord], url: str, release: Release, dest: str,
                remove_tree: Callable[[str, List[Tuple[str, str]]], None] = profiles.remove_tree) -> Fetched:
    """One `git clone --depth 1 --branch NAME URL DEST`, then the checks: the commit held is the commit the release was listed with, and the copy is a copy of this tool. `dest` must not exist
    (check_destination). A copy that fails to be made or checked is removed again, and only that folder. Raises UpdateError('bad_name', 'differs', 'not_a_release' or 'unreachable')."""
    if not RELEASE_NAME.match(release.name):
        raise UpdateError("bad_name", release.name[:64])
    check_destination(dest, None)                               # nothing may be there now: what is removed after a failure must be only what the clone made
    try:
        result = networked(consent, ["git", "clone", "--depth", "1", "--branch", release.name, url, dest], [GET_ID])
    except fetch.FetchError as exc:
        _remove_made(dest, remove_tree)
        raise UpdateError("unreachable", exc.detail or exc.code)
    except KeyboardInterrupt:                                   # Ctrl+C in the middle of the download: the half-made folder is this program's own and goes
        _remove_made(dest, remove_tree)
        raise
    if result.returncode != 0:
        _remove_made(dest, remove_tree)
        raise UpdateError("unreachable", _tail(result))
    if head_commit(dest) != release.commit:
        _remove_made(dest, remove_tree)
        raise UpdateError("differs", release.name)
    if not os.path.isfile(dest + "/" + PACKAGE_FILE):
        _remove_made(dest, remove_tree)
        raise UpdateError("not_a_release", release.name)
    return Fetched(release, dest, read_version(dest))


# ---------------------------------------------------------------- what is different

@dataclass(frozen=True)
class Changes:
    changed: Dict[str, Tuple[str, ...]]
    added: Dict[str, Tuple[str, ...]]
    removed: Dict[str, Tuple[str, ...]]

    @property
    def any(self) -> bool:
        return any(self.changed.values()) or any(self.added.values()) or any(self.removed.values())


def category_of(rel: str) -> str:
    if rel.startswith("tools/voice_studio/data/locks/") or rel.startswith("tools/voice_studio/data/native/") or rel == "tools/voice_studio/data/environments.json":
        return "programs"
    if rel == "tools/voice_studio/data/sources.json":
        return "downloads"
    if rel.startswith("tools/voice_studio/data/text/"):
        return "words"
    if rel.startswith("tools/freeform_studio/"):
        return "recordings"
    if rel.startswith("docs/"):                                   # _files has already left out the guides that are not this tool's
        return "docs"
    return "code"


def _digest(path: str) -> str:
    try:
        size = os.path.getsize(path)
        if size > MAX_FILE_BYTES:
            return "size:%d" % size
        digest = hashlib.sha256()
        with open(path, "rb") as handle:
            for block in iter(lambda: handle.read(1 << 20), b""):
                digest.update(block)
        return digest.hexdigest()
    except OSError:
        return "unreadable"


def _files(root: str) -> Dict[str, str]:
    """Every plain file the comparison looks at, by path under the copy, with a digest. Links are not followed and not listed."""
    found: Dict[str, str] = {}
    base = root.rstrip("/")
    scopes = [base + "/" + r for r in COMPARED_ROOTS]
    docs = base + "/docs"
    for top in scopes + [docs]:
        for folder, names, files in os.walk(top, followlinks=False):
            names[:] = [n for n in names if n != "__pycache__"]
            for name in files:
                full = os.path.join(folder, name)
                rel = os.path.relpath(full, base)
                if os.path.islink(full) or name.endswith(".pyc") or (top == docs and not rel.startswith(DOC_PREFIXES)):
                    continue
                found[rel] = _digest(full)
    return found


def compare(old_root: str, new_root: str) -> Changes:
    """What differs between two copies, by area. Reads files only."""
    old, new = _files(old_root), _files(new_root)
    changed = {c: tuple(sorted(r for r in new if r in old and old[r] != new[r] and category_of(r) == c)) for c in CATEGORIES}
    added = {c: tuple(sorted(r for r in new if r not in old and category_of(r) == c)) for c in CATEGORIES}
    removed = {c: tuple(sorted(r for r in old if r not in new and category_of(r) == c)) for c in CATEGORIES}
    return Changes(changed, added, removed)
