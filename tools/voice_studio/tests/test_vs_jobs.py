# SPDX-License-Identifier: GPL-3.0-or-later
"""The job supervisor (plan task VS-1.6): jobs that outlive the window, stop once and gently, and cannot take the GPU twice or the network at all.

Most of these start real (short) processes through the real detached runner. A fixture force-stops anything still running at the end of each test.
"""
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

from voice_studio.core import jobs as jb
from voice_studio.core.jobs import JobError, JobSpec, JobStatus

PY = sys.executable


def py(code, *args):
    return (PY, "-u", "-c", code) + tuple(args)


def wait_until(condition, timeout=20.0, what="condition"):
    deadline = time.time() + timeout
    while time.time() < deadline:
        value = condition()
        if value:
            return value
        time.sleep(0.03)
    raise AssertionError("timed out waiting for " + what)


def is_running(pid):
    try:
        with open("/proc/%d/stat" % pid) as handle:
            return handle.read().rsplit(")", 1)[1].split()[0] not in ("Z", "X")
    except OSError:
        return False


@pytest.fixture()
def root(tmp_path):
    jobs_root = str(tmp_path / "jobs")
    yield jobs_root
    for info in jb.list_jobs(jobs_root).jobs:
        if info.status in jb.ACTIVE:
            jb.force_stop(info.dir)
    wait_until(lambda: not [j for j in jb.list_jobs(jobs_root).jobs if j.status in jb.ACTIVE], 30, "every job to end")


def finish(info):
    return wait_until(lambda: (lambda i: i if i.status not in jb.ACTIVE else None)(jb.job_info(info.dir)), 30, "the job to end")


SLEEPER = "import time; time.sleep(60)"


# ---------------------------------------------------------------- is this process still the one we started?

STAT = "1234 (python3) S 1 1234 1234 0 -1 4194304 100 0 0 0 1 2 0 0 20 0 1 0 %d 1000000 500 18446744073709551615 0 0 0 0 0 0 0 0 0 0 0 0 17 0 0 0 0 0 0\n"


def test_the_state_and_start_time_are_read_even_when_the_program_name_is_odd():
    assert jb.parse_proc_stat(STAT % 987654) == ("S", 987654)
    odd = "77 (a b) c) R 1 1 1 0 -1 0 0 0 0 0 0 0 0 0 20 0 1 0 555 0 0 0 0 0 0 0 0 0 0 0 0 0 17 0 0 0 0 0 0\n"
    assert jb.parse_proc_stat(odd) == ("R", 555)
    for bad in (None, "", "no brackets", "1 (x) S 1 2", "1 (x) S " + "a " * 30):
        assert jb.parse_proc_stat(bad) is None
    assert jb.parse_proc_starttime(STAT % 42) == 42 and jb.parse_proc_starttime(None) is None


def fake_proc(files):
    return lambda path: files.get(path)


def test_a_process_is_only_the_runner_if_pid_start_time_and_boot_all_agree():
    files = {"/proc/sys/kernel/random/boot_id": "boot-a\n", "/proc/1234/stat": STAT % 500}
    read = fake_proc(files)
    assert jb.process_alive(1234, 500, "boot-a", read)
    assert not jb.process_alive(1234, 501, "boot-a", read)           # the pid was reused by another program
    assert not jb.process_alive(1234, 500, "boot-b", read)           # from before a restart
    assert not jb.process_alive(1234, 500, "", fake_proc({"/proc/1234/stat": STAT % 500}))
    assert not jb.process_alive(9999, 500, "boot-a", read) and not jb.process_alive(None, 500, "boot-a", read) and not jb.process_alive(1234, None, "boot-a", read)
    zombie = dict(files, **{"/proc/1234/stat": (STAT % 500).replace(") S ", ") Z ")})
    assert not jb.process_alive(1234, 500, "boot-a", fake_proc(zombie))


@pytest.mark.parametrize("runner, result, stop, alive, age, expected", [
    (None, None, False, False, 1.0, JobStatus.STARTING),
    (None, None, False, False, jb.START_GRACE_S - 0.1, JobStatus.STARTING),
    (None, None, False, False, jb.START_GRACE_S, JobStatus.NEVER_STARTED),
    ({"pid": 1}, None, False, True, 5, JobStatus.RUNNING),
    ({"pid": 1}, None, True, True, 5, JobStatus.STOPPING),
    ({"pid": 1}, None, False, False, 5, JobStatus.INTERRUPTED),
    ({"pid": 1}, None, True, False, 5, JobStatus.INTERRUPTED),
    ({"pid": 1}, {"exit_code": 0}, False, False, 5, JobStatus.FINISHED),
    ({"pid": 1}, {"exit_code": 3}, False, False, 5, JobStatus.FAILED),
    ({"pid": 1}, {"exit_code": None, "signal": 9}, False, False, 5, JobStatus.FAILED),
    ({"pid": 1}, {"exit_code": 0}, True, False, 5, JobStatus.STOPPED),
    ({"pid": 1}, {"exit_code": 130}, True, False, 5, JobStatus.STOPPED),
    (None, {"exit_code": None, "error": "program_not_found"}, False, False, 5, JobStatus.NEVER_STARTED),
])
def test_every_combination_of_files_and_liveness_has_one_status(runner, result, stop, alive, age, expected):
    assert jb.compute_status(runner, result, stop, alive, age) is expected


def test_job_info_reads_a_folder_made_by_hand(tmp_path):
    d = tmp_path / "20261010-000000-train-ab12"
    d.mkdir()
    jb.write_json(str(d / "job.json"), {"schema": 1, "kind": "train", "project": "anna", "argv": ["x", "y"], "env": {"A": "1"}, "gpu": True,
                                        "started_at": "2026-10-10T00:00:00Z", "created_epoch": time.time() - 100})
    info = jb.job_info(str(d), fake_proc({}))
    assert info.status is JobStatus.NEVER_STARTED and info.spec.argv == ("x", "y") and info.spec.gpu and info.spec.env == {"A": "1"} and info.id == d.name
    jb.write_json(str(d / "runner.json"), {"pid": 1234, "starttime": 500, "boot_id": "boot-a"})
    files = {"/proc/sys/kernel/random/boot_id": "boot-a\n", "/proc/1234/stat": STAT % 500}
    assert jb.job_info(str(d), fake_proc(files)).status is JobStatus.RUNNING
    assert jb.job_info(str(d), fake_proc({})).status is JobStatus.INTERRUPTED
    jb.write_json(str(d / "result.json"), {"exit_code": 0})
    assert jb.job_info(str(d), fake_proc(files)).status is JobStatus.FINISHED and jb.job_info(str(d)).exit_code == 0


@pytest.mark.parametrize("content", [None, "not json", "[]", '{"schema": 9}', '{"schema": 1}', '{"schema": 1, "kind": "x", "argv": 5}'])
def test_a_job_folder_that_cannot_be_read_is_not_found_and_not_a_crash(tmp_path, content):
    d = tmp_path / "j"
    d.mkdir()
    if content is not None:
        (d / "job.json").write_text(content)
    with pytest.raises(JobError) as caught:
        jb.job_info(str(d))
    assert caught.value.code == "not_found"


# ---------------------------------------------------------------- real jobs

def test_a_job_runs_on_its_own_and_its_output_ends_up_in_the_log(root, tmp_path):
    info = jb.start_job(root, JobSpec("dataset", "anna", py("import os; print('hello'); print(os.getcwd()); print(os.environ['HF_HUB_OFFLINE'], os.environ.get('MINE'))"),
                                      cwd=str(tmp_path), env={"MINE": "yes"}))
    assert info.id.endswith("-dataset-" + info.id.split("-")[-1]) and info.runner_pid and info.runner_pid != os.getpid()
    done = finish(info)
    assert done.status is JobStatus.FINISHED and done.exit_code == 0 and done.spec.project == "anna"
    assert jb.tail_log(done.dir) == ["hello", str(tmp_path), "1 yes"]


def test_the_runner_is_a_session_of_its_own_so_closing_the_window_cannot_end_it(root):
    info = jb.start_job(root, JobSpec("asr", "", py(SLEEPER)))
    assert info.status is JobStatus.RUNNING and os.getsid(info.runner_pid) == info.runner_pid != os.getsid(0)
    assert os.getppid() != info.runner_pid and jb.read_json(info.dir + "/runner.json")["child_pid"] > 0
    jb.force_stop(info.dir)
    finish(info)


def test_job_files_are_owner_only(root):
    info = finish(jb.start_job(root, JobSpec("dataset", "", py("print(1)"))))
    assert oct(os.stat(root).st_mode & 0o777) == "0o700" and oct(os.stat(info.dir).st_mode & 0o777) == "0o700"
    for name in ("job.json", "runner.json", "result.json", "log.txt"):
        assert oct(os.stat(info.dir + "/" + name).st_mode & 0o777) == "0o600", name


def test_a_failing_command_is_a_failed_job_with_its_exit_status(root):
    done = finish(jb.start_job(root, JobSpec("dataset", "", py("import sys; print('bad'); sys.exit(3)"))))
    assert done.status is JobStatus.FAILED and done.exit_code == 3 and jb.tail_log(done.dir) == ["bad"]


def test_a_program_that_is_not_there_never_starts_and_says_why(root, tmp_path):
    info = jb.start_job(root, JobSpec("dataset", "", ("/definitely/not/a/program",)))
    assert info.status is JobStatus.NEVER_STARTED and info.error == "program_not_found" and info.runner_pid is None
    plain = tmp_path / "plain"
    plain.write_text("x")
    plain.chmod(0o600)
    assert jb.start_job(root, JobSpec("dataset", "", (str(plain),))).error == "not_executable"


def test_one_stop_request_sends_one_ctrl_c_however_many_times_it_is_asked(root, tmp_path):
    count = tmp_path / "count"
    code = ("import signal, sys, time, pathlib\n"
            "n = 0\n"
            "def handler(*a):\n"
            "    global n\n"
            "    n += 1\n"
            "    pathlib.Path(sys.argv[1]).write_text(str(n))\n"
            "    time.sleep(0.4)\n"
            "    sys.exit(0)\n"
            "signal.signal(signal.SIGINT, handler)\n"
            "print('ready', flush=True)\n"
            "time.sleep(60)\n")
    info = jb.start_job(root, JobSpec("train", "anna", py(code, str(count)), gpu=True))
    wait_until(lambda: "ready" in jb.tail_log(info.dir), what="the command to be ready")
    assert [jb.request_stop(info.dir) for _ in range(3)] == ["asked", "already", "already"]
    assert wait_until(lambda: jb.job_info(info.dir).status in (JobStatus.STOPPING, JobStatus.STOPPED), what="the stop to show")
    done = finish(info)
    assert done.status is JobStatus.STOPPED and done.exit_code == 0 and count.read_text() == "1"
    assert jb.request_stop(info.dir) == "not_running" and jb.force_stop(info.dir) == "not_running"


def test_a_command_that_ignores_ctrl_c_keeps_running_until_a_forced_stop_ends_it(root):
    code = "import signal, time; signal.signal(signal.SIGINT, signal.SIG_IGN); print('ready', flush=True); time.sleep(60)"
    info = jb.start_job(root, JobSpec("train", "", py(code), force_grace_s=0.3))
    wait_until(lambda: "ready" in jb.tail_log(info.dir), what="the command to be ready")
    assert jb.request_stop(info.dir) == "asked"
    time.sleep(0.6)
    assert jb.job_info(info.dir).status is JobStatus.STOPPING          # asked nicely, still going: nothing harder is sent by itself
    assert jb.force_stop(info.dir) == "asked" and jb.force_stop(info.dir) == "already"
    done = finish(info)
    assert done.status is JobStatus.STOPPED and done.signal == 15 and done.exit_code is None


def test_a_command_that_ignores_terminate_too_is_killed_after_the_grace_time(root):
    code = "import signal, time; signal.signal(signal.SIGINT, signal.SIG_IGN); signal.signal(signal.SIGTERM, signal.SIG_IGN); print('ready', flush=True); time.sleep(60)"
    info = jb.start_job(root, JobSpec("train", "", py(code), force_grace_s=0.5))
    wait_until(lambda: "ready" in jb.tail_log(info.dir), what="the command to be ready")
    began = time.time()
    jb.force_stop(info.dir)
    done = finish(info)
    assert done.signal == 9 and 0.4 <= time.time() - began < 10


def test_whatever_a_killed_command_started_is_not_left_running(root, tmp_path):
    pidfile = tmp_path / "grandchild"
    code = ("import subprocess, sys, time\n"
            "p = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])\n"
            "open(sys.argv[1], 'w').write(str(p.pid))\n"
            "print('ready', flush=True)\n"
            "time.sleep(60)\n")
    info = jb.start_job(root, JobSpec("train", "", py(code, str(pidfile)), force_grace_s=0.2))
    wait_until(lambda: "ready" in jb.tail_log(info.dir), what="the command to be ready")
    grandchild = int(pidfile.read_text())
    assert is_running(grandchild)
    jb.force_stop(info.dir)
    finish(info)
    wait_until(lambda: not is_running(grandchild), 10, "the grandchild to be gone")


@pytest.mark.parametrize("how, expected_status", [("os.kill(os.getpid(), signal.SIGKILL)", JobStatus.FAILED), ("sys.exit(1)", JobStatus.FAILED)])
def test_workers_left_behind_by_a_command_that_dies_or_fails_are_cleaned_up(root, tmp_path, how, expected_status):
    pidfile = tmp_path / "worker"
    code = ("import os, signal, subprocess, sys, time\n"
            "p = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])\n"
            "open(sys.argv[1], 'w').write(str(p.pid))\n"
            "time.sleep(0.5)\n" + how + "\n")
    info = jb.start_job(root, JobSpec("train", "", py(code, str(pidfile))))
    wait_until(pidfile.exists, what="the worker to start")
    worker = int(pidfile.read_text())
    done = finish(info)
    assert done.status is expected_status
    wait_until(lambda: not is_running(worker), 10, "the worker left behind to be cleaned up")


def test_a_second_job_that_needs_the_gpu_is_refused_while_one_has_it(root):
    first = jb.start_job(root, JobSpec("train", "anna", py(SLEEPER), gpu=True))
    assert jb.gpu_busy(root).id == first.id
    with pytest.raises(JobError) as caught:
        jb.start_job(root, JobSpec("train", "ben", py(SLEEPER), gpu=True))
    assert caught.value.code == "gpu_busy" and caught.value.detail == first.id
    other = jb.start_job(root, JobSpec("dataset", "ben", py(SLEEPER)))              # a job that does not use the GPU is fine
    assert other.status is JobStatus.RUNNING
    jb.force_stop(other.dir)
    jb.request_stop(first.dir)
    jb.force_stop(first.dir)
    finish(first)
    finish(other)
    assert jb.gpu_busy(root) is None
    again = jb.start_job(root, JobSpec("train", "ben", py("print(1)"), gpu=True))
    assert finish(again).status is JobStatus.FINISHED


def test_the_gpu_is_still_held_while_a_job_is_stopping(root):
    code = "import signal, time; signal.signal(signal.SIGINT, signal.SIG_IGN); print('ready', flush=True); time.sleep(60)"
    first = jb.start_job(root, JobSpec("train", "", py(code), gpu=True))
    wait_until(lambda: "ready" in jb.tail_log(first.dir), what="ready")
    jb.request_stop(first.dir)
    assert jb.job_info(first.dir).status is JobStatus.STOPPING and jb.gpu_busy(root) is not None
    jb.force_stop(first.dir)
    finish(first)


def test_a_job_killed_with_its_runner_is_interrupted_not_running(root):
    info = jb.start_job(root, JobSpec("dataset", "", py(SLEEPER)))
    runner = jb.read_json(info.dir + "/runner.json")
    os.kill(runner["pid"], 9)
    os.killpg(runner["child_pid"], 9)
    assert wait_until(lambda: jb.job_info(info.dir).status is JobStatus.INTERRUPTED, 10, "the job to be seen as interrupted")


def test_the_environment_of_a_job_is_offline_by_default_and_can_be_extended_but_the_offline_part_is_the_floor(root):
    done = finish(jb.start_job(root, JobSpec("dataset", "", py("import os; print(os.environ['HF_HUB_DISABLE_TELEMETRY'], os.environ['DO_NOT_TRACK'], os.environ['TRANSFORMERS_OFFLINE'])"))))
    assert jb.tail_log(done.dir) == ["1 1 1"]
    assert set(jb.OFFLINE_ENV) >= {"HF_HUB_OFFLINE", "HF_HUB_DISABLE_TELEMETRY", "DO_NOT_TRACK"}


# ---------------------------------------------------------------- refusals

@pytest.mark.parametrize("spec, code, detail", [
    (JobSpec("Train", "", py("1")), "bad_spec", ""), (JobSpec("", "", py("1")), "bad_spec", ""), (JobSpec("x" * 21, "", py("1")), "bad_spec", ""),
    (JobSpec("train", "", ()), "bad_spec", ""), (JobSpec("train", "", ("",)), "bad_spec", ""), (JobSpec("train", "", ("a\x00b",)), "bad_spec", ""),
    (JobSpec("train", "../x", py("1")), "bad_spec", "project"), (JobSpec("train", "", py("1"), cwd="/no/such/folder"), "bad_spec", "cwd"),
    (JobSpec("train", "", py("1"), force_grace_s=-1), "bad_spec", "force_grace_s"), (JobSpec("train", "", py("1"), force_grace_s=601), "bad_spec", "force_grace_s"),
    (JobSpec("train", "", ("curl", "x")), "network_program", "curl"), (JobSpec("train", "", ("sudo", "apt-get", "install", "x")), "network_program", "sudo"),
    (JobSpec("train", "", ("/usr/bin/python3", "-m", "pip", "install", "x")), "network_program", "python3"),
])
def test_a_job_that_is_malformed_or_would_use_the_network_is_refused_before_anything_is_made(root, spec, code, detail):
    with pytest.raises(JobError) as caught:
        jb.start_job(root, spec)
    assert caught.value.code == code and caught.value.detail == detail
    assert not os.path.exists(root) or os.listdir(root) == []


# ---------------------------------------------------------------- reading

def test_the_log_tail_is_the_last_lines_and_progress_bars_count_as_lines(tmp_path):
    d = str(tmp_path)
    assert jb.tail_log(d) == []
    Path(d + "/log.txt").write_bytes(b"one\ntwo\r\nthree\n\n  \nEpoch 1: 10%\rEpoch 1: 50%\rEpoch 1: 100%\nlast")
    assert jb.tail_log(d, 3) == ["Epoch 1: 50%", "Epoch 1: 100%", "last"]
    assert jb.tail_log(d, 100) == ["one", "two", "three", "Epoch 1: 10%", "Epoch 1: 50%", "Epoch 1: 100%", "last"]
    Path(d + "/log.txt").write_bytes(b"caf\xc3\xa9 \xff\xfe broken\nnext")
    assert jb.tail_log(d)[1] == "next" and "café" in jb.tail_log(d)[0]


def test_a_huge_log_is_read_from_the_end_only_and_the_cut_first_line_is_dropped(tmp_path):
    d = str(tmp_path)
    with open(d + "/log.txt", "wb") as handle:
        for i in range(200000):
            handle.write(b"line %d\n" % i)
    lines = jb.tail_log(d, 5, max_bytes=1000)
    assert lines[-1] == "line 199999" and len(lines) == 5 and all(l.startswith("line ") and l.split()[1].isdigit() for l in lines)
    assert len(jb.tail_log(d, 10 ** 6, max_bytes=1000)) < 200       # bounded by the bytes read, not by the line count asked for


def test_the_cut_first_line_of_a_window_is_never_shown_as_if_it_were_whole(tmp_path):
    d = str(tmp_path)
    Path(d + "/log.txt").write_bytes(b"AAAAAAAAAA\n" * 1000)                 # 11 bytes a line
    assert jb.tail_log(d, 10 ** 6, max_bytes=105) == ["AAAAAAAAAA"] * 9           # 105 bytes start 6 bytes into a line: that partial line is dropped
    assert jb.tail_log(d, 10 ** 6, max_bytes=110) == ["AAAAAAAAAA"] * 9           # 110 bytes start 1 byte in
    assert jb.tail_log(d, 10 ** 6, max_bytes=11) == []                               # a window one line long cannot tell whether it starts mid-line, so its only line is dropped
    assert jb.tail_log(d, 10 ** 6, max_bytes=10 ** 6) == ["AAAAAAAAAA"] * 1000      # the whole file fits: nothing is dropped


def test_listing_orders_by_start_and_names_folders_it_cannot_read(root):
    a = finish(jb.start_job(root, JobSpec("dataset", "", py("print(1)")), now=datetime(2026, 1, 2, tzinfo=timezone.utc)))
    b = finish(jb.start_job(root, JobSpec("dataset", "", py("print(2)")), now=datetime(2026, 1, 1, tzinfo=timezone.utc)))
    os.mkdir(root + "/broken")
    Path(root + "/stray.txt").write_text("")
    listing = jb.list_jobs(root)
    assert [j.id for j in listing.jobs] == [b.id, a.id] and listing.problems == ("broken",)
    assert jb.list_jobs("/no/such/folder") == jb.JobList((), ())
