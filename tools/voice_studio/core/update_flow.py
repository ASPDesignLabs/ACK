# SPDX-License-Identifier: GPL-3.0-or-later
"""The terminal front for updating the tool (plan task VS-6.2, decisions D11, P4 and P21): `python3 -m voice_studio.update check | get RELEASE`.

The decisions are in core/update.py. Both commands contact the internet, so each one says first, in words and with the exact commands, what it will ask github.com and what that request carries,
and asks (a typed yes, or `--yes`; nobody to ask means nothing is contacted). The yes is for that run only: nothing is saved and nothing is ever checked in the background (decision P4).
`get` puts the release in a new folder beside this copy and never touches this copy; it then says what is different and the commands for trying the new copy and, when the person is
satisfied, for using it under the usual name. Those commands are printed for the person to type: this program cannot replace the folder it is running from.
Exit codes as the other fronts: 0 done, 1 something failed after it began, 2 nothing was done (declined, nobody to ask, refused, an option or a name that could not be told).
"""
from __future__ import annotations

import os
import shlex
from typing import Callable, Optional, Sequence

from . import projectbackup as pb, update as up
from .update import UpdateError
from .cliargs import ArgError, parse_args
from .consent import make_consent
from .describe import error_text
from .projects_flow import EXIT_NOTHING_DONE, EXIT_OK, EXIT_PROBLEM, say_bad_arg
from .registry import ReleaseSource
from .rounds_flow import YES, _confirmed
from .setup_flow import IO
from .system import System
from .text import Catalog, size_text
from .uninstall_flow import code_folder

UPDATE_COMMAND = "python3 -m voice_studio.update"
COMMANDS = ("check", "get", "help")
OPTIONS = {"check": frozenset(YES), "get": frozenset(YES) | frozenset({"--to"})}          # the checklist is held to these
USAGE = ("update.usage.check", "update.usage.get", "update.usage.options")
MAX_ROWS = 10
MAX_NAMES = 10


def _say_error(cat: Catalog, io: IO, error: UpdateError) -> None:
    parts = error_text(cat, "update", error.code)
    for line in (parts.what, parts.changed, parts.next):
        io.say(line)
    if error.detail:
        io.say("  " + cat.t("cli.technical", detail=error.detail))


def _say_here(cat: Catalog, io: IO, here: str, version: str) -> None:
    """Where this copy is, and that it cannot be compared with a release when it is not a plain git copy."""
    io.say(cat.t("update.here", version=version, folder=here))
    if up.head_commit(here) is None:
        io.say(cat.t("update.here_no_git"))


def _say_contact(cat: Catalog, io: IO, source: ReleaseSource) -> None:
    io.say(cat.t(source.why_key))
    io.say(cat.t("update.contact.sent"))


# ---------------------------------------------------------------- check

def _check(args: Sequence[str], system: System, here: str, version: str, source: ReleaseSource, networked: Callable, cat: Catalog, io: IO) -> int:
    try:
        parsed = parse_args(args, flags=YES, values={}, max_words=0)
    except ArgError as error:
        return say_bad_arg(error, cat, io)
    io.say(cat.t("update.title"))
    _say_here(cat, io, here, version)
    if system.which("git") is None:
        _say_error(cat, io, UpdateError("no_git"))
        return EXIT_NOTHING_DONE
    _say_contact(cat, io, source)
    io.say(cat.t("update.contact.check", host=source.host, command="git ls-remote --tags " + source.url))
    declined = _confirmed(parsed, cat.t("update.question.check"), cat, io)
    if declined is not None:
        return declined
    try:
        releases = up.sort_releases(up.list_releases(networked, make_consent([], extra_ids=[up.LIST_ID]), source.url))
    except UpdateError as error:
        _say_error(cat, io, error)
        return EXIT_PROBLEM
    if not releases:
        io.say(cat.t("update.releases.none"))
        return EXIT_OK
    commit = up.head_commit(here)
    current = up.release_at(releases, commit)
    if current is not None:
        io.say(cat.t("update.here_release", name=current.name))
    elif commit is not None:
        io.say(cat.t("update.here_unknown", commit=commit[:10]))
    newer = up.newer_than(releases, current)
    io.say(cat.count("update.releases.head", len(releases)))
    for release in releases[:MAX_ROWS]:
        if current is not None and release.name == current.name:
            note = cat.t("update.note.this")
        elif release in newer:
            note = cat.t("update.note.newer")
        else:
            note = ""
        io.say("  " + (cat.t("update.releases.row", name=release.name, note=note) if note else release.name))
    if len(releases) > MAX_ROWS:
        io.say("  " + cat.count("update.releases.more", len(releases) - MAX_ROWS))
    if current is None:
        io.say(cat.t("update.releases.cannot_compare"))
    elif newer:
        io.say(cat.count("update.releases.newer", len(newer)))
    else:
        io.say(cat.t("update.releases.no_newer"))
    io.say(cat.t("update.releases.how", command="%s get %s" % (UPDATE_COMMAND, releases[0].name)))
    return EXIT_OK


# ---------------------------------------------------------------- get

def _say_changes(changes: up.Changes, cat: Catalog, io: IO) -> None:
    io.say(cat.t("update.diff.head"))
    if not changes.any:
        io.say("  " + cat.t("update.diff.same"))
        return
    for part in up.CATEGORIES:
        changed, added, removed = changes.changed[part], changes.added[part], changes.removed[part]
        if not (changed or added or removed):
            continue
        io.say("  " + cat.t("update.diff.row", part=cat.t("update.part." + part), changed=len(changed), added=len(added), removed=len(removed)))
        if part in ("programs", "downloads"):
            for path in (changed + added + removed)[:MAX_NAMES]:
                io.say("    " + path)
    if changes.changed["programs"] or changes.added["programs"] or changes.removed["programs"]:
        io.say(cat.t("update.diff.programs"))
    if changes.changed["downloads"] or changes.added["downloads"] or changes.removed["downloads"]:
        io.say(cat.t("update.diff.downloads"))


def _get(args: Sequence[str], system: System, here: str, version: str, source: ReleaseSource, networked: Callable, cat: Catalog, io: IO) -> int:
    try:
        parsed = parse_args(args, flags=YES, values={"--to": "to"}, max_words=1)
    except ArgError as error:
        return say_bad_arg(error, cat, io)
    io.say(cat.t("update.title"))
    if not parsed.words:
        io.say(cat.t("update.which", command="%s get v1.0" % UPDATE_COMMAND))
        return EXIT_NOTHING_DONE
    name = parsed.words[0]
    if not up.RELEASE_NAME.match(name):
        _say_error(cat, io, UpdateError("bad_name", name[:64]))
        return EXIT_NOTHING_DONE
    given = parsed.values.get("to")
    dest = os.path.expanduser(given) if given is not None else up.folder_name(here, name)
    if not os.path.isabs(dest):
        io.say(cat.t("update.to_not_absolute"))
        return EXIT_NOTHING_DONE
    dest = os.path.normpath(dest)
    _say_here(cat, io, here, version)
    if system.which("git") is None:
        _say_error(cat, io, UpdateError("no_git"))
        return EXIT_NOTHING_DONE
    usage = system.disk_free(pb.nearest_existing(dest))
    free = usage[1] if usage else None
    try:
        up.check_destination(dest, free)
    except UpdateError as error:
        _say_error(cat, io, error)
        return EXIT_NOTHING_DONE
    _say_contact(cat, io, source)
    io.say(cat.t("update.contact.get", name=name, host=source.host, folder=dest))
    io.say("  " + cat.t("update.contact.first", command="git ls-remote --tags " + source.url))
    io.say("  " + cat.t("update.contact.second", command="git clone --depth 1 --branch %s %s %s" % (name, source.url, dest)))
    io.say(cat.t("update.contact.untouched"))
    io.say(cat.t("update.contact.room", need=size_text(up.ROOM_BYTES)) if free is None else cat.t("update.contact.room_known", need=size_text(up.ROOM_BYTES), free=size_text(free)))
    declined = _confirmed(parsed, cat.t("update.question.get", name=name), cat, io)
    if declined is not None:
        return declined
    consent = make_consent([], extra_ids=[up.LIST_ID, up.GET_ID])
    try:
        releases = up.list_releases(networked, consent, source.url)
        release = next((r for r in releases if r.name == name), None)
        if release is None:
            raise UpdateError("unknown_release", name)
        if release.commit == up.head_commit(here):
            io.say(cat.t("update.already", name=name))
            return EXIT_NOTHING_DONE
        fetched = up.get_release(networked, consent, source.url, release, dest)
    except UpdateError as error:
        _say_error(cat, io, error)
        return EXIT_PROBLEM
    io.say(cat.t("update.done" if fetched.version else "update.done_no_version", name=name, commit=release.commit[:10], folder=dest, version=fetched.version or ""))
    io.say(cat.t("update.checked"))
    _say_changes(up.compare(here, dest), cat, io)
    io.say(cat.t("update.next.try", command="PYTHONPATH=%s python3 -m voice_studio" % shlex.quote(dest + "/tools")))
    io.say("  " + cat.t("update.next.try_why"))
    io.say(cat.t("update.next.switch", command="mv %s %s && mv %s %s" % (shlex.quote(here), shlex.quote(here + ".old"), shlex.quote(dest), shlex.quote(here))))
    io.say("  " + cat.t("update.next.kept"))
    return EXIT_OK


# ---------------------------------------------------------------- the front

def _help(cat: Catalog, io: IO) -> int:
    io.say(cat.t("update.title"))
    io.say(cat.t("update.usage.head"))
    for key in USAGE:
        io.say("  " + cat.t(key))
    return EXIT_OK


def run_update(argv: Sequence[str], cat: Catalog, io: IO, *, system: System, source: ReleaseSource, networked: Callable, tools_dir: str, version: str) -> int:
    """`python3 -m voice_studio.update COMMAND ...`. `networked` is the download module's `run_networked`; a test gives its own. Ctrl+C stops cleanly: a folder that was being made is removed again."""
    command = argv[0] if argv else "help"
    rest = list(argv[1:])
    here = code_folder(tools_dir)
    try:
        if command in ("help", "--help", "-h"):
            return _help(cat, io)
        if command == "check":
            return _check(rest, system, here, version, source, networked, cat, io)
        if command == "get":
            return _get(rest, system, here, version, source, networked, cat, io)
        io.say(cat.t("cli.bad_command", command=command[:60]))
        return EXIT_NOTHING_DONE
    except KeyboardInterrupt:
        io.say(cat.t("update.interrupted"))
        return EXIT_PROBLEM
