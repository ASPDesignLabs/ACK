# SPDX-License-Identifier: GPL-3.0-or-later
"""Training rounds (plan task VS-4.2, decisions D12, D34 and P11): many rounds in a row, each one continuing from the person's own latest saved point.

A **round** is one run of the trainer for about 25 minutes. It always resumes from a saved point (a `last.ckpt`): the starting voice's the first time, and after that the
**chosen round's**, never the starting voice again by accident. Everything the tool knows about the rounds is one small file, `rounds/rounds.json`; the trainer's own files
stay where it puts them (`rounds/run/lightning_logs/version_N/checkpoints/`), and the tool never deletes, moves or renames any of them (that is *Free up space*, VS-4.7).

    starting ──► running ──► finished     ended by itself (the time limit, or finished its work)      } a saved point is kept only when
        │            ├──────► stopped      ended after the person asked it to stop (one Ctrl+C)        } the file is whole: then the round
        │            ├──────► failed       ended by itself with an error                               } becomes the **chosen** one
        │            └──────► interrupted  the computer restarted, or the job was ended from outside     (a failed or interrupted round's file is never trusted)
        └───────────────────► never_started  the job never came up

* **The chosen round** (`Record.current`) is where the next round resumes from, what *listen* and *export* use, and what *go back* moves. It moves to a round by itself when
  that round ends with a whole saved point, and by hand through `choose` / `go_back` (never while a round runs). `0` means "no round of this person's has a saved point yet":
  only then does a round start from the starting voice (and then it records which one).
* **Going back** is choosing the round the chosen one resumed from (its *parent*). The next round resumes from there and is a new branch: the round that was left is not erased.
  Rounds are numbered 1, 2, 3 ... and a number is never reused or renumbered.
* **The trainer numbers its own folders** (`version_0`, `version_1` ...) and the tool does not choose them: a round's folder is the one that appeared since it began
  (`versions_before` is the list at that moment). A folder is never claimed by two rounds.
* **Every round gets a new working folder** (`caches/<training set>-r<NNN>`, which `train_command` refuses to reuse): a cache built from other audio trains on the old audio
  without a word, and this makes that impossible rather than unlikely. The plan's words "rotate the cache whenever the audio changes" are therefore kept in their strongest form
  (it changes every round). Reusing one across rounds would save the minute or two of building it; that needs a measurement and a way to tell a half-built cache from a whole one.
* **What is kept** (P11): the chosen round's `last.ckpt` and its parent's. Every other checkpoint file is *spare*, offered only through *Free up space* after one confirmation,
  and nothing the tool did not make is ever offered (`classify`).

This file decides, reads small files and writes the record. It starts a job only through the function it is handed (`start_round`), says no words (the catalog has them) and never
touches the network.
"""
from __future__ import annotations

import errno
import fcntl
import json
import os
import tempfile
import time
import zipfile
from contextlib import contextmanager
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Iterator, List, Optional, Tuple

from . import jobs
from .commands import BATCH_SIZE, CHECK_VAL_EVERY_N_EPOCH, CHECKPOINT_DIR, NUM_WORKERS, ROUND_MINUTES, SAFE_NAME, Command, train_command
from .diskbudget import CleanupItem, Kind
from .envbuild import EnvPaths
from .paths import ProjectPaths, ScratchPaths
from .project import clean_text

SCHEMA = 1
MAX_MINUTES = 24 * 60            # a sanity limit against a typo, not a rule about training: a whole day
MAX_NOTE = 500
MAX_VERSION = 1_000_000
MAX_ROUNDS = 10_000
STARTING_GRACE_S = 120.0         # a round that was written down but whose job has not shown up after this long never started (the program ended in between)
LOCK_WAIT_S = 5.0

STATES = ("starting", "running", "finished", "stopped", "failed", "interrupted", "never_started")             # each has words in the text catalog
ACTIVE_STATES = ("starting", "running")
RESUMABLE_STATES = ("finished", "stopped")
FAILURE_CODES = ("no_checkpoint", "exit", "signal", "program", "job_missing", "never_started")                # each has words in the text catalog
ERROR_CODES = ("damaged", "newer", "unreadable", "cannot_save", "busy", "bad_value", "round_running", "no_start", "checkpoint_missing", "checkpoint_damaged",
               "unknown_round", "not_usable", "nowhere_back")                                                  # each has words in the text catalog
CHECKPOINT_STATUSES = ("none", "missing", "damaged", "ok")
LAST = "last.ckpt"
STAMP_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


class RoundsError(Exception):
    """`code` is a short word the screens turn into a plain sentence (ERROR_CODES); `detail` is a short fact (a round number, a field name) for Show details."""

    def __init__(self, code: str, detail: str = ""):
        super().__init__(code + (": " + detail if detail else ""))
        self.code = code
        self.detail = detail


# ---------------------------------------------------------------- the model

@dataclass(frozen=True)
class Round:
    number: int                              # 1, 2, 3 ...; never reused
    parent: int                              # the round it resumed from; 0 = the starting voice
    voice: str                               # the starting voice used, when parent is 0 (empty otherwise)
    dataset: str                             # the training set's folder name
    minutes: int                             # how long it was asked to train
    state: str                               # one of STATES
    started: str                             # UTC, "2026-10-11T12:00:00Z"
    ended: str = ""
    job: str = ""                            # the job's folder name under state/jobs
    version: Optional[int] = None            # the trainer's lightning_logs/version_N for this round, once it exists
    versions_before: Tuple[int, ...] = ()    # the version folders that existed when the round began
    has_checkpoint: bool = False             # it ended with a whole saved point (finished or stopped); that is what makes it choosable
    failure: str = ""                        # one of FAILURE_CODES, or empty
    exit_code: Optional[int] = None
    note: str = ""                           # the helper's own words about the round (VS-4.5)
    extra: Dict[str, Any] = field(default_factory=dict)       # fields a newer version added, kept so saving never loses them


@dataclass(frozen=True)
class Record:
    rounds: Tuple[Round, ...] = ()
    current: int = 0                         # the chosen round; 0 = none yet
    extra: Dict[str, Any] = field(default_factory=dict)


ROUND_FIELDS = {"number", "parent", "voice", "dataset", "minutes", "state", "started", "ended", "job", "version", "versions_before", "has_checkpoint", "failure",
                "exit_code", "note"}
RECORD_FIELDS = {"schema", "rounds", "current"}


def find(record: Record, number: int) -> Optional[Round]:
    if isinstance(number, bool) or not isinstance(number, int):                 # True is not round 1
        return None
    return next((r for r in record.rounds if r.number == number), None)


def active(record: Record) -> Optional[Round]:
    return next((r for r in record.rounds if r.state in ACTIVE_STATES), None)


def chosen(record: Record) -> Optional[Round]:
    return find(record, record.current) if record.current else None


def next_number(record: Record) -> int:
    return max((r.number for r in record.rounds), default=0) + 1


def lineage(record: Record, number: int) -> Tuple[Round, ...]:
    """The round and every round it was resumed from, oldest first: the training that made that voice. Rounds left on a side branch are not in it."""
    chain: List[Round] = []
    current = find(record, number)
    while current is not None and len(chain) <= len(record.rounds):
        chain.append(current)
        current = find(record, current.parent) if current.parent else None
    return tuple(reversed(chain))


def _parse_stamp(text: str) -> Optional[datetime]:
    try:
        return datetime.strptime(text, STAMP_FORMAT).replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None


def elapsed_minutes(r: Round) -> Optional[int]:
    """Whole minutes from the start to the end of a round, or None when either time cannot be read. It includes the minute or so of loading and saving."""
    start, end = _parse_stamp(r.started), _parse_stamp(r.ended)
    if start is None or end is None:
        return None
    return max(0, int((end - start).total_seconds() // 60))


def trained_minutes(record: Record, number: int) -> int:
    """About how long the voice at round `number` has been trained: the asked length of each round that ran its whole time, and the time a stopped one actually ran
    (never more than it was asked for). Failed rounds are never in a lineage. A total, not a promise: the minute of loading is not training."""
    total = 0
    for r in lineage(record, number):
        if r.state == "stopped":
            elapsed = elapsed_minutes(r)
            total += r.minutes if elapsed is None else min(r.minutes, elapsed)
        elif r.state == "finished":
            total += r.minutes
    return total


# ---------------------------------------------------------------- reading and writing the record

def _int(raw: Any, key: str, low: int, high: int) -> int:
    value = raw.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise RoundsError("damaged", key)
    return value


def _opt_int(raw: Any, key: str, low: int, high: int) -> Optional[int]:
    if raw.get(key) is None:
        return None
    return _int(raw, key, low, high)


def _str(raw: Any, key: str, limit: int, *, required: bool = False) -> str:
    value = raw.get(key, "")
    if value is None:
        value = ""
    if not isinstance(value, str) or len(value) > limit:
        raise RoundsError("damaged", key)
    if required and not value:
        raise RoundsError("damaged", key)
    return value


def _stamp(raw: Any, key: str, *, required: bool) -> str:
    value = _str(raw, key, 40, required=required)
    if value and _parse_stamp(value) is None:
        raise RoundsError("damaged", key)
    return value


def _name(raw: Any, key: str, *, required: bool) -> str:
    value = _str(raw, key, 64, required=required)
    if value and not SAFE_NAME.match(value):
        raise RoundsError("damaged", key)
    return value


def _round_from(raw: Any) -> Round:
    if not isinstance(raw, dict):
        raise RoundsError("damaged", "rounds")
    parent = _int(raw, "parent", 0, MAX_ROUNDS)
    before = raw.get("versions_before", [])
    if not isinstance(before, list) or len(before) > MAX_ROUNDS or any(isinstance(v, bool) or not isinstance(v, int) or not 0 <= v <= MAX_VERSION for v in before):
        raise RoundsError("damaged", "versions_before")
    flag = raw.get("has_checkpoint", False)
    if not isinstance(flag, bool):
        raise RoundsError("damaged", "has_checkpoint")
    state, failure = _str(raw, "state", 20, required=True), _str(raw, "failure", 20)
    if state not in STATES:
        raise RoundsError("damaged", "state")
    if failure and failure not in FAILURE_CODES:
        raise RoundsError("damaged", "failure")
    note = raw.get("note", "")
    if note is None:
        note = ""
    if not isinstance(note, str):
        raise RoundsError("damaged", "note")
    return Round(
        number=_int(raw, "number", 1, MAX_ROUNDS), parent=parent, voice=_name(raw, "voice", required=(parent == 0)), dataset=_name(raw, "dataset", required=True),
        minutes=_int(raw, "minutes", 1, MAX_MINUTES), state=state, started=_stamp(raw, "started", required=True), ended=_stamp(raw, "ended", required=False), job=_name(raw, "job", required=False),
        version=_opt_int(raw, "version", 0, MAX_VERSION), versions_before=tuple(before), has_checkpoint=flag, failure=failure, exit_code=_opt_int(raw, "exit_code", -1_000_000, 1_000_000),
        note=clean_text(note, MAX_NOTE), extra={k: v for k, v in raw.items() if k not in ROUND_FIELDS})


def validate(record: Record) -> None:
    """The rules a record keeps whatever wrote it. A record that breaks one is *damaged*: it is reported and left exactly as it is, never repaired by guessing."""
    seen: List[int] = []
    versions: List[int] = []
    saved_points = {r.number for r in record.rounds if r.has_checkpoint}
    for r in record.rounds:
        if seen and r.number <= seen[-1]:
            raise RoundsError("damaged", "order")
        if r.state not in STATES or (r.failure and r.failure not in FAILURE_CODES):
            raise RoundsError("damaged", "state")
        if r.parent >= r.number or (r.parent and r.parent not in saved_points):          # a round resumes from a saved point, so its parent has one
            raise RoundsError("damaged", "parent")
        if (r.parent == 0) != bool(r.voice):
            raise RoundsError("damaged", "voice")
        if r.state not in ACTIVE_STATES and not r.ended:
            raise RoundsError("damaged", "ended")
        if r.state in ACTIVE_STATES and (r.ended or r.has_checkpoint or r.failure):
            raise RoundsError("damaged", "state")
        if r.has_checkpoint and (r.state not in RESUMABLE_STATES or r.version is None):
            raise RoundsError("damaged", "has_checkpoint")
        if r.failure and r.state in RESUMABLE_STATES:
            raise RoundsError("damaged", "failure")
        if r.version is not None:
            if r.version in versions or r.version in r.versions_before:
                raise RoundsError("damaged", "version")
            versions.append(r.version)
        if list(r.versions_before) != sorted(set(r.versions_before)):
            raise RoundsError("damaged", "versions_before")
        seen.append(r.number)
    if sum(1 for r in record.rounds if r.state in ACTIVE_STATES) > 1 or any(r.state in ACTIVE_STATES for r in record.rounds[:-1]):
        raise RoundsError("damaged", "active")
    if record.current != 0 and record.current not in saved_points:
        raise RoundsError("damaged", "current")
    if record.current == 0 and saved_points:
        raise RoundsError("damaged", "current")


def record_from_text(text: str) -> Record:
    try:
        raw = json.loads(text)
    except (ValueError, RecursionError):                         # RecursionError: a file nested far too deep is damaged too
        raise RoundsError("damaged", "not JSON")
    if not isinstance(raw, dict):
        raise RoundsError("damaged", "not an object")
    schema = raw.get("schema")
    if isinstance(schema, bool) or not isinstance(schema, int):
        raise RoundsError("damaged", "schema")
    if schema > SCHEMA:
        raise RoundsError("newer", str(schema))                  # made by a newer version: read-only here, never rewritten by an older one
    listed = raw.get("rounds", [])
    if listed is None:
        listed = []
    if not isinstance(listed, list) or len(listed) > MAX_ROUNDS:
        raise RoundsError("damaged", "rounds")
    record = Record(tuple(_round_from(r) for r in listed), _int(raw, "current", 0, MAX_ROUNDS) if "current" in raw else 0,
                    {k: v for k, v in raw.items() if k not in RECORD_FIELDS})
    validate(record)
    return record


def record_to_dict(record: Record) -> Dict[str, Any]:
    data: Dict[str, Any] = dict(record.extra)
    data.update({"schema": SCHEMA, "current": record.current, "rounds": [round_to_dict(r) for r in record.rounds]})
    return data


def round_to_dict(r: Round) -> Dict[str, Any]:
    data: Dict[str, Any] = dict(r.extra)
    data.update({"number": r.number, "parent": r.parent, "voice": r.voice, "dataset": r.dataset, "minutes": r.minutes, "state": r.state, "started": r.started,
                 "ended": r.ended, "job": r.job, "version": r.version, "versions_before": list(r.versions_before), "has_checkpoint": r.has_checkpoint,
                 "failure": r.failure, "exit_code": r.exit_code, "note": r.note})
    return data


def _atomic_write(path: str, body: bytes) -> None:
    fd, temp = tempfile.mkstemp(dir=os.path.dirname(path), prefix=".rounds-", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(body)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temp, 0o600)
        os.replace(temp, path)
    except BaseException:
        try:
            os.unlink(temp)
        except OSError:
            pass
        raise


def load(paths: ProjectPaths) -> Record:
    """The record, or an empty one when none was ever written. A file that cannot be read or is damaged is reported and left exactly as it is."""
    try:
        with open(paths.rounds_file, encoding="utf-8") as handle:
            return record_from_text(handle.read())
    except FileNotFoundError:
        return Record()
    except (OSError, UnicodeDecodeError) as exc:
        raise RoundsError("unreadable", getattr(exc, "strerror", None) or type(exc).__name__)


def _save(paths: ProjectPaths, record: Record) -> None:
    validate(record)
    body = (json.dumps(record_to_dict(record), indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    try:
        if os.path.exists(paths.rounds_file):
            try:
                with open(paths.rounds_file, "rb") as old:
                    _atomic_write(paths.rounds_previous, old.read())            # the exact bytes of the version being replaced
            except OSError:
                pass                                                              # a copy that cannot be made must not stop the save, but is not pretended
        _atomic_write(paths.rounds_file, body)
    except OSError as exc:
        raise RoundsError("cannot_save", getattr(exc, "strerror", None) or type(exc).__name__)


@contextmanager
def _locked(paths: ProjectPaths) -> Iterator[None]:
    """Two windows (or a window and a terminal) never change the record at the same time: the second waits a few seconds, then says so."""
    try:
        os.makedirs(paths.rounds, mode=0o700, exist_ok=True)
        fd = os.open(paths.rounds_lock, os.O_RDWR | os.O_CREAT, 0o600)
    except OSError as exc:
        raise RoundsError("cannot_save", getattr(exc, "strerror", None) or type(exc).__name__)
    try:
        deadline = time.monotonic() + LOCK_WAIT_S
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError as exc:
                if exc.errno not in (errno.EAGAIN, errno.EACCES, errno.EWOULDBLOCK):
                    raise RoundsError("cannot_save", exc.strerror or "lock")
                if time.monotonic() >= deadline:
                    raise RoundsError("busy", "record")
                time.sleep(0.05)
        yield
    finally:
        os.close(fd)


def modify(paths: ProjectPaths, change: Callable[[Record], Record]) -> Record:
    """Read, change and write back under the lock. `change` may raise RoundsError (nothing is written); a change that changes nothing writes nothing."""
    with _locked(paths):
        old = load(paths)
        new = change(old)
        if new != old:
            _save(paths, new)
        return new


# ---------------------------------------------------------------- the trainer's files

def checkpoint_complete(path: str) -> bool:
    """Is this a whole saved point? PyTorch writes a checkpoint as a zip whose index is at the *end* of the file, so a file cut short by a crash or a full disk does not open,
    and one that opens has the pickled state in it (`data.pkl`). Reads the index only, never the weights."""
    try:
        with zipfile.ZipFile(path) as archive:
            return any(name == "data.pkl" or name.endswith("/data.pkl") for name in archive.namelist())
    except (OSError, zipfile.BadZipFile, zipfile.LargeZipFile, ValueError, EOFError, RuntimeError, NotImplementedError):
        return False


def version_dirs(paths: ProjectPaths) -> Tuple[int, ...]:
    """The `lightning_logs/version_N` folders under the run folder, as numbers. A link is not a folder the trainer made."""
    base = paths.run + "/lightning_logs"
    try:
        with os.scandir(base) as entries:
            found = sorted(int(m.group(1)) for e in entries for m in [CHECKPOINT_DIR.match(e.name)] if m and e.is_dir(follow_symlinks=False))
    except OSError:
        return ()
    return tuple(found)


def checkpoint_file(paths: ProjectPaths, r: Round) -> Optional[str]:
    """Where this round's `last.ckpt` is (or would be). Worked out from the round's version number, never read from the record as a path."""
    if r.version is None:
        return None
    return "%s/lightning_logs/version_%d/checkpoints/%s" % (paths.run, r.version, LAST)


def checkpoint_status(paths: ProjectPaths, r: Round) -> str:
    """none (this round never made a whole saved point), missing (it did and the file is gone), damaged (it is there but not whole), ok."""
    path = checkpoint_file(paths, r)
    if path is None or not r.has_checkpoint:
        return "none"
    if not os.path.isfile(path):
        return "missing"
    return "ok" if checkpoint_complete(path) else "damaged"


def _new_version(paths: ProjectPaths, record: Record, r: Round) -> Optional[int]:
    """The folder that appeared since this round began and that no other round claimed. If several did, the newest."""
    taken = {o.version for o in record.rounds if o.version is not None and o.number != r.number}
    fresh = [v for v in version_dirs(paths) if v not in r.versions_before and v not in taken]
    return max(fresh) if fresh else None


# ---------------------------------------------------------------- planning a round

@dataclass(frozen=True)
class Base:
    voice: str                    # the starting voice's id
    checkpoint: str               # its file, kept and checked (core/startvoice.py::kept_path)


@dataclass(frozen=True)
class RoundPlan:
    number: int
    parent: int
    voice: str
    dataset: str
    minutes: int
    resume_from: str
    run_dir: str
    cache_dir: str
    config_path: str
    dataset_dir: str
    versions_before: Tuple[int, ...]


def _check_minutes(minutes: object) -> None:
    if isinstance(minutes, bool) or not isinstance(minutes, int) or not 1 <= minutes <= MAX_MINUTES:
        raise RoundsError("bad_value", "minutes")


def _check_name(value: object, what: str) -> None:
    if not isinstance(value, str) or not SAFE_NAME.match(value):
        raise RoundsError("bad_value", what)


def resume_source(paths: ProjectPaths, record: Record, base: Optional[Base]) -> Tuple[str, int, str]:
    """(file, parent, starting voice). The chosen round's saved point if there is a chosen round; otherwise, and only then, the starting voice.
    A chosen round whose file is gone or is not whole stops the round with a reason: it never quietly falls back to another file."""
    pick = chosen(record)
    if pick is not None:
        status = checkpoint_status(paths, pick)
        if status == "ok":
            return checkpoint_file(paths, pick) or "", pick.number, ""
        raise RoundsError("checkpoint_damaged" if status == "damaged" else "checkpoint_missing", str(pick.number))
    if base is None:
        raise RoundsError("no_start")
    _check_name(base.voice, "voice")
    return base.checkpoint, 0, base.voice


def plan_round(paths: ProjectPaths, scratch: ScratchPaths, record: Record, *, dataset: str, minutes: int = ROUND_MINUTES, base: Optional[Base] = None) -> RoundPlan:
    """What the next round would be. Changes nothing. Refuses while a round is running."""
    _check_minutes(minutes)
    _check_name(dataset, "dataset")
    running = active(record)
    if running is not None:
        raise RoundsError("round_running", str(running.number))
    source, parent, voice = resume_source(paths, record, base)
    number = next_number(record)
    return RoundPlan(number=number, parent=parent, voice=voice, dataset=dataset, minutes=minutes, resume_from=source, run_dir=paths.run,
                     cache_dir="%s/%s-r%03d" % (scratch.caches, dataset, number), config_path="%s/round-%03d.json" % (paths.round_configs, number),
                     dataset_dir="%s/%s" % (scratch.datasets, dataset), versions_before=version_dirs(paths))


def command_for(training: EnvPaths, plan: RoundPlan, *, batch_size: int = BATCH_SIZE, workers: int = NUM_WORKERS, check_every: int = CHECK_VAL_EVERY_N_EPOCH) -> Command:
    """The trainer's command for a plan, with every rule in `train_command` applied (the training set is whole, the working folder is new, the saved point is a file)."""
    return train_command(training, plan.dataset_dir, plan.run_dir, plan.cache_dir, plan.config_path, plan.resume_from, minutes=plan.minutes, batch_size=batch_size,
                         workers=workers, check_every=check_every)


def prepare_folders(paths: ProjectPaths, plan: RoundPlan) -> None:
    """The folders the job runs in. The working folder itself is the trainer's to make (it must not exist yet)."""
    for folder in (plan.run_dir, paths.round_configs, os.path.dirname(plan.cache_dir)):
        os.makedirs(folder, mode=0o700, exist_ok=True)


# ---------------------------------------------------------------- beginning, ending and choosing

def begin(paths: ProjectPaths, plan: RoundPlan, now: Optional[datetime] = None) -> Record:
    """Write the round down as `starting` *before* the job is started, so a crash in between is found later instead of being a job nobody knows about."""
    def change(record: Record) -> Record:
        running = active(record)
        if running is not None:
            raise RoundsError("round_running", str(running.number))
        if plan.number != next_number(record) or plan.parent != record.current:
            raise RoundsError("busy", "changed since planned")                      # another window began or finished a round after this was planned
        made = Round(plan.number, plan.parent, plan.voice, plan.dataset, plan.minutes, "starting", jobs.utc_stamp(now), versions_before=plan.versions_before)
        return replace(record, rounds=record.rounds + (made,))
    return modify(paths, change)


def attach_job(paths: ProjectPaths, number: int, job_id: str) -> Record:
    """`starting` becomes `running`. Anything else is left as it is (a window that looked in between may already have moved it on)."""
    _check_name(job_id, "job")

    def change(record: Record) -> Record:
        r = find(record, number)
        if r is None or r.state != "starting":
            return record
        return _replace_round(record, replace(r, state="running", job=job_id))
    return modify(paths, change)


def rollback_start(paths: ProjectPaths, number: int) -> Record:
    """The job did not start, so the round never was: take its line out again. This is the only line the tool ever removes, and only while it is `starting` with no job."""
    def change(record: Record) -> Record:
        r = find(record, number)
        if r is None or r.state != "starting" or r.job:
            return record
        return replace(record, rounds=tuple(o for o in record.rounds if o.number != number))
    return modify(paths, change)


def _replace_round(record: Record, new: Round) -> Record:
    return replace(record, rounds=tuple(new if r.number == new.number else r for r in record.rounds))


def choose(paths: ProjectPaths, number: int) -> Record:
    """Make this round the chosen one. Only a round that ended with a whole saved point, whose file is still there and whole, and never while a round runs."""
    def change(record: Record) -> Record:
        running = active(record)
        if running is not None:
            raise RoundsError("round_running", str(running.number))
        r = find(record, number)
        if r is None:
            raise RoundsError("unknown_round", str(number))
        if not r.has_checkpoint:
            raise RoundsError("not_usable", str(number))
        status = checkpoint_status(paths, r)
        if status != "ok":
            raise RoundsError("checkpoint_damaged" if status == "damaged" else "checkpoint_missing", str(number))
        return replace(record, current=number)
    return modify(paths, change)


def go_back_target(paths: ProjectPaths, record: Record) -> Optional[int]:
    """The round *go back* would choose: the one the chosen round resumed from, if that is a round of this person's whose saved point is still there and whole."""
    pick = chosen(record)
    if pick is None or pick.parent == 0:
        return None
    before = find(record, pick.parent)
    return before.number if before is not None and before.has_checkpoint and checkpoint_status(paths, before) == "ok" else None


def go_back(paths: ProjectPaths) -> Record:
    """Choose the round before the chosen one. The round that was left stays as it is, and its files are not touched."""
    def change(record: Record) -> Record:
        running = active(record)
        if running is not None:
            raise RoundsError("round_running", str(running.number))
        target = go_back_target(paths, record)
        if target is None:
            raise RoundsError("nowhere_back")
        return replace(record, current=target)
    return modify(paths, change)


def set_note(paths: ProjectPaths, number: int, text: str) -> Record:
    """The helper's words about a round. Tidied like any typed text; empty removes the note."""
    if not isinstance(text, str):
        raise RoundsError("bad_value", "note")

    def change(record: Record) -> Record:
        r = find(record, number)
        if r is None:
            raise RoundsError("unknown_round", str(number))
        return _replace_round(record, replace(r, note=clean_text(text, MAX_NOTE)))
    return modify(paths, change)


# ---------------------------------------------------------------- noticing how a round ended

def _job_for(r: Round, scratch: ScratchPaths, jobs_root: str, project_id: str, listed: Callable[[], Tuple[jobs.JobInfo, ...]]) -> Optional[jobs.JobInfo]:
    """The job of a round: the one its record names, or, when the program ended between writing the round down and writing the job's name, the one whose command names this
    round's working folder (every round has its own)."""
    if r.job:
        try:
            return jobs.job_info(jobs_root.rstrip("/") + "/" + r.job)
        except jobs.JobError:
            pass
    cache = "%s/%s-r%03d" % (scratch.caches, r.dataset, r.number)
    for info in listed():
        argv = info.spec.argv
        if info.spec.kind == "train" and info.spec.project == project_id and "--data.cache_dir" in argv:
            at = argv.index("--data.cache_dir")
            if at + 1 < len(argv) and argv[at + 1] == cache:
                return info
    return None


def _ended(r: Round, record: Record, paths: ProjectPaths, state: str, failure: str, exit_code: Optional[int], ended: str) -> Tuple[Round, bool]:
    """The round as it ended: its folder found, its saved point checked. A round that finished without writing one did not finish. Returns (round, chosen-by-itself)."""
    version = r.version if r.version is not None else _new_version(paths, record, r)
    probe = replace(r, version=version)
    path = checkpoint_file(paths, probe)
    whole = path is not None and os.path.isfile(path) and checkpoint_complete(path)
    if state == "finished" and not whole:
        state, failure = "failed", "no_checkpoint"
    keeps = whole and state in RESUMABLE_STATES
    return replace(r, state=state, failure=failure, exit_code=exit_code, ended=ended, version=version, has_checkpoint=keeps), keeps


def reconcile(paths: ProjectPaths, scratch: ScratchPaths, jobs_root: str, project_id: str, *, now: Optional[datetime] = None, write: bool = True) -> Record:
    """Bring the record up to date with what the jobs and the disk say. Safe to run at any time, from any window, as often as wanted; a round that has ended stays as it ended.
    With `write=False` the answer is worked out and returned and nothing is written, for a command that only looks."""
    moment = now or datetime.now(timezone.utc)
    cache: List[Tuple[jobs.JobInfo, ...]] = []

    def listed() -> Tuple[jobs.JobInfo, ...]:
        if not cache:
            cache.append(jobs.list_jobs(jobs_root).jobs)
        return cache[0]

    def change(record: Record) -> Record:
        for r in [r for r in record.rounds if r.state in ACTIVE_STATES]:
            info = _job_for(r, scratch, jobs_root, project_id, listed)
            if info is None:
                began = _parse_stamp(r.started)
                if r.state == "starting" and began is not None and (moment - began).total_seconds() < STARTING_GRACE_S:
                    continue                                                   # the window that began it may be about to start the job
                failure = "never_started" if r.state == "starting" else "job_missing"
                new, keeps = _ended(r, record, paths, "never_started" if r.state == "starting" else "interrupted", failure, None, jobs.utc_stamp(moment))
            elif info.status in jobs.ACTIVE:
                version = r.version if r.version is not None else _new_version(paths, record, r)
                new, keeps = replace(r, state="running", job=info.id, version=version), False
            else:
                result = jobs.read_json(info.dir + "/result.json") or {}
                stamp = result.get("ended_at")
                ended = stamp if isinstance(stamp, str) and 0 < len(stamp) <= 40 and _parse_stamp(stamp) is not None else jobs.utc_stamp(moment)
                state, failure = {jobs.JobStatus.FINISHED: ("finished", ""), jobs.JobStatus.STOPPED: ("stopped", ""), jobs.JobStatus.INTERRUPTED: ("interrupted", ""),
                                  jobs.JobStatus.NEVER_STARTED: ("never_started", "never_started")}.get(info.status, ("failed", ""))
                if info.status is jobs.JobStatus.FAILED:
                    failure = "signal" if info.signal else "exit"
                elif info.status is jobs.JobStatus.NEVER_STARTED and info.error:
                    failure = "program"                                          # the program could not be run at all (not found, not allowed)
                new, keeps = _ended(replace(r, job=info.id), record, paths, state, failure, info.exit_code, ended)
            record = _replace_round(record, new)
            if keeps:
                record = replace(record, current=new.number)
        return record
    if not write:
        return change(load(paths))
    return modify(paths, change)


def noticed(before: Record, after: Record) -> Tuple[Round, ...]:
    """The rounds that are new or changed their state between two records: what `reconcile` found out, for a screen to say."""
    old = {r.number: r.state for r in before.rounds}
    return tuple(r for r in after.rounds if old.get(r.number) != r.state)


# ---------------------------------------------------------------- starting a round

@dataclass(frozen=True)
class Started:
    number: int
    job: str


def start_round(paths: ProjectPaths, scratch: ScratchPaths, project_id: str, training: EnvPaths, jobs_root: str, *, dataset: str, minutes: int = ROUND_MINUTES,
                base: Optional[Base] = None, now: Optional[datetime] = None, start: Callable[[str, jobs.JobSpec], jobs.JobInfo] = jobs.start_job,
                batch_size: int = BATCH_SIZE, workers: int = NUM_WORKERS, check_every: int = CHECK_VAL_EVERY_N_EPOCH) -> Started:
    """Bring the record up to date, plan the next round, check the command, write the round down, start the job, and write the job's name. Every step that can refuse
    does so before anything is written; if the job does not start, the line written for it is taken out again and the reason is raised."""
    record = reconcile(paths, scratch, jobs_root, project_id, now=now)
    plan = plan_round(paths, scratch, record, dataset=dataset, minutes=minutes, base=base)
    command = command_for(training, plan, batch_size=batch_size, workers=workers, check_every=check_every)
    prepare_folders(paths, plan)
    begin(paths, plan, now)
    try:
        info = start(jobs_root, command.job(project_id))
    except Exception:
        try:
            rollback_start(paths, plan.number)
        except RoundsError:
            pass                                          # the reason the job did not start matters more; reconcile finds a line left behind
        raise
    attach_job(paths, plan.number, info.id)
    return Started(plan.number, info.id)


# ---------------------------------------------------------------- what may be freed (plan P11)

@dataclass(frozen=True)
class CheckpointFile:
    version: int
    name: str
    path: str
    size: int


def scan_checkpoint_files(paths: ProjectPaths) -> Tuple[CheckpointFile, ...]:
    """Every regular `*.ckpt` file in a `version_N/checkpoints` folder of the run folder. Links are not listed, so they can never be offered."""
    found: List[CheckpointFile] = []
    for version in version_dirs(paths):
        folder = "%s/lightning_logs/version_%d/checkpoints" % (paths.run, version)
        try:
            with os.scandir(folder) as entries:
                for entry in entries:
                    if entry.name.endswith(".ckpt") and entry.is_file(follow_symlinks=False):
                        found.append(CheckpointFile(version, entry.name, entry.path, entry.stat(follow_symlinks=False).st_size))
        except OSError:
            continue
    return tuple(sorted(found, key=lambda f: (f.version, f.name)))


@dataclass(frozen=True)
class Retention:
    keep: Tuple[Tuple[int, CheckpointFile], ...]          # (round, file): the chosen round's `last.ckpt` and its parent's: never offered
    spare: Tuple[Tuple[int, CheckpointFile], ...]         # every other file of a round that has ended: offered by Free up space, after one confirmation
    busy: Tuple[Tuple[int, CheckpointFile], ...]          # files of the round that is running now: never offered
    unclaimed: Tuple[CheckpointFile, ...]                 # in a folder no round claims (not made by this tool, or made before the record): left alone, never offered


def kept_rounds(record: Record) -> Tuple[int, ...]:
    """The chosen round and the round it resumed from (going back needs that one)."""
    pick = chosen(record)
    if pick is None:
        return ()
    return (pick.number,) + ((pick.parent,) if pick.parent else ())


def classify(record: Record, files: Tuple[CheckpointFile, ...]) -> Retention:
    owner = {r.version: r for r in record.rounds if r.version is not None}
    running = active(record)
    protected = kept_rounds(record)
    keep, spare, busy, unclaimed = [], [], [], []
    for f in files:
        r = owner.get(f.version)
        if r is None and running is not None and running.version is None and f.version not in running.versions_before:
            r = running                                       # the folder the running round has just made, before anything has noticed it
        if r is None:
            unclaimed.append(f)
        elif r.state in ACTIVE_STATES:
            busy.append((r.number, f))
        elif r.number in protected and f.name == LAST:
            keep.append((r.number, f))
        else:
            spare.append((r.number, f))
    return Retention(tuple(keep), tuple(spare), tuple(busy), tuple(unclaimed))


def retention(paths: ProjectPaths, record: Record) -> Retention:
    return classify(record, scan_checkpoint_files(paths))


def cleanup_items(r: Retention) -> Tuple[CleanupItem, ...]:
    """The same files as the disk budget's list (core/diskbudget.py): kept ones are precious and protected, spare ones disposable. Nothing else is in it."""
    items = [CleanupItem("checkpoint.round%d.%s" % (n, f.name), Kind.PRECIOUS, f.size, protected=True) for n, f in r.keep]
    items += [CleanupItem("checkpoint.round%d.%s" % (n, f.name), Kind.DISPOSABLE, f.size) for n, f in r.spare]
    return tuple(items)
