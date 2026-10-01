# SPDX-License-Identifier: GPL-3.0-or-later
"""Corrects word timings against the actual audio.

Whisper's word timestamps are good on average but have a known weakness: a word next to a pause can absorb
the silence (its span stretches across the quiet part), and occasionally a short word gets a span that lies
entirely in silence. Cutting clips from those times gives clips that start or end in dead air, or a one-word
"sentence" separated from the rest by a pause that doesn't really belong to it.

This checks each word against the audio level and fixes only clear cases, leaving well-timed words untouched.
The raw recognizer output is never modified; a corrected copy is returned.
"""
from __future__ import annotations

import copy
from typing import Any, Dict, List, Tuple

import numpy as np

from .audio import voiced_regions

ABSORBED_SILENCE_S = 0.25   # only trim silence at a word's edge when there is at least this much of it
LEAD_KEEP_S = 0.06          # ...and leave this much before the first sound
TAIL_KEEP_S = 0.08          # ...and this much after the last
MAX_SNAP_DISTANCE_S = 3.0   # a word with no sound in its span is moved only if speech is within this distance
MIN_WORD_S = 0.03


def speech_threshold(db: np.ndarray) -> float:
    """A level (dBFS) separating speech from room noise, adapted to this recording."""
    if len(db) == 0:
        return -45.0
    floor = float(np.percentile(db, 10))
    top = float(np.percentile(db, 95))
    return float(min(max(max(floor + 8.0, top - 35.0), -60.0), -30.0))


def refine_word_times(asr: Dict[str, Any], db: np.ndarray, hop_s: float) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    out = copy.deepcopy(asr)
    stats: Dict[str, Any] = {"moved": 0, "trimmed": 0, "threshold_db": None}
    if len(db) == 0:
        return out, stats
    thr = speech_threshold(db)
    stats["threshold_db"] = round(thr, 1)
    regions = voiced_regions(db, hop_s, thresh_db=thr, min_silence_s=0.08, min_len_s=0.03)
    words: List[Dict[str, Any]] = []
    position: Dict[int, str] = {}  # id(word) -> "first" | "last" | "mid" within its recognizer segment
    for seg in out.get("segments", []):
        seg_words = seg.get("words", [])
        for k, w in enumerate(seg_words):
            words.append(w)
            position[id(w)] = "first" if k == 0 else ("last" if k == len(seg_words) - 1 else "mid")
    if not regions or not words:
        return out, stats
    starts = np.array([r[0] for r in regions])
    ends = np.array([r[1] for r in regions])

    for w in words:
        s, e = float(w["s"]), float(w["e"])
        i0 = int(np.searchsorted(ends, s, side="right"))  # first region that ends after the word starts
        overlaps = []
        i = i0
        while i < len(regions) and starts[i] < e:
            overlaps.append(regions[i])
            i += 1
        voiced = sum(min(e, b) - max(s, a) for a, b in overlaps)

        if voiced >= 0.02:  # there is sound inside the word: trim only clearly absorbed silence at its edges
            first = max(s, overlaps[0][0])
            last = min(e, overlaps[-1][1])
            ns = max(s, first - LEAD_KEEP_S) if first - s > ABSORBED_SILENCE_S else s
            ne = min(e, last + TAIL_KEEP_S) if e - last > ABSORBED_SILENCE_S else e
            if (ns, ne) != (s, e):
                stats["trimmed"] += 1
                w["s"], w["e"] = round(ns, 3), round(ne, 3)
            continue

        # No sound inside its span at all: the timing is wrong. Place it at the nearest speech.
        after = regions[i0] if i0 < len(regions) else None
        before = regions[i0 - 1] if i0 > 0 else None
        d_after = (after[0] - e) if after else float("inf")
        d_before = (s - before[1]) if before else float("inf")
        if min(d_after, d_before) > MAX_SNAP_DISTANCE_S:
            continue
        # Where the recognizer stamped it tells us which side it really belongs to: the first word of a segment
        # inherits the previous segment's end time (so it belongs to the speech AFTER it); the last word of a
        # segment trails off into the following silence (so it belongs to the speech BEFORE it).
        where = position[id(w)]
        if where == "first" and d_after <= MAX_SNAP_DISTANCE_S:
            use_after = True
        elif where == "last" and d_before <= MAX_SNAP_DISTANCE_S:
            use_after = False
        else:
            use_after = d_after <= d_before
        est = min(0.6, max(0.12, 0.06 * len(w["w"]) + 0.1))
        if use_after:
            ns = after[0]
            ne = min(after[1], ns + est)
        else:
            ne = before[1]
            ns = max(before[0], ne - est)
        w["s"], w["e"], w["m"] = round(ns, 3), round(ne, 3), True
        stats["moved"] += 1

    words.sort(key=lambda w: (w["s"], w["e"]))  # same dict objects, so fixes below apply to `out`
    for prev, cur in zip(words, words[1:]):
        if cur["s"] < prev["e"]:
            if cur["s"] - prev["s"] >= 2 * MIN_WORD_S:
                prev["e"] = round(cur["s"] - 0.001, 3)
            else:
                cur["s"] = prev["e"]
                cur["e"] = max(cur["e"], round(cur["s"] + MIN_WORD_S, 3))
    return out, stats
