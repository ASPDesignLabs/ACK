# SPDX-License-Identifier: GPL-3.0-or-later
"""A headless tour of the window, for a virtual display (plan P6: a headless check of the accessible names; section 3: tests for the GTK edge).

`python3 -m voice_studio.window --selftest` builds the real window against whatever is under HOME, visits every page, checks that every control has an accessible name and that text is
12 pt or larger, then presses the real buttons: a Choose answered No and then Yes, a Free up space answered No, and a Make the voice file that is refused. It prints one JSON object of
checks and exits 0 when all hold. Run it only on a copy of a project (HOME set to a folder made for the test): Yes really changes the record of that project.
"""
from __future__ import annotations

import json
import sys
import time
from typing import Callable, Dict, List, Optional

from ..core import rounds as rd
from ..core import windowmodel as wm
from . import a11y, style
from .gtkload import Gio, GLib, Gtk, Pango, version_text

TIMEOUT_S = 15.0


def pump(condition: Callable[[], bool], timeout: float = TIMEOUT_S) -> bool:
    """Let the window run until `condition` holds (or the time is up)."""
    context = GLib.MainContext.default()
    deadline = time.time() + timeout
    while time.time() < deadline:
        while context.pending():
            context.iteration(False)
        if condition():
            return True
        time.sleep(0.01)
    return False


def find(root: Gtk.Widget, name: str) -> Optional[Gtk.Widget]:
    for widget in a11y.walk(root):
        if a11y.label_of(widget) == name:
            return widget
    return None


def points(widget: Gtk.Widget) -> float:
    """The widget's text size in points. GTK gives pixels for a size written in points in the style file, at the screen's dpi."""
    description = widget.get_pango_context().get_font_description()
    size = description.get_size() / Pango.SCALE
    if description.get_size_is_absolute():
        dpi = Gtk.Settings.get_default().get_property("gtk-xft-dpi") / 1024.0 or 96.0
        return size * 72.0 / dpi
    return size


def labels(root: Gtk.Widget) -> List[Gtk.Label]:
    return [w for w in a11y.walk(root) if isinstance(w, Gtk.Label)]


def run(services: wm.Services) -> int:
    from .app import Application
    checks: Dict[str, object] = {}
    app = Application(services)
    app.register(None)
    Gio.Application.activate(app)
    shell = app.props.active_window
    pump(lambda: shell.is_visible())
    cat = services.cat
    checks["gtk"] = version_text()
    checks["window_title"] = shell.get_title()
    pages = [shell.stack.get_page(p.widget).get_title() for p in shell.pages]
    checks["pages"] = pages
    checks["project_opened"] = shell.project_id

    unnamed: Dict[str, List[str]] = {}
    smallest = 99.0
    for key, page in zip(("projects", "rounds", "voicefile", "free"), shell.pages):
        shell.stack.set_visible_child_name(key)
        page.refresh()
        pump(lambda: True, 0.05)
        missing = a11y.unnamed_controls(page.widget)
        if missing:
            unnamed[key] = missing
        for label in labels(page.widget):
            smallest = min(smallest, points(label))
    checks["unnamed_controls"] = unnamed
    checks["smallest_text_pt"] = round(smallest, 1)
    checks["animations_off"] = not Gtk.Settings.get_default().get_property("gtk-enable-animations")

    pid = shell.project_id
    if pid is None:
        print(json.dumps(checks))
        return 1
    record = rd.load(wm.open_project(services.home, pid).paths)
    chosen = record.current

    shell.stack.set_visible_child_name("rounds")
    shell.pages[1].refresh()
    other = next((i.number for i in wm.rounds_view(services.home, pid, cat).items if i.can_choose), None)
    checks["a_round_can_be_chosen"] = other is not None
    if other is not None:
        button = find(shell.pages[1].widget, cat.t("window.rounds.choose_name", number=other))
        checks["choose_button_found"] = button is not None
        button.emit("clicked")
        checks["choose_question_shown"] = pump(lambda: shell.dialog is not None)
        question_ok = shell.dialog is not None
        if question_ok:
            pump(lambda: shell.dialog.get_focus() is not None, 2.0)
            no_button = shell.dialog.get_widget_for_response(Gtk.ResponseType.CANCEL)
            checks["no_is_where_the_focus_starts"] = shell.dialog.get_focus() is no_button and no_button.get_label() == cat.t("window.dialog.no")
            checks["yes_is_not_the_default"] = shell.dialog.get_widget_for_response(Gtk.ResponseType.YES).get_label() == cat.t("window.dialog.yes")
            checks["question_has_no_typed_instruction"] = "Type yes" not in " ".join(w.get_label() for w in labels(shell.dialog.get_content_area()))
        shell.dialog.response(Gtk.ResponseType.CANCEL) if question_ok else None
        checks["no_answered"] = pump(lambda: not shell.busy and shell.dialog is None and shell.last_result[0] == 2)
        checks["no_changed_nothing"] = rd.load(wm.open_project(services.home, pid).paths).current == chosen
        shell.pages[1].refresh()
        find(shell.pages[1].widget, cat.t("window.rounds.choose_name", number=other)).emit("clicked")
        pump(lambda: shell.dialog is not None)
        shell.dialog.response(Gtk.ResponseType.YES) if shell.dialog is not None else None
        checks["yes_answered"] = pump(lambda: not shell.busy and shell.dialog is None and shell.last_result[0] == 0)
        checks["yes_chose_it"] = rd.load(wm.open_project(services.home, pid).paths).current == other

    shell.stack.set_visible_child_name("free")
    shell.pages[3].refresh()
    free_page = shell.pages[3]
    if free_page.checks:
        free_page.checks[0][0].set_active(True)
        checks["remove_button_ready"] = free_page.remove.get_sensitive()
        free_page.remove.emit("clicked")
        checks["free_question_shown"] = pump(lambda: shell.dialog is not None)
        shell.dialog.close() if shell.dialog is not None else None                  # closing the question any way but Yes is a No
        checks["free_no_answered"] = pump(lambda: not shell.busy and shell.dialog is None and shell.last_result[0] == 2)
    checks["free_listed"] = len(free_page.checks)

    shell.stack.set_visible_child_name("voicefile")
    shell.pages[2].refresh()
    make = find(shell.pages[2].widget, cat.t("window.voicefile.make"))
    checks["make_button_found"] = make is not None
    if make is not None:
        make.emit("clicked")
        pump(lambda: shell.busy or shell.last_result[1])
        checks["make_finished"] = pump(lambda: not shell.busy)
        checks["make_said_why"] = bool(shell.last_result[1]) and shell.last_result[0] in (1, 2)

    checks["not_busy_at_the_end"] = not shell.busy
    shell.destroy()
    failed = sorted(k for k, v in checks.items() if v is False or (k == "unnamed_controls" and v) or (k == "smallest_text_pt" and float(v) < style.BASE_PT - 0.05))
    checks["failed"] = failed
    print(json.dumps(checks, sort_keys=True))
    return 1 if failed else 0
