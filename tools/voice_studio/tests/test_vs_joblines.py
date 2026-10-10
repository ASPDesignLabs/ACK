# SPDX-License-Identifier: GPL-3.0-or-later
"""Reading what the processor and the dataset builder print (plan tasks VS-2.4, VS-2.5), including against the real programs."""
import contextlib
import io
import json
import shutil
import sys
import wave
from pathlib import Path

import pytest

from voice_studio.core import joblines as jl

TESTS = Path(__file__).resolve().parents[2] / "freeform_studio" / "tests"


def line(**kw):
    return json.dumps(kw)


def write_tone(path, seconds, rate=48000):
    """A steady tone, mono 16-bit: loud enough to pass the dataset builder's checks, with no extra library."""
    import array
    import math
    samples = array.array("h", (int(16000 * math.sin(2 * math.pi * 200 * n / rate)) for n in range(int(seconds * rate))))
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(samples.tobytes())


# ---------------------------------------------------------------- lines

def test_only_json_objects_are_read_and_everything_else_is_skipped():
    lines = ["warning: something", "", "   ", "[1, 2]", "42", '"text"', "{not json", line(a=1), "  " + line(b=2) + "  ", "{" + "x" * 300_000 + "}"]
    assert jl.json_objects(lines) == [{"a": 1}, {"b": 2}]
    assert jl.json_objects([]) == [] and jl.json_objects(iter([line(z=1)])) == [{"z": 1}]


# ---------------------------------------------------------------- finishing recordings

def take(name, status, progress=None, error=None, label="", duration=None):
    return line(take=name, status=status, progress=progress, error=error, label=label, duration=duration)


def test_a_log_with_no_result_yet_reads_as_still_going_not_as_failed():
    state = jl.process_state(["starting up...", "Using device cpu"])
    assert state == jl.ProcessState((), False, 0, (), False, "") and state.fraction == 0.0


def test_each_recording_shows_the_last_thing_said_about_it_in_the_order_they_appeared():
    state = jl.process_state([take("t1", "finishing"), take("t2", "finishing"), take("t1", "queued"), take("t1", "transcribing", 0.5), take("t2", "queued")])
    assert [(t.take, t.status, t.progress) for t in state.takes] == [("t1", "transcribing", 0.5), ("t2", "queued", None)] and not state.finished


def test_the_fraction_counts_a_ready_recording_whole_and_never_reaches_one_before_the_end():
    mid = jl.process_state([take("a", "ready", 1.0), take("b", "transcribing", 0.5)])
    assert mid.fraction == 0.75 and mid.ready == 1
    almost = jl.process_state([take("a", "transcribing", 1.0)])
    assert almost.fraction == 0.99
    assert jl.process_state([take("a", "transcribing", 1.0), line(done=True, ready=1, error=0, failed=[])]).fraction == 1.0
    assert jl.process_state([take("a", "queued", -3), take("b", "queued", 7)]).fraction == pytest.approx((0 + 0.99) / 2, abs=0.001)


def test_the_closing_line_ends_it_and_lists_what_could_not_be_finished():
    lines = [take("a", "ready", 1.0, label="Morning"), take("b", "error", None, "no audio was received"), line(done=True, ready=1, error=1, failed=[])]
    state = jl.process_state(lines)
    assert state.finished and state.ready == 1 and [(t.take, t.error) for t in state.failed] == [("b", "no audio was received")]
    assert state.takes[0].label == "Morning"


def test_nothing_waiting_and_a_missing_speech_model_are_told_apart():
    assert jl.process_state([line(done=True, ready=0, error=0, nothing_waiting=True)]).nothing_waiting
    missing = jl.process_state([line(done=True, ready=0, error=0, model_missing="small.en", size="about 480 MB")])
    assert missing.model_missing == "small.en" and missing.finished and not missing.nothing_waiting


def test_lines_that_are_json_but_the_wrong_shape_are_ignored():
    state = jl.process_state([line(take=5, status="ready"), line(take="a"), line(status="ready"), line(other=1), take("ok", "ready", 1.0)])
    assert [t.take for t in state.takes] == ["ok"]


def test_odd_values_are_read_as_missing_rather_than_trusted():
    t = jl.process_state([line(take="a", status="ready", progress="half", error=5, label=None, duration=True)]).takes[0]
    assert (t.progress, t.error, t.label, t.duration) == (None, "", "", None)


# ---------------------------------------------------------------- the reasons

@pytest.mark.parametrize("reason, kind, detail", [
    ("you dropped it", "dropped", ""), ("no text", "no_text", ""), ("text has a character that would break the training file", "bad_character", ""),
    ("too short (0.4s)", "too_short", "0.4s"), ("too long (13.0s)", "too_long", "13.0s"), ("tagged: laugh, noise", "tagged", "laugh, noise"),
    ("a cut point falls inside a word (move it in Review, or pass --allow cuts_word)", "cuts_word", ""), ("not approved yet", "not_approved", ""),
    ("flagged: low_confidence, x", "flagged", "low_confidence, x"), ("flagged", "flagged", ""), ("already in freeform-dataset-1 (from an earlier export; re-export and rebuild)", "already_in", "freeform-dataset-1"),
    ("audio is empty", "audio_empty", ""), ("the recording clips (hits the maximum level repeatedly)", "clipping", ""), ("too quiet to use", "too_quiet", ""),
    ("audio conversion failed", "conversion_failed", ""), ("something new", "other", "something new"), ("", "other", ""),
])
def test_each_reason_freeform_studio_gives_becomes_a_kind_with_its_detail(reason, kind, detail):
    assert jl.reason_kind(reason) == (kind, detail) and kind in jl.REASON_KINDS


def test_every_kind_is_reachable_and_the_list_has_no_repeats():
    assert len(set(jl.REASON_KINDS)) == len(jl.REASON_KINDS)
    reached = {jl.reason_kind(r)[0] for r in ("you dropped it", "no text", "text has a character x", "too short", "too long", "tagged: x", "a cut point falls inside a word",
                                               "not approved yet", "flagged: x", "already in y (z)", "audio is empty", "the recording clips (..)", "too quiet to use",
                                               "audio conversion failed", "zzz")}
    assert reached == set(jl.REASON_KINDS)


# ---------------------------------------------------------------- the dataset

def result(**over):
    base = {"result": "built", "out": "/s/dataset-1", "takes": 2, "pieces_considered": 50, "skipped_takes": [["t3", "transcribing"]],
            "included": {"pieces": 40, "minutes": 12.5, "shortest": 1.2, "median": 4.0, "longest": 11.0}, "merged": 0,
            "left_out": {"pieces": 10, "by_reason": {"flagged": 4, "too short (0.4s)": 2, "too short (0.2s)": 1, "you dropped it": 3}, "by_flag": {"low_confidence": 3, "x": 1}},
            "warnings": ["w1"], "problems": [], "policy": {}}
    base.update(over)
    return line(**base)


def test_a_built_dataset_is_read_with_its_counts_and_the_reasons_grouped_by_kind():
    s = jl.dataset_summary(["noise", result()])
    assert (s.result, s.out, s.takes, s.pieces_considered, s.pieces, s.minutes, s.shortest, s.median, s.longest, s.merged, s.left_out) == (
        "built", "/s/dataset-1", 2, 50, 40, 12.5, 1.2, 4.0, 11.0, 0, 10)
    assert s.reasons == (("flagged", 4), ("dropped", 3), ("too_short", 3))
    assert s.flags == (("low_confidence", 3), ("x", 1)) and s.skipped_takes == (("t3", "transcribing"),) and s.warnings == ("w1",) and s.ok


def test_reasons_that_differ_only_in_their_numbers_are_added_together():
    s = jl.dataset_summary([result(left_out={"pieces": 3, "by_reason": {"too short": 1, "too short (0.2s)": 2}, "by_flag": {}})])
    assert s.reasons == (("too_short", 3),)


def test_equal_counts_are_listed_in_a_steady_order():
    s = jl.dataset_summary([result(left_out={"pieces": 4, "by_reason": {"you dropped it": 2, "no text": 2}, "by_flag": {"b": 1, "a": 1}})])
    assert s.reasons == (("dropped", 2), ("no_text", 2)) and s.flags == (("a", 1), ("b", 1))


def test_no_result_yet_is_none_and_the_last_result_wins():
    assert jl.dataset_summary(["working...", line(other=1)]) is None and jl.dataset_summary([]) is None
    assert jl.dataset_summary([result(result="dry_run"), result(result="built")]).result == "built"
    assert jl.dataset_summary([line(result="nonsense")]) is None


@pytest.mark.parametrize("name, ok", [("built", True), ("dry_run", True), ("nothing_qualified", False), ("problems", False), ("refused_existing", False), ("no_takes_folder", False)])
def test_only_a_built_dataset_or_a_preview_counts_as_a_success(name, ok):
    assert jl.dataset_summary([result(result=name)]).ok is ok


@pytest.mark.parametrize("minutes, advice", [(0.5, "short"), (9.99, "short"), (10.0, None), (29.99, None), (30.0, "comfortable"), (200.0, "comfortable")])
def test_the_advice_follows_freeform_studios_own_thresholds_at_the_exact_edges(minutes, advice):
    assert jl.dataset_summary([result(included={"pieces": 5, "minutes": minutes})]).advice == advice


def test_there_is_no_advice_about_length_when_nothing_was_included_or_it_did_not_work():
    assert jl.dataset_summary([result(included={"pieces": 0, "minutes": 0.0}, result="nothing_qualified")]).advice is None
    assert jl.dataset_summary([result(included={"pieces": 0, "minutes": 0.0})]).advice is None
    assert jl.dataset_summary([result(result="problems", problems=["row 3: x is missing"])]).advice is None
    assert set(jl.ADVICE_CODES) == {"short", "comfortable"}


def test_a_summary_with_missing_or_odd_fields_still_reads():
    s = jl.dataset_summary([line(result="refused_existing", out="/s/x")])
    assert (s.out, s.takes, s.pieces, s.minutes, s.left_out, s.reasons, s.flags, s.warnings, s.problems, s.skipped_takes) == ("/s/x", 0, 0, 0.0, 0, (), (), (), (), ())
    odd = jl.dataset_summary([line(result="built", out=5, takes="2", included=[], left_out="x", warnings="w", problems={}, skipped_takes=[[1, 2]])])
    assert (odd.out, odd.takes, odd.pieces, odd.left_out, odd.warnings, odd.problems, odd.skipped_takes) == ("", 0, 0, 0, (), (), ())


def test_flags_without_a_sentence_are_shown_as_words():
    assert jl.flag_name("speech_touches_edge") == "speech touches edge" and jl.flag_name("low_confidence") == "low confidence"
    assert len(set(jl.KNOWN_FLAGS)) == len(jl.KNOWN_FLAGS)


# ---------------------------------------------------------------- the real programs' output

def test_the_real_dataset_builder_output_is_read_correctly(tmp_path):
    pytest.importorskip("numpy")
    if shutil.which("ffmpeg") is None:
        pytest.skip("ffmpeg is not installed")
    sys.path.insert(0, str(TESTS))
    from freeform_studio import build_dataset as bd    # noqa: E402
    out_dir = tmp_path / "output"
    take = out_dir / "_freeform" / "en-US" / "takes" / "t20260930-000001-aaaa"
    take.mkdir(parents=True)
    write_tone(take / "audio.wav", 30.0)
    seg = lambda i, a, b, **kw: {"id": "s%03d" % i, "start": a, "end": b, "text": kw.pop("text", "hello there."), "words": [], "status": kw.pop("status", "pending"),
                                 "tags": [], "note": "", "flags": kw.pop("flags", []), "auto": None}
    (take / "take.json").write_text(json.dumps({"id": "t20260930-000001-aaaa", "status": "ready", "duration": 30.0}))
    (take / "edit.json").write_text(json.dumps({"schema": 1, "rev": 1, "segments": [seg(1, 0, 3), seg(2, 3, 6, flags=["low_confidence"]), seg(3, 6, 9, status="dropped"),
                                                                                       seg(4, 9, 9.4), seg(5, 10, 13, text="a | b")]}))
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        code = bd.main(["--output", str(out_dir), "--out", str(tmp_path / "ds"), "--json"])
    summary = jl.dataset_summary(buffer.getvalue().splitlines())
    assert code == 0 and summary.result == "built" and summary.pieces == 1 and summary.left_out == 4 and summary.out == str(tmp_path / "ds")
    assert dict(summary.reasons) == {"flagged": 1, "dropped": 1, "too_short": 1, "bad_character": 1} and summary.flags == (("low_confidence", 1),)
    assert summary.advice == "short" and (tmp_path / "ds" / "metadata.csv").exists()
    with wave.open(str(tmp_path / "ds" / "wav" / next((tmp_path / "ds" / "wav").iterdir()).name), "rb") as w:
        assert w.getframerate() == 22050


def test_the_real_processors_output_is_read_correctly(tmp_path, monkeypatch):
    pytest.importorskip("numpy")
    if shutil.which("ffmpeg") is None:
        pytest.skip("ffmpeg is not installed")
    sys.path.insert(0, str(TESTS))
    from ack_package_builder import ClipSpec, PackageBuilder       # noqa: E402
    import freeform_studio.ack_import as imp                      # noqa: E402
    import freeform_studio.process as proc                         # noqa: E402
    from freeform_studio.ack_package import open_package           # noqa: E402
    for name in ("HF_HUB_OFFLINE", "HF_HUB_DISABLE_TELEMETRY", "DO_NOT_TRACK"):
        monkeypatch.delenv(name, raising=False)
    b = PackageBuilder()
    b.script_session([ClipSpec("The tide came in.", speech=2.0), ClipSpec("Gulls circled overhead.", speech=2.0)])
    out_dir = tmp_path / "output"
    out_dir.mkdir()
    imp.apply_import(imp.make_plan(open_package(b.write(tmp_path / "p.zip")), out_dir, "en-US"))
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        code = proc.main(["--output", str(out_dir), "--asr-engine", "fake", "--json"])
    state = jl.process_state(buffer.getvalue().splitlines())
    assert code == 0 and state.finished and state.ready == 1 and state.failed == () and state.fraction == 1.0 and state.takes[-1].status == "ready"
    assert state.takes[-1].duration and state.takes[-1].label
