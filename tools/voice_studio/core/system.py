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
from typing import Mapping, Optional, Protocol, Sequence, Tuple


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str = ""
    stderr: str = ""


class System(Protocol):
    def read_text(self, path: str) -> Optional[str]: ...
    def run(self, argv: Sequence[str], timeout: float = 15.0) -> Optional[CommandResult]: ...   # None: could not run it at all
    def which(self, name: str) -> Optional[str]: ...
    def environ(self) -> Mapping[str, str]: ...
    def exists(self, path: str) -> bool: ...
    def disk_free(self, path: str) -> Optional[Tuple[int, int]]: ...      # (total bytes, free bytes), None if it cannot be read
    def python_version(self) -> Tuple[int, int, int]: ...
    def python_executable(self) -> str: ...
    def geteuid(self) -> int: ...
    def home(self) -> str: ...


class RealSystem:
    """The real computer. Output is requested in the C locale so the parsers see one format whatever language the computer speaks."""

    def read_text(self, path: str) -> Optional[str]:
        try:
            return Path(path).read_text(encoding="utf-8", errors="replace")
        except OSError:
            return None

    def run(self, argv: Sequence[str], timeout: float = 15.0) -> Optional[CommandResult]:
        env = dict(os.environ, LC_ALL="C", LANG="C")
        try:
            done = subprocess.run(list(argv), capture_output=True, text=True, errors="replace", timeout=timeout, env=env, stdin=subprocess.DEVNULL)
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
        return sys.executable or "python3"

    def geteuid(self) -> int:
        return os.geteuid() if hasattr(os, "geteuid") else 1000

    def home(self) -> str:
        return str(Path.home())
