# SPDX-License-Identifier: GPL-3.0-or-later
"""A project is one person's voice: their recordings, rounds, exports and a note about who agreed to what (plan decisions D9, D21, D13).

`project.json` is versioned and tolerant: fields a newer version added are kept when this version saves (never silently dropped), and a
missing field means "no change". A damaged file is reported and left exactly as it is; saving keeps the version before it as
`project.json.previous`. The consent note is required to continue for someone else's voice (D21); it verifies nothing, it starts the
conversation, and "how it was given" includes spoken, through a guardian and using AAC.
"""
from __future__ import annotations

import json
import os
import re
import tempfile
import unicodedata
from dataclasses import astuple, dataclass, field, replace
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from .paths import ProjectPaths
from .scratch import PROJECT_ID

SCHEMA = 1
OWN, SOMEONE_ELSE = "own", "someone_else"
HOW_GIVEN = ("spoken", "signed", "through_guardian", "using_aac", "other")
SCRATCH_DEFAULT, SCRATCH_CUSTOM = "default", "custom"
MAX_NAME = 80
MAX_NOTE = 500
MIN_HOURS, MAX_HOURS = 0.5, 100.0
ERROR_CODES = ("damaged", "newer", "exists", "bad_name", "consent", "bad_value", "unreadable")        # each has words in the text catalog
CONSENT_PROBLEM_CODES = ("given_by", "what_to", "when", "withdraw", "how_given", "how_given_other")


class ProjectError(Exception):
    """`code` is a short word the screens turn into a plain sentence: damaged, newer, exists, bad_name, consent, bad_value, unreadable."""

    def __init__(self, code: str, detail: str = ""):
        super().__init__(code + (": " + detail if detail else ""))
        self.code = code
        self.detail = detail


# ---------------------------------------------------------------- the model

@dataclass(frozen=True)
class Consent:
    given_by: str = ""              # who agreed
    what_to: str = ""               # what they agreed to
    when: str = ""                  # when, in their words or a date
    withdraw: str = ""              # how it can be withdrawn
    how_given: str = ""             # one of HOW_GIVEN
    how_given_other: str = ""       # in words, when how_given is "other"


@dataclass(frozen=True)
class Scratch:
    mode: str = SCRATCH_DEFAULT
    place: Optional[str] = None     # the chosen place when mode is custom (core/scratch.py)


@dataclass(frozen=True)
class Acknowledgment:
    voice: str
    at: str
    revision: str


@dataclass(frozen=True)
class Project:
    id: str
    name: str
    whose_voice: str
    created: str
    planned_hours: float = 1.0
    starting_voice: Optional[str] = None
    consent: Consent = field(default_factory=Consent)
    scratch: Scratch = field(default_factory=Scratch)
    acknowledgments: Tuple[Acknowledgment, ...] = ()
    extra: Dict[str, Any] = field(default_factory=dict)       # fields this version does not know, kept so saving never loses them


KNOWN_FIELDS = {"schema", "id", "name", "whose_voice", "created", "planned_hours", "starting_voice", "consent", "scratch", "acknowledgments"}


# ---------------------------------------------------------------- text the person typed

def clean_text(value: Any, limit: int) -> str:
    """Line breaks and runs of white space become one space (U+0085 and the Unicode line separators included), control characters go, the ends
    are trimmed and the text is cut at `limit`. Format characters stay: a zero-width joiner is part of the writing in Hindi, Persian and emoji."""
    text = " ".join(str(value if value is not None else "").split())
    text = "".join(ch for ch in text if unicodedata.category(ch) not in ("Cc", "Cs"))
    return text[:limit].strip()


def slugify(name: str, taken: Iterable[str] = ()) -> str:
    """A safe folder name from a person's name: lower-case letters and digits with single hyphens. Names with no Latin letters become "person"."""
    ascii_text = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii").lower()
    base = re.sub(r"[^a-z0-9]+", "-", ascii_text).strip("-")[:40].strip("-") or "person"
    used = set(taken)
    candidate, n = base, 1
    while candidate in used:
        n += 1
        candidate = "%s-%d" % (base, n)
    return candidate


# ---------------------------------------------------------------- rules

def consent_problems(project: Project) -> Tuple[str, ...]:
    """What is missing from the note. Empty for the person's own voice (the note is optional there) and once everything is filled in."""
    if project.whose_voice != SOMEONE_ELSE:
        return ()
    c = project.consent
    problems = [code for code, value in (("given_by", c.given_by), ("what_to", c.what_to), ("when", c.when), ("withdraw", c.withdraw)) if not value.strip()]
    if c.how_given not in HOW_GIVEN:
        problems.append("how_given")
    elif c.how_given == "other" and not c.how_given_other.strip():
        problems.append("how_given_other")
    return tuple(problems)


def may_record(project: Project) -> bool:
    return not consent_problems(project)


def validate(project: Project) -> None:
    if not PROJECT_ID.match(project.id):
        raise ProjectError("bad_value", "id")
    if not project.name or len(project.name) > MAX_NAME:
        raise ProjectError("bad_name")
    if project.whose_voice not in (OWN, SOMEONE_ELSE):
        raise ProjectError("bad_value", "whose_voice")
    if not (MIN_HOURS <= project.planned_hours <= MAX_HOURS):
        raise ProjectError("bad_value", "planned_hours")
    if project.scratch.mode not in (SCRATCH_DEFAULT, SCRATCH_CUSTOM) or (project.scratch.mode == SCRATCH_CUSTOM) != bool(project.scratch.place):
        raise ProjectError("bad_value", "scratch")
    if project.consent.how_given and project.consent.how_given not in HOW_GIVEN:
        raise ProjectError("bad_value", "how_given")


# ---------------------------------------------------------------- reading and writing the file

def project_to_dict(p: Project) -> Dict[str, Any]:
    data: Dict[str, Any] = dict(p.extra)
    data.update({
        "schema": SCHEMA, "id": p.id, "name": p.name, "whose_voice": p.whose_voice, "created": p.created, "planned_hours": p.planned_hours,
        "starting_voice": p.starting_voice,
        "consent": {"given_by": p.consent.given_by, "what_to": p.consent.what_to, "when": p.consent.when, "withdraw": p.consent.withdraw,
                    "how_given": p.consent.how_given, "how_given_other": p.consent.how_given_other},
        "scratch": {"mode": p.scratch.mode, "place": p.scratch.place},
        "acknowledgments": [{"voice": a.voice, "at": a.at, "revision": a.revision} for a in p.acknowledgments]})
    return data


def _text(raw: Mapping, key: str, limit: int, default: str = "") -> str:
    value = raw.get(key, default)
    if value is None:
        return default
    if not isinstance(value, str):
        raise ProjectError("damaged", key)
    return clean_text(value, limit)


def project_from_text(text: str) -> Project:
    try:
        raw = json.loads(text)
    except ValueError:
        raise ProjectError("damaged", "not JSON")
    if not isinstance(raw, dict):
        raise ProjectError("damaged", "not an object")
    schema = raw.get("schema")
    if not isinstance(schema, int) or isinstance(schema, bool):
        raise ProjectError("damaged", "schema")
    if schema > SCHEMA:
        raise ProjectError("newer", str(schema))              # made by a newer version: read-only here, never rewritten by an older one
    consent_raw, scratch_raw = raw.get("consent", {}), raw.get("scratch", {})
    consent_raw = {} if consent_raw is None else consent_raw
    scratch_raw = {} if scratch_raw is None else scratch_raw
    if not isinstance(consent_raw, dict) or not isinstance(scratch_raw, dict):
        raise ProjectError("damaged", "section")             # present but not an object: reported, not read as "empty"
    hours = raw.get("planned_hours", 1.0)
    if isinstance(hours, bool) or not isinstance(hours, (int, float)):
        raise ProjectError("damaged", "planned_hours")
    acks = []
    listed = raw.get("acknowledgments", [])
    if listed is not None and not isinstance(listed, list):
        raise ProjectError("damaged", "acknowledgments")
    for a in listed or []:
        if not isinstance(a, dict) or not all(isinstance(a.get(k), str) for k in ("voice", "at", "revision")):
            raise ProjectError("damaged", "acknowledgments")
        acks.append(Acknowledgment(a["voice"], a["at"], a["revision"]))
    place = scratch_raw.get("place")
    if place is not None and not isinstance(place, str):
        raise ProjectError("damaged", "scratch")
    voice = raw.get("starting_voice")
    if voice is not None and not isinstance(voice, str):
        raise ProjectError("damaged", "starting_voice")
    project = Project(
        id=_text(raw, "id", 64), name=_text(raw, "name", MAX_NAME), whose_voice=_text(raw, "whose_voice", 20), created=_text(raw, "created", 40),
        planned_hours=float(hours), starting_voice=voice,
        consent=Consent(*(_text(consent_raw, k, MAX_NOTE) for k in ("given_by", "what_to", "when", "withdraw", "how_given", "how_given_other"))),
        scratch=Scratch(_text(scratch_raw, "mode", 20, SCRATCH_DEFAULT) or SCRATCH_DEFAULT, place or None),
        acknowledgments=tuple(acks), extra={k: v for k, v in raw.items() if k not in KNOWN_FIELDS})
    try:
        validate(project)
    except ProjectError as exc:
        raise ProjectError("damaged", exc.detail or exc.code)
    return project


def _atomic_write(path: str, body: bytes) -> None:
    directory = os.path.dirname(path)
    fd, temp = tempfile.mkstemp(dir=directory, prefix=".project-", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(body)
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


def save_project(paths: ProjectPaths, project: Project) -> None:
    """Atomic, owner-only, and the version being replaced is kept as project.json.previous (a copy of what was there, made before the swap)."""
    validate(project)
    body = (json.dumps(project_to_dict(project), indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    if os.path.exists(paths.project_json):
        try:
            with open(paths.project_json, "rb") as old:
                _atomic_write(paths.previous_json, old.read())          # the exact bytes, whatever they were
        except OSError:
            pass                                             # a copy that cannot be made must not stop the save, but is not pretended
    _atomic_write(paths.project_json, body)


def load_project(paths: ProjectPaths) -> Project:
    try:
        with open(paths.project_json, encoding="utf-8") as handle:
            return project_from_text(handle.read())
    except (OSError, UnicodeDecodeError) as exc:
        raise ProjectError("unreadable", getattr(exc, "strerror", None) or type(exc).__name__)


# ---------------------------------------------------------------- making and listing

def create_project(projects_root: str, name: str, whose_voice: str, consent: Optional[Consent] = None, planned_hours: float = 1.0,
                   now: Optional[datetime] = None) -> Project:
    """Make the folders and the file. Refuses a someone-else project with an incomplete note, and never touches an existing folder."""
    clean_name = clean_text(name, MAX_NAME)
    if not clean_name:
        raise ProjectError("bad_name")
    if isinstance(planned_hours, bool) or not isinstance(planned_hours, (int, float)):
        raise ProjectError("bad_value", "planned_hours")
    os.makedirs(projects_root, mode=0o700, exist_ok=True)
    taken = set(os.listdir(projects_root))
    project = Project(
        id=slugify(clean_name, taken), name=clean_name, whose_voice=whose_voice,
        created=(now or datetime.now(timezone.utc)).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), planned_hours=float(planned_hours),
        consent=Consent(*(clean_text(v, MAX_NOTE) for v in astuple(consent or Consent()))))
    validate(project)
    if consent_problems(project):
        raise ProjectError("consent", ",".join(consent_problems(project)))
    paths = ProjectPaths(projects_root.rstrip("/") + "/" + project.id)
    try:
        os.mkdir(paths.root, 0o700)
    except FileExistsError:
        raise ProjectError("exists", project.id)
    for folder in paths.folders:
        os.mkdir(folder, 0o700)
    save_project(paths, project)
    return project


@dataclass(frozen=True)
class ProjectList:
    projects: Tuple[Project, ...]
    problems: Tuple[Tuple[str, str], ...]          # (folder name, error code) for each folder that has a project.json that could not be read


def list_projects(projects_root: str) -> ProjectList:
    """Every project, oldest first. A folder whose file is damaged or newer is listed as a problem, never hidden and never touched."""
    found: List[Project] = []
    problems: List[Tuple[str, str]] = []
    try:
        names = sorted(os.listdir(projects_root))
    except OSError:
        return ProjectList((), ())
    for name in names:
        paths = ProjectPaths(projects_root.rstrip("/") + "/" + name)
        if not os.path.isfile(paths.project_json):
            continue
        try:
            found.append(load_project(paths))
        except ProjectError as exc:
            problems.append((name, exc.code))
    return ProjectList(tuple(sorted(found, key=lambda p: (p.created, p.id))), tuple(problems))


# ---------------------------------------------------------------- small updates (each returns a new project; saving is separate)

def with_scratch_place(project: Project, place: Optional[str]) -> Project:
    return replace(project, scratch=Scratch(SCRATCH_CUSTOM, place) if place else Scratch())


def with_starting_voice(project: Project, voice_id: Optional[str]) -> Project:
    return replace(project, starting_voice=voice_id)


def with_acknowledgment(project: Project, voice: str, revision: str, now: Optional[datetime] = None) -> Project:
    """D27: one click per voice, recorded with the date and the exact revision. A second click for the same voice and revision adds nothing."""
    stamp = (now or datetime.now(timezone.utc)).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if any(a.voice == voice and a.revision == revision for a in project.acknowledgments):
        return project
    return replace(project, acknowledgments=project.acknowledgments + (Acknowledgment(voice, stamp, revision),))
