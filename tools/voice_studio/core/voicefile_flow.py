# SPDX-License-Identifier: GPL-3.0-or-later
"""The terminal front for making the voice file (until the window exists): `make` it from the chosen round in one go, `list` the ones made before.

It is the front of core/voicefile.py and decides nothing that module does not. `make` shows what it will do, checks the room, and asks first (a typed yes, or `--yes`); a terminal
with nobody at it is never asked. It writes only into one new folder under the project's `exports`; when a step fails it says which, where the folder is, and that nothing was deleted.
`list` changes nothing.

Every sentence comes from the text catalog. Exit codes: 0 done, 1 something failed or could not be done, 2 nothing was done (declined, nobody to ask, an option that could not be told).
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional, Sequence

from . import commands, envbuild, envfind, jobs, listen_flow, modelcard, rounds as rd, voicefile as vf, voicesend_flow, voicezip
from .. import __version__
from .cliargs import ArgError, parse_args
from .diskbudget import Level
from .paths import DataHome
from .projects_flow import EXIT_NOTHING_DONE, EXIT_OK, EXIT_PROBLEM, say_bad_arg
from .registry import Registry
from .rounds_flow import BUILDENV_COMMAND, PROJECT, YES, TrainingEnv, _confirmed, _free, _look, _open, _say_parts
from .setup_flow import IO
from .system import RealSystem, System
from .text import Catalog, size_text

VOICEFILE_COMMAND = "python3 -m voice_studio.voicefile"
OPTIONS = {"make": frozenset(YES) | frozenset(PROJECT), "list": frozenset(PROJECT), "listen": listen_flow.OPTIONS, "send": voicesend_flow.OPTIONS}                 # the checklist is held to these
STAGE_TEXT = {"export": "voicefile.make.stage_export", "settings": "voicefile.make.stage_settings", "patch": "voicefile.make.stage_patch", "zip": "voicefile.make.stage_zip",
              "check": "voicefile.make.stage_check", "card": "voicefile.make.stage_card"}


def _help(cat: Catalog, io: IO) -> int:
    io.say(cat.t("voicefile.title"))
    io.say(cat.t("voicefile.usage.head"))
    for key in ("voicefile.usage.make", "voicefile.usage.list", "voicefile.usage.listen", "voicefile.usage.send", "voicefile.usage.options"):
        io.say("  " + cat.t(key))
    return EXIT_OK


def _list(args: Sequence[str], home: DataHome, cat: Catalog, io: IO) -> int:
    try:
        parsed = parse_args(args, flags={}, values=PROJECT, max_words=0)
    except ArgError as error:
        return say_bad_arg(error, cat, io)
    io.say(cat.t("voicefile.title"))
    ctx, code = _open(parsed, home, cat, io)
    if ctx is None:
        return code
    made = vf.existing_voice_files(ctx.paths)
    if not made:
        io.say(cat.t("voicefile.list.none"))
        io.say(cat.t("voicefile.list.next", command="%s make --project %s" % (VOICEFILE_COMMAND, ctx.project.id)))
        return EXIT_OK
    io.say(cat.t("voicefile.list.heading", name=ctx.project.name))
    for name, zip_path, size in made:
        io.say("  " + cat.t("voicefile.list.row", name=name, size=size_text(size)))
        io.say("    " + zip_path)
    return EXIT_OK


def _say_plan(plan: vf.VoicePlan, cat: Catalog, io: IO) -> None:
    io.say(cat.t("voicefile.make.plan_head"))
    for line in (cat.t("voicefile.make.plan_round", round=plan.round, size=size_text(plan.checkpoint_bytes), minutes=plan.trained_minutes),
                 cat.t("voicefile.make.plan_settings"), cat.t("voicefile.make.plan_steps"), cat.t("voicefile.make.plan_zip"), cat.t("voicefile.make.plan_card"), cat.t("voicefile.make.plan_folder", folder=plan.folder),
                 cat.t("voicefile.make.plan_time")):
        io.say("  " + line)
    io.say(cat.t("voicefile.make.checks_head"))
    if plan.free_bytes is None:
        io.say("  " + cat.t("voicefile.make.disk_unknown"))
    elif plan.room is Level.TIGHT:
        io.say("  " + cat.t("voicefile.make.disk_tight", free=size_text(plan.free_bytes), need=size_text(plan.need_bytes)))
    else:
        io.say("  " + cat.t("voicefile.make.disk_ok", need=size_text(plan.need_bytes), free=size_text(plan.free_bytes)))


def _where_it_stands(folder: str, cat: Catalog, io: IO) -> None:
    io.say("  " + cat.t("voicefile.make.left_where", folder=folder))


def _make(args: Sequence[str], home: DataHome, now: Optional[datetime], training: TrainingEnv, system: System, tools_dir: str, registry: Optional[Registry], cat: Catalog, io: IO) -> int:
    try:
        parsed = parse_args(args, flags=YES, values=PROJECT, max_words=0)
    except ArgError as error:
        return say_bad_arg(error, cat, io)
    io.say(cat.t("voicefile.title"))
    ctx, code = _open(parsed, home, cat, io)
    if ctx is None:
        return code
    record = _look(ctx, now, cat, io, write=True)
    environment, state = training()
    if environment is None:
        io.say(cat.t("voicefile.make.no_environment", state=state, command=BUILDENV_COMMAND))
        return EXIT_PROBLEM
    free = _free(system, ctx)["project"]
    try:
        plan = vf.plan_voice(ctx.paths, record, ctx.project.id, jobs.utc_stamp(now), free)
    except vf.VoiceFileError as error:
        _say_parts(cat, io, "voicefile", error.code, error.detail)
        return EXIT_PROBLEM
    _say_plan(plan, cat, io)
    declined = _confirmed(parsed, cat.t("voicefile.make.question", round=plan.round), cat, io)
    if declined is not None:
        return declined

    def stage(name: str) -> None:
        io.say(cat.t(STAGE_TEXT[name]))

    def card(made: vf.Made) -> modelcard.Card:
        """The card is read from what the project stored, at the moment the voice file is finished."""
        programs, _why = envbuild.read_record(environment.env_dir)
        inp = modelcard.gather(record, plan.round, ctx.project, registry, zip_bytes=made.zip_bytes, model_sha256=made.model_sha256,
                               config_sha256=made.config_sha256, made_at=jobs.utc_stamp(now), tool_version=__version__, programs=programs)
        return modelcard.build_card(inp, cat)

    try:
        made = vf.make_voice(plan, environment, tools_dir, system, stage, card)
    except vf.VoiceFileError as error:
        _say_parts(cat, io, "voicefile", error.code, error.detail)
        if error.folder:
            _where_it_stands(error.folder, cat, io)
        return EXIT_PROBLEM
    except voicezip.VoiceZipError as error:
        _say_parts(cat, io, "voicezip", error.code, error.detail)
        for problem in error.problems:
            io.say("    - " + cat.t("voicezip.problem." + problem))
        _where_it_stands(plan.folder, cat, io)
        return EXIT_PROBLEM
    except commands.CommandError as error:
        _say_parts(cat, io, "commands", error.code, error.detail)
        _where_it_stands(plan.folder, cat, io)
        return EXIT_PROBLEM
    except KeyboardInterrupt:
        io.say(cat.t("voicefile.make.interrupted", folder=plan.folder))
        return EXIT_PROBLEM
    io.say(cat.t("voicefile.make.done", zip=made.zip_path))
    io.say(cat.t("voicefile.make.done_size", size=size_text(made.zip_bytes)))
    io.say(cat.t("voicefile.make.done_folder", folder=made.folder))
    io.say(cat.t("voicefile.make.done_card", card=made.card_path))
    io.say(cat.t("voicefile.make.done_next"))
    return EXIT_OK


def _no_studio() -> tuple:
    return None, "absent"


def run_voicefile(argv: Sequence[str], home: DataHome, registry: Registry, cat: Catalog, io, *, training: TrainingEnv, now: Optional[datetime] = None,
                  system: Optional[System] = None, tools_dir: Optional[str] = None, studio: Optional[TrainingEnv] = None, speech: Optional[listen_flow.Speech] = None,
                  serve: Optional[voicesend_flow.Serve] = None) -> int:
    """`python3 -m voice_studio.voicefile COMMAND ...`. `studio` finds the studio programs (the ones that carry the speech engine) for `listen`; `speech` finds the listening model
    (the one that writes down recordings), which `listen` uses to write down what it hears; by default it is looked for where the recordings commands look."""
    command = argv[0] if argv else "help"
    rest = list(argv[1:])
    system = system or RealSystem()
    tools = tools_dir or str(jobs.TOOLS_DIR)
    try:
        if command in ("help", "--help", "-h"):
            return _help(cat, io)
        if command == "list":
            return _list(rest, home, cat, io)
        if command == "make":
            return _make(rest, home, now, training, system, tools, registry, cat, io)
        if command == "listen":
            return listen_flow.run_listen(rest, home, now, training, studio or _no_studio, system, tools, cat, io,
                                            speech=speech or (lambda: envfind.speech_model(home, registry)))
        if command == "send":
            return voicesend_flow.run_send(rest, home, cat, io, system=system, now=now, serve=serve)
        io.say(cat.t("cli.bad_command", command=command[:60]))
        return EXIT_NOTHING_DONE
    except KeyboardInterrupt:
        io.say(cat.t("cli.nothing_done"))
        return EXIT_PROBLEM
    except rd.RoundsError as error:
        _say_parts(cat, io, "rounds", error.code, error.detail)
        return EXIT_PROBLEM
