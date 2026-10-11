# SPDX-License-Identifier: GPL-3.0-or-later
"""Asks whether GTK can be used without letting a missing GTK stop the program: the answer is data (core/windowcli.py Toolkit), so `--check` can explain it in plain words."""
from __future__ import annotations

import importlib

from ..core.windowcli import Toolkit


def toolkit() -> Toolkit:
    try:
        loaded = importlib.import_module("voice_studio.window.gtkload")
        loaded.need_display()
    except Exception as error:                               # gtkload raises its own WindowUnavailable while it is imported, so the class cannot be named here
        reason = getattr(error, "reason", "")
        if reason:
            return Toolkit(False, reason, getattr(error, "detail", ""))
        raise
    return Toolkit(True, version=loaded.version_text())
