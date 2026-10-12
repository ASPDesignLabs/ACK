# SPDX-License-Identifier: GPL-3.0-or-later
"""What the window shows, as plain data (plan task VS-2.1; the rule in section 3: decisions in plain Python, a thin GTK edge).

Every function here only looks: it reads the files the terminal commands read and returns words from the text catalog and numbers, so the window has nothing to decide and a plain
test run covers it. A round is described by the same function the terminal uses (`rounds_flow.round_lines`). What a button does is not here: it is a list of words for the very
command the terminal runs (`rounds choose 2 --project anna`), built by the `*_args` functions below and run by `Services.run`.

Nothing here writes. The window's own questions and the changes they lead to belong to the flows.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Callable, List, Optional, Sequence, Tuple

from . import commands, freeup, jobs, rounds as rd, voicefile as vf
from .describe import error_text
from .paths import DataHome, ProjectPaths
from .project import OWN, SOMEONE_ELSE, Consent, Project, list_projects
from .newproject import FormInput
from .profiles import EditInput, split
from .projects_flow import WHOSE_WORDS, _hours, edit_form_problems, new_form_problems, run_projects
from .registry import Registry
from .startvoice import voices as starting_voices
from .rounds_flow import Open, TrainingEnv, free_row_text, round_lines, run_rounds, scratch_ready, scratch_root
from .system import RealSystem, System
from .text import Catalog, size_text
from .voicefile_flow import run_voicefile

TOOLS = ("projects", "rounds", "voicefile")
MAX_NOTE_SHOWN = 500


# ---------------------------------------------------------------- the computer the window works on

@dataclass
class Services:
    """Everything a flow needs, held once for the window. `run` runs one terminal command by name, with the window's IO."""

    home: DataHome
    registry: Registry
    cat: Catalog
    training: TrainingEnv
    system: System
    tools_dir: str = str(jobs.TOOLS_DIR)

    def titles(self) -> Tuple[str, ...]:
        return (self.cat.t("projects.title"), self.cat.t("rounds.title"), self.cat.t("voicefile.title"))

    def run(self, tool: str, argv: Sequence[str], io) -> int:
        if tool == "projects":
            return run_projects(argv, self.system, self.home, self.registry, self.cat, io)
        if tool == "rounds":
            return run_rounds(argv, self.home, self.registry, self.cat, io, training=self.training, system=self.system)
        if tool == "voicefile":
            return run_voicefile(argv, self.home, self.registry, self.cat, io, training=self.training, system=self.system, tools_dir=self.tools_dir)
        raise ValueError("unknown tool: " + tool)


def real_services(home: DataHome, registry: Registry, cat: Catalog, training: TrainingEnv) -> Services:
    return Services(home, registry, cat, training, RealSystem())


# ---------------------------------------------------------------- projects

@dataclass(frozen=True)
class ProjectItem:
    id: str
    name: str
    line: str                                    # 'voice-check: Voice check, own voice, about 1 hours planned. Starting voice: voice-mike.'
    away: bool = False                           # put away: not opened by anything until it is brought back


@dataclass(frozen=True)
class ProjectsView:
    items: Tuple[ProjectItem, ...]               # the projects in use
    away: Tuple[ProjectItem, ...]                # the projects put away
    problems: Tuple[str, ...]                    # a project file that could not be used: said, never hidden, never touched
    folder: str


def projects_view(home: DataHome, cat: Catalog) -> ProjectsView:
    listing = list_projects(home.projects)
    in_use, away = split(listing.projects)

    def item(p: Project) -> ProjectItem:
        return ProjectItem(p.id, p.name, cat.t("projects.row", id=p.id, name=p.name, whose=cat.t(WHOSE_WORDS[p.whose_voice]), hours=_hours(p.planned_hours),
                                               voice=p.starting_voice or cat.t("projects.no_voice")), p.archived)
    problems = tuple(cat.t("projects.damaged", folder=home.projects + "/" + folder) + " " + error_text(cat, "project", code).what for folder, code in listing.problems)
    return ProjectsView(tuple(item(p) for p in in_use), tuple(item(p) for p in away), problems, home.projects)


def find_project(home: DataHome, project_id: str, include_away: bool = False) -> Optional[Project]:
    """The project with this id, or None. One that is put away is found only when asked for: nothing opens it by accident."""
    return next((p for p in list_projects(home.projects).projects if p.id == project_id and (include_away or not p.archived)), None)


def open_project(home: DataHome, project_id: str) -> Optional[Open]:
    project = find_project(home, project_id)
    if project is None:
        return None
    paths = ProjectPaths(home.projects + "/" + project.id)
    return Open(project, paths, scratch_root(project, paths), home.jobs)


# ---------------------------------------------------------------- rounds

@dataclass(frozen=True)
class RoundItem:
    number: int
    lines: Tuple[str, ...]                       # the head, then the indented lines the terminal prints
    chosen: bool
    can_choose: bool                             # has a whole saved point, is not the chosen one, and nothing is training
    note: str


@dataclass(frozen=True)
class RoundsView:
    project_id: str
    project_name: str
    items: Tuple[RoundItem, ...]
    summary: Tuple[str, ...]
    running: Optional[int]
    back_target: Optional[int]                   # the round 'go back' would choose, if there is one
    sets: Tuple[str, ...]                        # the training sets this project has, by name
    can_start: bool
    problem: str                                 # the record could not be read: nothing else is shown


def _datasets(ctx: Open) -> Tuple[str, ...]:
    try:
        return tuple(sorted(n for n in os.listdir(ctx.scratch.datasets) if os.path.isdir(ctx.scratch.datasets + "/" + n) and not os.path.islink(ctx.scratch.datasets + "/" + n)
                            and commands.SAFE_NAME.match(n)))
    except OSError:
        return ()


def rounds_view(home: DataHome, project_id: str, cat: Catalog, now=None) -> Optional[RoundsView]:
    """None when there is no such project. Brings the record up to date in memory only (a round that ended since is shown as ended); it saves nothing."""
    ctx = open_project(home, project_id)
    if ctx is None:
        return None
    try:
        record = rd.reconcile(ctx.paths, ctx.scratch, ctx.jobs_root, ctx.project.id, now=now, write=False)
    except rd.RoundsError as error:
        return RoundsView(ctx.project.id, ctx.project.name, (), (), None, None, (), False, error_text(cat, "rounds", error.code).what)
    running = rd.active(record)
    items = tuple(RoundItem(r.number, tuple(round_lines(r, r.number == record.current, ctx.paths, cat)), r.number == record.current,
                            running is None and r.has_checkpoint and r.number != record.current and rd.checkpoint_status(ctx.paths, r) == "ok", r.note) for r in record.rounds)
    summary: List[str] = []
    pick = rd.chosen(record)
    if not record.rounds:
        summary.append(cat.t("rounds.list.none"))
    if pick is not None:
        summary.append(cat.t("rounds.list.chosen", number=pick.number, minutes=rd.trained_minutes(record, pick.number)))
    else:
        summary.append(cat.t("rounds.list.none_chosen"))
    if running is not None:
        summary.append(cat.t("window.rounds.running", number=running.number))
    sets = _datasets(ctx)
    return RoundsView(ctx.project.id, ctx.project.name, items, tuple(summary), running.number if running is not None else None,
                      None if running is not None else rd.go_back_target(ctx.paths, record), sets,
                      running is None and bool(sets) and scratch_ready(ctx.project, ctx.paths), "")


# ---------------------------------------------------------------- voice files

@dataclass(frozen=True)
class VoiceFileItem:
    name: str
    folder: str
    zip_path: str
    line: str                                    # 'voice-check-round-003-...: 64 MB'


@dataclass(frozen=True)
class VoiceFilesView:
    project_id: str
    items: Tuple[VoiceFileItem, ...]
    exports: str


def voicefiles_view(home: DataHome, project_id: str, cat: Catalog) -> Optional[VoiceFilesView]:
    ctx = open_project(home, project_id)
    if ctx is None:
        return None
    items = tuple(VoiceFileItem(name, os.path.dirname(zip_path), zip_path, cat.t("voicefile.list.row", name=name, size=size_text(size)))
                  for name, zip_path, size in vf.existing_voice_files(ctx.paths))
    return VoiceFilesView(ctx.project.id, items, ctx.paths.exports)


# ---------------------------------------------------------------- free up space

@dataclass(frozen=True)
class FreeItem:
    kind: str                                    # 'saved' or 'working': the option the terminal command takes
    round: int
    line: str
    bytes: int
    gives_up_saved_point: bool


@dataclass(frozen=True)
class FreeView:
    project_id: str
    items: Tuple[FreeItem, ...]
    notes: Tuple[str, ...]                       # what is kept for sure, in use, or not ours: said so the list is not mistaken for everything
    problem: str


def free_view(home: DataHome, project_id: str, cat: Catalog, now=None) -> Optional[FreeView]:
    ctx = open_project(home, project_id)
    if ctx is None:
        return None
    try:
        record = rd.reconcile(ctx.paths, ctx.scratch, ctx.jobs_root, ctx.project.id, now=now, write=False)
    except rd.RoundsError as error:
        return FreeView(ctx.project.id, (), (), error_text(cat, "rounds", error.code).what)
    plan = freeup.plan(ctx.paths, ctx.scratch, record)
    items = tuple(FreeItem("working" if o.kind == "folder" else "saved", o.round, free_row_text(o, cat), o.bytes, o.includes_saved_point) for o in plan.offers)
    notes: List[str] = []
    if plan.kept:
        notes.append(cat.count("rounds.free.kept", len(plan.kept), size=size_text(sum(f.size for _n, f in plan.kept))))
    if plan.busy:
        notes.append(cat.count("rounds.free.busy", plan.busy))
    if plan.unclaimed:
        notes.append(cat.count("rounds.free.unclaimed", plan.unclaimed))
    notes.append(cat.t("rounds.free.never"))
    return FreeView(ctx.project.id, items, tuple(notes), "")


# ---------------------------------------------------------------- what a button asks for (the words of the terminal command)

def _project(project_id: str) -> List[str]:
    return ["--project", project_id]


@dataclass(frozen=True)
class NewFields:
    """What the new-project form holds, as typed."""
    name: str = ""
    whose: str = ""                              # OWN, SOMEONE_ELSE, or "" until chosen
    hours: str = "1"
    given_by: str = ""
    what_to: str = ""
    when: str = ""
    withdraw: str = ""
    how_given: str = ""
    how_given_other: str = ""
    voice: str = ""                              # a starting voice id, or "" for choose later


@dataclass(frozen=True)
class EditFields:
    name: str
    hours: str
    given_by: str = ""
    what_to: str = ""
    when: str = ""
    withdraw: str = ""
    how_given: str = ""
    how_given_other: str = ""


def voice_choices(registry) -> Tuple[str, ...]:
    """The starting voice ids the new-project form offers, in the order the plan lists them."""
    return tuple(card.voice_id for card in starting_voices(registry))


def _new_form(fields: NewFields, registry) -> FormInput:
    consent = Consent(fields.given_by, fields.what_to, fields.when, fields.withdraw, fields.how_given, fields.how_given_other) if fields.whose == SOMEONE_ELSE else Consent()
    return FormInput(name=fields.name, whose_voice=fields.whose, consent=consent, hours=fields.hours, starting_voice=fields.voice or None)


def check_new(home: DataHome, registry, cat: Catalog, fields: NewFields) -> Tuple[str, ...]:
    """The sentences for everything wrong with the form (empty when it can be made). Changes nothing."""
    return new_form_problems(_new_form(fields, registry), home, registry, cat)


def new_args(fields: NewFields) -> Tuple[str, List[str]]:
    """`projects new ...` with every answer given as an option, so the flow asks only its one question (make it?), with Yes and No buttons. The values use the `--option=value` form, so a name
    that begins with two hyphens is a name and never another option."""
    argv = ["new", "--name=" + fields.name, "--hours=" + fields.hours, "--own" if fields.whose == OWN else "--someone-else"]
    if fields.whose == SOMEONE_ELSE:
        argv += ["--given-by=" + fields.given_by, "--agreed-to=" + fields.what_to, "--when=" + fields.when, "--withdraw=" + fields.withdraw, "--how-given=" + fields.how_given]
        if fields.how_given_other:
            argv.append("--how-given-other=" + fields.how_given_other)
    if fields.voice:
        argv.append("--voice=" + fields.voice)
    return "projects", argv


def edit_fields_of(project: Project) -> EditFields:
    c = project.consent
    return EditFields(project.name, _hours(project.planned_hours), c.given_by, c.what_to, c.when, c.withdraw, c.how_given, c.how_given_other)


def _edit_input(fields: EditFields) -> EditInput:
    return EditInput(fields.name, fields.hours, Consent(fields.given_by, fields.what_to, fields.when, fields.withdraw, fields.how_given, fields.how_given_other))


def check_edit(project: Project, cat: Catalog, fields: EditFields) -> Tuple[Tuple[str, ...], bool]:
    """(the sentences for everything wrong with the form, whether saving it would change anything)."""
    return edit_form_problems(project, _edit_input(fields), cat)


def edit_args(project: Project, fields: EditFields) -> Tuple[str, List[str]]:
    """`projects edit ID ...` with an option for each thing that differs from what is saved, and no other."""
    old = edit_fields_of(project)
    names = (("name", "--name="), ("hours", "--hours="), ("given_by", "--given-by="), ("what_to", "--agreed-to="), ("when", "--when="), ("withdraw", "--withdraw="),
             ("how_given", "--how-given="), ("how_given_other", "--how-given-other="))
    argv = ["edit", project.id]
    for attribute, option in names:
        if getattr(fields, attribute) != getattr(old, attribute):
            argv.append(option + getattr(fields, attribute))
    return "projects", argv


def archive_args(project_id: str) -> Tuple[str, List[str]]:
    return "projects", ["archive", project_id]


def unarchive_args(project_id: str) -> Tuple[str, List[str]]:
    return "projects", ["unarchive", project_id]


def delete_args(project_id: str) -> Tuple[str, List[str]]:
    return "projects", ["delete", project_id]


def choose_args(project_id: str, number: int) -> Tuple[str, List[str]]:
    return "rounds", ["choose", str(int(number))] + _project(project_id)


def back_args(project_id: str) -> Tuple[str, List[str]]:
    return "rounds", ["back"] + _project(project_id)


def stop_args(project_id: str) -> Tuple[str, List[str]]:
    return "rounds", ["stop"] + _project(project_id)


def start_args(project_id: str, dataset: str, minutes: Optional[int] = None) -> Tuple[str, List[str]]:
    argv = ["start", "--set", dataset]
    if minutes is not None:
        argv += ["--minutes", str(int(minutes))]
    return "rounds", argv + _project(project_id)


def note_args(project_id: str, number: int, text: str) -> Tuple[str, List[str]]:
    return "rounds", ["note", str(int(number)), "--text=" + text] + _project(project_id)


def make_args(project_id: str) -> Tuple[str, List[str]]:
    return "voicefile", ["make"] + _project(project_id)


def free_args(project_id: str, items: Sequence[FreeItem]) -> Tuple[str, List[str]]:
    """The command for the items that are ticked: each kind lists its rounds. Nothing ticked is not a command (the window keeps the button off)."""
    argv = ["free"]
    for kind in ("saved", "working"):
        rounds_for_kind = sorted({i.round for i in items if i.kind == kind})
        if rounds_for_kind:
            argv += ["--" + kind, ",".join(str(n) for n in rounds_for_kind)]
    return "rounds", argv + _project(project_id)
