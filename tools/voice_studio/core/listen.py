# SPDX-License-Identifier: GPL-3.0-or-later
"""Hear a finished voice on this computer before it goes to the phone (plan task VS-5.4).

The phone says a sentence with sherpa-onnx, from three things: the voice's model, a list of sounds it writes from the voice's settings file, and a folder of pronunciation data.
This does the same on the computer, with the same engine at the same version (the studio programs carry it), the same list of sounds (core/phonemes.py, held to the phone's
code by a test), and the pronunciation data that the training programs already carry, so the sound is what the phone will say. What is not the same is the speaker, and the
phone's own copy of the pronunciation data: for English the two gave the same sounds for every one of 4,961 words and 3,010 sentences tried (plan finding F35), which is evidence for
English only.

It looks at one voice file made by core/voicefile.py: the very files that are in its zip. It checks they are (the folder's model and settings file must match the zip's byte for byte,
or what is heard might not be what goes to the phone), makes a new folder of small sound files in the project's own `listening` folder (grouped by the round or voice file they were made from, so
they sit with the training they came from; they can be made again, and only *Free up space* removes them, when asked), and plays them. It changes nothing that was there. The sentences are fixed by the tool; whatever a person types is only ever written into a job file, never into a
log, and the program that speaks never prints a sentence (voice_studio/listen_runner.py).

It can also listen to a round without a zip: it makes the voice from the round's saved point the way core/voicefile.py does (the same three steps), in the new listening folder, and
afterwards offers to remove that voice copy, which is large (the sound files stay). And it can have the listening model write down what it hears in each sound file (voice_studio/hear_runner.py),
so a person who cannot judge the sound can read whether the words came out (core/heardcheck.py compares); that step is a hint, never a verdict, and is skipped, with a reason, when it cannot be done.

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
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from . import commands, phonemes, voicefile as vf, voicezip
from .diskbudget import DEFAULT_TABLE, Level, check_step, floors_for
from .envbuild import EnvPaths
from .paths import ProjectPaths
from .system import CommandResult, System

ERROR_CODES = ("no_voice", "folder_unknown", "voice_not_ready", "differs_from_zip", "no_pronunciation", "no_room", "exists", "no_engine", "runner_failed", "no_clips",
               "hear_failed")      # each has words in the text catalog
RUNNER_MODULE = "voice_studio.listen_runner"
HEAR_MODULE = "voice_studio.hear_runner"
NEED_BYTES = 32 * 1024 * 1024        # eight sentences of a minute each would be about 21 MB; the fixed ones are a few seconds: an upper bound, not a guess about this voice
HEAR_TIMEOUT_S = 300.0               # loading the listening model and writing down a few short sounds, on a processor; room for a slow computer
RUN_TIMEOUT_S = 180.0                # loading the voice takes a couple of seconds and a sentence a fraction of one, on a processor; this is room for a slow computer
ROUND_NEED_BYTES = NEED_BYTES + 2 * voicezip.MAX_MODEL_BYTES + voicezip.MAX_CONFIG_BYTES      # listening to a round also holds the voice made from it: the model and its untouched copy, at the largest size ACK takes
VOICE_COPY_NAMES = (vf.VOICE_NAME + ".onnx", vf.VOICE_NAME + ".onnx.before-patch", vf.VOICE_NAME + ".onnx.json")      # the exact files making a voice leaves in the folder; the only ones ever removed
CLIP_FILES = re.compile(r"(?:clip-\d{1,3}\.wav|tokens\.txt|job\.json|hear-job\.json)\Z")      # the small files a listening leaves besides the voice copy: the only others *Free up space* may remove
RUN_FOLDER = re.compile(r"heard-(\d{8})-(\d{6})\Z")                                                  # a listening's own folder, inside its source's
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
    round: Optional[vf.PickedRound] = None     # set when listening straight to a round: the voice is made in `folder` first, and `voice.zip_path` is ""


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

def listening_folder(paths: ProjectPaths, source: str, stamp: str) -> str:
    """Where one listening goes: `<project>/listening/<source>/heard-<date>-<time>`, `source` being the round (`round-003`) or the voice file's folder name it was made from, so the sound
    files sit with the project and the training they came from and every listening to one source is in one place. A new name every time."""
    digits = "".join(c for c in stamp if c.isdigit())
    if len(digits) < 14 or not commands.SAFE_NAME.match(source):
        raise commands.CommandError("bad_value", "stamp")
    return "%s/%s/heard-%s-%s" % (paths.listening, source, digits[:8], digits[8:14])


def round_of_source(source: str) -> int:
    """The round a listening folder's source stands for: `round-003` is round 3, and a voice file folder `voice-check-round-003-20261011-130000` was made from round 3. 0 when it cannot be told."""
    found = re.match(r"round-(\d{1,6})\Z", source) or re.search(r"-round-(\d{1,6})-\d{8}-\d{6}\Z", source)
    return int(found.group(1)) if found else 0


def plan_listen(paths: ProjectPaths, voice_name: Optional[str], sentences: Sequence[str], training: EnvPaths, system: System, stamp: str, free_bytes: Optional[int]) -> ListenPlan:
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
    return ListenPlan(voice, listening_folder(paths, voice.name, stamp), tuple(sentences), data_dir, language, language.lower().startswith("en"), len(tokens.skipped),
                      NEED_BYTES, free_bytes, room)


def plan_listen_round(paths: ProjectPaths, record, number: Optional[int], sentences: Sequence[str], training: EnvPaths, system: System, stamp: str,
                      free_bytes: Optional[int]) -> ListenPlan:
    """What listening straight to a round (the chosen one, or the one with this number) would do. Changes nothing. Refuses, with a code, when a voice cannot honestly be made from
    that round (core/voicefile.py::pick_round: a VoiceFileError), when its settings file cannot give a list of sounds (core/phonemes.TokensError), or for no pronunciation data or no room."""
    pick = vf.pick_round(paths, record, number)
    try:
        config_text = Path(pick.settings).read_text(encoding="utf-8", errors="strict")
    except (OSError, UnicodeDecodeError):
        raise phonemes.TokensError("not_json")
    tokens = phonemes.tokens_text(config_text)
    language = language_of(config_text)
    data_dir = espeak_data(training, system, language)
    if data_dir is None:
        raise ListenError("no_pronunciation", language)
    room = check_step(free_bytes, ROUND_NEED_BYTES, floors_for(DEFAULT_TABLE, holds_recordings=True))
    if room is Level.NOT_ENOUGH:
        raise ListenError("no_room", "%d free, %d needed" % (free_bytes or 0, ROUND_NEED_BYTES))
    name = "round-%03d" % pick.number
    folder = listening_folder(paths, name, stamp)
    voice = VoiceFolder(name, folder, "%s/%s.onnx" % (folder, vf.VOICE_NAME), "%s/%s.onnx.json" % (folder, vf.VOICE_NAME), "")
    return ListenPlan(voice, folder, tuple(sentences), data_dir, language, language.lower().startswith("en"), len(tokens.skipped), ROUND_NEED_BYTES, free_bytes, room, pick)


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


def listen(plan: ListenPlan, studio: EnvPaths, system: System, tools_dir: str, stage: Optional[Callable[[str], None]] = None, training: Optional[EnvPaths] = None) -> Heard:
    """Make the sound files. Any failure raises ListenError (or, making a voice from a round, core/voicefile.py's VoiceFileError); the new folder is left as it is, and nothing is deleted.
    A plan for a round needs `training` (the programs that make the voice)."""
    tell = stage or (lambda _name: None)
    if plan.round is not None and training is None:
        raise ListenError("runner_failed", "the training programs were not given")
    try:
        source = os.path.dirname(plan.folder)
        os.makedirs(os.path.dirname(source), mode=0o700, exist_ok=True)          # each folder is made for its owner only: makedirs applies the mode to the last one only
        os.makedirs(source, mode=0o700, exist_ok=True)
        os.mkdir(plan.folder, 0o700)
    except FileExistsError:
        raise ListenError("exists", os.path.basename(plan.folder))
    except OSError as error:
        raise ListenError("exists", error.strerror or type(error).__name__)
    here = plan.folder
    if plan.round is not None:
        vf.prepare_voice(here, plan.round.checkpoint, plan.round.settings, plan.voice.model, training, tools_dir, system, tell)      # type: ignore[arg-type]
        found = voicezip.check_voice(Path(plan.voice.model), Path(plan.voice.config))
        if found.problems:
            raise ListenError("voice_not_ready", ",".join(found.problems), here)
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


# ---------------------------------------------------------------- writing down what is heard

def hear(heard: Heard, speech_dir: str, studio: EnvPaths, system: System, tools_dir: str) -> Dict[int, str]:
    """What the listening model writes down for each sound that is not silent, by the clip's number. Never told what the voice was asked to say. Any failure raises
    ListenError("hear_failed"); the sound files are as they were, so the person can still play them."""
    audible = [clip for clip in heard.clips if not clip.silent]
    if not audible:
        return {}
    job_path = heard.folder + "/hear-job.json"
    try:
        _write_private(job_path, json.dumps({"model_dir": speech_dir, "clips": [clip.path for clip in audible]}))
    except OSError as error:
        raise ListenError("hear_failed", error.strerror or type(error).__name__, heard.folder)
    done = system.run([studio.python, "-m", HEAR_MODULE, job_path], timeout=HEAR_TIMEOUT_S, cwd=heard.folder, env={"PYTHONPATH": tools_dir})
    events = _events(done.stdout) if done is not None else []
    problem = next((e for e in events if e.get("event") == "error"), None)
    if problem is not None:
        raise ListenError("hear_failed", " ".join(str(problem.get(k)) for k in ("code", "kind", "n") if problem.get(k)), heard.folder)
    if done is None:
        raise ListenError("hear_failed", "the listening program could not be started or took too long", heard.folder)
    if done.returncode != 0:
        raise ListenError("hear_failed", _tail(done) or ("exit code %d" % done.returncode), heard.folder)
    texts: Dict[int, str] = {}
    for item in (e for e in events if e.get("event") == "heard"):
        number, text = item.get("n"), item.get("text")
        if not (isinstance(number, int) and 1 <= number <= len(audible) and isinstance(text, str) and audible[number - 1].number not in texts):
            raise ListenError("hear_failed", "an answer was not as expected", heard.folder)
        texts[audible[number - 1].number] = text
    if len(texts) != len(audible):
        raise ListenError("hear_failed", "%d of %d" % (len(texts), len(audible)), heard.folder)
    return texts


# ---------------------------------------------------------------- the voice copy a round leaves behind

def voice_copy(plan: ListenPlan) -> List[Tuple[str, int]]:
    """(name, bytes) of the voice copy that making a voice from a round left in the listening folder: exactly the files it makes, plain files only. Nothing for any other plan: a
    voice file that was made earlier is never touched. Looks only."""
    if plan.round is None:
        return []
    found = []
    for name in VOICE_COPY_NAMES:
        path = "%s/%s" % (plan.folder, name)
        if os.path.isfile(path) and not os.path.islink(path):
            found.append((name, os.stat(path).st_size))
    return found


def remove_voice_copy(plan: ListenPlan) -> Tuple[List[str], List[str]]:
    """Remove the voice copy (see `voice_copy`). (names removed, names that could not be). The sound files, the list of sounds and the job files stay."""
    removed, failed = [], []
    for name, _size in voice_copy(plan):
        try:
            os.unlink("%s/%s" % (plan.folder, name))
            removed.append(name)
        except OSError:
            failed.append(name)
    return removed, failed
