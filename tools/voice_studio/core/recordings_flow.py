# SPDX-License-Identifier: GPL-3.0-or-later
"""The terminal front for a project's recordings (plan task VS-2.10); the window runs these same flows: see what is in the project, bring voice data in, let the computer listen to it,
and make a training set from it.

Four kinds of data can be brought in (core/recordings.py names them): an ACK package, a folder of audio files each with a text file, a folder of audio files with one table of
sentences, or a folder of audio files alone. The kind is always said by the person (`--kind`), never guessed from the files, because a wrong guess would quietly give a recording the
wrong words. Bringing in is Freeform Studio's own code, so the two programs cannot disagree.

Rules for a person who has to be able to trust it, the same as the other fronts. `show` only looks. `import` shows what it found and what it would add, checks there is room, and asks
before it writes anything; a folder or package that is chosen is only ever read. `finish` starts the listening as a job of its own (closing the terminal does not stop it) after showing what it will do and asking.
`set` shows what the training set would hold before it writes one, asks, and writes only to a new folder. Nothing is ever deleted here, except the checked copy of a package that
this very command made for itself when the person then said no (the original is never touched). Exit codes: 0 done, 1 something failed, 2 nothing was done (declined, nobody to ask, an
option or a name that could not be told, nothing that could be done).
"""
from __future__ import annotations

import math
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Callable, List, Optional, Sequence, Tuple

from freeform_studio import files_import
from freeform_studio.ack_import import ImportProblem, NotEnoughRoom
from freeform_studio.privacy import sync_warning

from . import ackimport, commands, envfind, fetch, joblines, jobs, progress as prog, recordings as rec
from .cliargs import ArgError, parse_args
from .consent import load_consent, make_consent, merge_consent, save_consent
from .envbuild import EnvPaths
from .paths import DataHome, ProjectPaths
from .projects_flow import EXIT_NOTHING_DONE, EXIT_OK, EXIT_PROBLEM, resolve_project, say_bad_arg
from .registry import Registry
from .rounds_flow import Open, _confirmed, _say_parts, scratch_ready, scratch_root
from .setup_flow import IO
from .voices_flow import Download
from .system import RealSystem, System
from .text import Catalog, size_text

RECORDINGS_COMMAND = "python3 -m voice_studio.recordings"
ROUNDS_COMMAND = "python3 -m voice_studio.rounds"
MODEL_COMMAND = RECORDINGS_COMMAND + " model"
BUILDENV_STUDIO_COMMAND = "python3 -m voice_studio.buildenv studio"
COMMANDS = ("show", "import", "finish", "model", "set", "help")
SHOW_NEXT = {"import": "recordings.show.next_import", "finish": "recordings.show.next_finish", "set": "recordings.show.next_set"}      # what `show` suggests next, besides waiting
YES = {"--yes": "yes", "-y": "yes"}
PROJECT = {"--project": "project"}
IMPORT_VALUES = {**PROJECT, "--kind": "kind", "--table": "table"}
SET_FLAGS = {**YES, "--preview": "preview"}
SET_VALUES = {**PROJECT, "--max-gain-db": "gain"}
OPTIONS = {"show": frozenset(PROJECT), "import": frozenset(YES) | frozenset(IMPORT_VALUES), "finish": frozenset(YES) | frozenset(PROJECT), "model": frozenset(YES),
           "set": frozenset(SET_FLAGS) | frozenset(SET_VALUES)}                              # the checklist is held to these
MAX_ROWS_SHOWN = 20
MAX_NOTES_SHOWN = 10
PREVIEW_TIMEOUT_S = 900.0
BUILD_TIMEOUT_S = 3600.0
STATUS_WORDS = {"ready": "recordings.status.ready", "waiting": "recordings.status.waiting", "failed": "recordings.status.failed", "other": "recordings.status.other"}
Studio = Callable[[], Tuple[Optional[EnvPaths], str]]
Speech = Callable[[], Tuple[Optional[str], str]]


def status_group(status: str) -> str:
    """Which of the four words a recording's status is shown as."""
    if status == rec.READY:
        return "ready"
    if status in rec.WAITING:
        return "waiting"
    if status == rec.FAILED:
        return "failed"
    return "other"


def minutes_of(seconds: float) -> str:
    return prog.minutes_text(seconds / 60.0)


def _open(parsed, home: DataHome, cat: Catalog, io: IO) -> Tuple[Optional[Open], int]:
    project, code = resolve_project(parsed.values.get("project"), home, cat, io)
    if project is None:
        return None, code
    paths = ProjectPaths(home.projects + "/" + project.id)
    return Open(project, paths, scratch_root(project, paths), home.jobs), EXIT_OK


def _command(verb: str, project_id: str, *more: str) -> str:
    return " ".join([RECORDINGS_COMMAND, verb] + list(more) + ["--project", project_id])


# ---------------------------------------------------------------- show

def show_lines(view: rec.TakesView, listening: Optional[rec.Listening], cat: Catalog) -> List[str]:
    """What is said about the recordings in a project: the counts, each recording (the newest first), and the listening job. The terminal prints it and the window draws it."""
    lines: List[str] = []
    if view.total == 0:
        lines.append(cat.t("recordings.show.none"))
    else:
        lines.append(cat.count("recordings.show.total", view.total))
        if view.minutes > 0:
            lines.append(cat.t("recordings.show.length", minutes=prog.minutes_text(view.minutes)))
        lines.append(cat.t("recordings.show.counts", ready=view.ready, waiting=view.waiting, failed=view.failed, other=view.other))
        for row in view.rows[:MAX_ROWS_SHOWN]:
            status = cat.t(STATUS_WORDS[status_group(row.status)])
            if row.seconds is None:
                lines.append("  " + cat.t("recordings.show.row_unknown", label=row.label or row.id, status=status))
            else:
                lines.append("  " + cat.t("recordings.show.row", label=row.label or row.id, status=status, minutes=minutes_of(row.seconds)))
        if view.total > MAX_ROWS_SHOWN:
            lines.append("  " + cat.t("recordings.show.more", count=view.total - MAX_ROWS_SHOWN))
    if view.unreadable:
        lines.append(cat.count("recordings.show.unreadable", view.unreadable))
    if listening is not None and listening.active:
        lines.append(cat.t("recordings.show.listening_now"))
        if listening.doing and listening.percent is not None:
            lines.append("  " + cat.t("recordings.show.listening_on", name=listening.doing, percent=listening.percent))
    elif listening is not None and view.waiting > 0:
        lines.append(cat.t("recordings.show.listening_stopped", state=cat.t("job.status." + listening.job.status.value)))
    return lines


def next_step(view: rec.TakesView, listening: Optional[rec.Listening]) -> str:
    """One of "import", "wait", "finish", "set": the next thing that makes sense, by what is in the project."""
    if view.total == 0:
        return "import"
    if listening is not None and listening.active:
        return "wait"
    if view.waiting > 0:
        return "finish"
    return "set" if view.ready > 0 else "import"


def _show(args: Sequence[str], home: DataHome, cat: Catalog, io: IO) -> int:
    try:
        parsed = parse_args(args, flags={}, values=PROJECT, max_words=0)
    except ArgError as error:
        return say_bad_arg(error, cat, io)
    io.say(cat.t("recordings.title"))
    ctx, code = _open(parsed, home, cat, io)
    if ctx is None:
        return code
    view = rec.read_takes(ctx.paths.recordings)
    listening = rec.listening_job(ctx.jobs_root, ctx.project.id)
    io.say(cat.t("recordings.show.heading", name=ctx.project.name))
    for line in show_lines(view, listening, cat):
        io.say(line)
    if view.failed:
        io.say(cat.count("progress.takes.failed", view.failed))
    step = next_step(view, listening)
    if step == "wait":
        io.say(cat.t("recordings.show.next_wait"))
    else:
        command = _command("import", ctx.project.id, "SOURCE", "--kind", "KIND") if step == "import" else _command(step, ctx.project.id)
        io.say(cat.t(SHOW_NEXT[step], command=command))
    return EXIT_OK


# ---------------------------------------------------------------- import

def _kind_lines(cat: Catalog) -> List[str]:
    return ["  %s: %s %s" % (kind, cat.t("recordings.kind." + kind), cat.t("recordings.kind_help." + kind)) for kind in rec.KINDS]


def plan_lines(plan: files_import.Plan, cat: Catalog) -> List[str]:
    """What a folder import found and would add, then the notes about single files. The terminal prints it and the window draws it."""
    lines = [cat.t("recordings.import.looked_at", name=plan.source_name, kind=cat.t("recordings.kind." + plan.kind)),
             cat.count("recordings.import.found", len(plan.items))]
    new = plan.to_import
    if new:
        lines.append(cat.count("recordings.import.will_add", len(new), minutes=minutes_of(plan.seconds_new)))
        if plan.kind == "audio":
            lines.append(cat.t("recordings.import.no_sentences_asked"))
        elif plan.with_text == 0:
            lines.append(cat.t("recordings.import.no_sentences"))
        else:
            lines.append(cat.count("recordings.import.with_sentences", plan.with_text))
            if plan.with_text < len(new):
                lines.append(cat.count("recordings.import.without_sentences", len(new) - plan.with_text))
            lines.append(cat.t("recordings.import.sentences_note"))
    for state in ("already", "duplicate", "unusable"):
        if plan.count(state):
            lines.append(cat.count("recordings.import.%s" % state, plan.count(state)))
    for problem in plan.problems[:MAX_NOTES_SHOWN]:
        key = "recordings.note." + problem.code if problem.code in files_import.PROBLEM_CODES else "recordings.note.other"
        lines.append("  " + cat.t(key, what=problem.what[:80], detail=problem.detail[:80], code=problem.code))
    if len(plan.problems) > MAX_NOTES_SHOWN:
        lines.append("  " + cat.t("recordings.import.more_notes", count=len(plan.problems) - MAX_NOTES_SHOWN))
    return lines


def package_lines(summary: ackimport.PackageSummary, cat: Catalog) -> List[str]:
    """What an ACK package holds and what adding it would do."""
    lines = [cat.t("recordings.import.looked_at", name=summary.name, kind=cat.t("recordings.kind.package")), cat.count("recordings.import.sessions", len(summary.sessions))]
    for session in summary.sessions[:MAX_ROWS_SHOWN]:
        lines.append("  " + cat.t("recordings.import.session_row", label=session.label or session.id, mode=cat.t("ackimport.mode." + session.mode),
                                   minutes=minutes_of(session.seconds), state=cat.t("ackimport.state." + session.state)))
    if len(summary.sessions) > MAX_ROWS_SHOWN:
        lines.append("  " + cat.t("recordings.import.more_notes", count=len(summary.sessions) - MAX_ROWS_SHOWN))
    for note in summary.warnings[:MAX_NOTES_SHOWN]:
        lines.append(cat.t("recordings.note_line", text=note))
    return lines


def _room_short(need_mb: float, free_mb: float, spare_mb: float, cat: Catalog) -> str:
    mib = 1024 * 1024
    return cat.t("recordings.import.no_room", need=size_text(int(need_mb * mib)), spare=size_text(int(spare_mb * mib)), free=size_text(int(free_mb * mib)))


def _import(args: Sequence[str], home: DataHome, plan_files: Callable[..., files_import.Plan], cat: Catalog, io: IO) -> int:
    try:
        parsed = parse_args(args, flags=YES, values=IMPORT_VALUES, max_words=1)
    except ArgError as error:
        return say_bad_arg(error, cat, io)
    io.say(cat.t("recordings.title"))
    kind = parsed.values.get("kind")
    if not parsed.words:
        io.say(cat.t("recordings.import.which_source", example="%s import ~/Documents/voice-files --kind pairs" % RECORDINGS_COMMAND))
        return EXIT_NOTHING_DONE
    if kind is None:
        io.say(cat.t("recordings.import.which_kind"))
        for line in _kind_lines(cat):
            io.say(line)
        return EXIT_NOTHING_DONE
    if kind not in rec.KINDS:
        io.say(cat.t("recordings.import.kind_unknown", kind=kind[:40], kinds=", ".join(rec.KINDS)))
        return EXIT_NOTHING_DONE
    if parsed.values.get("table") is not None and kind != "table":
        io.say(cat.t("recordings.import.table_only"))
        return EXIT_NOTHING_DONE
    ctx, code = _open(parsed, home, cat, io)
    if ctx is None:
        return code
    source = parsed.words[0]
    if kind == "package":
        return _import_package(parsed, source, ctx, cat, io)
    plan = plan_files(Path(source), kind, Path(ctx.paths.recordings), table=parsed.values.get("table", ""))
    return _import_files(parsed, plan, ctx, cat, io)


def _note_sync(recordings: str, cat: Catalog, io: IO) -> None:
    warning = sync_warning(Path(recordings), "Your recordings folder")
    if warning:
        io.say(cat.t("recordings.note_line", text=warning))


def _import_files(parsed, plan: files_import.Plan, ctx: Open, cat: Catalog, io: IO) -> int:
    for line in plan_lines(plan, cat):
        io.say(line)
    if not plan.to_import:
        io.say(cat.t("recordings.import.nothing_new"))
        return EXIT_OK
    _note_sync(ctx.paths.recordings, cat, io)
    if not plan.enough_room:
        io.say(_room_short(plan.need_mb, plan.free_mb, plan.min_free_mb, cat))
        return EXIT_NOTHING_DONE                                          # said in words, with nothing written; --yes does not get past this
    declined = _confirmed(parsed, cat.count("recordings.import.question_files", len(plan.to_import), name=ctx.project.name), cat, io)
    if declined is not None:
        return declined
    try:
        result = files_import.apply_import(plan)
    except NotEnoughRoom as exc:
        _say_parts(cat, io, "ackimport", "no_room", str(exc))
        return EXIT_PROBLEM
    except ImportProblem as exc:
        _say_parts(cat, io, "ackimport", "problem", str(exc))
        return EXIT_PROBLEM
    except OSError as exc:
        _say_parts(cat, io, "ackimport", "copy_failed", exc.strerror or type(exc).__name__)
        return EXIT_PROBLEM
    if result.clips:
        io.say(cat.count("recordings.import.done_files", result.clips))
        io.say(cat.count("recordings.import.made", len(result.created)))
    for skipped in result.skipped[:MAX_NOTES_SHOWN]:
        io.say("  " + cat.t("recordings.import.skipped_row", name=skipped.rel[:80], reason=cat.t("recordings.reason." + skipped.reason)))
    if result.skipped:
        io.say(cat.count("recordings.import.skipped", len(result.skipped)))
    if not result.clips:
        io.say(cat.t("recordings.import.none_added"))
        return EXIT_PROBLEM
    io.say(cat.t("recordings.import.next", command=_command("finish", ctx.project.id)))
    return EXIT_OK


def _import_package(parsed, source: str, ctx: Open, cat: Catalog, io: IO) -> int:
    try:
        prepared = ackimport.prepare(source, Path(ctx.paths.recordings))
    except ackimport.AckImportError as error:
        _say_parts(cat, io, "ackimport", error.code, error.detail)
        for problem in error.problems[:MAX_NOTES_SHOWN]:
            io.say("  " + problem)
        return EXIT_PROBLEM
    summary = prepared.summary
    for line in package_lines(summary, cat):
        io.say(line)
    if summary.to_add == 0:
        ackimport.discard_copy(prepared)
        io.say(cat.t("recordings.import.nothing_new"))
        return EXIT_OK
    if summary.sync_warning:
        io.say(cat.t("recordings.note_line", text=summary.sync_warning))
    if not summary.enough_room:
        ackimport.discard_copy(prepared)
        io.say(_room_short(summary.need_mb, summary.free_mb, summary.min_free_mb, cat))
        return EXIT_NOTHING_DONE
    declined = _confirmed(parsed, cat.count("recordings.import.question_package", summary.to_add, name=ctx.project.name), cat, io)
    if declined is not None:
        ackimport.discard_copy(prepared)
        return declined
    try:
        created = ackimport.add(prepared)
    except ackimport.AckImportError as error:
        _say_parts(cat, io, "ackimport", error.code, error.detail)
        return EXIT_PROBLEM
    io.say(cat.count("recordings.import.made", len(created)))
    io.say(cat.t("recordings.import.next", command=_command("finish", ctx.project.id)))
    return EXIT_OK


# ---------------------------------------------------------------- finish: let the computer listen

def _finish(args: Sequence[str], home: DataHome, registry: Registry, studio: Studio, speech: Speech, tools_dir: str, now: Optional[datetime], start: Callable, cat: Catalog, io: IO) -> int:
    try:
        parsed = parse_args(args, flags=YES, values=PROJECT, max_words=0)
    except ArgError as error:
        return say_bad_arg(error, cat, io)
    io.say(cat.t("recordings.title"))
    ctx, code = _open(parsed, home, cat, io)
    if ctx is None:
        return code
    view = rec.read_takes(ctx.paths.recordings)
    if view.waiting == 0:
        io.say(cat.t("recordings.finish.nothing_waiting"))
        if view.failed:
            io.say(cat.count("progress.takes.failed", view.failed))
        return EXIT_OK
    listening = rec.listening_job(ctx.jobs_root, ctx.project.id)
    if listening is not None and listening.active:
        io.say(cat.t("recordings.finish.already", command=_command("show", ctx.project.id)))
        return EXIT_NOTHING_DONE
    env, state = studio()
    if env is None:
        io.say(cat.t("recordings.finish.no_environment", state=cat.t("env.state." + state), command=BUILDENV_STUDIO_COMMAND))
        return EXIT_NOTHING_DONE
    model, why = speech()
    if model is None:
        own, hub = envfind.speech_places(home)
        if why == "incomplete":
            io.say(cat.t("recordings.finish.model_incomplete", folder=own, command=MODEL_COMMAND))
        else:
            io.say(cat.t("recordings.finish.no_model", command=MODEL_COMMAND))
            io.say(cat.t("recordings.finish.model_looked", own=own, hub=hub))
        return EXIT_NOTHING_DONE
    io.say(cat.count("recordings.finish.plan_count", view.waiting))
    io.say("  " + cat.t("recordings.finish.plan_how"))
    io.say("  " + cat.t("recordings.finish.plan_time"))
    declined = _confirmed(parsed, cat.t("recordings.finish.question"), cat, io)
    if declined is not None:
        return declined
    spec = commands.process_command(env, tools_dir, ctx.paths.recordings, model, "cpu").job(ctx.project.id)
    started = start(ctx.jobs_root, spec, now)
    io.say(cat.t("recordings.finish.started", job=started.id))
    io.say(cat.t("recordings.finish.follow", command=_command("show", ctx.project.id)))
    return EXIT_OK


# ---------------------------------------------------------------- model: get the listening model

def _model(args: Sequence[str], home: DataHome, registry: Registry, speech: Speech, sleep: Callable[[float], None], clock: Callable[[], float], fetcher: Optional[Callable],
           now: Optional[datetime], cat: Catalog, io: IO) -> int:
    try:
        parsed = parse_args(args, flags=YES, values={}, max_words=0)
    except ArgError as error:
        return say_bad_arg(error, cat, io)
    io.say(cat.t("recordings.title"))
    found, _why = speech()
    if found is not None:
        io.say(cat.t("recordings.model.ready", folder=found))
        return EXIT_OK
    files = envfind.speech_files(registry)
    if not files or any(item.pin_problems() for item in files):
        io.say(cat.t("recordings.model.not_pinned"))
        return EXIT_NOTHING_DONE
    folder = Path(envfind.speech_places(home)[0])
    todo = [item for item in files if not fetch.is_fetched(item, folder)]
    total = sum(item.size_bytes or 0 for item in todo)
    site = next((item.url.split("/")[2] for item in todo if item.url), "-")
    io.say(cat.t("recordings.model.about", size=size_text(total), site=site, folder=str(folder)))
    declined = _confirmed(parsed, cat.t("recordings.model.question"), cat, io)
    if declined is not None:
        return declined
    try:
        save_consent(Path(home.consent_file), merge_consent(load_consent(Path(home.consent_file)), make_consent(todo, now=now)))
    except OSError as error:                                      # nothing is downloaded on a yes that could not be kept
        io.say(cat.t("voices.get.agree_not_saved"))
        io.say("  " + cat.t("cli.technical", detail=error.strerror or type(error).__name__))
        return EXIT_PROBLEM
    io.say(cat.t("recordings.model.agree_saved"))
    consent = load_consent(Path(home.consent_file))
    io.say(cat.t("voices.get.downloading", size=size_text(total), site=site))
    shown = Download(cat, io)
    before = 0
    try:
        for item in todo:
            fetch.fetch_patiently(item, folder, consent, on_wait=shown.wait, on_back=shown.back, sleep=sleep, clock=clock, fetcher=fetcher,
                                  progress=lambda done, size, base=before: shown.progress(base + done, total))
            before += item.size_bytes or 0
    except fetch.FetchError as error:
        _say_parts(cat, io, "fetch", error.code, error.detail)
        return EXIT_PROBLEM
    except KeyboardInterrupt:                                     # what arrived is kept, and the same command carries on
        io.say(cat.t("voices.interrupted"))
        return EXIT_PROBLEM
    found, _why = speech()
    if found is None:                                             # every file was fetched and checked one by one, so this is not expected; say so rather than claim success
        io.say(cat.t("recordings.model.not_there", folder=str(folder)))
        return EXIT_PROBLEM
    io.say(cat.t("recordings.model.done", folder=found))
    io.say(cat.t("recordings.model.next", command=_command("finish", "PROJECT")))
    return EXIT_OK


# ---------------------------------------------------------------- set: make a training set

def dataset_lines(summary: joblines.DatasetSummary, cat: Catalog) -> List[str]:
    """What the dataset builder said, in plain words: the result, what the set holds, what was left out and why, then its own notes."""
    lines = [cat.t("dataset.result." + summary.result)]
    if summary.ok or summary.result == "problems":
        lines.append(cat.t("recordings.set.holds", count=summary.pieces, minutes=prog.minutes_text(summary.minutes)))
    if summary.left_out:
        lines.append(cat.t("recordings.set.left_out", count=summary.left_out))
    for kind, count in summary.reasons:
        lines.append("  " + cat.t("recordings.set.reason_row", count=count, reason=cat.t("dataset.reason." + kind)))
    for flag, count in summary.flags[:5]:
        lines.append("  " + cat.t("recordings.set.flag_row", count=count, flag=cat.t("dataset.flag." + flag) if flag in joblines.KNOWN_FLAGS else joblines.flag_name(flag)))
    for note in summary.warnings + summary.problems:
        lines.append(cat.t("recordings.note_line", text=note))
    return lines


def _gain(text: Optional[str]) -> Tuple[Optional[float], bool]:
    """(the most a quiet piece may be turned up, whether the text was a good number). No text is fine: the builder's own default is used."""
    if text is None:
        return None, True
    try:
        value = float(text) if text.isascii() else math.nan
    except ValueError:
        return None, False
    if not math.isfinite(value) or not 0 <= value <= commands.MAX_GAIN_LIMIT_DB:
        return None, False
    return value, True


def _run_builder(system: System, command: commands.Command, timeout: float) -> Tuple[Optional[joblines.DatasetSummary], str]:
    """Run a dataset command to its end and read its closing line: (the summary or None, the last of what it said when there is none)."""
    done = system.run(command.argv, timeout=timeout, cwd=command.cwd)
    if done is None:
        return None, ""
    summary = joblines.dataset_summary(done.stdout.splitlines())
    tail = "" if summary is not None else " ".join((done.stderr or done.stdout or "").strip().splitlines()[-2:])[:200]
    return summary, tail


def _set(args: Sequence[str], home: DataHome, studio: Studio, tools_dir: str, now: Optional[datetime], system: System, cat: Catalog, io: IO) -> int:
    try:
        parsed = parse_args(args, flags=SET_FLAGS, values=SET_VALUES, max_words=0)
    except ArgError as error:
        return say_bad_arg(error, cat, io)
    io.say(cat.t("recordings.title"))
    gain, good = _gain(parsed.values.get("gain"))
    if not good:
        io.say(cat.t("recordings.set.bad_gain", limit="%g" % commands.MAX_GAIN_LIMIT_DB))
        return EXIT_NOTHING_DONE
    ctx, code = _open(parsed, home, cat, io)
    if ctx is None:
        return code
    if not scratch_ready(ctx.project, ctx.paths):
        io.say(cat.t("recordings.set.scratch_not_ready"))
        return EXIT_NOTHING_DONE
    view = rec.read_takes(ctx.paths.recordings)
    if view.ready == 0:
        io.say(cat.t("recordings.set.none_ready", command=_command("finish", ctx.project.id)))
        return EXIT_NOTHING_DONE
    if view.waiting:
        io.say(cat.count("recordings.set.waiting_note", view.waiting))
    env, state = studio()
    if env is None:
        io.say(cat.t("recordings.finish.no_environment", state=cat.t("env.state." + state), command=BUILDENV_STUDIO_COMMAND))
        return EXIT_NOTHING_DONE
    folder_name = commands.dataset_folder_name(jobs.utc_stamp(now))
    out = ctx.scratch.datasets + "/" + folder_name
    io.say(cat.t("recordings.set.checking"))
    summary, tail = _run_builder(system, commands.dataset_command(env, tools_dir, ctx.paths.recordings, out, dry_run=True, max_gain_db=gain), PREVIEW_TIMEOUT_S)
    if summary is None:
        io.say(cat.t("recordings.set.no_answer"))
        if tail:
            io.say("  " + cat.t("cli.technical", detail=tail))
        return EXIT_PROBLEM
    for line in dataset_lines(summary, cat):
        io.say(line)
    numbers = prog.assess(summary, ctx.project.planned_hours, custom_scratch=ctx.scratch.root != ctx.paths.default_scratch)
    if numbers is not None:
        for line in prog.lines(numbers, cat):
            io.say(line)
    if not summary.ok:
        return EXIT_NOTHING_DONE
    if "preview" in parsed.flags:
        io.say(cat.t("recordings.set.preview_only", command=_command("set", ctx.project.id)))
        return EXIT_OK
    declined = _confirmed(parsed, cat.t("recordings.set.question"), cat, io)
    if declined is not None:
        return declined
    os.makedirs(ctx.scratch.datasets, mode=0o700, exist_ok=True)
    built, tail = _run_builder(system, commands.dataset_command(env, tools_dir, ctx.paths.recordings, out, max_gain_db=gain), BUILD_TIMEOUT_S)
    if built is None:
        io.say(cat.t("recordings.set.no_answer"))
        if tail:
            io.say("  " + cat.t("cli.technical", detail=tail))
        if os.path.lexists(out):
            io.say(cat.t("recordings.set.kept_folder", folder=out))
        return EXIT_PROBLEM
    if built.result != "built":
        for line in dataset_lines(built, cat):
            io.say(line)
        if os.path.lexists(out):
            io.say(cat.t("recordings.set.kept_folder", folder=out))
        return EXIT_NOTHING_DONE if built.result == "nothing_qualified" else EXIT_PROBLEM
    try:
        rows, size = commands.dataset_size(out)
    except commands.CommandError as error:                                # the builder said it was done but what it left is not whole: say so, name the folder, delete nothing
        io.say(cat.t("dataset.result.problems"))
        io.say(cat.t("recordings.set.kept_folder", folder=out))
        io.say("  " + cat.t("cli.technical", detail=error.detail))
        return EXIT_PROBLEM
    io.say(cat.t("dataset.result.built"))
    io.say(cat.t("recordings.set.where", folder=out))
    io.say(cat.count("recordings.set.ready", rows, size=size_text(size)))
    io.say(cat.t("recordings.set.next", command="%s start --set %s --project %s" % (ROUNDS_COMMAND, folder_name, ctx.project.id)))
    return EXIT_OK


# ---------------------------------------------------------------- help and the front door

def _help(cat: Catalog, io: IO) -> int:
    io.say(cat.t("recordings.title"))
    io.say(cat.t("recordings.usage.head"))
    for key in ("recordings.usage.show", "recordings.usage.import", "recordings.usage.finish", "recordings.usage.model", "recordings.usage.set", "recordings.usage.options"):
        io.say("  " + cat.t(key))
    return EXIT_OK


def run_recordings(argv: Sequence[str], home: DataHome, registry: Registry, cat: Catalog, io: IO, *, studio: Studio, speech: Optional[Speech] = None, tools_dir: Optional[str] = None,
                   now: Optional[datetime] = None, start: Callable = jobs.start_job, system: Optional[System] = None,
                   plan_files: Callable[..., files_import.Plan] = files_import.make_plan, sleep: Callable[[float], None] = time.sleep,
                   clock: Callable[[], float] = time.monotonic, fetcher: Optional[Callable] = None) -> int:
    """`python3 -m voice_studio.recordings COMMAND ...`. Ctrl+C at any point stops cleanly: what was already added is kept, and listening that had started keeps going by itself."""
    command = argv[0] if argv else "help"
    rest = list(argv[1:])
    system = system or RealSystem()
    where = tools_dir or str(jobs.TOOLS_DIR)
    listen = speech or (lambda: envfind.speech_model(home, registry))
    try:
        if command in ("help", "--help", "-h"):
            return _help(cat, io)
        if command == "show":
            return _show(rest, home, cat, io)
        if command == "import":
            return _import(rest, home, plan_files, cat, io)
        if command == "finish":
            return _finish(rest, home, registry, studio, listen, where, now, start, cat, io)
        if command == "model":
            return _model(rest, home, registry, listen, sleep, clock, fetcher, now, cat, io)
        if command == "set":
            return _set(rest, home, studio, where, now, system, cat, io)
        io.say(cat.t("cli.bad_command", command=command[:60]))
        return EXIT_NOTHING_DONE
    except KeyboardInterrupt:
        io.say(cat.t("recordings.interrupted", command=_command("show", "PROJECT")))
        return EXIT_PROBLEM
    except files_import.FilesImportProblem as problem:
        stopped = rec.stop_from(problem)
        _say_parts(cat, io, "recordings", stopped.code, stopped.detail)
        return EXIT_PROBLEM
    except commands.CommandError as error:
        _say_parts(cat, io, "commands", error.code, error.detail)
        return EXIT_PROBLEM
    except jobs.JobError as error:
        _say_parts(cat, io, "job", error.code, error.detail)
        return EXIT_PROBLEM
