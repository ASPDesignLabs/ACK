# SPDX-License-Identifier: GPL-3.0-or-later
"""The terminal front for refreshing the tool (plan task VS-6.6, decision P18): `python3 -m voice_studio.refresh check | repair | rebuild | older`.

The decisions are in core/refresh.py. This shows what will happen, asks first (a typed yes, or `--yes`; nobody to ask means nothing is done), and says what happened in plain words.
`check` and a plain `older` only look. `repair` mends only what `check` found broken. `rebuild` builds a second whole copy of a set of programs beside the one in use, by the same builder
and the same questions as the first setup, and switches to it only when it has passed its own check. Nothing here touches a project, a recording, a round, a finished voice or a backup.
Exit codes as the other fronts: 0 done (or in order), 1 something is broken or failed, 2 nothing was done (declined, nobody to ask, an option or a name that could not be told).
"""
from __future__ import annotations

import dataclasses
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from . import envbuild, envgen, fetch, projectbackup as pb, refresh as rf
from .buildenv_flow import USABLE_GPU, BuildOptions, duration_text, run_build_env
from .guided_flow import GUIDED_ENVS
from .cliargs import ArgError, parse_args
from .consent import load_consent
from .describe import error_text
from .envspec import EnvSpec
from .paths import DataHome
from .preflight import run_preflight
from .projects_flow import EXIT_NOTHING_DONE, EXIT_OK, EXIT_PROBLEM, say_bad_arg
from .registry import Registry
from .rounds_flow import YES, _ask_yes, _confirmed
from .setup_flow import IO
from .system import System
from .text import Catalog, size_text

REFRESH_COMMAND = "python3 -m voice_studio.refresh"
SETUP_COMMAND = "python3 -m voice_studio"
BACKUP_COMMAND = "python3 -m voice_studio.backup"
COMMANDS = ("check", "repair", "rebuild", "older", "help")
QUICK = {"--quick": "quick"}
OPTIONS = {"check": frozenset(QUICK), "repair": frozenset(QUICK) | frozenset(YES), "rebuild": frozenset(YES) | frozenset({"--programs"}), "older": frozenset({"--remove"}) | frozenset(YES)}      # the checklist is held to these
USAGE = ("refresh.usage.check", "refresh.usage.repair", "refresh.usage.rebuild", "refresh.usage.older", "refresh.usage.options")
BACKUP_ADVICE = {pb.NEVER: "refresh.rebuild.backup_never", pb.CHANGED: "refresh.rebuild.backup_changed"}         # what is said of a project that has no up-to-date backup
OLDER_STATES = ("ready", "building", "failed")                          # what a copy's own record can say; each has words under refresh.older.state.<id>
MAX_ROWS = 10


def voice_name(item_id: str) -> str:
    """The plain name of a starting voice: its registry id without the word every one begins with ("voice-mike" is Mike)."""
    return item_id[len("voice-"):].capitalize() if item_id.startswith("voice-") else item_id


def mid(words: str) -> str:
    """A name as it reads in the middle of a sentence: the first letter small, the rest as it is (a person's name keeps its capital)."""
    return words[:1].lower() + words[1:]


def subject_name(cat: Catalog, area: str, subject: str) -> str:
    if area == rf.PROGRAMS:
        key = "refresh.name." + subject
        return cat.t(key) if cat.has(key) else cat.t("refresh.name.other", id=subject)
    if area == rf.NOTE:
        return cat.t("refresh.note." + subject)
    return cat.t("refresh.name.speech") if subject == rf.SPEECH else cat.t("refresh.name.voice", name=voice_name(subject))


def _error(cat: Catalog, io: IO, error: rf.RefreshError) -> None:
    parts = error_text(cat, "refresh", error.code)
    io.say(parts.what)
    io.say(parts.changed)
    io.say(parts.next)
    if error.detail:
        io.say("  " + cat.t("cli.technical", detail=error.detail))


def _context(home: DataHome, system: System, registry: Registry, networked: Callable, seams: Optional[Dict[str, object]]) -> envbuild.Context:
    report = run_preflight(system)
    ctx = envbuild.Context(system=system, home=home, registry=registry, consent=load_consent(Path(home.consent_file)), gpu_ok=report.gpu.state in USABLE_GPU, networked=networked)
    return dataclasses.replace(ctx, **seams) if seams else ctx


# ---------------------------------------------------------------- saying what a look found

def reason_text(cat: Catalog, finding: rf.Finding) -> str:
    detail = finding.detail
    if finding.reason == "ready_untried":
        detail = ", ".join(cat.t("env.probe." + p) if cat.has("env.probe." + p) else p for p in finding.detail.split(", ") if p)
    elif finding.reason == "probe_failed":
        detail = cat.t("env.probe." + finding.detail) if cat.has("env.probe." + finding.detail) else finding.detail
    elif finding.reason == "cannot_build" and cat.has("env.error.%s.what" % finding.detail):
        parts = error_text(cat, "env", finding.detail)
        detail = parts.what + " " + parts.next
    steps = ", ".join(cat.t("env.step." + s) if cat.has("env.step." + s) else s for s in finding.steps)
    return cat.t("refresh.reason." + finding.reason, detail=detail, steps=steps)


def _say_finding(finding: rf.Finding, cat: Catalog, io: IO) -> None:
    io.say("  %s %s: %s" % ("[%s]" % cat.t("refresh.tag." + finding.status), subject_name(cat, finding.area, finding.subject), reason_text(cat, finding)))


def _say_next(problems: Sequence[rf.Finding], cat: Catalog, io: IO) -> None:
    """What to do about each problem: the one command that mends what can be mended, and for each problem that needs more, the command that does."""
    if any(f.fix in ("resume", "fetch", "set_aside") for f in problems):
        io.say(cat.t("refresh.next_repair", command=REFRESH_COMMAND + " repair"))
    for finding in problems:
        name = mid(subject_name(cat, finding.area, finding.subject))
        if finding.fix == "rebuild":
            io.say(cat.t("refresh.next_rebuild", name=name, command="%s rebuild --programs %s" % (REFRESH_COMMAND, finding.subject)))
        elif finding.fix == "setup":
            io.say(cat.t("refresh.next_setup", name=name, command=SETUP_COMMAND))


def _say_report(report: rf.Report, cat: Catalog, io: IO) -> None:
    for finding in report.findings:
        _say_finding(finding, cat, io)
    problems = report.problems
    not_set_up = tuple(f for f in report.findings if f.fix == "setup")
    if not problems:
        io.say(cat.t("refresh.in_order"))
        _say_next(not_set_up, cat, io)
        return
    io.say(cat.count("refresh.problems", len(problems)))
    _say_next(problems + not_set_up, cat, io)


def _looking(cat: Catalog, io: IO, probes: bool):
    """The line said before each thing is looked at, because running the programs' own checks and reading the downloads take a while. Notes are quick and not announced."""
    def announce(area: str, subject: str) -> None:
        if area == rf.NOTE or (area == rf.PROGRAMS and not probes):
            return
        io.say("  " + cat.t("refresh.looking_at", what=mid(subject_name(cat, area, subject))))
    return announce


def _look(home: DataHome, registry: Registry, specs: Sequence[EnvSpec], ctx: envbuild.Context, cat: Catalog, io: IO, probes: bool) -> rf.Report:
    io.say(cat.t("refresh.looking"))
    return rf.look(home, registry, specs, ctx, probes=probes, announce=_looking(cat, io, probes))


# ---------------------------------------------------------------- check

def _check(args: Sequence[str], home: DataHome, system: System, registry: Registry, specs: Sequence[EnvSpec], networked: Callable, seams, cat: Catalog, io: IO) -> int:
    try:
        parsed = parse_args(args, flags=QUICK, values={}, max_words=0)
    except ArgError as error:
        return say_bad_arg(error, cat, io)
    io.say(cat.t("refresh.title"))
    ctx = _context(home, system, registry, networked, seams)
    report = _look(home, registry, specs, ctx, cat, io, "quick" not in parsed.flags)
    _say_report(report, cat, io)
    return EXIT_OK if report.in_order else EXIT_PROBLEM


# ---------------------------------------------------------------- repair

def _say_repair_plan(plan: rf.RepairPlan, cat: Catalog, io: IO) -> None:
    io.say(cat.t("refresh.repair.head"))
    for finding in plan.resume:
        steps = ", ".join(cat.t("env.step." + s) for s in finding.steps) or cat.t("env.step.self_test")
        io.say("  " + cat.t("refresh.repair.resume", name=mid(subject_name(cat, finding.area, finding.subject)), steps=steps))
    for finding in plan.fetch:
        io.say("  " + cat.t("refresh.repair.fetch", name=mid(subject_name(cat, finding.area, finding.subject))))
    for finding in plan.set_aside:
        io.say("  " + cat.t("refresh.repair.set_aside", name=mid(subject_name(cat, finding.area, finding.subject))))


def _fetch_again(finding: rf.Finding, home: DataHome, registry: Registry, ctx: envbuild.Context, clock: Callable[[], float], cat: Catalog, io: IO) -> None:
    name = subject_name(cat, finding.area, finding.subject)
    wanted = rf.items_to_fetch(home, registry, [finding])
    if not wanted:
        io.say("  " + cat.t("refresh.repair.nothing_to_fetch", name=name))
        return
    for item, folder in wanted:
        io.say("  " + cat.t("refresh.repair.fetching", name=mid(name)))
        try:
            fetch.fetch_patiently(item, folder, ctx.consent, on_wait=lambda wait: io.say("  " + cat.t("connection.offline_again", seconds=wait.pause_s, waited=duration_text(cat, wait.waited_s))),
                                  on_back=lambda: io.say("  " + cat.t("connection.online")), sleep=ctx.sleep, clock=clock, patience=ctx.patience, fetcher=ctx.fetcher)
        except fetch.FetchError as error:
            parts = error_text(cat, "fetch", error.code)
            io.say("  " + cat.t("refresh.repair.fetch_failed", name=name))
            for line in (parts.what, parts.changed, parts.next):
                io.say("  " + line)
            return
    io.say("  " + cat.t("refresh.repair.fetched", name=name))


def _repair(args: Sequence[str], home: DataHome, system: System, registry: Registry, specs: Sequence[EnvSpec], networked: Callable, clock: Callable[[], float], now: Optional[datetime],
            seams, cat: Catalog, io: IO) -> int:
    try:
        parsed = parse_args(args, flags={**QUICK, **YES}, values={}, max_words=0)
    except ArgError as error:
        return say_bad_arg(error, cat, io)
    io.say(cat.t("refresh.title"))
    probes = "quick" not in parsed.flags
    ctx = _context(home, system, registry, networked, seams)
    report = _look(home, registry, specs, ctx, cat, io, probes)
    plan = rf.plan_repair(report)
    if report.in_order:
        io.say(cat.t("refresh.repair.nothing"))
        return EXIT_OK
    if not plan.work:
        for finding in plan.needs_more:
            _say_finding(finding, cat, io)
        io.say(cat.t("refresh.repair.cannot"))
        _say_next(plan.needs_more, cat, io)
        return EXIT_PROBLEM
    _say_repair_plan(plan, cat, io)
    if plan.needs_more:
        io.say(cat.t("refresh.repair.more_head"))
        for finding in plan.needs_more:
            _say_finding(finding, cat, io)
        _say_next(plan.needs_more, cat, io)
    declined = _confirmed(parsed, cat.t("refresh.repair.question"), cat, io)
    if declined is not None:
        return declined
    for finding in plan.set_aside:
        name = subject_name(cat, finding.area, finding.subject)
        try:
            moved = rf.set_aside(home, finding.subject, now)
        except OSError as exc:
            io.say("  " + cat.t("refresh.repair.aside_failed", name=name))
            io.say("    " + cat.t("cli.technical", detail=exc.strerror or type(exc).__name__))
            continue
        io.say("  " + cat.t("refresh.repair.aside_done", name=name, path=moved))
    for finding in plan.fetch:
        _fetch_again(finding, home, registry, ctx, clock, cat, io)
    for finding in plan.resume:
        code = run_build_env(BuildOptions(env_id=finding.subject), system, home, specs, cat, io, networked, clock, registry, seams)
        if code == EXIT_PROBLEM:
            break                                                           # a build that went wrong stops everything after it, as in the first setup; one that was declined does not
    io.say(cat.t("refresh.repair.after"))
    again = rf.look(home, registry, specs, _context(home, system, registry, networked, seams), probes=probes)
    _say_report(again, cat, io)
    return EXIT_OK if again.in_order else EXIT_PROBLEM


# ---------------------------------------------------------------- older copies

def _say_older(older: rf.Older, cat: Catalog, io: IO) -> None:
    io.say(cat.count("refresh.older.head", len(older.copies)))
    for copy in older.copies[:MAX_ROWS]:
        state = cat.t("refresh.older.state." + copy.state) if copy.state in OLDER_STATES else copy.state
        io.say("  " + cat.t("refresh.older.row", folder=copy.folder, size=size_text(copy.bytes), state=state))
    if len(older.copies) > MAX_ROWS:
        io.say("  " + cat.count("refresh.older.more", len(older.copies) - MAX_ROWS))
    io.say(cat.t("refresh.older.total", size=size_text(sum(c.bytes for c in older.copies))))


def _remove_older(older: rf.Older, home: DataHome, specs: Sequence[EnvSpec], ctx: envbuild.Context, cat: Catalog, io: IO) -> int:
    try:
        result = rf.remove_older(home, specs, ctx, older.copies)
    except rf.RefreshError as error:
        _error(cat, io, error)
        return EXIT_PROBLEM
    io.say(cat.count("refresh.older.done", len(result.removed), size=size_text(result.bytes)))
    if result.failed:
        io.say(cat.t("refresh.older.failed_head"))
        for folder, reason in result.failed[:MAX_ROWS]:
            io.say("  " + cat.t("refresh.older.failed_row", folder=folder, reason=reason))
    return EXIT_PROBLEM if result.failed else EXIT_OK


def _older(args: Sequence[str], home: DataHome, system: System, registry: Registry, specs: Sequence[EnvSpec], networked: Callable, seams, cat: Catalog, io: IO) -> int:
    try:
        parsed = parse_args(args, flags={"--remove": "remove", **YES}, values={}, max_words=0)
    except ArgError as error:
        return say_bad_arg(error, cat, io)
    io.say(cat.t("refresh.title"))
    ctx = _context(home, system, registry, networked, seams)
    older = rf.older_copies(home, specs, ctx)
    if older.left_alone:
        io.say(cat.count("refresh.older.left_alone", older.left_alone))
    if not older.copies:
        io.say(cat.t("refresh.older.none"))
        return EXIT_OK
    _say_older(older, cat, io)
    if "remove" not in parsed.flags:
        io.say(cat.t("refresh.older.how", command=REFRESH_COMMAND + " older --remove"))
        return EXIT_OK
    declined = _confirmed(parsed, cat.count("refresh.older.question", len(older.copies), size=size_text(sum(c.bytes for c in older.copies))), cat, io)
    if declined is not None:
        return declined
    return _remove_older(older, home, specs, ctx, cat, io)


# ---------------------------------------------------------------- rebuild

def _say_rebuild_preface(spec: EnvSpec, home: DataHome, cat: Catalog, io: IO) -> None:
    name = mid(subject_name(cat, rf.PROGRAMS, spec.id))
    io.say(cat.t("refresh.rebuild.head", name=name))
    for key in ("refresh.rebuild.beside", "refresh.rebuild.old_works", "refresh.rebuild.untouched"):
        io.say("  " + cat.t(key))
    behind = rf.unprotected(home)
    if behind:
        io.say(cat.t("refresh.rebuild.backup_head"))
        for project, why in behind:
            io.say("  " + cat.t(BACKUP_ADVICE[why], name=project.name, command="%s now --project %s" % (BACKUP_COMMAND, project.id)))


def _rebuild(args: Sequence[str], home: DataHome, system: System, registry: Registry, specs: Sequence[EnvSpec], networked: Callable, clock: Callable[[], float], seams,
             cat: Catalog, io: IO) -> int:
    try:
        parsed = parse_args(args, flags=YES, values={"--programs": "programs"}, max_words=0)
    except ArgError as error:
        return say_bad_arg(error, cat, io)
    io.say(cat.t("refresh.title"))
    ctx = _context(home, system, registry, networked, seams)
    wanted = parsed.values.get("programs")
    if wanted is not None and not any(s.id == wanted for s in specs):
        io.say(cat.t("refresh.rebuild.unknown", name=wanted[:60], names=", ".join(s.id for s in specs)))
        return EXIT_NOTHING_DONE
    chosen = [s for s in specs if wanted in (None, s.id) and envbuild.inspect(s, ctx).state != "absent"]
    if not chosen:
        io.say(cat.t("refresh.rebuild.nothing_set_up", command=SETUP_COMMAND))
        return EXIT_NOTHING_DONE
    for spec in chosen:
        try:
            number = rf.next_generation(home, spec.id)
        except rf.RefreshError as error:
            _error(cat, io, error)
            return EXIT_PROBLEM
        _say_rebuild_preface(spec, home, cat, io)
        code = run_build_env(BuildOptions(env_id=spec.id, yes="yes" in parsed.flags), system, home, specs, cat, io, networked, clock, registry,
                             {**(seams or {}), "generations": rf.with_generation(ctx, spec.id, number).generations})
        if code != EXIT_OK:
            io.say(cat.t("refresh.rebuild.not_switched", name=mid(subject_name(cat, rf.PROGRAMS, spec.id))))
            return code
        try:
            rf.note_generation(home, spec.id, number)
        except rf.RefreshError as error:
            _error(cat, io, error)
            return EXIT_PROBLEM
        io.say(cat.t("refresh.rebuild.switched", name=mid(subject_name(cat, rf.PROGRAMS, spec.id))))
    return _offer_old(home, system, registry, specs, networked, seams, cat, io)


def _offer_old(home: DataHome, system: System, registry: Registry, specs: Sequence[EnvSpec], networked: Callable, seams, cat: Catalog, io: IO) -> int:
    """The old copy is not needed now. It is offered for removal with a typed yes; `--yes` on the line does not answer this, because it was given for the building."""
    ctx = _context(home, system, registry, networked, seams)
    older = rf.older_copies(home, specs, ctx)
    if not older.copies:
        return EXIT_OK
    _say_older(older, cat, io)
    answer = _ask_yes(io, cat.count("refresh.older.question", len(older.copies), size=size_text(sum(c.bytes for c in older.copies))))
    if not answer:
        io.say(cat.t("refresh.older.kept", command=REFRESH_COMMAND + " older --remove"))
        return EXIT_OK
    return _remove_older(older, home, specs, ctx, cat, io)


# ---------------------------------------------------------------- the command

def _help(cat: Catalog, io: IO) -> int:
    io.say(cat.t("refresh.title"))
    io.say(cat.t("refresh.usage.head"))
    for key in USAGE:
        io.say("  " + cat.t(key))
    return EXIT_OK


def run_refresh(argv: Sequence[str], home: DataHome, cat: Catalog, io: IO, *, system: System, registry: Registry, specs: Sequence[EnvSpec], networked: Callable,
                clock: Callable[[], float], now: Optional[datetime] = None, seams: Optional[Dict[str, object]] = None) -> int:
    """`python3 -m voice_studio.refresh COMMAND ...`. `seams` replaces parts of the builder's context (where the shipped lock files are read from, the downloader): for tests only.
    Ctrl+C stops cleanly at any point; what was finished is kept."""
    command = argv[0] if argv else "help"
    rest = list(argv[1:])
    specs = sorted(specs, key=lambda s: (GUIDED_ENVS.index(s.id) if s.id in GUIDED_ENVS else len(GUIDED_ENVS), s.id))          # the small set first, as the first setup builds them
    try:
        if command in ("help", "--help", "-h"):
            return _help(cat, io)
        if command == "check":
            return _check(rest, home, system, registry, specs, networked, seams, cat, io)
        if command == "repair":
            return _repair(rest, home, system, registry, specs, networked, clock, now, seams, cat, io)
        if command == "rebuild":
            return _rebuild(rest, home, system, registry, specs, networked, clock, seams, cat, io)
        if command == "older":
            return _older(rest, home, system, registry, specs, networked, seams, cat, io)
        io.say(cat.t("cli.bad_command", command=command[:60]))
        return EXIT_NOTHING_DONE
    except KeyboardInterrupt:
        io.say(cat.t("refresh.interrupted"))
        return EXIT_PROBLEM
