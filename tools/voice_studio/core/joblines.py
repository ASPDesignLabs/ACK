# SPDX-License-Identifier: GPL-3.0-or-later
"""Reading what a job printed (plan tasks VS-2.4 and VS-2.5).

Freeform Studio's processor and dataset builder print one JSON object per line when asked (`--json`), and the job supervisor keeps everything a job printed in
its log. This file turns those lines into plain data for the screens and says nothing itself: a line that is not JSON (a library's warning, a progress bar) is skipped,
a line that is JSON but not shaped as expected is skipped, and a log with no result yet reads as "still going", never as a failure.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple

MAX_LINE = 200_000                                 # a longer line is not one of ours
SHORT_MINUTES = 10                                 # Freeform Studio's own note: under about this much speech tends to give an uneven voice
COMFORTABLE_MINUTES = 30
RESULTS = ("built", "dry_run", "nothing_qualified", "problems", "refused_existing", "no_takes_folder")        # each has words in the text catalog
REASON_KINDS = ("dropped", "no_text", "bad_character", "too_short", "too_long", "tagged", "cuts_word", "not_approved", "flagged", "already_in",
                "audio_empty", "clipping", "too_quiet", "conversion_failed", "other")                         # each has words in the text catalog
KNOWN_FLAGS = ("low_confidence", "has_digits", "bracket_tag", "no_speech", "clipped", "quiet", "noisy", "cuts_word")        # each has words in the text catalog
ADVICE_CODES = ("short", "comfortable")


def json_objects(lines: Iterable[str]) -> List[Dict[str, Any]]:
    """Every line that is a JSON object, in order. Anything else is skipped."""
    found = []
    for line in lines:
        text = line.strip()
        if not text.startswith("{") or len(text) > MAX_LINE:
            continue
        try:
            obj = json.loads(text)
        except (ValueError, RecursionError):          # a line nested a hundred thousand deep is not one of ours either
            continue
        if isinstance(obj, dict):
            found.append(obj)
    return found


def _num(value: Any) -> Optional[float]:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _text(value: Any) -> str:
    return value if isinstance(value, str) else ""


# ---------------------------------------------------------------- finishing recordings

@dataclass(frozen=True)
class TakeProgress:
    take: str
    status: str
    progress: Optional[float]
    error: str
    label: str
    duration: Optional[float]


@dataclass(frozen=True)
class ProcessState:
    takes: Tuple[TakeProgress, ...]           # the last thing said about each recording, in the order they first appeared
    finished: bool                            # the processor printed its closing line
    ready: int
    failed: Tuple[TakeProgress, ...]
    nothing_waiting: bool
    model_missing: str                        # the speech model that is not on this computer, or ""

    @property
    def fraction(self) -> float:
        """How far along, 0 to 1, over every recording named so far. A finished one counts as whole."""
        if self.finished:
            return 1.0
        if not self.takes:
            return 0.0
        total = sum(1.0 if t.status == "ready" else min(max(t.progress or 0.0, 0.0), 0.99) for t in self.takes)
        return round(total / len(self.takes), 3)


def process_state(lines: Iterable[str]) -> ProcessState:
    order: List[str] = []
    latest: Dict[str, TakeProgress] = {}
    done: Optional[Dict[str, Any]] = None
    for obj in json_objects(lines):
        if obj.get("done") is True:
            done = obj
        elif isinstance(obj.get("take"), str) and isinstance(obj.get("status"), str):
            name = obj["take"]
            if name not in latest:
                order.append(name)
            latest[name] = TakeProgress(name, obj["status"], _num(obj.get("progress")), _text(obj.get("error")), _text(obj.get("label")), _num(obj.get("duration")))
    takes = tuple(latest[n] for n in order)
    ready = sum(1 for t in takes if t.status == "ready")
    failed = tuple(t for t in takes if t.status == "error")
    return ProcessState(takes, done is not None, ready, failed, bool(done and done.get("nothing_waiting")), _text(done.get("model_missing")) if done else "")


# ---------------------------------------------------------------- the dataset

def reason_kind(reason: str) -> Tuple[str, str]:
    """(one of REASON_KINDS, the detail to show with it) for Freeform Studio's reason for leaving a piece out."""
    r = reason.strip()
    if r == "you dropped it":
        return "dropped", ""
    if r == "no text":
        return "no_text", ""
    if r.startswith("text has a character"):
        return "bad_character", ""
    if r.startswith("too short"):
        return "too_short", r[len("too short"):].strip(" ()")
    if r.startswith("too long"):
        return "too_long", r[len("too long"):].strip(" ()")
    if r.startswith("tagged:"):
        return "tagged", r[len("tagged:"):].strip()
    if r.startswith("a cut point falls inside a word"):
        return "cuts_word", ""
    if r == "not approved yet":
        return "not_approved", ""
    if r == "flagged" or r.startswith("flagged:"):
        return "flagged", r[len("flagged:"):].strip() if r.startswith("flagged:") else ""      # the builder's summary groups every flagged piece under the bare word
    if r.startswith("already in "):
        return "already_in", r[len("already in "):].split(" (")[0]
    if r == "audio is empty":
        return "audio_empty", ""
    if r.startswith("the recording clips"):
        return "clipping", ""
    if r == "too quiet to use":
        return "too_quiet", ""
    if r == "audio conversion failed":
        return "conversion_failed", ""
    return "other", r[:200]


@dataclass(frozen=True)
class DatasetSummary:
    result: str                                # one of RESULTS
    out: str
    takes: int
    pieces_considered: int
    skipped_takes: Tuple[Tuple[str, str], ...]
    pieces: int
    minutes: float
    shortest: Optional[float]
    median: Optional[float]
    longest: Optional[float]
    merged: int
    left_out: int
    reasons: Tuple[Tuple[str, int], ...]       # (REASON_KINDS member, how many), most first
    flags: Tuple[Tuple[str, int], ...]         # (flag, how many pieces carry it), most first
    warnings: Tuple[str, ...]
    problems: Tuple[str, ...]
    advice: Optional[str]                      # one of ADVICE_CODES, or None

    @property
    def ok(self) -> bool:
        return self.result in ("built", "dry_run")


def _ranked(counts: Dict[str, int]) -> Tuple[Tuple[str, int], ...]:
    return tuple(sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])))


def dataset_summary(lines: Iterable[str]) -> Optional[DatasetSummary]:
    """The dataset builder's closing JSON line as data, or None while there is none (the job is still going, or it died before saying anything)."""
    result = None
    for obj in json_objects(lines):
        if obj.get("result") in RESULTS:
            result = obj
    if result is None:
        return None
    included = result.get("included") if isinstance(result.get("included"), dict) else {}
    left = result.get("left_out") if isinstance(result.get("left_out"), dict) else {}
    kinds: Dict[str, int] = {}
    details = left.get("by_reason") if isinstance(left.get("by_reason"), dict) else {}
    for reason, count in details.items():
        if isinstance(count, int) and not isinstance(count, bool):
            kind, _ = reason_kind(str(reason))
            kinds[kind] = kinds.get(kind, 0) + count
    flags = {str(k): v for k, v in (left.get("by_flag") or {}).items() if isinstance(v, int) and not isinstance(v, bool)} if isinstance(left.get("by_flag"), dict) else {}
    pieces = int(included.get("pieces") or 0) if isinstance(included.get("pieces"), int) else 0
    minutes = _num(included.get("minutes")) or 0.0
    advice = advice_for(minutes, pieces) if result["result"] in ("built", "dry_run") else None
    skipped = tuple((str(a), str(b)) for a, b in (result.get("skipped_takes") or []) if isinstance(a, str) and isinstance(b, str)) if isinstance(result.get("skipped_takes"), list) else ()
    return DatasetSummary(
        result["result"], _text(result.get("out")), int(result.get("takes") or 0) if isinstance(result.get("takes"), int) else 0,
        int(result.get("pieces_considered") or 0) if isinstance(result.get("pieces_considered"), int) else 0, skipped, pieces, minutes,
        _num(included.get("shortest")), _num(included.get("median")), _num(included.get("longest")),
        int(result.get("merged") or 0) if isinstance(result.get("merged"), int) else 0, int(left.get("pieces") or 0) if isinstance(left.get("pieces"), int) else 0,
        _ranked(kinds), _ranked(flags), tuple(str(w) for w in (result.get("warnings") or []))[:10] if isinstance(result.get("warnings"), list) else (),
        tuple(str(p) for p in (result.get("problems") or []))[:20] if isinstance(result.get("problems"), list) else (), advice)


def advice_for(minutes: float, pieces: int) -> Optional[str]:
    """Freeform Studio's own note about length: "short" under about ten minutes of speech, "comfortable" from thirty, nothing in between or with no pieces."""
    if pieces <= 0:
        return None
    return "short" if minutes < SHORT_MINUTES else ("comfortable" if minutes >= COMFORTABLE_MINUTES else None)


def flag_name(flag: str) -> str:
    """The flag as shown when it has no sentence of its own: its words, not its code."""
    return flag.replace("_", " ")
