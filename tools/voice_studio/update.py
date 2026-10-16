# SPDX-License-Identifier: GPL-3.0-or-later
"""python3 -m voice_studio.update [check | get RELEASE | help]: look for newer releases of ACK Voice Studio, and fetch one into a new folder beside this copy.

The terminal front of core/update.py (plan task VS-6.2). It contacts github.com only when the person runs it and says yes, shows the exact commands first, and never touches the copy it is
running from: the new copy goes in a new folder, and the commands for trying it and for using it under the usual name are printed for the person to type.
"""
from __future__ import annotations

import os
import sys
from typing import Optional, Sequence

from . import __version__
from .__main__ import TerminalIO, reports_failures
from .core import fetch
from .core.registry import load_release_source
from .core.system import RealSystem
from .core.text import load_catalog
from .core.update_flow import run_update


@reports_failures("update")
def main(argv: Optional[Sequence[str]] = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    tools_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))          # the folder that holds the voice_studio package: what PYTHONPATH points at
    return run_update(args, load_catalog("en"), TerminalIO(), system=RealSystem(), source=load_release_source(), networked=fetch.run_networked, tools_dir=tools_dir, version=__version__)


if __name__ == "__main__":
    sys.exit(main())
