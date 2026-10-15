# SPDX-License-Identifier: GPL-3.0-or-later
"""Helpers for the listening tests: a project with a made voice file, a training environment that holds pronunciation data, and a studio environment whose Python is a stand-in program.

The stand-in is a real executable: it runs the real speaking program (voice_studio/listen_runner.py) in a real child process, with a stand-in for the engine behind it, so the job file,
the process boundary, the output lines and the sound files are all the real ones. The `System` really runs that stand-in, but only records the sound players and answers for them."""
import json
import math
import os
import stat
import sys
from pathlib import Path

from vs_voice_helpers import PATCHED, onnx_bytes, piper_config, write_voice
from vs_voicefile_helpers import MakerSystem, ProjectRig, TOOLS, write_settings
from voice_studio.core import voicezip
from voice_studio.core.envbuild import EnvPaths
from voice_studio.core.system import CommandResult, RealSystem

VOICE_FOLDER = "voice-check-round-001-20261011-130000"
SENTENCES = ("Hello, my name is Anna.", "I need some help, please.", "Thank you, that is all.")
SYMBOLS = {"_": [0], "^": [1], "$": [2], " ": [3], "a": [4], "b": [5], "e": [6], "eɪ": [7], "\n": [8]}      # one two-character sound and the line break: both left out of the list of sounds
DATA_FILES = ("phontab", "phondata", "phonindex", "intonations", "en_dict")

STUB = r'''
import json, math, os, sys, types
here = os.path.dirname(os.path.abspath(__file__))
mode = open(os.path.join(here, "mode.txt")).read().strip()
args = sys.argv[1:]
sys.path.insert(0, os.environ.get("PYTHONPATH", ""))
seen = {"args": args, "cwd": os.getcwd(), "pythonpath": os.environ.get("PYTHONPATH", "")}
if args[:2] == ["-m", "voice_studio.hear_runner"] and len(args) == 3:
    hear_mode = open(os.path.join(here, "hear-mode.txt")).read().strip() if os.path.exists(os.path.join(here, "hear-mode.txt")) else "ok"
    scripted = json.load(open(os.path.join(here, "heard.json"))) if os.path.exists(os.path.join(here, "heard.json")) else []
    seen["job"] = json.load(open(args[2]))
    seen["job_mode"] = oct(os.stat(args[2]).st_mode & 0o777)
    json.dump(seen, open(os.path.join(here, "seen-hear.json"), "w"))
    from voice_studio import hear_runner as hr
    class Hearer:
        calls = 0
        def transcribe(self, samples):
            self.calls += 1
            if hear_mode == "hear_fail": raise RuntimeError("boom words")
            return scripted[self.calls - 1] if self.calls <= len(scripted) else ""
    def hear_factory(model_dir):
        seen["offline"] = {k: os.environ.get(k) for k in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE")}       # set by the program itself before the model is asked for
        json.dump(seen, open(os.path.join(here, "seen-hear.json"), "w"))
        if hear_mode == "hear_no_engine": raise ImportError("no faster_whisper")
        if hear_mode == "hear_load_failed": raise ValueError("cannot load")
        return Hearer()
    if hear_mode == "hear_crash":
        print("Traceback: the listening model fell over", file=sys.stderr); sys.exit(1)
    if hear_mode == "hear_nothing":
        sys.exit(0)
    if hear_mode == "hear_extra":
        print(json.dumps({"event": "heard", "n": 1, "text": "x"})); print(json.dumps({"event": "heard", "n": 1, "text": "y"})); print(json.dumps({"event": "done", "clips": 2})); sys.exit(0)
    if hear_mode == "hear_duplicate":
        for n in (1, 1, 2, 3): print(json.dumps({"event": "heard", "n": n, "text": "x"}))
        print(json.dumps({"event": "done", "clips": 3})); sys.exit(0)
    if hear_mode == "hear_not_text_full":
        print(json.dumps({"event": "heard", "n": 1, "text": 5})); print(json.dumps({"event": "heard", "n": 2, "text": "y"})); print(json.dumps({"event": "heard", "n": 3, "text": "z"}))
        print(json.dumps({"event": "done", "clips": 3})); sys.exit(0)
    if hear_mode == "hear_out_of_range":
        print(json.dumps({"event": "heard", "n": 9, "text": "x"})); sys.exit(0)
    if hear_mode == "hear_not_text":
        print(json.dumps({"event": "heard", "n": 1, "text": 5})); sys.exit(0)
    sys.exit(hr.main(args[2:], engine_factory=hear_factory))
if args[:2] != ["-m", "voice_studio.listen_runner"] or len(args) != 3:
    print("unexpected arguments", args, file=sys.stderr); sys.exit(9)
job = json.load(open(args[2]))
seen["tokens"] = open(job["tokens"], encoding="utf-8").read()
seen["data_dir_exists"] = os.path.isdir(job["data_dir"])
seen["model"] = job["model"]
json.dump(seen, open(os.path.join(here, "seen.json"), "w"))
from voice_studio import listen_runner as lr
class Engine:
    sample_rate = 22050
    def generate(self, text, sid=0, speed=1.0):
        n = max(2205, len(text) * 1500)
        quiet = mode == "silent" or (mode == "first_silent" and text.startswith("Hello"))
        samples = [0.0] * n if quiet else [0.4 * math.sin(i / 12.0) for i in range(n)]
        return types.SimpleNamespace(samples=samples, sample_rate=22050)
def factory(model, tokens, data_dir, threads):
    if mode == "no_engine": raise ImportError("no sherpa_onnx")
    if mode == "load_failed": raise ValueError("cannot load")
    return Engine()
if mode == "crash":
    print("Error when reading tokens at Line ae 161. size: 2", file=sys.stderr); sys.exit(1)
if mode == "nothing":
    sys.exit(0)
if mode == "short":
    job["sentences"] = job["sentences"][:2]
    json.dump(job, open(args[2], "w"))
sys.exit(lr.main(args[2:], engine_factory=factory))
'''


class ListenSystem(RealSystem):
    """Really runs the stand-in Python and anything else that is not a sound player; records the players and answers for them."""

    def __init__(self, studio_python, *, wsl=False, installed=("ffplay",), results=None, free=None, export="ok", patch="ok"):
        self.studio_python, self.wsl, self.installed = studio_python, wsl, tuple(installed)
        self.maker = MakerSystem(export=export, patch=patch)           # the export and the patcher are stood in for, as in the voice file tests
        self.results = dict(results or {})              # player name -> CommandResult (default: success)
        self.free = free
        self.wslpath_ok = True
        self.played = []                                # (program name, argv, timeout)
        self.windows_path = "\\\\wsl.localhost\\Ubuntu\\home\\anna\\listening\\clip-1.wav"

    def read_text(self, path):
        if path == "/proc/version":
            return "Linux version 5.15.0-microsoft-standard-WSL2" if self.wsl else "Linux version 6.8.0-generic"
        return super().read_text(path)

    def which(self, name):
        return "/usr/bin/" + name if name in self.installed else None

    def disk_free(self, path):
        if isinstance(self.free, dict):                       # a different answer for different places: {place: (total, free)}
            for place, value in self.free.items():
                if path == place or path.startswith(place.rstrip("/") + "/"):
                    return value
            return super().disk_free(path)
        return self.free if self.free is not None else super().disk_free(path)

    def run(self, argv, timeout=15.0, cwd=None, env=None):
        name = os.path.basename(argv[0])
        if name == "wslpath":
            return CommandResult(0, self.windows_path + "\n") if self.wslpath_ok else CommandResult(1, "", "no")
        if "piper.train.export_onnx" in argv or (len(argv) > 1 and str(argv[1]).endswith("patch_voice_for_sherpa_onnx.py")):
            return self.maker.run(argv, timeout=timeout, cwd=cwd, env=env)
        if argv[0].startswith("/usr/bin/") and name != "wslpath":
            self.played.append((name, tuple(argv), timeout))
            return self.results.get(name, CommandResult(0))
        return super().run(argv, timeout=timeout, cwd=cwd, env=env)


class ListenRig(ProjectRig):
    """The shared project, a voice file in its exports, the two environments, and a way to run `listen` on a made-up terminal."""

    def __init__(self, tmp_path, *, language="en-us", make=True, data=True, wsl=False, installed=("ffplay",), mode="ok", export="ok", patch="ok", **kw):
        super().__init__(tmp_path, **kw)
        self.tmp = tmp_path
        self.studio = EnvPaths(str(tmp_path / "environments" / "studio-xyz"))
        self.language = language
        self.write_studio(mode)
        if data:
            self.write_data(language)
        if make:
            self.make_voice(VOICE_FOLDER, language=language)
        self.system = ListenSystem(self.studio.python, wsl=wsl, installed=installed, export=export, patch=patch)
        self.speech_dir = tmp_path / "speech-model"

    def speech_ready(self):
        """A resolver that says the listening model is here (a folder; the stand-in never reads it)."""
        self.speech_dir.mkdir(exist_ok=True)
        return lambda: (str(self.speech_dir), "ready")

    def set_hear_mode(self, mode):
        (Path(self.studio.venv) / "bin" / "hear-mode.txt").write_text(mode)

    def set_heard(self, texts):
        (Path(self.studio.venv) / "bin" / "heard.json").write_text(json.dumps(list(texts)))

    def seen_hear(self):
        return json.loads((Path(self.studio.venv) / "bin" / "seen-hear.json").read_text())

    def heard_ran(self):
        return (Path(self.studio.venv) / "bin" / "seen-hear.json").exists()

    def finish_rounds(self, count=2, language="en-us"):
        """`count` finished rounds with their settings files, the last one chosen (the settings say the language)."""
        self.finish(count)
        for number in range(1, count + 1):
            config = piper_config()
            config["espeak"]["voice"] = language
            write_settings(self.paths, number, config)

    def write_studio(self, mode="ok"):
        folder = Path(self.studio.venv) / "bin"
        folder.mkdir(parents=True, exist_ok=True)
        stub = folder / "stub.py"
        stub.write_text(STUB)
        python = Path(self.studio.python)
        python.write_text('#!/bin/sh\nexec "%s" "%s" "$@"\n' % (sys.executable, stub))
        python.chmod(python.stat().st_mode | stat.S_IXUSR)
        (folder / "mode.txt").write_text(mode)

    def set_mode(self, mode):
        (Path(self.studio.venv) / "bin" / "mode.txt").write_text(mode)

    def seen(self):
        return json.loads((Path(self.studio.venv) / "bin" / "seen.json").read_text())

    def write_data(self, language="en-us", version="python3.12", files=DATA_FILES):
        folder = Path(self.training.venv) / "lib" / version / "site-packages" / "piper" / "espeak-ng-data"
        folder.mkdir(parents=True, exist_ok=True)
        for name in files:
            (folder / name).write_bytes(b"data")
        if not language.lower().startswith("en"):
            (folder / ("%s_dict" % language.split("-")[0])).write_bytes(b"data")
        return str(folder)

    def make_voice(self, name, language="en-us", symbols=None, patched=True, zip_it=True):
        folder = Path(self.paths.exports) / name
        config = piper_config(symbols=symbols if symbols is not None else SYMBOLS)
        config["espeak"]["voice"] = language
        model, conf = write_voice(folder, metadata=PATCHED if patched else {}, config=config, name="my_voice")
        if zip_it and patched:
            voicezip.write_voice_zip(model, conf, folder / (name + ".zip"))
        elif zip_it:
            (folder / (name + ".zip")).write_bytes(b"PK")                  # a zip that is there but is not this voice's
        return folder

    def studio_env(self):
        return (self.studio, "ready")


class FlowRig(ListenRig):
    """A rig that runs `listen` on a made-up terminal. `speech` is the listening-model lookup: None means it is not there; "ready" means it is."""

    def run(self, *argv, answers=(), interactive=True, training=None, studio=None, speech=None):
        from vs_rounds_helpers import NOW
        from vs_startvoice_helpers import Terminal, implies_permission, leaked_keys
        from voice_studio.core import listen_flow as lf, text
        io = Terminal(answers, interactive)
        lookup = self.speech_ready() if speech == "ready" else speech
        code = lf.run_listen(list(argv), self.home, NOW, training or self.training_env, studio or self.studio_env, self.system, str(TOOLS), text.load_catalog("en"), io, speech=lookup)
        assert leaked_keys(io.text + "\n".join(io.prompts)) == [], "a catalog key was printed instead of words"
        assert implies_permission(io.text) == [], "something printed says or implies that use is permitted"
        return code, io

    def made(self):
        folder = Path(self.paths.default_scratch, "listening")
        return sorted(os.listdir(folder)) if folder.is_dir() else []

    def folder_of(self, name):
        return Path(self.paths.default_scratch, "listening", name)
