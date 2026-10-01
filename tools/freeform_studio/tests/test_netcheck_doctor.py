import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

from freeform_studio import doctor, netcheck

TOOLS = Path(__file__).resolve().parents[2]
needs_openssl = pytest.mark.skipif(shutil.which("openssl") is None, reason="openssl not installed")


def make_cert(tmp_path, sans):
    cert, key = tmp_path / "c.pem", tmp_path / "k.pem"
    subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-keyout", str(key), "-out", str(cert),
                    "-days", "2", "-subj", "/CN=test", "-addext", f"subjectAltName={sans}"],
                   check=True, capture_output=True)
    return cert, key


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def run_server(out, port, *extra):
    proc = subprocess.Popen([sys.executable, "-m", "freeform_studio", "--output", str(out), "--port", str(port),
                             "--token", "none", "--asr-engine", "fake", *extra],
                            cwd=TOOLS, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(100):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/healthz", timeout=0.5)
            return proc
        except OSError:
            if proc.poll() is not None:
                break
            time.sleep(0.1)
    return proc


def test_the_link_prefers_an_address_the_certificate_covers():
    assert netcheck.pick_advertised_host("192.168.1.2", ["192.168.1.2", "127.0.0.1"]) == ("192.168.1.2", None)
    host, note = netcheck.pick_advertised_host("172.20.0.5", ["192.168.1.2", "127.0.0.1"])
    assert host == "192.168.1.2" and "172.20.0.5" in note
    host, note = netcheck.pick_advertised_host("192.168.1.9", ["127.0.0.1"])
    assert host == "192.168.1.9" and "mkcert 192.168.1.9" in note
    assert netcheck.pick_advertised_host("10.0.0.4", []) == ("10.0.0.4", None)  # no certificate: nothing to compare


@needs_openssl
def test_certificate_names_are_read(tmp_path):
    cert, _ = make_cert(tmp_path, "DNS:localhost,IP:192.168.1.2,IP:127.0.0.1")
    info = netcheck.san_info(cert)
    assert info["dns"] == ["localhost"] and info["ips"] == ["192.168.1.2", "127.0.0.1"] and info["error"] is None
    assert "GMT" in info["not_after"]
    (tmp_path / "junk.pem").write_text("not a certificate")
    assert netcheck.san_info(tmp_path / "junk.pem")["error"]


def test_port_state_and_probe(tmp_path):
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    s.listen()
    assert netcheck.port_state("127.0.0.1", s.getsockname()[1]) == "in_use"
    s.close()
    port = free_port()
    assert netcheck.port_state("127.0.0.1", port) == "free"
    ok, detail = netcheck.probe("127.0.0.1", port, tls=False)
    assert not ok and "no connection" in detail
    proc = run_server(tmp_path, port)
    try:
        assert netcheck.probe("127.0.0.1", port, tls=False) == (True, "answered")
        ok, detail = netcheck.probe("127.0.0.1", port, tls=True)  # asking a plain-http server for https
        assert not ok and "secure connection failed" in detail
    finally:
        proc.terminate()
        proc.wait(timeout=10)


@pytest.fixture(autouse=True)
def environment_is_fine(monkeypatch):
    """These tests are about networking; don't let whatever happens to be installed here change the outcome."""
    monkeypatch.setattr(doctor, "_has_module", lambda name: True)
    monkeypatch.setattr(doctor, "_has_ffmpeg", lambda: True)


def doctor_output(capsys, *argv):
    code = doctor.main(list(argv))
    return code, capsys.readouterr().out


def test_doctor_says_when_the_server_is_not_running(tmp_path, capsys):
    (tmp_path / "out").mkdir()
    code, out = doctor_output(capsys, "--output", str(tmp_path / "out"), "--port", str(free_port()))
    assert code == 0 and "isn't running yet" in out and "Link for your phone" in out


def test_doctor_reports_missing_certificate_files_with_the_likely_cause(tmp_path, capsys):
    (tmp_path / "out").mkdir()
    code, out = doctor_output(capsys, "--output", str(tmp_path / "out"), "--port", str(free_port()),
                              "--certfile", "/nope/<your-ip>+2.pem", "--keyfile", "/nope/<your-ip>+2-key.pem")
    assert code == 1 and "FIX THESE, IN ORDER:" in out and "placeholder like <your-ip>" in out


def test_doctor_confirms_a_server_that_the_network_can_reach(tmp_path, capsys):
    (tmp_path / "out").mkdir()
    port = free_port()
    proc = run_server(tmp_path / "out", port, "--host", "0.0.0.0")
    try:
        code, out = doctor_output(capsys, "--output", str(tmp_path / "out"), "--port", str(port))
        assert code == 0 and "the server is running and answers on this computer" in out
        assert "listening on the network, not just locally" in out and "PROBLEM" not in out
    finally:
        proc.terminate()
        proc.wait(timeout=10)


def test_doctor_flags_a_server_that_only_listens_locally(tmp_path, capsys):
    # the classic phone problem: started without --host 0.0.0.0
    (tmp_path / "out").mkdir()
    port = free_port()
    proc = run_server(tmp_path / "out", port)  # default host is loopback only
    try:
        code, out = doctor_output(capsys, "--output", str(tmp_path / "out"), "--port", str(port))
        assert code == 1 and "does not answer on" in out and "Start it with --host 0.0.0.0" in out
    finally:
        proc.terminate()
        proc.wait(timeout=10)


def start_and_capture(tmp_path, *args):
    return subprocess.run([sys.executable, "-m", "freeform_studio", "--output", str(tmp_path), "--asr-engine", "fake", *args],
                          cwd=TOOLS, capture_output=True, text=True, timeout=30)


def test_bad_certificate_path_fails_plainly_before_any_link_is_shown(tmp_path):
    r = start_and_capture(tmp_path, "--port", str(free_port()), "--certfile", "/nope/a.pem", "--keyfile", "/nope/b.pem")
    assert r.returncode == 2
    assert "certificate file was not found" in r.stderr and "ls ~/piper-recording-studio/certs" in r.stderr
    assert "Traceback" not in r.stderr and "usage:" not in r.stderr
    assert "open on your phone" not in r.stdout  # never advertise a link for a server that isn't starting


def test_port_already_in_use_fails_plainly(tmp_path):
    with socket.socket() as s:
        s.bind(("0.0.0.0", 0))
        s.listen()
        r = start_and_capture(tmp_path, "--port", str(s.getsockname()[1]), "--host", "0.0.0.0")
    assert r.returncode == 2 and "already in use" in r.stderr and "Traceback" not in r.stderr


@needs_openssl
def test_link_uses_the_address_in_the_certificate(tmp_path):
    cert, key = make_cert(tmp_path, "DNS:localhost,IP:192.168.77.5,IP:127.0.0.1")
    port = free_port()
    proc = subprocess.Popen([sys.executable, "-u", "-m", "freeform_studio", "--output", str(tmp_path), "--port", str(port),
                             "--host", "0.0.0.0", "--asr-engine", "fake", "--token", "none",
                             "--certfile", str(cert), "--keyfile", str(key)],
                            cwd=TOOLS, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        banner = ""
        for _ in range(40):
            line = proc.stdout.readline()
            banner += line
            if "can't connect?" in line:
                break
        assert f"open on your phone:   https://192.168.77.5:{port}/" in banner
        assert f"open on this PC:      https://localhost:{port}/" in banner
    finally:
        proc.terminate()
        proc.wait(timeout=10)


def test_doctor_lists_every_problem_in_order_not_just_the_first(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(doctor, "_has_ffmpeg", lambda: False)
    (tmp_path / "out").mkdir()
    code, out = doctor_output(capsys, "--output", str(tmp_path / "out"), "--port", str(free_port()),
                              "--certfile", "/nope/a.pem", "--keyfile", "/nope/b.pem")
    assert code == 1 and "FIX THESE, IN ORDER:" in out
    assert out.index("sudo apt install ffmpeg") < out.index("doesn't exist. Check the path")  # in the order found


def test_certs_dir_picks_the_newest_matching_pair_and_ignores_the_rest(tmp_path):
    d = tmp_path / "certs"
    d.mkdir()
    for name in ("192.168.1.2+2.pem", "192.168.1.2+2-key.pem", "192.168.9.9+2.pem", "192.168.9.9+2-key.pem",
                 "rootCA.pem", "lonely-key.pem"):
        (d / name).write_text("x")
    old = time.time() - 1000
    os.utime(d / "192.168.1.2+2.pem", (old, old))
    os.utime(d / "192.168.1.2+2-key.pem", (old, old))
    cert, key = netcheck.find_cert_pair(d)
    assert cert.name == "192.168.9.9+2.pem" and key.name == "192.168.9.9+2-key.pem"  # newest pair; rootCA + unpaired ignored
    assert netcheck.find_cert_pair(tmp_path) is None


@needs_openssl
def test_server_starts_from_just_the_certs_folder(tmp_path):
    d = tmp_path / "certs"
    d.mkdir()
    cert, key = make_cert(tmp_path, "DNS:localhost,IP:127.0.0.1")
    shutil.copy(cert, d / "10.1.2.3+2.pem")
    shutil.copy(key, d / "10.1.2.3+2-key.pem")
    port = free_port()
    proc = subprocess.Popen([sys.executable, "-u", "-m", "freeform_studio", "--output", str(tmp_path), "--port", str(port),
                             "--asr-engine", "fake", "--token", "none", "--certs-dir", str(d)],
                            cwd=TOOLS, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        seen = ""
        for _ in range(40):
            line = proc.stdout.readline()
            seen += line
            if "can't connect?" in line:
                break
        assert "using certificate 10.1.2.3+2.pem" in seen and "https://" in seen
        deadline = time.time() + 10
        while time.time() < deadline and not netcheck.probe("127.0.0.1", port, tls=True)[0]:
            time.sleep(0.2)
        assert netcheck.probe("127.0.0.1", port, tls=True) == (True, "answered")
    finally:
        proc.terminate()
        proc.wait(timeout=10)


def test_empty_certs_folder_fails_plainly(tmp_path):
    (tmp_path / "certs").mkdir()
    r = start_and_capture(tmp_path, "--port", str(free_port()), "--certs-dir", str(tmp_path / "certs"))
    assert r.returncode == 2 and "no certificate pair found" in r.stderr and "Traceback" not in r.stderr


# ---------------------------------------------------------------- disk, backups and repair (read straight from the folders)

from collections import namedtuple
from datetime import datetime, timedelta

from freeform_studio import backup as bk
from freeform_studio import health
from test_backup import make_take

_MB = 1024 * 1024
_Usage = namedtuple("Usage", "total used free")


def doctor_here(capsys, tmp_path, *extra):
    return doctor_output(capsys, "--output", str(tmp_path / "out"), "--backup-dir", str(tmp_path / "bk"),
                         "--port", str(free_port()), *extra)


def disk(monkeypatch, free_mb):
    monkeypatch.setattr(health.shutil, "disk_usage", lambda p: _Usage(500_000 * _MB, 0, int(free_mb * _MB)))


def test_doctor_is_quiet_about_a_roomy_disk(tmp_path, capsys, monkeypatch):
    (tmp_path / "out").mkdir()
    disk(monkeypatch, 80_000)
    code, out = doctor_here(capsys, tmp_path)
    assert "78 GB of disk space is free" in out and code == 0


def test_doctor_notes_a_disk_that_is_getting_low_without_failing(tmp_path, capsys, monkeypatch):
    (tmp_path / "out").mkdir()
    disk(monkeypatch, 1_500)
    code, out = doctor_here(capsys, tmp_path)
    assert "NOTE" in out and "1.5 GB of disk space is free" in out and "free some soon" in out
    assert code == 0, "a low disk is a warning, not a failure: recording still works"


def test_doctor_calls_a_nearly_full_disk_a_problem_and_names_the_limit(tmp_path, capsys, monkeypatch):
    (tmp_path / "out").mkdir()
    disk(monkeypatch, 300)
    code, out = doctor_here(capsys, tmp_path)
    assert code == 1 and "only 300 MB of disk space is free, so new audio is refused" in out
    assert "refuses new audio below 500 MB free" in out and "stays on the phone" in out


def test_doctor_uses_the_same_floor_the_server_was_started_with(tmp_path, capsys, monkeypatch):
    (tmp_path / "out").mkdir()
    disk(monkeypatch, 1_500)
    code, out = doctor_here(capsys, tmp_path, "--min-free-mb", "2000")
    assert code == 1 and "refuses new audio below 2000 MB free" in out
    code, out = doctor_here(capsys, tmp_path, "--min-free-mb", "1000")
    assert "only 1500 MB" not in out, "above the floor it is only a note"


def test_doctor_shrugs_when_the_disk_cannot_be_measured(tmp_path, capsys, monkeypatch):
    (tmp_path / "out").mkdir()

    def boom(_p):
        raise OSError("no such device")

    monkeypatch.setattr(health.shutil, "disk_usage", boom)
    code, out = doctor_here(capsys, tmp_path)
    assert "free disk space could not be measured" in out and code == 0


def test_doctor_has_nothing_to_say_about_backups_before_the_first_recording(tmp_path, capsys):
    (tmp_path / "out").mkdir()
    code, out = doctor_here(capsys, tmp_path)
    assert "no recordings yet, so nothing to back up" in out and code == 0


def test_doctor_nudges_when_recordings_have_never_been_backed_up(tmp_path, capsys):
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    make_take(out_dir, "t20260930-000001-aaaa")
    code, out = doctor_here(capsys, tmp_path)
    assert "you have recordings but no backup yet" in out and "python -m freeform_studio.backup" in out
    assert code == 0, "a missing backup is advice, never a reason to stop"


def test_doctor_shows_a_recent_backup_as_fine_and_an_old_one_as_a_nudge(tmp_path, capsys):
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    make_take(out_dir, "t20260930-000001-aaaa")
    bk.create(out_dir, "en-US", tmp_path / "bk", now=datetime.now() - timedelta(hours=2))
    code, out = doctor_here(capsys, tmp_path)
    assert "last backup" in out and "(1 kept)" in out and "days ago" not in out

    for f in (tmp_path / "bk").iterdir():
        f.unlink()
    bk.create(out_dir, "en-US", tmp_path / "bk", force=True, now=datetime.now() - timedelta(days=12))
    code, out = doctor_here(capsys, tmp_path)
    assert "12 days ago" in out and "consider python -m freeform_studio.backup" in out and code == 0


def test_doctor_counts_recordings_waiting_for_their_audio_to_be_rebuilt(tmp_path, capsys):
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    d = make_take(out_dir, "t20260930-000001-aaaa")           # ready, raw audio present, derived files unusable
    code, out = doctor_here(capsys, tmp_path)
    assert "1 recording(s) are missing their decoded audio" in out and "freeform_studio.repair" in out and code == 0

    (d / "peaks.json").write_text('{"levels": []}')           # a valid waveform summary and the wav: nothing to rebuild
    code, out = doctor_here(capsys, tmp_path)
    assert "missing their decoded audio" not in out


def test_doctor_does_not_touch_anything_it_inspects(tmp_path, capsys, monkeypatch):
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    make_take(out_dir, "t20260930-000001-aaaa")
    disk(monkeypatch, 80_000)

    def snapshot():
        return sorted((str(p.relative_to(tmp_path)), p.stat().st_mtime_ns, p.stat().st_size) for p in tmp_path.rglob("*") if p.is_file())

    before = snapshot()
    doctor_here(capsys, tmp_path)
    assert snapshot() == before and not (tmp_path / "bk").exists(), "the doctor only looks; it never makes a backup or repairs anything"
