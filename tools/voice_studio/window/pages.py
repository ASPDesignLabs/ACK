# SPDX-License-Identifier: GPL-3.0-or-later
"""The pages. Each builds its widgets from a view in core/windowmodel.py and, when a button is pressed, hands the shell the words of the terminal command that button stands for.
A page keeps no state of its own that the files do not have: `refresh` reads again and rebuilds."""
from __future__ import annotations

from typing import Callable, List, Optional, Tuple

from ..core import showfolder
from ..core import windowmodel as wm
from ..core.text import size_text
from . import a11y
from .gtkload import GLib, Gtk

MINUTES_DEFAULT = 25
MINUTES_MAX = 240
REFRESH_SECONDS = 10                                      # while a round trains the list is read again by itself; reading changes nothing and nothing is started


def clear(box: Gtk.Box) -> None:
    """Remove everything in the box. If the keyboard focus is on something that is about to go (a selectable text or a button), the focus is put down first: GTK 4.6 otherwise asks about a
    widget that no longer exists and prints a warning."""
    root = box.get_root()
    focused = root.get_focus() if root is not None else None
    if focused is not None and focused.is_ancestor(box):
        root.set_focus(None)
    child = box.get_first_child()
    while child is not None:
        following = child.get_next_sibling()
        box.remove(child)
        child = following


def text(label: str, css: Tuple[str, ...] = (), selectable: bool = False) -> Gtk.Label:
    return Gtk.Label(label=label, wrap=True, xalign=0, selectable=selectable, max_width_chars=90, css_classes=list(css))


def button(label: str, on_click: Callable[[], None], name: str = "", sensitive: bool = True) -> Gtk.Button:
    widget = Gtk.Button(label=label, sensitive=sensitive)
    widget.connect("clicked", lambda _b: on_click())
    if name:
        a11y.name(widget, name)
    return widget


class Page:
    """A page is a box inside a scrolled window. `build` makes the part that does not change, `refresh` the part that does."""

    def __init__(self, shell):
        self.shell = shell
        self.cat = shell.cat
        self.content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10, margin_top=14, margin_bottom=14, margin_start=18, margin_end=18)
        self.widget = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER, hexpand=True, vexpand=True)
        self.widget.set_child(self.content)
        self.build()

    def build(self) -> None:
        raise NotImplementedError

    def refresh(self) -> None:
        raise NotImplementedError

    def need_project(self) -> bool:
        """Show the 'open a project first' line instead of the page when there is none. True when there is a project."""
        if self.shell.project_id is not None:
            return True
        clear(self.content)
        self.content.append(text(self.cat.t("window.no_project")))
        return False


class ProjectsPage(Page):
    def build(self) -> None:
        self.selected: Optional[str] = None
        self.refresh()

    def refresh(self) -> None:
        cat, services = self.cat, self.shell.services
        clear(self.content)
        view = wm.projects_view(services.home, cat)
        self.content.append(text(cat.t("window.nav.projects"), ("page-heading",)))
        self.content.append(text(cat.t("projects.where", folder=view.folder), selectable=True))
        if not view.items and not view.problems:
            self.content.append(text(cat.t("window.projects.none", command="python3 -m voice_studio.projects new"), selectable=True))
        self.open_button = button(cat.t("window.projects.open"), self._open, sensitive=False)
        self.rows = Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE, css_classes=["boxed-list"])
        a11y.name(self.rows, cat.t("window.nav.projects"))
        self.ids: List[str] = []
        for item in view.items:
            row = Gtk.ListBoxRow(activatable=True)
            row.set_child(text(item.line, ("row-box",)))
            a11y.name(row, item.line)
            self.rows.append(row)
            self.ids.append(item.id)
        self.rows.connect("row-selected", self._selected)
        self.rows.connect("row-activated", lambda _l, _r: self._open())
        if view.items:
            self.content.append(self.rows)
            self.content.append(self.open_button)
        for problem in view.problems:
            self.content.append(text(problem, selectable=True))
        current = self.shell.project_id
        if current in self.ids:
            self.rows.select_row(self.rows.get_row_at_index(self.ids.index(current)))

    def _selected(self, _box: Gtk.ListBox, row: Optional[Gtk.ListBoxRow]) -> None:
        self.selected = self.ids[row.get_index()] if row is not None else None
        self.open_button.set_sensitive(self.selected is not None)

    def _open(self) -> None:
        if self.selected is not None:
            self.shell.open_project(self.selected)


class RoundsPage(Page):
    """The list is rebuilt on every refresh; the form that starts a round is built once and updated in place, so what the person picked (the training set, the minutes) survives a refresh
    and a drop-down is never destroyed and rebuilt under them."""

    def build(self) -> None:
        cat = self.cat
        self.timer = 0
        self.dynamic = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.start_box = self._build_start_box()
        self.content.append(self.dynamic)
        self.content.append(self.start_box)
        self.refresh()

    def _build_start_box(self) -> Gtk.Box:
        cat = self.cat
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box.append(text(cat.t("window.rounds.start_heading"), ("section-heading",)))
        self.no_sets = text(cat.t("window.rounds.no_sets"), selectable=True)
        box.append(self.no_sets)
        self.form = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.set_names = Gtk.StringList.new([])
        self.choices = Gtk.DropDown(model=self.set_names)
        a11y.name(self.choices, cat.t("window.rounds.set_label"))
        self.minutes = Gtk.SpinButton.new_with_range(1, MINUTES_MAX, 1)
        self.minutes.set_value(MINUTES_DEFAULT)
        a11y.name(self.minutes, cat.t("window.rounds.minutes_label"))
        self.start = button(cat.t("window.rounds.start"), self._start)
        for widget in (text(cat.t("window.rounds.set_label")), self.choices, text(cat.t("window.rounds.minutes_label")), self.minutes, self.start):
            self.form.append(widget)
        box.append(self.form)
        return box

    def _update_start_box(self, view: wm.RoundsView) -> None:
        names = [self.set_names.get_string(i) for i in range(self.set_names.get_n_items())]
        if names != list(view.sets):
            kept = names[self.choices.get_selected()] if names and self.choices.get_selected() < len(names) else None
            self.set_names.splice(0, len(names), list(view.sets))
            if kept in view.sets:
                self.choices.set_selected(view.sets.index(kept))
        self.no_sets.set_visible(not view.sets)
        self.form.set_visible(bool(view.sets))
        self.start.set_sensitive(view.can_start)

    def _start(self) -> None:
        if self.shell.project_id is None or self.set_names.get_n_items() == 0:
            return
        chosen = self.set_names.get_string(self.choices.get_selected())
        self.shell.run(wm.start_args(self.shell.project_id, chosen, int(self.minutes.get_value())))

    def refresh(self) -> None:
        cat, shell = self.cat, self.shell
        clear(self.dynamic)
        has_project = shell.project_id is not None
        self.start_box.set_visible(False)
        if not has_project:
            self.dynamic.append(text(cat.t("window.no_project")))
            return
        view = wm.rounds_view(shell.services.home, shell.project_id, cat)
        if view is None:
            self.dynamic.append(text(cat.t("window.no_project")))
            return
        self.dynamic.append(text(cat.t("window.rounds.heading", name=view.project_name), ("page-heading",)))
        if view.problem:
            self.dynamic.append(text(view.problem, selectable=True))
            return
        for line in view.summary:
            self.dynamic.append(text(line, selectable=True))
        pid = shell.project_id
        controls = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        controls.append(button(cat.t("window.rounds.refresh"), self.refresh))
        if view.back_target is not None:
            controls.append(button(cat.t("window.rounds.back", target=view.back_target), lambda: shell.run(wm.back_args(pid))))
        if view.running is not None:
            controls.append(button(cat.t("window.rounds.stop"), lambda: shell.run(wm.stop_args(pid))))
        self.dynamic.append(controls)
        rows = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE, css_classes=["boxed-list"])
        a11y.name(rows, cat.t("window.rounds.list_name"))
        for item in view.items:
            rows.append(self._row(item, pid))
        if view.items:
            self.dynamic.append(rows)
        self._update_start_box(view)
        self.start_box.set_visible(True)
        self._arm_refresh(view.running is not None)

    def _row(self, item: wm.RoundItem, pid: str) -> Gtk.ListBoxRow:
        cat, shell = self.cat, self.shell
        row = Gtk.ListBoxRow(activatable=False, selectable=False)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4, css_classes=["row-box"])
        box.append(text(item.lines[0], ("round-head",), selectable=True))
        if len(item.lines) > 1:
            box.append(text("\n".join(line.strip() for line in item.lines[1:]), selectable=True))
        actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        if item.can_choose:
            actions.append(button(cat.t("window.rounds.choose"), lambda n=item.number: shell.run(wm.choose_args(pid, n)), cat.t("window.rounds.choose_name", number=item.number)))
        actions.append(button(cat.t("window.rounds.note"), lambda n=item.number, current=item.note: self._write_note(pid, n, current), cat.t("window.rounds.note_name", number=item.number)))
        box.append(actions)
        row.set_child(box)
        return row

    def _write_note(self, pid: str, number: int, current: str) -> None:
        def got(note: Optional[str]) -> None:
            if note is not None:
                self.shell.run(wm.note_args(pid, number, note))
        self.shell.show_entry(self.cat.t("window.note.prompt", number=number), current, got, limit=wm.MAX_NOTE_SHOWN)

    def _arm_refresh(self, running: bool) -> None:
        if self.timer:
            GLib.source_remove(self.timer)
            self.timer = 0
        if running:
            self.timer = GLib.timeout_add_seconds(REFRESH_SECONDS, self._tick)

    def _tick(self) -> bool:
        self.timer = 0
        if self.shell.project_id is None:
            return False
        if not self.shell.busy and self.shell.stack.get_visible_child() is self.widget:
            self.refresh()
        else:
            self._arm_refresh(True)
        return False


class VoiceFilePage(Page):
    def build(self) -> None:
        self.refresh()

    def refresh(self) -> None:
        cat, shell = self.cat, self.shell
        clear(self.content)
        if not self.need_project():
            return
        view = wm.voicefiles_view(shell.services.home, shell.project_id, cat)
        if view is None:
            self.content.append(text(cat.t("window.no_project")))
            return
        project = wm.find_project(shell.services.home, shell.project_id)
        self.content.append(text(cat.t("window.voicefile.heading", name=project.name if project else ""), ("page-heading",)))
        self.content.append(text(cat.t("window.voicefile.intro"), selectable=True))
        pid = shell.project_id
        self.content.append(button(cat.t("window.voicefile.make"), lambda: shell.run(wm.make_args(pid))))
        self.content.append(text(cat.t("window.voicefile.made_heading"), ("section-heading",)))
        if not view.items:
            self.content.append(text(cat.t("voicefile.list.none"), selectable=True))
            return
        rows = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE, css_classes=["boxed-list"])
        a11y.name(rows, cat.t("window.voicefile.made_heading"))
        for item in view.items:
            row = Gtk.ListBoxRow(activatable=False, selectable=False)
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4, css_classes=["row-box"])
            box.append(text(item.line, ("round-head",), selectable=True))
            box.append(text(item.zip_path, selectable=True))
            actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            actions.append(button(cat.t("window.voicefile.show"), lambda i=item: self._show(i), cat.t("window.voicefile.show_name", name=item.name)))
            actions.append(button(cat.t("window.voicefile.copy"), lambda i=item: self._copy(i), cat.t("window.voicefile.copy_name", name=item.name)))
            box.append(actions)
            row.set_child(box)
            rows.append(row)
        self.content.append(rows)

    def _show(self, item: wm.VoiceFileItem) -> None:
        """Open the folder in the computer's file manager (on WSL, Windows File Explorer). It only looks; if it cannot be opened, the path is said so it can be copied."""
        if showfolder.open_folder(item.folder, self.shell.services.system):
            self.shell.set_result(0, (self.cat.t("window.voicefile.shown", name=item.name),))
        else:
            self.shell.set_result(1, (self.cat.t("window.voicefile.show_failed", path=item.folder),))

    def _copy(self, item: wm.VoiceFileItem) -> None:
        self.shell.get_clipboard().set(item.zip_path)
        self.shell.set_result(0, (self.cat.t("window.voicefile.copied", name=item.name),))


class FreePage(Page):
    def build(self) -> None:
        self.refresh()

    def refresh(self) -> None:
        cat, shell = self.cat, self.shell
        clear(self.content)
        if not self.need_project():
            return
        view = wm.free_view(shell.services.home, shell.project_id, cat)
        if view is None:
            self.content.append(text(cat.t("window.no_project")))
            return
        project = wm.find_project(shell.services.home, shell.project_id)
        self.content.append(text(cat.t("window.free.heading", name=project.name if project else ""), ("page-heading",)))
        if view.problem:
            self.content.append(text(view.problem, selectable=True))
            return
        self.content.append(text(cat.t("window.free.intro"), selectable=True))
        self.checks: List[Tuple[Gtk.CheckButton, wm.FreeItem]] = []
        if not view.items:
            self.content.append(text(cat.t("rounds.free.nothing"), selectable=True))
        for item in view.items:
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10, css_classes=["row-box"])
            check = Gtk.CheckButton(valign=Gtk.Align.START)
            a11y.name(check, item.line)
            check.connect("toggled", lambda _c: self._update())
            label = text(item.line, selectable=False)
            click = Gtk.GestureClick()                         # GTK 4.6 has no CheckButton.set_child: a click on the words ticks the box
            click.connect("released", lambda _g, _n, _x, _y, c=check: c.set_active(not c.get_active()))
            label.add_controller(click)
            row.append(check)
            row.append(label)
            self.content.append(row)
            self.checks.append((check, item))
        self.total = text("")
        self.remove = button(cat.t("window.free.remove"), self._remove, sensitive=False)
        self.content.append(self.total)
        self.content.append(self.remove)
        for note in view.notes:
            self.content.append(text(note, selectable=True))
        self._update()

    def ticked(self) -> List[wm.FreeItem]:
        return [item for check, item in self.checks if check.get_active()]

    def _update(self) -> None:
        picked = self.ticked()
        self.remove.set_sensitive(bool(picked))
        self.total.set_label(self.cat.t("window.free.ticked", size=size_text(sum(i.bytes for i in picked))) if picked else self.cat.t("window.free.none_ticked"))

    def _remove(self) -> None:
        picked = self.ticked()
        if picked:
            self.shell.run(wm.free_args(self.shell.project_id, picked))
