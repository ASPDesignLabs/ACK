# SPDX-License-Identifier: GPL-3.0-or-later
"""Proposed pieces for a recording that came from ACK (see ack_import.py).

A recording made in the browser has to be cut into pieces by guessing where sentences end. An ACK script session already knows:
every clip was recorded on its own, so each clip is one piece, bounded by where ACK recorded it, with the words the recognizer heard
inside it. The pieces are still ordinary pieces: the same fields, the same review, the same edit rules, and a person can still
move a cut point, split or join them.

Free-speech sessions are cut the usual way, from the recognizer's word timings, because those are better information than the
phone's silence-only guesses. The phone's suggested cuts are the fallback when nothing was recognized, so there is still something
to review and type against.
"""
from __future__ import annotations

import bisect
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .ack_checks import check_free, check_script
from .audio import rms_envelope
from .refine import refine_word_times
from .segmenter import SegOptions, build_segments, ingest_words, make_segment, split_long

MIN_PIECE_S = 0.05      # the shortest piece an edit document accepts


def usable_notes(notes: Any) -> bool:
    """Whether ack_clips.json holds what this module needs. Anything else falls back to cutting by sentences."""
    if not isinstance(notes, dict):
        return False
    if notes.get("mode") == "script":
        clips = notes.get("clips")
        return isinstance(clips, list) and bool(clips) and all(
            isinstance(c, dict) and isinstance(c.get("start_s"), (int, float)) and isinstance(c.get("end_s"), (int, float))
            and c["end_s"] > c["start_s"] for c in clips) and all(a["end_s"] <= b["start_s"] + 1e-6 for a, b in zip(clips, clips[1:]))
    return notes.get("mode") == "free"


def _assign(words: List[Dict[str, Any]], clips: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
    """Each word goes to the clip whose stretch of the recording contains its middle; one in a gap goes to the nearer clip."""
    starts = [c["start_s"] for c in clips]
    ends = [c["end_s"] for c in clips]
    buckets: List[List[Dict[str, Any]]] = [[] for _ in clips]
    for w in words:
        mid = (w["s"] + w["e"]) / 2.0
        k = bisect.bisect_right(starts, mid) - 1
        if k >= 0 and mid <= ends[k]:
            pick = k
        else:
            near: List[Tuple[float, int]] = []
            if k >= 0:
                near.append((mid - ends[k], k))
            if k + 1 < len(clips):
                near.append((starts[k + 1] - mid, k + 1))
            pick = min(near)[1]
        buckets[pick].append(w)
    return buckets


def script_segments_with_clips(refined_asr: Dict[str, Any], duration: float, notes: Dict[str, Any],
                               o: SegOptions) -> Tuple[List[Dict[str, Any]], List[int]]:
    """The pieces, and for each piece the position of the clip it came from in notes["clips"]."""
    clips = notes["clips"]
    buckets = _assign(ingest_words(refined_asr), clips)
    out: List[Dict[str, Any]] = []
    clip_of: List[int] = []
    for position, (clip, words) in enumerate(zip(clips, buckets)):
        lo, hi = max(0.0, float(clip["start_s"])), min(duration, float(clip["end_s"]))
        spans: List[Tuple[List[Dict[str, Any]], float, float]] = []
        if words:
            parts = split_long(words, o)            # normally one piece; more only if the clip ran past the length limit
            for k, g in enumerate(parts):
                a, b = g[0]["s"] - o.pad_lead_s, g[-1]["e"] + o.pad_tail_s
                if k > 0:
                    a = max(a, (parts[k - 1][-1]["e"] + g[0]["s"]) / 2)
                if k + 1 < len(parts):
                    b = min(b, (g[-1]["e"] + parts[k + 1][0]["s"]) / 2)
                spans.append((g, max(lo, a), min(hi, b)))
        else:                                       # nothing recognized: keep the clip so it can still be typed from its card
            sp = clip.get("speech")
            if isinstance(sp, dict) and isinstance(sp.get("start_s"), (int, float)) and isinstance(sp.get("end_s"), (int, float)):
                a, b = lo + sp["start_s"] - o.pad_lead_s, lo + sp["end_s"] + o.pad_tail_s
                spans.append(([], max(lo, a), min(hi, b)))
            else:
                spans.append(([], lo, hi))
        for g, a, b in spans:
            if b - a >= MIN_PIECE_S:
                out.append(make_segment(len(out), g, a, b, o))
                clip_of.append(position)
    return out, clip_of


def script_segments(refined_asr: Dict[str, Any], duration: float, notes: Dict[str, Any], o: SegOptions) -> List[Dict[str, Any]]:
    return script_segments_with_clips(refined_asr, duration, notes, o)[0]


def free_segments(refined_asr: Dict[str, Any], duration: float, notes: Dict[str, Any], o: SegOptions) -> List[Dict[str, Any]]:
    segs = build_segments(refined_asr, duration, o)
    if segs:
        return segs
    out: List[Dict[str, Any]] = []
    for p in notes.get("proposed_segments") or []:
        a, b = max(0.0, float(p["start_s"])), min(duration, float(p["end_s"]))
        if b - a >= MIN_PIECE_S:
            out.append(make_segment(len(out), [], a, b, o))
    return out


def propose_segments_ack(asr: Dict[str, Any], wav_path: Path, duration: float, notes: Dict[str, Any],
                         opts: Optional[SegOptions] = None) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    o = opts or SegOptions()
    db, hop = rms_envelope(wav_path)
    refined, stats = refine_word_times(asr, db, hop)
    if notes.get("mode") == "script":
        segs, clip_of = script_segments_with_clips(refined, duration, notes, o)
        stats["ack_checks"] = check_script(segs, clip_of, notes, db, hop, wav_path)
    else:
        segs = free_segments(refined, duration, notes, o)
        stats["ack_checks"] = check_free(segs, notes, db, hop, wav_path)
    return segs, stats
