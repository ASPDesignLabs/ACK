# SPDX-License-Identifier: GPL-3.0-or-later
"""The terminal step that comes first (plan decision D5): look at the computer, say what is missing, ask once, install it, and stop.

The password is typed into the terminal the person already has open, to `sudo`, which asks for it itself; nothing here reads or sees it. Every
sentence comes from the text catalog, and every decision is made from a `System` and an `IO` handed in, so it is tested without a terminal.
Exit codes: 0 ready (or installed), 1 something blocks or failed, 2 nothing was done (declined, could not ask, or an unknown option).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List, Optional, Protocol, Sequence, Tuple

from .consent import make_consent
from .describe import apt_reason, check_text
from .preflight import PreflightReport, Status, run_preflight
from .system import System
from .text import Catalog

EXIT_OK, EXIT_PROBLEM, EXIT_NOTHING_DONE = 0, 1, 2


class IO(Protocol):
    interactive: bool
    def say(self, text: str) -> None: ...
    def ask(self, prompt: str) -> Optional[str]: ...            # None when there is nobody to ask


# runs one command that reaches the network with the consent record and the ids it covers; returns its exit status
AptRunner = Callable[[object, Sequence[str], Sequence[str]], int]


@dataclass(frozen=True)
class Options:
    check: bool = False          # only look: exit 0 if ready, 1 if anything needs fixing
    dry_run: bool = False        # show what would run, change nothing, ask nothing
    yes: bool = False            # the person already said yes (typed on the command line)


def parse_options(argv: Sequence[str]) -> Tuple[Optional[Options], str]:
    """(options, "") or (None, the first option that is not known)."""
    flags = {"--check": "check", "--dry-run": "dry_run", "--yes": "yes", "-y": "yes"}
    chosen = {}
    for arg in argv:
        if arg not in flags:
            return None, arg
        chosen[flags[arg]] = True
    return Options(**chosen), ""


def apt_commands(report: PreflightReport) -> List[List[str]]:
    packages = [r.package for r in report.missing]
    return [["sudo", "apt-get", "update"], ["sudo", "apt-get", "install", "-y"] + packages] if packages else []


def _tag(cat: Catalog, status: Status) -> str:
    return "[%s]" % cat.t("setup.tag." + status.value)


def _show_checks(report: PreflightReport, cat: Catalog, io: IO) -> None:
    problems, notes = report.blockers, [c for c in report.checks if c.status is Status.WARN]
    if problems:
        io.say(cat.t("setup.problems"))
        for check in problems:
            io.say("  %s %s" % (_tag(cat, check.status), check_text(cat, check)))
    if notes:
        io.say(cat.t("setup.notes"))
        for check in notes:
            io.say("  %s %s" % (_tag(cat, check.status), check_text(cat, check)))


def _said_yes(answer: Optional[str]) -> bool:
    return answer is not None and answer.strip().lower() in ("y", "yes")


def run_setup(opts: Options, system: System, cat: Catalog, io: IO, run_apt: AptRunner) -> int:
    io.say(cat.t("setup.title"))
    io.say(cat.t("setup.looking"))
    report = run_preflight(system)
    _show_checks(report, cat, io)
    packages = list(report.missing)

    if not report.can_continue:
        io.say(cat.t("setup.check_not_ready") if opts.check else cat.t("setup.cannot_continue"))
        return EXIT_PROBLEM

    if packages:
        io.say(cat.t("setup.needs_install"))
        for req in packages:
            io.say("  " + cat.t("setup.package_line", package=req.package, reason=apt_reason(cat, req)))

    if opts.check:
        io.say(cat.t("setup.check_not_ready") if packages else cat.t("setup.check_ready"))
        return EXIT_PROBLEM if packages else EXIT_OK

    commands = apt_commands(report)
    if opts.dry_run:
        io.say(cat.t("setup.dry_run_header"))
        for command in commands:
            io.say("  " + cat.t("setup.dry_run_command", command=" ".join(command)))
        if not commands:
            io.say("  " + cat.t("setup.dry_run_none"))
        return EXIT_OK

    if packages:
        io.say(cat.t("setup.admin_note"))
        if not opts.yes:
            answer = io.ask(cat.t("setup.question") + " ") if io.interactive else None
            if answer is None:
                io.say(cat.t("setup.cannot_ask"))
                return EXIT_NOTHING_DONE
            if not _said_yes(answer):
                io.say(cat.t("setup.declined"))
                return EXIT_NOTHING_DONE
        io.say(cat.t("setup.installing"))
        consent = make_consent([], extra_ids=["apt:update"] + ["apt:" + r.package for r in packages])
        ids = [["apt:update"], ["apt:" + r.package for r in packages]]
        for command, covered in zip(commands, ids):
            if run_apt(consent, command, covered) != 0:
                io.say(cat.t("setup.install_failed"))
                return EXIT_PROBLEM
        again = run_preflight(system)
        if again.missing:
            io.say(cat.count("setup.still_missing", len(again.missing)))
            return EXIT_PROBLEM
        io.say(cat.t("setup.installed"))
    io.say(cat.t("setup.ready"))
    io.say(cat.t("setup.window_not_built"))
    return EXIT_OK


def refuse_option(option: str, cat: Catalog, io: IO) -> int:
    io.say(cat.t("setup.bad_option", option=option))
    return EXIT_NOTHING_DONE
