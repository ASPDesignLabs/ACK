# SPDX-License-Identifier: GPL-3.0-or-later
"""`voicefile send` (plan task VS-5.1, decision D10, choices P25): the order of the steps, what is asked, what is said, and what is left behind. The certificate steps use the real `openssl`;
the listener is a stand-in that records what it was given (the real one is held to its rules in test_vs_lansend.py), so no port is opened here."""
import inspect
import os
import re
import shutil
from datetime import timedelta
from pathlib import Path

import pytest

from vs_fakes import PROC_NATIVE, PROC_WSL2
from vs_listen_helpers import VOICE_FOLDER, ListenRig
from vs_rounds_helpers import NOW
from vs_startvoice_helpers import Terminal, implies_permission, leaked_keys
from voice_studio.core import lansend as ls, phonecert as pc, text, voicefile_flow as vff
from voice_studio.core.system import CommandResult, RealSystem

pytestmark = pytest.mark.skipif(shutil.which("openssl") is None, reason="needs the openssl program")
CAT = text.load_catalog("en")
WIFI = "2: wlp3s0    inet 192.168.1.23/24 brd 192.168.1.255 scope global dynamic noprefixroute wlp3s0\\       valid_lft 85234sec\n"
VOICE = VOICE_FOLDER


class SendSystem(RealSystem):
    """The real computer for openssl, with the network card list and the kind of system made up."""

    def __init__(self, ip_output=WIFI, has_ip=True, wsl=False):
        self.ip_output, self.has_ip, self.wsl = ip_output, has_ip, wsl

    def which(self, name):
        if name == "ip":
            return "/usr/sbin/ip" if self.has_ip else None
        return super().which(name)

    def run(self, argv, timeout=15.0, cwd=None, env=None):
        if os.path.basename(argv[0]) == "ip":
            return CommandResult(0, self.ip_output)
        return super().run(argv, timeout, cwd, env)

    def read_text(self, path):
        return (PROC_WSL2 if self.wsl else PROC_NATIVE) if path == "/proc/version" else super().read_text(path)

    def environ(self):
        return {}


class Serve:
    """A stand-in listener: records what it was given, says what a real one says, and returns the result a test chooses."""

    def __init__(self, result=None, events=(), raises=None, port=None, drop_folder=False):
        self.result = result or ls.SendResult(ls.DELIVERED, 123, 1, 0, 0)
        self.events, self.raises, self.port, self.drop_folder = list(events), raises, port, drop_folder
        self.calls = []

    def __call__(self, path, name, address, port, certificate, key, token, *, on_event, should_stop, **kw):
        files_then = {"certificate": os.path.isfile(certificate), "key": os.path.isfile(key), "mode": oct(os.stat(key).st_mode & 0o777), "dir": os.path.dirname(certificate)}
        self.calls.append(dict(path=path, name=name, address=address, port=port, certificate=certificate, key=key, token=token, stop=should_stop, kw=kw, files=files_then))
        on_event("listening", port=self.port or port)
        if self.drop_folder:                                    # something else removed the work folder while it was listening
            shutil.rmtree(files_then["dir"])
        for kind, facts in self.events:
            on_event(kind, **facts)
        if self.raises:
            raise self.raises
        return self.result


class Rig(ListenRig):
    def __init__(self, tmp_path, *, system=None, **kw):
        super().__init__(tmp_path, **kw)
        self.send_system = system or SendSystem()

    def send(self, *argv, answers=(), interactive=True, serve=None, now=NOW, ansi=False, system=None):
        io = Terminal(answers, interactive)
        if ansi is not None:                                    # None: a terminal that does not say whether it can show colour at all
            io.ansi = ansi
        serve = serve if serve is not None else Serve()
        code = vff.run_voicefile(["send"] + list(argv), self.home, None, CAT, io, training=self.training_env, now=now, system=system or self.send_system, serve=serve)
        assert leaked_keys(io.text + "\n".join(io.prompts)) == [], "a catalog key was printed instead of words"
        assert implies_permission(io.text) == []
        return code, io, serve

    def authority(self):
        return pc.make_authority(self.home, RealSystem(), now=NOW)

    def workdirs(self):
        folder = pc.folder(self.home)
        return sorted(n for n in (os.listdir(folder) if os.path.isdir(folder) else []) if n.startswith("send-"))


@pytest.fixture
def rig(tmp_path):
    return Rig(tmp_path)


def said(io, fragment):
    return any(fragment in line for line in io.lines)


def say(key, **kw):
    return CAT.t(key, **kw)


# ---------------------------------------------------------------- before anything is offered

def test_with_no_voice_file_it_says_so_points_at_make_and_does_nothing(tmp_path):
    rig = Rig(tmp_path, make=False)
    code, io, serve = rig.send("--yes")
    assert code == 2 and said(io, say("voicefile.list.none")) and said(io, "voicefile make --project voice-check") and serve.calls == []
    assert not os.path.exists(pc.folder(rig.home))


def test_a_name_that_is_not_one_of_the_voice_files_lists_the_ones_there_are(rig):
    code, io, serve = rig.send("--yes", "--folder", "nope")
    assert code == 2 and said(io, say("voicefile.send.no_such", name="nope")) and any(line.startswith("  " + VOICE + ": ") for line in io.lines)
    assert serve.calls == [] and not os.path.exists(pc.folder(rig.home))


def test_the_newest_voice_file_is_used_unless_one_is_named(tmp_path):
    rig = Rig(tmp_path)
    rig.make_voice("voice-check-round-3-20261012-090000")
    rig.authority()
    code, io, serve = rig.send("--yes")
    assert code == 0 and serve.calls[0]["name"] == "voice-check-round-3-20261012-090000.zip"
    code, io, serve = rig.send("--yes", "--folder", VOICE)
    assert code == 0 and serve.calls[0]["name"] == VOICE + ".zip" and serve.calls[0]["path"].endswith("/%s/%s.zip" % (VOICE, VOICE))


def test_a_voice_file_the_phone_would_refuse_is_never_offered(tmp_path):
    rig = Rig(tmp_path, make=False)
    rig.make_voice(VOICE, patched=False)                   # a zip that is there but is not this voice's
    code, io, serve = rig.send("--yes")
    assert code == 1 and said(io, say("voicefile.send.not_ok", name=VOICE)) and said(io, "    - " + say("voicezip.problem.zip_unreadable"))
    assert serve.calls == [] and not os.path.exists(pc.folder(rig.home)), "nothing is made for a file that could not be sent"


def test_an_unknown_option_and_an_extra_word_are_told_and_nothing_is_done(rig):
    rig.authority()                                             # so that nothing else would stop a send that was understood
    for argv in (("--nope", "--yes"), ("extra", "--yes"), ("--address",), ("--port", "1", "--port", "2")):
        code, io, serve = rig.send(*argv)
        assert code == 2 and serve.calls == [] and not said(io, say("voicefile.send.title")) and not said(io, say("voicefile.send.plan_head")), argv


def test_a_project_that_does_not_exist_is_told_and_nothing_is_done(rig):
    rig.authority()
    code, io, serve = rig.send("--project", "nobody-by-that-name", "--yes")
    assert code == 2 and serve.calls == [] and not said(io, say("voicefile.send.plan_head")) and io.lines[1:], "a reason is given"


@pytest.mark.parametrize("port", ["0", "1023", "65536", "-1", "abc", "", "80", "8443.5", "８４４３", "1e4", " 8443"])
def test_a_port_outside_the_range_is_refused_before_anything_else(rig, port):
    code, io, serve = rig.send("--yes", "--port=" + port)
    assert code == 2 and said(io, say("voicefile.send.bad_port", low=1024, high=65535)) and serve.calls == []
    assert not os.path.exists(pc.folder(rig.home))


@pytest.mark.parametrize("port,expected", [("1024", 1024), ("65535", 65535), ("8443", 8443), ("9000", 9000)])
def test_a_port_in_the_range_is_used(rig, port, expected):
    rig.authority()
    code, io, serve = rig.send("--yes", "--port", port)
    assert code == 0 and serve.calls[0]["port"] == expected


def test_without_a_port_the_default_is_used(rig):
    rig.authority()
    assert rig.send("--yes")[2].calls[0]["port"] == ls.DEFAULT_PORT == 8443


# ---------------------------------------------------------------- the certificate file

def test_the_first_time_it_explains_asks_makes_the_certificate_file_and_stops_without_sending(rig):
    code, io, serve = rig.send(answers=["yes"])
    assert code == 0 and serve.calls == []
    assert [q.strip() for q in io.prompts] == [say("voicefile.send.cert_question")], "one question, and it is about the certificate file"
    for key in ("cert_head", "cert_what", "cert_limits", "cert_secret"):
        assert said(io, say("voicefile.send." + key))
    assert said(io, say("voicefile.send.cert_where", folder=pc.folder(rig.home)))
    assert said(io, say("voicefile.send.cert_made", file=pc.certificate_path(rig.home)))
    for key in ("phone_head", "phone_1", "phone_2", "phone_3", "phone_4"):
        assert said(io, say("voicefile.send." + key))
    assert said(io, say("voicefile.send.cert_next", command="python3 -m voice_studio.voicefile send"))
    assert pc.status(rig.home, RealSystem(), NOW).state == pc.OK and rig.workdirs() == []
    order = [i for i, line in enumerate(io.lines) if line in (say("voicefile.send.cert_head"), say("voicefile.send.cert_made", file=pc.certificate_path(rig.home)), say("voicefile.send.phone_head"))]
    assert order == sorted(order) and len(order) == 3


def test_a_no_makes_nothing_and_a_terminal_with_nobody_at_it_is_not_asked(rig):
    code, io, serve = rig.send(answers=["no"])
    assert code == 2 and not os.path.exists(pc.certificate_path(rig.home)) and said(io, say("cli.nothing_done"))
    code, io, serve = rig.send(answers=[], interactive=False)
    assert code == 2 and said(io, say("cli.cannot_ask")) and not os.path.exists(pc.certificate_path(rig.home))


def test_yes_on_the_command_line_makes_the_certificate_file_without_asking_and_still_does_not_send(rig):
    code, io, serve = rig.send("--yes")
    assert code == 0 and io.prompts == [] and os.path.exists(pc.certificate_path(rig.home)) and serve.calls == []


def test_a_failure_to_make_the_certificate_file_is_told_in_three_parts(tmp_path):
    rig = Rig(tmp_path, system=SendSystem())
    class NoOpenssl(SendSystem):
        def which(self, name):
            return None if name == "openssl" else super().which(name)
    code, io, serve = rig.send("--yes", system=NoOpenssl())
    parts = [say("phonecert.error.no_openssl.what"), say("phonecert.error.no_openssl.changed"), say("phonecert.error.no_openssl.next")]
    assert code == 1 and all(said(io, "  " + p) for p in parts) and serve.calls == [] and not os.path.exists(pc.folder(rig.home))


def test_a_damaged_or_ended_certificate_file_is_reported_and_never_used(rig):
    rig.authority()
    Path(pc.certificate_path(rig.home)).write_text("garbage")
    code, io, serve = rig.send("--yes")
    assert code == 1 and said(io, "  " + say("phonecert.error.damaged.what")) and said(io, say("voicefile.send.cert_where", folder=pc.folder(rig.home))) and serve.calls == []
    assert Path(pc.certificate_path(rig.home)).read_text() == "garbage", "nothing is replaced or removed"
    shutil.rmtree(pc.folder(rig.home))
    rig.authority()
    code, io, serve = rig.send("--yes", now=NOW + timedelta(days=800))
    assert code == 1 and said(io, "  " + say("phonecert.error.expired.what")) and serve.calls == []


def test_a_certificate_file_that_ends_soon_is_said_and_sending_goes_on(rig):
    rig.authority()
    code, io, serve = rig.send("--yes", now=NOW + timedelta(days=715))
    left = pc.status(rig.home, RealSystem(), NOW + timedelta(days=715)).days_left
    assert 0 < left < 30 and code == 0 and said(io, say("voicefile.send.cert_ending", days=left)) and len(serve.calls) == 1
    code, io, serve = rig.send("--yes")
    assert not any("ends in" in line for line in io.lines)


# ---------------------------------------------------------------- the address

def test_the_one_home_network_address_is_used(rig):
    rig.authority()
    code, io, serve = rig.send("--yes")
    assert serve.calls[0]["address"] == "192.168.1.23"


def test_an_address_given_is_used_if_it_is_a_home_network_address_and_refused_if_not(rig):
    rig.authority()
    code, io, serve = rig.send("--yes", "--address", "10.1.2.3")
    assert code == 0 and serve.calls[0]["address"] == "10.1.2.3"
    for bad in ("8.8.8.8", "127.0.0.1", "example.com", "192.168.1.1/24", ""):
        code, io, serve = rig.send("--yes", "--address=" + bad)
        assert code == 2 and said(io, "  " + say("phonecert.error.not_private.what")) and serve.calls == [], bad


def test_no_address_and_more_than_one_address_are_told_and_nothing_is_started(tmp_path):
    rig = Rig(tmp_path)
    rig.authority()
    code, io, serve = rig.send("--yes", system=SendSystem(ip_output=""))
    assert code == 2 and said(io, say("voicefile.send.no_address")) and said(io, "  " + say("voicefile.send.no_address_next", example="--address 192.168.1.23")) and serve.calls == []
    code, io, serve = rig.send("--yes", system=SendSystem(has_ip=False))
    assert code == 2 and said(io, say("voicefile.send.no_address")) and serve.calls == []
    two = WIFI + "3: eno1    inet 10.0.0.5/24 brd 10.0.0.255 scope global eno1\\ x\n"
    code, io, serve = rig.send("--yes", system=SendSystem(ip_output=two))
    assert code == 2 and serve.calls == []
    assert said(io, say("voicefile.send.several")) and said(io, "  " + say("voicefile.send.several_row", card="wlp3s0", address="192.168.1.23")) and said(io, "  " + say("voicefile.send.several_row", card="eno1", address="10.0.0.5"))
    assert said(io, say("voicefile.send.several_next", example="--address 192.168.1.23"))
    code, io, serve = rig.send("--yes", "--address", "10.0.0.5", system=SendSystem(ip_output=two))
    assert code == 0 and serve.calls[0]["address"] == "10.0.0.5"


# ---------------------------------------------------------------- the plan and the question

def test_the_plan_is_said_before_the_one_question_and_only_a_yes_starts_it(rig):
    rig.authority()
    code, io, serve = rig.send(answers=["yes"])
    size = os.stat(serve.calls[0]["path"]).st_size
    lines = [say("voicefile.send.plan_head"), "  " + say("voicefile.send.plan_file", name=VOICE + ".zip", size=text.size_text(size)),
             "  " + say("voicefile.send.plan_where", address="192.168.1.23", port=8443, minutes=10), "  " + say("voicefile.send.plan_once"), "  " + say("voicefile.send.plan_stop"),
             "  " + say("voicefile.send.plan_only")]
    positions = [io.lines.index(line) for line in lines]
    assert positions == sorted(positions) and [q.strip() for q in io.prompts] == [say("voicefile.send.question")] and code == 0
    ask_at = next(i for i, (kind, _) in enumerate(io.events) if kind == "ask")
    assert all(io.events.index(("say", line)) < ask_at for line in lines), "all of it is said before the question"
    assert len(serve.calls) == 1


def test_a_no_or_nobody_to_ask_starts_nothing_and_leaves_nothing(rig):
    rig.authority()
    code, io, serve = rig.send(answers=["no"])
    assert code == 2 and serve.calls == [] and rig.workdirs() == [] and said(io, say("cli.nothing_done"))
    code, io, serve = rig.send(answers=[], interactive=False)
    assert code == 2 and serve.calls == [] and said(io, say("cli.cannot_ask"))


def test_only_the_words_yes_and_y_start_it(rig):
    rig.authority()
    for answer in ("", "n", "nope", "maybe", "yess"):
        assert rig.send(answers=[answer])[2].calls == [], answer
    for answer in ("yes", "y", "YES", " yes "):
        assert len(rig.send(answers=[answer])[2].calls) == 1, answer


def test_ubuntu_under_windows_gets_one_extra_note_before_the_question_and_native_does_not(tmp_path):
    rig = Rig(tmp_path, system=SendSystem(wsl=True))
    rig.authority()
    code, io, serve = rig.send("--yes")
    assert said(io, say("voicefile.send.wsl_note", command="python3 -m voice_studio.wsl check")) and code == 0
    code, io, serve = rig.send("--yes", system=SendSystem(wsl=False))
    assert not said(io, say("voicefile.send.wsl_note", command="python3 -m voice_studio.wsl check"))


# ---------------------------------------------------------------- listening

def test_the_listener_is_given_the_file_the_name_the_address_the_certificate_and_a_fresh_token(rig):
    rig.authority()
    sig = inspect.signature(ls.serve_once)
    code, io, first = rig.send("--yes")
    call = first.calls[0]
    sig.bind(call["path"], call["name"], call["address"], call["port"], call["certificate"], call["key"], call["token"], on_event=print, should_stop=call["stop"], **call["kw"])
    assert call["files"]["certificate"] and call["files"]["key"] and call["files"]["mode"] == "0o600"
    assert call["files"]["dir"].startswith(pc.folder(rig.home) + "/send-")
    assert re.fullmatch(r"[A-Za-z0-9_-]{22}", call["token"]) and call["kw"] == {}
    assert call["stop"]() is False
    second = rig.send("--yes")[2].calls[0]
    assert second["token"] != call["token"]


def test_the_address_and_the_code_are_shown_when_the_listener_is_ready_and_the_code_only_where_colour_can_be_written(rig):
    rig.authority()
    serve = Serve(port=9001)
    code, io, serve = rig.send("--yes", "--port=9001", serve=serve)
    url = "https://192.168.1.23:9001/%s/%s.zip" % (serve.calls[0]["token"], VOICE)
    assert said(io, say("voicefile.send.waiting")) and said(io, "  " + url) and said(io, say("voicefile.send.stop_hint"))
    assert not any(line.startswith("\x1b[") for line in io.lines), "no colour codes, so no code is drawn"
    code, io, serve = rig.send("--yes", ansi=True)
    shown = [line for line in io.lines if line.startswith("\x1b[30;47m")]
    assert shown and all(line.endswith("\x1b[0m") for line in shown)
    url = "https://192.168.1.23:8443/%s/%s.zip" % (serve.calls[0]["token"], VOICE)
    at = io.lines.index(say("voicefile.send.waiting"))
    assert io.lines[at + 1:at + 1 + len(shown)] == shown and io.lines[at + 1 + len(shown)] == "  " + url, "the code, then the address under it"


def test_the_address_uses_the_port_the_listener_really_took(rig):
    rig.authority()
    code, io, serve = rig.send("--yes", serve=Serve(port=45555))
    assert said(io, "  https://192.168.1.23:45555/%s/%s.zip" % (serve.calls[0]["token"], VOICE))


def test_what_happens_while_it_waits_is_said_as_it_happens(rig):
    rig.authority()
    events = [("untrusted", {}), ("sending", {"size": 5_000_000}), ("interrupted", {}), ("sending", {"size": 5_000_000}), ("stranger", {})]
    code, io, serve = rig.send("--yes", serve=Serve(events=events))
    wanted = [say("voicefile.send.untrusted"), say("voicefile.send.sending", size="5.0 MB"), say("voicefile.send.interrupted"), say("voicefile.send.sending", size="5.0 MB")]
    got = [line for line in io.lines if line in wanted]
    assert got == wanted
    assert not any("stranger" in line for line in io.lines), "a request for something else is not announced"


def test_a_delivered_file_ends_with_the_next_steps_and_exit_zero_and_the_work_folder_is_gone(rig):
    rig.authority()
    size = os.stat(rig.paths.exports + "/%s/%s.zip" % (VOICE, VOICE)).st_size
    code, io, serve = rig.send("--yes")
    assert code == 0 and said(io, say("voicefile.send.done", size=text.size_text(size))) and said(io, say("voicefile.send.done_next"))
    assert rig.workdirs() == [] and not os.path.exists(serve.calls[0]["dir"] if "dir" in serve.calls[0] else serve.calls[0]["files"]["dir"])
    assert sorted(os.listdir(pc.folder(rig.home))) == [pc.CERT_FILE, pc.KEY_FILE]


@pytest.mark.parametrize("outcome,key,exit_code", [(ls.TIMED_OUT, "voicefile.send.timed_out", 1), (ls.STOPPED, "voicefile.send.stopped", 1), (ls.TOO_MANY, "voicefile.send.too_many", 1)])
def test_each_way_it_ends_without_the_file_is_told_and_is_not_a_success(rig, outcome, key, exit_code):
    rig.authority()
    code, io, serve = rig.send("--yes", serve=Serve(result=ls.SendResult(outcome, 0, 0, 0, 12)))
    assert code == exit_code and said(io, say(key, minutes=10, count=12)) and not said(io, say("voicefile.send.done_next")) and rig.workdirs() == []
    assert not said(io, say("voicefile.send.untrusted_end"))


def test_a_device_that_would_not_trust_the_certificate_is_remembered_at_the_end(rig):
    rig.authority()
    code, io, serve = rig.send("--yes", serve=Serve(result=ls.SendResult(ls.TIMED_OUT, 0, 0, 2, 0)))
    assert code == 1 and said(io, say("voicefile.send.untrusted_end"))


@pytest.mark.parametrize("error,parts", [(ls.SendError("in_use"), "lansend.error.in_use"), (ls.SendError("cannot_listen", "Cannot assign requested address"), "lansend.error.cannot_listen"),
                                         (ls.SendError("bad_name"), "lansend.error.bad_name"), (pc.PhoneCertError("openssl_failed", "boom"), "phonecert.error.openssl_failed")])
def test_a_refusal_from_the_listener_is_told_in_three_parts_and_the_work_folder_is_gone(rig, error, parts):
    rig.authority()
    code, io, serve = rig.send("--yes", serve=Serve(raises=error))
    assert code == 1 and all(said(io, "  " + say(parts + "." + p)) for p in ("what", "changed", "next")) and rig.workdirs() == []
    if error.detail:
        assert said(io, "  " + say("cli.technical", detail=error.detail))


def test_ctrl_c_stops_it_cleanly_and_removes_the_certificate_made_for_the_send(rig):
    rig.authority()
    code, io, serve = rig.send("--yes", serve=Serve(raises=KeyboardInterrupt()))
    assert code == 1 and said(io, say("voicefile.send.stopped")) and rig.workdirs() == []


def test_the_real_listener_refuses_an_address_this_computer_does_not_have_and_the_flow_says_so(rig):
    rig.authority()
    code, io, serve = rig.send("--yes", "--address", "10.254.254.254", serve=ls.serve_once)
    assert code == 1 and said(io, "  " + say("lansend.error.cannot_listen.what")) and rig.workdirs() == []


def test_a_certificate_for_the_address_is_really_made_by_the_authority_before_the_listener_starts(rig):
    rig.authority()
    code, io, serve = rig.send("--yes", "--address", "10.1.2.3")
    import subprocess
    # the work folder is gone by now; ask again while it is there by capturing the certificate inside the stand-in
    seen = {}

    class Inspecting(Serve):
        def __call__(self, path, name, address, port, certificate, key, token, **kw):
            seen["text"] = subprocess.run(["openssl", "x509", "-in", certificate, "-noout", "-text"], capture_output=True, text=True).stdout
            seen["verify"] = subprocess.run(["openssl", "verify", "-CAfile", pc.certificate_path(rig.home), "-purpose", "sslserver", certificate], capture_output=True, text=True).stdout
            return super().__call__(path, name, address, port, certificate, key, token, **kw)
    rig.send("--yes", "--address", "10.1.2.3", serve=Inspecting())
    assert "IP Address:10.1.2.3" in seen["text"] and seen["verify"].strip().endswith(": OK")


# ---------------------------------------------------------------- the command's help and wiring

def test_a_computer_without_openssl_that_has_the_certificate_files_is_told_in_three_parts_and_nothing_is_started(rig):
    rig.authority()

    class NoOpenssl(SendSystem):
        def which(self, name):
            return None if name == "openssl" else super().which(name)
    code, io, serve = rig.send("--yes", system=NoOpenssl())
    assert code == 1 and serve.calls == [] and said(io, say("phonecert.error.no_openssl.what")) and said(io, say("phonecert.error.no_openssl.next"))


def test_a_work_folder_that_cannot_be_made_is_told_in_three_parts_and_nothing_is_started(rig, monkeypatch):
    rig.authority()

    def refuse(home):
        raise pc.PhoneCertError("folder")
    monkeypatch.setattr(pc, "new_workdir", refuse)
    code, io, serve = rig.send("--yes")
    assert code == 1 and serve.calls == [] and said(io, say("phonecert.error.folder.what")) and rig.workdirs() == []


def test_a_work_folder_that_is_already_gone_at_the_end_is_no_trouble(rig):
    rig.authority()
    code, io, serve = rig.send("--yes", serve=Serve(drop_folder=True))
    assert code == 0 and said(io, say("voicefile.send.done_next")) and rig.workdirs() == []


def test_a_terminal_that_does_not_say_whether_it_can_show_colour_gets_the_address_and_no_code(rig):
    rig.authority()
    code, io, serve = rig.send("--yes", ansi=None)
    assert code == 0 and said(io, say("voicefile.send.waiting")) and not any(line.startswith("\x1b[") for line in io.lines)


def test_the_code_is_drawn_with_two_light_squares_around_it(rig):
    from voice_studio.core import qrcode
    rig.authority()
    code, io, serve = rig.send("--yes", ansi=True)
    url = "https://192.168.1.23:8443/%s/%s.zip" % (serve.calls[0]["token"], VOICE)
    drawn = [line for line in io.lines if line.startswith("\x1b[30;47m")]
    assert drawn == qrcode.lines(qrcode.encode(url), 2, color=True)


def test_the_help_lists_send_and_the_options_the_checklist_may_name():
    io = Terminal()
    assert vff.run_voicefile(["help"], None, None, CAT, io, training=lambda: (None, "absent")) == 0
    assert said(io, "  " + say("voicefile.usage.send")) and "send" in vff.OPTIONS
    assert set(vff.OPTIONS["send"]) == {"--yes", "-y", "--project", "--folder", "--address", "--port"}
    assert io.lines.index("  " + say("voicefile.usage.listen")) < io.lines.index("  " + say("voicefile.usage.send")) < io.lines.index("  " + say("voicefile.usage.options"))


def test_nothing_is_sent_over_the_network_by_this_front_itself():
    source = Path(inspect.getsourcefile(vff.voicesend_flow)).read_text()
    for forbidden in ("import socket", "import ssl", "urllib", "http.client", "subprocess", "connect("):
        assert forbidden not in source, forbidden
