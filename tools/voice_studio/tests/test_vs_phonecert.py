# SPDX-License-Identifier: GPL-3.0-or-later
"""The certificate for the phone (plan task VS-3.5, decision D16, choices P25). The proofs are made with the real `openssl` program: a certificate for a home-network address passes, one for
a public address or a name is refused by the authority itself (not only by this module), the keys are owner-only, and an authority is never replaced."""
import os
import shutil
import ssl
import stat
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from vs_fakes import FakeSystem
from voice_studio.core import phonecert as pc
from voice_studio.core.paths import DataHome
from voice_studio.core.system import CommandResult, RealSystem

pytestmark = pytest.mark.skipif(shutil.which("openssl") is None, reason="needs the openssl program")


@pytest.fixture
def home(tmp_path):
    return DataHome(str(tmp_path / "home"))


@pytest.fixture
def system():
    return RealSystem()


def openssl(*argv, cwd=None):
    return subprocess.run(["openssl"] + list(argv), capture_output=True, text=True, cwd=cwd)


def code_of(fn, *a, **kw):
    with pytest.raises(pc.PhoneCertError) as caught:
        fn(*a, **kw)
    return caught.value.code


def made(home, system, **kw):
    return pc.make_authority(home, system, **kw)


def mode(path):
    return stat.S_IMODE(os.stat(path).st_mode)


# ---------------------------------------------------------------- which addresses count as a home network

@pytest.mark.parametrize("address", ["10.0.0.1", "10.255.255.254", "172.16.0.1", "172.31.255.254", "192.168.0.1", "192.168.255.254", "192.168.1.23"])
def test_home_network_addresses_are_accepted(address):
    assert pc.is_private_address(address)


@pytest.mark.parametrize("address", ["8.8.8.8", "11.0.0.1", "9.255.255.255", "172.15.255.255", "172.32.0.1", "192.167.255.255", "192.169.0.1", "127.0.0.1", "0.0.0.0", "169.254.1.1", "100.64.0.1",
                                     "::1", "fd00::1", "fe80::1", "", " 192.168.1.1", "192.168.1.1 ", "192.168.1.1\n", "192.168.1", "192.168.1.1.1", "192.168.001.001", "192.168.1.256",
                                     "192.168.1.1/24", "example.com", "localhost", "192.168.1.1:8443", "０.0.0.0", "+192.168.1.1", None, 3232235777])
def test_everything_else_is_refused(address):
    assert not pc.is_private_address(address)


def test_the_ranges_can_be_widened_only_by_being_asked_to():
    assert not pc.is_private_address("127.0.0.1")
    assert pc.is_private_address("127.0.0.1", (("127.0.0.0", "255.0.0.0"),))
    assert not pc.is_private_address("192.168.1.1", (("127.0.0.0", "255.0.0.0"),))


# ---------------------------------------------------------------- the authority

def test_with_nothing_made_there_is_no_authority_and_nothing_is_created(home, system):
    got = pc.status(home, system)
    assert got.state == pc.ABSENT and got.certificate == "" and got.expires is None and got.days_left is None
    assert not os.path.exists(pc.folder(home))


def test_making_the_authority_writes_two_files_and_keeps_the_key_owner_only(home, system):
    got = made(home, system, now=datetime(2026, 10, 16))
    assert got.state == pc.OK and got.certificate == pc.certificate_path(home)
    assert sorted(os.listdir(pc.folder(home))) == [pc.CERT_FILE, pc.KEY_FILE]
    assert mode(pc.key_path(home)) == 0o600 and mode(pc.folder(home)) == 0o700 and mode(pc.certificate_path(home)) == 0o644
    assert pc.folder(home).startswith(home.state + "/")


def test_the_authority_lasts_two_years_and_is_named_with_its_day(home, system):
    got = made(home, system)
    assert 729 <= got.days_left <= 730 and abs((got.expires - (pc.utc_now() + timedelta(days=730))).total_seconds()) < 120
    subject = openssl("x509", "-in", pc.certificate_path(home), "-noout", "-subject").stdout
    assert "ACK Voice Studio phone certificate" in subject and pc.utc_now().strftime("%Y-%m-%d") in subject


def test_the_authority_is_restricted_to_home_network_addresses_and_one_name_that_cannot_exist(home, system):
    made(home, system)
    text = openssl("x509", "-in", pc.certificate_path(home), "-noout", "-text").stdout
    assert "Name Constraints: critical" in text and "CA:TRUE, pathlen:0" in text and "Certificate Sign" in text
    for pair in pc.PRIVATE_RANGES:
        assert "IP:%s/%s" % pair in text
    assert "DNS:ack-voice-studio.invalid" in text and "Excluded" not in text and text.count("IP:") == 3 and text.count("DNS:") == 1
    assert "Public Key Algorithm: id-ecPublicKey" in text and "prime256v1" in text


def test_the_authority_is_named_for_the_day_it_was_made(home, system):
    made(home, system, now=datetime(2026, 10, 16, 23, 30))
    out = openssl("x509", "-in", pc.certificate_path(home), "-noout", "-subject").stdout
    assert "O = ACK Voice Studio" in out and "CN = ACK Voice Studio phone certificate 2026-10-16" in out and "%" not in out


def test_an_authority_that_exists_is_never_replaced(home, system):
    made(home, system)
    before = {n: Path(pc.folder(home), n).read_bytes() for n in os.listdir(pc.folder(home))}
    assert code_of(pc.make_authority, home, system) == "exists"
    assert {n: Path(pc.folder(home), n).read_bytes() for n in os.listdir(pc.folder(home))} == before


@pytest.mark.parametrize("leftover", [pc.KEY_FILE, pc.CERT_FILE])
def test_one_leftover_file_also_stops_a_new_authority_and_reads_as_damaged(home, system, leftover):
    os.makedirs(pc.folder(home))
    Path(pc.folder(home), leftover).write_text("not what this tool made")
    assert code_of(pc.make_authority, home, system) == "exists"
    assert pc.status(home, system).state == pc.DAMAGED
    assert Path(pc.folder(home), leftover).read_text() == "not what this tool made"


def test_a_missing_half_a_changed_key_or_an_unrestricted_certificate_is_damaged_and_never_used(home, system, tmp_path):
    made(home, system)
    assert pc.status(home, system).state == pc.OK
    crt, key = pc.certificate_path(home), pc.key_path(home)
    saved_crt, saved_key = Path(crt).read_bytes(), Path(key).read_bytes()
    os.remove(key)
    assert pc.status(home, system).state == pc.DAMAGED and pc.status(home, system).certificate == crt, "the file that is there is named"
    Path(key).write_bytes(saved_key)
    os.remove(crt)
    assert pc.status(home, system).state == pc.DAMAGED and pc.status(home, system).certificate == "", "a file that is not there is not named"
    Path(crt).write_bytes(saved_crt)
    assert pc.status(home, system).state == pc.OK
    other = tmp_path / "other"
    other.mkdir()
    openssl("req", "-x509", "-newkey", "ec", "-pkeyopt", "ec_paramgen_curve:prime256v1", "-nodes", "-keyout", str(other / "k"), "-out", str(other / "c"), "-subj", "/CN=other", "-addext", "basicConstraints=critical,CA:TRUE")
    Path(key).write_bytes((other / "k").read_bytes())
    assert pc.status(home, system).state == pc.DAMAGED, "a key that is not the certificate's"
    Path(key).write_bytes(saved_key)
    Path(crt).write_bytes((other / "c").read_bytes())
    Path(key).write_bytes((other / "k").read_bytes())
    assert pc.status(home, system).state == pc.DAMAGED, "a matching pair that is an authority with no restriction"
    Path(crt).write_text("garbage")
    assert pc.status(home, system).state == pc.DAMAGED


def test_a_matching_pair_with_the_right_restrictions_that_is_not_an_authority_is_damaged(home, system, tmp_path):
    os.makedirs(pc.folder(home), mode=0o700)
    crt, key = pc.certificate_path(home), pc.key_path(home)
    for ca, state in (("CA:TRUE", pc.OK), ("CA:FALSE", pc.DAMAGED)):
        for path in (crt, key):
            if os.path.exists(path):
                os.remove(path)
        openssl("req", "-x509", "-newkey", "ec", "-pkeyopt", "ec_paramgen_curve:prime256v1", "-nodes", "-keyout", key, "-out", crt, "-subj", "/CN=same", "-days", "100",
                "-addext", "basicConstraints=critical," + ca, "-addext", "nameConstraints=critical," + pc._constraints(pc.PRIVATE_RANGES))
        assert pc.status(home, system).state == state, ca


def test_a_certificate_with_a_wider_restriction_is_damaged(home, system, tmp_path):
    made(home, system, ranges=(("10.0.0.0", "255.0.0.0"),))
    assert pc.status(home, system).state == pc.DAMAGED, "the ranges it was made for are not the ranges this tool allows"
    assert pc.status(home, system, ranges=(("10.0.0.0", "255.0.0.0"),)).state == pc.OK


def test_a_time_that_carries_its_zone_is_read_as_the_same_moment_in_utc(home, system):
    from datetime import timezone
    made(home, system, now=datetime(2026, 10, 16, 23, 30, tzinfo=timezone(timedelta(hours=-5))))
    assert "2026-10-17" in openssl("x509", "-in", pc.certificate_path(home), "-noout", "-subject").stdout, "23:30 at UTC-5 is already the 17th in UTC"
    ends = pc.status(home, system).expires
    assert pc.status(home, system, now=(ends - timedelta(days=5)).replace(tzinfo=timezone.utc)).state == pc.EXPIRING
    minus_five = timezone(timedelta(hours=-5))
    assert pc.status(home, system, now=(ends + timedelta(hours=1)).replace(tzinfo=timezone.utc).astimezone(minus_five)).state == pc.EXPIRED, "an hour past the end, written as 4 hours before it on the wall clock of UTC-5"
    assert pc.status(home, system, now=(ends - timedelta(hours=1)).replace(tzinfo=timezone.utc).astimezone(minus_five)).state == pc.EXPIRING


def test_the_state_follows_the_clock_and_warns_thirty_days_before_the_end(home, system):
    made(home, system)
    ends = pc.status(home, system).expires
    assert pc.status(home, system, now=ends - timedelta(days=31)).state == pc.OK
    soon = pc.status(home, system, now=ends - timedelta(days=29, hours=1))
    assert soon.state == pc.EXPIRING and soon.days_left == 29
    assert pc.status(home, system, now=ends - timedelta(days=30, seconds=1)).state == pc.OK
    assert pc.status(home, system, now=ends - timedelta(days=30)).state == pc.EXPIRING and pc.status(home, system, now=ends - timedelta(days=30)).days_left == 30
    assert pc.status(home, system, now=ends - timedelta(seconds=1)).state == pc.EXPIRING
    gone = pc.status(home, system, now=ends)
    assert gone.state == pc.EXPIRED and gone.days_left == 0
    assert pc.status(home, system, now=ends + timedelta(days=400)).state == pc.EXPIRED


# ---------------------------------------------------------------- the certificate for one address

def leaf_for(home, system, tmp_path, address, ranges=pc.PRIVATE_RANGES):
    work = tmp_path / ("work-" + address.replace(".", "-"))
    work.mkdir()
    return pc.issue_leaf(home, system, address, str(work), ranges), work


def test_a_certificate_for_a_home_address_is_verified_by_openssl_against_the_authority(home, system, tmp_path):
    made(home, system)
    leaf, work = leaf_for(home, system, tmp_path, "192.168.1.23")
    done = openssl("verify", "-CAfile", pc.certificate_path(home), "-purpose", "sslserver", leaf.certificate)
    assert done.returncode == 0 and done.stdout.strip().endswith(": OK"), done.stdout + done.stderr
    text = openssl("x509", "-in", leaf.certificate, "-noout", "-text").stdout
    assert "IP Address:192.168.1.23" in text and text.count("IP Address:") == 1 and "DNS:" not in text
    assert "TLS Web Server Authentication" in text and "CA:FALSE" in text and "Digital Signature" in text and "prime256v1" in text
    assert "Subject: O = ACK Voice Studio one-time send" in text and "CN =" not in text.split("Subject Public Key Info")[0].split("Subject:")[1]
    assert mode(leaf.key) == 0o600


def test_the_certificate_for_an_address_lasts_seven_days(home, system, tmp_path):
    made(home, system)
    leaf, _ = leaf_for(home, system, tmp_path, "10.1.2.3")
    ends = pc._read_end(system, leaf.certificate)
    assert abs((ends - (pc.utc_now() + timedelta(days=7))).total_seconds()) < 120


def test_the_certificate_is_not_valid_for_any_other_address(home, system, tmp_path):
    made(home, system)
    leaf, _ = leaf_for(home, system, tmp_path, "192.168.1.23")
    for other in ("192.168.1.24", "10.0.0.1"):
        done = openssl("verify", "-CAfile", pc.certificate_path(home), "-purpose", "sslserver", "-verify_ip", other, leaf.certificate)
        assert done.returncode != 0, other
    assert openssl("verify", "-CAfile", pc.certificate_path(home), "-purpose", "sslserver", "-verify_ip", "192.168.1.23", leaf.certificate).returncode == 0


@pytest.mark.parametrize("address", ["8.8.8.8", "172.32.0.1", "127.0.0.1", "example.com", "", "192.168.1.1/24", "::1"])
def test_no_certificate_is_made_for_an_address_outside_a_home_network(home, system, tmp_path, address):
    made(home, system)
    work = tmp_path / "w"
    work.mkdir()
    assert code_of(pc.issue_leaf, home, system, address, str(work)) == "not_private"
    assert os.listdir(work) == []


def test_the_authority_itself_refuses_to_vouch_for_a_public_address_or_a_name(home, system, tmp_path):
    """Not only this module: a certificate made by hand with the authority's own key is rejected by openssl, which is what a phone relies on."""
    made(home, system)
    work = tmp_path / "hand"
    work.mkdir()
    for index, alt in enumerate(["IP:8.8.8.8", "IP:172.32.0.1", "IP:127.0.0.1", "DNS:example.com", "DNS:ack-voice-studio.invalid.example.com", "email:a@example.com"]):
        (work / ("e%d.cnf" % index)).write_text("[v3]\nbasicConstraints=critical,CA:FALSE\nextendedKeyUsage=serverAuth\nsubjectAltName=%s\n" % alt)
        openssl("req", "-new", "-newkey", "ec", "-pkeyopt", "ec_paramgen_curve:prime256v1", "-nodes", "-keyout", "k%d" % index, "-out", "r%d" % index, "-subj", "/O=x", cwd=str(work))
        openssl("x509", "-req", "-in", "r%d" % index, "-CA", pc.certificate_path(home), "-CAkey", pc.key_path(home), "-CAserial", "s%d" % index, "-CAcreateserial", "-out", "c%d.crt" % index,
                "-days", "3", "-extfile", "e%d.cnf" % index, "-extensions", "v3", cwd=str(work))
        done = openssl("verify", "-CAfile", pc.certificate_path(home), "-purpose", "sslserver", "c%d.crt" % index, cwd=str(work))
        expected_ok = alt == "email:a@example.com"
        assert (done.returncode == 0) == expected_ok or "permitted subtree violation" in done.stdout + done.stderr, alt
        if alt.startswith(("IP:8", "IP:172.32", "IP:127", "DNS:example")):
            assert done.returncode != 0 and "permitted subtree violation" in done.stdout + done.stderr, alt


def test_every_number_in_a_certificate_is_different(home, system, tmp_path):
    made(home, system)
    first, _ = leaf_for(home, system, tmp_path, "192.168.1.23")
    work2 = tmp_path / "again"
    work2.mkdir()
    second = pc.issue_leaf(home, system, "192.168.1.23", str(work2))
    serial = lambda p: openssl("x509", "-in", p, "-noout", "-serial").stdout.strip()
    assert serial(first.certificate) != serial(second.certificate)
    assert sorted(os.listdir(pc.folder(home))) == [pc.CERT_FILE, pc.KEY_FILE], "the authority's own folder gets nothing from making a certificate"


def test_a_missing_damaged_or_expired_authority_is_not_used(home, system, tmp_path):
    work = tmp_path / "w"
    work.mkdir()
    assert code_of(pc.issue_leaf, home, system, "192.168.1.5", str(work)) == "absent"
    made(home, system)
    Path(pc.certificate_path(home)).write_text("garbage")
    assert code_of(pc.issue_leaf, home, system, "192.168.1.5", str(work)) == "damaged"
    assert os.listdir(work) == []


def test_an_expired_authority_is_refused_by_name(home, system, tmp_path, monkeypatch):
    made(home, system)
    real = pc.status
    monkeypatch.setattr(pc, "status", lambda h, s, now=None, ranges=pc.PRIVATE_RANGES: real(h, s, now=pc.utc_now() + timedelta(days=800), ranges=ranges))
    work = tmp_path / "w"
    work.mkdir()
    assert code_of(pc.issue_leaf, home, system, "192.168.1.5", str(work)) == "expired"


def test_a_certificate_that_the_authority_does_not_stand_behind_is_not_handed_back(home, system, tmp_path):
    made(home, system, ranges=(("127.0.0.0", "255.0.0.0"),))
    work = tmp_path / "w"
    work.mkdir()
    assert code_of(pc.issue_leaf, home, system, "192.168.1.5", str(work)) == "damaged", "an authority made for other ranges is not this tool's"


# ---------------------------------------------------------------- a real handshake (the shape the phone will see, on this computer's own loopback)

def test_a_real_secure_connection_is_trusted_with_the_authority_and_not_without_it(home, system, tmp_path):
    import socket
    import threading
    loopback = (("127.0.0.0", "255.0.0.0"),)
    made(home, system, ranges=loopback)
    leaf, _ = leaf_for(home, system, tmp_path, "127.0.0.1", loopback)
    server_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    server_context.load_cert_chain(leaf.certificate, leaf.key)
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(2)
    port = listener.getsockname()[1]
    seen = []

    def serve():
        for _ in range(2):
            raw, _addr = listener.accept()
            try:
                with server_context.wrap_socket(raw, server_side=True) as tls:
                    seen.append(tls.recv(5))
                    tls.sendall(b"hello")
            except (ssl.SSLError, OSError):
                seen.append(None)
    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    trusting = ssl.create_default_context(cafile=pc.certificate_path(home))
    with trusting.wrap_socket(socket.create_connection(("127.0.0.1", port), timeout=5), server_hostname="127.0.0.1") as tls:
        tls.sendall(b"ping!")
        assert tls.recv(5) == b"hello"
    strangers = ssl.create_default_context()
    with pytest.raises(ssl.SSLCertVerificationError):
        with strangers.wrap_socket(socket.create_connection(("127.0.0.1", port), timeout=5), server_hostname="127.0.0.1"):
            pass
    thread.join(5)
    listener.close()
    assert seen[0] == b"ping!" and seen[1] is None


# ---------------------------------------------------------------- when openssl cannot be used

def test_without_openssl_everything_that_needs_it_says_so_and_changes_nothing(home, tmp_path):
    fake = FakeSystem(tools={})
    assert code_of(pc.make_authority, home, fake) == "no_openssl"
    assert not os.path.exists(pc.key_path(home)) and not os.path.exists(pc.certificate_path(home))
    assert pc.status(home, fake).state == pc.ABSENT
    os.makedirs(pc.folder(home))
    Path(pc.key_path(home)).write_text("x")
    Path(pc.certificate_path(home)).write_text("y")
    fake.present.update({pc.key_path(home), pc.certificate_path(home)})
    assert code_of(pc.status, home, fake) == "no_openssl", "a computer without openssl cannot tell, and does not call the files damaged"


class Scripted:
    """A System whose openssl does what a test says."""

    def __init__(self, result, found="/usr/bin/openssl"):
        self.result, self.found, self.ran = result, found, []

    def which(self, name):
        return self.found

    def exists(self, path):
        return os.path.exists(path)

    def run(self, argv, timeout=15.0, cwd=None, env=None):
        self.ran.append((tuple(argv), timeout, cwd))
        return self.result


@pytest.mark.parametrize("result", [None, CommandResult(1, "", "Error: something\nsecond line"), CommandResult(2)])
def test_a_failed_openssl_leaves_no_half_made_authority(home, result):
    scripted = Scripted(result)
    assert code_of(pc.make_authority, home, scripted) == "openssl_failed"
    assert not os.path.exists(pc.folder(home)) and len(scripted.ran) == 1, "a folder this try made is taken away again when it fails"
    assert scripted.ran[0][1] == pc.OPENSSL_TIMEOUT and scripted.ran[0][2] == pc.folder(home)


def test_a_failed_try_leaves_a_folder_that_was_already_there_as_it_found_it(home):
    os.makedirs(pc.folder(home))
    Path(pc.folder(home), "other-file").write_text("kept")
    assert code_of(pc.make_authority, home, Scripted(CommandResult(1, "", "no"))) == "openssl_failed"
    assert os.listdir(pc.folder(home)) == ["other-file"]


def test_a_failed_try_does_not_take_away_an_empty_folder_that_was_already_there(home):
    os.makedirs(pc.folder(home))
    assert code_of(pc.make_authority, home, Scripted(CommandResult(1, "", "no"))) == "openssl_failed"
    assert os.path.isdir(pc.folder(home)) and os.listdir(pc.folder(home)) == []


def test_the_first_line_of_what_openssl_said_is_kept_as_the_detail(home):
    with pytest.raises(pc.PhoneCertError) as caught:
        pc.make_authority(home, Scripted(CommandResult(1, "", "\n  Error: something\nsecond line")))
    assert caught.value.detail == "Error: something"
    with pytest.raises(pc.PhoneCertError) as caught:
        pc.make_authority(home, Scripted(CommandResult(1, "", "x" * 500)))
    assert caught.value.detail == "x" * 200


def test_the_work_folder_for_one_send_is_private_and_inside_the_authoritys_folder(home):
    work = pc.new_workdir(home)
    try:
        assert os.path.dirname(work) == pc.folder(home) and os.path.basename(work).startswith("send-") and mode(work) == 0o700
    finally:
        shutil.rmtree(work)


def test_an_unwritable_place_is_reported_as_a_folder_problem(tmp_path, system):
    blocker = tmp_path / "file"
    blocker.write_text("x")
    broken = DataHome(str(blocker))
    assert code_of(pc.make_authority, broken, system) == "folder"
    assert code_of(pc.new_workdir, broken) == "folder"


def test_every_error_code_the_module_can_raise_is_listed():
    import ast
    tree = ast.parse(Path(pc.__file__).read_text())
    raised = {n.args[0].value for n in ast.walk(tree) if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "PhoneCertError" and n.args and isinstance(n.args[0], ast.Constant)}
    assert raised <= set(pc.ERROR_CODES) and {"no_openssl", "openssl_failed", "not_private", "exists", "folder"} <= raised
