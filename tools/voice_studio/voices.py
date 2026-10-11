# SPDX-License-Identifier: GPL-3.0-or-later
"""python3 -m voice_studio.voices [list | show voice | choose voice | get voice | help]: starting voices from a terminal, until the window exists.

The terminal front of core/startvoice.py (plan task VS-4.1). `get` shows where a voice comes from, asks for the acknowledgment and the agreement to the download as
two separate things, and only then downloads. Nothing reaches the network before both.
"""
from __future__ import annotations

import os
import sys
import time
from typing import Optional, Sequence

from .core.paths import DataHome
from .core.registry import load_registry
from .core.text import load_catalog
from .core.voices_flow import run_voices
from .__main__ import TerminalIO


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    return run_voices(args, DataHome(os.path.expanduser("~")), load_registry(), load_catalog("en"), TerminalIO(), sleep=time.sleep, clock=time.monotonic)


if __name__ == "__main__":
    sys.exit(main())
