# SPDX-License-Identifier: GPL-3.0-or-later
"""Loads GTK 4 or says, in a code the text catalog has words for, why it cannot (plan P7: no desktop means a plain sentence and a stop, never a crash or a browser)."""
from __future__ import annotations

REASONS = ("no_gi", "no_gtk4", "gtk_too_old", "no_display")        # each has words in the text catalog
MIN_MINOR = 6                                                       # GTK 4.6 is the floor (Ubuntu 22.04): see the package's docstring


class WindowUnavailable(Exception):
    def __init__(self, reason: str, detail: str = ""):
        super().__init__(reason + (": " + detail if detail else ""))
        self.reason = reason
        self.detail = detail


try:
    import gi
except ImportError as error:
    raise WindowUnavailable("no_gi", str(error))
try:
    gi.require_version("Gtk", "4.0")
    gi.require_version("Gdk", "4.0")
    from gi.repository import Gdk, Gio, GLib, Gtk, Pango
except (ValueError, ImportError) as error:
    raise WindowUnavailable("no_gtk4", str(error))
if Gtk.get_major_version() != 4 or Gtk.get_minor_version() < MIN_MINOR:
    raise WindowUnavailable("gtk_too_old", "%d.%d" % (Gtk.get_major_version(), Gtk.get_minor_version()))


def version_text() -> str:
    return "%d.%d.%d" % (Gtk.get_major_version(), Gtk.get_minor_version(), Gtk.get_micro_version())


def need_display() -> None:
    """Raises WindowUnavailable("no_display") when there is no desktop to show a window on. Asks for the display itself: with the bindings Ubuntu 22.04 ships, `Gtk.init_check()` says True even with
    no display (found by running it there), so its answer is not used."""
    Gtk.init_check()
    if Gdk.Display.get_default() is None:
        raise WindowUnavailable("no_display")
