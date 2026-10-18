# SPDX-License-Identifier: GPL-3.0-or-later
"""Free up space offers the test clips and the voices made for hearing a round (decision D43): exactly the files a listening makes, one listening at a time, chosen by round, removed only
when shown and asked for, and nothing else in that folder ever touched. The listenings are made by the real flows where that matters and written by hand where an exact state is needed."""
import os
from pathlib import Path

import pytest

from vs_listen_helpers import SENTENCES, VOICE_FOLDER, FlowRig
from vs_rounds_helpers import NOW
from vs_startvoice_helpers import Terminal, leaked_keys
from voice_studio.core import freeup, listen, rounds as rd, rounds_flow as rf, text, windowmodel as wm
from voice_studio.core.paths import ScratchPaths
from vs_voicefile_helpers import tree_of

CAT = text.load_catalog("en")
RUN = "heard-20261011-120000"


@pytest.fixture(autouse=True)
def no_inherited_path(monkeypatch):
    monkeypatch.delenv("PYTHONPATH", raising=False)


@pytest.fixture
def rig(tmp_path):
    r = FlowRig(tmp_path)
    r.finish_rounds(2)
    return r


def planned(rig):
    return freeup.plan(rig.paths, ScratchPaths(rig.paths.default_scratch), rd.load(rig.paths))


def make_run(rig, source="round-002", run=RUN, clips=("clip-1.wav", "clip-2.wav", "tokens.txt", "job.json"), copy=("my_voice.onnx", "my_voice.onnx.json"), size=100):
    folder = Path(rig.paths.listening, source, run)
    folder.mkdir(parents=True, exist_ok=True)
    for name in tuple(clips) + tuple(copy):
        (folder / name).write_bytes(b"x" * size)
    return folder


def free(rig, *argv, answers=("yes",)):
    io = Terminal(list(answers))
    code = rf.run_rounds(["free", *argv, "--project", "voice-check"], rig.home, None, CAT, io, training=rig.training_env, now=NOW, system=rig.system)
    assert leaked_keys(io.text + "\n".join(io.prompts)) == [], "a catalog key was printed instead of words"
    return code, io


# ---------------------------------------------------------------- what is offered

def test_a_project_with_no_listening_has_nothing_of_this_kind_on_the_list(rig):
    assert [o for o in planned(rig).offers if o.kind in ("copy", "clips")] == []


def test_a_listening_is_offered_as_its_voice_copy_and_its_test_clips_with_their_sizes_and_where_they_came_from(rig):
    make_run(rig)
    offers = [o for o in planned(rig).offers if o.kind in ("copy", "clips")]
    assert [o.kind for o in offers] == ["copy", "clips"]
    copy, clips = offers
    run = rig.paths.listening + "/round-002/" + RUN
    assert copy.paths == (run + "/my_voice.onnx", run + "/my_voice.onnx.json") and copy.bytes == 200 and copy.round == 2 and copy.source == "round-002" and copy.when == "2026-10-11 12:00 UTC"
    assert clips.paths == (run + "/clip-1.wav", run + "/clip-2.wav", run + "/job.json", run + "/tokens.txt") and clips.bytes == 400 and clips.round == 2 and clips.when == copy.when


def test_the_list_numbers_run_on_across_the_kinds_and_the_large_voice_copies_come_before_the_small_clips(rig):
    make_run(rig, "round-001", "heard-20261010-090000")
    make_run(rig, "round-002", RUN)
    offers = planned(rig).offers
    assert [o.number for o in offers] == list(range(1, len(offers) + 1))
    heard = [(o.kind, o.round) for o in offers if o.kind in ("copy", "clips")]
    assert heard == [("copy", 1), ("copy", 2), ("clips", 1), ("clips", 2)]
    assert max(i for i, o in enumerate(offers) if o.kind in ("files", "folder")) < min(i for i, o in enumerate(offers) if o.kind in ("copy", "clips"))


def test_a_voice_files_listening_belongs_to_the_round_its_name_says(rig):
    make_run(rig, VOICE_FOLDER, RUN, copy=())
    clips = [o for o in planned(rig).offers if o.kind == "clips"]
    assert len(clips) == 1 and clips[0].round == 1 and clips[0].source == VOICE_FOLDER


def test_a_source_whose_round_cannot_be_told_is_round_zero(rig):
    make_run(rig, "an-older-name", RUN, copy=())
    assert [o.round for o in planned(rig).offers if o.kind == "clips"] == [0]


def test_a_run_with_only_the_copy_or_only_the_clips_makes_one_offer(rig):
    make_run(rig, "round-001", "heard-20261010-090000", copy=())
    make_run(rig, "round-002", RUN, clips=())
    assert sorted((o.kind, o.round) for o in planned(rig).offers if o.kind in ("copy", "clips")) == [("clips", 1), ("copy", 2)]


def test_the_hearing_job_file_is_one_of_the_clips(rig):
    make_run(rig, clips=("clip-1.wav", "hear-job.json"), copy=())
    assert [os.path.basename(p) for p in [o for o in planned(rig).offers if o.kind == "clips"][0].paths] == ["clip-1.wav", "hear-job.json"]


def test_only_the_exact_names_are_offered_and_everything_else_is_left_out(rig):
    folder = make_run(rig, clips=("clip-1.wav",), copy=("my_voice.onnx",))
    for name in ("notes.txt", "clip-1.wav.part", "clip-1234.wav", "my_voice.onnx.bak", "my_voice.onnx.before-patch.old", "tokens.txt.keep", "MY_VOICE.ONNX"):
        (folder / name).write_bytes(b"mine")
    (folder / "extra").mkdir()
    (folder / "extra" / "clip-2.wav").write_bytes(b"mine")
    (folder / "clip-7.wav").symlink_to(folder / "clip-1.wav")
    heard = [o for o in planned(rig).offers if o.kind in ("copy", "clips")]
    assert sorted(os.path.basename(p) for o in heard for p in o.paths) == ["clip-1.wav", "my_voice.onnx"]


def test_a_link_for_a_folder_and_names_this_tool_does_not_give_are_not_looked_into(rig, tmp_path):
    elsewhere = tmp_path / "elsewhere" / RUN
    elsewhere.mkdir(parents=True)
    (elsewhere / "clip-1.wav").write_bytes(b"x")
    os.makedirs(rig.paths.listening)
    os.symlink(str(elsewhere.parent), rig.paths.listening + "/round-003")                      # a source that is a link
    os.makedirs(rig.paths.listening + "/round-004")
    os.symlink(str(elsewhere), rig.paths.listening + "/round-004/" + RUN)                      # a run that is a link
    make_run(rig, "bad name", RUN)                                                              # a source name this tool never gives
    make_run(rig, "round-005", "heard-2026")                                                    # a run name this tool never gives
    make_run(rig, "round-006", "heard-20261011-120000-x")
    assert [o for o in planned(rig).offers if o.kind in ("copy", "clips")] == []


def test_a_listening_folder_that_is_itself_a_link_is_not_looked_into(rig, tmp_path):
    other = tmp_path / "other-listening"
    (other / "round-002" / RUN).mkdir(parents=True)
    (other / "round-002" / RUN / "clip-1.wav").write_bytes(b"x")
    os.symlink(str(other), rig.paths.listening)
    assert [o for o in planned(rig).offers if o.kind in ("copy", "clips")] == []


def test_planning_changes_nothing_on_the_disk(rig):
    make_run(rig)
    before = tree_of(rig.paths.root)
    planned(rig)
    assert tree_of(rig.paths.root) == before


def test_the_real_flows_leave_exactly_what_the_list_offers(rig):
    rig.set_heard(SENTENCES)
    rig.run("--round", "chosen", "--yes", answers=["yes", "no"], speech="ready")          # keeps the voice copy
    rig.run("--yes", answers=["yes"])                                                       # the made voice file of round 1
    offers = [o for o in planned(rig).offers if o.kind in ("copy", "clips")]
    by = {(o.kind, o.source): sorted(os.path.basename(p) for p in o.paths) for o in offers}
    assert by[("copy", "round-002")] == ["my_voice.onnx", "my_voice.onnx.before-patch", "my_voice.onnx.json"]
    assert by[("clips", "round-002")] == ["clip-1.wav", "clip-2.wav", "clip-3.wav", "hear-job.json", "job.json", "tokens.txt"]
    assert by[("clips", VOICE_FOLDER)] == ["clip-1.wav", "clip-2.wav", "clip-3.wav", "job.json", "tokens.txt"] and ("copy", VOICE_FOLDER) not in by
    listed = {p for o in offers for p in o.paths}
    on_disk = {str(p) for p in Path(rig.paths.listening).rglob("*") if p.is_file()}
    assert listed == on_disk, "the list holds every file a listening makes and nothing it does not"


# ---------------------------------------------------------------- removing

def test_removing_the_clips_leaves_the_voice_copy_and_the_folder(rig):
    folder = make_run(rig)
    shown = planned(rig)
    clips = next(o for o in shown.offers if o.kind == "clips")
    result = freeup.remove(rig.paths, ScratchPaths(rig.paths.default_scratch), shown, [clips.number])
    assert (result.removed_heard, result.removed_files, result.removed_folders, result.removed_bytes, result.failed) == (4, 0, 0, 400, ())
    assert sorted(os.listdir(folder)) == ["my_voice.onnx", "my_voice.onnx.json"]


def test_removing_the_copy_leaves_the_clips(rig):
    folder = make_run(rig)
    shown = planned(rig)
    copy = next(o for o in shown.offers if o.kind == "copy")
    result = freeup.remove(rig.paths, ScratchPaths(rig.paths.default_scratch), shown, [copy.number])
    assert (result.removed_heard, result.removed_bytes) == (2, 200) and sorted(os.listdir(folder)) == ["clip-1.wav", "clip-2.wav", "job.json", "tokens.txt"]


def test_removing_both_takes_the_listenings_folder_and_its_source_when_nothing_else_is_in_them(rig):
    make_run(rig)
    shown = planned(rig)
    numbers = [o.number for o in shown.offers if o.kind in ("copy", "clips")]
    result = freeup.remove(rig.paths, ScratchPaths(rig.paths.default_scratch), shown, numbers)
    assert result.removed_heard == 6 and not os.path.exists(rig.paths.listening + "/round-002") and os.path.isdir(rig.paths.listening)


def test_a_source_with_another_listening_in_it_stays(rig):
    make_run(rig, "round-002", "heard-20261010-090000")
    make_run(rig, "round-002", RUN)
    shown = planned(rig)
    numbers = [o.number for o in shown.offers if o.kind in ("copy", "clips") and o.when.startswith("2026-10-11")]
    freeup.remove(rig.paths, ScratchPaths(rig.paths.default_scratch), shown, numbers)
    assert os.listdir(rig.paths.listening + "/round-002") == ["heard-20261010-090000"]
    assert len(os.listdir(rig.paths.listening + "/round-002/heard-20261010-090000")) == 6


def test_a_folder_with_something_else_in_it_is_never_removed_and_that_something_is_untouched(rig):
    folder = make_run(rig)
    (folder / "my notes.txt").write_text("mine")
    (folder / "extra").mkdir()
    (folder / "extra" / "x.txt").write_text("mine")
    shown = planned(rig)
    freeup.remove(rig.paths, ScratchPaths(rig.paths.default_scratch), shown, [o.number for o in shown.offers if o.kind in ("copy", "clips")])
    assert sorted(os.listdir(folder)) == ["extra", "my notes.txt"] and (folder / "my notes.txt").read_text() == "mine" and (folder / "extra" / "x.txt").read_text() == "mine"


def test_nothing_else_in_the_project_is_touched(rig):
    make_run(rig)
    elsewhere = {p: Path(p).read_bytes() for p in tree_of(rig.paths.root) if "/listening/" not in p}
    shown = planned(rig)
    freeup.remove(rig.paths, ScratchPaths(rig.paths.default_scratch), shown, [o.number for o in shown.offers if o.kind in ("copy", "clips")])
    assert {p: Path(p).read_bytes() for p in tree_of(rig.paths.root) if "/listening/" not in p} == elsewhere


def test_a_list_that_changed_since_it_was_shown_removes_nothing(rig):
    folder = make_run(rig)
    shown = planned(rig)
    make_run(rig, "round-001", "heard-20261010-090000")                      # another listening appeared
    with pytest.raises(freeup.FreeError) as caught:
        freeup.remove(rig.paths, ScratchPaths(rig.paths.default_scratch), shown, [o.number for o in shown.offers if o.kind == "clips"])
    assert caught.value.code == "changed" and len(os.listdir(folder)) == 6


def test_a_file_that_cannot_be_removed_is_reported_and_the_others_still_go(rig, monkeypatch):
    folder = make_run(rig)
    shown = planned(rig)
    real = os.unlink

    def unlink(path, *a, **k):
        if str(path).endswith("clip-2.wav"):
            raise PermissionError("no")
        return real(path, *a, **k)
    monkeypatch.setattr(os, "unlink", unlink)
    result = freeup.remove(rig.paths, ScratchPaths(rig.paths.default_scratch), shown, [o.number for o in shown.offers if o.kind == "clips"])
    assert result.removed_heard == 3 and [os.path.basename(p) for p, _r in result.failed] == ["clip-2.wav"] and "clip-2.wav" in os.listdir(folder)


def test_a_number_that_is_not_on_the_list_removes_nothing(rig):
    make_run(rig)
    shown = planned(rig)
    for wanted in ([], [999]):
        with pytest.raises(freeup.FreeError):
            freeup.remove(rig.paths, ScratchPaths(rig.paths.default_scratch), shown, wanted)
    assert len(os.listdir(rig.paths.listening + "/round-002/" + RUN)) == 6


@pytest.mark.parametrize("make_bad", ["link", "directory", "wrong_depth", "too_deep", "wrong_name", "outside", "odd_source", "odd_run"])
def test_the_check_made_at_the_moment_of_removal_refuses_a_file_that_is_no_longer_what_it_was_shown_as(rig, tmp_path, make_bad):
    folder = make_run(rig, clips=("clip-1.wav",), copy=("my_voice.onnx",))
    target = folder / "clip-1.wav"
    if make_bad == "link":
        target.unlink()
        (tmp_path / "precious").write_bytes(b"p")
        target.symlink_to(tmp_path / "precious")
    elif make_bad == "directory":
        target.unlink()
        target.mkdir()
    elif make_bad == "wrong_depth":
        target = folder.parent / "clip-1.wav"
        target.write_bytes(b"x")
    elif make_bad == "too_deep":
        (folder / "extra").mkdir()
        target = folder / "extra" / "clip-1.wav"
        target.write_bytes(b"x")
    elif make_bad == "odd_source":
        target = make_run(rig, "bad name", RUN, clips=("clip-1.wav",), copy=()) / "clip-1.wav"
    elif make_bad == "odd_run":
        target = make_run(rig, "round-002", "heard-2026", clips=("clip-1.wav",), copy=()) / "clip-1.wav"
    elif make_bad == "wrong_name":
        target = folder / "notes.txt"
        target.write_bytes(b"x")
    else:
        target = tmp_path / "clip-1.wav"
        target.write_bytes(b"x")
    assert not freeup._may_remove_listening_file(rig.paths, str(target), "clips")


def test_listenings_of_one_round_are_listed_in_the_order_of_their_times(rig):
    for run in ("heard-20261012-080000", "heard-20261010-090000", RUN):
        make_run(rig, "round-002", run, copy=())
    assert [o.when for o in planned(rig).offers if o.kind == "clips"] == ["2026-10-10 09:00 UTC", "2026-10-11 12:00 UTC", "2026-10-12 08:00 UTC"]


def test_each_kind_accepts_only_its_own_names(rig):
    folder = make_run(rig)
    assert freeup._may_remove_listening_file(rig.paths, str(folder / "clip-1.wav"), "clips") and freeup._may_remove_listening_file(rig.paths, str(folder / "my_voice.onnx"), "copy")
    assert not freeup._may_remove_listening_file(rig.paths, str(folder / "my_voice.onnx"), "clips") and not freeup._may_remove_listening_file(rig.paths, str(folder / "clip-1.wav"), "copy")


def test_nothing_is_removed_through_a_listening_folder_that_is_a_link(rig, tmp_path):
    folder = make_run(rig)
    moved = tmp_path / "moved-listening"
    os.rename(rig.paths.listening, moved)
    os.symlink(str(moved), rig.paths.listening)
    assert not freeup._may_remove_listening_file(rig.paths, str(Path(rig.paths.listening, "round-002", RUN, "clip-1.wav")), "clips")
    assert (moved / "round-002" / RUN / "clip-1.wav").exists()


# ---------------------------------------------------------------- the command

def test_the_list_shows_each_in_words_with_its_round_time_and_size_and_how_to_choose_them(rig):
    make_run(rig)
    make_run(rig, VOICE_FOLDER, "heard-20261010-090000", copy=())
    code, io = free(rig)
    assert code == 0
    assert "The voice made for hearing round 2 on 2026-10-11 12:00 UTC: 200 B. The test clips stay." in io.text
    assert "Test clips of round 2, made on 2026-10-11 12:00 UTC: 400 B. They can be made again." in io.text
    assert "Test clips made on 2026-10-10 09:00 UTC from the voice file %s: 400 B. They can be made again." % VOICE_FOLDER in io.text
    assert "are chosen by round too, with --clips and --copies. For example: python3 -m voice_studio.rounds free --copies 2 --project voice-check" in io.text


def test_nothing_about_listening_is_said_when_there_is_nothing_to_say(rig):
    code, io = free(rig)
    assert "test clips" not in io.text.lower() and "--clips" not in io.text


def test_clips_are_chosen_by_round_and_every_listening_of_that_round_goes(rig):
    make_run(rig, "round-002", "heard-20261010-090000", copy=())
    make_run(rig, "round-002", RUN)
    make_run(rig, "round-001", RUN, copy=())
    code, io = free(rig, "--clips", "2", answers=["yes"])
    assert code == 0 and "Test clips and voices made for hearing, removed: 8 files." in io.text
    left = sorted(str(p.relative_to(rig.paths.listening)) for p in Path(rig.paths.listening).rglob("*") if p.is_file())
    assert left == ["round-001/%s/%s" % (RUN, n) for n in ("clip-1.wav", "clip-2.wav", "job.json", "tokens.txt")] + ["round-002/%s/my_voice.onnx" % RUN, "round-002/%s/my_voice.onnx.json" % RUN]


def test_copies_are_chosen_by_round_and_the_clips_stay(rig):
    make_run(rig)
    code, io = free(rig, "--copies", "2", answers=["yes"])
    assert code == 0 and "Test clips and voices made for hearing, removed: 2 files." in io.text and "Saved files removed: 0" in io.text
    assert sorted(os.listdir(rig.paths.listening + "/round-002/" + RUN)) == ["clip-1.wav", "clip-2.wav", "job.json", "tokens.txt"]


def test_the_question_names_what_goes_and_a_no_removes_nothing(rig):
    make_run(rig)
    before = tree_of(rig.paths.listening)
    code, io = free(rig, "--clips", "2", answers=["no"])
    assert code == 2 and "This removes:" in io.text and "Test clips of round 2" in io.text and tree_of(rig.paths.listening) == before


def test_all_takes_the_test_clips_and_the_voice_copies_too(rig):
    make_run(rig)
    code, io = free(rig, "--all", answers=["yes"])
    assert code == 0 and not os.path.exists(rig.paths.listening + "/round-002") and "removed: 6 files." in io.text


def test_a_round_with_none_of_that_kind_is_said_plainly_and_nothing_is_removed(rig):
    make_run(rig, copy=())
    code, io = free(rig, "--copies", "2", answers=["yes"])
    assert code == 2 and "The list has nothing for --copies 2. Nothing was removed." in io.text and len(os.listdir(rig.paths.listening + "/round-002/" + RUN)) == 4


def test_round_zero_is_a_round_for_clips_and_copies_only(rig):
    make_run(rig, "an-older-name", RUN, copy=())
    code, io = free(rig, "--saved", "0", answers=["yes"])
    assert code == 2 and "I did not understand 0." in io.text
    code, io = free(rig, "--clips", "0", answers=["yes"])
    assert code == 0 and not os.path.exists(rig.paths.listening + "/an-older-name")


@pytest.mark.parametrize("word", ["x", "-1", "1.5", "", "1;2"])
def test_a_round_that_is_not_a_number_is_not_understood_for_the_new_options_either(rig, word):
    make_run(rig)
    for option in ("--clips", "--copies"):
        code, io = free(rig, option, word)
        assert code == 2 and "I did not understand" in io.text and len(os.listdir(rig.paths.listening + "/round-002/" + RUN)) == 6


def test_the_new_options_with_all_are_refused_like_the_old_ones(rig):
    make_run(rig)
    code, io = free(rig, "--all", "--clips", "2")
    assert code == 2 and "Give either --all or a list of rounds, not both." in io.text


def test_the_real_listening_is_removed_whole_by_the_command(rig):
    rig.run("--round", "chosen", "--yes", answers=["yes", "no"])
    assert rig.made() == ["round-002/" + RUN]
    code, io = free(rig, "--copies", "2", "--clips", "2", answers=["yes"])
    assert code == 0 and not os.path.exists(rig.paths.listening + "/round-002") and rig.made() == []


# ---------------------------------------------------------------- the window

def test_the_window_lists_them_with_the_option_each_takes_and_asks_for_the_command_that_removes_them(rig):
    make_run(rig)
    view = wm.free_view(rig.home, "voice-check", CAT)
    heard = [i for i in view.items if i.kind in ("clips", "copies")]
    assert sorted((i.kind, i.round) for i in heard) == [("clips", 2), ("copies", 2)] and all(i.line and i.bytes for i in heard)
    command, argv = wm.free_args("voice-check", heard)
    assert command == "rounds" and argv == ["free", "--copies", "2", "--clips", "2", "--project", "voice-check"]
    assert wm.free_args("voice-check", [i for i in heard if i.kind == "clips"])[1] == ["free", "--clips", "2", "--project", "voice-check"]


def test_removing_only_saved_files_does_not_talk_about_test_clips(rig):
    code, io = free(rig, "--saved", "1", answers=["yes"])
    assert "Test clips and voices made for hearing, removed" not in io.text


# ---------------------------------------------------------------- listenings that have sat for 30 days (decision D43): a notice and an offer, never a removal

OLD_RUN = "heard-20260901-090000"                                  # 40 days before NOW
from datetime import datetime, timedelta, timezone


def at(days=0, seconds=0):
    return NOW + timedelta(days=days, seconds=seconds)


def test_the_age_is_thirty_days_and_a_listening_exactly_that_old_is_old():
    assert freeup.OLD_AFTER_DAYS == 30
    made = datetime(2026, 10, 11, 12, 0, 0, tzinfo=timezone.utc)
    assert freeup.is_old(RUN, made + timedelta(days=30))
    assert not freeup.is_old(RUN, made + timedelta(days=30) - timedelta(seconds=1))
    assert freeup.is_old(RUN, made + timedelta(days=31)) and not freeup.is_old(RUN, made + timedelta(days=29))


def test_a_time_in_the_future_or_a_name_that_is_not_a_time_is_never_old():
    assert not freeup.is_old("heard-20271011-120000", NOW)                       # the clock was set back
    for name in ("heard-20261399-120000", "heard-20261011-256100", "heard-2026", "x", ""):
        assert not freeup.is_old(name, NOW + timedelta(days=4000)), name


def test_a_clock_without_a_zone_is_taken_as_utc():
    assert freeup.is_old(OLD_RUN, datetime(2026, 10, 11, 12, 0, 0)) and not freeup.is_old(RUN, datetime(2026, 10, 12, 12, 0, 0))


def test_the_plan_marks_only_the_old_listenings(rig):
    make_run(rig, "round-001", OLD_RUN)
    make_run(rig, "round-002", RUN)
    shown = freeup.plan(rig.paths, ScratchPaths(rig.paths.default_scratch), rd.load(rig.paths), NOW)
    assert sorted((o.round, o.kind, o.old) for o in shown.offers if o.kind in ("copy", "clips")) == [(1, "clips", True), (1, "copy", True), (2, "clips", False), (2, "copy", False)]
    assert shown.old_listenings == 1


def test_a_listening_just_under_thirty_days_old_is_not_marked(rig):
    make_run(rig, "round-002", RUN)
    just_under = freeup.plan(rig.paths, ScratchPaths(rig.paths.default_scratch), rd.load(rig.paths), at(30, -1))
    exactly = freeup.plan(rig.paths, ScratchPaths(rig.paths.default_scratch), rd.load(rig.paths), at(30))
    assert not any(o.old for o in just_under.offers) and just_under.old_listenings == 0
    assert all(o.old for o in exactly.offers if o.kind in ("copy", "clips")) and exactly.old_listenings == 1


def test_a_voice_copy_and_clips_of_one_listening_count_as_one_and_two_listenings_as_two(rig):
    make_run(rig, "round-001", OLD_RUN)
    make_run(rig, "round-001", "heard-20260902-090000")
    make_run(rig, "round-002", "heard-20260801-090000", copy=())
    assert freeup.plan(rig.paths, ScratchPaths(rig.paths.default_scratch), rd.load(rig.paths), NOW).old_listenings == 3
    assert freeup.old_count(rig.paths, NOW) == 3


def test_the_age_does_not_make_the_list_look_changed(rig):
    make_run(rig, "round-002", RUN)
    early = freeup.plan(rig.paths, ScratchPaths(rig.paths.default_scratch), rd.load(rig.paths), NOW)
    late = freeup.plan(rig.paths, ScratchPaths(rig.paths.default_scratch), rd.load(rig.paths), at(40))
    assert early.fingerprint == late.fingerprint and [o.old for o in early.offers if o.kind == "clips"] != [o.old for o in late.offers if o.kind == "clips"]
    freeup.remove(rig.paths, ScratchPaths(rig.paths.default_scratch), early, [o.number for o in early.offers if o.kind == "clips"])       # shown young, removed after it turned old: still the list that was shown


def test_a_folder_with_nothing_to_remove_is_not_counted_as_old(rig):
    folder = make_run(rig, "round-001", OLD_RUN, clips=(), copy=())
    (folder / "my notes.txt").write_text("mine")
    assert freeup.old_count(rig.paths, NOW) == 0 and freeup.plan(rig.paths, ScratchPaths(rig.paths.default_scratch), rd.load(rig.paths), NOW).old_listenings == 0


def test_an_old_row_says_it_should_be_removed_and_a_young_one_does_not(rig):
    make_run(rig, "round-001", OLD_RUN)
    make_run(rig, "round-002", RUN)
    code, io = free(rig)
    note = "This is more than 30 days old and should be removed."
    assert io.text.count(note) == 2
    old_rows = [l for l in io.lines if "2026-09-01 09:00 UTC" in l]
    new_rows = [l for l in io.lines if "2026-10-11 12:00 UTC" in l]
    assert len(old_rows) == 2 and all(note in l for l in old_rows) and len(new_rows) == 2 and not any(note in l for l in new_rows)


def test_the_list_gives_one_notice_with_the_count_and_the_command_to_remove_them(rig):
    make_run(rig, "round-001", OLD_RUN)
    make_run(rig, "round-001", "heard-20260902-090000")
    make_run(rig, "round-002", RUN)
    code, io = free(rig)
    assert code == 0
    assert io.text.count("2 earlier listenings are more than 30 days old and should be removed.") == 1
    assert "To remove them, run: python3 -m voice_studio.rounds free --old --project voice-check" in io.text


def test_one_old_listening_is_said_in_the_singular(rig):
    make_run(rig, "round-001", OLD_RUN)
    _code, io = free(rig)
    assert "1 earlier listening is more than 30 days old and should be removed." in io.text


def test_no_notice_when_nothing_is_old(rig):
    make_run(rig, "round-002", RUN)
    _code, io = free(rig)
    assert "days old" not in io.text and "free --old" not in io.text


def test_old_takes_every_old_listening_and_leaves_the_young_ones(rig):
    make_run(rig, "round-001", OLD_RUN)
    make_run(rig, "round-001", "heard-20260902-090000", copy=())
    young = make_run(rig, "round-002", RUN)
    code, io = free(rig, "--old", answers=["yes"])
    assert code == 0 and "removed: 10 files." in io.text
    assert not os.path.exists(rig.paths.listening + "/round-001") and len(os.listdir(young)) == 6


def test_old_shows_what_it_will_remove_and_asks_first_and_a_no_removes_nothing(rig):
    make_run(rig, "round-001", OLD_RUN)
    before = tree_of(rig.paths.listening)
    code, io = free(rig, "--old", answers=["no"])
    assert code == 2 and "This removes:" in io.text and "should be removed" in io.text and tree_of(rig.paths.listening) == before and io.prompts


def test_old_with_nobody_to_ask_removes_nothing(rig):
    make_run(rig, "round-001", OLD_RUN)
    before = tree_of(rig.paths.listening)
    io = Terminal([], interactive=False)
    code = rf.run_rounds(["free", "--old", "--project", "voice-check"], rig.home, None, CAT, io, training=rig.training_env, now=NOW, system=rig.system)
    assert code == 2 and tree_of(rig.paths.listening) == before


def test_old_with_nothing_old_says_so_and_removes_nothing(rig):
    make_run(rig, "round-002", RUN)
    before = tree_of(rig.paths.listening)
    code, io = free(rig, "--old", answers=["yes"])
    assert code == 2 and "Nothing is more than 30 days old. Nothing was removed." in io.text and tree_of(rig.paths.listening) == before and io.prompts == []


@pytest.mark.parametrize("more", [["--all"], ["--saved", "1"], ["--working", "1"], ["--clips", "1"], ["--copies", "1"]])
def test_old_is_on_its_own(rig, more):
    make_run(rig, "round-001", OLD_RUN)
    before = tree_of(rig.paths.listening)
    code, io = free(rig, "--old", *more, answers=["yes"])
    assert code == 2 and "Give --old on its own, without --all or a list of rounds. Nothing was removed." in io.text and tree_of(rig.paths.listening) == before


def test_old_never_takes_anything_that_is_not_a_listening(rig):
    make_run(rig, "round-001", OLD_RUN)
    shown_before = [o for o in planned(rig).offers if o.kind in ("files", "folder")]
    checkpoints = [p for o in shown_before for p in o.paths]
    free(rig, "--old", answers=["yes"])
    assert all(os.path.exists(p) for p in checkpoints)


def test_a_notice_alone_never_removes_anything(rig):
    make_run(rig, "round-001", OLD_RUN)
    before = tree_of(rig.paths.listening)
    free(rig)
    free(rig, "--clips", "1", answers=["no"])
    rig.run(answers=["no"])
    assert tree_of(rig.paths.listening) == before


def test_listen_says_up_front_that_earlier_listenings_are_old_whatever_happens_next(rig):
    make_run(rig, "round-001", OLD_RUN)
    make_run(rig, "round-001", "heard-20260902-090000")
    code, io = rig.run(answers=["no"])
    assert code == 2
    notice = "2 earlier listenings are more than 30 days old and should be removed."
    assert notice in io.text and "To remove them, run: python3 -m voice_studio.rounds free --old --project voice-check" in io.text
    assert io.text.index(notice) < io.text.index("would be heard like this")


def test_listen_says_nothing_about_age_when_nothing_is_old(rig):
    make_run(rig, "round-001", RUN)
    _code, io = rig.run(answers=["no"])
    assert "days old" not in io.text


def test_a_run_of_listen_does_not_count_its_own_listening_and_removes_nothing(rig):
    old = make_run(rig, "round-001", OLD_RUN)
    before = tree_of(old)
    code, io = rig.run("--yes", answers=["yes"])
    assert code == 0 and io.text.count("should be removed.") == 1 and "1 earlier listening is more than 30 days old" in io.text and tree_of(old) == before


def test_the_window_page_gives_the_notice_first_and_marks_the_old_rows(rig):
    make_run(rig, "round-001", OLD_RUN)
    make_run(rig, "round-002", RUN)
    view = wm.free_view(rig.home, "voice-check", CAT, NOW)
    assert view.notes[0] == "1 earlier listening is more than 30 days old and should be removed."
    marked = [i for i in view.items if "should be removed" in i.line]
    assert sorted((i.kind, i.round) for i in marked) == [("clips", 1), ("copies", 1)]
    assert wm.free_view(rig.home, "voice-check", CAT, at(-60)).notes[0] != view.notes[0]


def test_the_window_has_no_notice_when_nothing_is_old(rig):
    make_run(rig, "round-002", RUN)
    assert not any("days old" in n for n in wm.free_view(rig.home, "voice-check", CAT, NOW).notes)


@pytest.fixture
def far_future_clock(monkeypatch):
    """The computer's own clock says 2030, so anything that forgets the time it was given and asks the clock would call every listening old."""
    class Future(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2030, 1, 1, tzinfo=tz or timezone.utc)
    monkeypatch.setattr(freeup, "datetime", Future)


def test_the_seconds_in_the_name_count_in_the_age():
    exactly = datetime(2026, 11, 10, 12, 0, 30, tzinfo=timezone.utc)
    assert freeup.is_old("heard-20261011-120030", exactly) and not freeup.is_old("heard-20261011-120030", exactly - timedelta(seconds=1))


def test_with_no_time_given_the_computers_own_clock_is_used(far_future_clock):
    assert freeup.is_old(RUN) and freeup.is_old(RUN, None)


def test_every_front_uses_the_time_it_was_given_and_not_the_clock(rig, far_future_clock):
    make_run(rig, "round-001", "heard-20260920-090000")                       # 21 days before NOW: young; the 2030 clock would call it old
    assert freeup.old_count(rig.paths, NOW) == 0
    _code, io = free(rig)
    assert "days old" not in io.text
    _code, io = rig.run(answers=["no"])
    assert "days old" not in io.text
    assert not any("days old" in n for n in wm.free_view(rig.home, "voice-check", CAT, NOW).notes)
    assert not any(o.old for o in freeup.plan(rig.paths, ScratchPaths(rig.paths.default_scratch), rd.load(rig.paths), NOW).offers)
