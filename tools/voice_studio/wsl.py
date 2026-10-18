# SPDX-License-Identifier: GPL-3.0-or-later
"""python3 -m voice_studio.wsl [check | phone | idle | help]: help for the Windows side of Ubuntu under WSL, from a terminal.

The terminal front of core/wsl.py (plan task VS-3.6). `check` only looks. `phone` and `idle` show the one change they want to make to the Windows file `.wslconfig`, ask first and keep the
file as it was under a new name. The firewall command and the restart are printed for the person to run; this program never runs them.
"""
from __future__ import annotations

import os
import sys
from typing import Optional, Sequence

from .__main__ import TerminalIO, reports_failures
from .core.paths import DataHome
from .core.system import RealSystem
from .core.text import load_catalog
from .core.wsl_flow import run_wsl


@reports_failures("wsl")
def main(argv: Optional[Sequence[str]] = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    return run_wsl(args, DataHome(os.path.expanduser("~")), load_catalog("en"), TerminalIO(), system=RealSystem())


if __name__ == "__main__":
    sys.exit(main())
