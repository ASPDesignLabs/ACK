# SPDX-License-Identifier: GPL-3.0-or-later
"""Refresh (plan task VS-6.6, decisions D41 and P18): look at the tool's own programs, downloaded files and notes and say what is broken, repair only that, build a second whole copy of the
programs beside the first, and remove the copies that are no longer in use.

Refresh is a reinstall that does not wipe data. **It never touches** a project, a recording, a round, a finished voice file, a consent note about a person, a backup, or the starting voices
beyond fetching a damaged one again (and a file is only ever replaced after the new one has been checked byte for byte). It makes no change to anything it cannot name in advance, and
every change is shown and asked first by the front (core/refresh_flow.py). Looking changes nothing at all: not even the log of a set of programs.

**What a look covers.** Each set of programs (core/envbuild.py `inspect`, then the self-test run again, because only that finds a package whose files are broken while its record is in
order); the downloaded files, byte for byte against what was agreed (the listening model, and any starting voice that was fetched); and the small notes the tool keeps (what the person
agreed to, the window's choices, which copy of the programs is in use, when each project was last backed up). **What it does not cover:** the menu entry (`--install-launcher` shows and
replaces it), the system packages (the first setup step), and a project (use the backup command).

**A rebuild** is a second copy, not a repair in place. The folder of a set of programs is named for what it is built from, so a copy of the same list needs a new name: core/envgen.py keeps
a generation number that goes into the name, and it is only raised after the new copy has passed its self-test. Until then the old copy is the one in use, so a rebuild that fails costs
only disk space and time. The old copy is then *older*: it is listed, with its size, and removed only when the person says so, never while a task is running.

Plain Python with no words; the words are in the text catalog under `refresh.*`.
"""
from __future__ import annotations

import dataclasses
import os
import re
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from . import envbuild, envfind, envgen, fetch, jobs, projectbackup as pb, rounds as rd, startvoice, windowprefs
from .consent import load_consent
from .envspec import EnvSpec
from .paths import DataHome, ProjectPaths
from .project import Project, list_projects
from .registry import Item, Registry

PROGRAMS, DOWNLOAD, NOTE = "programs", "download", "note"
AREAS = (PROGRAMS, DOWNLOAD, NOTE)
GOOD, PROBLEM, ABSENT = "good", "problem", "absent"
STATUSES = (GOOD, PROBLEM, ABSENT)
FIXES = ("", "resume", "rebuild", "fetch", "set_aside", "setup")          # what a finding is mended by; "" is "nothing this tool can do from here"
REASONS = ("ready", "ready_untried", "needs_work", "not_checked", "failed", "not_set_up", "damaged_record", "not_ours", "newer_record", "cannot_build", "probe_failed", "launcher_failed",
           "fetched", "fetched_elsewhere", "not_fetched", "incomplete", "damaged", "unfinished", "readable", "no_note", "unreadable")      # each has words in the text catalog under refresh.reason.<code>
NOTES = ("consent", "window", "backups", "copies")                         # the small files; each has words under refresh.note.<id>
ERROR_CODES = ("job_running", "changed", "not_noted", "no_more_copies")      # each has words in the text catalog
SPEECH = "speech"
SET_ASIDE_SUFFIX = ".damaged-"
MAX_OLDER = 200                                                            # a folder of more than this many copies is not something this tool made
COPY_NAME = re.compile(r"^(?P<id>[a-z0-9][a-z0-9-]{0,63})-(?P<fp>[0-9a-f]{10})\Z")


class RefreshError(Exception):
    """`code` is one of ERROR_CODES; `detail` is a short fact for Show details."""

    def __init__(self, code: str, detail: str = ""):
        super().__init__(code + (": " + detail if detail else ""))
        self.code = code
        self.detail = detail


# ---------------------------------------------------------------- looking

@dataclass(frozen=True)
class Finding:
    id: str                              # "programs:training", "download:speech", "download:voice-mike", "note:consent"
    area: str                            # one of AREAS
    subject: str                         # the set of programs, "speech" or the voice's id in the registry, or the note's id
    status: str                          # one of STATUSES
    reason: str                          # one of REASONS
    fix: str = ""                        # one of FIXES
    detail: str = ""                     # a short fact for the line: the probe that failed, the programs not tried
    steps: Tuple[str, ...] = ()          # for programs that need work: the steps that would run again


@dataclass(frozen=True)
class Report:
    findings: Tuple[Finding, ...]

    @property
    def problems(self) -> Tuple[Finding, ...]:
        return tuple(f for f in self.findings if f.status == PROBLEM)

    @property
    def in_order(self) -> bool:
        return not self.problems

    def of(self, fix: str) -> Tuple[Finding, ...]:
        return tuple(f for f in self.problems if f.fix == fix)


def _programs(spec: EnvSpec, ctx: envbuild.Context, probes: bool) -> Finding:
    found = envbuild.inspect(spec, ctx)
    ident = "programs:" + spec.id
    state = found.state
    if state == "ready":
        if not probes:
            return Finding(ident, PROGRAMS, spec.id, GOOD, "ready")
        report = envbuild.probe(spec, ctx, found.env_dir)
        if report.ok:
            return Finding(ident, PROGRAMS, spec.id, GOOD, "ready_untried" if report.skipped else "ready", detail=", ".join(report.skipped))
        return Finding(ident, PROGRAMS, spec.id, PROBLEM, "launcher_failed" if report.code == "launcher_failed" else "probe_failed", "rebuild", report.detail)
    if state in ("needs_work", "failed"):
        return Finding(ident, PROGRAMS, spec.id, PROBLEM, state if found.stale else "not_checked", "resume", steps=found.stale)
    if state == "absent":
        return Finding(ident, PROGRAMS, spec.id, ABSENT, "not_set_up", "setup")
    if state == "damaged":
        return Finding(ident, PROGRAMS, spec.id, PROBLEM, "damaged_record", "rebuild")
    if state == "not_ours":
        return Finding(ident, PROGRAMS, spec.id, PROBLEM, "not_ours", "rebuild")
    if state == "newer":
        return Finding(ident, PROGRAMS, spec.id, PROBLEM, "newer_record")
    return Finding(ident, PROGRAMS, spec.id, PROBLEM, "cannot_build", detail=found.error.code if found.error is not None else "")


def _speech(home: DataHome, registry: Registry) -> Finding:
    folder, state = envfind.speech_model(home, registry)
    if state == "ready":
        own = envfind.speech_places(home)[0]
        return Finding("download:" + SPEECH, DOWNLOAD, SPEECH, GOOD, "fetched" if folder == own else "fetched_elsewhere")
    if state == "incomplete":
        return Finding("download:" + SPEECH, DOWNLOAD, SPEECH, PROBLEM, "incomplete", "fetch")
    return Finding("download:" + SPEECH, DOWNLOAD, SPEECH, ABSENT, "not_fetched")


def voice_items(registry: Registry) -> List[Item]:
    """The starting voices the registry can fetch, in the registry's order."""
    return [item for item in registry.items if item.kind == "voice" and not item.pin_problems() and item.filename]


def voice_target(home: DataHome, item: Item) -> Path:
    return startvoice.voice_folder(home, item) / (item.filename or "")


def _voice(home: DataHome, item: Item) -> Optional[Finding]:
    """A starting voice that was fetched: whole, damaged or unfinished. One that was never fetched is not mentioned (a voice is fetched when it is chosen)."""
    target = voice_target(home, item)
    ident = "download:" + item.id
    if fetch.is_fetched(item, startvoice.voice_folder(home, item)):
        return Finding(ident, DOWNLOAD, item.id, GOOD, "fetched")
    if os.path.lexists(str(target)):
        return Finding(ident, DOWNLOAD, item.id, PROBLEM, "damaged", "fetch")
    if os.path.lexists(str(target) + ".part"):
        return Finding(ident, DOWNLOAD, item.id, PROBLEM, "unfinished", "fetch")
    return None


def note_path(home: DataHome, note: str) -> str:
    return {"consent": home.consent_file, "window": home.window_file, "backups": home.state + "/" + pb.STATE_FILE, "copies": envgen.path_of(home)}[note]


def _readable(home: DataHome, note: str) -> bool:
    path = note_path(home, note)
    if note == "consent":
        return load_consent(Path(path)) is not None
    if note == "window":
        return windowprefs.load(path) is not None
    return jobs.read_json(path) is not None


def _note(home: DataHome, note: str) -> Finding:
    ident = "note:" + note
    if not os.path.lexists(note_path(home, note)):
        return Finding(ident, NOTE, note, ABSENT, "no_note")
    if _readable(home, note):
        return Finding(ident, NOTE, note, GOOD, "readable")
    return Finding(ident, NOTE, note, PROBLEM, "unreadable", "set_aside")


def look(home: DataHome, registry: Registry, specs: Sequence[EnvSpec], ctx: envbuild.Context, *, probes: bool = True,
         announce: Optional[Callable[[str, str], None]] = None) -> Report:
    """Everything a refresh can say about, in a fixed order: the programs, the downloads, the notes. Changes nothing. `announce(area, subject)` is called before each thing is looked at, because
    running the programs' own checks and reading two gigabytes of downloads take a while."""
    say = announce or (lambda area, subject: None)
    found: List[Finding] = []
    for spec in specs:
        say(PROGRAMS, spec.id)
        found.append(_programs(spec, ctx, probes))
    say(DOWNLOAD, SPEECH)
    found.append(_speech(home, registry))
    for item in voice_items(registry):
        say(DOWNLOAD, item.id)
        voice = _voice(home, item)
        if voice is not None:
            found.append(voice)
    for note in NOTES:
        say(NOTE, note)
        found.append(_note(home, note))
    return Report(tuple(found))


# ---------------------------------------------------------------- repairing

@dataclass(frozen=True)
class RepairPlan:
    resume: Tuple[Finding, ...]            # programs finished by the builder, which shows what it downloads and asks
    fetch: Tuple[Finding, ...]             # downloads fetched again; the file in the way is replaced only after the new one is checked
    set_aside: Tuple[Finding, ...]         # notes that cannot be read, moved aside (never deleted)
    needs_more: Tuple[Finding, ...]        # problems a repair does not mend: a rebuild, the setup, or an update of this tool

    @property
    def work(self) -> bool:
        return bool(self.resume or self.fetch or self.set_aside)


def plan_repair(report: Report) -> RepairPlan:
    """What a repair would do, from a look. A problem is mended by the way it names; every other problem is listed as needing more than a repair."""
    return RepairPlan(report.of("resume"), report.of("fetch"), report.of("set_aside"), tuple(f for f in report.problems if f.fix in ("", "rebuild", "setup")))


def set_aside(home: DataHome, note: str, now: Optional[datetime] = None) -> str:
    """Move a note that cannot be read out of the way, beside itself, and return where it went. Nothing is deleted and nothing already there is replaced. Raises OSError."""
    path = note_path(home, note)
    stamp = (now or datetime.now(timezone.utc)).astimezone(timezone.utc).strftime("%Y%m%d-%H%M%S")
    target, n = "%s%s%s" % (path, SET_ASIDE_SUFFIX, stamp), 1
    while os.path.lexists(target):
        n += 1
        target = "%s%s%s-%d" % (path, SET_ASIDE_SUFFIX, stamp, n)
    os.replace(path, target)
    return target


def items_to_fetch(home: DataHome, registry: Registry, findings: Sequence[Finding]) -> List[Tuple[Item, Path]]:
    """For each download finding that is to be fetched again: the registry file and the folder it belongs in. The speech model is its files together in its own folder; a voice is its one file."""
    wanted: List[Tuple[Item, Path]] = []
    for finding in findings:
        if finding.subject == SPEECH:
            folder = Path(envfind.speech_places(home)[0])
            for item in envfind.speech_files(registry):
                if not fetch.is_fetched(item, folder):
                    wanted.append((item, folder))
        else:
            item = next((i for i in registry.items if i.id == finding.subject), None)
            if item is not None:
                wanted.append((item, startvoice.voice_folder(home, item)))
    return wanted


# ---------------------------------------------------------------- a second copy, and the copies no longer in use

def next_generation(home: DataHome, env_id: str) -> int:
    """The number the next copy of this set of programs will have. Raises RefreshError when there is no higher number to give."""
    current = envgen.generation_of(home, env_id)
    if current >= envgen.MAX_GENERATION:
        raise RefreshError("no_more_copies", env_id)
    return current + 1


def with_generation(ctx: envbuild.Context, env_id: str, generation: int) -> envbuild.Context:
    """The builder's context with this one set of programs at `generation`, every other set as the note says."""
    return dataclasses.replace(ctx, generations=lambda home, other: generation if other == env_id else envgen.generation_of(home, other))


def note_generation(home: DataHome, env_id: str, generation: int) -> None:
    """Switch to the new copy: raised only now that it is ready. Raises RefreshError('not_noted') when the note cannot be written (the old copy stays in use)."""
    try:
        envgen.write(home, env_id, generation)
    except OSError as exc:
        raise RefreshError("not_noted", exc.strerror or type(exc).__name__)


@dataclass(frozen=True)
class OlderCopy:
    folder: str
    env_id: str
    bytes: int
    files: int
    state: str                           # what its own record says: "ready", "building" or "failed"
    updated: str                         # when its record was last written


@dataclass(frozen=True)
class Older:
    copies: Tuple[OlderCopy, ...]
    left_alone: int                      # folders there that this tool did not make (or cannot tell the use of): never listed, never touched
    in_use: Tuple[str, ...]              # the folder of each set of programs that is in use


def _tree(folder: str) -> Tuple[int, int]:
    size = files = 0
    for base, _folders, names in os.walk(folder, followlinks=False):
        for name in names:
            try:
                info = os.lstat(os.path.join(base, name))
            except OSError:
                continue
            if os.path.isfile(os.path.join(base, name)) and not os.path.islink(os.path.join(base, name)):
                size += info.st_size
                files += 1
    return size, files


def older_copies(home: DataHome, specs: Sequence[EnvSpec], ctx: envbuild.Context) -> Older:
    """The folders of earlier copies of each set of programs: ours (they carry our record, and their name is made from it), not the one in use, and not being built right now. Looks only."""
    in_use: Dict[str, str] = {}
    for spec in specs:
        try:
            in_use[spec.id] = envbuild.environment_dir(spec, ctx)
        except envbuild.EnvError:
            pass                                                    # what is in use cannot be told, so nothing of that set of programs is offered
    try:
        names = sorted(os.listdir(home.environments))
    except OSError:
        return Older((), 0, tuple(in_use.values()))
    copies: List[OlderCopy] = []
    left = 0
    for name in names:
        folder = home.environments + "/" + name
        match = COPY_NAME.match(name)
        ours = match is not None and match.group("id") in in_use and os.path.isdir(folder) and not os.path.islink(folder)
        record, _why = envbuild.read_record(folder) if ours else (None, "")
        if record is None or record["id"] != match.group("id") or record["fingerprint"][:10] != match.group("fp"):
            left += 1
            continue
        if folder == in_use[match.group("id")] or os.path.lexists(folder + "/" + envbuild.BUILD_LOCK_NAME) or len(copies) >= MAX_OLDER:
            continue
        size, files = _tree(folder)
        copies.append(OlderCopy(folder, match.group("id"), size, files, str(record.get("state", "")), str(record.get("updated_at", ""))))
    return Older(tuple(copies), left, tuple(in_use.values()))


@dataclass(frozen=True)
class Removed:
    removed: Tuple[OlderCopy, ...]
    failed: Tuple[Tuple[str, str], ...]         # (folder, the system's reason)

    @property
    def bytes(self) -> int:
        return sum(c.bytes for c in self.removed)


def remove_older(home: DataHome, specs: Sequence[EnvSpec], ctx: envbuild.Context, shown: Sequence[OlderCopy], remove: Callable[[str], None] = shutil.rmtree) -> Removed:
    """Remove the copies that were shown, and only those. Refused while any task is running (a training round runs from the copy it began with), and when the list is no longer the one shown.
    A folder is looked at again just before it is removed: still a plain folder, still ours, still not the one in use."""
    if any(job.status in jobs.ACTIVE for job in jobs.list_jobs(home.jobs).jobs):
        raise RefreshError("job_running")
    again = older_copies(home, specs, ctx)
    if tuple((c.folder, c.state) for c in again.copies) != tuple((c.folder, c.state) for c in shown):
        raise RefreshError("changed")
    done: List[OlderCopy] = []
    failed: List[Tuple[str, str]] = []
    for copy in again.copies:
        if os.path.islink(copy.folder) or not os.path.isdir(copy.folder) or copy.folder in again.in_use:
            failed.append((copy.folder, "it is no longer an old copy"))
            continue
        try:
            remove(copy.folder)
        except OSError as exc:
            failed.append((copy.folder, exc.strerror or type(exc).__name__))
            continue
        done.append(copy)
    return Removed(tuple(done), tuple(failed))


# ---------------------------------------------------------------- the projects, before a rebuild

def unprotected(home: DataHome) -> Tuple[Tuple[Project, str], ...]:
    """The projects that have never been backed up on this computer, or have changed since: (project, "never" or "changed"). A rebuild touches no project; this is the advice that goes with it.
    A project whose record of rounds cannot be read is left out (its own commands say so)."""
    found: List[Tuple[Project, str]] = []
    for project in list_projects(home.projects).projects:
        try:
            standing = pb.standing(home, ProjectPaths(home.projects + "/" + project.id), project.id)
        except rd.RoundsError:
            continue
        if standing.state in (pb.NEVER, pb.CHANGED):
            found.append((project, standing.state))
    return tuple(found)
