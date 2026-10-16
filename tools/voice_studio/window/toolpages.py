# SPDX-License-Identifier: GPL-3.0-or-later
"""The pages for the tool's own commands: Hear the voice, Backup, Check the tool, Updates and Problem report.

Each is the window's face for a terminal command (`voicefile listen`, `backup`, `refresh`, `update`, `report`). A page builds its widgets from a view in core/windowmodel.py and, when a button
is pressed, hands the shell the words of that command; the command shows what it will do and asks first, with Yes and No buttons, before it changes anything or contacts anything. Nothing on
these pages starts by itself, nothing reads again by a timer, and a page keeps no state of its own that the files do not have except what the person has just picked. A drop-down is built once
and updated in place (GTK 4.6 prints a critical warning for one that is destroyed and rebuilt under the keyboard focus).
"""
from __future__ import annotations

from typing import Callable, List, Optional, Sequence, Tuple

from ..core import showfolder
from ..core import windowmodel as wm
from . import a11y, sizing, toolforms
from .gtkload import Gtk
from .pages import Page, action_bar, button, clear, text


def check_row(label: str, active: bool, on_toggled: Callable[[bool], None], name: str = "") -> Tuple[Gtk.Box, Gtk.CheckButton]:
    """A tick box with its words beside it. GTK 4.6 cannot wrap the words of a tick box, so a long sentence would make the page wider than the window; here the words wrap, and a click on
    them ticks the box."""
    row = sizing.track(Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL), spacing=10)
    check = Gtk.CheckButton(valign=Gtk.Align.START, active=active)
    a11y.name(check, name or label)
    check.connect("toggled", lambda c: on_toggled(c.get_active()))
    words = text(label)
    click = Gtk.GestureClick()
    click.connect("released", lambda _g, _n, _x, _y, c=check: c.set_active(not c.get_active()) if c.get_sensitive() else None)
    words.add_controller(click)
    row.append(check)
    row.append(words)
    return row, check


def fill(model: Gtk.StringList, items: Sequence[str]) -> None:
    """Replace what a drop-down offers, in place."""
    model.splice(0, model.get_n_items(), list(items))


def chosen_index(dropdown: Gtk.DropDown, count: int) -> int:
    selected = dropdown.get_selected()
    return selected if 0 <= selected < count else -1


def show_folder(page: Page, folder: str, done_key: str, failed_key: str) -> None:
    """Open a folder in the computer's file manager. It only looks; if it cannot be opened, its path is said so it can be copied."""
    if showfolder.open_folder(folder, page.shell.services.system):
        page.shell.set_result(0, (page.cat.t(done_key),))
    else:
        page.shell.set_result(1, (page.cat.t(failed_key, path=folder),))


# ---------------------------------------------------------------- Backup

class BackupPage(Page):
    """The project's backups: where the next one goes, make one, and check or put back one that is there. The page lists what is in the folder it would use; it reads that again whenever
    it is shown, and a backup file chosen from somewhere else is checked or put back the same way."""

    def build(self) -> None:
        self.folder = ""                                   # a folder the person chose for the next backup; "" is the one used last, or the tool's own
        self.leave_out = False
        self.now = self.choose = self.usual = self.points = self.check_other = self.put_back_other = None
        self.rows: Optional[Gtk.ListBox] = None
        self.refresh()

    def refresh(self) -> None:
        cat, shell = self.cat, self.shell
        clear(self.content)
        self.now = self.choose = self.usual = self.points = self.check_other = self.put_back_other = None
        self.rows = None
        if not self.need_project():
            return
        view = wm.backup_view(shell.services.home, shell.project_id, cat)
        if view is None:
            self.content.append(text(cat.t("window.no_project")))
            return
        pid = view.project_id
        c = self.content
        c.append(text(cat.t("window.backup.heading", name=view.project_name), ("page-heading",)))
        c.append(text(cat.t("window.backup.intro"), ("dim-text",)))
        if view.problem:
            c.append(text(view.problem, selectable=True))
            return
        if view.standing:
            c.append(text(view.standing, selectable=True))
        c.append(text(wm.backup_folder_line(cat, view.how, self.folder or view.folder, bool(self.folder)), selectable=True))
        row, self.points = check_row(cat.t("window.backup.without_points"), self.leave_out, self._points_changed)
        c.append(row)
        self.now = button(cat.t("window.backup.now"), lambda: shell.run(wm.backup_now_args(pid, self.folder, not self.leave_out), then=self._after_backup))
        self.choose = button(cat.t("window.backup.choose_folder"), self._choose_folder)
        made = [self.now, self.choose]
        if self.folder:
            self.usual = button(cat.t("window.backup.usual_folder"), self._use_usual)
            made.append(self.usual)
        made.append(button(cat.t("window.backup.show_folder"), lambda: show_folder(self, self.folder or view.folder, "window.backup.folder_shown", "window.backup.folder_failed")))
        c.append(action_bar(made))
        c.append(text(cat.t("window.backup.list_heading"), ("section-heading",)))
        if not view.items:
            c.append(text(cat.t("window.backup.none"), selectable=True))
        else:
            self.rows = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE, css_classes=["boxed-list"])
            a11y.name(self.rows, cat.t("window.backup.list_heading"))
            for item in view.items:
                self.rows.append(self._row(item))
            c.append(self.rows)
        c.append(text(cat.t("window.backup.elsewhere_heading"), ("section-heading",)))
        c.append(text(cat.t("window.backup.elsewhere_hint"), ("dim-text",)))
        self.check_other = button(cat.t("window.backup.check_other"), lambda: self._pick_file(wm.backup_verify_args))
        self.put_back_other = button(cat.t("window.backup.put_back_other"), lambda: self._pick_file(wm.backup_restore_args))
        c.append(action_bar([self.check_other, self.put_back_other]))

    def _row(self, item: wm.BackupItem) -> Gtk.ListBoxRow:
        cat, shell = self.cat, self.shell
        row = Gtk.ListBoxRow(activatable=False, selectable=False)
        box = sizing.track(Gtk.Box(orientation=Gtk.Orientation.VERTICAL, css_classes=["row-box"]), spacing=4)
        box.append(text(item.line, ("round-head",), selectable=True))
        box.append(text(item.path, selectable=True))
        actions = sizing.track(Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL), spacing=8)
        actions.append(button(cat.t("window.backup.check"), lambda p=item.path: shell.run(wm.backup_verify_args(p)), cat.t("window.backup.check_name", name=item.name)))
        actions.append(button(cat.t("window.backup.put_back"), lambda p=item.path: shell.run(wm.backup_restore_args(p)), cat.t("window.backup.put_back_name", name=item.name)))
        box.append(actions)
        row.set_child(box)
        return row

    # ---------------------------------------------------------------- what the buttons do

    def _points_changed(self, active: bool) -> None:
        self.leave_out = active

    def _use_usual(self) -> None:
        self.folder = ""
        self.refresh()

    def _choose_folder(self) -> None:
        toolforms.open_chooser(self.shell, self.shell, self.cat.t("window.backup.chooser_folder"), True, self.folder_chosen)

    def folder_chosen(self, path: str) -> None:
        """What the chooser hands back. A folder that cannot be used is said so in a sentence, and nothing is changed."""
        problem = wm.check_backup_folder(self.cat, path)
        if problem:
            self.shell.set_result(2, problem)
            return
        self.folder = path
        self.refresh()

    def _pick_file(self, command: Callable[[str], Tuple[str, List[str]]]) -> None:
        toolforms.open_chooser(self.shell, self.shell, self.cat.t("window.backup.chooser_file"), False, lambda path: self.shell.run(command(path)),
                               self.cat.t("window.backup.filter"), ("*.tar", "*.TAR"))

    def _after_backup(self, code: int) -> None:
        """A folder chosen for one backup is not kept for the next: the command itself remembers the folder it used, and that is what the page then says."""
        if code == 0:
            self.folder = ""
            self.refresh()


# ---------------------------------------------------------------- Hear the voice

class HearPage(Page):
    """Hearing a voice on this computer before it goes to the phone: a voice file that was made, or a training round straight. The list of voice files is rebuilt on every look; the
    drop-down of rounds is built once and updated in place."""

    def build(self) -> None:
        self.top = sizing.track(Gtk.Box(orientation=Gtk.Orientation.VERTICAL), spacing=10)
        self.rounds_box = self._build_rounds_box()
        self.bottom = sizing.track(Gtk.Box(orientation=Gtk.Orientation.VERTICAL), spacing=10)
        for part in (self.top, self.rounds_box, self.bottom):
            self.content.append(part)
        self.round_numbers: List[int] = []
        self.refresh()

    def _build_rounds_box(self) -> Gtk.Box:
        cat = self.cat
        box = sizing.track(Gtk.Box(orientation=Gtk.Orientation.VERTICAL), spacing=10)
        box.append(text(cat.t("window.hear.rounds_heading"), ("section-heading",)))
        box.append(text(cat.t("window.hear.rounds_hint"), ("dim-text",)))
        self.running_note = text("", selectable=True)
        self.no_rounds = text(cat.t("window.hear.no_rounds"), selectable=True)
        box.append(self.running_note)
        box.append(self.no_rounds)
        self.round_form = sizing.track(Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL), spacing=10)
        self.round_names = Gtk.StringList.new([])
        self.round_choice = Gtk.DropDown(model=self.round_names)
        a11y.name(self.round_choice, cat.t("window.hear.round_label"))
        self.hear_round = button(cat.t("window.hear.hear_round"), self._hear_round)
        for widget in (text(cat.t("window.hear.round_label")), self.round_choice, self.hear_round):
            self.round_form.append(widget)
        box.append(self.round_form)
        return box

    def refresh(self) -> None:
        cat, shell = self.cat, self.shell
        clear(self.top)
        clear(self.bottom)
        self.rounds_box.set_visible(False)
        if shell.project_id is None:
            self.top.append(text(cat.t("window.no_project")))
            return
        view = wm.hear_view(shell.services.home, shell.project_id, cat)
        if view is None:
            self.top.append(text(cat.t("window.no_project")))
            return
        pid = view.project_id
        self.top.append(text(cat.t("window.hear.heading", name=view.project_name), ("page-heading",)))
        self.top.append(text(cat.t("window.hear.intro"), ("dim-text",)))
        if view.problem:
            self.top.append(text(view.problem, selectable=True))
            return
        self.top.append(text(cat.t("window.hear.voices_heading"), ("section-heading",)))
        if not view.voices:
            self.top.append(text(cat.t("window.hear.no_voices"), selectable=True))
        else:
            rows = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE, css_classes=["boxed-list"])
            a11y.name(rows, cat.t("window.hear.voices_heading"))
            for item in view.voices:
                row = Gtk.ListBoxRow(activatable=False, selectable=False)
                box = sizing.track(Gtk.Box(orientation=Gtk.Orientation.VERTICAL, css_classes=["row-box"]), spacing=4)
                box.append(text(item.line, ("round-head",), selectable=True))
                actions = sizing.track(Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL), spacing=8)
                actions.append(button(cat.t("window.hear.hear_voice"), lambda n=item.name: shell.run(wm.listen_voice_args(pid, n)), cat.t("window.hear.hear_voice_name", name=item.name)))
                box.append(actions)
                row.set_child(box)
                rows.append(row)
            self.top.append(rows)
        self._update_rounds(view)
        self.rounds_box.set_visible(True)
        self.bottom.append(button(cat.t("window.hear.show_folder"), lambda: show_folder(self, view.folder, "window.hear.folder_shown", "window.hear.folder_failed")))

    def _update_rounds(self, view: wm.HearView) -> None:
        cat = self.cat
        kept = self.round_numbers[self.round_choice.get_selected()] if 0 <= self.round_choice.get_selected() < len(self.round_numbers) else None
        self.round_numbers = [r.number for r in view.rounds]
        fill(self.round_names, [r.line for r in view.rounds])
        if view.rounds:
            wanted = kept if kept in self.round_numbers else next((r.number for r in view.rounds if r.chosen), self.round_numbers[-1])
            self.round_choice.set_selected(self.round_numbers.index(wanted))
        self.running_note.set_label(cat.t("window.hear.running", number=view.running) if view.running is not None else "")
        self.running_note.set_visible(bool(self.running_note.get_label()))
        self.no_rounds.set_visible(not view.rounds and view.running is None)
        self.round_form.set_visible(bool(view.rounds))

    def _hear_round(self) -> None:
        index = chosen_index(self.round_choice, len(self.round_numbers))
        if self.shell.project_id is not None and index >= 0:
            self.shell.run(wm.listen_round_args(self.shell.project_id, self.round_numbers[index]))


# ---------------------------------------------------------------- Check the tool

class RefreshPage(Page):
    """Looking at the tool's own programs, downloads and notes, mending what is broken, building a fresh copy of the programs, and the older copies. Built once: nothing here depends on
    a project, and nothing is read until a button is pressed (a look can take a while)."""

    def build(self) -> None:
        cat, shell, c = self.cat, self.shell, self.content
        c.append(text(cat.t("window.refresh.heading"), ("page-heading",)))
        c.append(text(cat.t("window.refresh.intro"), ("dim-text",)))
        self.check = button(cat.t("window.refresh.check"), lambda: shell.run(wm.refresh_check_args()))
        self.check_quick = button(cat.t("window.refresh.check_quick"), lambda: shell.run(wm.refresh_check_args(quick=True)))
        self.repair = button(cat.t("window.refresh.repair"), lambda: shell.run(wm.refresh_repair_args()))
        c.append(action_bar([self.check, self.check_quick, self.repair]))
        c.append(text(cat.t("window.refresh.rebuild_heading"), ("section-heading",)))
        c.append(text(cat.t("window.refresh.rebuild_hint"), ("dim-text",)))
        self.choices = wm.programs_choices(cat, shell.services.environments())
        self.programs = Gtk.DropDown(model=Gtk.StringList.new([choice.label for choice in self.choices]))
        a11y.name(self.programs, cat.t("window.refresh.programs_label"))
        self.rebuild = button(cat.t("window.refresh.rebuild"), self._rebuild)
        form = sizing.track(Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL), spacing=10)
        for widget in (text(cat.t("window.refresh.programs_label")), self.programs, self.rebuild):
            form.append(widget)
        c.append(form)
        c.append(text(cat.t("window.refresh.older_heading"), ("section-heading",)))
        c.append(text(cat.t("window.refresh.older_hint"), ("dim-text",)))
        self.older = button(cat.t("window.refresh.older_list"), lambda: shell.run(wm.refresh_older_args()))
        self.older_remove = button(cat.t("window.refresh.older_remove"), lambda: shell.run(wm.refresh_older_args(remove=True)))
        c.append(action_bar([self.older, self.older_remove]))

    def refresh(self) -> None:
        pass                                                # nothing to read until a button is pressed

    def _rebuild(self) -> None:
        index = chosen_index(self.programs, len(self.choices))
        if index >= 0:
            self.shell.run(wm.refresh_rebuild_args(self.choices[index].id))


# ---------------------------------------------------------------- Updates

class UpdatePage(Page):
    """Looking for releases of the tool and fetching one into a new folder. The page never contacts anything by itself: the look is a command that says what it will ask and asks first.
    The releases it found are offered in a drop-down, built once."""

    def build(self) -> None:
        cat, shell, c = self.cat, self.shell, self.content
        c.append(text(cat.t("window.update.heading"), ("page-heading",)))
        c.append(text(cat.t("window.update.intro"), ("dim-text",)))
        self.here = text("", selectable=True)
        c.append(self.here)
        self.look = button(cat.t("window.update.look"), lambda: shell.run(wm.update_check_args()))
        c.append(self.look)
        c.append(text(cat.t("window.update.releases_heading"), ("section-heading",)))
        self.status = text("", selectable=True)
        c.append(self.status)
        self.names = Gtk.StringList.new([])
        self.release = Gtk.DropDown(model=self.names)
        a11y.name(self.release, cat.t("window.update.release_label"))
        self.get = button(cat.t("window.update.get"), self._get, cat.t("window.update.get_name"))
        self.form = sizing.track(Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL), spacing=10)
        for widget in (text(cat.t("window.update.release_label")), self.release, self.get):
            self.form.append(widget)
        c.append(self.form)
        c.append(text(cat.t("window.update.switch_note"), ("dim-text",)))
        self.releases: Tuple[str, ...] = ()
        self.refresh()

    def refresh(self) -> None:
        cat = self.cat
        view = wm.update_view(self.shell.services)
        self.here.set_label("\n".join(view.here))
        found = view.releases or ()
        kept = self.releases[self.release.get_selected()] if 0 <= self.release.get_selected() < len(self.releases) else None
        if found != self.releases:
            self.releases = found
            fill(self.names, found)
            if kept in found:
                self.release.set_selected(found.index(kept))
        self.status.set_label(cat.t("window.update.not_looked") if view.releases is None else cat.t("window.update.none_found") if not found else "")
        self.status.set_visible(not found)
        self.form.set_visible(bool(found))

    def _get(self) -> None:
        index = chosen_index(self.release, len(self.releases))
        if index >= 0:
            self.shell.run(wm.update_get_args(self.releases[index]))


# ---------------------------------------------------------------- Problem report

class ReportPage(Page):
    """A report a helper can read. The page asks for little (what were you doing, and which task, if any), builds the report with the terminal's `report show`, shows all of it here, and saves
    it only where the person says, through a form and then the command's own question. Nothing is sent anywhere."""

    def build(self) -> None:
        cat, shell, c = self.cat, self.shell, self.content
        self._seen_failure = None
        self.job_values: List[str] = [""]
        c.append(text(cat.t("window.report.heading"), ("page-heading",)))
        c.append(text(cat.t("window.report.intro"), ("dim-text",)))
        self.failure_row = sizing.track(Gtk.Box(orientation=Gtk.Orientation.VERTICAL), spacing=0)
        self.failure_words = text("")
        click = Gtk.GestureClick()
        self.failure_check = Gtk.CheckButton(valign=Gtk.Align.START, active=True)
        a11y.name(self.failure_check, cat.t("window.report.use_failure", step=""))
        click.connect("released", lambda _g, _n, _x, _y: self.failure_check.set_active(not self.failure_check.get_active()))
        self.failure_words.add_controller(click)
        line = sizing.track(Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL), spacing=10)
        line.append(self.failure_check)
        line.append(self.failure_words)
        self.failure_row.append(line)
        c.append(self.failure_row)
        c.append(text(cat.t("window.report.step_label")))
        self.step = Gtk.Entry(hexpand=True, width_chars=40, max_length=200)
        a11y.name(self.step, cat.t("window.report.step_label"))
        c.append(self.step)
        c.append(text(cat.t("window.report.task_label")))
        self.job_names = Gtk.StringList.new([])
        self.jobs = Gtk.DropDown(model=self.job_names)
        a11y.name(self.jobs, cat.t("window.report.task_label"))
        self.jobs.connect("notify::selected", lambda _d, _p: self._job_changed())
        c.append(self.jobs)
        row, self.log_check = check_row(cat.t("window.report.include_log"), False, lambda _a: None)
        self.log_row = row
        c.append(row)
        self.show = button(cat.t("window.report.show"), self._show)
        self.save = button(cat.t("window.report.save"), self._save)
        c.append(action_bar([self.show, self.save]))
        c.append(text(cat.t("window.report.shown_heading"), ("section-heading",)))
        self.nothing = text(cat.t("window.report.nothing_shown"), selectable=True)
        c.append(self.nothing)
        self.report_label = Gtk.Label(label="", wrap=True, xalign=0, selectable=True, max_width_chars=100, css_classes=["result-text"])
        self.report_scroll = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER, propagate_natural_height=True)
        sizing.track(self.report_scroll, min_content_height=160, max_content_height=460)
        self.report_scroll.set_child(self.report_label)
        c.append(self.report_scroll)
        self.copy = button(cat.t("window.report.copy"), self._copy)
        c.append(self.copy)
        self.refresh()

    def refresh(self) -> None:
        cat, shell = self.cat, self.shell
        failure = shell.last_failure
        if failure is not self._seen_failure:
            self._seen_failure = failure                     # a new failure is offered ticked; a person who unticked it keeps that until the next one
            self.failure_check.set_active(True)
        self.failure_row.set_visible(failure is not None)
        if failure is not None:
            self.failure_words.set_label(cat.t("window.report.use_failure", step=failure.step))
        choices = wm.job_choices(shell.services.home, cat)
        kept = self.job_values[self.jobs.get_selected()] if 0 <= self.jobs.get_selected() < len(self.job_values) else ""
        values = [value for value, _words in choices]
        if values != self.job_values or self.job_names.get_n_items() != len(values):
            self.job_values = values
            fill(self.job_names, [words for _value, words in choices])
            self.jobs.set_selected(values.index(kept) if kept in values else 0)
        self._job_changed()
        report = shell.services.learned.report
        self.report_label.set_label(report)
        self.report_scroll.set_visible(bool(report))
        self.copy.set_visible(bool(report))
        self.nothing.set_visible(not report)

    def _job_changed(self) -> None:
        index = chosen_index(self.jobs, len(self.job_values))
        has_task = index > 0
        self.log_row.set_sensitive(has_task)
        if not has_task:
            self.log_check.set_active(False)

    def fields(self) -> wm.ReportFields:
        """What the form holds. A failure the window showed fills in the step and the one problem it told, unless the person typed their own words for the step."""
        failure = self.shell.last_failure
        use = failure is not None and self.failure_check.get_active()
        index = chosen_index(self.jobs, len(self.job_values))
        job = self.job_values[index] if index >= 0 else ""
        return wm.ReportFields(self.step.get_text().strip() or (failure.step if use and failure is not None else ""), failure.problem if use and failure is not None else "", job,
                               self.log_check.get_active())

    def _show(self) -> None:
        self.shell.run(wm.report_args(self.fields()), then=self._after_show)

    def _after_show(self, code: int) -> None:
        """The report is below the buttons; the keyboard focus goes to it so that it is in view and a screen reader starts reading it."""
        if code == 0 and self.report_scroll.get_visible():
            self.report_scroll.grab_focus()

    def _save(self) -> None:
        if self.shell.dialog is None:
            toolforms.open_save_report(self.shell, self.fields())

    def _copy(self) -> None:
        self.shell.get_clipboard().set(self.shell.services.learned.report)
        self.shell.set_result(0, (self.cat.t("window.report.copied"),))
