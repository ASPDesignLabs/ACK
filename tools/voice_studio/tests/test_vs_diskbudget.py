# SPDX-License-Identifier: GPL-3.0-or-later
"""The disk budget (plan task VS-1.10): the estimate, the three answers at their exact edges, the floors, and what may be freed."""
from dataclasses import replace

import pytest

from voice_studio.core import diskbudget as db
from voice_studio.core.diskbudget import (GIB, MIB, CleanupItem, DriveMap, Kind, Level, Line, Role, SizeTable, Watch)

# A small table of round numbers, so the arithmetic in the tests can be done by hand.
T = SizeTable(tool_environments=1000, tool_download_cache=100, recording_per_hour=100, dataset_per_hour=40, training_cache_per_hour=60,
              checkpoint=10, checkpoints_per_round=3, rounds=4, margin=50,
              bases={k: "measured" for k in ("tool_environments", "tool_download_cache", "recording_per_hour", "dataset_per_hour",
                                              "training_cache_per_hour", "checkpoint", "checkpoints_per_round", "rounds", "margin")})
VOICES = [("voice-mike", 200), ("voice-amy", 200)]
DOWNLOADS = VOICES + [("speech-model-small-en", 80)]
ONE = DriveMap()                                   # everything on one drive


def total(lines):
    return sum(l.bytes for l in lines)


# ---------------------------------------------------------------- the estimate

def test_one_persons_lines_by_hand():
    lines = {l.key: l for l in db.person_lines(T, hours=2, rounds=4)}
    assert lines["person.recordings"].bytes == 200 and lines["person.recordings"].kind is Kind.PRECIOUS and lines["person.recordings"].role is Role.PROJECT
    assert lines["person.dataset"].bytes == 80 and lines["person.cache"].bytes == 120                    # 2 h x 40, 2 h x 60
    assert lines["person.checkpoints_kept"].bytes == 20 and lines["person.checkpoints_kept"].role is Role.PROJECT      # the two protected ones
    assert lines["person.checkpoints_older"].bytes == (4 * 3 - 2) * 10 and lines["person.checkpoints_older"].kind is Kind.DISPOSABLE
    assert lines["person.backup_copy"].bytes == 200 + 20 and lines["person.backup_copy"].role is Role.BACKUP
    assert lines["person.dataset"].kind is Kind.REBUILDABLE and lines["person.dataset"].role is Role.SCRATCH


def test_a_plan_shorter_than_the_smallest_is_treated_as_the_smallest():
    assert total(db.person_lines(T, hours=0)) == total(db.person_lines(T, hours=db.MIN_PLAN_HOURS))
    assert total(db.person_lines(T, hours=-3)) == total(db.person_lines(T, hours=db.MIN_PLAN_HOURS))


def test_fewer_checkpoints_than_the_protected_pair_never_makes_a_negative_line():
    assert {l.key: l.bytes for l in db.person_lines(T, 1, rounds=0)}["person.checkpoints_older"] == 0
    assert {l.key: l.bytes for l in db.person_lines(T, 1, rounds=1)}["person.checkpoints_older"] == (3 - 2) * 10


def test_the_start_estimate_counts_the_tool_every_download_and_every_person():
    lines = db.start_lines(T, DOWNLOADS, people=2, hours=1)
    keys = [l.key for l in lines]
    assert keys[:2] == ["tool.environments", "tool.download_cache"] and "download.voice-mike" in keys and "download.voice-amy" in keys
    assert keys.count("person.recordings") == 2
    assert total(lines) == 1000 + 100 + 480 + 2 * total(db.person_lines(T, 1))


def test_needs_are_summed_per_drive_with_the_margin_on_each_drive_in_use():
    lines = db.start_lines(T, DOWNLOADS, people=2, hours=1)
    single = db.need_by_drive(lines, ONE, T.margin)
    assert single == {"home": total(lines) + 50}
    split = db.need_by_drive(lines, DriveMap(tool="a", project="a", scratch="b", backup="c"), T.margin)
    assert set(split) == {"a", "b", "c"} and sum(split.values()) == total(lines) + 3 * 50
    scratch = sum(l.bytes for l in lines if l.role is Role.SCRATCH)
    assert split["b"] == scratch + 50


def test_a_drive_nothing_lands_on_gets_no_margin():
    assert db.need_by_drive([Line("x", Role.TOOL, Kind.TOOL, 0)], ONE, 50) == {}
    assert db.need_by_drive([], ONE, 50) == {}


def test_the_default_table_says_where_every_number_came_from_and_that_it_is_rough():
    assert set(db.DEFAULT_TABLE.bases) == {f for f in db.DEFAULT_TABLE.__dataclass_fields__ if f != "bases"}
    assert not db.DEFAULT_TABLE.all_measured and set(db.DEFAULT_TABLE.bases.values()) <= {"measured", "listing", "freeform", "computed", "guess"}
    assert db.DEFAULT_TABLE.dataset_per_hour == 158_760_000 and db.DEFAULT_TABLE.checkpoint == 846_000_000
    assert db.DEFAULT_TABLE.recording_per_hour == 400 * MIB


def test_the_recording_figure_is_freeform_studios_own():
    try:
        from freeform_studio import health
    except Exception:                      # Freeform Studio's dependencies are not installed here
        pytest.skip("freeform_studio not importable")
    assert health.HOUR_MB * health.MB == db.DEFAULT_TABLE.recording_per_hour


def test_the_recorders_floor_is_freeform_studios_own():
    try:
        from freeform_studio.config import Config
    except Exception:
        pytest.skip("freeform_studio not importable")
    assert Config.__dataclass_fields__["min_free_mb"].default * MIB == db.RECORDER_FLOOR


# ---------------------------------------------------------------- the three answers

def verdict(free, *, downloads=DOWNLOADS, hours=1, drives=ONE, people=2):
    return db.judge_start(T, downloads, hours, drives, free, people)


def needs():
    full = db.need_by_drive(db.start_lines(T, DOWNLOADS, 2, 1), ONE, T.margin)["home"]
    one = db.need_by_drive(db.start_lines(T, DOWNLOADS, 1, 1), ONE, T.margin)["home"]
    voices = [d for d in DOWNLOADS if d[0].startswith("voice-")]
    keep = [d for d in DOWNLOADS if not d[0].startswith("voice-")] + [min(voices, key=lambda d: d[1])]
    minimum = db.need_by_drive(db.start_lines(T, keep, 1, db.MIN_PLAN_HOURS, rounds=1), ONE, T.margin)["home"]
    return full, one, minimum


def test_the_three_needs_are_ordered_and_distinct():
    full, one, minimum = needs()
    assert minimum < one < full


@pytest.mark.parametrize("delta, level", [(0, Level.ENOUGH), (1, Level.ENOUGH), (-1, Level.TIGHT)])
def test_exactly_enough_is_enough_and_one_byte_less_is_tight(delta, level):
    full, _, _ = needs()
    assert verdict({"home": full + delta}).level is level


@pytest.mark.parametrize("delta, level", [(0, Level.TIGHT), (-1, Level.TIGHT)])
def test_between_the_smallest_plan_and_one_person_is_still_tight_and_offers_to_drop_a_voice(delta, level):
    _, one, minimum = needs()
    v = verdict({"home": minimum + delta})
    if delta == 0:
        assert v.level is Level.TIGHT and v.suggest_drop_voice
    full, one, minimum = needs()
    assert verdict({"home": one}).level is Level.TIGHT and not verdict({"home": one}).suggest_drop_voice


def test_one_byte_under_the_smallest_possible_plan_is_not_enough():
    _, _, minimum = needs()
    assert verdict({"home": minimum}).level is Level.TIGHT
    assert verdict({"home": minimum - 1}).level is Level.NOT_ENOUGH


def test_the_shortfall_is_reported_per_drive():
    full, _, _ = needs()
    assert verdict({"home": full - 123}).short_by == {"home": 123}
    assert verdict({"home": full + 5}).short_by == {"home": 0}


def test_people_is_never_fewer_than_two_at_start():
    full, _, _ = needs()
    assert verdict({"home": full}, people=1).level is Level.ENOUGH
    assert verdict({"home": full - 1}, people=1).level is Level.TIGHT          # still judged for two
    bigger = verdict({"home": full}, people=3)
    assert bigger.level is Level.TIGHT and bigger.need["home"] > full


def test_a_single_voice_has_nothing_to_drop():
    one_voice = [("voice-mike", 200), ("speech-model-small-en", 80)]
    minimum = db.need_by_drive(db.start_lines(T, one_voice, 1, db.MIN_PLAN_HOURS, rounds=1), ONE, T.margin)["home"]
    v = db.judge_start(T, one_voice, 1, ONE, {"home": minimum}, 2)
    assert v.level is Level.TIGHT and not v.suggest_drop_voice


def test_declining_a_voice_gives_a_smaller_number():
    assert verdict({"home": 10**9}, downloads=[VOICES[0], DOWNLOADS[2]]).need["home"] < verdict({"home": 10**9}).need["home"]


def test_a_drive_that_cannot_be_read_is_not_judged_and_is_named():
    split = DriveMap(tool="a", project="a", scratch="b", backup="a")
    full = db.need_by_drive(db.start_lines(T, DOWNLOADS, 2, 1), split, T.margin)
    v = db.judge_start(T, DOWNLOADS, 1, split, {"a": full["a"], "b": None}, 2)
    assert v.level is Level.ENOUGH and v.unknown_drives == ("b",)
    assert db.judge_start(T, DOWNLOADS, 1, split, {"a": full["a"]}, 2).unknown_drives == ("b",)


def test_the_worst_drive_decides_when_scratch_is_on_another_drive():
    split = DriveMap(tool="a", project="a", scratch="b", backup="a")
    full = db.need_by_drive(db.start_lines(T, DOWNLOADS, 2, 1), split, T.margin)
    assert db.judge_start(T, DOWNLOADS, 1, split, {"a": full["a"], "b": full["b"]}, 2).level is Level.ENOUGH
    assert db.judge_start(T, DOWNLOADS, 1, split, {"a": full["a"] - 1, "b": full["b"]}, 2).level is Level.TIGHT
    assert db.judge_start(T, DOWNLOADS, 1, split, {"a": full["a"], "b": 0}, 2).level is Level.NOT_ENOUGH
    # an enormous project drive does not rescue a scratch drive that is too small
    assert db.judge_start(T, DOWNLOADS, 1, split, {"a": 10**12, "b": 0}, 2).level is Level.NOT_ENOUGH


def test_the_verdict_says_when_the_numbers_are_rough():
    assert not verdict({"home": 10**9}).rough
    assert db.judge_start(db.DEFAULT_TABLE, DOWNLOADS, 1, ONE, {"home": 10**13}).rough


def test_the_real_default_table_needs_a_believable_amount_for_two_people_and_both_voices():
    voices = [("voice-mike", 846_000_000), ("voice-amy", 846_000_000), ("speech-model-small-en", 480_000_000)]
    v = db.judge_start(db.DEFAULT_TABLE, voices, 1.0, ONE, {"home": 10**13})
    assert v.level is Level.ENOUGH and 20 * GIB < v.need["home"] < 80 * GIB, v.need


# ---------------------------------------------------------------- floors and watching

def test_training_stops_strictly_above_the_recorders_floor_and_the_floors_are_ordered():
    f = db.floors_for(T, holds_recordings=True)
    assert f.recorder == db.RECORDER_FLOOR and f.recorder < f.stop < f.low
    assert f.stop >= f.recorder + T.checkpoint, "a stop must still have room to write one checkpoint"
    g = db.floors_for(T, holds_recordings=False)
    assert g.recorder == 0 and 0 < g.stop < g.low and g.stop == T.checkpoint + db.STOP_SLACK


def test_the_real_floors_keep_the_recorders_500_mb_clear():
    f = db.floors_for(db.DEFAULT_TABLE, True)
    assert f.stop > db.RECORDER_FLOOR + db.DEFAULT_TABLE.checkpoint


@pytest.mark.parametrize("offset, expected", [(-1, Watch.STOP), (0, Watch.LOW), (1, Watch.LOW)])
def test_watch_at_the_stop_floor(offset, expected):
    f = db.floors_for(T, True)
    assert db.watch(f.stop + offset, f) is expected


@pytest.mark.parametrize("offset, expected", [(-1, Watch.LOW), (0, Watch.FINE), (1, Watch.FINE)])
def test_watch_at_the_low_floor(offset, expected):
    f = db.floors_for(T, True)
    assert db.watch(f.low + offset, f) is expected


def test_a_drive_that_reports_nothing_never_stops_a_job_on_a_guess():
    assert db.watch(None, db.floors_for(T, True)) is Watch.FINE and db.watch(0, db.floors_for(T, True)) is Watch.STOP


@pytest.mark.parametrize("left, expected", [(0, Level.ENOUGH), (-1, Level.TIGHT)])
def test_a_step_needs_the_low_floor_left_over_to_be_comfortable(left, expected):
    f = db.floors_for(T, True)
    need = 1000
    assert db.check_step(need + f.low + left, need, f) is expected


@pytest.mark.parametrize("left, expected", [(0, Level.TIGHT), (-1, Level.NOT_ENOUGH)])
def test_a_step_is_refused_if_it_would_leave_less_than_the_stop_floor(left, expected):
    f = db.floors_for(T, True)
    need = 1000
    assert db.check_step(need + f.stop + left, need, f) is expected


def test_a_step_on_a_drive_that_reports_nothing_goes_ahead():
    assert db.check_step(None, 10**9, db.floors_for(T, True)) is Level.ENOUGH


# ---------------------------------------------------------------- what may be freed

def test_protected_rounds_are_the_chosen_one_and_the_one_before_it():
    assert db.protected_rounds(5, chosen=3) == {3, 2}
    assert db.protected_rounds(5, chosen=None) == {5, 4}
    assert db.protected_rounds(5, chosen=1) == {1}                     # nothing before round 1
    assert db.protected_rounds(1, chosen=None) == {1}
    assert db.protected_rounds(0, chosen=None) == frozenset()


def test_older_checkpoints_are_disposable_and_the_protected_ones_are_precious():
    items = {n: db.checkpoint_item(n, 10, rounds_done=5, chosen=3) for n in range(1, 6)}
    assert [n for n, i in items.items() if i.protected] == [2, 3]
    assert all(items[n].kind is Kind.DISPOSABLE for n in (1, 4, 5)) and all(items[n].kind is Kind.PRECIOUS for n in (2, 3))


def test_only_disposable_and_rebuildable_unprotected_items_are_ever_listed():
    items = [CleanupItem("recordings", Kind.PRECIOUS, 999), CleanupItem("tool", Kind.TOOL, 999), CleanupItem("kept", Kind.DISPOSABLE, 999, protected=True),
             CleanupItem("empty", Kind.DISPOSABLE, 0), CleanupItem("cache", Kind.REBUILDABLE, 50), CleanupItem("old", Kind.DISPOSABLE, 10),
             CleanupItem("listen", Kind.DISPOSABLE, 30)]
    assert [i.key for i in db.reclaimable(items)] == ["listen", "old", "cache"]       # disposable first, larger first, then rebuildable


def test_a_precious_item_cannot_be_listed_even_if_it_is_not_marked_protected():
    assert db.reclaimable([CleanupItem("recordings", Kind.PRECIOUS, 10**9, protected=False)]) == []


def test_picking_takes_the_fewest_in_order_and_says_whether_it_is_enough():
    items = [CleanupItem("a", Kind.DISPOSABLE, 40), CleanupItem("b", Kind.DISPOSABLE, 30), CleanupItem("c", Kind.REBUILDABLE, 100)]
    picked, enough = db.pick_to_free(items, 60)
    assert [i.key for i in picked] == ["a", "b"] and enough
    picked, enough = db.pick_to_free(items, 70)
    assert [i.key for i in picked] == ["a", "b"] and enough
    picked, enough = db.pick_to_free(items, 71)
    assert [i.key for i in picked] == ["a", "b", "c"] and enough
    picked, enough = db.pick_to_free(items, 171)
    assert len(picked) == 3 and not enough
    assert db.pick_to_free(items, 0) == ([], True)


# ---------------------------------------------------------------- showing a size

@pytest.mark.parametrize("n, expected", [(0, ("0", "B")), (512, ("512", "B")), (999, ("999", "B")), (1000, ("1.0", "KB")), (846_000_000, ("846", "MB")),
                                         (1_692_000_000, ("1.7", "GB")), (9_949_999_999, ("9.9", "GB")), (9_950_000_000, ("10", "GB")),
                                         (999_499_999, ("999", "MB")), (999_500_000, ("1.0", "GB")), (999_999, ("1.0", "MB")), (-5, ("0", "B")),
                                         (10**15, ("1000", "TB"))])
def test_sizes_are_shown_in_decimal_units_with_latin_digits(n, expected):
    assert db.size_parts(n) == expected
