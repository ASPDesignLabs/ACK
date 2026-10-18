# SPDX-License-Identifier: GPL-3.0-or-later
"""What the window shows, as plain data (plan task VS-2.1; the rule in section 3: decisions in plain Python, a thin GTK edge).

Every function here only looks: it reads the files the terminal commands read and returns words from the text catalog and numbers, so the window has nothing to decide and a plain
test run covers it. A round is described by the same function the terminal uses (`rounds_flow.round_lines`). What a button does is not here: it is a list of words for the very
command the terminal runs (`rounds choose 2 --project anna`), built by the `*_args` functions below and run by `Services.run`.

Nothing here writes. The window's own questions and the changes they lead to belong to the flows.

Five pages were added after the first six (Hear the voice, Backup, Check the tool, Updates, Problem report); they follow the same rule: a view that only looks, and the words of the terminal
command each button stands for. What a command learns that a page wants (the names of the releases it listed, the text of the report it built) reaches the window through a small callback
the flow offers (`on_releases`, `on_report`), never by reading the sentences back.
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Sequence, Tuple

from . import commands, describe, fetch, freeup, jobs, projectbackup as pb, recordings as rec, refresh as rf, reportcmd as rc, rounds as rd, update as up, voicefile as vf
from .. import __version__
from .backup_flow import remembered_folder, run_backup, standing_line
from .backupnudge import when_text
from .describe import error_text
from .envspec import EnvSpec, load_environments
from .guided_flow import GUIDED_ENVS
from .paths import DataHome, ProjectPaths
from .project import OWN, SOMEONE_ELSE, Consent, Project, list_projects
from .newproject import FormInput
from .profiles import EditInput, split
from .projects_flow import WHOSE_WORDS, _hours, edit_form_problems, new_form_problems, run_projects
from .recordings_flow import Studio, next_step as recordings_next_step, run_recordings, show_lines as recordings_lines
from .refresh_flow import run_refresh, subject_name
from .registry import Registry, ReleaseSource, load_release_source
from .reportcmd_flow import run_report
from .startvoice import voices as starting_voices
from .rounds_flow import FREE_OPTION, Open, TrainingEnv, free_row_text, round_lines, run_rounds, scratch_ready, scratch_root
from .system import RealSystem, System
from .text import Catalog, size_text
from .uninstall_flow import code_folder
from .update_flow import run_update
from .voicefile_flow import run_voicefile

PAGES = ("projects", "recordings", "rounds", "hear", "voicefile", "backup", "free", "refresh", "update", "report", "display")          # the window's pages, in the order of its list; their titles are `window.nav.<name>`
TOOLS = ("projects", "recordings", "rounds", "voicefile", "backup", "refresh", "update", "report")
TITLE_KEYS = {"projects": ("projects.title",), "recordings": ("recordings.title",), "rounds": ("rounds.title",), "voicefile": ("voicefile.title", "listen.title"),      # a heading each flow prints first: the window has its own
              "backup": ("backup.title",), "refresh": ("refresh.title",), "update": ("update.title",), "report": ("reportcmd.title",)}
MAX_NOTE_SHOWN = 500
MAX_TABLE_NAME = 200
NEXT_WORDS = {"import": "window.recordings.next_import", "wait": "window.recordings.next_wait", "finish": "window.recordings.next_finish", "set": "window.recordings.next_set"}


def no_studio() -> Tuple[None, str]:
    """The studio programs when nobody said where they are: not there."""
    return None, "absent"


# ---------------------------------------------------------------- the computer the window works on

@dataclass
class Learned:
    """What the last commands told the window beyond their sentences: the names of the releases `update check` listed (newest first) and the text of the report `report` last built.
    Both are only ever words the person has already been shown; nothing is kept on disk."""

    releases: Optional[Tuple[str, ...]] = None       # None until `update check` has listed them; () when it listed none
    report: str = ""


@dataclass
class Services:
    """Everything a flow needs, held once for the window. `run` runs one terminal command by name, with the window's IO. `source`, `networked`, `version` and `specs` are what `update` and
    `refresh` are given by their terminal fronts; a test gives its own."""

    home: DataHome
    registry: Registry
    cat: Catalog
    training: TrainingEnv
    system: System
    tools_dir: str = str(jobs.TOOLS_DIR)
    studio: Studio = no_studio
    source: Optional[ReleaseSource] = None
    networked: Callable = fetch.run_networked
    version: str = __version__
    specs: Optional[Sequence[EnvSpec]] = None
    learned: Learned = field(default_factory=Learned)

    def titles(self) -> Tuple[str, ...]:
        return tuple(self.cat.t(key) for tool in TOOLS for key in TITLE_KEYS[tool])

    def release_source(self) -> ReleaseSource:
        return self.source if self.source is not None else load_release_source()

    def environments(self) -> Sequence[EnvSpec]:
        return self.specs if self.specs is not None else load_environments()

    def _learn_releases(self, names: Sequence[str]) -> None:
        self.learned.releases = tuple(names)

    def _learn_report(self, text: str) -> None:
        self.learned.report = text

    def run(self, tool: str, argv: Sequence[str], io) -> int:
        if tool == "projects":
            return run_projects(argv, self.system, self.home, self.registry, self.cat, io)
        if tool == "recordings":
            return run_recordings(argv, self.home, self.registry, self.cat, io, studio=self.studio, system=self.system, tools_dir=self.tools_dir)
        if tool == "rounds":
            return run_rounds(argv, self.home, self.registry, self.cat, io, training=self.training, system=self.system)
        if tool == "voicefile":
            return run_voicefile(argv, self.home, self.registry, self.cat, io, training=self.training, system=self.system, tools_dir=self.tools_dir, studio=self.studio)
        if tool == "backup":
            return run_backup(argv, self.home, self.cat, io, system=self.system)
        if tool == "refresh":
            return run_refresh(argv, self.home, self.cat, io, system=self.system, registry=self.registry, specs=self.environments(), networked=self.networked, clock=time.monotonic)
        if tool == "update":
            return run_update(argv, self.cat, io, system=self.system, source=self.release_source(), networked=self.networked, tools_dir=self.tools_dir, version=self.version,
                              on_releases=self._learn_releases)
        if tool == "report":
            return run_report(argv, self.home, self.cat, io, system=self.system, on_report=self._learn_report)
        raise ValueError("unknown tool: " + tool)


def real_services(home: DataHome, registry: Registry, cat: Catalog, training: TrainingEnv, studio: Studio = no_studio) -> Services:
    return Services(home, registry, cat, training, RealSystem(), studio=studio)


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


# ---------------------------------------------------------------- recordings

@dataclass(frozen=True)
class RecordingsView:
    project_id: str
    project_name: str
    lines: Tuple[str, ...]                       # the very lines the terminal's `recordings show` prints
    next_line: str                               # one sentence on what to do next
    next_step: str                               # "import", "wait", "finish" or "set"
    listening: bool                              # the computer is listening now: the page looks again by itself
    can_listen: bool                             # recordings are waiting and nothing is listening
    can_make: bool                               # at least one recording is ready to use
    folder: str


def recordings_view(home: DataHome, project_id: str, cat: Catalog) -> Optional[RecordingsView]:
    """None when there is no such project in use. Reads the recordings' own notes and the listening job's files; changes nothing."""
    ctx = open_project(home, project_id)
    if ctx is None:
        return None
    view = rec.read_takes(ctx.paths.recordings)
    listening = rec.listening_job(ctx.jobs_root, ctx.project.id)
    lines = list(recordings_lines(view, listening, cat))
    if view.failed:
        lines.append(cat.count("progress.takes.failed", view.failed))
    step = recordings_next_step(view, listening)
    active = listening is not None and listening.active
    return RecordingsView(ctx.project.id, ctx.project.name, tuple(lines), cat.t(NEXT_WORDS[step]), step, active, view.waiting > 0 and not active, view.ready > 0, ctx.paths.recordings)


def check_import(cat: Catalog, kind: str, source: str, table: str) -> Tuple[str, ...]:
    """The sentences for everything the import form lacks (empty when it can go on). Changes nothing."""
    problems: List[str] = []
    if kind not in rec.KINDS:
        problems.append(cat.t("window.import.need_kind"))
    if not source or "\x00" in source or "\n" in source:
        problems.append(cat.t("window.import.need_source"))
    if kind == "table" and (len(table) > MAX_TABLE_NAME or any(ch in table for ch in "\r\n\x00")):
        problems.append(cat.t("window.import.bad_table"))
    return tuple(problems)


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
    kind: str                                    # 'saved', 'working', 'copies' or 'clips': the option the terminal command takes
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
    plan = freeup.plan(ctx.paths, ctx.scratch, record, now)
    items = tuple(FreeItem(FREE_OPTION[o.kind], o.round, free_row_text(o, cat), o.bytes, o.includes_saved_point) for o in plan.offers)
    notes: List[str] = []
    if plan.kept:
        notes.append(cat.count("rounds.free.kept", len(plan.kept), size=size_text(sum(f.size for _n, f in plan.kept))))
    if plan.busy:
        notes.append(cat.count("rounds.free.busy", plan.busy))
    if plan.unclaimed:
        notes.append(cat.count("rounds.free.unclaimed", plan.unclaimed))
    if plan.old_listenings:
        notes.insert(0, cat.count("rounds.free.old_notice", plan.old_listenings, days=freeup.OLD_AFTER_DAYS))
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


def import_args(project_id: str, kind: str, source: str, table: str = "") -> Tuple[str, List[str]]:
    """`recordings import --kind=K [--table=T] --project P -- SOURCE`: every answer given as an option, so the flow shows what it found and asks only its one question, with Yes and No buttons.
    The values use the `--option=value` form and the source comes after `--`, so a name that begins with hyphens is a name and never another option. A table name goes only with the table kind."""
    argv = ["import", "--kind=" + kind]
    if kind == "table" and table:
        argv.append("--table=" + table)
    return "recordings", argv + _project(project_id) + ["--", source]


def get_model_args() -> Tuple[str, List[str]]:
    """`recordings model`: look for the listening model and, if it is not here, say where it comes from and ask before downloading it. It belongs to no project."""
    return "recordings", ["model"]


def finish_args(project_id: str) -> Tuple[str, List[str]]:
    return "recordings", ["finish"] + _project(project_id)


def preview_set_args(project_id: str) -> Tuple[str, List[str]]:
    return "recordings", ["set", "--preview"] + _project(project_id)


def make_set_args(project_id: str) -> Tuple[str, List[str]]:
    return "recordings", ["set"] + _project(project_id)


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
    for kind in FREE_OPTION.values():
        rounds_for_kind = sorted({i.round for i in items if i.kind == kind})
        if rounds_for_kind:
            argv += ["--" + kind, ",".join(str(n) for n in rounds_for_kind)]
    return "rounds", argv + _project(project_id)


# ---------------------------------------------------------------- backup


@dataclass(frozen=True)
class BackupItem:
    name: str
    path: str
    line: str                                    # 'when, size, name': the terminal's own row


@dataclass(frozen=True)
class BackupView:
    project_id: str
    project_name: str
    standing: str                                # whether the project has been backed up, and whether anything precious changed since ('' for a project with nothing to lose)
    folder: str                                  # where the next backup goes when no other folder is chosen
    how: str                                     # "remembered" (the one used last) or "default" (the tool's own backups folder)
    items: Tuple[BackupItem, ...]                # the backups found in that folder for this project, newest first
    problem: str                                 # the record of rounds could not be read: nothing else is shown


def backup_view(home: DataHome, project_id: str, cat: Catalog, now=None) -> Optional[BackupView]:
    """None when there is no such project. Reads the project's own files and the folder of backups; changes nothing."""
    ctx = open_project(home, project_id)
    if ctx is None:
        return None
    folder, how = remembered_folder(home, ctx.project.id)
    try:
        record = rd.reconcile(ctx.paths, ctx.scratch, ctx.jobs_root, ctx.project.id, now=now, write=False)
    except rd.RoundsError as error:
        return BackupView(ctx.project.id, ctx.project.name, "", folder, how, (), error_text(cat, "rounds", error.code).what)
    standing = standing_line(pb.standing(home, ctx.paths, ctx.project.id, record), ctx.project.name, cat) or ""
    items = tuple(BackupItem(str(b["name"]), str(b["path"]), cat.t("backup.list_row", when=when_text(str(b["created"])), size=size_text(int(b["size"])), name=b["name"]))
                  for b in pb.list_backups(folder, ctx.project.id))
    return BackupView(ctx.project.id, ctx.project.name, standing, folder, how, items, "")


FOLDER_WORDS = {"remembered": "window.backup.folder_remembered", "default": "window.backup.folder_default"}


def backup_folder_line(cat: Catalog, how: str, folder: str, chosen: bool = False) -> str:
    """Where the next backup goes, and why that folder: the one the person chose in this window, the one used last, or the tool's own."""
    return cat.t("window.backup.folder_chosen", folder=folder) if chosen else cat.t(FOLDER_WORDS[how], folder=folder)


def check_backup_folder(cat: Catalog, folder: str) -> Tuple[str, ...]:
    """The sentence for a folder that cannot be the place to back up to (empty when it can). The terminal's command checks the room, the drive and the rest when it shows its plan."""
    if not os.path.isabs(folder) or "\x00" in folder or "\n" in folder:
        return (cat.t("window.backup.need_folder"),)
    return ()


def backup_now_args(project_id: str, folder: str = "", saved_points: bool = True) -> Tuple[str, List[str]]:
    """`backup now --project P [--to=FOLDER] [--without-saved-points]`. A folder is named only when the person chose one; otherwise the command uses the one used last, or its own."""
    argv = ["now"] + _project(project_id)
    if folder:
        argv.append("--to=" + folder)
    if not saved_points:
        argv.append("--without-saved-points")
    return "backup", argv


def backup_verify_args(path: str) -> Tuple[str, List[str]]:
    """`backup verify -- FILE`: read a backup all the way through. The path comes after `--`, so a name that begins with hyphens is a name and never another option."""
    return "backup", ["verify", "--", path]


def backup_restore_args(path: str) -> Tuple[str, List[str]]:
    """`backup restore -- FILE`: the command shows what it would add and asks first; it only ever adds."""
    return "backup", ["restore", "--", path]


# ---------------------------------------------------------------- refresh (checking the tool)

@dataclass(frozen=True)
class ProgramsChoice:
    id: str                                      # "" for every set that is set up, otherwise a set's id (the option `--programs` takes)
    label: str


def programs_choices(cat: Catalog, specs: Sequence[EnvSpec]) -> Tuple[ProgramsChoice, ...]:
    """What the rebuild button can be pointed at: every set of programs that is set up, or one of them, named the way the terminal names it and in its order (the small set first)."""
    ordered = sorted(specs, key=lambda s: (GUIDED_ENVS.index(s.id) if s.id in GUIDED_ENVS else len(GUIDED_ENVS), s.id))
    return (ProgramsChoice("", cat.t("window.refresh.all_programs")),) + tuple(ProgramsChoice(s.id, subject_name(cat, rf.PROGRAMS, s.id)) for s in ordered)


def refresh_check_args(quick: bool = False) -> Tuple[str, List[str]]:
    return "refresh", ["check"] + (["--quick"] if quick else [])


def refresh_repair_args() -> Tuple[str, List[str]]:
    return "refresh", ["repair"]


def refresh_rebuild_args(programs: str = "") -> Tuple[str, List[str]]:
    return "refresh", ["rebuild"] + (["--programs=" + programs] if programs else [])


def refresh_older_args(remove: bool = False) -> Tuple[str, List[str]]:
    return "refresh", ["older"] + (["--remove"] if remove else [])


# ---------------------------------------------------------------- update

@dataclass(frozen=True)
class UpdateView:
    here: Tuple[str, ...]                        # where this copy is and, for a copy that is not a plain git copy, that it cannot be compared with a release
    releases: Optional[Tuple[str, ...]]          # the releases the last look listed, newest first; None until the person has looked


def update_view(services: Services) -> UpdateView:
    """Looks at this copy's own files only; it contacts nothing."""
    cat = services.cat
    here = code_folder(services.tools_dir)
    lines = [cat.t("update.here", version=services.version, folder=here)]
    if up.head_commit(here) is None:
        lines.append(cat.t("update.here_no_git"))
    return UpdateView(tuple(lines), services.learned.releases)


def update_check_args() -> Tuple[str, List[str]]:
    """`update check`: says what it will ask github.com and asks first. Nothing is contacted before the person says yes."""
    return "update", ["check"]


def update_get_args(release: str) -> Tuple[str, List[str]]:
    """`update get -- RELEASE`: fetches one release into a new folder beside this copy, after saying what it will ask and asking."""
    return "update", ["get", "--", release]


# ---------------------------------------------------------------- the problem report

MAX_REPORT_FILE_NAME = 100
RECENT_TASKS = 10
LAST_TASK = "last"


@dataclass(frozen=True)
class ReportFields:
    """What the report form holds. `problem` is a name the catalog has words for (`update/unreachable`) and is filled in only from a failure the window itself showed."""
    step: str = ""
    problem: str = ""
    job: str = ""                                # "", "last" or a task's id
    include_log: bool = False


@dataclass(frozen=True)
class Failure:
    """The last task that ended because something failed after it began: what it was doing, and the one problem it told the person about (empty when it told none or several)."""
    step: str
    problem: str


def failure_about(tool: str, argv: Sequence[str], shown: Sequence[Tuple[str, str]]) -> Failure:
    """The very rule the terminal's closing lines use (core/reportcmd.py): the step is the command and its first plain word, and a problem is named only when exactly one was told."""
    problem = "%s/%s" % shown[0] if len(shown) == 1 and rc.PROBLEM_NAME.match("%s/%s" % shown[0]) else ""
    return Failure(rc.step_of(tool, argv), problem)


def job_choices(home: DataHome, cat: Catalog) -> Tuple[Tuple[str, str], ...]:
    """(the value for `--job`, the words), for: no task, the newest, and then the newest few by name. A task is named by its id, its kind and how it ended; nothing of what it did."""
    found = jobs.list_jobs(home.jobs).jobs
    rows = [("", cat.t("window.report.no_task"))]
    if found:
        rows.append((LAST_TASK, cat.t("window.report.newest_task")))
    for info in reversed(found[-RECENT_TASKS:]):
        rows.append((info.id, cat.t("window.report.task_row", id=info.id, kind=info.spec.kind, status=describe.status_text(cat, info.status))))
    return tuple(rows)


def report_args(fields: ReportFields, save_to: str = "") -> Tuple[str, List[str]]:
    """`report show ...` or, with a file, `report save --to=FILE ...`: one option for each thing the person gave. The end of a task's log is asked for only together with a task."""
    argv = ["save" if save_to else "show"]
    if fields.step.strip():
        argv.append("--step=" + fields.step.strip()[:rc.MAX_STEP])
    if fields.problem:
        argv.append("--problem=" + fields.problem)
    if fields.job:
        argv.append("--job=" + fields.job)
        if fields.include_log:
            argv.append("--include-log")
    if save_to:
        argv.append("--to=" + save_to)
    return "report", argv


def check_report_save(cat: Catalog, folder: str, name: str) -> Tuple[Tuple[str, ...], str]:
    """(what is wrong, the whole path). The folder is one the person chose, and the name is only a file name; the place is then held to the terminal's own rules (the folder exists and nothing
    is there already). Changes nothing."""
    problems: List[str] = []
    cleaned = name.strip()
    if not os.path.isabs(folder):
        problems.append(cat.t("window.report.need_folder"))
    if not cleaned:
        problems.append(cat.t("window.report.need_name"))
    elif len(cleaned) > MAX_REPORT_FILE_NAME or cleaned in (".", "..") or any(ch in cleaned for ch in "/\\\x00\r\n"):
        problems.append(cat.t("window.report.bad_name", limit=MAX_REPORT_FILE_NAME))
    if problems:
        return tuple(problems), ""
    path = folder.rstrip("/") + "/" + cleaned
    try:
        rc.check_place(path, False)
    except rc.ReportError as error:
        return (error_text(cat, "reportcmd", error.code).what,), ""
    return (), path


# ---------------------------------------------------------------- hearing the voice

@dataclass(frozen=True)
class HearRound:
    number: int
    line: str
    chosen: bool


@dataclass(frozen=True)
class HearView:
    project_id: str
    project_name: str
    voices: Tuple[VoiceFileItem, ...]            # the voice files made so far, newest last as the terminal lists them
    rounds: Tuple[HearRound, ...]                # the rounds a voice can honestly be made from now
    running: Optional[int]                       # a round is training: hearing a round waits for it to end
    folder: str                                  # where the small sound files are kept with the project
    problem: str


def hear_view(home: DataHome, project_id: str, cat: Catalog, now=None) -> Optional[HearView]:
    """None when there is no such project. Looks at the voice files and the record of rounds; changes nothing."""
    ctx = open_project(home, project_id)
    if ctx is None:
        return None
    voices = tuple(VoiceFileItem(name, os.path.dirname(zip_path), zip_path, cat.t("voicefile.list.row", name=name, size=size_text(size))) for name, zip_path, size in vf.existing_voice_files(ctx.paths))
    try:
        record = rd.reconcile(ctx.paths, ctx.scratch, ctx.jobs_root, ctx.project.id, now=now, write=False)
    except rd.RoundsError as error:
        return HearView(ctx.project.id, ctx.project.name, voices, (), None, ctx.paths.listening, error_text(cat, "rounds", error.code).what)
    running = rd.active(record)
    hearable = () if running is not None else tuple(
        HearRound(r.number, cat.t("window.hear.round_chosen" if r.number == record.current else "window.hear.round_row", number=r.number, minutes=rd.trained_minutes(record, r.number)),
                  r.number == record.current)
        for r in record.rounds if rd.checkpoint_status(ctx.paths, r) == "ok" and os.path.isfile(vf.settings_file(ctx.paths, r.number)) and not os.path.islink(vf.settings_file(ctx.paths, r.number)))
    return HearView(ctx.project.id, ctx.project.name, voices, hearable, running.number if running is not None else None, ctx.paths.listening, "")


def listen_voice_args(project_id: str, voice_name: str) -> Tuple[str, List[str]]:
    """`voicefile listen --project P --folder=NAME`: hear a voice file that was made. The command shows what it will do and asks first."""
    return "voicefile", ["listen"] + _project(project_id) + ["--folder=" + voice_name]


def listen_round_args(project_id: str, number: int) -> Tuple[str, List[str]]:
    """`voicefile listen --project P --round N`: hear a round straight, with no zip file made."""
    return "voicefile", ["listen"] + _project(project_id) + ["--round", str(int(number))]
