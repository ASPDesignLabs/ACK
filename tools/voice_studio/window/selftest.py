# SPDX-License-Identifier: GPL-3.0-or-later
"""A headless tour of the window, for a virtual display (plan P6: a headless check of the accessible names; section 3: tests for the GTK edge).

`python3 -m voice_studio.window --selftest` builds the real window against whatever is under HOME, visits every page, checks that every control has an accessible name and that text is
12 pt or larger, then presses the real buttons: a Choose answered No and then Yes, a Free up space answered No, and a Make the voice file that is refused. It prints one JSON object of
checks and exits 0 when all hold. Run it only on a copy of a project (HOME set to a folder made for the test): Yes really changes the record of that project.
"""
from __future__ import annotations

import json
import os
import sys
import time
from typing import Callable, Dict, List, Optional

from ..core import rounds as rd
from ..core import windowmodel as wm
from ..core import windowprefs as wp
from ..core import windowtheme as wt
from . import a11y, sizing
from .gtkload import Gio, GLib, Gtk, Pango, version_text

TIMEOUT_S = 15.0


def pump(condition: Callable[[], bool], timeout: float = TIMEOUT_S) -> bool:
    """Let the window run until `condition` holds (or the time is up)."""
    context = GLib.MainContext.default()
    deadline = time.time() + timeout
    while time.time() < deadline:
        while context.pending():
            context.iteration(False)
        if condition():
            return True
        time.sleep(0.01)
    return False


def find(root: Gtk.Widget, name: str) -> Optional[Gtk.Widget]:
    for widget in a11y.walk(root):
        if a11y.label_of(widget) == name:
            return widget
    return None


def points(widget: Gtk.Widget) -> float:
    """The widget's text size in points. GTK gives pixels for a size written in points in the style file, at the screen's dpi."""
    description = widget.get_pango_context().get_font_description()
    size = description.get_size() / Pango.SCALE
    if description.get_size_is_absolute():
        dpi = Gtk.Settings.get_default().get_property("gtk-xft-dpi") / 1024.0 or 96.0
        return size * 72.0 / dpi
    return size


def labels(root: Gtk.Widget) -> List[Gtk.Label]:
    return [w for w in a11y.walk(root) if isinstance(w, Gtk.Label)]


def run(services: wm.Services) -> int:
    from .app import Application
    checks: Dict[str, object] = {}
    app = Application(services)
    app.register(None)
    Gio.Application.activate(app)
    shell = app.props.active_window
    pump(lambda: shell.is_visible())
    cat = services.cat
    checks["gtk"] = version_text()
    checks["window_title"] = shell.get_title()
    pages = [shell.stack.get_page(p.widget).get_title() for p in shell.pages]
    checks["pages"] = pages
    checks["project_opened"] = shell.project_id

    unnamed: Dict[str, List[str]] = {}
    smallest = 99.0
    for key, page in zip(("projects", "rounds", "voicefile", "free", "display"), shell.pages):
        shell.stack.set_visible_child_name(key)
        page.refresh()
        pump(lambda: True, 0.05)
        missing = a11y.unnamed_controls(page.widget)
        if missing:
            unnamed[key] = missing
        for label in labels(page.widget):
            smallest = min(smallest, points(label))
    checks["unnamed_controls"] = unnamed
    checks["smallest_text_pt"] = round(smallest, 1)
    checks["animations_off"] = not Gtk.Settings.get_default().get_property("gtk-enable-animations")

    pid = shell.project_id
    if pid is None:
        print(json.dumps(checks))
        return 1
    record = rd.load(wm.open_project(services.home, pid).paths)
    chosen = record.current

    shell.stack.set_visible_child_name("rounds")
    shell.pages[1].refresh()
    other = next((i.number for i in wm.rounds_view(services.home, pid, cat).items if i.can_choose), None)
    checks["a_round_can_be_chosen"] = other is not None
    checks["the_chosen_round_has_no_choose_button"] = find(shell.pages[1].widget, cat.t("window.rounds.choose_name", number=chosen)) is None
    if other is not None:
        button = find(shell.pages[1].widget, cat.t("window.rounds.choose_name", number=other))
        checks["choose_button_found"] = button is not None
        button.emit("clicked")
        checks["choose_question_shown"] = pump(lambda: shell.dialog is not None)
        question_ok = shell.dialog is not None
        if question_ok:
            pump(lambda: shell.dialog.get_focus() is not None, 2.0)
            no_button = shell.dialog.get_widget_for_response(Gtk.ResponseType.CANCEL)
            checks["no_is_where_the_focus_starts"] = shell.dialog.get_focus() is no_button and no_button.get_label() == cat.t("window.dialog.no")
            checks["yes_is_not_the_default"] = shell.dialog.get_widget_for_response(Gtk.ResponseType.YES).get_label() == cat.t("window.dialog.yes")
            checks["no_is_the_default_widget"] = shell.dialog.get_default_widget() is no_button
            checks["pages_locked_while_a_question_waits"] = not shell.stack.get_sensitive() and not shell.sidebar.get_sensitive()
            handle = shell.run_handle
            shell.run(wm.back_args(pid))
            checks["a_second_task_is_refused_while_busy"] = shell.run_handle is handle
            checks["question_has_no_typed_instruction"] = "Type yes" not in " ".join(w.get_label() for w in labels(shell.dialog.get_content_area()))
        shell.dialog.response(Gtk.ResponseType.DELETE_EVENT) if question_ok else None        # any answer that is not Yes is a No
        checks["no_answered"] = pump(lambda: not shell.busy and shell.dialog is None and shell.last_result[0] == 2)
        checks["pages_unlocked_after"] = shell.stack.get_sensitive() and shell.sidebar.get_sensitive()
        checks["result_head_for_nothing"] = shell.result_label.get_label().splitlines()[0] == cat.t("window.result.nothing") and "Nothing was done." in shell.result_label.get_label()
        checks["no_changed_nothing"] = rd.load(wm.open_project(services.home, pid).paths).current == chosen
        shell.pages[1].refresh()
        find(shell.pages[1].widget, cat.t("window.rounds.choose_name", number=other)).emit("clicked")
        pump(lambda: shell.dialog is not None)
        shell.dialog.response(Gtk.ResponseType.YES) if shell.dialog is not None else None
        checks["yes_answered"] = pump(lambda: not shell.busy and shell.dialog is None and shell.last_result[0] == 0)
        checks["result_head_for_done"] = shell.result_label.get_label().splitlines()[0] == cat.t("window.result.ok")
        checks["yes_chose_it"] = rd.load(wm.open_project(services.home, pid).paths).current == other

    shell.stack.set_visible_child_name("free")
    shell.pages[3].refresh()
    free_page = shell.pages[3]
    if free_page.checks:
        checks["remove_button_off_when_nothing_is_ticked"] = not free_page.remove.get_sensitive()
        free_page.checks[0][0].set_active(True)
        checks["remove_button_ready"] = free_page.remove.get_sensitive()
        free_page.remove.emit("clicked")
        checks["free_question_shown"] = pump(lambda: shell.dialog is not None)
        if shell.dialog is not None:
            shown = " ".join(w.get_label() for w in labels(shell.dialog.get_content_area()))
            others = [item.line for _check, item in free_page.checks[1:]]
            checks["free_question_names_only_the_ticked"] = free_page.checks[0][1].line.split(":")[0] in shown and not any(o.split(":")[0] in shown for o in others if o.split(":")[0] != free_page.checks[0][1].line.split(":")[0])
        shell.dialog.close() if shell.dialog is not None else None                  # closing the question any way but Yes is a No
        checks["free_no_answered"] = pump(lambda: not shell.busy and shell.dialog is None and shell.last_result[0] == 2)
    checks["free_listed"] = len(free_page.checks)

    shell.stack.set_visible_child_name("voicefile")
    shell.pages[2].refresh()
    make = find(shell.pages[2].widget, cat.t("window.voicefile.make"))
    checks["make_button_found"] = make is not None
    if make is not None:
        make.emit("clicked")
        pump(lambda: shell.busy or shell.last_result[1])
        checks["make_finished"] = pump(lambda: not shell.busy)
        checks["make_said_why"] = bool(shell.last_result[1]) and shell.last_result[0] in (1, 2)
        checks["result_head_for_a_problem"] = shell.result_label.get_label().splitlines()[0] == cat.t("window.result.problem")

    profile_checks(shell, checks)
    look_checks(shell, checks)
    checks["not_busy_at_the_end"] = not shell.busy
    shell.destroy()
    failed = sorted(k for k, v in checks.items() if v is False or (k == "unnamed_controls" and v) or (k == "smallest_text_pt" and float(v) < wt.TEXT_STEPS[0] - 0.05))
    checks["failed"] = failed
    print(json.dumps(checks, sort_keys=True))
    return 1 if failed else 0


def answer(shell, yes: bool, timeout: float = 8.0) -> bool:
    """Wait for the question on the screen (not a form) and answer it with its Yes or its No button."""
    if not pump(lambda: shell.dialog is not None and shell.form is None, timeout):
        return False
    shell.dialog.response(Gtk.ResponseType.YES if yes else Gtk.ResponseType.CANCEL)
    return pump(lambda: shell.dialog is None, 3.0)


def settled(shell, timeout: float = 8.0) -> bool:
    return pump(lambda: not shell.busy and shell.dialog is None and shell.form is None, timeout)


def fill_new(form, name: str, hours: str = "2") -> None:
    form.name.set_text(name)
    form.hours.set_text(hours)
    form.own.set_active(True)


def profile_checks(shell, checks: Dict[str, object]) -> None:
    """Making, changing, putting away, bringing back and deleting a project, by the real buttons: a form that is not whole stays open and says why, a whole one closes and the command asks once
    more, a No changes nothing, a project that is put away leaves the list and is closed if it was open, and a delete needs two Yes answers and removes only that project."""
    cat, home = shell.cat, shell.services.home
    page = shell.pages[0]
    keep_open = shell.project_id
    shell.stack.set_visible_child_name("projects")
    page.refresh()
    folder = home.projects + "/tour-anna"

    page.new_button.emit("clicked")
    form = shell.form
    checks["new_form_opens_as_the_question_on_the_screen"] = form is not None and shell.dialog is form.dialog
    if form is None:
        return
    form.dialog.response(Gtk.ResponseType.OK)
    pump(lambda: False, 0.05)
    said = form.problems.get_label()
    checks["new_form_says_what_is_wrong_and_stays_open"] = shell.form is form and form.problems.get_visible() and cat.t("newproject.problem.name.blank") in said and cat.t("newproject.problem.whose_voice.missing") in said
    checks["form_controls_are_named"] = a11y.unnamed_controls(form.dialog) == []
    form.other.set_active(True)
    checks["agreement_shows_for_someone_elses_voice"] = form.consent_box.get_visible()
    form.name.set_text("Tour Ben")
    form.dialog.response(Gtk.ResponseType.OK)
    pump(lambda: False, 0.05)
    checks["a_missing_agreement_is_named_in_the_form"] = cat.t("project.consent.missing.given_by") in form.problems.get_label() and not os.path.exists(home.projects + "/tour-ben")
    form.own.set_active(True)
    checks["agreement_hides_for_my_own_voice"] = not form.consent_box.get_visible()
    fill_new(form, "Tour Anna")
    form.dialog.response(Gtk.ResponseType.OK)
    checks["a_whole_form_closes_and_the_command_asks_once_more"] = pump(lambda: shell.form is None and shell.dialog is not None) and "Make this project?" in message_of(shell.dialog)
    answer(shell, False)
    settled(shell)
    checks["a_no_makes_no_project"] = not os.path.exists(folder) and shell.last_result[0] == 2

    page.new_button.emit("clicked")
    fill_new(shell.form, "Tour Anna")
    shell.form.dialog.response(Gtk.ResponseType.OK)
    answer(shell, True)
    settled(shell)
    checks["a_yes_makes_the_project_and_chooses_its_row"] = os.path.isfile(folder + "/project.json") and page.selected == "tour-anna" and shell.last_result[0] == 0

    find(page.widget, cat.t("window.projects.edit")).emit("clicked")
    form = shell.form
    checks["edit_form_is_filled_in"] = form is not None and form.name.get_text() == "Tour Anna" and form.hours.get_text() == "2" and not form.consent_box.get_visible()
    if form is not None:
        form.dialog.response(Gtk.ResponseType.OK)
        pump(lambda: False, 0.05)
        checks["edit_with_nothing_different_says_so_and_stays_open"] = shell.form is form and cat.t("window.form.no_changes") in form.problems.get_label()
        form.name.set_text("Tour Anna B")
        form.dialog.response(Gtk.ResponseType.OK)
        answer(shell, True)
        settled(shell)
        checks["edit_saves_after_a_yes"] = wm.find_project(home, "tour-anna").name == "Tour Anna B"

    find(page.widget, cat.t("window.projects.away")).emit("clicked")
    answer(shell, False)
    settled(shell)
    checks["a_no_keeps_the_project_in_the_list"] = "tour-anna" in [i.id for i in wm.projects_view(home, cat).items]
    find(page.widget, cat.t("window.projects.away")).emit("clicked")
    answer(shell, True)
    settled(shell)
    view = wm.projects_view(home, cat)
    checks["put_away_moves_it_to_the_other_list"] = "tour-anna" in [i.id for i in view.away] and "tour-anna" not in [i.id for i in view.items] and os.path.isfile(folder + "/project.json")
    checks["the_away_list_is_offered_not_shown"] = page.away_toggle is not None and page.away_rows is None
    page.away_toggle.set_active(True)
    checks["the_away_list_shows_when_asked"] = page.away_rows is not None
    page.away_rows.select_row(page.away_rows.get_row_at_index(0))
    checks["bring_back_is_ready_for_a_project_that_is_away"] = find(page.widget, cat.t("window.projects.back")).get_sensitive() and not find(page.widget, cat.t("window.projects.edit")).get_sensitive()
    find(page.widget, cat.t("window.projects.back")).emit("clicked")
    answer(shell, True)
    settled(shell)
    checks["bring_back_returns_it_to_the_list"] = "tour-anna" in [i.id for i in wm.projects_view(home, cat).items] and wm.find_project(home, "tour-anna") is not None

    shell.open_project("tour-anna", announce=False)
    shell.stack.set_visible_child_name("projects")
    page.select("tour-anna")
    find(page.widget, cat.t("window.projects.away")).emit("clicked")
    answer(shell, True)
    settled(shell)
    checks["an_open_project_that_is_put_away_is_closed"] = shell.project_id is None and cat.t("window.projects.closed") in shell.last_result[1]
    shell.run(wm.unarchive_args("tour-anna"))
    answer(shell, True)
    settled(shell)

    page.select("tour-anna")
    find(page.widget, cat.t("window.projects.delete")).emit("clicked")
    asked = pump(lambda: shell.dialog is not None)
    first = message_of(shell.dialog) if shell.dialog is not None else ""
    checks["delete_lists_what_goes_before_it_asks"] = asked and "tour-anna" in first and cat.t("projects.delete.backup") in first
    answer(shell, True)
    second = pump(lambda: shell.dialog is not None)
    checks["delete_asks_a_second_time"] = second and "Last question." in message_of(shell.dialog)
    answer(shell, False)
    settled(shell)
    checks["a_no_to_the_second_question_removes_nothing"] = os.path.isfile(folder + "/project.json")
    find(page.widget, cat.t("window.projects.delete")).emit("clicked")
    answer(shell, True)
    answer(shell, True)
    settled(shell)
    checks["two_yes_answers_delete_only_that_project"] = not os.path.lexists(folder) and "tour-anna" not in [i.id for i in wm.projects_view(home, cat).items] and wm.find_project(home, keep_open) is not None
    checks["projects_page_controls_are_named"] = a11y.unnamed_controls(page.widget) == []
    if keep_open is not None:
        shell.open_project(keep_open, announce=False)


def every_look() -> List[wt.Look]:
    looks = [wt.Look("ack", accent, 14, 100) for accent in range(len(wt.ACCENTS))]
    looks += [wt.Look("ack", 0, pt, pct) for pt in (wt.TEXT_STEPS[0], wt.TEXT_STEPS[-1]) for pct in (wt.SCALE_STEPS[0], wt.SCALE_STEPS[-1])]
    looks += [wt.Look("system", 0, pt, pct) for pt in (wt.TEXT_STEPS[0], wt.TEXT_STEPS[-1]) for pct in (wt.SCALE_STEPS[0], wt.SCALE_STEPS[-1])]
    return looks


def message_of(dialog: Gtk.Dialog) -> str:
    return " ".join(w.get_label() for w in labels(dialog.get_content_area()))


def look_checks(shell, checks: Dict[str, object]) -> None:
    """The display page: every look is a style sheet GTK takes without a complaint, a change is shown at once, the first change asks before it writes anything, a No writes nothing, a Yes writes the
    small file, and removing it is listed first and asked about."""
    cat, appearance = shell.cat, shell.appearance
    start = appearance.look
    page = shell.pages[4]
    shell.stack.set_visible_child_name("display")
    page.refresh()
    bad = []
    for look in every_look():
        appearance.look = look
        appearance.apply()
        pump(lambda: False, 0.02)
        if appearance.errors:
            bad.append((look, appearance.errors[:2]))
    checks["every_look_is_a_sheet_gtk_accepts"] = bad == []
    checks["sheet_errors"] = [str(b) for b in bad][:3]
    appearance.look = wt.Look("ack", 0, 14, 200)
    appearance.apply()
    checks["scale_reaches_python_sizes"] = shell.sidebar.get_size_request()[0] == 460 and sizing.px(10) == 20
    appearance.look = wt.Look()
    appearance.apply()
    checks["scale_goes_back"] = shell.sidebar.get_size_request()[0] == 230 and sizing.px(10) == 10

    path = appearance.path
    checks["no_file_before_any_choice"] = not os.path.exists(path) and appearance.keeper.state == "undecided"
    system = find(page.widget, cat.t("window.display.theme_system_name"))
    checks["theme_buttons_are_named"] = system is not None and find(page.widget, cat.t("window.display.theme_ack_name")) is not None
    checks["accent_buttons_are_named"] = all(find(page.widget, cat.t("window.display.accent_name", name=cat.t(w))) is not None for w in (
        "window.display.accent_cyan", "window.display.accent_pink"))
    system.set_active(True)
    checks["first_change_asks"] = pump(lambda: shell.dialog is not None)
    if shell.dialog is not None:
        said = message_of(shell.dialog)
        checks["question_names_the_file_and_what_it_holds"] = path in said and "colour theme" in said and "Keep your choices in this file?" in said
        no_button = shell.dialog.get_widget_for_response(Gtk.ResponseType.CANCEL)
        checks["keep_question_starts_on_no"] = no_button is not None and no_button.get_label() == cat.t("window.dialog.no")
        shell.dialog.response(Gtk.ResponseType.CANCEL)
    pump(lambda: shell.dialog is None, 2.0)
    checks["the_change_is_shown_though_not_kept"] = appearance.look.theme == "system" and not os.path.exists(path)
    checks["a_no_is_said_in_the_result"] = shell.last_result[0] == 2 and cat.t("window.display.session_only") in shell.last_result[1]
    shell.bigger_text.emit("clicked")
    pump(lambda: False, 0.05)
    checks["after_a_no_nothing_asks_and_nothing_is_written"] = shell.dialog is None and not os.path.exists(path) and appearance.look.text_pt == 16
    smaller_ends = wt.Look(text_pt=wt.TEXT_STEPS[0])
    appearance.look = smaller_ends
    appearance.apply()
    checks["smaller_text_is_off_at_the_smallest_step"] = not shell.smaller_text.get_sensitive() and shell.bigger_text.get_sensitive()

    appearance.keeper.forgot()
    appearance.look = wt.Look()
    appearance.apply()
    shell.bigger_text.emit("clicked")
    checks["asks_again_after_a_fresh_start"] = pump(lambda: shell.dialog is not None)
    if shell.dialog is not None:
        shell.dialog.response(Gtk.ResponseType.YES)
    pump(lambda: shell.dialog is None, 2.0)
    saved = wp.load(path)
    checks["a_yes_writes_the_small_file"] = saved == appearance.look and saved.text_pt == 16 and appearance.keeper.state == "kept"
    checks["the_file_is_owner_only_and_small"] = oct(os.stat(path).st_mode & 0o777) == "0o600" and os.path.getsize(path) < 200
    checks["a_yes_is_said_in_the_result"] = shell.last_result[0] == 0 and path in " ".join(shell.last_result[1])
    shell.bigger_text.emit("clicked")
    pump(lambda: False, 0.05)
    checks["later_changes_are_written_without_asking"] = shell.dialog is None and wp.load(path).text_pt == 18 and os.path.exists(wp.previous_path(path))
    page.refresh()
    checks["the_page_says_where_they_are_kept"] = path in page.status.get_label() and page.forget.get_visible() and not page.keep.get_visible()

    page.forget.emit("clicked")
    checks["removing_lists_the_files_first"] = pump(lambda: shell.dialog is not None)
    if shell.dialog is not None:
        said = message_of(shell.dialog)
        checks["removing_names_both_files"] = path in said and wp.previous_path(path) in said
        shell.dialog.response(Gtk.ResponseType.CANCEL)
    pump(lambda: shell.dialog is None, 2.0)
    checks["a_no_to_removing_keeps_both"] = os.path.exists(path) and os.path.exists(wp.previous_path(path))
    page.forget.emit("clicked")
    pump(lambda: shell.dialog is not None)
    if shell.dialog is not None:
        shell.dialog.response(Gtk.ResponseType.YES)
    pump(lambda: shell.dialog is None, 2.0)
    checks["a_yes_removes_them_and_the_window_asks_again_next_time"] = not os.path.exists(path) and not os.path.exists(wp.previous_path(path)) and appearance.keeper.state == "undecided"
    checks["the_window_keeps_its_look_after_removing"] = appearance.look.text_pt == 18

    # a change is shown whatever becomes of the file, and what it reports is true
    scratch = shell.services.home.root
    blocker = os.path.abspath(__file__)                      # a file that is there: a path "inside" it can never be made, so a save under it fails
    kept_path, kept_keeper = appearance.path, appearance.keeper
    shown = {}
    for name, state, target in (("saved", "kept", kept_path), ("ask", "undecided", os.path.join(scratch, "tour-ask.json")),
                                ("session", "declined", os.path.join(scratch, "tour-session.json")), ("failed", "kept", os.path.join(blocker, "choices-file"))):
        appearance.path, appearance.keeper = target, wp.Keeper(state)
        wanted = wt.Look("ack", 3, 20, 125)
        shown[name] = appearance.change(wanted) == name and appearance.applied == wanted
    appearance.path, appearance.keeper = kept_path, kept_keeper
    wp.forget(wp.plan_forget(kept_path))                     # the file the "saved" case made (this is a copy of a home folder made for the tour)
    checks["a_change_is_shown_and_reported_truly_whatever_becomes_of_the_file"] = all(shown.values())
    appearance.keeper = wp.Keeper("kept")
    appearance.path = os.path.join(blocker, "choices-file")
    shell.change_look(wt.Look("ack", 0, 18, 100))
    checks["a_failed_save_says_so_in_the_window"] = shell.last_result[0] == 1 and cat.t("window.display.not_saved") in shell.last_result[1]
    appearance.path, appearance.keeper = kept_path, kept_keeper

    # the system theme hands the dark setting back, the ACK theme asks for dark
    settings = Gtk.Settings.get_default()
    was_dark = appearance._system_dark
    handed_back = []
    for system_dark in (False, True):
        appearance._system_dark = system_dark
        appearance.look = wt.Look("system")
        appearance.apply()
        handed_back.append(settings.get_property("gtk-application-prefer-dark-theme") == system_dark)
        appearance.look = wt.Look("ack")
        appearance.apply()
        handed_back.append(settings.get_property("gtk-application-prefer-dark-theme") is True)
    appearance._system_dark = was_dark
    checks["the_system_theme_hands_the_dark_setting_back_and_ack_asks_for_dark"] = all(handed_back)

    page.reset.emit("clicked")
    pump(lambda: shell.dialog is not None, 1.0)
    if shell.dialog is not None:
        shell.dialog.response(Gtk.ResponseType.CANCEL)
    pump(lambda: shell.dialog is None, 2.0)
    checks["standard_look_comes_back"] = appearance.look == wt.Look(theme=appearance.look.theme)
    appearance.look = start
    appearance.apply()
