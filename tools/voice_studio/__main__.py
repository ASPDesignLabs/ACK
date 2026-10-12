# SPDX-License-Identifier: GPL-3.0-or-later
"""python3 -m voice_studio [--check] [--dry-run] [--yes] [--no-window]: the guided setup (plan decisions D3 and D5), one command that ends at the window.

Run by setup.sh. First the Ubuntu packages (the only step that needs administrator rights, core/setup_flow.py), then the two sets of programs and the window
(core/guided_flow.py). `--check` and `--dry-run` only look or show, and stop after the first step.
"""
from __future__ import annotations

import os
import sys
import time
from typing import Optional, Sequence

from .core import fetch, jobs
from .core.envspec import load_environments
from .core.guided_flow import run_guided
from .core.paths import DataHome
from .core.registry import load_registry
from .core.setup_flow import EXIT_OK, Options, parse_options, refuse_option, run_setup
from .core.system import RealSystem
from .core.text import load_catalog


class TerminalIO:
    def __init__(self) -> None:
        self.interactive = bool(sys.stdin and sys.stdin.isatty())

    def say(self, text: str) -> None:
        print(text, flush=True)

    def ask(self, prompt: str) -> Optional[str]:
        try:
            return input(prompt)
        except EOFError:
            return None


def run_apt(consent, argv, ids) -> int:
    """The password prompt belongs to sudo, in this terminal: the command inherits it, and nothing here reads it."""
    try:
        return fetch.run_networked(consent, argv, ids, inherit_stdio=True).returncode
    except fetch.FetchError:
        return 1


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    cat = load_catalog("en")
    io = TerminalIO()
    opts, unknown = parse_options(args)
    if opts is None:
        return refuse_option(unknown, cat, io)
    system = RealSystem()
    code = run_setup(opts, system, cat, io, run_apt)
    if code != EXIT_OK or opts.check or opts.dry_run:
        return code
    return run_guided(opts, system, DataHome(os.path.expanduser("~")), load_environments(), cat, io, fetch.run_networked, time.monotonic, load_registry(), str(jobs.TOOLS_DIR))


if __name__ == "__main__":
    sys.exit(main())
