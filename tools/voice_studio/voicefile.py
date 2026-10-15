# SPDX-License-Identifier: GPL-3.0-or-later
"""python3 -m voice_studio.voicefile [make | list | listen | help]: make the voice file for ACK from the chosen training round, and hear it, from a terminal, until the window exists.

The terminal front of core/voicefile.py (plan task VS-5.2). `make` does the whole of checklist section J in one go: it shows what it will do, checks the room, asks first,
and writes only into one new folder under the project's `exports`. `list` only looks.
"""
from __future__ import annotations

import os
import sys
from typing import Optional, Sequence

from .__main__ import TerminalIO
from .core import envfind
from .core.paths import DataHome
from .core.registry import load_registry
from .core.system import RealSystem
from .core.text import load_catalog
from .core.voicefile_flow import run_voicefile
from .rounds import training_environment


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    home, registry = DataHome(os.path.expanduser("~")), load_registry()
    return run_voicefile(args, home, registry, load_catalog("en"), TerminalIO(), training=training_environment(home, registry), system=RealSystem(),
                         studio=envfind.resolver("studio", home, registry, RealSystem()))


if __name__ == "__main__":
    sys.exit(main())
