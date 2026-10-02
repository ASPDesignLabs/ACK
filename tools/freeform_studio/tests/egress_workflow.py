# SPDX-License-Identifier: GPL-3.0-or-later
"""Drive the whole Freeform Studio workflow and record every network call anything makes. Used by test_no_network.py.

    python egress_workflow.py WORKDIR [--isolated] [--strace]

It starts the real server and runs record -> transcribe -> edit -> export -> back up -> dataset -> doctor, the way a person
would, then prints one JSON line:  {"steps": [[name, ok, detail]...], "guard": [...], "strace": [...], "isolated": bool}

* guard:  every connect / send / name lookup made by any Python process in the workflow (a sitecustomize hook).
* strace: with --strace, every connect / send made by ANY process, including ffmpeg (needs `strace`).
* --isolated: first brings up only the loopback interface (run it inside `unshare -rn`) and proves 1.1.1.1 and a hostname
  are unreachable, so a passing run shows nothing in the workflow NEEDS the network, not just that it didn't use it.
"""
import fcntl
import json
import os
import random
import re
import shutil
import socket
import struct
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOOLS = HERE.parents[1]
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(HERE))
from conftest import make_live_webm, make_wav  # noqa: E402

TOKEN = "SECRET-TOKEN-do-not-log-me-0123456789"

SITECUSTOMIZE = '''
import json, os, socket
_LOG = os.environ.get("EGRESS_LOG")
def _note(kind, target):
    if not _LOG:
        return
    try:
        with open(_LOG, "a") as f:
            f.write(json.dumps({"kind": kind, "target": repr(target), "pid": os.getpid()}) + "\\n")
    except Exception:
        pass
_connect, _connect_ex, _sendto = socket.socket.connect, socket.socket.connect_ex, socket.socket.sendto
def connect(self, addr, *a, **k):
    _note("connect", addr); return _connect(self, addr, *a, **k)
def connect_ex(self, addr, *a, **k):
    _note("connect_ex", addr); return _connect_ex(self, addr, *a, **k)
def sendto(self, data, *args):
    _note("sendto", args[-1] if args else None); return _sendto(self, data, *args)
socket.socket.connect, socket.socket.connect_ex, socket.socket.sendto = connect, connect_ex, sendto
for _name in ("getaddrinfo", "gethostbyname", "gethostbyname_ex", "gethostbyaddr", "getfqdn"):
    def _wrap(orig, name):
        def f(*a, **k):
            _note(name, a[:2]); return orig(*a, **k)
        return f
    setattr(socket, _name, _wrap(getattr(socket, _name), _name))
'''


_STRACE = re.compile(r"\b(connect|sendto|sendmsg|sendmmsg)\(.*?sa_family=(AF_INET6?|AF_UNIX|AF_NETLINK)(?:, sin6?_port=htons\((\d+)\))?"
                     r"(?:, sin_addr=inet_addr\(\"([^\"]+)\"\))?(?:, sin6_addr=inet_pton\(AF_INET6, \"([^\"]+)\"\))?")


def parse_strace(text: str, process: str = "?") -> list:
    """The connect/send calls in strace output, as dicts with the family, address and port."""
    found = []
    for line in text.splitlines():
        m = _STRACE.search(line)
        if m:
            found.append({"process": process, "call": m.group(1), "family": m.group(2), "port": m.group(3), "address": m.group(4) or m.group(5)})
    return found


def bring_up_loopback_and_prove_isolation() -> bool:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    flags = struct.unpack("16sH14s", fcntl.ioctl(s, 0x8913, struct.pack("16sH14s", b"lo", 0, b"")))[1]
    fcntl.ioctl(s, 0x8914, struct.pack("16sH14s", b"lo", flags | 0x1, b""))
    if sorted(n for _, n in socket.if_nameindex()) != ["lo"]:
        raise SystemExit("isolation failed: more than loopback is visible")
    for target in (("1.1.1.1", 443), ("huggingface.co", 443)):
        try:
            socket.create_connection(target, timeout=3).close()
        except OSError:
            continue
        raise SystemExit(f"isolation failed: reached {target}")
    return True


def main() -> int:
    work = Path(sys.argv[1])
    isolated = "--isolated" in sys.argv
    use_strace = "--strace" in sys.argv
    if isolated:
        bring_up_loopback_and_prove_isolation()
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True)
    out, bk, ds, guard_dir = work / "out", work / "bk", work / "ds", work / "guard"
    out.mkdir()
    guard_dir.mkdir()
    (guard_dir / "sitecustomize.py").write_text(SITECUSTOMIZE)
    log = work / "guard.jsonl"

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    base = f"http://127.0.0.1:{port}"
    env = {k: v for k, v in os.environ.items() if k.lower() not in ("http_proxy", "https_proxy", "all_proxy")}
    env.update(PYTHONPATH=os.pathsep.join([str(guard_dir), str(TOOLS)]), EGRESS_LOG=str(log))
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def traced(name, cmd):
        if not use_strace:
            return cmd
        return ["strace", "-f", "-qq", "-s", "100", "-e", "trace=connect,sendto,sendmsg,sendmmsg", "-o", str(work / f"{name}.strace")] + cmd

    def call(method, path, body=None, raw=None, auth=True):
        headers = {"Authorization": f"Bearer {TOKEN}"} if auth else {}
        data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
        if body is not None:
            headers["Content-Type"] = "application/json"
        try:
            with opener.open(urllib.request.Request(base + path, data=data, method=method, headers=headers), timeout=60) as r:
                return r.status, r.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read()

    def jcall(*a, **k):
        st, data = call(*a, **k)
        try:
            return st, json.loads(data or b"null")
        except ValueError:
            return st, None

    steps = []

    def step(name, ok, detail=""):
        steps.append([name, bool(ok), detail])

    wav = make_wav(work / "in.wav", 9.0, [(0.5, 3.5), (5.0, 8.0)], rate=44100)
    data = make_live_webm(wav, work / "in.webm").read_bytes()
    cuts = sorted(random.Random(4).sample(range(1, len(data)), 4))
    chunks = [data[a:b] for a, b in zip([0] + cuts, cuts + [len(data)])]

    server_log = open(work / "server.log", "wb")
    server = subprocess.Popen(
        traced("server", [sys.executable, "-m", "freeform_studio", "--output", str(out), "--host", "0.0.0.0", "--port", str(port),
                          "--token", TOKEN, "--asr-engine", "fake", "--backup-dir", str(bk), "--no-auto-backup"]),
        cwd=TOOLS, env=env, stdout=server_log, stderr=subprocess.STDOUT)
    try:
        for _ in range(200):
            try:
                if call("GET", "/healthz", auth=False)[0] == 200:
                    break
            except OSError:
                time.sleep(0.2)
        else:
            step("server started", False, (work / "server.log").read_text(errors="replace")[-500:])
            raise RuntimeError("server did not start")
        step("server started", True)
        step("open the phone page and the review page", call("GET", "/", auth=True)[0] == 200 and call("GET", "/review")[0] == 200)
        static_ok = all(call("GET", "/static/" + f.relative_to(TOOLS / "freeform_studio" / "static").as_posix())[0] == 200
                        for f in (TOOLS / "freeform_studio" / "static").rglob("*") if f.is_file())
        step("every page file is served by this PC itself", static_ok)
        st, take = jcall("POST", "/api/takes", {"reference_text": "So here is a thing I wanted to say.", "label": "no-network test"})
        tid = take["id"]
        step("upload the recording in parts", all(call("PUT", f"/api/takes/{tid}/chunks/{n}", raw=c)[0] == 200 for n, c in enumerate(chunks)))
        step("finish", jcall("POST", f"/api/takes/{tid}/finish")[0] in (200, 202))
        doc = {}
        for _ in range(300):
            st, doc = jcall("GET", f"/api/takes/{tid}")
            if doc and doc["status"] in ("ready", "error"):
                break
            time.sleep(0.1)
        step("transcribed and ready to review", doc and doc["status"] == "ready", str(doc and doc.get("status")))
        # a package saved by the ACK app: brought in through the browser's own routes, looked inside, added, and processed
        from ack_package_builder import ClipSpec, PackageBuilder
        builder = PackageBuilder()
        builder.script_session([ClipSpec("The tide came in slowly.", speech=2.5), ClipSpec("We walked along the shore.", speech=3.0)])
        builder.free_session([(0.4, 3.0), (0.5, 7.0)])
        package = builder.write(work / "ack-training.zip")
        pkg_bytes = package.read_bytes()
        half = len(pkg_bytes) // 2
        step("bring an ACK package onto the PC", call("PUT", "/api/ack/incoming/ack-training.zip?offset=0", raw=pkg_bytes[:half])[0] == 200
             and call("PUT", f"/api/ack/incoming/ack-training.zip?offset={half}", raw=pkg_bytes[half:])[0] == 200
             and jcall("POST", "/api/ack/incoming/ack-training.zip/done", {"size": len(pkg_bytes)})[0] == 200)
        st, plan = jcall("POST", "/api/ack/check", {"name": "ack-training.zip"})
        step("look inside it", st == 200 and plan and plan["to_import"] == 2, str(st))
        st, added = jcall("POST", "/api/ack/import", {"name": "ack-training.zip"})
        step("add its recordings", st == 200 and added and len(added["created"]) == 2, str(st))
        for item in (added or {}).get("created", []):
            for _ in range(300):
                st, adoc = jcall("GET", f"/api/takes/{item['take_id']}")
                if adoc and adoc["status"] in ("ready", "error"):
                    break
                time.sleep(0.1)
            step("transcribed and ready to review (from ACK)", adoc and adoc["status"] == "ready", str(adoc and adoc.get("status")))
        st, edit = jcall("GET", f"/api/takes/{tid}/edit")
        segs = edit["segments"]
        segs[0]["status"] = "approved"
        step("edit and approve a piece", jcall("PUT", f"/api/takes/{tid}/edit", {"rev": edit["rev"], "segments": segs})[0] == 200)
        step("replace the reference text", jcall("PUT", f"/api/takes/{tid}/reference", {"text": "A new reference."})[0] == 200)
        step("listen to it and see its waveform", call("GET", f"/api/takes/{tid}/audio")[0] == 200 and call("GET", f"/api/takes/{tid}/peaks")[0] == 200)
        step("export the approved pieces", jcall("POST", f"/api/takes/{tid}/export")[0] == 200)
        step("back up now", jcall("POST", "/api/backup", {"force": True})[0] == 200)
        step("status and free the model", jcall("GET", "/api/status")[0] == 200 and jcall("POST", "/api/asr/release")[0] == 200)
        call("GET", f"/api/takes?token={TOKEN}", auth=False)
        for name, args in [("build_dataset", ["-m", "freeform_studio.build_dataset", "--output", str(out), "--out", str(ds), "--include", "approved",
                                              "--allow", "none", "--min-seconds", "0.5"]),
                           ("ack_import_dry_run", ["-m", "freeform_studio.ack_import", str(package), "--output", str(out), "--dry-run"]),
                           ("export_cli", ["-m", "freeform_studio.export", "--output", str(out), "--dry-run"]),
                           ("backup_cli", ["-m", "freeform_studio.backup", "--output", str(out), "--backup-dir", str(bk), "--force"]),
                           ("repair_cli", ["-m", "freeform_studio.repair", "--output", str(out)]),
                           ("models_list", ["-m", "freeform_studio.models", "list"]),
                           ("doctor", ["-m", "freeform_studio.doctor", "--output", str(out), "--backup-dir", str(bk), "--port", str(port)])]:
            r = subprocess.run(traced(name, [sys.executable] + args), cwd=TOOLS, env=env, capture_output=True, text=True, timeout=180)
            step(f"command: {name}", r.returncode in (0, 1), f"exit {r.returncode}")
    finally:
        server.terminate()
        try:
            server.wait(timeout=15)
        except subprocess.TimeoutExpired:
            server.kill()
        server_log.close()

    guard = [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []
    strace = []
    for f in sorted(work.glob("*.strace")):
        strace.extend(parse_strace(f.read_text(errors="replace"), f.stem))
    token_in_server_log = TOKEN in (work / "server.log").read_text(errors="replace").replace(f"?token={TOKEN}", "")
    print(json.dumps({"steps": steps, "guard": guard, "strace": strace, "isolated": isolated, "token_leaked_in_log": token_in_server_log}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
