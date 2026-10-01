"""The edit document: what the reviewer decided. Raw audio is never touched; clips are rendered from this at export."""
from __future__ import annotations

import math
import re
from typing import Any, Dict, List, Optional

STATUSES = ("pending", "approved", "dropped")
SEG_ID_RE = re.compile(r"^s\d{3,6}$")
TAG_RE = re.compile(r"^[a-z0-9_-]{1,24}$")
FLAG_RE = re.compile(r"^[a-z_]{1,32}$")
MAX_FLAGS = 16
MAX_SEGMENTS = 5000
MAX_WORDS = 400
MAX_WORD_LEN = 80
MAX_TEXT = 2000
_CONTROL = re.compile(r"[\x00-\x08\x0a-\x1f\x7f]")  # tab (\x09) allowed; newlines are not


def new_edit_doc(segments: List[Dict[str, Any]], rev: int = 1) -> Dict[str, Any]:
    return {"schema": 1, "rev": rev, "segments": segments}


def _num(x: Any) -> Optional[float]:
    if isinstance(x, bool) or not isinstance(x, (int, float)):
        return None
    return float(x) if math.isfinite(x) else None


def clean_words(words: Any) -> List[Dict[str, Any]]:
    """Keep only well-formed word entries and known keys. Words are timing aids; `text` stays the authority."""
    out: List[Dict[str, Any]] = []
    if not isinstance(words, list):
        return out
    for w in words[:MAX_WORDS]:
        if not isinstance(w, dict) or not isinstance(w.get("w"), str):
            continue
        s, e = _num(w.get("s")), _num(w.get("e"))
        if s is None or e is None:
            continue
        p = _num(w.get("p"))
        item: Dict[str, Any] = {"w": w["w"][:MAX_WORD_LEN], "s": round(s, 3), "e": round(max(s, e), 3),
                                "p": round(min(1.0, max(0.0, p)), 3) if p is not None else 1.0}
        for flag in ("j", "m", "ed"):
            if w.get(flag) is True:
                item[flag] = True
        out.append(item)
    return out


def clean_flags(flags: Any) -> List[str]:
    """Warning labels are free-form on purpose (the screens add their own), but only short lowercase names are kept."""
    out: List[str] = []
    if isinstance(flags, list):
        for f in flags:
            if isinstance(f, str) and FLAG_RE.match(f) and f not in out:
                out.append(f)
    return out[:MAX_FLAGS]


def normalize_edit(doc: Any) -> Dict[str, Any]:
    """Copy only the known fields, so stray keys from a client never reach disk."""
    if not isinstance(doc, dict):
        return {"schema": 1, "rev": None, "segments": None}
    segs = doc.get("segments")
    out_segs: Any = None
    if isinstance(segs, list):
        out_segs = []
        for s in segs:
            if not isinstance(s, dict):
                out_segs.append(None)
                continue
            out_segs.append({
                "id": s.get("id"), "start": s.get("start"), "end": s.get("end"), "text": s.get("text"),
                "words": clean_words(s.get("words")),
                "status": s.get("status", "pending"),
                "tags": s.get("tags", []), "note": s.get("note", ""),
                "flags": clean_flags(s.get("flags")),
                "auto": s.get("auto") if isinstance(s.get("auto"), dict) else None,
            })
    return {"schema": 1, "rev": doc.get("rev"), "segments": out_segs}


def validate_edit(doc: Dict[str, Any], duration: float) -> List[str]:
    """Human-readable problems; an empty list means the document is acceptable."""
    errors: List[str] = []
    segs = doc.get("segments")
    if not isinstance(segs, list):
        return ["segments must be a list"]
    if len(segs) > MAX_SEGMENTS:
        return [f"too many segments ({len(segs)} > {MAX_SEGMENTS})"]
    seen = set()
    prev_end = -1.0
    for i, s in enumerate(segs):
        where = f"segment {i + 1}"
        if s is None:
            errors.append(f"{where}: not an object")
            continue
        sid = s.get("id")
        if not isinstance(sid, str) or not SEG_ID_RE.match(sid):
            errors.append(f"{where}: bad id {sid!r}")
        elif sid in seen:
            errors.append(f"{where}: duplicate id {sid}")
        else:
            seen.add(sid)
        a, b = _num(s.get("start")), _num(s.get("end"))
        if a is None or b is None:
            errors.append(f"{where}: start/end must be numbers")
        else:
            if a < 0 or b > duration + 0.05:
                errors.append(f"{where}: outside the recording (0 to {duration:.2f}s)")
            if b - a < 0.05:
                errors.append(f"{where}: shorter than 0.05s")
            if a < prev_end - 1e-6:
                errors.append(f"{where}: overlaps or is out of order with the previous segment")
            prev_end = max(prev_end, b)
        text = s.get("text")
        if not isinstance(text, str):
            errors.append(f"{where}: text must be a string")
        else:
            if len(text) > MAX_TEXT:
                errors.append(f"{where}: text longer than {MAX_TEXT} characters")
            if "|" in text:
                errors.append(f"{where}: text contains '|', which is the metadata.csv separator")
            if _CONTROL.search(text):
                errors.append(f"{where}: text contains control characters or line breaks")
        status = s.get("status")
        if status not in STATUSES:
            errors.append(f"{where}: status must be one of {STATUSES}")
        elif status == "approved" and isinstance(text, str) and not text.strip():
            errors.append(f"{where}: cannot approve a segment with no text")
        tags = s.get("tags")
        if not isinstance(tags, list) or len(tags) > 8 or not all(isinstance(t, str) and TAG_RE.match(t) for t in tags):
            errors.append(f"{where}: tags must be up to 8 short lowercase labels")
        note = s.get("note")
        if not isinstance(note, str) or len(note) > 500:
            errors.append(f"{where}: note must be text up to 500 characters")
    return errors
