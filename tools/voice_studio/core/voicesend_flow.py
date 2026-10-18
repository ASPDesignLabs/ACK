# SPDX-License-Identifier: GPL-3.0-or-later
"""The terminal front for giving the finished voice file to a phone over the home network (plan task VS-5.1, decision D10, choices P25): `voicefile send`.

It decides nothing that core/phonecert.py, core/lansend.py, core/lanaddress.py and core/qrcode.py do not. The order is fixed and every step that changes something asks first:

1. Pick the voice file (the newest, or `--folder`), and check it again with the very rules the phone applies. A file the phone would refuse is never offered.
2. The certificate file for the phone. The first time it does not exist: it is explained, made after a yes, and the command **stops**, because the phone has to be given the file before it
   can take a download without a warning. Every later time it is only looked at; one that is damaged or has ended is reported and never used.
3. The address the phone will be sent to: the computer's one home-network address, or the one chosen with `--address`.
4. The plan, in plain words, and one question. Only a yes starts listening.
5. It listens, shows the address and a QR code, tells the person what happens, and ends by itself. The certificate made for this one send is removed afterwards.

Every sentence comes from the text catalog. Exit codes: 0 the file was sent (or the certificate file was made), 1 it was not sent or something failed after it began, 2 nothing was done (declined,
nobody to ask, an option that could not be told).
"""
from __future__ import annotations

import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional, Sequence

from . import lanaddress, lansend, phonecert, qrcode, voicefile as vf, voicezip
from .cliargs import ArgError, parse_args
from .paths import DataHome
from .projects_flow import EXIT_NOTHING_DONE, EXIT_OK, EXIT_PROBLEM, say_bad_arg
from .rounds_flow import PROJECT, YES, _confirmed, _open, _say_parts
from .setup_flow import IO
from .system import RealSystem, System
from .text import Catalog, size_text

SEND_VALUES = dict(PROJECT, **{"--folder": "folder", "--address": "address", "--port": "port"})
OPTIONS = frozenset(YES) | frozenset(SEND_VALUES)                                        # the checklist is held to these
QR_QUIET = 2                                                                             # light squares around the code: enough for a phone, small on a screen

Serve = Callable[..., lansend.SendResult]


def _port(text: Optional[str]) -> Optional[int]:
    """The port typed, or the default when none was; None when it is not a number in the range a person may use."""
    if text is None:
        return lansend.DEFAULT_PORT
    if not text.isascii() or not text.isdigit():
        return None
    value = int(text)
    return value if 1024 <= value <= 65535 else None


def _say_phone_steps(cat: Catalog, io: IO) -> None:
    io.say(cat.t("voicefile.send.phone_head"))
    for key in ("voicefile.send.phone_1", "voicefile.send.phone_2", "voicefile.send.phone_3", "voicefile.send.phone_4"):
        io.say("  " + cat.t(key))


def _make_certificate(parsed, home: DataHome, system: System, now: Optional[datetime], cat: Catalog, io: IO) -> int:
    """The first time: say what will be made, ask, make it, say how to put it on the phone, and stop (the phone has to have it before anything can be sent)."""
    io.say(cat.t("voicefile.send.cert_head"))
    for line in (cat.t("voicefile.send.cert_what"), cat.t("voicefile.send.cert_limits"), cat.t("voicefile.send.cert_where", folder=phonecert.folder(home)), cat.t("voicefile.send.cert_secret")):
        io.say("  " + line)
    declined = _confirmed(parsed, cat.t("voicefile.send.cert_question"), cat, io)
    if declined is not None:
        return declined
    try:
        made = phonecert.make_authority(home, system, now)
    except phonecert.PhoneCertError as error:
        _say_parts(cat, io, "phonecert", error.code, error.detail)
        return EXIT_PROBLEM
    io.say(cat.t("voicefile.send.cert_made", file=made.certificate))
    _say_phone_steps(cat, io)
    io.say(cat.t("voicefile.send.cert_next", command="%s send" % "python3 -m voice_studio.voicefile"))
    return EXIT_OK


def _certificate_ok(authority: phonecert.Authority, home: DataHome, cat: Catalog, io: IO) -> Optional[int]:
    """None when the certificate file can be used; otherwise the exit code, with the reason said."""
    if authority.state in (phonecert.DAMAGED, phonecert.EXPIRED):
        _say_parts(cat, io, "phonecert", authority.state)
        io.say("  " + cat.t("voicefile.send.cert_where", folder=phonecert.folder(home)))
        return EXIT_PROBLEM
    if authority.state == phonecert.EXPIRING:
        io.say(cat.t("voicefile.send.cert_ending", days=authority.days_left))
    return None


def _choose_address(parsed, system: System, cat: Catalog, io: IO) -> Optional[str]:
    """The address to listen on, or None after saying why not (the caller then ends with nothing done)."""
    given = parsed.values.get("address")
    if given is not None:
        if not phonecert.is_private_address(given):
            _say_parts(cat, io, "phonecert", "not_private")
            return None
        return given
    found = lanaddress.candidates(system)
    if not found:
        io.say(cat.t("voicefile.send.no_address"))
        io.say("  " + cat.t("voicefile.send.no_address_next", example="--address 192.168.1.23"))
        return None
    if len(found) > 1:
        io.say(cat.t("voicefile.send.several"))
        for item in found:
            io.say("  " + cat.t("voicefile.send.several_row", card=item.card, address=item.address))
        io.say(cat.t("voicefile.send.several_next", example="--address %s" % found[0].address))
        return None
    return found[0].address


def _say_plan(name: str, size: int, address: str, port: int, wsl: bool, cat: Catalog, io: IO) -> None:
    io.say(cat.t("voicefile.send.plan_head"))
    for line in (cat.t("voicefile.send.plan_file", name=name, size=size_text(size)), cat.t("voicefile.send.plan_where", address=address, port=port, minutes=lansend.MINUTES),
                 cat.t("voicefile.send.plan_once"), cat.t("voicefile.send.plan_stop"), cat.t("voicefile.send.plan_only")):
        io.say("  " + line)
    if wsl:
        io.say(cat.t("voicefile.send.wsl_note", command="python3 -m voice_studio.wsl check"))


def _show_address(url: str, cat: Catalog, io: IO) -> None:
    io.say(cat.t("voicefile.send.waiting"))
    if getattr(io, "ansi", False):                                                       # a code is drawn only where it can be drawn black on white whatever the terminal's colours
        try:
            for line in qrcode.lines(qrcode.encode(url), QR_QUIET, color=True):
                io.say(line)
        except qrcode.QrError:
            pass
    io.say("  " + url)
    io.say(cat.t("voicefile.send.stop_hint"))


def _event_printer(cat: Catalog, io: IO) -> Callable[..., None]:
    def on_event(kind: str, **facts) -> None:
        if kind == "sending":
            io.say(cat.t("voicefile.send.sending", size=size_text(facts["size"])))
        elif kind == "interrupted":
            io.say(cat.t("voicefile.send.interrupted"))
        elif kind == "untrusted":
            io.say(cat.t("voicefile.send.untrusted"))
    return on_event


def _say_result(result: lansend.SendResult, size: int, cat: Catalog, io: IO) -> int:
    if result.outcome == lansend.DELIVERED:
        io.say(cat.t("voicefile.send.done", size=size_text(size)))
        io.say(cat.t("voicefile.send.done_next"))
        return EXIT_OK
    key = {lansend.TIMED_OUT: "voicefile.send.timed_out", lansend.STOPPED: "voicefile.send.stopped", lansend.TOO_MANY: "voicefile.send.too_many"}[result.outcome]
    io.say(cat.t(key, minutes=lansend.MINUTES, count=result.strangers))
    if result.untrusted:
        io.say(cat.t("voicefile.send.untrusted_end"))
    return EXIT_PROBLEM


def run_send(args: Sequence[str], home: DataHome, cat: Catalog, io: IO, *, system: Optional[System] = None, now: Optional[datetime] = None, serve: Optional[Serve] = None,
             should_stop: Callable[[], bool] = lambda: False) -> int:
    system = system or RealSystem()
    serve = serve or lansend.serve_once
    try:
        parsed = parse_args(args, flags=YES, values=SEND_VALUES, max_words=0)
    except ArgError as error:
        return say_bad_arg(error, cat, io)
    io.say(cat.t("voicefile.send.title"))
    port = _port(parsed.values.get("port"))
    if port is None:
        io.say(cat.t("voicefile.send.bad_port", low=1024, high=65535))
        return EXIT_NOTHING_DONE
    ctx, code = _open(parsed, home, cat, io)
    if ctx is None:
        return code
    made = vf.existing_voice_files(ctx.paths)
    if not made:
        io.say(cat.t("voicefile.list.none"))
        io.say(cat.t("voicefile.list.next", command="python3 -m voice_studio.voicefile make --project %s" % ctx.project.id))
        return EXIT_NOTHING_DONE
    wanted = parsed.values.get("folder")
    chosen = next((m for m in made if m[0] == wanted), None) if wanted is not None else made[-1]
    if chosen is None:
        io.say(cat.t("voicefile.send.no_such", name=wanted))
        for name, _zip, size in made:
            io.say("  " + cat.t("voicefile.list.row", name=name, size=size_text(size)))
        return EXIT_NOTHING_DONE
    folder_name, zip_path, size = chosen
    problems = voicezip.verify_voice_zip(Path(zip_path))
    if problems:
        io.say(cat.t("voicefile.send.not_ok", name=folder_name))
        for problem in problems:
            io.say("    - " + cat.t("voicezip.problem." + problem))
        return EXIT_PROBLEM
    try:
        authority = phonecert.status(home, system, now)
    except phonecert.PhoneCertError as error:
        _say_parts(cat, io, "phonecert", error.code, error.detail)
        return EXIT_PROBLEM
    if authority.state == phonecert.ABSENT:
        return _make_certificate(parsed, home, system, now, cat, io)
    refused = _certificate_ok(authority, home, cat, io)
    if refused is not None:
        return refused
    address = _choose_address(parsed, system, cat, io)
    if address is None:
        return EXIT_NOTHING_DONE
    name = os.path.basename(zip_path)
    _say_plan(name, size, address, port, lanaddress.on_wsl(system), cat, io)
    declined = _confirmed(parsed, cat.t("voicefile.send.question"), cat, io)
    if declined is not None:
        return declined
    return _send(home, system, zip_path, name, size, address, port, serve, should_stop, cat, io)


def _send(home: DataHome, system: System, zip_path: str, name: str, size: int, address: str, port: int, serve: Serve, should_stop: Callable[[], bool], cat: Catalog, io: IO) -> int:
    work = None
    try:
        work = phonecert.new_workdir(home)
        leaf = phonecert.issue_leaf(home, system, address, work)
        token = lansend.new_token()
        shown = {"url": ""}

        def on_event(kind: str, **facts) -> None:
            if kind == "listening":
                shown["url"] = lansend.address_of(address, facts["port"], token, name)
                _show_address(shown["url"], cat, io)
            else:
                _event_printer(cat, io)(kind, **facts)
        result = serve(zip_path, name, address, port, leaf.certificate, leaf.key, token, on_event=on_event, should_stop=should_stop)
        return _say_result(result, size, cat, io)
    except phonecert.PhoneCertError as error:
        _say_parts(cat, io, "phonecert", error.code, error.detail)
        return EXIT_PROBLEM
    except lansend.SendError as error:
        _say_parts(cat, io, "lansend", error.code, error.detail)
        return EXIT_PROBLEM
    except KeyboardInterrupt:
        io.say(cat.t("voicefile.send.stopped"))
        return EXIT_PROBLEM
    finally:
        if work:
            shutil.rmtree(work, ignore_errors=True)
