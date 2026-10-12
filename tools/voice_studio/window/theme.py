# SPDX-License-Identifier: GPL-3.0-or-later
"""Loads the window's look into GTK (the style sheet and the settings that go with it), and keeps the person's display choices.

The decisions are in core/windowtheme.py (the colours, the steps, the text of the style sheet) and core/windowprefs.py (the small file); this file only hands GTK what they made. In the ACK theme the
dark variant of GTK's own theme is asked for, so the parts the sheet does not paint (a scroll bar's arrows, an icon) match it; in the system theme that setting is put back as it was found.
"""
from __future__ import annotations

from typing import Callable, List, Optional

from ..core import windowprefs as wp
from ..core import windowtheme as wt
from . import sizing
from .gtkload import Gdk, Gtk


class Appearance:
    def __init__(self, path: str, look: wt.Look, keeper: wp.Keeper):
        self.path = path
        self.look = look.normalised()
        self.applied: Optional[wt.Look] = None      # the look the window is showing now (the headless tour checks a change reaches it whatever becomes of the file)
        self.keeper = keeper
        self.errors: List[str] = []                 # what GTK did not understand in the sheet: [] when all is in order (the headless tour checks)
        self.provider = Gtk.CssProvider()
        self.provider.connect("parsing-error", self._parsing_error)
        self._listeners: List[Callable[[], None]] = []
        self._added = False
        self._system_dark = Gtk.Settings.get_default().get_property("gtk-application-prefer-dark-theme")

    @classmethod
    def load(cls, path: str) -> "Appearance":
        return cls(path, wp.load(path) or wt.Look(), wp.Keeper.for_file(path))

    def _parsing_error(self, _provider: Gtk.CssProvider, section: object, error: object) -> None:
        self.errors.append(str(getattr(error, "message", error)))

    def listen(self, callback: Callable[[], None]) -> None:
        self._listeners.append(callback)

    def apply(self) -> None:
        """Make the window look the way `self.look` says."""
        self.errors.clear()
        text = wt.css_for(self.look)
        self.provider.load_from_data(text.encode("utf-8"))                # bytes: the one form both GTK 4.6 and 4.14 accept (checked on both)
        display = Gdk.Display.get_default()
        if not self._added:
            Gtk.StyleContext.add_provider_for_display(display, self.provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
            self._added = True
        settings = Gtk.Settings.get_default()
        settings.set_property("gtk-application-prefer-dark-theme", True if self.look.theme == "ack" else self._system_dark)
        settings.set_property("gtk-enable-animations", False)
        settings.set_property("gtk-enable-event-sounds", False)
        settings.set_property("gtk-enable-input-feedback-sounds", False)
        sizing.set_scale(self.look.scale_pct)
        self.applied = self.look
        for callback in list(self._listeners):
            callback()

    def change(self, look: wt.Look) -> str:
        """Show a new look now, and say what to do about keeping it: "saved" (written, the person had said yes), "ask" (the first change: the window asks), "session" (the person said no), or
        "failed" (it could not be written; it lasts until the window is closed). The look is shown in every case."""
        self.look = look.normalised()
        self.apply()
        action = self.keeper.on_change()
        if action == "write":
            return self.save()
        return "ask" if action == "ask" else "session"

    def save(self) -> str:
        try:
            wp.save(self.path, self.look)
        except OSError:
            return "failed"
        return "saved"
