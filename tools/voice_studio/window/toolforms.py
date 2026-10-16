# SPDX-License-Identifier: GPL-3.0-or-later
"""What the pages of the tools need beyond a button: the system's file chooser, to pick a folder or a file that is already there, and the small form that saves the problem report.

A chooser only ever returns a path; nothing is read here. The report form asks for a folder the person chose and a file name, checks them with the very rules the terminal's `report save` uses
(core/windowmodel.py), shows every problem inside the form so that nothing chosen is lost, and only when both are whole closes and hands the shell the words of the terminal command. That command
then builds the report, shows all of it, and asks once more, with Yes and No buttons, before it writes the one file.
"""
from __future__ import annotations

from typing import Callable, Optional, Sequence

from ..core import windowmodel as wm
from . import a11y, sizing
from .gtkload import Gtk

SECTION = "section-heading"


def open_chooser(shell, parent: Gtk.Window, title: str, folder: bool, reply: Callable[[str], None], filter_name: str = "", patterns: Sequence[str] = ()) -> Gtk.FileChooserDialog:
    """The system's own chooser for a folder, or for a file that already exists (never a place to save to: a new file is named in the window's own form). `reply` is told the path when the
    person chooses one, and is not called at all when the chooser is cancelled or closed. The chooser is kept in `shell.chooser` so the headless tour can find it and close it."""
    cat = shell.cat
    chooser = Gtk.FileChooserDialog(title=title, transient_for=parent, modal=True, action=Gtk.FileChooserAction.SELECT_FOLDER if folder else Gtk.FileChooserAction.OPEN)
    chooser.add_button(cat.t("window.dialog.cancel"), Gtk.ResponseType.CANCEL)
    chooser.add_button(cat.t("window.import.chooser_accept"), Gtk.ResponseType.ACCEPT)
    if patterns:
        only = Gtk.FileFilter()
        only.set_name(filter_name)
        for pattern in patterns:
            only.add_pattern(pattern)
        chooser.add_filter(only)

    def answered(dialog: Gtk.FileChooserDialog, response: int) -> None:
        path = dialog.get_file().get_path() if response == Gtk.ResponseType.ACCEPT and dialog.get_file() is not None else ""
        dialog.destroy()
        shell.chooser = None
        if path:
            reply(path)

    chooser.connect("response", answered)
    shell.chooser = chooser
    chooser.present()
    return chooser


class SaveReportForm:
    """Where to save the problem report: a folder (chosen with the system's chooser) and a file name. Attributes are public so the headless tour can fill the form without opening the chooser."""

    def __init__(self, shell, fields: wm.ReportFields):
        self.shell = shell
        self.cat = shell.cat
        self.fields = fields
        self.folder = ""
        self.chooser: Optional[Gtk.FileChooserDialog] = None
        cat = self.cat
        self.dialog = Gtk.Dialog(title=cat.t("window.report.save_title"), transient_for=shell, modal=True, destroy_with_parent=True, css_classes=["ack-dialog"])
        body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, css_classes=["ack-dialog-body"])
        sizing.track(body, spacing=8, margin_top=12, margin_bottom=12, margin_start=12, margin_end=12)
        self.problems = Gtk.Label(label="", wrap=True, xalign=0, selectable=True, visible=False, max_width_chars=60, css_classes=["error-text"], accessible_role=Gtk.AccessibleRole.ALERT)
        body.append(self.problems)
        body.append(Gtk.Label(label=cat.t("window.report.folder"), xalign=0, css_classes=[SECTION]))
        self.folder_label = Gtk.Label(label=cat.t("window.report.folder_none"), xalign=0, wrap=True, selectable=True, max_width_chars=60)
        body.append(self.folder_label)
        self.pick = Gtk.Button(label=cat.t("window.report.choose_folder"), css_classes=["ack-button"], halign=Gtk.Align.START)
        self.pick.connect("clicked", lambda _b: self._choose())
        body.append(self.pick)
        body.append(Gtk.Label(label=cat.t("window.report.file_name"), xalign=0, css_classes=[SECTION]))
        self.name = Gtk.Entry(text=cat.t("window.report.default_name"), max_length=wm.MAX_REPORT_FILE_NAME, hexpand=True, width_chars=40, activates_default=True)
        a11y.name(self.name, cat.t("window.report.file_name"))
        body.append(self.name)
        self.dialog.get_content_area().append(body)
        self.dialog.set_default_size(sizing.px(560), sizing.px(320))
        self.cancel = self.dialog.add_button(cat.t("window.dialog.cancel"), Gtk.ResponseType.CANCEL)
        self.accept = self.dialog.add_button(cat.t("window.report.save_go"), Gtk.ResponseType.OK)
        self.dialog.set_default_response(Gtk.ResponseType.CANCEL)
        for widget in (self.cancel, self.accept):
            widget.add_css_class("ack-button")
        a11y.name(self.pick, cat.t("window.report.choose_folder"))
        self._answered = False
        self.dialog.connect("response", self._on_response)
        self.dialog.connect("close-request", lambda _d: (self._on_response(self.dialog, Gtk.ResponseType.CANCEL), True)[1])

    def set_folder(self, path: str) -> None:
        self.folder = path
        self.folder_label.set_label(path or self.cat.t("window.report.folder_none"))

    def _choose(self) -> None:
        self.chooser = open_chooser(self.shell, self.dialog, self.cat.t("window.report.chooser"), True, self.set_folder)

    def _problems(self):
        problems, path = wm.check_report_save(self.cat, self.folder, self.name.get_text())
        return problems, None if problems else wm.report_args(self.fields, save_to=path)

    def _on_response(self, dialog: Gtk.Dialog, response: int) -> None:
        if self._answered:
            return
        if response == Gtk.ResponseType.OK:
            problems, command = self._problems()
            if problems:
                self.problems.set_label("\n".join([self.cat.t("window.form.problems_head")] + ["  " + p for p in problems]))
                self.problems.set_visible(True)
                return                                                     # stays open: nothing chosen is lost
            self._answered = True
            self._close(dialog)
            self.shell.run(command)
            return
        self._answered = True
        self._close(dialog)

    def _close(self, dialog: Gtk.Dialog) -> None:
        if self.shell.chooser is not None:                                 # a chooser still open goes with the form
            self.shell.chooser.destroy()
            self.shell.chooser = None
        self.chooser = None
        dialog.destroy()
        self.shell.form = None
        self.shell.dialog = None

    def present(self) -> None:
        self.shell.form = self
        self.shell.dialog = self.dialog
        self.dialog.present()
        self.name.grab_focus()


def open_save_report(shell, fields: wm.ReportFields) -> SaveReportForm:
    form = SaveReportForm(shell, fields)
    form.present()
    return form
