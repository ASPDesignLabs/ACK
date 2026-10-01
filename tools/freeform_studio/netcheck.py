# SPDX-License-Identifier: GPL-3.0-or-later
"""Small, dependency-free network and certificate helpers used by the server's startup checks and by `doctor`."""
from __future__ import annotations

import http.client
import re
import socket
import ssl
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

LOOPBACK = ("127.0.0.1", "localhost", "::1")


def lan_ip() -> str:
    """Best-effort address other devices can reach. Opens no connection; UDP connect only picks a route."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("192.0.2.1", 9))
        return s.getsockname()[0]
    except OSError:
        return socket.gethostname()
    finally:
        s.close()


def local_ips() -> List[str]:
    """Every IPv4 address this machine has, best effort."""
    found: List[str] = []
    try:
        out = subprocess.run(["hostname", "-I"], capture_output=True, text=True, timeout=3).stdout.split()
        found.extend(ip for ip in out if re.fullmatch(r"\d+\.\d+\.\d+\.\d+", ip))
    except (OSError, subprocess.SubprocessError):
        pass
    detected = lan_ip()
    if re.fullmatch(r"\d+\.\d+\.\d+\.\d+", detected) and detected not in found:
        found.insert(0, detected)
    return found


def san_info(certfile: Path) -> Dict[str, Any]:
    """{'dns': [...], 'ips': [...], 'not_after': str|None, 'error': str|None} for a PEM certificate."""
    info: Dict[str, Any] = {"dns": [], "ips": [], "not_after": None, "error": None}
    try:
        proc = subprocess.run(["openssl", "x509", "-in", str(certfile), "-noout", "-enddate", "-ext", "subjectAltName"],
                              capture_output=True, text=True, timeout=5)
        if proc.returncode == 0:
            info["dns"] = re.findall(r"DNS:([^,\s]+)", proc.stdout)
            info["ips"] = re.findall(r"IP Address:([0-9a-fA-F:.]+)", proc.stdout)
            m = re.search(r"notAfter=(.+)", proc.stdout)
            info["not_after"] = m.group(1).strip() if m else None
            return info
        info["error"] = (proc.stderr or "openssl could not read the certificate").strip().splitlines()[-1]
        return info
    except (OSError, subprocess.SubprocessError):
        pass
    try:  # no openssl program: fall back to Python's own decoder
        decoded = ssl._ssl._test_decode_cert(str(certfile))  # type: ignore[attr-defined]
        for kind, value in decoded.get("subjectAltName", ()):
            (info["dns"] if kind == "DNS" else info["ips"] if kind == "IP Address" else []).append(value)
        info["not_after"] = decoded.get("notAfter")
    except Exception as e:  # noqa: BLE001 - report whatever went wrong in plain words
        info["error"] = f"could not read the certificate ({type(e).__name__})"
    return info


def pick_advertised_host(detected: str, cert_ips: List[str]) -> Tuple[str, Optional[str]]:
    """Choose the address to show the user. Prefer one the certificate covers, so the phone doesn't see a warning."""
    real = [ip for ip in cert_ips if ip not in ("127.0.0.1", "::1")]
    if not cert_ips or detected in cert_ips:
        return detected, None
    if real:
        return real[0], (f"This computer's address looks like {detected}, but your certificate is for {real[0]}, "
                         f"so the link uses {real[0]}. If that isn't this computer's address, make a new certificate.")
    return detected, (f"Your certificate doesn't cover {detected}, so a phone will show a certificate warning. "
                      f"Make a new one with: mkcert {detected} localhost 127.0.0.1")


def port_state(host: str, port: int) -> str:
    """'free' if we could listen on it, 'in_use' if something already is."""
    s = socket.socket(socket.AF_INET6 if ":" in host else socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind((host, port))
        return "free"
    except OSError:
        return "in_use"
    finally:
        s.close()


def probe(host: str, port: int, tls: bool, timeout: float = 3.0) -> Tuple[bool, str]:
    """GET /healthz. Returns (is_freeform_studio, plain-language detail). Certificates are not verified here."""
    try:
        if tls:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            conn: http.client.HTTPConnection = http.client.HTTPSConnection(host, port, timeout=timeout, context=ctx)
        else:
            conn = http.client.HTTPConnection(host, port, timeout=timeout)
        conn.request("GET", "/healthz")
        resp = conn.getresponse()
        body = resp.read(64).decode("utf-8", "replace").strip()
        conn.close()
        if resp.status == 200 and body == "ok":
            return True, "answered"
        return False, f"something answered with HTTP {resp.status}, but it isn't Freeform Studio"
    except ssl.SSLError as e:
        return False, f"secure connection failed ({e.reason or 'TLS error'}); the server may be plain http, or the reverse"
    except (ConnectionRefusedError, socket.timeout, OSError) as e:
        return False, f"no connection ({type(e).__name__})"


def is_wsl() -> bool:
    try:
        return "microsoft" in Path("/proc/version").read_text().lower()
    except OSError:
        return False


def wsl_networking_mode() -> Optional[str]:
    try:
        out = subprocess.run(["wslinfo", "--networking-mode"], capture_output=True, text=True, timeout=3)
        return out.stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def firewall_command(port: int) -> str:
    return (f'New-NetFirewallRule -DisplayName "Freeform Studio {port}" -Direction Inbound -Protocol TCP '
            f'-LocalPort {port} -Action Allow -Profile Private')


def find_cert_pair(folder: Path) -> Optional[Tuple[Path, Path]]:
    """The newest matching (certificate, key) pair in a folder, e.g. mkcert's `192.168.1.2+2.pem` + `192.168.1.2+2-key.pem`."""
    pairs = []
    for key in Path(folder).expanduser().glob("*-key.pem"):
        cert = key.with_name(key.name[: -len("-key.pem")] + ".pem")
        if cert.is_file():
            pairs.append((max(cert.stat().st_mtime, key.stat().st_mtime), cert, key))
    if not pairs:
        return None
    _t, cert, key = max(pairs)
    return cert, key
