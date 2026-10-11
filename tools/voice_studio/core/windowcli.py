# SPDX-License-Identifier: GPL-3.0-or-later
"""The window's command line, before any window exists: `--check` (can the window start here, and if not, why in plain words), `--install-launcher` and `--remove-launcher` (the menu entry,
shown first and asked about), and the plain start. No GTK is imported here; the caller says what GTK found (`Toolkit`) and how to start the window, so every sentence and every refusal
is tested without a display. Exit codes as the other fronts: 0 done, 1 could not, 2 nothing done."""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Callable, Optional, Sequence

from . import launcher
from .cliargs import ArgError, parse_args
from .projects_flow import EXIT_NOTHING_DONE, EXIT_OK, EXIT_PROBLEM, say_bad_arg
from .setup_flow import IO, _said_yes
from .text import Catalog

WINDOW_COMMAND = "/usr/bin/python3 -m voice_studio.window"
INSTALL_COMMAND = "sudo apt install python3-gi gir1.2-gtk-4.0"
FLAGS = {"--check": "check", "--install-launcher": "install", "--remove-launcher": "remove", "--yes": "yes", "-y": "yes", "--selftest": "selftest"}
OPTIONS = frozenset(FLAGS)                                      # the checklist is held to these


@dataclass(frozen=True)
class Toolkit:
    """What loading GTK found: ready, or the reason it is not (a code from window/gtkload.py REASONS) and a detail for Show details."""
    ready: bool
    reason: str = ""
    detail: str = ""
    version: str = ""


PLAN_WORDS = {"new": "window.launcher.plan_new", "update": "window.launcher.plan_update"}
REASON_WORDS = {"no_gi": "window.check.no_gi", "no_gtk4": "window.check.no_gtk4", "gtk_too_old": "window.check.gtk_too_old", "no_display": "window.check.no_display"}


def _say_toolkit(tk: Toolkit, python: str, cat: Catalog, io: IO) -> None:
    io.say("  " + cat.t("window.check.python", program=python))
    if tk.version:
        io.say("  " + cat.t("window.check.gtk", version=tk.version))
    if not tk.ready:
        io.say("  " + cat.t(REASON_WORDS[tk.reason], detail=tk.detail, command=INSTALL_COMMAND))


def _check(tk: Toolkit, python: str, cat: Catalog, io: IO) -> int:
    io.say(cat.t("window.check.title"))
    _say_toolkit(tk, python, cat, io)
    if tk.ready:
        io.say(cat.t("window.check.ready", command=WINDOW_COMMAND))
        return EXIT_OK
    io.say(cat.t("window.check.not_ready"))
    return EXIT_PROBLEM


def _confirm(parsed, question: str, cat: Catalog, io: IO) -> Optional[int]:
    if "yes" in parsed.flags:
        return None
    if not io.interactive:
        io.say(cat.t("cli.cannot_ask"))
        return EXIT_NOTHING_DONE
    answer = io.ask(question + " ")
    if answer is None:
        io.say(cat.t("cli.cannot_ask"))
        return EXIT_NOTHING_DONE
    if not _said_yes(answer):
        io.say(cat.t("cli.nothing_done"))
        return EXIT_NOTHING_DONE
    return None


def _install(parsed, home: str, python: str, tools_dir: str, icon_text: str, cat: Catalog, io: IO) -> int:
    io.say(cat.t("window.launcher.title"))
    try:
        plan = launcher.plan_install(home, python, tools_dir, cat.t("window.launcher.name"), cat.t("window.launcher.comment"), icon_text)
    except launcher.LauncherError as error:
        return _launcher_problem(error, cat, io)
    if plan.refused:
        for target in plan.targets:
            if target.state == "foreign":
                io.say(cat.t("window.launcher.foreign", path=target.path))
        io.say(cat.t("window.launcher.nothing_changed"))
        return EXIT_PROBLEM
    if not plan.changes:
        io.say(cat.t("window.launcher.already"))
        return EXIT_OK
    io.say(cat.t("window.launcher.plan_head"))
    for target in plan.targets:
        if target.state in ("new", "update"):
            io.say("  " + cat.t(PLAN_WORDS[target.state], path=target.path))
    io.say(cat.t("window.launcher.plan_only"))
    declined = _confirm(parsed, cat.t("window.launcher.question"), cat, io)
    if declined is not None:
        return declined
    try:
        launcher.install(plan)
    except launcher.LauncherError as error:
        return _launcher_problem(error, cat, io)
    io.say(cat.t("window.launcher.done"))
    io.say(cat.t("window.launcher.where"))
    return EXIT_OK


def _remove(parsed, home: str, cat: Catalog, io: IO) -> int:
    io.say(cat.t("window.launcher.title"))
    plan = launcher.plan_remove(home)
    for path in plan.foreign:
        io.say(cat.t("window.launcher.foreign_left", path=path))
    if not plan.paths:
        io.say(cat.t("window.launcher.none"))
        return EXIT_OK
    io.say(cat.t("window.launcher.remove_head"))
    for path in plan.paths:
        io.say("  " + path)
    declined = _confirm(parsed, cat.t("window.launcher.remove_question"), cat, io)
    if declined is not None:
        return declined
    try:
        launcher.remove(plan)
    except launcher.LauncherError as error:
        return _launcher_problem(error, cat, io)
    io.say(cat.t("window.launcher.removed"))
    return EXIT_OK


def _launcher_problem(error: launcher.LauncherError, cat: Catalog, io: IO) -> int:
    base = "window.error.%s." % error.code
    for part in ("what", "changed", "next"):
        io.say("  " + cat.t(base + part))
    if error.detail:
        io.say("  " + cat.t("cli.technical", detail=error.detail))
    return EXIT_PROBLEM


def run_window_cli(argv: Sequence[str], home: str, python: str, tools_dir: str, icon_text: str, cat: Catalog, io: IO, *, toolkit: Callable[[], Toolkit],
                   start: Callable[[], int], selftest: Optional[Callable[[], int]] = None) -> int:
    """`python3 -m voice_studio.window [--check | --install-launcher | --remove-launcher] [--yes]`. With none of them the window starts, if GTK can."""
    try:
        parsed = parse_args(argv, flags=FLAGS, values={}, max_words=0)
    except ArgError as error:
        return say_bad_arg(error, cat, io)
    chosen = [name for name in ("check", "install", "remove", "selftest") if name in parsed.flags]
    if len(chosen) > 1:
        io.say(cat.t("window.cli.one_only"))
        return EXIT_NOTHING_DONE
    if "check" in parsed.flags:
        return _check(toolkit(), python, cat, io)
    if "install" in parsed.flags:
        return _install(parsed, home, python, tools_dir, icon_text, cat, io)
    if "remove" in parsed.flags:
        return _remove(parsed, home, cat, io)
    if "selftest" in parsed.flags:
        return selftest() if selftest is not None else EXIT_PROBLEM
    tk = toolkit()
    if not tk.ready:
        io.say(cat.t("window.check.title"))
        _say_toolkit(tk, python, cat, io)
        io.say(cat.t("window.check.not_ready"))
        return EXIT_PROBLEM
    return start()
