# SPDX-License-Identifier: GPL-3.0-or-later
"""Pieces for recordings that came from ACK: a script clip is one piece, bounded by where the phone recorded it."""
import asyncio
import json

import pytest

import freeform_studio.ack_import as imp
from ack_package_builder import ClipSpec, PackageBuilder
from conftest import needs_ffmpeg
from freeform_studio.ack_package import open_package
from freeform_studio.ack_segments import free_segments, script_segments, usable_notes
from freeform_studio.app import create_app
from freeform_studio.config import Config
from freeform_studio.edit import new_edit_doc, validate_edit
from freeform_studio.segmenter import SegOptions, build_segments

O = SegOptions()


def words(text, start, per=0.4, gap=0.0):
    out, t = [], start
    for tok in text.split():
        out.append({"w": tok, "s": round(t, 3), "e": round(t + per * 0.9, 3), "p": 0.95})
        t += per + gap
    return out


def asr_of(*word_lists):
    allw = [w for ws in word_lists for w in ws]
    return {"segments": [{"id": 0, "words": allw, "no_speech_prob": 0.01, "avg_logprob": -0.2, "compression_ratio": 1.1}]}


def clip(start, end, speech=None):
    c = {"start_s": start, "end_s": end}
    if speech:
        c["speech"] = {"start_s": speech[0], "end_s": speech[1]}
    return c


def notes_of(*clips):
    return {"mode": "script", "clips": list(clips)}


def acceptable(segs, duration):
    assert validate_edit(new_edit_doc(segs), duration) == []


# ------------------------------------------------------------------ one clip, one piece
def test_each_clip_becomes_one_piece_inside_its_own_stretch():
    asr = asr_of(words("The tide came in.", 0.5), words("We walked along the shore.", 4.9), words("Gulls circled overhead.", 10.3))
    notes = notes_of(clip(0.0, 3.0), clip(4.4, 8.4), clip(9.8, 13.0))
    segs = script_segments(asr, 13.0, notes, O)
    assert [s["text"] for s in segs] == ["The tide came in.", "We walked along the shore.", "Gulls circled overhead."]
    assert [s["id"] for s in segs] == ["s001", "s002", "s003"]
    for s, c in zip(segs, notes["clips"]):
        assert c["start_s"] <= s["start"] < s["end"] <= c["end_s"]
    acceptable(segs, 13.0)


def test_pieces_are_padded_around_the_words_and_never_reach_into_the_next_clip():
    asr = asr_of(words("Hello there friend.", 0.5), words("Another one here.", 3.6))
    segs = script_segments(asr, 6.0, notes_of(clip(0.0, 2.7), clip(3.1, 5.5)), O)
    assert segs[0]["start"] == pytest.approx(0.5 - O.pad_lead_s, abs=1e-3)
    assert segs[0]["end"] <= 2.7 < 3.1 <= segs[1]["start"]


def test_pieces_never_extend_beyond_their_clips_even_when_words_touch_the_edges():
    first = words("Right at the very start", 0.02, per=0.5)                      # padding would reach before the recording
    second = words("Hugging both edges of it", 3.42, per=0.5)                    # starts 0.02 s into its clip, ends 0.1 s before its end
    notes = notes_of(clip(0.0, 2.6), clip(3.4, 6.0))
    segs = script_segments(asr_of(first, second), 6.5, notes, O)
    assert len(segs) == 2
    for s, c in zip(segs, notes["clips"]):
        assert c["start_s"] <= s["start"] and s["end"] <= c["end_s"], (s["start"], s["end"], c)
    acceptable(segs, 6.5)


def test_two_sentences_recorded_as_one_clip_stay_one_piece_unlike_ordinary_cutting():
    spoken = words("It rained all day. We stayed inside.", 0.5, per=0.4, gap=0.05)
    assert len(build_segments(asr_of(spoken), 6.0, O)) == 2                       # the usual cutter splits at the full stop
    segs = script_segments(asr_of(spoken), 6.0, notes_of(clip(0.0, 5.0)), O)
    assert len(segs) == 1 and segs[0]["text"] == "It rained all day. We stayed inside."


def test_a_clip_longer_than_the_limit_is_still_cut_at_a_natural_gap():
    first = words(" ".join(f"a{i}" for i in range(12)), 0.5, per=0.5)       # 0.5 s to 6.45 s
    second = words(" ".join(f"b{i}" for i in range(12)), 7.0, per=0.5)      # 7.0 s to 12.95 s: 12.5 s of speech in one clip
    segs = script_segments(asr_of(first, second), 14.0, notes_of(clip(0.0, 13.5)), O)
    assert len(segs) >= 2
    for s in segs:
        assert s["end"] - s["start"] <= O.max_s + 1e-6 and 0.0 <= s["start"] < s["end"] <= 13.5
    assert all(a["end"] <= b["start"] + 1e-6 for a, b in zip(segs, segs[1:]))
    assert " ".join(s["text"] for s in segs) == " ".join([f"a{i}" for i in range(12)] + [f"b{i}" for i in range(12)])
    acceptable(segs, 14.0)


def test_a_word_heard_in_the_gap_between_clips_goes_to_the_nearer_clip():
    asr = asr_of(words("First clip words.", 0.4), words("late", 3.05, per=0.1), words("Second clip words.", 4.3))
    segs = script_segments(asr, 7.0, notes_of(clip(0.0, 3.0), clip(4.0, 6.5)), O)
    assert segs[0]["text"] == "First clip words. late" and segs[1]["text"] == "Second clip words."


def test_a_clip_where_nothing_was_heard_is_kept_so_it_can_be_typed_from_its_card():
    asr = asr_of(words("Heard this one.", 0.5), words("And this one.", 8.2))
    notes = notes_of(clip(0.0, 3.0), clip(4.0, 7.5, speech=(0.8, 2.6)), clip(7.9, 11.0))
    segs = script_segments(asr, 11.0, notes, O)
    assert len(segs) == 3 and segs[1]["text"] == "" and "empty" in segs[1]["flags"]
    assert segs[1]["start"] == pytest.approx(4.0 + 0.8 - O.pad_lead_s, abs=1e-3) and segs[1]["end"] == pytest.approx(4.0 + 2.6 + O.pad_tail_s, abs=1e-3)
    acceptable(segs, 11.0)


def test_with_nothing_heard_and_no_speech_note_the_whole_clip_is_the_piece():
    segs = script_segments(asr_of(), 5.0, notes_of(clip(0.0, 2.0), clip(2.4, 5.0)), O)
    assert [(s["start"], s["end"]) for s in segs] == [(0.0, 2.0), (2.4, 5.0)] and all("empty" in s["flags"] for s in segs)


def test_the_usual_warning_flags_still_apply_to_pieces():
    asr = asr_of(words("Costs 20 dollars", 0.5))
    segs = script_segments(asr, 3.0, notes_of(clip(0.0, 3.0)), O)
    assert "has_digits" in segs[0]["flags"]


# ------------------------------------------------------------------ free speech and fallbacks
def test_free_speech_is_cut_by_sentences_as_before():
    spoken = asr_of(words("It rained all day.", 0.5, per=0.4), words("We stayed inside.", 3.0, per=0.4))
    segs = free_segments(spoken, 6.0, {"mode": "free", "proposed_segments": [{"start_s": 0.3, "end_s": 5.0, "end_kind": "end"}]}, O)
    assert [s["text"] for s in segs] == ["It rained all day.", "We stayed inside."]


def test_free_speech_with_nothing_recognized_falls_back_to_the_phones_suggested_pieces():
    notes = {"mode": "free", "proposed_segments": [{"start_s": 0.3, "end_s": 9.9, "end_kind": "pause"}, {"start_s": 10.1, "end_s": 14.0, "end_kind": "end"},
                                                   {"start_s": 14.0, "end_s": 99.0, "end_kind": "end"}]}
    segs = free_segments(asr_of(), 15.0, notes, O)
    assert [(s["start"], s["end"]) for s in segs] == [(0.3, 9.9), (10.1, 14.0), (14.0, 15.0)]
    assert all("empty" in s["flags"] for s in segs)
    acceptable(segs, 15.0)


@pytest.mark.parametrize("notes,ok", [
    (None, False), ({}, False), ({"mode": "script"}, False), ({"mode": "script", "clips": []}, False),
    ({"mode": "script", "clips": [{"start_s": 1, "end_s": 0.5}]}, False),
    ({"mode": "script", "clips": [{"start_s": 0, "end_s": 3}, {"start_s": 2, "end_s": 4}]}, False),     # overlapping stretches
    ({"mode": "script", "clips": [{"start_s": 0, "end_s": 3}]}, True), ({"mode": "free"}, True),
])
def test_notes_that_cannot_be_used_fall_back_to_cutting_by_sentences(notes, ok):
    assert usable_notes(notes) is ok


# ------------------------------------------------------------------ through the real pipeline
@needs_ffmpeg
def test_imported_script_recording_is_cut_into_its_clips_by_the_real_pipeline(tmp_path, out_dir):
    b = PackageBuilder()
    # the middle card has two sentences: ordinary cutting would make four pieces from this recording, the clips make three
    texts = ["The tide came in slowly.", "It rained all day. We stayed inside until dark.", "Gulls circled overhead again."]
    b.script_session([ClipSpec(texts[0], speech=2.5), ClipSpec(texts[1], speech=4.5), ClipSpec(texts[2], speech=2.5)])
    b.free_session([(0.4, 3.0), (0.5, 7.0), (0.4, 4.0)])
    path = b.write(tmp_path / "p.zip")
    created = imp.apply_import(imp.make_plan(open_package(path), out_dir, "en-US"))
    script_id = next(c.take_id for c in created if c.session == b.sessions[0]["id"])
    free_id = next(c.take_id for c in created if c.session == b.sessions[1]["id"])

    async def settle(client, tid):
        for _ in range(300):
            doc = await (await client.get(f"/api/takes/{tid}")).get_json()
            if doc["status"] in ("ready", "error"):
                return doc
            await asyncio.sleep(0.1)
        raise AssertionError("timed out")

    async def main():
        app = create_app(Config(output_dir=out_dir, asr_engine="fake", asr_idle_unload_s=0))
        async with app.test_app():
            c = app.test_client()
            assert (await settle(c, script_id))["status"] == "ready"
            edit = await (await c.get(f"/api/takes/{script_id}/edit")).get_json()
            clips = json.loads((Config(output_dir=out_dir).takes_dir / script_id / "ack_clips.json").read_text(encoding="utf-8"))["clips"]
            segs = edit["segments"]
            assert len(segs) == 3, [s["text"] for s in segs]
            for s, cl in zip(segs, clips):
                assert cl["start_s"] <= s["start"] < s["end"] <= cl["end_s"] + 1e-6
            assert all(s["text"] for s in segs)
            assert (await settle(c, free_id))["status"] == "ready"
            free_edit = await (await c.get(f"/api/takes/{free_id}/edit")).get_json()
            assert free_edit["segments"], "free speech was not cut at all"
            # asking for the pieces to be made again keeps them tied to the phone's clips
            r = await c.post(f"/api/takes/{script_id}/transcribe", json={"regenerate": True})
            assert r.status_code == 202
            assert (await settle(c, script_id))["status"] == "ready"
            again = await (await c.get(f"/api/takes/{script_id}/edit")).get_json()
            assert len(again["segments"]) == 3
    asyncio.run(main())
