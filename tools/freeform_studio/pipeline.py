# SPDX-License-Identifier: GPL-3.0-or-later
"""recognizer output + audio -> proposed segments. Shared by the server and the smoke-test script."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .ack_segments import propose_segments_ack, usable_notes
from .audio import rms_envelope
from .refine import refine_word_times
from .segmenter import SegOptions, build_segments


def propose_segments(asr: Dict[str, Any], wav_path: Path, duration: float,
                     opts: Optional[SegOptions] = None) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    db, hop = rms_envelope(wav_path)
    refined, stats = refine_word_times(asr, db, hop)
    return build_segments(refined, duration, opts), stats


def propose_segments_for_take(asr: Dict[str, Any], wav_path: Path, duration: float, opts: Optional[SegOptions] = None,
                              ack_notes: Optional[Dict[str, Any]] = None) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Pieces for one recording. One that came from ACK (it has ack_clips.json) is cut where the phone recorded its clips; every
    other recording is cut by sentences, exactly as before."""
    if ack_notes is not None and usable_notes(ack_notes):
        return propose_segments_ack(asr, wav_path, duration, ack_notes, opts)
    return propose_segments(asr, wav_path, duration, opts)
