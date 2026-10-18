# SPDX-License-Identifier: GPL-3.0-or-later
"""python3 -m voice_studio.refresh [check | repair | rebuild | older | help]: look at the tool's own programs, downloads and notes, mend what is broken, build a fresh copy.

The terminal front of core/refresh.py (plan task VS-6.6). Like a reinstall that does not wipe data: it never touches a project, a recording, a round, a finished voice or a backup, and every
change is shown and asked first.
"""
from __future__ import annotations

import os
import sys
import time
from typing import Optional, Sequence

from .__main__ import TerminalIO, reports_failures
from .core import fetch
from .core.envspec import load_environments
from .core.paths import DataHome
from .core.refresh_flow import run_refresh
from .core.registry import load_registry
from .core.system import RealSystem
from .core.text import load_catalog


@reports_failures("refresh")
def main(argv: Optional[Sequence[str]] = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    return run_refresh(args, DataHome(os.path.expanduser("~")), load_catalog("en"), TerminalIO(), system=RealSystem(), registry=load_registry(), specs=load_environments(),
                       networked=fetch.run_networked, clock=time.monotonic)


if __name__ == "__main__":
    sys.exit(main())
