# SPDX-License-Identifier: GPL-3.0-or-later
"""Text size and spacing, and nothing else: no colours (so the system's contrast theme is respected), no animation, no sound (plan P6)."""
from __future__ import annotations

from pathlib import Path

from .gtkload import Gdk, Gio, Gtk

CSS_FILE = Path(__file__).resolve().parent.parent / "data" / "style.css"
BASE_PT = 12                                                         # P6: text 12 pt or larger. Absolute points still follow the system's text scale, because that scales the dpi


def apply() -> Gtk.CssProvider:
    """Load the style file for the whole application and switch off animation and sounds. A file, not a string: the way to pass CSS text differs between GTK 4.6 and later ones."""
    provider = Gtk.CssProvider()
    provider.load_from_file(Gio.File.new_for_path(str(CSS_FILE)))
    Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
    settings = Gtk.Settings.get_default()
    settings.set_property("gtk-enable-animations", False)
    settings.set_property("gtk-enable-event-sounds", False)
    settings.set_property("gtk-enable-input-feedback-sounds", False)
    return provider
