# SPDX-License-Identifier: GPL-3.0-or-later
"""Training rounds (plan task VS-4.2): many rounds in a row, each continuing from the person's own chosen round, never the starting voice by accident.

Most tests write the files a round leaves (the record, the trainer's folders, the job's last word) and read the answer back; one runs real detached jobs with a
stand-in trainer. Nothing here needs a graphics card.
"""
import errno
import json
import os
import threading
from dataclasses import replace
from datetime import timedelta

import pytest

from voice_studio.core import diskbudget, jobs, rounds as rd
from voice_studio.core.commands import CommandError
from vs_rounds_helpers import (DATASET, NOW, PROJECT, VOICE, end_job, fake_job, make_fake_training_env, make_world, stamp, wait_for_end, write_checkpoint)


def slurp(path):
    with open(path, "rb") as handle:
        return handle.read()


def spit(path, data):
    with open(path, "wb" if isinstance(data, bytes) else "w") as handle:
        handle.write(data)


@pytest.fixture()
def world(tmp_path):
    return make_world(tmp_path)


def code_of(fn, *a, **kw):
    with pytest.raises(rd.RoundsError) as caught:
        fn(*a, **kw)
    return caught.value.code


def R(number, **over):
    base = dict(number=number, parent=0, voice=VOICE, dataset=DATASET, minutes=25, state="finished", started=stamp(), ended=stamp(26), version=number - 1,
                has_checkpoint=True)
    base.update(over)
    return rd.Round(**base)


def put(world, record):
    """Write a record by hand, past `modify`, so a test can start from any state."""
    os.makedirs(world.paths.rounds, exist_ok=True)
    with open(world.paths.rounds_file, "w") as handle:
        json.dump(rd.record_to_dict(record), handle)
    return record


# ---------------------------------------------------------------- the record on disk

def test_a_project_with_no_rounds_reads_as_an_empty_record_and_reading_writes_nothing(world):
    assert rd.load(world.paths) == rd.Record() and not os.path.exists(world.paths.rounds_file) and not os.path.exists(world.paths.rounds_lock)


def test_a_record_is_saved_owner_only_and_reads_back_the_same(world):
    record = rd.Record((R(1), R(2, parent=1, voice="", note="clearer")), current=2)
    saved = rd.modify(world.paths, lambda old: record)
    assert saved == record and rd.load(world.paths) == record
    assert (os.stat(world.paths.rounds_file).st_mode & 0o777) == 0o600 and (os.stat(world.paths.rounds_lock).st_mode & 0o777) == 0o600


def test_saving_keeps_the_exact_bytes_of_the_version_it_replaces(world):
    rd.modify(world.paths, lambda old: rd.Record((R(1),), 1))
    first = slurp(world.paths.rounds_file)
    rd.set_note(world.paths, 1, "better")
    assert slurp(world.paths.rounds_previous) == first and slurp(world.paths.rounds_file) != first
    assert (os.stat(world.paths.rounds_previous).st_mode & 0o777) == 0o600


def test_a_change_that_changes_nothing_writes_nothing(world):
    rd.modify(world.paths, lambda old: rd.Record((R(1),), 1))
    before, stat = slurp(world.paths.rounds_file), os.stat(world.paths.rounds_file)
    rd.modify(world.paths, lambda old: old)
    assert slurp(world.paths.rounds_file) == before and os.stat(world.paths.rounds_file).st_mtime_ns == stat.st_mtime_ns
    assert not os.path.exists(world.paths.rounds_previous)


def test_nothing_is_written_when_the_first_ever_change_is_no_change(tmp_path):
    w = make_world(tmp_path)
    rd.modify(w.paths, lambda old: old)
    assert not os.path.exists(w.paths.rounds_file)


def test_fields_a_newer_version_added_are_kept_when_this_one_saves(world):
    record = rd.Record((R(1, extra={"quality": 0.9}),), 1, {"future": [1, 2]})
    rd.modify(world.paths, lambda old: record)
    rd.set_note(world.paths, 1, "x")
    data = json.loads(slurp(world.paths.rounds_file))
    assert data["future"] == [1, 2] and data["rounds"][0]["quality"] == 0.9 and data["rounds"][0]["note"] == "x"


def good_dict():
    """Three rounds and a running fourth: round 1 from the starting voice, 2 from 1, 3 on a branch from 1 that failed, 4 (running) from 2."""
    r1, r2 = R(1), R(2, parent=1, voice="")
    r3 = R(3, parent=1, voice="", state="failed", failure="exit", exit_code=1, has_checkpoint=False, version=2, versions_before=(0, 1))
    r4 = R(4, parent=2, voice="", state="running", ended="", has_checkpoint=False, version=None, versions_before=(0, 1, 2), job="job-4")
    return rd.record_to_dict(rd.Record((r1, r2, r3, r4), current=2))


def test_the_record_used_by_the_damage_tests_is_itself_good():
    rd.record_from_text(json.dumps(good_dict()))


@pytest.mark.parametrize("change, why", [
    (lambda d: d.update(schema=True), "schema is a flag"), (lambda d: d.update(schema="1"), "schema is text"), (lambda d: d.pop("schema"), "schema is missing"),
    (lambda d: d.update(rounds={}), "rounds is not a list"), (lambda d: d["rounds"].append(5), "a round is not an object"),
    (lambda d: d["rounds"][0].update(number=0), "number below 1"), (lambda d: d["rounds"][0].update(number="1"), "number is text"),
    (lambda d: d["rounds"][0].update(number=True), "number is a flag"), (lambda d: d["rounds"][1].update(number=1), "numbers repeat"),
    (lambda d: d["rounds"][1].update(number=0 + 9), "numbers out of order"),
    (lambda d: d["rounds"][1].update(parent=2), "parent is itself"), (lambda d: d["rounds"][1].update(parent=7), "parent unknown"),
    (lambda d: d["rounds"][1].update(parent=3), "parent is a round that came later"),
    (lambda d: d["rounds"][3].update(parent=3), "parent is a round without a saved point"),
    (lambda d: d["rounds"][0].update(voice=""), "no starting voice named on a first round"),
    (lambda d: d["rounds"][1].update(voice="voice-mike"), "a starting voice named on a later round"),
    (lambda d: d["rounds"][0].update(voice="../x"), "starting voice with a slash"),
    (lambda d: d["rounds"][0].update(state="done"), "state unknown"), (lambda d: d["rounds"][2].update(failure="kaboom"), "failure unknown"),
    (lambda d: d["rounds"][0].update(dataset="../../etc"), "training set climbs out"), (lambda d: d["rounds"][0].update(dataset=""), "training set empty"),
    (lambda d: d["rounds"][0].update(dataset="a/b"), "training set has a slash"), (lambda d: d["rounds"][0].update(dataset=".hidden"), "training set starts with a dot"),
    (lambda d: d["rounds"][3].update(job="../../x"), "job name climbs out"), (lambda d: d["rounds"][0].update(job="a/b"), "job name has a slash"),
    (lambda d: d["rounds"][0].update(minutes=0), "no minutes"), (lambda d: d["rounds"][0].update(minutes=rd.MAX_MINUTES + 1), "too many minutes"),
    (lambda d: d["rounds"][0].update(minutes=True), "minutes is a flag"), (lambda d: d["rounds"][0].update(minutes=25.0), "minutes is a fraction"),
    (lambda d: d["rounds"][0].update(started="yesterday"), "start is not a time"), (lambda d: d["rounds"][0].pop("started"), "start missing"),
    (lambda d: d["rounds"][0].update(ended=""), "an ended round with no end time"), (lambda d: d["rounds"][0].update(ended="soon"), "end is not a time"),
    (lambda d: d["rounds"][3].update(ended=stamp(1)), "a running round with an end time"),
    (lambda d: d["rounds"][2].update(has_checkpoint=True), "a failed round with a saved point"),
    (lambda d: d["rounds"][0].update(version=None), "a saved point with no folder"), (lambda d: d["rounds"][0].update(has_checkpoint="yes"), "saved point is text"),
    (lambda d: d["rounds"][1].update(version=0), "one folder claimed twice"), (lambda d: d["rounds"][2].update(versions_before=[0, 1, 2]), "own folder was there before"),
    (lambda d: d["rounds"][3].update(versions_before=[1, 0]), "folders not in order"), (lambda d: d["rounds"][3].update(versions_before=[0, 0, 1]), "folders repeat"),
    (lambda d: d["rounds"][3].update(versions_before=[-1]), "a negative folder"), (lambda d: d["rounds"][3].update(versions_before="0"), "folders are text"),
    (lambda d: d["rounds"][3].update(versions_before=[True]), "a folder is a flag"), (lambda d: d["rounds"][0].update(failure="exit"), "a finished round with a failure"),
    (lambda d: d["rounds"][3].update(failure="exit"), "a running round with a failure"), (lambda d: d["rounds"][3].update(has_checkpoint=True), "a running round with a saved point"),
    (lambda d: d["rounds"].__setitem__(1, dict(d["rounds"][3], number=5, parent=2)), "a running round that is not the last"),
    (lambda d: d["rounds"].append(dict(d["rounds"][3], number=5, parent=2, versions_before=[0, 1, 2])), "two running rounds"),
    (lambda d: d.update(current=0), "no chosen round although saved points exist"), (lambda d: d.update(current=3), "chosen round has no saved point"),
    (lambda d: d.update(current=9), "chosen round unknown"), (lambda d: d.update(current="2"), "chosen round is text"), (lambda d: d.update(current=True), "chosen is a flag"),
    (lambda d: d.update(current=None), "chosen is nothing"), (lambda d: d["rounds"][0].update(exit_code="1"), "exit code is text"),
    (lambda d: d["rounds"][0].update(note=5), "note is a number"), (lambda d: d["rounds"][0].update(version=-1), "folder below zero"),
    (lambda d: d["rounds"][0].update(version=rd.MAX_VERSION + 1), "folder far too large"),
])
def test_a_record_that_breaks_a_rule_is_damaged_and_never_guessed_at(change, why):
    data = good_dict()
    change(data)
    assert code_of(rd.record_from_text, json.dumps(data)) == "damaged", why


@pytest.mark.parametrize("text", ["", "not json", "[]", "5", "null", '"x"', "{", '{"schema": 1, "rounds": ' + "[" * 200_000])
def test_a_file_that_is_not_a_record_is_damaged(text):
    assert code_of(rd.record_from_text, text) == "damaged"


def test_a_record_with_nothing_in_it_but_the_version_is_an_empty_record():
    assert rd.record_from_text('{"schema": 1}') == rd.Record() and rd.record_from_text('{"schema": 1, "rounds": null}') == rd.Record()


def test_a_record_from_a_newer_version_is_refused_not_rewritten(world):
    data = good_dict()
    data["schema"] = rd.SCHEMA + 1
    os.makedirs(world.paths.rounds, exist_ok=True)
    spit(world.paths.rounds_file, json.dumps(data))
    before = slurp(world.paths.rounds_file)
    assert code_of(rd.load, world.paths) == "newer" and code_of(rd.set_note, world.paths, 1, "x") == "newer"
    assert slurp(world.paths.rounds_file) == before


def test_a_damaged_file_is_reported_and_left_exactly_as_it_is(world):
    os.makedirs(world.paths.rounds, exist_ok=True)
    spit(world.paths.rounds_file, "{broken")
    assert code_of(rd.load, world.paths) == "damaged" and code_of(rd.set_note, world.paths, 1, "x") == "damaged"
    assert slurp(world.paths.rounds_file) == b"{broken" and not os.path.exists(world.paths.rounds_previous)


def test_a_record_that_cannot_be_opened_is_unreadable(world):
    os.makedirs(world.paths.rounds_file)                       # a folder where the file should be
    assert code_of(rd.load, world.paths) == "unreadable"
    os.rmdir(world.paths.rounds_file)
    spit(world.paths.rounds_file, b"\xff\xfe\x00bad")
    assert code_of(rd.load, world.paths) == "unreadable"


def test_a_save_that_fails_says_so_and_leaves_the_earlier_record_alone(world, monkeypatch):
    rd.modify(world.paths, lambda old: rd.Record((R(1),), 1))
    before = slurp(world.paths.rounds_file)
    real = rd._atomic_write

    def full_disk(path, body):
        if path == world.paths.rounds_file:
            raise OSError(errno.ENOSPC, "No space left on device")
        real(path, body)
    monkeypatch.setattr(rd, "_atomic_write", full_disk)
    assert code_of(rd.set_note, world.paths, 1, "x") == "cannot_save"
    assert slurp(world.paths.rounds_file) == before
    assert not [n for n in os.listdir(world.paths.rounds) if n.endswith(".tmp")]


def test_a_failed_copy_of_the_old_version_does_not_stop_the_save(world, monkeypatch):
    rd.modify(world.paths, lambda old: rd.Record((R(1),), 1))
    real = rd._atomic_write

    def no_copy(path, body):
        if path == world.paths.rounds_previous:
            raise OSError(errno.EACCES, "denied")
        real(path, body)
    monkeypatch.setattr(rd, "_atomic_write", no_copy)
    assert rd.set_note(world.paths, 1, "x").rounds[0].note == "x" and rd.load(world.paths).rounds[0].note == "x"


def test_a_record_is_never_written_if_it_would_be_damaged(world):
    assert code_of(rd.modify, world.paths, lambda old: rd.Record((R(1, parent=4),), 1)) == "damaged"
    assert not os.path.exists(world.paths.rounds_file)


def test_the_lock_makes_a_second_change_wait_and_then_say_busy(world, monkeypatch):
    monkeypatch.setattr(rd, "LOCK_WAIT_S", 0.3)
    started = []

    def inner():
        started.append(code_of(rd.modify, world.paths, lambda old: old))
    with rd._locked(world.paths):
        thread = threading.Thread(target=inner)
        thread.start()
        thread.join(5)
    assert started == ["busy"]
    rd.modify(world.paths, lambda old: old)                    # free again


def test_two_windows_changing_the_record_at_once_lose_no_change(world):
    rd.modify(world.paths, lambda old: rd.Record((R(1), R(2, parent=1, voice="")), 2))
    errors = []

    def work(number):
        try:
            for i in range(25):
                rd.set_note(world.paths, number, "note %d from %d" % (i, number))
        except Exception as exc:                              # pragma: no cover
            errors.append(exc)
    threads = [threading.Thread(target=work, args=(n,)) for n in (1, 2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(60)
    assert not errors
    final = rd.load(world.paths)
    assert [r.note for r in final.rounds] == ["note 24 from 1", "note 24 from 2"]


# ---------------------------------------------------------------- the trainer's files

def test_a_saved_point_is_whole_only_if_it_opens_and_holds_the_state(tmp_path):
    whole = write_checkpoint(str(tmp_path / "a.ckpt"))
    cut = write_checkpoint(str(tmp_path / "b.ckpt"), whole=False)
    assert rd.checkpoint_complete(whole) is True and rd.checkpoint_complete(cut) is False
    import zipfile
    with zipfile.ZipFile(tmp_path / "plain.ckpt", "w") as z:
        z.writestr("data.pkl", b"x")
    with zipfile.ZipFile(tmp_path / "other.ckpt", "w") as z:
        z.writestr("archive/weights.bin", b"x")
        z.writestr("archive/not_data.pkl.bak", b"x")
        z.writestr("data.pkl.txt", b"x")
    (tmp_path / "empty.ckpt").write_bytes(b"")
    (tmp_path / "text.ckpt").write_text("not a zip")
    (tmp_path / "folder.ckpt").mkdir()
    assert rd.checkpoint_complete(str(tmp_path / "plain.ckpt")) is True            # the state may sit at the top of the archive
    for name in ("other.ckpt", "empty.ckpt", "text.ckpt", "folder.ckpt", "missing.ckpt"):
        assert rd.checkpoint_complete(str(tmp_path / name)) is False, name


def test_a_file_cut_at_any_point_is_never_called_whole(tmp_path):
    whole = slurp(write_checkpoint(str(tmp_path / "a.ckpt")))
    for length in range(0, len(whole), 97):                    # a crash or a full disk can stop the write anywhere
        (tmp_path / "cut.ckpt").write_bytes(whole[:length])
        assert rd.checkpoint_complete(str(tmp_path / "cut.ckpt")) is False, length
    (tmp_path / "cut.ckpt").write_bytes(whole)
    assert rd.checkpoint_complete(str(tmp_path / "cut.ckpt")) is True


def test_only_the_folders_the_trainer_makes_count_as_versions(world):
    base = world.paths.run + "/lightning_logs"
    for name in ("version_0", "version_2", "version_10", "version_x", "version_", "Version_3", "version_3.bak", "other"):
        os.makedirs(base + "/" + name)
    open(base + "/version_4", "w").close()                    # a file
    os.symlink(base + "/version_0", base + "/version_5")       # a link
    assert rd.version_dirs(world.paths) == (0, 2, 10) and rd.version_dirs(type(world.paths)("/nowhere")) == ()


def test_a_round_has_a_saved_point_that_is_none_missing_damaged_or_ok(world):
    r = R(1)
    assert rd.checkpoint_status(world.paths, replace(r, has_checkpoint=False)) == "none" and rd.checkpoint_status(world.paths, replace(r, version=None, has_checkpoint=False)) == "none"
    assert rd.checkpoint_status(world.paths, r) == "missing"
    world.trainer_makes(0)
    assert rd.checkpoint_status(world.paths, r) == "ok"
    write_checkpoint(rd.checkpoint_file(world.paths, r), whole=False)
    assert rd.checkpoint_status(world.paths, r) == "damaged"
    assert rd.checkpoint_file(world.paths, r) == world.paths.run + "/lightning_logs/version_0/checkpoints/last.ckpt" and rd.checkpoint_file(world.paths, replace(r, version=None)) is None


# ---------------------------------------------------------------- planning the next round

def test_the_first_round_starts_from_the_starting_voice_and_says_which(world):
    plan = world.plan()
    assert (plan.number, plan.parent, plan.voice, plan.resume_from) == (1, 0, VOICE, world.base_path)
    assert plan.run_dir == world.paths.run and plan.dataset_dir == world.scratch.datasets + "/" + DATASET and plan.minutes == 25 and plan.versions_before == ()
    assert plan.cache_dir == world.scratch.caches + "/" + DATASET + "-r001" and plan.config_path == world.paths.round_configs + "/round-001.json"


def test_every_round_after_a_saved_one_continues_from_that_round_and_never_from_the_starting_voice(world):
    world.run_round(version=0)
    plan = world.plan()
    assert plan.number == 2 and plan.parent == 1 and plan.voice == ""
    assert plan.resume_from == world.paths.run + "/lightning_logs/version_0/checkpoints/last.ckpt" and plan.resume_from != world.base_path
    world.run_round(version=1)
    assert world.plan().resume_from == world.paths.run + "/lightning_logs/version_1/checkpoints/last.ckpt" and world.plan().parent == 2
    assert world.plan(base=None).resume_from.endswith("version_1/checkpoints/last.ckpt")            # the starting voice is not even needed any more


def test_a_chosen_round_whose_file_is_gone_stops_the_round_and_nothing_else_is_used_instead(world):
    world.run_round(version=0)
    world.run_round(version=1)
    os.unlink(world.paths.run + "/lightning_logs/version_1/checkpoints/last.ckpt")
    assert code_of(world.plan) == "checkpoint_missing"
    assert rd.RoundsError("checkpoint_missing", "2").detail == "2"
    write_checkpoint(world.paths.run + "/lightning_logs/version_1/checkpoints/last.ckpt", whole=False)
    assert code_of(world.plan) == "checkpoint_damaged"


def test_with_nothing_chosen_and_no_starting_voice_there_is_nothing_to_start_from(world):
    assert code_of(world.plan, base=None) == "no_start"


def test_a_round_is_not_planned_while_another_runs(world):
    world.begin()
    assert code_of(world.plan) == "round_running"


def test_the_length_of_a_round_is_a_whole_number_of_minutes_from_one_to_a_day(world):
    for good in (1, 25, rd.MAX_MINUTES):
        assert world.plan(minutes=good).minutes == good
    for bad in (0, -1, rd.MAX_MINUTES + 1, True, False, "25", 25.0, None, [25]):
        assert code_of(world.plan, minutes=bad) == "bad_value", bad


def test_the_training_set_and_the_starting_voice_must_be_plain_names(world):
    for bad in ("", "../x", "a/b", ".hidden", "-x", "a b", "x" * 65, 5, None):
        assert code_of(world.plan, dataset=bad) == "bad_value", bad
    assert code_of(world.plan, base=rd.Base("../x", world.base_path)) == "bad_value"
    assert world.plan(dataset="x" * 64).dataset == "x" * 64


def test_planning_changes_nothing_on_the_disk(world):
    before = sorted(os.listdir(world.paths.root))
    world.plan()
    assert sorted(os.listdir(world.paths.root)) == before and not os.path.exists(world.paths.rounds_file) and not os.path.exists(world.paths.run)
    assert not os.path.exists(world.scratch.caches)


def test_every_round_gets_its_own_working_folder_and_settings_file(world):
    first = world.plan()
    other_set = world.plan(dataset="dataset-20261012-090000")
    assert other_set.cache_dir != first.cache_dir and other_set.cache_dir.endswith("dataset-20261012-090000-r001")
    world.run_round(version=0)
    second = world.plan()
    assert second.cache_dir == world.scratch.caches + "/" + DATASET + "-r002" and second.config_path.endswith("round-002.json")
    assert second.cache_dir != first.cache_dir and second.config_path != first.config_path             # the same audio, a new folder: a cache is never reused


def test_the_plan_remembers_which_trainer_folders_were_there_already(world):
    world.run_round(version=0)
    world.trainer_makes(1)                                     # something left in the run folder that no round claims
    assert world.plan().versions_before == (0, 1)


def test_round_numbers_keep_counting_after_going_back(world):
    world.run_round(version=0)
    world.run_round(version=1)
    rd.go_back(world.paths)
    plan = world.plan()
    assert (plan.number, plan.parent) == (3, 1)
    assert plan.resume_from.endswith("version_0/checkpoints/last.ckpt")


# ---------------------------------------------------------------- writing a round down, and taking it back

def test_a_round_is_written_down_as_starting_before_any_job_exists(world):
    plan = world.begin()
    record = rd.load(world.paths)
    assert record.current == 0 and record.rounds == (rd.Round(1, 0, VOICE, DATASET, 25, "starting", stamp(), versions_before=()),)
    assert os.path.isdir(world.paths.run) and os.path.isdir(world.paths.round_configs) and os.path.isdir(world.scratch.caches) and not os.path.exists(plan.cache_dir)


def test_the_folders_the_trainer_had_already_are_written_down_with_the_round(world):
    world.run_round(version=0)
    world.trainer_makes(3)
    world.begin()
    assert rd.load(world.paths).rounds[-1].versions_before == (0, 3)


def test_a_second_round_cannot_begin_while_one_is_written_down_as_running(world):
    plan = world.begin()
    assert code_of(rd.begin, world.paths, plan) == "round_running"
    assert len(rd.load(world.paths).rounds) == 1


def test_a_plan_made_before_another_window_changed_things_is_refused_not_applied(world):
    world.run_round(version=0)
    old = world.plan()
    world.run_round(version=1)                                         # another window finished a round after `old` was planned
    assert code_of(rd.begin, world.paths, old) == "busy"
    stale_number = replace(world.plan(), number=9)
    assert code_of(rd.begin, world.paths, stale_number) == "busy"
    rd.go_back(world.paths)
    assert code_of(rd.begin, world.paths, replace(world.plan(), parent=2)) == "busy"                       # it would resume from a round that is not the chosen one
    rd.begin(world.paths, world.plan(), NOW)


def test_naming_the_job_turns_starting_into_running_and_nothing_else(world):
    world.begin()
    assert rd.attach_job(world.paths, 1, "job-a").rounds[0].state == "running" and rd.load(world.paths).rounds[0].job == "job-a"
    again = rd.attach_job(world.paths, 1, "job-b")
    assert again.rounds[0].job == "job-a"                              # already running: the first name stands
    assert rd.attach_job(world.paths, 7, "job-c") == again
    assert code_of(rd.attach_job, world.paths, 1, "../x") == "bad_value"


def test_taking_back_a_round_that_never_started_removes_that_line_and_only_that_line(world):
    world.run_round(version=0)
    world.begin()
    assert [r.number for r in rd.rollback_start(world.paths, 2).rounds] == [1]
    world.begin()
    rd.attach_job(world.paths, 2, "job-a")
    assert [r.number for r in rd.rollback_start(world.paths, 2).rounds] == [1, 2]                       # it has a job: it is not taken back
    assert [r.number for r in rd.rollback_start(world.paths, 1).rounds] == [1, 2]                       # it ended: never removed
    assert [r.number for r in rd.rollback_start(world.paths, 9).rounds] == [1, 2]


# ---------------------------------------------------------------- noticing how a round ended

@pytest.mark.parametrize("job, files, state, failure, saved, exit_code", [
    ("finished", "whole", "finished", "", True, 0),
    ("finished", "none", "failed", "no_checkpoint", False, 0),                  # it said it finished, but no folder appeared
    ("finished", "no_last", "failed", "no_checkpoint", False, 0),               # a folder, but no last.ckpt in it
    ("finished", "cut", "failed", "no_checkpoint", False, 0),                   # a last.ckpt that is not whole
    ("stopped", "whole", "stopped", "", True, 130),
    ("stopped", "cut", "stopped", "", False, 130),
    ("stopped", "no_last", "stopped", "", False, 130),                          # stopped before its first check: nothing new was saved
    ("stopped", "none", "stopped", "", False, 130),
    ("failed", "whole", "failed", "exit", False, 1),                            # a file left by a round that failed is never trusted
    ("failed", "none", "failed", "exit", False, 1),
])
def test_how_a_round_ended_decides_whether_it_can_be_continued_from(world, job, files, state, failure, saved, exit_code):
    world.run_round(version=0, ends=job, files=files)
    r = rd.load(world.paths).rounds[0]
    assert (r.state, r.failure, r.has_checkpoint, r.exit_code) == (state, failure, saved, exit_code)
    assert rd.load(world.paths).current == (1 if saved else 0)
    assert (r.version == 0) == (files in ("whole", "cut", "no_last")) and r.ended == stamp(26) and r.job


def test_a_program_ended_from_outside_is_a_failure_with_that_reason(world):
    plan = world.begin()
    info = world.job_for(plan, "failed", exit_code=None, signal=9, ended_at=stamp(5))
    rd.attach_job(world.paths, 1, info.id)
    world.trainer_makes(0)
    r = world.reconcile().rounds[0]
    assert (r.state, r.failure, r.exit_code, r.has_checkpoint) == ("failed", "signal", None, False)


@pytest.mark.parametrize("status, kw, failure", [("never_started", {"error": "program_not_found"}, "program"), ("starting", {"age": 10_000.0}, "never_started")])
def test_a_job_that_never_came_up_is_said_so_in_the_reason_it_has(world, status, kw, failure):
    plan = world.begin()
    info = world.job_for(plan, status, **kw)
    assert info.status is jobs.JobStatus.NEVER_STARTED
    rd.attach_job(world.paths, 1, info.id)
    r = world.reconcile().rounds[0]
    assert (r.state, r.failure, r.has_checkpoint) == ("never_started", failure, False)


def test_a_job_that_died_with_the_computer_is_interrupted_and_its_file_is_not_trusted(world):
    plan = world.begin()
    info = world.job_for(plan, "interrupted")
    rd.attach_job(world.paths, 1, info.id)
    world.trainer_makes(0)
    r = world.reconcile().rounds[0]
    assert (r.state, r.failure, r.has_checkpoint, r.version) == ("interrupted", "", False, 0) and world.reconcile().current == 0
    assert r.ended == jobs.utc_stamp(NOW + timedelta(minutes=30))


@pytest.mark.parametrize("status", ["running", "stopping"])
def test_a_round_whose_job_is_still_going_stays_running_and_finds_its_folder_when_it_appears(world, status):
    plan = world.begin()
    info = world.job_for(plan, status)
    rd.attach_job(world.paths, 1, info.id)
    r = world.reconcile().rounds[0]
    assert (r.state, r.version, r.has_checkpoint, r.ended) == ("running", None, False, "")
    world.trainer_makes(0, with_last=False)
    r = world.reconcile().rounds[0]
    assert (r.state, r.version) == ("running", 0) and world.reconcile().current == 0
    write_checkpoint(rd.checkpoint_file(world.paths, r))
    assert world.reconcile().current == 0                              # a saved point appearing while it runs does not make the round chosen


def test_a_job_the_record_never_got_the_name_of_is_found_by_its_working_folder(world):
    plan = world.begin()
    info = world.job_for(plan, "running")                              # the program ended after starting the job and before writing its name
    assert rd.load(world.paths).rounds[0].job == ""
    r = world.reconcile().rounds[0]
    assert (r.state, r.job) == ("running", info.id)
    end_job(info.dir, "finished", ended_at=stamp(20))
    world.trainer_makes(0)
    assert world.reconcile().rounds[0].state == "finished"


def test_another_projects_job_or_another_kind_of_job_is_never_taken_for_this_round(world):
    plan = world.begin()
    world.job_for(plan, "running", project="someone-else")
    world.job_for(plan, "running", kind="process")
    after = world.reconcile(now=NOW + timedelta(seconds=30))
    assert (after.rounds[0].state, after.rounds[0].job) == ("starting", "")
    assert world.reconcile(now=NOW + timedelta(seconds=rd.STARTING_GRACE_S)).rounds[0].state == "never_started"


def test_a_round_written_down_but_never_started_is_left_alone_for_a_while_and_then_called_what_it_is(world):
    world.begin()
    grace = rd.STARTING_GRACE_S
    assert world.reconcile(now=NOW + timedelta(seconds=grace - 1)).rounds[0].state == "starting"
    assert world.reconcile(now=NOW + timedelta(seconds=0)).rounds[0].state == "starting"
    r = world.reconcile(now=NOW + timedelta(seconds=grace)).rounds[0]
    assert (r.state, r.failure, r.has_checkpoint, r.ended) == ("never_started", "never_started", False, stamp(grace / 60))
    assert world.plan().number == 2 and world.plan().parent == 0                      # the number is not reused; it started from nothing, so still the starting voice


def test_a_round_whose_job_has_vanished_is_interrupted_not_lost(world):
    import shutil
    plan = world.begin()
    info = world.job_for(plan, "running")
    rd.attach_job(world.paths, 1, info.id)
    shutil.rmtree(info.dir)
    r = world.reconcile().rounds[0]
    assert (r.state, r.failure, r.has_checkpoint) == ("interrupted", "job_missing", False)


def test_noticing_is_repeatable_and_a_round_that_ended_is_never_looked_at_again(world):
    world.run_round(version=0)
    before, previous_exists = slurp(world.paths.rounds_file), os.path.exists(world.paths.rounds_previous)
    for _ in range(3):
        world.reconcile()
    assert slurp(world.paths.rounds_file) == before and os.path.exists(world.paths.rounds_previous) == previous_exists
    job = rd.load(world.paths).rounds[0].job
    end_job(world.jobs_root + "/" + job, "failed", ended_at=stamp(90))                         # the job's folder changes afterwards: the round does not
    world.reconcile()
    assert rd.load(world.paths).rounds[0].state == "finished"


@pytest.mark.parametrize("written, expected", [(stamp(26), stamp(26)), ("yesterday", stamp(30)), ("", stamp(30)), (None, stamp(30)), ("x" * 100, stamp(30)), (5, stamp(30))])
def test_the_end_time_is_the_runners_own_if_it_is_a_time_and_the_moment_of_noticing_if_not(tmp_path, written, expected):
    w = make_world(tmp_path)
    plan = w.begin()
    info = w.job_for(plan, "running")
    rd.attach_job(w.paths, 1, info.id)
    w.trainer_makes(0)
    end_job(info.dir, "finished")
    data = json.loads(slurp(info.dir + "/result.json"))
    data["ended_at"] = written
    spit(info.dir + "/result.json", json.dumps(data))
    assert w.reconcile().rounds[0].ended == expected


def test_a_trainer_folder_another_round_owns_is_never_taken_and_among_several_new_ones_the_newest_is(world):
    running = R(2, parent=1, voice="", state="running", ended="", has_checkpoint=False, version=None, versions_before=(), job="job-x")
    put(world, rd.Record((R(1, version=0), running), 1))
    argv = ("py", "ack_run.py", "--data.cache_dir", "%s/%s-r002" % (world.scratch.caches, DATASET))
    fake_job(world.jobs_root, argv, "finished", name="job-x", ended_at=stamp(20))
    world.trainer_makes(0)                                             # round 1's
    world.trainer_makes(1)
    world.trainer_makes(4)
    after = world.reconcile()
    assert (after.rounds[1].version, after.rounds[1].state, after.current) == (4, "finished", 2)


def test_when_the_only_new_folder_is_one_another_round_owns_the_round_has_no_folder_of_its_own(world):
    running = R(2, parent=1, voice="", state="running", ended="", has_checkpoint=False, version=None, versions_before=(), job="job-x")
    put(world, rd.Record((R(1, version=0), running), 1))
    argv = ("py", "ack_run.py", "--data.cache_dir", "%s/%s-r002" % (world.scratch.caches, DATASET))
    fake_job(world.jobs_root, argv, "finished", name="job-x", ended_at=stamp(20))
    world.trainer_makes(0)
    after = world.reconcile()
    assert (after.rounds[1].version, after.rounds[1].state, after.rounds[1].failure, after.current) == (None, "failed", "no_checkpoint", 1)


def test_a_round_that_ends_badly_does_not_take_the_chosen_round_away_from_an_earlier_one(world):
    world.run_round(version=0)
    world.run_round(version=1, ends="failed")
    world.run_round(version=2, ends="stopped", files="no_last")
    record = rd.load(world.paths)
    assert [r.state for r in record.rounds] == ["finished", "failed", "stopped"] and record.current == 1
    assert world.plan().parent == 1 and world.plan().resume_from.endswith("version_0/checkpoints/last.ckpt")


def test_a_round_stopped_by_hand_after_it_saved_a_point_becomes_the_chosen_one(world):
    world.run_round(version=0)
    world.run_round(version=1, ends="stopped")
    record = rd.load(world.paths)
    assert record.current == 2 and record.rounds[1].state == "stopped" and record.rounds[1].has_checkpoint


# ---------------------------------------------------------------- choosing a round, and going back

def test_a_round_can_be_chosen_when_it_ended_with_a_whole_saved_point_that_is_still_there(world):
    world.run_round(version=0)
    world.run_round(version=1)
    assert rd.choose(world.paths, 1).current == 1 and rd.load(world.paths).current == 1
    assert rd.choose(world.paths, 2).current == 2


def test_choosing_the_round_that_is_already_chosen_changes_nothing(world):
    world.run_round(version=0)
    before = slurp(world.paths.rounds_file)
    rd.choose(world.paths, 1)
    assert slurp(world.paths.rounds_file) == before


def test_a_round_cannot_be_chosen_if_it_is_unknown_failed_missing_damaged_or_while_one_runs(world):
    world.run_round(version=0)
    world.run_round(version=1, ends="failed")
    world.run_round(version=2)
    assert code_of(rd.choose, world.paths, 9) == "unknown_round" and code_of(rd.choose, world.paths, 0) == "unknown_round"
    assert code_of(rd.choose, world.paths, True) == "unknown_round" and code_of(rd.choose, world.paths, "1") == "unknown_round"
    assert code_of(rd.choose, world.paths, 2) == "not_usable"
    path = world.paths.run + "/lightning_logs/version_0/checkpoints/last.ckpt"
    saved = slurp(path)
    os.unlink(path)
    assert code_of(rd.choose, world.paths, 1) == "checkpoint_missing"
    spit(path, saved[: len(saved) // 2])
    assert code_of(rd.choose, world.paths, 1) == "checkpoint_damaged"
    spit(path, saved)
    world.begin()
    assert code_of(rd.choose, world.paths, 1) == "round_running"
    assert rd.load(world.paths).current == 3


def test_going_back_chooses_the_round_the_chosen_one_continued_from_and_touches_no_file(world):
    world.run_round(version=0)
    world.run_round(version=1)
    files = sorted(os.listdir(world.paths.run + "/lightning_logs/version_1/checkpoints"))
    assert rd.go_back_target(world.paths, rd.load(world.paths)) == 1
    assert rd.go_back(world.paths).current == 1
    assert sorted(os.listdir(world.paths.run + "/lightning_logs/version_1/checkpoints")) == files and len(rd.load(world.paths).rounds) == 2


def test_there_is_nowhere_to_go_back_to_from_the_first_round_or_with_nothing_chosen_or_when_the_earlier_file_is_gone(world):
    assert code_of(rd.go_back, world.paths) == "nowhere_back"
    world.run_round(version=0)
    assert rd.go_back_target(world.paths, rd.load(world.paths)) is None and code_of(rd.go_back, world.paths) == "nowhere_back"
    world.run_round(version=1)
    path = world.paths.run + "/lightning_logs/version_0/checkpoints/last.ckpt"
    saved = slurp(path)
    os.unlink(path)
    assert rd.go_back_target(world.paths, rd.load(world.paths)) is None
    spit(path, saved[:50])
    assert rd.go_back_target(world.paths, rd.load(world.paths)) is None and code_of(rd.go_back, world.paths) == "nowhere_back"
    spit(path, saved)
    assert rd.go_back(world.paths).current == 1 and code_of(rd.go_back, world.paths) == "nowhere_back"


def test_going_back_is_not_possible_while_a_round_runs(world):
    world.run_round(version=0)
    world.run_round(version=1)
    world.begin()
    assert code_of(rd.go_back, world.paths) == "round_running" and rd.load(world.paths).current == 2


def test_after_going_back_the_next_round_is_a_new_branch_and_the_round_that_was_left_stays(world):
    world.run_round(version=0)
    world.run_round(version=1)
    rd.go_back(world.paths)
    world.run_round(version=2)
    record = rd.load(world.paths)
    assert [(r.number, r.parent) for r in record.rounds] == [(1, 0), (2, 1), (3, 1)] and record.current == 3
    assert [r.number for r in rd.lineage(record, 3)] == [1, 3] and [r.number for r in rd.lineage(record, 2)] == [1, 2]
    assert os.path.isfile(world.paths.run + "/lightning_logs/version_1/checkpoints/last.ckpt")
    assert rd.choose(world.paths, 2).current == 2                       # the left-behind round can still be chosen while its file is there


# ---------------------------------------------------------------- how long a voice has been trained

def test_the_time_a_voice_has_been_trained_counts_only_the_rounds_that_made_it(world):
    world.run_round(version=0, minutes=20)
    world.run_round(version=1, minutes=25)
    rd.go_back(world.paths)
    world.run_round(version=2, minutes=10)
    record = rd.load(world.paths)
    assert rd.trained_minutes(record, 3) == 30 and rd.trained_minutes(record, 2) == 45 and rd.trained_minutes(record, 1) == 20
    assert rd.trained_minutes(record, 9) == 0 and rd.trained_minutes(rd.Record(), 1) == 0


def test_a_round_stopped_early_counts_for_the_time_it_ran_and_never_for_more_than_it_was_asked(world):
    base = rd.Record((R(1, state="stopped", started=stamp(0), ended=stamp(10)),), 1)
    assert rd.trained_minutes(base, 1) == 10
    for ended, expected in ((stamp(0), 0), (stamp(24), 24), (stamp(25), 25), (stamp(26), 25), (stamp(600), 25)):
        assert rd.trained_minutes(rd.Record((R(1, state="stopped", started=stamp(0), ended=ended),), 1), 1) == expected, ended
    assert rd.trained_minutes(rd.Record((R(1, state="stopped", started="?", ended=stamp(3)),), 1), 1) == 25      # times that cannot be read: the asked length


def test_elapsed_minutes_are_whole_minutes_and_never_negative():
    r = R(1, started=stamp(0))
    assert rd.elapsed_minutes(replace(r, ended=NOW.strftime("%Y-%m-%dT%H:%M:59Z"))) == 0
    assert rd.elapsed_minutes(replace(r, ended=NOW.strftime("%Y-%m-%dT%H:%M:00Z").replace(":00:00Z", ":01:00Z"))) == 1
    assert rd.elapsed_minutes(replace(r, ended=stamp(-5))) == 0 and rd.elapsed_minutes(replace(r, ended="")) is None and rd.elapsed_minutes(replace(r, started="x")) is None


def test_a_loop_of_parents_in_a_record_cannot_hang_the_lineage():
    loop = rd.Record((R(1, parent=2, voice=""), R(2, parent=1, voice="")), 1)
    assert len(rd.lineage(loop, 2)) <= 3


# ---------------------------------------------------------------- the helper's note on a round

def test_a_note_is_tidied_like_other_typed_text_and_can_be_removed(world):
    world.run_round(version=0)
    assert rd.set_note(world.paths, 1, "  clearer\non the  S sounds ").rounds[0].note == "clearer on the S sounds"
    assert rd.set_note(world.paths, 1, "x" * rd.MAX_NOTE).rounds[0].note == "x" * rd.MAX_NOTE
    assert rd.set_note(world.paths, 1, "y" * (rd.MAX_NOTE + 1)).rounds[0].note == "y" * rd.MAX_NOTE
    assert rd.set_note(world.paths, 1, "").rounds[0].note == "" and rd.set_note(world.paths, 1, "a\x00b").rounds[0].note == "ab"
    assert code_of(rd.set_note, world.paths, 5, "x") == "unknown_round" and code_of(rd.set_note, world.paths, 1, None) == "bad_value"


def test_a_note_can_be_written_while_the_round_is_running(world):
    world.begin()
    assert rd.set_note(world.paths, 1, "listening for the R sounds").rounds[0].note == "listening for the R sounds"


# ---------------------------------------------------------------- what may be freed

def names(pairs):
    return sorted((n, f.version, f.name) for n, f in pairs)


def three_rounds(world):
    for version in range(3):
        world.run_round(version=version)
    return rd.load(world.paths)


def test_only_the_chosen_rounds_saved_point_and_the_one_before_it_are_kept(world):
    record = three_rounds(world)
    kept = rd.retention(world.paths, record)
    assert names(kept.keep) == [(2, 1, "last.ckpt"), (3, 2, "last.ckpt")]
    assert len(kept.spare) == 7 and not kept.busy and not kept.unclaimed                    # round 1: three files, rounds 2 and 3: the extras
    assert all(not (f.name == "last.ckpt" and n in (2, 3)) for n, f in kept.spare)
    assert {n for n, f in kept.spare if f.name == "last.ckpt"} == {1}
    assert rd.kept_rounds(record) == (3, 2)


def test_going_back_moves_what_is_kept_and_the_round_that_was_left_becomes_spare(world):
    three_rounds(world)
    rd.go_back(world.paths)
    kept = rd.retention(world.paths, rd.load(world.paths))
    assert names(kept.keep) == [(1, 0, "last.ckpt"), (2, 1, "last.ckpt")]
    assert {n for n, f in kept.spare if f.name == "last.ckpt"} == {3}


def test_a_round_that_started_from_the_starting_voice_keeps_only_its_own_file(world):
    world.run_round(version=0)
    record = rd.load(world.paths)
    kept = rd.retention(world.paths, record)
    assert names(kept.keep) == [(1, 0, "last.ckpt")] and rd.kept_rounds(record) == (1,) and len(kept.spare) == 2


def test_with_nothing_chosen_nothing_is_kept_and_the_files_of_failed_rounds_are_spare(world):
    world.run_round(version=0, ends="failed")
    kept = rd.retention(world.paths, rd.load(world.paths))
    assert kept.keep == () and len(kept.spare) == 3 and rd.kept_rounds(rd.load(world.paths)) == ()


def test_the_files_of_the_round_that_is_running_are_never_offered(world):
    world.run_round(version=0)
    plan = world.begin()
    rd.attach_job(world.paths, 2, world.job_for(plan, "running").id)
    world.trainer_makes(1)
    kept = rd.retention(world.paths, rd.load(world.paths))
    assert {n for n, f in kept.busy} == {2} and len(kept.busy) == 3 and not any(n == 2 for n, f in kept.spare + kept.keep) and not kept.unclaimed      # before anything noticed the folder
    world.reconcile(now=NOW + timedelta(seconds=1))
    again = rd.retention(world.paths, rd.load(world.paths))
    assert again.busy == kept.busy and rd.load(world.paths).rounds[1].version == 1 and not again.unclaimed                                           # and after


def test_files_in_a_folder_no_round_claims_are_left_alone_and_never_offered(world):
    world.run_round(version=0)
    world.trainer_makes(7)                                             # from before the record, or not made by this tool
    kept = rd.retention(world.paths, rd.load(world.paths))
    assert {f.version for f in kept.unclaimed} == {7} and len(kept.unclaimed) == 3
    assert not any(f.version == 7 for n, f in kept.keep + kept.spare + kept.busy)
    assert all("version_7" not in item.key for item in rd.cleanup_items(kept))


def test_links_and_other_files_are_not_listed_so_they_can_never_be_offered(world):
    world.run_round(version=0)
    folder = world.paths.run + "/lightning_logs/version_0/checkpoints"
    outside = os.path.join(os.path.dirname(world.paths.root), "elsewhere.ckpt")
    spit(outside, b"precious")
    os.symlink(outside, folder + "/linked.ckpt")
    spit(folder + "/notes.txt", "hi")
    os.makedirs(folder + "/a-folder.ckpt")
    listed = [f.name for f in rd.scan_checkpoint_files(world.paths)]
    assert "linked.ckpt" not in listed and "notes.txt" not in listed and "a-folder.ckpt" not in listed and "last.ckpt" in listed


def test_the_list_for_freeing_up_space_matches_the_disk_budgets_and_never_offers_a_kept_file(world):
    record = three_rounds(world)
    kept = rd.retention(world.paths, record)
    items = rd.cleanup_items(kept)
    assert len({i.key for i in items}) == len(items) == 9
    assert all(i.protected and i.kind is diskbudget.Kind.PRECIOUS for i in items if i.key in ("checkpoint.round2.last.ckpt", "checkpoint.round3.last.ckpt"))
    offered = diskbudget.reclaimable(items)
    assert {i.key for i in offered} == {"checkpoint.round%d.%s" % (n, f.name) for n, f in kept.spare} and not any(i.protected for i in offered)
    picked, enough = diskbudget.pick_to_free(items, 10 ** 12)
    assert not enough and {i.key for i in picked} == {i.key for i in offered}
    assert sum(i.bytes for i in offered) == sum(f.size for n, f in kept.spare) and all(i.bytes > 0 for i in offered)


def test_a_run_folder_that_does_not_exist_yet_has_nothing_to_offer(world):
    assert rd.retention(world.paths, rd.Record()) == rd.Retention((), (), (), ())


# ---------------------------------------------------------------- starting a round

def starter(status="running", calls=None):
    calls = [] if calls is None else calls

    def start(jobs_root, spec):
        calls.append(spec)
        return fake_job(jobs_root, spec.argv, status, run_dir=spec.cwd)
    return start, calls


def go(world, start, **kw):
    kw.setdefault("dataset", DATASET)
    kw.setdefault("base", world.base)
    kw.setdefault("now", NOW)
    return rd.start_round(world.paths, world.scratch, PROJECT, world.training, world.jobs_root, start=start, **kw)


def option(spec, name):
    return spec.argv[spec.argv.index(name) + 1]


def test_the_first_round_is_started_from_the_starting_voice_with_every_rule_applied(world):
    world.dataset()
    start, calls = starter()
    started = go(world, start)
    spec = calls[0]
    assert (started.number, spec.kind, spec.gpu, spec.project, spec.cwd) == (1, "train", True, PROJECT, world.paths.run)
    assert option(spec, "--ckpt_path") == world.base_path and option(spec, "--trainer.max_time") == "00:00:25:00"
    assert option(spec, "--data.cache_dir") == world.scratch.caches + "/" + DATASET + "-r001" and option(spec, "--data.config_path").endswith("/config/round-001.json")
    assert option(spec, "--data.audio_dir") == world.scratch.datasets + "/" + DATASET + "/wav"
    record = rd.load(world.paths)
    assert (record.rounds[0].state, record.rounds[0].job, record.rounds[0].voice, record.rounds[0].parent, record.rounds[0].started) == ("running", started.job, VOICE, 0, stamp())
    assert os.path.isdir(world.paths.run) and os.path.isdir(world.scratch.caches) and not os.path.exists(option(spec, "--data.cache_dir"))


def test_a_round_started_after_one_ended_is_started_from_that_rounds_saved_point_in_the_same_call(world):
    world.dataset()
    start, calls = starter()
    first = go(world, start)
    end_job(world.jobs_root + "/" + first.job, "finished", ended_at=stamp(26))
    world.trainer_makes(0)
    second = go(world, start, now=NOW + timedelta(minutes=30), minutes=10)               # nothing noticed the first round's end before this call
    record = rd.load(world.paths)
    assert [(r.number, r.state, r.parent) for r in record.rounds] == [(1, "finished", 0), (2, "running", 1)] and record.current == 1
    assert option(calls[1], "--ckpt_path") == world.paths.run + "/lightning_logs/version_0/checkpoints/last.ckpt" and option(calls[1], "--trainer.max_time") == "00:00:10:00"
    assert second.number == 2 and option(calls[1], "--data.cache_dir").endswith("-r002")


def test_a_round_that_cannot_be_built_leaves_nothing_behind_and_starts_nothing(world):
    start, calls = starter()
    with pytest.raises(CommandError) as caught:
        go(world, start)                                               # the training set has not been made
    assert caught.value.code == "dataset_incomplete" and calls == [] and not os.path.exists(world.paths.rounds_file)
    world.dataset()
    os.makedirs(world.scratch.caches + "/" + DATASET + "-r001")
    with pytest.raises(CommandError) as caught:
        go(world, start)                                               # an old working folder is in the way
    assert caught.value.code == "cache_exists" and calls == [] and not os.path.exists(world.paths.rounds_file)
    os.rmdir(world.scratch.caches + "/" + DATASET + "-r001")
    os.unlink(world.base_path)
    with pytest.raises(CommandError) as caught:
        go(world, start)                                               # the starting voice's file is not there
    assert caught.value.code == "bad_checkpoint" and calls == [] and not os.path.exists(world.paths.rounds_file)


def test_a_round_with_a_bad_length_or_no_way_to_start_is_refused_before_anything_is_made(world):
    world.dataset()
    start, calls = starter()
    assert code_of(go, world, start, minutes=0) == "bad_value" and code_of(go, world, start, base=None) == "no_start"
    assert calls == [] and not os.path.exists(world.paths.run) and not os.path.exists(world.paths.rounds_file)


def test_a_second_round_is_not_started_while_one_runs(world):
    world.dataset()
    start, calls = starter()
    go(world, start)
    assert code_of(go, world, start, now=NOW + timedelta(minutes=1)) == "round_running" and len(calls) == 1 and len(rd.load(world.paths).rounds) == 1


def test_if_the_job_does_not_start_the_reason_is_raised_and_the_round_is_taken_back(world):
    world.dataset()

    def busy(jobs_root, spec):
        raise jobs.JobError("gpu_busy", "20261011-000000-train-abcd")
    with pytest.raises(jobs.JobError) as caught:
        go(world, busy)
    assert caught.value.code == "gpu_busy" and rd.load(world.paths).rounds == ()
    start, _ = starter()
    assert go(world, start).number == 1                                # the number is free again


def test_any_failure_to_start_takes_the_round_back_and_the_original_reason_wins_even_if_taking_back_fails(world, monkeypatch):
    world.dataset()

    def odd(jobs_root, spec):
        raise RuntimeError("odd")
    with pytest.raises(RuntimeError):
        go(world, odd)
    assert rd.load(world.paths).rounds == ()

    def refuse(paths, number):
        raise rd.RoundsError("busy", "x")
    monkeypatch.setattr(rd, "rollback_start", refuse)
    with pytest.raises(RuntimeError):
        go(world, odd)
    assert [r.state for r in rd.load(world.paths).rounds] == ["starting"]                    # left for the next look: it becomes "never started" after a while
    assert world.reconcile(now=NOW + timedelta(seconds=rd.STARTING_GRACE_S + 1)).rounds[0].state == "never_started"


def test_the_graphics_card_being_busy_refuses_the_round_through_the_real_supervisor(world):
    world.dataset()
    fake_job(world.jobs_root, ("py", "something"), "running")
    with pytest.raises(jobs.JobError) as caught:
        go(world, jobs.start_job)
    assert caught.value.code == "gpu_busy" and rd.load(world.paths).rounds == ()


def test_a_program_that_stopped_between_writing_a_round_down_and_starting_its_job_leaves_a_round_that_is_called_what_it_is(world):
    world.begin()                                                      # then the program ended: no job, no name
    assert world.reconcile(now=NOW + timedelta(seconds=10)).rounds[0].state == "starting"
    world.dataset()
    start, calls = starter()
    assert code_of(go, world, start, now=NOW + timedelta(seconds=10)) == "round_running"             # still within the wait: not started on top of it
    started = go(world, start, now=NOW + timedelta(seconds=rd.STARTING_GRACE_S))
    record = rd.load(world.paths)
    assert [(r.number, r.state) for r in record.rounds] == [(1, "never_started"), (2, "running")] and started.number == 2


# ---------------------------------------------------------------- real detached jobs with a stand-in trainer

def test_three_rounds_through_real_detached_jobs_with_going_back_in_the_middle(tmp_path):
    w = make_world(tmp_path)
    training = make_fake_training_env(tmp_path)
    w.dataset()

    def one_round(**kw):
        started = rd.start_round(w.paths, w.scratch, PROJECT, training, w.jobs_root, dataset=DATASET, base=w.base, minutes=1, **kw)
        info = wait_for_end(w.jobs_root + "/" + started.job)
        assert info.status is jobs.JobStatus.FINISHED, jobs.tail_log(info.dir)
        return started, "\n".join(jobs.tail_log(info.dir))

    run = w.paths.run + "/lightning_logs/version_%d/checkpoints/last.ckpt"
    first, log = one_round()
    assert "trained version_0 from %s for 00:00:01:00" % w.base_path in log
    second, log = one_round()
    assert "trained version_1 from %s" % (run % 0) in log                                      # the person's own file, not the starting voice's
    record = rd.reconcile(w.paths, w.scratch, w.jobs_root, PROJECT)
    assert [(r.number, r.state, r.version, r.has_checkpoint) for r in record.rounds] == [(1, "finished", 0, True), (2, "finished", 1, True)] and record.current == 2
    assert rd.go_back(w.paths).current == 1
    third, log = one_round()
    assert "trained version_2 from %s" % (run % 0) in log                                      # a new branch from round 1, not from the round that was left
    record = rd.reconcile(w.paths, w.scratch, w.jobs_root, PROJECT)
    assert [(r.number, r.parent, r.version) for r in record.rounds] == [(1, 0, 0), (2, 1, 1), (3, 1, 2)] and record.current == 3
    assert [r.number for r in rd.lineage(record, 3)] == [1, 3] and rd.trained_minutes(record, 3) == 2
    kept = rd.retention(w.paths, record)
    assert names(kept.keep) == [(1, 0, "last.ckpt"), (3, 2, "last.ckpt")] and {n for n, f in kept.spare if f.name == "last.ckpt"} == {2}
    assert not os.path.exists(w.scratch.caches + "/" + DATASET + "-r004") and sorted(os.listdir(w.scratch.caches)) == [DATASET + "-r001", DATASET + "-r002", DATASET + "-r003"]


# ---------------------------------------------------------------- looking without writing

def test_looking_works_out_what_noticing_would_write_and_writes_nothing(world):
    plan = world.begin()
    info = world.job_for(plan, "running")
    rd.attach_job(world.paths, 1, info.id)
    world.trainer_makes(0)
    end_job(info.dir, "finished", ended_at=stamp(20))
    before, stat, previous = slurp(world.paths.rounds_file), os.stat(world.paths.rounds_file), slurp(world.paths.rounds_previous)
    seen = rd.reconcile(world.paths, world.scratch, world.jobs_root, PROJECT, now=NOW + timedelta(minutes=30), write=False)
    assert slurp(world.paths.rounds_file) == before and os.stat(world.paths.rounds_file).st_mtime_ns == stat.st_mtime_ns and slurp(world.paths.rounds_previous) == previous
    assert (seen.rounds[0].state, seen.current) == ("finished", 1) and rd.load(world.paths).rounds[0].state == "running"
    written = world.reconcile()
    assert written == seen and rd.load(world.paths) == seen                                   # the same answer, then written


def test_looking_at_a_project_with_no_record_creates_nothing(world):
    assert rd.reconcile(world.paths, world.scratch, world.jobs_root, PROJECT, write=False) == rd.Record()
    assert not os.path.exists(world.paths.rounds_file) and not os.path.exists(world.paths.rounds_lock)


def test_what_was_noticed_is_the_rounds_that_are_new_or_changed_state():
    a, b = R(1), R(2, parent=1, voice="", state="running", ended="", has_checkpoint=False, version=None, versions_before=(0,))
    before = rd.Record((a, b), 1)
    after = rd.Record((a, replace(b, state="finished", ended=stamp(5), has_checkpoint=True, version=1), R(3, parent=2, voice="", state="starting", ended="", has_checkpoint=False, version=None)), 2)
    assert [r.number for r in rd.noticed(before, after)] == [2, 3] and rd.noticed(after, after) == () and rd.noticed(rd.Record(), before) == before.rounds
    assert rd.noticed(before, replace(before, rounds=(a, replace(b, note="x")))) == ()                  # a note is not something that happened


# ---------------------------------------------------------------- limits, to the number

def one_round_dict(**over):
    data = rd.record_to_dict(rd.Record((R(1),), 1))
    data["rounds"][0].update(over)
    return data


@pytest.mark.parametrize("key, value, good", [
    ("number", rd.MAX_ROUNDS, True), ("number", rd.MAX_ROUNDS + 1, False), ("number", 1, True), ("number", 0, False),
    ("version", rd.MAX_VERSION, True), ("version", rd.MAX_VERSION + 1, False), ("version", 0, True), ("version", -1, False),
    ("minutes", rd.MAX_MINUTES, True), ("minutes", rd.MAX_MINUTES + 1, False), ("minutes", 1, True), ("minutes", 0, False),
    ("exit_code", 1_000_000, True), ("exit_code", 1_000_001, False), ("exit_code", -1_000_000, True), ("exit_code", -1_000_001, False),
    ("versions_before", [rd.MAX_VERSION], True), ("versions_before", [rd.MAX_VERSION + 1], False),
])
def test_a_number_in_a_record_is_accepted_up_to_its_limit_and_not_one_past_it(key, value, good):
    data = one_round_dict(**{key: value})
    if key == "version":
        data["rounds"][0]["versions_before"] = []
    if key == "versions_before":
        data["rounds"][0]["version"] = 0
    if key == "number":
        data["current"] = value
    if good:
        assert rd.record_from_text(json.dumps(data)).rounds
    else:
        assert code_of(rd.record_from_text, json.dumps(data)) == "damaged"


def test_the_chosen_round_and_the_parent_may_be_as_large_as_a_round_number_can_be():
    big = rd.MAX_ROUNDS
    record = rd.Record((R(1), R(big, parent=1, voice="", version=1)), current=big)
    assert rd.record_from_text(json.dumps(rd.record_to_dict(record))) == record
    data = rd.record_to_dict(record)
    data["current"] = big + 1
    assert code_of(rd.record_from_text, json.dumps(data)) == "damaged"
    data = rd.record_to_dict(rd.Record((R(1), R(2, parent=1, voice="", version=1)), 2))
    data["rounds"][1]["parent"] = rd.MAX_ROUNDS + 1
    assert code_of(rd.record_from_text, json.dumps(data)) == "damaged"


def test_the_next_round_number_follows_the_highest_number_not_how_many_rounds_there_are(world):
    put(world, rd.Record((R(1), R(3, parent=1, voice="", version=1)), 3))                    # a gap is legal: numbers are only never reused
    world.trainer_makes(0)
    world.trainer_makes(1)
    assert rd.next_number(rd.load(world.paths)) == 4 and world.plan(base=None).number == 4


def test_a_round_that_failed_adds_nothing_to_the_time_a_voice_has_been_trained(world):
    world.run_round(version=0, minutes=20)
    world.run_round(version=1, ends="failed", minutes=25)
    record = rd.load(world.paths)
    assert [r.state for r in record.rounds] == ["finished", "failed"] and rd.trained_minutes(record, 2) == 20 and rd.trained_minutes(record, 1) == 20       # not 45
    interrupted = rd.Record((R(1), R(2, parent=1, voice="", state="interrupted")), 1)
    assert rd.trained_minutes(interrupted, 2) == 25


@pytest.mark.parametrize("value", [5, None, {}, "0", 0.5, True])
def test_the_list_of_folders_from_before_must_be_a_list_whatever_else_it_is(value):
    data = one_round_dict(versions_before=value)
    assert code_of(rd.record_from_text, json.dumps(data)) == "damaged"


def test_a_note_read_from_the_file_is_tidied_like_one_typed():
    data = one_round_dict(note="  a\nb   c\x00d ")
    assert rd.record_from_text(json.dumps(data)).rounds[0].note == "a b cd"
    assert rd.record_from_text(json.dumps(one_round_dict(note="x" * 900))).rounds[0].note == "x" * rd.MAX_NOTE
    assert rd.record_from_text(json.dumps(one_round_dict(note=None))).rounds[0].note == ""


@pytest.mark.parametrize("numbers, ordered", [((1, 2), True), ((1, 3), True), ((1, 1), False), ((2, 1), False), ((1, 3, 2), False), ((1, 2, 2), False)])
def test_round_numbers_must_go_up_down_the_list_and_never_repeat(numbers, ordered):
    record = rd.Record(tuple(R(n, version=i) for i, n in enumerate(numbers)), current=numbers[0])
    if ordered:
        rd.validate(record)
    else:
        with pytest.raises(rd.RoundsError) as caught:
            rd.validate(record)
        assert (caught.value.code, caught.value.detail) == ("damaged", "order")


def test_a_running_round_that_is_not_the_last_round_is_damaged_even_when_it_is_the_only_one_running():
    running = R(1, state="running", ended="", has_checkpoint=False, version=None, job="job-1")
    later = R(2, version=0)                                      # a round that began and finished while round 1 was written down as running
    record = rd.Record((running, later), current=2)
    with pytest.raises(rd.RoundsError) as caught:
        rd.validate(record)
    assert (caught.value.code, caught.value.detail) == ("damaged", "active")
    rd.validate(rd.Record((later, replace(running, number=3, parent=0)), current=2))      # the same two, in the right order


def test_reading_a_project_that_has_no_rounds_folder_makes_no_folder(tmp_path):
    from voice_studio.core.paths import ProjectPaths, ScratchPaths
    paths, scratch = ProjectPaths(str(tmp_path / "nowhere")), ScratchPaths(str(tmp_path / "nowhere/scratch"))
    assert rd.load(paths) == rd.Record() and rd.reconcile(paths, scratch, str(tmp_path / "jobs"), PROJECT, write=False) == rd.Record()
    assert not os.path.exists(tmp_path / "nowhere")


def test_a_write_that_fails_part_way_leaves_no_half_made_file_behind(world, monkeypatch):
    rd.modify(world.paths, lambda old: rd.Record((R(1),), 1))

    def fail(source, target):
        raise OSError(errno.EXDEV, "cannot rename across devices")
    monkeypatch.setattr(os, "replace", fail)
    assert code_of(rd.set_note, world.paths, 1, "x") == "cannot_save"
    assert [n for n in os.listdir(world.paths.rounds) if n.endswith(".tmp")] == []


def test_a_saved_record_is_forced_to_disk_before_it_replaces_the_old_one(world, monkeypatch):
    synced = []
    real = os.fsync
    monkeypatch.setattr(os, "fsync", lambda fd: (synced.append(fd), real(fd))[1])
    rd.modify(world.paths, lambda old: rd.Record((R(1),), 1))
    assert synced, "the new record must be on the disk before the old one is replaced by it"


def test_a_lock_that_cannot_be_taken_for_another_reason_than_someone_holding_it_is_not_called_busy(world, monkeypatch):
    def broken(fd, how):
        raise OSError(errno.ENOLCK, "No locks available")
    monkeypatch.setattr(rd.fcntl, "flock", broken)
    assert code_of(rd.modify, world.paths, lambda old: old) == "cannot_save"
    monkeypatch.undo()
    assert code_of(rd.modify, type(world.paths)("/proc/does-not-exist/p"), lambda old: old) == "cannot_save"          # not even the folder for the lock can be made


def test_a_file_whose_name_only_ends_in_data_pkl_is_not_the_state(tmp_path):
    import zipfile
    with zipfile.ZipFile(tmp_path / "x.ckpt", "w") as z:
        z.writestr("archive/notdata.pkl", b"x")
        z.writestr("xdata.pkl", b"x")
    assert rd.checkpoint_complete(str(tmp_path / "x.ckpt")) is False


def test_a_folder_that_was_there_before_the_round_is_never_taken_for_the_rounds_own(world):
    world.trainer_makes(7)                                             # left in the run folder before the round began
    world.run_round(version=0, files="none")                          # the trainer made nothing
    r = rd.load(world.paths).rounds[0]
    assert (r.version, r.state, r.failure, r.versions_before) == (None, "failed", "no_checkpoint", (7,))


def test_a_round_written_as_starting_that_already_has_a_job_is_never_taken_back(world):
    put(world, rd.Record((R(1, state="starting", ended="", has_checkpoint=False, version=None, job="job-1"),), 0))
    assert [r.number for r in rd.rollback_start(world.paths, 1).rounds] == [1]


def test_going_back_after_a_branch_goes_to_the_round_the_chosen_one_continued_from_not_to_the_number_before_it(world):
    world.run_round(version=0)
    world.run_round(version=1)
    rd.go_back(world.paths)                                            # back to round 1
    world.run_round(version=2)                                         # round 3 continues from round 1; round 2 is the number before it, but not what it came from
    record = rd.load(world.paths)
    assert (record.current, rd.chosen(record).parent) == (3, 1)
    assert rd.go_back_target(world.paths, record) == 1
    assert rd.go_back(world.paths).current == 1
    assert rd.kept_rounds(rd.load(world.paths)) == (1,)


def test_a_job_for_another_working_folder_is_never_taken_for_this_round(world):
    plan = world.begin()
    other = ("py", "ack_run.py", "--data.cache_dir", "%s/%s-r002" % (world.scratch.caches, DATASET))
    fake_job(world.jobs_root, other, "running")
    fake_job(world.jobs_root, ("py", "ack_run.py", "--data.cache_dir"), "running")                    # an option with no value after it
    r = world.reconcile(now=NOW + timedelta(seconds=30)).rounds[0]
    assert (r.state, r.job) == ("starting", "")
    mine = fake_job(world.jobs_root, world.command_of(plan).argv, "running")
    assert world.reconcile(now=NOW + timedelta(seconds=30)).rounds[0].job == mine.id


def test_a_round_whose_named_job_folder_is_gone_is_still_found_by_its_working_folder(world):
    plan = world.begin()
    rd.attach_job(world.paths, 1, "job-gone")                                                   # the name the record has no folder for
    mine = fake_job(world.jobs_root, world.command_of(plan).argv, "running")
    r = world.reconcile().rounds[0]
    assert (r.state, r.job) == ("running", mine.id)


def test_the_folder_a_running_round_was_seen_to_make_stays_its_own_when_another_appears_before_it_ends(world):
    plan = world.begin()
    info = world.job_for(plan, "running")
    rd.attach_job(world.paths, 1, info.id)
    world.trainer_makes(0)
    assert world.reconcile().rounds[0].version == 0                    # seen while it ran
    world.trainer_makes(5)                                             # something else appears in the run folder afterwards
    end_job(info.dir, "finished", ended_at=stamp(20))
    r = world.reconcile().rounds[0]
    assert (r.state, r.version) == ("finished", 0)


def test_a_running_round_whose_job_is_gone_does_not_wait_out_the_start_up_time(world):
    world.begin()
    rd.attach_job(world.paths, 1, "job-gone")                          # a job's folder exists before its name is written down, so a missing one has vanished
    r = world.reconcile(now=NOW + timedelta(seconds=10)).rounds[0]
    assert (r.state, r.failure) == ("interrupted", "job_missing")


def test_the_batch_size_the_workers_and_the_check_interval_asked_for_reach_the_trainers_command(world):
    world.dataset()
    start, calls = starter()
    rd.start_round(world.paths, world.scratch, PROJECT, world.training, world.jobs_root, dataset=DATASET, base=world.base, now=NOW, start=start, batch_size=8, workers=2, check_every=5)
    spec = calls[0]
    assert [option(spec, o) for o in ("--data.batch_size", "--data.num_workers", "--trainer.check_val_every_n_epoch")] == ["8", "2", "5"]


def test_the_saved_files_are_listed_in_the_same_order_whatever_order_the_disk_gives_them(world, monkeypatch):
    for version in (2, 0, 1):
        world.trainer_makes(version, extras=3)
    real = os.scandir

    class Backwards:
        def __init__(self, path):
            self.inner = real(path)

        def __enter__(self):
            return iter(list(self.inner.__enter__())[::-1])

        def __exit__(self, *exc):
            return self.inner.__exit__(*exc)
    monkeypatch.setattr(os, "scandir", Backwards)
    listed = [(f.version, f.name) for f in rd.scan_checkpoint_files(world.paths)]
    assert listed == sorted(listed) and len(listed) == 12 and rd.version_dirs(world.paths) == (0, 1, 2)


def test_a_trainer_folder_with_no_saved_files_does_not_hide_the_ones_after_it(world):
    os.makedirs(world.paths.run + "/lightning_logs/version_0")                                    # a round that failed before it saved anything
    world.trainer_makes(1)
    assert {f.version for f in rd.scan_checkpoint_files(world.paths)} == {1}


def test_a_folder_that_was_already_there_when_the_running_round_began_is_not_that_rounds_busy_file(world):
    world.trainer_makes(7)
    plan = world.begin()
    rd.attach_job(world.paths, 1, world.job_for(plan, "running").id)
    world.trainer_makes(8)
    kept = rd.retention(world.paths, rd.load(world.paths))
    assert {f.version for n, f in kept.busy} == {8} and {f.version for f in kept.unclaimed} == {7}


def test_once_the_running_round_has_its_folder_a_newer_stray_one_is_not_also_its_own(world):
    plan = world.begin()
    rd.attach_job(world.paths, 1, world.job_for(plan, "running").id)
    world.trainer_makes(8)
    world.reconcile(now=NOW + timedelta(seconds=1))                    # the round is seen to own version 8
    world.trainer_makes(9)
    kept = rd.retention(world.paths, rd.load(world.paths))
    assert {f.version for n, f in kept.busy} == {8} and {f.version for f in kept.unclaimed} == {9}


def test_the_files_of_the_running_round_and_files_nobody_claimed_are_not_in_the_list_for_freeing_up_space(world):
    world.run_round(version=0)
    world.trainer_makes(9)                                             # there before the next round began
    plan = world.begin()
    rd.attach_job(world.paths, 2, world.job_for(plan, "running").id)
    world.trainer_makes(10)
    kept = rd.retention(world.paths, rd.load(world.paths))
    assert len(kept.busy) == 3 and len(kept.unclaimed) == 3 and {f.version for n, f in kept.busy} == {10} and {f.version for f in kept.unclaimed} == {9}
    items = rd.cleanup_items(kept)
    assert {i.key for i in items} == {"checkpoint.round1.%s" % f.name for n, f in kept.keep + kept.spare}
    assert not [i for i in diskbudget.reclaimable(items) if "round2" in i.key]


# ---------------------------------------------------------------- stopped by the disk guard

def test_a_round_the_runner_stopped_because_the_disk_was_nearly_full_remembers_why_and_can_still_be_continued_from(world):
    world.run_round(version=0, ends="stopped", reason="disk")
    r = rd.load(world.paths).rounds[0]
    assert (r.state, r.stopped_for, r.has_checkpoint) == ("stopped", "disk", True) and rd.load(world.paths).current == 1
    world.run_round(version=1, ends="stopped")                          # a stop a person asked for has no reason
    assert rd.load(world.paths).rounds[1].stopped_for == ""


def test_a_stop_reason_is_only_read_from_a_stop_and_a_later_stopped_round_keeps_its_own(world):
    world.run_round(version=0, ends="failed", reason="disk")
    assert rd.load(world.paths).rounds[0].stopped_for == ""            # reason is only written for a stop; a plain failure writes none
    world.run_round(version=1)
    plan = world.begin()
    info = world.job_for(plan, "running")
    rd.attach_job(world.paths, 3, info.id)
    end_job(info.dir, "stopped", reason="disk")
    assert world.reconcile().rounds[2].stopped_for == "disk"


@pytest.mark.parametrize("change, good", [
    (lambda d: d["rounds"][0].update(stopped_for="disk"), True), (lambda d: d["rounds"][0].update(stopped_for=""), True), (lambda d: d["rounds"][0].update(stopped_for=None), True),
    (lambda d: d["rounds"][0].update(stopped_for="because"), False), (lambda d: d["rounds"][0].update(stopped_for=5), False),
    (lambda d: d["rounds"][0].update(state="running", ended="", has_checkpoint=False, version=None, stopped_for="disk") or d.update(current=0), False),
])
def test_the_reason_a_round_was_stopped_is_one_of_the_known_ones_and_only_for_a_round_that_ended(change, good):
    data = one_round_dict()
    change(data)
    if good:
        rd.record_from_text(json.dumps(data))
    else:
        assert code_of(rd.record_from_text, json.dumps(data)) == "damaged"


def test_the_reason_survives_saving_and_reading(world):
    record = rd.Record((R(1, state="stopped", stopped_for="disk"),), 1)
    rd.modify(world.paths, lambda old: record)
    assert rd.load(world.paths) == record and json.loads(slurp(world.paths.rounds_file))["rounds"][0]["stopped_for"] == "disk"


def test_the_free_space_floors_asked_for_reach_the_job_the_runner_will_watch(world):
    world.dataset()
    start, calls = starter()
    watch = ((world.paths.run, 1_640_000_000), (world.scratch.caches, 1_114_000_000))
    rd.start_round(world.paths, world.scratch, PROJECT, world.training, world.jobs_root, dataset=DATASET, base=world.base, now=NOW, start=start, watch=watch)
    assert calls[0].watch == watch
