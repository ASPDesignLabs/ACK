"""Checks each link in the chain between your phone and this program, and says which one is broken.

    python -m freeform_studio.doctor --port 8001 --certfile <cert.pem> --keyfile <key.pem>

Run it in a second terminal while the server is running (or before starting it). Changes nothing.
"""
from __future__ import annotations

import argparse
import importlib
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

from . import backup, health, netcheck, repair

Line = Tuple[str, str]  # (label, text) where label is OK / PROBLEM / NOTE


def _has_module(name: str) -> bool:
    try:
        importlib.import_module(name)
        return True
    except ImportError:
        return False


def _has_ffmpeg() -> bool:
    return shutil.which("ffmpeg") is not None


def check(args: argparse.Namespace) -> Tuple[List[Line], List[str], bool]:
    lines: List[Line] = []
    fixes: List[str] = []
    server_up = False

    def add(label: str, text: str, fix: str = "") -> None:
        lines.append((label, text))
        if label == "PROBLEM":
            fixes.append(fix or text)

    # 1. the program itself
    add("OK" if sys.version_info >= (3, 10) else "PROBLEM", f"Python {sys.version_info.major}.{sys.version_info.minor}",
        "Python 3.10 or newer is required.")
    for mod in ("quart", "hypercorn", "numpy", "faster_whisper"):
        if _has_module(mod):
            add("OK", f"package {mod} is installed")
        else:
            add("PROBLEM", f"package {mod} is missing",
                "Install the requirements: pip install -r freeform_studio/requirements.txt (with the venv active).")
    add("OK" if _has_ffmpeg() else "PROBLEM", "ffmpeg is on the PATH" if _has_ffmpeg() else "ffmpeg is missing",
        "Install ffmpeg: sudo apt install ffmpeg")

    out = Path(args.output).expanduser()
    add("OK" if out.is_dir() else "PROBLEM", f"recordings folder {out}" + ("" if out.is_dir() else " does not exist"),
        f"The folder {out} doesn't exist. Point --output at piper-recording-studio's output folder.")

    # 1b. room, backups, and anything waiting to be rebuilt (read straight from the folders: no server needed)
    if out.is_dir():
        floor = getattr(args, "min_free_mb", 500)
        d = health.disk_status(out, floor, 3000)   # the server's own warning level
        if not d["known"]:
            add("NOTE", "free disk space could not be measured")
        elif d["critical"]:
            add("PROBLEM", f"only {d['free_mb']} MB of disk space is free, so new audio is refused",
                f"Free some disk space. The server refuses new audio below {floor} MB free (what you record stays on the phone until then).")
        elif d["low"]:
            add("NOTE", f"{d['free_mb'] / 1024:.1f} GB of disk space is free (about {d['hours_left']} hours of recording); free some soon")
        else:
            add("OK", f"{d['free_mb'] / 1024:.0f} GB of disk space is free")
        code = getattr(args, "code", "en-US")
        have = bool(backup.collect(out, code))
        found = backup.list_backups(Path(getattr(args, "backup_dir", backup.DEFAULT_DIR)).expanduser(), code)
        if not have:
            add("NOTE", "no recordings yet, so nothing to back up")
        elif not found:
            add("NOTE", "you have recordings but no backup yet. Run: python -m freeform_studio.backup")
        else:
            last = found[0]
            age_days = (datetime.now() - datetime.fromisoformat(last["created"])).days
            add("OK" if age_days <= 7 else "NOTE", f"last backup {last['created'][:16].replace('T', ' ')} ({len(found)} kept)"
                + ("" if age_days <= 7 else f", {age_days} days ago: consider python -m freeform_studio.backup"))
        pending = [d_.name for d_ in (out / "_freeform" / code / "takes").glob("t*") if d_.is_dir() and repair.needs_repair(d_)] \
            if (out / "_freeform" / code / "takes").is_dir() else []
        if pending:
            add("NOTE", f"{len(pending)} recording(s) are missing their decoded audio (the server rebuilds it at startup, "
                        "or run: python -m freeform_studio.repair)")

    # 2. the certificate (needed for the phone's microphone)
    tls = bool(args.certfile)
    cert_ips: List[str] = []
    if tls:
        cert, key = Path(args.certfile).expanduser(), Path(args.keyfile or "").expanduser()
        for label, p in (("certificate file", cert), ("key file", key)):
            if p.is_file():
                add("OK", f"{label} found")
            else:
                add("PROBLEM", f"{label} not found: {p}",
                    f"The {label} '{p}' doesn't exist. Check the path (did a placeholder like <your-ip> get left in?) "
                    f"with: ls ~/piper-recording-studio/certs")
        if cert.is_file():
            info = netcheck.san_info(cert)
            if info["error"]:
                add("PROBLEM", f"certificate unreadable: {info['error']}", "The certificate file isn't valid; make a new one with mkcert.")
            else:
                cert_ips = info["ips"]
                add("OK", f"certificate is valid for: {', '.join(info['dns'] + info['ips']) or '(nothing listed)'}")
                add("NOTE", f"certificate expires {info['not_after']}")
                mine = netcheck.local_ips()
                covered = [ip for ip in mine if ip in cert_ips]
                if covered:
                    add("OK", f"this computer's address {covered[0]} is covered by the certificate")
                elif mine:
                    add("PROBLEM", f"this computer's addresses ({', '.join(mine)}) are not in the certificate",
                        f"Make a new certificate for the address your phone uses: mkcert {mine[0]} localhost 127.0.0.1")
    else:
        add("NOTE", "no certificate given: fine for testing on this computer, but the phone microphone needs https")

    # 3. is the server up, and reachable the ways a phone would reach it
    port = args.port
    scheme = "https" if tls else "http"
    ok_local, detail = netcheck.probe("127.0.0.1", port, tls)
    if ok_local:
        server_up = True
        add("OK", f"the server is running and answers on this computer ({scheme}://localhost:{port})")
        mine = [ip for ip in netcheck.local_ips() if ip != "127.0.0.1"]
        for ip in mine[:2]:
            ok_lan, d = netcheck.probe(ip, port, tls)
            if ok_lan:
                add("OK", f"it also answers on {ip}:{port}, so it is listening on the network, not just locally")
            else:
                add("PROBLEM", f"it does not answer on {ip}:{port} ({d})",
                    "The server is only listening on this computer. Start it with --host 0.0.0.0")
    else:
        state = netcheck.port_state("0.0.0.0", port)
        if state == "in_use":
            add("PROBLEM", f"port {port} is taken by something else ({detail})",
                f"Another program is using port {port}. Pick another with --port, or stop that program.")
        else:
            add("NOTE", f"the server is not running on port {port} right now ({detail}). Start it in another terminal, then run this again.")

    # 4. the parts only Windows can fix
    if netcheck.is_wsl():
        mode = netcheck.wsl_networking_mode()
        add("OK" if mode == "mirrored" else "NOTE", f"WSL networking mode: {mode or 'unknown'}"
            + ("" if mode == "mirrored" else " (a phone can only reach WSL directly in 'mirrored' mode)"))
        lines.append(("NOTE", "If the phone still can't open the link but everything above is OK, Windows Firewall is blocking "
                              f"port {port}. Run this in an ADMINISTRATOR PowerShell (the same kind of rule you made for port 8000):"))
        lines.append(("CMD", netcheck.firewall_command(port)))
        lines.append(("NOTE", "In mirrored mode, Windows may also need to let the network reach WSL. If that still fails, try:"))
        lines.append(("CMD", "Set-NetFirewallHyperVVMSetting -Name '{40E0AC32-46A5-438A-A0B2-2B479E8F2E90}' -DefaultInboundAction Allow"))
        if tls:
            lines.append(("NOTE", "On THIS PC, Chrome will warn about the certificate because only your phone (and WSL) trust "
                                  "mkcert's authority. Click Advanced, then Proceed. That is safe on your own network."))

    # 5. the link to use
    token_file = out / "_freeform" / "token"
    token = token_file.read_text().strip() if token_file.is_file() else ""
    host, warn = netcheck.pick_advertised_host(netcheck.lan_ip(), cert_ips)
    if warn:
        lines.append(("NOTE", warn))
    q = f"/?token={token}" if token else "/"
    lines.append(("NOTE", f"Link for your phone:  {scheme}://{host}:{port}{q}"))
    lines.append(("NOTE", f"Link for this PC:     {scheme}://localhost:{port}{q}"))
    if not token:
        lines.append(("NOTE", "No access token exists yet; it is created the first time the server starts."))
    return lines, fixes, server_up


def main(argv: Optional[list] = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--output", default="~/piper-recording-studio/output")
    p.add_argument("--code", default="en-US")
    p.add_argument("--backup-dir", default=backup.DEFAULT_DIR, help="where your backups are kept (default: %(default)s)")
    p.add_argument("--min-free-mb", type=int, default=500, help="the free-space floor the server was started with (default: %(default)s)")
    p.add_argument("--port", type=int, default=8001)
    p.add_argument("--certs-dir", help="folder holding your mkcert certificate + key")
    p.add_argument("--certfile")
    p.add_argument("--keyfile")
    args = p.parse_args(argv)
    if args.certs_dir and not args.certfile:
        pair = netcheck.find_cert_pair(Path(args.certs_dir))
        if pair:
            args.certfile, args.keyfile = str(pair[0]), str(pair[1])
        else:
            print(f"\n  PROBLEM no certificate pair found in {args.certs_dir}. It should contain files like "
                  f"192.168.1.2+2.pem and 192.168.1.2+2-key.pem. List it with:  ls {args.certs_dir}\n")
            return 1
    if bool(args.certfile) != bool(args.keyfile):
        p.error("--certfile and --keyfile go together")
    lines, fixes, server_up = check(args)
    print()
    for label, text in lines:
        print(f"    {text}" if label == "CMD" else f"  {label:<8}{text}")
    print()
    if fixes:
        if len(fixes) == 1:
            print(f"FIX THIS: {fixes[0]}\n")
        else:
            print("FIX THESE, IN ORDER:")
            for i, f in enumerate(fixes, 1):
                print(f"  {i}. {f}")
            print()
        return 1
    if server_up:
        print("Nothing wrong found on this computer. If the phone still can't open the link, the block is between "
              "the phone and this PC: see the Windows Firewall notes above.\n")
    else:
        print("Everything checked out, but the server isn't running yet. Start it, then run this again.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
