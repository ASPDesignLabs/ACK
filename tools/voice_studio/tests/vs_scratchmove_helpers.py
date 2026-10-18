# SPDX-License-Identifier: GPL-3.0-or-later
"""Stand-ins for the move-scratch tests: a project with a default scratch that holds a training set and one round's working files, a folder that stands for another drive, and a computer whose
mount table and free room the test chooses (the machine running the tests never decides whether a place is a memory disk)."""
import os
from pathlib import Path

from vs_refresh_helpers import CAT
from voice_studio.core import scratchmove_flow as smf
from voice_studio.core.paths import DataHome, ProjectPaths
from voice_studio.core.project import create_project, load_project
from voice_studio.core.system import RealSystem

TERMINAL_MOUNTS = "/dev/sda1 / ext4 rw,relatime 0 0\n"
BIG = (10 ** 13, 4 * 10 ** 12)
FILES = {"datasets/d1/wav/a.wav": b"RIFF" + bytes(range(256)) * 20, "datasets/d1/wav/b.wav": b"RIFF" + bytes(reversed(range(256))) * 33, "datasets/d1/metadata.csv": b"a.wav|hello there\nb.wav|and again\n",
         "caches/d1-r001/mels.bin": bytes(range(256)) * 400}


class ScratchSystem(RealSystem):
    """The real disk for files, with the mount table, the kind of computer and the free room chosen by the test."""

    def __init__(self, mounts=TERMINAL_MOUNTS, wsl=False, free=None):
        self.mounts, self.wsl, self.free = mounts, wsl, free
        self.asked_free = []

    def read_text(self, path):
        if path == "/proc/mounts":
            return self.mounts
        if path == "/proc/version":
            return "Linux version 5.15.0-microsoft-standard-WSL2" if self.wsl else "Linux version 6.8.0-generic"
        return super().read_text(path)

    def environ(self):
        return {}

    def run(self, argv, timeout=15.0, cwd=None, env=None):
        return None if os.path.basename(argv[0]) == "lsblk" else super().run(argv, timeout, cwd, env)

    def disk_free(self, path):
        self.asked_free.append(path)
        if callable(self.free):
            return self.free(path)
        return self.free if self.free is not None else BIG


class ScratchRig:
    def __init__(self, tmp_path, *, files=FILES, name="Voice check"):
        self.tmp = Path(tmp_path)
        self.home = DataHome(str(self.tmp / "home"))
        self.project = create_project(self.home.projects, name, "own")
        self.paths = ProjectPaths(self.home.projects + "/" + self.project.id)
        os.makedirs(self.home.jobs, exist_ok=True)
        self.drive = self.tmp / "drive"                             # stands for another drive: an empty folder
        self.drive.mkdir()
        self.system = ScratchSystem()
        for rel, data in files.items():
            self.put(self.paths.default_scratch, rel, data)
        os.makedirs(self.paths.default_scratch + "/datasets/empty", exist_ok=True)

    @staticmethod
    def put(root, rel, data):
        path = Path(root, rel)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return str(path)

    def saved(self):
        return load_project(self.paths)

    def tree(self, root):
        found = {}
        for path in sorted(Path(root).rglob("*")):
            if path.is_symlink():
                found[str(path.relative_to(root))] = "->" + os.readlink(path)
            elif path.is_file():
                found[str(path.relative_to(root))] = (path.read_bytes(), oct(path.stat().st_mode & 0o777))
            elif path.is_dir():
                found[str(path.relative_to(root)) + "/"] = oct(path.stat().st_mode & 0o777)
        return found

    def contents(self, root):
        """Just the names and the bytes, for comparing two folders that were made at different times."""
        return {k: (v[0] if isinstance(v, tuple) else None) for k, v in self.tree(root).items()}

    def second_project(self, name="Ben"):
        project = create_project(self.home.projects, name, "own")
        return project
