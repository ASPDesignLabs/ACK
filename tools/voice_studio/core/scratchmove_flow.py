# SPDX-License-Identifier: GPL-3.0-or-later
"""The terminal front for moving a project's scratch (plan task VS-6.5, decision P20): `python3 -m voice_studio.scratch show | move`.

The decisions are in core/scratchmove.py and the rules for a place in core/scratch.py (plan task VS-1.11). `show` only looks. `move` checks the new place, shows what it will do, asks
once (a typed yes, or `--yes`; nobody to ask means nothing is done), copies and checks, switches the project to the new place, and then asks separately whether to remove the old one
(a typed yes only: `--yes` was given for the move and does not answer this). Nothing here touches a recording, a round or a finished voice.
Exit codes as the other fronts: 0 done (or looked), 1 something failed after it began, 2 nothing was done (declined, nobody to ask, refused, an option that could not be told).
"""
from __future__ import annotations

import os
import shlex
from typing import Callable, List, Optional, Sequence

from . import projectbackup as pb, scratch as sc, scratchmove as sm
from .cliargs import ArgError, parse_args
from .describe import refusal_text, warning_text
from .diskbudget import Level
from .paths import DataHome, ProjectPaths
from .preflight import Platform, detect_platform
from .project import SCRATCH_CUSTOM, Project, list_projects
from .projects_flow import EXIT_NOTHING_DONE, EXIT_OK, EXIT_PROBLEM, say_bad_arg
from .rounds_flow import PROJECT, YES, Open, _ask_yes, _confirmed, _open, _say_parts, scratch_ready
from .setup_flow import IO
from .system import System
from .text import Catalog, size_text

SCRATCH_COMMAND = "python3 -m voice_studio.scratch"
COMMANDS = ("show", "move", "help")
MOVE_VALUES = {**PROJECT, "--to": "to"}
MOVE_FLAGS = {**YES, "--default": "default"}
OPTIONS = {"show": frozenset(PROJECT), "move": frozenset(MOVE_VALUES) | frozenset(MOVE_FLAGS)}          # the checklist is held to these
USAGE = ("scratchmove.usage.show", "scratchmove.usage.move", "scratchmove.usage.options")
PROGRESS_STEPS = 10                                                                                       # at most this many "copied n of m" lines
MAX_FAILED_SHOWN = 10


def _on_wsl(system: System) -> bool:
    return detect_platform(system.read_text("/proc/version"), system.environ()) is not Platform.NATIVE


def _where(ctx: Open) -> str:
    return ctx.scratch.root


def _custom(ctx: Open) -> bool:
    return ctx.project.scratch.mode == SCRATCH_CUSTOM          # a project file cannot say custom without a place (core/project.py validates it)


def _say_tree(cat: Catalog, io: IO, tree: sm.Tree, indent: str = "") -> None:
    if tree.files:
        io.say(indent + cat.count("scratchmove.size", len(tree.files), size=size_text(tree.bytes)))
    else:
        io.say(indent + cat.t("scratchmove.empty"))
    if tree.skipped:
        io.say(indent + cat.count("scratchmove.skipped", len(tree.skipped)))


# ---------------------------------------------------------------- show

def _show(args: Sequence[str], system: System, home: DataHome, cat: Catalog, io: IO) -> int:
    try:
        parsed = parse_args(args, flags={}, values=PROJECT, max_words=0)
    except ArgError as error:
        return say_bad_arg(error, cat, io)
    io.say(cat.t("scratchmove.title"))
    ctx, code = _open(parsed, home, cat, io)
    if ctx is None:
        return code
    io.say(cat.t("scratchmove.show.custom" if _custom(ctx) else "scratchmove.show.default", name=ctx.project.name, folder=_where(ctx)))
    if not scratch_ready(ctx.project, ctx.paths):
        io.say(cat.t("scratchmove.show.not_ready"))
    else:
        try:
            _say_tree(cat, io, sm.read_tree(_where(ctx)), "  ")
        except OSError:
            io.say("  " + cat.t("scratchmove.show.unreadable"))
        usage = system.disk_free(pb.nearest_existing(_where(ctx)))
        if usage:
            io.say("  " + cat.t("scratchmove.show.free", free=size_text(usage[1])))
    io.say(cat.t("scratchmove.show.how", command="%s move --project %s --to FOLDER" % (SCRATCH_COMMAND, ctx.project.id)))
    return EXIT_OK


# ---------------------------------------------------------------- move

def _others(home: DataHome, project_id: str) -> List[str]:
    return [home.projects + "/" + p.id for p in list_projects(home.projects).projects if p.id != project_id]


def _refuse(cat: Catalog, io: IO, reasons: Sequence[str]) -> int:
    io.say(cat.t("scratchmove.refused"))
    for reason in reasons:
        io.say("  " + refusal_text(cat, reason))
    io.say(cat.t("cli.nothing_done"))
    return EXIT_NOTHING_DONE


def _progress(cat: Catalog, io: IO) -> Callable[[int, int, str], None]:
    shown = {"step": -1}

    def on_file(done: int, total: int, _rel: str) -> None:
        step = (done * PROGRESS_STEPS) // total
        if step != shown["step"]:
            shown["step"] = step
            io.say("  " + cat.t("scratchmove.progress", done=done, total=total))
    return on_file


def _offer_old(before: Project, ctx: Open, cat: Catalog, io: IO) -> int:
    old = sm.old_place(before, ctx.paths)
    if old is None:
        return EXIT_OK
    io.say(cat.count("scratchmove.old.head", old.files, folder=old.folder, size=size_text(old.bytes)))
    answer = _ask_yes(io, cat.t("scratchmove.old.question"))
    if not answer:
        io.say(cat.t("scratchmove.old.kept", command="rm -r " + shlex.quote(old.folder)))
        return EXIT_OK
    try:
        result = sm.remove_old(old, ctx.project, ctx.jobs_root)
    except sm.MoveError as error:
        _say_parts(cat, io, "scratchmove", error.code, error.detail)
        return EXIT_PROBLEM
    if result.failed:
        io.say(cat.t("scratchmove.old.failed_head"))
        for path, why in result.failed[:MAX_FAILED_SHOWN]:
            io.say("  " + cat.t("scratchmove.old.failed_row", path=path, reason=why))
        return EXIT_PROBLEM
    io.say(cat.t("scratchmove.old.done", size=size_text(result.bytes)))
    return EXIT_OK


def _move(args: Sequence[str], system: System, home: DataHome, cat: Catalog, io: IO) -> int:
    try:
        parsed = parse_args(args, flags=MOVE_FLAGS, values=MOVE_VALUES, max_words=0)
    except ArgError as error:
        return say_bad_arg(error, cat, io)
    io.say(cat.t("scratchmove.title"))
    given = parsed.values.get("to")
    if (given is None) == ("default" not in parsed.flags):
        io.say(cat.t("scratchmove.which"))
        return EXIT_NOTHING_DONE
    ctx, code = _open(parsed, home, cat, io)
    if ctx is None:
        return code
    project = ctx.project
    if not scratch_ready(project, ctx.paths):
        _say_parts(cat, io, "scratchmove", "source_missing")
        return EXIT_NOTHING_DONE
    if sm.task_blocks(ctx.jobs_root, project.id):
        _say_parts(cat, io, "scratchmove", "job_running")
        return EXIT_NOTHING_DONE

    warnings: Sequence[str] = ()
    if given is None:
        target_place, target = "", ctx.paths.default_scratch
    else:
        facts = sc.gather_place_facts(system, given, project_id=project.id, project_root=ctx.paths.root, other_project_roots=_others(home, project.id), wsl=_on_wsl(system),
                                      project_device=system.device_of(ctx.paths.root))
        found = sc.assess_scratch(facts)
        if found.refusals:
            return _refuse(cat, io, found.refusals)
        target = found.scratch_dir
        target_place = os.path.dirname(os.path.dirname(target))
        warnings = found.warnings
    if os.path.realpath(target) == os.path.realpath(ctx.scratch.root):
        io.say(cat.t("scratchmove.same", folder=ctx.scratch.root))
        io.say(cat.t("cli.nothing_done"))
        return EXIT_NOTHING_DONE

    try:
        plan = sm.plan(project, ctx.paths, ctx.scratch.root, target, target_place, ctx.jobs_root)
    except sm.MoveError as error:
        _say_parts(cat, io, "scratchmove", error.code, error.detail)
        return EXIT_NOTHING_DONE
    usage = system.disk_free(pb.nearest_existing(target))
    free = usage[1] if usage else None
    level = pb.judge_room(free, plan.tree.bytes, pb.same_drive(pb.nearest_existing(target), ctx.paths.root))

    io.say(cat.t("scratchmove.head", name=project.name))
    io.say("  " + cat.t("scratchmove.from", folder=plan.source))
    io.say("  " + cat.t("scratchmove.to", folder=plan.target))
    _say_tree(cat, io, plan.tree, "  ")
    for warning in warnings:
        io.say("  " + warning_text(cat, warning))
    if level is Level.NOT_ENOUGH:
        io.say(cat.t("scratchmove.no_room", need=size_text(plan.tree.bytes), free=size_text(free or 0)))
        io.say(cat.t("cli.nothing_done"))
        return EXIT_NOTHING_DONE
    if level is Level.TIGHT:
        io.say(cat.t("scratchmove.tight"))
    for key in ("scratchmove.how.copy", "scratchmove.how.switch", "scratchmove.how.old"):
        io.say("  " + cat.t(key))
    declined = _confirmed(parsed, cat.t("scratchmove.question"), cat, io)
    if declined is not None:
        return declined

    try:
        sm.prepare_target(plan)
        copied = sm.copy_tree(plan, _progress(cat, io))
        sm.check_copy(plan)
        io.say(cat.t("scratchmove.copied", copied=copied.copied, already=copied.already))
        moved = sm.switch(project, ctx.paths, plan, ctx.jobs_root)
    except sm.MoveError as error:
        _say_parts(cat, io, "scratchmove", error.code, error.detail)
        return EXIT_PROBLEM
    io.say(cat.t("scratchmove.switched", name=moved.name, folder=plan.target))
    return _offer_old(project, ctx, cat, io)


# ---------------------------------------------------------------- the front

def _help(cat: Catalog, io: IO) -> int:
    io.say(cat.t("scratchmove.title"))
    io.say(cat.t("scratchmove.usage.head"))
    for key in USAGE:
        io.say("  " + cat.t(key))
    return EXIT_OK


def run_scratch(argv: Sequence[str], system: System, home: DataHome, cat: Catalog, io: IO) -> int:
    """`python3 -m voice_studio.scratch COMMAND ...`. Ctrl+C stops cleanly: the project keeps the place it had, and the same command carries on."""
    command = argv[0] if argv else "help"
    rest = list(argv[1:])
    try:
        if command in ("help", "--help", "-h"):
            return _help(cat, io)
        if command == "show":
            return _show(rest, system, home, cat, io)
        if command == "move":
            return _move(rest, system, home, cat, io)
        io.say(cat.t("cli.bad_command", command=command[:60]))
        return EXIT_NOTHING_DONE
    except KeyboardInterrupt:
        io.say(cat.t("scratchmove.interrupted"))
        return EXIT_PROBLEM
