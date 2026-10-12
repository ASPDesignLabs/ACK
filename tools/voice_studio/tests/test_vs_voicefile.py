# SPDX-License-Identifier: GPL-3.0-or-later
"""Making the voice file from the chosen round (plan task VS-5.2): what is refused before anything is written, the five steps in order inside one new folder, and that a failed
step leaves what was made as it is. The programs that make the voice are stood in for by a fake that writes what they write, so the real checks of the zip run."""
import os
import zipfile
from datetime import timedelta

import pytest

from vs_rounds_helpers import NOW, make_world, slurp, stamp
from vs_voicefile_helpers import MakerSystem, TOOLS, finished_rounds, tree_of, write_settings
from vs_voice_helpers import PATCHED, onnx_bytes, piper_config
from voice_studio.core import commands, rounds as rd, voicefile as vf, voicezip
from voice_studio.core.diskbudget import DEFAULT_TABLE, Level, floors_for

STAMP = "2026-10-11T13:00:00Z"


@pytest.fixture()
def world(tmp_path):
    return make_world(tmp_path)


def plan_for(world, free=500 * 2**30, record=None, stamp_text=STAMP):
    return vf.plan_voice(world.paths, rd.load(world.paths) if record is None else record, "voice-check", stamp_text, free)


def code_of(fn, *a, **kw):
    with pytest.raises(vf.VoiceFileError) as caught:
        fn(*a, **kw)
    return caught.value.code


def make(world, plan=None, system=None, stages=None):
    plan = plan or plan_for(world)
    system = system or MakerSystem()
    return vf.make_voice(plan, world.training, str(TOOLS), system, stages.append if stages is not None else None), system


# ---------------------------------------------------------------- the plan

def test_the_plan_names_the_chosen_rounds_saved_point_its_own_settings_file_and_one_new_folder(world):
    finished_rounds(world, 3)
    plan = plan_for(world)
    assert plan.round == 3 and plan.checkpoint == "%s/lightning_logs/version_2/checkpoints/last.ckpt" % world.paths.run and plan.checkpoint_bytes == os.stat(plan.checkpoint).st_size
    assert plan.settings == world.paths.round_configs + "/round-003.json"
    assert plan.folder == world.paths.exports + "/voice-check-round-003-20261011-130000"
    assert plan.model == plan.folder + "/my_voice.onnx" and plan.model_config == plan.folder + "/my_voice.onnx.json"
    assert plan.zip_path == plan.folder + "/voice-check-round-003-20261011-130000.zip" and plan.trained_minutes == rd.trained_minutes(rd.load(world.paths), 3)
    assert not os.path.exists(plan.folder)


def test_after_going_back_the_plan_uses_the_round_that_was_gone_back_to_not_the_newest(world):
    finished_rounds(world, 3)
    rd.go_back(world.paths)
    plan = plan_for(world)
    assert plan.round == 2 and plan.checkpoint.endswith("version_1/checkpoints/last.ckpt") and plan.settings.endswith("round-002.json")


def test_planning_changes_nothing_on_the_disk(world):
    finished_rounds(world, 2)
    before = tree_of(world.paths.root)
    plan_for(world)
    assert tree_of(world.paths.root) == before


def test_with_no_round_chosen_nothing_is_planned_and_no_other_file_is_used(world):
    assert code_of(plan_for, world) == "no_chosen_round"
    world.run_round(version=0, ends="failed")
    write_settings(world.paths, 1)
    assert code_of(plan_for, world) == "no_chosen_round"


def test_while_a_round_is_running_nothing_is_planned(world):
    finished_rounds(world, 1)
    plan = world.begin()
    rd.attach_job(world.paths, plan.number, world.job_for(plan, "running").id)
    assert code_of(plan_for, world) == "round_running"


def test_a_chosen_round_whose_saved_point_is_gone_or_cut_short_is_refused_instead_of_using_another_file(world):
    finished_rounds(world, 2)
    checkpoint = plan_for(world).checkpoint
    data = slurp(checkpoint)
    with open(checkpoint, "wb") as handle:
        handle.write(data[: len(data) // 2])
    assert code_of(plan_for, world) == "saved_point_damaged"
    os.unlink(checkpoint)
    assert code_of(plan_for, world) == "saved_point_missing"


def test_a_round_without_a_settings_file_is_refused_and_a_link_is_not_a_settings_file(world, tmp_path):
    finished_rounds(world, 2, settings=False)
    assert code_of(plan_for, world) == "no_settings"
    elsewhere = tmp_path / "elsewhere.json"
    elsewhere.write_text("{}")
    os.makedirs(world.paths.round_configs, exist_ok=True)
    os.symlink(str(elsewhere), world.paths.round_configs + "/round-002.json")
    assert code_of(plan_for, world) == "no_settings"
    write_settings(world.paths, 1)                                                                  # round 1's file does not stand in for round 2's
    assert code_of(plan_for, world) == "no_settings"


def test_the_room_is_judged_against_the_most_that_could_be_written_with_the_recorders_floor(world):
    finished_rounds(world, 1)
    floors = floors_for(DEFAULT_TABLE, holds_recordings=True)
    enough = vf.NEED_BYTES + floors.low
    assert plan_for(world, free=enough).room is Level.ENOUGH
    assert plan_for(world, free=enough - 1).room is Level.TIGHT
    assert plan_for(world, free=vf.NEED_BYTES + floors.stop).room is Level.TIGHT
    assert code_of(plan_for, world, free=vf.NEED_BYTES + floors.stop - 1) == "no_room"
    assert plan_for(world, free=None).room is Level.ENOUGH and plan_for(world, free=None).free_bytes is None
    assert vf.NEED_BYTES == 3 * voicezip.MAX_MODEL_BYTES + 2 * voicezip.MAX_CONFIG_BYTES


@pytest.mark.parametrize("project, number, text", [("voice-check", 0, STAMP), ("voice-check", 1, "2026-10-11"), ("../x", 1, STAMP), ("", 1, STAMP), ("voice check", 1, STAMP)])
def test_the_folder_name_refuses_what_cannot_make_a_safe_one(project, number, text):
    with pytest.raises(commands.CommandError):
        vf.voice_folder_name(project, number, text)


def test_the_folder_name_is_the_project_the_round_and_the_time_to_the_second():
    assert vf.voice_folder_name("voice-check", 3, "2026-10-11T13:00:05Z") == "voice-check-round-003-20261011-130005"
    assert vf.voice_folder_name("a", 1234, "2026-01-02T03:04:05Z") == "a-round-1234-20260102-030405"


# ---------------------------------------------------------------- making it

def test_the_five_steps_run_in_order_and_everything_lands_in_the_one_new_folder(world):
    finished_rounds(world, 2)
    plan = plan_for(world)
    before = tree_of(world.paths.root)
    stages = []
    made, system = make(world, plan, stages=stages)
    assert stages == list(vf.STAGES) == ["export", "settings", "patch", "zip", "check"] and system.kinds() == ["export", "patch"]
    assert made.folder == plan.folder and made.zip_path == plan.zip_path and made.zip_bytes == os.stat(plan.zip_path).st_size
    new = [p for p in tree_of(world.paths.root) if p not in before]
    assert sorted(os.path.basename(p) for p in new) == sorted(["my_voice.onnx", "my_voice.onnx.json", "my_voice.onnx.before-patch", os.path.basename(plan.zip_path)])
    assert all(p.startswith(plan.folder + "/") for p in new) and all(p in tree_of(world.paths.root) for p in before)


def test_nothing_that_was_there_before_is_changed_or_removed(world):
    finished_rounds(world, 2)
    before = {p: slurp(p) for p in tree_of(world.paths.root)}
    make(world)
    assert all(os.path.exists(p) and slurp(p) == data for p, data in before.items())


def test_the_programs_are_given_the_saved_point_the_folder_and_the_patchers_own_script(world):
    finished_rounds(world, 2)
    plan = plan_for(world)
    _made, system = make(world, plan)
    (_k, export, export_timeout, export_cwd), (_k2, patch, patch_timeout, patch_cwd) = system.calls
    assert export[:3] == (world.training.python, world.training.launcher, "piper.train.export_onnx") and export[export.index("--checkpoint") + 1] == plan.checkpoint
    assert export[export.index("--output-file") + 1] == plan.model and export_cwd == plan.folder and export_timeout == vf.EXPORT_TIMEOUT_S
    assert patch == (world.training.python, str(TOOLS) + "/patch_voice_for_sherpa_onnx.py", plan.model, plan.model_config) and patch_cwd == plan.folder
    assert patch_timeout == vf.PATCH_TIMEOUT_S


def test_the_settings_file_is_a_copy_of_that_rounds_own_and_the_original_is_kept_beside_the_patched_voice(world):
    finished_rounds(world, 2)
    own = piper_config()
    own["audio"]["quality"] = "x_low_for_this_round_only"
    write_settings(world.paths, 2, own)
    write_settings(world.paths, 1, piper_config())
    plan = plan_for(world)
    make(world, plan)
    assert slurp(plan.model_config) == slurp(plan.settings) and b"x_low_for_this_round_only" in slurp(plan.model_config)
    assert slurp(plan.model + ".before-patch") == onnx_bytes({}) and slurp(plan.model) == onnx_bytes(PATCHED)


def test_the_zip_holds_exactly_the_two_files_the_phone_looks_for_and_passes_the_phones_checks(world):
    finished_rounds(world, 2)
    made, _ = make(world)
    with zipfile.ZipFile(made.zip_path) as archive:
        assert archive.namelist() == ["model.onnx", "model.onnx.json"]
        assert archive.read("model.onnx") == slurp(made.model) and archive.read("model.onnx.json") == slurp(made.model_config)
    assert voicezip.verify_voice_zip(__import__("pathlib").Path(made.zip_path)) == ()
    assert len(made.model_sha256) == 64 and len(made.config_sha256) == 64


def test_the_new_folder_is_private_to_the_person(world):
    finished_rounds(world, 1)
    made, _ = make(world)
    assert os.stat(made.folder).st_mode & 0o777 == 0o700 and os.stat(made.zip_path).st_mode & 0o077 == 0


def test_the_same_second_never_lands_in_an_earlier_folder_and_the_earlier_one_is_untouched(world):
    finished_rounds(world, 1)
    made, _ = make(world)
    before = {p: slurp(p) for p in tree_of(made.folder)}
    with pytest.raises(vf.VoiceFileError) as caught:
        make(world, plan_for(world))
    assert caught.value.code == "exists" and caught.value.folder == ""
    assert {p: slurp(p) for p in tree_of(made.folder)} == before
    later = vf.make_voice(plan_for(world, stamp_text="2026-10-11T13:00:01Z"), world.training, str(TOOLS), MakerSystem())
    assert later.folder != made.folder and os.path.isfile(later.zip_path)


# ---------------------------------------------------------------- when a step fails the folder is left as it is

@pytest.mark.parametrize("how", ["fail", "none", "nothing_written", "wrote_then_failed"])
def test_a_failed_export_says_so_and_leaves_the_new_folder_and_changes_nothing_else(world, how):
    finished_rounds(world, 2)
    before = tree_of(world.paths.root)
    plan = plan_for(world)
    system = MakerSystem(export={"fail": "fail", "none": "none", "nothing_written": "silent", "wrote_then_failed": "wrote_then_failed"}[how])
    with pytest.raises(vf.VoiceFileError) as caught:
        vf.make_voice(plan, world.training, str(TOOLS), system)
    error = caught.value
    assert error.code == "export_failed" and error.folder == plan.folder and error.stage == "export" and os.path.isdir(plan.folder)
    assert sorted(os.listdir(plan.folder)) == (["my_voice.onnx"] if how == "wrote_then_failed" else []) and system.kinds() == ["export"]
    assert [p for p in tree_of(world.paths.root) if p not in before] == ([plan.model] if how == "wrote_then_failed" else [])
    if how == "fail":
        assert "GuardOnDataDependentSymNode: boom" in error.detail


@pytest.mark.parametrize("how", ["fail", "none"])
def test_a_failed_patch_leaves_the_voice_and_its_settings_file_where_they_are_and_makes_no_zip(world, how):
    finished_rounds(world, 2)
    plan = plan_for(world)
    system = MakerSystem(patch=how)
    with pytest.raises(vf.VoiceFileError) as caught:
        vf.make_voice(plan, world.training, str(TOOLS), system)
    assert caught.value.code == "patch_failed" and caught.value.stage == "patch" and ("onnx is not installed" in caught.value.detail) == (how == "fail")
    assert sorted(os.listdir(plan.folder)) == ["my_voice.onnx", "my_voice.onnx.json"] and slurp(plan.model) == onnx_bytes({})


def test_a_voice_that_was_not_prepared_is_refused_by_the_zip_check_and_no_zip_is_left(world):
    finished_rounds(world, 2)
    plan = plan_for(world)
    with pytest.raises(voicezip.VoiceZipError) as caught:
        vf.make_voice(plan, world.training, str(TOOLS), MakerSystem(patch="silent"))
    assert caught.value.code == "not_ready" and "not_patched" in caught.value.problems
    assert sorted(os.listdir(plan.folder)) == ["my_voice.onnx", "my_voice.onnx.json"]


def test_a_zip_that_fails_the_read_back_is_reported_and_left_where_it_is(world, monkeypatch):
    finished_rounds(world, 1)
    plan = plan_for(world)
    monkeypatch.setattr(voicezip, "verify_voice_zip", lambda path: ("zip_unreadable", "zip_wrong_entries"))
    with pytest.raises(vf.VoiceFileError) as caught:
        vf.make_voice(plan, world.training, str(TOOLS), MakerSystem())
    assert caught.value.code == "zip_not_ok" and caught.value.detail == "zip_unreadable,zip_wrong_entries" and caught.value.stage == "check" and os.path.isfile(plan.zip_path)


def test_stopping_with_ctrl_c_during_the_export_leaves_the_new_folder_and_nothing_else_changed(world):
    finished_rounds(world, 2)
    before = tree_of(world.paths.root)
    plan = plan_for(world)
    with pytest.raises(KeyboardInterrupt):
        vf.make_voice(plan, world.training, str(TOOLS), MakerSystem(export="interrupt"))
    assert tree_of(world.paths.root) == before and os.path.isdir(plan.folder)


def test_the_last_lines_a_program_said_are_kept_for_the_details_and_no_more_than_fit():
    from voice_studio.core.system import CommandResult
    many = CommandResult(1, "", "\n".join("line %d" % n for n in range(30)))
    tail = vf._tail(many)
    assert tail.endswith("line 29") and tail.startswith("line 24") and tail.count(" | ") == vf.TAIL_LINES - 1
    assert len(vf._tail(CommandResult(1, "x" * 5000, ""))) == vf.TAIL_CHARS and vf._tail(None) == "" and vf._tail(CommandResult(0, "\n \n", "")) == ""
    long = vf._tail(CommandResult(1, "y" * 500 + "\n" + "z" * 500 + "END", ""))
    assert long.endswith("zzzEND") and len(long) == vf.TAIL_CHARS                                    # when it is cut, it is the end that is kept: that is where the error is
    assert vf._tail(CommandResult(1, "out\n", "err\n")) == "err | out"


# ---------------------------------------------------------------- what was made before

def test_the_voice_files_made_before_are_the_zips_that_sit_in_a_folder_of_the_same_name(world, tmp_path):
    finished_rounds(world, 1)
    assert vf.existing_voice_files(world.paths) == ()
    made, _ = make(world)
    os.makedirs(world.paths.exports + "/not-ours")
    open(world.paths.exports + "/not-ours/other.zip", "wb").close()
    open(world.paths.exports + "/loose.zip", "wb").close()
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (elsewhere / "linked.zip").write_bytes(b"not ours")
    os.symlink(str(elsewhere), world.paths.exports + "/linked")                                  # a link to a folder that holds a zip of the right name
    os.makedirs(world.paths.exports + "/real")
    os.symlink(str(elsewhere / "linked.zip"), world.paths.exports + "/real/real.zip")           # a real folder whose zip is a link
    assert vf.existing_voice_files(world.paths) == ((os.path.basename(made.folder), made.zip_path, made.zip_bytes),)
