"""recognizer output + audio -> proposed segments. Shared by the server and the smoke-test script."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .audio import rms_envelope
from .refine import refine_word_times
from .segmenter import SegOptions, build_segments


def propose_segments(asr: Dict[str, Any], wav_path: Path, duration: float,
                     opts: Optional[SegOptions] = None) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    db, hop = rms_envelope(wav_path)
    refined, stats = refine_word_times(asr, db, hop)
    return build_segments(refined, duration, opts), stats
