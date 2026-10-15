# SPDX-License-Identifier: GPL-3.0-or-later
"""The words and the order of hearing a voice file on this computer (plan task VS-5.4): `python3 -m voice_studio.voicefile listen`.

It shows what it will do, checks the room, and asks first (a typed yes, or `--yes`; the window asks with its Yes and No buttons); a terminal with nobody at it is never asked. It writes
only a new folder of small sound files under the project's scratch place. When a step fails it says which, where the folder is, and that nothing was deleted. Afterwards it asks whether
the sounds were heard, because a player that ran to the end does not prove that a speaker made a sound.

The decisions are in core/listen.py and core/playback.py; every sentence a person reads is in the text catalog. Exit codes: 0 done, 1 something failed or could not be done,
2 nothing was done (declined, nobody to ask, an option that could not be told).
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional, Sequence

from . import commands, jobs, listen, phonemes, playback, voicezip
from .cliargs import ArgError, parse_args
from .diskbudget import Level
from .paths import DataHome
from .projects_flow import EXIT_NOTHING_DONE, EXIT_OK, EXIT_PROBLEM, say_bad_arg
from .rounds_flow import BUILDENV_COMMAND, PROJECT, YES, TrainingEnv, _ask_yes, _confirmed, _free, _open, _say_parts, scratch_ready
from .setup_flow import IO
from .system import System
from .text import Catalog, size_text

FOLDER = {"--folder": "folder"}
OPTIONS = frozenset(YES) | frozenset(PROJECT) | frozenset(FOLDER)                 # the checklist is held to these
SENTENCE_KEYS = ("listen.sentence.1", "listen.sentence.2", "listen.sentence.3")
STUDIO_COMMAND = "python3 -m voice_studio.buildenv studio"
STAGE_TEXT = {"sounds": "listen.stage_sounds", "speaking": "listen.stage_speaking"}


def _state_words(cat: Catalog, state: str) -> str:
    """The plain words for how an environment stands (Not set up yet, ...); a state with no words reads as itself, never as a catalog key."""
    words = cat.t("env.state." + state)
    return state if words == "env.state." + state else words


def sentences(cat: Catalog) -> tuple:
    return tuple(cat.t(key) for key in SENTENCE_KEYS)


def _say_plan(plan: listen.ListenPlan, cat: Catalog, io: IO) -> None:
    io.say(cat.t("listen.plan_head"))
    io.say("  " + cat.t("listen.plan_voice", folder=plan.voice.folder))
    io.say("  " + cat.t("listen.plan_sentences"))
    for number, text in enumerate(plan.sentences, 1):
        io.say("    " + cat.t("listen.plan_sentence_row", number=number, text=text))
    io.say("  " + cat.t("listen.plan_engine"))
    io.say("  " + cat.t("listen.plan_folder", folder=plan.folder))
    io.say("  " + cat.t("listen.plan_play"))
    io.say("  " + cat.t("listen.plan_time"))
    if not plan.english:
        io.say(cat.t("listen.not_english"))
    io.say(cat.t("voicefile.make.checks_head"))
    if plan.free_bytes is None:
        io.say("  " + cat.t("voicefile.make.disk_unknown"))
    elif plan.room is Level.TIGHT:
        io.say("  " + cat.t("voicefile.make.disk_tight", free=size_text(plan.free_bytes), need=size_text(plan.need_bytes)))
    else:
        io.say("  " + cat.t("voicefile.make.disk_ok", need=size_text(plan.need_bytes), free=size_text(plan.free_bytes)))


def _say_listen_error(error: listen.ListenError, cat: Catalog, io: IO) -> None:
    _say_parts(cat, io, "listen", error.code, error.detail)
    if error.code == "voice_not_ready":
        for problem in error.detail.split(","):
            if problem in voicezip.PROBLEM_CODES:
                io.say("    - " + cat.t("voicezip.problem." + problem))


def run_listen(args: Sequence[str], home: DataHome, now: Optional[datetime], training: TrainingEnv, studio: TrainingEnv, system: System, tools_dir: str, cat: Catalog, io: IO) -> int:
    try:
        parsed = parse_args(args, flags=YES, values={**PROJECT, **FOLDER}, max_words=0)
    except ArgError as error:
        return say_bad_arg(error, cat, io)
    io.say(cat.t("listen.title"))
    ctx, code = _open(parsed, home, cat, io)
    if ctx is None:
        return code
    if not scratch_ready(ctx.project, ctx.paths):
        io.say(cat.t("rounds.start.scratch_not_ready"))
        return EXIT_NOTHING_DONE
    pronunciation, state = training()
    if pronunciation is None:
        io.say(cat.t("voicefile.make.no_environment", state=_state_words(cat, state), command=BUILDENV_COMMAND))
        return EXIT_PROBLEM
    speaker, state = studio()
    if speaker is None:
        io.say(cat.t("listen.no_studio", state=_state_words(cat, state), command=STUDIO_COMMAND))
        return EXIT_PROBLEM
    free = _free(system, ctx)["scratch"]
    try:
        plan = listen.plan_listen(ctx.paths, ctx.scratch, parsed.values.get("folder"), sentences(cat), pronunciation, system, jobs.utc_stamp(now), free)
    except listen.ListenError as error:
        _say_listen_error(error, cat, io)
        return EXIT_PROBLEM
    except phonemes.TokensError as error:
        _say_parts(cat, io, "phonemes", error.code, error.detail)
        return EXIT_PROBLEM
    except commands.CommandError as error:
        _say_parts(cat, io, "commands", error.code, error.detail)
        return EXIT_PROBLEM
    _say_plan(plan, cat, io)
    declined = _confirmed(parsed, cat.t("listen.question"), cat, io)
    if declined is not None:
        return declined

    def stage(name: str) -> None:
        io.say(cat.t(STAGE_TEXT[name]))

    try:
        heard = listen.listen(plan, speaker, system, tools_dir, stage)
    except listen.ListenError as error:
        _say_listen_error(error, cat, io)
        if error.folder:
            io.say("  " + cat.t("voicefile.make.left_where", folder=error.folder))
        return EXIT_PROBLEM
    except phonemes.TokensError as error:
        _say_parts(cat, io, "phonemes", error.code, error.detail)
        io.say("  " + cat.t("voicefile.make.left_where", folder=plan.folder))
        return EXIT_PROBLEM
    except KeyboardInterrupt:
        io.say(cat.t("voicefile.make.interrupted", folder=plan.folder))
        return EXIT_PROBLEM
    io.say(cat.t("listen.made", folder=heard.folder))
    for clip in heard.clips:
        io.say("  " + (cat.t("listen.clip_silent", number=clip.number, text=clip.text) if clip.silent
                       else cat.t("listen.clip_row", number=clip.number, text=clip.text, seconds="%.1f" % clip.seconds)))
    audible = [clip for clip in heard.clips if not clip.silent]
    if not audible:
        io.say(cat.t("listen.silent_all"))
        io.say(cat.t("listen.where", folder=heard.folder))
        return EXIT_PROBLEM
    if len(audible) != len(heard.clips):
        io.say(cat.t("listen.silent_some"))
    player = playback.Playback(system)
    for clip in audible:
        io.say(cat.t("listen.playing", number=clip.number, count=len(heard.clips), text=clip.text))
        if player.play(clip.path, clip.seconds) is None:
            break
    if player.worked is None:
        io.say(cat.t("listen.no_player", folder=heard.folder))
        if playback.is_wsl(system):
            io.say(cat.t("listen.no_player_wsl"))
        io.say(cat.t("cli.technical", detail="tried: " + ", ".join(player.tried())))
        io.say(cat.t("listen.where", folder=heard.folder))
        return EXIT_PROBLEM
    io.say(cat.t("cli.technical", detail="played with " + player.worked))
    answer = _ask_yes(io, cat.t("listen.heard_question"))
    if answer is False:
        io.say(cat.t("listen.heard_no", folder=heard.folder))
        return EXIT_OK
    if answer:
        io.say(cat.t("listen.heard_yes"))
    io.say(cat.t("listen.where", folder=heard.folder))
    io.say(cat.t("listen.done_next"))
    return EXIT_OK
