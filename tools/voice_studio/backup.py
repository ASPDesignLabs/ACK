# SPDX-License-Identifier: GPL-3.0-or-later
"""python3 -m voice_studio.backup [now | list | verify | restore | help]: back up a project's recordings, notes and finished voices, from a terminal.

The terminal front of core/projectbackup.py (plan task VS-6.1). `now` and `restore` show what they will do and ask first; `list` and `verify` only look. A backup is always a new file in
a folder outside every project, read back in full before it counts, and no earlier backup is ever replaced or removed.
"""
from __future__ import annotations

import os
import sys
from typing import Optional, Sequence

from .__main__ import TerminalIO, reports_failures
from .core.backup_flow import run_backup
from .core.paths import DataHome
from .core.system import RealSystem
from .core.text import load_catalog


@reports_failures("backup")
def main(argv: Optional[Sequence[str]] = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    return run_backup(args, DataHome(os.path.expanduser("~")), load_catalog("en"), TerminalIO(), system=RealSystem())


if __name__ == "__main__":
    sys.exit(main())
