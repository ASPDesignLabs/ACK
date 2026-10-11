# SPDX-License-Identifier: GPL-3.0-or-later
"""python3 -m voice_studio.projects [list | show [name] | new | help]: projects from a terminal, until the window exists.

The terminal front of core/newproject.py and core/project.py (plan tasks VS-2.3 and VS-4.1). It makes nothing without a yes.
"""
from __future__ import annotations

import os
import sys
from typing import Optional, Sequence

from .core.paths import DataHome
from .core.projects_flow import run_projects
from .core.registry import load_registry
from .core.system import RealSystem
from .core.text import load_catalog
from .__main__ import TerminalIO


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    return run_projects(args, RealSystem(), DataHome(os.path.expanduser("~")), load_registry(), load_catalog("en"), TerminalIO())


if __name__ == "__main__":
    sys.exit(main())
