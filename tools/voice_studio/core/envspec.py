# SPDX-License-Identifier: GPL-3.0-or-later
"""What a Python environment is made of (data/environments.json), and the rules a lock file must meet.

An environment is listed here or it is not built. It is made from a **lock file** that pins every package to an exact version with
checksums (pip's hash-checking mode, so what is installed is what was tested, whatever the package index serves), and, for the trainer,
from one pinned source archive in the download registry. Nothing is built from an entry whose lock has no checksum: it is listed and
sized for the disk estimate, and the lock is made on a real machine (plan task VS-0.2). Plan decision D11.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

from .registry import SLUG, Registry

SCHEMA = 1
DEFAULT_PATH = Path(__file__).resolve().parent.parent / "data" / "environments.json"
LOCKS_DIR = Path(__file__).resolve().parent.parent / "data" / "locks"
SHA256 = re.compile(r"^[0-9a-f]{64}$")
SAFE_LOCK_NAME = re.compile(r"^[a-z0-9][a-z0-9._-]{0,79}\.txt$")
SAFE_RELATIVE = re.compile(r"^[A-Za-z0-9._*/+-]{1,200}$")
DIST_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$")
MAX_PRELUDE_LINES = 20
MAX_LINE = 300


class EnvSpecError(Exception):
    pass


@dataclass(frozen=True)
class Probe:
    id: str
    code: str                       # Python statements run inside the finished environment; they pass if they raise nothing
    needs_gpu: bool = False         # skipped (and said so) on a computer with no usable graphics card: training is then simply off (D4)


@dataclass(frozen=True)
class SourcePatch:
    """A change to one file of the unpacked source. Never made without the person's yes; the original is kept first (see core/envbuild.py)."""
    id: str
    file: str                       # relative to the unpacked source
    old: str
    new: str


@dataclass(frozen=True)
class SourceUse:
    item_id: str                    # the registry entry holding the pinned archive
    install: bool                   # pip-install it (editable) after the lock
    dist: Optional[str]             # the distribution name that must exist afterwards
    native_build: Optional[str]     # a script in the source that builds the native part
    native_artifact: Optional[str]  # a pattern (relative to the source) that proves it was built


@dataclass(frozen=True)
class EnvSpec:
    id: str
    why_key: str
    python_min: Tuple[int, int]
    approx_size_bytes: int
    lock_filename: str
    lock_sha256: Optional[str]
    source: Optional[SourceUse]
    prelude: Tuple[str, ...]
    patches: Tuple[SourcePatch, ...]
    probes: Tuple[Probe, ...]
    python_max: Optional[Tuple[int, int]] = None    # the newest Python the lock has checksums for (and has been tried on); newer is refused plainly, not left to pip

    @property
    def lock_path(self) -> Path:
        return LOCKS_DIR / self.lock_filename

    def pin_problems(self, registry: Optional[Registry] = None) -> List[str]:
        """Why this cannot be built yet, as short codes (empty: it can). The source entry is looked up in `registry` when one is given."""
        problems = []
        if self.lock_sha256 is None:
            problems.append("lock_unpinned")
        if self.source is not None and registry is not None:
            try:
                if not registry.get(self.source.item_id).pinned:
                    problems.append("source_unpinned")
            except KeyError:
                problems.append("source_unknown")
        return problems


# ---------------------------------------------------------------- the lock file

_NAME = r"[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?"
_REQUIREMENT = re.compile(r"^(?P<name>%s)(?P<extras>\[[A-Za-z0-9._,-]+\])?==(?P<version>[A-Za-z0-9][A-Za-z0-9._+!-]*)(?P<marker>\s*;[^#]*)?$" % _NAME)
_HASH = re.compile(r"^--hash=sha256:(?P<digest>[0-9a-f]{64})$")


def normalise_name(name: str) -> str:
    """Package names compare equal ignoring case and runs of - _ . (PEP 503)."""
    return re.sub(r"[-_.]+", "-", name).lower()


@dataclass(frozen=True)
class Pin:
    name: str                       # normalised
    version: str
    hashes: Tuple[str, ...]
    marker: str = ""                # the part after ";" (for example python_version < "3.12"), or ""


def parse_lock(text: str) -> Tuple[List[Pin], List[str]]:
    """(the pins, the problems). A lock file holds only `name==version` lines, each with at least one `--hash=sha256:...`, and comments.
    Anything else (an address, an editable install, an index option, a version range, a line without a checksum) is a problem: pip is given
    its options by the builder, never by a file."""
    pins: List[Pin] = []
    problems: List[str] = []
    logical, current, start = [], "", 0
    for number, raw in enumerate(text.splitlines(), 1):
        if not current:
            start = number
        line = raw.rstrip()
        if line.endswith("\\"):
            current += line[:-1].rstrip() + " "
            continue
        logical.append((start, (current + line).strip()))
        current = ""
    if current:
        logical.append((start, current.strip()))
    seen = set()
    for number, line in logical:
        stripped = "" if line.startswith("#") else line.split(" #", 1)[0].strip()
        if not stripped:
            continue
        parts = stripped.split()
        head, hashes, bad = [], [], False
        for token in parts:
            match = _HASH.match(token)
            if match:
                hashes.append(match.group("digest"))
            elif token.startswith("--"):
                problems.append("line %d: option %s" % (number, token.split("=", 1)[0]))
                bad = True
            else:
                head.append(token)
        if bad:
            continue
        requirement = _REQUIREMENT.match(" ".join(head))
        if requirement is None:
            problems.append("line %d: not a pinned name==version" % number)
            continue
        if not hashes:
            problems.append("line %d: %s has no checksum" % (number, requirement.group("name")))
            continue
        key = (normalise_name(requirement.group("name")), requirement.group("marker") or "")
        if key in seen:
            problems.append("line %d: %s is listed twice" % (number, requirement.group("name")))
            continue
        seen.add(key)
        marker = (requirement.group("marker") or "").strip().lstrip(";").strip()
        pins.append(Pin(normalise_name(requirement.group("name")), requirement.group("version"), tuple(hashes), marker))
    if not pins and not problems:
        problems.append("the lock lists nothing")
    return pins, problems


def lock_digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# ---------------------------------------------------------------- reading the spec file

def _need(raw: dict, key: str, kind: type, where: str):
    value = raw.get(key)
    if not isinstance(value, kind) or isinstance(value, bool):
        raise EnvSpecError("%s: %r is missing or the wrong kind" % (where, key))
    return value


def _relative(value: object, where: str) -> str:
    if not isinstance(value, str) or not SAFE_RELATIVE.match(value) or value.startswith("/") or ".." in value.split("/"):
        raise EnvSpecError("%s: %r is not a safe relative path" % (where, value))
    return value


def _parse_source(raw: object, where: str) -> Optional[SourceUse]:
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise EnvSpecError("%s: source is not an object" % where)
    item_id = _need(raw, "item_id", str, where)
    if not SLUG.match(item_id):
        raise EnvSpecError("%s: bad source id" % where)
    dist = raw.get("dist")
    if dist is not None and (not isinstance(dist, str) or not DIST_NAME.match(dist)):
        raise EnvSpecError("%s: bad distribution name" % where)
    native, artifact = raw.get("native_build"), raw.get("native_artifact")
    if (native is None) != (artifact is None):
        raise EnvSpecError("%s: a native build needs an artifact that proves it, and the other way round" % where)
    return SourceUse(item_id, bool(raw.get("install", False)), dist,
                     _relative(native, where) if native is not None else None, _relative(artifact, where) if artifact is not None else None)


def parse_environments(text: str) -> Tuple[EnvSpec, ...]:
    try:
        data = json.loads(text)
    except ValueError as exc:
        raise EnvSpecError("not valid JSON: %s" % exc)
    if not isinstance(data, dict) or data.get("schema") != SCHEMA or not isinstance(data.get("environments"), list):
        raise EnvSpecError("not a list of environments this version understands")
    specs, seen = [], set()
    for raw in data["environments"]:
        if not isinstance(raw, dict):
            raise EnvSpecError("an entry is not an object")
        env_id = _need(raw, "id", str, "environment")
        if not SLUG.match(env_id) or env_id in seen:
            raise EnvSpecError("bad or repeated id %r" % env_id)
        seen.add(env_id)
        where = env_id
        why = _need(raw, "why_key", str, where)
        python_min = raw.get("python_min")
        if not (isinstance(python_min, list) and len(python_min) == 2 and all(isinstance(n, int) and not isinstance(n, bool) and 0 <= n < 100 for n in python_min)):
            raise EnvSpecError("%s: python_min must be [major, minor]" % where)
        python_max = raw.get("python_max")
        if python_max is not None:
            if not (isinstance(python_max, list) and len(python_max) == 2 and all(isinstance(n, int) and not isinstance(n, bool) and 0 <= n < 100 for n in python_max)):
                raise EnvSpecError("%s: python_max must be [major, minor]" % where)
            if (python_max[0], python_max[1]) < (python_min[0], python_min[1]):
                raise EnvSpecError("%s: python_max is older than python_min" % where)
        size = _need(raw, "approx_size_bytes", int, where)
        if not 0 < size <= 2**40:
            raise EnvSpecError("%s: approx_size_bytes out of range" % where)
        lock = _need(raw, "lock", dict, where)
        filename, digest = _need(lock, "filename", str, where), lock.get("sha256")
        if not SAFE_LOCK_NAME.match(filename):
            raise EnvSpecError("%s: unsafe lock file name" % where)
        if digest is not None and (not isinstance(digest, str) or not SHA256.match(digest)):
            raise EnvSpecError("%s: bad lock checksum" % where)
        prelude = raw.get("prelude", [])
        if not isinstance(prelude, list) or len(prelude) > MAX_PRELUDE_LINES or not all(isinstance(l, str) and 0 < len(l) <= MAX_LINE and "\n" not in l for l in prelude):
            raise EnvSpecError("%s: prelude must be a short list of one-line strings" % where)
        for line in prelude:
            try:
                compile(line, "<prelude>", "exec")
            except SyntaxError:
                raise EnvSpecError("%s: a prelude line is not valid Python: %r" % (where, line))
        patches = []
        for p in _need(raw, "patches", list, where):
            if not isinstance(p, dict):
                raise EnvSpecError("%s: a patch is not an object" % where)
            patch_id = _need(p, "id", str, where)
            if not SLUG.match(patch_id) or any(patch_id == q.id for q in patches):
                raise EnvSpecError("%s: bad or repeated patch id" % where)
            old, new = _need(p, "old", str, where), _need(p, "new", str, where)
            if not old or old == new:
                raise EnvSpecError("%s: patch %s changes nothing" % (where, patch_id))
            patches.append(SourcePatch(patch_id, _relative(p.get("file"), where), old, new))
        probes = []
        for p in _need(raw, "probes", list, where):
            if not isinstance(p, dict):
                raise EnvSpecError("%s: a probe is not an object" % where)
            probe_id = _need(p, "id", str, where)
            if not SLUG.match(probe_id) or any(probe_id == q.id for q in probes):
                raise EnvSpecError("%s: bad or repeated probe id" % where)
            code = _need(p, "code", str, where)
            try:
                compile(code, "<probe>", "exec")
            except SyntaxError:
                raise EnvSpecError("%s: probe %s is not valid Python" % (where, probe_id))
            probes.append(Probe(probe_id, code, bool(p.get("needs_gpu", False))))
        if not probes:
            raise EnvSpecError("%s: an environment with no self-test cannot be called ready" % where)
        source = _parse_source(raw.get("source"), where)
        if patches and source is None:
            raise EnvSpecError("%s: patches need a source" % where)
        specs.append(EnvSpec(env_id, why, (python_min[0], python_min[1]), size, filename, digest, source, tuple(prelude), tuple(patches), tuple(probes),
                         (python_max[0], python_max[1]) if python_max is not None else None))
    return tuple(specs)


def load_environments(path: Optional[Path] = None) -> Tuple[EnvSpec, ...]:
    path = Path(path) if path else DEFAULT_PATH
    try:
        return parse_environments(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise EnvSpecError("cannot read %s: %s" % (path.name, exc.strerror or exc))
