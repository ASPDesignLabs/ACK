# SPDX-License-Identifier: GPL-3.0-or-later
"""The two forms of the Projects page: a new project, and a project's details. A form is a dialog with fields; it decides nothing. When its button is pressed it asks core/windowmodel.py whether
the form is whole (the very rules and sentences of the terminal's `projects new` and `projects edit`), shows every problem in the form so that nothing typed is lost, and only when the form is
whole closes and hands the shell the words of the terminal command. That command then shows what it will do and asks once more, with Yes and No buttons, before anything is written."""
from __future__ import annotations

from typing import Callable, List, Optional, Sequence, Tuple

from ..core import windowmodel as wm
from ..core.project import HOW_GIVEN, MAX_NAME, MAX_NOTE, OWN, SOMEONE_ELSE, Project
from . import a11y, sizing
from .gtkload import Gtk

SECTION = "section-heading"


def _entry(label: str, value: str, limit: int, rows: Gtk.Box) -> Gtk.Entry:
    rows.append(Gtk.Label(label=label, xalign=0, wrap=True))
    field = Gtk.Entry(text=value, max_length=limit, hexpand=True, width_chars=40)
    a11y.name(field, label)
    rows.append(field)
    return field


class ProjectForm:
    """One dialog for both forms. `project` is None for a new project and the saved project for its details. Attributes are public so the headless tour can fill the fields and press the button."""

    def __init__(self, shell, project: Optional[Project], registry_voices: Sequence[str]):
        self.shell = shell
        self.cat = shell.cat
        self.project = project
        self.after: Optional[Callable[[int], None]] = None          # told the exit code of the command the form ends with
        self.voices = tuple(registry_voices)
        cat = self.cat
        title = cat.t("window.form.new_title") if project is None else cat.t("window.form.edit_title", name=project.name)
        self.dialog = Gtk.Dialog(title=title, transient_for=shell, modal=True, destroy_with_parent=True, css_classes=["ack-dialog"])
        body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, css_classes=["ack-dialog-body"])
        sizing.track(body, spacing=8, margin_top=12, margin_bottom=12, margin_start=12, margin_end=12)
        self.problems = Gtk.Label(label="", wrap=True, xalign=0, selectable=True, visible=False, max_width_chars=60, css_classes=["error-text"], accessible_role=Gtk.AccessibleRole.ALERT)
        body.append(self.problems)
        self.name = _entry(cat.t("window.form.name"), "" if project is None else project.name, MAX_NAME, body)
        self.hours = _entry(cat.t("window.form.hours"), "1" if project is None else wm.edit_fields_of(project).hours, 12, body)
        self.own: Optional[Gtk.CheckButton] = None
        self.other: Optional[Gtk.CheckButton] = None
        self.voice: Optional[Gtk.DropDown] = None
        if project is None:
            self._build_whose(body)
        self.consent_box = sizing.track(Gtk.Box(orientation=Gtk.Orientation.VERTICAL), spacing=8)
        self._build_consent(self.consent_box)
        body.append(self.consent_box)
        if project is None:
            self._build_voice(body)
        self.scroll = Gtk.ScrolledWindow(vexpand=True, hscrollbar_policy=Gtk.PolicyType.NEVER)
        self.scroll.set_child(body)
        self.dialog.get_content_area().append(self.scroll)
        tall = project is None or project.whose_voice == SOMEONE_ELSE                 # a window is not resized by what is shown later, so it starts as tall as the fullest form needs
        self.dialog.set_default_size(sizing.px(640), sizing.px(660 if tall else 360))
        self.cancel = self.dialog.add_button(cat.t("window.dialog.cancel"), Gtk.ResponseType.CANCEL)
        self.accept = self.dialog.add_button(cat.t("window.form.make") if project is None else cat.t("window.form.save"), Gtk.ResponseType.OK)
        self.dialog.set_default_response(Gtk.ResponseType.CANCEL)
        for widget in (self.cancel, self.accept):
            widget.add_css_class("ack-button")
        self._answered = False
        self.dialog.connect("response", self._on_response)
        self.dialog.connect("close-request", lambda _d: (self._on_response(self.dialog, Gtk.ResponseType.CANCEL), True)[1])
        self._show_consent()

    # ---------------------------------------------------------------- the parts

    def _build_whose(self, body: Gtk.Box) -> None:
        cat = self.cat
        body.append(Gtk.Label(label=cat.t("window.form.whose"), xalign=0, wrap=True))
        self.own = Gtk.CheckButton(label=cat.t("window.form.own"))
        self.other = Gtk.CheckButton(label=cat.t("window.form.someone_else"))
        self.other.set_group(self.own)
        self.own.connect("toggled", lambda _c: self._show_consent())
        self.other.connect("toggled", lambda _c: self._show_consent())
        body.append(self.own)
        body.append(self.other)

    def _build_consent(self, box: Gtk.Box) -> None:
        cat = self.cat
        project = self.project
        old = wm.edit_fields_of(project) if project is not None else wm.EditFields("", "1")
        box.append(Gtk.Label(label=cat.t("window.form.consent_heading"), xalign=0, css_classes=[SECTION]))
        box.append(Gtk.Label(label=cat.t("window.form.consent_hint"), xalign=0, wrap=True, max_width_chars=60))
        self.given_by = _entry(cat.t("project.consent.missing.given_by"), old.given_by, MAX_NOTE, box)
        self.what_to = _entry(cat.t("project.consent.missing.what_to"), old.what_to, MAX_NOTE, box)
        self.when = _entry(cat.t("project.consent.missing.when"), old.when, MAX_NOTE, box)
        self.withdraw = _entry(cat.t("project.consent.missing.withdraw"), old.withdraw, MAX_NOTE, box)
        box.append(Gtk.Label(label=cat.t("project.consent.missing.how_given"), xalign=0, wrap=True))
        self.how_names = [""] + list(HOW_GIVEN)
        self.how_given = Gtk.DropDown(model=Gtk.StringList.new([cat.t("window.form.how_given_none")] + [cat.t("project.how_given." + h) for h in HOW_GIVEN]))
        a11y.name(self.how_given, cat.t("project.consent.missing.how_given"))
        self.how_given.set_selected(self.how_names.index(old.how_given) if old.how_given in self.how_names else 0)
        box.append(self.how_given)
        self.how_other = _entry(cat.t("project.consent.missing.how_given_other"), old.how_given_other, MAX_NOTE, box)

    def _build_voice(self, body: Gtk.Box) -> None:
        cat = self.cat
        body.append(Gtk.Label(label=cat.t("window.form.voice"), xalign=0, wrap=True))
        self.voice = Gtk.DropDown(model=Gtk.StringList.new([cat.t("window.form.voice_later")] + list(self.voices)))
        a11y.name(self.voice, cat.t("window.form.voice"))
        body.append(self.voice)

    def _someone_else(self) -> bool:
        if self.project is not None:
            return self.project.whose_voice == SOMEONE_ELSE
        return self.other is not None and self.other.get_active()

    def _show_consent(self) -> None:
        self.consent_box.set_visible(self._someone_else())

    # ---------------------------------------------------------------- reading and answering

    def whose(self) -> str:
        if self.project is not None:
            return self.project.whose_voice
        if self.own is not None and self.own.get_active():
            return OWN
        if self.other is not None and self.other.get_active():
            return SOMEONE_ELSE
        return ""

    def _how(self) -> str:
        return self.how_names[self.how_given.get_selected()]

    def new_fields(self) -> wm.NewFields:
        voice = ""
        if self.voice is not None and self.voice.get_selected() > 0:
            voice = self.voices[self.voice.get_selected() - 1]
        return wm.NewFields(name=self.name.get_text(), whose=self.whose(), hours=self.hours.get_text(), given_by=self.given_by.get_text(), what_to=self.what_to.get_text(),
                            when=self.when.get_text(), withdraw=self.withdraw.get_text(), how_given=self._how(), how_given_other=self.how_other.get_text(), voice=voice)

    def edit_fields(self) -> wm.EditFields:
        old = wm.edit_fields_of(self.project)
        if not self._someone_else():
            return wm.EditFields(self.name.get_text(), self.hours.get_text(), old.given_by, old.what_to, old.when, old.withdraw, old.how_given, old.how_given_other)
        return wm.EditFields(self.name.get_text(), self.hours.get_text(), self.given_by.get_text(), self.what_to.get_text(), self.when.get_text(), self.withdraw.get_text(),
                             self._how(), self.how_other.get_text())

    def _problems(self) -> Tuple[Sequence[str], Optional[Tuple[str, List[str]]]]:
        """(what is wrong, the command when nothing is). For a project's details, a form with nothing different from what is saved is also something to say, not to run."""
        shell = self.shell
        if self.project is None:
            fields = self.new_fields()
            problems = wm.check_new(shell.services.home, shell.services.registry, self.cat, fields)
            return problems, None if problems else wm.new_args(fields)
        fields = self.edit_fields()
        problems, changed = wm.check_edit(self.project, self.cat, fields)
        if problems:
            return problems, None
        if not changed:
            return (self.cat.t("window.form.no_changes"),), None
        return (), wm.edit_args(self.project, fields)

    def _on_response(self, dialog: Gtk.Dialog, response: int) -> None:
        if self._answered:
            return
        if response == Gtk.ResponseType.OK:
            problems, command = self._problems()
            if problems:
                self.problems.set_label("\n".join([self.cat.t("window.form.problems_head")] + ["  " + p for p in problems]))
                self.problems.set_visible(True)
                self.scroll.get_vadjustment().set_value(0)                  # the problems are at the top: bring them into view
                return                                                     # stays open: nothing typed is lost
            self._answered = True
            dialog.destroy()
            self.shell.form = None
            self.shell.dialog = None
            self.shell.run(command, then=self.after)
            return
        self._answered = True
        dialog.destroy()
        self.shell.form = None
        self.shell.dialog = None

    def present(self) -> None:
        self.shell.form = self
        self.shell.dialog = self.dialog
        self.dialog.present()
        self.name.grab_focus()


def open_new(shell, after: Optional[Callable[[int], None]] = None) -> ProjectForm:
    form = ProjectForm(shell, None, wm.voice_choices(shell.services.registry))
    form.after = after
    form.present()
    return form


def open_edit(shell, project: Project, after: Optional[Callable[[int], None]] = None) -> ProjectForm:
    form = ProjectForm(shell, project, ())
    form.after = after
    form.present()
    return form
