# SPDX-License-Identifier: GPL-3.0-or-later
"""tools/patch_voice_for_sherpa_onnx.py: it explains mistakes in plain words, never damages the model, and keeps a copy of it."""
import importlib.util
import json
import os
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "patch_voice_for_sherpa_onnx.py"
spec = importlib.util.spec_from_file_location("patch_voice", SCRIPT)
patcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(patcher)          # importing it must not need the onnx package (that is only needed to patch)

CONFIG = {"audio": {"sample_rate": 22050}, "num_speakers": 1, "espeak": {"voice": "en-us"}}
BINARY = b"\x08\x07\x12\x07pytorch\xf7\xff\x00 not text " * 20      # starts like a real model; byte 0xf7 is not valid UTF-8


def run(capsys, *args):
    code = patcher.main([str(a) for a in args])
    captured = capsys.readouterr()
    return code, captured.out, captured.err


@pytest.fixture()
def voice(tmp_path):
    """A folder like ~/piper/my-training: an exported model (not yet patched) and the config training wrote."""
    model = tmp_path / "Snakesan2.onnx"
    model.write_bytes(BINARY)
    (tmp_path / "config.json").write_text(json.dumps(CONFIG))
    return tmp_path, model


def untouched(folder, model):
    """Nothing about the model changed and no backup or scratch file appeared."""
    assert model.read_bytes() == BINARY
    assert not list(folder.glob("*.before-patch*")) and not list(folder.glob("*.patching"))


# ---------------------------------------------------------------- the mistake that was actually made

def test_giving_the_model_twice_is_explained_and_changes_nothing(voice, capsys):
    folder, model = voice
    code, out, err = run(capsys, model, model)
    assert code == 2 and "Traceback" not in err
    assert "The second file you gave is a model, not a config" in err
    assert f"cp {folder / 'config.json'} {model}.json" in err, "the exact command to make the missing file"
    assert f"{model} {model}.json" in err, "and the exact command to run afterwards"
    untouched(folder, model)


def test_a_different_binary_file_as_the_config_is_also_caught_before_anything_changes(voice, capsys):
    folder, model = voice
    other = folder / "copy.bin"
    other.write_bytes(BINARY)
    code, out, err = run(capsys, model, other)
    assert code == 2 and "isn't a text file" in err and "UnicodeDecodeError" not in err
    assert model.read_bytes() == BINARY and not list(folder.glob("*.before-patch*"))


def test_the_two_files_the_wrong_way_round_say_so(voice, capsys):
    folder, model = voice
    cfg = folder / "Snakesan2.onnx.json"
    cfg.write_text(json.dumps(CONFIG))
    code, out, err = run(capsys, cfg, model)
    assert code == 2 and "wrong way round" in err and f"{model} {cfg}" not in err.split("wrong way round")[0]
    assert f"{model} {cfg}" in err.replace("\n", " ")


def test_a_missing_config_names_the_file_to_copy_when_config_json_is_next_to_it(voice, capsys):
    folder, model = voice
    code, out, err = run(capsys, model)                 # no second argument: <model>.json is assumed
    assert code == 2 and "The config file doesn't exist" in err and f"cp {folder / 'config.json'} {model}.json" in err
    (folder / "config.json").unlink()
    code, out, err = run(capsys, model)
    assert code == 2 and "--data.config_path" in err and "cp " not in err
    assert model.read_bytes() == BINARY


def test_a_model_path_that_does_not_exist_is_reported(tmp_path, capsys):
    code, out, err = run(capsys, tmp_path / "nope.onnx", tmp_path / "nope.onnx.json")
    assert code == 2 and "The model file doesn't exist" in err and "Traceback" not in err


@pytest.mark.parametrize("content,expected", [
    ("{ not json", "isn't valid JSON"),
    ("[1, 2, 3]", "doesn't look like a Piper voice config"),
    (json.dumps({"audio": {}}), "doesn't look like a Piper voice config"),
    (json.dumps({"audio": {"sample_rate": "22050"}}), "doesn't look like a Piper voice config"),
])
def test_a_config_that_is_not_a_piper_config_is_refused(voice, capsys, content, expected):
    folder, model = voice
    (folder / "Snakesan2.onnx.json").write_text(content)
    code, out, err = run(capsys, model, folder / "Snakesan2.onnx.json")
    assert code == 2 and expected in err and "Nothing was changed" in err
    assert model.read_bytes() == BINARY and not list(folder.glob("*.before-patch*"))


def test_the_metadata_comes_from_the_config():
    meta = patcher.build_metadata({"audio": {"sample_rate": 16000}, "num_speakers": 3, "espeak": {"voice": "en-gb"}})
    assert meta["sample_rate"] == 16000 and meta["n_speakers"] == 3 and meta["comment"] == "piper"
    assert meta["language"] == "English" and meta["voice"] == "en-gb" and meta["model_type"] == "vits"
    assert patcher.build_metadata(CONFIG)["n_speakers"] == 1


# ---------------------------------------------------------------- patching a real (tiny) ONNX model

@pytest.fixture()
def tiny_voice(tmp_path):
    onnx = pytest.importorskip("onnx")
    from onnx import TensorProto, helper
    x = helper.make_tensor_value_info("x", TensorProto.FLOAT, [1])
    y = helper.make_tensor_value_info("y", TensorProto.FLOAT, [1])
    graph = helper.make_graph([helper.make_node("Identity", ["x"], ["y"])], "g", [x], [y])
    model = tmp_path / "my_voice.onnx"
    onnx.save(helper.make_model(graph, opset_imports=[helper.make_opsetid("", 13)]), str(model))
    cfg = tmp_path / "my_voice.onnx.json"
    cfg.write_text(json.dumps(CONFIG))
    return onnx, model, cfg


def metadata(onnx, path):
    return {p.key: p.value for p in onnx.load(str(path)).metadata_props}


def test_patching_adds_the_metadata_and_keeps_the_original(tiny_voice, capsys):
    onnx, model, cfg = tiny_voice
    original = model.read_bytes()
    assert metadata(onnx, model) == {}
    code, out, err = run(capsys, model, cfg)
    assert code == 0 and err == "" and "Patched" in out and "A copy of the original is kept at" in out
    assert metadata(onnx, model)["sample_rate"] == "22050" and metadata(onnx, model)["comment"] == "piper"
    backup = model.with_name("my_voice.onnx.before-patch")
    assert backup.read_bytes() == original, "the backup is the original, byte for byte"
    assert "my_voice.onnx\n  my_voice.onnx.json" in out, "it says to import both files"
    assert not list(model.parent.glob("*.patching")), "no half-written leftovers"


def test_the_second_argument_can_be_left_out(tiny_voice, capsys):
    onnx, model, cfg = tiny_voice
    assert run(capsys, model)[0] == 0 and metadata(onnx, model)["n_speakers"] == "1"


def test_patching_twice_changes_nothing_the_second_time(tiny_voice, capsys):
    onnx, model, cfg = tiny_voice
    run(capsys, model, cfg)
    patched = model.read_bytes()
    code, out, err = run(capsys, model, cfg)
    assert code == 0 and "already has this metadata" in out
    assert model.read_bytes() == patched and len(list(model.parent.glob("*.before-patch*"))) == 1


def test_a_newer_export_gets_its_own_backup_and_the_older_one_is_kept(tiny_voice, capsys):
    onnx, model, cfg = tiny_voice
    run(capsys, model, cfg)
    first_backup = model.with_name("my_voice.onnx.before-patch")
    older = first_backup.read_bytes()
    from onnx import TensorProto, helper                  # a different model exported to the same name later
    x = helper.make_tensor_value_info("x", TensorProto.FLOAT, [2])
    y = helper.make_tensor_value_info("y", TensorProto.FLOAT, [2])
    graph = helper.make_graph([helper.make_node("Identity", ["x"], ["y"])], "g2", [x], [y])
    onnx.save(helper.make_model(graph, opset_imports=[helper.make_opsetid("", 13)]), str(model))
    newer = model.read_bytes()
    assert run(capsys, model, cfg)[0] == 0
    backups = sorted(model.parent.glob("*.before-patch*"))
    assert len(backups) == 2 and first_backup.read_bytes() == older
    assert any(b.read_bytes() == newer for b in backups if b != first_backup)


def test_a_failure_while_writing_leaves_the_model_exactly_as_it_was(tiny_voice, capsys, monkeypatch):
    onnx, model, cfg = tiny_voice
    original = model.read_bytes()
    real_save = onnx.save

    def dies_halfway(m, path, *a, **k):
        Path(path).write_bytes(b"half a model")            # the scratch file, not the real one
        raise OSError("no space left on device")

    monkeypatch.setattr(onnx, "save", dies_halfway)
    code, out, err = run(capsys, model, cfg)
    assert code == 1 and "Your model was not changed" in err and "no space left" in err
    assert model.read_bytes() == original, "the swap never happened"
    assert not list(model.parent.glob("*.patching")), "and the half-written scratch file was removed"
    monkeypatch.setattr(onnx, "save", real_save)
    assert run(capsys, model, cfg)[0] == 0                      # and trying again afterwards works


def test_a_file_that_is_not_an_onnx_model_is_reported_not_crashed_on(tmp_path, capsys):
    pytest.importorskip("onnx")
    model = tmp_path / "v.onnx"
    model.write_bytes(b"this is not a model")
    (tmp_path / "v.onnx.json").write_text(json.dumps(CONFIG))
    code, out, err = run(capsys, model)
    assert code == 2 and "can't be read as an ONNX model" in err and "Nothing was changed" in err
    assert model.read_bytes() == b"this is not a model" and not list(tmp_path.glob("*.before-patch*"))


def test_a_missing_onnx_package_says_how_to_install_it(voice, capsys, monkeypatch):
    folder, model = voice
    (folder / "Snakesan2.onnx.json").write_text(json.dumps(CONFIG))
    import builtins
    real_import = builtins.__import__

    def no_onnx(name, *a, **k):
        if name == "onnx":
            raise ImportError("No module named 'onnx'")
        return real_import(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", no_onnx)
    code, out, err = run(capsys, model)
    assert code == 2 and "pip install onnx" in err and "(.venv)" in err
    assert model.read_bytes() == BINARY
