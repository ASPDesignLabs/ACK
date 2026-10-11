# SPDX-License-Identifier: GPL-3.0-or-later
"""Helpers for the voice file tests: a project with finished rounds and their settings files, and a stand-in for the programs that make the voice (the export and the patcher)
that writes what they write, so the real checks of core/voicezip.py run on real-shaped files."""
import json
import os
import shutil
from pathlib import Path

from vs_fakes import FakeSystem
from vs_rounds_helpers import DATASET, make_world
from vs_voice_helpers import PATCHED, onnx_bytes, piper_config
from voice_studio.core.system import CommandResult

TOOLS = Path(__file__).resolve().parents[2]


class MakerSystem(FakeSystem):
    """The export writes a model file with no metadata (as Piper's own export does); the patcher keeps the original beside it and writes the metadata. Anything can be made to fail."""

    def __init__(self, *args, export="ok", patch="ok", **kw):
        super().__init__(*args, **kw)
        self.export, self.patch = export, patch
        self.calls = []

    def run(self, argv, timeout=15.0, cwd=None, env=None):
        argv = tuple(argv)
        if "piper.train.export_onnx" in argv:
            self.calls.append(("export", argv, timeout, cwd))
            if self.export == "interrupt":
                raise KeyboardInterrupt()
            if self.export == "none":
                return None
            if self.export == "fail":
                return CommandResult(1, "", "Traceback\nGuardOnDataDependentSymNode: boom\n")
            if self.export in ("ok", "wrote_then_failed"):
                target = argv[argv.index("--output-file") + 1]
                with open(target, "wb") as handle:
                    handle.write(onnx_bytes({}))
            return CommandResult(1 if self.export == "wrote_then_failed" else 0, "exported\n", "")
        if argv[1:2] and argv[1].endswith("patch_voice_for_sherpa_onnx.py"):
            self.calls.append(("patch", argv, timeout, cwd))
            model = argv[2]
            if self.patch == "none":
                return None
            if self.patch == "fail":
                return CommandResult(2, "", "onnx is not installed\n")
            if self.patch == "ok":
                shutil.copyfile(model, model + ".before-patch")
                with open(model, "wb") as handle:
                    handle.write(onnx_bytes(PATCHED))
            return CommandResult(0, "patched\n", "")
        return super().run(argv, timeout, cwd, env)

    def kinds(self):
        return [c[0] for c in self.calls]


def write_settings(paths, number, config=None):
    """The settings file the trainer wrote for a round (core/voicefile.py::settings_file)."""
    os.makedirs(paths.round_configs, exist_ok=True)
    path = "%s/round-%03d.json" % (paths.round_configs, number)
    with open(path, "w") as handle:
        json.dump(piper_config() if config is None else config, handle)
    return path


def finished_rounds(world, count=2, settings=True):
    """`count` finished rounds, the last one chosen, each with its settings file."""
    for version in range(count):
        world.run_round(version=version)
        if settings:
            write_settings(world.paths, version + 1)


def tree_of(root):
    return sorted(str(p) for p in Path(root).rglob("*") if p.is_file() or p.is_symlink())


class ProjectRig:
    """A project called Voice check with a made-up training environment, a place for rounds, and a stand-in for the programs that make the voice."""

    def __init__(self, tmp_path, environment="ready", **system_kw):
        from vs_rounds_helpers import World, write_checkpoint
        from voice_studio.core.envbuild import EnvPaths
        from voice_studio.core.paths import DataHome, ProjectPaths, ScratchPaths
        from voice_studio.core.project import create_project
        self.home = DataHome(str(tmp_path / "home"))
        create_project(self.home.projects, "Voice check", "own")
        self.paths = ProjectPaths(self.home.projects + "/voice-check")
        os.makedirs(self.home.jobs, exist_ok=True)
        self.training = EnvPaths(str(tmp_path / "environments" / "training-abc"))
        self.environment = environment
        base = tmp_path / "voices" / "mike.ckpt"
        base.parent.mkdir(parents=True)
        write_checkpoint(str(base))
        self.world = World(self.paths, ScratchPaths(self.paths.default_scratch), self.home.jobs, self.training, str(base))
        self.system = MakerSystem(disks={self.paths.rounds: (500 * 2**30, 300 * 2**30)}, **system_kw)

    def training_env(self):
        return (self.training, "ready") if self.environment == "ready" else (None, self.environment)

    def finish(self, count=2, **kw):
        for version in range(count):
            self.world.run_round(version=version, **kw)
            write_settings(self.paths, version + 1)

    def exports(self):
        return sorted(os.listdir(self.paths.exports)) if os.path.isdir(self.paths.exports) else []
