# SPDX-License-Identifier: GPL-3.0-or-later
"""The launcher entry that puts the window in the desktop's menu (on WSL: the Windows Start menu), written only when the person asks, after being shown exactly what will be written.

Two small text files in the person's own folders, nothing in system folders and no administrator rights: a `.desktop` entry in `~/.local/share/applications` and the icon in
`~/.local/share/icons`. A file is only ever replaced or removed when it carries this tool's marker line (so a file of the same name that someone else made is never touched), and a
replaced one is kept beside it as `.previous`. The entry runs the window with the same Python that installed it, the system one that has GTK, with the tool's folder on PYTHONPATH.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Optional

APP_ID = "org.aspdesignlabs.AckVoiceStudio"
MARKER = "X-ACK-Voice-Studio-Launcher=1"
SAFE_PATH = re.compile(r"^/[A-Za-z0-9_./+@:,=~-]+$")           # no space or symbol that the Desktop Entry format would need quoting rules for
STATES = ("new", "same", "update", "foreign")                   # foreign: a file of that name is there and is not ours


class LauncherError(Exception):
    def __init__(self, code: str, detail: str = ""):
        super().__init__(code + (": " + detail if detail else ""))
        self.code = code
        self.detail = detail


ERROR_CODES = ("odd_path", "foreign_file", "write_failed")      # each has words in the text catalog


def desktop_path(home: str) -> str:
    return "%s/.local/share/applications/%s.desktop" % (home.rstrip("/"), APP_ID)


def icon_path(home: str) -> str:
    return "%s/.local/share/icons/hicolor/scalable/apps/%s.svg" % (home.rstrip("/"), APP_ID)


def desktop_text(python: str, tools_dir: str, name: str, comment: str) -> str:
    """The entry. Paths with a space or a symbol are refused rather than quoted: a wrong quote would start the wrong program."""
    for path in (python, tools_dir):
        if not SAFE_PATH.match(path):
            raise LauncherError("odd_path", path)
    for words in (name, comment):
        if "\n" in words or "\r" in words:
            raise LauncherError("odd_path", "text")
    return "\n".join([
        "[Desktop Entry]",
        "Type=Application",
        "Name=" + name,
        "Comment=" + comment,
        "Exec=env PYTHONPATH=%s %s -m voice_studio.window" % (tools_dir, python),
        "Icon=" + APP_ID,
        "Terminal=false",
        "Categories=Utility;AudioVideo;",
        "StartupWMClass=" + APP_ID,
        MARKER,
        ""])


@dataclass(frozen=True)
class Target:
    path: str
    text: str
    state: str                    # one of STATES
    previous: str                 # what is there now (empty when new)


@dataclass(frozen=True)
class LauncherPlan:
    entry: Target
    icon: Target

    @property
    def targets(self):
        return (self.entry, self.icon)

    @property
    def changes(self) -> bool:
        return any(t.state in ("new", "update") for t in self.targets)

    @property
    def refused(self) -> bool:
        return any(t.state == "foreign" for t in self.targets)


def _read(path: str) -> Optional[str]:
    try:
        with open(path, encoding="utf-8") as handle:
            return handle.read()
    except FileNotFoundError:
        return None
    except (OSError, UnicodeDecodeError):
        return ""                                               # there, but not readable as ours: treated as foreign


def _target(path: str, text: str) -> Target:
    now = _read(path)
    if now is None:
        return Target(path, text, "new", "")
    if now == text:
        return Target(path, text, "same", now)
    if MARKER in now or (path.endswith(".svg") and "ack-voice-studio-icon" in now):
        return Target(path, text, "update", now)
    return Target(path, text, "foreign", now)


def plan_install(home: str, python: str, tools_dir: str, name: str, comment: str, icon_text: str) -> LauncherPlan:
    return LauncherPlan(_target(desktop_path(home), desktop_text(python, tools_dir, name, comment)), _target(icon_path(home), icon_text))


def _write(path: str, text: str) -> None:
    folder = os.path.dirname(path)
    os.makedirs(folder, mode=0o755, exist_ok=True)
    part = path + ".part"
    with open(part, "w", encoding="utf-8") as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(part, path)


def install(plan: LauncherPlan) -> None:
    """Write what the plan says, nothing if any file in it is not ours. A file of ours that is replaced is kept as `.previous`."""
    if plan.refused:
        raise LauncherError("foreign_file", next(t.path for t in plan.targets if t.state == "foreign"))
    try:
        for target in plan.targets:
            if target.state == "update":
                _write(target.path + ".previous", target.previous)
            if target.state in ("new", "update"):
                _write(target.path, target.text)
    except OSError as error:
        raise LauncherError("write_failed", error.strerror or type(error).__name__)


@dataclass(frozen=True)
class RemovalPlan:
    paths: tuple                  # files that are ours and are there
    foreign: tuple                # files of the same names that are not ours: left alone


def plan_remove(home: str) -> RemovalPlan:
    ours, foreign = [], []
    for path in (desktop_path(home), icon_path(home)):
        now = _read(path)
        if now is None:
            continue
        (ours if (MARKER in now or "ack-voice-studio-icon" in now) else foreign).append(path)
    return RemovalPlan(tuple(ours), tuple(foreign))


def remove(plan: RemovalPlan) -> None:
    """Remove the files that are ours; the `.previous` copies stay (nothing is deleted that the person did not see listed)."""
    try:
        for path in plan.paths:
            os.unlink(path)
    except OSError as error:
        raise LauncherError("write_failed", error.strerror or type(error).__name__)
