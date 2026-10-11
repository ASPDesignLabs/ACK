# SPDX-License-Identifier: GPL-3.0-or-later
"""python3 -m voice_studio.window [--check | --install-launcher | --remove-launcher]: the window. Needs the system Python (the one with Ubuntu's python3-gi), not a virtual environment."""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional, Sequence

from ..__main__ import TerminalIO
from ..core import jobs, windowmodel as wm
from ..core.registry import load_registry
from ..core.paths import DataHome
from ..core.text import load_catalog
from ..core.windowcli import run_window_cli
from ..rounds import training_environment
from .probe import toolkit

ICON = Path(__file__).resolve().parent.parent / "data" / "icons" / "org.aspdesignlabs.AckVoiceStudio.svg"


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    home_dir = os.path.expanduser("~")
    home, registry, cat = DataHome(home_dir), load_registry(), load_catalog("en")
    services = wm.real_services(home, registry, cat, training_environment(home, registry))

    def start() -> int:
        from . import app
        return app.run(services)

    def selftest() -> int:
        from . import selftest as tour
        return tour.run(services)

    return run_window_cli(args, home_dir, sys.executable, str(jobs.TOOLS_DIR), ICON.read_text(encoding="utf-8"), cat, TerminalIO(), toolkit=toolkit, start=start, selftest=selftest)


if __name__ == "__main__":
    sys.exit(main())
