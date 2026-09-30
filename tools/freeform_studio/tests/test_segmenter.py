from freeform_studio.segmenter import SegOptions, build_segments


def words(spec, start=0.0):
    """spec: list of (text, duration, gap_after). Returns asr dict with one segment."""
    out, t = [], start
    for text, dur, gap in spec:
        out.append({"w": text, "s": round(t, 3), "e": round(t + dur, 3), "p": 0.95})
        t += dur + gap
    return {"segments": [{"id": 0, "words": out, "no_speech_prob": 0.01, "avg_logprob": -0.2, "compression_ratio": 1.1}]}


def test_splits_at_sentence_ends_with_capital_next():
    asr = words([("Hello", .8, .05), ("there.", .8, .1), ("How", .6, .05), ("are", .6, .05), ("you?", .8, 0)])
    segs = build_segments(asr, 5.0)
    assert [s["text"] for s in segs] == ["Hello there.", "How are you?"]


def test_abbreviation_is_not_a_sentence_end():
    asr = words([("I", .3, .02), ("met", .4, .02), ("Dr.", .4, .05), ("Smith", .5, .02), ("today.", .6, 0)])
    segs = build_segments(asr, 3.0)
    assert len(segs) == 1 and segs[0]["text"] == "I met Dr. Smith today."


def test_long_silence_splits_without_punctuation():
    asr = words([("and", .6, .05), ("then", .6, 1.5), ("we", .6, .05), ("left", .7, 0)])
    segs = build_segments(asr, 6.0)
    assert [s["text"] for s in segs] == ["and then", "we left"]


def test_over_length_splits_at_the_biggest_gap_and_respects_cap():
    spec = [(f"w{i}", .5, 0.05) for i in range(40)]  # ~22s of unpunctuated speech
    spec[19] = ("w19,", .5, 0.6)  # a comma and a real pause near the middle
    asr = words(spec)
    o = SegOptions(max_s=11.5)
    segs = build_segments(asr, 24.0, o)
    assert len(segs) >= 2
    assert all((s["end"] - s["start"]) <= o.max_s + 1e-6 for s in segs)
    assert any(s["text"].endswith("w19,") for s in segs)


def test_tiny_fragment_merges_into_a_close_neighbour():
    asr = words([("Yes.", .3, .3), ("That", .8, .05), ("is", .6, .05), ("right", .9, .05), ("indeed.", .9, 0)])
    segs = build_segments(asr, 5.0)
    assert len(segs) == 1 and "too_short" not in segs[0]["flags"]


def test_padding_never_overlaps_and_stays_inside_the_recording():
    asr = words([("One", .9, .1), ("thing.", .9, .12), ("Two", .9, .05), ("things.", .9, 0)], start=0.05)
    segs = build_segments(asr, 3.7)
    assert segs[0]["start"] >= 0.0 and segs[-1]["end"] <= 3.7
    for a, b in zip(segs, segs[1:]):
        assert a["end"] <= b["start"] + 1e-9
    assert all(s["start"] < s["end"] for s in segs)


def test_flags():
    asr = words([("Call", .7, .05), ("555", .7, .05), ("[MUSIC]", .7, .05), ("now.", .7, 0)])
    asr["segments"][0]["words"][1]["p"] = 0.2
    (seg,) = build_segments(asr, 4.0)
    assert {"low_confidence", "has_digits", "bracket_tag"} <= set(seg["flags"])
    asr["segments"][0].update(no_speech_prob=0.9, avg_logprob=-1.6, compression_ratio=3.0)
    (seg,) = build_segments(asr, 4.0)
    assert {"possible_hallucination", "repetitive"} <= set(seg["flags"])


def test_auto_snapshot_and_ids_and_defaults():
    asr = words([("Hello", .8, .05), ("there.", .8, .1), ("How", .6, .05), ("are", .6, .05), ("you?", .8, 0)])
    segs = build_segments(asr, 5.0)
    assert [s["id"] for s in segs] == ["s001", "s002"]
    assert all(s["status"] == "pending" and s["tags"] == [] and s["note"] == "" for s in segs)
    assert segs[0]["auto"]["text"] == segs[0]["text"]


def test_empty_input():
    assert build_segments({"segments": []}, 1.0) == []
    assert build_segments({"segments": [{"id": 0, "words": [{"w": " ", "s": 0, "e": 1, "p": 1}]}]}, 1.0) == []


def test_joined_pieces_rebuild_the_original_text_without_stray_spaces():
    asr = words([("The", .3, .02), ("archive", .5, .02), ("cataloged", .6, .02), ("11", .4, 0), (",000", .5, .02),
                 ("testimonies", .8, .02), ("before", .5, .02), ("admitting,", .8, 0)])
    asr["segments"][0]["words"][4]["j"] = True
    (seg,) = build_segments(asr, 6.0)
    assert seg["text"] == "The archive cataloged 11,000 testimonies before admitting,"
    assert any(w.get("j") for w in seg["words"])  # kept, so the review screen can re-join after edits
