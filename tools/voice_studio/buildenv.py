# SPDX-License-Identifier: GPL-3.0-or-later
"""python3 -m voice_studio.buildenv [training|studio] [--check] [--yes] [--verbose]: set up one set of programs from a terminal.

The terminal front of the environment builder, for use until the window exists (plan task VS-0.2). It asks once before it downloads anything.
"""
from __future__ import annotations

import os
import sys
import time
from typing import Optional, Sequence

from .core import fetch
from .core.buildenv_flow import parse_build_options, refuse_build_option, run_build_env
from .core.envspec import load_environments
from .core.paths import DataHome
from .core.registry import load_registry
from .core.system import RealSystem
from .core.text import load_catalog
from .__main__ import TerminalIO


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    cat = load_catalog("en")
    io = TerminalIO()
    opts, unknown = parse_build_options(args)
    if opts is None:
        return refuse_build_option(unknown, cat, io)
    return run_build_env(opts, RealSystem(), DataHome(os.path.expanduser("~")), load_environments(), cat, io, fetch.run_networked, time.monotonic, load_registry())


if __name__ == "__main__":
    sys.exit(main())
