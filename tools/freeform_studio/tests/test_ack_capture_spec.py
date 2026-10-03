# SPDX-License-Identifier: GPL-3.0-or-later
"""The capture format is written down twice, on purpose: in prose (docs/ACK_TRAINING_CAPTURE_FORMAT.md) and as running code
(ack_capture_reference.py). These tests keep the two, and the shared test cases the Kotlin side will be held to, from drifting
apart, and check the rules hold on inputs nobody wrote by hand.
"""
import json
import math
import random
import re
from pathlib import Path

import numpy as np
import pytest

import ack_capture_reference as ref
from freeform_studio.audio import voiced_regions

ROOT = Path(__file__).resolve().parents[3]
DOC = ROOT / "docs" / "ACK_TRAINING_CAPTURE_FORMAT.md"
DATA = Path(__file__).resolve().parent / "data" / "ack_capture"
needs_doc = pytest.mark.skipif(not DOC.exists(), reason="not inside the full ACK repository")


# ------------------------------------------------------------------ the document and the code agree
@needs_doc
def test_the_constants_in_the_document_are_the_ones_the_code_uses():
    text = DOC.read_text(encoding="utf-8")
    section = text.split("## 11. Constants", 1)[1]
    block = re.search(r"```json\n(.*?)\n```", section, re.S).group(1)
    assert json.loads(block) == ref.CONSTANTS


@needs_doc
def test_the_document_lists_every_shared_test_file():
    text = DOC.read_text(encoding="utf-8")
    on_disk = sorted(p.name for p in DATA.glob("*.json"))
    assert on_disk, "no shared test cases found"
    for name in on_disk:
        assert f"`{name}`" in text, f"{name} is not described in section 12 of the document"


def test_the_shared_test_cases_are_what_the_reference_code_produces():
    vectors = ref.build_vectors()
    stale = [name for name, obj in vectors.items()
             if not (DATA / name).exists() or (DATA / name).read_text(encoding="utf-8") != ref.dump(obj)]
    assert not stale, "run: python tools/freeform_studio/tests/ack_capture_reference.py --write   (out of date: " + ", ".join(stale) + ")"


def test_rounding_is_half_away_from_zero_and_never_negative_zero():
    assert ref.rnd(2.5, 0) == 3 and ref.rnd(-2.5, 0) == -3
    assert ref.rnd(0.25, 1) == 0.3 and ref.rnd(-0.25, 1) == -0.3
    assert str(ref.rnd(-0.0004, 3)) == "0.0"


# ------------------------------------------------------------------ measurements
def random_levels(rng, seconds=60.0):
    """Alternating loud and quiet stretches with a few in-between levels, as hop levels."""
    out = []
    while len(out) < seconds * 100:
        level = rng.choice([-70.0, -20.0, -20.0, -44.0, -46.0, -60.0])
        out.extend([level] * rng.randint(2, 900))
    return out[: int(seconds * 100)]


def test_the_region_finder_matches_freeforms_own_voiced_regions():
    rng = random.Random(7)
    for _ in range(60):
        levels = random_levels(rng, 40.0)
        mine = ref.regions_hops(levels, -45.0)
        theirs = voiced_regions(np.asarray(levels, dtype=np.float64), ref.HOP, -45.0, ref.C["REGION_MIN_SILENCE_S"],
                                ref.C["REGION_MIN_LEN_S"])
        assert [(round(a * ref.HOP, 6), round(b * ref.HOP, 6)) for a, b in mine] == [(round(a, 6), round(b, 6)) for a, b in theirs]


def test_levels_are_worked_out_the_way_freeforms_envelope_does(tmp_path):
    import wave
    from freeform_studio.audio import rms_envelope
    rng = np.random.RandomState(3)
    samples = (rng.randn(48000 * 2) * 3000).astype("<i2")
    path = tmp_path / "x.wav"
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(48000)
        w.writeframes(samples.tobytes())
    theirs, hop_s = rms_envelope(path)
    mine = np.asarray(ref.hop_levels(samples, 48000))
    assert hop_s == pytest.approx(ref.HOP) and len(mine) == len(theirs)
    assert np.max(np.abs(mine - theirs)) < 0.01


def test_metrics_agree_with_a_plain_calculation():
    samples = ref.square_samples([{"seconds": 0.5, "amp": 0}, {"seconds": 1.0, "amp": 8000}, {"seconds": 0.5, "amp": 0}], 48000)
    m = ref.clip_metrics(samples, 48000, -52.0)
    assert m["peak_dbfs"] == round(20 * math.log10(8000 / 32768), 1)
    assert m["rms_dbfs"] == round(20 * math.log10(8000 * math.sqrt(0.5) / 32768), 1)
    assert m["clipped_samples"] == 0 and m["speech"] == {"start_s": 0.5, "end_s": 1.5}


def test_the_speech_threshold_follows_the_noise_floor_within_its_limits():
    assert ref.threshold_db(None) == -45.0
    assert ref.threshold_db(-62.0) == -52.0
    assert ref.threshold_db(-90.0) == -55.0       # never lower than the minimum
    assert ref.threshold_db(-20.0) == -30.0       # never higher than the maximum


# ------------------------------------------------------------------ cards
def random_script(rng, paragraphs=6):
    words = "the quiet river runs past old stone houses while children laugh and dogs bark beside a small blue boat".split()
    out = []
    for _ in range(paragraphs):
        sentences = []
        for _ in range(rng.randint(1, 7)):
            n = rng.randint(2, 45)
            body = [rng.choice(words) for _ in range(n)]
            for k in range(3, n - 1, rng.randint(5, 12)):
                body[k] += rng.choice([",", ";", ":"])
            body[0] = body[0].capitalize()
            sentences.append(" ".join(body) + rng.choice([".", "!", "?"]))
        out.append(" ".join(sentences))
    return "\n\n".join(out)


@pytest.mark.parametrize("pace", [1.5, 2.6, 4.0])
def test_cards_keep_every_word_in_order_and_stay_within_limits(pace):
    rng = random.Random(11)
    for _ in range(40):
        text = random_script(rng)
        cards = ref.split_cards(text, pace)
        assert " ".join(c["text"] for c in cards).split() == text.split()
        max_words = max(max(6, math.floor(pace * ref.C["TARGET_S"])), math.floor(pace * ref.C["MAX_EST_S"]))
        for c in cards:
            assert len(c["text"]) <= ref.C["MAX_CARD_CHARS"]
            assert 1 <= c["words"] <= max_words
            assert "long" not in c["warnings"]       # built within the limit for the pace they were made at
            assert "\n" not in c["text"]


def test_a_card_never_spans_a_paragraph_break():
    cards = ref.split_cards("One short paragraph here.\n\nAnother short paragraph here.")
    assert [c["text"] for c in cards] == ["One short paragraph here.", "Another short paragraph here."]


# ------------------------------------------------------------------ hands-free detector
def test_detector_clips_are_ordered_inside_the_stream_and_never_overlap():
    rng = random.Random(21)
    for _ in range(80):
        levels = random_levels(rng, 120.0)
        events = ref.run_detector(levels, -45.0)
        total = len(levels) * ref.HOP
        prev_end = 0.0
        for e in events:
            if e["event"] != "clip":
                continue
            assert e["start_s"] >= prev_end - 1e-9, "a clip reached back into the one before it"
            assert e["start_s"] <= e["speech_start_s"] < e["speech_end_s"] <= e["end_s"] + 1e-9
            assert e["end_s"] <= total + 1e-9
            assert e["end_s"] - e["start_s"] <= ref.C["HARD_CLIP_HOPS"] * ref.HOP + 1e-9
            prev_end = e["end_s"]


def test_a_pause_shorter_than_the_end_wait_does_not_split_a_card():
    events = ref.run_detector(ref.levels_from_runs([[0.5, -70], [1.0, -20], [0.1, -70], [1.5, -20], [2.0, -70]]), -45.0)
    assert len(events) == 1 and events[0]["speech_start_s"] == 0.5 and events[0]["speech_end_s"] == 3.1


# ------------------------------------------------------------------ proposed segments
def test_proposed_segments_are_ordered_inside_the_recording_short_enough_and_cover_all_speech():
    rng = random.Random(5)
    for trial in range(200):
        levels = random_levels(rng, rng.choice([8.0, 25.0, 70.0]))
        duration = len(levels) * ref.HOP
        segs = ref.propose_segments(levels, -45.0)
        prev_end = 0.0
        for s in segs:
            assert 0.0 <= s["start_s"] < s["end_s"] <= duration + 1e-9
            assert s["start_s"] >= prev_end - 1e-9, f"trial {trial}: segments overlap"
            assert s["end_s"] - s["start_s"] <= ref.C["MAX_CLIP_S"] + 1e-9, f"trial {trial}: a segment is {s['end_s'] - s['start_s']:.3f}s"
            assert s["end_kind"] in ("pause", "forced", "end")
            prev_end = s["end_s"]
        assert segs == [] or segs[-1]["end_kind"] == "end"
        for a, b in ref.regions_hops(levels, -45.0):                      # every voiced hop sits inside some segment
            for h in range(a, b, 7):
                t = (h + 0.5) * ref.HOP
                assert any(s["start_s"] <= t <= s["end_s"] for s in segs), f"trial {trial}: speech at {t:.2f}s is in no segment"


def test_a_forced_cut_is_exact_so_the_two_neighbours_share_one_time():
    segs = ref.propose_segments(ref.levels_from_runs([[0.3, -70], [15.0, -20], [0.3, -70]]), -45.0)
    forced = [i for i, s in enumerate(segs) if s["end_kind"] == "forced"]
    assert forced, "15 s of unbroken speech must be cut somewhere"
    for i in forced:
        assert segs[i]["end_s"] == segs[i + 1]["start_s"]


# ------------------------------------------------------------------ the example manifest
def test_the_example_manifest_is_internally_consistent():
    m = json.loads((DATA / "manifest_example.json").read_text(encoding="utf-8"))
    assert m["schema"] == "ack-training-capture/1"
    path_ok = re.compile(r"^sessions/s\d{8}-\d{6}-[0-9a-f]{4}/(clips/\d{4,5}\.wav|session\.wav)$")
    listed = [f["path"] for f in m["files"]]
    assert len(listed) == len(set(listed)), "a file is listed twice"
    assert all(path_ok.match(p) for p in listed)
    assert all(re.fullmatch(r"[0-9a-f]{64}", f["sha256"]) and f["bytes"] > 0 for f in m["files"])
    used = []
    ids = [s["id"] for s in m["sessions"]]
    assert len(ids) == len(set(ids))
    for s in m["sessions"]:
        assert re.fullmatch(r"s\d{8}-\d{6}-[0-9a-f]{4}", s["id"])
        if s["mode"] == "script":
            idx = [c["index"] for c in s["clips"]]
            assert idx == sorted(set(idx)) and idx[0] == 1
            for c in s["clips"]:
                assert c["file"].startswith(f"sessions/{s['id']}/clips/") and len(c["text"]) <= ref.C["MAX_CARD_CHARS"]
                used.append(c["file"])
        else:
            assert s["mode"] == "free"
            used.append(s["recording"]["file"])
            for p in s["recording"]["proposed_segments"]:
                assert 0 <= p["start_s"] < p["end_s"] <= s["recording"]["duration_s"] and p["end_s"] - p["start_s"] <= ref.C["MAX_CLIP_S"]
    assert sorted(used) == sorted(listed), "every listed file belongs to a session and every session file is listed"
