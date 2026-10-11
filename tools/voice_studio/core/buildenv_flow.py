# SPDX-License-Identifier: GPL-3.0-or-later
"""Setting up one set of programs from a terminal (plan task VS-0.2, until the window exists): look, say what will happen, ask once, build.

It is the terminal front of core/envbuild.py and does nothing the builder does not already do: the agreement is the setup plan's own (pip:<name>), saved the
same way, and every failure is the builder's three-part error. Every sentence comes from the text catalog, and every decision is made from a `System` and an
`IO` handed in, so it is tested without a terminal or a network. Exit codes: 0 ready, 1 it did not finish or something blocks, 2 nothing was done
(declined, nobody to ask, or an unknown option).
"""
from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from . import envbuild
from .consent import load_consent
from .describe import error_text
from .envspec import EnvSpec, normalise_name, parse_lock
from .paths import DataHome
from .preflight import GpuState, run_preflight
from .registry import Registry
from .setup_flow import IO, _said_yes
from .setupplan import PACKAGE_HOSTS, plan_setup
from .setuprun import agree
from .system import System
from .text import Catalog, size_text

EXIT_OK, EXIT_PROBLEM, EXIT_NOTHING_DONE = 0, 1, 2
DEFAULT_ENV = "training"
HEARTBEAT_S = 20.0                       # how often a quiet step says it is still working
BUILD_STATES = ("absent", "needs_work", "failed")        # the states a build can start from; "ready" needs nothing and the rest need a person
USABLE_GPU = (GpuState.OK, GpuState.SMALL, GpuState.UNKNOWN)
NEEDED_FROM_THE_SYSTEM = ("python3-venv", "python3-dev", "build-essential")      # what building programs needs; the window's own libraries are not needed to do it


@dataclass(frozen=True)
class BuildOptions:
    env_id: str = DEFAULT_ENV
    check: bool = False          # only look: exit 0 if ready, 1 if not
    yes: bool = False            # the person already said yes (typed on the command line)
    verbose: bool = False        # print every line the installer prints, not only a sign of life now and then


def parse_build_options(argv: Sequence[str]) -> Tuple[Optional[BuildOptions], str]:
    """(options, "") or (None, the first thing that is not understood). One name of a set of programs may be given."""
    flags = {"--check": "check", "--yes": "yes", "-y": "yes", "--verbose": "verbose", "-v": "verbose"}
    chosen: Dict[str, object] = {}
    named = False
    for arg in argv:
        if arg in flags:
            chosen[flags[arg]] = True
        elif not arg.startswith("-") and not named:
            chosen["env_id"], named = arg, True
        else:
            return None, arg
    return BuildOptions(**chosen), ""


def duration_text(cat: Catalog, seconds: float) -> str:
    whole = max(0, int(round(seconds)))
    if whole < 60:
        return cat.t("buildenv.seconds", seconds=whole)
    return cat.t("buildenv.minutes_seconds", minutes=whole // 60, seconds=whole % 60)


class _Progress:
    """Turns the builder's events into lines: a step starting, finishing (with how long it took), being kept, or a quiet one still working."""

    def __init__(self, cat: Catalog, io: IO, clock: Callable[[], float], verbose: bool):
        self.cat, self.io, self.clock, self.verbose = cat, io, clock, verbose
        self.started: Dict[str, float] = {}
        self.last_sign = 0.0

    def _step(self, step: str) -> str:
        key = "env.step." + step
        return self.cat.t(key) if self.cat.has(key) else step

    def __call__(self, event: envbuild.Event) -> None:
        now = self.clock()
        if event.kind == "start":
            self.started[event.step] = self.last_sign = now
            self.io.say("  " + self.cat.t("buildenv.step_start", step=self._step(event.step)))
        elif event.kind == "done":
            took = now - self.started.get(event.step, now)
            self.io.say("  " + self.cat.t("buildenv.step_done", step=self._step(event.step), time=duration_text(self.cat, took)))
        elif event.kind == "kept":
            self.io.say("  " + self.cat.t("buildenv.step_kept", step=self._step(event.step)))
        elif event.kind == "skipped":
            pass                                                      # said once, at the end, with every other probe that was not tried
        elif event.kind == "line" and event.text.strip():
            if self.verbose:
                self.io.say("    " + event.text.rstrip())
            elif now - self.last_sign >= HEARTBEAT_S:
                self.last_sign = now
                self.io.say("    " + self.cat.t("buildenv.still_working", last=event.text.strip()[:90]))


def _lock_names(spec: EnvSpec, ctx: envbuild.Context) -> List[str]:
    try:
        pins, _ = parse_lock(ctx.read_lock(spec).decode("utf-8"))
    except (OSError, UnicodeDecodeError):
        return []
    return [p.name for p in pins]


def _say_error(cat: Catalog, io: IO, error: envbuild.EnvError) -> None:
    parts = error_text(cat, "env", error.code)
    io.say("  " + parts.what)
    io.say("  " + parts.changed)
    io.say("  " + parts.next)
    if error.detail:
        io.say("  " + cat.t("buildenv.technical", detail=error.detail))


def run_build_env(opts: BuildOptions, system: System, home: DataHome, specs: Sequence[EnvSpec], cat: Catalog, io: IO, networked: Callable,
                  clock: Callable[[], float], registry: Optional[Registry] = None, seams: Optional[Dict[str, object]] = None) -> int:
    """`seams` replaces parts of the builder's context (where the shipped lock and native files are read from, the downloader): for tests only.
    Ctrl+C at any point (while asked, or while it works) stops cleanly: what was finished is kept, and the same command carries on."""
    try:
        return _run(opts, system, home, specs, cat, io, networked, clock, registry, seams)
    except KeyboardInterrupt:
        io.say(cat.t("buildenv.interrupted"))
        return EXIT_PROBLEM


def _run(opts: BuildOptions, system: System, home: DataHome, specs: Sequence[EnvSpec], cat: Catalog, io: IO, networked: Callable,
         clock: Callable[[], float], registry: Optional[Registry], seams: Optional[Dict[str, object]]) -> int:
    registry = registry if registry is not None else Registry(())
    io.say(cat.t("buildenv.title"))
    spec = next((s for s in specs if s.id == opts.env_id), None)
    if spec is None:
        io.say(cat.t("buildenv.unknown", name=opts.env_id, names=", ".join(s.id for s in specs)))
        return EXIT_NOTHING_DONE
    io.say(cat.t(spec.why_key))
    io.say(cat.t("buildenv.looking"))

    report = run_preflight(system)
    absent = [r.package for r in report.missing if r.package in NEEDED_FROM_THE_SYSTEM]
    if absent:
        io.say(cat.t("buildenv.needs_setup", packages=", ".join(absent)))
        return EXIT_PROBLEM
    consent = load_consent(Path(home.consent_file))
    ctx = envbuild.Context(system=system, home=home, registry=registry, consent=consent, gpu_ok=report.gpu.state in USABLE_GPU, networked=networked)
    if seams:
        ctx = dataclasses.replace(ctx, **seams)

    inspection = envbuild.inspect(spec, ctx)
    io.say(cat.t("buildenv.state", state=cat.t("env.state." + inspection.state)))
    if inspection.error is not None:
        _say_error(cat, io, inspection.error)
    if inspection.state == "ready":
        io.say(cat.t("buildenv.ready_already", folder=inspection.env_dir))
        return EXIT_OK
    if inspection.state not in BUILD_STATES:
        return EXIT_PROBLEM
    if opts.check:
        io.say(cat.t("buildenv.check_not_ready"))
        return EXIT_PROBLEM

    folder = envbuild.environment_dir(spec, ctx)
    disk = system.disk_free(home.home)
    mine = Registry(tuple(i for i in registry.items if spec.source is not None and i.id == spec.source.item_id))      # the agreement covers this one set of programs only
    plan = plan_setup(mine, [spec], free={"home": disk[1] if disk else None})
    io.say(cat.t("buildenv.folder", folder=folder))
    if disk:
        io.say(cat.t("buildenv.space", size=size_text(spec.approx_size_bytes), free=size_text(disk[1])))
    else:
        io.say(cat.t("buildenv.space_unknown", size=size_text(spec.approx_size_bytes)))
    io.say(cat.t("buildenv.sites", sites=", ".join(PACKAGE_HOSTS)))
    if any(normalise_name(n).startswith("nvidia-") for n in _lock_names(spec, ctx)):
        io.say(cat.t("buildenv.nvidia"))
    if not opts.yes:
        answer = io.ask(cat.t("buildenv.question") + " ") if io.interactive else None
        if answer is None:
            io.say(cat.t("buildenv.cannot_ask"))
            return EXIT_NOTHING_DONE
        if not _said_yes(answer):
            io.say(cat.t("buildenv.declined"))
            return EXIT_NOTHING_DONE
    try:
        saved = agree(plan, mine, home)
    except OSError as exc:                                       # nothing is downloaded on a yes that could not be kept
        io.say(cat.t("buildenv.not_agreed"))
        io.say("  " + cat.t("buildenv.technical", detail=exc.strerror or type(exc).__name__))
        return EXIT_PROBLEM
    ctx = dataclasses.replace(ctx, consent=saved, on_event=_Progress(cat, io, clock, opts.verbose))

    io.say(cat.t("buildenv.working"))
    begun = clock()
    result = envbuild.build(spec, ctx)
    took = duration_text(cat, clock() - begun)
    if not result.ok:
        io.say(cat.t("buildenv.failed", time=took))
        _say_error(cat, io, result.error)
        if result.error.tail:
            io.say("  " + cat.t("buildenv.tail_header"))
            for line in result.error.tail:
                io.say("    " + line)
        io.say("  " + cat.t("buildenv.log", path=result.env_dir + "/" + envbuild.LOG_NAME))
        return EXIT_PROBLEM
    io.say(cat.t("buildenv.ready", time=took))
    io.say(cat.t("buildenv.where", folder=result.env_dir))
    if result.skipped:
        io.say(cat.t("buildenv.skipped", names=", ".join(result.skipped)))
    return EXIT_OK


def refuse_build_option(option: str, cat: Catalog, io: IO) -> int:
    io.say(cat.t("buildenv.bad_option", option=option))
    return EXIT_NOTHING_DONE
