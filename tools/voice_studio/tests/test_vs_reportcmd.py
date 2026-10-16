# SPDX-License-Identifier: GPL-3.0-or-later
"""The problem report as a command (plan task VS-6.4, decision P22): the problem name, the task, the place a file may go, the saving, and the line a failed command ends with."""
import errno
import os
import stat
from datetime import datetime, timezone
from pathlib import Path

import pytest

from vs_refresh_helpers import CAT
from vs_rounds_helpers import fake_job
from voice_studio.core import describe, jobs, report as rp, reportcmd as rc
from voice_studio.core.report import Report


@pytest.fixture(autouse=True)
def nothing_shown_yet():
    describe.forget_errors_shown()
    yield
    describe.forget_errors_shown()


def code_of(fn, *args, **kw):
    with pytest.raises(rc.ReportError) as caught:
        fn(*args, **kw)
    return caught.value.code


def a_report(text="line one\nline two\n"):
    return Report(text, 0, False)


# ---------------------------------------------------------------- the problem name

def test_a_problem_name_is_one_the_catalog_has_the_three_parts_of_words_for():
    assert rc.parse_problem(CAT, "update/unreachable") == ("update", "unreachable")
    assert rc.parse_problem(CAT, "reportcmd/cannot_save") == ("reportcmd", "cannot_save")


@pytest.mark.parametrize("name", ["update", "update/", "/unreachable", "update/nothing_like_it", "nothing/unreachable", "Update/unreachable", "update/unreachable\n", "update/unreachable ",
                                  "update/unreachable/x", "../x", "", " ", "a" * 31 + "/x", "update/" + "a" * 41, "9update/unreachable", "update/Unreachable", "update.error/unreachable"])
def test_anything_else_is_not_a_problem_name(name):
    assert code_of(rc.parse_problem, CAT, name) == "bad_problem"


def test_a_name_that_is_not_known_is_shown_cut_to_eighty_letters():
    with pytest.raises(rc.ReportError) as caught:
        rc.parse_problem(CAT, "x" * 200)
    assert caught.value.detail == "x" * 80


def test_the_longest_name_the_pattern_allows_is_still_looked_up():
    assert code_of(rc.parse_problem, CAT, "a" * 31 + "/" + "b" * 41) == "bad_problem"
    assert rc.PROBLEM_NAME.match("a" * 31 + "/" + "b" * 41) and not rc.PROBLEM_NAME.match("a" * 32 + "/b") and not rc.PROBLEM_NAME.match("a/" + "b" * 42)


def test_the_patterns_end_exactly_at_the_last_letter_and_start_with_a_letter():
    assert rc.PROBLEM_NAME.match("update/unreachable") and not rc.PROBLEM_NAME.match("update/unreachable\n") and not rc.PROBLEM_NAME.match("9a/b") and not rc.PROBLEM_NAME.match("a/9b")
    assert rc.STEP_WORD.match("get-it") and not rc.STEP_WORD.match("get\n") and not rc.STEP_WORD.match("9get") and not rc.STEP_WORD.match("a" * 21) and rc.STEP_WORD.match("a" * 20)


# ---------------------------------------------------------------- which task

@pytest.fixture
def jobs_root(tmp_path):
    root = tmp_path / "jobs"
    root.mkdir()
    return str(root)


def test_last_is_the_newest_task_and_an_id_is_that_task(jobs_root):
    first = fake_job(jobs_root, ["x"], "failed", name="20261011-000001-train-0001", exit_code=1)
    second = fake_job(jobs_root, ["x"], "finished", name="20261011-000002-train-0002", exit_code=0)
    assert rc.pick_job(jobs_root, "last").id == second.id and rc.pick_job(jobs_root, first.id).id == first.id and rc.pick_job(jobs_root, second.id).id == second.id


def test_no_task_and_no_such_task_are_both_no_job(jobs_root, tmp_path):
    assert code_of(rc.pick_job, jobs_root, "last") == "no_job" and code_of(rc.pick_job, str(tmp_path / "missing"), "last") == "no_job"
    fake_job(jobs_root, ["x"], "failed", name="20261011-000001-train-0001", exit_code=1)
    assert code_of(rc.pick_job, jobs_root, "20261011-000001-train-000") == "no_job" and code_of(rc.pick_job, jobs_root, "LAST") == "no_job"
    with pytest.raises(rc.ReportError) as caught:
        rc.pick_job(jobs_root, "y" * 200)
    assert caught.value.detail == "y" * 80


def test_a_task_called_last_is_not_confused_with_the_newest(jobs_root):
    assert rc.LAST == "last"


# ---------------------------------------------------------------- where the file may go

def test_a_place_needs_a_whole_path_and_a_folder_that_exists_and_makes_no_folder(tmp_path):
    good = rc.check_place(str(tmp_path / "r.txt"), False)
    assert good == str(tmp_path / "r.txt")
    assert code_of(rc.check_place, "r.txt", False) == "not_absolute" and code_of(rc.check_place, "sub/r.txt", False) == "not_absolute"
    assert code_of(rc.check_place, str(tmp_path / "missing" / "r.txt"), False) == "folder_missing" and not (tmp_path / "missing").exists()
    (tmp_path / "plain").write_text("x")
    assert code_of(rc.check_place, str(tmp_path / "plain" / "r.txt"), False) == "folder_missing"


def test_a_place_with_a_tilde_or_dots_is_tidied(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    assert rc.check_place("~/r.txt", False) == str(tmp_path / "r.txt")
    (tmp_path / "a").mkdir()
    assert rc.check_place(str(tmp_path / "a" / ".." / "r.txt"), False) == str(tmp_path / "r.txt")


def test_a_file_that_is_there_is_never_a_place_unless_replacing_and_then_only_a_plain_file(tmp_path):
    (tmp_path / "there.txt").write_text("mine")
    assert code_of(rc.check_place, str(tmp_path / "there.txt"), False) == "file_exists"
    assert rc.check_place(str(tmp_path / "there.txt"), True) == str(tmp_path / "there.txt")
    (tmp_path / "folder").mkdir()
    assert code_of(rc.check_place, str(tmp_path / "folder"), False) == "file_exists" and code_of(rc.check_place, str(tmp_path / "folder"), True) == "not_a_file"
    os.symlink(tmp_path / "there.txt", tmp_path / "link.txt")
    os.symlink(tmp_path / "nowhere", tmp_path / "dangling.txt")
    for name in ("link.txt", "dangling.txt"):
        assert code_of(rc.check_place, str(tmp_path / name), False) == "file_exists" and code_of(rc.check_place, str(tmp_path / name), True) == "not_a_file"
    assert (tmp_path / "there.txt").read_text() == "mine"


def test_the_detail_of_a_refused_place_is_the_place_or_the_folder_that_is_missing(tmp_path):
    with pytest.raises(rc.ReportError) as caught:
        rc.check_place(str(tmp_path / "gone" / "r.txt"), False)
    assert caught.value.detail == str(tmp_path / "gone")
    with pytest.raises(rc.ReportError) as caught:
        rc.check_place("r" * 300, False)
    assert caught.value.detail == "r" * 200
    (tmp_path / "x.txt").write_text("1")
    with pytest.raises(rc.ReportError) as caught:
        rc.check_place(str(tmp_path / "x.txt"), False)
    assert caught.value.detail == str(tmp_path / "x.txt")


def test_a_folder_a_cloud_service_copies_is_noticed_and_an_ordinary_one_is_not(tmp_path):
    assert rc.sync_reason(str(tmp_path / "r.txt")) is None and rc.sync_reason(str(tmp_path / "OneDrive")) is None, "the folder is judged, not the name of the file"
    assert "OneDrive" in rc.sync_reason(str(tmp_path / "OneDrive" / "r.txt"))


# ---------------------------------------------------------------- saving

def test_the_file_holds_exactly_the_text_and_only_its_owner_can_read_it(tmp_path):
    path = str(tmp_path / "r.txt")
    size = rc.save(path, a_report("héllo\nline two\n"), False)
    assert Path(path).read_bytes() == "héllo\nline two\n".encode("utf-8") and size == len("héllo\nline two\n".encode("utf-8"))
    assert stat.S_IMODE(os.stat(path).st_mode) == 0o600


def test_a_file_that_is_there_is_not_replaced_unless_that_was_asked(tmp_path):
    path = tmp_path / "r.txt"
    path.write_text("mine")
    assert code_of(rc.save, str(path), a_report(), False) == "file_exists" and path.read_text() == "mine"
    assert rc.save(str(path), a_report("new\n"), True) == 4 and path.read_text() == "new\n"


def test_a_file_someone_made_after_the_place_was_checked_is_theirs_and_is_left_alone(tmp_path, monkeypatch):
    path = tmp_path / "r.txt"

    def raced(target, report, overwrite=False):
        path.write_text("theirs")
        raise FileExistsError(errno.EEXIST, "already exists", target)
    monkeypatch.setattr(rc, "write_report", raced)
    with pytest.raises(rc.ReportError) as caught:
        rc.save(str(path), a_report(), False)
    assert caught.value.code == "file_exists" and caught.value.detail == str(path) and path.read_text() == "theirs"


def test_a_write_that_fails_half_way_leaves_no_file_of_ours_and_names_the_reason(tmp_path, monkeypatch):
    path = tmp_path / "r.txt"

    def half(target, report, overwrite=False):
        Path(target).write_bytes(b"half")
        raise OSError(errno.ENOSPC, "No space left on device")
    monkeypatch.setattr(rc, "write_report", half)
    with pytest.raises(rc.ReportError) as caught:
        rc.save(str(path), a_report(), False)
    assert caught.value.code == "cannot_save" and caught.value.detail == "No space left on device" and not path.exists()


def test_a_failed_replace_keeps_the_old_file(tmp_path, monkeypatch):
    path = tmp_path / "r.txt"
    path.write_text("mine")

    def fails(target, report, overwrite=False):
        raise OSError(errno.EACCES, "Permission denied")
    monkeypatch.setattr(rc, "write_report", fails)
    assert code_of(rc.save, str(path), a_report(), True) == "cannot_save" and path.read_text() == "mine"


def test_ctrl_c_half_way_removes_the_half_written_file_and_goes_on_raising(tmp_path, monkeypatch):
    path = tmp_path / "r.txt"

    def interrupted(target, report, overwrite=False):
        if not overwrite:
            Path(target).write_bytes(b"half")                # a replace is written beside the file and moved over it, so the file itself is never half written
        raise KeyboardInterrupt
    monkeypatch.setattr(rc, "write_report", interrupted)
    with pytest.raises(KeyboardInterrupt):
        rc.save(str(path), a_report(), False)
    assert not path.exists()
    path.write_text("mine")
    with pytest.raises(KeyboardInterrupt):
        rc.save(str(path), a_report(), True)
    assert path.read_text() == "mine", "a file that was there before is never removed"


def test_what_was_written_is_read_back_and_a_difference_removes_the_new_file(tmp_path, monkeypatch):
    path = tmp_path / "r.txt"

    def wrong(target, report, overwrite=False):
        Path(target).write_bytes(b"not the report")
    monkeypatch.setattr(rc, "write_report", wrong)
    with pytest.raises(rc.ReportError) as caught:
        rc.save(str(path), a_report(), False)
    assert caught.value.code == "cannot_save" and "did not hold" in caught.value.detail and not path.exists()


def test_a_file_that_cannot_be_read_back_is_a_failure_and_goes(tmp_path, monkeypatch):
    path = tmp_path / "r.txt"
    real = open

    def refuse(name, *a, **kw):
        if str(name) == str(path) and a and a[0] == "rb":
            raise OSError(errno.EIO, "Input/output error")
        return real(name, *a, **kw)
    monkeypatch.setattr("builtins.open", refuse)
    with pytest.raises(rc.ReportError) as caught:
        rc.save(str(path), a_report(), False)
    monkeypatch.undo()
    assert caught.value.detail == "Input/output error" and not path.exists()


def test_an_error_with_no_reason_is_named_by_its_kind(tmp_path, monkeypatch):
    class Odd(OSError):
        pass

    def fails(target, report, overwrite=False):
        raise Odd()
    monkeypatch.setattr(rc, "write_report", fails)
    with pytest.raises(rc.ReportError) as caught:
        rc.save(str(tmp_path / "r.txt"), a_report(), False)
    assert caught.value.detail == "Odd"


def test_an_error_reads_as_its_code_and_its_detail():
    assert str(rc.ReportError("cannot_save")) == "cannot_save" and str(rc.ReportError("cannot_save", "no room")) == "cannot_save: no room"
    assert rc.ReportError("cannot_save", "no room").detail == "no room" and rc.ReportError("cannot_save").detail == ""


# ---------------------------------------------------------------- the line a failed command ends with

@pytest.mark.parametrize("argv, step", [(["get", "v1.1", "--yes"], "update get"), ([], "update"), (["--check"], "update"), (["Get"], "update"), (["/home/anna/x"], "update"),
                                         (["a" * 20], "update " + "a" * 20), (["a" * 21], "update"), (["get-it"], "update get-it"), ([""], "update"), (["9x"], "update"), (["x9"], "update")])
def test_the_step_is_the_command_and_a_plain_lower_case_word_after_it_and_never_a_value(argv, step):
    assert rc.step_of("update", argv) == step


def test_the_command_to_paste_names_the_one_problem_that_was_shown_and_only_that_one():
    assert rc.hint_command("update", ["get", "v1.1"], [("update", "unreachable")]) == "python3 -m voice_studio.report show --step 'update get' --problem update/unreachable"
    assert rc.hint_command("update", ["get"], []) == "python3 -m voice_studio.report show --step 'update get'"
    assert rc.hint_command("update", ["get"], [("update", "unreachable"), ("update", "differs")]) == "python3 -m voice_studio.report show --step 'update get'"
    assert rc.hint_command("setup", [], [("fetch", "no_room")]) == "python3 -m voice_studio.report show --step setup --problem fetch/no_room"


def test_a_problem_that_could_not_be_typed_back_is_not_put_in_the_command():
    assert rc.hint_command("update", [], [("Bad", "code")]) == "python3 -m voice_studio.report show --step update"


@pytest.mark.parametrize("code, lines", [(0, 0), (1, 2), (2, 0), (3, 0), (-1, 0), (130, 0)])
def test_only_a_command_that_failed_after_it_began_is_pointed_at_the_report(code, lines):
    assert len(rc.hint_lines(CAT, "update", ["get"], [("update", "unreachable")], code)) == lines


def test_the_two_lines_say_what_a_report_is_and_give_the_command():
    what, command = rc.hint_lines(CAT, "update", ["get", "v1.1"], [("update", "unreachable")], 1)
    assert what.startswith("A problem report can be made for a helper") and "nothing is saved or sent unless you say so" in what
    assert command == "To see it, run: python3 -m voice_studio.report show --step 'update get' --problem update/unreachable"


def test_every_problem_the_commands_can_show_can_be_named_back_to_the_report():
    for namespace, code in (("update", "unreachable"), ("fetch", "no_room"), ("job", "not_found"), ("project", "bad_name"), ("rounds", "job_running"), ("scratchmove", "source_missing"),
                            ("uninstall", "job_running"), ("refresh", "job_running")):
        if CAT.has("%s.error.%s.what" % (namespace, code)):
            assert rc.parse_problem(CAT, "%s/%s" % (namespace, code)) == (namespace, code)


# ---------------------------------------------------------------- what the program has told the person

def test_the_problems_told_are_remembered_once_each_in_the_order_told():
    assert describe.errors_shown() == ()
    describe.error_text(CAT, "update", "unreachable")
    describe.error_text(CAT, "fetch", "no_room")
    describe.error_text(CAT, "update", "unreachable")
    assert describe.errors_shown() == (("update", "unreachable"), ("fetch", "no_room"))
    describe.forget_errors_shown()
    assert describe.errors_shown() == ()


def test_the_list_cannot_be_changed_from_outside():
    describe.error_text(CAT, "update", "unreachable")
    shown = describe.errors_shown()
    assert isinstance(shown, tuple)
    describe.error_text(CAT, "update", "differs")
    assert shown == (("update", "unreachable"),)
