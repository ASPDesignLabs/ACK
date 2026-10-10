# SPDX-License-Identifier: GPL-3.0-or-later
"""The finished voice as ACK wants it (plan tasks VS-2.8, VS-5.3): checked before it is made, made carefully, and read back."""
import hashlib
import json
import os
import stat
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from vs_voice_helpers import PATCHED, field_bytes, meta_entry, onnx_bytes, piper_config, varint, write_voice
from voice_studio.core import voicezip as vz

TOOLS = Path(__file__).resolve().parents[2]


def read_meta(data: bytes):
    import io
    return vz.read_onnx_metadata(io.BytesIO(data), len(data))


# ---------------------------------------------------------------- reading the metadata of a model

def test_the_metadata_is_read_from_a_model_made_the_way_the_patcher_makes_it():
    assert read_meta(onnx_bytes(PATCHED)) == PATCHED


def test_metadata_before_the_graph_or_after_it_reads_the_same_and_unknown_fields_are_skipped():
    assert read_meta(onnx_bytes(PATCHED, metadata_first=True)) == PATCHED
    extra = field_bytes(99, b"something from a newer onnx") + varint((98 << 3) | 0) + varint(7) + varint((97 << 3) | 1) + b"12345678" + varint((96 << 3) | 5) + b"1234"
    assert read_meta(onnx_bytes(PATCHED, extra=extra)) == PATCHED


def test_a_model_with_no_metadata_reads_as_empty_not_as_broken():
    assert read_meta(onnx_bytes({})) == {}


def test_a_big_graph_is_skipped_not_read():
    import io

    class Counting(io.BytesIO):
        read_total = 0

        def read(self, n=-1):
            data = super().read(n)
            Counting.read_total += len(data)
            return data

    data = onnx_bytes(PATCHED, graph=3_000_000)
    handle = Counting(data)
    assert vz.read_onnx_metadata(handle, len(data)) == PATCHED and Counting.read_total < 2000


@pytest.mark.parametrize("data", [
    b"", b"\x00" * 100, b"not an onnx file at all", b"PK\x03\x04zip", b"\x08", b"\x08\x08\x12", b"\x08\x08\x12\xff\xff\xff\x7f",
    b"\x08\x08" + b"\x80" * 12, b"\x08\x08\x00", b"\x08\x08\x1b", b"\x08\x08\x1c",
    onnx_bytes(PATCHED)[:-3], onnx_bytes(PATCHED) + b"\x12",
])
def test_anything_that_is_not_shaped_like_a_model_is_not_a_model(data):
    assert read_meta(data) is None


def test_a_metadata_entry_that_is_too_large_is_refused():
    assert read_meta(onnx_bytes({"k": "v" * (vz.MAX_META_ENTRY + 1)})) is None
    assert read_meta(onnx_bytes({"k": "v" * 1000})) == {"k": "v" * 1000}


def test_a_metadata_entry_that_ends_early_or_has_a_strange_field_is_refused():
    bad = b"\x08\x08" + field_bytes(14, field_bytes(1, b"key") + b"\x12\x09short")
    assert read_meta(bad) is None
    group = b"\x08\x08" + field_bytes(14, varint((1 << 3) | 3))
    assert read_meta(group) is None


def test_metadata_with_unusual_text_is_read_as_text():
    data = onnx_bytes({"language": "Español", "bad": "\xff"})
    assert read_meta(data)["language"] == "Español"


def test_the_same_answer_as_the_onnx_library_on_a_real_model(tmp_path):
    onnx = pytest.importorskip("onnx")
    from onnx import TensorProto, helper
    node = helper.make_node("Identity", ["x"], ["y"])
    graph = helper.make_graph([node], "g", [helper.make_tensor_value_info("x", TensorProto.FLOAT, [1])], [helper.make_tensor_value_info("y", TensorProto.FLOAT, [1])])
    model = helper.make_model(graph)
    for key, value in PATCHED.items():
        entry = model.metadata_props.add()
        entry.key, entry.value = key, value
    path = tmp_path / "m.onnx"
    onnx.save(model, str(path))
    with open(path, "rb") as handle:
        assert vz.read_onnx_metadata(handle, path.stat().st_size) == PATCHED == {p.key: p.value for p in onnx.load(str(path)).metadata_props}


# ---------------------------------------------------------------- what ACK would refuse

def check(tmp_path, **kw):
    model, config = write_voice(tmp_path, **kw)
    return vz.check_voice(model, config)


def test_a_voice_that_was_patched_and_has_a_piper_config_passes(tmp_path):
    result = check(tmp_path)
    assert result.ok and result.problems == () and result.metadata == PATCHED and result.sample_rate == 22050 and result.skipped_symbols == 0


@pytest.mark.parametrize("missing", vz.REQUIRED_METADATA)
def test_a_model_missing_any_one_of_the_four_things_sherpa_requires_is_not_patched(tmp_path, missing):
    meta = {k: v for k, v in PATCHED.items() if k != missing}
    assert check(tmp_path, metadata=meta).problems == ("not_patched",)


def test_a_model_straight_from_training_with_no_metadata_is_not_patched(tmp_path):
    assert check(tmp_path, metadata={}).problems == ("not_patched",)


@pytest.mark.parametrize("comment, ok", [("piper", True), ("a piper voice", True), ("vits", False), ("", False), ("PIPER", False)])
def test_the_comment_must_say_piper(tmp_path, comment, ok):
    result = check(tmp_path, metadata={**PATCHED, "comment": comment})
    assert result.ok if ok else result.problems == ("wrong_comment",)


def test_a_file_that_is_not_a_model_is_named_so(tmp_path):
    model, config = write_voice(tmp_path)
    model.write_bytes(b"this is a text file")
    assert vz.check_voice(model, config).problems == ("not_onnx",)


def test_a_missing_or_empty_model_is_named(tmp_path):
    model, config = write_voice(tmp_path)
    model.write_bytes(b"")
    assert vz.check_voice(model, config).problems == ("model_empty",)
    model.unlink()
    assert vz.check_voice(model, config).problems == ("model_missing",)


def test_the_model_may_be_exactly_as_big_as_acks_limit_and_not_one_byte_more(tmp_path, monkeypatch):
    model, config = write_voice(tmp_path)
    size = model.stat().st_size
    monkeypatch.setattr(vz, "MAX_MODEL_BYTES", size)
    assert vz.check_voice(model, config).ok
    monkeypatch.setattr(vz, "MAX_MODEL_BYTES", size - 1)
    assert vz.check_voice(model, config).problems == ("model_too_big",)


def test_the_config_may_be_exactly_as_big_as_acks_limit_and_not_one_byte_more(tmp_path, monkeypatch):
    model, config = write_voice(tmp_path)
    size = config.stat().st_size
    monkeypatch.setattr(vz, "MAX_CONFIG_BYTES", size)
    assert vz.check_voice(model, config).ok
    monkeypatch.setattr(vz, "MAX_CONFIG_BYTES", size - 1)
    assert vz.check_voice(model, config).problems == ("config_too_big",)


@pytest.mark.parametrize("text, problem", [
    ("", "config_empty"), ("not json {", "config_not_json"), ("[1, 2]", "config_not_piper"), ('"text"', "config_not_piper"), ("{}", "config_not_piper"),
    (json.dumps({"audio": {"sample_rate": 22050}}), "config_not_piper"), (json.dumps({"phoneme_id_map": {}}), "config_not_piper"),
    (json.dumps({"audio": {}, "phoneme_id_map": {}}), "config_not_piper"), (json.dumps({"audio": {"sample_rate": "22050"}, "phoneme_id_map": {}}), "config_not_piper"),
    (json.dumps({"audio": {"sample_rate": True}, "phoneme_id_map": {}}), "config_not_piper"), (json.dumps({"audio": [], "phoneme_id_map": {}}), "config_not_piper"),
])
def test_a_config_that_does_not_look_like_a_piper_config_is_named(tmp_path, text, problem):
    model, config = write_voice(tmp_path)
    config.write_text(text)
    assert vz.check_voice(model, config).problems == (problem,)


def test_a_config_that_is_not_text_or_not_there_is_named(tmp_path):
    model, config = write_voice(tmp_path)
    config.write_bytes(b"\xff\xfe\x00bad")
    assert vz.check_voice(model, config).problems == ("config_not_json",)
    config.unlink()
    assert vz.check_voice(model, config).problems == ("config_missing",)


def test_the_models_rate_must_agree_with_the_configs(tmp_path):
    assert check(tmp_path, metadata={**PATCHED, "sample_rate": "16000"}).problems == ("rate_mismatch",)


def test_the_models_speaker_count_must_agree_with_the_configs_and_one_is_the_default(tmp_path):
    assert check(tmp_path / "a", metadata={**PATCHED, "n_speakers": "4"}).problems == ("speakers_mismatch",)
    assert check(tmp_path / "b", metadata={**PATCHED, "n_speakers": "4"}, config=piper_config(speakers=4)).ok
    assert check(tmp_path / "c", config=piper_config(speakers=1)).ok


def test_several_problems_are_listed_together_once_each(tmp_path):
    model, config = write_voice(tmp_path, metadata={})
    config.write_text("{}")
    assert vz.check_voice(model, config).problems == ("not_patched", "config_not_piper")


def test_symbols_of_more_than_one_character_are_counted_for_the_details_and_newline_is_not(tmp_path):
    symbols = {"_": [0], "a": [1], "eɪ": [2], "aɪ": [3], "\n": [4], "ə": [5]}
    assert check(tmp_path, config=piper_config(symbols=symbols)).skipped_symbols == 2
    assert check(tmp_path / "b", config=piper_config(symbols={})).skipped_symbols == 0


def test_the_files_given_are_only_read(tmp_path):
    model, config = write_voice(tmp_path)
    before = (model.read_bytes(), config.read_bytes(), model.stat().st_mtime_ns, config.stat().st_mtime_ns)
    vz.check_voice(model, config)
    assert before == (model.read_bytes(), config.read_bytes(), model.stat().st_mtime_ns, config.stat().st_mtime_ns)


# ---------------------------------------------------------------- the real patcher's output passes

def test_a_real_model_after_the_real_patcher_passes_and_before_it_does_not(tmp_path):
    onnx = pytest.importorskip("onnx")
    from onnx import TensorProto, helper
    graph = helper.make_graph([helper.make_node("Identity", ["x"], ["y"])], "g", [helper.make_tensor_value_info("x", TensorProto.FLOAT, [1])],
                              [helper.make_tensor_value_info("y", TensorProto.FLOAT, [1])])
    model = tmp_path / "my_voice.onnx"
    onnx.save(helper.make_model(graph), str(model))
    config = tmp_path / "my_voice.onnx.json"
    config.write_text(json.dumps(piper_config(rate=22050)))
    assert vz.check_voice(model, config).problems == ("not_patched",)
    done = subprocess.run([sys.executable, str(TOOLS / "patch_voice_for_sherpa_onnx.py"), str(model), str(config)], capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    result = vz.check_voice(model, config)
    assert result.ok and result.metadata["comment"] == "piper" and result.metadata["sample_rate"] == "22050"


# ---------------------------------------------------------------- making the zip

def make(tmp_path, **kw):
    model, config = write_voice(tmp_path / "in", **kw)
    return model, config, tmp_path / "out" / "my_voice_backup.zip"


def test_a_good_voice_becomes_a_zip_with_exactly_the_two_entries_acks_import_reads(tmp_path):
    model, config, dest = make(tmp_path)
    dest.parent.mkdir()
    report = vz.write_voice_zip(model, config, dest)
    with zipfile.ZipFile(dest) as zf:
        assert [i.filename for i in zf.infolist()] == ["model.onnx", "model.onnx.json"]
        assert zf.read("model.onnx") == model.read_bytes() and zf.read("model.onnx.json") == config.read_bytes()
        assert zf.getinfo("model.onnx").compress_type == zipfile.ZIP_STORED and zf.getinfo("model.onnx.json").compress_type == zipfile.ZIP_DEFLATED
        assert all(i.extra == b"" for i in zf.infolist()), "no zip64 fields: the phone's zip reader is not asked to understand them"
    assert report.path == str(dest) and report.zip_bytes == dest.stat().st_size and report.model_bytes == model.stat().st_size
    assert report.model_sha256 == hashlib.sha256(model.read_bytes()).hexdigest() and report.config_sha256 == hashlib.sha256(config.read_bytes()).hexdigest()
    assert vz.verify_voice_zip(dest) == ()


def test_the_zip_is_owner_only_and_leaves_no_part_file(tmp_path):
    model, config, dest = make(tmp_path)
    dest.parent.mkdir()
    old = os.umask(0o022)
    try:
        vz.write_voice_zip(model, config, dest)
    finally:
        os.umask(old)
    assert stat.S_IMODE(dest.stat().st_mode) == 0o600 and os.listdir(dest.parent) == [dest.name]


def test_the_same_voice_always_gives_the_same_bytes(tmp_path):
    model, config, dest = make(tmp_path)
    dest.parent.mkdir()
    again = dest.with_name("again.zip")
    vz.write_voice_zip(model, config, dest)
    os.utime(model, (1, 1))
    vz.write_voice_zip(model, config, again)
    assert dest.read_bytes() == again.read_bytes()


def test_the_files_the_zip_was_made_from_are_not_touched(tmp_path):
    model, config, dest = make(tmp_path)
    dest.parent.mkdir()
    before = (model.read_bytes(), config.read_bytes(), model.stat().st_mtime_ns)
    vz.write_voice_zip(model, config, dest)
    assert before == (model.read_bytes(), config.read_bytes(), model.stat().st_mtime_ns)


def test_a_voice_that_is_not_ready_makes_no_file_and_says_what_is_wrong(tmp_path):
    model, config, dest = make(tmp_path, metadata={})
    dest.parent.mkdir()
    with pytest.raises(vz.VoiceZipError) as caught:
        vz.write_voice_zip(model, config, dest)
    assert caught.value.code == "not_ready" and caught.value.problems == ("not_patched",) and os.listdir(dest.parent) == []


def test_a_file_already_there_is_never_replaced(tmp_path):
    model, config, dest = make(tmp_path)
    dest.parent.mkdir()
    dest.write_bytes(b"an earlier export")
    with pytest.raises(vz.VoiceZipError) as caught:
        vz.write_voice_zip(model, config, dest)
    assert caught.value.code == "exists" and dest.read_bytes() == b"an earlier export" and os.listdir(dest.parent) == [dest.name]


def test_a_link_in_the_way_is_not_followed_or_replaced(tmp_path):
    model, config, dest = make(tmp_path)
    dest.parent.mkdir()
    target = tmp_path / "elsewhere.txt"
    dest.symlink_to(target)
    with pytest.raises(vz.VoiceZipError) as caught:
        vz.write_voice_zip(model, config, dest)
    assert caught.value.code == "exists" and not target.exists()


def test_a_missing_folder_is_a_plain_failure(tmp_path):
    model, config, dest = make(tmp_path)
    with pytest.raises(vz.VoiceZipError) as caught:
        vz.write_voice_zip(model, config, dest)
    assert caught.value.code == "write_failed" and not dest.parent.exists()


def test_there_must_be_room_for_both_files_and_the_margin(tmp_path, monkeypatch):
    model, config, dest = make(tmp_path)
    dest.parent.mkdir()
    need = model.stat().st_size + config.stat().st_size + vz.ROOM_MARGIN_BYTES
    from collections import namedtuple
    usage = namedtuple("usage", "total used free")
    monkeypatch.setattr(vz.shutil, "disk_usage", lambda p: usage(10 * need, 0, need - 1))
    with pytest.raises(vz.VoiceZipError) as caught:
        vz.write_voice_zip(model, config, dest)
    assert caught.value.code == "no_room" and os.listdir(dest.parent) == []
    monkeypatch.setattr(vz.shutil, "disk_usage", lambda p: usage(10 * need, 0, need))
    vz.write_voice_zip(model, config, dest)
    assert dest.exists()


def test_a_write_that_fails_part_way_leaves_nothing_behind(tmp_path, monkeypatch):
    model, config, dest = make(tmp_path)
    dest.parent.mkdir()

    def broken(*args, **kwargs):
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(vz.shutil, "copyfileobj", broken)
    with pytest.raises(vz.VoiceZipError) as caught:
        vz.write_voice_zip(model, config, dest)
    assert caught.value.code == "write_failed" and caught.value.detail == "No space left on device" and os.listdir(dest.parent) == []


def test_a_zip_that_does_not_read_back_the_same_is_not_kept(tmp_path, monkeypatch):
    model, config, dest = make(tmp_path)
    dest.parent.mkdir()
    real = vz._sha256
    calls = {"n": 0}

    def lying(handle):
        calls["n"] += 1
        return "0" * 64 if calls["n"] == 1 else real(handle)

    monkeypatch.setattr(vz, "_sha256", lying)
    with pytest.raises(vz.VoiceZipError) as caught:
        vz.write_voice_zip(model, config, dest)
    assert caught.value.code == "verify_failed" and "does not match" in caught.value.detail and os.listdir(dest.parent) == []


def test_a_zip_larger_than_acks_limit_is_not_kept(tmp_path, monkeypatch):
    model, config, dest = make(tmp_path)
    dest.parent.mkdir()
    monkeypatch.setattr(vz, "MAX_ZIP_BYTES", 100)
    with pytest.raises(vz.VoiceZipError) as caught:
        vz.write_voice_zip(model, config, dest)
    assert caught.value.code == "verify_failed" and "larger" in caught.value.detail and os.listdir(dest.parent) == []


def test_the_limit_is_for_the_zip_itself_and_the_edge_is_exact(tmp_path, monkeypatch):
    model, config, dest = make(tmp_path)
    dest.parent.mkdir()
    vz.write_voice_zip(model, config, dest)
    size = dest.stat().st_size
    other = dest.with_name("other.zip")
    monkeypatch.setattr(vz, "MAX_ZIP_BYTES", size)
    vz.write_voice_zip(model, config, other)
    monkeypatch.setattr(vz, "MAX_ZIP_BYTES", size - 1)
    with pytest.raises(vz.VoiceZipError):
        vz.write_voice_zip(model, config, dest.with_name("third.zip"))


# ---------------------------------------------------------------- reading a finished zip the way ACK's import does

def zip_of(tmp_path, entries, name="v.zip"):
    path = tmp_path / name
    with zipfile.ZipFile(path, "w") as zf:
        for entry, data in entries:
            zf.writestr(entry, data)
    return path


def good_entries():
    return [("model.onnx", onnx_bytes(PATCHED)), ("model.onnx.json", json.dumps(piper_config()))]


def test_a_zip_made_by_the_writer_passes_acks_rules(tmp_path):
    model, config, dest = make(tmp_path)
    dest.parent.mkdir()
    vz.write_voice_zip(model, config, dest)
    assert vz.verify_voice_zip(dest) == ()


def test_a_zip_missing_either_entry_or_with_other_names_is_wrong(tmp_path):
    assert vz.verify_voice_zip(zip_of(tmp_path, good_entries()[:1])) == ("zip_wrong_entries",)
    assert vz.verify_voice_zip(zip_of(tmp_path, good_entries()[1:], "b.zip")) == ("zip_wrong_entries",)
    assert vz.verify_voice_zip(zip_of(tmp_path, [("voice.onnx", b"x"), ("voice.onnx.json", b"{}")], "c.zip")) == ("zip_wrong_entries",)
    assert vz.verify_voice_zip(zip_of(tmp_path, [("folder/model.onnx", b"x"), ("folder/model.onnx.json", b"{}")], "d.zip")) == ("zip_wrong_entries",)


def test_extra_entries_are_ignored_the_way_acks_import_ignores_them(tmp_path):
    assert vz.verify_voice_zip(zip_of(tmp_path, good_entries() + [("README.txt", b"hi")])) == ()


def test_a_zip_with_an_unpatched_model_or_a_wrong_config_is_named(tmp_path):
    assert vz.verify_voice_zip(zip_of(tmp_path, [("model.onnx", onnx_bytes({})), good_entries()[1]])) == ("not_patched",)
    assert vz.verify_voice_zip(zip_of(tmp_path, [good_entries()[0], ("model.onnx.json", "{}")], "b.zip")) == ("config_not_piper",)
    assert vz.verify_voice_zip(zip_of(tmp_path, [("model.onnx", b"junk"), good_entries()[1]], "c.zip")) == ("not_onnx",)
    assert vz.verify_voice_zip(zip_of(tmp_path, [("model.onnx", b""), good_entries()[1]], "d.zip")) == ("model_empty",)


def test_the_zip_limits_are_acks_and_exact(tmp_path, monkeypatch):
    path = zip_of(tmp_path, good_entries())
    size = path.stat().st_size
    monkeypatch.setattr(vz, "MAX_ZIP_BYTES", size)
    assert vz.verify_voice_zip(path) == ()
    monkeypatch.setattr(vz, "MAX_ZIP_BYTES", size - 1)
    assert vz.verify_voice_zip(path) == ("zip_too_big",)
    monkeypatch.undo()
    model_size = len(good_entries()[0][1])
    monkeypatch.setattr(vz, "MAX_MODEL_BYTES", model_size - 1)
    assert vz.verify_voice_zip(path) == ("model_too_big",)


def test_a_file_that_is_not_a_zip_or_not_there_is_named(tmp_path):
    bad = tmp_path / "bad.zip"
    bad.write_bytes(b"not a zip")
    assert vz.verify_voice_zip(bad) == ("zip_unreadable",)
    assert vz.verify_voice_zip(tmp_path / "gone.zip") == ("zip_missing",)


def test_the_problem_and_error_codes_are_distinct_and_written_in_lower_case():
    assert len(set(vz.PROBLEM_CODES)) == len(vz.PROBLEM_CODES) and len(set(vz.ERROR_CODES)) == len(vz.ERROR_CODES)
    assert all(c == c.lower() for c in vz.PROBLEM_CODES + vz.ERROR_CODES)
    assert str(vz.VoiceZipError("not_ready", problems=("a",))) == "not_ready" and vz.VoiceZipError("exists", "x").problems == ()
