# SPDX-License-Identifier: GPL-3.0-or-later
"""python3 -m voice_studio.uninstall [show | remove | help]: take the tool's programs and downloaded files off the disk.

The terminal front of core/uninstall.py (plan task VS-6.3). It never touches a project, a recording, a round, a finished voice, a backup or the starting voices; `show` only looks and `remove`
shows the same list and asks first.
"""
from __future__ import annotations

import os
import sys
from typing import Optional, Sequence

from .__main__ import TerminalIO
from .core.envspec import load_environments
from .core.paths import DataHome
from .core.text import load_catalog
from .core.uninstall_flow import run_uninstall


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    tools_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))          # the folder that holds the voice_studio package: what PYTHONPATH points at
    return run_uninstall(args, DataHome(os.path.expanduser("~")), load_catalog("en"), TerminalIO(), specs=load_environments(), tools_dir=tools_dir)


if __name__ == "__main__":
    sys.exit(main())
