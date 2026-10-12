# SPDX-License-Identifier: GPL-3.0-or-later
"""Show a folder in the computer's file manager (plan task VS-0.1: opening Windows programs from inside WSL). It only looks: nothing is written, moved or run except the file manager.

On WSL the file manager is Windows File Explorer, reached with `explorer.exe` and the folder's Windows name (`wslpath -w`); elsewhere `xdg-open`. Explorer reports a failure status even when
its window opens, so a program that could be started counts as success and nothing is read from it. Whether a window really appeared is on the device-test list.
"""
from __future__ import annotations

from typing import List, Tuple

from .system import System


def on_wsl(system: System) -> bool:
    return "microsoft" in (system.read_text("/proc/version") or "").lower()


def attempts(path: str, system: System) -> List[Tuple[str, ...]]:
    """The programs to try, in order. Empty when the path is not an absolute folder that exists, so nothing odd is ever handed to a program."""
    if not path.startswith("/") or "\x00" in path or "\n" in path or not system.is_dir(path):
        return []
    found: List[Tuple[str, ...]] = []
    if on_wsl(system) and system.which("explorer.exe") and system.which("wslpath"):
        named = system.run(["wslpath", "-w", path])
        windows_path = named.stdout.strip() if named is not None and named.returncode == 0 else ""
        if windows_path and "\n" not in windows_path:
            found.append(("explorer.exe", windows_path))
    if system.which("xdg-open"):
        found.append(("xdg-open", path))
    return found


def open_folder(path: str, system: System) -> bool:
    """True when a file manager could be started for the folder; False when there is none to try or none could be started. Starting a program goes through System (plan section 3)."""
    for argv in attempts(path, system):
        if system.start(argv):
            return True
    return False
