# SPDX-License-Identifier: GPL-3.0-or-later
"""The headless tour of the five pages for the tool's own commands (Hear the voice, Backup, Check the tool, Updates, Problem report), run from window/selftest.py on a copy of a project.

Every check presses the real button and answers the real question: the plan comes before the question, a No changes nothing, a Yes does exactly what was shown. The update page is given a stand-in
for the download module, so the tour never reaches the internet; it learns how many times it was asked. The order matters: the hearing fails on purpose (the copy has no training programs), and the
Problem report page is then checked against that failure.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List

from ..core import describe
from ..core import windowio as wio
from ..core import windowmodel as wm
from ..core.refresh_flow import SETUP_COMMAND
from ..core.system import CommandResult
from . import a11y
from .gtkload import Gtk
from .selftest import answer, labels, message_of, pump, settled

SHA = "0123456789abcdef0123456789abcdef01234567"


def _tree(root: str) -> List[str]:
    return sorted(str(p) for p in Path(root).rglob("*"))


def _said(shell) -> str:
    return "\n".join(shell.last_result[1])


def _click_on_words(words: Gtk.Widget) -> bool:
    """Press on the words beside a tick box (the page gives them a click of their own). True when the words had one."""
    controllers = words.observe_controllers()
    for index in range(controllers.get_n_items()):
        controller = controllers.get_item(index)
        if isinstance(controller, Gtk.GestureClick):
            controller.emit("released", 1, 5.0, 5.0)
            return True
    return False


def _go(shell, name: str):
    page = shell.page(name)
    shell.stack.set_visible_child_name(name)
    page.refresh()
    pump(lambda: True, 0.05)
    return page


def tool_checks(shell, checks: Dict[str, object]) -> None:
    if shell.project_id is None:
        return
    hear_checks(shell, checks)
    report_checks(shell, checks)
    backup_checks(shell, checks)
    refresh_checks(shell, checks)
    update_checks(shell, checks)


# ---------------------------------------------------------------- Hear the voice

def hear_checks(shell, checks: Dict[str, object]) -> None:
    cat, home, pid = shell.cat, shell.services.home, shell.project_id
    page = _go(shell, "hear")
    view = wm.hear_view(home, pid, cat)
    checks["hear_page_controls_are_named"] = a11y.unnamed_controls(page.widget) == []
    checks["hear_page_offers_the_rounds_the_model_lists"] = page.round_numbers == [r.number for r in view.rounds] and page.round_form.get_visible() == bool(view.rounds)
    checks["hear_page_has_a_round_to_hear"] = bool(view.rounds)
    checks["the_chosen_round_is_the_one_preselected"] = bool(view.rounds) and page.round_numbers[page.round_choice.get_selected()] == next(r.number for r in view.rounds if r.chosen)
    checks["no_voice_file_is_said_so"] = bool(view.voices) or any(label.get_label() == cat.t("window.hear.no_voices") for label in labels(page.widget))
    rounds_checks(shell, page, checks)
    if not view.rounds:
        return
    if len(view.rounds) > 1:
        page.round_choice.set_selected(0)
        page.refresh()
        checks["a_look_keeps_the_round_that_was_picked"] = page.round_numbers[page.round_choice.get_selected()] == view.rounds[0].number
        page.round_choice.set_selected(page.round_numbers.index(next(r.number for r in view.rounds if r.chosen)))
    before = _tree(home.root)
    page.hear_round.emit("clicked")
    checks["hearing_a_round_finishes"] = settled(shell)
    checks["hearing_without_the_programs_says_so_and_starts_nothing"] = shell.last_result[0] == 1 and "voice_studio.buildenv" in _said(shell) and _tree(home.root) == before
    checks["the_failure_names_only_what_that_task_told"] = shell.last_failure is not None and shell.last_failure.problem == "" and describe.errors_shown() == ()
    checks["a_failed_task_offers_the_way_to_the_report_page"] = shell.report_button.get_visible() and shell.stack.get_visible_child_name() == "hear"
    shell.report_button.emit("clicked")
    checks["the_way_to_the_report_page_goes_there_and_goes_away"] = shell.stack.get_visible_child_name() == "report" and not shell.report_button.get_visible()
    shell.stack.set_visible_child_name("hear")
    checks["a_failed_task_points_at_the_problem_report"] = (shell.last_failure is not None and shell.last_failure.step == "voicefile listen"
                                                              and cat.t("window.result.report_hint", page=cat.t("window.nav.report")) in shell.last_result[1])


def _round_view(rounds, chosen=None, running=None) -> wm.HearView:
    return wm.HearView("p", "P", (), tuple(wm.HearRound(n, "Round %d" % n, n == chosen) for n in rounds), running, "/x", "")


def rounds_checks(shell, page, checks: Dict[str, object]) -> None:
    """The round list is given views the copy of the project could not produce (several rounds, none chosen, one training, none at all), and then rebuilt from the project."""
    cat = shell.cat
    picked = lambda: page.round_numbers[page.round_choice.get_selected()]
    page._update_rounds(_round_view(()))                       # nothing picked yet, whatever the project's own rounds were
    page._update_rounds(_round_view((1, 2, 3), chosen=2))
    checks["the_round_the_command_chose_is_preselected_among_several"] = page.round_numbers == [1, 2, 3] and picked() == 2
    checks["with_rounds_to_hear_the_form_shows_and_the_notes_do_not"] = page.round_form.get_visible() and not page.no_rounds.get_visible() and not page.running_note.get_visible() and page.running_note.get_label() == ""
    page.round_choice.set_selected(0)
    page._update_rounds(_round_view((1, 2, 3), chosen=2))
    checks["a_look_keeps_a_round_that_is_still_there"] = picked() == 1
    page._update_rounds(_round_view((2, 3, 4), chosen=3))
    checks["a_round_that_is_gone_gives_way_to_the_one_the_command_chose"] = picked() == 3
    page._update_rounds(_round_view((5, 6, 7)))
    checks["with_none_chosen_the_newest_round_is_offered"] = page.round_numbers == [5, 6, 7] and picked() == 7
    page._update_rounds(_round_view((), running=4))
    checks["a_round_in_training_is_said_and_nothing_can_be_heard"] = (page.running_note.get_visible() and page.running_note.get_label() == cat.t("window.hear.running", number=4)
                                                                      and not page.no_rounds.get_visible() and not page.round_form.get_visible())
    page._update_rounds(_round_view(()))
    checks["with_no_round_at_all_that_is_said_and_the_form_is_hidden"] = (page.no_rounds.get_visible() and not page.running_note.get_visible() and page.running_note.get_label() == ""
                                                                         and not page.round_form.get_visible())
    page.refresh()


# ---------------------------------------------------------------- Problem report

def report_checks(shell, checks: Dict[str, object]) -> None:
    cat, home = shell.cat, shell.services.home
    page = _go(shell, "report")
    failure = shell.last_failure
    checks["report_page_controls_are_named"] = a11y.unnamed_controls(page.widget) == []
    checks["the_page_offers_the_failure_just_shown"] = failure is not None and page.failure_row.get_visible() and page.failure_check.get_active() and failure.step in page.failure_words.get_label()
    checks["nothing_is_shown_before_a_report_is_built"] = page.nothing.get_visible() and not page.report_scroll.get_visible() and not page.copy.get_visible()
    checks["the_log_choice_waits_for_a_task"] = not page.log_row.get_sensitive()
    page.show.emit("clicked")
    checks["a_report_is_built_without_a_question"] = settled(shell) and shell.last_result[0] == 0
    report = shell.services.learned.report
    checks["the_report_is_shown_on_its_page"] = bool(report) and page.report_label.get_label() == report and page.report_scroll.get_visible() and page.copy.get_visible() and not page.nothing.get_visible()
    checks["the_report_takes_the_focus_so_it_is_in_view"] = shell.get_focus() is not None and (shell.get_focus() is page.report_scroll or shell.get_focus().is_ancestor(page.report_scroll))
    checks["the_report_names_the_step_that_failed"] = failure is not None and failure.step in report
    checks["the_report_holds_no_folder_of_this_computer"] = bool(report) and home.root not in report
    checks["making_a_report_keeps_the_failure_it_is_about"] = shell.last_failure is failure
    page.copy.emit("clicked")
    checks["copy_says_it_copied_the_report"] = cat.t("window.report.copied") in shell.last_result[1]
    if failure is not None:
        page.failure_check.set_active(False)
        page.step.set_text("")
        checks["an_unticked_failure_adds_nothing_when_no_words_were_typed"] = page.fields().step == "" and page.fields().problem == ""
        page.step.set_text("my own words")
        unticked = page.fields()
        page.failure_check.set_active(True)
        page.step.set_text("")
        ticked = page.fields()
        page.step.set_text("typed")
        typed = page.fields()
        page.step.set_text("")
        checks["an_unticked_failure_adds_nothing_and_the_persons_words_stay"] = unticked.step == "my own words" and unticked.problem == ""
        checks["a_ticked_failure_fills_in_the_step_and_the_one_problem"] = ticked.step == failure.step and ticked.problem == failure.problem
        checks["typed_words_win_for_the_step_but_the_problem_stays"] = typed.step == "typed" and typed.problem == failure.problem
    real_choices = wm.job_choices
    wm.job_choices = lambda _home, _cat: (("", "no task"), ("last", "newest"), ("j-1", "task one"))      # the copy of the project holds no tasks; the page is given some
    try:
        page.refresh()
        page.jobs.set_selected(2)
        asked_for_log = page.log_row.get_sensitive()
        page.log_check.set_active(True)
        named = page.fields()
        checks["choosing_a_task_lets_the_log_be_asked_for_and_the_fields_name_both"] = asked_for_log and named.job == "j-1" and named.include_log
        wm.job_choices = lambda _home, _cat: (("", "no task"), ("last", "newest"), ("j-2", "task two"), ("j-1", "task one"))
        page.refresh()
        checks["a_look_keeps_the_task_that_was_picked_when_the_list_changes"] = page.job_values == ["", "last", "j-2", "j-1"] and page.job_values[page.jobs.get_selected()] == "j-1"
        page.jobs.set_selected(0)
        checks["choosing_no_task_clears_the_log_choice"] = not page.log_row.get_sensitive() and not page.log_check.get_active() and not page.fields().include_log
    finally:
        wm.job_choices = real_choices
        page.refresh()
    if failure is not None:
        page.failure_check.set_active(False)
        page.refresh()
        checks["a_look_keeps_a_failure_unticked"] = not page.failure_check.get_active()
        shell.last_failure = wm.Failure("voicefile listen", "")
        page.refresh()
        checks["a_new_failure_is_offered_ticked_again"] = page.failure_check.get_active() and "voicefile listen" in page.failure_words.get_label()
        shell.last_failure = None
        page.refresh()
        checks["with_no_failure_the_page_offers_none"] = not page.failure_row.get_visible() and page.fields().step == ""
        shell.last_failure = failure
        page.refresh()

    folder = home.root + "/tour-report"
    os.makedirs(folder, exist_ok=True)
    target = folder + "/tour-report.txt"
    page.save.emit("clicked")
    form = shell.form
    checks["save_form_opens_as_the_question_on_the_screen"] = form is not None and shell.dialog is form.dialog
    if form is None:
        return
    checks["the_form_starts_with_a_name_to_keep"] = bool(cat.t("window.report.default_name")) and form.name.get_text() == cat.t("window.report.default_name")
    page.save.emit("clicked")
    checks["pressing_save_again_does_not_open_a_second_form"] = shell.form is form and shell.dialog is form.dialog
    checks["save_form_controls_are_named"] = a11y.unnamed_controls(form.dialog) == []
    form.dialog.response(Gtk.ResponseType.OK)
    pump(lambda: False, 0.05)
    checks["save_form_says_no_folder_was_chosen_and_stays_open"] = shell.form is form and form.problems.get_visible() and cat.t("window.report.need_folder") in form.problems.get_label()
    said_before = shell.last_result
    form.pick.emit("clicked")
    opened = pump(lambda: shell.chooser is not None and shell.chooser.is_visible(), 3.0)
    action = shell.chooser.get_action() if opened else None
    if shell.chooser is not None:
        shell.chooser.response(Gtk.ResponseType.CANCEL)
    checks["the_chooser_picks_a_folder_and_closes_choosing_nothing"] = (opened and action == Gtk.FileChooserAction.SELECT_FOLDER and pump(lambda: shell.chooser is None, 3.0) and form.folder == ""
                                                                         and shell.last_result == said_before)
    form.set_folder(folder)
    form.name.set_text("a/b")
    form.dialog.response(Gtk.ResponseType.OK)
    pump(lambda: False, 0.05)
    checks["a_file_name_with_a_slash_is_refused_in_the_form"] = shell.form is form and cat.t("window.report.bad_name", limit=wm.MAX_REPORT_FILE_NAME) in form.problems.get_label()
    form.name.set_text("tour-report.txt")
    form.dialog.response(Gtk.ResponseType.OK)
    asked = pump(lambda: shell.dialog is not None and shell.form is None)
    shown = message_of(shell.dialog) if shell.dialog is not None else ""
    first_line = next((line for line in report.splitlines() if line.strip()), "")
    checks["saving_shows_the_whole_report_before_it_asks"] = asked and bool(first_line) and first_line in shown and wio.question_text(cat.t("reportcmd.save.question", file=target)) in shown
    answer(shell, False)
    settled(shell)
    checks["a_no_saves_nothing"] = not os.path.exists(target) and shell.last_result[0] == 2
    page.save.emit("clicked")
    form = shell.form
    form.set_folder(folder)
    form.name.set_text("tour-report.txt")
    form.dialog.response(Gtk.ResponseType.OK)
    answer(shell, True)
    settled(shell)
    saved = Path(target).read_text(encoding="utf-8") if os.path.isfile(target) else None
    checks["a_yes_saves_exactly_the_report_that_was_shown"] = saved is not None and saved.strip() == shell.services.learned.report.strip() and shell.last_result[0] == 0
    page.save.emit("clicked")
    form = shell.form
    form.set_folder(folder)
    form.name.set_text("tour-report.txt")
    form.dialog.response(Gtk.ResponseType.OK)
    pump(lambda: False, 0.05)
    checks["a_file_that_is_there_is_never_replaced_the_form_says_so"] = shell.form is form and form.problems.get_visible() and Path(target).read_text(encoding="utf-8") == saved
    form.dialog.response(Gtk.ResponseType.CANCEL)
    checks["cancelling_the_form_does_nothing"] = pump(lambda: shell.form is None and shell.dialog is None, 3.0) and Path(target).read_text(encoding="utf-8") == saved
    page.save.emit("clicked")
    form = shell.form
    form.pick.emit("clicked")
    open_chooser = shell.chooser if pump(lambda: shell.chooser is not None and shell.chooser.is_visible(), 3.0) else None
    form.dialog.response(Gtk.ResponseType.CANCEL)
    checks["cancelling_the_form_takes_a_chooser_that_is_still_open_with_it"] = (open_chooser is not None and pump(lambda: shell.form is None and shell.chooser is None and not open_chooser.is_visible(), 3.0)
                                                                              and shell.dialog is None)


# ---------------------------------------------------------------- Backup

def backup_checks(shell, checks: Dict[str, object]) -> None:
    cat, home, pid = shell.cat, shell.services.home, shell.project_id
    page = _go(shell, "backup")
    view = wm.backup_view(home, pid, cat)
    checks["backup_page_controls_are_named"] = a11y.unnamed_controls(page.widget) == []
    texts = [label.get_label() for label in labels(page.widget)]
    checks["backup_page_says_how_the_project_stands"] = bool(view.standing) and view.standing in texts
    checks["backup_page_says_where_the_next_one_goes"] = any(view.folder in line for line in texts)
    checks["no_backup_is_listed_before_one_is_made"] = page.rows is None and not view.items
    page.now.emit("clicked")
    asked = pump(lambda: shell.dialog is not None and shell.form is None)
    checks["backing_up_shows_what_it_holds_before_it_asks"] = asked and cat.t("backup.plan_head", name=view.project_name) in message_of(shell.dialog) and cat.t("backup.plan_never_removes") in message_of(shell.dialog)
    answer(shell, False)
    settled(shell)
    checks["a_no_makes_no_backup"] = shell.last_result[0] == 2 and wm.backup_view(home, pid, cat).items == () and not (os.path.isdir(home.backups) and os.listdir(home.backups))
    checks["a_declined_task_is_not_a_failure"] = shell.last_failure is None and not shell.report_button.get_visible()
    page.points.set_active(True)
    page.refresh()
    checks["leaving_out_the_saved_points_is_kept_across_a_look"] = page.points.get_active()
    page.now.emit("clicked")
    asked = pump(lambda: shell.dialog is not None and shell.form is None)
    checks["leaving_out_the_saved_points_is_said_in_the_plan"] = asked and cat.t("backup.left_out.saved_points") in message_of(shell.dialog)
    answer(shell, False)
    settled(shell)
    page.points.set_active(False)
    page.refresh()
    ticked = page.points.get_active()
    clicked = _click_on_words(page.points.get_next_sibling())
    checks["a_click_on_the_words_ticks_the_box"] = clicked and not ticked and page.points.get_active()
    _click_on_words(page.points.get_next_sibling())
    checks["a_second_click_on_the_words_unticks_it"] = not page.points.get_active()
    page.points.set_active(False)
    page.now.emit("clicked")
    answer(shell, True)
    settled(shell)
    made = wm.backup_view(home, pid, cat).items
    checks["a_yes_makes_a_backup_and_the_page_lists_it"] = shell.last_result[0] == 0 and len(made) == 1 and page.rows is not None
    checks["the_page_now_says_nothing_has_changed_since"] = wm.backup_view(home, pid, cat).standing in [label.get_label() for label in labels(page.widget)]
    if not made:
        return
    name = made[0].name
    find_button = lambda key: next((w for w in a11y.walk(page.widget) if isinstance(w, Gtk.Button) and a11y.label_of(w) == cat.t(key, name=name)), None)
    check_button, put_back_button = find_button("window.backup.check_name"), find_button("window.backup.put_back_name")
    checks["each_backup_has_check_and_put_back_buttons"] = check_button is not None and put_back_button is not None
    check_button.emit("clicked")
    settled(shell)
    checks["check_it_reads_the_backup_back"] = shell.last_result[0] == 0 and cat.t("backup.verify_ok", name=name) in _said(shell)
    before = _tree(home.root)
    find_button("window.backup.put_back_name").emit("clicked")
    settled(shell)
    checks["putting_back_what_is_all_there_adds_nothing_and_asks_nothing"] = shell.last_result[0] == 0 and cat.t("backup.restore_nothing") in _said(shell) and _tree(home.root) == before
    said_before = shell.last_result
    page.choose.emit("clicked")
    opened = pump(lambda: shell.chooser is not None and shell.chooser.is_visible(), 3.0)
    action = shell.chooser.get_action() if opened else None
    if shell.chooser is not None:
        shell.chooser.response(Gtk.ResponseType.CANCEL)
    checks["choosing_a_folder_opens_the_chooser_and_cancel_changes_nothing"] = (opened and action == Gtk.FileChooserAction.SELECT_FOLDER and pump(lambda: shell.chooser is None, 3.0) and page.folder == ""
                                                                                and shell.last_result == said_before)
    odd = home.root + "/odd\nfolder"
    page.folder_chosen(odd)          # the headless chooser cannot be made to hand a folder back, so what it would hand back is given to the page
    checks["a_folder_whose_name_has_a_line_break_is_refused_with_a_sentence"] = page.folder == "" and cat.t("window.backup.need_folder") in shell.last_result[1] and shell.last_result[0] == 2
    os.makedirs(home.root + "/elsewhere", exist_ok=True)
    page.folder_chosen(home.root + "/elsewhere")
    checks["a_folder_chosen_in_the_chooser_becomes_the_place"] = page.folder == home.root + "/elsewhere"
    chosen_words = cat.t("window.backup.folder_chosen", folder=home.root + "/elsewhere")
    checks["a_chosen_folder_is_said_and_can_be_put_down"] = chosen_words in [label.get_label() for label in labels(page.widget)] and page.usual is not None
    page.usual.emit("clicked")
    checks["the_usual_folder_comes_back"] = page.folder == "" and page.usual is None
    second = home.root + "/second-backups"
    os.makedirs(second, exist_ok=True)
    page.folder = second
    page.refresh()
    page.now.emit("clicked")
    asked = pump(lambda: shell.dialog is not None and shell.form is None)
    checks["a_chosen_folder_is_the_one_the_plan_names"] = asked and cat.t("backup.plan_where", folder=second) in message_of(shell.dialog)
    answer(shell, True)
    settled(shell)
    again = wm.backup_view(home, pid, cat)
    checks["a_chosen_folder_is_used_once_and_then_remembered_by_the_command"] = (shell.last_result[0] == 0 and any(n.endswith(".tar") for n in os.listdir(second)) and page.folder == ""
                                                                                  and again.folder == second and again.how == "remembered")
    checks["backup_page_controls_are_named_after"] = a11y.unnamed_controls(page.widget) == []
    if again.items:
        os.link(again.items[0].path, "%s/ack-project-backup-%s-20200101-000000.tar" % (second, pid))          # a second name for the same bytes: the list shows two backups
        page.refresh()
        two = wm.backup_view(home, pid, cat).items
        buttons = [a11y.label_of(w) for w in a11y.walk(page.widget) if isinstance(w, Gtk.Button)]
        checks["each_backup_in_the_folder_has_its_own_row_with_buttons_named_for_it"] = len(two) == 2 and all(cat.t(key, name=item.name) in buttons for item in two
                                                                                                           for key in ("window.backup.check_name", "window.backup.put_back_name"))


# ---------------------------------------------------------------- Check the tool

def refresh_checks(shell, checks: Dict[str, object]) -> None:
    cat, home = shell.cat, shell.services.home
    page = _go(shell, "refresh")
    checks["refresh_page_controls_are_named"] = a11y.unnamed_controls(page.widget) == []
    checks["the_programs_choice_offers_every_set_and_all"] = page.programs.get_model().get_n_items() == len(page.choices) == 1 + len(shell.services.environments()) and page.choices[0].id == ""
    before = _tree(home.root)
    page.check_quick.emit("clicked")
    checks["a_quick_look_finishes_and_says_something"] = settled(shell) and bool(shell.last_result[1])
    checks["a_look_changes_nothing"] = _tree(home.root) == before
    page.rebuild.emit("clicked")
    settled(shell)
    checks["a_fresh_copy_with_nothing_set_up_says_so_and_starts_nothing"] = shell.last_result[0] == 2 and cat.t("refresh.rebuild.nothing_set_up", command=SETUP_COMMAND) in _said(shell) and _tree(home.root) == before
    page.older.emit("clicked")
    settled(shell)
    checks["older_copies_are_listed_without_a_question"] = shell.last_result[0] == 0 and cat.t("refresh.older.none") in _said(shell)
    page.older_remove.emit("clicked")
    settled(shell)
    checks["removing_older_copies_with_none_there_asks_nothing"] = shell.last_result[0] == 0 and cat.t("refresh.older.none") in _said(shell) and _tree(home.root) == before


# ---------------------------------------------------------------- Updates

def update_checks(shell, checks: Dict[str, object]) -> None:
    cat, services = shell.cat, shell.services
    page = _go(shell, "update")
    calls: List[List[str]] = []
    prefix = services.release_source().tag_prefix

    def stand_in(_consent, argv, _ids):
        calls.append(list(argv))
        return CommandResult(0, "".join("%s\trefs/tags/%s%s\n" % (SHA, prefix, name) for name in ("v0.1.0", "v0.2.0")))
    real, services.networked = services.networked, stand_in
    try:
        checks["update_page_controls_are_named"] = a11y.unnamed_controls(page.widget) == []
        checks["update_page_says_which_copy_this_is"] = services.version in page.here.get_label()
        checks["nothing_is_looked_for_until_asked"] = calls == [] and page.status.get_label() == cat.t("window.update.not_looked") and not page.form.get_visible() and page.releases == ()
        checks["update_yes_check"] = "ran" if services.system.which("git") is not None else "skipped: no git on this computer"
        page.look.emit("clicked")
        if services.system.which("git") is None:
            settled(shell)
            checks["without_git_the_look_says_so_and_contacts_nothing"] = shell.last_result[0] == 2 and calls == []
            return
        asked = pump(lambda: shell.dialog is not None and shell.form is None)
        shown = message_of(shell.dialog) if shell.dialog is not None else ""
        checks["looking_says_what_it_will_ask_before_it_asks"] = asked and "git ls-remote --tags" in shown and wio.question_text(cat.t("update.question.check")) in shown and calls == []
        answer(shell, False)
        settled(shell)
        checks["a_no_contacts_nothing"] = calls == [] and shell.last_result[0] == 2 and page.status.get_label() == cat.t("window.update.not_looked")
        page.look.emit("clicked")
        answer(shell, True)
        settled(shell)
        checks["a_yes_asks_once_and_only_for_the_list"] = len(calls) == 1 and calls[0][:3] == ["git", "ls-remote", "--tags"] and shell.last_result[0] == 0
        checks["the_releases_found_are_offered_newest_first"] = page.releases == ("v0.2.0", "v0.1.0") and page.form.get_visible() and not page.status.get_visible() and page.names.get_n_items() == 2
        page.release.set_selected(1)
        page.refresh()
        checks["a_look_keeps_the_release_that_was_picked"] = page.releases[page.release.get_selected()] == "v0.1.0"
        services.networked = lambda _consent, argv, _ids: (calls.append(list(argv)), CommandResult(0, "".join("%s\trefs/tags/%s%s\n" % (SHA, prefix, name) for name in ("v0.1.0", "v0.2.0", "v0.3.0"))))[1]
        page.look.emit("clicked")
        answer(shell, True)
        settled(shell)
        checks["a_look_that_finds_a_newer_release_keeps_the_one_that_was_picked"] = page.releases == ("v0.3.0", "v0.2.0", "v0.1.0") and page.releases[page.release.get_selected()] == "v0.1.0"
        del calls[1:]
        services.networked = stand_in
        page.get.emit("clicked")
        asked = pump(lambda: shell.dialog is not None and shell.form is None)
        shown = message_of(shell.dialog) if shell.dialog is not None else ""
        checks["fetching_says_the_exact_commands_before_it_asks"] = asked and ("git clone --depth 1 --branch %sv0.1.0" % prefix) in shown and len(calls) == 1
        answer(shell, False)
        settled(shell)
        checks["a_no_to_fetching_contacts_nothing_more"] = len(calls) == 1 and shell.last_result[0] == 2
        services.networked = lambda _consent, argv, _ids: (calls.append(list(argv)), CommandResult(0, ""))[1]          # the second look finds nothing
        page.look.emit("clicked")
        answer(shell, True)
        settled(shell)
        checks["a_look_that_finds_no_release_says_so_and_offers_none"] = (page.status.get_label() == cat.t("window.update.none_found") and page.status.get_visible()
                                                                          and not page.form.get_visible() and page.releases == ())
        checks["update_page_controls_are_named_after"] = a11y.unnamed_controls(page.widget) == []
    finally:
        services.networked = real
