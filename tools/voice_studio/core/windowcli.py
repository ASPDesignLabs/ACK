# SPDX-License-Identifier: GPL-3.0-or-later
"""The window's command line, before any window exists: `--check` (can the window start here, and if not, why in plain words), `--install-launcher` and `--remove-launcher` (the menu entry,
shown first and asked about), and the plain start. No GTK is imported here; the caller says what GTK found (`Toolkit`) and how to start the window, so every sentence and every refusal
is tested without a display. Exit codes as the other fronts: 0 done, 1 could not, 2 nothing done.

On WSL the menu entry is a shortcut in the person's own Windows Start menu, made through the Windows program that WSL lets Linux start (core/winshortcut.py): it needs no `sudo` and no
administrator rights. Only when Windows cannot be reached from Linux does the older way follow (a menu entry on the Linux side, and the commands that put it where WSL reads, printed
for the person; this tool never runs them)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Callable, Optional, Sequence, Tuple

from . import iconmake, launcher, winshortcut
from .cliargs import ArgError, parse_args
from .projects_flow import EXIT_NOTHING_DONE, EXIT_OK, EXIT_PROBLEM, say_bad_arg
from .setup_flow import IO, _said_yes
from .system import System
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
WIN_SHORTCUT_WORDS = {"new": "window.launcher.win_shortcut_new", "update": "window.launcher.win_shortcut_update"}
WIN_ICON_WORDS = {"new": "window.launcher.win_icon_new", "update": "window.launcher.win_icon_update"}
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


def _wsl_notes(home: str, exists: Callable[[str], bool], cat: Catalog, io: IO) -> None:
    """On WSL the Start menu is made from the system folders only (WSLg's own log lists them, and the person's `~/.local/share/applications` is not among them), so the entry is not in the
    Start menu until the two files are copied there. That needs a password, so the commands are shown for the person to run and the tool runs nothing."""
    if exists(launcher.SYSTEM_ENTRY):
        io.say(cat.t("window.launcher.wsl_present", path=launcher.SYSTEM_ENTRY))
        return
    io.say(cat.t("window.launcher.wsl_why"))
    io.say(cat.t("window.launcher.wsl_ask"))
    for command in launcher.system_copy_commands(home):
        io.say("  " + command)
    io.say(cat.t("window.launcher.wsl_after"))
    io.say(cat.t("window.launcher.wsl_undo", command=launcher.system_remove_command()))


def _install_on_windows(parsed, system: System, python: str, tools_dir: str, cat: Catalog, io: IO, icon_bytes: Callable[[], bytes], exists: Callable[[str], bool]) -> Optional[int]:
    """The Start menu shortcut on the Windows side. Returns the exit code, or None when the Windows side cannot be reached (the older steps then follow)."""
    if exists(launcher.SYSTEM_ENTRY):
        io.say(cat.t("window.launcher.wsl_present", path=launcher.SYSTEM_ENTRY))
        io.say(cat.t("window.launcher.nothing_changed"))
        return EXIT_OK
    reach = winshortcut.route(system)
    if reach is None:
        io.say(cat.t("window.launcher.no_windows_route"))
        return None
    try:
        want = winshortcut.wanted(reach.distro, tools_dir, python, cat.t("window.launcher.name"), cat.t("window.launcher.comment"), icon_bytes())
    except launcher.LauncherError as error:
        return _launcher_problem(error, cat, io)
    io.say(cat.t("window.launcher.win_looking"))
    found = winshortcut.probe(system, reach, want.name, want.distro)
    if found is None:
        io.say(cat.t("window.launcher.no_windows_route"))
        return None
    plan = winshortcut.plan_install(found, want)
    if plan.state == "no_wslg":
        return _launcher_problem(launcher.LauncherError("no_wslg"), cat, io)
    if plan.state == "wslg":
        io.say(cat.t("window.launcher.wslg_has_it", path=plan.wslg_shortcut))
        io.say(cat.t("window.launcher.nothing_changed"))
        return EXIT_OK
    if plan.state == "foreign":
        io.say(cat.t("window.launcher.foreign", path=plan.shortcut_path))
        io.say(cat.t("window.launcher.nothing_changed"))
        return EXIT_PROBLEM
    if plan.state == "same":
        io.say(cat.t("window.launcher.already"))
        io.say(cat.t("window.launcher.win_look", name=want.name))
        return EXIT_OK
    io.say(cat.t("window.launcher.win_plan_head"))
    if plan.shortcut_change != "same":
        io.say("  " + cat.t(WIN_SHORTCUT_WORDS[plan.shortcut_change], path=plan.shortcut_path, folder=plan.folder))
    if plan.icon_change != "same":
        io.say("  " + cat.t(WIN_ICON_WORDS[plan.icon_change], path=plan.icon_path))
    io.say(cat.t("window.launcher.win_plan_only"))
    declined = _confirm(parsed, cat.t("window.launcher.question"), cat, io)
    if declined is not None:
        return declined
    io.say(cat.t("window.launcher.win_making"))
    try:
        winshortcut.install(system, reach, want)
    except launcher.LauncherError as error:
        return _launcher_problem(error, cat, io)
    io.say(cat.t("window.launcher.win_done"))
    io.say(cat.t("window.launcher.win_look", name=want.name))
    io.say(cat.t("window.launcher.win_slow"))
    io.say(cat.t("window.launcher.win_undo"))
    return EXIT_OK


def _install(parsed, home: str, python: str, tools_dir: str, icon_text: str, cat: Catalog, io: IO, on_wsl: bool, exists: Callable[[str], bool], system: Optional[System],
             icon_bytes: Callable[[], bytes]) -> int:
    io.say(cat.t("window.launcher.title"))
    if on_wsl and system is not None:
        outcome = _install_on_windows(parsed, system, python, tools_dir, cat, io, icon_bytes, exists)
        if outcome is not None:
            return outcome
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
        if on_wsl:
            _wsl_notes(home, exists, cat, io)
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
    if on_wsl:
        _wsl_notes(home, exists, cat, io)
    else:
        io.say(cat.t("window.launcher.where"))
    return EXIT_OK


def _windows_removal(system: System, cat: Catalog, io: IO) -> Optional[Tuple[winshortcut.Route, str, winshortcut.RemovalPlan]]:
    """What is on the Windows side to remove, or None when that side cannot be reached (a line says so)."""
    reach = winshortcut.route(system)
    if reach is not None:
        try:
            name = winshortcut.shortcut_name(cat.t("window.launcher.name"), reach.distro)
        except launcher.LauncherError:
            reach = None
    if reach is None:
        io.say(cat.t("window.launcher.no_windows_route_remove"))
        return None
    io.say(cat.t("window.launcher.win_looking"))
    found = winshortcut.probe(system, reach, name, reach.distro)
    if found is None:
        io.say(cat.t("window.launcher.no_windows_route_remove"))
        return None
    return reach, name, winshortcut.plan_remove(found)


def _remove(parsed, home: str, cat: Catalog, io: IO, on_wsl: bool, exists: Callable[[str], bool], system: Optional[System]) -> int:
    io.say(cat.t("window.launcher.title"))
    plan = launcher.plan_remove(home)
    for path in plan.foreign:
        io.say(cat.t("window.launcher.foreign_left", path=path))
    windows = _windows_removal(system, cat, io) if (on_wsl and system is not None) else None
    windows_paths: Tuple[str, ...] = ()
    if windows is not None:
        if windows[2].state == "foreign":
            io.say(cat.t("window.launcher.foreign_left", path=windows[2].foreign))
        elif windows[2].state == "ours":
            windows_paths = windows[2].paths
    copy_left = on_wsl and exists(launcher.SYSTEM_ENTRY)
    if not plan.paths and not windows_paths:
        io.say(cat.t("window.launcher.none"))
        if copy_left:
            io.say(cat.t("window.launcher.wsl_remove", command=launcher.system_remove_command()))
        return EXIT_OK
    io.say(cat.t("window.launcher.remove_head"))
    for path in windows_paths + tuple(plan.paths):
        io.say("  " + path)
    declined = _confirm(parsed, cat.t("window.launcher.remove_question"), cat, io)
    if declined is not None:
        return declined
    try:
        if windows_paths and windows is not None and system is not None:
            io.say(cat.t("window.launcher.win_removing"))
            winshortcut.remove(system, windows[0], windows[1], windows[0].distro)
        if plan.paths:
            launcher.remove(plan)
    except launcher.LauncherError as error:
        return _launcher_problem(error, cat, io)
    io.say(cat.t("window.launcher.removed"))
    if copy_left:
        io.say(cat.t("window.launcher.wsl_remove", command=launcher.system_remove_command()))
    return EXIT_OK


def _launcher_problem(error: launcher.LauncherError, cat: Catalog, io: IO) -> int:
    base = "window.error.%s." % error.code
    for part in ("what", "changed", "next"):
        io.say("  " + cat.t(base + part))
    if error.detail:
        io.say("  " + cat.t("cli.technical", detail=error.detail))
    return EXIT_PROBLEM


def run_window_cli(argv: Sequence[str], home: str, python: str, tools_dir: str, icon_text: str, cat: Catalog, io: IO, *, toolkit: Callable[[], Toolkit],
                   start: Callable[[], int], selftest: Optional[Callable[[], int]] = None, on_wsl: bool = False, exists: Callable[[str], bool] = os.path.exists, system: Optional[System] = None,
                   icon_bytes: Callable[[], bytes] = iconmake.ico_bytes) -> int:
    """`python3 -m voice_studio.window [--check | --install-launcher | --remove-launcher] [--yes]`. With none of them the window starts, if GTK can.
    `system` is how the Windows side is reached on WSL; without it only the Linux side is looked at."""
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
        return _install(parsed, home, python, tools_dir, icon_text, cat, io, on_wsl, exists, system, icon_bytes)
    if "remove" in parsed.flags:
        return _remove(parsed, home, cat, io, on_wsl, exists, system)
    if "selftest" in parsed.flags:
        return selftest() if selftest is not None else EXIT_PROBLEM
    tk = toolkit()
    if not tk.ready:
        io.say(cat.t("window.check.title"))
        _say_toolkit(tk, python, cat, io)
        io.say(cat.t("window.check.not_ready"))
        return EXIT_PROBLEM
    return start()
