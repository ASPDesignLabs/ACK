# SPDX-License-Identifier: GPL-3.0-or-later
"""The terminal front for backing up a project (plan task VS-6.1, decision P17): `python3 -m voice_studio.backup now | list | verify | restore`.

The decisions are in core/projectbackup.py and the list of what is precious in core/areas.py; this shows what will happen, asks first (a typed yes, or `--yes`; a terminal with nobody at it is
never asked), and says what happened in plain words. `now` and `restore` ask; `list` and `verify` only look. A backup is only ever added to: no earlier backup is replaced or removed here.
`nudge_lines` is the short reminder that a project has not been backed up (or has changed since), which `rounds start` and bringing recordings in print before they go on; it never writes.

Every sentence is in the text catalog. Exit codes: 0 done, 1 something failed, 2 nothing was done (declined, nobody to ask, an option or a file that could not be told).
"""
from __future__ import annotations

import os
from datetime import datetime
from typing import Dict, List, Optional, Sequence, Tuple

from . import projectbackup as pb, rounds as rd
from .backupnudge import BACKUP_COMMAND, nudge_lines as _nudge, when_text
from .cliargs import ArgError, parse_args
from .describe import error_text
from .diskbudget import Level
from .paths import DataHome
from .projects_flow import EXIT_NOTHING_DONE, EXIT_OK, EXIT_PROBLEM, say_bad_arg
from .rounds_flow import PROJECT, YES, Open, _ask_yes, _confirmed, _free, _look, _open, _say_parts
from .setup_flow import IO
from .system import System
from .text import Catalog, size_text

TO = {"--to": "to"}
NOW_FLAGS = {**YES, "--without-saved-points": "without_saved_points"}
OPTIONS = {"now": frozenset(NOW_FLAGS) | frozenset(PROJECT) | frozenset(TO), "list": frozenset(PROJECT) | frozenset(TO), "verify": frozenset(), "restore": frozenset(YES)}      # the checklist is held to these
COMMANDS = ("now", "list", "verify", "restore", "help")
USAGE = ("backup.usage.now", "backup.usage.list", "backup.usage.verify", "backup.usage.restore", "backup.usage.options")
MAX_NAMES_SHOWN = 10


def _say_error(error: pb.BackupError, cat: Catalog, io: IO) -> None:
    _say_parts(cat, io, "backup", error.code, error.detail)
    for line in error.problems:
        io.say("    - " + cat.t("backup.verify_problem", problem=line))


def _folder_for(parsed, home: DataHome, project_id: str) -> Tuple[Optional[str], str]:
    """(the folder, how it was chosen: "to", "remembered" or "default"), or (None, "bad") for an option that cannot be a folder."""
    wanted = parsed.values.get("to")
    if wanted is not None:
        return os.path.expanduser(wanted), "to"
    last = pb.read_state(home).get(project_id, {}).get("folder")
    if isinstance(last, str) and os.path.isabs(last):
        return last, "remembered"
    return home.backups, "default"


def _free_at(system: System, folder: str) -> Optional[int]:
    usage = system.disk_free(pb.nearest_existing(folder)) if os.path.isabs(folder) else None
    return usage[1] if usage else None


def _current_record(ctx: Open, now: Optional[datetime], cat: Catalog, io: IO) -> rd.Record:
    """The record of rounds as it really is: a round that ended since is brought up to date first (and said), so the saved point it made is the one that is kept. Nothing is written when
    nothing has ended, so a project with no rounds yet gets no new folder from a backup."""
    stale = rd.load(ctx.paths) != rd.reconcile(ctx.paths, ctx.scratch, ctx.jobs_root, ctx.project.id, now=now, write=False)
    return _look(ctx, now, cat, io, write=stale)


def _say_standing(standing: pb.Standing, name: str, cat: Catalog, io: IO) -> None:
    if standing.state == pb.NEVER:
        io.say(cat.t("backup.standing.never", name=name))
    elif standing.state == pb.CHANGED:
        io.say(cat.t("backup.standing.changed", name=name, when=when_text(standing.last), folder=standing.folder))
    elif standing.last:
        io.say(cat.t("backup.standing.current", name=name, when=when_text(standing.last)))


def nudge_lines(home: DataHome, ctx: Open, cat: Catalog, record: Optional[rd.Record] = None) -> List[str]:
    """The reminder (core/backupnudge.py) for the project this command opened."""
    return _nudge(home, ctx.project, ctx.paths, cat, record)


# ---------------------------------------------------------------- now

def _say_plan(plan: pb.BackupPlan, how: str, ctx: Open, standing: pb.Standing, hint: Optional[str], cat: Catalog, io: IO) -> None:
    io.say(cat.t("backup.plan_head", name=ctx.project.name))
    _say_standing(standing, ctx.project.name, cat, io)
    io.say("  " + cat.t("backup.plan_holds"))
    for part in plan.parts:
        io.say("    " + cat.count("backup.plan_part", part.files, what=cat.t("backup.part." + part.part), size=size_text(part.bytes)))
    if plan.left_out:
        io.say("  " + cat.t("backup.plan_leaves"))
        for left in plan.left_out:
            io.say("    " + cat.t("backup.left_out_row", what=cat.t("backup.left_out." + left.id), size=size_text(left.bytes)))
    io.say("  " + cat.t("backup.plan_where", folder=plan.destination))
    io.say("  " + cat.t("backup.plan_read_back"))
    io.say("  " + cat.t("backup.plan_never_removes"))
    if plan.skipped:
        io.say(cat.count("backup.skipped", len(plan.skipped)))
        for item in plan.skipped[:MAX_NAMES_SHOWN]:
            io.say("    " + cat.t("cli.technical", detail=item.name + " (" + item.reason + ")"))
    if how == "default":
        io.say(cat.t("backup.default_folder"))
    if plan.same_drive:
        io.say(cat.t("backup.same_drive"))
        if hint:
            io.say(cat.t("backup.windows_hint", folder=hint))
    if plan.sync_warning:
        io.say(cat.t("recordings.note_line", text=plan.sync_warning))
    io.say(cat.t("voicefile.make.checks_head"))
    if plan.free_bytes is None:
        io.say("  " + cat.t("voicefile.make.disk_unknown"))
    elif plan.room is Level.TIGHT:
        io.say("  " + cat.t("voicefile.make.disk_tight", free=size_text(plan.free_bytes), need=size_text(plan.need_bytes)))
    else:
        io.say("  " + cat.t("voicefile.make.disk_ok", need=size_text(plan.need_bytes), free=size_text(plan.free_bytes)))


def _now(args: Sequence[str], home: DataHome, now: Optional[datetime], system: System, cat: Catalog, io: IO) -> int:
    try:
        parsed = parse_args(args, flags=NOW_FLAGS, values={**PROJECT, **TO}, max_words=0)
    except ArgError as error:
        return say_bad_arg(error, cat, io)
    io.say(cat.t("backup.title"))
    ctx, code = _open(parsed, home, cat, io)
    if ctx is None:
        return code
    record = _current_record(ctx, now, cat, io)
    folder, how = _folder_for(parsed, home, ctx.project.id)
    try:
        plan = pb.plan_backup(ctx.paths, home, ctx.project.id, folder or "", _free_at(system, folder or ""), record, saved_points="without_saved_points" not in parsed.flags)
    except pb.BackupError as error:
        _say_error(error, cat, io)
        return EXIT_PROBLEM
    _say_plan(plan, how, ctx, pb.standing(home, ctx.paths, ctx.project.id, record), pb.windows_side_folder(system) if how != "to" else None, cat, io)
    if plan.room is Level.NOT_ENOUGH:
        _say_error(pb.BackupError("no_room", "%d free, %d needed" % (plan.free_bytes or 0, plan.need_bytes)), cat, io)
        return EXIT_PROBLEM
    declined = _confirmed(parsed, cat.t("backup.question"), cat, io)
    if declined is not None:
        return declined
    shown: Dict[str, int] = {}

    def progress(part: str, done: int, total: int) -> None:
        if part not in shown:
            shown[part] = 1
            io.say(cat.t("backup.reading_back") if part == "read_back" else cat.t("backup.writing", what=cat.t("backup.part." + part)))
    try:
        made = pb.create(plan, ctx.paths, now, progress, record)
    except pb.BackupError as error:
        _say_error(error, cat, io)
        return EXIT_PROBLEM
    except KeyboardInterrupt:
        io.say(cat.t("backup.stopped"))
        return EXIT_PROBLEM
    pb.record_backup(home, made, ctx.project.id, plan.destination)
    io.say(cat.t("backup.done", path=made.path))
    io.say(cat.count("backup.done_files", made.files) + " " + cat.t("backup.done_detail", size=size_text(made.archive_bytes)))
    if made.skipped:
        io.say(cat.count("backup.skipped", len(made.skipped)))
    io.say(cat.t("backup.done_kept"))
    io.say(cat.t("backup.done_verify", command="%s verify %s" % (BACKUP_COMMAND, made.path)))
    io.say(cat.t("backup.done_restore", command="%s restore %s" % (BACKUP_COMMAND, made.path)))
    return EXIT_OK


# ---------------------------------------------------------------- list and verify

def _list(args: Sequence[str], home: DataHome, now: Optional[datetime], cat: Catalog, io: IO) -> int:
    try:
        parsed = parse_args(args, flags={}, values={**PROJECT, **TO}, max_words=0)
    except ArgError as error:
        return say_bad_arg(error, cat, io)
    io.say(cat.t("backup.title"))
    ctx, code = _open(parsed, home, cat, io)
    if ctx is None:
        return code
    folder, _how = _folder_for(parsed, home, ctx.project.id)
    found = pb.list_backups(folder or "", ctx.project.id)
    if found:
        io.say(cat.t("backup.list_head", name=ctx.project.name, folder=folder))
        for item in found:
            io.say("  " + cat.t("backup.list_row", when=when_text(str(item["created"])), size=size_text(int(item["size"])), name=item["name"]))
    else:
        io.say(cat.t("backup.list_none", name=ctx.project.name, folder=folder))
        io.say(cat.t("backup.list_next", command="%s now --project %s" % (BACKUP_COMMAND, ctx.project.id)))
    try:
        _say_standing(pb.standing(home, ctx.paths, ctx.project.id, rd.reconcile(ctx.paths, ctx.scratch, ctx.jobs_root, ctx.project.id, now=now, write=False)), ctx.project.name, cat, io)
    except rd.RoundsError as error:
        _say_parts(cat, io, "rounds", error.code, error.detail)
        return EXIT_PROBLEM
    return EXIT_OK


def _verify(args: Sequence[str], cat: Catalog, io: IO) -> int:
    try:
        parsed = parse_args(args, flags={}, values={}, max_words=1)
    except ArgError as error:
        return say_bad_arg(error, cat, io)
    io.say(cat.t("backup.title"))
    if not parsed.words:
        io.say(cat.t("backup.usage.verify"))
        return EXIT_NOTHING_DONE
    path = os.path.expanduser(parsed.words[0])
    if pb._regular(path) is None:
        _say_error(pb.BackupError("no_such_backup", os.path.basename(path)), cat, io)
        return EXIT_PROBLEM
    problems, _manifest = pb.verify(path)
    name = os.path.basename(path)
    if not problems:
        io.say(cat.t("backup.verify_ok", name=name))
        return EXIT_OK
    io.say(cat.t("backup.verify_bad", name=name))
    for line in problems[:MAX_NAMES_SHOWN]:
        io.say("  - " + cat.t("backup.verify_problem", problem=line))
    return EXIT_PROBLEM


# ---------------------------------------------------------------- restore

def _restore(args: Sequence[str], home: DataHome, system: System, cat: Catalog, io: IO) -> int:
    try:
        parsed = parse_args(args, flags=YES, values={}, max_words=1)
    except ArgError as error:
        return say_bad_arg(error, cat, io)
    io.say(cat.t("backup.title"))
    if not parsed.words:
        io.say(cat.t("backup.usage.restore"))
        return EXIT_NOTHING_DONE
    archive = os.path.expanduser(parsed.words[0])
    try:
        usage = system.disk_free(pb.nearest_existing(home.projects))
        plan = pb.plan_restore(home, archive, usage[1] if usage else None)
    except pb.BackupError as error:
        _say_error(error, cat, io)
        return EXIT_PROBLEM
    io.say(cat.t("backup.restore_plan_head", when=when_text(plan.created)))
    io.say("  " + cat.t("backup.restore_new" if plan.new_project else "backup.restore_into", id=plan.project_id))
    if plan.add:
        io.say("  " + cat.count("backup.restore_add", len(plan.add), size=size_text(plan.bytes_to_add)))
    if plan.same:
        io.say("  " + cat.count("backup.restore_same", plan.same))
    if plan.conflicts:
        io.say("  " + cat.count("backup.restore_conflict", len(plan.conflicts)))
        for name in plan.conflicts[:MAX_NAMES_SHOWN]:
            io.say("    " + cat.t("backup.restore_conflict_row", name=name))
    if not plan.add:
        io.say(cat.t("backup.restore_nothing"))
        return EXIT_OK
    if plan.room is Level.NOT_ENOUGH:
        _say_error(pb.BackupError("no_room", "%d free, %d needed" % (plan.free_bytes or 0, plan.bytes_to_add)), cat, io)
        return EXIT_PROBLEM
    declined = _confirmed(parsed, cat.t("backup.restore_question"), cat, io)
    if declined is not None:
        return declined
    try:
        result = pb.restore(home, plan)
    except pb.BackupError as error:
        _say_error(error, cat, io)
        return EXIT_PROBLEM
    except KeyboardInterrupt:
        io.say(cat.t("backup.stopped"))
        return EXIT_PROBLEM
    io.say(cat.count("backup.restore_done", result.added, size=size_text(result.bytes)))
    if result.conflicts:
        io.say(cat.count("backup.restore_left", len(result.conflicts)))
    if result.failed:
        io.say(cat.t("backup.restore_failed_head"))
        for name, reason in result.failed[:MAX_NAMES_SHOWN]:
            io.say("  " + cat.t("backup.restore_failed_row", name=name, reason=reason))
    io.say(cat.t("backup.restore_next", command="python3 -m voice_studio.rounds list --project %s" % plan.project_id))
    return EXIT_PROBLEM if result.failed else EXIT_OK


# ---------------------------------------------------------------- the command

def _help(cat: Catalog, io: IO) -> int:
    io.say(cat.t("backup.title"))
    io.say(cat.t("backup.usage.head"))
    for key in USAGE:
        io.say("  " + cat.t(key))
    return EXIT_OK


def run_backup(argv: Sequence[str], home: DataHome, cat: Catalog, io: IO, *, now: Optional[datetime] = None, system: Optional[System] = None) -> int:
    """`python3 -m voice_studio.backup COMMAND ...`. Ctrl+C stops cleanly at any point; an unfinished backup is removed."""
    from .system import RealSystem
    command = argv[0] if argv else "help"
    rest = list(argv[1:])
    system = system or RealSystem()
    try:
        if command in ("help", "--help", "-h"):
            return _help(cat, io)
        if command == "now":
            return _now(rest, home, now, system, cat, io)
        if command == "list":
            return _list(rest, home, now, cat, io)
        if command == "verify":
            return _verify(rest, cat, io)
        if command == "restore":
            return _restore(rest, home, system, cat, io)
        io.say(cat.t("cli.bad_command", command=command[:60]))
        return EXIT_NOTHING_DONE
    except KeyboardInterrupt:
        io.say(cat.t("cli.nothing_done"))
        return EXIT_PROBLEM
    except rd.RoundsError as error:
        _say_parts(cat, io, "rounds", error.code, error.detail)
        return EXIT_PROBLEM
