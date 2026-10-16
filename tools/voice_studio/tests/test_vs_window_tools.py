# SPDX-License-Identifier: GPL-3.0-or-later
"""What the window shows and asks for on its five pages for the tool's own commands (Hear the voice, Backup, Check the tool, Updates, Problem report), in core/windowmodel.py: plain data from the
files the terminal reads, words from the catalog, nothing written, and a button that is the words of the terminal command. Real flows run through the bridge with scripted answers, which is exactly what
the window does; the update tests use a real git repository on this disk with the phone app's tags in it, and a stand-in for the download module that remembers what it was asked."""
import os
import threading
from pathlib import Path

import pytest

from vs_rounds_helpers import NOW, end_job, fake_job, stamp
from vs_update_helpers import UpdateRig
from vs_voicefile_helpers import ProjectRig, TOOLS, tree_of, write_settings
from voice_studio.core import describe, projectbackup as pb, reportcmd as rc, rounds as rd, text, windowio as wio, windowmodel as wm
from voice_studio.core.envspec import load_environments
from voice_studio.core.registry import load_registry
from voice_studio.core.system import CommandResult
from voice_studio.core.text import size_text

CAT = text.load_catalog("en")
PREFIX = "voice-studio-"


class Script:
    """A sink that answers like a person: the next Yes or No in the list, on a thread of its own."""

    def __init__(self, *answers):
        self.answers, self.questions, self.said, self.done = list(answers), [], [], threading.Event()
        self.result = None

    def line(self, line):
        self.said.append(line)

    def confirm(self, lines, question, reply):
        self.questions.append((lines, question))
        answer = self.answers.pop(0)
        threading.Timer(0.01, lambda: reply(answer)).start()

    def ask(self, lines, prompt, reply):
        raise AssertionError("no typed answer is expected")

    def finished(self, code, lines):
        self.result = (code, lines)
        self.done.set()


@pytest.fixture
def rig(tmp_path):
    return ProjectRig(tmp_path)


def services(rig, **more):
    return wm.Services(rig.home, load_registry(), CAT, rig.training_env, rig.system, **{"tools_dir": str(TOOLS), **more})


def press(svc, button, *answers):
    tool, argv = button
    sink = Script(*answers)
    wio.start_run(lambda io: svc.run(tool, argv, io), sink, svc.titles())
    assert sink.done.wait(30)
    return sink.result, sink


# ---------------------------------------------------------------- the tools the window can run

def test_every_tool_has_the_headings_its_flows_print_first_so_the_window_can_drop_them():
    assert set(wm.TITLE_KEYS) == set(wm.TOOLS) and set(wm.TOOLS) >= {"backup", "refresh", "update", "report"}
    svc = services(ProjectRigStub())
    assert len(svc.titles()) == sum(len(keys) for keys in wm.TITLE_KEYS.values())
    for key in ("update.title", "reportcmd.title", "listen.title", "voicefile.title"):
        assert CAT.t(key) in svc.titles(), key


class ProjectRigStub:
    """Only what Services needs to be made and asked for its headings."""
    home, training_env, system = None, None, None


def test_a_new_services_has_learned_nothing_and_uses_the_registrys_release_address(rig):
    svc = services(rig)
    assert svc.learned.releases is None and svc.learned.report == ""
    assert svc.release_source().tag_prefix == PREFIX and svc.release_source().host == "github.com"
    assert [s.id for s in svc.environments()] == [s.id for s in load_environments()]


# ---------------------------------------------------------------- hear the voice

def test_hearing_lists_the_rounds_a_voice_can_honestly_be_made_from_and_marks_the_chosen_one(rig):
    rig.finish(3)
    view = wm.hear_view(rig.home, "voice-check", CAT)
    record = rd.load(rig.paths)
    assert [r.number for r in view.rounds] == [1, 2, 3] and [r.chosen for r in view.rounds] == [False, False, True] and view.running is None and view.problem == ""
    assert view.rounds[0].line == CAT.t("window.hear.round_row", number=1, minutes=rd.trained_minutes(record, 1))
    assert view.rounds[2].line == CAT.t("window.hear.round_chosen", number=3, minutes=rd.trained_minutes(record, 3)) and "the chosen round" in view.rounds[2].line
    assert view.folder == rig.paths.listening and view.voices == ()


def test_a_round_with_no_settings_file_or_a_damaged_saved_point_is_not_offered(rig):
    rig.finish(3)
    from voice_studio.core import voicefile as vf
    os.unlink(vf.settings_file(rig.paths, 2))
    os.unlink(vf.settings_file(rig.paths, 1))
    os.symlink(vf.settings_file(rig.paths, 3), vf.settings_file(rig.paths, 1))
    assert [r.number for r in wm.hear_view(rig.home, "voice-check", CAT).rounds] == [3]


def test_while_a_round_trains_no_round_is_offered_and_the_view_says_which_trains(rig):
    rig.finish(2)
    plan = rig.world.begin()
    rd.attach_job(rig.paths, plan.number, rig.world.job_for(plan, "running").id)
    view = wm.hear_view(rig.home, "voice-check", CAT)
    assert view.rounds == () and view.running == 3


def test_hearing_lists_the_voice_files_that_were_made_in_the_terminals_words(rig):
    rig.finish(2)
    svc = services(rig)
    (code, _lines), _sink = press(svc, wm.make_args("voice-check"), True)
    assert code == 0
    view = wm.hear_view(rig.home, "voice-check", CAT)
    assert len(view.voices) == 1 and view.voices[0].line == CAT.t("voicefile.list.row", name=view.voices[0].name, size=size_text(os.stat(view.voices[0].zip_path).st_size))
    assert view.voices[0].folder == os.path.dirname(view.voices[0].zip_path)


def test_hearing_says_why_when_the_record_of_rounds_cannot_be_read_and_offers_no_round(rig):
    rig.finish(2)
    Path(rig.paths.rounds_file).write_text("{broken")
    view = wm.hear_view(rig.home, "voice-check", CAT)
    assert view.rounds == () and view.problem and view.running is None


def test_hearing_for_a_project_that_is_not_there_is_none(rig):
    assert wm.hear_view(rig.home, "nobody", CAT) is None


def test_the_words_of_a_hearing_button_are_the_terminals_own(rig):
    assert wm.listen_voice_args("voice-check", "a-voice") == ("voicefile", ["listen", "--project", "voice-check", "--folder=a-voice"])
    assert wm.listen_round_args("voice-check", 3) == ("voicefile", ["listen", "--project", "voice-check", "--round", "3"])
    assert wm.listen_round_args("voice-check", "7")[1][-1] == "7"


def test_hearing_a_round_without_the_training_programs_says_so_and_changes_nothing(tmp_path):
    rig = ProjectRig(tmp_path, environment="absent")
    rig.finish(2)
    before = tree_of(rig.home.root)
    (code, lines), sink = press(services(rig), wm.listen_round_args("voice-check", 2))
    assert code == 1 and sink.questions == [] and any("voice_studio.buildenv" in line for line in lines) and tree_of(rig.home.root) == before


# ---------------------------------------------------------------- backup

def test_a_project_never_backed_up_is_said_so_and_the_page_would_use_the_tools_own_folder(rig):
    rig.finish(2)
    view = wm.backup_view(rig.home, "voice-check", CAT)
    assert view.standing == CAT.t("backup.standing.never", name="Voice check") and view.folder == rig.home.backups and view.how == "default" and view.items == () and view.problem == ""
    assert view.project_id == "voice-check" and view.project_name == "Voice check"


def test_a_backup_made_is_listed_with_the_terminals_row_and_the_project_stands_current(rig):
    rig.finish(2)
    svc = services(rig)
    (code, _lines), sink = press(svc, wm.backup_now_args("voice-check"), True)
    assert code == 0 and len(sink.questions) == 1
    view = wm.backup_view(rig.home, "voice-check", CAT)
    found = pb.list_backups(rig.home.backups, "voice-check")
    assert len(view.items) == 1 and view.items[0].name == found[0]["name"] and view.items[0].path == found[0]["path"]
    assert view.items[0].line == CAT.t("backup.list_row", when=wm.when_text(str(found[0]["created"])), size=size_text(int(found[0]["size"])), name=found[0]["name"])
    assert view.standing.startswith("Nothing precious in Voice check has changed since the last backup")


def test_a_folder_named_for_one_backup_is_the_one_remembered_for_the_next(rig, tmp_path):
    rig.finish(2)
    away = tmp_path / "away"
    away.mkdir()
    svc = services(rig)
    (code, _lines), _sink = press(svc, wm.backup_now_args("voice-check", str(away)), True)
    assert code == 0
    view = wm.backup_view(rig.home, "voice-check", CAT)
    assert view.folder == str(away) and view.how == "remembered" and len(view.items) == 1 and os.path.dirname(view.items[0].path) == str(away)
    assert wm.backup_folder_line(CAT, view.how, view.folder) == CAT.t("window.backup.folder_remembered", folder=str(away))
    assert wm.backup_folder_line(CAT, "default", "/x") == CAT.t("window.backup.folder_default", folder="/x")
    assert wm.backup_folder_line(CAT, "default", "/y", chosen=True) == CAT.t("window.backup.folder_chosen", folder="/y")


def test_a_change_after_a_backup_is_said_and_the_view_changes_nothing(rig):
    rig.finish(2)
    press(services(rig), wm.backup_now_args("voice-check"), True)
    Path(rig.paths.root + "/project.json").write_text(Path(rig.paths.root + "/project.json").read_text().replace("Voice check", "Voice check two"))
    before = tree_of(rig.home.root)
    view = wm.backup_view(rig.home, "voice-check", CAT)
    assert "has changed since the last backup" in view.standing and tree_of(rig.home.root) == before


def test_backup_says_why_when_the_record_of_rounds_cannot_be_read(rig):
    rig.finish(2)
    Path(rig.paths.rounds_file).write_text("{broken")
    view = wm.backup_view(rig.home, "voice-check", CAT)
    assert view.problem and view.items == () and view.standing == ""


def test_backup_for_a_project_that_is_not_there_is_none(rig):
    assert wm.backup_view(rig.home, "nobody", CAT) is None


def test_the_words_of_the_backup_buttons_are_the_terminals_own():
    assert wm.backup_now_args("p") == ("backup", ["now", "--project", "p"])
    assert wm.backup_now_args("p", "/a b", saved_points=False) == ("backup", ["now", "--project", "p", "--to=/a b", "--without-saved-points"])
    assert wm.backup_now_args("p", saved_points=False)[1] == ["now", "--project", "p", "--without-saved-points"]
    assert wm.backup_verify_args("/x/--odd.tar") == ("backup", ["verify", "--", "/x/--odd.tar"])
    assert wm.backup_restore_args("-rf.tar") == ("backup", ["restore", "--", "-rf.tar"])


def test_a_folder_for_a_backup_must_be_a_whole_path():
    assert wm.check_backup_folder(CAT, "/home/x/backups") == ()
    for bad in ("", "relative/folder", "~/x", "/a\nb", "/a\x00b"):
        assert wm.check_backup_folder(CAT, bad) == (CAT.t("window.backup.need_folder"),), bad


def test_putting_back_a_backup_that_has_nothing_to_add_asks_nothing_and_checking_it_says_it_is_whole(rig):
    rig.finish(2)
    svc = services(rig)
    press(svc, wm.backup_now_args("voice-check"), True)
    item = wm.backup_view(rig.home, "voice-check", CAT).items[0]
    (code, lines), sink = press(svc, wm.backup_verify_args(item.path))
    assert code == 0 and CAT.t("backup.verify_ok", name=item.name) in lines and sink.questions == []
    before = tree_of(rig.home.root)
    (code, lines), sink = press(svc, wm.backup_restore_args(item.path))
    assert code == 0 and CAT.t("backup.restore_nothing") in lines and sink.questions == [] and tree_of(rig.home.root) == before


# ---------------------------------------------------------------- check the tool

def test_the_programs_choice_offers_all_and_then_each_set_named_as_the_terminal_names_it():
    specs = load_environments()
    choices = wm.programs_choices(CAT, specs)
    assert choices[0] == wm.ProgramsChoice("", CAT.t("window.refresh.all_programs")) and [c.id for c in choices[1:]] == ["studio", "training"] and len(choices) == 1 + len(specs)
    assert [c.label for c in choices[1:]] == [CAT.t("refresh.name.studio"), CAT.t("refresh.name.training")]
    assert [c.id for c in wm.programs_choices(CAT, tuple(reversed(specs)))[1:]] == ["studio", "training"], "the order does not depend on the order the sets were listed in"


def test_the_words_of_the_refresh_buttons_are_the_terminals_own():
    assert wm.refresh_check_args() == ("refresh", ["check"]) and wm.refresh_check_args(quick=True) == ("refresh", ["check", "--quick"])
    assert wm.refresh_repair_args() == ("refresh", ["repair"])
    assert wm.refresh_rebuild_args() == ("refresh", ["rebuild"]) and wm.refresh_rebuild_args("training") == ("refresh", ["rebuild", "--programs=training"])
    assert wm.refresh_older_args() == ("refresh", ["older"]) and wm.refresh_older_args(remove=True) == ("refresh", ["older", "--remove"])


def test_a_quick_look_and_the_older_copies_change_nothing_and_ask_nothing(rig):
    svc = services(rig)
    before = tree_of(rig.home.root)
    (code, lines), sink = press(svc, wm.refresh_check_args(quick=True))
    assert lines and sink.questions == [] and tree_of(rig.home.root) == before
    (code, lines), sink = press(svc, wm.refresh_older_args(remove=True))
    assert code == 0 and CAT.t("refresh.older.none") in lines and sink.questions == [] and tree_of(rig.home.root) == before


def test_a_fresh_copy_with_nothing_set_up_says_so_and_starts_nothing(rig):
    from voice_studio.core.refresh_flow import SETUP_COMMAND
    before = tree_of(rig.home.root)
    (code, lines), sink = press(services(rig), wm.refresh_rebuild_args("training"))
    assert code == 2 and CAT.t("refresh.rebuild.nothing_set_up", command=SETUP_COMMAND) in lines and sink.questions == [] and tree_of(rig.home.root) == before
    (code, lines), _sink = press(services(rig), wm.refresh_rebuild_args("nonsense"))
    assert code == 2 and CAT.t("refresh.rebuild.unknown", name="nonsense", names=", ".join(c.id for c in wm.programs_choices(CAT, load_environments())[1:])) in lines


# ---------------------------------------------------------------- updates

def update_services(tmp_path, rig, **more):
    updates = UpdateRig(tmp_path / "upd", releases=("v0.1.0", "v0.2.0"), here_at="v0.1.0", tag_prefix=PREFIX, app_tags=("v1.0-beta.1", "v1.0-beta.2"))
    svc = services(rig, source=updates.source, networked=updates.networked, tools_dir=str(updates.here / "tools"), version="1.0.0", **more)
    svc.system = updates.system
    return svc, updates


def test_the_update_view_says_which_copy_this_is_and_that_nothing_was_looked_for(tmp_path, rig):
    (tmp_path / "upd").mkdir()
    svc, updates = update_services(tmp_path, rig)
    view = wm.update_view(svc)
    assert view.releases is None and view.here == (CAT.t("update.here", version="1.0.0", folder=str(updates.here)),) and updates.calls == []


def test_a_copy_that_is_not_a_plain_git_copy_says_so_in_the_view(tmp_path, rig):
    svc = services(rig, tools_dir=str(tmp_path / "plain" / "tools"), version="2.0.0")
    view = wm.update_view(svc)
    assert view.here == (CAT.t("update.here", version="2.0.0", folder=str(tmp_path / "plain")), CAT.t("update.here_no_git"))


def test_looking_for_releases_asks_first_and_a_no_contacts_nothing(tmp_path, rig):
    (tmp_path / "upd").mkdir()
    svc, updates = update_services(tmp_path, rig)
    (code, lines), sink = press(svc, wm.update_check_args(), False)
    assert code == 2 and updates.calls == [] and svc.learned.releases is None and len(sink.questions) == 1
    shown, question = sink.questions[0]
    assert question == wio.question_text(CAT.t("update.question.check")) and any("git ls-remote --tags " + updates.url in line for line in shown)


def test_a_yes_asks_once_and_the_window_learns_the_tools_own_releases_newest_first_and_not_the_apps(tmp_path, rig):
    (tmp_path / "upd").mkdir()
    svc, updates = update_services(tmp_path, rig)
    (code, lines), _sink = press(svc, wm.update_check_args(), True)
    assert code == 0 and len(updates.calls) == 1 and updates.calls[0][0][:3] == ["git", "ls-remote", "--tags"]
    assert svc.learned.releases == ("v0.2.0", "v0.1.0") and wm.update_view(svc).releases == ("v0.2.0", "v0.1.0")
    assert not any("beta" in name for name in svc.learned.releases)


def test_a_look_that_finds_no_release_of_the_tool_teaches_an_empty_list_not_nothing(tmp_path, rig):
    updates = UpdateRig(tmp_path, releases=(), here_at=None, tag_prefix=PREFIX, app_tags=("v1.0-beta.1",))
    svc = services(rig, source=updates.source, networked=updates.networked, tools_dir=str(tmp_path / "x"), version="1.0.0")
    svc.system = updates.system
    (code, lines), _sink = press(svc, wm.update_check_args(), True)
    assert code == 0 and svc.learned.releases == () and wm.update_view(svc).releases == () and CAT.t("update.releases.none") in lines


def test_a_look_that_fails_teaches_nothing(tmp_path, rig):
    updates = UpdateRig(tmp_path, releases=("v0.1.0",), here_at=None, tag_prefix=PREFIX)
    svc = services(rig, source=updates.source, networked=lambda c, a, i: CommandResult(128, "", "unreachable"), tools_dir=str(tmp_path / "x"), version="1.0.0")
    svc.system = updates.system
    (code, _lines), _sink = press(svc, wm.update_check_args(), True)
    assert code == 1 and svc.learned.releases is None


def test_fetching_names_the_exact_commands_and_a_no_contacts_nothing_more(tmp_path, rig):
    (tmp_path / "upd").mkdir()
    svc, updates = update_services(tmp_path, rig)
    press(svc, wm.update_check_args(), True)
    calls_before = len(updates.calls)
    (code, _lines), sink = press(svc, wm.update_get_args("v0.2.0"), False)
    shown, _question = sink.questions[0]
    assert code == 2 and len(updates.calls) == calls_before and any(("git clone --depth 1 --branch %sv0.2.0 " % PREFIX) in line for line in shown)


def test_the_words_of_the_update_buttons_are_the_terminals_own():
    assert wm.update_check_args() == ("update", ["check"])
    assert wm.update_get_args("v1.2") == ("update", ["get", "--", "v1.2"])


# ---------------------------------------------------------------- the problem report

def test_a_failure_names_the_step_and_the_one_problem_it_told_and_no_problem_when_it_told_two_or_none():
    assert wm.failure_about("backup", ["now", "--project", "x"], [("backup", "no_room")]) == wm.Failure("backup now", "backup/no_room")
    assert wm.failure_about("backup", ["now"], []) == wm.Failure("backup now", "")
    assert wm.failure_about("backup", ["now"], [("backup", "no_room"), ("rounds", "damaged")]) == wm.Failure("backup now", "")
    assert wm.failure_about("voicefile", ["listen", "--project", "x"], [("a b", "c")]) == wm.Failure("voicefile listen", "")
    assert wm.failure_about("refresh", ["--quick"], [("refresh", "x")]).step == "refresh"
    assert wm.failure_about("update", ["get", "--", "v1"], ()).step == "update get"


def test_the_failure_the_window_reports_is_the_one_the_terminals_closing_lines_would_name():
    for argv in (["check"], ["get", "v1"], ["now", "--project", "p"], []):
        assert wm.failure_about("update", argv, [("update", "unreachable")]).step == rc.step_of("update", argv)
        assert wm.failure_about("update", argv, [("update", "unreachable")]).problem == "update/unreachable"
        assert ("--problem update/unreachable" in rc.hint_command("update", argv, [("update", "unreachable")])) is True


def test_report_buttons_are_the_terminals_own_words_and_the_log_goes_only_with_a_task():
    assert wm.report_args(wm.ReportFields()) == ("report", ["show"])
    assert wm.report_args(wm.ReportFields(step="  update check  ", problem="update/unreachable", job="last", include_log=True)) == (
        "report", ["show", "--step=update check", "--problem=update/unreachable", "--job=last", "--include-log"])
    assert wm.report_args(wm.ReportFields(include_log=True)) == ("report", ["show"]), "the end of a log is asked for only together with a task"
    assert wm.report_args(wm.ReportFields(job="20261011-000001"))[1] == ["show", "--job=20261011-000001"]
    assert wm.report_args(wm.ReportFields(step="x" * 500))[1] == ["show", "--step=" + "x" * rc.MAX_STEP]
    assert wm.report_args(wm.ReportFields(step="  "))[1] == ["show"]
    assert wm.report_args(wm.ReportFields(step="a"), save_to="/f/r.txt") == ("report", ["save", "--step=a", "--to=/f/r.txt"])
    assert wm.report_args(wm.ReportFields(), save_to="/--odd")[1] == ["save", "--to=/--odd"]


def test_the_task_choices_are_none_the_newest_and_then_the_newest_few_by_name_and_how_they_ended(rig):
    assert wm.job_choices(rig.home, CAT) == (("", CAT.t("window.report.no_task")),)
    for _ in range(wm.RECENT_TASKS + 2):
        fake_job(rig.home.jobs, ["x"], "failed", name="j%02d" % _, age=100 - _)
    rows = wm.job_choices(rig.home, CAT)
    assert rows[0] == ("", CAT.t("window.report.no_task")) and rows[1] == (wm.LAST_TASK, CAT.t("window.report.newest_task")) and len(rows) == 2 + wm.RECENT_TASKS
    ids = [value for value, _words in rows[2:]]
    from voice_studio.core import jobs
    newest_first = [j.id for j in reversed(jobs.list_jobs(rig.home.jobs).jobs)][:wm.RECENT_TASKS]
    assert ids == newest_first
    first = jobs.list_jobs(rig.home.jobs).jobs[-1]
    assert rows[2][1] == CAT.t("window.report.task_row", id=first.id, kind=first.spec.kind, status=describe.status_text(CAT, first.status))


def test_a_report_shown_teaches_the_window_its_exact_text_and_changes_nothing(rig):
    svc = services(rig)
    before = tree_of(rig.home.root)
    (code, lines), sink = press(svc, wm.report_args(wm.ReportFields(step="update check")))
    assert code == 0 and sink.questions == [] and tree_of(rig.home.root) == before
    report = svc.learned.report
    assert report.startswith(CAT.t("report.title")) and "Step: update check" in report
    start, end = CAT.t("reportcmd.rule.start"), CAT.t("reportcmd.rule.end")
    assert list(lines[lines.index(start) + 1:lines.index(end)]) == report.rstrip("\n").split("\n")
    assert rig.home.root not in report


def test_a_report_that_cannot_be_built_teaches_nothing_new(rig):
    svc = services(rig)
    (code, _lines), _sink = press(svc, ("report", ["show", "--problem=not-a-name"]))
    assert code == 2 and svc.learned.report == ""


def test_saving_shows_the_report_before_it_asks_a_no_writes_nothing_and_a_yes_writes_what_was_shown(rig, tmp_path):
    svc = services(rig)
    folder = tmp_path / "out"
    folder.mkdir()
    target = str(folder / "r.txt")
    (code, lines), sink = press(svc, wm.report_args(wm.ReportFields(step="x"), save_to=target), False)
    assert code == 2 and not os.path.exists(target) and len(sink.questions) == 1
    shown, question = sink.questions[0]
    assert "Step: x" in "\n".join(shown) and question == wio.question_text(CAT.t("reportcmd.save.question", file=target))
    (code, lines), sink = press(svc, wm.report_args(wm.ReportFields(step="x"), save_to=target), True)
    assert code == 0 and Path(target).read_text(encoding="utf-8").strip() == svc.learned.report.strip()
    (code, lines), sink = press(svc, wm.report_args(wm.ReportFields(step="x"), save_to=target), True)
    assert code == 2 and sink.questions == [] and Path(target).read_text(encoding="utf-8").strip() != "", "a file that is there is never replaced"


@pytest.mark.parametrize("folder,name,problem", [("", "r.txt", "window.report.need_folder"), ("relative", "r.txt", "window.report.need_folder"), ("/tmp", "", "window.report.need_name"),
                                                  ("/tmp", "   ", "window.report.need_name"), ("/tmp", "a/b", "window.report.bad_name"), ("/tmp", "a\\b", "window.report.bad_name"),
                                                  ("/tmp", ".", "window.report.bad_name"), ("/tmp", "..", "window.report.bad_name"), ("/tmp", "a\nb", "window.report.bad_name"),
                                                  ("/tmp", "a\x00b", "window.report.bad_name"), ("/tmp", "x" * (wm.MAX_REPORT_FILE_NAME + 1), "window.report.bad_name")])
def test_a_place_for_the_report_must_be_a_chosen_folder_and_a_plain_file_name(folder, name, problem):
    problems, path = wm.check_report_save(CAT, folder, name)
    assert path == "" and CAT.t(problem, limit=wm.MAX_REPORT_FILE_NAME) in problems


def test_both_a_missing_folder_and_a_missing_name_are_said_together():
    problems, path = wm.check_report_save(CAT, "", "")
    assert path == "" and problems == (CAT.t("window.report.need_folder"), CAT.t("window.report.need_name"))


def test_the_longest_file_name_is_accepted_and_the_place_is_held_to_the_terminals_own_rules(tmp_path):
    problems, path = wm.check_report_save(CAT, str(tmp_path), "x" * wm.MAX_REPORT_FILE_NAME)
    assert problems == () and path == str(tmp_path) + "/" + "x" * wm.MAX_REPORT_FILE_NAME
    problems, path = wm.check_report_save(CAT, str(tmp_path) + "/", "  r.txt  ")
    assert problems == () and path == str(tmp_path) + "/r.txt"
    (tmp_path / "r.txt").write_text("mine")
    problems, path = wm.check_report_save(CAT, str(tmp_path), "r.txt")
    assert path == "" and problems == (CAT.t("reportcmd.error.file_exists.what"),) and (tmp_path / "r.txt").read_text() == "mine"
    problems, path = wm.check_report_save(CAT, str(tmp_path / "missing"), "r.txt")
    assert path == "" and problems == (CAT.t("reportcmd.error.folder_missing.what"),)


# ---------------------------------------------------------------- the record as it really is, and what the services hand to each flow

def round_ended_since_the_record_was_saved(rig, number=2):
    """A round that finished after the record was last written: the record on disk still says it runs."""
    plan = rig.world.begin()
    info = rig.world.job_for(plan, "running")
    rd.attach_job(rig.paths, plan.number, info.id)
    rig.world.trainer_makes(number - 1)
    end_job(info.dir, "finished", ended_at=stamp(20))


def test_the_backup_page_reads_the_rounds_as_they_really_are_now_and_writes_nothing(rig):
    rig.finish(1)
    press(services(rig), wm.backup_now_args("voice-check"), True)
    round_ended_since_the_record_was_saved(rig)
    before = tree_of(rig.home.root)
    view = wm.backup_view(rig.home, "voice-check", CAT, now=NOW)
    assert "has changed since the last backup" in view.standing, "the saved point the ended round made is something precious that the last backup does not hold"
    assert tree_of(rig.home.root) == before and rd.load(rig.paths).rounds[1].state == "running"


def test_the_backup_page_works_out_how_the_project_stands_from_the_record_it_has_just_read(rig, monkeypatch):
    rig.finish(1)
    seen = []
    real = wm.pb.standing
    monkeypatch.setattr(wm.pb, "standing", lambda home, paths, project_id, record=None: (seen.append(record), real(home, paths, project_id, record))[1])
    wm.backup_view(rig.home, "voice-check", CAT, now=NOW)
    assert len(seen) == 1 and isinstance(seen[0], rd.Record), "a second read of the record could disagree with the one the page's rounds came from"


def test_the_rounds_page_is_given_the_time_it_asks_for(rig):
    rig.finish(1)
    rig.world.begin()                                                  # begun at NOW and with no task yet: it has a short while to start
    assert wm.rounds_view(rig.home, "voice-check", CAT, now=NOW).running == 2
    assert wm.rounds_view(rig.home, "voice-check", CAT).running is None, "by the clock of this computer, long after, it never started"


def test_the_hear_page_reads_the_rounds_as_they_really_are_now_and_writes_nothing(rig):
    rig.finish(1)
    round_ended_since_the_record_was_saved(rig)
    write_settings(rig.paths, 2)
    before = tree_of(rig.home.root)
    view = wm.hear_view(rig.home, "voice-check", CAT, now=NOW)
    assert view.running is None and [r.number for r in view.rounds] == [1, 2]
    assert tree_of(rig.home.root) == before and rd.load(rig.paths).rounds[1].state == "running"


def test_a_round_that_has_only_just_begun_is_still_training_for_the_time_the_page_is_given(rig):
    rig.finish(1)
    rig.world.begin()                                                  # begun at NOW and with no task yet: it has a short while to start
    assert wm.hear_view(rig.home, "voice-check", CAT, now=NOW).running == 2
    assert wm.hear_view(rig.home, "voice-check", CAT).running is None, "by the clock of this computer, long after, it never started"


def test_a_backup_of_another_project_in_the_same_folder_is_not_listed(rig, tmp_path):
    from voice_studio.core.project import create_project
    create_project(rig.home.projects, "Second", "own")
    shared = tmp_path / "shared"
    shared.mkdir()
    svc = services(rig)
    press(svc, wm.backup_now_args("voice-check", str(shared)), True)
    press(svc, wm.backup_now_args("second", str(shared)), True)
    assert len(os.listdir(shared)) >= 2
    for project in ("voice-check", "second"):
        items = wm.backup_view(rig.home, project, CAT).items
        assert len(items) == 1 and project in items[0].name


def test_a_view_that_cannot_read_the_rounds_still_says_where_backups_go_and_which_voice_files_there_are(rig):
    rig.finish(2)
    press(services(rig), wm.make_args("voice-check"), True)
    Path(rig.paths.rounds_file).write_text("{broken")
    backup = wm.backup_view(rig.home, "voice-check", CAT)
    assert backup.problem and backup.folder == rig.home.backups and backup.how == "default" and backup.project_name == "Voice check"
    hear = wm.hear_view(rig.home, "voice-check", CAT)
    assert hear.problem and len(hear.voices) == 1 and hear.folder == rig.paths.listening and hear.project_id == "voice-check"


def test_a_project_with_nothing_to_lose_has_no_standing_sentence(rig, monkeypatch):
    monkeypatch.setattr(pb, "standing", lambda home, paths, project_id, record=None: pb.Standing(pb.CURRENT, "", ""))
    assert wm.backup_view(rig.home, "voice-check", CAT).standing == ""


def test_the_programs_choice_puts_known_sets_first_and_any_other_after_them_by_name():
    from types import SimpleNamespace
    sets = [SimpleNamespace(id=name) for name in ("zeta", "training", "alpha", "studio")]
    assert [c.id for c in wm.programs_choices(CAT, sets)] == ["", "studio", "training", "alpha", "zeta"]
    assert wm.programs_choices(CAT, sets)[2].label == CAT.t("refresh.name.training") and wm.programs_choices(CAT, sets)[3].label == CAT.t("refresh.name.other", id="alpha")


@pytest.mark.parametrize("name", ["a\rb", "a\nb", "a\x00b", "a\\b", "a/b"])
def test_each_character_a_file_name_cannot_hold_is_refused(name):
    problems, path = wm.check_report_save(CAT, "/tmp", name)
    assert path == "" and problems == (CAT.t("window.report.bad_name", limit=wm.MAX_REPORT_FILE_NAME),)


def test_the_services_hand_each_flow_what_they_hold(rig, monkeypatch):
    seen = {}

    def spy(name):
        def run(argv, *args, **kwargs):
            seen[name] = (list(argv), args, kwargs)
            return 0
        return run
    for name in ("run_refresh", "run_update", "run_report", "run_backup"):
        monkeypatch.setattr(wm, name, spy(name))
    specs, networked, source = (object(),), object(), object()
    svc = services(rig, specs=specs, networked=networked, source=source, version="9.9.9", tools_dir="/the/tools")
    for tool in ("refresh", "update", "report", "backup"):
        assert svc.run(tool, ["x"], "the-io") == 0
    assert seen["run_refresh"][2]["specs"] is specs and seen["run_refresh"][2]["networked"] is networked and seen["run_refresh"][2]["registry"] is svc.registry
    update = seen["run_update"][2]
    assert update["source"] is source and update["networked"] is networked and update["version"] == "9.9.9" and update["tools_dir"] == "/the/tools" and update["system"] is svc.system
    svc.learned.releases = None
    update["on_releases"](["v2", "v1"])
    assert svc.learned.releases == ("v2", "v1")
    report = seen["run_report"][2]
    assert report["system"] is svc.system
    report["on_report"]("the text")
    assert svc.learned.report == "the text"
    with pytest.raises(ValueError):
        svc.run("nonsense", [], "io")


def test_the_services_with_nothing_given_use_the_shipped_sets_and_address(rig):
    svc = services(rig)
    from voice_studio.core.registry import load_release_source
    assert svc.environments() == load_environments() and svc.release_source() == load_release_source()
    assert [s.id for s in svc.environments()] and svc.release_source().url.startswith("https://")
    given = (object(),)
    assert services(rig, specs=given).environments() is given


def test_the_window_builds_its_pages_and_their_titles_in_the_one_order_the_model_names():
    import re
    source = (Path(__file__).resolve().parents[1] / "window" / "shell.py").read_text(encoding="utf-8")
    classes = re.search(r"self\.pages: List\[Page\] = \[(.*?)\]\n", source, flags=re.S).group(1)
    assert re.findall(r"(\w+)\(self\)", classes) == ["ProjectsPage", "RecordingsPage", "RoundsPage", "HearPage", "VoiceFilePage", "BackupPage", "FreePage", "RefreshPage", "UpdatePage", "ReportPage", "DisplayPage"]
    assert re.findall(r'cat\.t\("window\.nav\.(\w+)"\)', source.split("titles = (")[1].split(")\n")[0] + ")") == list(wm.PAGES)
    assert "self.page_names = wm.PAGES" in source and len(set(wm.PAGES)) == len(wm.PAGES) == 11
    assert [CAT.t("window.nav." + name) for name in wm.PAGES] == ["Projects", "Recordings", "Training rounds", "Hear the voice", "Voice file", "Backup", "Free up space", "Check the tool", "Updates",
                                                                  "Problem report", "Display"]
