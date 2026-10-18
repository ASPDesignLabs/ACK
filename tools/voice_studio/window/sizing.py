# SPDX-License-Identifier: GPL-3.0-or-later
"""Pixel values that are set from Python (spacing, margins, minimum sizes) follow the window's scale, the way the style sheet's lengths do (core/windowtheme.py).

A value is given once, at its 100% size, through `track`; the widget keeps the scaled number, and when the person changes the scale every live widget is set again. A widget that is destroyed
is forgotten. Nothing here reads or writes a file: the scale itself comes from the Look (window/theme.py).
"""
from __future__ import annotations

import weakref
from typing import Dict, Tuple

from .gtkload import Gtk

PROPERTIES = ("spacing", "column_spacing", "row_spacing", "margin_top", "margin_bottom", "margin_start", "margin_end", "width_request", "height_request", "min_content_height", "max_content_height", "min_content_width")

_scale = 1.0
_tracked: Dict[int, Tuple["weakref.ReferenceType", Dict[str, int]]] = {}


def px(value: float) -> int:
    """A length at the current scale, in whole pixels (0 stays 0, anything else is at least 1)."""
    if value <= 0:
        return int(value)
    return max(1, int(round(value * _scale)))


def scale() -> float:
    return _scale


def _apply(widget: Gtk.Widget, values: Dict[str, int]) -> None:
    """Set each property at the current scale. A scrolled window refuses a minimum height above the maximum it still holds (GTK prints a critical warning and keeps the old minimum), and a
    jump of the scale can put the new minimum above the old maximum; so when both are given the minimum is cleared first, the maximum is set, and the minimum is set last."""
    names = list(values)
    if "min_content_height" in values and "max_content_height" in values:
        widget.set_property("min-content-height", -1)
        names.remove("min_content_height")
        names.append("min_content_height")
    for name in names:
        widget.set_property(name.replace("_", "-"), px(values[name]))


def track(widget: Gtk.Widget, **values: int) -> Gtk.Widget:
    """Set these properties (given at 100%) now and every time the scale changes. Returns the widget so a call can be part of an expression."""
    for name in values:
        if name not in PROPERTIES:
            raise ValueError("not a size property: " + name)
    key = hash(widget)
    merged = dict(_tracked[key][1]) if key in _tracked else {}
    merged.update(values)
    _tracked[key] = (weakref.ref(widget, lambda _r, k=key: _tracked.pop(k, None)), merged)
    _apply(widget, values)
    return widget


def set_scale(percent: int) -> None:
    """Make every live tracked widget follow a new scale (100 is 1:1)."""
    global _scale
    _scale = max(0.5, percent / 100.0)
    for ref, values in list(_tracked.values()):
        widget = ref()
        if widget is not None:
            _apply(widget, values)


def count() -> int:
    return sum(1 for ref, _v in _tracked.values() if ref() is not None)
