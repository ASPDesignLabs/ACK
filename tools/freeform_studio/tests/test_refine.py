# SPDX-License-Identifier: GPL-3.0-or-later
import numpy as np

from freeform_studio.refine import refine_word_times, speech_threshold
from freeform_studio.segmenter import build_segments

HOP = 0.01


def envelope(seconds, bursts, quiet=-80.0, loud=-20.0):
    db = np.full(int(seconds / HOP), quiet, dtype=np.float32)
    for a, b in bursts:
        db[int(a / HOP):int(b / HOP)] = loud
    return db


def asr(*words):
    """One recognizer segment. words: (text, start, end)"""
    return asr_segments(list(words))


def asr_segments(*segments):
    """Several recognizer segments, each a list of (text, start, end)."""
    return {"segments": [{"id": i, "no_speech_prob": 0.01, "avg_logprob": -0.2, "compression_ratio": 1.2,
                          "words": [{"w": t, "s": s, "e": e, "p": 0.95} for t, s, e in seg]}
                         for i, seg in enumerate(segments)]}


def times(res):
    return [(w["w"], w["s"], w["e"]) for seg in res["segments"] for w in seg["words"]]


def test_well_timed_words_are_left_exactly_alone():
    db = envelope(6.0, [(1.0, 3.0), (4.0, 5.5)])
    original = asr(("Hello", 1.0, 1.8), ("there.", 1.8, 3.0), ("Again", 4.0, 4.7), ("now.", 4.7, 5.5))
    out, stats = refine_word_times(original, db, HOP)
    assert times(out) == times(original) and stats["moved"] == 0 and stats["trimmed"] == 0


def test_word_that_absorbed_leading_silence_is_trimmed_to_the_sound():
    db = envelope(6.0, [(2.0, 4.0)])
    out, stats = refine_word_times(asr(("The", 0.5, 2.6), ("end.", 2.6, 4.0)), db, HOP)
    the = times(out)[0]
    assert stats["trimmed"] == 1 and abs(the[1] - 1.94) < 0.03 and the[2] == 2.6  # starts just before the sound


def test_word_that_absorbed_trailing_silence_is_trimmed():
    db = envelope(6.0, [(1.0, 2.0)])
    out, _ = refine_word_times(asr(("Done.", 1.0, 4.5)), db, HOP)
    assert abs(times(out)[0][2] - 2.08) < 0.03


def test_phantom_first_word_of_a_segment_goes_to_the_speech_after_it():
    # the real-world case: "A" starts a new segment but was stamped right after the previous speech, inside a
    # long pause; the sound it belongs to only begins a second word later
    db = envelope(10.0, [(1.0, 2.0), (6.0, 8.0)])
    original = asr_segments([("Hello", 1.0, 1.5), ("there.", 1.5, 2.0)],
                            [("A", 2.05, 3.6), ("ripple", 6.2, 6.8), ("moved.", 6.8, 8.0)])
    out, stats = refine_word_times(original, db, HOP)
    got = {w: (s, e) for w, s, e in times(out)}
    assert stats["moved"] == 1
    assert abs(got["A"][0] - 6.0) < 0.02 and got["A"][1] <= got["ripple"][0]  # now sits at the start of that speech
    # ...so the segmenter no longer cuts "A" off as its own clip
    texts = [s["text"] for s in build_segments(out, 10.0)]
    assert texts == ["Hello there.", "A ripple moved."]
    assert [s["text"] for s in build_segments(original, 10.0)] != texts  # and it did before the fix


def test_phantom_last_word_of_a_segment_goes_to_the_speech_before_it():
    db = envelope(10.0, [(1.0, 2.0), (6.0, 8.0)])
    original = asr_segments([("Hello", 1.0, 1.5), ("there.", 2.4, 3.9)], [("Next", 6.0, 6.5), ("part.", 6.5, 8.0)])
    out, stats = refine_word_times(original, db, HOP)
    there = {w: (s, e) for w, s, e in times(out)}["there."]
    assert stats["moved"] == 1 and abs(there[1] - 2.0) < 0.02  # ends where the sound ends, not in the pause


def test_phantom_word_mid_segment_goes_to_the_nearest_speech():
    db = envelope(10.0, [(1.0, 2.0), (6.0, 8.0)])
    out, _ = refine_word_times(asr(("Hi", 1.0, 1.5), ("um", 2.3, 2.9), ("there.", 6.0, 8.0)), db, HOP)
    um = {w: (s, e) for w, s, e in times(out)}["um"]
    assert um[1] <= 2.001  # 2.3 is 0.3s after the first burst but 3.1s before the second


def test_far_from_any_speech_is_not_moved():
    db = envelope(30.0, [(1.0, 2.0)])
    out, stats = refine_word_times(asr(("Hi.", 1.0, 2.0), ("Ghost", 20.0, 21.0)), db, HOP)
    assert stats["moved"] == 0 and times(out)[1] == ("Ghost", 20.0, 21.0)


def test_result_is_ordered_and_non_overlapping_and_input_is_not_modified():
    db = envelope(8.0, [(1.0, 5.0)])
    original = asr(("a", 1.0, 1.5), ("b", 1.4, 2.0), ("c", 2.0, 2.0), ("d", 6.0, 6.5))
    snapshot = times(original)
    out, _ = refine_word_times(original, db, HOP)
    assert times(original) == snapshot  # raw recognizer output is never changed
    ws = sorted(times(out), key=lambda t: t[1])
    for (_, s1, e1), (_, s2, _e2) in zip(ws, ws[1:]):
        assert e1 <= s2 + 1e-6 and s1 < e1


def test_threshold_adapts_to_the_recording_and_handles_silence():
    quiet_room = envelope(10.0, [(1.0, 9.0)], quiet=-70.0, loud=-25.0)
    noisy_room = envelope(10.0, [(1.0, 9.0)], quiet=-45.0, loud=-20.0)
    assert speech_threshold(noisy_room) > speech_threshold(quiet_room)
    assert -60.0 <= speech_threshold(np.zeros(0, dtype=np.float32)) <= -30.0
    out, stats = refine_word_times(asr(("x", 0.1, 0.5)), np.full(100, -120.0, dtype=np.float32), HOP)
    assert times(out) == [("x", 0.1, 0.5)]  # nothing audible at all: leave it alone rather than guess
