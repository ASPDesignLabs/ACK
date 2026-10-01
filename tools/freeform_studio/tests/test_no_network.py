# SPDX-License-Identifier: GPL-3.0-or-later
"""Nothing you record, edit or export leaves this computer, and nothing in the workflow needs the network at all.

Three layers, strongest first. Every layer that this machine supports is used:
  1. the workflow runs inside a network namespace that has ONLY the loopback interface (`unshare -rn`), after proving that
     1.1.1.1 and a hostname are unreachable. If anything needed the internet, a step would fail.
  2. every connect/send/name lookup made by any Python process is logged by a hook, and any destination that is not this computer fails.
  3. with `strace`, the same is checked for every process, including ffmpeg.
Plus a plain scan of the shipped files for web addresses, which the browser's Content-Security-Policy would block anyway.
"""
import ast
import ipaddress
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import needs_ffmpeg
from egress_workflow import SITECUSTOMIZE, parse_strace
from freeform_studio import netcheck

HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parent
ROUTE_PROBE = ("192.0.2.1", "9")   # netcheck.lan_ip(): a UDP connect() to a documentation address just picks a route; nothing is sent


def can_isolate() -> bool:
    return shutil.which("unshare") is not None and subprocess.run(["unshare", "-rn", "true"], capture_output=True).returncode == 0


def own_addresses():
    return set(netcheck.local_ips())


def is_this_computer(address, port, own, kind="connect"):
    if address in (None, ""):
        return True                       # a Unix or netlink socket: local by nature
    try:
        ip = ipaddress.ip_address(address)
    except ValueError:
        return address.lower() in ("localhost", "")   # a name that is not an address must be localhost
    if ip.is_loopback or address in own:
        return True
    return (address, str(port)) == ROUTE_PROBE and kind in ("connect", "connect_ex")


def guard_violations(events, own):
    bad = []
    for e in events:
        target = ast.literal_eval(e["target"]) if e["target"] not in ("None", "") else None
        kind = e["kind"]
        if isinstance(target, str):                                   # a Unix socket path
            continue
        if kind in ("getaddrinfo", "gethostbyname", "gethostbyname_ex", "gethostbyaddr", "getfqdn"):
            host = target[0] if target else ""
            if not is_this_computer(host if isinstance(host, str) else None, None, own):
                bad.append(f"name lookup: {kind}{target}")
            continue
        if target and not is_this_computer(target[0], target[1] if len(target) > 1 else None, own, kind):
            bad.append(f"{kind} {target}")
    return bad


def strace_violations(events, own):
    return [f"{e['process']}: {e['call']} {e['address']}:{e['port']}" for e in events
            if e["family"] in ("AF_INET", "AF_INET6")
            and not is_this_computer(e["address"], e["port"], own, "connect" if e["call"] == "connect" else "send")]


def run_workflow(work, isolate, use_strace):
    cmd = [sys.executable, str(HERE / "egress_workflow.py"), str(work)]
    if isolate:
        cmd = ["unshare", "-rn"] + cmd + ["--isolated"]
    if use_strace:
        cmd.append("--strace")
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=400)
    assert proc.returncode == 0, proc.stderr[-1500:] or proc.stdout[-1500:]
    return json.loads(proc.stdout.strip().splitlines()[-1])


@needs_ffmpeg
def test_the_whole_workflow_needs_no_network_and_uses_none(tmp_path):
    result = run_workflow(tmp_path / "wf", isolate=can_isolate(), use_strace=shutil.which("strace") is not None)
    failed = [s for s in result["steps"] if not s[1]]
    assert not failed, f"steps that failed (isolated={result['isolated']}): {failed}"
    assert len(result["steps"]) >= 18
    assert result["guard"], "the logging hook never ran, so this test would prove nothing"
    own = own_addresses()
    assert guard_violations(result["guard"], own) == []
    assert strace_violations(result["strace"], own) == []
    assert result["token_leaked_in_log"] is False, "the access token must only appear in the start-up message you are meant to read"


# ---------------------------------------------------------------- the detectors really do catch an outbound call

def test_the_python_hook_catches_a_connection_to_somewhere_else(tmp_path):
    (tmp_path / "sitecustomize.py").write_text(SITECUSTOMIZE)
    log = tmp_path / "log.jsonl"
    code = ("import socket\n"
            "socket.socket().connect_ex(('203.0.113.5', 80))\n"           # TEST-NET-3: documentation address, never routed
            "socket.socket(type=socket.SOCK_DGRAM).sendto(b'x', ('203.0.113.6', 9))\n"
            "try: socket.getaddrinfo('example.invalid', 443)\nexcept OSError: pass\n"
            "socket.socket().connect_ex(('127.0.0.1', 9))\n")
    env = {"PYTHONPATH": str(tmp_path), "EGRESS_LOG": str(log), "PATH": "/usr/bin:/bin"}
    subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, timeout=60)
    events = [json.loads(line) for line in log.read_text().splitlines()]
    bad = guard_violations(events, own=set())
    assert any("203.0.113.5" in b for b in bad) and any("203.0.113.6" in b for b in bad) and any("example.invalid" in b for b in bad)
    assert not any("127.0.0.1" in b for b in bad), "this computer is fine"


@pytest.mark.skipif(shutil.which("strace") is None, reason="strace not installed")
def test_strace_catches_a_connection_made_by_a_child_program(tmp_path):
    out = tmp_path / "s.strace"
    code = "import socket; socket.socket().connect_ex(('203.0.113.5', 80)); socket.socket().connect_ex(('127.0.0.1', 9))"
    subprocess.run(["strace", "-f", "-qq", "-e", "trace=connect,sendto", "-o", str(out), sys.executable, "-c", code], capture_output=True, timeout=60)
    bad = strace_violations(parse_strace(out.read_text(), "probe"), own=set())
    assert bad and all("203.0.113.5" in b for b in bad)


def test_the_route_probe_is_allowed_only_as_a_connect_never_as_something_sent():
    assert is_this_computer("192.0.2.1", "9", set(), "connect")
    assert not is_this_computer("192.0.2.1", "9", set(), "sendto"), "actually sending to it would be a leak"
    assert not is_this_computer("192.0.2.1", "80", set(), "connect")
    assert not is_this_computer("huggingface.co", None, set())


# ---------------------------------------------------------------- nothing in the shipped files points at the internet

SHIPPED = [p for p in PACKAGE.rglob("*") if p.is_file() and p.suffix in (".py", ".js", ".html", ".css", ".sh", ".json", ".txt")
           and "tests" not in p.relative_to(PACKAGE).parts and "__pycache__" not in p.parts]


def test_no_shipped_file_contains_a_web_address():
    offenders = []
    for p in SHIPPED:
        for n, line in enumerate(p.read_text(errors="replace").splitlines(), 1):
            if re.search(r"(?:https?|wss?|ftp)://", line):
                offenders.append(f"{p.relative_to(PACKAGE)}:{n}: {line.strip()[:90]}")
    assert not offenders, ("web addresses in shipped files. If one is a genuine reference in a comment, say why in the test; "
                           "nothing may load from one:\n" + "\n".join(offenders))


def test_the_pages_load_only_from_this_server():
    for page in (PACKAGE / "static").glob("*.html"):
        for attr, value in re.findall(r"""\b(src|href|action|data)=["']([^"']*)["']""", page.read_text()):
            assert value.startswith(("/", "#", "data:")) and not value.startswith("//"), f"{page.name}: {attr}={value}"
    css = (PACKAGE / "static" / "app.css").read_text()
    assert "@import" not in css and not re.search(r"url\(\s*[\"']?(?!data:|/)", css), "the stylesheet must not load anything from elsewhere"
