# SPDX-License-Identifier: GPL-3.0-or-later
"""The builder carries on by itself when the connection drops (plan finding F20, decision D35).

The computer and the network are the builder tests' stand-ins, so a whole build runs here; what pip prints when something goes wrong is what
real pip printed (tests/data/pip_transcripts). Nothing here sleeps: waiting moves a fake clock.
"""
import dataclasses
from pathlib import Path

import pytest

from vs_env_helpers import FakeTime, make_rig, pip_text
from voice_studio.core import connection as cn
from voice_studio.core import envbuild as eb


def lock_runs(rig):
    return [argv for argv in rig.doors.pip_runs if "--require-hashes" in argv]


def with_time(rig, patience=None):
    t = FakeTime()
    rig.ctx = dataclasses.replace(rig.ctx, sleep=t.sleep, monotonic=t.monotonic, **({"patience": patience} if patience else {}))
    return t


@pytest.fixture
def rig(tmp_path):
    return make_rig(tmp_path)


def log_text(rig):
    return Path(rig.paths.log).read_text(encoding="utf-8")


# ---------------------------------------------------------------- a drop that comes back

def test_a_connection_that_drops_and_comes_back_is_waited_for_and_the_build_finishes(rig):
    t = with_time(rig)
    rig.doors.pip_script = [(1, pip_text("connection_refused"))]
    result = rig.build()
    assert result.ok and rig.record()["state"] == "ready"
    assert t.slept == [5] and len(lock_runs(rig)) == 2                     # the same command, run again, once


def test_the_person_is_told_when_it_drops_and_when_it_is_back_by_events_not_by_log_lines(rig):
    with_time(rig)
    rig.doors.pip_script = [(1, pip_text("connection_refused"))]
    rig.build()
    offline = [e for e in rig.events if e.kind == "offline"]
    assert offline == [eb.Event("offline", "pip_lock", wait=cn.Wait(5, 0, 1800, True))]
    assert [e.step for e in rig.events if e.kind == "online"] == ["pip_lock"]
    assert not any("ack-voice-studio" in e.text for e in rig.events if e.kind == "line")      # the tool's own remarks are for the saved log, not progress


def test_the_saved_log_records_each_wait_and_the_return(rig):
    with_time(rig)
    rig.doors.pip_script = [(1, pip_text("connection_refused")), (1, pip_text("connection_refused"))]
    rig.build()
    log = log_text(rig)
    assert "[ack-voice-studio] the connection stopped; trying again in 5 s (away for 0 s so far)" in log
    assert "[ack-voice-studio] the connection stopped; trying again in 10 s (away for 5 s so far)" in log
    assert log.count("[ack-voice-studio] the connection is back") == 1


def test_the_waits_follow_the_schedule_and_the_first_is_marked(rig):
    t = with_time(rig)
    rig.doors.pip_script = [(1, pip_text("connection_refused"))] * 5
    assert rig.build().ok
    assert t.slept == [5, 10, 20, 30, 60]
    assert [e.wait.first for e in rig.events if e.kind == "offline"] == [True, False, False, False, False]


@pytest.mark.parametrize("name", ["reset_during_download", "stalled_download"])
def test_a_reset_or_a_stall_in_the_middle_of_a_file_ends_in_exit_two_and_is_waited_for_too(rig, name):
    t = with_time(rig)
    rig.doors.pip_script = [(2, pip_text(name))]
    assert rig.build().ok and t.slept == [5]


def test_a_download_cut_in_half_reads_as_a_mismatch_and_is_tried_again(rig):
    t = with_time(rig)
    rig.doors.pip_script = [(1, pip_text("cut_download_pip22"))]
    assert rig.build().ok and t.slept == [5]


def test_a_download_cut_in_a_different_place_each_time_keeps_going(rig):
    t = with_time(rig)
    first = pip_text("cut_download_pip22")
    other = first.replace("1d62f08f0e846718c190ca0d89834db74887cef0b7400c5e8b5d239c5e5eb69e", "2" * 64)
    rig.doors.pip_script = [(1, first), (1, other), (1, first)]
    assert rig.build().ok and t.slept == [5, 10, 20]


# ---------------------------------------------------------------- what is not waited for

def test_a_wrong_file_that_comes_out_the_same_way_twice_stops_and_says_it_is_not_the_connection(rig):
    t = with_time(rig)
    rig.doors.pip_script = [(1, pip_text("cut_download_pip22"))] * 3
    result = rig.build()
    assert not result.ok and result.error.code == "download_mismatch" and result.error.detail == "exit 1"
    assert t.slept == [5] and len(lock_runs(rig)) == 2 and rig.record()["state"] == "failed"
    assert result.error.tail                                                # the person can see what pip said


def test_a_certificate_problem_is_not_waited_for(rig):
    t = with_time(rig)
    rig.doors.pip_script = [(1, pip_text("certificate_not_trusted"))]
    result = rig.build()
    assert not result.ok and result.error.code == "pip_failed" and result.error.detail == "exit 1"
    assert t.slept == [] and len(lock_runs(rig)) == 1


def test_a_plain_failure_is_not_waited_for(rig):
    t = with_time(rig)
    rig.doors.pip_script = [(1, "ERROR: Could not find a version that satisfies the requirement x\nERROR: No matching distribution found for x\n")]
    result = rig.build()
    assert not result.ok and result.error.code == "pip_failed" and t.slept == [] and rig.events and not [e for e in rig.events if e.kind == "offline"]


def test_a_failure_on_the_second_try_that_is_not_the_connection_ends_the_waiting(rig):
    t = with_time(rig)
    rig.doors.pip_script = [(1, pip_text("connection_refused")), (1, "ERROR: Could not find a version that satisfies the requirement x\n")]
    result = rig.build()
    assert not result.ok and result.error.code == "pip_failed" and t.slept == [5]
    assert not [e for e in rig.events if e.kind == "online"]


# ---------------------------------------------------------------- giving up, and carrying on after

def test_when_the_connection_never_comes_back_it_gives_up_with_a_clear_error(rig):
    t = with_time(rig, cn.Patience(total_s=30, pauses_s=(10,), progress_s=60))
    rig.doors.pip_script = [(1, pip_text("connection_refused"))] * 20
    result = rig.build()
    assert not result.ok and result.error.code == "connection_lost"
    assert result.error.detail == "away for 0 minutes (exit 1)"
    assert t.slept == [10, 10, 10] and len(lock_runs(rig)) == 4
    assert rig.record()["state"] == "failed" and rig.record()["failed"]["code"] == "connection_lost"


def test_the_give_up_message_counts_whole_minutes(rig):
    with_time(rig, cn.Patience(total_s=600, pauses_s=(300,), progress_s=1000))
    rig.doors.pip_script = [(1, pip_text("connection_refused"))] * 20
    assert rig.build().error.detail == "away for 10 minutes (exit 1)"


def test_after_giving_up_the_same_build_carries_on_and_finishes_when_run_again(rig):
    with_time(rig, cn.Patience(total_s=30, pauses_s=(10,), progress_s=60))
    rig.doors.pip_script = [(1, pip_text("connection_refused"))] * 4
    assert not rig.build().ok
    again = rig.build()
    assert again.ok and rig.record()["state"] == "ready" and "failed" not in rig.record()
    assert len(lock_runs(rig)) == 5


def test_ctrl_c_while_waiting_stops_cleanly_and_the_next_run_carries_on(rig):
    def interrupted(seconds):
        raise KeyboardInterrupt

    rig.ctx = dataclasses.replace(rig.ctx, sleep=interrupted, monotonic=FakeTime().monotonic)
    rig.doors.pip_script = [(1, pip_text("connection_refused"))]
    with pytest.raises(KeyboardInterrupt):
        rig.build()
    assert not Path(rig.env_dir, eb.BUILD_LOCK_NAME).exists()                 # nobody is left holding the build
    with_time(rig)
    assert rig.build().ok


def test_the_agreement_is_still_checked_on_every_try(rig):
    t = with_time(rig)
    rig.ctx = dataclasses.replace(rig.ctx, consent=None)
    result = rig.build()
    assert not result.ok and result.error.code == "consent" and t.slept == []
