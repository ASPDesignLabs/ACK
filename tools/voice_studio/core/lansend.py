# SPDX-License-Identifier: GPL-3.0-or-later
"""Hand one file to a phone on the same home network, once, over a secure connection (plan task VS-5.1, decision D10, choices P25).

This is the one place in the tool that *listens* for a connection, and so the one place the rules are strictest. A person starts it on purpose, after being shown what it will do and being
asked (core/voicefile_flow.py), and it ends by itself. While it runs:

* It listens on **one address, a home-network address** (10.x, 172.16-31.x or 192.168.x) given to it, never on every address and never on a public one, and refuses to start otherwise.
* It speaks **only secure connections** (TLS 1.2 or newer) with the certificate made for that one address (core/phonecert.py). A device that does not trust the certificate gets no file; it
  is counted so that the person can be told the certificate has not been put on the phone.
* It serves **exactly one file**, at a web address that holds a random token (128 bits) and the file's name. Any other request, whatever it asks for, gets the same short "not found".
* It ends when the file has been **sent completely once**, when the time runs out (ten minutes by default), when the person stops it, or after a dozen requests that did not ask for the file.
  A transfer that breaks half way does not end it: the phone may ask again until the time is up.
* It **dials nothing and looks nothing up**: no connection is opened from here, no name is resolved, and the file is read from the disk and written to the one connection and nowhere else.
  `tests/test_vs_network_rules.py` holds this file to that by reading it.

Nothing here says a word or knows what a voice file is: it sends the bytes of the file it is given.
"""
from __future__ import annotations

import errno
import os
import re
import secrets
import socket
import ssl
import stat
import time
from dataclasses import dataclass
from typing import Callable, Optional, Sequence, Tuple

from . import phonecert

DEFAULT_PORT = 8443
MINUTES = 10
TOKEN_BYTES = 16                                    # 128 bits
MAX_STRANGERS = 12                                  # requests that did not ask for the file, after which it stops listening
CHUNK = 64 * 1024
LISTEN_POLL_SECONDS = 0.25                          # how often the listener looks at the clock and at whether it was stopped
REQUEST_SECONDS = 5.0                               # a connection that has not asked for anything in this time is dropped
SEND_SECONDS = 60.0                                 # a phone that takes no data for this long while the file is going to it is let go
MAX_REQUEST_BYTES = 8192
SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}\Z")

ERROR_CODES = ("not_private", "bad_port", "bad_name", "no_file", "in_use", "cannot_listen", "bad_certificate")

DELIVERED, TIMED_OUT, STOPPED, TOO_MANY = "delivered", "timed_out", "stopped", "too_many"
OUTCOMES = (DELIVERED, TIMED_OUT, STOPPED, TOO_MANY)


class SendError(Exception):
    def __init__(self, code: str, detail: str = ""):
        super().__init__(code + (": " + detail if detail else ""))
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class SendResult:
    outcome: str                                    # one of OUTCOMES
    bytes_sent: int                                 # bytes of the file written to the phone in the last (or the complete) transfer
    attempts: int                                   # times the file was started
    untrusted: int                                  # connections that did not get as far as a request because the device would not trust the certificate
    strangers: int                                  # requests that did not ask for the file


def new_token() -> str:
    return secrets.token_urlsafe(TOKEN_BYTES)


def address_of(address: str, port: int, token: str, name: str) -> str:
    """The web address the phone is sent to."""
    return "https://%s:%d/%s/%s" % (address, port, token, name)


def _check(address: str, port: int, name: str, ranges: Sequence[Tuple[str, str]]) -> None:
    if not phonecert.is_private_address(address, ranges):
        raise SendError("not_private")
    if not isinstance(port, int) or isinstance(port, bool) or not (port == 0 or 1024 <= port <= 65535):
        raise SendError("bad_port")
    if not SAFE_NAME.match(name):
        raise SendError("bad_name")


def _open_file(path: str) -> Tuple[int, int]:
    """(file descriptor, size) of a plain file, opened without following a link."""
    try:
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    except OSError:
        raise SendError("no_file")
    try:
        info = os.fstat(fd)
    except OSError:
        os.close(fd)
        raise SendError("no_file")
    if not stat.S_ISREG(info.st_mode) or info.st_size <= 0:
        os.close(fd)
        raise SendError("no_file")
    return fd, info.st_size


def _read_request(connection: ssl.SSLSocket) -> Optional[Tuple[str, str]]:
    """(method, path) from the request line, after reading to the end of the headers; None when it is not a request this server understands."""
    data = b""
    while b"\r\n\r\n" not in data:
        if len(data) > MAX_REQUEST_BYTES:
            return None
        piece = connection.recv(2048)
        if not piece:
            return None
        data += piece
    first = data.split(b"\r\n", 1)[0].decode("latin-1")
    parts = first.split(" ")
    if len(parts) != 3 or not parts[2].startswith("HTTP/1."):
        return None
    return parts[0], parts[1]


def _reply(connection: ssl.SSLSocket, status: str, headers: Sequence[Tuple[str, str]], body: bytes = b"") -> None:
    lines = ["HTTP/1.1 " + status] + ["%s: %s" % h for h in headers] + ["Connection: close", "", ""]
    connection.sendall("\r\n".join(lines).encode("latin-1") + body)


def serve_once(path: str, name: str, address: str, port: int, certificate: str, key: str, token: str, *, minutes: float = MINUTES, on_event: Callable[..., None] = lambda *a, **k: None,
               should_stop: Callable[[], bool] = lambda: False, clock: Callable[[], float] = time.monotonic, ranges: Sequence[Tuple[str, str]] = phonecert.PRIVATE_RANGES) -> SendResult:
    """Listen on `address:port` and give the file at `path` (shown to the phone as `name`) to the first device that asks for `/<token>/<name>` and takes all of it.

    `on_event(kind, **facts)` is told: `listening` (port), `untrusted`, `stranger`, `sending` (size), `interrupted`, and the end. Never raises for what a remote device does; raises SendError for what
    is wrong before it starts (an address that is not a home-network address, a port, a name, a file that is not there, a port already in use, a certificate that will not load)."""
    _check(address, port, name, ranges)
    fd, size = _open_file(path)
    try:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        try:
            context.load_cert_chain(certificate, key)
        except (ssl.SSLError, OSError):
            raise SendError("bad_certificate")
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                listener.bind((address, port))
            except OSError as error:
                if error.errno in (errno.EADDRINUSE, 48, 10048):          # 48 and 10048: the same refusal on other systems
                    raise SendError("in_use")
                raise SendError("cannot_listen", (error.strerror or "")[:100])
            listener.listen(4)
            listener.settimeout(LISTEN_POLL_SECONDS)
            on_event("listening", port=listener.getsockname()[1])
            return _loop(listener, context, fd, size, name, token, minutes, on_event, should_stop, clock)
        finally:
            listener.close()
    finally:
        os.close(fd)


def _loop(listener: socket.socket, context: ssl.SSLContext, fd: int, size: int, name: str, token: str, minutes: float, on_event: Callable[..., None],
          should_stop: Callable[[], bool], clock: Callable[[], float]) -> SendResult:
    wanted = "/%s/%s" % (token, name)
    deadline = clock() + minutes * 60
    attempts = untrusted = strangers = sent = 0
    told_untrusted = False
    while True:
        if should_stop():
            return SendResult(STOPPED, sent, attempts, untrusted, strangers)
        if clock() >= deadline:
            return SendResult(TIMED_OUT, sent, attempts, untrusted, strangers)
        try:
            raw, _peer = listener.accept()
        except socket.timeout:
            continue
        except OSError:
            continue
        raw.settimeout(REQUEST_SECONDS)
        try:
            connection = context.wrap_socket(raw, server_side=True)
        except (ssl.SSLError, OSError):
            raw.close()
            untrusted += 1
            if not told_untrusted:
                told_untrusted = True
                on_event("untrusted")
            continue
        try:
            request = _read_request(connection)
            if request is not None and request[1] == wanted and request[0] in ("GET", "HEAD"):
                headers = [("Content-Type", "application/zip"), ("Content-Length", str(size)), ("Content-Disposition", 'attachment; filename="%s"' % name), ("Cache-Control", "no-store"),
                           ("X-Content-Type-Options", "nosniff")]
                if request[0] == "HEAD":
                    _reply(connection, "200 OK", headers)
                    continue
                attempts += 1
                sent = 0
                on_event("sending", size=size)
                connection.settimeout(SEND_SECONDS)
                _reply(connection, "200 OK", headers)
                done = _stream(connection, fd, size)
                sent = done
                if done == size:
                    return SendResult(DELIVERED, sent, attempts, untrusted, strangers)
                on_event("interrupted")
                continue
            strangers += 1
            on_event("stranger")
            try:
                _reply(connection, "404 Not Found", [("Content-Type", "text/plain"), ("Content-Length", "10")], b"Not found\n")
            except (ssl.SSLError, OSError):
                pass
            if strangers >= MAX_STRANGERS:
                return SendResult(TOO_MANY, sent, attempts, untrusted, strangers)
        except (ssl.SSLError, OSError):
            continue
        finally:
            try:
                connection.close()
            except OSError:
                pass


def _stream(connection: ssl.SSLSocket, fd: int, size: int) -> int:
    """Write the whole file to the connection; returns how many bytes went (less than `size` when the phone went away)."""
    sent, at = 0, 0
    try:
        while at < size:
            block = os.pread(fd, min(CHUNK, size - at), at)
            if not block:
                break
            connection.sendall(block)
            at += len(block)
            sent = at
    except (ssl.SSLError, OSError):
        return sent
    return sent
