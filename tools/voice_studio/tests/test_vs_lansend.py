# SPDX-License-Identifier: GPL-3.0-or-later
"""Handing one file to a phone once (plan task VS-5.1, decision D10, choices P25). Every test runs a real secure listener on this computer's own loopback address and talks to it with real
clients: what is served, to whom, how often, and when it stops. The certificate is a real one made by the real `openssl` (core/phonecert.py), allowed here for loopback only because the
default ranges (rightly) do not include it."""
import http.client
import os
import shutil
import socket
import ssl
import threading
import time
from pathlib import Path

import pytest

from voice_studio.core import lansend as ls, phonecert as pc
from voice_studio.core.paths import DataHome
from voice_studio.core.system import RealSystem

pytestmark = pytest.mark.skipif(shutil.which("openssl") is None, reason="needs the openssl program")

LOOPBACK = (("127.0.0.0", "255.0.0.0"),)
NAME = "my_voice_backup.zip"


@pytest.fixture(scope="module")
def authority(tmp_path_factory):
    """One authority and one certificate for 127.0.0.1, made once for the whole file (making them is the slow part)."""
    base = tmp_path_factory.mktemp("lansend")
    home = DataHome(str(base / "home"))
    system = RealSystem()
    pc.make_authority(home, system, ranges=LOOPBACK)
    work = base / "work"
    work.mkdir()
    leaf = pc.issue_leaf(home, system, "127.0.0.1", str(work), LOOPBACK)
    return {"ca": pc.certificate_path(home), "certificate": leaf.certificate, "key": leaf.key}


@pytest.fixture
def blob(tmp_path):
    path = tmp_path / NAME
    path.write_bytes(os.urandom(200_000))             # more than three chunks, so a transfer is not one write
    return path


class Server:
    """serve_once in a thread, with its events and its result, and a way to stop it."""

    def __init__(self, authority, path, **kw):
        self.events, self.result, self.error = [], None, None
        self.port = None
        self.token = kw.pop("token", ls.new_token())
        self.name = kw.pop("name", NAME)
        self.stop = threading.Event()
        self._ready = threading.Event()
        kw.setdefault("ranges", LOOPBACK)
        address = kw.pop("address", "127.0.0.1")
        port = kw.pop("port", 0)

        def on_event(kind, **facts):
            self.events.append((kind, facts))
            if kind == "listening":
                self.port = facts["port"]
                self._ready.set()

        def run():
            try:
                self.result = ls.serve_once(str(path), self.name, address, port, authority["certificate"], authority["key"], self.token, on_event=on_event,
                                            should_stop=self.stop.is_set, **kw)
            except ls.SendError as error:
                self.error = error
            finally:
                self._ready.set()
        self.thread = threading.Thread(target=run, daemon=True)
        self.thread.start()
        assert self._ready.wait(10)

    def kinds(self):
        return [k for k, _ in self.events]

    def finish(self, seconds=10):
        self.thread.join(seconds)
        assert not self.thread.is_alive(), "the listener is still going"
        return self.result

    def close(self):
        self.stop.set()
        self.thread.join(5)


@pytest.fixture
def serve(authority, blob):
    made = []

    def start(**kw):
        server = Server(authority, kw.pop("path", blob), **kw)
        made.append(server)
        return server
    yield start
    for server in made:
        server.close()


def trusting(authority):
    return ssl.create_default_context(cafile=authority["ca"])


def get(authority, server, path, method="GET", timeout=10):
    connection = http.client.HTTPSConnection("127.0.0.1", server.port, context=trusting(authority), timeout=timeout)
    try:
        connection.request(method, path)
        response = connection.getresponse()
        return response.status, dict(response.getheaders()), response.read()
    finally:
        connection.close()


def right(server):
    return "/%s/%s" % (server.token, server.name)


# ---------------------------------------------------------------- the one file, once

def test_the_right_address_gets_the_whole_file_with_the_headers_a_phone_needs_and_then_the_listener_ends(authority, serve, blob):
    server = serve()
    status, headers, body = get(authority, server, right(server))
    assert status == 200 and body == blob.read_bytes()
    assert headers["Content-Length"] == str(blob.stat().st_size) and headers["Content-Type"] == "application/zip"
    assert headers["Content-Disposition"] == 'attachment; filename="%s"' % NAME
    assert headers["Cache-Control"] == "no-store" and headers["X-Content-Type-Options"] == "nosniff" and headers["Connection"] == "close"
    result = server.finish()
    assert result == ls.SendResult(ls.DELIVERED, blob.stat().st_size, 1, 0, 0)
    assert server.kinds() == ["listening", "sending"]
    assert server.events[1][1] == {"size": blob.stat().st_size}
    with pytest.raises(OSError):
        socket.create_connection(("127.0.0.1", server.port), timeout=2)


def test_a_second_request_after_the_file_was_sent_gets_nothing(authority, serve):
    server = serve()
    get(authority, server, right(server))
    server.finish()
    with pytest.raises(OSError):
        get(authority, server, right(server))


@pytest.mark.parametrize("path", ["/", "/x", "/{token}", "/{token}/", "/{token}/other.zip", "/{token}/{name}/extra", "/{token}/{name}?x=1", "/{token}/{name}#f", "/{TOKEN}/{name}",
                                  "//{token}/{name}", "/./{token}/{name}", "/{token}/../{token}/{name}", "/%7Btoken%7D/{name}", "/wrong/{name}", "/{token}x/{name}", "/{token}/{NAME}"])
def test_anything_but_the_one_address_gets_the_same_short_not_found_and_the_file_stays_available(authority, serve, blob, path):
    server = serve()
    asked = path.format(token=server.token, TOKEN=server.token.swapcase(), name=NAME, NAME=NAME.upper())
    status, headers, body = get(authority, server, asked)
    assert (status, body) == (404, b"Not found\n") and headers["Content-Length"] == "10" and "Content-Disposition" not in headers
    assert server.thread.is_alive()
    assert get(authority, server, right(server))[2] == blob.read_bytes()
    result = server.finish()
    assert result.outcome == ls.DELIVERED and result.strangers == 1 and server.kinds() == ["listening", "stranger", "sending"]


def test_only_a_get_for_the_file_is_served_and_a_head_sends_the_headers_without_counting_as_the_download(authority, serve, blob):
    server = serve()
    status, headers, body = get(authority, server, right(server), method="HEAD")
    assert status == 200 and body == b"" and headers["Content-Length"] == str(blob.stat().st_size) and server.thread.is_alive()
    for method in ("POST", "PUT", "DELETE", "OPTIONS"):
        status, _, body = get(authority, server, right(server), method=method)
        assert (status, body) == (404, b"Not found\n"), method
    assert server.thread.is_alive()
    assert get(authority, server, right(server))[0] == 200
    result = server.finish()
    assert result.outcome == ls.DELIVERED and result.strangers == 4 and result.attempts == 1


def test_a_dozen_requests_for_something_else_end_the_listening_and_eleven_do_not(authority, serve):
    server = serve()
    for _ in range(ls.MAX_STRANGERS - 1):
        assert get(authority, server, "/nothing")[0] == 404
    assert server.thread.is_alive()
    assert get(authority, server, "/nothing")[0] == 404
    result = server.finish()
    assert result.outcome == ls.TOO_MANY and result.strangers == ls.MAX_STRANGERS == 12 and result.attempts == 0 and result.bytes_sent == 0


def test_a_transfer_that_breaks_half_way_does_not_end_it_and_a_second_try_can_finish(authority, serve, tmp_path):
    big = tmp_path / "big.zip"
    big.write_bytes(os.urandom(12_000_000))
    server = serve(path=big, name="big.zip")
    raw = socket.socket()
    raw.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4096)
    raw.settimeout(10)
    raw.connect(("127.0.0.1", server.port))
    tls = trusting(authority).wrap_socket(raw, server_hostname="127.0.0.1")
    tls.sendall(("GET /%s/big.zip HTTP/1.1\r\nHost: x\r\n\r\n" % server.token).encode())
    got = b""
    while len(got) < 60_000:
        got += tls.recv(8192)
    tls.close()
    deadline = time.time() + 10
    while "interrupted" not in server.kinds() and time.time() < deadline:
        time.sleep(0.05)
    assert "interrupted" in server.kinds() and server.thread.is_alive()
    status, _, body = get(authority, server, "/%s/big.zip" % server.token, timeout=60)
    assert status == 200 and body == big.read_bytes()
    result = server.finish(30)
    assert result.outcome == ls.DELIVERED and result.attempts == 2 and result.bytes_sent == 12_000_000
    assert server.kinds().count("sending") == 2 and server.kinds().count("interrupted") == 1


# ---------------------------------------------------------------- when it ends without a download

def test_it_ends_by_itself_when_the_time_is_up(serve):
    server = serve(minutes=0.01)
    started = time.time()
    result = server.finish()
    assert result == ls.SendResult(ls.TIMED_OUT, 0, 0, 0, 0) and 0.3 < time.time() - started < 5


def test_it_ends_when_it_is_stopped_and_not_before(serve):
    server = serve()
    time.sleep(0.6)
    assert server.thread.is_alive()
    server.stop.set()
    assert server.finish().outcome == ls.STOPPED


def test_the_time_is_read_from_the_clock_it_is_given(serve):
    ticks = iter([0.0, 1.0, 2.0, 100.0, 100.0, 100.0])
    server = serve(minutes=1, clock=lambda: next(ticks, 1000.0))
    assert server.finish().outcome == ls.TIMED_OUT


def test_a_device_that_does_not_trust_the_certificate_is_counted_and_told_once_and_gets_no_file(authority, serve, blob):
    server = serve()
    for _ in range(2):
        with pytest.raises(ssl.SSLError):
            http.client.HTTPSConnection("127.0.0.1", server.port, context=ssl.create_default_context(), timeout=5).request("GET", right(server))
    plain = socket.create_connection(("127.0.0.1", server.port), timeout=5)
    plain.sendall(("GET %s HTTP/1.1\r\n\r\n" % right(server)).encode())
    plain.settimeout(5)
    try:
        assert b"200" not in plain.recv(100)
    except OSError:
        pass
    plain.close()
    assert get(authority, server, right(server))[2] == blob.read_bytes()
    result = server.finish()
    assert result.outcome == ls.DELIVERED and result.untrusted == 3 and result.strangers == 0
    assert server.kinds().count("untrusted") == 1


def test_a_connection_that_sends_nothing_is_dropped_and_does_not_hold_the_listener(authority, serve, blob, monkeypatch):
    monkeypatch.setattr(ls, "REQUEST_SECONDS", 0.5)
    server = serve()
    idle = trusting(authority).wrap_socket(socket.create_connection(("127.0.0.1", server.port), timeout=5), server_hostname="127.0.0.1")
    started = time.time()
    status, _, body = get(authority, server, right(server), timeout=20)
    assert status == 200 and body == blob.read_bytes() and time.time() - started < 5
    idle.close()
    assert server.finish().outcome == ls.DELIVERED


def test_an_oversized_or_broken_request_is_a_stranger_and_gets_the_same_not_found(authority, serve):
    server = serve()
    answers = []
    for payload in (b"GET / HTTP/1.1\r\n" + b"X: " + b"a" * 9000 + b"\r\n\r\n", b"NOT HTTP\r\n\r\n", b"GET /\r\n\r\n", b"GET / FTP/1.0\r\n\r\n"):
        tls = trusting(authority).wrap_socket(socket.create_connection(("127.0.0.1", server.port), timeout=5), server_hostname="127.0.0.1")
        tls.sendall(payload)
        tls.settimeout(5)
        answers.append(tls.recv(200))
        tls.close()
    assert all(a.startswith(b"HTTP/1.1 404 Not Found\r\n") and a.endswith(b"Not found\n") for a in answers), answers
    assert server.thread.is_alive()
    server.close()
    assert server.result.outcome == ls.STOPPED and server.result.strangers == 4 and server.kinds().count("stranger") == 4


# ---------------------------------------------------------------- what it refuses to start

def code_of(authority, path, **kw):
    server = Server.__new__(Server)
    with pytest.raises(ls.SendError) as caught:
        ls.serve_once(str(path), kw.pop("name", NAME), kw.pop("address", "127.0.0.1"), kw.pop("port", 0), authority["certificate"], authority["key"], ls.new_token(),
                      ranges=kw.pop("ranges", LOOPBACK), **kw)
    return caught.value.code


def test_an_address_outside_a_home_network_is_refused_before_anything_is_opened(authority, blob):
    for address in ("127.0.0.1", "0.0.0.0", "8.8.8.8", "", "::", "localhost", "192.168.1.1/24"):
        assert code_of(authority, blob, address=address, ranges=pc.PRIVATE_RANGES) == "not_private", address


@pytest.mark.parametrize("port", [-1, 1, 80, 1023, 65536, 100000, True, False, None, "8443", 8443.0])
def test_a_port_outside_the_unprivileged_range_is_refused(authority, blob, port):
    assert code_of(authority, blob, port=port) == "bad_port"


@pytest.mark.parametrize("name", ["", ".hidden", "-x", "a b", "a/b", "../x", "a\n.zip", "voice.zip\n", "é.zip", "x" * 101, "a;b", "a\\b", 'a".zip'])
def test_a_file_name_that_is_not_plain_is_refused(authority, blob, name):
    assert code_of(authority, blob, name=name) == "bad_name"


def test_the_longest_plain_name_is_accepted(authority, serve):
    server = serve(name="a" * 100)
    assert server.error is None and server.port


def test_a_file_that_is_missing_empty_a_folder_or_a_link_is_refused(authority, tmp_path, blob):
    empty = tmp_path / "empty"
    empty.write_bytes(b"")
    folder = tmp_path / "folder"
    folder.mkdir()
    link = tmp_path / "link.zip"
    link.symlink_to(blob)
    for bad in (tmp_path / "nothing", empty, folder, link):
        assert code_of(authority, bad) == "no_file", bad


def test_a_port_in_use_and_an_address_this_computer_does_not_have_are_told_apart(authority, blob):
    holder = socket.socket()
    holder.bind(("127.0.0.1", 0))
    holder.listen(1)
    try:
        assert code_of(authority, blob, port=holder.getsockname()[1]) == "in_use"
    finally:
        holder.close()
    assert code_of(authority, blob, address="10.254.254.254", ranges=pc.PRIVATE_RANGES + LOOPBACK) == "cannot_listen"


def test_a_certificate_that_will_not_load_is_refused(authority, blob, tmp_path):
    junk = tmp_path / "junk.pem"
    junk.write_text("not a certificate")
    for certificate, key in ((str(junk), authority["key"]), (authority["certificate"], str(junk)), (str(tmp_path / "gone"), authority["key"])):
        with pytest.raises(ls.SendError) as caught:
            ls.serve_once(str(blob), NAME, "127.0.0.1", 0, certificate, key, ls.new_token(), ranges=LOOPBACK)
        assert caught.value.code == "bad_certificate"


def test_it_listens_on_the_one_address_it_was_given_and_on_no_other(authority, serve):
    server = serve()
    with pytest.raises(OSError):
        socket.create_connection(("127.0.0.2", server.port), timeout=2)
    socket.create_connection(("127.0.0.1", server.port), timeout=2).close()


def test_the_file_is_opened_once_and_left_alone_when_the_listener_ends(authority, serve, blob):
    before = blob.read_bytes()
    server = serve(minutes=0.005)
    server.finish()
    assert blob.read_bytes() == before and sorted(p.name for p in blob.parent.iterdir()) == [NAME]
    assert not any(os.readlink("/proc/self/fd/%s" % fd).endswith(NAME) for fd in os.listdir("/proc/self/fd") if os.path.exists("/proc/self/fd/%s" % fd)), "no descriptor on the file is left open"


def test_a_modern_secure_connection_is_what_it_speaks(authority, serve):
    server = serve()
    context = trusting(authority)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    with context.wrap_socket(socket.create_connection(("127.0.0.1", server.port), timeout=5), server_hostname="127.0.0.1") as tls:
        assert tls.version() in ("TLSv1.2", "TLSv1.3")
    old = trusting(authority)
    old.maximum_version = ssl.TLSVersion.TLSv1_2
    with old.wrap_socket(socket.create_connection(("127.0.0.1", server.port), timeout=5), server_hostname="127.0.0.1") as tls:
        assert tls.version() == "TLSv1.2"


# ---------------------------------------------------------------- the address

def test_the_token_is_random_urlsafe_and_one_hundred_and_twenty_eight_bits():
    tokens = {ls.new_token() for _ in range(50)}
    assert len(tokens) == 50 and all(len(t) == 22 and all(c.isalnum() or c in "-_" for c in t) for t in tokens)
    assert ls.TOKEN_BYTES == 16


def test_the_address_the_phone_is_sent_to_has_the_token_before_the_name():
    assert ls.address_of("192.168.1.23", 8443, "TOKEN", NAME) == "https://192.168.1.23:8443/TOKEN/my_voice_backup.zip"
    assert ls.DEFAULT_PORT == 8443 and ls.MINUTES == 10


def test_every_error_code_the_module_can_raise_is_listed():
    import ast
    tree = ast.parse(Path(ls.__file__).read_text())
    raised = {n.args[0].value for n in ast.walk(tree) if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "SendError" and n.args and isinstance(n.args[0], ast.Constant)}
    assert raised <= set(ls.ERROR_CODES)
    assert {"not_private", "bad_port", "bad_name", "no_file", "bad_certificate", "cannot_listen"} <= raised
