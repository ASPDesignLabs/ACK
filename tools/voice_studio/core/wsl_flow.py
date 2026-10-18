# SPDX-License-Identifier: GPL-3.0-or-later
"""The terminal front for the Windows side of Ubuntu under WSL (plan task VS-3.6, decision D17, choices P26): `python3 -m voice_studio.wsl check | phone | idle`.

The decisions are in core/wsl.py. `check` only looks. `phone` and `idle` each show the one change they want to make to the Windows file `.wslconfig` (the lines that differ), ask once (a typed
yes, or `--yes`; nobody to ask means nothing is done) and then write it, keeping the file as it was under a new name. The firewall command and the restart are only ever printed: this program
never runs them, never restarts WSL, and never changes anything on Windows but that one file.
Exit codes as the other fronts: 0 done (or looked), 1 the file could not be written, 2 nothing was done (declined, nobody to ask, not Ubuntu in Windows, a file or a name that could not be used).
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional, Sequence

from . import jobs, preflight, wsl
from .cliargs import ArgError, Parsed, parse_args
from .paths import DataHome
from .projects_flow import EXIT_NOTHING_DONE, EXIT_OK, EXIT_PROBLEM, say_bad_arg
from .rounds_flow import YES, _confirmed, _say_parts
from .setup_flow import IO
from .system import RealSystem, System
from .text import Catalog
from .voicesend_flow import _port

WSL_COMMAND = "python3 -m voice_studio.wsl"
SEND_COMMAND = "python3 -m voice_studio.voicefile send"
RESTART_COMMAND = "wsl.exe --shutdown"
USER = {"--windows-user": "user"}
PORT = {"--port": "port"}
COMMANDS = ("check", "phone", "idle", "help")
OPTIONS = {"check": frozenset(USER), "phone": frozenset(YES) | frozenset(USER) | frozenset(PORT), "idle": frozenset(YES) | frozenset(USER)}          # the checklist is held to these
USAGE = ("wsl.usage.check", "wsl.usage.phone", "wsl.usage.idle", "wsl.usage.options")


def _task_running(home: DataHome) -> bool:
    return any(job.status in jobs.ACTIVE for job in jobs.list_jobs(home.jobs).jobs)


def _say_error(error: wsl.WslError, cat: Catalog, io: IO) -> None:
    _say_parts(cat, io, "wsl", error.code, error.detail)


def _parse(args: Sequence[str], flags, values, cat: Catalog, io: IO) -> Optional[Parsed]:
    try:
        return parse_args(args, flags=flags, values=values, max_words=0)
    except ArgError as error:
        say_bad_arg(error, cat, io)
        return None


# ---------------------------------------------------------------- check

def _say_windows(facts: wsl.Facts, cat: Catalog, io: IO) -> None:
    if facts.interop == wsl.INTEROP_WORKS:
        io.say("  " + cat.t("wsl.check.windows_works"))
        if facts.build is not None:
            io.say("  " + cat.t("wsl.check.windows_build", build=facts.build))
    elif facts.interop == wsl.INTEROP_FAILED:
        io.say("  " + cat.t("wsl.check.windows_failed"))
        io.say("  " + cat.t("wsl.check.windows_failed_next", command=RESTART_COMMAND))
    else:
        io.say("  " + cat.t("wsl.check.windows_missing"))


def _say_file(facts: wsl.Facts, cat: Catalog, io: IO) -> None:
    if facts.home is None:
        _say_error(facts.home_error, cat, io)                  # a home is missing only for a reason
        return
    io.say("  " + cat.t("wsl.check.home", path=facts.home.path))
    if facts.config_bad:
        io.say("  " + cat.t("wsl.check.file_bad", path=facts.config_path))
    elif facts.config_text is None:
        io.say("  " + cat.t("wsl.check.file_none", name=wsl.CONFIG_NAME))
    else:
        io.say("  " + cat.t("wsl.check.file_there", path=facts.config_path))


def _mirrored_now(facts: wsl.Facts) -> bool:
    """Whether Ubuntu is on the Windows network now: what the running Ubuntu says where it can say, otherwise what the file asks for."""
    if facts.runtime_mode is not None:
        return facts.runtime_mode == wsl.MIRRORED
    return facts.file_mode == wsl.MIRRORED


def _say_network(facts: wsl.Facts, cat: Catalog, io: IO) -> None:
    if facts.file_mode is not None:
        io.say("  " + cat.t("wsl.check.mode_file", mode=facts.file_mode[:40]))
    elif facts.home is not None and not facts.config_bad:
        io.say("  " + cat.t("wsl.check.mode_unset"))
    if facts.runtime_mode is not None:
        io.say("  " + cat.t("wsl.check.mode_running", mode=facts.runtime_mode))
        if facts.file_mode is not None and facts.file_mode != facts.runtime_mode:
            io.say("  " + cat.t("wsl.check.mode_restart"))
    if wsl.mirrored_possible(facts.build) is False:
        io.say("  " + cat.t("wsl.check.phone_old", need=wsl.MIRRORED_MIN_BUILD))
    elif _mirrored_now(facts):
        io.say("  " + cat.t("wsl.check.phone_yes"))
    else:
        io.say("  " + cat.t("wsl.check.phone_no", command=WSL_COMMAND + " phone"))


def _say_idle(facts: wsl.Facts, cat: Catalog, io: IO) -> None:
    if facts.file_idle is None:
        io.say("  " + cat.t("wsl.check.idle_default", command=WSL_COMMAND + " idle"))
    elif facts.file_idle == wsl.NEVER:
        io.say("  " + cat.t("wsl.check.idle_never"))
    else:
        io.say("  " + cat.t("wsl.check.idle_other", value=facts.file_idle[:40], command=WSL_COMMAND + " idle"))


def _check(args: Sequence[str], system: System, cat: Catalog, io: IO) -> int:
    parsed = _parse(args, {}, USER, cat, io)
    if parsed is None:
        return EXIT_NOTHING_DONE
    io.say(cat.t("wsl.title"))
    facts = wsl.look(system, named=parsed.values.get("user"))
    if facts.platform is preflight.Platform.NATIVE:
        io.say(cat.t("wsl.not_wsl"))
        return EXIT_OK
    io.say(cat.t("wsl.check.head"))
    _say_windows(facts, cat, io)
    _say_file(facts, cat, io)
    _say_network(facts, cat, io)
    _say_idle(facts, cat, io)
    return EXIT_OK


# ---------------------------------------------------------------- the change to the file

def _change(parsed: Parsed, facts: wsl.Facts, section: str, key: str, value: str, keep_key: str, cat: Catalog, io: IO, now: datetime) -> int:
    """Show the change to `.wslconfig` that sets the value and, after a yes, make it. EXIT_OK when the file now says so (it already did, or it was changed)."""
    try:
        plan = wsl.plan_edit(facts, section, key, value)
    except wsl.WslError as error:
        _say_error(error, cat, io)
        return EXIT_NOTHING_DONE
    if plan is None:
        io.say(cat.t(keep_key))
        return EXIT_OK
    io.say(cat.t("wsl.change.head", path=plan.path))
    for line in plan.listing:
        io.say("    " + line)
    if plan.creates:
        io.say(cat.t("wsl.change.creates", name=wsl.CONFIG_NAME))
    declined = _confirmed(parsed, cat.t("wsl.change.question"), cat, io)
    if declined is not None:
        return declined
    try:
        kept = wsl.apply_edit(plan, now)
    except wsl.WslError as error:
        _say_error(error, cat, io)
        return EXIT_PROBLEM
    io.say(cat.t("wsl.change.done_new", path=plan.path) if kept is None else cat.t("wsl.change.done", backup=kept))
    return EXIT_OK


def _say_restart(home: DataHome, step: str, cat: Catalog, io: IO) -> None:
    io.say(cat.t(step, command=RESTART_COMMAND))
    if _task_running(home):
        io.say(cat.t("wsl.change.task"))


# ---------------------------------------------------------------- phone

def _phone(args: Sequence[str], home: DataHome, system: System, now: datetime, cat: Catalog, io: IO) -> int:
    parsed = _parse(args, YES, dict(USER, **PORT), cat, io)
    if parsed is None:
        return EXIT_NOTHING_DONE
    port = _port(parsed.values.get("port"))
    if port is None:
        io.say(cat.t("voicefile.send.bad_port", low=1024, high=65535))
        return EXIT_NOTHING_DONE
    io.say(cat.t("wsl.title"))
    facts = wsl.look(system, named=parsed.values.get("user"))
    if facts.platform is preflight.Platform.NATIVE:
        io.say(cat.t("wsl.not_wsl"))
        return EXIT_NOTHING_DONE
    if wsl.mirrored_possible(facts.build) is False:
        io.say(cat.t("wsl.check.phone_old", need=wsl.MIRRORED_MIN_BUILD))
        return EXIT_NOTHING_DONE
    io.say(cat.t("wsl.phone.head"))
    io.say(cat.t("wsl.phone.step1"))
    code = _change(parsed, facts, wsl.SECTION_NETWORK, wsl.KEY_NETWORK, wsl.MIRRORED, "wsl.phone.step1_ok", cat, io, now)
    if code != EXIT_OK:
        return code
    add, undo = wsl.firewall_commands(port)
    io.say(cat.t("wsl.phone.step2", port=port))
    io.say("    " + add)
    io.say(cat.t("wsl.phone.step2_undo"))
    io.say("    " + undo)
    io.say(cat.t("wsl.phone.step2_never"))
    _say_restart(home, "wsl.phone.step3", cat, io)
    io.say(cat.t("wsl.phone.step3_after", command=SEND_COMMAND))
    io.say(cat.t("wsl.phone.unconfirmed"))
    return EXIT_OK


# ---------------------------------------------------------------- idle

def _idle(args: Sequence[str], home: DataHome, system: System, now: datetime, cat: Catalog, io: IO) -> int:
    parsed = _parse(args, YES, USER, cat, io)
    if parsed is None:
        return EXIT_NOTHING_DONE
    io.say(cat.t("wsl.title"))
    facts = wsl.look(system, named=parsed.values.get("user"))
    if facts.platform is preflight.Platform.NATIVE:
        io.say(cat.t("wsl.not_wsl"))
        return EXIT_NOTHING_DONE
    io.say(cat.t("wsl.idle.head"))
    io.say(cat.t("wsl.idle.step1"))
    code = _change(parsed, facts, wsl.SECTION_IDLE, wsl.KEY_IDLE, wsl.NEVER, "wsl.idle.step1_ok", cat, io, now)
    if code != EXIT_OK:
        return code
    _say_restart(home, "wsl.idle.step2", cat, io)
    io.say(cat.t("wsl.idle.after"))
    io.say(cat.t("wsl.idle.old"))
    return EXIT_OK


def _help(cat: Catalog, io: IO) -> int:
    io.say(cat.t("wsl.title"))
    io.say(cat.t("wsl.usage.head"))
    for key in USAGE:
        io.say("  " + cat.t(key))
    return EXIT_OK


def run_wsl(argv: Sequence[str], home: DataHome, cat: Catalog, io: IO, *, system: Optional[System] = None, now: Optional[datetime] = None) -> int:
    """`python3 -m voice_studio.wsl COMMAND ...`. Ctrl+C stops cleanly: a file that was changed stays changed, and the copy of the old one stays."""
    system = system or RealSystem()
    when = now or datetime.now()
    command = argv[0] if argv else "help"
    rest = list(argv[1:])
    try:
        if command in ("help", "--help", "-h"):
            return _help(cat, io)
        if command == "check":
            return _check(rest, system, cat, io)
        if command == "phone":
            return _phone(rest, home, system, when, cat, io)
        if command == "idle":
            return _idle(rest, home, system, when, cat, io)
        io.say(cat.t("cli.bad_command", command=command[:60]))
        return EXIT_NOTHING_DONE
    except KeyboardInterrupt:
        io.say(cat.t("wsl.interrupted"))
        return EXIT_PROBLEM
