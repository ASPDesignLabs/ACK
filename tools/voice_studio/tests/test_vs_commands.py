# SPDX-License-Identifier: GPL-3.0-or-later
"""The commands for each step (plan tasks VS-2.5, VS-2.6, VS-2.7): the guide's rules, enforced before a job can start."""
import os
import stat
from pathlib import Path

import pytest

from voice_studio.core import commands as cm
from voice_studio.core.envbuild import EnvPaths
from voice_studio.core.jobs import JobSpec, _check_spec

STUDIO, TRAINING = EnvPaths("/data/environments/studio-abc"), EnvPaths("/data/environments/training-def")
TOOLS = "/home/user/ack-tools/tools"


def code_of(fn, *a, **kw):
    with pytest.raises(cm.CommandError) as caught:
        fn(*a, **kw)
    return caught.value.code


def make_dataset(tmp_path, names=("a.wav", "b.wav"), name="dataset-20261010-120000"):
    folder = tmp_path / name
    (folder / "wav").mkdir(parents=True)
    for n in names:
        (folder / "wav" / n).write_bytes(b"RIFFxxxx")
    (folder / "metadata.csv").write_text("".join("%s|text %s\n" % (n, n) for n in names))
    return folder


def make_checkpoint(tmp_path, name="base.ckpt"):
    path = tmp_path / name
    path.write_bytes(b"ckpt")
    return path


# ---------------------------------------------------------------- finishing the recordings

def test_the_process_command_runs_freeform_studios_processor_with_the_studio_environments_python():
    c = cm.process_command(STUDIO, TOOLS, "/p/anna/recordings", "/data/models/small-en")
    assert c.argv == (STUDIO.python, "-m", "freeform_studio.process", "--output", "/p/anna/recordings", "--code", "en-US", "--asr-model", "/data/models/small-en",
                      "--asr-device", "cpu", "--json")
    assert c.kind == "process" and c.cwd == TOOLS and c.gpu is False


def test_the_processor_holds_the_graphics_card_only_when_it_is_asked_to_use_it():
    assert cm.process_command(STUDIO, TOOLS, "/p/r", "m", "cuda").gpu is True
    assert cm.process_command(STUDIO, TOOLS, "/p/r", "m", "cpu").gpu is False
    assert code_of(cm.process_command, STUDIO, TOOLS, "/p/r", "m", "tpu") == "bad_value"


def test_the_device_that_was_asked_for_is_the_device_named_in_the_command():
    assert cm.process_command(STUDIO, TOOLS, "/p/r", "m", "cuda").argv[-2:-1] == ("cuda",)
    assert cm.process_command(STUDIO, TOOLS, "/p/r", "m", "cpu").argv[-2:-1] == ("cpu",)


def test_a_path_is_written_in_its_plain_form_so_two_spellings_of_one_folder_make_one_command():
    c = cm.process_command(STUDIO, TOOLS + "/", "/p/anna//recordings/../recordings/", "m")
    assert c.argv[c.argv.index("--output") + 1] == "/p/anna/recordings" and c.cwd == TOOLS
    d = cm.dataset_command(STUDIO, TOOLS, "/p/./r", "/p/a/../out", dry_run=True)
    assert d.argv[d.argv.index("--out") + 1] == "/p/out" and d.argv[d.argv.index("--output") + 1] == "/p/r"


@pytest.mark.parametrize("recordings", ["relative/path", "", "recordings", "~/recordings", "/p/r\nrm -rf /", "/p/r\x00"])
def test_a_recordings_path_that_is_not_an_absolute_plain_path_is_refused(recordings):
    assert code_of(cm.process_command, STUDIO, TOOLS, recordings, "m") == "bad_path"


# ---------------------------------------------------------------- the dataset

def test_a_new_dataset_folder_is_built_with_the_json_result_and_a_preview_writes_nothing(tmp_path):
    out = str(tmp_path / "datasets" / "dataset-20261010-120000")
    build = cm.dataset_command(STUDIO, TOOLS, "/p/anna/recordings", out)
    assert build.argv == (STUDIO.python, "-m", "freeform_studio.build_dataset", "--output", "/p/anna/recordings", "--code", "en-US", "--out", out, "--json")
    preview = cm.dataset_command(STUDIO, TOOLS, "/p/anna/recordings", out, dry_run=True)
    assert preview.argv == build.argv + ("--dry-run",) and build.kind == preview.kind == "dataset" and not build.gpu


def test_a_dataset_folder_that_already_holds_anything_is_refused_before_a_job_starts(tmp_path):
    out = tmp_path / "ds"
    out.mkdir()
    cm.dataset_command(STUDIO, TOOLS, "/p/r", str(out))                                    # empty: fine
    (out / "keep.txt").write_text("mine")
    assert code_of(cm.dataset_command, STUDIO, TOOLS, "/p/r", str(out)) == "exists"
    cm.dataset_command(STUDIO, TOOLS, "/p/r", str(out), dry_run=True)                       # a preview writes nothing, so it may look at an existing folder
    file_in_the_way = tmp_path / "ds2"
    file_in_the_way.write_text("x")
    assert code_of(cm.dataset_command, STUDIO, TOOLS, "/p/r", str(file_in_the_way)) == "exists"


def test_a_gain_limit_the_person_chose_is_passed_on_and_none_means_freeform_studios_own(tmp_path):
    base = cm.dataset_command(STUDIO, TOOLS, "/p/r", str(tmp_path / "d1"))
    assert "--max-gain-db" not in base.argv, "nothing is added unless the person chose a limit"
    for value, text in ((36, "36"), (36.0, "36"), (12.5, "12.5"), (0, "0"), (60, "60")):
        c = cm.dataset_command(STUDIO, TOOLS, "/p/r", str(tmp_path / "d2"), max_gain_db=value)
        assert c.argv[-2:] == ("--max-gain-db", text)
    preview = cm.dataset_command(STUDIO, TOOLS, "/p/r", str(tmp_path / "d3"), dry_run=True, max_gain_db=24)
    assert preview.argv[-3:] == ("--max-gain-db", "24", "--dry-run")


@pytest.mark.parametrize("bad", [-1, -0.01, 60.01, 100, float("nan"), float("inf"), True, "36", [36]])
def test_a_gain_limit_that_is_not_a_sensible_number_of_decibels_is_refused_before_a_job_starts(tmp_path, bad):
    assert code_of(cm.dataset_command, STUDIO, TOOLS, "/p/r", str(tmp_path / "d"), max_gain_db=bad) == "bad_value"


def test_each_dataset_gets_a_new_name_from_the_time():
    assert cm.dataset_folder_name("2026-10-10T12:00:00Z") == "dataset-20261010-120000"
    assert cm.dataset_folder_name("2026-10-10T12:00:01Z") != cm.dataset_folder_name("2026-10-10T12:00:00Z")
    assert code_of(cm.dataset_folder_name, "2026") == "bad_value"
    assert code_of(cm.dataset_folder_name, "2026-10-10T12:00:0") == "bad_value", "13 digits is one short of a whole second"
    assert cm.dataset_folder_name("20261010120000") == "dataset-20261010-120000"
    assert cm.dataset_folder_name("2026-10-10T12:00:00.123456Z") == "dataset-20261010-120000", "digits after the second are not part of the name"


def test_a_finished_dataset_is_counted_and_an_incomplete_one_is_named(tmp_path):
    assert cm.check_dataset(str(make_dataset(tmp_path))) == 2
    broken = make_dataset(tmp_path, name="b")
    (broken / "wav" / "b.wav").unlink()
    assert code_of(cm.check_dataset, str(broken)) == "dataset_incomplete"
    assert code_of(cm.check_dataset, str(tmp_path / "nope")) == "dataset_incomplete"
    empty = tmp_path / "empty"
    (empty / "wav").mkdir(parents=True)
    (empty / "metadata.csv").write_text("\n\n")
    assert code_of(cm.check_dataset, str(empty)) == "dataset_incomplete"
    nested = make_dataset(tmp_path, name="n")
    (nested / "metadata.csv").write_text("sub/a.wav|text\n")
    assert code_of(cm.check_dataset, str(nested)) == "dataset_incomplete", "a row may not name a file outside the wav folder"
    noname = make_dataset(tmp_path, name="z")
    (noname / "metadata.csv").write_text("|text\n")
    assert code_of(cm.check_dataset, str(noname)) == "dataset_incomplete"


def test_an_incomplete_dataset_is_named_by_what_is_missing_never_by_a_crash(tmp_path):
    no_meta = make_dataset(tmp_path, name="m")
    (no_meta / "metadata.csv").unlink()
    with pytest.raises(cm.CommandError) as caught:
        cm.check_dataset(str(no_meta))
    assert caught.value.code == "dataset_incomplete" and caught.value.detail == "m"
    no_wav = make_dataset(tmp_path, name="w")
    for f in (no_wav / "wav").iterdir():
        f.unlink()
    (no_wav / "wav").rmdir()
    with pytest.raises(cm.CommandError) as caught:
        cm.check_dataset(str(no_wav))
    assert caught.value.code == "dataset_incomplete" and caught.value.detail == "w", "a missing wav folder is named as such, not as its first file"
    noname = make_dataset(tmp_path, name="z")
    (noname / "metadata.csv").write_text("|text\n")
    with pytest.raises(cm.CommandError) as caught:
        cm.check_dataset(str(noname))
    assert caught.value.detail == "empty name"


def test_blank_lines_in_the_list_of_recordings_are_not_rows_and_do_not_spoil_it(tmp_path):
    d = make_dataset(tmp_path, name="blank")
    (d / "metadata.csv").write_text("\na.wav|one\n\n   \nb.wav|two\n\n")
    assert cm.check_dataset(str(d)) == 2


def test_a_file_in_a_folder_inside_the_wav_folder_is_not_where_the_trainer_looks(tmp_path):
    d = make_dataset(tmp_path, name="deep")
    (d / "wav" / "sub").mkdir()
    (d / "wav" / "sub" / "a.wav").write_bytes(b"RIFFxxxx")
    (d / "metadata.csv").write_text("sub/a.wav|text\n")
    with pytest.raises(cm.CommandError) as caught:
        cm.check_dataset(str(d))
    assert caught.value.code == "dataset_incomplete" and caught.value.detail == "sub/a.wav"


# ---------------------------------------------------------------- one round

def train(tmp_path, **kw):
    dataset = make_dataset(tmp_path)
    return cm.train_command(TRAINING, str(dataset), str(tmp_path / "run"), str(tmp_path / "cache-dataset-20261010-120000"), str(tmp_path / "config.json"),
                            str(make_checkpoint(tmp_path)), **kw), dataset


def test_a_round_is_the_guides_command_with_the_environments_launcher_and_a_time_limit(tmp_path):
    c, dataset = train(tmp_path)
    assert c.argv[:4] == (TRAINING.python, TRAINING.launcher, "piper.train", "fit")
    pairs = dict(zip(c.argv[4::2], c.argv[5::2]))
    assert pairs == {
        "--data.voice_name": "my_voice", "--data.csv_path": str(dataset) + "/metadata.csv", "--data.audio_dir": str(dataset) + "/wav", "--model.sample_rate": "22050", "--model.mos_metric": "none",
        "--data.espeak_voice": "en-us", "--data.cache_dir": str(tmp_path / "cache-dataset-20261010-120000"), "--data.config_path": str(tmp_path / "config.json"),
        "--data.batch_size": "12", "--data.num_workers": "4", "--trainer.check_val_every_n_epoch": "10", "--trainer.log_every_n_steps": "1",
        "--trainer.max_time": "00:00:25:00", "--ckpt_path": str(tmp_path / "base.ckpt")}
    assert c.kind == "train" and c.gpu is True and c.cwd == str(tmp_path / "run")


def test_the_quality_score_that_fetches_code_from_the_internet_is_always_turned_off(tmp_path):
    c, _ = train(tmp_path)
    assert c.argv[c.argv.index("--model.mos_metric") + 1] == "none" and c.argv.count("--model.mos_metric") == 1


def test_the_audio_folder_is_exactly_the_datasets_wav_folder(tmp_path):
    c, dataset = train(tmp_path)
    assert c.argv[c.argv.index("--data.audio_dir") + 1] == str(dataset) + "/wav"


@pytest.mark.parametrize("minutes, expected", [(1, "00:00:01:00"), (59, "00:00:59:00"), (60, "00:01:00:00"), (61, "00:01:01:00"), (150, "00:02:30:00")])
def test_the_round_length_is_written_the_way_the_trainer_reads_a_time_limit(tmp_path, minutes, expected):
    c, _ = train(tmp_path, minutes=minutes)
    assert c.argv[c.argv.index("--trainer.max_time") + 1] == expected


def test_the_settings_can_be_changed_for_a_bigger_card(tmp_path):
    c, _ = train(tmp_path, batch_size=16, workers=2, check_every=5)
    pairs = dict(zip(c.argv[4::2], c.argv[5::2]))
    assert (pairs["--data.batch_size"], pairs["--data.num_workers"], pairs["--trainer.check_val_every_n_epoch"]) == ("16", "2", "5")


@pytest.mark.parametrize("name, value", [("minutes", 0), ("minutes", -5), ("minutes", 1.5), ("minutes", True), ("batch_size", 0), ("workers", 0), ("check_every", 0), ("batch_size", "12")])
def test_a_setting_that_is_not_a_whole_positive_number_is_refused(tmp_path, name, value):
    dataset = make_dataset(tmp_path)
    kw = {name: value}
    assert code_of(cm.train_command, TRAINING, str(dataset), str(tmp_path / "r"), str(tmp_path / "c"), str(tmp_path / "cfg"), str(make_checkpoint(tmp_path)), **kw) == "bad_value"


def test_an_old_cache_folder_is_never_reused(tmp_path):
    dataset = make_dataset(tmp_path)
    cache = tmp_path / "cache"
    cache.mkdir()
    ckpt = make_checkpoint(tmp_path)
    assert code_of(cm.train_command, TRAINING, str(dataset), str(tmp_path / "r"), str(cache), str(tmp_path / "cfg"), str(ckpt)) == "cache_exists"
    file_in_the_way = tmp_path / "cachefile"
    file_in_the_way.write_text("x")
    assert code_of(cm.train_command, TRAINING, str(dataset), str(tmp_path / "r"), str(file_in_the_way), str(tmp_path / "cfg"), str(ckpt)) == "cache_exists"


def test_training_refuses_an_incomplete_dataset(tmp_path):
    dataset = make_dataset(tmp_path)
    (dataset / "wav" / "a.wav").unlink()
    assert code_of(cm.train_command, TRAINING, str(dataset), str(tmp_path / "r"), str(tmp_path / "c"), str(tmp_path / "cfg"), str(make_checkpoint(tmp_path))) == "dataset_incomplete"


@pytest.mark.parametrize("name", ["base.pt", "base.ckpt.bak", "base", "last.CKPT"])
def test_training_starts_only_from_a_ckpt_file_that_is_there(tmp_path, name):
    dataset = make_dataset(tmp_path)
    path = tmp_path / name
    path.write_bytes(b"x")
    assert code_of(cm.train_command, TRAINING, str(dataset), str(tmp_path / "r"), str(tmp_path / "c"), str(tmp_path / "cfg"), str(path)) == "bad_checkpoint"
    assert code_of(cm.train_command, TRAINING, str(dataset), str(tmp_path / "r"), str(tmp_path / "c"), str(tmp_path / "cfg"), str(tmp_path / "gone.ckpt")) == "bad_checkpoint"


def test_every_path_must_be_absolute(tmp_path):
    dataset = make_dataset(tmp_path)
    ckpt = str(make_checkpoint(tmp_path))
    for index, bad in enumerate(["rel", "rel", "rel", "rel", "rel"]):
        args = [str(dataset), str(tmp_path / "r"), str(tmp_path / "c"), str(tmp_path / "cfg"), ckpt]
        args[index] = bad
        assert code_of(cm.train_command, TRAINING, *args) == "bad_path", index


# ---------------------------------------------------------------- the checkpoints a round leaves behind

def write_version(run, number, data=b"x" * 10):
    folder = run / "lightning_logs" / ("version_%d" % number) / "checkpoints"
    folder.mkdir(parents=True)
    (folder / "last.ckpt").write_bytes(data)
    return folder / "last.ckpt"


def test_the_latest_checkpoint_is_the_highest_version_not_the_newest_file(tmp_path):
    run = tmp_path / "run"
    a, b, c = write_version(run, 0), write_version(run, 2, b"y" * 20), write_version(run, 10, b"z" * 30)
    os.utime(b, (9_999_999_999, 9_999_999_999))                                    # touching an older version must not make it "latest"
    found = cm.find_checkpoints(str(run))
    assert [x.version for x in found] == [0, 2, 10] and [x.path for x in found] == [str(a), str(b), str(c)] and found[2].size == 30
    assert cm.latest_checkpoint(str(run)).path == str(c)


def test_versions_without_a_last_checkpoint_or_with_other_names_are_not_listed(tmp_path):
    run = tmp_path / "run"
    write_version(run, 1)
    (run / "lightning_logs" / "version_2" / "checkpoints").mkdir(parents=True)                       # a round that stopped before saving
    (run / "lightning_logs" / "version_x" / "checkpoints").mkdir(parents=True)
    (run / "lightning_logs" / "version_x" / "checkpoints" / "last.ckpt").write_bytes(b"x")
    (run / "lightning_logs" / "other").mkdir()
    (run / "lightning_logs" / "version_3").write_bytes(b"a file, not a folder")
    assert [x.version for x in cm.find_checkpoints(str(run))] == [1]


def test_a_folder_whose_name_only_starts_like_a_version_is_not_one(tmp_path):
    run = tmp_path / "run"
    write_version(run, 1)
    for name in ("version_2_old", "version_3.bak", "version_4x"):
        (run / "lightning_logs" / name / "checkpoints").mkdir(parents=True)
        (run / "lightning_logs" / name / "checkpoints" / "last.ckpt").write_bytes(b"x")
    assert [x.version for x in cm.find_checkpoints(str(run))] == [1] and cm.latest_checkpoint(str(run)).version == 1


def test_no_run_folder_or_no_logs_means_no_checkpoint(tmp_path):
    assert cm.find_checkpoints(str(tmp_path / "nope")) == [] and cm.latest_checkpoint(str(tmp_path / "nope")) is None
    (tmp_path / "empty").mkdir()
    assert cm.latest_checkpoint(str(tmp_path / "empty")) is None


# ---------------------------------------------------------------- listening: export, the settings file, the patch

def test_export_uses_the_environments_launcher_and_a_new_model_file(tmp_path):
    ckpt = make_checkpoint(tmp_path, "last.ckpt")
    out = tmp_path / "export"
    out.mkdir()
    c = cm.export_command(TRAINING, str(ckpt), str(out))
    assert c.argv == (TRAINING.python, TRAINING.launcher, "piper.train.export_onnx", "--checkpoint", str(ckpt), "--output-file", str(out / "my_voice.onnx"))
    assert c.kind == "export" and c.cwd == str(out) and not c.gpu


def test_export_never_replaces_a_model_that_is_there_and_wants_a_ckpt_and_a_safe_name(tmp_path):
    ckpt = make_checkpoint(tmp_path, "last.ckpt")
    out = tmp_path / "export"
    out.mkdir()
    (out / "my_voice.onnx").write_bytes(b"earlier")
    assert code_of(cm.export_command, TRAINING, str(ckpt), str(out)) == "exists"
    assert code_of(cm.export_command, TRAINING, str(tmp_path / "gone.ckpt"), str(out), "other") == "bad_checkpoint"
    for bad in ("../x", "a b", "", "a/b", "-x"):
        assert code_of(cm.export_command, TRAINING, str(ckpt), str(out), bad) == "bad_value", bad


def test_export_starts_only_from_a_ckpt_file_and_not_over_a_link_that_leads_nowhere(tmp_path):
    out = tmp_path / "export"
    out.mkdir()
    not_ckpt = make_checkpoint(tmp_path, "last.pt")
    assert code_of(cm.export_command, TRAINING, str(not_ckpt), str(out)) == "bad_checkpoint", "a file that is there but is not a checkpoint"
    ckpt = make_checkpoint(tmp_path, "last.ckpt")
    (out / "my_voice.onnx").symlink_to(tmp_path / "nowhere")
    assert code_of(cm.export_command, TRAINING, str(ckpt), str(out)) == "exists", "a dangling link is still something in the way"


def test_the_settings_file_is_named_exactly_like_the_model_plus_json():
    assert cm.config_name("/e/my_voice.onnx") == "/e/my_voice.onnx.json"
    assert code_of(cm.config_name, "/e/my_voice.bin") == "bad_path"


def test_the_settings_file_is_copied_next_to_the_model_owner_only_and_never_over_another(tmp_path):
    config = tmp_path / "config.json"
    config.write_text('{"audio": {}}')
    model = tmp_path / "export" / "my_voice.onnx"
    model.parent.mkdir()
    target = cm.copy_config(str(config), str(model))
    assert target == str(model) + ".json" and Path(target).read_text() == config.read_text() and stat.S_IMODE(os.stat(target).st_mode) == 0o600
    assert sorted(os.listdir(model.parent)) == ["my_voice.onnx.json"] and config.exists()
    with pytest.raises(cm.CommandError) as caught:
        cm.copy_config(str(config), str(model))
    assert caught.value.code == "exists" and Path(target).read_text() == '{"audio": {}}'


def test_a_missing_settings_file_is_named(tmp_path):
    assert code_of(cm.copy_config, str(tmp_path / "nope.json"), str(tmp_path / "m.onnx")) == "bad_path"


def test_the_patch_runs_the_repositorys_own_script_on_the_model_and_its_settings_file(tmp_path):
    tools = tmp_path / "tools"
    tools.mkdir()
    (tools / "patch_voice_for_sherpa_onnx.py").write_text("# the script")
    model = tmp_path / "export" / "my_voice.onnx"
    c = cm.patch_command("/env/venv/bin/python", str(tools), str(model))
    assert c.argv == ("/env/venv/bin/python", str(tools / "patch_voice_for_sherpa_onnx.py"), str(model), str(model) + ".json")
    assert c.kind == "patch" and c.cwd == str(model.parent)
    assert code_of(cm.patch_command, "/env/venv/bin/python", str(tmp_path / "elsewhere"), str(model)) == "bad_path"


def test_the_real_patch_script_is_where_the_command_expects_it():
    tools = Path(__file__).resolve().parents[2]
    assert (tools / "patch_voice_for_sherpa_onnx.py").is_file()
    assert cm.patch_command("/p", str(tools), "/m/my_voice.onnx").argv[1].endswith("tools/patch_voice_for_sherpa_onnx.py")


# ---------------------------------------------------------------- handing a command to the job supervisor

def test_a_command_becomes_a_job_the_supervisor_accepts(tmp_path):
    c = cm.process_command(STUDIO, str(tmp_path), "/p/r", "m")
    spec = c.job("anna")
    assert isinstance(spec, JobSpec) and (spec.kind, spec.project, spec.argv, spec.cwd, spec.gpu, spec.force_grace_s) == ("process", "anna", c.argv, str(tmp_path), False, 10.0)
    _check_spec(spec)
    for kind in ("process", "dataset", "train", "export", "patch"):
        _check_spec(JobSpec(kind, "anna", ("/x/python", "a"), str(tmp_path), {}, False, 10.0))


def test_a_training_round_becomes_a_graphics_card_job_with_its_own_grace_time(tmp_path):
    c, _ = train(tmp_path)
    (tmp_path / "run").mkdir()
    spec = c.job("anna", force_grace_s=30.0)
    assert spec.gpu is True and spec.force_grace_s == 30.0 and spec.kind == "train"
    _check_spec(spec)


def test_the_job_kinds_are_the_ones_the_supervisor_allows_and_none_starts_a_network_program():
    from voice_studio.core.system import is_network_command
    for c in (cm.process_command(STUDIO, TOOLS, "/p/r", "m"), cm.dataset_command(STUDIO, TOOLS, "/p/r", "/d/new", dry_run=True)):
        assert not is_network_command(c.argv)
