# SPDX-License-Identifier: GPL-3.0-or-later
"""The line a failed command ends with (plan task VS-6.4): two lines that point at the problem report, only after a failure, naming the one problem the command told the person about, and on
every command that can fail."""
import re
from pathlib import Path

import pytest

from vs_refresh_helpers import CAT
from voice_studio.__main__ import reports_failures
from voice_studio.core import describe

PKG = Path(__file__).resolve().parents[1]
NOT_WRAPPED = {"report.py": "the report command itself: a failure to save a report must not point at another report",
               "hear_runner.py": "a program the tool starts, not a command a person runs", "listen_runner.py": "a program the tool starts, not a command a person runs"}


@pytest.fixture(autouse=True)
def nothing_shown_yet():
    describe.forget_errors_shown()
    yield
    describe.forget_errors_shown()


def command_that(code, tells=(), calls=None):
    @reports_failures("update")
    def main(argv=None):
        if calls is not None:
            calls.append(argv)
        for namespace, error in tells:
            describe.error_text(CAT, namespace, error)
        return code
    return main


def test_a_command_that_failed_after_it_began_ends_with_the_two_lines_naming_the_one_problem(capsys):
    assert command_that(1, [("update", "unreachable")])(["get", "v1.1"]) == 1
    out = capsys.readouterr().out.splitlines()
    assert out == [CAT.t("reportcmd.hint.what"), "To see it, run: python3 -m voice_studio.report show --step 'update get' --problem update/unreachable"]


def test_a_command_that_told_of_two_problems_does_not_guess_which_one_is_the_failure(capsys):
    command_that(1, [("update", "unreachable"), ("update", "differs")])(["get"])
    assert capsys.readouterr().out.splitlines()[-1] == "To see it, run: python3 -m voice_studio.report show --step 'update get'"


def test_a_command_that_told_of_no_problem_still_points_at_the_report(capsys):
    command_that(1)([])
    assert capsys.readouterr().out.splitlines()[-1] == "To see it, run: python3 -m voice_studio.report show --step update"


@pytest.mark.parametrize("code", [0, 2, 3, 130])
def test_a_command_that_did_not_fail_after_it_began_prints_nothing_extra(code, capsys):
    assert command_that(code, [("update", "unreachable")])(["get"]) == code
    assert capsys.readouterr().out == ""


def test_the_exit_code_and_the_words_typed_pass_through_untouched(capsys):
    seen = []
    assert command_that(1, calls=seen)(["get", "--to", "/x y"]) == 1 and seen == [["get", "--to", "/x y"]]
    capsys.readouterr()


def test_with_no_words_given_the_real_command_line_is_read(capsys, monkeypatch):
    seen = []
    monkeypatch.setattr("sys.argv", ["prog", "check", "--yes"])
    command_that(1, calls=seen)()
    assert seen == [["check", "--yes"]] and "--step 'update check'" in capsys.readouterr().out


def test_the_wrapped_function_keeps_its_name_and_can_be_reached():
    main = command_that(0)
    assert main.__name__ == "main" and callable(main.__wrapped__)


# ---------------------------------------------------------------- every command

def entry_files():
    return sorted(p for p in PKG.glob("*.py") if re.search(r"^def main\(argv", p.read_text(encoding="utf-8"), re.M))


def test_every_command_a_person_runs_has_the_line_and_names_itself_as_it_is_run():
    found = {p.name for p in entry_files()}
    assert found >= {"__main__.py", "backup.py", "buildenv.py", "projects.py", "recordings.py", "refresh.py", "report.py", "rounds.py", "scratch.py", "uninstall.py", "update.py", "voicefile.py", "voices.py"}
    for path in entry_files():
        text = path.read_text(encoding="utf-8")
        name = "setup" if path.name == "__main__.py" else path.stem
        if path.name in NOT_WRAPPED:
            assert "reports_failures" not in text, path.name
        else:
            assert re.search(r'^@reports_failures\("%s"\)\ndef main\(argv' % re.escape(name), text, re.M), path.name
            if path.name != "__main__.py":
                assert "from .__main__ import TerminalIO, reports_failures" in text, path.name


def test_the_report_command_is_not_wrapped_and_the_exceptions_say_why():
    assert set(NOT_WRAPPED) <= {p.name for p in entry_files()} and all(NOT_WRAPPED.values())
    assert "reports_failures" not in (PKG / "report.py").read_text(encoding="utf-8")


def test_the_command_in_the_line_is_one_that_exists_and_takes_the_options_in_it():
    from voice_studio.core import reportcmd_flow as rf
    assert (PKG / "report.py").is_file() and rf.OPTIONS["show"] >= {"--step", "--problem"}
