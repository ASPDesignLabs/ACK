# SPDX-License-Identifier: GPL-3.0-or-later
"""The terminal front for training rounds (until the window exists): see the rounds, start one, stop it, choose a round, go back, write a note, see what is kept, free up space.

It is the front of core/rounds.py and decides nothing that module does not. Commands that only look (`list`, `keep`, and `free` with no rounds named) change nothing, not even the record: they work out
what a write would find and show it. Every command that changes something shows what it will do and asks first (a typed yes, or `--yes`); a terminal with nobody at it is
never asked, whatever else is queued. A command that changes the record first brings it up to date (a round that ended since is written down as ended) and says so, because
that is a fact about what already happened, not an edit the person asked for.

Every sentence comes from the text catalog. Exit codes: 0 done, 1 something failed, 2 nothing was done (declined, nobody to ask, an option or a name that could not be told).
"""
from __future__ import annotations

import dataclasses
import os
from datetime import datetime
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from . import commands, freeup, jobs, rounds as rd, startvoice as sv, trainguard as tg
from .backupnudge import nudge_lines as backup_nudge
from .buildenv_flow import duration_text
from .diskbudget import DEFAULT_TABLE, MIB, DriveMap, Level, Role, Watch, floors_for, watch as disk_watch
from .cliargs import ArgError, Parsed, parse_args
from .describe import error_text
from .envbuild import EnvPaths
from .paths import DataHome, ProjectPaths, ScratchPaths
from .project import MAX_NOTE, SCRATCH_CUSTOM, Project, clean_text
from .projects_flow import EXIT_NOTHING_DONE, EXIT_OK, EXIT_PROBLEM, VOICES_COMMAND, resolve_project, say_bad_arg
from .registry import Registry
from .scratch import MARKER_NAME, check_marker, may_start_job, scratch_dir_for
from .setup_flow import IO, _said_yes
from .system import RealSystem, System
from .text import Catalog, size_text

ROUNDS_COMMAND = "python3 -m voice_studio.rounds"
BUILDENV_COMMAND = "python3 -m voice_studio.buildenv training"
YES = {"--yes": "yes", "-y": "yes"}
PROJECT = {"--project": "project"}
START_VALUES = {**PROJECT, "--set": "dataset", "--minutes": "minutes"}
NOTE_VALUES = {**PROJECT, "--text": "text"}
FREE_FLAGS = {**YES, "--all": "all", "--old": "old"}
FREE_VALUES = {**PROJECT, "--saved": "saved", "--working": "working", "--copies": "copies", "--clips": "clips"}
FREE_OPTION = {"files": "saved", "folder": "working", "copy": "copies", "clips": "clips"}         # the option of the free command that names each kind of offer, by round number
MAX_FAILURES_SHOWN = 10
FILES_ROW = {"chosen": "rounds.free.files_chosen", "before": "rounds.free.files_before", "other": "rounds.free.files_other", "point": "rounds.free.files_other_point"}
OPTIONS = {"list": frozenset(PROJECT), "start": frozenset(YES) | frozenset(START_VALUES), "stop": frozenset(YES) | frozenset(PROJECT),
           "choose": frozenset(YES) | frozenset(PROJECT), "back": frozenset(YES) | frozenset(PROJECT), "note": frozenset(YES) | frozenset(NOTE_VALUES),
           "keep": frozenset(PROJECT), "free": frozenset(FREE_FLAGS) | frozenset(FREE_VALUES)}                       # the checklist is held to these
TrainingEnv = Callable[[], Tuple[Optional[EnvPaths], str]]


def _say_parts(cat: Catalog, io: IO, namespace: str, code: str, detail: str = "") -> None:
    parts = error_text(cat, namespace, code)
    io.say("  " + parts.what)
    io.say("  " + parts.changed)
    io.say("  " + parts.next)
    if detail:
        io.say("  " + cat.t("cli.technical", detail=detail))


def _ask_yes(io: IO, prompt: str) -> Optional[bool]:
    """True for a yes, False for any other answer, None when nobody is there to ask. A window asks with a Yes and a No button instead of a typed word: an IO that has `confirm` is given the question."""
    if not io.interactive:
        return None
    confirm = getattr(io, "confirm", None)
    if confirm is not None:
        return confirm(prompt)
    answer = io.ask(prompt + " ")                              # a catalog sentence never ends in a space, so the prompt gets its own
    if answer is None:
        return None
    return _said_yes(answer)


def _confirmed(parsed: Parsed, question: str, cat: Catalog, io: IO) -> Optional[int]:
    """None when the person said yes (go on); otherwise the exit code, with the reason already said."""
    if "yes" in parsed.flags:
        return None
    answer = _ask_yes(io, question)
    if answer is None:
        io.say(cat.t("cli.cannot_ask"))
        return EXIT_NOTHING_DONE
    if not answer:
        io.say(cat.t("cli.nothing_done"))
        return EXIT_NOTHING_DONE
    return None


class Open:
    """The project a command works on, where its files are, and the record as it is."""

    def __init__(self, project: Project, paths: ProjectPaths, scratch: ScratchPaths, jobs_root: str):
        self.project, self.paths, self.scratch, self.jobs_root = project, paths, scratch, jobs_root


def scratch_root(project: Project, paths: ProjectPaths) -> ScratchPaths:
    """Where this project's training sets and working folders are. Only names the place; `scratch_ready` is what decides a job may use it."""
    if project.scratch.mode == SCRATCH_CUSTOM and project.scratch.place:
        try:
            return ScratchPaths(scratch_dir_for(project.scratch.place, project.id))
        except ValueError:
            pass
    return ScratchPaths(paths.default_scratch)


def scratch_ready(project: Project, paths: ProjectPaths) -> bool:
    """The default folder inside the project is always the person's own. A place they chose counts only if its marker names this project (an unplugged drive leaves an empty folder)."""
    if project.scratch.mode != SCRATCH_CUSTOM:
        return True
    if not project.scratch.place:
        return False
    try:
        folder = scratch_dir_for(project.scratch.place, project.id)
        with open(folder + "/" + MARKER_NAME, encoding="utf-8") as handle:
            text: Optional[str] = handle.read()
    except FileNotFoundError:
        text = None
    except (OSError, ValueError, UnicodeDecodeError):
        return False
    return may_start_job(check_marker(text, project.id))


def _open(parsed: Parsed, home: DataHome, cat: Catalog, io: IO) -> Tuple[Optional[Open], int]:
    project, code = resolve_project(parsed.values.get("project"), home, cat, io)
    if project is None:
        return None, code
    paths = ProjectPaths(home.projects + "/" + project.id)
    return Open(project, paths, scratch_root(project, paths), home.jobs), EXIT_OK


def _look(ctx: Open, now: Optional[datetime], cat: Catalog, io: IO, *, write: bool) -> rd.Record:
    """The record brought up to date. A command that writes saves that and says what it found out; one that only looks saves nothing."""
    before = rd.load(ctx.paths)
    after = rd.reconcile(ctx.paths, ctx.scratch, ctx.jobs_root, ctx.project.id, now=now, write=write)
    if write:
        for r in rd.noticed(before, after):
            if r.state not in rd.ACTIVE_STATES:
                io.say(cat.t("rounds.noticed", number=r.number, state=cat.t("rounds.state." + r.state)))
    return after


def _same_drive(a: str, b: str) -> bool:
    try:
        return os.stat(a).st_dev == os.stat(b).st_dev
    except OSError:
        return False                                                     # a place that cannot be looked at is counted as another drive, which asks for more room


def _drives(ctx: Open) -> DriveMap:
    """The project's drive, and scratch's when it is another one (a place the person chose on a different disk)."""
    return DriveMap(tool="project", project="project", scratch="project" if _same_drive(ctx.paths.rounds, ctx.scratch.root) else "scratch", backup="project")


def _free(system: System, ctx: Open) -> Dict[str, Optional[int]]:
    found: Dict[str, Optional[int]] = {}
    for drive, path in (("project", ctx.paths.rounds), ("scratch", ctx.scratch.root)):
        usage = system.disk_free(path)
        found[drive] = usage[1] if usage else None
    return found


def _number(word: str) -> Optional[int]:
    return int(word) if word.isascii() and word.isdigit() and len(word) <= 6 else None


def _when(stamp: str) -> str:
    return stamp.replace("T", " ").replace("Z", " UTC")


# ---------------------------------------------------------------- list and keep (they change nothing)

def round_lines(r: rd.Round, chosen: bool, paths: ProjectPaths, cat: Catalog) -> List[str]:
    """What is said about one round: its head, then indented lines. The terminal prints them and the window draws them, so the two never word a round differently."""
    label = "%d %s" % (r.number, cat.t("rounds.row.mark")) if chosen else str(r.number)
    lines = [cat.t("rounds.row.head", label=label, state=cat.t("rounds.state." + r.state))]
    if r.parent:
        lines.append("  " + cat.t("rounds.row.from_round", minutes=r.minutes, parent=r.parent, set=r.dataset))
    else:
        lines.append("  " + cat.t("rounds.row.from_voice", minutes=r.minutes, voice=r.voice, set=r.dataset))
    lines.append("  " + cat.t("rounds.row.started", when=_when(r.started)))
    if r.failure:
        lines.append("  " + cat.t("rounds.failure." + r.failure))
    if r.stopped_for:
        lines.append("  " + cat.t("rounds.stopped_for." + r.stopped_for))
    if r.has_checkpoint:
        lines.append("  " + cat.t("rounds.checkpoint." + rd.checkpoint_status(paths, r)))
    if r.note:
        lines.append("  " + cat.t("rounds.row.note", note=r.note))
    return lines


def _row(r: rd.Round, chosen: bool, ctx: Open, cat: Catalog, io: IO) -> None:
    for line in round_lines(r, chosen, ctx.paths, cat):
        io.say(line)


def _list(args: Sequence[str], home: DataHome, now: Optional[datetime], system: System, cat: Catalog, io: IO) -> int:
    try:
        parsed = parse_args(args, flags={}, values=PROJECT, max_words=0)
    except ArgError as error:
        return say_bad_arg(error, cat, io)
    io.say(cat.t("rounds.title"))
    ctx, code = _open(parsed, home, cat, io)
    if ctx is None:
        return code
    record = _look(ctx, now, cat, io, write=False)
    io.say(cat.t("rounds.list.heading", name=ctx.project.name))
    for r in record.rounds:
        _row(r, r.number == record.current, ctx, cat, io)
    if not record.rounds:
        io.say(cat.t("rounds.list.none"))
    pick = rd.chosen(record)
    if pick is not None:
        io.say(cat.t("rounds.list.chosen", number=pick.number, minutes=rd.trained_minutes(record, pick.number)))
    else:
        io.say(cat.t("rounds.list.none_chosen"))
    running = rd.active(record)
    if running is not None:
        io.say(cat.t("rounds.list.running", number=running.number, command="%s stop --project %s" % (ROUNDS_COMMAND, ctx.project.id)))
        free = _free(system, ctx)["project"]
        if free is not None:
            floors = floors_for(DEFAULT_TABLE, holds_recordings=True)
            io.say(cat.t("rounds.list.disk", free=size_text(free)))
            state = disk_watch(free, floors)
            if state is Watch.LOW:
                io.say(cat.t("rounds.list.disk_low", floor=size_text(floors.stop)))
            elif state is Watch.STOP:
                io.say(cat.t("rounds.list.disk_stop"))
    else:
        io.say(cat.t("rounds.list.next", command="%s start --set <name> --project %s" % (ROUNDS_COMMAND, ctx.project.id)))
    return EXIT_OK


def _keep(args: Sequence[str], home: DataHome, now: Optional[datetime], cat: Catalog, io: IO) -> int:
    try:
        parsed = parse_args(args, flags={}, values=PROJECT, max_words=0)
    except ArgError as error:
        return say_bad_arg(error, cat, io)
    io.say(cat.t("rounds.title"))
    ctx, code = _open(parsed, home, cat, io)
    if ctx is None:
        return code
    record = _look(ctx, now, cat, io, write=False)
    kept = rd.retention(ctx.paths, record)
    io.say(cat.t("rounds.keep.heading"))
    if not (kept.keep or kept.spare or kept.busy or kept.unclaimed):
        io.say(cat.t("rounds.keep.none"))
    if kept.keep:
        io.say(cat.t("rounds.keep.kept", count=len(kept.keep), size=size_text(sum(f.size for n, f in kept.keep))))
        for n, f in kept.keep:
            io.say("  " + cat.t("rounds.keep.kept_row", number=n, name=f.name, size=size_text(f.size)))
    if kept.spare:
        io.say(cat.t("rounds.keep.spare", count=len(kept.spare), size=size_text(sum(f.size for n, f in kept.spare))))
    if kept.busy:
        io.say(cat.t("rounds.keep.busy", count=len(kept.busy)))
    if kept.unclaimed:
        io.say(cat.t("rounds.keep.unclaimed", count=len(kept.unclaimed), size=size_text(sum(f.size for f in kept.unclaimed))))
    io.say(cat.t("rounds.keep.nothing_removed"))
    return EXIT_OK


# ---------------------------------------------------------------- free up space

def _round_numbers(word: str, minimum: int = 1) -> Optional[List[int]]:
    """'1,3' -> [1, 3]; anything that is not whole round numbers separated by commas -> None. Test clips and voice copies may be of round 0: a voice file whose round cannot be told."""
    found = [_number(part) for part in word.split(",")]
    if any(n is None or n < minimum for n in found):
        return None
    return [n for n in found if n is not None]


def old_notice_lines(count: int, project_id: str, cat: Catalog) -> List[str]:
    """The notice that earlier listenings are old and should be removed, and how: said by `free`, at the end of `listen`, and by the window. Nothing is removed because of it."""
    if count < 1:
        return []
    return [cat.count("rounds.free.old_notice", count, days=freeup.OLD_AFTER_DAYS),
            cat.t("rounds.free.old_how", command="%s free --old --project %s" % (ROUNDS_COMMAND, project_id))]


def free_row_text(offer: freeup.Offer, cat: Catalog) -> str:
    """What is said about one thing that could be freed. The terminal prints it and the window draws it."""
    if offer.kind in ("copy", "clips") and offer.old:
        return free_row_text(dataclasses.replace(offer, old=False), cat) + " " + cat.t("rounds.free.old_note", days=freeup.OLD_AFTER_DAYS)
    if offer.kind == "folder":
        return cat.t("rounds.free.working", round=offer.round, size=size_text(offer.bytes))
    if offer.kind == "copy":
        return cat.t("rounds.free.copy", round=offer.round, when=offer.when, size=size_text(offer.bytes))
    if offer.kind == "clips":
        if offer.source.startswith("round-"):
            return cat.t("rounds.free.clips_round", round=offer.round, when=offer.when, size=size_text(offer.bytes))
        return cat.t("rounds.free.clips_voice", name=offer.source, when=offer.when, size=size_text(offer.bytes))
    key = FILES_ROW["point" if offer.includes_saved_point else offer.relation]
    return cat.count(key, len(offer.paths), round=offer.round, size=size_text(offer.bytes))


def _free_row(offer: freeup.Offer, cat: Catalog, io: IO) -> None:
    io.say("  " + free_row_text(offer, cat))


def _free_list(shown: freeup.Plan, ctx: Open, cat: Catalog, io: IO) -> None:
    """Everything that could be freed, then what never can be."""
    io.say(cat.t("rounds.free.heading", name=ctx.project.name))
    if not shown.offers:
        io.say(cat.t("rounds.free.nothing"))
    for offer in shown.offers:
        _free_row(offer, cat, io)
    if shown.offers:
        io.say(cat.t("rounds.free.total", size=size_text(sum(o.bytes for o in shown.offers))))
    for line in old_notice_lines(shown.old_listenings, ctx.project.id, cat):
        io.say(line)
    if shown.kept:
        io.say(cat.count("rounds.free.kept", len(shown.kept), size=size_text(sum(f.size for _n, f in shown.kept))))
    if shown.busy:
        io.say(cat.count("rounds.free.busy", shown.busy))
    if shown.unclaimed:
        io.say(cat.count("rounds.free.unclaimed", shown.unclaimed))
    io.say(cat.t("rounds.free.never"))
    if shown.offers:
        io.say(cat.t("rounds.free.how", command="%s free --saved 1 --project %s" % (ROUNDS_COMMAND, ctx.project.id)))
        heard = next((o for o in shown.offers if o.kind in ("copy", "clips")), None)
        if heard is not None:
            io.say(cat.t("rounds.free.how_heard", command="%s free --%s %d --project %s" % (ROUNDS_COMMAND, FREE_OPTION[heard.kind], heard.round, ctx.project.id)))
        io.say(cat.t("rounds.free.how_all"))


def _free_up(args: Sequence[str], home: DataHome, now: Optional[datetime], system: System, cat: Catalog, io: IO) -> int:
    try:
        parsed = parse_args(args, flags=FREE_FLAGS, values=FREE_VALUES, max_words=0)
    except ArgError as error:
        return say_bad_arg(error, cat, io)
    io.say(cat.t("rounds.title"))
    named = {kind: parsed.values[kind] for kind in FREE_OPTION.values() if kind in parsed.values}
    if "all" in parsed.flags and named:
        io.say(cat.t("rounds.free.both"))
        return EXIT_NOTHING_DONE
    numbers: Dict[str, List[int]] = {}
    for kind, word in named.items():
        found = _round_numbers(word, 0 if kind in ("clips", "copies") else 1)
        if found is None:
            io.say(cat.t("rounds.free.bad_numbers", text=word[:40]))
            return EXIT_NOTHING_DONE
        numbers[kind] = found
    if "old" in parsed.flags and ("all" in parsed.flags or named):
        io.say(cat.t("rounds.free.old_alone"))
        return EXIT_NOTHING_DONE
    selecting = "all" in parsed.flags or "old" in parsed.flags or bool(named)
    ctx, code = _open(parsed, home, cat, io)
    if ctx is None:
        return code
    record = _look(ctx, now, cat, io, write=selecting)
    shown = freeup.plan(ctx.paths, ctx.scratch, record, now)
    if not selecting:
        _free_list(shown, ctx, cat, io)
        return EXIT_OK
    if not shown.offers:
        io.say(cat.t("rounds.free.nothing"))
        return EXIT_NOTHING_DONE
    if "old" in parsed.flags:
        picked = [o for o in shown.offers if o.old]
        if not picked:
            io.say(cat.t("rounds.free.nothing_old", days=freeup.OLD_AFTER_DAYS))
            return EXIT_NOTHING_DONE
    elif "all" in parsed.flags:
        picked = list(shown.offers)
    else:
        picked = []
        for kind, wanted in numbers.items():
            offer_kind = next(k for k, option in FREE_OPTION.items() if option == kind)
            by_round: Dict[int, List[freeup.Offer]] = {}
            for o in shown.offers:
                if o.kind == offer_kind:
                    by_round.setdefault(o.round, []).append(o)
            missing = [n for n in wanted if n not in by_round]
            if missing:
                io.say(cat.t("rounds.free.unknown", option="--" + kind, numbers=",".join(str(n) for n in missing), command="%s free --project %s" % (ROUNDS_COMMAND, ctx.project.id)))
                return EXIT_NOTHING_DONE
            for n in sorted(set(wanted)):
                picked += by_round[n]                                  # every listening of that round, for the two kinds a round can have several of
    io.say(cat.t("rounds.free.will_remove"))
    for offer in picked:
        _free_row(offer, cat, io)
    declined = _confirmed(parsed, cat.t("rounds.free.question", size=size_text(sum(o.bytes for o in picked))), cat, io)
    if declined is not None:
        return declined
    try:
        result = freeup.remove(ctx.paths, ctx.scratch, shown, [o.number for o in picked])
    except freeup.FreeError as error:
        _say_parts(cat, io, "freeup", error.code, error.detail)
        return EXIT_PROBLEM
    io.say(cat.t("rounds.free.done", files=result.removed_files, folders=result.removed_folders, size=size_text(result.removed_bytes)))
    if result.removed_heard:
        io.say(cat.t("rounds.free.done_heard", files=result.removed_heard))
    free = _free(system, ctx)
    if free["project"] is not None:
        io.say(cat.t("rounds.free.free_now", free=size_text(free["project"])))
    drives = _drives(ctx)
    if drives.of(Role.SCRATCH) != drives.of(Role.PROJECT) and free["scratch"] is not None:
        io.say(cat.t("rounds.free.free_now_scratch", free=size_text(free["scratch"])))
    if result.failed:
        io.say(cat.t("rounds.free.failed_head"))
        for path, reason in result.failed[:MAX_FAILURES_SHOWN]:
            io.say("  " + cat.t("rounds.free.failed_row", path=path, reason=reason))
        if len(result.failed) > MAX_FAILURES_SHOWN:
            io.say("  " + cat.t("rounds.free.failed_more", count=len(result.failed) - MAX_FAILURES_SHOWN))
        return EXIT_PROBLEM
    return EXIT_OK


# ---------------------------------------------------------------- start

def _datasets(ctx: Open) -> List[str]:
    try:
        return sorted(n for n in os.listdir(ctx.scratch.datasets) if os.path.isdir(ctx.scratch.datasets + "/" + n) and not os.path.islink(ctx.scratch.datasets + "/" + n)
                      and commands.SAFE_NAME.match(n))
    except OSError:
        return []


def _starting_point(ctx: Open, record: rd.Record, home: DataHome, registry: Registry, cat: Catalog, io: IO) -> Tuple[Optional[rd.Base], int]:
    """The starting voice, but only when no round of the person's can be continued from. (None, EXIT_OK) when none is needed."""
    if rd.chosen(record) is not None or rd.active(record) is not None:
        return None, EXIT_OK
    voice = ctx.project.starting_voice
    if not voice:
        io.say(cat.t("rounds.start.no_voice", command="%s choose <voice> --project %s" % (VOICES_COMMAND, ctx.project.id)))
        return None, EXIT_NOTHING_DONE
    step = sv.next_step(ctx.project, registry, voice, home)
    path = sv.kept_path(home, registry, voice) if step == "ready" else None
    if path is None:
        io.say(cat.t("rounds.start.voice_not_ready", voice=voice, step=cat.t("startvoice.step." + step),
                     command="%s get %s --project %s" % (VOICES_COMMAND, voice, ctx.project.id)))
        return None, EXIT_NOTHING_DONE
    return rd.Base(voice, str(path)), EXIT_OK


def _start(args: Sequence[str], home: DataHome, registry: Registry, training: TrainingEnv, now: Optional[datetime], start: Callable, system: System, cat: Catalog, io: IO) -> int:
    try:
        parsed = parse_args(args, flags=YES, values=START_VALUES, max_words=0)
    except ArgError as error:
        return say_bad_arg(error, cat, io)
    io.say(cat.t("rounds.title"))
    ctx, code = _open(parsed, home, cat, io)
    if ctx is None:
        return code
    if not scratch_ready(ctx.project, ctx.paths):
        io.say(cat.t("rounds.start.scratch_not_ready"))
        return EXIT_NOTHING_DONE
    record = _look(ctx, now, cat, io, write=True)
    names = _datasets(ctx)
    wanted = parsed.values.get("dataset")
    if not names:
        io.say(cat.t("rounds.start.no_sets"))
        return EXIT_NOTHING_DONE
    if wanted is None:
        io.say(cat.t("rounds.start.which_set", names=", ".join(names)))
        return EXIT_NOTHING_DONE
    if wanted not in names:
        io.say(cat.t("rounds.start.set_unknown", name=wanted[:60], names=", ".join(names)))
        return EXIT_NOTHING_DONE
    env, state = training()
    if env is None:
        io.say(cat.t("rounds.start.no_environment", state=cat.t("env.state." + state), command=BUILDENV_COMMAND))
        return EXIT_NOTHING_DONE
    base, code = _starting_point(ctx, record, home, registry, cat, io)
    if code != EXIT_OK:
        return code
    minutes_text = parsed.values.get("minutes")
    minutes: object = commands.ROUND_MINUTES if minutes_text is None else (int(minutes_text) if minutes_text.isascii() and minutes_text.isdigit() and len(minutes_text) <= 6 else minutes_text)
    plan = rd.plan_round(ctx.paths, ctx.scratch, record, dataset=wanted, minutes=minutes, base=base)       # type: ignore[arg-type]
    clips, wav_bytes = commands.dataset_size(plan.dataset_dir)
    card = tg.read_gpu_memory(system)
    choice = tg.batch_for(card.total_mib if card else None)
    if choice.batch is None:
        io.say(cat.t("rounds.start.gpu_small", memory=size_text((card.total_mib if card else 0) * MIB), least=size_text(tg.MIN_GPU_MIB * MIB)))
        return EXIT_NOTHING_DONE
    every = tg.check_every(clips, choice.batch)
    room = tg.judge_gpu_room(card.total_mib if card else None, card.used_mib if card else None, choice.batch)
    drives = _drives(ctx)
    disk = tg.judge_round_disk(DEFAULT_TABLE, tg.hours_of_speech(wav_bytes), drives, _free(system, ctx))
    stop_floor = floors_for(DEFAULT_TABLE, holds_recordings=True).stop
    io.say(cat.t("rounds.start.plan_head", number=plan.number))
    io.say("  " + (cat.t("rounds.start.plan_round", parent=plan.parent) if plan.parent else cat.t("rounds.start.plan_voice", voice=plan.voice)))
    io.say("  " + cat.t("rounds.start.plan_set", set=plan.dataset, clips=clips))
    io.say("  " + cat.t("rounds.start.plan_length", minutes=plan.minutes))
    io.say("  " + cat.t("rounds.start.plan_batch", batch=choice.batch, basis=cat.t("rounds.basis." + choice.basis)))
    io.say("  " + cat.t("rounds.start.plan_check", time=duration_text(cat, tg.lost_seconds(clips, choice.batch, every))))
    io.say("  " + cat.t("rounds.start.plan_card"))
    io.say("  " + cat.t("rounds.start.guard", floor=size_text(stop_floor)))
    io.say("  " + cat.t("rounds.start.plan_files", folder=ctx.paths.run))
    io.say(cat.t("rounds.start.checks_head"))
    if room.free_mib is None:
        io.say("  " + cat.t("rounds.start.gpu_unknown"))
    else:
        words = dict(free=size_text(room.free_mib * MIB), need=size_text(room.need_mib * MIB))
        io.say("  " + cat.t({Level.ENOUGH: "rounds.start.gpu_ok", Level.TIGHT: "rounds.start.gpu_tight", Level.NOT_ENOUGH: "rounds.start.gpu_short"}[room.level], **words))
    for drive in disk.drives:
        if drive.free is None:
            io.say("  " + cat.t("rounds.start.disk_unknown"))
        elif drive.level is Level.NOT_ENOUGH:
            io.say("  " + cat.t("rounds.start.disk_short", free=size_text(drive.free), need=size_text(drive.need), short=size_text(drive.short_by)))
        elif drive.level is Level.TIGHT:
            io.say("  " + cat.t("rounds.start.disk_tight", free=size_text(drive.free), need=size_text(drive.need)))
        else:
            io.say("  " + cat.t("rounds.start.disk_ok", free=size_text(drive.free), need=size_text(drive.need)))
    if Level.NOT_ENOUGH in (room.level, disk.level):
        return EXIT_NOTHING_DONE                                          # said above, in words, with nothing started; --yes does not get past this
    for line in backup_nudge(home, ctx.project, ctx.paths, cat, record):      # a reminder before training, never a stop (plan D7)
        io.say(line)
    declined = _confirmed(parsed, cat.t("rounds.start.question", number=plan.number), cat, io)
    if declined is not None:
        return declined
    started = rd.start_round(ctx.paths, ctx.scratch, ctx.project.id, env, ctx.jobs_root, dataset=wanted, minutes=plan.minutes, base=base, now=now, start=start,
                             batch_size=choice.batch, check_every=every, watch=tg.watches(DEFAULT_TABLE, ctx.paths.run, ctx.scratch.caches, drives))
    io.say(cat.t("rounds.start.started", number=started.number, job=started.job))
    io.say(cat.t("rounds.start.watch", list="%s list --project %s" % (ROUNDS_COMMAND, ctx.project.id), stop="%s stop --project %s" % (ROUNDS_COMMAND, ctx.project.id)))
    return EXIT_OK


# ---------------------------------------------------------------- stop

def _stop(args: Sequence[str], home: DataHome, now: Optional[datetime], cat: Catalog, io: IO) -> int:
    try:
        parsed = parse_args(args, flags=YES, values=PROJECT, max_words=0)
    except ArgError as error:
        return say_bad_arg(error, cat, io)
    io.say(cat.t("rounds.title"))
    ctx, code = _open(parsed, home, cat, io)
    if ctx is None:
        return code
    record = _look(ctx, now, cat, io, write=True)
    running = rd.active(record)
    if running is None:
        io.say(cat.t("rounds.stop.none"))
        return EXIT_NOTHING_DONE
    if not running.job:
        io.say(cat.t("rounds.stop.no_job", number=running.number))
        return EXIT_NOTHING_DONE
    declined = _confirmed(parsed, cat.t("rounds.stop.question", number=running.number), cat, io)
    if declined is not None:
        return declined
    answer = jobs.request_stop(ctx.jobs_root + "/" + running.job)
    if answer == "asked":
        io.say(cat.t("rounds.stop.asked", number=running.number, command="%s list --project %s" % (ROUNDS_COMMAND, ctx.project.id)))
    elif answer == "already":
        io.say(cat.t("rounds.stop.already", number=running.number))
    else:
        io.say(cat.t("rounds.stop.not_running", number=running.number))
    return EXIT_OK


# ---------------------------------------------------------------- choose and back

def _choosable(record: rd.Record) -> str:
    return ", ".join(str(r.number) for r in record.rounds if r.has_checkpoint)


def _choose(args: Sequence[str], home: DataHome, now: Optional[datetime], cat: Catalog, io: IO) -> int:
    try:
        parsed = parse_args(args, flags=YES, values=PROJECT, max_words=1)
    except ArgError as error:
        return say_bad_arg(error, cat, io)
    io.say(cat.t("rounds.title"))
    ctx, code = _open(parsed, home, cat, io)
    if ctx is None:
        return code
    record = _look(ctx, now, cat, io, write=True)
    number = _number(parsed.words[0]) if parsed.words else None
    if number is None:
        io.say(cat.t("rounds.choose.which", numbers=_choosable(record)) if _choosable(record) else cat.t("rounds.choose.none"))
        return EXIT_NOTHING_DONE
    if record.current == number:
        io.say(cat.t("rounds.choose.already", number=number))
        return EXIT_OK
    declined = _confirmed(parsed, cat.t("rounds.choose.question", number=number), cat, io)
    if declined is not None:
        return declined
    rd.choose(ctx.paths, number)
    io.say(cat.t("rounds.choose.done", number=number))
    return EXIT_OK


def _back(args: Sequence[str], home: DataHome, now: Optional[datetime], cat: Catalog, io: IO) -> int:
    try:
        parsed = parse_args(args, flags=YES, values=PROJECT, max_words=0)
    except ArgError as error:
        return say_bad_arg(error, cat, io)
    io.say(cat.t("rounds.title"))
    ctx, code = _open(parsed, home, cat, io)
    if ctx is None:
        return code
    record = _look(ctx, now, cat, io, write=True)
    target = rd.go_back_target(ctx.paths, record)
    if target is None:
        _say_parts(cat, io, "rounds", "nowhere_back")
        return EXIT_PROBLEM
    declined = _confirmed(parsed, cat.t("rounds.back.question", target=target, current=record.current), cat, io)
    if declined is not None:
        return declined
    rd.go_back(ctx.paths)
    io.say(cat.t("rounds.back.done", target=target, current=record.current))
    return EXIT_OK


# ---------------------------------------------------------------- note

def _note(args: Sequence[str], home: DataHome, now: Optional[datetime], cat: Catalog, io: IO) -> int:
    try:
        parsed = parse_args(args, flags=YES, values=NOTE_VALUES, max_words=1)
    except ArgError as error:
        return say_bad_arg(error, cat, io)
    io.say(cat.t("rounds.title"))
    number = _number(parsed.words[0]) if parsed.words else None
    if number is None:
        io.say(cat.t("rounds.note.which"))
        return EXIT_NOTHING_DONE
    if "text" not in parsed.values:
        io.say(cat.t("rounds.note.which_text"))
        return EXIT_NOTHING_DONE
    ctx, code = _open(parsed, home, cat, io)
    if ctx is None:
        return code
    record = _look(ctx, now, cat, io, write=True)
    found = rd.find(record, number)
    if found is None:
        _say_parts(cat, io, "rounds", "unknown_round", str(number))
        return EXIT_PROBLEM
    text = clean_text(parsed.values["text"], MAX_NOTE)
    if text == found.note:
        io.say(cat.t("rounds.note.unchanged", number=number))
        return EXIT_OK
    question = cat.t("rounds.note.question", number=number, note=text) if text else cat.t("rounds.note.question_clear", number=number)
    declined = _confirmed(parsed, question, cat, io)
    if declined is not None:
        return declined
    rd.set_note(ctx.paths, number, text)
    io.say(cat.t("rounds.note.done" if text else "rounds.note.done_cleared", number=number))
    return EXIT_OK


# ---------------------------------------------------------------- the front

def _help(cat: Catalog, io: IO) -> int:
    io.say(cat.t("rounds.title"))
    io.say(cat.t("rounds.usage.head"))
    for key in ("rounds.usage.list", "rounds.usage.start", "rounds.usage.stop", "rounds.usage.choose", "rounds.usage.back", "rounds.usage.note", "rounds.usage.keep",
                "rounds.usage.free", "rounds.usage.options"):
        io.say("  " + cat.t(key))
    return EXIT_OK


def run_rounds(argv: Sequence[str], home: DataHome, registry: Registry, cat: Catalog, io: IO, *, training: TrainingEnv, now: Optional[datetime] = None,
               start: Callable = jobs.start_job, system: Optional[System] = None) -> int:
    """`python3 -m voice_studio.rounds COMMAND ...`. Ctrl+C at any point stops cleanly; a round that had already started keeps running by itself."""
    command = argv[0] if argv else "help"
    rest = list(argv[1:])
    system = system or RealSystem()
    try:
        if command in ("help", "--help", "-h"):
            return _help(cat, io)
        if command == "list":
            return _list(rest, home, now, system, cat, io)
        if command == "keep":
            return _keep(rest, home, now, cat, io)
        if command == "free":
            return _free_up(rest, home, now, system, cat, io)
        if command == "start":
            return _start(rest, home, registry, training, now, start, system, cat, io)
        if command == "stop":
            return _stop(rest, home, now, cat, io)
        if command == "choose":
            return _choose(rest, home, now, cat, io)
        if command == "back":
            return _back(rest, home, now, cat, io)
        if command == "note":
            return _note(rest, home, now, cat, io)
        io.say(cat.t("cli.bad_command", command=command[:60]))
        return EXIT_NOTHING_DONE
    except KeyboardInterrupt:
        io.say(cat.t("rounds.interrupted", command="%s list" % ROUNDS_COMMAND))
        return EXIT_PROBLEM
    except rd.RoundsError as error:
        _say_parts(cat, io, "rounds", error.code, error.detail)
        return EXIT_PROBLEM
    except commands.CommandError as error:
        _say_parts(cat, io, "commands", error.code, error.detail)
        return EXIT_PROBLEM
    except jobs.JobError as error:
        _say_parts(cat, io, "job", error.code, error.detail)
        return EXIT_PROBLEM
    except sv.StartVoiceError as error:
        _say_parts(cat, io, "startvoice", error.code, error.detail)
        return EXIT_PROBLEM
    except freeup.FreeError as error:
        _say_parts(cat, io, "freeup", error.code, error.detail)
        return EXIT_PROBLEM
