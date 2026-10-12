# SPDX-License-Identifier: GPL-3.0-or-later
"""The window's display choices (theme, accent colour, text size, scale), kept in one small file, only if the person says so.

The window has never written a file of its own, so the first change asks: "keep your choices in this file?". Yes means every later change is written (the person has agreed); No means the choices
last until the window is closed and nothing is written; the next launch asks again at the next change. The file is a few lines of JSON that only its owner can read, written atomically (a crash
leaves the old file or the new one), and the one it replaces is kept beside it as `.previous`. Nothing in it names a person, a project or a path. A damaged or unknown file is ignored, and a
field that is not one of the steps becomes the default for that choice, so a bad file can never make an odd window. Removing the file is its own action, listed first (`plan_forget`).
"""
from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

from .windowtheme import Look

SCHEMA = 1
MAX_BYTES = 4096                                   # a file of four short fields is a few dozen bytes: anything big is not ours


def previous_path(path: str) -> str:
    return str(path) + ".previous"


def load(path: str) -> Optional[Look]:
    """The saved choices, or None when there is no file or it is not a file of ours. Never raises."""
    try:
        if os.path.getsize(path) > MAX_BYTES:
            return None
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError, RecursionError):
        return None
    if not isinstance(data, dict) or data.get("schema") != SCHEMA:
        return None
    return Look(data.get("theme"), data.get("accent"), data.get("text_pt"), data.get("scale_pct")).normalised()      # type: ignore[arg-type]


def _write_atomic(path: Path, data: bytes) -> None:
    """A temporary file in the same folder, flushed to disk, owner-only, then moved into place: a crash leaves the old file or the new one, never half of one."""
    fd, temp = tempfile.mkstemp(dir=str(path.parent), prefix=".window-", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temp, 0o600)
        os.replace(temp, str(path))
    except BaseException:
        try:
            os.unlink(temp)
        except OSError:
            pass
        raise


def save(path: str, look: Look) -> None:
    """Write the choices. Owner-only, atomic, and the file it replaces is kept as `.previous`. Raises OSError when it cannot be written (the caller says so and keeps the choices for the session)."""
    target = Path(path)
    look = look.normalised()
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    body = (json.dumps({"schema": SCHEMA, "theme": look.theme, "accent": look.accent, "text_pt": look.text_pt, "scale_pct": look.scale_pct}, indent=2) + "\n").encode("utf-8")
    if target.is_file():
        old = target.read_bytes()
        if old == body:
            return                                  # nothing changed: nothing is written, and the kept copy is not overwritten with the same thing
        _write_atomic(Path(previous_path(path)), old)
    _write_atomic(target, body)


def plan_forget(path: str) -> Tuple[str, ...]:
    """The files that removing the choices would remove, for showing first: the file, and the older copy beside it."""
    return tuple(p for p in (str(path), previous_path(path)) if os.path.isfile(p) and not os.path.islink(p))


def forget(paths: Tuple[str, ...]) -> None:
    """Remove the files that were shown. Raises OSError when one cannot be removed."""
    for p in paths:
        try:
            os.unlink(p)
        except FileNotFoundError:
            pass


# ---------------------------------------------------------------- whether to write

@dataclass
class Keeper:
    """Whether changes are written. `kept`: the person said yes, or a file of theirs was already there. `undecided`: ask at the next change. `declined`: said no, so nothing is written until the window is closed."""
    state: str = "undecided"

    @classmethod
    def for_file(cls, path: str) -> "Keeper":
        return cls("kept" if load(path) is not None else "undecided")

    def on_change(self) -> str:
        """"write", "ask" or "nothing": what to do about a change the person just made."""
        return {"kept": "write", "undecided": "ask", "declined": "nothing"}[self.state]

    def said_yes(self) -> None:
        self.state = "kept"

    def said_no(self) -> None:
        self.state = "declined"

    def forgot(self) -> None:
        self.state = "undecided"
