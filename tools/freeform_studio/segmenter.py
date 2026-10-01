# SPDX-License-Identifier: GPL-3.0-or-later
"""Turns a flat list of timed words into review-sized segments (roughly one sentence each).

Rules, in order:
  1. Split after sentence-ending punctuation when the next word looks like a new sentence or a real pause
     follows; always split on a long silence.
  2. Split anything longer than the cap at the best internal gap (preferring punctuation).
  3. Merge fragments that are too short into a close neighbour.
  4. Pad each segment a little so consonants aren't clipped, never overlapping a neighbour.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

_TERMINAL = re.compile(r"[.!?][\"'”’)\]]*$")
_SOFT = re.compile(r"[,;:—–-][\"'”’)]*$")
_NEW_SENTENCE = re.compile(r"^[\"'“‘(]*[A-Z0-9]")
_ABBREV = {"mr.", "mrs.", "ms.", "dr.", "st.", "vs.", "etc.", "e.g.", "i.e.", "no.", "jr.", "sr.", "prof.", "gen.", "col."}


@dataclass
class SegOptions:
    max_s: float = 11.5
    min_s: float = 1.0
    pad_lead_s: float = 0.12
    pad_tail_s: float = 0.20
    hard_gap_s: float = 1.0
    sentence_gap_s: float = 0.20
    low_conf: float = 0.5


def _is_sentence_end(word: str) -> bool:
    return bool(_TERMINAL.search(word)) and word.lower().rstrip("\"'”’)]") not in _ABBREV


def join_words(words: List[Dict[str, Any]]) -> str:
    out = ""
    for i, w in enumerate(words):
        if i and not w.get("j"):
            out += " "
        out += w["w"]
    return out


def _span(words: List[Dict[str, Any]]) -> float:
    return words[-1]["e"] - words[0]["s"]


def _split_by_sentence(words: List[Dict[str, Any]], o: SegOptions) -> List[List[Dict[str, Any]]]:
    groups: List[List[Dict[str, Any]]] = []
    cur: List[Dict[str, Any]] = []
    for i, w in enumerate(words):
        cur.append(w)
        if i + 1 == len(words):
            break
        nxt = words[i + 1]
        gap = nxt["s"] - w["e"]
        boundary = gap >= o.hard_gap_s or (
            _is_sentence_end(w["w"]) and (gap >= o.sentence_gap_s or bool(_NEW_SENTENCE.match(nxt["w"]))))
        if boundary:
            groups.append(cur)
            cur = []
    if cur:
        groups.append(cur)
    return groups


def _split_long(words: List[Dict[str, Any]], o: SegOptions) -> List[List[Dict[str, Any]]]:
    budget = o.max_s - (o.pad_lead_s + o.pad_tail_s)
    if len(words) < 2 or _span(words) <= budget:
        return [words]
    total = _span(words)
    best_k, best_score = None, None
    for k in range(len(words) - 1):  # split after word k
        left = words[k]["e"] - words[0]["s"]
        right = words[-1]["e"] - words[k + 1]["s"]
        if left < 0.25 * total or right < 0.25 * total:
            continue
        gap = words[k + 1]["s"] - words[k]["e"]
        bonus = 0.5 if _TERMINAL.search(words[k]["w"]) else (0.25 if _SOFT.search(words[k]["w"]) else 0.0)
        score = gap + bonus - 0.02 * abs(left - right)  # gentle pull toward the middle
        if best_score is None or score > best_score:
            best_k, best_score = k, score
    if best_k is None:  # no acceptable candidate: cut in the middle by word count
        best_k = len(words) // 2 - 1
    return _split_long(words[: best_k + 1], o) + _split_long(words[best_k + 1:], o)


def _merge_short(groups: List[List[Dict[str, Any]]], o: SegOptions) -> List[List[Dict[str, Any]]]:
    budget = o.max_s - (o.pad_lead_s + o.pad_tail_s)
    changed = True
    while changed and len(groups) > 1:
        changed = False
        for i, g in enumerate(groups):
            if _span(g) >= o.min_s:
                continue
            prev_gap = g[0]["s"] - groups[i - 1][-1]["e"] if i > 0 else None
            next_gap = groups[i + 1][0]["s"] - g[-1]["e"] if i + 1 < len(groups) else None
            options = []
            if prev_gap is not None and prev_gap < 1.5 and (g[-1]["e"] - groups[i - 1][0]["s"]) <= budget:
                options.append((prev_gap, "prev"))
            if next_gap is not None and next_gap < 1.5 and (groups[i + 1][-1]["e"] - g[0]["s"]) <= budget:
                options.append((next_gap, "next"))
            if not options:
                continue
            _gap, side = min(options)
            if side == "prev":
                groups[i - 1] = groups[i - 1] + g
                del groups[i]
            else:
                groups[i + 1] = g + groups[i + 1]
                del groups[i]
            changed = True
            break
    return groups


def _flags(text: str, words: List[Dict[str, Any]], dur: float, stats: Dict[str, Optional[float]], o: SegOptions) -> List[str]:
    f: List[str] = []
    if not text.strip():
        f.append("empty")
    if dur < o.min_s:
        f.append("too_short")
    if dur > o.max_s:
        f.append("too_long")
    if any(w["p"] < o.low_conf for w in words):
        f.append("low_confidence")
    nsp, lp, cr = stats.get("no_speech_prob"), stats.get("avg_logprob"), stats.get("compression_ratio")
    if nsp is not None and lp is not None and nsp > 0.6 and lp < -1.0:
        f.append("possible_hallucination")
    if cr is not None and cr > 2.4:
        f.append("repetitive")
    if re.search(r"\d", text):
        f.append("has_digits")
    if re.search(r"\[[^\]]*\]|\([^)]*\)", text):
        f.append("bracket_tag")
    if re.search(r"[&@#%*_=+<>{}\\/|]", text):
        f.append("has_symbols")
    return f


def build_segments(asr: Dict[str, Any], duration: float, opts: Optional[SegOptions] = None) -> List[Dict[str, Any]]:
    o = opts or SegOptions()
    words: List[Dict[str, Any]] = []
    for seg in asr.get("segments", []):
        stats = {"no_speech_prob": seg.get("no_speech_prob"), "avg_logprob": seg.get("avg_logprob"),
                 "compression_ratio": seg.get("compression_ratio")}
        for w in seg.get("words", []):
            if not str(w.get("w", "")).strip():
                continue
            s, e = float(w["s"]), float(w["e"])
            item = {"w": str(w["w"]).strip(), "s": s, "e": max(s, e), "p": float(w.get("p", 1.0)), "_st": stats}
            if w.get("j"):
                item["j"] = True
            if w.get("m"):
                item["m"] = True
            words.append(item)
    words.sort(key=lambda w: (w["s"], w["e"]))
    if not words:
        return []

    groups: List[List[Dict[str, Any]]] = []
    for g in _split_by_sentence(words, o):
        groups.extend(_split_long(g, o))
    groups = _merge_short(groups, o)

    out: List[Dict[str, Any]] = []
    for idx, g in enumerate(groups):
        prev_end = groups[idx - 1][-1]["e"] if idx > 0 else None
        next_start = groups[idx + 1][0]["s"] if idx + 1 < len(groups) else None
        start = g[0]["s"] - o.pad_lead_s
        end = g[-1]["e"] + o.pad_tail_s
        if prev_end is not None:  # never reach past the midpoint of the silence between segments
            start = max(start, (prev_end + g[0]["s"]) / 2)
        if next_start is not None:
            end = min(end, (g[-1]["e"] + next_start) / 2)
        start, end = max(0.0, start), min(duration, end)
        text = join_words(g)
        stats = {
            "no_speech_prob": max((w["_st"]["no_speech_prob"] for w in g if w["_st"]["no_speech_prob"] is not None), default=None),
            "avg_logprob": min((w["_st"]["avg_logprob"] for w in g if w["_st"]["avg_logprob"] is not None), default=None),
            "compression_ratio": max((w["_st"]["compression_ratio"] for w in g if w["_st"]["compression_ratio"] is not None), default=None),
        }
        clean_words = []
        for w in g:
            cw = {"w": w["w"], "s": round(w["s"], 3), "e": round(w["e"], 3), "p": round(w["p"], 3)}
            for k in ("j", "m"):
                if w.get(k):
                    cw[k] = True
            clean_words.append(cw)
        out.append({
            "id": f"s{idx + 1:03d}",
            "start": round(start, 3), "end": round(end, 3),
            "text": text, "words": clean_words,
            "status": "pending", "tags": [], "note": "",
            "flags": _flags(text, clean_words, end - start, stats, o),
            "auto": {"start": round(start, 3), "end": round(end, 3), "text": text},
        })
    return out
