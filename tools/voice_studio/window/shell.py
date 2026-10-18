# SPDX-License-Identifier: GPL-3.0-or-later
"""The main window: a list of pages on the left, the page on the right, and below them the last result and a busy line. It owns the one task that can run at a time (a flow in a worker
thread, core/windowio.py) and answers that task's questions with dialogs. Everything that decides is in core/; this file only places widgets and moves calls between threads."""
from __future__ import annotations

from typing import Callable, List, Optional, Sequence, Tuple

from ..core import describe
from ..core import windowio as wio
from ..core import windowmodel as wm
from ..core import windowprefs as wp
from . import a11y, dialogs, sizing
from .gtkload import GLib, Gtk
from .pages import DisplayPage, FreePage, Page, ProjectsPage, RecordingsPage, RoundsPage, VoiceFilePage
from .theme import Appearance
from .toolpages import BackupPage, HearPage, RefreshPage, ReportPage, UpdatePage

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
    def __init__(self, app: Gtk.Application, services: wm.Services, appearance: Appearance):
        super().__init__(application=app, title=services.cat.t("window.title"), default_width=1100, default_height=820)
        self.services = services
        self.appearance = appearance
        self.cat = services.cat
        self.project_id: Optional[str] = None
        self.run_handle: Optional[wio.Run] = None
        self.dialog: Optional[Gtk.Dialog] = None            # the question on the screen, kept so a test can answer it
        self.form = None                                    # the form on the screen (window/forms.py), kept so a test can fill it
        self.chooser = None                                 # the system's file chooser on the screen (window/toolforms.py), kept so a test can close it
        self.last_failure: Optional[wm.Failure] = None      # the last task that failed after it began (not a report): what the Problem report page offers to be about
        self._current: Tuple[str, Sequence[str]] = ("", ())
        self._then: Optional[Callable[[int], None]] = None  # told the exit code when the task that is running ends
        self.last_result: Tuple[int, Tuple[str, ...]] = (0, ())
        self._pulse_id = 0
        self._run_lines: List[str] = []
        self._build()
        self.connect("close-request", self._on_close)
        self.auto_open_only_project()

    # ---------------------------------------------------------------- layout

    def _build(self) -> None:
        cat = self.cat
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, css_classes=["ack-frame"])
        sizing.track(outer, spacing=12)
        outer.append(self._build_header())
        middle = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, vexpand=True)
        sizing.track(middle, spacing=12)
        self.stack = Gtk.Stack(hexpand=True, vexpand=True, transition_type=Gtk.StackTransitionType.NONE)
        self.pages: List[Page] = [ProjectsPage(self), RecordingsPage(self), RoundsPage(self), HearPage(self), VoiceFilePage(self), BackupPage(self), FreePage(self), RefreshPage(self),
                                  UpdatePage(self), ReportPage(self), DisplayPage(self)]
        self.page_names = wm.PAGES
        titles = (cat.t("window.nav.projects"), cat.t("window.nav.recordings"), cat.t("window.nav.rounds"), cat.t("window.nav.hear"), cat.t("window.nav.voicefile"), cat.t("window.nav.backup"),
                  cat.t("window.nav.free"), cat.t("window.nav.refresh"), cat.t("window.nav.update"), cat.t("window.nav.report"), cat.t("window.nav.display"))
        for page, key, title in zip(self.pages, self.page_names, titles):
            self.stack.add_titled(page.widget, key, title)
        self.sidebar = Gtk.StackSidebar(stack=self.stack, css_classes=["ack-nav"])
        sizing.track(self.sidebar, width_request=230)
        a11y.name(self.sidebar, cat.t("window.nav.label"))
        middle.append(self.sidebar)
        middle.append(self.stack)
        outer.append(middle)
        outer.append(self._build_result())
        self.set_child(outer)

    def page(self, name: str) -> Page:
        """The page with this name (one of `page_names`)."""
        return self.pages[self.page_names.index(name)]

    def _build_header(self) -> Gtk.Widget:
        """ACK's header: the name large, what this is under it, the project, and the two buttons that change the size of the text (the rest of the display choices are on their own page)."""
        cat = self.cat
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, css_classes=["ack-header"])
        sizing.track(header, spacing=16)
        left = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, hexpand=True)
        sizing.track(left, spacing=2)
        left.append(Gtk.Label(label="ACK", xalign=0, css_classes=["brand"]))
        left.append(Gtk.Label(label=cat.t("window.header.tagline"), xalign=0, css_classes=["tagline"]))
        self.project_label = Gtk.Label(label=cat.t("window.header.no_project"), xalign=0, wrap=True, css_classes=["dim-text"])
        left.append(self.project_label)
        header.append(left)
        controls = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, valign=Gtk.Align.START)
        sizing.track(controls, spacing=8)
        self.smaller_text = Gtk.Button(label="A\u2212", css_classes=["ack-button"])
        self.bigger_text = Gtk.Button(label="A+", css_classes=["ack-button"])
        a11y.name(self.smaller_text, cat.t("window.display.smaller_text_name"))
        a11y.name(self.bigger_text, cat.t("window.display.bigger_text_name"))
        self.smaller_text.connect("clicked", lambda _b: self.change_look(self.appearance.look.smaller_text()))
        self.bigger_text.connect("clicked", lambda _b: self.change_look(self.appearance.look.bigger_text()))
        controls.append(self.smaller_text)
        controls.append(self.bigger_text)
        header.append(controls)
        self.appearance.listen(self._look_changed)
        self._look_changed()
        return header

    def _look_changed(self) -> None:
        look = self.appearance.look
        self.smaller_text.set_sensitive(look.smaller_text() != look)
        self.bigger_text.set_sensitive(look.bigger_text() != look)

    def _build_result(self) -> Gtk.Widget:
        cat = self.cat
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, css_classes=["panel"])
        sizing.track(box, spacing=4)
        box.append(Gtk.Label(label=cat.t("window.result.heading"), xalign=0, css_classes=["section-heading"]))
        self.busy_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, visible=False)
        sizing.track(self.busy_row, spacing=10)
        self.busy_label = Gtk.Label(label=cat.t("window.busy"), xalign=0)
        self.progress = Gtk.ProgressBar(hexpand=True, valign=Gtk.Align.CENTER)
        a11y.name(self.progress, cat.t("window.busy"))
        self.busy_row.append(self.busy_label)
        self.busy_row.append(self.progress)
        box.append(self.busy_row)
        self.result_label = Gtk.Label(label=cat.t("window.result.none"), wrap=True, xalign=0, selectable=True, css_classes=["result-text"], accessible_role=Gtk.AccessibleRole.STATUS)
        scroll = Gtk.ScrolledWindow(propagate_natural_height=True, hscrollbar_policy=Gtk.PolicyType.NEVER)
        sizing.track(scroll, min_content_height=70, max_content_height=170)
        scroll.set_child(self.result_label)
        box.append(scroll)
        self.report_button = Gtk.Button(label=cat.t("window.result.report_button"), css_classes=["ack-button"], halign=Gtk.Align.START, visible=False)
        self.report_button.connect("clicked", lambda _b: self.stack.set_visible_child_name("report"))
        a11y.name(self.report_button, cat.t("window.result.report_button"))
        self.stack.connect("notify::visible-child", lambda _s, _p: self._show_report_button())
        box.append(self.report_button)
        return box

    # ---------------------------------------------------------------- the display

    def change_look(self, look) -> None:
        """Show a new look, and keep it the way the person has agreed to. The first change asks (the window has never written a file of its own); a No keeps the change for this session only."""
        outcome = self.appearance.change(look)
        if outcome == "failed":
            self.set_result(1, (self.cat.t("window.display.not_saved"),))
        elif outcome == "ask" and self.dialog is None:
            self.ask_to_keep()

    def ask_to_keep(self) -> None:
        cat, appearance = self.cat, self.appearance
        lines = (cat.t("window.display.keep_plan_head"), "  " + appearance.path, cat.t("window.display.keep_plan_holds"), cat.t("window.display.keep_plan_private"))

        def reply(yes: bool) -> None:
            if not yes:
                appearance.keeper.said_no()
                self.set_result(2, (cat.t("window.display.session_only"),))
                return
            appearance.keeper.said_yes()
            if appearance.save() == "saved":
                self.set_result(0, (cat.t("window.display.kept", path=appearance.path),))
            else:
                appearance.keeper.said_no()
                self.set_result(1, (cat.t("window.display.not_saved"),))
        self.show_confirm(lines, cat.t("window.display.keep_question"), reply)

    def ask_to_forget(self) -> None:
        cat, appearance = self.cat, self.appearance
        shown = wp.plan_forget(appearance.path)
        if not shown:
            self.set_result(0, (cat.t("window.display.nothing_kept"),))
            return

        def reply(yes: bool) -> None:
            if not yes:
                self.set_result(2, ())
                return
            try:
                wp.forget(shown)
            except OSError:
                self.set_result(1, (cat.t("window.display.not_removed"),))
                return
            appearance.keeper.forgot()
            self.set_result(0, (cat.t("window.display.forgotten"),))
            self.refresh()
        self.show_confirm((cat.t("window.display.forget_plan_head"),) + tuple("  " + p for p in shown), cat.t("window.display.forget_question"), reply)

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
        self.project_label.set_label(self.cat.t("window.header.project", name=project.name))
        if announce:
            self.set_result(0, (self.cat.t("window.projects.opened", name=project.name),))
        self.refresh()
        self.stack.set_visible_child_name("recordings")

    def refresh(self) -> None:
        self._close_project_if_gone()
        for page in self.pages:
            page.refresh()

    def _close_project_if_gone(self) -> None:
        """A project that was put away or deleted is no longer open: nothing keeps working on a project that is not in use."""
        if self.project_id is not None and wm.find_project(self.services.home, self.project_id) is None:
            self.project_id = None
            self.set_title(self.cat.t("window.title"))
            self.project_label.set_label(self.cat.t("window.header.no_project"))
            self.add_to_result(self.cat.t("window.projects.closed"))

    # ---------------------------------------------------------------- the one task at a time

    @property
    def busy(self) -> bool:
        return self.run_handle is not None and self.run_handle.active

    def run(self, button: Tuple[str, Sequence[str]], then: Optional[Callable[[int], None]] = None) -> None:
        """Run what a button asks for (the words of a terminal command) as the one task. A second click while one runs does nothing. `then` is told the exit code when the task ends."""
        if self.busy:
            return
        tool, argv = button
        self._current = (tool, argv)
        describe.forget_errors_shown()                     # the problems this task tells the person about are the ones a report may name
        self._then = then
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
        tool, argv = self._current
        if tool != "report":                                # a report is about the task before it, so making one does not forget which that was
            self.last_failure = wm.failure_about(tool, argv, describe.errors_shown()) if code == 1 else None
            if code == 1:
                self.add_to_result(self.cat.t("window.result.report_hint", page=self.cat.t("window.nav.report")))
            self._show_report_button()
        then, self._then = self._then, None
        self.refresh()
        if then is not None:
            then(code)

    def _show_report_button(self) -> None:
        """The way to the Problem report page is offered under a failed task, so it is found without looking through the list of pages. It goes away on that page and after a task that did not fail."""
        self.report_button.set_visible(self.last_failure is not None and self.stack.get_visible_child_name() != "report")

    def add_to_result(self, line: str) -> None:
        """One more line under what the last task said (the task's own words stay)."""
        code, lines = self.last_result
        self.last_result = (code, tuple(lines) + (line,))
        self.result_label.set_label(self.result_label.get_label() + "\n" + line)

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
