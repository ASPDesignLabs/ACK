# SPDX-License-Identifier: GPL-3.0-or-later
"""Managing profiles (plan task VS-2.10): change a profile's details, put one away without losing anything, and delete one for good, safely.

A profile is a project (core/project.py): one person's voice with its own recordings, rounds and voice files. This file decides; it asks nobody and says nothing. The flows in
projects_flow.py show what will happen and ask first, and the window uses those same flows.

* **Details** (`renamed`, `with_hours`, `with_consent`) return a changed copy. Saving is `project.save_project`, which keeps the file it replaces as `project.json.previous`. The folder
  name (the id) never changes, so nothing that points at the folder is lost. Whose voice it is cannot be changed afterwards: that would change what the consent note means.
* **Archive** (`project.with_archived`) only sets a flag. Nothing is moved or removed, and bringing the profile back undoes it exactly.
* **Delete** is the one thing here that cannot be undone, so it is built to be hard to do by accident. `plan_delete` works out, without removing anything, exactly what would go and how
  large it is, and whether something stops it (a task for this profile is running). `delete_project` takes that plan, works it out again, and removes nothing if it is not the same
  (`changed`). It only ever removes the profile's own folder under the projects folder (never a link, never anything outside it) and a scratch folder on another drive whose marker names
  this profile. **`project.json` is removed last**, so a delete that fails half way leaves a profile that is still listed and can be deleted again, never a folder of recordings that nothing
  lists.
"""
from __future__ import annotations

import hashlib
import os
import shutil
import sys
from dataclasses import dataclass, replace
from typing import Iterable, List, Optional, Sequence, Tuple

from . import jobs, voicefile
from .paths import DataHome, ProjectPaths
from .newproject import CONSENT_TEXT_FIELDS, MAX_TYPED, Problem, parse_hours
from .project import Consent, MAX_NAME, MAX_NOTE, Project, SCRATCH_CUSTOM, clean_text, consent_problems, validate
from .scratch import MARKER_NAME, MarkerState, check_marker, scratch_dir_for

ERROR_CODES = ("job_running", "changed", "unsafe")                  # each has words in the text catalog
CONSENT_PARTS = ("given_by", "what_to", "when", "withdraw", "how_given", "how_given_other")
KEPT_LAST = (os.path.basename(ProjectPaths("/x").project_json), os.path.basename(ProjectPaths("/x").previous_json))      # removed after everything else, so a failed delete leaves a profile that is still listed


class ProfileError(Exception):
    """`code` is a short word the screens turn into a plain sentence: job_running, changed, unsafe."""

    def __init__(self, code: str, detail: str = ""):
        super().__init__(code + (": " + detail if detail else ""))
        self.code = code
        self.detail = detail


# ---------------------------------------------------------------- details

@dataclass(frozen=True)
class EditInput:
    """What the edit form holds, as typed. Whose voice it is stays as it was."""
    name: str
    hours: str
    consent: Consent


@dataclass(frozen=True)
class EditState:
    problems: Tuple[Problem, ...]
    project: Optional[Project]                  # the changed copy, when nothing is wrong with the form
    changes: Tuple["Change", ...]               # what differs from the saved profile (empty when nothing was changed)

    @property
    def can_save(self) -> bool:
        return not self.problems and self.project is not None and bool(self.changes)


def evaluate_edit(old: Project, form: EditInput) -> EditState:
    """Everything wrong with the edit form at once, using the new-profile form's own rules and words, and the changed copy when there is nothing wrong. What was typed is never cut:
    a name or a note over its limit is a problem to fix. For someone else's voice the consent note must stay complete, so a profile never loses the record that its owner agreed; for a
    person's own voice any part may be empty."""
    problems: List[Problem] = []
    name = clean_text(str(form.name)[:MAX_TYPED], MAX_TYPED)
    if not name:
        problems.append(Problem("name", "blank"))
    elif len(name) > MAX_NAME:
        problems.append(Problem("name", "too_long", str(MAX_NAME)))
    hours, why = parse_hours(form.hours)
    if why:
        problems.append(Problem("hours", why))
    consent = Consent(*(clean_text(str(getattr(form.consent, part))[:MAX_TYPED], MAX_TYPED) for part in CONSENT_PARTS))
    for part in CONSENT_TEXT_FIELDS:
        if len(getattr(consent, part)) > MAX_NOTE:
            problems.append(Problem("consent." + part, "too_long", str(MAX_NOTE)))
    probe = replace(old, consent=consent)
    problems += [Problem("consent." + code, "missing") for code in consent_problems(probe)]
    if problems:
        return EditState(tuple(problems), None, ())
    new = replace(old, name=name, planned_hours=float(hours), consent=consent)
    validate(new)
    return EditState((), new, changes(old, new))


@dataclass(frozen=True)
class Change:
    field: str                      # name, hours, consent.<part>
    before: str
    after: str


def changes(old: Project, new: Project) -> Tuple[Change, ...]:
    """What differs between two versions of a profile, for showing before anything is saved. Whole numbers of hours read as '2', not '2.0'."""
    found: List[Change] = []
    if old.name != new.name:
        found.append(Change("name", old.name, new.name))
    if old.planned_hours != new.planned_hours:
        found.append(Change("hours", "%g" % old.planned_hours, "%g" % new.planned_hours))
    for part in CONSENT_PARTS:
        before, after = getattr(old.consent, part), getattr(new.consent, part)
        if before != after:
            found.append(Change("consent." + part, before, after))
    return tuple(found)


def split(projects: Iterable[Project]) -> Tuple[Tuple[Project, ...], Tuple[Project, ...]]:
    """(profiles in use, profiles put away), each in the order given."""
    active: List[Project] = []
    away: List[Project] = []
    for p in projects:
        (away if p.archived else active).append(p)
    return tuple(active), tuple(away)


# ---------------------------------------------------------------- what a delete would remove

@dataclass(frozen=True)
class Part:
    kind: str                       # recordings, rounds, exports, listening, scratch, record, other
    path: str
    bytes: int
    files: int


@dataclass(frozen=True)
class DeletePlan:
    project_id: str
    name: str
    root: str
    parts: Tuple[Part, ...]
    total_bytes: int
    total_files: int
    voice_files: Tuple[str, ...]    # the finished voice files (the zips for ACK) that would go: what to save first
    outside_scratch: str            # a scratch folder on another drive that this profile made and that would go too, or ""
    left_scratch: str               # a scratch folder named in the profile that would NOT go because its marker does not name this profile, or ""
    blocked: str                    # "" or "job_running"
    fingerprint: str

    @property
    def by_kind(self) -> Tuple[Tuple[str, int, int], ...]:
        """(kind, bytes, files) with the parts of one kind added together, in the order the screens show them."""
        order = ("recordings", "rounds", "exports", "listening", "scratch", "record", "other")
        return tuple((kind, sum(p.bytes for p in self.parts if p.kind == kind), sum(p.files for p in self.parts if p.kind == kind)) for kind in order if any(p.kind == kind for p in self.parts))


def measure(path: str) -> Tuple[int, int]:
    """(bytes, files) under a folder or of one file, counting a link as a file of no size and never following it."""
    total = files = 0
    stack = [path]
    while stack:
        current = stack.pop()
        try:
            info = os.lstat(current)
        except OSError:
            continue
        if os.path.isdir(current) and not os.path.islink(current):
            try:
                with os.scandir(current) as entries:
                    stack.extend(entry.path for entry in entries)
            except OSError:
                continue
        else:
            files += 1
            if not os.path.islink(current):
                total += info.st_size
    return total, files


def _kind(paths: ProjectPaths, entry: str) -> str:
    return {paths.recordings: "recordings", paths.rounds: "rounds", paths.exports: "exports", paths.listening: "listening", paths.default_scratch: "scratch"}.get(entry, "record" if os.path.basename(entry) in KEPT_LAST else "other")


def _custom_scratch(project: Project) -> Tuple[str, str]:
    """(a custom scratch folder that carries this profile's marker, one that does not): at most one of them is not ''."""
    if project.scratch.mode != SCRATCH_CUSTOM or not project.scratch.place:
        return "", ""
    try:
        folder = scratch_dir_for(project.scratch.place, project.id)
    except ValueError:
        return "", project.scratch.place
    if not os.path.isdir(folder) or os.path.islink(folder):
        return "", ""
    try:
        with open(folder + "/" + MARKER_NAME, encoding="utf-8") as handle:
            state = check_marker(handle.read(), project.id)
    except OSError:
        state = MarkerState.MISSING
    return (folder, "") if state is MarkerState.OK else ("", folder)


def task_running(home: DataHome, project_id: str) -> bool:
    """Whether a task for this profile (a round, a training set, listening to recordings) is starting, running or stopping."""
    return any(j.spec.project == project_id and j.status in jobs.ACTIVE for j in jobs.list_jobs(home.jobs).jobs)


def _fingerprint(parts: Sequence[Part]) -> str:
    text = "\n".join("%s|%s|%d|%d" % (p.kind, p.path, p.bytes, p.files) for p in parts)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _root_of(home: DataHome, project: Project) -> str:
    root = home.projects + "/" + project.id
    if os.path.islink(root) or not os.path.isdir(root) or os.path.dirname(root) != home.projects or not os.path.isfile(root + "/project.json"):
        raise ProfileError("unsafe", project.id)
    return root


def plan_delete(home: DataHome, project: Project) -> DeletePlan:
    """Everything a delete would remove, worked out without removing anything. Raises `unsafe` for a profile folder that is a link or is not where profiles are kept."""
    root = _root_of(home, project)
    paths = ProjectPaths(root)
    parts: List[Part] = []
    for entry in sorted(os.listdir(root)):
        full = root + "/" + entry
        size, count = measure(full)
        parts.append(Part(_kind(paths, full), full, size, count))
    outside, left = _custom_scratch(project)
    if outside:
        size, count = measure(outside)
        parts.append(Part("scratch", outside, size, count))
    voice = tuple(name for name, _zip, _size in voicefile.existing_voice_files(paths))
    return DeletePlan(project.id, project.name, root, tuple(parts), sum(p.bytes for p in parts), sum(p.files for p in parts), voice, outside, left,
                      "job_running" if task_running(home, project.id) else "", _fingerprint(parts))


@dataclass(frozen=True)
class DeleteResult:
    bytes: int
    files: int
    failed: Tuple[Tuple[str, str], ...]         # (path, why) for each thing that could not be removed
    gone: bool                                  # the profile's folder no longer exists


def _remove_tree(path: str, failed: List[Tuple[str, str]]) -> None:
    def note(_func: object, bad: str, error: object) -> None:
        exc = error[1] if isinstance(error, tuple) else error
        failed.append((bad, getattr(exc, "strerror", None) or type(exc).__name__))
    if os.path.islink(path) or not os.path.isdir(path):
        try:
            os.unlink(path)
        except OSError as exc:
            failed.append((path, exc.strerror or type(exc).__name__))
        return
    if sys.version_info >= (3, 12):
        shutil.rmtree(path, onexc=note)
    else:
        shutil.rmtree(path, onerror=note)


def delete_project(home: DataHome, project: Project, shown: DeletePlan) -> DeleteResult:
    """Remove what `shown` listed, after working it out again. Raises `job_running` when a task for the profile has started since, and `changed` (removing nothing) when what is
    there now is not what was shown. A part that cannot be removed is reported and stops the delete before `project.json`, so the profile stays listed."""
    fresh = plan_delete(home, project)
    if fresh.blocked:
        raise ProfileError("job_running")
    if fresh.fingerprint != shown.fingerprint or fresh.root != shown.root:
        raise ProfileError("changed")
    failed: List[Tuple[str, str]] = []
    gone_bytes = gone_files = 0
    outside = [p for p in fresh.parts if fresh.outside_scratch and p.path == fresh.outside_scratch]
    inside = [p for p in fresh.parts if p.path.startswith(fresh.root + "/") and p.kind != "record"]
    for part in outside + inside:
        before = len(failed)
        _remove_tree(part.path, failed)
        if len(failed) == before and not os.path.lexists(part.path):
            gone_bytes += part.bytes
            gone_files += part.files
        if failed:
            break
    if not failed:
        for name in KEPT_LAST:
            target = fresh.root + "/" + name
            if os.path.lexists(target):
                _remove_tree(target, failed)
        if not failed:
            try:
                os.rmdir(fresh.root)
            except OSError as exc:
                failed.append((fresh.root, exc.strerror or type(exc).__name__))
    record = [p for p in fresh.parts if p.kind == "record"]
    if not failed:
        gone_bytes += sum(p.bytes for p in record)
        gone_files += sum(p.files for p in record)
    return DeleteResult(gone_bytes, gone_files, tuple(failed), not os.path.lexists(fresh.root))
