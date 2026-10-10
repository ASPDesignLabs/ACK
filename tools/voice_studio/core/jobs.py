# SPDX-License-Identifier: GPL-3.0-or-later
"""Long jobs that outlive the window: training, dataset building, speech recognition (plan decision D12: "training keeps running if the window closes").

A job is a folder under `state/jobs/<job id>/` holding plain files, so its state can be read by any later run of the window, or after a restart:

    job.json     what was asked (written first)            runner.json  the runner's and the command's process ids and start times
    log.txt      everything the command printed             result.json  how it ended (written by the runner, last)
    stop.json    a request to stop, if one was made

`start_job` starts a small detached *runner* (core/jobrunner.py) that runs the command in its own process group and writes the result. The window
never holds the process, so closing it changes nothing. Stopping is a file, not a signal: the runner forwards one Ctrl+C-equivalent to the
command (the guide's "Ctrl+C once, then wait") and only an explicit force stop sends anything harder. Only one job that uses the GPU runs at a
time (the 8 GB rule). A job never gets the network: Hugging Face's libraries are switched to offline mode for it, and network programs are refused.
"""
from __future__ import annotations

import json
import os
import re
import secrets
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Callable, Dict, List, Mapping, Optional, Tuple

from .system import is_network_command

SCHEMA = 1
KIND = re.compile(r"^[a-z0-9][a-z0-9-]{0,19}$")
START_GRACE_S = 15.0
OFFLINE_ENV = {"HF_HUB_OFFLINE": "1", "HF_HUB_DISABLE_TELEMETRY": "1", "DO_NOT_TRACK": "1", "TRANSFORMERS_OFFLINE": "1"}
TOOLS_DIR = Path(__file__).resolve().parents[2]            # the folder that holds the voice_studio package


class JobError(Exception):
    """`code` is a short word the screens turn into a plain sentence: bad_spec, network_program, gpu_busy, launch_failed, no_start, not_found."""

    def __init__(self, code: str, detail: str = ""):
        super().__init__(code + (": " + detail if detail else ""))
        self.code = code
        self.detail = detail


class JobStatus(Enum):
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"            # a stop was asked for and the command is still finishing (writing its last checkpoint, say)
    FINISHED = "finished"            # ended by itself, exit status 0
    FAILED = "failed"                # ended by itself with a failure
    STOPPED = "stopped"              # ended after a stop was asked for
    INTERRUPTED = "interrupted"      # the runner is gone and left no result: the computer restarted, or the runner was killed
    NEVER_STARTED = "never_started"  # the runner never came up


ACTIVE = (JobStatus.STARTING, JobStatus.RUNNING, JobStatus.STOPPING)


@dataclass(frozen=True)
class JobSpec:
    kind: str                                    # "train", "dataset", "asr"...
    project: str                                 # project id, or "" for a job of the tool itself
    argv: Tuple[str, ...]
    cwd: Optional[str] = None
    env: Mapping[str, str] = field(default_factory=dict)
    gpu: bool = False
    force_grace_s: float = 10.0                  # how long a forced stop waits between "terminate" and "kill"


@dataclass(frozen=True)
class JobInfo:
    id: str
    dir: str
    spec: JobSpec
    started_at: str
    status: JobStatus
    exit_code: Optional[int] = None
    signal: Optional[int] = None
    error: str = ""
    runner_pid: Optional[int] = None


# ---------------------------------------------------------------- files

def write_json(path: str, data: object) -> None:
    """Atomic and owner-only: a reader sees the old file or the new one, never half of one."""
    fd, temp = tempfile.mkstemp(dir=os.path.dirname(path), prefix=".job-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle)
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


def read_json(path: str) -> Optional[dict]:
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


def utc_stamp(now: Optional[datetime] = None) -> str:
    return (now or datetime.now(timezone.utc)).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------- is a process still the one we started?

def parse_proc_stat(stat_text: Optional[str]) -> Optional[Tuple[str, int]]:
    """(state, start time) from /proc/<pid>/stat: field 3 and field 22 (clock ticks since boot). The program name (field 2) may hold spaces and
    brackets, so everything is read after the last ')'."""
    if not stat_text or ")" not in stat_text:
        return None
    rest = stat_text[stat_text.rindex(")") + 1:].split()
    try:
        return rest[0], int(rest[19])
    except (IndexError, ValueError):
        return None


def parse_proc_starttime(stat_text: Optional[str]) -> Optional[int]:
    parsed = parse_proc_stat(stat_text)
    return parsed[1] if parsed else None


def read_text_file(path: str) -> Optional[str]:
    try:
        with open(path, encoding="utf-8", errors="replace") as handle:
            return handle.read()
    except OSError:
        return None


def boot_id(read: Callable[[str], Optional[str]] = read_text_file) -> str:
    return (read("/proc/sys/kernel/random/boot_id") or "").strip()


def process_alive(pid: Optional[int], starttime: Optional[int], boot: str, read: Callable[[str], Optional[str]] = read_text_file) -> bool:
    """True only if `pid` exists, started at `starttime`, in this boot. A reused pid, or one from before a restart, is not the runner."""
    if not pid or starttime is None or boot_id(read) != boot or not boot:
        return False
    parsed = parse_proc_stat(read("/proc/%d/stat" % pid))
    return parsed is not None and parsed[1] == starttime and parsed[0] not in ("Z", "X")       # a zombie or a dead process is not running


# ---------------------------------------------------------------- the status of a job (pure)

def compute_status(runner: Optional[dict], result: Optional[dict], stop_asked: bool, alive: bool, age_s: float) -> JobStatus:
    if result is not None:
        if result.get("error"):
            return JobStatus.NEVER_STARTED
        if stop_asked:
            return JobStatus.STOPPED
        return JobStatus.FINISHED if result.get("exit_code") == 0 else JobStatus.FAILED
    if runner is None:
        return JobStatus.STARTING if age_s < START_GRACE_S else JobStatus.NEVER_STARTED
    if alive:
        return JobStatus.STOPPING if stop_asked else JobStatus.RUNNING
    return JobStatus.INTERRUPTED


def _spec_from(raw: dict) -> JobSpec:
    return JobSpec(kind=str(raw["kind"]), project=str(raw.get("project", "")), argv=tuple(str(a) for a in raw["argv"]), cwd=raw.get("cwd"),
                   env={str(k): str(v) for k, v in (raw.get("env") or {}).items()}, gpu=bool(raw.get("gpu", False)),
                   force_grace_s=float(raw.get("force_grace_s", 10.0)))


def job_info(job_dir: str, read: Callable[[str], Optional[str]] = read_text_file, now: Optional[float] = None) -> JobInfo:
    raw = read_json(job_dir + "/job.json")
    if raw is None or raw.get("schema") != SCHEMA:
        raise JobError("not_found", os.path.basename(job_dir))
    try:
        spec = _spec_from(raw)
    except (KeyError, TypeError, ValueError):
        raise JobError("not_found", os.path.basename(job_dir))
    runner, result = read_json(job_dir + "/runner.json"), read_json(job_dir + "/result.json")
    stop_asked = os.path.exists(job_dir + "/stop.json")
    alive = bool(runner) and process_alive(runner.get("pid"), runner.get("starttime"), str(runner.get("boot_id", "")), read)
    age = max(0.0, (now if now is not None else time.time()) - float(raw.get("created_epoch", 0)))
    status = compute_status(runner, result, stop_asked, alive, age)
    exit_code = result.get("exit_code") if result else None
    return JobInfo(os.path.basename(job_dir), job_dir, spec, str(raw.get("started_at", "")), status,
                   exit_code if isinstance(exit_code, int) else None, (result or {}).get("signal"), str((result or {}).get("error", "")),
                   runner.get("pid") if runner else None)


@dataclass(frozen=True)
class JobList:
    jobs: Tuple[JobInfo, ...]
    problems: Tuple[str, ...]


def list_jobs(jobs_root: str) -> JobList:
    found: List[JobInfo] = []
    problems: List[str] = []
    try:
        names = sorted(os.listdir(jobs_root))
    except OSError:
        return JobList((), ())
    for name in names:
        if not os.path.isdir(jobs_root + "/" + name):
            continue
        try:
            found.append(job_info(jobs_root + "/" + name))
        except JobError:
            problems.append(name)
    return JobList(tuple(sorted(found, key=lambda j: (j.started_at, j.id))), tuple(problems))


def gpu_busy(jobs_root: str) -> Optional[JobInfo]:
    """The job holding the GPU, if one is running (or starting, or still stopping). 8 GB is not enough for two."""
    return next((j for j in list_jobs(jobs_root).jobs if j.spec.gpu and j.status in ACTIVE), None)


# ---------------------------------------------------------------- starting, stopping, reading

def _check_spec(spec: JobSpec) -> None:
    if not KIND.match(spec.kind) or not spec.argv or any((not isinstance(a, str)) or "\x00" in a for a in spec.argv) or not spec.argv[0]:
        raise JobError("bad_spec")
    if spec.project and not re.match(r"^[a-z0-9][a-z0-9-]{0,63}$", spec.project):
        raise JobError("bad_spec", "project")
    if spec.cwd is not None and not os.path.isdir(spec.cwd):
        raise JobError("bad_spec", "cwd")
    if is_network_command(spec.argv):
        raise JobError("network_program", os.path.basename(spec.argv[0]))
    if not (0 <= spec.force_grace_s <= 600):
        raise JobError("bad_spec", "force_grace_s")


def start_job(jobs_root: str, spec: JobSpec, now: Optional[datetime] = None, wait_s: float = 15.0, python: Optional[str] = None) -> JobInfo:
    """Start `spec` detached and return once the runner is up. Refuses a second GPU job, a network program and a malformed spec."""
    _check_spec(spec)
    os.makedirs(jobs_root, mode=0o700, exist_ok=True)
    busy = gpu_busy(jobs_root) if spec.gpu else None
    if busy is not None:
        raise JobError("gpu_busy", busy.id)
    stamp = (now or datetime.now(timezone.utc))
    job_id = "%s-%s-%s" % (stamp.astimezone(timezone.utc).strftime("%Y%m%d-%H%M%S"), spec.kind, secrets.token_hex(2))
    job_dir = jobs_root.rstrip("/") + "/" + job_id
    os.mkdir(job_dir, 0o700)
    env = dict(OFFLINE_ENV)
    env.update(spec.env)
    write_json(job_dir + "/job.json", {"schema": SCHEMA, "kind": spec.kind, "project": spec.project, "argv": list(spec.argv), "cwd": spec.cwd, "env": env,
                                       "gpu": spec.gpu, "force_grace_s": spec.force_grace_s, "started_at": utc_stamp(stamp), "created_epoch": time.time()})
    launcher_env = dict(os.environ, PYTHONPATH=os.pathsep.join([str(TOOLS_DIR)] + ([os.environ["PYTHONPATH"]] if os.environ.get("PYTHONPATH") else [])))
    try:
        with subprocess.Popen([python or sys.executable, "-m", "voice_studio.core.jobrunner", job_dir], cwd=str(TOOLS_DIR), env=launcher_env,
                              stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, close_fds=True) as launcher:
            code = launcher.wait(timeout=wait_s)           # the launcher hands over to the runner at once and exits
    except (OSError, subprocess.SubprocessError) as exc:
        raise JobError("launch_failed", type(exc).__name__)
    if code != 0:
        raise JobError("launch_failed", "exit %d" % code)
    deadline = time.time() + wait_s
    while time.time() < deadline:
        if os.path.exists(job_dir + "/runner.json") or os.path.exists(job_dir + "/result.json"):
            return job_info(job_dir)
        time.sleep(0.02)
    raise JobError("no_start", job_id)


def request_stop(job_dir: str) -> str:
    """Ask the command to stop the way Ctrl+C does, once. Returns "asked", "already" (a request is already there) or "not_running"."""
    info = job_info(job_dir)
    if info.status not in ACTIVE:
        return "not_running"
    if os.path.exists(job_dir + "/stop.json"):
        return "already"
    write_json(job_dir + "/stop.json", {"forced": False, "at": utc_stamp()})
    return "asked"


def force_stop(job_dir: str) -> str:
    """The harder stop, for after the person has been told it can lose the last minutes of training: terminate, then kill after the grace time."""
    info = job_info(job_dir)
    if info.status not in ACTIVE:
        return "not_running"
    existing = read_json(job_dir + "/stop.json")
    if existing and existing.get("forced"):
        return "already"
    write_json(job_dir + "/stop.json", {"forced": True, "at": utc_stamp()})
    return "asked"


def tail_log(job_dir: str, max_lines: int = 40, max_bytes: int = 65536) -> List[str]:
    """The last lines of the log, reading at most `max_bytes` from the end. Progress bars redraw with carriage returns, so those count as line breaks."""
    try:
        with open(job_dir + "/log.txt", "rb") as handle:
            handle.seek(0, os.SEEK_END)
            size = handle.tell()
            handle.seek(max(0, size - max_bytes))
            data = handle.read()
    except OSError:
        return []
    text = data.decode("utf-8", errors="replace").replace("\r\n", "\n").replace("\r", "\n")
    lines = [ln for ln in text.split("\n") if ln.strip()]
    if size > max_bytes and lines:
        lines = lines[1:]                             # the first line may be cut in half
    return lines[-max_lines:]
