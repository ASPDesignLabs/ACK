# SPDX-License-Identifier: GPL-3.0-or-later
"""python3 -m voice_studio [--check] [--dry-run] [--yes]: the terminal step of the guided setup (plan decision D5).

Run by setup.sh. The window itself arrives in a later stage; until then this is all it does.
"""
from __future__ import annotations

import sys
from typing import Optional, Sequence

from .core import fetch
from .core.setup_flow import Options, parse_options, refuse_option, run_setup
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
    return run_setup(opts, RealSystem(), cat, io, run_apt)


if __name__ == "__main__":
    sys.exit(main())
