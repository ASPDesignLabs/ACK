# SPDX-License-Identifier: GPL-3.0-or-later
"""Listening straight to a round, with no zip file (plan task VS-5.5): what is refused before anything is written, the voice made in the new listening folder with the same three steps as
the make command, the large voice copy that is removed only on a yes and only by its exact names, and the terminal front. The export and the patcher are stood in for, as in the voice file tests;
the speaking program is the real one."""
import dataclasses
import os
import stat
from pathlib import Path

import pytest

from vs_listen_helpers import SENTENCES, FlowRig, SYMBOLS
from vs_rounds_helpers import NOW
from vs_voicefile_helpers import TOOLS, tree_of, write_settings
from voice_studio.core import jobs, listen, phonemes, rounds as rd, voicefile as vf
from voice_studio.core.paths import ScratchPaths
from voice_studio.core.system import CommandResult

STAMP = jobs.utc_stamp(NOW)
FOLDER_2 = "round-002-heard-20261011-120000"


@pytest.fixture(autouse=True)
def no_inherited_path(monkeypatch):
    monkeypatch.delenv("PYTHONPATH", raising=False)


@pytest.fixture
def rig(tmp_path):
    r = FlowRig(tmp_path, make=False)
    r.finish_rounds(2)
    return r


def plan_round(rig, number=None, free=10**12, record=None, training=None):
    return listen.plan_listen_round(rig.paths, ScratchPaths(rig.paths.default_scratch), rd.load(rig.paths) if record is None else record, number, SENTENCES,
                                    training or rig.training, rig.system, STAMP, free)


def code_of(fn, *a, **kw):
    with pytest.raises((vf.VoiceFileError, listen.ListenError)) as caught:
        fn(*a, **kw)
    return caught.value.code


# ---------------------------------------------------------------- the plan

def test_the_plan_names_the_chosen_round_a_new_folder_and_no_zip(rig):
    plan = plan_round(rig)
    folder = rig.paths.default_scratch + "/listening/" + FOLDER_2
    assert plan.round.number == 2 and plan.folder == folder and plan.voice.folder == folder and plan.voice.zip_path == ""
    assert plan.voice.model == folder + "/my_voice.onnx" and plan.voice.config == folder + "/my_voice.onnx.json" and plan.voice.name == "round-002"
    assert plan.round.settings == rig.paths.round_configs + "/round-002.json" and plan.round.checkpoint.endswith("version_1/checkpoints/last.ckpt")
    assert plan.sentences == SENTENCES and plan.english and plan.language == "en-us" and plan.skipped_symbols == 0 and not os.path.exists(folder)


def test_a_number_picks_that_round_and_not_the_chosen_one(rig):
    plan = plan_round(rig, 1)
    assert plan.round.number == 1 and plan.folder.endswith("/round-001-heard-20261011-120000") and plan.round.settings.endswith("round-001.json")


def test_planning_changes_nothing_on_the_disk(rig):
    before = tree_of(rig.paths.root)
    plan_round(rig)
    assert tree_of(rig.paths.root) == before


def test_the_room_needed_is_the_voice_made_twice_over_at_the_largest_size_plus_the_sounds(rig):
    plan = plan_round(rig)
    from voice_studio.core import voicezip
    assert plan.need_bytes == listen.ROUND_NEED_BYTES == listen.NEED_BYTES + 2 * voicezip.MAX_MODEL_BYTES + voicezip.MAX_CONFIG_BYTES


def test_without_that_room_nothing_is_planned_and_with_it_barely_it_is(rig):
    assert code_of(plan_round, rig, free=listen.ROUND_NEED_BYTES // 10) == "no_room"
    from voice_studio.core.diskbudget import Level
    assert plan_round(rig, free=10**12).room is not Level.NOT_ENOUGH
    assert plan_round(rig, free=None).free_bytes is None


def test_a_round_that_does_not_exist_is_refused_with_its_number(rig):
    with pytest.raises(vf.VoiceFileError) as caught:
        plan_round(rig, 9)
    assert (caught.value.code, caught.value.detail) == ("no_such_round", "9")


def test_with_no_round_chosen_nothing_is_planned(tmp_path):
    rig = FlowRig(tmp_path, make=False)
    assert code_of(plan_round, rig) == "no_chosen_round"


def test_while_a_round_is_running_nothing_is_planned(rig):
    plan = rig.world.begin()
    rd.attach_job(rig.paths, plan.number, rig.world.job_for(plan, "running").id)
    assert code_of(plan_round, rig) == "round_running" and code_of(plan_round, rig, 1) == "round_running"


def test_a_saved_point_that_is_gone_or_cut_short_is_refused_instead_of_using_another(rig):
    checkpoint = plan_round(rig).round.checkpoint
    data = Path(checkpoint).read_bytes()
    Path(checkpoint).write_bytes(data[: len(data) // 2])
    assert code_of(plan_round, rig) == "saved_point_damaged"
    os.unlink(checkpoint)
    assert code_of(plan_round, rig) == "saved_point_missing"


def test_a_round_with_no_settings_file_is_refused(rig):
    os.unlink(rig.paths.round_configs + "/round-002.json")
    assert code_of(plan_round, rig) == "no_settings" and plan_round(rig, 1).round.number == 1


def test_without_pronunciation_data_it_says_so_and_names_the_language(tmp_path):
    rig = FlowRig(tmp_path, make=False, data=False)
    rig.finish_rounds(1)
    with pytest.raises(listen.ListenError) as caught:
        plan_round(rig)
    assert (caught.value.code, caught.value.detail) == ("no_pronunciation", "en-us")


def test_a_settings_file_that_cannot_give_a_list_of_sounds_is_a_tokens_error(rig):
    for content in (b"not json", b"\xff\xfe\x00bad", b'{"audio": {}}'):
        Path(rig.paths.round_configs + "/round-002.json").write_bytes(content)
        with pytest.raises(phonemes.TokensError):
            plan_round(rig)


def test_the_sounds_the_phone_leaves_out_are_counted_from_the_rounds_own_settings_file(rig):
    write_settings(rig.paths, 2, {"audio": {"sample_rate": 22050}, "espeak": {"voice": "en-us"}, "phoneme_type": "espeak", "phoneme_id_map": SYMBOLS})
    assert plan_round(rig).skipped_symbols == 1                    # the two-character sound; the line break is never counted


def test_another_language_is_planned_and_marked_not_english(tmp_path):
    rig = FlowRig(tmp_path, make=False, language="es-es")
    rig.finish_rounds(1, language="es-es")
    plan = plan_round(rig)
    assert plan.language == "es-es" and not plan.english


# ---------------------------------------------------------------- doing it: the voice, then the sounds

def run_plan(rig, plan=None, stages=None, training=True):
    plan = plan or plan_round(rig)
    return plan, listen.listen(plan, rig.studio, rig.system, str(TOOLS), stages.append if stages is not None else None, training=rig.training if training else None)


def test_the_voice_is_made_with_the_three_steps_in_order_then_the_sounds(rig):
    stages = []
    plan, heard = run_plan(rig, stages=stages)
    assert stages == ["export", "settings", "patch", "sounds", "speaking"] and rig.system.maker.kinds() == ["export", "patch"]
    assert [c.number for c in heard.clips] == [1, 2, 3]
    names = sorted(os.listdir(plan.folder))
    assert names == ["clip-1.wav", "clip-2.wav", "clip-3.wav", "job.json", "my_voice.onnx", "my_voice.onnx.before-patch", "my_voice.onnx.json", "tokens.txt"]


def test_the_export_gets_the_round_saved_point_and_the_new_folder_and_the_patcher_the_new_model(rig):
    plan, _heard = run_plan(rig)
    export, patch = rig.system.maker.calls
    assert export[1][export[1].index("--checkpoint") + 1] == plan.round.checkpoint and export[1][export[1].index("--output-file") + 1] == plan.voice.model
    assert patch[1][2] == plan.voice.model and patch[1][3] == plan.voice.config and patch[3] == plan.folder


def test_the_rounds_own_settings_file_is_copied_next_to_the_model_byte_for_byte(rig):
    plan, _heard = run_plan(rig)
    assert Path(plan.voice.config).read_bytes() == Path(plan.round.settings).read_bytes()


def test_the_speaking_program_is_given_the_sounds_of_the_copied_settings_and_the_new_model(rig):
    plan, _heard = run_plan(rig)
    seen = rig.seen()
    assert seen["model"] == plan.voice.model and seen["data_dir_exists"] and seen["tokens"].splitlines()[:3] == ["_ 0", "^ 1", "$ 2"]


def test_no_zip_is_made_and_nothing_under_exports_or_the_record_changes(rig):
    before_exports, record = tree_of(rig.paths.exports), Path(rig.paths.root, "rounds.json")
    before_record = record.read_bytes() if record.exists() else None
    run_plan(rig)
    assert tree_of(rig.paths.exports) == before_exports and not [p for p in tree_of(rig.paths.root) if p.endswith(".zip")]
    assert (record.read_bytes() if record.exists() else None) == before_record


def test_a_round_plan_needs_the_training_programs_and_makes_nothing_without_them(rig):
    plan = plan_round(rig)
    with pytest.raises(listen.ListenError) as caught:
        listen.listen(plan, rig.studio, rig.system, str(TOOLS), None)
    assert caught.value.code == "runner_failed" and "training" in caught.value.detail and rig.system.maker.calls == []


def test_a_failed_export_leaves_the_folder_as_it_is_and_never_goes_on(tmp_path):
    rig = FlowRig(tmp_path, make=False, export="fail")
    rig.finish_rounds(1)
    with pytest.raises(vf.VoiceFileError) as caught:
        run_plan(rig)
    assert caught.value.code == "export_failed" and caught.value.folder.endswith("/round-001-heard-20261011-120000") and rig.system.maker.kinds() == ["export"]
    assert os.listdir(caught.value.folder) == [] and not rig.heard_ran()


def test_a_failed_patch_leaves_what_was_made_and_never_makes_sounds(tmp_path):
    rig = FlowRig(tmp_path, make=False, patch="fail")
    rig.finish_rounds(1)
    with pytest.raises(vf.VoiceFileError) as caught:
        run_plan(rig)
    folder = caught.value.folder
    assert caught.value.code == "patch_failed" and sorted(os.listdir(folder)) == ["my_voice.onnx", "my_voice.onnx.json"] and not [n for n in os.listdir(folder) if n.endswith(".wav")]


def test_a_voice_the_phone_would_refuse_is_not_played(tmp_path):
    rig = FlowRig(tmp_path, make=False, patch="skipped")                  # the patcher says it is done but changed nothing
    rig.finish_rounds(1)
    with pytest.raises(listen.ListenError) as caught:
        run_plan(rig)
    assert caught.value.code == "voice_not_ready" and caught.value.detail and not [n for n in os.listdir(caught.value.folder) if n.endswith(".wav")]


def test_a_folder_that_is_already_there_is_never_used(rig):
    plan = plan_round(rig)
    os.makedirs(plan.folder)
    Path(plan.folder, "mine.txt").write_text("mine")
    with pytest.raises(listen.ListenError) as caught:
        run_plan(rig, plan)
    assert caught.value.code == "exists" and os.listdir(plan.folder) == ["mine.txt"] and rig.system.maker.calls == []


def test_a_stop_during_the_export_is_not_swallowed(tmp_path):
    rig = FlowRig(tmp_path, make=False, export="interrupt")
    rig.finish_rounds(1)
    with pytest.raises(KeyboardInterrupt):
        run_plan(rig)


# ---------------------------------------------------------------- the voice copy

def test_the_voice_copy_is_exactly_the_three_files_making_a_voice_leaves(rig):
    plan, heard = run_plan(rig)
    copy = listen.voice_copy(plan)
    assert [n for n, _s in copy] == ["my_voice.onnx", "my_voice.onnx.before-patch", "my_voice.onnx.json"] and all(size > 0 for _n, size in copy)
    assert listen.VOICE_COPY_NAMES == tuple(n for n, _s in copy)


def test_removing_it_removes_those_files_and_nothing_else(rig):
    plan, heard = run_plan(rig)
    clips = {c.path: Path(c.path).read_bytes() for c in heard.clips}
    removed, failed = listen.remove_voice_copy(plan)
    assert removed == ["my_voice.onnx", "my_voice.onnx.before-patch", "my_voice.onnx.json"] and failed == []
    assert sorted(os.listdir(plan.folder)) == ["clip-1.wav", "clip-2.wav", "clip-3.wav", "job.json", "tokens.txt"]
    assert {c.path: Path(c.path).read_bytes() for c in heard.clips} == clips and listen.voice_copy(plan) == []


def test_a_second_removal_finds_nothing_to_do(rig):
    plan, _heard = run_plan(rig)
    listen.remove_voice_copy(plan)
    assert listen.remove_voice_copy(plan) == ([], [])


def test_a_link_or_a_folder_with_one_of_those_names_is_left_alone(rig, tmp_path):
    plan, _heard = run_plan(rig)
    os.unlink(plan.voice.model)
    other = tmp_path / "precious.bin"
    other.write_bytes(b"precious")
    os.symlink(str(other), plan.voice.model)
    os.unlink(plan.voice.config)
    os.mkdir(plan.voice.config)
    Path(plan.voice.config, "inside").write_text("x")
    removed, failed = listen.remove_voice_copy(plan)
    assert removed == ["my_voice.onnx.before-patch"] and failed == []
    assert other.read_bytes() == b"precious" and os.path.islink(plan.voice.model) and Path(plan.voice.config, "inside").read_text() == "x"


def test_a_file_that_cannot_be_removed_is_reported_and_the_rest_still_go(rig, monkeypatch):
    plan, _heard = run_plan(rig)
    real = os.unlink

    def unlink(path, *a, **k):
        if str(path).endswith(".before-patch"):
            raise PermissionError("no")
        return real(path, *a, **k)
    monkeypatch.setattr(os, "unlink", unlink)
    removed, failed = listen.remove_voice_copy(plan)
    assert removed == ["my_voice.onnx", "my_voice.onnx.json"] and failed == ["my_voice.onnx.before-patch"]


def test_a_plan_for_a_voice_file_that_was_made_earlier_never_has_a_copy_to_remove(tmp_path):
    rig = FlowRig(tmp_path)                                            # a voice file in exports, as made by the make command
    plan = listen.plan_listen(rig.paths, ScratchPaths(rig.paths.default_scratch), None, SENTENCES, rig.training, rig.system, STAMP, 10**12)
    assert plan.round is None and listen.voice_copy(plan) == [] and listen.remove_voice_copy(plan) == ([], [])
    exports_before = tree_of(rig.paths.exports)
    heard = listen.listen(plan, rig.studio, rig.system, str(TOOLS))
    assert listen.remove_voice_copy(plan) == ([], []) and tree_of(rig.paths.exports) == exports_before and heard.clips


def test_even_a_plan_that_points_at_the_files_of_a_made_voice_removes_nothing_unless_it_is_a_round_plan(tmp_path):
    rig = FlowRig(tmp_path)
    made = Path(rig.paths.exports, "voice-check-round-001-20261011-130000" if False else os.listdir(rig.paths.exports)[0])
    plan = listen.plan_listen(rig.paths, ScratchPaths(rig.paths.default_scratch), None, SENTENCES, rig.training, rig.system, STAMP, 10**12)
    pointing_at_it = dataclasses.replace(plan, folder=str(made))
    assert listen.voice_copy(pointing_at_it) == [] and listen.remove_voice_copy(pointing_at_it) == ([], [])
    assert (made / "my_voice.onnx").exists() and (made / "my_voice.onnx.json").exists()


# ---------------------------------------------------------------- the screen

def test_the_plan_for_a_round_is_shown_before_anything_is_asked_or_written(rig):
    code, io = rig.run("--round", "chosen", answers=["no"])
    first_ask = next(i for i, (kind, _t) in enumerate(io.events) if kind == "ask")
    before = "\n".join(t for kind, t in io.events[:first_ask] if kind == "say")
    assert code == 2 and rig.made() == [] and rig.system.maker.calls == []
    for part in ("Round 2 would be heard like this:", "make a voice from the saved point of round 2 (", "about %d minutes of training" % rd.trained_minutes(rd.load(rig.paths), 2), "It uses the same steps as the make command, but makes no zip file",
                 "1. Hello, my name is Anna.", "write the voice and the sound files into a new folder, ", FOLDER_2, "at the end, ask whether to remove the voice it made here, which is large",
                 "take a few minutes, because making the voice is the slow part", "Checked before starting:"):
        assert part in before, part
    assert "the very files that are in its zip" not in before


def test_a_yes_makes_the_voice_the_sounds_plays_them_and_asks_about_the_copy_last(rig):
    code, io = rig.run("--round", "chosen", answers=["yes", "yes", "yes"])
    assert code == 0 and rig.made() == [FOLDER_2]
    assert io.prompts[0].strip() == "Make the sound files and play them now? Type yes to go on."
    assert io.prompts[1].strip() == "Did you hear them all? Type yes if you did."
    assert io.prompts[2].startswith("Remove the voice made for this (") and io.prompts[2].strip().endswith("The sound files stay. Type yes to remove it.")
    for stage in ("Making the voice from the saved point. This is the slow step.", "Preparing it for the phone.", "Getting the voice ready.", "Making the sounds. This takes a few seconds."):
        assert stage in io.lines
    assert io.lines.index("Making the voice from the saved point. This is the slow step.") < io.lines.index("Preparing it for the phone.") < io.lines.index("Getting the voice ready.")
    assert "Good. These sounds were made the way the phone makes them, with the same steps that make the zip file." in io.text
    assert "If it sounds right, choose this round with the rounds command, then make the voice file." in io.text and "copy the zip file" not in io.text


def test_a_yes_to_the_copy_removes_it_and_keeps_the_sounds(rig):
    _code, io = rig.run("--round", "chosen", answers=["yes", "yes", "yes"])
    folder = rig.folder_of(FOLDER_2)
    assert sorted(os.listdir(folder)) == ["clip-1.wav", "clip-2.wav", "clip-3.wav", "job.json", "tokens.txt"]
    assert "Removed. The sound files are still in " + str(folder) in io.text


@pytest.mark.parametrize("answer", ["no", "n", "", "maybe", "yes please"])
def test_any_answer_but_yes_keeps_the_copy_and_says_how_big_it_is(rig, answer):
    _code, io = rig.run("--round", "chosen", answers=["yes", "yes", answer])
    folder = rig.folder_of(FOLDER_2)
    assert "my_voice.onnx" in os.listdir(folder) and "my_voice.onnx.before-patch" in os.listdir(folder) and "my_voice.onnx.json" in os.listdir(folder)
    assert "Kept. The voice made for this is still in " + str(folder) + ", and takes " in io.text and "Removed." not in io.text


def test_nobody_to_ask_keeps_the_copy_whatever_was_said_before(rig):
    code, io = rig.run("--round", "chosen", "--yes", interactive=False)
    assert code == 0 and "Kept. The voice made for this is still in " in io.text and "my_voice.onnx" in os.listdir(rig.folder_of(FOLDER_2))
    assert io.prompts == []


def test_the_dash_dash_yes_answers_only_the_first_question_never_the_one_about_the_copy(rig):
    _code, io = rig.run("--round", "chosen", "--yes", answers=["yes", "no"])
    assert [p.strip()[:10] for p in io.prompts] == ["Did you he", "Remove the"] and "my_voice.onnx" in os.listdir(rig.folder_of(FOLDER_2))


def test_the_copy_question_is_asked_even_when_the_heard_answer_was_no(rig):
    _code, io = rig.run("--round", "chosen", "--yes", answers=["no", "yes"])
    assert len(io.prompts) == 2 and "my_voice.onnx" not in os.listdir(rig.folder_of(FOLDER_2))
    assert "The sound files are still in " in io.text and "Open one with any player" in io.text


def test_when_the_sounds_cannot_be_played_the_copy_is_still_asked_about_and_the_sounds_stay(tmp_path):
    rig = FlowRig(tmp_path, make=False, installed=())
    rig.finish_rounds(1)
    code, io = rig.run("--round", "chosen", "--yes", answers=["yes"])
    assert code == 1 and "No way of playing sound worked on this computer." in io.text
    assert io.prompts[0].startswith("Remove the voice made for this") and len([n for n in os.listdir(rig.folder_of("round-001-heard-20261011-120000")) if n.endswith(".wav")]) == 3


def test_every_clip_silent_still_asks_about_the_copy(tmp_path):
    rig = FlowRig(tmp_path, make=False, mode="silent")
    rig.finish_rounds(1)
    code, io = rig.run("--round", "chosen", "--yes", answers=["yes"])
    assert code == 1 and "Every sound came out silent" in io.text and io.prompts[0].startswith("Remove the voice made for this")


def test_a_round_by_number_is_listened_to_without_being_chosen(rig):
    code, io = rig.run("--round", "1", "--yes", answers=["yes", "yes"])
    assert code == 0 and rig.made() == ["round-001-heard-20261011-120000"] and "Round 1 would be heard like this:" in io.text
    assert rd.chosen(rd.load(rig.paths)).number == 2


@pytest.mark.parametrize("word", ["CHOSEN", " chosen ", "Chosen"])
def test_the_word_chosen_is_taken_in_any_case(rig, word):
    code, io = rig.run("--round", word, "--yes", answers=["yes", "no"])
    assert code == 0 and rig.made() == [FOLDER_2]


def test_spaces_around_a_round_number_are_ignored(rig):
    code, io = rig.run("--round", " 1 ", "--yes", answers=["yes", "no"])
    assert code == 0 and rig.made() == ["round-001-heard-20261011-120000"]


@pytest.mark.parametrize("word", ["x", "0", "-1", "1.5", "1e3", "", "٣", "9999999", "chosen2", "one"])
def test_a_round_that_is_not_a_number_or_the_word_chosen_is_not_understood_and_nothing_is_made(rig, word):
    code, io = rig.run("--round", word, "--yes")
    assert code == 2 and "I did not understand " in io.text and "Nothing was made." in io.text and rig.made() == [] and rig.system.maker.calls == [] and io.prompts == []


def test_a_round_number_that_does_not_exist_is_said_in_three_parts(rig):
    code, io = rig.run("--round", "9", "--yes")
    assert code == 1 and "There is no round with that number in this project." in io.text and "Look at the rounds with the rounds list command" in io.text and rig.made() == []


def test_folder_and_round_together_are_refused_before_anything_else(rig):
    code, io = rig.run("--round", "chosen", "--folder", "x", "--yes")
    assert code == 2 and "Give --folder or --round, not both." in io.text and rig.made() == [] and rig.system.maker.calls == []


def test_a_round_that_is_running_is_refused_with_the_make_commands_own_words(rig):
    plan = rig.world.begin()
    rd.attach_job(rig.paths, plan.number, rig.world.job_for(plan, "running").id)
    code, io = rig.run("--round", "chosen", "--yes")
    assert code == 1 and rig.made() == [] and rig.system.maker.calls == [] and "still" in io.text.lower()


def test_without_a_chosen_round_it_says_so_and_makes_nothing(tmp_path):
    rig = FlowRig(tmp_path, make=False)
    code, io = rig.run("--round", "chosen", "--yes")
    assert code == 1 and rig.made() == [] and rig.system.maker.calls == []


def test_a_failed_export_says_what_happened_where_the_folder_is_and_asks_nothing_more(tmp_path):
    rig = FlowRig(tmp_path, make=False, export="fail")
    rig.finish_rounds(1)
    code, io = rig.run("--round", "chosen", "--yes", answers=["yes", "yes"])
    folder = rig.folder_of("round-001-heard-20261011-120000")
    assert code == 1 and "What was made so far is in " + str(folder) + ". Nothing was deleted." in io.text and io.prompts == []
    assert "Making the sounds" not in io.text and "Removed" not in io.text and "Kept." not in io.text


def test_a_failed_patch_says_so_and_nothing_is_played(tmp_path):
    rig = FlowRig(tmp_path, make=False, patch="fail")
    rig.finish_rounds(1)
    code, io = rig.run("--round", "chosen", "--yes", answers=["yes"])
    assert code == 1 and rig.system.played == [] and "What was made so far is in " in io.text


def test_a_stop_while_the_voice_is_made_says_where_what_was_made_is(tmp_path):
    rig = FlowRig(tmp_path, make=False, export="interrupt")
    rig.finish_rounds(1)
    code, io = rig.run("--round", "chosen", "--yes", answers=["yes"])
    assert code == 1 and "Stopped. What was made so far is in " in io.text and "Nothing was deleted." in io.text and io.prompts == []


def test_a_voice_the_phone_would_refuse_is_said_in_three_parts_with_the_problem_listed(tmp_path):
    rig = FlowRig(tmp_path, make=False, patch="skipped")
    rig.finish_rounds(1)
    code, io = rig.run("--round", "chosen", "--yes", answers=["yes"])
    assert code == 1 and "The voice file is not ready for the phone, so it was not played." in io.text and rig.system.played == []


def test_a_settings_file_that_gives_no_list_of_sounds_is_said_before_anything_is_asked(rig):
    Path(rig.paths.round_configs + "/round-002.json").write_text("not json")
    code, io = rig.run("--round", "chosen", "--yes")
    assert code == 1 and rig.made() == [] and rig.system.maker.calls == [] and io.prompts == []


def test_a_round_run_changes_no_round_record(rig):
    before = tree_of(rig.paths.rounds)
    contents = {p: Path(p).read_bytes() for p in before}
    rig.run("--round", "chosen", "--yes", answers=["yes", "yes"])
    assert tree_of(rig.paths.rounds) == before and {p: Path(p).read_bytes() for p in before} == contents


def test_a_round_run_with_hearing_writes_down_the_sentences_and_still_asks_about_the_copy_last(rig):
    rig.set_heard(SENTENCES)
    code, io = rig.run("--round", "chosen", "--yes", answers=["yes", "yes"], speech="ready")
    assert code == 0 and io.text.count("The same words.") == 3 and rig.heard_ran()
    assert io.lines.index("Writing down what the computer hears in them. This takes up to a minute.") > io.lines.index("Preparing it for the phone.")
    assert [p.strip()[:10] for p in io.prompts] == ["Did you he", "Remove the"] and "my_voice.onnx" not in os.listdir(rig.folder_of(FOLDER_2))


def test_the_listing_of_voice_files_and_an_earlier_voice_file_are_unaffected(tmp_path):
    rig = FlowRig(tmp_path)
    rig.finish_rounds(1)
    before = tree_of(rig.paths.exports)
    code, io = rig.run("--round", "chosen", "--yes", answers=["yes", "yes"])
    assert code == 0 and tree_of(rig.paths.exports) == before
