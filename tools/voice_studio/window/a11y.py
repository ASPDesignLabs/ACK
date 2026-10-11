# SPDX-License-Identifier: GPL-3.0-or-later
"""Accessible names (plan P6: every control has a name and a role). GTK 4.6 has no call that reads back the name it computed, so the names this package gives are kept here and the headless
check (selftest.py) asks this module whether every control has one. A button or a check button with a label of its own already has a name."""
from __future__ import annotations

from typing import Dict, Iterator, List

from .gtkload import Gtk

_GIVEN: Dict[int, str] = {}                  # by the widget's address, not the Python object: PyGObject makes a new object for the same widget once the old one is dropped, and a weak key would lose the name

# widgets that are controls (the thing a person acts on); widgets that are made of other widgets are not looked into
CONTROLS = (Gtk.Button, Gtk.CheckButton, Gtk.Entry, Gtk.SpinButton, Gtk.DropDown, Gtk.Switch, Gtk.ListBoxRow)
COMPOSITES = (Gtk.DropDown, Gtk.SpinButton, Gtk.Entry, Gtk.StackSidebar, Gtk.ProgressBar)


def name(widget: Gtk.Widget, label: str, description: str = "") -> Gtk.Widget:
    """Give a control its accessible name (and, if there is one, a longer description). Returns the widget so a call can be part of an expression."""
    widget.update_property([Gtk.AccessibleProperty.LABEL], [label])
    if description:
        widget.update_property([Gtk.AccessibleProperty.DESCRIPTION], [description])
    key = hash(widget)
    if key not in _GIVEN:
        widget.connect("destroy", lambda _w, k=key: _GIVEN.pop(k, None))
    _GIVEN[key] = label
    return widget


def walk(root: Gtk.Widget) -> Iterator[Gtk.Widget]:
    yield root
    if isinstance(root, COMPOSITES):
        return
    child = root.get_first_child()
    while child is not None:
        yield from walk(child)
        child = child.get_next_sibling()


def label_of(widget: Gtk.Widget) -> str:
    given = _GIVEN.get(hash(widget))
    if given:
        return given
    if isinstance(widget, (Gtk.Button, Gtk.CheckButton)):
        return widget.get_label() or ""
    return ""


def unnamed_controls(root: Gtk.Widget) -> List[str]:
    """Every control under `root` that has no accessible name, described by its type (empty when the window is in order)."""
    found = []
    for widget in walk(root):
        if isinstance(widget, CONTROLS) and not label_of(widget):
            if isinstance(widget, Gtk.ListBoxRow) and not widget.get_activatable():
                continue                                    # a row that cannot be activated is not a control
            found.append(type(widget).__name__)
    return found
