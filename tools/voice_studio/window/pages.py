# SPDX-License-Identifier: GPL-3.0-or-later
"""The pages. Each builds its widgets from a view in core/windowmodel.py and, when a button is pressed, hands the shell the words of the terminal command that button stands for.
A page keeps no state of its own that the files do not have: `refresh` reads again and rebuilds."""
from __future__ import annotations

from typing import Callable, List, Optional, Tuple

from ..core import showfolder
from ..core import windowmodel as wm
from ..core import windowprefs as wp
from ..core import windowtheme as wt
from ..core.text import size_text
from . import a11y, forms, sizing
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
    widget = Gtk.Button(label=label, sensitive=sensitive, css_classes=["ack-button"], halign=Gtk.Align.START)
    widget.connect("clicked", lambda _b: on_click())
    if name:
        a11y.name(widget, name)
    return widget


def action_bar(buttons: List[Gtk.Button]) -> Gtk.FlowBox:
    """Buttons side by side that wrap onto the next line when the page is too narrow (a longer word in another language, a larger text size or scale). A page cannot scroll sideways, so a
    row of buttons that is wider than the page would be squeezed below its smallest size. The wrapper boxes GTK adds take no keyboard focus of their own: Tab goes from button to button."""
    bar = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, homogeneous=False, min_children_per_line=1, max_children_per_line=8, hexpand=True)          # it fills the page's width: a wrapping box measured at a narrower width than it is given would overlap what is under it
    sizing.track(bar, column_spacing=8, row_spacing=8)
    for widget in buttons:
        bar.insert(widget, -1)
        bar.get_last_child().set_focusable(False)
    return bar


class Page:
    """A page is a box inside a scrolled window. `build` makes the part that does not change, `refresh` the part that does."""

    def __init__(self, shell):
        self.shell = shell
        self.cat = shell.cat
        self.content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        sizing.track(self.content, spacing=10, margin_top=16, margin_bottom=16, margin_start=20, margin_end=20)
        self.widget = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER, hexpand=True, vexpand=True, css_classes=["ack-page"])
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
    """The projects in use, then (when asked for) the ones put away. A row is chosen, then a button under the list acts on it. Every change is a terminal command that shows what it will do and
    asks first; nothing here removes or changes a file by itself."""

    def build(self) -> None:
        self.selected: Optional[str] = None
        self.selected_away = False
        self.show_away = False
        self.refresh()

    def _list(self, items, away: bool) -> Gtk.ListBox:
        rows = Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE, css_classes=["boxed-list"])
        a11y.name(rows, self.cat.t("window.projects.away_heading") if away else self.cat.t("window.nav.projects"))
        ids: List[str] = []
        for item in items:
            row = Gtk.ListBoxRow(activatable=True)
            row.set_child(text(item.line, ("row-box",)))
            a11y.name(row, item.line)
            rows.append(row)
            ids.append(item.id)
        rows.connect("row-selected", lambda _l, row, a=away, i=ids: self._chosen(row, a, i))
        if not away:
            rows.connect("row-activated", lambda _l, _r: self._open())
        return rows

    def refresh(self) -> None:
        cat, services = self.cat, self.shell.services
        clear(self.content)
        view = wm.projects_view(services.home, cat)
        in_use = [i.id for i in view.items]
        away_ids = [i.id for i in view.away]
        if self.selected is not None and self.selected not in (away_ids if self.selected_away else in_use):
            self.selected = None
        self.rows: Optional[Gtk.ListBox] = None
        self.away_rows: Optional[Gtk.ListBox] = None
        self.content.append(text(cat.t("window.nav.projects"), ("page-heading",)))
        self.content.append(text(cat.t("projects.where", folder=view.folder), selectable=True))
        self.new_button = button(cat.t("window.projects.new"), self._new)
        self.content.append(self.new_button)
        if not view.items and not view.problems and not view.away:
            self.content.append(text(cat.t("window.projects.none"), selectable=True))
        self.actions: List[Tuple[Gtk.Button, bool]] = []                 # (button, acts on a project in use)
        if view.items:
            self.rows = self._list(view.items, False)
            self.content.append(self.rows)
            self.content.append(text(cat.t("window.projects.pick"), ("dim-text",)))
            made = []
            for label, handler in ((cat.t("window.projects.open"), self._open), (cat.t("window.projects.edit"), self._edit), (cat.t("window.projects.away"), self._put_away),
                                   (cat.t("window.projects.show_folder"), self._show_folder), (cat.t("window.projects.delete"), self._delete)):
                action = button(label, handler, sensitive=False)
                made.append(action)
                self.actions.append((action, True))
            self.content.append(action_bar(made))
            if self.selected is not None and not self.selected_away:
                self.rows.select_row(self.rows.get_row_at_index(in_use.index(self.selected)))
            elif self.shell.project_id in in_use and self.selected is None:
                self.rows.select_row(self.rows.get_row_at_index(in_use.index(self.shell.project_id)))
        self.away_toggle = None
        if view.away:
            self.away_toggle = Gtk.CheckButton(label=cat.t("window.projects.show_away"), active=self.show_away)
            self.away_toggle.connect("toggled", self._toggled)
            self.content.append(self.away_toggle)
            if self.show_away:
                self.content.append(text(cat.t("window.projects.away_heading"), ("section-heading",)))
                self.away_rows = self._list(view.away, True)
                self.content.append(self.away_rows)
                made = []
                for label, handler in ((cat.t("window.projects.back"), self._bring_back), (cat.t("window.projects.delete"), self._delete)):
                    action = button(label, handler, sensitive=False)
                    made.append(action)
                    self.actions.append((action, False))
                self.content.append(action_bar(made))
                if self.selected is not None and self.selected_away:
                    self.away_rows.select_row(self.away_rows.get_row_at_index(away_ids.index(self.selected)))
        for problem in view.problems:
            self.content.append(text(problem, selectable=True))
        self._update_actions()

    # ---------------------------------------------------------------- choosing

    def select(self, project_id: str) -> None:
        """Choose a row by its project (used after a new project is made)."""
        self.selected, self.selected_away = project_id, False
        self.refresh()

    def _chosen(self, row: Optional[Gtk.ListBoxRow], away: bool, ids: List[str]) -> None:
        if row is None:
            return                                                  # a list was cleared because the other one was chosen from
        self.selected, self.selected_away = ids[row.get_index()], away
        other = self.rows if away else self.away_rows
        if other is not None:
            other.unselect_all()
        self._update_actions()

    def _update_actions(self) -> None:
        for widget, for_use in self.actions:
            widget.set_sensitive(self.selected is not None and self.selected_away != for_use)

    def _toggled(self, check: Gtk.CheckButton) -> None:
        self.show_away = check.get_active()
        if not self.show_away and self.selected_away:
            self.selected = None
        self.refresh()

    # ---------------------------------------------------------------- what the buttons do

    def _name_of(self, project_id: str) -> str:
        project = wm.find_project(self.shell.services.home, project_id, include_away=True)
        return project.name if project else project_id

    def _open(self) -> None:
        if self.selected is not None and not self.selected_away:
            self.shell.open_project(self.selected)

    def _new(self) -> None:
        before = {i.id for i in wm.projects_view(self.shell.services.home, self.cat).items} | {i.id for i in wm.projects_view(self.shell.services.home, self.cat).away}

        def made(code: int) -> None:
            if code != 0:
                return
            now = [i.id for i in wm.projects_view(self.shell.services.home, self.cat).items if i.id not in before]
            if now:
                self.select(now[0])
        forms.open_new(self.shell, made)

    def _edit(self) -> None:
        project = wm.find_project(self.shell.services.home, self.selected) if self.selected else None
        if project is not None:
            forms.open_edit(self.shell, project)

    def _put_away(self) -> None:
        if self.selected is not None and not self.selected_away:
            self.shell.run(wm.archive_args(self.selected))

    def _bring_back(self) -> None:
        if self.selected is not None and self.selected_away:
            self.shell.run(wm.unarchive_args(self.selected))

    def _delete(self) -> None:
        if self.selected is not None:
            self.shell.run(wm.delete_args(self.selected))

    def _show_folder(self) -> None:
        """Open the project's folder in the computer's file manager, so what is in it can be copied before anything is removed. It only looks."""
        if self.selected is None:
            return
        folder = self.shell.services.home.projects + "/" + self.selected
        if showfolder.open_folder(folder, self.shell.services.system):
            self.shell.set_result(0, (self.cat.t("window.projects.folder_shown", name=self._name_of(self.selected)),))
        else:
            self.shell.set_result(1, (self.cat.t("window.projects.folder_failed", path=folder),))


class RoundsPage(Page):
    """The list is rebuilt on every refresh; the form that starts a round is built once and updated in place, so what the person picked (the training set, the minutes) survives a refresh
    and a drop-down is never destroyed and rebuilt under them."""

    def build(self) -> None:
        cat = self.cat
        self.timer = 0
        self.dynamic = sizing.track(Gtk.Box(orientation=Gtk.Orientation.VERTICAL), spacing=10)
        self.start_box = self._build_start_box()
        self.content.append(self.dynamic)
        self.content.append(self.start_box)
        self.refresh()

    def _build_start_box(self) -> Gtk.Box:
        cat = self.cat
        box = sizing.track(Gtk.Box(orientation=Gtk.Orientation.VERTICAL), spacing=10)
        box.append(text(cat.t("window.rounds.start_heading"), ("section-heading",)))
        self.no_sets = text(cat.t("window.rounds.no_sets"), selectable=True)
        box.append(self.no_sets)
        self.form = sizing.track(Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL), spacing=10)
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
        controls = sizing.track(Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL), spacing=8)
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
        box = sizing.track(Gtk.Box(orientation=Gtk.Orientation.VERTICAL, css_classes=["row-box"]), spacing=4)
        box.append(text(item.lines[0], ("round-head",), selectable=True))
        if len(item.lines) > 1:
            box.append(text("\n".join(line.strip() for line in item.lines[1:]), selectable=True))
        actions = sizing.track(Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL), spacing=8)
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
            box = sizing.track(Gtk.Box(orientation=Gtk.Orientation.VERTICAL, css_classes=["row-box"]), spacing=4)
            box.append(text(item.line, ("round-head",), selectable=True))
            box.append(text(item.zip_path, selectable=True))
            actions = sizing.track(Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL), spacing=8)
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
            row = sizing.track(Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, css_classes=["row-box"]), spacing=10)
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


ACCENT_WORDS = {"cyan": "window.display.accent_cyan", "red": "window.display.accent_red", "green": "window.display.accent_green", "orange": "window.display.accent_orange",
                "purple": "window.display.accent_purple", "yellow": "window.display.accent_yellow", "blue": "window.display.accent_blue", "magenta": "window.display.accent_magenta",
                "lime": "window.display.accent_lime", "pink": "window.display.accent_pink"}


class DisplayPage(Page):
    """The display choices. Built once and updated in place (a choice does not rebuild the page under the person's keyboard focus). Every change is shown at once; the first one asks whether to keep
    the choices in a small file (Shell.change_look), and nothing is written before the person says yes."""

    def build(self) -> None:
        cat, shell = self.cat, self.shell
        self.appearance = shell.appearance
        self._updating = False
        c = self.content
        c.append(text(cat.t("window.display.heading"), ("page-heading",)))
        c.append(text(cat.t("window.display.intro")))

        c.append(text(cat.t("window.display.colours_heading"), ("section-heading",)))
        row = sizing.track(Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL), spacing=8)
        self.theme_buttons = {}
        group = None
        for key, label_key, name_key in (("ack", "window.display.theme_ack", "window.display.theme_ack_name"), ("system", "window.display.theme_system", "window.display.theme_system_name")):
            widget = Gtk.ToggleButton(label=cat.t(label_key), css_classes=["ack-button"])
            if group is not None:
                widget.set_group(group)
            group = group or widget
            a11y.name(widget, cat.t(name_key))
            widget.connect("toggled", lambda w, k=key: self._pick_theme(k, w))
            row.append(widget)
            self.theme_buttons[key] = widget
        c.append(row)
        self.system_note = text(cat.t("window.display.theme_system_note"), ("dim-text",))
        c.append(self.system_note)

        self.accent_box = sizing.track(Gtk.Box(orientation=Gtk.Orientation.VERTICAL), spacing=10)
        self.accent_box.append(text(cat.t("window.display.accent_heading"), ("section-heading",)))
        swatches = sizing.track(Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL), spacing=8)
        self.swatches = []
        group = None
        for index, (name, _color) in enumerate(wt.ACCENTS):
            widget = Gtk.ToggleButton(css_classes=["swatch", "swatch-" + name])
            if group is not None:
                widget.set_group(group)
            group = group or widget
            a11y.name(widget, cat.t("window.display.accent_name", name=cat.t(ACCENT_WORDS[name])))
            widget.connect("toggled", lambda w, i=index: self._pick_accent(i, w))
            swatches.append(widget)
            self.swatches.append(widget)
        self.accent_box.append(swatches)
        c.append(self.accent_box)

        c.append(text(cat.t("window.display.text_heading"), ("section-heading",)))
        c.append(self._stepper("text"))
        c.append(text(cat.t("window.display.scale_heading"), ("section-heading",)))
        c.append(text(cat.t("window.display.scale_note"), ("dim-text",)))
        c.append(self._stepper("scale"))

        c.append(text(cat.t("window.display.keep_heading"), ("section-heading",)))
        self.status = text("", selectable=True)
        c.append(self.status)
        actions = sizing.track(Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL), spacing=8)
        self.keep = button(cat.t("window.display.keep_button"), self._keep)
        self.forget = button(cat.t("window.display.forget_button"), shell.ask_to_forget)
        self.reset = button(cat.t("window.display.reset_button"), lambda: shell.change_look(wt.Look(theme=self.appearance.look.theme)))
        for widget in (self.keep, self.forget, self.reset):
            actions.append(widget)
        c.append(actions)
        self.appearance.listen(self.refresh)
        self.refresh()

    def _stepper(self, kind: str) -> Gtk.Box:
        """A smaller button, the value, a bigger button."""
        cat = self.cat
        box = sizing.track(Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, valign=Gtk.Align.CENTER), spacing=10)
        names = {"text": ("window.display.smaller_text_name", "window.display.bigger_text_name"), "scale": ("window.display.smaller_scale_name", "window.display.bigger_scale_name")}[kind]
        smaller = button("−", lambda: self._step(kind, -1), cat.t(names[0]))
        bigger = button("+", lambda: self._step(kind, 1), cat.t(names[1]))
        value = Gtk.Label(label="", css_classes=["round-head"], width_chars=8)
        sizing.track(value, margin_start=4, margin_end=4)
        box.append(smaller)
        box.append(value)
        box.append(bigger)
        setattr(self, kind + "_smaller", smaller)
        setattr(self, kind + "_bigger", bigger)
        setattr(self, kind + "_value", value)
        return box

    def _step(self, kind: str, direction: int) -> None:
        look = self.appearance.look
        if kind == "text":
            look = look.bigger_text() if direction > 0 else look.smaller_text()
        else:
            look = look.bigger_scale() if direction > 0 else look.smaller_scale()
        self.shell.change_look(look)

    def _pick_theme(self, key: str, widget: Gtk.ToggleButton) -> None:
        if not self._updating and widget.get_active() and self.appearance.look.theme != key:
            self.shell.change_look(wt.Look(key, self.appearance.look.accent, self.appearance.look.text_pt, self.appearance.look.scale_pct))

    def _pick_accent(self, index: int, widget: Gtk.ToggleButton) -> None:
        if not self._updating and widget.get_active() and self.appearance.look.accent != index:
            look = self.appearance.look
            self.shell.change_look(wt.Look(look.theme, index, look.text_pt, look.scale_pct))

    def _keep(self) -> None:
        if self.shell.dialog is None:
            self.shell.ask_to_keep()

    def refresh(self) -> None:
        look, cat = self.appearance.look, self.cat
        self._updating = True
        try:
            for key, widget in self.theme_buttons.items():
                widget.set_active(look.theme == key)
            for index, widget in enumerate(self.swatches):
                widget.set_active(look.accent == index)
        finally:
            self._updating = False
        self.accent_box.set_visible(look.theme == "ack")
        self.system_note.set_visible(look.theme == "system")
        self.text_value.set_label(cat.t("window.display.text_value", points=look.text_pt))
        self.text_smaller.set_sensitive(look.smaller_text() != look)
        self.text_bigger.set_sensitive(look.bigger_text() != look)
        self.scale_value.set_label(cat.t("window.display.scale_value", percent=look.scale_pct))
        self.scale_smaller.set_sensitive(look.smaller_scale() != look)
        self.scale_bigger.set_sensitive(look.bigger_scale() != look)
        kept = bool(wp.plan_forget(self.appearance.path)) and self.appearance.keeper.state == "kept"
        self.status.set_label(cat.t("window.display.status_kept", path=self.appearance.path) if kept else cat.t("window.display.status_session"))
        self.keep.set_visible(not kept)
        self.forget.set_visible(kept)
