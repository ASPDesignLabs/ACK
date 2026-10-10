# SPDX-License-Identifier: GPL-3.0-or-later
"""The one module allowed to use the network.

Two doors, both closed unless the person has agreed to the download by name (a `ConsentRecord`, core/consent.py):

* `fetch(item, ...)` downloads one registry file (core/registry.py), checks it byte for byte against the size and SHA-256 that were
  shown, and only then puts it where it belongs. It can resume, can be cancelled, and refuses to start without room for the file.
* `run_networked(consent, argv, item_ids, ...)` runs a command that reaches the network (pip, apt, git) after the same check.

Nothing else in this package imports a network library or starts a network program: tests/test_vs_network_rules.py reads every file to
prove it, and `System.run` refuses them at run time. Nothing a person recorded is ever sent: a request names the file and, as any web
request does, carries this computer's address and the program asking.
"""
from __future__ import annotations

import errno
import hashlib
import os
import shutil
import subprocess
import urllib.error
import urllib.request
from contextlib import closing
from pathlib import Path
from typing import Callable, Dict, Iterable, Optional, Sequence, Tuple
from urllib.parse import urlparse

from .consent import ConsentRecord
from .registry import SAFE_FILENAME, Item
from .system import CommandResult

CHUNK = 1 << 20
ROOM_MARGIN_BYTES = 1 << 30            # PROVISIONAL (plan P11): spare room that must remain after the download
USER_AGENT = "ACK-Voice-Studio"


class FetchError(Exception):
    """`code` is a short word the screens turn into a plain sentence: consent, not_pinned, unsafe_name, room, disk, http, size, checksum, cancelled."""

    def __init__(self, code: str, detail: str = ""):
        super().__init__(code + (": " + detail if detail else ""))
        self.code = code
        self.detail = detail


# ---------------------------------------------------------------- opening a connection

class _HttpsOnlyRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):          # a redirect (to a CDN, say) must stay on https
        if urlparse(newurl).scheme.lower() != "https":
            raise urllib.error.HTTPError(newurl, code, "redirect to a non-https address refused", headers, fp)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def default_opener(url: str, headers: Dict[str, str], timeout: float = 30.0):
    request = urllib.request.Request(url, headers=headers)
    return urllib.request.build_opener(_HttpsOnlyRedirects()).open(request, timeout=timeout)


# ---------------------------------------------------------------- helpers

def _disk_free(path: Path) -> Optional[int]:
    try:
        return shutil.disk_usage(str(path)).free
    except OSError:
        return None


def _sha256_of(path: Path) -> Tuple[str, int]:
    digest, size = hashlib.sha256(), 0
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(CHUNK), b""):
            digest.update(block)
            size += len(block)
    return digest.hexdigest(), size


def _matches(path: Path, item: Item) -> bool:
    digest, size = _sha256_of(path)
    return size == item.size_bytes and digest == item.sha256


def _target(dest_dir: Path, filename: str) -> Path:
    if not SAFE_FILENAME.match(filename) or ".." in filename:
        raise FetchError("unsafe_name", filename)
    target = (dest_dir / filename)
    if target.resolve().parent != dest_dir.resolve():
        raise FetchError("unsafe_name", filename)
    return target


def _content_range_start(headers) -> Optional[int]:
    value = headers.get("Content-Range") if headers is not None else None
    if not value or not value.startswith("bytes "):
        return None
    try:
        return int(value[6:].split("-", 1)[0])
    except ValueError:
        return None


# ---------------------------------------------------------------- door one: a registry file

def fetch(item: Item, dest_dir: Path, consent: Optional[ConsentRecord], *, opener: Callable = default_opener,
          progress: Optional[Callable[[int, int], None]] = None, cancelled: Optional[Callable[[], bool]] = None,
          room_margin: int = ROOM_MARGIN_BYTES, disk_free: Callable[[Path], Optional[int]] = _disk_free) -> Path:
    """Download `item` into `dest_dir` and return the finished file. Nothing is requested unless every check before it passes."""
    problems = item.pin_problems()
    if problems:
        raise FetchError("not_pinned", ",".join(problems))          # nothing to agree to yet: the entry has no checked address
    if consent is None or not consent.covers(item):
        raise FetchError("consent", item.id)                        # no agreement for this exact file
    assert item.url and item.filename and item.size_bytes and item.sha256
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    target = _target(dest_dir, item.filename)

    if target.exists() and _matches(target, item):                  # already here and right: no network at all
        return target
    part = target.with_name(target.name + ".part")
    have = part.stat().st_size if part.exists() else 0
    if have > item.size_bytes:
        part.unlink()
        have = 0
    if have == item.size_bytes:                                     # an earlier run got everything but stopped before the last step
        if _matches(part, item):
            os.chmod(part, 0o600)
            os.replace(part, target)
            return target
        part.unlink()
        have = 0

    free = disk_free(dest_dir)
    if free is not None and free < (item.size_bytes - have) + room_margin:
        raise FetchError("room", "%d bytes needed" % ((item.size_bytes - have) + room_margin))

    for attempt in (1, 2):
        headers = {"User-Agent": USER_AGENT}
        if have:
            headers["Range"] = "bytes=%d-" % have
        try:
            response = opener(item.url, headers)
        except urllib.error.HTTPError as exc:
            if exc.code == 416 and have and attempt == 1:           # the server cannot give that range: start again from the beginning
                part.unlink(missing_ok=True)
                have = 0
                continue
            raise FetchError("http", str(exc.code))
        except (urllib.error.URLError, OSError) as exc:
            raise FetchError("http", type(exc).__name__)
        with closing(response):
            status = getattr(response, "status", 200)
            if have and status == 206 and _content_range_start(getattr(response, "headers", None)) == have:
                append = True
            elif status == 200:                                      # a whole file, whether or not a range was asked for
                append, have = False, 0
            else:
                raise FetchError("http", str(status))
            digest = hashlib.sha256()
            if append:
                with open(part, "rb") as old:                        # the bytes already kept are part of the checksum too
                    for block in iter(lambda: old.read(CHUNK), b""):
                        digest.update(block)
            done = have
            try:
                fd = os.open(part, os.O_WRONLY | os.O_CREAT | (os.O_APPEND if append else os.O_TRUNC), 0o600)
                with os.fdopen(fd, "ab" if append else "wb") as out:
                    while True:
                        if cancelled and cancelled():
                            raise FetchError("cancelled")            # the .part file stays, so a later try resumes
                        block = response.read(CHUNK)
                        if not block:
                            break
                        done += len(block)
                        if done > item.size_bytes:
                            raise FetchError("size", "more than %d bytes" % item.size_bytes)
                        out.write(block)
                        digest.update(block)
                        if progress:
                            progress(done, item.size_bytes)
                    out.flush()
                    os.fsync(out.fileno())
            except OSError as exc:
                raise FetchError("disk" if exc.errno in (errno.ENOSPC, errno.EDQUOT) else "http", exc.strerror or type(exc).__name__)
        break

    if done != item.size_bytes:
        raise FetchError("size", "got %d of %d bytes" % (done, item.size_bytes))      # the .part file stays so the rest can be fetched
    if digest.hexdigest() != item.sha256:
        part.unlink(missing_ok=True)                                 # wrong content is never kept, and never resumed
        raise FetchError("checksum")
    os.chmod(part, 0o600)
    os.replace(part, target)
    return target


# ---------------------------------------------------------------- door two: a command that reaches the network

def run_networked(consent: Optional[ConsentRecord], argv: Sequence[str], item_ids: Iterable[str], *, cwd: Optional[Path] = None,
                  on_line: Optional[Callable[[str], None]] = None, runner: Optional[Callable[[Sequence[str]], CommandResult]] = None) -> CommandResult:
    """Run pip, apt or git for the named things, but only if the person agreed to each by name. Output is passed on line by line."""
    ids = list(item_ids)
    if consent is None or not ids or not all(consent.covers_id(i) for i in ids):
        raise FetchError("consent", ",".join(ids))
    if runner is not None:
        result = runner(argv)
        for line in result.stdout.splitlines():
            if on_line:
                on_line(line)
        return result
    env = dict(os.environ, LC_ALL="C", LANG="C")
    try:
        proc = subprocess.Popen(list(argv), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, text=True, errors="replace",
                                cwd=str(cwd) if cwd else None, env=env)
    except OSError as exc:
        raise FetchError("http", exc.strerror or type(exc).__name__)
    lines = []
    assert proc.stdout is not None
    for line in proc.stdout:
        lines.append(line)
        if on_line:
            on_line(line.rstrip("\n"))
    return CommandResult(proc.wait(), "".join(lines), "")
