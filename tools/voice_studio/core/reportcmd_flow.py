# SPDX-License-Identifier: GPL-3.0-or-later
"""The terminal front for the problem report (plan task VS-6.4, decisions D22 and P22): `python3 -m voice_studio.report show | save --to FILE`.

The report is built by core/report.py (plan task VS-1.8) and holds versions, the checks on this computer, the problem the person names, how a task ended and, only when asked, the end
of that task's log; names and folders are blanked and there is no place in it for a recording or a phrase. `show` builds it and prints all of it, and changes nothing. `save` prints the same
text, asks once (a typed yes, or `--yes`; nobody to ask means nothing is written) and writes exactly the text that was shown to the one file the person named, never replacing a file unless
`--replace` was given. Nothing here sends anything anywhere, and no folder is made for it.
Exit codes as the other fronts: 0 done, 1 the file could not be saved, 2 nothing was done (declined, nobody to ask, an option or a place that could not be used).
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Optional, Sequence

from . import jobs, preflight, report as rp, reportcmd as rc
from .cliargs import ArgError, parse_args
from .describe import error_text
from .paths import DataHome
from .project import list_projects
from .projects_flow import EXIT_NOTHING_DONE, EXIT_OK, EXIT_PROBLEM, say_bad_arg
from .reportcmd import ReportError
from .rounds_flow import YES, _confirmed
from .setup_flow import IO
from .system import System
from .text import Catalog

COMMANDS = ("show", "save", "help")
SHOW_VALUES = {"--problem": "problem", "--detail": "detail", "--step": "step", "--job": "job"}
SHOW_FLAGS = {"--include-log": "log"}
SAVE_VALUES = {**SHOW_VALUES, "--to": "to"}
SAVE_FLAGS = {**SHOW_FLAGS, "--replace": "replace", **YES}
OPTIONS = {"show": frozenset(SHOW_VALUES) | frozenset(SHOW_FLAGS), "save": frozenset(SAVE_VALUES) | frozenset(SAVE_FLAGS)}          # the checklist is held to these
USAGE = ("reportcmd.usage.show", "reportcmd.usage.save", "reportcmd.usage.blanked", "reportcmd.usage.options")


def _say_error(cat: Catalog, io: IO, error: ReportError) -> None:
    parts = error_text(cat, "reportcmd", error.code)
    for line in (parts.what, parts.changed, parts.next):
        io.say(line)
    if error.detail:
        io.say("  " + cat.t("cli.technical", detail=error.detail))


def _build(parsed, home: DataHome, system: System, cat: Catalog, now: datetime) -> rp.Report:
    """The report the options ask for. Raises ReportError('bad_problem', 'needs_problem', 'needs_job' or 'no_job') before anything is read from the computer."""
    values, flags = parsed.values, parsed.flags
    error = None
    if values.get("problem") is not None:
        namespace, code = rc.parse_problem(cat, values["problem"])
        error = (namespace, code, values.get("detail", ""))
    elif values.get("detail") is not None:
        raise ReportError("needs_problem")
    job, lines = None, ()
    if values.get("job") is not None:
        job = rc.pick_job(home.jobs, values["job"])
        lines = tuple(jobs.tail_log(job.dir, rp.MAX_LOG_LINES))
    elif "log" in flags:
        raise ReportError("needs_job")
    projects = list_projects(home.projects).projects
    people = [(p.id, p.name) for p in projects] + [(p.consent.given_by.strip(),) * 2 for p in projects if p.consent.given_by.strip() and p.consent.given_by.strip() != p.name.strip()]      # who agreed is a name too
    inp = rp.ReportInput(now=now, identity=rp.gather_identity(system, people), step=values.get("step", "")[:rc.MAX_STEP], error=error,
                         preflight=preflight.run_preflight(system, measure=[home.root]), job=job, log_lines=lines, python_version=system.python_version())
    return rp.build_report(inp, cat, include_log="log" in flags)


def _print(report: rp.Report, cat: Catalog, io: IO) -> None:
    """All of it, exactly as it would be saved, between two lines that are not part of it."""
    io.say(cat.t("reportcmd.rule.start"))
    for line in report.text.rstrip("\n").split("\n"):
        io.say(line)
    io.say(cat.t("reportcmd.rule.end"))


def _show(args: Sequence[str], home: DataHome, system: System, cat: Catalog, io: IO, now: datetime) -> int:
    try:
        parsed = parse_args(args, flags=SHOW_FLAGS, values=SHOW_VALUES, max_words=0)
    except ArgError as error:
        return say_bad_arg(error, cat, io)
    io.say(cat.t("reportcmd.title"))
    try:
        report = _build(parsed, home, system, cat, now)
    except ReportError as error:
        _say_error(cat, io, error)
        return EXIT_NOTHING_DONE
    _print(report, cat, io)
    io.say(cat.t("reportcmd.show.kept_nothing"))
    io.say(cat.t("reportcmd.show.how", command=rc.REPORT_COMMAND + " save --to ~/problem-report.txt"))
    return EXIT_OK


def _save(args: Sequence[str], home: DataHome, system: System, cat: Catalog, io: IO, now: datetime) -> int:
    try:
        parsed = parse_args(args, flags=SAVE_FLAGS, values=SAVE_VALUES, max_words=0)
    except ArgError as error:
        return say_bad_arg(error, cat, io)
    io.say(cat.t("reportcmd.title"))
    replace = "replace" in parsed.flags
    try:
        if parsed.values.get("to") is None:
            raise ReportError("no_place")
        place = rc.check_place(parsed.values["to"], replace)
        report = _build(parsed, home, system, cat, now)
    except ReportError as error:
        _say_error(cat, io, error)
        return EXIT_NOTHING_DONE
    _print(report, cat, io)
    reason = rc.sync_reason(place)
    if reason:
        io.say(cat.t("reportcmd.save.sync", reason=reason))
    if report.included_log:
        io.say(cat.t("reportcmd.save.log"))
    if os.path.lexists(place):                                 # only with --replace: a file that was there would have been refused
        io.say(cat.t("reportcmd.save.replace", file=place))
    declined = _confirmed(parsed, cat.t("reportcmd.save.question", file=place), cat, io)
    if declined is not None:
        return declined
    try:
        size = rc.save(place, report, replace)
    except ReportError as error:
        _say_error(cat, io, error)
        return EXIT_PROBLEM
    io.say(cat.t("reportcmd.saved", size=size, file=place))
    io.say(cat.t("reportcmd.saved.next"))
    return EXIT_OK


def _help(cat: Catalog, io: IO) -> int:
    io.say(cat.t("reportcmd.title"))
    io.say(cat.t("reportcmd.usage.head"))
    for key in USAGE:
        io.say("  " + cat.t(key))
    return EXIT_OK


def run_report(argv: Sequence[str], home: DataHome, cat: Catalog, io: IO, *, system: System, now: Optional[datetime] = None) -> int:
    """`python3 -m voice_studio.report COMMAND ...`. `now` is for a test; the real one is the clock."""
    command = argv[0] if argv else "help"
    rest = list(argv[1:])
    when = now or datetime.now(timezone.utc)
    try:
        if command in ("help", "--help", "-h"):
            return _help(cat, io)
        if command == "show":
            return _show(rest, home, system, cat, io, when)
        if command == "save":
            return _save(rest, home, system, cat, io, when)
        io.say(cat.t("cli.bad_command", command=command[:60]))
        return EXIT_NOTHING_DONE
    except KeyboardInterrupt:
        io.say(cat.t("reportcmd.interrupted"))
        return EXIT_PROBLEM
