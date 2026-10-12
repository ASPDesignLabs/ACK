# SPDX-License-Identifier: GPL-3.0-or-later
"""The GTK application: one window, started once (a second start brings the first to the front)."""
from __future__ import annotations

from ..core import launcher
from ..core import windowmodel as wm
from .gtkload import Gio, Gtk
from .shell import Shell
from .theme import Appearance


class Application(Gtk.Application):
    def __init__(self, services: wm.Services):
        super().__init__(application_id=launcher.APP_ID, flags=Gio.ApplicationFlags.FLAGS_NONE)
        self.services = services
        self.appearance = Appearance.load(services.home.window_file)

    def do_startup(self) -> None:
        Gtk.Application.do_startup(self)
        self.appearance.apply()

    def do_activate(self) -> None:
        window = self.props.active_window or Shell(self, self.services, self.appearance)
        window.present()


def run(services: wm.Services) -> int:
    return Application(services).run([])
