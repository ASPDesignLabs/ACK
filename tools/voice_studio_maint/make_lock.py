# SPDX-License-Identifier: GPL-3.0-or-later
"""Make a hash-checked lock file for one of ACK Voice Studio's Python environments, from a list of exact versions.

For maintainers only. It is NOT part of the app (tools/voice_studio never imports it, and the app never runs it): it reads the package
site's public listing of each pinned release, so it needs a network, and the only person it is for is whoever refreshes a lock.

    python3 tools/voice_studio_maint/make_lock.py --versions freeze.txt --python 3.10 3.11 3.12 \
        --note "Made 2026-10-10 from the list the developer tested." --out tools/voice_studio/data/locks/training.lock.txt

The input is `pip freeze` output (or any file of `name==version` lines). The output lists every package at that version with the
checksum of every wheel that could be installed on Linux x86_64 under one of the Pythons asked for, plus the pure-Python wheels. The
builder (core/envbuild.py) installs with `--require-hashes --only-binary=:all: --no-deps`, so a package with no wheel for a Python asked for
is an error here, said plainly, and never a quiet change to those flags (plan task VS-0.2). Nothing is written until every package is covered.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
import urllib.request
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Tuple

PACKAGE_SITE = "https://pypi.org/pypi/%s/%s/json"
LINE = re.compile(r"^(?P<name>[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?)==(?P<version>[A-Za-z0-9][A-Za-z0-9._+!-]*)$")
Minor = Tuple[int, int]


class LockError(Exception):
    pass


def normalise(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def parse_versions(text: str) -> Tuple[List[Tuple[str, str]], List[str]]:
    """(the name==version pairs, the lines skipped). Editable installs (`-e ...`) are skipped and reported: they are installed from the
    pinned source archive, not from the package site. Any other line that is not `name==version` is an error."""
    pairs: List[Tuple[str, str]] = []
    skipped: List[str] = []
    seen = set()
    for number, raw in enumerate(text.splitlines(), 1):
        line = raw.split(" #", 1)[0].strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("-e ") or line.startswith("--editable"):
            skipped.append("line %d: %s" % (number, line[:80]))
            continue
        match = LINE.match(line)
        if match is None:
            raise LockError("line %d is not a plain name==version: %r" % (number, line[:80]))
        key = normalise(match.group("name"))
        if key in seen:
            raise LockError("line %d: %s is listed twice" % (number, match.group("name")))
        seen.add(key)
        pairs.append((match.group("name"), match.group("version")))
    if not pairs:
        raise LockError("the list holds no name==version lines")
    return pairs, skipped


def parse_minor(text: str) -> Minor:
    match = re.fullmatch(r"3\.(\d{1,2})", text)
    if match is None:
        raise LockError("%r is not a Python 3 version like 3.12" % text)
    return (3, int(match.group(1)))


def _platform_ok(platform: str) -> bool:
    for part in platform.split("."):
        if part == "any" or (part.startswith("manylinux") and part.endswith("_x86_64")):
            return True
    return False


def wheel_covers(filename: str, minor: Minor) -> bool:
    """Whether this wheel installs on Linux x86_64 (glibc) under CPython 3.<minor>. PyPy, musl and other processors are never counted, and
    neither are free-threaded builds: their ABI tags (cp313t, abi3t) are never equal to the ordinary one, so nothing here lets them through."""
    if not filename.endswith(".whl"):
        return False
    parts = filename[:-4].split("-")
    if len(parts) < 5:
        return False
    python_tags, abi_tags, platform = parts[-3], parts[-2], parts[-1]
    if not _platform_ok(platform):
        return False
    for py in python_tags.split("."):
        for abi in abi_tags.split("."):
            cp = re.fullmatch(r"cp3(\d+)", py)
            if cp:
                n = int(cp.group(1))
                if (abi == "abi3" and n <= minor[1]) or (abi in ("none", py) and n == minor[1]):
                    return True
                continue
            generic = re.fullmatch(r"py3(\d*)", py)
            if generic and abi == "none" and int(generic.group(1) or 0) <= minor[1]:       # py3 is from 3.0 on; py311 from 3.11
                return True
    return False


def usable_files(release: dict, pythons: Sequence[Minor]) -> List[dict]:
    """The release's wheel files that install under at least one of the Pythons, in a fixed order."""
    files = [f for f in release.get("urls", []) if isinstance(f, dict) and not f.get("yanked") and isinstance(f.get("filename"), str)]
    chosen = [f for f in files if any(wheel_covers(f["filename"], m) for m in pythons)]
    return sorted(chosen, key=lambda f: f["filename"])


def uncovered(release: dict, pythons: Sequence[Minor]) -> List[Minor]:
    files = [f["filename"] for f in release.get("urls", []) if isinstance(f, dict) and not f.get("yanked") and isinstance(f.get("filename"), str)]
    return [m for m in pythons if not any(wheel_covers(name, m) for name in files)]


def _digest(file: dict, where: str) -> str:
    value = (file.get("digests") or {}).get("sha256")
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise LockError("%s: the listing gives no usable sha256 for %s" % (where, file.get("filename")))
    return value


def render_lock(entries: Sequence[Tuple[str, str, Sequence[str]]], notes: Sequence[str]) -> str:
    out = []
    for note in notes:
        out.append(("# " + note).rstrip())
    out.append("")
    for name, version, hashes in sorted(entries, key=lambda e: normalise(e[0])):
        lines = ["%s==%s" % (name, version)] + ["    --hash=sha256:%s" % h for h in sorted(set(hashes))]
        out.append(" \\\n".join(lines))
    return "\n".join(out) + "\n"


def build_lock(pairs: Sequence[Tuple[str, str]], fetch: Callable[[str, str], dict], pythons: Sequence[Minor], notes: Sequence[str] = ()) -> Tuple[str, Dict[str, int]]:
    """(the lock text, the number of checksums per package). Raises one LockError naming every package that has no wheel for a Python asked for."""
    if not pythons:
        raise LockError("no Python version asked for")
    entries, missing, counts = [], [], {}
    for name, version in pairs:
        release = fetch(name, version)
        gaps = uncovered(release, pythons)
        if gaps:
            missing.append("%s %s: no Linux x86_64 wheel for Python %s" % (name, version, ", ".join("%d.%d" % m for m in gaps)))
            continue
        hashes = [_digest(f, "%s %s" % (name, version)) for f in usable_files(release, pythons)]
        counts[name] = len(set(hashes))
        entries.append((name, version, hashes))
    if missing:
        raise LockError("these cannot be installed from wheels alone, which is a decision for the maintainer, not something to work around:\n  " + "\n  ".join(missing))
    return render_lock(entries, notes), counts


def fetch_from_package_site(name: str, version: str, tries: int = 4, opener: Optional[Callable] = None, sleep: Callable[[float], None] = time.sleep) -> dict:
    url = PACKAGE_SITE % (normalise(name), version)
    last = "no answer"
    for attempt in range(tries):
        try:
            with (opener or urllib.request.urlopen)(url, timeout=30) as response:
                data = json.load(response)
            if not isinstance(data, dict) or not isinstance(data.get("urls"), list):
                raise LockError("%s %s: the listing is not in the shape expected" % (name, version))
            return data
        except LockError:
            raise
        except Exception as exc:                    # a dropped connection, a timeout, a 5xx: wait and try again; a 404 is the same answer every time
            last = "%s" % exc
            if "404" in last:
                break
            sleep(1.5 * (attempt + 1))
    raise LockError("%s %s: could not read its listing (%s)" % (name, version, last))


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Make a hash-checked lock file from a list of exact versions (maintainers only; needs a network).")
    parser.add_argument("--versions", required=True, help="a file of name==version lines (pip freeze output is fine)")
    parser.add_argument("--add", action="append", default=[], metavar="NAME==VERSION", help="a package pip freeze hides (setuptools, wheel); may be repeated")
    parser.add_argument("--python", nargs="+", required=True, metavar="3.X", help="the Python versions the lock must install under")
    parser.add_argument("--note", action="append", default=[], help="a line for the lock file's header (a comment); may be repeated")
    parser.add_argument("--out", required=True, help="where to write the lock; an existing file is kept as FILE.before-<n> first")
    args = parser.parse_args(argv)
    try:
        text = Path(args.versions).read_text(encoding="utf-8")
        pairs, skipped = parse_versions(text + "\n" + "\n".join(args.add))
        pythons = [parse_minor(p) for p in args.python]
        notes = list(args.note) + ["Python versions covered: %s. Linux x86_64 wheels only; Python 3.13 and newer are not covered." % ", ".join("%d.%d" % m for m in pythons),
                                   "Input list sha256: %s" % hashlib.sha256((text + "\n" + "\n".join(args.add)).encode("utf-8")).hexdigest()]
        lock, counts = build_lock(pairs, fetch_from_package_site, pythons, notes)
    except (LockError, OSError) as exc:
        print("NOT WRITTEN: %s" % exc, file=sys.stderr)
        return 2
    out = Path(args.out)
    if out.exists():
        n = 1
        while out.with_name(out.name + ".before-%d" % n).exists():
            n += 1
        out.with_name(out.name + ".before-%d" % n).write_bytes(out.read_bytes())
    out.write_text(lock, encoding="utf-8")
    for line in skipped:
        print("skipped (installed from the pinned source instead): " + line)
    print("wrote %s: %d packages, %d checksums" % (out, len(counts), sum(counts.values())))
    print("lock sha256: %s" % hashlib.sha256(lock.encode("utf-8")).hexdigest())
    return 0


if __name__ == "__main__":
    sys.exit(main())
