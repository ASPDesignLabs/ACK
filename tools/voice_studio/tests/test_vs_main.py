# SPDX-License-Identifier: GPL-3.0-or-later
"""The entry point (plan task VS-1.4): `python3 -m voice_studio` wires the real parts to setup_flow and keeps the password in sudo's hands."""
import io as stdlib_io

import pytest

from pathlib import Path

from vs_fakes import ALL_PACKAGES, ALL_TOOLS, FakeSystem
from voice_studio import __main__ as entry
from voice_studio.core import fetch
from voice_studio.core.consent import make_consent
from voice_studio.core.system import CommandResult
from voice_studio.core.text import load_catalog

CAT = load_catalog("en")


def test_the_terminal_is_interactive_only_when_input_is_a_terminal(monkeypatch):
    class Stdin:
        def __init__(self, tty):
            self.tty = tty

        def isatty(self):
            return self.tty

    monkeypatch.setattr(entry.sys, "stdin", Stdin(True))
    assert entry.TerminalIO().interactive is True
    monkeypatch.setattr(entry.sys, "stdin", Stdin(False))
    assert entry.TerminalIO().interactive is False
    monkeypatch.setattr(entry.sys, "stdin", None)
    assert entry.TerminalIO().interactive is False


def test_asking_returns_what_was_typed_and_nothing_when_input_has_ended(monkeypatch):
    shown = []
    monkeypatch.setattr("builtins.input", lambda prompt="": shown.append(prompt) or "yes")
    assert entry.TerminalIO().ask("Install? ") == "yes" and shown == ["Install? "]

    def closed(prompt=""):
        raise EOFError

    monkeypatch.setattr("builtins.input", closed)
    assert entry.TerminalIO().ask("Install? ") is None


def test_saying_prints_the_line(capsys):
    entry.TerminalIO().say("hello")
    assert capsys.readouterr().out == "hello\n"


def test_the_package_command_runs_in_the_persons_own_terminal_with_the_agreement_it_was_given(monkeypatch):
    seen = {}

    def fake(consent, argv, ids, **kwargs):
        seen.update(consent=consent, argv=list(argv), ids=list(ids), kwargs=kwargs)
        return CommandResult(0, "", "")

    monkeypatch.setattr(entry.fetch, "run_networked", fake)
    consent = make_consent([], ["apt:git"])
    assert entry.run_apt(consent, ["sudo", "apt-get", "install", "-y", "git"], ["apt:git"]) == 0
    assert seen["consent"] is consent and seen["ids"] == ["apt:git"] and seen["kwargs"] == {"inherit_stdio": True}


def test_the_exit_status_of_the_package_command_is_passed_on(monkeypatch):
    monkeypatch.setattr(entry.fetch, "run_networked", lambda *a, **k: CommandResult(100, "", ""))
    assert entry.run_apt(make_consent([], ["apt:git"]), ["sudo", "apt-get", "update"], ["apt:git"]) == 100


def test_a_refused_or_failed_start_is_a_failure_not_a_traceback():
    assert entry.run_apt(None, ["sudo", "apt-get", "update"], ["apt:update"]) == 1               # no agreement: refused before anything starts
    assert entry.run_apt(make_consent([], ["apt:update"]), ["/definitely/not/a/program"], ["apt:update"]) == 1


def test_an_unknown_option_is_named_and_nothing_else_happens(capsys, monkeypatch):
    monkeypatch.setattr(entry, "RealSystem", lambda: pytest.fail("the computer must not be looked at for a mistyped option"))
    assert entry.main(["--chek"]) == 2
    assert "--chek" in capsys.readouterr().out


def test_main_looks_at_the_computer_it_is_given_and_reports_ready(capsys, monkeypatch):
    monkeypatch.setattr(entry, "RealSystem", lambda: FakeSystem())
    assert entry.main(["--check"]) == 0
    assert CAT.t("setup.check_ready") in capsys.readouterr().out


def test_main_with_programs_missing_and_nothing_to_ask_changes_nothing(capsys, monkeypatch):
    system = FakeSystem(installed=[p for p in ALL_PACKAGES if p != "git"], tools={n: p for n, p in ALL_TOOLS.items() if n != "git"})
    monkeypatch.setattr(entry, "RealSystem", lambda: system)
    monkeypatch.setattr(entry, "run_apt", lambda *a: pytest.fail("nothing may be installed without a yes"))
    monkeypatch.setattr(entry.sys, "stdin", stdlib_io.StringIO(""))              # not a terminal
    assert entry.main([]) == 2
    assert CAT.t("setup.cannot_ask") in capsys.readouterr().out


def test_the_entry_point_uses_only_the_networked_door_for_package_commands():
    source = Path(entry.__file__).read_text(encoding="utf-8")
    assert "subprocess" not in source and "os.system" not in source and "getpass" not in source
    assert fetch.run_networked is entry.fetch.run_networked
