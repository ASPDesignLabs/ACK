# SPDX-License-Identifier: GPL-3.0-or-later
"""The recordings of a project as plain facts (plan task VS-2.10): reading each recording's own notes without ever writing, grouping them the way the screens do, the one error vocabulary for
a folder import that cannot start, and reading what the listening job is doing from its own files."""
import hashlib
import os

import pytest

from freeform_studio import files_import
from vs_rounds_helpers import PROJECT, fake_job
from vs_recordings_helpers import write_take
from voice_studio.core import jobs
from voice_studio.core import recordings as rec

TAKE_A, TAKE_B, TAKE_C, TAKE_D = ("t20261001-10000%d-abcd" % n for n in range(4))


def tree(root):
    found = {}
    for base, _dirs, files in os.walk(root):
        for name in files:
            path = os.path.join(base, name)
            found[os.path.relpath(path, root)] = hashlib.sha256(open(path, "rb").read()).hexdigest()
    return found


# ---------------------------------------------------------------- reading the recordings

def test_a_project_with_no_recordings_folder_reads_as_nothing(tmp_path):
    view = rec.read_takes(str(tmp_path / "nope"))
    assert view.rows == () and view.unreadable == 0 and view.total == 0 and view.minutes == 0.0


def test_recordings_are_grouped_by_how_far_each_has_got_and_counted_once(tmp_path):
    for take, status in (("t20261001-100000-aaaa", "ready"), ("t20261001-100001-aaaa", "ready"), ("t20261001-100002-aaaa", "finishing"), ("t20261001-100003-aaaa", "queued"),
                         ("t20261001-100004-aaaa", "transcribing"), ("t20261001-100005-aaaa", "error"), ("t20261001-100006-aaaa", "importing"), ("t20261001-100007-aaaa", "recording"),
                         ("t20261001-100008-aaaa", "something-new")):
        write_take(tmp_path, take, status=status)
    view = rec.read_takes(str(tmp_path))
    assert (view.total, view.ready, view.waiting, view.failed, view.other) == (9, 2, 3, 1, 3)
    assert view.ready + view.waiting + view.failed + view.other == view.total
    assert view.count("ready", "error") == 3 and view.count() == 0


def test_the_newest_recording_comes_first_and_only_real_recording_folders_count(tmp_path):
    write_take(tmp_path, "t20261001-100000-aaaa", label="older")
    write_take(tmp_path, "t20261002-100000-bbbb", label="newer")
    takes = os.path.join(str(tmp_path), "_freeform", "en-US", "takes")
    os.makedirs(os.path.join(takes, "not-a-take"))
    open(os.path.join(takes, "stray-file.txt"), "w").write("x")
    os.makedirs(os.path.join(takes, "t20261003-100000-cccc.moved"))
    view = rec.read_takes(str(tmp_path))
    assert [r.label for r in view.rows] == ["newer", "older"] and view.unreadable == 0


def test_the_length_adds_up_only_the_lengths_that_are_known(tmp_path):
    write_take(tmp_path, "t20261001-100000-aaaa", duration=90.0)
    write_take(tmp_path, "t20261001-100001-aaaa", duration=30.0)
    write_take(tmp_path, "t20261001-100002-aaaa", status="finishing", duration=None)
    view = rec.read_takes(str(tmp_path))
    assert view.minutes == 2.0
    assert [r.seconds for r in view.rows] == [None, 30.0, 90.0]


@pytest.mark.parametrize("duration", [-1, True, "12", [3], {"a": 1}, float("nan"), float("inf"), -0.001])
def test_a_length_that_is_not_a_plain_number_of_seconds_is_not_a_length(tmp_path, duration):
    write_take(tmp_path, "t20261001-100000-aaaa", duration=duration)
    view = rec.read_takes(str(tmp_path))
    assert view.rows[0].seconds is None and view.minutes == 0.0


@pytest.mark.parametrize("duration, seconds", [(0, 0.0), (0.0, 0.0), (12, 12.0), (12.5, 12.5)])
def test_a_length_of_nothing_or_a_whole_number_is_still_a_length(tmp_path, duration, seconds):
    write_take(tmp_path, "t20261001-100000-aaaa", duration=duration)
    assert rec.read_takes(str(tmp_path)).rows[0].seconds == seconds


def test_where_a_recording_came_from_is_told_by_its_own_notes(tmp_path):
    write_take(tmp_path, "t20261001-100000-aaaa", client={"source": "files", "files_kind": "pairs"})
    write_take(tmp_path, "t20261001-100001-aaaa", client={"ack_session": "s-1"})
    write_take(tmp_path, "t20261001-100002-aaaa", client={"source": "browser"})
    write_take(tmp_path, "t20261001-100003-aaaa", client="oops")
    write_take(tmp_path, "t20261001-100004-aaaa", client={"source": "files", "ack_session": "s-2"})
    assert [r.origin for r in rec.read_takes(str(tmp_path)).rows] == ["files", "other", "other", "phone", "files"]


def test_a_label_is_cut_at_a_sensible_length_and_a_label_that_is_not_text_is_empty(tmp_path):
    write_take(tmp_path, "t20261001-100000-aaaa", label="x" * 500)
    write_take(tmp_path, "t20261001-100001-aaaa", label=7)
    rows = rec.read_takes(str(tmp_path)).rows
    assert [len(r.label) for r in rows] == [0, 120]


def test_notes_that_cannot_be_read_are_counted_and_left_exactly_as_they_were(tmp_path):
    write_take(tmp_path, TAKE_A, raw=b"{not json")
    write_take(tmp_path, TAKE_B, raw=b"[1, 2, 3]")
    write_take(tmp_path, TAKE_C, raw=b"{" + b" " * (rec.MAX_TAKE_FILE + 10) + b"}")
    write_take(tmp_path, TAKE_D, raw=b"\xff\xfe\x00bad")
    write_take(tmp_path, "t20261001-100009-aaaa")
    before = tree(str(tmp_path))
    view = rec.read_takes(str(tmp_path))
    assert view.total == 1 and view.unreadable == 4
    assert tree(str(tmp_path)) == before, "looking changed nothing"


def test_a_deeply_nested_note_is_not_a_crash(tmp_path):
    write_take(tmp_path, TAKE_A, raw=b"[" * 200000)
    assert rec.read_takes(str(tmp_path)).unreadable == 1


def test_a_link_instead_of_a_recording_or_its_notes_is_never_followed(tmp_path):
    takes = os.path.join(str(tmp_path), "_freeform", "en-US", "takes")
    real = write_take(tmp_path, "t20261001-100000-aaaa")
    os.symlink(real, os.path.join(takes, "t20261001-100001-aaaa"))
    folder = write_take(tmp_path, "t20261001-100002-aaaa", raw=b"{}")
    os.remove(os.path.join(folder, "take.json"))
    os.symlink(os.path.join(real, "take.json"), os.path.join(folder, "take.json"))
    view = rec.read_takes(str(tmp_path))
    assert [r.id for r in view.rows] == ["t20261001-100000-aaaa"] and view.unreadable == 1


# ---------------------------------------------------------------- the one error vocabulary

@pytest.mark.parametrize("code", ["bad_kind", "not_a_folder", "no_audio", "too_many_files", "too_big"])
def test_every_stop_a_folder_import_can_hit_keeps_its_own_code_and_detail(code):
    error = rec.stop_from(files_import.FilesImportProblem(code, "a detail"))
    assert isinstance(error, rec.RecordingsError) and (error.code, error.detail) == (code, "a detail")


def test_a_stop_this_tool_does_not_know_reads_as_unreadable_with_the_original_kept_for_show_details():
    error = rec.stop_from(files_import.FilesImportProblem("from_the_future", "something odd"))
    assert error.code == "unreadable" and error.detail == "something odd"
    assert rec.stop_from(files_import.FilesImportProblem("from_the_future")).detail == "from_the_future"


def test_every_code_freeform_studio_stops_with_is_one_this_tool_can_word():
    for code in files_import.STOP_CODES:
        assert rec.stop_from(files_import.FilesImportProblem(code, "d")).code in rec.ERROR_CODES, code


def test_the_error_codes_are_exactly_what_a_stop_can_turn_into():
    produced = {rec.stop_from(files_import.FilesImportProblem(code, "d")).code for code in files_import.STOP_CODES + ("zzz",)}
    assert produced == set(rec.ERROR_CODES)


def test_the_four_kinds_are_the_four_the_person_chooses_between():
    assert rec.KINDS == ("package", "pairs", "table", "audio")
    assert set(rec.KINDS) - {"package"} == set(files_import.KINDS)


# ---------------------------------------------------------------- the job that listens

def log(job, *lines):
    with open(job.dir + "/log.txt", "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


def test_a_project_that_never_listened_has_no_listening_job(tmp_path):
    jobs_root = str(tmp_path / "jobs")
    os.makedirs(jobs_root)
    assert rec.listening_job(jobs_root, PROJECT) is None
    assert rec.listening_job(str(tmp_path / "missing"), PROJECT) is None


def test_only_a_listening_job_of_this_project_counts_and_the_newest_one_wins(tmp_path):
    root = str(tmp_path / "jobs")
    os.makedirs(root)
    fake_job(root, ["x"], "finished", kind="train", project=PROJECT, name="20261011-100000-train-0001")
    fake_job(root, ["x"], "finished", kind="process", project="ben", name="20261011-100001-process-0002")
    old = fake_job(root, ["x"], "failed", kind="process", project=PROJECT, name="20261011-100002-process-0003")
    new = fake_job(root, ["x"], "running", kind="process", project=PROJECT, name="20261011-100003-process-0004")
    found = rec.listening_job(root, PROJECT)
    assert found.job.id == new.id != old.id and found.active is True


@pytest.mark.parametrize("how", ["finished", "failed", "stopped", "interrupted", "never_started"])
def test_a_job_that_ended_is_not_active_whichever_way_it_ended(tmp_path, how):
    root = str(tmp_path / "jobs")
    os.makedirs(root)
    fake_job(root, ["x"], how, kind="process", project=PROJECT)
    assert rec.listening_job(root, PROJECT).active is False


def test_what_the_job_is_on_and_how_far_comes_from_its_own_log(tmp_path):
    root = str(tmp_path / "jobs")
    os.makedirs(root)
    job = fake_job(root, ["x"], "running", kind="process")
    log(job, '{"take": "t1", "status": "ready", "label": "first", "progress": 1.0}', '{"take": "t2", "status": "transcribing", "label": "second one", "progress": 0.426}', "a library warning")
    found = rec.listening_job(root, PROJECT)
    assert (found.doing, found.percent) == ("second one", 42)


@pytest.mark.parametrize("progress, percent", [(0.0, 0), (0.999, 99), (1.5, 99), (-2, 0)])
def test_the_percent_stays_between_nothing_and_not_quite_done_while_a_recording_is_still_being_listened_to(tmp_path, progress, percent):
    root = str(tmp_path / "jobs")
    os.makedirs(root)
    log(fake_job(root, ["x"], "running", kind="process"), '{"take": "t1", "status": "transcribing", "label": "one", "progress": %s}' % progress)
    assert rec.listening_job(root, PROJECT).percent == percent


def test_with_every_recording_done_there_is_nothing_it_is_on_and_a_missing_model_is_carried_through(tmp_path):
    root = str(tmp_path / "jobs")
    os.makedirs(root)
    log(fake_job(root, ["x"], "failed", kind="process"), '{"take": "t1", "status": "ready", "label": "one", "progress": 1.0}', '{"done": true, "model_missing": "small.en"}')
    found = rec.listening_job(root, PROJECT)
    assert (found.doing, found.percent, found.model_missing) == ("", None, "small.en")


def test_a_job_with_no_log_yet_reads_as_nothing_known_yet(tmp_path):
    root = str(tmp_path / "jobs")
    os.makedirs(root)
    fake_job(root, ["x"], "starting", kind="process")
    found = rec.listening_job(root, PROJECT)
    assert (found.doing, found.percent, found.model_missing, found.active) == ("", None, "", True)


def test_listing_the_job_starts_and_changes_nothing(tmp_path):
    root = str(tmp_path / "jobs")
    os.makedirs(root)
    log(fake_job(root, ["x"], "running", kind="process"), '{"take": "t1", "status": "transcribing", "label": "one", "progress": 0.5}')
    before = tree(root)
    rec.listening_job(root, PROJECT)
    assert tree(root) == before and jobs.list_jobs(root).problems == ()
