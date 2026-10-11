# SPDX-License-Identifier: GPL-3.0-or-later
"""The main window: a list of pages on the left, the page on the right, and below them the last result and a busy line. It owns the one task that can run at a time (a flow in a worker
thread, core/windowio.py) and answers that task's questions with dialogs. Everything that decides is in core/; this file only places widgets and moves calls between threads."""
from __future__ import annotations

from typing import Callable, List, Optional, Sequence, Tuple

from ..core import windowio as wio
from ..core import windowmodel as wm
from . import a11y, dialogs
from .gtkload import GLib, Gtk
from .pages import FreePage, Page, ProjectsPage, RoundsPage, VoiceFilePage

PULSE_MS = 150


class GtkSink:
    """Moves a run's calls from its worker thread to the window's thread. `GLib.idle_add` is the only thing here that is safe to call from the worker."""

    def __init__(self, shell: "Shell"):
        self._shell = shell

    def line(self, text: str) -> None:
        GLib.idle_add(lambda: (self._shell.on_line(text), False)[1])

    def confirm(self, lines: Tuple[str, ...], question: str, reply: Callable[[bool], None]) -> None:
        GLib.idle_add(lambda: (self._shell.show_confirm(lines, question, reply), False)[1])

    def ask(self, lines: Tuple[str, ...], prompt: str, reply: Callable[[Optional[str]], None]) -> None:
        GLib.idle_add(lambda: (self._shell.show_entry(prompt, "", reply), False)[1])

    def finished(self, code: int, lines: Tuple[str, ...]) -> None:
        GLib.idle_add(lambda: (self._shell.on_finished(code, lines), False)[1])


class Shell(Gtk.ApplicationWindow):
    def __init__(self, app: Gtk.Application, services: wm.Services):
        super().__init__(application=app, title=services.cat.t("window.title"), default_width=1020, default_height=760)
        self.services = services
        self.cat = services.cat
        self.project_id: Optional[str] = None
        self.run_handle: Optional[wio.Run] = None
        self.dialog: Optional[Gtk.Dialog] = None            # the question on the screen, kept so a test can answer it
        self.last_result: Tuple[int, Tuple[str, ...]] = (0, ())
        self._pulse_id = 0
        self._run_lines: List[str] = []
        self._build()
        self.connect("close-request", self._on_close)
        self.auto_open_only_project()

    # ---------------------------------------------------------------- layout

    def _build(self) -> None:
        cat = self.cat
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        middle = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, vexpand=True)
        self.stack = Gtk.Stack(hexpand=True, vexpand=True, transition_type=Gtk.StackTransitionType.NONE)
        self.pages: List[Page] = [ProjectsPage(self), RoundsPage(self), VoiceFilePage(self), FreePage(self)]
        names = ("projects", "rounds", "voicefile", "free")
        titles = (cat.t("window.nav.projects"), cat.t("window.nav.rounds"), cat.t("window.nav.voicefile"), cat.t("window.nav.free"))
        for page, key, title in zip(self.pages, names, titles):
            self.stack.add_titled(page.widget, key, title)
        self.sidebar = Gtk.StackSidebar(stack=self.stack, width_request=210)
        a11y.name(self.sidebar, cat.t("window.nav.label"))
        middle.append(self.sidebar)
        middle.append(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL))
        middle.append(self.stack)
        outer.append(middle)
        outer.append(Gtk.Separator())
        outer.append(self._build_result())
        self.set_child(outer)

    def _build_result(self) -> Gtk.Widget:
        cat = self.cat
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4, css_classes=["panel"])
        box.append(Gtk.Label(label=cat.t("window.result.heading"), xalign=0, css_classes=["section-heading"]))
        self.busy_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10, visible=False)
        self.busy_label = Gtk.Label(label=cat.t("window.busy"), xalign=0)
        self.progress = Gtk.ProgressBar(hexpand=True, valign=Gtk.Align.CENTER)
        a11y.name(self.progress, cat.t("window.busy"))
        self.busy_row.append(self.busy_label)
        self.busy_row.append(self.progress)
        box.append(self.busy_row)
        self.result_label = Gtk.Label(label=cat.t("window.result.none"), wrap=True, xalign=0, selectable=True, css_classes=["result-text"], accessible_role=Gtk.AccessibleRole.STATUS)
        scroll = Gtk.ScrolledWindow(min_content_height=70, max_content_height=170, propagate_natural_height=True, hscrollbar_policy=Gtk.PolicyType.NEVER)
        scroll.set_child(self.result_label)
        box.append(scroll)
        return box

    # ---------------------------------------------------------------- the project

    def auto_open_only_project(self) -> None:
        view = wm.projects_view(self.services.home, self.cat)
        if len(view.items) == 1:
            self.open_project(view.items[0].id, announce=False)
        else:
            self.refresh()

    def open_project(self, project_id: str, announce: bool = True) -> None:
        project = wm.find_project(self.services.home, project_id)
        if project is None:
            return
        self.project_id = project.id
        self.set_title("%s - %s" % (self.cat.t("window.title"), project.name))
        if announce:
            self.set_result(0, (self.cat.t("window.projects.opened", name=project.name),))
        self.refresh()
        self.stack.set_visible_child_name("rounds")

    def refresh(self) -> None:
        for page in self.pages:
            page.refresh()

    # ---------------------------------------------------------------- the one task at a time

    @property
    def busy(self) -> bool:
        return self.run_handle is not None and self.run_handle.active

    def run(self, button: Tuple[str, Sequence[str]]) -> None:
        """Run what a button asks for (the words of a terminal command) as the one task. A second click while one runs does nothing."""
        if self.busy:
            return
        tool, argv = button
        self._run_lines = []
        self._set_busy(True)
        services, crashed = self.services, self.cat.t("window.crashed")
        self.run_handle = wio.start_run(lambda io: services.run(tool, argv, io), GtkSink(self), services.titles(), crashed)

    def _set_busy(self, busy: bool) -> None:
        self.busy_row.set_visible(busy)
        self.stack.set_sensitive(not busy)
        self.sidebar.set_sensitive(not busy)
        if busy and not self._pulse_id:
            self._pulse_id = GLib.timeout_add(PULSE_MS, self._pulse)
        if not busy:
            self.progress.set_fraction(0.0)

    def _pulse(self) -> bool:
        if self.run_handle is None or not self.busy_row.get_visible():
            self._pulse_id = 0
            return False
        self.progress.pulse()
        return True

    def on_line(self, text: str) -> None:
        self._run_lines.append(text)
        self.result_label.set_label("\n".join(self._run_lines))

    def on_finished(self, code: int, lines: Sequence[str]) -> None:
        self._set_busy(False)
        self.set_result(code, tuple(lines))
        self.refresh()

    def set_result(self, code: int, lines: Sequence[str]) -> None:
        self.last_result = (code, tuple(lines))
        head = self.cat.t({0: "window.result.ok", 2: "window.result.nothing"}.get(code, "window.result.problem"))
        self.result_label.set_label("\n".join([head] + list(lines)))

    # ---------------------------------------------------------------- questions

    def show_confirm(self, lines: Sequence[str], question: str, reply: Callable[[bool], None]) -> None:
        def done(answer: bool) -> None:
            self.dialog = None
            reply(answer)
        self.dialog = dialogs.confirm(self, self.cat.t("window.dialog.title"), lines, question, self.cat.t("window.dialog.yes"), self.cat.t("window.dialog.no"), done)

    def show_entry(self, prompt: str, initial: str, reply: Callable[[Optional[str]], None], limit: int = 200) -> None:
        def done(text: Optional[str]) -> None:
            self.dialog = None
            reply(text)
        self.dialog = dialogs.entry(self, self.cat.t("window.dialog.title"), prompt, initial, self.cat.t("window.dialog.save"), self.cat.t("window.dialog.cancel"), limit, done)

    # ---------------------------------------------------------------- closing

    def _on_close(self, _window: Gtk.Window) -> bool:
        """A task that is running is not left running unseen: ask first. Stopping the wait never deletes anything (what a flow has made stays where it is)."""
        if not self.busy:
            return False
        if self.dialog is not None:
            return True

        def answered(close: bool) -> None:
            if close:
                if self.run_handle is not None:
                    self.run_handle.cancel()
                self.destroy()
        self.show_confirm((self.cat.t("window.close.body"),), self.cat.t("window.close.question"), answered)
        return True
