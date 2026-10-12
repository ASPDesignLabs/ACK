# SPDX-License-Identifier: GPL-3.0-or-later
"""python3 -m voice_studio.recordings [show | import | finish | set | help]: a project's recordings from a terminal.

The terminal front of core/recordings.py (plan task VS-2.10); the window runs the same flows. `show` only looks. `import` brings in an ACK package, a folder of audio files with a
text file each, a folder of audio files with one table, or a folder of audio files alone; it shows what it found and asks before it adds anything. `finish` lets the computer
listen to the recordings that are waiting, as a job of its own: closing the terminal does not stop it. `set` makes a training set from the recordings that are ready (`--preview`
only shows what it would hold). Everything that changes something shows what it will do and asks first.
"""
from __future__ import annotations

import os
import sys
from typing import Optional, Sequence

from .core import envfind
from .core.paths import DataHome
from .core.recordings_flow import run_recordings
from .core.registry import load_registry
from .core.system import RealSystem
from .core.text import load_catalog
from .__main__ import TerminalIO


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    home, registry = DataHome(os.path.expanduser("~")), load_registry()
    return run_recordings(args, home, registry, load_catalog("en"), TerminalIO(), studio=envfind.resolver("studio", home, registry, RealSystem()), system=RealSystem())


if __name__ == "__main__":
    sys.exit(main())
