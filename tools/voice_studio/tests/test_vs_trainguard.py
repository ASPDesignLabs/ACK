# SPDX-License-Identifier: GPL-3.0-or-later
"""Automatic settings and guards for a round (plan task VS-4.3): the batch size for a card, how often to save a check, whether the card and the disks have room."""
import pytest

from vs_fakes import FakeSystem, SMI_4060_MEMORY
from voice_studio.core import trainguard as tg
from voice_studio.core.diskbudget import DEFAULT_TABLE, MIB, DriveMap, Level, floors_for
from voice_studio.core.system import CommandResult


# ---------------------------------------------------------------- the batch size

@pytest.mark.parametrize("memory, batch, basis", [
    (24576, 12, "measured"), (8188, 12, "measured"), (8000, 12, "measured"), (7999, 8, "guess"), (6144, 8, "guess"), (6000, 8, "guess"), (5999, 4, "guess"),
    (4000, 4, "guess"), (3999, None, "too_small"), (2048, None, "too_small"), (0, None, "too_small"), (None, 12, "unknown"),
])
def test_the_batch_follows_the_cards_memory_and_says_how_sure_it_is(memory, batch, basis):
    assert tg.batch_for(memory) == tg.BatchChoice(batch, basis)


def test_the_measured_row_is_the_one_batch_that_was_run_on_a_real_card():
    assert [row for row in tg.BATCH_TABLE if row[2] == "measured"] == [(8000, 12, "measured")] and tg.MIN_GPU_MIB == 4000


# ---------------------------------------------------------------- how often to save a check

@pytest.mark.parametrize("clips, batch, steps", [(23, 12, 1), (24, 12, 2), (35, 12, 2), (36, 12, 3), (0, 12, 1), (5, 12, 1), (800, 12, 66), (800, 8, 100), (10, 0, 10)])
def test_the_trainer_drops_a_last_short_batch_so_a_set_gives_this_many_steps_an_epoch(clips, batch, steps):
    assert tg.steps_per_epoch(clips, batch) == steps


@pytest.mark.parametrize("clips, batch, every", [
    (23, 12, 10),         # one step an epoch, about half a second: checking every 10 epochs is a check every few seconds
    (276, 12, 10), (288, 12, 10),      # 23 and 24 steps: 119.6 s and 124.8 s... the target is two minutes, so 10 epochs is already about right
    (300, 12, 9), (800, 12, 3), (1500, 12, 2), (3000, 12, 1), (100000, 12, 1),
    (800, 8, 3), (800, 4, 3),
])
def test_a_small_set_checks_every_ten_epochs_as_before_and_a_real_one_checks_about_every_two_minutes(clips, batch, every):
    assert tg.check_every(clips, batch) == every


def test_the_interval_never_goes_below_one_or_above_ten_and_a_round_never_loses_much_more_than_the_target():
    for clips in range(0, 6000, 7):
        for batch in (4, 8, 12):
            every = tg.check_every(clips, batch)
            assert 1 <= every <= tg.MAX_CHECK_EVERY
            one_epoch = tg.lost_seconds(clips, batch, 1)
            assert tg.lost_seconds(clips, batch, every) <= max(tg.CHECK_TARGET_S * 1.5, one_epoch), (clips, batch, every)


def test_what_the_measured_rounds_lost_matches_what_the_rule_says_it_costs():
    assert tg.lost_seconds(30, 12, 10) == pytest.approx(10.4)                   # F25: 7 to 9 epochs of 2 steps, some ten seconds
    assert tg.lost_seconds(800, 12, 3) == pytest.approx(102.96) and tg.lost_seconds(800, 12, 10) == pytest.approx(343.2)       # about six minutes if left at 10


# ---------------------------------------------------------------- the graphics card's room

@pytest.mark.parametrize("batch, need", [(12, 5760), (8, 4240), (4, 2720)])
def test_the_room_a_batch_needs_grows_with_the_batch(batch, need):
    assert tg.gpu_need_mib(batch) == need


@pytest.mark.parametrize("used, level, free", [
    (2100, Level.ENOUGH, 6088), (2428, Level.ENOUGH, 5760),          # exactly the need
    (2429, Level.TIGHT, 5759), (3004, Level.TIGHT, 5184),            # nine tenths of the need
    (3005, Level.NOT_ENOUGH, 5183), (8188, Level.NOT_ENOUGH, 0), (9000, Level.NOT_ENOUGH, 0), (0, Level.ENOUGH, 8188),
])
def test_the_card_has_room_at_the_need_a_warning_down_to_nine_tenths_and_none_below(used, level, free):
    room = tg.judge_gpu_room(8188, used, 12)
    assert (room.level, room.free_mib, room.need_mib) == (level, free, 5760)


def test_a_card_whose_use_cannot_be_read_is_not_judged():
    for total, used in ((None, 100), (8188, None), (None, None)):
        room = tg.judge_gpu_room(total, used, 12)
        assert (room.level, room.free_mib) == (Level.ENOUGH, None)


@pytest.mark.parametrize("text, expected", [
    ("NVIDIA GeForce RTX 4060, 1203, 8188\n", tg.GpuMemory(8188, 1203)),
    ("GT 1030, 100, 2048\nRTX 4060, 1203, 8188\n", tg.GpuMemory(8188, 1203)),             # the card with the most memory
    ("RTX 4060, 1203, 8188\nGT 1030, 100, 2048\n", tg.GpuMemory(8188, 1203)),
    ("NVIDIA, Inc. card, with commas, 7, 8000\n", tg.GpuMemory(8000, 7)),
    ("RTX, [N/A], 8188\n", None), ("RTX, 12, [N/A]\n", None), ("", None), ("\n\n", None), ("nonsense\n", None), ("a, b\n", None), ("RTX, -5, 8188\n", None),
    ("RTX, 1.5, 8188\n", None), ("RTX, 12, 8188\nbroken line\n", tg.GpuMemory(8188, 12)),
])
def test_the_memory_lines_the_driver_prints_are_read_strictly(text, expected):
    assert tg.parse_gpu_memory(text) == expected


def test_the_memory_is_asked_of_the_driver_and_only_asked():
    system = FakeSystem()
    assert tg.read_gpu_memory(system) == tg.GpuMemory(8188, 1203)
    assert system.ran[-1][1:] == ("--query-gpu=name,memory.used,memory.total", "--format=csv,noheader,nounits")


def test_no_driver_a_failing_driver_or_an_unreadable_answer_is_no_answer():
    assert tg.read_gpu_memory(FakeSystem(tools={})) is None
    assert tg.read_gpu_memory(FakeSystem(smi_memory=CommandResult(9, "NVIDIA-SMI has failed"))) is None
    assert tg.read_gpu_memory(FakeSystem(smi_memory=None)) is None
    assert tg.read_gpu_memory(FakeSystem(smi_memory=CommandResult(0, "garbage\n"))) is None
    wsl = FakeSystem(tools={}, present={"/usr/lib/wsl/lib/nvidia-smi"})
    assert tg.read_gpu_memory(wsl) == tg.GpuMemory(8188, 1203) and wsl.ran[-1][0] == "/usr/lib/wsl/lib/nvidia-smi"


# ---------------------------------------------------------------- the disk a round writes

def test_an_hour_of_speech_is_the_size_the_plan_says_it_is():
    assert tg.hours_of_speech(158_760_000) == pytest.approx(1.0) and tg.hours_of_speech(0) == 0 and tg.hours_of_speech(-5) == 0
    assert tg.hours_of_speech(79_380_000) == pytest.approx(0.5)


def test_one_round_writes_six_saved_files_to_the_project_and_a_working_folder_to_scratch():
    lines = {l.key: l for l in tg.round_lines(DEFAULT_TABLE, 2.0)}
    assert lines["round.checkpoints"].bytes == 6 * 846_000_000 and lines["round.checkpoints"].role.value == "project"
    assert lines["round.cache"].bytes == 2 * DEFAULT_TABLE.training_cache_per_hour and lines["round.cache"].role.value == "scratch"
    assert tg.round_lines(DEFAULT_TABLE, 0.1)[1].bytes == DEFAULT_TABLE.training_cache_per_hour // 2          # a set is never counted as smaller than half an hour


HOME = DriveMap(tool="project", project="project", scratch="project", backup="project")
SPLIT = DriveMap(tool="project", project="project", scratch="scratch", backup="project")
FLOORS = floors_for(DEFAULT_TABLE, holds_recordings=True)
NEED = 6 * 846_000_000 + DEFAULT_TABLE.training_cache_per_hour          # one hour of speech


def test_a_round_has_room_if_what_is_left_afterwards_stays_above_the_low_floor():
    check = tg.judge_round_disk(DEFAULT_TABLE, 1.0, HOME, {"project": NEED + FLOORS.low})
    assert check.level is Level.ENOUGH and check.drives[0].need == NEED and check.drives[0].short_by == 0
    below = tg.judge_round_disk(DEFAULT_TABLE, 1.0, HOME, {"project": NEED + FLOORS.low - 1})
    assert below.level is Level.TIGHT and below.drives[0].short_by == 1


def test_a_round_that_would_leave_less_than_the_stop_floor_does_not_start():
    assert tg.judge_round_disk(DEFAULT_TABLE, 1.0, HOME, {"project": NEED + FLOORS.stop}).level is Level.TIGHT
    refused = tg.judge_round_disk(DEFAULT_TABLE, 1.0, HOME, {"project": NEED + FLOORS.stop - 1})
    assert refused.level is Level.NOT_ENOUGH and refused.drives[0].short_by == FLOORS.low - FLOORS.stop + 1
    assert tg.judge_round_disk(DEFAULT_TABLE, 1.0, HOME, {"project": 0}).level is Level.NOT_ENOUGH


def test_the_drive_that_holds_recordings_is_held_to_the_higher_floor():
    assert FLOORS.recorder > 0 and FLOORS.stop > floors_for(DEFAULT_TABLE, holds_recordings=False).stop
    scratch_floors = floors_for(DEFAULT_TABLE, holds_recordings=False)
    cache = int(DEFAULT_TABLE.training_cache_per_hour)
    ok = tg.judge_round_disk(DEFAULT_TABLE, 1.0, SPLIT, {"project": 6 * 846_000_000 + FLOORS.low, "scratch": cache + scratch_floors.low})
    assert ok.level is Level.ENOUGH and [d.drive for d in ok.drives] == ["project", "scratch"]
    only_scratch_short = tg.judge_round_disk(DEFAULT_TABLE, 1.0, SPLIT, {"project": 10 ** 12, "scratch": cache + scratch_floors.stop - 1})
    assert only_scratch_short.level is Level.NOT_ENOUGH and [d.level for d in only_scratch_short.drives] == [Level.ENOUGH, Level.NOT_ENOUGH]
    same_bytes_on_the_project_drive = tg.judge_round_disk(DEFAULT_TABLE, 1.0, SPLIT, {"project": 6 * 846_000_000 + scratch_floors.low, "scratch": 10 ** 12})
    assert same_bytes_on_the_project_drive.level is Level.TIGHT          # the same room is enough for scratch's lower floor and only a warning for the project drive's higher one


def test_the_worst_drive_decides_and_a_drive_that_cannot_be_read_is_not_judged():
    mixed = tg.judge_round_disk(DEFAULT_TABLE, 1.0, SPLIT, {"project": 0, "scratch": 10 ** 12})
    assert mixed.level is Level.NOT_ENOUGH
    unknown = tg.judge_round_disk(DEFAULT_TABLE, 1.0, SPLIT, {"project": None, "scratch": 10 ** 12})
    assert unknown.level is Level.ENOUGH and unknown.drives[0].free is None and unknown.drives[0].short_by == 0
    missing = tg.judge_round_disk(DEFAULT_TABLE, 1.0, HOME, {})
    assert missing.level is Level.ENOUGH and missing.drives[0].free is None


def test_a_longer_set_needs_more_room_for_its_working_folder():
    small = tg.judge_round_disk(DEFAULT_TABLE, 0.5, HOME, {"project": 0}).drives[0].need
    big = tg.judge_round_disk(DEFAULT_TABLE, 3.0, HOME, {"project": 0}).drives[0].need
    assert big - small == int(2.5 * DEFAULT_TABLE.training_cache_per_hour)


# ---------------------------------------------------------------- what a running round is watched against

def test_one_drive_is_watched_at_the_higher_floor_and_two_drives_each_at_their_own():
    assert tg.watches(DEFAULT_TABLE, "/p/rounds/run", "/p/scratch", HOME) == (("/p/rounds/run", FLOORS.stop),)
    two = tg.watches(DEFAULT_TABLE, "/p/rounds/run", "/usb/scratch", SPLIT)
    assert two == (("/p/rounds/run", FLOORS.stop), ("/usb/scratch", floors_for(DEFAULT_TABLE, holds_recordings=False).stop))
    assert two[1][1] < two[0][1] and two[0][1] > 500 * MIB


def test_what_a_failed_driver_printed_is_not_trusted_even_if_it_looks_like_numbers():
    assert tg.read_gpu_memory(FakeSystem(smi_memory=CommandResult(1, "NVIDIA GeForce RTX 4060, 100, 8188\n"))) is None


def test_a_drive_with_room_to_spare_is_short_by_nothing_not_by_a_negative_amount():
    check = tg.judge_round_disk(DEFAULT_TABLE, 1.0, HOME, {"project": 10 ** 13})
    assert check.drives[0].short_by == 0 and check.level is Level.ENOUGH


def test_a_round_that_writes_nothing_needs_no_room():
    from dataclasses import replace
    empty = replace(DEFAULT_TABLE, checkpoints_per_round=0, training_cache_per_hour=0)
    check = tg.judge_round_disk(empty, 1.0, HOME, {"project": 0})
    assert check.level is Level.ENOUGH and check.drives == ()
