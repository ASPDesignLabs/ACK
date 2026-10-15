# SPDX-License-Identifier: GPL-3.0-or-later
"""The program that says the sentences (plan task VS-5.4), tested with a stand-in for the engine: its job file, its sound files, what it says and, above all, what it never says."""
import json
import math
import os
import stat
import struct
import wave
from pathlib import Path
from types import SimpleNamespace

import pytest

from voice_studio import listen_runner as lr

CANARY = "ZEBRA-CANARY-SENTENCE-12345"


class FakeEngine:
    sample_rate = 22050

    def __init__(self, samples=None, fail=None):
        self.samples = samples
        self.fail = fail
        self.calls = []

    def generate(self, text, sid=0, speed=1.0):
        self.calls.append((text, sid, speed))
        if self.fail:
            raise self.fail
        data = self.samples if self.samples is not None else [0.5 * math.sin(i / 20.0) for i in range(2205)]
        return SimpleNamespace(samples=data, sample_rate=22050)


@pytest.fixture
def place(tmp_path):
    for name in ("model.onnx", "tokens.txt"):
        (tmp_path / name).write_text("x")
    (tmp_path / "data").mkdir()
    (tmp_path / "out").mkdir()
    return tmp_path


def job_file(place, sentences=("Hello there.",), **more):
    job = {"model": str(place / "model.onnx"), "tokens": str(place / "tokens.txt"), "data_dir": str(place / "data"), "out_dir": str(place / "out"),
           "sentences": list(sentences) if isinstance(sentences, tuple) else sentences}
    job.update(more)
    path = place / "job.json"
    path.write_text(json.dumps(job))
    return str(path)


def lines(capsys):
    out = capsys.readouterr()
    return [json.loads(l) for l in out.out.splitlines()], out.err


def go(place, capsys, engine=None, sentences=("Hello there.",), **more):
    engine = engine or FakeEngine()
    code = lr.main([job_file(place, sentences, **more)], engine_factory=lambda *a: engine)
    events, err = lines(capsys)
    return code, events, err, engine


# ---------------------------------------------------------------- the good run

def test_each_sentence_becomes_a_numbered_sound_file_and_each_step_is_reported_as_one_line(place, capsys):
    code, events, err, engine = go(place, capsys, sentences=("One.", "Two.", "Three."))
    assert code == 0 and err == ""
    assert [e["event"] for e in events] == ["loaded", "clip", "clip", "clip", "done"]
    assert [e["file"] for e in events if e["event"] == "clip"] == ["clip-1.wav", "clip-2.wav", "clip-3.wav"] and events[-1]["clips"] == 3
    assert sorted(os.listdir(place / "out")) == ["clip-1.wav", "clip-2.wav", "clip-3.wav"]


def test_the_engine_is_asked_as_the_phone_asks_for_the_first_speaker_at_normal_speed(place, capsys):
    _code, _events, _err, engine = go(place, capsys, sentences=("One.", "Two."))
    assert engine.calls == [("One.", 0, 1.0), ("Two.", 0, 1.0)]


def test_a_sound_file_is_a_plain_mono_16_bit_wav_at_the_engines_rate_with_every_sample_in(place, capsys):
    go(place, capsys)
    with wave.open(str(place / "out" / "clip-1.wav"), "rb") as w:
        assert (w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()) == (1, 2, 22050, 2205)


def test_the_samples_are_scaled_to_the_full_range_and_clipped_not_wrapped(place, capsys):
    go(place, capsys, engine=FakeEngine(samples=[0.0, 1.0, -1.0, 2.0, -2.0]))
    with wave.open(str(place / "out" / "clip-1.wav"), "rb") as w:
        raw = w.readframes(5)
    import array
    values = array.array("h")
    values.frombytes(raw)
    assert list(values) == [0, 32767, -32767, 32767, -32768]


def test_a_clip_line_gives_the_length_the_rate_and_how_loud_it_is_so_a_screen_can_show_something(place, capsys):
    _code, events, _err, _engine = go(place, capsys)
    clip = events[1]
    assert clip["seconds"] == 0.1 and clip["sample_rate"] == 22050 and 0.3 < clip["rms"] < 0.4 and 0.49 < clip["peak"] <= 0.5 and clip["silent"] is False


def test_the_loaded_line_names_the_engines_rate(place, capsys):
    _code, events, _err, _engine = go(place, capsys)
    assert events[0]["event"] == "loaded" and events[0]["sample_rate"] == 22050


def test_a_clip_that_came_out_silent_is_made_and_said_to_be_silent_not_hidden(place, capsys):
    code, events, _err, _engine = go(place, capsys, engine=FakeEngine(samples=[0.0] * 100))
    assert code == 0 and events[1]["silent"] is True and (place / "out" / "clip-1.wav").is_file()


def test_the_edge_of_silence_a_peak_just_under_the_limit_is_silent_and_exactly_at_it_is_not(place, capsys):
    assert go(place, capsys, engine=FakeEngine(samples=[lr.SILENT_BELOW * 0.99]))[1][1]["silent"] is True
    (place / "out" / "clip-1.wav").unlink()
    assert go(place, capsys, engine=FakeEngine(samples=[lr.SILENT_BELOW]))[1][1]["silent"] is False


def test_an_engine_that_returns_nothing_gives_an_empty_but_valid_file_marked_silent(place, capsys):
    code, events, _err, _engine = go(place, capsys, engine=FakeEngine(samples=[]))
    assert code == 0 and events[1]["silent"] is True and events[1]["seconds"] == 0.0
    with wave.open(str(place / "out" / "clip-1.wav"), "rb") as w:
        assert w.getnframes() == 0


def test_files_are_readable_by_their_owner_only(place, capsys):
    go(place, capsys)
    mode = stat.S_IMODE(os.stat(place / "out" / "clip-1.wav").st_mode)
    assert mode & 0o077 == 0


# ---------------------------------------------------------------- what it never says

def test_no_sentence_is_ever_printed_not_in_the_lines_nor_in_what_goes_to_the_error_stream(place, capsys):
    code, events, err, _engine = go(place, capsys, sentences=(CANARY, "Another " + CANARY))
    assert code == 0 and CANARY not in json.dumps(events) and CANARY not in err


def test_a_failure_in_the_engine_says_what_kind_of_failure_and_never_its_message_which_could_hold_the_words(place, capsys):
    code, events, err, _engine = go(place, capsys, engine=FakeEngine(fail=RuntimeError("could not say " + CANARY)), sentences=(CANARY,))
    assert code == 1 and events[-1] == {"event": "error", "code": "speak_failed", "kind": "RuntimeError", "n": 1}
    assert CANARY not in json.dumps(events) and CANARY not in err


def test_a_voice_that_will_not_load_says_what_kind_of_failure_and_nothing_else(place, capsys):
    def broken(*_a):
        raise ValueError("model says " + CANARY)
    code = lr.main([job_file(place, (CANARY,))], engine_factory=broken)
    events, err = lines(capsys)
    assert code == 1 and events == [{"code": "load_failed", "event": "error", "kind": "ValueError"}] and CANARY not in err


def test_a_computer_without_the_engine_exits_with_its_own_code(place, capsys):
    def missing(*_a):
        raise ImportError("no sherpa_onnx")
    code = lr.main([job_file(place)], engine_factory=missing)
    events, _err = lines(capsys)
    assert code == lr.EXIT_NO_ENGINE == 3 and events == [{"code": "no_engine", "event": "error"}]


# ---------------------------------------------------------------- the job file

@pytest.mark.parametrize("sentences", [[], [""], ["   "], ["a"] * (lr.MAX_SENTENCES + 1), ["x" * (lr.MAX_SENTENCE_CHARS + 1)], [5], "text"])
def test_a_job_with_no_sentence_a_blank_one_too_many_or_one_too_long_is_refused_before_anything_is_made(place, capsys, sentences):
    code, events, _err, engine = go(place, capsys, sentences=sentences)
    assert code == 1 and events == [{"code": "bad_job", "event": "error"}] and engine.calls == [] and os.listdir(place / "out") == []


def test_the_edges_of_what_is_allowed_are_allowed(place, capsys):
    code, events, _err, _engine = go(place, capsys, sentences=["a"] * lr.MAX_SENTENCES)
    assert code == 0 and events[-1]["clips"] == lr.MAX_SENTENCES
    for name in os.listdir(place / "out"):
        os.unlink(place / "out" / name)
    code, _events, _err, _engine = go(place, capsys, sentences=["x" * lr.MAX_SENTENCE_CHARS])
    assert code == 0


@pytest.mark.parametrize("missing", ["model", "tokens", "data_dir", "out_dir", "sentences"])
def test_a_job_that_lacks_a_part_is_refused(place, capsys, missing):
    path = job_file(place)
    job = json.loads(Path(path).read_text())
    del job[missing]
    Path(path).write_text(json.dumps(job))
    assert lr.main([path], engine_factory=lambda *a: FakeEngine()) == 1
    assert lines(capsys)[0] == [{"code": "bad_job", "event": "error"}]


@pytest.mark.parametrize("key", ["model", "tokens", "data_dir", "out_dir"])
def test_a_relative_path_or_one_that_is_not_there_is_refused(place, capsys, key):
    for value in ("relative/path", str(place / "nope")):
        path = job_file(place)
        job = json.loads(Path(path).read_text())
        job[key] = value
        Path(path).write_text(json.dumps(job))
        assert lr.main([path], engine_factory=lambda *a: FakeEngine()) == 1
        assert lines(capsys)[0] == [{"code": "bad_job", "event": "error"}]


@pytest.mark.parametrize("content", ["", "not json", "[]", "null", "[" * 100000])
def test_a_job_file_that_is_not_a_job_is_refused_without_a_crash(place, capsys, content):
    path = place / "job.json"
    path.write_text(content)
    assert lr.main([str(path)], engine_factory=lambda *a: FakeEngine()) == 1
    assert lines(capsys)[0] == [{"code": "bad_job", "event": "error"}]


def test_a_job_file_that_is_too_big_is_refused_unread(place, capsys):
    path = place / "job.json"
    path.write_text(" " * (lr.MAX_JOB_BYTES + 1))
    assert lr.main([str(path)], engine_factory=lambda *a: FakeEngine()) == 1
    assert lines(capsys)[0] == [{"code": "bad_job", "event": "error"}]


def test_no_job_file_or_two_is_refused(capsys):
    assert lr.main([]) == 1 and lr.main(["a", "b"]) == 1
    assert [e["code"] for e in lines(capsys)[0]] == ["bad_job", "bad_job"]


def test_a_missing_job_file_is_refused(capsys, tmp_path):
    assert lr.main([str(tmp_path / "nope.json")]) == 1
    assert lines(capsys)[0] == [{"code": "bad_job", "event": "error"}]


# ---------------------------------------------------------------- never over a file that is there

def test_a_sound_file_that_is_already_there_is_never_written_over(place, capsys):
    (place / "out" / "clip-1.wav").write_bytes(b"mine")
    code, events, _err, _engine = go(place, capsys)
    assert code == 1 and events[-1] == {"code": "exists", "event": "error", "n": 1} and (place / "out" / "clip-1.wav").read_bytes() == b"mine"


def test_a_failure_after_some_clips_keeps_the_clips_already_made(place, capsys):
    engine = FakeEngine()
    original = engine.generate

    def second_fails(text, sid=0, speed=1.0):
        if len(engine.calls) == 1:
            engine.calls.append(text)
            raise RuntimeError("x")
        return original(text, sid, speed)
    engine.generate = second_fails
    code, events, _err, _engine = go(place, capsys, engine=engine, sentences=("One.", "Two.", "Three."))
    assert code == 1 and events[-1]["code"] == "speak_failed" and events[-1]["n"] == 2 and os.listdir(place / "out") == ["clip-1.wav"]


# ---------------------------------------------------------------- more edges

def test_a_relative_path_is_refused_even_when_it_names_a_file_that_is_really_there(place, capsys, monkeypatch):
    monkeypatch.chdir(place)
    path = job_file(place)
    job = json.loads(Path(path).read_text())
    job["model"] = "model.onnx"                                   # exists, relative to where we are
    Path(path).write_text(json.dumps(job))
    assert lr.main([path], engine_factory=lambda *a: FakeEngine()) == 1
    assert lines(capsys)[0] == [{"code": "bad_job", "event": "error"}]


def test_a_job_file_over_the_limit_is_refused_unread_even_when_it_is_a_good_job(place, capsys):
    path = job_file(place)
    Path(path).write_text(Path(path).read_text() + " " * (lr.MAX_JOB_BYTES + 1))
    called = []
    assert lr.main([path], engine_factory=lambda *a: called.append(1)) == 1 and called == []
    assert lines(capsys)[0] == [{"code": "bad_job", "event": "error"}]


def test_a_good_job_followed_by_something_else_on_the_command_line_is_refused_and_makes_nothing(place, capsys):
    called = []
    assert lr.main([job_file(place), "extra"], engine_factory=lambda *a: called.append(1)) == 1 and called == [] and os.listdir(place / "out") == []
    assert lines(capsys)[0] == [{"code": "bad_job", "event": "error"}]


def test_on_a_big_endian_computer_the_samples_are_swapped_so_the_file_is_still_little_endian(monkeypatch):
    assert lr.pcm16([1.0]) == struct.pack("<h", 32767)
    monkeypatch.setattr(lr.sys, "byteorder", "big")
    assert lr.pcm16([1.0]) == struct.pack(">h", 32767)            # what native big-endian storage becomes after the swap: little-endian on such a computer
