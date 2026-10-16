# SPDX-License-Identifier: GPL-3.0-or-later
"""The certificate the phone is asked to trust, so that it can fetch the finished voice file over the home network without a warning (plan task VS-3.5, decisions D10 and D16, choices P25).

A phone downloads from a secure web address quietly only if it trusts the certificate. This module makes the two small pieces that allow that, with the `openssl` program the computer
already has (no new library, nothing downloaded):

* **A certificate authority, made once**, kept in the data home under `state/phone-certificate/`. It is restricted by *name constraints* to the addresses of a home network
  (10.x.x.x, 172.16.x.x to 172.31.x.x, 192.168.x.x) and to one name that never exists (`ack-voice-studio.invalid`), so a phone that trusts it cannot be made to trust a web site on the
  internet by anyone, including whoever might one day get hold of the key. Its key never leaves this computer, is owner-only, and is not in a project backup (the `state` area).
* **A certificate for one address, made each time a file is sent** and thrown away afterwards (valid seven days, so a forgotten copy goes stale by itself). It names the one address the
  phone will be sent to, and only that.

Nothing here opens a connection, reads a project or says a word: it makes files, and the front (core/voicefile_flow.py) says what it is doing. A certificate authority that already exists is
never replaced (a replacement would mean installing a new file on every phone), and one that is not what this module made is reported as damaged, never used.
"""
from __future__ import annotations

import ipaddress
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional, Sequence, Tuple

from .paths import DataHome
from .system import System

# The addresses of a home network (RFC 1918). The authority may vouch for these and nothing else: not a public address, not a name.
PRIVATE_RANGES: Tuple[Tuple[str, str], ...] = (("10.0.0.0", "255.0.0.0"), ("172.16.0.0", "255.240.0.0"), ("192.168.0.0", "255.255.0.0"))
NO_SUCH_NAME = "ack-voice-studio.invalid"           # `.invalid` can never exist on the internet: it is the one name the authority may vouch for, so that it may vouch for no real name
AUTHORITY_DAYS = 730                                # two years; the person is told before it ends, and a new one has to be put on the phone again
LEAF_DAYS = 7
WARN_DAYS = 30
KEY_FILE = "authority.key"
CERT_FILE = "ack-voice-studio-phone-certificate.crt"        # the file the person copies to the phone; it holds no secret
OPENSSL_TIMEOUT = 60.0

ERROR_CODES = ("no_openssl", "openssl_failed", "not_private", "exists", "absent", "damaged", "expired", "folder")

ABSENT, OK, EXPIRING, EXPIRED, DAMAGED = "absent", "ok", "expiring", "expired", "damaged"
STATES = (ABSENT, OK, EXPIRING, EXPIRED, DAMAGED)


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _utc(now: Optional[datetime]) -> datetime:
    """A clock reading as a plain UTC time: the clock of this computer when none is given, and a time that carries its zone (the other commands pass one) converted."""
    if now is None:
        return utc_now()
    return now.astimezone(timezone.utc).replace(tzinfo=None) if now.tzinfo is not None else now


class PhoneCertError(Exception):
    def __init__(self, code: str, detail: str = ""):
        super().__init__(code + (": " + detail if detail else ""))
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class Authority:
    state: str                                      # one of STATES
    certificate: str                                # the file for the phone ("" when there is none)
    expires: Optional[datetime]                     # UTC, None when it could not be read
    days_left: Optional[int]


def folder(home: DataHome) -> str:
    return home.state + "/phone-certificate"


def certificate_path(home: DataHome) -> str:
    return folder(home) + "/" + CERT_FILE


def key_path(home: DataHome) -> str:
    return folder(home) + "/" + KEY_FILE


def is_private_address(address: str, ranges: Sequence[Tuple[str, str]] = PRIVATE_RANGES) -> bool:
    """True for a single IPv4 address inside one of the ranges. Anything else (a name, a network, IPv6, a leading zero, a space) is not an address this module will make a certificate for."""
    if not isinstance(address, str):
        return False
    try:
        ip = ipaddress.IPv4Address(address)                 # Python 3.10 and later refuse padding, a mask, a scope, a leading zero ("192.168.001.005") and anything that is not four plain numbers
    except ValueError:
        return False
    return any(ip in ipaddress.IPv4Network("%s/%s" % (net, mask)) for net, mask in ranges)


def _constraints(ranges: Sequence[Tuple[str, str]]) -> str:
    return ",".join(["permitted;IP:%s/%s" % pair for pair in ranges] + ["permitted;DNS:" + NO_SUCH_NAME])


def _require_openssl(system: System) -> str:
    found = system.which("openssl")
    if not found:
        raise PhoneCertError("no_openssl")
    return found


def _openssl(system: System, argv: Sequence[str], cwd: Optional[str] = None) -> str:
    done = system.run([_require_openssl(system)] + list(argv), timeout=OPENSSL_TIMEOUT, cwd=cwd)
    if done is None or done.returncode != 0:
        detail = ""
        if done is not None:
            detail = next((line.strip() for line in (done.stderr + "\n" + done.stdout).splitlines() if line.strip()), "")
        raise PhoneCertError("openssl_failed", detail[:200])
    return done.stdout


def _read_end(system: System, crt: str) -> Optional[datetime]:
    out = _openssl(system, ["x509", "-in", crt, "-noout", "-enddate"])
    prefix = "notAfter="
    line = next((l for l in out.splitlines() if l.startswith(prefix)), "")
    try:
        return datetime.strptime(line[len(prefix):].strip(), "%b %d %H:%M:%S %Y GMT")
    except ValueError:
        return None


def status(home: DataHome, system: System, now: Optional[datetime] = None, ranges: Sequence[Tuple[str, str]] = PRIVATE_RANGES) -> Authority:
    """Whether there is an authority, and whether it can be used. Looks only. `damaged` covers every way the files can be something other than what `make_authority` wrote: a missing half, a key
    that is not the certificate's, a certificate that is not an authority restricted to exactly these ranges, or one that cannot be read."""
    crt, key = certificate_path(home), key_path(home)
    if not system.exists(crt) and not system.exists(key):
        return Authority(ABSENT, "", None, None)
    if not system.exists(crt) or not system.exists(key):
        return Authority(DAMAGED, crt if system.exists(crt) else "", None, None)
    try:
        text = _openssl(system, ["x509", "-in", crt, "-noout", "-text"])
        pub_from_cert = _openssl(system, ["x509", "-in", crt, "-noout", "-pubkey"])
        pub_from_key = _openssl(system, ["pkey", "-in", key, "-pubout"])
        ends = _read_end(system, crt)
    except PhoneCertError as error:
        if error.code == "no_openssl":
            raise
        return Authority(DAMAGED, crt, None, None)
    wanted = ["IP:%s/%s" % pair for pair in ranges] + ["DNS:" + NO_SUCH_NAME]
    constrained = "Name Constraints: critical" in text and all(w in text for w in wanted) and "CA:TRUE" in text and text.count("IP:") == len(ranges) and text.count("DNS:") == 1
    if not pub_from_cert.strip() or pub_from_cert.strip() != pub_from_key.strip() or not constrained or ends is None:
        return Authority(DAMAGED, crt, ends, None)
    now = _utc(now)
    if ends <= now:
        return Authority(EXPIRED, crt, ends, 0)
    return Authority(EXPIRING if ends - now <= timedelta(days=WARN_DAYS) else OK, crt, ends, (ends - now).days)


def make_authority(home: DataHome, system: System, now: Optional[datetime] = None, ranges: Sequence[Tuple[str, str]] = PRIVATE_RANGES) -> Authority:
    """Make the authority, once. Refuses when anything is already in the folder, whatever it is: nothing is replaced and nothing is removed here (a replacement has to be a decision the person
    makes, because every phone that trusted the old one would have to be given the new file)."""
    where = folder(home)
    _require_openssl(system)                                # before anything is made: a computer without it is told so and nothing is left behind
    if system.exists(certificate_path(home)) or system.exists(key_path(home)):
        raise PhoneCertError("exists")
    try:
        existed = os.path.isdir(where)
        os.makedirs(where, mode=0o700, exist_ok=True)
        os.chmod(where, 0o700)
        stamp = _utc(now).strftime("%Y-%m-%d")
        _openssl(system, ["req", "-x509", "-newkey", "ec", "-pkeyopt", "ec_paramgen_curve:prime256v1", "-nodes", "-keyout", KEY_FILE, "-out", CERT_FILE, "-days", str(AUTHORITY_DAYS),
                          "-subj", "/O=ACK Voice Studio/CN=ACK Voice Studio phone certificate %s" % stamp,
                          "-addext", "basicConstraints=critical,CA:TRUE,pathlen:0", "-addext", "keyUsage=critical,keyCertSign,cRLSign", "-addext", "subjectKeyIdentifier=hash",
                          "-addext", "nameConstraints=critical," + _constraints(ranges)], cwd=where)
        os.chmod(key_path(home), 0o600)
        os.chmod(certificate_path(home), 0o644)
    except OSError:
        raise PhoneCertError("folder")
    except PhoneCertError:
        for name in (KEY_FILE, CERT_FILE):                  # a half-made pair is not left behind: it would read as damaged and block the next try
            try:
                os.remove(where + "/" + name)
            except OSError:
                pass
        if not existed:
            try:
                os.rmdir(where)
            except OSError:
                pass
        raise
    return status(home, system, now, ranges)


@dataclass(frozen=True)
class Leaf:
    certificate: str                                # the certificate for the one address (the phone already holds the authority's)
    key: str


def issue_leaf(home: DataHome, system: System, address: str, workdir: str, ranges: Sequence[Tuple[str, str]] = PRIVATE_RANGES) -> Leaf:
    """A certificate for `address`, made in `workdir` (the caller's own folder, removed by the caller). Refuses an address that is not a home-network address before anything is made,
    and uses only an authority that `status` calls usable."""
    if not is_private_address(address, ranges):
        raise PhoneCertError("not_private")
    ca = status(home, system, ranges=ranges)
    if ca.state == ABSENT:
        raise PhoneCertError("absent")
    if ca.state == DAMAGED:
        raise PhoneCertError("damaged")
    if ca.state == EXPIRED:
        raise PhoneCertError("expired")
    try:
        with open(workdir + "/extensions.cnf", "w", encoding="utf-8") as handle:
            handle.write("[v3]\nbasicConstraints=critical,CA:FALSE\nkeyUsage=critical,digitalSignature\nextendedKeyUsage=serverAuth\nsubjectAltName=IP:%s\n"
                         "subjectKeyIdentifier=hash\nauthorityKeyIdentifier=keyid\n" % address)
    except OSError:
        raise PhoneCertError("folder")
    _openssl(system, ["req", "-new", "-newkey", "ec", "-pkeyopt", "ec_paramgen_curve:prime256v1", "-nodes", "-keyout", "leaf.key", "-out", "leaf.csr", "-subj", "/O=ACK Voice Studio one-time send"],
             cwd=workdir)
    _openssl(system, ["x509", "-req", "-in", "leaf.csr", "-CA", certificate_path(home), "-CAkey", key_path(home), "-CAcreateserial", "-CAserial", "serial", "-out", "leaf.crt",
                      "-days", str(LEAF_DAYS), "-extfile", "extensions.cnf", "-extensions", "v3"], cwd=workdir)
    try:
        os.chmod(workdir + "/leaf.key", 0o600)
    except OSError:
        raise PhoneCertError("folder")
    _openssl(system, ["verify", "-CAfile", certificate_path(home), "-purpose", "sslserver", workdir + "/leaf.crt"], cwd=workdir)      # what was made is checked before it is used
    return Leaf(workdir + "/leaf.crt", workdir + "/leaf.key")


def new_workdir(home: DataHome) -> str:
    """A private folder for one send's certificate, inside the authority's own folder (so that it is owner-only and in one known place). The caller removes it."""
    try:
        os.makedirs(folder(home), mode=0o700, exist_ok=True)
        return tempfile.mkdtemp(prefix="send-", dir=folder(home))
    except OSError:
        raise PhoneCertError("folder")
