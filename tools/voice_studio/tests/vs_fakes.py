# SPDX-License-Identifier: GPL-3.0-or-later
"""A fake computer for the tests: facts and command output come from the test, never from the machine running it.

The samples below are written from the documented formats (os-release(5), /proc/version, nvidia-smi's CSV query, /proc/meminfo, dpkg-query),
because the build sandbox has no GPU and no WSL. When the developer runs the spikes (plan tasks VS-0.1 to VS-0.3), replace them with
captures from the real machines; the tests should not need to change.
"""
import os
from typing import Dict, Iterable, Optional, Sequence, Set, Tuple

from voice_studio.core.system import CommandResult

UBUNTU_2404 = 'PRETTY_NAME="Ubuntu 24.04.1 LTS"\nNAME="Ubuntu"\nVERSION_ID="24.04"\nVERSION="24.04.1 LTS (Noble Numbat)"\nVERSION_CODENAME=noble\nID=ubuntu\nID_LIKE=debian\nUBUNTU_CODENAME=noble\n'
UBUNTU_2204 = 'PRETTY_NAME="Ubuntu 22.04.5 LTS"\nNAME="Ubuntu"\nVERSION_ID="22.04"\nVERSION="22.04.5 LTS (Jammy Jellyfish)"\nVERSION_CODENAME=jammy\nID=ubuntu\nID_LIKE=debian\nUBUNTU_CODENAME=jammy\n'
UBUNTU_2004 = 'NAME="Ubuntu"\nVERSION_ID="20.04"\nPRETTY_NAME="Ubuntu 20.04.6 LTS"\nID=ubuntu\nID_LIKE=debian\n'
LINUX_MINT = 'NAME="Linux Mint"\nVERSION_ID="21.3"\nPRETTY_NAME="Linux Mint 21.3"\nID=linuxmint\nID_LIKE="ubuntu debian"\nUBUNTU_CODENAME=jammy\n'
DEBIAN_12 = 'PRETTY_NAME="Debian GNU/Linux 12 (bookworm)"\nNAME="Debian GNU/Linux"\nVERSION_ID="12"\nID=debian\n'

PROC_NATIVE = "Linux version 6.8.0-45-generic (buildd@host) (x86_64-linux-gnu-gcc-13 (Ubuntu 13.2.0) 13.2.0) #45-Ubuntu SMP PREEMPT_DYNAMIC Fri Aug 30 12:02:04 UTC 2024\n"
PROC_WSL2 = "Linux version 5.15.153.1-microsoft-standard-WSL2 (root@host) (gcc (GCC) 11.2.0, GNU ld (GNU Binutils) 2.37) #1 SMP Fri Mar 29 23:14:13 UTC 2024\n"
PROC_WSL1 = "Linux version 4.4.0-19041-Microsoft (Microsoft@Microsoft.com) (gcc version 5.4.0 (GCC) ) #1237-Microsoft Sat Sep 11 14:32:00 PST 2021\n"

MEM_16G = "MemTotal:       16119428 kB\nMemFree:         9000000 kB\n"
MEM_8G = "MemTotal:        8040000 kB\n"
MEM_4G = "MemTotal:        4021000 kB\n"

SMI_4060 = "NVIDIA GeForce RTX 4060, 8188, 560.35.03\n"
SMI_3090 = "NVIDIA GeForce RTX 3090, 24576, 535.183.01\n"
SMI_6G = "NVIDIA GeForce GTX 1660, 6144, 535.183.01\n"
SMI_TWO = "NVIDIA GeForce GT 1030, 2048, 535.183.01\nNVIDIA GeForce RTX 4060, 8188, 535.183.01\n"
SMI_DRIVER_DOWN = "NVIDIA-SMI has failed because it couldn't communicate with the NVIDIA driver. Make sure that the latest NVIDIA driver is installed and running.\n"

ALL_PACKAGES = ["python3-venv", "python3-dev", "build-essential", "cmake", "ninja-build", "git", "ffmpeg", "python3-gi", "gir1.2-gtk-4.0"]
ALL_TOOLS = {n: "/usr/bin/" + n for n in ["gcc", "g++", "make", "cmake", "ninja", "git", "ffmpeg", "ffprobe", "apt-get", "sudo", "nvidia-smi"]}


class FakeSystem:
    def __init__(self, *, os_release: Optional[str] = UBUNTU_2404, proc_version: Optional[str] = PROC_NATIVE, meminfo: Optional[str] = MEM_16G,
                 environ: Optional[Dict[str, str]] = None, tools: Optional[Dict[str, str]] = None, present: Iterable[str] = (),
                 disks: Optional[Dict[str, Tuple[int, int]]] = None, python: Tuple[int, int, int] = (3, 12, 3), euid: int = 1000,
                 home: str = "/home/user", python_exe: str = "/usr/bin/python3", installed: Optional[Iterable[str]] = None,
                 failing_probes: Sequence[str] = (), smi: Optional[CommandResult] = CommandResult(0, SMI_4060),
                 dirs: Iterable[str] = (), unwritable: Iterable[str] = (), devices: Optional[Dict[str, int]] = None,
                 symlinks: Optional[Dict[str, str]] = None, lsblk: Optional[CommandResult] = None, listings: Optional[Dict[str, list]] = None):
        self.files = {"/etc/os-release": os_release, "/proc/version": proc_version, "/proc/meminfo": meminfo}
        self._environ = {"DISPLAY": ":0"} if environ is None else dict(environ)
        self.tools = dict(ALL_TOOLS) if tools is None else dict(tools)
        self.present: Set[str] = set(present)
        self.disks = {"/home/user": (500 * 2**30, 300 * 2**30)} if disks is None else dict(disks)
        self._python, self._euid, self._home, self._python_exe = python, euid, home, python_exe
        self.installed = set(ALL_PACKAGES if installed is None else installed)
        self.failing_probes = tuple(failing_probes)
        self.smi = smi
        self.dirs, self.unwritable = set(dirs), set(unwritable)
        self.devices, self.symlinks, self.lsblk, self.listings = dict(devices or {}), dict(symlinks or {}), lsblk, dict(listings or {})
        self.ran = []

    def read_text(self, path):
        return self.files.get(path)

    def run(self, argv, timeout=15.0):
        self.ran.append(tuple(argv))
        exe = os.path.basename(argv[0])
        if exe == "dpkg-query":
            asked = [a for a in argv[3:]]
            lines = ["%s %s" % (p, "installed" if p in self.installed else "not-installed") for p in asked]
            return CommandResult(0, "\n".join(lines) + "\n")
        if exe == "nvidia-smi":
            return self.smi
        if exe == "lsblk":
            return self.lsblk
        if argv[0] == self._python_exe and len(argv) >= 3 and argv[1] == "-c":
            return CommandResult(1 if any(f in argv[2] for f in self.failing_probes) else 0)
        return None

    def which(self, name):
        return self.tools.get(name)

    def environ(self):
        return dict(self._environ)

    def exists(self, path):
        return path in self.present or path in self.dirs

    def disk_free(self, path):
        return self.disks.get(path)

    def python_version(self):
        return self._python

    def python_executable(self):
        return self._python_exe

    def geteuid(self):
        return self._euid

    def home(self):
        return self._home

    def realpath(self, path):
        return self.symlinks.get(path, os.path.normpath(path))

    def is_dir(self, path):
        return path in self.dirs

    def writable(self, path):
        return path in self.dirs and path not in self.unwritable

    def device_of(self, path):
        return self.devices.get(path)

    def listdir(self, path):
        return self.listings.get(path)


def wsl2(**overrides):
    base = dict(proc_version=PROC_WSL2, environ={"DISPLAY": ":0", "WAYLAND_DISPLAY": "wayland-0", "WSL_DISTRO_NAME": "Ubuntu-24.04"},
                present={"/mnt/wslg", "/mnt/c"}, disks={"/home/user": (900 * 2**30, 700 * 2**30), "/mnt/c": (1000 * 2**30, 400 * 2**30)})
    base.update(overrides)
    return FakeSystem(**base)
