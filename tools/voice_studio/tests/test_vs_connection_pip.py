# SPDX-License-Identifier: GPL-3.0-or-later
"""The waiting and retrying against a REAL pip and a local package server that misbehaves on purpose (plan finding F20).

Everything is on this computer (127.0.0.1): a tiny package index serves two small wheels and can cut a download in half, reset the connection, go
quiet, be absent, or serve a different file than the lock names. The real `pip install --require-hashes` runs against it, and the same adapter the
builder uses (`connection.raise_if_connection`) decides what each failure was. Waiting moves a fake clock, so nothing here sleeps.
It is skipped when this Python has no pip.
"""
import hashlib
import io
import os
import random
import socket
import socketserver
import struct
import subprocess
import sys
import threading
import time
import zipfile
import http.server
from pathlib import Path

import pytest

from vs_env_helpers import FakeTime
from voice_studio.core import connection as cn


def pip_available():
    try:
        return subprocess.run([sys.executable, "-m", "pip", "--version"], capture_output=True, timeout=60).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


pytestmark = pytest.mark.skipif(not pip_available(), reason="this Python has no pip")


def pip_resumes_by_itself():
    """pip 25.1 and later pick an interrupted download up again on their own (--resume-retries). The tests switch that off, so what is tested is the
    behaviour of the pip that Ubuntu 22.04 and 24.04 ship (22.0.2 and 24.0), which does not: a drop there ends the run, and the tool's loop takes over."""
    done = subprocess.run([sys.executable, "-m", "pip", "install", "--help"], capture_output=True, text=True, timeout=60)
    return "--resume-retries" in done.stdout


RESUME_OFF = ["--resume-retries", "0"] if pip_available() and pip_resumes_by_itself() else []


def make_wheel(name, size=600_000):
    rnd = random.Random(name)
    buf = io.BytesIO()

    def put(z, path, data):
        info = zipfile.ZipInfo(path, date_time=(2020, 1, 1, 0, 0, 0))
        info.compress_type = zipfile.ZIP_STORED
        z.writestr(info, data)
    with zipfile.ZipFile(buf, "w") as z:
        put(z, name + "/__init__.py", "x = 1\n")
        put(z, name + "/blob.bin", rnd.randbytes(size))
        put(z, name + "-1.0.dist-info/METADATA", "Metadata-Version: 2.1\nName: %s\nVersion: 1.0\n" % name)
        put(z, name + "-1.0.dist-info/WHEEL", "Wheel-Version: 1.0\nGenerator: x\nRoot-Is-Purelib: true\nTag: py3-none-any\n")
        put(z, name + "-1.0.dist-info/RECORD", "")
    return buf.getvalue()


WHEELS = {name: make_wheel(name) for name in ("connpkga", "connpkgb")}
HASHES = {name: hashlib.sha256(data).hexdigest() for name, data in WHEELS.items()}


class Index:
    """The misbehaving package index. `plan` lists, for each request of the second wheel in turn, what to do: ok, cut, reset, stall or wrong."""

    def __init__(self):
        self.plan, self.requests, self.server, self.thread = [], [], None, None
        index = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                path = self.path
                index.requests.append(path)
                if path.startswith("/simple/") and path.endswith("/") and path.count("/") == 3:
                    name = path.split("/")[2]
                    if name in WHEELS:
                        body = ('<!DOCTYPE html><html><body><a href="/files/%s-1.0-py3-none-any.whl#sha256=%s">%s-1.0-py3-none-any.whl</a></body></html>'
                                % (name, HASHES[name], name)).encode()
                        self.reply(200, body, "text/html")
                        return
                if path.startswith("/files/"):
                    name = path.split("/")[2].split("-")[0]
                    data = WHEELS.get(name)
                    if data is None:
                        self.reply(404, b"no", "text/plain")
                        return
                    action = index.plan.pop(0) if name == "connpkgb" and index.plan else "ok"
                    if action == "gone":
                        self.reply(404, b"gone", "text/plain")
                        return
                    if action == "wrong":
                        data = data[:-10] + b"X" * 10
                    self.send_response(200)
                    self.send_header("Content-Type", "application/octet-stream")
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    if action in ("cut", "reset", "stall"):
                        self.wfile.write(data[: len(data) // 2])
                        self.wfile.flush()
                        if action == "cut":
                            self.connection.shutdown(socket.SHUT_RDWR)
                        elif action == "reset":
                            self.connection.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0))
                        else:
                            time.sleep(4)
                        self.connection.close()
                        return
                    self.wfile.write(data)
                    return
                self.reply(404, b"no", "text/plain")

            def reply(self, status, body, kind):
                self.send_response(status)
                self.send_header("Content-Type", kind)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        class Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
            daemon_threads = True
            allow_reuse_address = True

        self.handler, self.server_class = Handler, Server
        probe = socket.socket()
        probe.bind(("127.0.0.1", 0))
        self.port = probe.getsockname()[1]
        probe.close()

    def start(self):
        self.server = self.server_class(("127.0.0.1", self.port), self.handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def stop(self):
        if self.server is not None:
            self.server.shutdown()
            self.server.server_close()
            self.server = None

    @property
    def address(self):
        return "http://127.0.0.1:%d/simple/" % self.port

    def wheel_requests(self, name):
        return [p for p in self.requests if p.startswith("/files/" + name)]


@pytest.fixture
def index():
    server = Index()
    yield server
    server.stop()


class Pip:
    """The same command the builder runs, aimed at the local index, with the quick tries and the short patience that keep the test fast."""

    def __init__(self, tmp_path, index):
        self.tmp, self.index = Path(tmp_path), index
        self.lock = self.tmp / "lock.txt"
        self.lock.write_text("".join("%s==1.0 \\\n    --hash=sha256:%s\n" % (name, HASHES[name]) for name in WHEELS))
        self.runs = 0

    def run(self):
        self.runs += 1
        argv = [sys.executable, "-m", "pip", "install", "--require-hashes", "--only-binary=:all:", "--no-deps", "--disable-pip-version-check", "--no-input",
                "--retries", "1", "--timeout", "2", "--no-cache-dir"] + RESUME_OFF + [ "--target", str(self.tmp / "target"), "--index-url", self.index.address, "-r", str(self.lock)]
        done = subprocess.run(argv, capture_output=True, text=True, env=dict(os.environ, LC_ALL="C", PIP_CONFIG_FILE=os.devnull), timeout=120)
        return done.returncode, done.stdout + done.stderr

    def attempt(self):
        status, output = self.run()
        if status == 0:
            return "installed"
        cn.raise_if_connection(status, output)
        raise RuntimeError("an ordinary failure: " + output[-300:])

    def keep_trying(self, time_=None, on_wait=None, patience=cn.DEFAULT_PATIENCE):
        time_ = time_ or FakeTime()
        return cn.keep_trying(self.attempt, on_wait=on_wait or (lambda wait: None), on_back=lambda: None, sleep=time_.sleep, clock=time_.monotonic,
                              patience=patience), time_

    def installed(self):
        target = self.tmp / "target"
        return sorted(p.name for p in target.iterdir() if p.is_dir() and not p.name.endswith(".dist-info")) if target.is_dir() else []


def test_a_download_cut_in_half_is_taken_for_a_drop_and_the_next_try_installs_both(tmp_path, index):
    index.plan = ["cut"]
    index.start()
    pip = Pip(tmp_path, index)
    value, clock = pip.keep_trying()
    assert value == "installed" and clock.slept == [5] and pip.runs == 2 and pip.installed() == ["connpkga", "connpkgb"]


def test_a_connection_reset_in_the_middle_of_a_file_is_waited_for(tmp_path, index):
    index.plan = ["reset"]
    index.start()
    pip = Pip(tmp_path, index)
    value, clock = pip.keep_trying()
    assert value == "installed" and clock.slept == [5] and pip.runs == 2


def test_a_server_that_goes_quiet_in_the_middle_of_a_file_is_waited_for(tmp_path, index):
    index.plan = ["stall"]
    index.start()
    pip = Pip(tmp_path, index)
    value, clock = pip.keep_trying()
    assert value == "installed" and clock.slept == [5] and pip.runs == 2


def test_a_server_that_is_not_there_yet_is_waited_for_and_found_when_it_comes_back(tmp_path, index):
    pip = Pip(tmp_path, index)
    time_ = FakeTime()
    waits = []

    def sleep(seconds):
        time_.sleep(seconds)
        if len(time_.slept) == 2:
            index.start()                                   # the connection comes back during the second wait

    clock = FakeTime()
    clock.sleep = sleep
    value = cn.keep_trying(pip.attempt, on_wait=waits.append, on_back=lambda: waits.append("back"), sleep=sleep, clock=time_.monotonic)
    assert value == "installed" and time_.slept == [5, 10] and waits[-1] == "back" and pip.runs == 3


def test_a_server_that_never_comes_back_ends_in_giving_up_and_the_real_pip_was_run_each_time(tmp_path, index):
    pip = Pip(tmp_path, index)
    time_ = FakeTime()
    with pytest.raises(cn.ConnectionGaveUp) as caught:
        cn.keep_trying(pip.attempt, on_wait=lambda wait: None, on_back=lambda: None, sleep=time_.sleep, clock=time_.monotonic,
                       patience=cn.Patience(total_s=30, pauses_s=(10,), progress_s=60))
    assert caught.value.waited_s == 30 and time_.slept == [10, 10, 10] and pip.runs == 4


def test_a_different_file_than_the_lock_names_twice_in_a_row_is_not_the_connection(tmp_path, index):
    index.plan = ["wrong", "wrong", "wrong"]
    index.start()
    pip = Pip(tmp_path, index)
    time_ = FakeTime()
    with pytest.raises(cn.NotTheConnection):
        cn.keep_trying(pip.attempt, on_wait=lambda wait: None, on_back=lambda: None, sleep=time_.sleep, clock=time_.monotonic)
    assert time_.slept == [5] and pip.runs == 2 and pip.installed() == []          # pip refused it both times: nothing wrong was installed


def test_a_file_the_server_no_longer_has_is_a_real_failure_not_a_wait(tmp_path, index):
    index.plan = ["gone"]
    index.start()
    pip = Pip(tmp_path, index)
    time_ = FakeTime()
    with pytest.raises(RuntimeError, match="ordinary failure"):
        cn.keep_trying(pip.attempt, on_wait=lambda wait: None, on_back=lambda: None, sleep=time_.sleep, clock=time_.monotonic)
    assert time_.slept == [] and pip.runs == 1


def test_a_clean_install_does_not_wait_at_all(tmp_path, index):
    index.start()
    pip = Pip(tmp_path, index)
    value, clock = pip.keep_trying()
    assert value == "installed" and clock.slept == [] and pip.runs == 1 and pip.installed() == ["connpkga", "connpkgb"]
