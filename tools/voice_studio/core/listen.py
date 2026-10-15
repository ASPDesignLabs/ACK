# SPDX-License-Identifier: GPL-3.0-or-later
"""Hear a finished voice on this computer before it goes to the phone (plan task VS-5.4).

The phone says a sentence with sherpa-onnx, from three things: the voice's model, a list of sounds it writes from the voice's settings file, and a folder of pronunciation data.
This does the same on the computer, with the same engine at the same version (the studio programs carry it), the same list of sounds (core/phonemes.py, held to the phone's
code by a test), and the pronunciation data that the training programs already carry, so the sound is what the phone will say. What is not the same is the speaker, and the
phone's own copy of the pronunciation data: for English the two gave the same sounds for every one of 4,961 words and 3,010 sentences tried (plan finding F35), which is evidence for
English only.

It looks at one voice file made by core/voicefile.py: the very files that are in its zip. It checks they are (the folder's model and settings file must match the zip's byte for byte,
or what is heard might not be what goes to the phone), makes a new folder of small sound files under the project's scratch place (disposable: they can be made again, and the tool
never deletes them), and plays them. It changes nothing that was there. The sentences are fixed by the tool; whatever a person types is only ever written into a job file, never into a
log, and the program that speaks never prints a sentence (voice_studio/listen_runner.py).

Decisions here, words in core/listen_flow.py. Starting programs goes through the `System` it is given.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional, Sequence, Tuple

from . import commands, phonemes, voicefile as vf, voicezip
from .diskbudget import DEFAULT_TABLE, Level, check_step, floors_for
from .envbuild import EnvPaths
from .paths import ProjectPaths, ScratchPaths
from .system import CommandResult, System

ERROR_CODES = ("no_voice", "folder_unknown", "voice_not_ready", "differs_from_zip", "no_pronunciation", "no_room", "exists", "no_engine", "runner_failed", "no_clips")      # each has words in the text catalog
RUNNER_MODULE = "voice_studio.listen_runner"
NEED_BYTES = 32 * 1024 * 1024        # eight sentences of a minute each would be about 21 MB; the fixed ones are a few seconds: an upper bound, not a guess about this voice
RUN_TIMEOUT_S = 180.0                # loading the voice takes a couple of seconds and a sentence a fraction of one, on a processor; this is room for a slow computer
REQUIRED_DATA = ("phontab", "phondata", "phonindex", "intonations")     # the files every language needs in the pronunciation folder; the language's own dictionary is checked too
TAIL_CHARS = 600
THREADS = 2                          # what the phone uses; it changes how fast the sound is made, not the sound


class ListenError(Exception):
    """`code` is one of ERROR_CODES; `detail` is a short fact (a name, a code, the end of what a program said) for Show details, never a sentence the voice was asked to say."""

    def __init__(self, code: str, detail: str = "", folder: str = ""):
        super().__init__(code + (": " + detail if detail else ""))
        self.code = code
        self.detail = detail
        self.folder = folder


@dataclass(frozen=True)
class VoiceFolder:
    name: str
    folder: str
    model: str
    config: str
    zip_path: str


@dataclass(frozen=True)
class ListenPlan:
    voice: VoiceFolder
    folder: str                      # the new folder the sound files are made in
    sentences: Tuple[str, ...]
    data_dir: str                    # the pronunciation data the sounds are made with
    language: str                    # the voice's own name for its language, such as en-us ("" when its settings do not say)
    english: bool                    # the fixed sentences are English: a voice for another language will not say them well
    skipped_symbols: int             # sounds the phone leaves out (core/phonemes.py), for Show details
    need_bytes: int
    free_bytes: Optional[int]
    room: Level


@dataclass(frozen=True)
class Clip:
    number: int
    path: str
    seconds: float
    silent: bool
    text: str


@dataclass(frozen=True)
class Heard:
    folder: str
    clips: Tuple[Clip, ...]
    load_seconds: float


# ---------------------------------------------------------------- which voice

def _made_at(name: str) -> Tuple[str, str]:
    found = re.search(r"-(\d{8}-\d{6})\Z", name)
    return (found.group(1) if found else "", name)


def find_voice(paths: ProjectPaths, name: Optional[str]) -> VoiceFolder:
    """The newest voice file made for this project, or the one called `name`. Looks at the disk; changes nothing."""
    made = [m for m in vf.existing_voice_files(paths) if commands.SAFE_NAME.match(m[0])]       # the name becomes part of a path: only the names this tool gives are used
    if not made:
        raise ListenError("no_voice")
    if name is None:
        pick = max((n for n, _z, _s in made), key=_made_at)           # the newest by the time in its name (the round number comes first in a name, so plain order would not do)
    elif any(n == name for n, _z, _s in made):
        pick = name
    else:
        raise ListenError("folder_unknown")
    folder = "%s/%s" % (paths.exports, pick)
    model, config, zip_path = "%s/%s.onnx" % (folder, vf.VOICE_NAME), "%s/%s.onnx.json" % (folder, vf.VOICE_NAME), "%s/%s.zip" % (folder, pick)
    for path in (model, config):
        if not os.path.isfile(path) or os.path.islink(path):
            raise ListenError("voice_not_ready", "the folder has no " + os.path.basename(path))
    return VoiceFolder(pick, folder, model, config, zip_path)


def _sha256(handle) -> str:
    digest = hashlib.sha256()
    for block in iter(lambda: handle.read(1 << 20), b""):
        digest.update(block)
    return digest.hexdigest()


def same_as_zip(voice: VoiceFolder) -> bool:
    """True only when the folder's model and settings file are, byte for byte, the two files in the zip that goes to the phone."""
    try:
        with zipfile.ZipFile(voice.zip_path) as zf:
            for entry, path in ((voicezip.MODEL_ENTRY, voice.model), (voicezip.CONFIG_ENTRY, voice.config)):
                with zf.open(entry) as inside, open(path, "rb") as outside:
                    if _sha256(inside) != _sha256(outside):
                        return False
    except (OSError, KeyError, zipfile.BadZipFile):
        return False
    return True


# ---------------------------------------------------------------- the pronunciation data

def language_of(config_text: str) -> str:
    """The voice's name for its language ("en-us") as the settings file gives it, or "" when it does not say."""
    try:
        data = json.loads(config_text)
        value = data["espeak"]["voice"]
    except (ValueError, KeyError, TypeError, RecursionError):
        return ""
    return value if isinstance(value, str) and re.match(r"^[A-Za-z0-9_-]{1,32}\Z", value) else ""


def espeak_data(training: EnvPaths, system: System, language: str) -> Optional[str]:
    """The folder of pronunciation data inside the training programs (the trainer's own copy), when it is whole for this language. Looks only."""
    base = re.match(r"[a-z]{2,3}", language.lower())
    wanted = REQUIRED_DATA + (("%s_dict" % base.group(0),) if base else ())
    lib = training.venv + "/lib"
    for name in sorted(system.listdir(lib) or [], reverse=True):
        if re.match(r"python3\.\d{1,2}\Z", name):
            folder = "%s/%s/site-packages/piper/espeak-ng-data" % (lib, name)
            if all(system.exists(folder + "/" + part) for part in wanted):
                return folder
    return None


# ---------------------------------------------------------------- the plan

def listening_folder(scratch: ScratchPaths, voice_name: str, stamp: str) -> str:
    digits = "".join(c for c in stamp if c.isdigit())
    if len(digits) < 14 or not commands.SAFE_NAME.match(voice_name):
        raise commands.CommandError("bad_value", "stamp")
    return "%s/%s-heard-%s-%s" % (scratch.listening, voice_name, digits[:8], digits[8:14])


def plan_listen(paths: ProjectPaths, scratch: ScratchPaths, voice_name: Optional[str], sentences: Sequence[str], training: EnvPaths, system: System, stamp: str,
                free_bytes: Optional[int]) -> ListenPlan:
    """What listening would do. Changes nothing. Refuses, with a code, when it cannot be done honestly: no voice file, one the phone would refuse, a folder that is not what is in
    the zip, no pronunciation data, or no room. A settings file the phone could not make a list of sounds from is a core/phonemes.TokensError."""
    voice = find_voice(paths, voice_name)
    found = voicezip.check_voice(Path(voice.model), Path(voice.config))
    if found.problems:
        raise ListenError("voice_not_ready", ",".join(found.problems))
    if not same_as_zip(voice):
        raise ListenError("differs_from_zip")
    config_text = Path(voice.config).read_text(encoding="utf-8", errors="strict")
    tokens = phonemes.tokens_text(config_text)
    language = language_of(config_text)
    data_dir = espeak_data(training, system, language)
    if data_dir is None:
        raise ListenError("no_pronunciation", language)
    room = check_step(free_bytes, NEED_BYTES, floors_for(DEFAULT_TABLE, holds_recordings=True))
    if room is Level.NOT_ENOUGH:
        raise ListenError("no_room", "%d free, %d needed" % (free_bytes or 0, NEED_BYTES))
    return ListenPlan(voice, listening_folder(scratch, voice.name, stamp), tuple(sentences), data_dir, language, language.lower().startswith("en"), len(tokens.skipped),
                      NEED_BYTES, free_bytes, room)


# ---------------------------------------------------------------- doing it

def _tail(done: Optional[CommandResult]) -> str:
    if done is None:
        return ""
    lines = [l.rstrip() for l in (done.stderr + "\n" + done.stdout).splitlines() if l.strip()]
    return " | ".join(lines[-4:])[-TAIL_CHARS:]


def _events(text: str) -> List[dict]:
    found = []
    for line in text.splitlines():
        try:
            item = json.loads(line)
        except ValueError:
            continue                                         # a warning from a library, not one of ours
        if isinstance(item, dict) and isinstance(item.get("event"), str):
            found.append(item)
    return found


def _write_private(path: str, text: str) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def listen(plan: ListenPlan, studio: EnvPaths, system: System, tools_dir: str, stage: Optional[Callable[[str], None]] = None) -> Heard:
    """Make the sound files. Any failure raises ListenError (the new folder is left as it is, and nothing is deleted)."""
    tell = stage or (lambda _name: None)
    try:
        os.makedirs(os.path.dirname(plan.folder), mode=0o700, exist_ok=True)
        os.mkdir(plan.folder, 0o700)
    except FileExistsError:
        raise ListenError("exists", os.path.basename(plan.folder))
    except OSError as error:
        raise ListenError("exists", error.strerror or type(error).__name__)
    here = plan.folder
    tell("sounds")
    tokens = phonemes.tokens_text(Path(plan.voice.config).read_text(encoding="utf-8", errors="strict"))
    tokens_path, job_path = here + "/tokens.txt", here + "/job.json"
    try:
        _write_private(tokens_path, tokens.text)
        _write_private(job_path, json.dumps({"model": plan.voice.model, "tokens": tokens_path, "data_dir": plan.data_dir, "out_dir": here, "sentences": list(plan.sentences)}))
    except OSError as error:
        raise ListenError("runner_failed", error.strerror or type(error).__name__, here)
    tell("speaking")
    done = system.run([studio.python, "-m", RUNNER_MODULE, job_path], timeout=RUN_TIMEOUT_S, cwd=here, env={"PYTHONPATH": tools_dir})
    events = _events(done.stdout) if done is not None else []
    problem = next((e for e in events if e.get("event") == "error"), None)
    if problem is not None and problem.get("code") == "no_engine":
        raise ListenError("no_engine", "", here)
    if problem is not None:
        raise ListenError("runner_failed", " ".join(str(problem.get(k)) for k in ("code", "kind") if problem.get(k)), here)
    if done is None:
        raise ListenError("runner_failed", "the speaking program could not be started or took too long", here)
    if done.returncode != 0:
        raise ListenError("runner_failed", _tail(done) or ("exit code %d" % done.returncode), here)
    loaded = next((e for e in events if e.get("event") == "loaded"), {})
    clips = []
    for item in (e for e in events if e.get("event") == "clip"):
        number = item.get("n")
        path = "%s/%s" % (here, item.get("file"))
        if not (isinstance(number, int) and 1 <= number <= len(plan.sentences) and item.get("file") == "clip-%d.wav" % number and os.path.isfile(path) and not os.path.islink(path)):
            raise ListenError("runner_failed", "a sound file was not where it was said to be", here)
        seconds = item.get("seconds")
        clips.append(Clip(number, path, float(seconds) if isinstance(seconds, (int, float)) else 0.0, item.get("silent") is not False, plan.sentences[number - 1]))
    if len(clips) != len(plan.sentences) or [c.number for c in clips] != list(range(1, len(clips) + 1)):
        raise ListenError("no_clips", "%d of %d" % (len(clips), len(plan.sentences)), here)
    seconds_to_load = loaded.get("seconds")
    return Heard(here, tuple(clips), float(seconds_to_load) if isinstance(seconds_to_load, (int, float)) else 0.0)
