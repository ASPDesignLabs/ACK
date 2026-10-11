# SPDX-License-Identifier: GPL-3.0-or-later
"""The edge between the decisions and the computer: how facts are read.

Preflight and the tasks after it ask a `System` instead of calling the operating system, so a test can hand them a fake built from captured
output. Reading facts never uses the network: the commands run are local ones (nvidia-smi, dpkg-query, the Python itself).
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping, Optional, Protocol, Sequence, Tuple


# Programs that can reach the network. `System.run` refuses them: the only code allowed to start one is core/fetch.py, and only after
# the person has agreed to that download by name (plan decisions D5, D27; tests/test_vs_network_rules.py).
NETWORK_PROGRAMS = frozenset({"curl", "wget", "git", "pip", "pip3", "apt", "apt-get", "aptitude", "snap", "flatpak", "ssh", "scp", "sftp",
                              "rsync", "nc", "ncat", "netcat", "ftp", "telnet"})
WRAPPER_PROGRAMS = frozenset({"sudo", "env", "nice", "nohup", "time", "timeout", "ionice", "stdbuf", "setsid"})


class NetworkBlocked(RuntimeError):
    """A command that can reach the network was asked for outside the download module."""


def real_interpreter(executable: str, minor: Tuple[int, int], prefix: str, base_prefix: str, base_exec_prefix: str, *,
                     is_usable: Callable[[str], bool] = lambda p: os.path.isfile(p) and os.access(p, os.X_OK), resolve: Callable[[str], str] = os.path.realpath) -> str:
    """The interpreter a Python environment should be built from: the real one, never the Python of a virtual environment.

    On Python 3.10 (Ubuntu 22.04's) an environment made while another is active is linked to the *other* environment's Python, not to the system's, and it
    stops working the day the other one is removed or rebuilt (found on a real computer: a training environment linked into a folder that was later deleted).
    So when this program is itself running inside a virtual environment, the real interpreter is named from where it lives: `<base prefix>/bin/python3.X`.
    Outside a virtual environment the running interpreter already is the real one."""
    executable = executable or "python3"
    if prefix == base_prefix:
        return executable
    named = os.path.join(base_exec_prefix, "bin", "python%d.%d" % minor)
    if is_usable(named):
        return named
    resolved = resolve(executable)
    if is_usable(resolved) and not os.path.isfile(os.path.join(os.path.dirname(os.path.dirname(resolved)), "pyvenv.cfg")):
        return resolved
    return executable


def is_network_command(argv: Sequence[str]) -> bool:
    """Best effort: the program itself, behind any wrappers (sudo, env, timeout...), or `python -m pip`. The static checks are the main guard."""
    names = [os.path.basename(a) for a in argv]
    i = 0
    while i < len(names) and names[i] in WRAPPER_PROGRAMS:
        i += 1
        while i < len(names) and (names[i].startswith("-") or "=" in names[i] or names[i].isdigit()):
            i += 1
    if i >= len(names):
        return False
    if names[i] in NETWORK_PROGRAMS:
        return True
    return names[i].startswith("python") and names[i + 1:i + 3] == ["-m", "pip"]


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str = ""
    stderr: str = ""


class System(Protocol):
    def read_text(self, path: str) -> Optional[str]: ...
    def run(self, argv: Sequence[str], timeout: float = 15.0, cwd: Optional[str] = None,
            env: Optional[Mapping[str, str]] = None) -> Optional[CommandResult]: ...         # None: could not run it at all; `env` adds to the usual
    def which(self, name: str) -> Optional[str]: ...
    def environ(self) -> Mapping[str, str]: ...
    def exists(self, path: str) -> bool: ...
    def disk_free(self, path: str) -> Optional[Tuple[int, int]]: ...      # (total bytes, free bytes), None if it cannot be read
    def python_version(self) -> Tuple[int, int, int]: ...
    def python_executable(self) -> str: ...
    def geteuid(self) -> int: ...
    def home(self) -> str: ...
    def realpath(self, path: str) -> str: ...                 # symbolic links resolved; works for a path that does not exist yet
    def is_dir(self, path: str) -> bool: ...
    def writable(self, path: str) -> bool: ...
    def device_of(self, path: str) -> Optional[int]: ...      # which filesystem a path is on (st_dev); None if it does not exist
    def listdir(self, path: str) -> Optional[list]: ...       # names in a folder; None if it cannot be read
    def hostname(self) -> str: ...


class RealSystem:
    """The real computer. Output is requested in the C locale so the parsers see one format whatever language the computer speaks."""

    def read_text(self, path: str) -> Optional[str]:
        try:
            return Path(path).read_text(encoding="utf-8", errors="replace")
        except OSError:
            return None

    def run(self, argv: Sequence[str], timeout: float = 15.0, cwd: Optional[str] = None,
            env: Optional[Mapping[str, str]] = None) -> Optional[CommandResult]:
        if is_network_command(argv):
            raise NetworkBlocked(os.path.basename(argv[0]))
        full_env = dict(os.environ, LC_ALL="C", LANG="C")
        full_env.update(env or {})
        try:
            done = subprocess.run(list(argv), capture_output=True, text=True, errors="replace", timeout=timeout, env=full_env, cwd=cwd,
                                  stdin=subprocess.DEVNULL)
        except (OSError, subprocess.SubprocessError):
            return None
        return CommandResult(done.returncode, done.stdout, done.stderr)

    def which(self, name: str) -> Optional[str]:
        return shutil.which(name)

    def environ(self) -> Mapping[str, str]:
        return dict(os.environ)

    def exists(self, path: str) -> bool:
        return os.path.exists(path)

    def disk_free(self, path: str) -> Optional[Tuple[int, int]]:
        try:
            usage = shutil.disk_usage(path)
        except OSError:
            return None
        return usage.total, usage.free

    def python_version(self) -> Tuple[int, int, int]:
        return tuple(sys.version_info[:3])  # type: ignore[return-value]

    def python_executable(self) -> str:
        return real_interpreter(sys.executable, tuple(sys.version_info[:2]), sys.prefix, sys.base_prefix, sys.base_exec_prefix)    # type: ignore[arg-type]

    def geteuid(self) -> int:
        return os.geteuid() if hasattr(os, "geteuid") else 1000

    def home(self) -> str:
        return str(Path.home())

    def realpath(self, path: str) -> str:
        return os.path.realpath(path)

    def is_dir(self, path: str) -> bool:
        return os.path.isdir(path)

    def writable(self, path: str) -> bool:
        return os.access(path, os.W_OK)

    def device_of(self, path: str) -> Optional[int]:
        try:
            return os.stat(path).st_dev
        except OSError:
            return None

    def listdir(self, path: str) -> Optional[list]:
        try:
            return os.listdir(path)
        except OSError:
            return None

    def hostname(self) -> str:
        return os.uname().nodename if hasattr(os, "uname") else ""
