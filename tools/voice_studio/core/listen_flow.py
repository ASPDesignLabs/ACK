# SPDX-License-Identifier: GPL-3.0-or-later
"""The words and the order of hearing a voice file on this computer (plan task VS-5.4): `python3 -m voice_studio.voicefile listen`.

It shows what it will do, checks the room, and asks first (a typed yes, or `--yes`; the window asks with its Yes and No buttons); a terminal with nobody at it is never asked. It writes
only a new folder of small sound files in the project's own `listening` folder (with the training they came from; only *Free up space* removes them). When a step fails it says which, where the folder is, and that nothing was deleted. Afterwards it asks whether
the sounds were heard, because a player that ran to the end does not prove that a speaker made a sound.

`--round` listens straight to a round (a number, or the word chosen) with no zip file: it makes the voice from that round's saved point in the new folder first, and afterwards asks
whether to remove that voice copy (only a yes removes it; the sound files stay; if it is kept, *Free up space* offers it later). When the listening model is set up and the voice is English, it also writes down what the computer
hears in each sound and shows it beside the sentence, as a hint and never a verdict; when it cannot, it says why and goes on.

The decisions are in core/listen.py and core/playback.py; every sentence a person reads is in the text catalog. Exit codes: 0 done, 1 something failed or could not be done,
2 nothing was done (declined, nobody to ask, an option that could not be told).
"""
from __future__ import annotations

from datetime import datetime
from typing import Callable, Optional, Sequence, Tuple

from . import commands, heardcheck, jobs, listen, phonemes, playback, voicefile as vf, voicezip
from .cliargs import ArgError, parse_args
from .diskbudget import Level
from .paths import DataHome
from .projects_flow import EXIT_NOTHING_DONE, EXIT_OK, EXIT_PROBLEM, say_bad_arg
from .rounds_flow import BUILDENV_COMMAND, PROJECT, ROUNDS_COMMAND, YES, TrainingEnv, _ask_yes, _confirmed, _free, _look, _number, _open, _say_parts
from .setup_flow import IO
from .system import System
from .text import Catalog, size_text

FOLDER = {"--folder": "folder"}
ROUND = {"--round": "round"}
OPTIONS = frozenset(YES) | frozenset(PROJECT) | frozenset(FOLDER) | frozenset(ROUND)                 # the checklist is held to these
CHOSEN = "chosen"
MODEL_COMMAND = "python3 -m voice_studio.recordings model"
Speech = Callable[[], Tuple[Optional[str], str]]
SENTENCE_KEYS = ("listen.sentence.1", "listen.sentence.2", "listen.sentence.3")
STUDIO_COMMAND = "python3 -m voice_studio.buildenv studio"
STAGE_TEXT = {"export": "listen.stage_export", "settings": None, "patch": "listen.stage_patch", "sounds": "listen.stage_sounds", "speaking": "listen.stage_speaking",
              "hearing": "listen.stage_hearing"}                    # the settings step of making a voice has no line of its own: it is instant
HEAR_PLAN_TEXT = {"yes": "listen.plan_hear", "no_model": "listen.plan_hear_no_model", "english_only": "listen.plan_hear_english_only"}
HEARD_TEXT = {heardcheck.SAME: "listen.heard_same", heardcheck.DIFFERENT: "listen.heard_different", heardcheck.NOTHING: "listen.heard_nothing"}


def _no_speech() -> Tuple[None, str]:
    return None, "missing"


def _state_words(cat: Catalog, state: str) -> str:
    """The plain words for how an environment stands (Not set up yet, ...); a state with no words reads as itself, never as a catalog key."""
    words = cat.t("env.state." + state)
    return state if words == "env.state." + state else words


def sentences(cat: Catalog) -> tuple:
    return tuple(cat.t(key) for key in SENTENCE_KEYS)


def _say_plan(plan: listen.ListenPlan, hearing: str, cat: Catalog, io: IO) -> None:
    if plan.round is not None:
        io.say(cat.t("listen.plan_head_round", number=plan.round.number))
        io.say("  " + cat.t("listen.plan_round", number=plan.round.number, size=size_text(plan.round.checkpoint_bytes), minutes=plan.round.trained_minutes))
    else:
        io.say(cat.t("listen.plan_head"))
        io.say("  " + cat.t("listen.plan_voice", folder=plan.voice.folder))
    io.say("  " + cat.t("listen.plan_sentences"))
    for number, text in enumerate(plan.sentences, 1):
        io.say("    " + cat.t("listen.plan_sentence_row", number=number, text=text))
    io.say("  " + cat.t("listen.plan_engine"))
    io.say("  " + cat.t("listen.plan_folder_round" if plan.round is not None else "listen.plan_folder", folder=plan.folder))
    io.say("  " + cat.t(HEAR_PLAN_TEXT[hearing], command=MODEL_COMMAND))
    io.say("  " + cat.t("listen.plan_play"))
    if plan.round is not None:
        io.say("  " + cat.t("listen.plan_copy"))
    io.say("  " + cat.t("listen.plan_time_round" if plan.round is not None else "listen.plan_time"))
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


def _hearing_kind(plan: listen.ListenPlan, speech_dir: Optional[str]) -> str:
    """Whether the listening step will happen: "yes", or why it will not (the voice is not English; the listening model is not here)."""
    if not plan.english:
        return "english_only"
    return "yes" if speech_dir else "no_model"


def _tidy_voice_copy(plan: listen.ListenPlan, project_id: str, cat: Catalog, io: IO) -> None:
    """Listening to a round leaves a large copy of the voice in the new folder. Ask whether to remove it; only a yes does, and nothing else in the folder is touched. A copy that is kept is
    still offered later by *Free up space*, and this says so and how."""
    copy = listen.voice_copy(plan)
    if not copy:
        return
    size = size_text(sum(n for _name, n in copy))
    if _ask_yes(io, cat.t("listen.copy_question", size=size)):
        _removed, failed = listen.remove_voice_copy(plan)
        io.say(cat.t("listen.copy_failed", folder=plan.folder) if failed else cat.t("listen.copy_removed", folder=plan.folder))
    else:
        io.say(cat.t("listen.copy_kept", folder=plan.folder, size=size))
        io.say(cat.t("listen.copy_kept_how", command="%s free --project %s" % (ROUNDS_COMMAND, project_id)))


def _present(plan: listen.ListenPlan, heard: listen.Heard, hearing: str, speech_dir: Optional[str], speaker, system: System, tools_dir: str, stage: Callable[[str], None],
             cat: Catalog, io: IO) -> int:
    """Show the sound files, write down what the computer hears in them when it can, play them, and ask whether they were heard."""
    io.say(cat.t("listen.made", folder=heard.folder))
    audible = [clip for clip in heard.clips if not clip.silent]
    texts = {}
    if audible and hearing == "yes" and speech_dir:
        stage("hearing")
        try:
            texts = listen.hear(heard, speech_dir, speaker, system, tools_dir)
        except listen.ListenError as error:
            _say_listen_error(error, cat, io)                     # the sounds are fine: carry on and play them
        except KeyboardInterrupt:
            io.say(cat.t("listen.hear_stopped"))
    checks = {number: heardcheck.compare(next(c.text for c in heard.clips if c.number == number), text) for number, text in texts.items()}
    for clip in heard.clips:
        io.say("  " + (cat.t("listen.clip_silent", number=clip.number, text=clip.text) if clip.silent
                       else cat.t("listen.clip_row", number=clip.number, text=clip.text, seconds="%.1f" % clip.seconds)))
        if clip.number in checks:
            io.say("      " + cat.t(HEARD_TEXT[checks[clip.number].kind], heard=checks[clip.number].heard))
    if any(check.kind != heardcheck.SAME for check in checks.values()):
        io.say(cat.t("listen.heard_hint"))
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
        io.say(cat.t("listen.heard_yes_round" if plan.round is not None else "listen.heard_yes"))
    io.say(cat.t("listen.where", folder=heard.folder))
    io.say(cat.t("listen.done_next_round" if plan.round is not None else "listen.done_next"))
    return EXIT_OK


def run_listen(args: Sequence[str], home: DataHome, now: Optional[datetime], training: TrainingEnv, studio: TrainingEnv, system: System, tools_dir: str, cat: Catalog, io: IO,
               speech: Optional[Speech] = None) -> int:
    try:
        parsed = parse_args(args, flags=YES, values={**PROJECT, **FOLDER, **ROUND}, max_words=0)
    except ArgError as error:
        return say_bad_arg(error, cat, io)
    io.say(cat.t("listen.title"))
    wanted_round = parsed.values.get("round")
    number: Optional[int] = None
    if wanted_round is not None:
        if "folder" in parsed.values:
            io.say(cat.t("listen.round_and_folder"))
            return EXIT_NOTHING_DONE
        if wanted_round.strip().lower() != CHOSEN:
            number = _number(wanted_round.strip())
            if number is None or number < 1:
                io.say(cat.t("listen.bad_round", text=wanted_round[:40]))
                return EXIT_NOTHING_DONE
    ctx, code = _open(parsed, home, cat, io)
    if ctx is None:
        return code
    pronunciation, state = training()
    if pronunciation is None:
        io.say(cat.t("voicefile.make.no_environment", state=_state_words(cat, state), command=BUILDENV_COMMAND))
        return EXIT_PROBLEM
    speaker, state = studio()
    if speaker is None:
        io.say(cat.t("listen.no_studio", state=_state_words(cat, state), command=STUDIO_COMMAND))
        return EXIT_PROBLEM
    free = _free(system, ctx)["project"]                       # the sound files are kept with the project, not in scratch
    try:
        if wanted_round is None:
            plan = listen.plan_listen(ctx.paths, parsed.values.get("folder"), sentences(cat), pronunciation, system, jobs.utc_stamp(now), free)
        else:
            record = _look(ctx, now, cat, io, write=False)
            plan = listen.plan_listen_round(ctx.paths, record, number, sentences(cat), pronunciation, system, jobs.utc_stamp(now), free)
    except listen.ListenError as error:
        _say_listen_error(error, cat, io)
        return EXIT_PROBLEM
    except vf.VoiceFileError as error:
        _say_parts(cat, io, "voicefile", error.code, error.detail)
        return EXIT_PROBLEM
    except phonemes.TokensError as error:
        _say_parts(cat, io, "phonemes", error.code, error.detail)
        return EXIT_PROBLEM
    except commands.CommandError as error:
        _say_parts(cat, io, "commands", error.code, error.detail)
        return EXIT_PROBLEM
    speech_dir, _why = (speech or _no_speech)()
    hearing = _hearing_kind(plan, speech_dir)
    _say_plan(plan, hearing, cat, io)
    declined = _confirmed(parsed, cat.t("listen.question"), cat, io)
    if declined is not None:
        return declined

    def stage(name: str) -> None:
        text = STAGE_TEXT[name]
        if text:
            io.say(cat.t(text))

    try:
        heard = listen.listen(plan, speaker, system, tools_dir, stage, training=pronunciation)
    except listen.ListenError as error:
        _say_listen_error(error, cat, io)
        if error.folder:
            io.say("  " + cat.t("voicefile.make.left_where", folder=error.folder))
        return EXIT_PROBLEM
    except vf.VoiceFileError as error:
        _say_parts(cat, io, "voicefile", error.code, error.detail)
        io.say("  " + cat.t("voicefile.make.left_where", folder=error.folder or plan.folder))
        return EXIT_PROBLEM
    except (phonemes.TokensError, commands.CommandError) as error:
        _say_parts(cat, io, "phonemes" if isinstance(error, phonemes.TokensError) else "commands", error.code, error.detail)
        io.say("  " + cat.t("voicefile.make.left_where", folder=plan.folder))
        return EXIT_PROBLEM
    except KeyboardInterrupt:
        io.say(cat.t("voicefile.make.interrupted", folder=plan.folder))
        return EXIT_PROBLEM
    code = _present(plan, heard, hearing, speech_dir, speaker, system, tools_dir, stage, cat, io)
    if plan.round is not None:
        _tidy_voice_copy(plan, ctx.project.id, cat, io)
    return code
