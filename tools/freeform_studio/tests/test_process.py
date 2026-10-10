# SPDX-License-Identifier: GPL-3.0-or-later
"""Finishing waiting recordings with no server: decoded, listened to, cut into pieces, ready for Review and for the dataset; nothing else is touched."""
import json
import os
import stat
from pathlib import Path

import pytest

import freeform_studio.ack_import as imp
import freeform_studio.process as proc
from ack_package_builder import ClipSpec, PackageBuilder
from conftest import needs_ffmpeg
from freeform_studio.ack_package import open_package
from freeform_studio.config import Config
from freeform_studio.storage import TakeStore

CARDS = ["The tide came in slowly.", "It rained all day.", "Gulls circled overhead again."]


def imported(tmp_path, out_dir):
    b = PackageBuilder()
    b.script_session([ClipSpec(CARDS[0], speech=2.5), ClipSpec(CARDS[1], speech=3.0), ClipSpec(CARDS[2], speech=2.5)])
    path = b.write(tmp_path / "p.zip")
    created = imp.apply_import(imp.make_plan(open_package(path), out_dir, "en-US"))
    return path, created


def store_of(out_dir):
    return TakeStore(Config(output_dir=out_dir).takes_dir)


def run_main(out_dir, *extra):
    return proc.main(["--output", str(out_dir), "--asr-engine", "fake", *extra])


@pytest.fixture(autouse=True)
def keep_the_environment(monkeypatch):
    for name in ("HF_HUB_OFFLINE", "HF_HUB_DISABLE_TELEMETRY", "DO_NOT_TRACK"):
        monkeypatch.delenv(name, raising=False)             # monkeypatch puts back whatever was there when the test ends


def lines(capsys):
    return [json.loads(line) for line in capsys.readouterr().out.splitlines() if line.startswith("{")]


@needs_ffmpeg
def test_an_imported_recording_is_finished_and_has_its_pieces(tmp_path, out_dir, capsys):
    _path, created = imported(tmp_path, out_dir)
    assert store_of(out_dir).get(created[0].take_id)["status"] == "finishing"
    assert run_main(out_dir, "--json") == 0
    take = store_of(out_dir).get(created[0].take_id)
    assert take["status"] == "ready" and take["asr"]["engine"] == "fake"
    folder = Config(output_dir=out_dir).takes_dir / created[0].take_id
    assert (folder / "audio.wav").exists() and (folder / "edit.json").exists() and (folder / "asr.json").exists()
    edit = json.loads((folder / "edit.json").read_text())
    assert len(edit["segments"]) == 3, "cut where the phone recorded its three clips"
    final = lines(capsys)[-1]
    assert final == {"done": True, "ready": 1, "error": 0, "failed": []}


@needs_ffmpeg
def test_progress_is_reported_as_it_changes_and_ends_ready(tmp_path, out_dir, capsys):
    imported(tmp_path, out_dir)
    run_main(out_dir, "--json")
    out = lines(capsys)
    statuses = [o["status"] for o in out if "status" in o]
    assert statuses[-1] == "ready" and "ready" in statuses and out[-1]["done"] is True
    assert all(set(o) >= {"take", "status", "progress", "error", "label", "duration"} for o in out if "status" in o)


@needs_ffmpeg
def test_the_sentences_are_plain_without_json(tmp_path, out_dir, capsys):
    imported(tmp_path, out_dir)
    assert run_main(out_dir) == 0
    text = capsys.readouterr().out
    assert "Finished 1 recording(s)." in text and "ready" in text and "{" not in text


@needs_ffmpeg
def test_running_again_finds_nothing_waiting_and_changes_nothing(tmp_path, out_dir, capsys):
    _path, created = imported(tmp_path, out_dir)
    run_main(out_dir)
    folder = Config(output_dir=out_dir).takes_dir / created[0].take_id
    before = {p.name: p.read_bytes() for p in folder.iterdir() if p.is_file()}
    capsys.readouterr()
    assert run_main(out_dir, "--json") == 0
    assert lines(capsys) == [{"done": True, "ready": 0, "error": 0, "nothing_waiting": True}]
    assert {p.name: p.read_bytes() for p in folder.iterdir() if p.is_file()} == before


def test_with_no_recordings_at_all_there_is_nothing_to_do(tmp_path, out_dir, capsys):
    assert run_main(out_dir) == 0 and "Nothing is waiting" in capsys.readouterr().out


@needs_ffmpeg
def test_the_package_the_recording_came_from_is_not_touched(tmp_path, out_dir):
    path, _created = imported(tmp_path, out_dir)
    before = path.read_bytes()
    run_main(out_dir)
    assert path.read_bytes() == before


@needs_ffmpeg
def test_what_it_makes_is_readable_by_the_owner_only(tmp_path, out_dir):
    old = os.umask(0o022)                                   # an ordinary, permissive setting: the command must override it
    try:
        _path, created = imported(tmp_path, out_dir)
        run_main(out_dir)
    finally:
        os.umask(old)
    folder = Config(output_dir=out_dir).takes_dir / created[0].take_id
    for name in ("audio.wav", "edit.json", "asr.json"):
        assert stat.S_IMODE((folder / name).stat().st_mode) & 0o077 == 0, name


@needs_ffmpeg
def test_a_recording_that_cannot_be_finished_is_reported_and_the_others_still_are(tmp_path, out_dir, capsys):
    _path, created = imported(tmp_path, out_dir)
    store = store_of(out_dir)
    broken = store.create({"label": "broken", "status": "finishing", "mime": "audio/wav"})          # no audio parts at all
    code = run_main(out_dir, "--json")
    out = lines(capsys)
    assert code == 1 and out[-1]["ready"] == 1 and out[-1]["error"] == 1
    assert out[-1]["failed"][0]["take"] == broken["id"] and "no audio" in out[-1]["failed"][0]["error"]
    assert store.get(created[0].take_id)["status"] == "ready" and store.get(broken["id"])["status"] == "error"


def test_the_real_speech_model_must_already_be_here_or_nothing_is_started(tmp_path, out_dir, capsys, monkeypatch):
    _ = out_dir
    store = store_of(out_dir)
    take = store.create({"label": "x", "status": "finishing", "mime": "audio/wav"})
    monkeypatch.setattr(proc, "is_available", lambda name: False)
    code = proc.main(["--output", str(out_dir), "--json"])
    out = lines(capsys)
    assert code == 3 and out == [{"done": True, "ready": 0, "error": 0, "model_missing": "small.en", "size": "about 480 MB"}]
    assert store.get(take["id"])["status"] == "finishing", "nothing was started, so nothing is stuck"


def test_the_message_for_a_missing_model_says_exactly_what_to_run(tmp_path, out_dir, capsys, monkeypatch):
    store_of(out_dir).create({"label": "x", "status": "finishing", "mime": "audio/wav"})
    monkeypatch.setattr(proc, "is_available", lambda name: False)
    assert proc.main(["--output", str(out_dir)]) == 3
    text = capsys.readouterr().out
    assert "python -m freeform_studio.models fetch small.en" in text and "about 480 MB" in text


def test_a_model_folder_that_exists_is_accepted_and_one_that_does_not_is_named(tmp_path, out_dir, capsys, monkeypatch):
    folder = tmp_path / "model"
    folder.mkdir()
    store_of(out_dir).create({"label": "x", "status": "finishing", "mime": "audio/wav"})
    seen = {}

    def fake_run(coro):
        coro.close()
        seen["ran"] = True
        return {}

    monkeypatch.setattr(proc.asyncio, "run", fake_run)
    assert proc.main(["--output", str(out_dir), "--asr-model", str(folder)]) == 0 and seen == {"ran": True}
    seen.clear()
    assert proc.main(["--output", str(out_dir), "--asr-model", str(tmp_path / "nope")]) == 3 and seen == {}
    text = capsys.readouterr().out
    assert "does not exist" in text and "models fetch" not in text


def test_the_command_turns_the_network_off_for_the_libraries_before_anything_else(tmp_path, out_dir, monkeypatch):
    calls = []
    monkeypatch.setattr(proc, "apply_offline_defaults", lambda allow=False: calls.append(allow))
    proc.main(["--output", str(out_dir), "--asr-engine", "fake"])
    assert calls == [False]


def test_a_wrong_option_is_a_usage_error(tmp_path, out_dir):
    with pytest.raises(SystemExit) as caught:
        proc.main(["--output", str(out_dir), "--asr-engine", "telepathy"])
    assert caught.value.code == 2


def test_only_unfinished_recordings_are_waiting(tmp_path, out_dir):
    store = store_of(out_dir)
    ids = {s: store.create({"label": s, "status": s, "mime": "audio/wav"})["id"] for s in ("finishing", "queued", "transcribing", "ready", "error", "decoded", "importing")}
    assert sorted(proc.waiting_takes(store)) == sorted([ids["finishing"], ids["queued"], ids["transcribing"]])
