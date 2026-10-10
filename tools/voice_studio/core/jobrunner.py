# SPDX-License-Identifier: GPL-3.0-or-later
"""The runner: run as `python -m voice_studio.core.jobrunner <job folder>` by core/jobs.py, and then on its own.

It forks and the first process returns at once (so whoever started it is not left holding a child), becomes a session of its own, runs the
command in a process group of its own with the output going to the log, watches for a stop request file, and writes `result.json` last.
It imports only the standard library and core/jobs.py, and it never opens a network connection.
"""
from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from typing import Optional

from . import jobs

POLL_S = 0.1


def _signal_group(pid: int, sig: int) -> None:
    try:
        os.killpg(pid, sig)
    except (ProcessLookupError, PermissionError):
        pass


def _starttime(pid: int) -> Optional[int]:
    return jobs.parse_proc_starttime(jobs.read_text_file("/proc/%d/stat" % pid))


def run(job_dir: str) -> int:
    raw = jobs.read_json(job_dir + "/job.json")
    if raw is None:
        return 2
    spec = jobs._spec_from(raw)
    env = dict(os.environ)
    env.update(spec.env)
    log = os.open(job_dir + "/log.txt", os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    result = {"exit_code": None, "signal": None, "ended_at": "", "stop_requested": False, "forced": False, "error": ""}
    child: Optional[subprocess.Popen] = None
    try:
        try:
            child = subprocess.Popen(list(spec.argv), cwd=spec.cwd, env=env, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        except FileNotFoundError:
            result["error"] = "program_not_found"
        except PermissionError:
            result["error"] = "not_executable"
        except OSError:
            result["error"] = "start_failed"
        if child is not None:
            jobs.write_json(job_dir + "/runner.json", {"pid": os.getpid(), "starttime": _starttime(os.getpid()), "boot_id": jobs.boot_id(),
                                                       "child_pid": child.pid, "child_starttime": _starttime(child.pid)})
            sent_int = sent_term = sent_kill = False
            term_at = 0.0

            def on_shutdown(signum, frame):                     # the computer is shutting down or the runner was asked to end: stop the command gently
                nonlocal sent_int
                if not sent_int:
                    sent_int = True
                    result["stop_requested"] = True
                    _signal_group(child.pid, signal.SIGINT)
            signal.signal(signal.SIGTERM, on_shutdown)
            signal.signal(signal.SIGHUP, on_shutdown)
            while child.poll() is None:
                stop = jobs.read_json(job_dir + "/stop.json")
                if stop is not None:
                    result["stop_requested"] = True
                    if not sent_int:
                        sent_int = True
                        _signal_group(child.pid, signal.SIGINT)          # once, like one Ctrl+C
                    if stop.get("forced"):
                        result["forced"] = True
                        if not sent_term:
                            sent_term, term_at = True, time.time()
                            _signal_group(child.pid, signal.SIGTERM)
                        elif not sent_kill and time.time() - term_at >= spec.force_grace_s:
                            sent_kill = True
                            _signal_group(child.pid, signal.SIGKILL)
                time.sleep(POLL_S)
            code = child.returncode
            result["exit_code"] = code if code >= 0 else None
            result["signal"] = -code if code < 0 else None
            if code != 0:
                _signal_group(child.pid, signal.SIGKILL)         # whatever the command started is not left behind after it failed or was killed
    finally:
        os.close(log)
        result["ended_at"] = jobs.utc_stamp()
        jobs.write_json(job_dir + "/result.json", result)
    return 0


def main(argv: list) -> int:
    if len(argv) != 2:
        return 2
    job_dir = argv[1]
    if os.fork():                      # the launcher's side: return at once
        os._exit(0)
    os.setsid()                        # on its own, not tied to the window or its terminal
    for fd, flags in ((0, os.O_RDONLY), (1, os.O_WRONLY), (2, os.O_WRONLY)):
        null = os.open(os.devnull, flags)
        os.dup2(null, fd)
        os.close(null)
    try:
        return run(job_dir)
    except BaseException:
        return 1


if __name__ == "__main__":
    os._exit(main(sys.argv))
