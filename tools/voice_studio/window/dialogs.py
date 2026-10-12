# SPDX-License-Identifier: GPL-3.0-or-later
"""The window's questions. A confirmation shows what the flow said (the plan, the list of what goes), then the question, and two buttons: No (where the focus starts, so Enter and Escape
both mean no) and Yes. Nothing here decides anything; an answer other than Yes is a No."""
from __future__ import annotations

from typing import Callable, Optional, Sequence

from . import a11y, sizing
from .gtkload import Gtk


def _body(lines: Sequence[str], question: str) -> Gtk.Box:
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, css_classes=["ack-dialog-body"])
    sizing.track(box, spacing=10, margin_top=12, margin_bottom=12, margin_start=12, margin_end=12)
    if lines:
        text = Gtk.Label(label="\n".join(lines), wrap=True, xalign=0, selectable=True, max_width_chars=70)
        scroll = Gtk.ScrolledWindow(propagate_natural_height=True, hscrollbar_policy=Gtk.PolicyType.NEVER)
        sizing.track(scroll, min_content_height=60, max_content_height=320)
        scroll.set_child(text)
        box.append(scroll)
    box.append(Gtk.Label(label=question, wrap=True, xalign=0, selectable=True, max_width_chars=70, css_classes=["question-text"]))
    return box


def _buttons(dialog: Gtk.Dialog) -> None:
    """The dialog's own buttons wear the same look as every other button."""
    for response in (Gtk.ResponseType.CANCEL, Gtk.ResponseType.YES, Gtk.ResponseType.OK):
        widget = dialog.get_widget_for_response(response)
        if widget is not None:
            widget.add_css_class("ack-button")


def confirm(parent: Gtk.Window, title: str, lines: Sequence[str], question: str, yes: str, no: str, reply: Callable[[bool], None]) -> Gtk.Dialog:
    """Ask a yes-or-no question. `reply(True)` only for a Yes; closing the dialog any other way is `reply(False)`. Returns the dialog (the window keeps it so a test can answer it)."""
    dialog = Gtk.Dialog(title=title, transient_for=parent, modal=True, destroy_with_parent=True, css_classes=["ack-dialog"])
    dialog.get_content_area().append(_body(lines, question))
    dialog.add_button(no, Gtk.ResponseType.CANCEL)
    dialog.add_button(yes, Gtk.ResponseType.YES)
    dialog.set_default_response(Gtk.ResponseType.CANCEL)
    _buttons(dialog)
    answered = []

    def on_response(dlg: Gtk.Dialog, response: int) -> None:
        if answered:
            return
        answered.append(True)
        dlg.destroy()
        reply(response == Gtk.ResponseType.YES)

    dialog.connect("response", on_response)
    dialog.connect("close-request", lambda dlg: (on_response(dlg, Gtk.ResponseType.CANCEL), True)[1])
    dialog.present()
    no_button = dialog.get_widget_for_response(Gtk.ResponseType.CANCEL)
    if no_button is not None:
        no_button.grab_focus()
    return dialog


def entry(parent: Gtk.Window, title: str, prompt: str, initial: str, ok: str, cancel: str, limit: int, reply: Callable[[Optional[str]], None]) -> Gtk.Dialog:
    """Ask for a line of text. `reply(text)` for the OK button or Enter, `reply(None)` for anything else. The text is whatever is in the field; the flow that receives it cleans it."""
    dialog = Gtk.Dialog(title=title, transient_for=parent, modal=True, destroy_with_parent=True, css_classes=["ack-dialog"])
    field = Gtk.Entry(text=initial, max_length=limit, activates_default=True, hexpand=True)
    a11y.name(field, prompt)
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, css_classes=["ack-dialog-body"])
    sizing.track(box, spacing=10, margin_top=12, margin_bottom=12, margin_start=12, margin_end=12)
    box.append(Gtk.Label(label=prompt, wrap=True, xalign=0, max_width_chars=60, css_classes=["question-text"]))
    box.append(field)
    dialog.get_content_area().append(box)
    dialog.add_button(cancel, Gtk.ResponseType.CANCEL)
    dialog.add_button(ok, Gtk.ResponseType.OK)
    dialog.set_default_response(Gtk.ResponseType.OK)
    _buttons(dialog)
    answered = []

    def on_response(dlg: Gtk.Dialog, response: int) -> None:
        if answered:
            return
        answered.append(True)
        text = field.get_text()
        dlg.destroy()
        reply(text if response == Gtk.ResponseType.OK else None)

    dialog.connect("response", on_response)
    dialog.connect("close-request", lambda dlg: (on_response(dlg, Gtk.ResponseType.CANCEL), True)[1])
    dialog.present()
    field.grab_focus()
    return dialog
