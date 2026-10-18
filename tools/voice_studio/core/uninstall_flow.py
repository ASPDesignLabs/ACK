# SPDX-License-Identifier: GPL-3.0-or-later
"""The terminal front for uninstalling the tool (plan task VS-6.3, decision P19): `python3 -m voice_studio.uninstall show | remove`.

The decisions are in core/uninstall.py. `show` only looks: it lists the programs and downloaded files that would go, what is kept, and the two things this program cannot do for itself (take the
entry out of the applications list or Start menu, and remove the folder it runs from) with the commands that do. `remove` shows the same, asks once (a typed yes, or `--yes`; nobody to ask means
nothing is done) and removes only what was shown. Nothing here touches a project, a recording, a round, a finished voice, a backup, the starting voices or the small notes.
Exit codes as the other fronts: 0 done (or looked), 1 something failed or a task is running, 2 nothing was done (declined, nobody to ask, an option or a name that could not be told).
"""
from __future__ import annotations

import os
import shlex
from typing import Callable, Optional, Sequence

from . import uninstall as un
from .cliargs import ArgError, parse_args
from .describe import error_text
from .envspec import EnvSpec
from .guided_flow import window_text
from .paths import DataHome
from .projects_flow import EXIT_NOTHING_DONE, EXIT_OK, EXIT_PROBLEM, say_bad_arg
from .rounds_flow import YES, _confirmed
from .setup_flow import IO
from .text import Catalog, size_text

UNINSTALL_COMMAND = "python3 -m voice_studio.uninstall"
SETUP_COMMAND = "python3 -m voice_studio"
COMMANDS = ("show", "remove", "help")
OPTIONS = {"show": frozenset(), "remove": frozenset(YES)}          # the checklist is held to these
USAGE = ("uninstall.usage.show", "uninstall.usage.remove", "uninstall.usage.options")
MAX_ROWS = 10
MAX_FAILED_SHOWN = 10


def code_folder(tools_dir: str) -> str:
    """The folder this tool's own files are in: the one `get.sh` made (the folder above `tools`), or the folder given when it is not laid out that way."""
    tools = tools_dir.rstrip("/")
    return os.path.dirname(tools) if os.path.basename(tools) == "tools" and os.path.dirname(tools) not in ("", "/") else tools


def _say_error(cat: Catalog, io: IO, error: un.UninstallError) -> None:
    parts = error_text(cat, "uninstall", error.code)
    for line in (parts.what, parts.changed, parts.next):
        io.say(line)


def _say_plan(plan: un.Plan, home: DataHome, cat: Catalog, io: IO, tools_dir: str) -> None:
    io.say(cat.t("uninstall.promise"))
    if plan.pieces:
        io.say(cat.t("uninstall.head"))
        for piece in plan.pieces[:MAX_ROWS]:
            io.say("  " + cat.t("uninstall.row", what=cat.t("uninstall.kind." + piece.kind), path=piece.path, size=size_text(piece.bytes)))
        if len(plan.pieces) > MAX_ROWS:
            io.say("  " + cat.count("uninstall.more", len(plan.pieces) - MAX_ROWS))
        io.say(cat.t("uninstall.total", size=size_text(plan.total_bytes)))
    else:
        io.say(cat.t("uninstall.none"))
    if plan.projects or plan.kept:
        io.say(cat.t("uninstall.kept_head"))
        if plan.projects:
            io.say("  " + cat.count("uninstall.kept.projects", plan.projects, folder=home.projects))
        for name, folder in plan.kept:
            io.say("  " + cat.t("uninstall.kept." + name, folder=folder))
    if plan.left_alone:
        io.say(cat.count("uninstall.left_alone", plan.left_alone))
    io.say(cat.t("uninstall.menu", command=window_text(tools_dir, "--remove-launcher")))
    folder = code_folder(tools_dir)
    io.say(cat.t("uninstall.code", folder=folder, command="rm -r " + shlex.quote(folder)))


def _show(args: Sequence[str], home: DataHome, specs: Sequence[EnvSpec], cat: Catalog, io: IO, tools_dir: str) -> int:
    try:
        parse_args(args, flags={}, values={}, max_words=0)
    except ArgError as error:
        return say_bad_arg(error, cat, io)
    io.say(cat.t("uninstall.title"))
    plan = un.plan(home, specs)
    _say_plan(plan, home, cat, io, tools_dir)
    if plan.pieces:
        io.say(cat.t("uninstall.how", command=UNINSTALL_COMMAND + " remove"))
    return EXIT_OK


def _remove(args: Sequence[str], home: DataHome, specs: Sequence[EnvSpec], cat: Catalog, io: IO, tools_dir: str, remove_tree: Optional[Callable] = None) -> int:
    try:
        parsed = parse_args(args, flags=YES, values={}, max_words=0)
    except ArgError as error:
        return say_bad_arg(error, cat, io)
    io.say(cat.t("uninstall.title"))
    plan = un.plan(home, specs)
    _say_plan(plan, home, cat, io, tools_dir)
    if not plan.pieces:
        return EXIT_OK
    if plan.blocked:
        _say_error(cat, io, un.UninstallError("job_running"))
        return EXIT_PROBLEM
    declined = _confirmed(parsed, cat.t("uninstall.question", size=size_text(plan.total_bytes)), cat, io)
    if declined is not None:
        return declined
    try:
        result = un.remove(home, specs, plan, **({"remove_tree": remove_tree} if remove_tree else {}))
    except un.UninstallError as error:
        _say_error(cat, io, error)
        return EXIT_PROBLEM
    if result.removed:
        io.say(cat.t("uninstall.done", size=size_text(result.bytes)))
    if result.failed:
        io.say(cat.t("uninstall.failed_head"))
        for path, why in result.failed[:MAX_FAILED_SHOWN]:
            io.say("  " + cat.t("uninstall.failed_row", path=path, reason=why))
        if len(result.failed) > MAX_FAILED_SHOWN:
            io.say("  " + cat.count("uninstall.failed_more", len(result.failed) - MAX_FAILED_SHOWN))
        return EXIT_PROBLEM
    io.say(cat.t("uninstall.again", command=SETUP_COMMAND))
    return EXIT_OK


def _help(cat: Catalog, io: IO) -> int:
    io.say(cat.t("uninstall.title"))
    io.say(cat.t("uninstall.usage.head"))
    for key in USAGE:
        io.say("  " + cat.t(key))
    return EXIT_OK


def run_uninstall(argv: Sequence[str], home: DataHome, cat: Catalog, io: IO, *, specs: Sequence[EnvSpec], tools_dir: str, remove_tree: Optional[Callable] = None) -> int:
    """`python3 -m voice_studio.uninstall COMMAND ...`. `remove_tree` replaces the remover: for tests only. Ctrl+C stops cleanly; what was removed stays removed."""
    command = argv[0] if argv else "help"
    rest = list(argv[1:])
    try:
        if command in ("help", "--help", "-h"):
            return _help(cat, io)
        if command == "show":
            return _show(rest, home, specs, cat, io, tools_dir)
        if command == "remove":
            return _remove(rest, home, specs, cat, io, tools_dir, remove_tree)
        io.say(cat.t("cli.bad_command", command=command[:60]))
        return EXIT_NOTHING_DONE
    except KeyboardInterrupt:
        io.say(cat.t("uninstall.interrupted"))
        return EXIT_PROBLEM
