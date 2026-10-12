# SPDX-License-Identifier: GPL-3.0-or-later
"""python3 -m voice_studio.rounds [list | start | stop | choose | back | note | keep | free | help]: training rounds from a terminal, until the window exists.

The terminal front of core/rounds.py (plan task VS-4.2). `list` and `keep` only look, and `free` only looks until it is told which rounds to free (then it shows what it will remove and asks first). `start`, `stop`, `choose`, `back`
and `note` show what they will do and ask first.
A round runs as a job of its own: closing the terminal does not stop it.
"""
from __future__ import annotations

import os
import sys
from typing import Callable, Optional, Sequence, Tuple

from .core import envfind
from .core.envbuild import EnvPaths
from .core.paths import DataHome
from .core.registry import Registry, load_registry
from .core.rounds_flow import run_rounds
from .core.system import RealSystem
from .core.text import load_catalog
from .__main__ import TerminalIO


def training_environment(home: DataHome, registry: Registry) -> Callable[[], Tuple[Optional[EnvPaths], str]]:
    """The training programs, if they are built and in order: (their places, "ready"), or (None, why not). Looks only; builds nothing."""
    return envfind.resolver("training", home, registry, RealSystem())


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    home, registry = DataHome(os.path.expanduser("~")), load_registry()
    return run_rounds(args, home, registry, load_catalog("en"), TerminalIO(), training=training_environment(home, registry), system=RealSystem())


if __name__ == "__main__":
    sys.exit(main())
