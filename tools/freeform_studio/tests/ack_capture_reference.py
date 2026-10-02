# SPDX-License-Identifier: GPL-3.0-or-later
"""Executable specification for the ACK training-capture format (docs/ACK_TRAINING_CAPTURE_FORMAT.md).

Not shipped code: it exists so the Kotlin in ACK and the Python in Freeform Studio can both be held to the same answers.
Everything that decides a boundary works in whole 10 ms hops (integers), so no two languages can disagree about rounding;
seconds appear only when results are written out.

    python tools/freeform_studio/tests/ack_capture_reference.py --write    # regenerate tests/data/ack_capture/*.json
    python tools/freeform_studio/tests/ack_capture_reference.py            # say whether the files are up to date
"""
from __future__ import annotations

import json
import math
import random
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

ROOT = Path(__file__).resolve().parents[2]            # tools/
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
DATA_DIR = Path(__file__).resolve().parent / "data" / "ack_capture"

CONSTANTS: Dict[str, Any] = {
    "HOP_S": 0.01,
    "MAX_CLIP_S": 11.5,
    "MIN_CLIP_S": 1.0,
    "THRESH_DEFAULT_DB": -45.0,
    "THRESH_OFFSET_DB": 10.0,
    "THRESH_MIN_DB": -55.0,
    "THRESH_MAX_DB": -30.0,
    "NOISE_CHECK_S": 2.0,
    "REGION_MIN_SILENCE_S": 0.3,
    "REGION_MIN_LEN_S": 0.1,
    "DEFAULT_PACE_WPS": 2.6,
    "PACE_MIN_WPS": 1.5,
    "PACE_MAX_WPS": 4.0,
    "PACE_MIN_CLIPS": 5,
    "TARGET_S": 9.5,
    "MAX_EST_S": 11.0,
    "MIN_CARD_WORDS": 3,
    "MIN_SPLIT_WORDS": 4,
    "MAX_CARD_CHARS": 600,
    "PRE_ROLL_HOPS": 50,
    "START_RUN_HOPS": 10,
    "END_SILENCE_HOPS": 120,
    "TAIL_HOPS": 40,
    "NO_SPEECH_TIMEOUT_HOPS": 2000,
    "HARD_CLIP_HOPS": 3000,
    "CUT_AFTER_S": 8.0,
    "FORCE_AT_S": 11.0,
    "FORCE_WINDOW_S": 2.0,
    "MIN_SEG_S": 1.0,
    "PAD_LEAD_S": 0.15,
    "PAD_TAIL_S": 0.25,
    "GAP_S": 0.4,
    "MAX_PACKAGE_BYTES": 2000000000,
    "MAX_ENTRIES": 20000,
    "MAX_MANIFEST_BYTES": 8388608,
    "MAX_SESSIONS": 200,
    "MAX_CLIPS_PER_SESSION": 5000,
    "MAX_FREE_SESSION_S": 5400,
}
C = CONSTANTS
HOP = C["HOP_S"]


def hops(seconds: float) -> int:
    """Seconds -> whole hops, the way every rule below uses them."""
    return int(round(seconds / HOP))


REGION_MIN_SILENCE = hops(C["REGION_MIN_SILENCE_S"])   # 30
REGION_MIN_LEN = hops(C["REGION_MIN_LEN_S"])           # 10
CUT_AFTER = hops(C["CUT_AFTER_S"])                     # 800
FORCE_AT = hops(C["FORCE_AT_S"])                       # 1100
FORCE_WINDOW = hops(C["FORCE_WINDOW_S"])               # 200
MIN_SEG = hops(C["MIN_SEG_S"])                         # 100
PAD_LEAD = hops(C["PAD_LEAD_S"])                       # 15
PAD_TAIL = hops(C["PAD_TAIL_S"])                       # 25


def rnd(x: float, nd: int) -> float:
    """Round half away from zero (what the Kotlin side must do too), not Python's banker's rounding."""
    f = 10 ** nd
    r = math.floor(abs(x) * f + 0.5) / f
    return -r if (x < 0 and r != 0) else r


def sec(h: float) -> float:
    return rnd(h * HOP, 3)


# ---------------------------------------------------------------- measurements (spec section 5)
def level_db(rms: float) -> float:
    return 20.0 * math.log10(max(rms, 1e-9) / 32768.0)


def clamp_floor(db: float) -> float:
    return max(db, -120.0)


def hop_levels(samples: np.ndarray, rate: int) -> List[float]:
    hop = rate // 100                      # whole samples per 10 ms, rounded down: 480 at 48000 Hz, 441 at 44100 Hz
    out = []
    for i in range(0, len(samples), hop):
        chunk = samples[i:i + hop].astype(np.float64)
        out.append(level_db(math.sqrt(float(np.mean(chunk * chunk)))))
    return out


def threshold_db(noise_floor_dbfs: Optional[float]) -> float:
    if noise_floor_dbfs is None:
        return C["THRESH_DEFAULT_DB"]
    return min(max(noise_floor_dbfs + C["THRESH_OFFSET_DB"], C["THRESH_MIN_DB"]), C["THRESH_MAX_DB"])


def regions_hops(levels: Sequence[float], thr: float) -> List[List[int]]:
    """Freeform's audio.voiced_regions, in whole hops: runs above the threshold, runs closer than REGION_MIN_SILENCE joined,
    joined runs shorter than REGION_MIN_LEN dropped."""
    runs: List[List[int]] = []
    start = None
    for i, lv in enumerate(levels):
        on = lv > thr
        if on and start is None:
            start = i
        elif not on and start is not None:
            runs.append([start, i])
            start = None
    if start is not None:
        runs.append([start, len(levels)])
    merged: List[List[int]] = []
    for r in runs:
        if merged and r[0] - merged[-1][1] < REGION_MIN_SILENCE:
            merged[-1][1] = r[1]
        else:
            merged.append(list(r))
    return [r for r in merged if r[1] - r[0] >= REGION_MIN_LEN]


def clip_metrics(samples: np.ndarray, rate: int, thr: float) -> Dict[str, Any]:
    x = samples.astype(np.int64)
    peak = int(np.max(np.abs(x))) if len(x) else 0
    rms = math.sqrt(float(np.mean(x.astype(np.float64) ** 2))) if len(x) else 0.0
    reg = regions_hops(hop_levels(samples, rate), thr)
    return {
        "peak_dbfs": rnd(clamp_floor(level_db(peak)), 1),
        "rms_dbfs": rnd(clamp_floor(level_db(rms)), 1),
        "clipped_samples": int(np.sum(np.abs(x) >= 32767)),
        "speech": {"start_s": sec(reg[0][0]), "end_s": sec(reg[-1][1])} if reg else None,
    }


# ---------------------------------------------------------------- cards (spec section 6)
_ABBREV = {"mr.", "mrs.", "ms.", "dr.", "st.", "vs.", "etc.", "e.g.", "i.e.", "no.", "jr.", "sr.", "prof.", "gen.", "col."}
_CLOSERS = "\"'”’)]"
_TERMINAL = re.compile(r"[.!?…][\"'”’)\]]*$")
_NEW_SENTENCE = re.compile(r"^[\"'“‘(\[]*[A-Z0-9]")
_STRONG = re.compile(r"[;:—–][\"'”’)\]]*$")
_COMMA = re.compile(r",[\"'”’)\]]*$")
_DIGIT = re.compile(r"\d")
_SYMBOL = re.compile(r"[&@#%*_=+<>{}\\/|]")


def _is_word(tok: str) -> bool:
    return any(unicodedata.category(ch)[0] in "LN" for ch in tok)     # a letter or a number of any script


def _wc(tokens: Sequence[str]) -> int:
    return sum(1 for t in tokens if _is_word(t))


def _paragraphs(text: str, lines: str) -> List[str]:
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\t", " ")
    text = "".join(ch for ch in text if ch == "\n" or (ch >= " " and ch != "\x7f"))
    if lines == "keep":
        return [ln.strip() for ln in text.split("\n") if ln.strip()]
    return [" ".join(p.split()) for p in re.split(r"\n\s*\n", text) if p.strip()]


def _sentences(tokens: List[str]) -> List[List[str]]:
    out: List[List[str]] = []
    cur: List[str] = []
    for i, t in enumerate(tokens):
        cur.append(t)
        nxt = tokens[i + 1] if i + 1 < len(tokens) else None
        if _TERMINAL.search(t) and t.lower().rstrip(_CLOSERS) not in _ABBREV and (nxt is None or _NEW_SENTENCE.match(nxt)):
            out.append(cur)
            cur = []
    if cur:
        out.append(cur)
    return out


def _split_long(tokens: List[str], max_words: int) -> List[List[str]]:
    n = _wc(tokens)
    if n <= max_words:
        return [tokens]
    best = None
    left = 0
    for i in range(len(tokens) - 1):                      # cut after token i
        left += 1 if _is_word(tokens[i]) else 0
        right = n - left
        if left < C["MIN_SPLIT_WORDS"] or right < C["MIN_SPLIT_WORDS"]:
            continue
        cls = 3 if _STRONG.search(tokens[i]) else (2 if _COMMA.search(tokens[i]) else 1)
        key = (cls, -abs(left - n / 2.0), -i)
        if best is None or key > best[0]:
            best = (key, i)
    if best is None:
        return [tokens]
    i = best[1]
    return _split_long(tokens[:i + 1], max_words) + _split_long(tokens[i + 1:], max_words)


def _merge_runts(cards: List[List[str]], max_words: int) -> List[List[str]]:
    changed = True
    while changed and len(cards) > 1:
        changed = False
        for idx, c in enumerate(cards):
            w = _wc(c)
            if w >= C["MIN_CARD_WORDS"]:
                continue
            if idx > 0 and _wc(cards[idx - 1]) + w <= max_words:
                cards[idx - 1] = cards[idx - 1] + c
                del cards[idx]
                changed = True
                break
            if idx + 1 < len(cards) and w + _wc(cards[idx + 1]) <= max_words:
                cards[idx + 1] = c + cards[idx + 1]
                del cards[idx]
                changed = True
                break
    return cards


def _cap_chars(text: str) -> List[str]:
    out = []
    limit = C["MAX_CARD_CHARS"]
    while len(text) > limit:
        cut = text.rfind(" ", 0, limit + 1)
        if cut <= 0:
            cut = limit
        out.append(text[:cut].rstrip())
        text = text[cut:].lstrip()
    out.append(text)
    return out


def describe_card(text: str, pace_wps: float) -> Dict[str, Any]:
    """Words, estimated seconds and warnings for a card at a given pace (also used when the person's pace changes later)."""
    pace = min(max(pace_wps, C["PACE_MIN_WPS"]), C["PACE_MAX_WPS"])
    words = _wc(text.split())
    est = rnd(words / pace, 1)
    warnings = []
    if _DIGIT.search(text):
        warnings.append("digits")
    if _SYMBOL.search(text):
        warnings.append("symbols")
    if est > C["MAX_EST_S"]:
        warnings.append("long")
    return {"words": words, "est_s": est, "warnings": warnings}


def split_cards(text: str, pace_wps: float = C["DEFAULT_PACE_WPS"], lines: str = "join") -> List[Dict[str, Any]]:
    pace = min(max(pace_wps, C["PACE_MIN_WPS"]), C["PACE_MAX_WPS"])
    budget = max(6, math.floor(pace * C["TARGET_S"]))
    max_words = max(budget, math.floor(pace * C["MAX_EST_S"]))
    cards: List[List[str]] = []
    for para in _paragraphs(text, lines):
        tokens = para.split()
        if _wc(tokens) == 0:
            continue
        units: List[List[str]] = []
        for s in _sentences(tokens):
            units.extend(_split_long(s, max_words))
        pcards: List[List[str]] = []
        cur: List[str] = []
        cur_w = 0
        for u in units:
            w = _wc(u)
            if cur and cur_w + w > budget:
                pcards.append(cur)
                cur, cur_w = [], 0
            cur = cur + u
            cur_w += w
        if cur:
            pcards.append(cur)
        cards.extend(_merge_runts(pcards, max_words))
    out: List[Dict[str, Any]] = []
    for toks in cards:
        for piece in _cap_chars(" ".join(toks)):
            out.append({"text": piece, **describe_card(piece, pace)})
    return out


# ---------------------------------------------------------------- hands-free detector (spec section 7)
class HandsFreeDetector:
    """Feed one level per hop, in order. Returns an event dict or None. Times are in seconds from hop 0 of the stream."""

    def __init__(self, thr: float, end_silence_hops: int = C["END_SILENCE_HOPS"], listen_from_hop: int = 0):
        self.thr = thr
        self.end_silence = end_silence_hops
        self.h = 0
        self.state = "listening"
        self.listen_hop = listen_from_hop
        self.run = 0
        self.clip_start = 0
        self.speech_start = 0
        self.last_voiced = 0

    def feed(self, level: float) -> Optional[Dict[str, Any]]:
        h = self.h
        self.h += 1
        above = level > self.thr
        if self.state == "idle":
            return None
        if self.state == "listening":
            self.run = self.run + 1 if above else 0
            if self.run >= C["START_RUN_HOPS"]:
                self.speech_start = h - C["START_RUN_HOPS"] + 1
                self.clip_start = max(self.listen_hop, self.speech_start - C["PRE_ROLL_HOPS"])
                self.last_voiced = h
                self.state = "speech"
                return None
            if h + 1 - self.listen_hop >= C["NO_SPEECH_TIMEOUT_HOPS"]:
                self.state = "idle"
                return {"event": "idle_timeout", "at_s": sec(h + 1)}
            return None
        # speech
        if above:
            self.last_voiced = h
        if h - self.last_voiced >= self.end_silence:
            return self._close("silence", self.last_voiced + 1 + C["TAIL_HOPS"], h)
        if h + 1 - self.clip_start >= C["HARD_CLIP_HOPS"]:
            return self._close("max", h + 1, h)
        return None

    def _close(self, reason: str, end_hop: int, h: int) -> Dict[str, Any]:
        ev = {"event": "clip", "start_s": sec(self.clip_start), "end_s": sec(end_hop),
              "speech_start_s": sec(self.speech_start), "speech_end_s": sec(self.last_voiced + 1), "reason": reason}
        self.state = "listening"            # at once: the hops since end_hop were all quiet, so nothing can be lost
        self.listen_hop = end_hop
        self.run = 0
        return ev


def run_detector(levels: Sequence[float], thr: float, end_silence_hops: int = C["END_SILENCE_HOPS"]) -> List[Dict[str, Any]]:
    det = HandsFreeDetector(thr, end_silence_hops)
    return [ev for ev in (det.feed(lv) for lv in levels) if ev is not None]


# ---------------------------------------------------------------- cut proposals for free speech (spec section 8)
def propose_segments(levels: Sequence[float], thr: float) -> List[Dict[str, Any]]:
    duration_h = len(levels)
    R = regions_hops(levels, thr)
    raw: List[Dict[str, Any]] = []
    i = 0
    start_exact = False
    while i < len(R):
        seg_a = R[i][0]
        start_i = i
        prev_b = R[i - 1][1] if (i > 0 and not start_exact) else None
        j = i
        while True:
            a, b = R[j]
            if b - seg_a > FORCE_AT:
                k = None
                for kk in range(j - 1, start_i - 1, -1):
                    if R[kk][1] - seg_a >= MIN_SEG:
                        k = kk
                        break
                if k is not None:
                    raw.append({"a": seg_a, "b": R[k][1], "kind": "pause", "start_exact": start_exact, "end_exact": False,
                                "prev_b": prev_b, "next_a": R[k + 1][0]})
                    i, start_exact = k + 1, False
                    break
                w0 = max(a, seg_a + FORCE_AT - FORCE_WINDOW)
                w1 = seg_a + FORCE_AT
                if w0 > w1:                                   # the window falls in the quiet before this region
                    raw.append({"a": seg_a, "b": R[j - 1][1], "kind": "pause", "start_exact": start_exact, "end_exact": False,
                                "prev_b": prev_b, "next_a": R[j][0]})
                    i, start_exact = j, False
                    break
                lo, hi = w0, w1 - 1                           # hops fully inside [w0, w1)
                if hi < lo:
                    cut = w1
                else:
                    cut = min(range(lo, hi + 1), key=lambda h: (levels[h], h))     # the START of the quietest hop
                raw.append({"a": seg_a, "b": cut, "kind": "forced", "start_exact": start_exact, "end_exact": True,
                            "prev_b": prev_b, "next_a": None})
                R[j][0] = cut
                i, start_exact = j, True
                break
            if j + 1 < len(R) and b - seg_a >= CUT_AFTER:
                raw.append({"a": seg_a, "b": b, "kind": "pause", "start_exact": start_exact, "end_exact": False,
                            "prev_b": prev_b, "next_a": R[j + 1][0]})
                i, start_exact = j + 1, False
                break
            if j + 1 >= len(R):
                raw.append({"a": seg_a, "b": b, "kind": "end", "start_exact": start_exact, "end_exact": False,
                            "prev_b": prev_b, "next_a": None})
                i = len(R)
                break
            j += 1
    out = []
    for s in raw:
        start = float(s["a"]) if s["start_exact"] else float(s["a"] - PAD_LEAD)
        if not s["start_exact"] and s["prev_b"] is not None:
            start = max(start, (s["prev_b"] + s["a"]) / 2.0)
        end = float(s["b"]) if s["end_exact"] else float(s["b"] + PAD_TAIL)
        if not s["end_exact"] and s["next_a"] is not None:
            end = min(end, (s["b"] + s["next_a"]) / 2.0)
        start, end = max(0.0, start), min(float(duration_h), end)
        out.append({"start_s": sec(start), "end_s": sec(end), "end_kind": s["kind"]})
    return out


# ---------------------------------------------------------------- test material
def levels_from_runs(runs: Sequence[Sequence[float]]) -> List[float]:
    out: List[float] = []
    for seconds, db in runs:
        out.extend([float(db)] * hops(seconds))
    return out


def square_samples(parts: Sequence[Dict[str, Any]], rate: int) -> np.ndarray:
    """Exact integer samples: +amp / -amp alternating every half_period samples (silence when amp is 0)."""
    chunks = []
    for p in parts:
        n = int(round(p["seconds"] * rate))
        amp, half = int(p["amp"]), int(p.get("half_period", 24))
        k = np.arange(n)
        sign = np.where((k // half) % 2 == 0, 1, -1)
        chunks.append((sign * amp).astype(np.int64))
    return np.concatenate(chunks).clip(-32768, 32767).astype(np.int16)


QUIET, LOUD = -70.0, -20.0

CARD_CASES: List[Dict[str, Any]] = [
    {"name": "short_sentences_pack_together", "pace_wps": 2.6, "lines": "join",
     "text": "The tide came in. We walked along the shore. Gulls circled overhead. Nobody said a word. Then the rain began to fall, "
             "and we ran for the car."},
    {"name": "abbreviation_is_not_a_sentence_end", "pace_wps": 2.6, "lines": "join",
     "text": "I asked Dr. Smith about it. He said it was fine."},
    {"name": "long_sentence_splits_at_strong_break_then_comma", "pace_wps": 2.6, "lines": "join",
     "text": "When the old lighthouse keeper finally retired after forty years of faithful service to the harbour, the whole town "
             "gathered on the quay to thank him; he stood quietly at the back, smiling, and said very little, because he had never "
             "enjoyed being the centre of attention."},
    {"name": "paragraphs_end_cards", "pace_wps": 2.6, "lines": "join",
     "text": "First paragraph is short.\n\nSecond paragraph is also short and sweet."},
    {"name": "single_line_breaks_are_spaces_when_joining", "pace_wps": 2.6, "lines": "join",
     "text": "A sentence that was\nwrapped by a narrow\nscreen before it was pasted here."},
    {"name": "keep_mode_makes_each_line_a_card", "pace_wps": 2.6, "lines": "keep",
     "text": "Roses are red,\nViolets are blue,\nSugar is sweet,\nAnd so are you."},
    {"name": "runt_is_joined_to_the_previous_card", "pace_wps": 2.6, "lines": "join",
     "text": "We reached the summit just before noon and stopped to eat our sandwiches in the thin cold air while the wind "
             "howled around us. Wow."},
    {"name": "runt_stays_alone_when_joining_would_pass_the_limit", "pace_wps": 2.6, "lines": "join",
     "text": "We reached the summit just before noon and stopped to eat our sandwiches in the thin cold air while the wind "
             "howled around us all through the afternoon. Wow."},
    {"name": "runt_at_the_start_is_joined_to_the_next_card", "pace_wps": 2.6, "lines": "join",
     "text": "Wow. We reached the summit just before noon and stopped to eat our sandwiches in the thin cold air while the wind "
             "howled around us."},
    {"name": "digits_and_symbols_are_warned_about", "pace_wps": 2.6, "lines": "join",
     "text": "It cost $20 for 3 tickets & a map."},
    {"name": "slow_pace_makes_smaller_cards", "pace_wps": 1.5, "lines": "join",
     "text": "She picked up the heavy book, opened it carefully near the middle, and began to read aloud to the sleepy children "
             "gathered around her feet."},
    {"name": "very_long_words_are_cut_at_the_character_limit", "pace_wps": 2.6, "lines": "join",
     "text": " ".join(["supercalifragilisticexpialidocious"] * 22) + "."},
    {"name": "control_characters_and_tabs", "pace_wps": 2.6, "lines": "join",
     "text": "Tabs\tbecome spaces.\x07 Bells are dropped.\r\nAnd CRLF is a line break."},
    {"name": "punctuation_only_paragraph_is_skipped", "pace_wps": 2.6, "lines": "join",
     "text": "Real words here for you today.\n\n* * *\n\nMore real words follow after the break."},
]


def _char_limit_case(extra: int) -> Dict[str, Any]:
    # one sentence of 25 words (so it is not split for length): 24 words of 23 letters and a last one of 24 characters, plus spaces
    word = "abcdefghijklmnopqrstuvw"
    text = " ".join([word] * 24 + [word + "x" * extra + "."])
    assert len(text) == C["MAX_CARD_CHARS"] + extra
    name = "a_card_of_exactly_the_character_limit_is_not_cut" if extra == 0 else "a_card_one_character_over_the_limit_is_cut"
    return {"name": name, "text": text, "pace_wps": 2.6, "lines": "join"}


def _break_case(name: str, ch: str, after_word: int, comma_after: Optional[int] = None) -> Dict[str, Any]:
    words = [f"w{i}" for i in range(1, 31)]
    words[after_word - 1] += ch
    if comma_after is not None:
        words[comma_after - 1] += ","
    words[-1] += "."
    return {"name": name, "text": " ".join(words), "pace_wps": 2.6, "lines": "join"}


CARD_CASES += [_char_limit_case(0), _char_limit_case(1)]
# a long sentence (30 words) is cut at the strongest break; each strong character must be tested on its own, far from the middle,
# with a comma at the middle that would win if the character were not recognised
CARD_CASES += [_break_case(f"strong_break_{n}_beats_a_comma_at_the_middle", ch, 8, 15)
               for n, ch in (("semicolon", ";"), ("colon", ":"), ("em_dash", "—"), ("en_dash", "–"))]
# a cut must leave at least MIN_SPLIT_WORDS (4) words on each side
CARD_CASES += [_break_case("a_cut_leaving_exactly_the_minimum_on_the_left_is_allowed", ";", 4),
               _break_case("a_cut_leaving_one_word_less_on_the_left_is_not", ";", 3),
               _break_case("a_cut_leaving_exactly_the_minimum_on_the_right_is_allowed", ";", 26),
               _break_case("a_cut_leaving_one_word_less_on_the_right_is_not", ";", 27)]


def _abbreviation_case(ab: str) -> Dict[str, Any]:
    token = ab if ab in ("etc.", "e.g.", "i.e.") else ab.title()
    words = " ".join(f"word{i}" for i in range(1, 21))
    return {"name": f"abbreviation_{ab.replace('.', '')}_is_not_a_sentence_end", "pace_wps": 2.6, "lines": "join",
            "text": f"{words} {token} Then we went home after the long day."}


# every abbreviation the splitter knows must be tested on its own: dropping one from a list is otherwise silent
CARD_CASES += [_abbreviation_case(a) for a in sorted(_ABBREV)]

DESCRIBE_CASES: List[Dict[str, Any]] = [
    {"name": "the_same_card_is_long_for_a_slower_reader", "pace_wps": 1.5,
     "text": "She picked up the heavy book opened it carefully near the middle and began to read aloud to the sleepy children "
             "gathered around her feet"},
    {"name": "and_fine_for_a_faster_one", "pace_wps": 2.6,
     "text": "She picked up the heavy book opened it carefully near the middle and began to read aloud to the sleepy children "
             "gathered around her feet"},
    {"name": "pace_is_limited_to_the_allowed_range", "pace_wps": 9.0, "text": "Four words only here."},
    {"name": "digits_and_symbols", "pace_wps": 2.6, "text": "Call 555 now & save 10%."},
]

# every symbol that triggers the "symbols" warning is tested on its own
DESCRIBE_CASES += [{"name": f"symbol_u{ord(ch):04x}_is_a_symbol_warning", "text": f"press {ch} now", "pace_wps": 2.6} for ch in "&@#%*_=+<>{}\\/|"]

HANDSFREE_CASES: List[Dict[str, Any]] = [
    {"name": "two_cards_with_silence_between", "threshold_dbfs": -45.0, "end_silence_hops": 120,
     "runs": [[1.0, QUIET], [3.0, LOUD], [2.0, QUIET], [4.0, LOUD], [2.0, QUIET]]},
    {"name": "a_click_shorter_than_the_start_run_is_ignored", "threshold_dbfs": -45.0, "end_silence_hops": 120,
     "runs": [[1.0, QUIET], [0.05, LOUD], [1.0, QUIET], [2.0, LOUD], [2.0, QUIET]]},
    {"name": "a_short_pause_inside_a_card_does_not_end_it", "threshold_dbfs": -45.0, "end_silence_hops": 120,
     "runs": [[0.5, QUIET], [2.0, LOUD], [0.8, QUIET], [2.0, LOUD], [2.0, QUIET]]},
    {"name": "a_long_pause_ends_the_clip_and_the_rest_is_the_next_card", "threshold_dbfs": -45.0, "end_silence_hops": 120,
     "runs": [[0.5, QUIET], [2.0, LOUD], [1.5, QUIET], [2.0, LOUD], [2.0, QUIET]]},
    {"name": "a_longer_end_wait_keeps_a_slow_reader_together", "threshold_dbfs": -45.0, "end_silence_hops": 200,
     "runs": [[0.5, QUIET], [2.0, LOUD], [1.5, QUIET], [2.0, LOUD], [3.0, QUIET]]},
    {"name": "speech_right_after_a_clip_closes_is_not_lost", "threshold_dbfs": -45.0, "end_silence_hops": 120,
     "runs": [[0.5, QUIET], [1.0, LOUD], [1.25, QUIET], [1.5, LOUD], [2.0, QUIET]]},
    {"name": "no_speech_for_twenty_seconds_pauses_the_session", "threshold_dbfs": -45.0, "end_silence_hops": 120,
     "runs": [[25.0, QUIET]]},
    {"name": "speech_that_never_stops_is_closed_at_the_hard_limit", "threshold_dbfs": -45.0, "end_silence_hops": 120,
     "runs": [[0.5, QUIET], [35.0, LOUD]]},
]

HANDSFREE_CASES += [
    {"name": "a_pause_exactly_as_long_as_the_end_wait_closes_the_clip", "threshold_dbfs": -45.0, "end_silence_hops": 120,
     "runs": [[0.5, QUIET], [2.0, LOUD], [1.2, QUIET], [1.0, LOUD], [2.0, QUIET]]},
    {"name": "a_pause_one_hop_shorter_than_the_end_wait_does_not", "threshold_dbfs": -45.0, "end_silence_hops": 120,
     "runs": [[0.5, QUIET], [2.0, LOUD], [1.19, QUIET], [1.0, LOUD], [2.0, QUIET]]},
    {"name": "a_run_exactly_the_start_length_starts_a_clip", "threshold_dbfs": -45.0, "end_silence_hops": 120,
     "runs": [[0.5, QUIET], [0.1, LOUD], [2.0, QUIET]]},
    {"name": "a_run_one_hop_short_of_the_start_length_is_ignored", "threshold_dbfs": -45.0, "end_silence_hops": 120,
     "runs": [[0.5, QUIET], [0.09, LOUD], [2.0, QUIET]]},
    {"name": "a_level_exactly_at_the_threshold_is_not_speech", "threshold_dbfs": -45.0, "end_silence_hops": 120,
     "runs": [[0.5, QUIET], [3.0, -45.0], [2.0, QUIET]]},
]

SEGMENT_CASES: List[Dict[str, Any]] = [
    {"name": "two_regions_reach_the_cut_length_at_a_pause", "threshold_dbfs": -45.0,
     "runs": [[0.5, QUIET], [3.0, LOUD], [0.5, QUIET], [6.0, LOUD], [0.6, QUIET], [2.0, LOUD], [0.5, QUIET]]},
    {"name": "continuous_speech_is_cut_inside_the_quietest_hop", "threshold_dbfs": -45.0,
     "runs": [[0.3, QUIET], [9.5, LOUD], [0.2, -44.0], [0.1, -60.0], [0.2, -44.0], [5.0, LOUD], [0.3, QUIET]]},
    {"name": "an_early_pause_beats_a_forced_cut", "threshold_dbfs": -45.0,
     "runs": [[0.3, QUIET], [2.0, LOUD], [0.4, QUIET], [12.0, LOUD], [0.3, QUIET]]},
    {"name": "long_silences_are_not_included_in_segments", "threshold_dbfs": -45.0,
     "runs": [[3.0, QUIET], [8.5, LOUD], [5.0, QUIET], [4.0, LOUD], [4.0, QUIET]]},
    {"name": "a_gap_barely_over_the_pause_length_splits_the_padding", "threshold_dbfs": -45.0,
     "runs": [[0.5, QUIET], [8.2, LOUD], [0.3, QUIET], [3.0, LOUD], [0.5, QUIET]]},
    {"name": "no_speech_proposes_nothing", "threshold_dbfs": -45.0, "runs": [[5.0, QUIET]]},
    {"name": "a_blip_shorter_than_the_minimum_region_is_ignored", "threshold_dbfs": -45.0,
     "runs": [[1.0, QUIET], [0.05, LOUD], [1.0, QUIET], [3.0, LOUD], [1.0, QUIET]]},
    {"name": "region_starting_after_the_force_window_cuts_at_the_previous_pause", "threshold_dbfs": -45.0,
     "runs": [[0.2, QUIET], [0.6, LOUD], [11.0, QUIET], [4.0, LOUD], [0.2, QUIET]]},
]

SEGMENT_CASES += [
    {"name": "a_region_exactly_the_cut_length_is_cut_at_the_next_pause", "threshold_dbfs": -45.0,
     "runs": [[0.5, QUIET], [8.0, LOUD], [0.5, QUIET], [1.0, LOUD], [0.5, QUIET]]},
    {"name": "a_region_one_hop_short_of_the_cut_length_keeps_going", "threshold_dbfs": -45.0,
     "runs": [[0.5, QUIET], [7.99, LOUD], [0.5, QUIET], [1.0, LOUD], [0.5, QUIET]]},
    {"name": "a_region_exactly_the_force_length_is_not_forced", "threshold_dbfs": -45.0,
     "runs": [[0.5, QUIET], [11.0, LOUD], [0.5, QUIET]]},
    {"name": "a_region_one_hop_over_the_force_length_is_forced", "threshold_dbfs": -45.0,
     "runs": [[0.5, QUIET], [11.01, LOUD], [0.5, QUIET]]},
    {"name": "an_early_pause_exactly_the_minimum_piece_is_used", "threshold_dbfs": -45.0,
     "runs": [[0.5, QUIET], [1.0, LOUD], [0.5, QUIET], [12.0, LOUD], [0.5, QUIET]]},
    {"name": "an_early_pause_one_hop_under_the_minimum_piece_is_not", "threshold_dbfs": -45.0,
     "runs": [[0.5, QUIET], [0.99, LOUD], [0.5, QUIET], [12.0, LOUD], [0.5, QUIET]]},
    {"name": "a_level_exactly_at_the_threshold_is_not_speech", "threshold_dbfs": -45.0,
     "runs": [[1.0, -45.0], [3.0, LOUD], [1.0, -45.0]]},
    {"name": "a_gap_exactly_the_pause_length_separates_two_regions", "threshold_dbfs": -45.0,
     "runs": [[0.5, QUIET], [8.0, LOUD], [0.3, QUIET], [2.0, LOUD], [0.5, QUIET]]},
    {"name": "a_gap_one_hop_shorter_than_a_pause_is_closed_up", "threshold_dbfs": -45.0,
     "runs": [[0.5, QUIET], [8.0, LOUD], [0.29, QUIET], [2.0, LOUD], [0.5, QUIET]]},
    {"name": "a_burst_exactly_the_minimum_region_length_is_kept", "threshold_dbfs": -45.0,
     "runs": [[1.0, QUIET], [0.1, LOUD], [1.0, QUIET]]},
]

METRICS_CASES: List[Dict[str, Any]] = [
    {"name": "tone_between_silences", "rate": 48000, "noise_floor_dbfs": -62.0,
     "parts": [{"seconds": 0.5, "amp": 0}, {"seconds": 1.0, "amp": 8000}, {"seconds": 0.5, "amp": 0}]},
    {"name": "clipping_is_counted", "rate": 48000, "noise_floor_dbfs": None,
     "parts": [{"seconds": 0.3, "amp": 0}, {"seconds": 0.5, "amp": 32767}, {"seconds": 0.2, "amp": 200}]},
    {"name": "44100_hz_uses_441_sample_hops", "rate": 44100, "noise_floor_dbfs": -50.0,
     "parts": [{"seconds": 0.4, "amp": 0}, {"seconds": 0.8, "amp": 3000}, {"seconds": 0.3, "amp": 0}]},
    {"name": "all_silence_has_no_speech_and_the_floor_level", "rate": 48000, "noise_floor_dbfs": None,
     "parts": [{"seconds": 1.0, "amp": 0}]},
    {"name": "a_short_burst_is_not_speech", "rate": 48000, "noise_floor_dbfs": -60.0,
     "parts": [{"seconds": 0.5, "amp": 0}, {"seconds": 0.05, "amp": 9000}, {"seconds": 0.5, "amp": 0}]},
]


def _manifest_example() -> Dict[str, Any]:
    sid1, sid2 = "s20261002-180411-a3f9", "s20261002-190000-0b1c"
    placeholder = "0" * 64
    clips = []
    for n, (text, dur) in enumerate([("The tide came in.", 3.2), ("We walked along the shore.", 3.9)], start=1):
        clips.append({"index": n, "card": n, "attempt": 1, "file": f"sessions/{sid1}/clips/{n:04d}.wav", "text": text,
                      "recorded": f"2026-10-02T18:0{n}:00Z", "duration_s": dur,
                      "speech": {"start_s": 0.41, "end_s": round(dur - 0.5, 3)},
                      "metrics": {"peak_dbfs": -4.2, "rms_dbfs": -23.1, "clipped_samples": 0},
                      "flags": ["stumble"] if n == 2 else []})
    files = [{"path": c["file"], "bytes": 1000000 * i, "sha256": placeholder} for i, c in enumerate(clips, start=1)]
    free = f"sessions/{sid2}/session.wav"
    files.append({"path": free, "bytes": 5760000, "sha256": placeholder})
    return {
        "schema": "ack-training-capture/1", "created": "2026-10-02T19:30:00Z", "app": {"name": "ACK", "version": "1.0-beta.9"},
        "sessions": [
            {"id": sid1, "mode": "script", "label": "closet, phone on stand, 30 cm", "started": "2026-10-02T18:04:11Z",
             "ended": "2026-10-02T18:20:00Z", "language": "en-US",
             "audio": {"sample_rate": 48000, "source": "UNPROCESSED", "source_requested": "UNPROCESSED"},
             "noise_floor_dbfs": -62.3, "threshold_dbfs": -52.3, "device": {"model": "Pixel 8", "sdk": 35},
             "script": {"id": "sample-script", "title": "Sample script", "cards_total": 120}, "clips": clips},
            {"id": sid2, "mode": "free", "label": "kitchen", "started": "2026-10-02T19:00:00Z", "ended": "2026-10-02T19:01:00Z",
             "language": "en-US", "audio": {"sample_rate": 48000, "source": "VOICE_RECOGNITION", "source_requested": "UNPROCESSED"},
             "noise_floor_dbfs": None, "threshold_dbfs": -45.0, "topic": "my morning routine",
             "recording": {"file": free, "duration_s": 60.0,
                           "metrics": {"peak_dbfs": -6.0, "rms_dbfs": -24.5, "clipped_samples": 0},
                           "proposed_segments": [{"start_s": 0.26, "end_s": 9.91, "end_kind": "pause",
                                                  "metrics": {"peak_dbfs": -6.0, "rms_dbfs": -24.0, "clipped_samples": 0}}]}},
        ],
        "files": files,
    }


# ---------------------------------------------------------------- generated cases (a differential check for other implementations)
# A fixed seed makes these reproducible: --write always produces the same file, and another implementation must give the same answers.
FUZZ_SEED = 20261002

_FUZZ_WORDS = ["the", "tide", "came", "in", "and", "we", "walked", "along", "shore", "Gulls", "circled", "overhead", "Nobody", "said",
               "a", "word", "naïve", "café", "日本語", "Привет", "über", "42", "3.5", "1,000", "R&D", "100%", "e-mail", "don't", "O'Brien",
               "x" * 55, "—", "&", "...", "(", "ok", "I", "to", "of", "reading", "slowly", "carefully", "because", "however"]
_FUZZ_ENDS = ["", "", "", "", ",", ",", ".", ".", "!", "?", ";", ":", "…", "—", ".\"", ".)", "?”", ",\""]
_FUZZ_ABBREV = ["Dr.", "Mr.", "Mrs.", "etc.", "e.g.", "St.", "vs.", "No."]
_FUZZ_OPEN = ["", "", "", "", "\"", "“", "(", "['"]
_FUZZ_SEPS = [" ", " ", " ", " ", " ", "\t", " ", "　", "  ", " \n", "\n"]


def _pick(r: random.Random, seq: Sequence[Any]) -> Any:
    return seq[int(r.random() * len(seq))]


def _fuzz_text(r: random.Random) -> str:
    paragraphs = []
    for _ in range(1 + int(r.random() * 4)):
        tokens = []
        for _ in range(3 + int(r.random() * 45)):
            if r.random() < 0.08:
                tokens.append(_pick(r, _FUZZ_ABBREV))
            else:
                tokens.append(_pick(r, _FUZZ_OPEN) + _pick(r, _FUZZ_WORDS) + _pick(r, _FUZZ_ENDS))
        text = ""
        for i, t in enumerate(tokens):
            text += t if i == 0 else _pick(r, _FUZZ_SEPS) + t
        if r.random() < 0.05:
            text += "\x07"                                   # a control character, which must be dropped
        paragraphs.append(text)
    return _pick(r, ["\n\n", "\n \n", "\r\n\r\n", "\n\n\n", "\n"]).join(paragraphs)


def _fuzz_runs(r: random.Random, shape: str) -> List[List[float]]:
    runs: List[List[float]] = []
    if shape == "cards":                                # bursts of speech between silences, now and then a very long silence or burst
        for _ in range(2 + int(r.random() * 8)):
            quiet = _pick(r, [0.05, 0.2, 0.6, 1.0, 1.5, 2.5, 2.5, 25.0 if r.random() < 0.12 else 0.4])
            burst = _pick(r, [0.03, 0.3, 1.0, 2.0, 3.0, 6.0, 9.0, 32.0 if r.random() < 0.1 else 4.0])
            runs.append([quiet, QUIET])
            runs.append([burst, LOUD])
            if r.random() < 0.3:                          # a dip inside speech, around the end-of-card wait
                runs.append([_pick(r, [0.1, 0.5, 0.9, 1.1, 1.3]), QUIET])
                runs.append([_pick(r, [0.5, 1.0, 2.0]), LOUD])
        runs.append([_pick(r, [0.3, 1.5, 3.0]), QUIET])
        return runs
    levels = [QUIET, QUIET, LOUD, LOUD, LOUD, -44.0, -46.0, -30.0, -60.0]       # a recording of someone talking
    for _ in range(3 + int(r.random() * 40)):
        runs.append([round(0.02 + (r.random() ** 2) * 9.0, 2), _pick(r, levels)])
    return runs


def build_fuzz() -> Dict[str, Any]:
    r = random.Random(FUZZ_SEED)
    cards = []
    for _ in range(70):
        text, pace, lines = _fuzz_text(r), _pick(r, [1.5, 2.0, 2.6, 2.6, 3.2, 4.0]), _pick(r, ["join", "join", "keep"])
        cards.append({"input": {"text": text, "pace_wps": pace, "lines": lines}, "expected": split_cards(text, pace, lines)})
    handsfree = []
    for _ in range(60):
        runs, thr, wait = _fuzz_runs(r, "cards"), _pick(r, [-45.0, -40.0, -50.0]), _pick(r, [120, 120, 80, 200])
        handsfree.append({"input": {"runs": runs, "threshold_dbfs": thr, "end_silence_hops": wait},
                          "expected": run_detector(levels_from_runs(runs), thr, wait)})
    segments = []
    for _ in range(60):
        runs, thr = _fuzz_runs(r, "talk"), _pick(r, [-45.0, -45.0, -40.0, -50.0])
        segments.append({"input": {"runs": runs, "threshold_dbfs": thr}, "expected": propose_segments(levels_from_runs(runs), thr)})
    return {"seed": FUZZ_SEED, "cards": cards, "handsfree": handsfree, "segments": segments}


# ---------------------------------------------------------------- vector files
def build_vectors() -> Dict[str, Any]:
    cards = {"split": [{"name": c["name"], "input": {"text": c["text"], "pace_wps": c["pace_wps"], "lines": c["lines"]},
                        "expected": split_cards(c["text"], c["pace_wps"], c["lines"])} for c in CARD_CASES],
             "describe": [{"name": c["name"], "input": {"text": c["text"], "pace_wps": c["pace_wps"]},
                           "expected": describe_card(c["text"], c["pace_wps"])} for c in DESCRIBE_CASES]}
    handsfree = [{"name": c["name"], "input": {"runs": c["runs"], "threshold_dbfs": c["threshold_dbfs"],
                                               "end_silence_hops": c["end_silence_hops"]},
                  "expected": run_detector(levels_from_runs(c["runs"]), c["threshold_dbfs"], c["end_silence_hops"])}
                 for c in HANDSFREE_CASES]
    segments = [{"name": c["name"], "input": {"runs": c["runs"], "threshold_dbfs": c["threshold_dbfs"]},
                 "expected": propose_segments(levels_from_runs(c["runs"]), c["threshold_dbfs"])} for c in SEGMENT_CASES]
    metrics = []
    for c in METRICS_CASES:
        samples = square_samples(c["parts"], c["rate"])
        thr = threshold_db(c["noise_floor_dbfs"])
        metrics.append({"name": c["name"], "input": {"rate": c["rate"], "parts": c["parts"], "noise_floor_dbfs": c["noise_floor_dbfs"]},
                        "expected": {"threshold_dbfs": rnd(thr, 1), **clip_metrics(samples, c["rate"], thr)}})
    return {"cards.json": cards, "handsfree.json": handsfree, "segments.json": segments, "metrics.json": metrics,
            "manifest_example.json": _manifest_example(), "fuzz.json": build_fuzz()}


def dump(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=1) + "\n"


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    vectors = build_vectors()
    if "--write" in args:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        for name, obj in vectors.items():
            (DATA_DIR / name).write_text(dump(obj), encoding="utf-8")
        print(f"wrote {len(vectors)} files to {DATA_DIR}")
        return 0
    stale = [n for n, obj in vectors.items() if not (DATA_DIR / n).exists() or (DATA_DIR / n).read_text(encoding="utf-8") != dump(obj)]
    print("up to date" if not stale else "out of date (run with --write): " + ", ".join(stale))
    return 1 if stale else 0


if __name__ == "__main__":
    sys.exit(main())
