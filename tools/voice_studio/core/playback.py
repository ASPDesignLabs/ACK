# SPDX-License-Identifier: GPL-3.0-or-later
"""Playing a short sound file on this computer (plan task VS-5.4).

Nothing about sound has been seen working from this tool on a real computer yet (plan task VS-0.1 still lists "playing a .wav" under WSLg as unchecked), so this does not pick a
player and hope: it tries the ways a computer may be able to play a file, in an order, keeps the one that works for the rest of the clips, and reports what it tried.

* On a native Ubuntu desktop: `pw-play`, `paplay`, `ffplay`, then `aplay`, whichever of them is installed.
* Under WSL: `ffplay` and `paplay` reach WSLg's sound; if they cannot, Windows' own player is asked to play the file (`powershell.exe` and `System.Media.SoundPlayer`, through the
  Windows path of the file that `wslpath` gives), which needs Ubuntu to be able to start Windows programs (plan finding F4: that is intermittent).

A player that exits with a success code has run; it does not prove sound came out of a speaker, so the caller asks the person. A player that prints that it has no audio device is counted
as failed. This module starts programs only through the `System` it is given (so tests can hand it a fake) and never uses the network.
"""
from __future__ import annotations

import base64
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from .system import System

NATIVE_ORDER = ("pw-play", "paplay", "ffplay", "aplay")
WSL_ORDER = ("ffplay", "paplay", "windows", "aplay")
EXTRA_SECONDS = 20.0                     # how long a player may take beyond the clip's own length (starting the sound system can be slow)
WINDOWS_PATH = re.compile(r"^(?:[A-Za-z]:\\|\\\\)[^'\"`$\r\n\0]+\Z")      # no quote, dollar or back-tick: the path goes inside a quoted PowerShell string
NO_AUDIO_HINTS = ("could not initialize sdl", "no such audio device", "audio open failed", "failed to open audio", "connection refused", "no audio", "pulseaudio: unable",
                  "cannot open audio device", "host is down")


def is_wsl(system: System) -> bool:
    return "microsoft" in (system.read_text("/proc/version") or "").lower()


@dataclass
class Playback:
    """Plays clips one after another. `worked` is the way that played the last clip; `failed` is every way that did not, in the order they were tried."""

    system: System
    worked: Optional[str] = None
    failed: List[str] = field(default_factory=list)

    def order(self) -> Tuple[str, ...]:
        base = WSL_ORDER if is_wsl(self.system) else NATIVE_ORDER
        if self.worked in base:
            return (self.worked,) + tuple(n for n in base if n != self.worked)
        return base

    def argv(self, name: str, path: str) -> Optional[Tuple[str, ...]]:
        """The command for one way of playing, or None when this computer cannot do it that way."""
        if name == "windows":
            return self._windows(path)
        program = self.system.which(name)
        if not program:
            return None
        if name == "ffplay":
            return (program, "-nodisp", "-autoexit", "-loglevel", "error", "-i", path)
        if name == "aplay":
            return (program, "-q", path)
        return (program, path)                                           # pw-play and paplay take the file alone

    def _windows(self, path: str) -> Optional[Tuple[str, ...]]:
        powershell, convert = self.system.which("powershell.exe"), self.system.which("wslpath")
        if not powershell or not convert or not is_wsl(self.system):
            return None
        done = self.system.run([convert, "-w", path], timeout=10.0)
        windows_path = done.stdout.strip() if done is not None and done.returncode == 0 else ""
        if not WINDOWS_PATH.match(windows_path):
            return None
        script = "$p = '%s'; (New-Object System.Media.SoundPlayer $p).PlaySync()" % windows_path
        encoded = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
        return (powershell, "-NoLogo", "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded)

    def play(self, path: str, seconds: float) -> Optional[str]:
        """Play one file. The name of the way that ran it to the end, or None when none could. A way that failed is not tried again for later clips."""
        for name in self.order():
            if name in self.failed:
                continue
            command = self.argv(name, path)
            if command is None:
                continue
            done = self.system.run(command, timeout=max(seconds, 0.0) + EXTRA_SECONDS)
            said = ((done.stderr + " " + done.stdout).lower() if done is not None else "")
            if done is not None and done.returncode == 0 and not any(hint in said for hint in NO_AUDIO_HINTS):
                self.worked = name
                return name
            self.failed.append(name)
        return None

    def tried(self) -> Tuple[str, ...]:
        return tuple(self.failed)
