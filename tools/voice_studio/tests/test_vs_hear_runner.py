# SPDX-License-Identifier: GPL-3.0-or-later
"""The program that writes down what is said in the sound files (plan task VS-5.5), with a stand-in for the listening model: its job file, how it reads a sound file, what it prints."""
import array
import json
import os
import struct
import sys
import wave
from pathlib import Path

import pytest

from voice_studio import hear_runner as hr


class FakeHearer:
    def __init__(self, texts=None, fail=None):
        self.texts, self.fail, self.calls = texts or ["hello there"], fail, []

    def transcribe(self, samples):
        self.calls.append(list(samples))
        if self.fail:
            raise self.fail
        return self.texts[min(len(self.calls), len(self.texts)) - 1]


def write_clip(path, samples, rate=22050, channels=1, width=2):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(width)
        w.setframerate(rate)
        w.writeframes(b"".join(struct.pack("<h", int(v * 32767)) for v in samples) if width == 2 else bytes(len(samples)))


@pytest.fixture
def place(tmp_path):
    (tmp_path / "model").mkdir()
    write_clip(tmp_path / "clip-1.wav", [0.0, 0.5, -0.5, 0.25] * 100)
    write_clip(tmp_path / "clip-2.wav", [0.1] * 400)
    return tmp_path


def job_file(place, clips=("clip-1.wav", "clip-2.wav"), **more):
    job = {"model_dir": str(place / "model"), "clips": [str(place / c) for c in clips]}
    job.update(more)
    path = place / "job.json"
    path.write_text(json.dumps(job))
    return str(path)


def lines(capsys):
    out = capsys.readouterr()
    return [json.loads(l) for l in out.out.splitlines()], out.err


def go(place, capsys, hearer=None, **kw):
    hearer = hearer or FakeHearer(["first heard", "second heard"])
    code = hr.main([job_file(place, **kw)], engine_factory=lambda model_dir: hearer)
    events, err = lines(capsys)
    return code, events, err, hearer


# ---------------------------------------------------------------- the good run

def test_each_sound_file_is_heard_in_order_and_what_was_heard_is_printed_one_line_each(place, capsys):
    code, events, err, hearer = go(place, capsys)
    assert code == 0 and err == ""
    assert [e["event"] for e in events] == ["loaded", "heard", "heard", "done"]
    assert [(e["n"], e["text"]) for e in events if e["event"] == "heard"] == [(1, "first heard"), (2, "second heard")] and events[-1]["clips"] == 2
    assert len(hearer.calls) == 2


def test_the_model_is_given_the_folder_named_and_nothing_else(place, capsys):
    seen = []
    hr.main([job_file(place)], engine_factory=lambda model_dir: seen.append(model_dir) or FakeHearer())
    assert seen == [str(place / "model")]


def test_the_sound_reaches_the_model_at_sixteen_thousand_samples_a_second(place, capsys):
    _code, _events, _err, hearer = go(place, capsys, hearer=FakeHearer(["a", "b"]))
    assert len(hearer.calls[0]) == int(400 * 16000 / 22050) and len(hearer.calls[1]) == int(400 * 16000 / 22050)


def test_samples_are_numbers_between_minus_one_and_one(place):
    samples, rate = hr.read_wav(str(place / "clip-1.wav"))
    assert rate == 22050 and len(samples) == 400 and max(samples) == pytest.approx(0.5, abs=1e-3) and min(samples) == pytest.approx(-0.5, abs=1e-3)


def test_the_program_forces_the_listening_libraries_offline_even_when_the_computer_says_otherwise(place, capsys, monkeypatch):
    monkeypatch.setenv("HF_HUB_OFFLINE", "0")
    monkeypatch.setenv("TRANSFORMERS_OFFLINE", "0")
    go(place, capsys)
    assert os.environ["HF_HUB_OFFLINE"] == "1" and os.environ["TRANSFORMERS_OFFLINE"] == "1" and os.environ["HF_HUB_DISABLE_TELEMETRY"] == "1"


# ---------------------------------------------------------------- the resampling

def test_a_sound_at_the_target_rate_is_returned_as_it_is():
    assert hr.resample([0.1, 0.2, 0.3], 16000) == [0.1, 0.2, 0.3]


def test_an_empty_sound_stays_empty():
    assert hr.resample([], 22050) == []


def test_downsampling_keeps_the_length_in_seconds_and_the_ends():
    samples = [i / 22050 for i in range(22050)]                            # one second, a ramp
    out = hr.resample(samples, 22050)
    assert len(out) == 16000 and out[0] == 0.0 and out[-1] == pytest.approx(samples[-1], abs=1e-3)
    assert all(b >= a for a, b in zip(out, out[1:])), "a ramp stays a ramp"


def test_a_value_between_two_samples_is_their_weighted_average():
    out = hr.resample([0.0, 1.0, 0.0, 1.0], 32000)                          # exactly half the rate: every other sample
    assert out == pytest.approx([0.0, 0.0])
    out = hr.resample([0.0, 1.0], 8000, target=16000)                       # upsampling puts the average between
    assert out[0] == 0.0 and out[1] == pytest.approx(0.5)


def test_the_last_new_sample_never_reads_past_the_end():
    assert len(hr.resample([0.5] * 3, 24000, target=16000)) == 2 and hr.resample([0.5], 22050) == [0.5]


# ---------------------------------------------------------------- what it never takes in

def test_a_sound_that_is_not_plain_mono_16_bit_is_refused_not_guessed_at(place, capsys):
    write_clip(place / "stereo.wav", [0.0] * 20, channels=2)
    write_clip(place / "eight.wav", [0.0] * 20, width=1)
    for name in ("stereo.wav", "eight.wav"):
        code = hr.main([job_file(place, clips=(name,))], engine_factory=lambda d: FakeHearer())
        assert code == 1 and lines(capsys)[0][-1] == {"code": "unreadable", "event": "error", "n": 1}, name


def test_a_sound_file_that_is_not_a_sound_file_is_refused(place, capsys):
    (place / "junk.wav").write_bytes(b"not a wave file at all")
    assert hr.main([job_file(place, clips=("junk.wav",))], engine_factory=lambda d: FakeHearer()) == 1
    assert lines(capsys)[0][-1] == {"code": "unreadable", "event": "error", "n": 1}


def test_a_sound_longer_than_two_minutes_is_refused_unread(place, capsys):
    path = place / "long.wav"
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(8000)
        w.writeframes(b"\0\0" * (8000 * (hr.MAX_CLIP_SECONDS + 1)))
    assert hr.main([job_file(place, clips=("long.wav",))], engine_factory=lambda d: FakeHearer()) == 1
    assert lines(capsys)[0][-1]["code"] == "unreadable"
    with wave.open(str(path), "wb") as w:                                   # exactly the limit is fine
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(8000)
        w.writeframes(b"\0\0" * (8000 * hr.MAX_CLIP_SECONDS))
    assert hr.main([job_file(place, clips=("long.wav",))], engine_factory=lambda d: FakeHearer(["x"])) == 0


@pytest.mark.parametrize("rate", [7999, 96001])
def test_a_rate_outside_the_range_of_speech_files_is_refused(place, capsys, rate):
    write_clip(place / "odd.wav", [0.0] * 20, rate=rate)
    assert hr.main([job_file(place, clips=("odd.wav",))], engine_factory=lambda d: FakeHearer()) == 1
    assert lines(capsys)[0][-1]["code"] == "unreadable"


@pytest.mark.parametrize("rate", [8000, 96000])
def test_the_edges_of_the_allowed_rates_are_allowed(place, capsys, rate):
    write_clip(place / "edge.wav", [0.0] * 20, rate=rate)
    assert hr.main([job_file(place, clips=("edge.wav",))], engine_factory=lambda d: FakeHearer(["x"])) == 0


# ---------------------------------------------------------------- the job file

@pytest.mark.parametrize("clips", [[], ["clip-1.wav"] * (hr.MAX_CLIPS + 1), "clip-1.wav", [5], ["nope.wav"], ["relative.wav"]])
def test_a_job_with_no_clip_too_many_or_one_that_is_not_there_is_refused_before_the_model_is_loaded(place, capsys, clips):
    loaded = []
    path = place / "job.json"
    path.write_text(json.dumps({"model_dir": str(place / "model"), "clips": [str(place / c) if isinstance(c, str) and not c.startswith("relative") else c for c in clips] if isinstance(clips, list) else clips}))
    assert hr.main([str(path)], engine_factory=lambda d: loaded.append(d)) == 1 and loaded == []
    assert lines(capsys)[0] == [{"code": "bad_job", "event": "error"}]


def test_a_job_that_carries_a_sentence_or_anything_else_extra_is_refused(place, capsys):
    loaded = []
    assert hr.main([job_file(place, sentences=["Hello."])], engine_factory=lambda d: loaded.append(d)) == 1 and loaded == []
    assert lines(capsys)[0] == [{"code": "bad_job", "event": "error"}]


def test_the_edge_of_how_many_clips_is_allowed(place, capsys):
    code, events, _e, _h = go(place, capsys, hearer=FakeHearer(["x"]), clips=("clip-1.wav",) * hr.MAX_CLIPS)
    assert code == 0 and events[-1]["clips"] == hr.MAX_CLIPS


def test_a_clip_that_is_a_link_is_not_followed(place, capsys):
    (place / "link.wav").symlink_to(place / "clip-1.wav")
    assert hr.main([job_file(place, clips=("link.wav",))], engine_factory=lambda d: FakeHearer()) == 1
    assert lines(capsys)[0] == [{"code": "bad_job", "event": "error"}]


@pytest.mark.parametrize("model_dir", ["relative/model", "", 5, None])
def test_a_model_folder_that_is_relative_missing_or_not_text_is_refused(place, capsys, model_dir):
    path = place / "job.json"
    path.write_text(json.dumps({"model_dir": model_dir if model_dir != "" else "", "clips": [str(place / "clip-1.wav")]}))
    assert hr.main([str(path)], engine_factory=lambda d: FakeHearer()) == 1
    assert lines(capsys)[0] == [{"code": "bad_job", "event": "error"}]


@pytest.mark.parametrize("content", ["", "nope", "[]", "null", "[" * 100000])
def test_a_job_file_that_is_not_a_job_is_refused_without_a_crash(place, capsys, content):
    path = place / "job.json"
    path.write_text(content)
    assert hr.main([str(path)], engine_factory=lambda d: FakeHearer()) == 1
    assert lines(capsys)[0] == [{"code": "bad_job", "event": "error"}]


def test_a_job_file_over_the_limit_is_refused_unread_even_if_it_is_a_good_job(place, capsys):
    path = Path(job_file(place))
    path.write_text(path.read_text() + " " * (hr.MAX_JOB_BYTES + 1))
    called = []
    assert hr.main([str(path)], engine_factory=lambda d: called.append(1)) == 1 and called == []


def test_no_job_file_or_two_is_refused(capsys, place):
    called = []
    assert hr.main([], engine_factory=lambda d: called.append(1)) == 1
    assert hr.main([job_file(place), "extra"], engine_factory=lambda d: called.append(1)) == 1 and called == []
    assert [e["code"] for e in lines(capsys)[0]] == ["bad_job", "bad_job"]


# ---------------------------------------------------------------- failures say what kind and nothing else

def test_a_model_that_will_not_load_says_the_kind_of_failure_and_not_its_message(place, capsys):
    def broken(_d):
        raise ValueError("secret words " + str(place))
    assert hr.main([job_file(place)], engine_factory=broken) == 1
    events, err = lines(capsys)
    assert events == [{"code": "load_failed", "event": "error", "kind": "ValueError"}] and "secret" not in err


def test_a_computer_without_the_listening_program_exits_with_its_own_code(place, capsys):
    def missing(_d):
        raise ImportError("no faster_whisper")
    assert hr.main([job_file(place)], engine_factory=missing) == hr.EXIT_NO_ENGINE == 3
    assert lines(capsys)[0] == [{"code": "no_engine", "event": "error"}]


def test_a_failure_while_listening_to_one_file_stops_there_and_names_which(place, capsys):
    code, events, err, _h = go(place, capsys, hearer=FakeHearer(fail=RuntimeError("boom")))
    assert code == 1 and events[-1] == {"code": "hear_failed", "event": "error", "kind": "RuntimeError", "n": 1} and "boom" not in json.dumps(events) + err


def test_what_the_model_returns_is_printed_as_text_even_when_it_is_not(place, capsys):
    code, events, _e, _h = go(place, capsys, hearer=FakeHearer([None, 5]))
    assert code == 0 and [e["text"] for e in events if e["event"] == "heard"] == ["None", "5"]


def test_the_program_prints_nothing_but_json_lines(place, capsys):
    go(place, capsys)
    for line in capsys.readouterr().out.splitlines():
        json.loads(line)
