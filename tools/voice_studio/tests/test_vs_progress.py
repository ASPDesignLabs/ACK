# SPDX-License-Identifier: GPL-3.0-or-later
"""Recording progress and the next step (plan task VS-3.7): the decisions at their exact edges, and against the dataset builder's real preview."""
import contextlib
import io
import json
import shutil
import sys
import wave
from pathlib import Path

import pytest

from voice_studio.core import diskbudget as db
from voice_studio.core import joblines as jl
from voice_studio.core import progress as pg
from voice_studio.core.text import load_catalog

TESTS = Path(__file__).resolve().parents[2] / "freeform_studio" / "tests"
GIB = db.GIB


def summary(result="dry_run", minutes=12.0, pieces=10, takes=2, skipped=(), left_out=3, reasons=None, flags=None):
    reasons = {"too short (0.4s)": 2, "you dropped it": 1} if reasons is None else reasons
    flags = {} if flags is None else flags
    line = json.dumps({"result": result, "out": "/s/ds", "takes": takes, "pieces_considered": pieces + left_out, "skipped_takes": [list(s) for s in skipped],
                       "included": {"pieces": pieces, "minutes": minutes, "shortest": 1.0, "median": 4.0, "longest": 9.0}, "merged": 0,
                       "left_out": {"pieces": left_out, "by_reason": reasons, "by_flag": flags}, "warnings": [], "problems": []})
    return jl.dataset_summary([line])


def assess(planned=1.0, **kw):
    free = kw.pop("free", None)
    custom = kw.pop("custom_scratch", False)
    return pg.assess(summary(**kw), planned, free=free, custom_scratch=custom)


# ---------------------------------------------------------------- how far along

def test_the_target_is_the_planned_hours_as_minutes_and_reaching_it_exactly_counts():
    below, at, above = assess(2.0, minutes=119.99), assess(2.0, minutes=120.0), assess(2.0, minutes=500.0)
    assert (below.target_minutes, at.target_minutes) == (120.0, 120.0)
    assert below.fraction < 1.0 and at.fraction == 1.0 and above.fraction == 1.0, "never above one"
    assert below.next_step == "record_more" and at.next_step != "record_more" and above.next_step != "record_more"
    assert assess(1.0, minutes=15.0).fraction == 0.25


def test_no_planned_time_is_no_target_not_a_crash():
    p = assess(0.0, minutes=5.0)
    assert (p.target_minutes, p.fraction) == (0.0, 0.0) and p.next_step != "record_more"
    assert assess(-1.0, minutes=5.0).target_minutes == 0.0


def test_pieces_count_is_what_decides_whether_there_are_any_minutes():
    assert assess(minutes=9.0, pieces=0, takes=1).minutes == 0.0
    assert assess(minutes=9.0, pieces=1).minutes == 9.0


# ---------------------------------------------------------------- the recordings that are not finished

def test_recordings_not_finished_are_grouped_by_what_is_happening_to_them():
    s = summary(skipped=[("a", "finishing"), ("b", "queued"), ("c", "transcribing"), ("d", "error"), ("e", "error"), ("f", "recording"), ("g", "importing"), ("h", "unreadable")])
    assert pg.takes_by_state(s) == (3, 2, 3)
    assert pg.takes_by_state(summary()) == (0, 0, 0)


def test_the_list_of_waiting_statuses_is_the_processors_own():
    pytest.importorskip("numpy")
    sys.path.insert(0, str(TESTS.parent.parent))
    from freeform_studio import process
    assert tuple(pg.WAITING_STATUSES) == tuple(process.WAITING), "a recording the processor will still work on is one that is waiting"


# ---------------------------------------------------------------- the next step

REVIEW_KINDS = [("flagged", 1), ("not_approved", 2), ("tagged", 1), ("cuts_word", 3)]


def step(takes=2, waiting=0, minutes=60.0, target=60.0, reasons=()):
    return pg.next_step(takes, waiting, minutes, target, tuple(reasons))


def test_the_next_step_follows_a_fixed_order():
    assert step(takes=0, waiting=0, minutes=0.0) == "record_first"
    assert step(takes=0, waiting=3, minutes=0.0, reasons=REVIEW_KINDS) == "record_first", "nothing recorded beats everything"
    assert step(waiting=1, minutes=1.0) == "finish_recordings", "an unfinished count would mislead, so finish first"
    assert step(waiting=1, minutes=100.0, reasons=REVIEW_KINDS) == "finish_recordings"
    assert step(minutes=59.99, reasons=REVIEW_KINDS) == "record_more", "short of the target beats looking over"
    assert step(minutes=60.0, reasons=REVIEW_KINDS) == "review"
    assert step(minutes=60.0, reasons=[("dropped", 5), ("too_short", 2), ("no_text", 1), ("already_in", 1), ("other", 1)]) == "build_training_set"
    assert step(minutes=60.0) == "build_training_set"


@pytest.mark.parametrize("kind", ["flagged", "not_approved", "tagged", "cuts_word"])
def test_each_reason_a_person_can_clear_by_looking_asks_for_a_review(kind):
    assert step(reasons=[(kind, 1)]) == "review"
    assert step(reasons=[(kind, 0)]) == "build_training_set"


def test_every_reviewable_kind_is_a_kind_the_dataset_reader_can_give():
    assert set(pg.REVIEWABLE) <= set(jl.REASON_KINDS)
    assert set(pg.NEXT_STEPS) == {"record_first", "finish_recordings", "record_more", "review", "build_training_set"}


def test_assess_gives_the_whole_picture_from_the_preview():
    p = assess(1.0, minutes=30.0, pieces=20, takes=4, skipped=[("a", "queued")], left_out=5, reasons={"flagged: x": 3, "you dropped it": 2}, flags={"clipped": 3})
    assert (p.minutes, p.pieces, p.takes, p.takes_waiting, p.takes_failed, p.takes_other, p.left_out) == (30.0, 20, 4, 1, 0, 0, 5)
    assert p.reasons == (("flagged", 3), ("dropped", 2)) and p.flags == (("clipped", 3),)
    assert p.advice == "comfortable" and p.next_step == "finish_recordings" and p.disk is None


@pytest.mark.parametrize("result, expected", [("dry_run", True), ("built", True), ("nothing_qualified", True), ("no_takes_folder", True), ("problems", False), ("refused_existing", False)])
def test_only_a_preview_about_numbers_gives_a_picture(result, expected):
    assert (pg.assess(summary(result=result), 1.0) is not None) is expected


def test_a_project_with_nothing_yet_starts_at_the_beginning():
    nothing = pg.assess(jl.dataset_summary([json.dumps({"result": "no_takes_folder", "out": "/s/takes"})]), 1.0)
    assert nothing.takes == 0 and nothing.minutes == 0.0 and nothing.next_step == "record_first" and nothing.advice is None
    only_short = assess(1.0, result="nothing_qualified", minutes=0.0, pieces=0, takes=2, left_out=4, reasons={"too short (0.2s)": 4})
    assert only_short.next_step == "record_more" and only_short.minutes == 0.0


def test_the_advice_is_the_dataset_readers_own():
    for minutes, expected in ((0.5, "short"), (9.99, "short"), (10.0, None), (29.99, None), (30.0, "comfortable")):
        assert assess(minutes=minutes).advice == expected == jl.advice_for(minutes, 10)
    assert jl.advice_for(5.0, 0) is None and assess(minutes=5.0, pieces=0).advice is None


# ---------------------------------------------------------------- the room that is left

TABLE = db.DEFAULT_TABLE


def test_what_the_plan_has_yet_to_write_is_the_recordings_still_to_come_and_everything_else_in_full():
    full = {l.key: l.bytes for l in db.person_lines(TABLE, 2.0)}
    rest = {l.key: l.bytes for l in pg.rest_of_plan(TABLE, 2.0, 30.0)}
    assert rest["person.recordings"] == int(1.5 * TABLE.recording_per_hour)
    assert {k: v for k, v in rest.items() if k != "person.recordings"} == {k: v for k, v in full.items() if k != "person.recordings"}
    assert pg.rest_of_plan(TABLE, 2.0, 120.0)[0].bytes == 0 and pg.rest_of_plan(TABLE, 2.0, 500.0)[0].bytes == 0, "recording past the plan owes nothing more"
    assert pg.rest_of_plan(TABLE, 2.0, 0.0)[0].bytes == int(2.0 * TABLE.recording_per_hour)


def one_drive_need(hours, done):
    return sum(l.bytes for l in pg.rest_of_plan(TABLE, hours, done))


def test_the_room_is_judged_at_the_exact_edges_the_disk_rules_use():
    need = one_drive_need(2.0, 30.0)
    floors = db.floors_for(TABLE, holds_recordings=True)
    def level(free):
        return pg.disk_note(TABLE, 2.0, 30.0, False, {"project": free}).level
    assert level(need + floors.low) is db.Level.ENOUGH
    assert level(need + floors.low - 1) is db.Level.TIGHT
    assert level(need + floors.stop) is db.Level.TIGHT
    assert level(need + floors.stop - 1) is db.Level.NOT_ENOUGH
    note = pg.disk_note(TABLE, 2.0, 30.0, False, {"project": need + floors.low})
    assert note.need == {"project": need} and note.short_by == {"project": 0}
    assert pg.disk_note(TABLE, 2.0, 30.0, False, {"project": need + floors.low - 1}).short_by == {"project": 1}
    assert pg.disk_note(TABLE, 2.0, 30.0, False, {"project": need + floors.low - 5 * GIB}).short_by == {"project": 5 * GIB}


def test_a_drive_that_cannot_be_read_is_not_judged():
    note = pg.disk_note(TABLE, 2.0, 30.0, False, {"project": None})
    assert note.level is db.Level.ENOUGH and note.short_by == {"project": 0} and note.free == {"project": None}
    assert pg.disk_note(TABLE, 2.0, 30.0, False, {}).level is db.Level.ENOUGH


def test_with_a_scratch_drive_each_drive_is_judged_by_what_lands_on_it_and_the_worst_decides():
    lines = pg.rest_of_plan(TABLE, 2.0, 30.0)
    project = sum(l.bytes for l in lines if l.role in (db.Role.PROJECT, db.Role.BACKUP))
    scratch = sum(l.bytes for l in lines if l.role is db.Role.SCRATCH)
    p_floors, s_floors = db.floors_for(TABLE, True), db.floors_for(TABLE, False)
    roomy = {"project": project + p_floors.low, "scratch": scratch + s_floors.low}
    assert pg.disk_note(TABLE, 2.0, 30.0, True, roomy).level is db.Level.ENOUGH
    assert pg.disk_note(TABLE, 2.0, 30.0, True, dict(roomy, scratch=scratch + s_floors.low - 1)).level is db.Level.TIGHT
    worst = pg.disk_note(TABLE, 2.0, 30.0, True, dict(roomy, project=project + p_floors.stop - 1, scratch=scratch + s_floors.low - 1))
    assert worst.level is db.Level.NOT_ENOUGH and worst.short_by["scratch"] == 1 and worst.need == {"project": project, "scratch": scratch}
    assert set(pg.disk_note(TABLE, 2.0, 30.0, False, {"project": 10 ** 12}).need) == {"project"}, "without a scratch drive everything is on the project's"


def test_the_picture_carries_the_room_only_when_it_was_asked_for():
    asked = assess(2.0, minutes=30.0, free={"project": 10 ** 13})
    assert asked.disk.level is db.Level.ENOUGH
    short = assess(2.0, minutes=30.0, free={"project": 1})
    assert short.disk.level is db.Level.NOT_ENOUGH and assess(2.0, minutes=30.0).disk is None


# ---------------------------------------------------------------- the words

CAT = load_catalog("en")


def test_minutes_read_the_way_a_person_says_them():
    assert [pg.minutes_text(m) for m in (0.0, 0.04, 2.5, 7.0, 9.96, 10.0, 10.49, 10.5, 11.5, 59.4, 60.0, 120.0)] == ["0", "0", "2.5", "7", "10", "10", "10", "11", "12", "59", "60", "120"]


def test_the_sentences_come_in_a_steady_order_and_say_only_what_is_true():
    p = assess(1.0, minutes=7.5, skipped=[("a", "queued"), ("b", "error"), ("c", "error"), ("d", "recording")], free={"project": 10 ** 13})
    out = pg.lines(p, CAT)
    assert out[0] == "About 7.5 of 60 minutes of speech you can use so far."
    assert out[1] == "1 recording is still being listened to." and out[2] == "2 recordings could not be finished. Look at them on the Review page."
    assert out[3] == "1 recording is still being made or brought in."
    assert out[4] == CAT.t("dataset.advice.short") and out[5] == CAT.t("progress.next.finish_recordings") and len(out) == 6
    plain = pg.lines(assess(1.0, minutes=20.0, free={"project": 10 ** 13}), CAT)
    assert plain == ("About 20 of 60 minutes of speech you can use so far.", CAT.t("progress.next.record_more")), "nothing is said about what is fine"


def test_a_short_room_is_said_in_the_disk_rules_own_words():
    tight = assess(2.0, minutes=30.0, free={"project": one_drive_need(2.0, 30.0) + db.floors_for(TABLE, True).low - 1})
    gone = assess(2.0, minutes=30.0, free={"project": 1})
    assert CAT.t("budget.level.tight") in pg.lines(tight, CAT) and CAT.t("budget.level.not_enough") in pg.lines(gone, CAT)
    assert CAT.t("budget.level.enough") not in pg.lines(assess(2.0, minutes=30.0, free={"project": 10 ** 13}), CAT)


def test_every_next_step_has_a_sentence_and_none_is_left_over():
    for name in pg.NEXT_STEPS:
        assert CAT.t("progress.next." + name) != "progress.next." + name


# ---------------------------------------------------------------- against the dataset builder's real preview

def test_the_real_dataset_preview_gives_the_right_picture(tmp_path):
    pytest.importorskip("numpy")
    if shutil.which("ffmpeg") is None:
        pytest.skip("ffmpeg is not installed")
    sys.path.insert(0, str(TESTS))
    sys.path.insert(0, str(TESTS.parent.parent))
    from test_vs_joblines import write_tone
    from freeform_studio import build_dataset as bd
    out_dir = tmp_path / "output"
    take = out_dir / "_freeform" / "en-US" / "takes" / "t20260930-000001-aaaa"
    take.mkdir(parents=True)
    write_tone(take / "audio.wav", 30.0)
    seg = lambda i, a, b, **kw: {"id": "s%03d" % i, "start": a, "end": b, "text": kw.pop("text", "hello there."), "words": [], "status": kw.pop("status", "pending"),
                                 "tags": [], "note": "", "flags": kw.pop("flags", []), "auto": None}
    (take / "take.json").write_text(json.dumps({"id": "t20260930-000001-aaaa", "status": "ready", "duration": 30.0}))
    (take / "edit.json").write_text(json.dumps({"schema": 1, "rev": 1, "segments": [seg(1, 0, 3), seg(2, 3, 6), seg(3, 6, 9, flags=["low_confidence"]), seg(4, 9, 9.4)]}))
    waiting = out_dir / "_freeform" / "en-US" / "takes" / "t20260930-000002-bbbb"
    waiting.mkdir()
    (waiting / "take.json").write_text(json.dumps({"id": "t20260930-000002-bbbb", "status": "transcribing"}))
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        code = bd.main(["--output", str(out_dir), "--out", str(tmp_path / "ds"), "--dry-run", "--json"])
    found = jl.dataset_summary(buffer.getvalue().splitlines())
    p = pg.assess(found, 0.5)
    assert code == 0 and p.pieces == 2 and p.takes == 2 and p.takes_waiting == 1
    assert abs(p.minutes - 0.1) < 0.01 and p.target_minutes == 30.0 and p.next_step == "finish_recordings" and p.advice == "short"
    assert dict(p.reasons) == {"flagged": 1, "too_short": 1} and p.flags == (("low_confidence", 1),)
    assert not (tmp_path / "ds").exists(), "a preview writes nothing"
