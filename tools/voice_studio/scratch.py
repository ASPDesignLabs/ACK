# SPDX-License-Identifier: GPL-3.0-or-later
"""python3 -m voice_studio.scratch [show | move | help]: say where a project's scratch is, and move it to another place.

The terminal front of core/scratchmove.py (plan task VS-6.5). `show` only looks. `move` copies the scratch, checks the copy, and switches the project to it only then; the old place is
never touched without a second question.
"""
from __future__ import annotations

import os
import sys
from typing import Optional, Sequence

from .__main__ import TerminalIO, reports_failures
from .core.paths import DataHome
from .core.scratchmove_flow import run_scratch
from .core.system import RealSystem
from .core.text import load_catalog


@reports_failures("scratch")
def main(argv: Optional[Sequence[str]] = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    return run_scratch(args, RealSystem(), DataHome(os.path.expanduser("~")), load_catalog("en"), TerminalIO())


if __name__ == "__main__":
    sys.exit(main())
