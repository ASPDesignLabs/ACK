# SPDX-License-Identifier: GPL-3.0-or-later
"""Builds ACK training-capture packages the way ACK's writer must (docs/ACK_TRAINING_CAPTURE_FORMAT.md): real WAV audio, a
manifest with true checksums and measurements, a zip holding only the allowed entries.

Tests use it to make good packages, and to break exactly one thing at a time (a hook edits the manifest, the zip entries or the
zip metadata just before it is written). It is also the Python half of the contract with the Kotlin writer.
"""
from __future__ import annotations

import copy
import hashlib
import json
import struct
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, Union

import numpy as np

import ack_capture_reference as ref


def wav_bytes(samples: np.ndarray, rate: int) -> bytes:
    data = np.asarray(samples, dtype="<i2").tobytes()
    header = (b"RIFF" + struct.pack("<I", 36 + len(data)) + b"WAVE" + b"fmt " + struct.pack("<IHHIIHH", 16, 1, 1, rate, rate * 2, 2, 16)
              + b"data" + struct.pack("<I", len(data)))
    return header + data


def tone(lead: float, speech: float, tail: float, amp: int, rate: int) -> np.ndarray:
    return ref.square_samples([{"seconds": lead, "amp": 0}, {"seconds": speech, "amp": amp}, {"seconds": tail, "amp": 0}], rate)


def iso(base: datetime, plus_s: float = 0.0) -> str:
    return (base + timedelta(seconds=plus_s)).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class ClipSpec:
    text: str
    lead: float = 0.5          # quiet before the speech
    speech: float = 2.0        # seconds of "speech" (a square wave)
    tail: float = 0.6
    amp: int = 8000
    flags: List[str] = field(default_factory=list)
    card: Optional[int] = None
    attempt: int = 1


Entry = Tuple[str, bytes]
ZipInfoEdit = Callable[[str, zipfile.ZipInfo], None]


class PackageBuilder:
    def __init__(self, created: str = "2026-10-02T19:30:00Z", version: str = "1.0-beta.9"):
        self.created = created
        self.version = version
        self.sessions: List[Dict[str, Any]] = []
        self.audio: Dict[str, bytes] = {}
        self._n = 0
        self._base = datetime(2026, 10, 2, 18, 4, 11, tzinfo=timezone.utc)

    # -- sessions ---------------------------------------------------------------------------------------------------
    def _next_id(self) -> str:
        self._n += 1
        return f"s20261002-18{self._n:02d}00-{0xa3f9 + self._n:04x}"

    def script_session(self, clips: Sequence[Union[str, ClipSpec]], *, rate: int = 48000, label: str = "closet, phone on stand, 30 cm",
                       noise_floor: Optional[float] = -62.3, sid: Optional[str] = None, source: str = "UNPROCESSED",
                       requested: str = "UNPROCESSED", script_id: str = "sample-script", device: Optional[Dict[str, Any]] = None) -> str:
        sid = sid or self._next_id()
        thr = ref.threshold_db(noise_floor)
        started = self._base + timedelta(minutes=self._n)
        out_clips = []
        t = 0.0
        for i, spec in enumerate(clips, start=1):
            spec = ClipSpec(spec) if isinstance(spec, str) else spec
            samples = tone(spec.lead, spec.speech, spec.tail, spec.amp, rate)
            name = f"sessions/{sid}/clips/{i:04d}.wav"
            self.audio[name] = wav_bytes(samples, rate)
            m = ref.clip_metrics(samples, rate, thr)
            speech = m.pop("speech")
            out_clips.append({"index": i, "card": spec.card or i, "attempt": spec.attempt, "file": name, "text": spec.text,
                              "recorded": iso(started, t), "duration_s": round(len(samples) / rate, 3), "speech": speech,
                              "metrics": m, "flags": list(spec.flags)})
            t += len(samples) / rate + 1.0
        s: Dict[str, Any] = {
            "id": sid, "mode": "script", "label": label, "started": iso(started), "ended": iso(started, t), "language": "en-US",
            "audio": {"sample_rate": rate, "source": source, "source_requested": requested},
            "noise_floor_dbfs": noise_floor, "threshold_dbfs": ref.rnd(thr, 1),
            "script": {"id": script_id, "title": "Sample script", "cards_total": max(len(out_clips), 1)}, "clips": out_clips}
        if device is not None:
            s["device"] = device
        self.sessions.append(s)
        return sid

    def free_session(self, pieces: Sequence[Tuple[float, float]], *, rate: int = 48000, label: str = "kitchen", topic: str = "",
                     amp: int = 8000, sid: Optional[str] = None, noise_floor: Optional[float] = None) -> str:
        """pieces: (quiet seconds, speech seconds) pairs, in order, followed by half a second of quiet."""
        sid = sid or self._next_id()
        thr = ref.threshold_db(noise_floor)
        parts = []
        for quiet, speech in pieces:
            parts += [{"seconds": quiet, "amp": 0}, {"seconds": speech, "amp": amp}]
        parts.append({"seconds": 0.5, "amp": 0})
        samples = ref.square_samples(parts, rate)
        name = f"sessions/{sid}/session.wav"
        self.audio[name] = wav_bytes(samples, rate)
        proposals = ref.propose_segments(ref.hop_levels(samples, rate), thr)
        for p in proposals:
            piece = samples[int(p["start_s"] * rate):int(p["end_s"] * rate)]
            m = ref.clip_metrics(piece, rate, thr)
            m.pop("speech")
            p["metrics"] = m
        whole = ref.clip_metrics(samples, rate, thr)
        whole.pop("speech")
        started = self._base + timedelta(minutes=self._n)
        dur = round(len(samples) / rate, 3)
        s: Dict[str, Any] = {
            "id": sid, "mode": "free", "label": label, "started": iso(started), "ended": iso(started, dur), "language": "en-US",
            "audio": {"sample_rate": rate, "source": "UNPROCESSED", "source_requested": "UNPROCESSED"},
            "noise_floor_dbfs": noise_floor, "threshold_dbfs": ref.rnd(thr, 1), "topic": topic,
            "recording": {"file": name, "duration_s": dur, "metrics": whole, "proposed_segments": proposals}}
        self.sessions.append(s)
        return sid

    # -- output -----------------------------------------------------------------------------------------------------
    def manifest(self) -> Dict[str, Any]:
        files = [{"path": name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()} for name, data in sorted(self.audio.items())]
        return {"schema": "ack-training-capture/1", "created": self.created, "app": {"name": "ACK", "version": self.version},
                "sessions": copy.deepcopy(self.sessions), "files": files}

    def write(self, path: Path, *, manifest_edit: Optional[Callable[[Dict[str, Any]], None]] = None,
              entries_edit: Optional[Callable[[List[Entry]], None]] = None, zipinfo_edit: Optional[ZipInfoEdit] = None,
              compression: int = zipfile.ZIP_DEFLATED) -> Path:
        manifest = self.manifest()
        if manifest_edit:
            manifest_edit(manifest)
        entries: List[Entry] = [("manifest.json", (json.dumps(manifest, indent=1) + "\n").encode("utf-8"))]
        entries += sorted(self.audio.items())
        if entries_edit:
            entries_edit(entries)
        write_zip(path, entries, compression, zipinfo_edit)
        return path


def write_zip(path: Path, entries: Sequence[Entry], compression: int = zipfile.ZIP_DEFLATED, zipinfo_edit: Optional[ZipInfoEdit] = None) -> None:
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")                      # duplicate names are made on purpose in some tests
        with zipfile.ZipFile(path, "w", compression) as zf:
            for name, data in entries:
                info = zipfile.ZipInfo(name, date_time=(2026, 10, 2, 19, 30, 0))
                info.compress_type = compression
                info.external_attr = 0o644 << 16
                if zipinfo_edit:
                    zipinfo_edit(name, info)
                zf.writestr(info, data)
