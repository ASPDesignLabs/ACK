# SPDX-License-Identifier: GPL-3.0-or-later
"""python3 -m voice_studio.report [show | save --to FILE | help]: a problem report a helper can read, shown in full first and saved only where you say.

The terminal front of core/reportcmd_flow.py (plan task VS-6.4). It reads the computer and the tool's own files, changes nothing but the one file `save` is told to write, and
sends nothing anywhere. A failed command ends with a line that points here.
"""
from __future__ import annotations

import os
import sys
from typing import Optional, Sequence

from .__main__ import TerminalIO
from .core.paths import DataHome
from .core.reportcmd_flow import run_report
from .core.system import RealSystem
from .core.text import load_catalog


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    return run_report(args, DataHome(os.path.expanduser("~")), load_catalog("en"), TerminalIO(), system=RealSystem())


if __name__ == "__main__":
    sys.exit(main())
