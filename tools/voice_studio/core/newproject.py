# SPDX-License-Identifier: GPL-3.0-or-later
"""The new-project form, as decisions (plan task VS-2.3, decisions D9, D21, D24, D25, D26).

`evaluate` takes what the person typed and says everything that is wrong with it at once (not the first thing only), what the plan will need on
the disk, and what the chosen scratch place looks like. It changes nothing. `create` makes the project, and only then touches a custom scratch
place, so a drive that turns out to be unusable never costs the person the project: the result says the project was made and the place was not.

What a person typed is never silently cut: a name or a note over its limit is a problem to fix, because shortening a consent note or a name for
them would change what they wrote.
"""
from __future__ import annotations

import math
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Iterable, Mapping, Optional, Tuple

from .diskbudget import DEFAULT_TABLE, DriveMap, Line, Role, SizeTable, need_by_drive, person_lines
from .paths import ProjectPaths
from .project import (MAX_HOURS, MAX_NAME, MAX_NOTE, MIN_HOURS, OWN, SOMEONE_ELSE, Consent, Project, ProjectError, clean_text, consent_problems,
                      create_project, save_project, slugify, with_scratch_place, with_starting_voice)
from .scratch import Assessment, PlaceFacts, assess_scratch, create_scratch

# every (field, code) the form reports that has a sentence of its own; the reasons a scratch place is refused use the scratch.refuse.* sentences
PROBLEMS = (("name", "blank"), ("name", "too_long"), ("whose_voice", "missing"), ("consent", "missing"), ("consent", "too_long"), ("hours", "blank"),
            ("hours", "not_a_number"), ("hours", "too_small"), ("hours", "too_big"), ("starting_voice", "unknown"), ("scratch", "not_checked"))
ERROR_CODES = ("scratch_failed",)               # the project exists, the chosen place could not be set up; words in the text catalog
CONSENT_TEXT_FIELDS = ("given_by", "what_to", "when", "withdraw", "how_given_other")
MAX_TYPED = 100_000                             # a form field longer than this is not looked at (a paste of the wrong thing)


@dataclass(frozen=True)
class FormInput:
    name: str = ""
    whose_voice: str = ""                       # "" until the person chooses; then OWN or SOMEONE_ELSE
    consent: Consent = field(default_factory=Consent)
    hours: str = "1"                            # as typed
    starting_voice: Optional[str] = None        # a registry voice id, or None for "choose later"
    scratch_place: str = ""                     # "" means the default place; anything else is the Advanced choice


@dataclass(frozen=True)
class Problem:
    field: str                                  # name, whose_voice, consent.<part>, hours, starting_voice, scratch
    code: str
    detail: str = ""


@dataclass(frozen=True)
class Estimate:
    lines: Tuple[Line, ...]
    project_bytes: int
    scratch_bytes: int
    backup_bytes: int
    need: Dict[str, int]                        # per drive name ("project", "scratch"), the margin included
    short_by: Dict[str, int]                    # per drive, what is missing (0 if it fits); a drive whose room is unknown is absent
    rough: bool                                 # the table still has numbers nobody measured


@dataclass(frozen=True)
class FormState:
    problems: Tuple[Problem, ...]
    warnings: Tuple[str, ...]                   # scratch warning codes; the person can go on
    clean_name: str
    project_id: str                             # the folder name this would get
    hours: Optional[float]
    estimate: Optional[Estimate]
    assessment: Optional[Assessment]

    @property
    def can_create(self) -> bool:
        return not self.problems and self.hours is not None


# ---------------------------------------------------------------- reading what was typed

def parse_hours(text: str) -> Tuple[Optional[float], Optional[str]]:
    """(hours, None) or (None, why): blank, not_a_number, too_small, too_big. One comma and no point is a decimal comma ("1,5")."""
    typed = (text or "").strip()
    if not typed:
        return None, "blank"
    if typed.count(",") == 1 and "." not in typed:
        typed = typed.replace(",", ".")
    try:
        value = float(typed)
    except ValueError:
        return None, "not_a_number"
    if math.isnan(value) or math.isinf(value):
        return None, "not_a_number"
    if value < MIN_HOURS:
        return None, "too_small"
    if value > MAX_HOURS:
        return None, "too_big"
    return value, None


def planned_id(name: str, taken: Iterable[str] = ()) -> str:
    return slugify(clean_text(name, MAX_NAME), taken)


def _estimate(table: SizeTable, hours: float, custom_scratch: bool, free: Mapping[str, Optional[int]]) -> Estimate:
    lines = tuple(person_lines(table, hours))
    drives = DriveMap(tool="project", project="project", scratch="scratch" if custom_scratch else "project", backup="project")
    need = need_by_drive(lines, drives, table.margin)
    short = {drive: max(0, total - have) for drive, total in need.items() for have in [free.get(drive)] if have is not None}
    by_role = {role: sum(l.bytes for l in lines if l.role is role) for role in Role}
    return Estimate(lines, by_role[Role.PROJECT], by_role[Role.SCRATCH], by_role[Role.BACKUP], need, short, not table.all_measured)


# ---------------------------------------------------------------- judging the form

def evaluate(form: FormInput, *, taken_ids: Iterable[str] = (), voice_ids: Iterable[str] = (), table: SizeTable = DEFAULT_TABLE,
             free: Mapping[str, Optional[int]] = {}, facts: Optional[PlaceFacts] = None) -> FormState:
    """Everything wrong with the form, the disk estimate, and the scratch place's assessment. `facts` are the facts about `scratch_place` for this
    project's folder name (core/scratch.gather_place_facts); without them a chosen place counts as not yet checked."""
    problems = []
    clean_name = clean_text(str(form.name)[:MAX_TYPED], MAX_TYPED)
    if not clean_name:
        problems.append(Problem("name", "blank"))
    elif len(clean_name) > MAX_NAME:
        problems.append(Problem("name", "too_long", str(MAX_NAME)))
    project_id = planned_id(clean_name[:MAX_NAME], taken_ids)

    if form.whose_voice not in (OWN, SOMEONE_ELSE):
        problems.append(Problem("whose_voice", "missing"))

    consent = Consent(*(clean_text(str(getattr(form.consent, n))[:MAX_TYPED], MAX_TYPED) for n in ("given_by", "what_to", "when", "withdraw", "how_given", "how_given_other")))
    for name in CONSENT_TEXT_FIELDS:
        if len(getattr(consent, name)) > MAX_NOTE:
            problems.append(Problem("consent." + name, "too_long", str(MAX_NOTE)))
    if form.whose_voice == SOMEONE_ELSE:
        probe = Project(id="x", name=clean_name or "x", whose_voice=SOMEONE_ELSE, created="", consent=consent)
        problems += [Problem("consent." + code, "missing") for code in consent_problems(probe)]

    hours, why = parse_hours(form.hours)
    if why:
        problems.append(Problem("hours", why))

    if form.starting_voice is not None and form.starting_voice not in set(voice_ids):
        problems.append(Problem("starting_voice", "unknown", str(form.starting_voice)[:80]))

    assessment: Optional[Assessment] = None
    warnings: Tuple[str, ...] = ()
    custom = bool(form.scratch_place.strip())
    if custom:
        if facts is None or facts.project_id != project_id or facts.given.strip() != form.scratch_place.strip():
            problems.append(Problem("scratch", "not_checked"))
        else:
            assessment = assess_scratch(facts)
            problems += [Problem("scratch", code) for code in assessment.refusals]
            warnings = assessment.warnings

    estimate = _estimate(table, hours, custom, free) if hours is not None else None
    return FormState(tuple(problems), warnings, clean_name, project_id, hours, estimate, assessment)


# ---------------------------------------------------------------- making it

@dataclass(frozen=True)
class CreateResult:
    project: Project
    scratch_dir: Optional[str] = None           # the folder made inside the chosen place, when there was one
    error: Optional[str] = None                 # "scratch_failed": the project exists but the chosen place could not be set up
    detail: str = ""


def create(form: FormInput, state: FormState, projects_root: str, now: Optional[datetime] = None) -> CreateResult:
    """Make the project from a form that `evaluate` passed. Refuses a form that did not pass. A chosen scratch place is set up only after the project
    exists; if that fails the project keeps its default place and nothing on the chosen drive has been changed beyond what is reported."""
    if not state.can_create:
        raise ProjectError("bad_value", "form")
    consent = Consent(*(clean_text(str(getattr(form.consent, n)), MAX_NOTE) for n in ("given_by", "what_to", "when", "withdraw", "how_given", "how_given_other")))
    project = create_project(projects_root, state.clean_name, form.whose_voice, consent, planned_hours=float(state.hours), now=now)
    paths = ProjectPaths(projects_root.rstrip("/") + "/" + project.id)
    if form.starting_voice is not None:
        project = with_starting_voice(project, form.starting_voice)
    scratch_dir: Optional[str] = None
    error, detail = None, ""
    place = form.scratch_place.strip()
    if place:
        real = state.assessment.scratch_dir if state.assessment else ""
        try:
            base = os.path.dirname(os.path.dirname(real)) if real else ""
            scratch_dir = create_scratch(base, project.id)
            project = with_scratch_place(project, base)
        except (OSError, ValueError) as exc:
            error, detail = "scratch_failed", getattr(exc, "strerror", None) or str(exc)
    save_project(paths, project)
    return CreateResult(project, scratch_dir, error, detail)
