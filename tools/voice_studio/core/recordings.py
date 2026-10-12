# SPDX-License-Identifier: GPL-3.0-or-later
"""The recordings of a project, as plain facts (plan task VS-2.10): what is in the project, how far each one has got, and the three ways voice data comes in.

Looking is all this file does for the folder: it reads each recording's own notes (`take.json`, the file Freeform Studio keeps) and never writes. Bringing data in is
Freeform Studio's own code (ack_import.py for an ACK package, files_import.py for audio files on disk), so the two programs can never disagree about what a recording is;
this file adds the one error vocabulary the screens speak and the small decisions around it.

Four kinds of data come in. They are a choice the person makes, never guessed from the files:
  package  a zip that ACK saved on the phone;
  pairs    a folder of audio files, each with a text file of the same name that holds what was said;
  table    a folder of audio files and one table (a `metadata.csv` such as other voice tools write) that says what each file holds;
  audio    a folder of audio files and nothing else: the computer listens and writes the sentences.
Nothing here uses the network.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from freeform_studio.config import Config
from freeform_studio.files_import import FilesImportProblem
from freeform_studio.storage import TAKE_ID_RE

from . import joblines, jobs

LANGUAGE = "en-US"                                                  # the folder name Freeform Studio files recordings under; one language for now
KINDS = ("package", "pairs", "table", "audio")                      # each has words in the text catalog (`recordings.kind.<kind>`)
WAITING = ("finishing", "queued", "transcribing")                   # Freeform Studio's process.WAITING: not yet listened to
FAILED = "error"
READY = "ready"
MAX_TAKE_FILE = 1 << 20                                             # a recording's notes are small; a larger file is not one of ours
ERROR_CODES = ("bad_kind", "not_a_folder", "no_audio", "too_many_files", "unreadable", "too_big")      # what stops an import of files before anything is written; each has words in the text catalog


class RecordingsError(Exception):
    """`code` is one of ERROR_CODES; `detail` is a short fact (a name, a number) for Show details."""

    def __init__(self, code: str, detail: str = ""):
        super().__init__(code + (": " + detail if detail else ""))
        self.code = code
        self.detail = detail


def stop_from(problem: FilesImportProblem) -> RecordingsError:
    """What stopped a folder import, in this tool's one error vocabulary. A code Freeform Studio has and this tool does not know reads as "unreadable", with the original under Show details."""
    code, detail = problem.code, problem.detail
    if code == "bad_kind":
        return RecordingsError("bad_kind", detail)
    if code == "not_a_folder":
        return RecordingsError("not_a_folder", detail)
    if code == "no_audio":
        return RecordingsError("no_audio", detail)
    if code == "too_many_files":
        return RecordingsError("too_many_files", detail)
    if code == "too_big":
        return RecordingsError("too_big", detail)
    return RecordingsError("unreadable", detail or code)


@dataclass(frozen=True)
class TakeRow:
    id: str
    label: str
    status: str
    seconds: Optional[float]
    origin: str                         # "phone" (an ACK package), "files" (audio files brought in) or "other" (recorded in Freeform Studio itself)


@dataclass(frozen=True)
class TakesView:
    rows: Tuple[TakeRow, ...]           # newest first
    unreadable: int                     # recording folders whose notes could not be read (they are left alone)

    @property
    def total(self) -> int:
        return len(self.rows)

    def count(self, *statuses: str) -> int:
        return sum(1 for r in self.rows if r.status in statuses)

    @property
    def waiting(self) -> int:
        return self.count(*WAITING)

    @property
    def failed(self) -> int:
        return self.count(FAILED)

    @property
    def ready(self) -> int:
        return self.count(READY)

    @property
    def other(self) -> int:
        return self.total - self.waiting - self.failed - self.ready

    @property
    def minutes(self) -> float:
        """The length of every recording whose length is known, in minutes."""
        return round(sum(r.seconds or 0.0 for r in self.rows) / 60.0, 1)


def takes_dir(recordings: str, code: str = LANGUAGE) -> Path:
    return Config(output_dir=Path(recordings), code=code).takes_dir


def origin_of(client: Any) -> str:
    if isinstance(client, dict):
        if client.get("source") == "files":
            return "files"
        if client.get("ack_session"):
            return "phone"
    return "other"


def _number(value: Any) -> Optional[float]:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0 else None


def _read_notes(folder: Path) -> Optional[Dict[str, Any]]:
    path = folder / "take.json"
    try:
        if path.is_symlink() or path.stat().st_size > MAX_TAKE_FILE:
            return None
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, RecursionError):
        return None
    return doc if isinstance(doc, dict) else None


def read_takes(recordings: str, code: str = LANGUAGE) -> TakesView:
    """Every recording in the project, newest first. A folder that is not a recording's is skipped; one whose notes cannot be read is counted and left alone."""
    base = takes_dir(recordings, code)
    rows = []
    bad = 0
    try:
        names = sorted((n for n in (p.name for p in base.iterdir()) if TAKE_ID_RE.match(n)), reverse=True)
    except OSError:
        return TakesView((), 0)
    for name in names:
        folder = base / name
        if folder.is_symlink() or not folder.is_dir():
            continue
        doc = _read_notes(folder)
        if doc is None:
            bad += 1
            continue
        status = doc.get("status")
        label = doc.get("label")
        rows.append(TakeRow(name, label[:120] if isinstance(label, str) else "", status if isinstance(status, str) else "", _number(doc.get("duration")), origin_of(doc.get("client"))))
    return TakesView(tuple(rows), bad)


# ---------------------------------------------------------------- the job that listens

@dataclass(frozen=True)
class Listening:
    """The newest job that listened to this project's recordings, and what its own log says it is doing."""
    job: jobs.JobInfo
    active: bool                        # still starting, running or stopping
    doing: str                          # the name of the recording it is on right now ("" when the log does not say)
    percent: Optional[int]              # how far through that one, 0 to 99
    model_missing: str                  # the listening model it could not find, or ""


def listening_job(jobs_root: str, project_id: str) -> Optional[Listening]:
    """The newest `process` job of this project, or None if there never was one. Reads the job's own files; starts and stops nothing."""
    mine = [j for j in jobs.list_jobs(jobs_root).jobs if j.spec.kind == "process" and j.spec.project == project_id]
    if not mine:
        return None
    job = mine[-1]
    state = joblines.process_state(jobs.tail_log(job.dir))
    current = next((t for t in reversed(state.takes) if t.status not in ("ready", "error")), None)
    percent = None if current is None or current.progress is None else max(0, min(99, int(current.progress * 100)))
    return Listening(job, job.status in jobs.ACTIVE, current.label[:120] if current else "", percent, state.model_missing)
