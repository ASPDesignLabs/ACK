# SPDX-License-Identifier: GPL-3.0-or-later
"""What Freeform Studio makes of the audio in a recording that came from ACK, to help the person reviewing it.

ACK already measured each clip on the phone (loudness, clipping, where speech starts and stops, the words on the card). The PC
listens again, with its own method and from the decoded audio, and the two are compared. This needs no speech model: it works
from the level of the audio alone, so it can run the moment a recording is decoded. A check that finds something adds a
short flag to the piece (the review page shows it in plain words); it never drops or edits anything by itself. Pieces carrying
a flag are held back from an unreviewed dataset build until a person has looked, exactly like the recognizer's own warnings.

Flags added here (all short, lower-case):
  no_speech          hardly any of the piece is louder than the room
  clipped            the audio hit the maximum level several times: distorted
  quiet              too soft to be brought up to full level
  noisy              speech is not much louder than the background noise
  cut_off            speech was still going at the very start or end of the clip ACK recorded (the first or last word may be missing)
  reads_differently  what was heard does not match the words on the card
  phone_stumble      the person marked this clip on the phone as a slip
  phone_disagrees    the phone and this computer disagree about whether there is speech in the clip
Tags set from the person's marks on the phone (these keep a piece out of training until a reviewer clears them):
  noise, unclear, laugh, cough
"""
from __future__ import annotations

import difflib
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from .audio import iter_blocks, voiced_regions, wav_info
from .edit import FLAG_RE, MAX_FLAGS, TAG_RE
from .refine import speech_threshold

# Measurements agree with docs/ACK_TRAINING_CAPTURE_FORMAT.md section 5 and with build_dataset.py's own clip tests (a test keeps them equal).
REGION_MIN_SILENCE_S = 0.3
REGION_MIN_LEN_S = 0.1
CLIP_SAMPLES = 5            # this many samples at the top level is distortion (build_dataset.CLIP_SAMPLES)
CLIP_LEVEL = 32736          # 0.999 of full scale, in 16-bit steps (build_dataset treats this and above as "at the top")
QUIET_PEAK_DB = -15.0       # the dataset builder can add at most 12 dB to reach -3 dB; softer than this cannot be brought up
MIN_SNR_DB = 20.0
NO_SPEECH_FRACTION = 0.1
EDGE_HOPS = 3               # speech counts as touching the edge of a clip when it is loud in the first or last 30 ms
FLOOR_IGNORE_DB = -95.0     # the silence between joined clips is digital zero: not a "room", so it is left out of the noise estimate
READS_DIFFERENTLY_BELOW = 0.7
THRESH_OFFSET_DB, THRESH_MIN_DB, THRESH_MAX_DB = 10.0, -55.0, -30.0     # speech threshold from the room's level (format document, 5.2)
MIN_DYNAMIC_RANGE_DB = 10.0 # a recording whose loud and quiet parts are closer than this tells us nothing about the room
PHONE_TAGS = ("noise", "unclear", "laugh", "cough")

_WORD = re.compile(r"[a-z0-9']+")


def _db(x: float) -> float:
    return 20.0 * float(np.log10(max(x, 1e-9) / 32768.0))


def reads_differently(card: str, heard: str) -> bool:
    """Whether the words heard are clearly not the words on the card. A number on the card may have been spoken as words, so
    number tokens on the card are left out of the comparison; nothing heard at all is reported by other flags, not this one."""
    a = _WORD.findall(card.lower().replace("’", "'"))
    b = _WORD.findall(heard.lower().replace("’", "'"))
    if not b:
        return False
    a = [t for t in a if not any(ch.isdigit() for ch in t)]
    if not a:
        return False
    return difflib.SequenceMatcher(None, a, b, autojunk=False).ratio() < READS_DIFFERENTLY_BELOW


def _number(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def room_level(db: np.ndarray, notes: Dict[str, Any]) -> float:
    """How loud the room is. ACK measures this on purpose at the start of a session (a few seconds of staying quiet), so that is
    used when it is there. Otherwise the quietest tenth of the recording (leaving out digital silence) is the best available guess,
    but only if the recording has real quiet moments; with none, the answer is a safe -60."""
    if _number(notes.get("noise_floor_dbfs")):
        return float(notes["noise_floor_dbfs"])
    live = db[db > FLOOR_IGNORE_DB]
    if len(live) < 50:
        return -60.0
    low, high = np.percentile(live, [10, 90])
    return float(low) if high - low >= MIN_DYNAMIC_RANGE_DB else -60.0


def speech_threshold_for(db: np.ndarray, notes: Dict[str, Any]) -> float:
    """What counts as speech. When ACK measured the room, the level that follows from that measurement is the yardstick (it does not
    move because some other clip in the recording happens to be loud); otherwise it adapts to the recording, as elsewhere."""
    if _number(notes.get("noise_floor_dbfs")):
        if _number(notes.get("threshold_dbfs")):
            return float(notes["threshold_dbfs"])
        return min(max(float(notes["noise_floor_dbfs"]) + THRESH_OFFSET_DB, THRESH_MIN_DB), THRESH_MAX_DB)
    return float(speech_threshold(db))


def measure_range(db: np.ndarray, hop: float, a: float, b: float, thr: float, floor: float) -> Optional[Dict[str, Any]]:
    i0, i1 = max(0, int(round(a / hop))), min(len(db), int(round(b / hop)))
    seg = db[i0:i1]
    if len(seg) == 0:
        return None
    voiced = seg > thr
    regions = voiced_regions(seg, hop, thr, REGION_MIN_SILENCE_S, REGION_MIN_LEN_S)
    speech_db = float(np.median(seg[voiced])) if voiced.any() else None
    return {"voiced_fraction": round(float(voiced.mean()), 3), "has_speech": bool(regions),
            "lead_s": round(regions[0][0], 3) if regions else None,
            "tail_s": round(len(seg) * hop - regions[-1][1], 3) if regions else None,
            "speech_db": round(speech_db, 1) if speech_db is not None else None,
            "snr_db": round(speech_db - floor, 1) if speech_db is not None else None}


def edge_speech(db: np.ndarray, hop: float, a: float, b: float, thr: float) -> Tuple[bool, bool]:
    """(speech at the very start, speech at the very end) of the stretch a..b."""
    i0, i1 = max(0, int(round(a / hop))), min(len(db), int(round(b / hop)))
    seg = db[i0:i1]
    if len(seg) < 2 * EDGE_HOPS:
        return False, False
    return bool(np.any(seg[:EDGE_HOPS] > thr)), bool(np.any(seg[-EDGE_HOPS:] > thr))


def sample_checks(wav_path: Path, ranges: Sequence[Tuple[float, float]]) -> Tuple[List[int], List[int]]:
    """(peak, count of samples at the top level) for each range, from one pass over the decoded audio in blocks."""
    _frames, rate = wav_info(wav_path)
    spans = [(int(a * rate), int(b * rate)) for a, b in ranges]
    peaks = [0] * len(spans)
    clipped = [0] * len(spans)
    pos = 0
    for block in iter_blocks(wav_path, rate * 30):
        end = pos + len(block)
        for i, (a, b) in enumerate(spans):
            if b <= pos or a >= end:
                continue
            seg = np.abs(block[max(a, pos) - pos:min(b, end) - pos].astype(np.int32))
            if len(seg):
                peaks[i] = max(peaks[i], int(seg.max()))
                clipped[i] += int(np.count_nonzero(seg >= CLIP_LEVEL))
        pos = end
    return peaks, clipped


def _merge_flags(segment: Dict[str, Any], add: Sequence[str]) -> None:
    flags = list(segment.get("flags") or [])
    for f in add:
        if f not in flags and FLAG_RE.match(f):
            flags.append(f)
    segment["flags"] = flags[:MAX_FLAGS]


def _piece_report(segment: Dict[str, Any], clip: Optional[int], m: Optional[Dict[str, Any]], peak: int, clipped: int) -> Dict[str, Any]:
    return {"start": segment["start"], "end": segment["end"], "clip": clip, "peak_dbfs": round(max(_db(peak), -120.0), 1),
            "clipped_samples": clipped, **({k: m[k] for k in ("voiced_fraction", "lead_s", "tail_s", "speech_db", "snr_db")} if m else {})}


def _common_flags(m: Optional[Dict[str, Any]], peak: int, clipped: int) -> List[str]:
    flags: List[str] = []
    if m is None or m["voiced_fraction"] < NO_SPEECH_FRACTION or not m["has_speech"]:
        flags.append("no_speech")
    if clipped >= CLIP_SAMPLES:
        flags.append("clipped")
    if m is not None and m["has_speech"]:
        if _db(peak) < QUIET_PEAK_DB:
            flags.append("quiet")
        if m["snr_db"] is not None and m["snr_db"] < MIN_SNR_DB:
            flags.append("noisy")
    return flags


def check_script(segments: List[Dict[str, Any]], clip_of: List[int], notes: Dict[str, Any], db: np.ndarray, hop: float,
                 wav_path: Path) -> Dict[str, Any]:
    """Annotate the pieces of a script session in place (flags and tags). Returns the measurements, to be saved beside the take."""
    clips = notes["clips"]
    thr = speech_threshold_for(db, notes)
    floor = room_level(db, notes)
    peaks, clipped = sample_checks(wav_path, [(s["start"], s["end"]) for s in segments])

    heard: Dict[int, List[str]] = {}
    first: Dict[int, int] = {}
    last: Dict[int, int] = {}
    for i, (s, k) in enumerate(zip(segments, clip_of)):
        heard.setdefault(k, []).append(s["text"])
        first.setdefault(k, i)
        last[k] = i

    clip_state: Dict[int, Dict[str, Any]] = {}
    for k, c in enumerate(clips):
        win = measure_range(db, hop, c["start_s"], c["end_s"], thr, floor)
        start_edge, end_edge = edge_speech(db, hop, c["start_s"], c["end_s"], thr)
        clip_state[k] = {"pc_speech": bool(win and win["has_speech"]), "phone_speech": bool(c.get("speech")),
                         "start_edge": start_edge, "end_edge": end_edge}

    report: Dict[str, Any] = {"schema": 1, "mode": "script", "threshold_dbfs": round(float(thr), 1), "noise_floor_dbfs": round(floor, 1),
                              "pieces": {}}
    for i, (s, k) in enumerate(zip(segments, clip_of)):
        m = measure_range(db, hop, s["start"], s["end"], thr, floor)
        add = _common_flags(m, peaks[i], clipped[i])
        st, clip = clip_state[k], clips[k]
        if (i == first[k] and st["start_edge"]) or (i == last[k] and st["end_edge"]):
            add.append("cut_off")
        if clip.get("text") and reads_differently(clip["text"], " ".join(t for t in heard[k] if t)):
            add.append("reads_differently")
        if st["phone_speech"] != st["pc_speech"]:
            add.append("phone_disagrees")
        user = [f for f in (clip.get("flags") or []) if isinstance(f, str)]
        if "stumble" in user:
            add.append("phone_stumble")
        s["tags"] = sorted(set(s.get("tags") or []) | {t for t in user if t in PHONE_TAGS and TAG_RE.match(t)})[:8]
        _merge_flags(s, add)
        report["pieces"][s["id"]] = _piece_report(s, clip.get("index"), m, peaks[i], clipped[i])
    return report


def check_free(segments: List[Dict[str, Any]], notes: Dict[str, Any], db: np.ndarray, hop: float, wav_path: Path) -> Dict[str, Any]:
    thr = speech_threshold_for(db, notes)
    floor = room_level(db, notes)
    peaks, clipped = sample_checks(wav_path, [(s["start"], s["end"]) for s in segments])
    report: Dict[str, Any] = {"schema": 1, "mode": "free", "threshold_dbfs": round(float(thr), 1), "noise_floor_dbfs": round(floor, 1),
                              "pieces": {}}
    for i, s in enumerate(segments):
        m = measure_range(db, hop, s["start"], s["end"], thr, floor)
        _merge_flags(s, _common_flags(m, peaks[i], clipped[i]))
        report["pieces"][s["id"]] = _piece_report(s, None, m, peaks[i], clipped[i])
    return report
