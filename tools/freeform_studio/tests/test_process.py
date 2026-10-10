# SPDX-License-Identifier: GPL-3.0-or-later
"""Finishing waiting recordings with no server: decoded, listened to, cut into pieces, ready for Review and for the dataset; nothing else is touched."""
import asyncio
import json
import os
import stat
import sys
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


# ---------------------------------------------------------------- the settings, the progress lines, and what is said about each

class Recorder:
    """Stands in for standard output and remembers every flush, so a program reading the lines as they come is not kept waiting for a full buffer."""

    def __init__(self):
        self.parts, self.flushes = [], 0

    def write(self, text):
        self.parts.append(text)
        return len(text)

    def flush(self):
        self.flushes += 1

    def isatty(self):
        return False

    @property
    def lines(self):
        return "".join(self.parts).splitlines()


def capture_config(monkeypatch):
    seen = {}

    async def fake_process(cfg, store, engines, report, poll_s=0.5):
        seen["cfg"] = cfg
        return {}

    monkeypatch.setattr(proc, "process", fake_process)
    monkeypatch.setattr(proc, "is_available", lambda name: True)
    return seen


def test_the_settings_come_from_the_options_and_a_download_is_never_allowed(tmp_path, out_dir, monkeypatch):
    seen = capture_config(monkeypatch)
    TakeStore(Config(output_dir=out_dir, code="en-GB").takes_dir).create({"label": "x", "status": "finishing", "mime": "audio/wav"})
    code = proc.main(["--output", str(out_dir), "--code", "en-GB", "--asr-engine", "fake", "--asr-model", "m", "--asr-device", "cuda", "--asr-compute-type", "int8"])
    cfg = seen["cfg"]
    assert code == 0 and (cfg.code, cfg.asr_engine, cfg.asr_model, cfg.asr_device, cfg.asr_compute_type) == ("en-GB", "fake", "m", "cuda", "int8")
    assert cfg.asr_allow_download is False and cfg.asr_idle_unload_s == 0


def test_the_defaults_are_this_computers_processor_and_the_small_english_model(tmp_path, out_dir, monkeypatch):
    seen = capture_config(monkeypatch)
    store_of(out_dir).create({"label": "x", "status": "finishing", "mime": "audio/wav"})
    assert proc.main(["--output", str(out_dir)]) == 0
    cfg = seen["cfg"]
    assert (cfg.code, cfg.asr_engine, cfg.asr_model, cfg.asr_device, cfg.asr_compute_type) == ("en-US", "faster-whisper", "small.en", "cpu", "auto")
    assert cfg.asr_allow_download is False


class ScriptedRunner:
    """Stands in for the job runner: changes a recording the way the real one does, and waits until the watcher has reported each step before the next."""
    reports = []
    steps = []
    instances = []

    def __init__(self, cfg, store, engines):
        self.store, self.stopped = store, False
        ScriptedRunner.instances.append(self)

    async def start(self):
        pass

    async def stop(self):
        self.stopped = True

    async def wait_idle(self):
        for take_id, fields, expect, linger in self.steps:
            if take_id:
                self.store.update(take_id, **fields)
            await asyncio.wait_for(self._until(expect), 3)
            await asyncio.sleep(linger)             # long enough for a watcher that repeats itself to show it

    async def _until(self, count):
        while len(self.reports) < count:
            await asyncio.sleep(0.001)


class Engines:
    unloaded = 0

    def unload(self):
        self.unloaded += 1


def drive(monkeypatch, out_dir, steps, runner=ScriptedRunner):
    store = store_of(out_dir)
    take = store.create({"label": "x", "status": "finishing", "mime": "audio/wav"})["id"]
    reports = []
    ScriptedRunner.reports, ScriptedRunner.instances = reports, []
    ScriptedRunner.steps = [(take if t else None, f, e, l) for t, f, e, l in steps]
    monkeypatch.setattr(proc, "JobRunner", runner)
    engines = Engines()
    final = asyncio.run(proc.process(Config(output_dir=out_dir), store, engines, lambda state: reports.append((state["status"], state["progress"])), poll_s=0.002))
    return take, reports, final, engines


def test_each_change_of_status_or_of_progress_is_reported_once_and_in_order(tmp_path, out_dir, monkeypatch):
    steps = [(False, {}, 1, 0.03),
             (True, {"status": "queued"}, 2, 0.03),                              # the status changes and the progress does not
             (True, {"status": "transcribing", "progress": 0.25}, 3, 0.03),
             (True, {"progress": 0.5}, 4, 0.03),                                # the progress changes and the status does not
             (True, {"status": "ready", "progress": 1.0}, 5, 0.03)]
    take, reports, final, engines = drive(monkeypatch, out_dir, steps)
    assert reports == [("finishing", 0.0), ("queued", 0.0), ("transcribing", 0.25), ("transcribing", 0.5), ("ready", 1.0)]
    assert final[take]["status"] == "ready" and ScriptedRunner.instances[0].stopped and engines.unloaded == 1


def test_a_change_made_just_before_the_end_is_still_reported_exactly_once(tmp_path, out_dir, monkeypatch):
    steps = [(False, {}, 1, 0.03), (True, {"status": "ready", "progress": 1.0}, 1, 0.0)]          # the watcher may never see "ready" itself
    take, reports, final, engines = drive(monkeypatch, out_dir, steps)
    assert reports == [("finishing", 0.0), ("ready", 1.0)] and final[take]["status"] == "ready"


def test_the_runner_is_stopped_and_the_engine_unloaded_even_when_the_run_fails(tmp_path, out_dir, monkeypatch):
    class Exploding(ScriptedRunner):
        async def wait_idle(self):
            raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        drive(monkeypatch, out_dir, [], runner=Exploding)
    assert ScriptedRunner.instances[0].stopped


def test_with_nothing_waiting_no_runner_is_made_and_nothing_is_reported(tmp_path, out_dir, monkeypatch):
    class Never:
        def __init__(self, *a):
            raise AssertionError("a runner was made with nothing to do")

    monkeypatch.setattr(proc, "JobRunner", Never)
    store_of(out_dir).create({"label": "x", "status": "ready", "mime": "audio/wav"})
    reports = []
    assert asyncio.run(proc.process(Config(output_dir=out_dir), store_of(out_dir), Engines(), reports.append)) == {} and reports == []


def test_what_is_said_about_a_recording_is_what_the_store_holds_and_a_missing_one_reads_as_unknown(tmp_path, out_dir):
    store = store_of(out_dir)
    take = store.create({"label": "Café 日本", "status": "queued", "mime": "audio/wav", "error": "e", "progress": 0.4, "duration": 12.5})["id"]
    gone = "t20200101-000000-0000"
    snap = proc.snapshot(store, [take, gone])
    assert snap[take] == {"take": take, "status": "queued", "progress": 0.4, "error": "e", "label": "Café 日本", "duration": 12.5}
    assert snap[gone] == {"take": gone, "status": "unknown", "progress": None, "error": None, "label": "", "duration": None}


def scripted_main(monkeypatch, out_dir, reports=(), final=None, *extra):
    async def fake_process(cfg, store, engines, report, poll_s=0.5):
        for state in reports:
            report(state)
        return final if final is not None else {}

    monkeypatch.setattr(proc, "process", fake_process)
    store_of(out_dir).create({"label": "x", "status": "finishing", "mime": "audio/wav"})
    return proc.main(["--output", str(out_dir), "--asr-engine", "fake", *extra])


def test_a_recording_still_not_ready_at_the_end_counts_as_not_finished(tmp_path, out_dir, monkeypatch, capsys):
    final = {"a": {"take": "a", "status": "queued", "progress": None, "error": None, "label": "", "duration": None},
             "b": {"take": "b", "status": "ready", "progress": 1.0, "error": None, "label": "", "duration": 3.0},
             "c": {"take": "c", "status": "error", "progress": None, "error": "no audio", "label": "", "duration": None}}
    assert scripted_main(monkeypatch, out_dir, (), final, "--json") == 1
    assert lines(capsys)[-1] == {"done": True, "ready": 1, "error": 2, "failed": [{"take": "a", "status": "queued", "error": None},
                                                                                  {"take": "c", "status": "error", "error": "no audio"}]}


def test_names_and_text_are_written_as_they_are_and_every_line_is_flushed(tmp_path, out_dir, monkeypatch):
    state = {"take": "t1", "status": "transcribing", "progress": 0.5, "error": None, "label": "Café 日本", "duration": 4.0}
    rec = Recorder()
    monkeypatch.setattr(sys, "stdout", rec)
    assert scripted_main(monkeypatch, out_dir, (state,), {}, "--json") == 0
    assert any("Café 日本" in line for line in rec.lines), "not escaped into \\u sequences"
    assert rec.flushes == len(rec.lines) == 2
    assert [json.loads(line) for line in rec.lines][0]["label"] == "Café 日本"


@pytest.mark.parametrize("name, says_path", [("/models/m", True), ("~/models/m", True), ("./m", True), ("../m", True), ("small.en", False), ("medium", False)])
def test_a_model_given_as_a_path_is_told_to_check_the_path_and_a_name_is_told_what_to_fetch(name, says_path):
    text = proc._sentence({"done": True, "ready": 0, "error": 0, "model_missing": name, "size": "about 1 GB"})
    assert ("does not exist" in text and "Check the path" in text) is says_path
    assert ("models fetch " + name in text and "about 1 GB" in text) is (not says_path)


def test_the_closing_sentence_tells_how_many_could_not_be_finished():
    assert proc._sentence({"done": True, "ready": 1, "error": 0}) == "Finished 1 recording(s)."
    assert proc._sentence({"done": True, "ready": 1, "error": 2}) == "Finished 1 recording(s); 2 could not be finished."


def test_a_progress_line_shows_a_whole_percent_and_the_reason_only_when_there_is_one():
    base = {"take": "t1", "status": "transcribing", "error": None}
    assert proc._sentence({**base, "progress": 0.5}) == "  t1: transcribing 50%"
    assert proc._sentence({**base, "progress": 1}) == "  t1: transcribing 100%"
    assert proc._sentence({**base, "progress": 0.999}) == "  t1: transcribing 99%"
    assert proc._sentence({**base, "progress": None}) == "  t1: transcribing"
    assert proc._sentence({**base, "progress": "half"}) == "  t1: transcribing", "a value that is not a number is not shown, and does not stop the line"
    assert proc._sentence({**base, "status": "error", "progress": None, "error": "no audio"}) == "  t1: error (no audio)"
