# SPDX-License-Identifier: GPL-3.0-or-later
"""The rest of the guided setup (plan decision D3, task VS-7.1): after the system packages are in, set up the two sets of programs and open the window.

`python3 -m voice_studio` is one command that ends at the window. The first step (core/setup_flow.py) is the Ubuntu packages and is the only one that needs administrator rights. This
file adds, in order: the programs that listen to recordings and make training sets (small), the programs that train the voice (large), and the window. Nothing here decides how a set
of programs is built or what the person agrees to: each step is the terminal front that already exists (core/buildenv_flow.py), so it shows what it will do, asks once and can be
refused. A no to one step does not stop the next; a step that goes wrong stops everything after it, because the window would open on programs that are not there. The same command
again carries on from where it stopped and asks nothing it has been told already.

The window is only started after its own check says it can start here (the same check as `python3 -m voice_studio.window --check`), and its reason is shown in plain words if not. It is
started apart from this program and not waited for, so the terminal is free again.
Exit codes as the other fronts: 0 done, 1 something stopped or the window could not open, 2 nothing was done (nobody to ask).
"""
from __future__ import annotations

from typing import Callable, Optional, Sequence

from .buildenv_flow import BuildOptions, run_build_env
from .envspec import EnvSpec
from .paths import DataHome
from .registry import Registry
from .setup_flow import IO, Options
from .system import System
from .text import Catalog
from .windowcli import WINDOW_COMMAND

EXIT_OK, EXIT_PROBLEM, EXIT_NOTHING_DONE = 0, 1, 2
GUIDED_ENVS = ("studio", "training")                    # in this order: the small one first, so a person who stops after it can already bring in and listen to recordings
INTRO_WORDS = {"studio": "guided.studio.intro", "training": "guided.training.intro"}
BUILDENV_COMMAND = "python3 -m voice_studio.buildenv"
CHECK_TIMEOUT_S = 90.0                                   # loading GTK for the first time can take a while on a slow disk
Build = Callable[..., int]


def window_argv(tools_dir: str, *more: str) -> list:
    """The window, run with the system Python (the one with Ubuntu's GTK) and this tool's folder on its path. `env` sets the path so the program needs no shell."""
    return ["env", "PYTHONPATH=" + tools_dir] + WINDOW_COMMAND.split() + list(more)


def window_text(tools_dir: str, *more: str) -> str:
    """The same command as a person would type it."""
    return " ".join(["PYTHONPATH=" + tools_dir] + WINDOW_COMMAND.split() + list(more))


def run_guided(opts: Options, system: System, home: DataHome, specs: Sequence[EnvSpec], cat: Catalog, io: IO, networked: Callable, clock: Callable[[], float],
               registry: Optional[Registry], tools_dir: str, build: Build = run_build_env) -> int:
    """Everything after the packages. `build` is the environment builder's terminal front (a stand-in in tests)."""
    if not opts.yes and not io.interactive:
        io.say(cat.t("guided.cannot_ask"))
        return EXIT_NOTHING_DONE
    for env_id in GUIDED_ENVS:
        io.say("")
        io.say(cat.t(INTRO_WORDS[env_id]))
        code = build(BuildOptions(env_id=env_id, yes=opts.yes), system, home, specs, cat, io, networked, clock, registry)
        if code == EXIT_PROBLEM:
            io.say(cat.t("guided.stopped"))
            return EXIT_PROBLEM
        if code == EXIT_NOTHING_DONE:
            io.say(cat.t("guided.skipped", command="%s %s" % (BUILDENV_COMMAND, env_id)))
    io.say("")
    if opts.no_window:
        io.say(cat.t("guided.no_window", command=window_text(tools_dir)))
        return EXIT_OK
    return _open_window(system, cat, io, tools_dir)


def _open_window(system: System, cat: Catalog, io: IO, tools_dir: str) -> int:
    checked = system.run(window_argv(tools_dir, "--check"), timeout=CHECK_TIMEOUT_S)
    if checked is None:
        io.say(cat.t("guided.window_not_started", command=window_text(tools_dir, "--check")))
        return EXIT_PROBLEM
    if checked.returncode != 0:
        for line in checked.stdout.splitlines():
            if line.strip():
                io.say(line)
        io.say(cat.t("guided.window_cannot"))
        return EXIT_PROBLEM
    if not system.start(window_argv(tools_dir)):
        io.say(cat.t("guided.window_not_started", command=window_text(tools_dir, "--check")))
        return EXIT_PROBLEM
    io.say(cat.t("guided.window_opening"))
    io.say(cat.t("guided.open_again", command=window_text(tools_dir)))
    io.say(cat.t("guided.launcher_hint", command=window_text(tools_dir, "--install-launcher")))
    return EXIT_OK
