# SPDX-License-Identifier: GPL-3.0-or-later
"""A computer for the WSL help tests: Ubuntu under Windows, with the Windows C drive a real folder in a temporary place, and a Windows program that answers as a test says."""
import os

from vs_fakes import PROC_NATIVE, PROC_WSL1, PROC_WSL2
from voice_studio.core.system import CommandResult, RealSystem

VER_11 = "\r\nMicrosoft Windows [Version 10.0.22631.4460]\r\n"
VER_10 = "\r\nMicrosoft Windows [Version 10.0.19045.5011]\r\n"
SAME = object()
PATH_CMD = "/mnt/c/Windows/system32/cmd.exe"          # where WSL puts it on the search path
KNOWN_CMD = "/mnt/c/Windows/System32/cmd.exe"         # where Windows keeps it


class WslSystem(RealSystem):
    """The real files (the Windows drive is a folder made by the test), a made-up kernel, environment and programs."""

    def __init__(self, tmp_path, *, kernel=PROC_WSL2, cmd=SAME, wslinfo=None, users=("Anna",), automount="mnt", wsl_conf=SAME, distro="Ubuntu-24.04", profile=SAME, cmd_on_path=True):
        self.root = str(tmp_path / automount)
        self.kernel, self.distro, self.cmd_on_path = kernel, distro, cmd_on_path
        self.cmd = CommandResult(0, VER_11) if cmd is SAME else cmd
        self.wslinfo = wslinfo
        self.profile = SAME if profile is SAME else profile
        self.ran = []
        self.wsl_conf = ("[automount]\nroot = %s/\n" % self.root) if wsl_conf is SAME else wsl_conf
        for name in users:
            os.makedirs("%s/c/Users/%s" % (self.root, name), exist_ok=True)
        os.makedirs("%s/c/Users" % self.root, exist_ok=True)
        self.user_files = {}

    @property
    def c_users(self):
        return "%s/c/Users" % self.root

    def config_path(self, name="Anna"):
        return "%s/%s/.wslconfig" % (self.c_users, name)

    def write_config(self, text, name="Anna", binary=None):
        with open(self.config_path(name), "wb") as out:
            out.write(binary if binary is not None else text.encode("utf-8"))

    def read_config(self, name="Anna"):
        with open(self.config_path(name), "rb") as source:
            return source.read().decode("utf-8")

    def read_text(self, path):
        if path == "/proc/version":
            return self.kernel
        if path == "/etc/wsl.conf":
            return self.wsl_conf
        return super().read_text(path)

    def environ(self):
        return {"WSL_DISTRO_NAME": self.distro} if self.distro and self.kernel != PROC_NATIVE else {}

    def which(self, name):
        if name == "cmd.exe":
            return PATH_CMD if self.cmd is not None and self.cmd_on_path else None
        if name == "wslinfo":
            return "/usr/bin/wslinfo" if self.wslinfo is not None else None
        return super().which(name)

    def exists(self, path):
        if path == KNOWN_CMD:
            return self.cmd is not None
        return super().exists(path)

    def run(self, argv, timeout=15.0, cwd=None, env=None):
        self.ran.append((tuple(argv), timeout))
        exe = os.path.basename(argv[0])
        if exe == "cmd.exe":
            if tuple(argv[1:]) == ("/c", "ver"):
                return self.cmd
            if tuple(argv[1:]) == ("/c", "echo %USERPROFILE%"):
                if self.profile is SAME:
                    return CommandResult(0, "C:\\Users\\Anna\r\n") if self.cmd is not None and self.cmd.returncode == 0 else None
                return self.profile
        if exe == "wslinfo" and tuple(argv[1:]) == ("--networking-mode",):
            return self.wslinfo
        raise AssertionError("an unexpected program was started: %r" % (argv,))
