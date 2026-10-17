# SPDX-License-Identifier: GPL-3.0-or-later
"""`python3 -m voice_studio.wsl check | phone | idle` (plan task VS-3.6, decision D17, choices P26): what is said and in which order, that nothing is changed without a yes, that the file is
copied before it is changed, that the firewall and restart commands are only printed, and that no program but the two Windows ones is ever started. The Windows drive is a real folder."""
import os
from datetime import datetime
from types import SimpleNamespace

import pytest

from vs_fakes import PROC_NATIVE
from vs_startvoice_helpers import Terminal, implies_permission, leaked_keys
from vs_wsl_helpers import PATH_CMD, VER_10, WslSystem
from voice_studio.core import jobs, text, wsl, wsl_flow as wf
from voice_studio.core.paths import DataHome
from voice_studio.core.system import CommandResult

CAT = text.load_catalog("en")
NOW = datetime(2026, 10, 17, 9, 30, 15)
MIRRORED = "[wsl2]\nnetworkingMode=mirrored\n"
CHECK = "python3 -m voice_studio.wsl"


def say(key, **kw):
    return CAT.t(key, **kw)


def run(tmp_path, *argv, answers=(), interactive=True, system=None):
    io = Terminal(answers, interactive)
    system = system or WslSystem(tmp_path)
    code = wf.run_wsl(list(argv), DataHome(str(tmp_path / "home")), CAT, io, system=system, now=NOW)
    assert leaked_keys(io.text + "\n".join(io.prompts)) == [], "a catalog key was printed instead of words"
    assert implies_permission(io.text) == []
    return code, io, system


def parts(code, detail=""):
    lines = ["  " + say("wsl.error.%s.%s" % (code, p)) for p in ("what", "changed", "next")]
    return lines + (["  " + say("cli.technical", detail=detail)] if detail else [])


def slurp(path):
    with open(path, "rb") as source:
        return source.read()


def programs(system):
    return [argv for argv, _ in system.ran]


# ---------------------------------------------------------------- the commands

def test_with_no_command_or_help_the_commands_are_listed(tmp_path):
    for argv in ((), ("help",), ("--help",), ("-h",)):
        code, io, system = run(tmp_path, *argv)
        assert code == 0 and io.lines == [say("wsl.title"), say("wsl.usage.head"), "  " + say("wsl.usage.check"), "  " + say("wsl.usage.phone"), "  " + say("wsl.usage.idle"),
                                          "  " + say("wsl.usage.options")], argv
        assert system.ran == []


def test_a_command_that_is_not_known_changes_nothing_and_is_named(tmp_path):
    code, io, system = run(tmp_path, "restart")
    assert code == 2 and io.lines == [say("cli.bad_command", command="restart")] and system.ran == []
    assert wf.COMMANDS == ("check", "phone", "idle", "help")


@pytest.mark.parametrize("argv", [("check", "--yes"), ("check", "extra"), ("check", "--port", "9000"), ("phone", "--nope"), ("phone", "extra"), ("idle", "--port", "9000"), ("idle", "extra"),
                                  ("phone", "--windows-user"), ("check", "--windows-user", "A", "--windows-user", "B")])
def test_an_option_a_command_does_not_have_a_word_it_does_not_take_or_a_missing_value_is_told_and_nothing_is_done(tmp_path, argv):
    code, io, system = run(tmp_path, *argv)
    assert code == 2 and system.ran == [] and not os.path.exists(system.config_path()), argv
    assert not any(line == say("wsl.title") for line in io.lines), "nothing was started"


def test_the_options_each_command_publishes_are_the_ones_it_accepts():
    assert wf.OPTIONS == {"check": frozenset({"--windows-user"}), "phone": frozenset({"--yes", "-y", "--windows-user", "--port"}), "idle": frozenset({"--yes", "-y", "--windows-user"})}


# ---------------------------------------------------------------- check

def test_ubuntu_that_is_not_in_windows_is_told_so_and_nothing_is_started(tmp_path):
    code, io, system = run(tmp_path, "check", system=WslSystem(tmp_path, kernel=PROC_NATIVE))
    assert code == 0 and io.lines == [say("wsl.title"), say("wsl.not_wsl")] and system.ran == []


def test_a_plain_wsl_with_no_file_says_what_it_means_for_a_phone_and_for_a_long_round(tmp_path):
    code, io, system = run(tmp_path, "check")
    home = system.c_users + "/Anna"
    assert code == 0 and io.lines == [
        say("wsl.title"), say("wsl.check.head"),
        "  " + say("wsl.check.windows_works"), "  " + say("wsl.check.windows_build", build=22631),
        "  " + say("wsl.check.home", path=home), "  " + say("wsl.check.file_none", name=".wslconfig"),
        "  " + say("wsl.check.mode_unset"), "  " + say("wsl.check.phone_no", command=CHECK + " phone"),
        "  " + say("wsl.check.idle_default", command=CHECK + " idle")]
    assert programs(system) == [(PATH_CMD, "/c", "ver"), (PATH_CMD, "/c", "echo %USERPROFILE%")], "only the two Windows questions, nothing else"
    assert not os.path.exists(system.config_path()), "looking changes nothing"


def test_a_file_that_asks_for_mirrored_and_a_running_ubuntu_that_agrees_says_a_phone_can_reach_it(tmp_path):
    system = WslSystem(tmp_path, wslinfo=CommandResult(0, "mirrored\n"))
    system.write_config("[wsl2]\nnetworkingMode=Mirrored\n[general]\ninstanceIdleTimeout=-1\n")
    code, io, _ = run(tmp_path, "check", system=system)
    assert code == 0 and io.lines[4:] == [
        "  " + say("wsl.check.home", path=system.c_users + "/Anna"), "  " + say("wsl.check.file_there", path=system.config_path()),
        "  " + say("wsl.check.mode_file", mode="mirrored"), "  " + say("wsl.check.mode_running", mode="mirrored"),
        "  " + say("wsl.check.phone_yes"), "  " + say("wsl.check.idle_never")]


def test_a_file_that_asks_for_mirrored_where_the_running_ubuntu_is_not_says_wsl_has_to_be_restarted(tmp_path):
    system = WslSystem(tmp_path, wslinfo=CommandResult(0, "nat\n"))
    system.write_config(MIRRORED)
    code, io, _ = run(tmp_path, "check", system=system)
    assert io.lines[6:9] == ["  " + say("wsl.check.mode_file", mode="mirrored"), "  " + say("wsl.check.mode_running", mode="nat"), "  " + say("wsl.check.mode_restart")]
    assert "  " + say("wsl.check.phone_no", command=CHECK + " phone") in io.lines and "  " + say("wsl.check.phone_yes") not in io.lines


def test_without_wslinfo_the_file_is_what_there_is_to_go_on(tmp_path):
    system = WslSystem(tmp_path)
    system.write_config(MIRRORED)
    code, io, _ = run(tmp_path, "check", system=system)
    assert "  " + say("wsl.check.phone_yes") in io.lines and not any("This Ubuntu is running with" in line for line in io.lines)
    system.write_config("[wsl2]\nnetworkingMode=nat\n")
    assert "  " + say("wsl.check.phone_no", command=CHECK + " phone") in run(tmp_path, "check", system=system)[1].lines


def test_a_running_ubuntu_that_is_mirrored_counts_even_when_the_file_says_nothing(tmp_path):
    system = WslSystem(tmp_path, wslinfo=CommandResult(0, "mirrored\n"))
    code, io, _ = run(tmp_path, "check", system=system)
    assert "  " + say("wsl.check.phone_yes") in io.lines and "  " + say("wsl.check.mode_unset") in io.lines and "  " + say("wsl.check.mode_restart") not in io.lines


def test_a_windows_older_than_the_one_with_mirrored_networking_says_to_copy_the_file_by_hand(tmp_path):
    system = WslSystem(tmp_path, cmd=CommandResult(0, VER_10))
    code, io, _ = run(tmp_path, "check", system=system)
    assert "  " + say("wsl.check.phone_old", need=22621) in io.lines and "  " + say("wsl.check.phone_no", command=CHECK + " phone") not in io.lines
    assert "  " + say("wsl.check.windows_build", build=19045) in io.lines


def test_a_windows_program_that_cannot_be_started_is_said_with_what_to_do_and_the_search_goes_on_without_it(tmp_path):
    system = WslSystem(tmp_path, cmd=CommandResult(1, ""))
    code, io, _ = run(tmp_path, "check", system=system)
    assert io.lines[2:4] == ["  " + say("wsl.check.windows_failed"), "  " + say("wsl.check.windows_failed_next", command="wsl.exe --shutdown")]
    assert "  " + say("wsl.check.home", path=system.c_users + "/Anna") in io.lines, "the only user folder was still found"
    system = WslSystem(tmp_path / "second", cmd=None)
    code, io, _ = run(tmp_path, "check", system=system)
    assert io.lines[2] == "  " + say("wsl.check.windows_missing") and "  " + say("wsl.check.home", path=system.c_users + "/Anna") in io.lines
    assert programs(system) == [], "no Windows program was tried"


def test_a_home_that_cannot_be_told_is_explained_in_three_parts_and_the_rest_is_still_said(tmp_path):
    system = WslSystem(tmp_path, cmd=None, users=("Anna", "Ben"))
    code, io, _ = run(tmp_path, "check", system=system)
    assert code == 0 and io.lines[3:7] == parts("several_users", "Anna, Ben")
    assert "  " + say("wsl.check.idle_default", command=CHECK + " idle") in io.lines
    code, io, _ = run(tmp_path, "check", "--windows-user", "Ben", system=system)
    assert "  " + say("wsl.check.home", path=system.c_users + "/Ben") in io.lines
    code, io, _ = run(tmp_path, "check", "--windows-user=Nobody", system=system)
    assert parts("no_such_user", "Nobody")[0] in io.lines


def test_a_file_that_is_not_plain_text_is_said_and_left_alone(tmp_path):
    system = WslSystem(tmp_path)
    system.write_config("", binary="[wsl2]\n".encode("utf-16"))
    before = slurp(system.config_path())
    code, io, _ = run(tmp_path, "check", system=system)
    assert "  " + say("wsl.check.file_bad", path=system.config_path()) in io.lines and slurp(system.config_path()) == before


@pytest.mark.parametrize("value,line", [("-1", "idle_never"), ("0", "idle_other"), ("15000", "idle_other")])
def test_what_the_file_says_about_stopping_is_said(tmp_path, value, line):
    system = WslSystem(tmp_path)
    system.write_config("[general]\ninstanceIdleTimeout=%s\n" % value)
    code, io, _ = run(tmp_path, "check", system=system)
    expected = {"idle_never": say("wsl.check.idle_never"), "idle_other": say("wsl.check.idle_other", value=value, command=CHECK + " idle")}[line]
    assert io.lines[-1] == "  " + expected


# ---------------------------------------------------------------- phone

def firewall_lines(port=8443):
    add, undo = wsl.firewall_commands(port)
    return [say("wsl.phone.step2", port=port), "    " + add, say("wsl.phone.step2_undo"), "    " + undo, say("wsl.phone.step2_never")]


def after_lines():
    return [say("wsl.phone.step3", command="wsl.exe --shutdown"), say("wsl.phone.step3_after", command="python3 -m voice_studio.voicefile send"), say("wsl.phone.unconfirmed")]


def test_a_yes_changes_the_file_after_showing_the_change_keeps_the_old_one_and_prints_the_commands(tmp_path):
    system = WslSystem(tmp_path)
    system.write_config("[wsl2]\nmemory=8GB\n")
    code, io, _ = run(tmp_path, "phone", answers=["yes"], system=system)
    assert code == 0 and io.lines == (
        [say("wsl.title"), say("wsl.phone.head"), say("wsl.phone.step1"), say("wsl.change.head", path=system.config_path()), "    " + " memory=8GB", "    +networkingMode=mirrored",
         ] + [say("wsl.change.done", backup=system.config_path() + ".bak")] + firewall_lines() + after_lines())
    assert [p.strip() for p in io.prompts] == [say("wsl.change.question")] and wf.RESTART_COMMAND == "wsl.exe --shutdown"
    assert system.read_config() == "[wsl2]\nmemory=8GB\nnetworkingMode=mirrored\n" and slurp(system.config_path() + ".bak") == b"[wsl2]\nmemory=8GB\n"


def test_the_question_comes_after_the_change_is_shown_and_before_anything_is_written(tmp_path):
    system = WslSystem(tmp_path)
    system.write_config("[wsl2]\nmemory=8GB\n")
    seen = []

    class Watching(Terminal):
        def ask(self, prompt):
            seen.append(slurp(system.config_path()))
            return super().ask(prompt)
    io = Watching(["yes"], True)
    wf.run_wsl(["phone"], DataHome(str(tmp_path / "home")), CAT, io, system=system, now=NOW)
    assert seen == [b"[wsl2]\nmemory=8GB\n"] and [e[0] for e in io.events].index("ask") > 0
    shown = [i for i, e in enumerate(io.events) if e == ("say", "    +networkingMode=mirrored")]
    assert shown and shown[0] < [i for i, e in enumerate(io.events) if e[0] == "ask"][0]


@pytest.mark.parametrize("answer", ["no", "n", "", "Yes please", "maybe"])
def test_anything_but_a_yes_changes_nothing_and_prints_no_commands(tmp_path, answer):
    system = WslSystem(tmp_path)
    system.write_config("[wsl2]\nmemory=8GB\n")
    code, io, _ = run(tmp_path, "phone", answers=[answer], system=system)
    assert code == 2 and io.lines[-1] == say("cli.nothing_done") and system.read_config() == "[wsl2]\nmemory=8GB\n"
    assert os.listdir(os.path.dirname(system.config_path())) == [".wslconfig"] and say("wsl.phone.step2", port=8443) not in io.lines


def test_with_nobody_to_ask_nothing_is_changed_and_yes_on_the_command_line_answers_it(tmp_path):
    system = WslSystem(tmp_path)
    code, io, _ = run(tmp_path, "phone", interactive=False, system=system)
    assert code == 2 and io.lines[-1] == say("cli.cannot_ask") and not os.path.exists(system.config_path())
    code, io, _ = run(tmp_path, "phone", "--yes", system=system)
    assert code == 0 and io.prompts == [] and system.read_config() == MIRRORED
    assert say("wsl.change.creates", name=".wslconfig") in io.lines and say("wsl.change.done_new", path=system.config_path()) in io.lines


def test_short_yes_is_the_same_as_yes(tmp_path):
    code, io, system = run(tmp_path, "phone", "-y")
    assert code == 0 and system.read_config() == MIRRORED


def test_a_file_that_already_asks_for_mirrored_is_not_touched_and_the_rest_is_still_said(tmp_path):
    system = WslSystem(tmp_path)
    system.write_config(MIRRORED)
    code, io, _ = run(tmp_path, "phone", system=system)
    assert code == 0 and io.prompts == [] and io.lines == [say("wsl.title"), say("wsl.phone.head"), say("wsl.phone.step1"), say("wsl.phone.step1_ok")] + firewall_lines() + after_lines()
    assert os.listdir(os.path.dirname(system.config_path())) == [".wslconfig"]


def test_the_port_in_the_firewall_command_is_the_one_asked_for(tmp_path):
    system = WslSystem(tmp_path)
    system.write_config(MIRRORED)
    code, io, _ = run(tmp_path, "phone", "--port", "9000", system=system)
    assert firewall_lines(9000)[1] in io.lines and not any("8443" in line for line in io.lines)
    code, io, _ = run(tmp_path, "phone", "--port=1024", system=system)
    assert firewall_lines(1024)[1] in io.lines


@pytest.mark.parametrize("port", ["80", "1023", "65536", "abc", "", "-5", "８４４３"])
def test_a_port_outside_the_range_is_refused_before_anything_is_looked_at_or_changed(tmp_path, port):
    code, io, system = run(tmp_path, "phone", "--port", port, "--yes")
    assert code == 2 and io.lines == [say("voicefile.send.bad_port", low=1024, high=65535)] and system.ran == [] and not os.path.exists(system.config_path())


def test_a_task_that_is_running_is_named_beside_the_restart_instruction(tmp_path, monkeypatch):
    monkeypatch.setattr(wf.jobs, "list_jobs", lambda root: SimpleNamespace(jobs=[SimpleNamespace(status=jobs.JobStatus.RUNNING)], problems=()))
    system = WslSystem(tmp_path)
    system.write_config(MIRRORED)
    code, io, _ = run(tmp_path, "phone", system=system)
    at = io.lines.index(say("wsl.phone.step3", command="wsl.exe --shutdown"))
    assert io.lines[at + 1] == say("wsl.change.task") and code == 0

@pytest.mark.parametrize("status", [jobs.JobStatus.FINISHED, jobs.JobStatus.FAILED, jobs.JobStatus.STOPPED, jobs.JobStatus.INTERRUPTED, jobs.JobStatus.NEVER_STARTED])
def test_a_task_that_has_ended_does_not_count(tmp_path, monkeypatch, status):
    monkeypatch.setattr(wf.jobs, "list_jobs", lambda root: SimpleNamespace(jobs=[SimpleNamespace(status=status)], problems=()))
    assert wf._task_running(DataHome(str(tmp_path))) is False


@pytest.mark.parametrize("status", [jobs.JobStatus.STARTING, jobs.JobStatus.RUNNING, jobs.JobStatus.STOPPING])
def test_every_kind_of_active_task_counts(tmp_path, monkeypatch, status):
    monkeypatch.setattr(wf.jobs, "list_jobs", lambda root: SimpleNamespace(jobs=[SimpleNamespace(status=status)], problems=()))
    assert wf._task_running(DataHome(str(tmp_path))) is True


def test_with_no_task_the_warning_is_not_said(tmp_path):
    system = WslSystem(tmp_path)
    system.write_config(MIRRORED)
    code, io, _ = run(tmp_path, "phone", system=system)
    assert say("wsl.change.task") not in io.lines and wf._task_running(DataHome(str(tmp_path / "home"))) is False


def test_a_windows_that_is_too_old_changes_nothing_and_says_to_copy_by_hand(tmp_path):
    system = WslSystem(tmp_path, cmd=CommandResult(0, VER_10))
    code, io, _ = run(tmp_path, "phone", "--yes", system=system)
    assert code == 2 and io.lines == [say("wsl.title"), say("wsl.check.phone_old", need=22621)] and not os.path.exists(system.config_path())


def test_ubuntu_that_is_not_in_windows_has_nothing_to_set_up(tmp_path):
    code, io, system = run(tmp_path, "phone", "--yes", system=WslSystem(tmp_path, kernel=PROC_NATIVE))
    assert code == 2 and io.lines == [say("wsl.title"), say("wsl.not_wsl")] and system.ran == []


def test_a_home_that_cannot_be_found_changes_nothing_and_says_why_in_three_parts(tmp_path):
    system = WslSystem(tmp_path, cmd=None, users=("Anna", "Ben"))
    code, io, _ = run(tmp_path, "phone", "--yes", system=system)
    assert code == 2 and io.lines[-4:] == parts("several_users", "Anna, Ben")
    code, io, _ = run(tmp_path, "phone", "--yes", "--windows-user", "Ben", system=system)
    assert code == 0 and slurp(system.config_path("Ben")) == MIRRORED.encode() and not os.path.exists(system.config_path("Anna"))
    code, io, _ = run(tmp_path, "phone", "--yes", "--windows-user", "Zed", system=system)
    assert code == 2 and io.lines[-4:] == parts("no_such_user", "Zed")


def test_a_file_that_cannot_be_edited_safely_is_left_alone_and_told_in_three_parts(tmp_path):
    system = WslSystem(tmp_path)
    system.write_config("[wsl2]\nnetworkingMode=nat\nnetworkingMode=none\n")
    code, io, _ = run(tmp_path, "phone", "--yes", system=system)
    assert code == 2 and io.lines[-4:] == parts("duplicate", "networkingMode") and system.read_config() == "[wsl2]\nnetworkingMode=nat\nnetworkingMode=none\n"
    system.write_config("", binary=b"\xff\xfe\x00")
    code, io, _ = run(tmp_path, "phone", "--yes", system=system)
    assert code == 2 and io.lines[-3:] == parts("bad_text") and slurp(system.config_path()) == b"\xff\xfe\x00"
    assert os.listdir(os.path.dirname(system.config_path())) == [".wslconfig"]


def test_a_write_that_fails_is_exit_one_and_says_so_in_three_parts_with_the_systems_words_and_no_commands(tmp_path, monkeypatch):
    def fail(plan, now):
        raise wsl.WslError("not_written", "Permission denied")
    monkeypatch.setattr(wf.wsl, "apply_edit", fail)
    system = WslSystem(tmp_path)
    code, io, _ = run(tmp_path, "phone", "--yes", system=system)
    assert code == 1 and io.lines[-4:] == parts("not_written", "Permission denied") and say("wsl.phone.step2", port=8443) not in io.lines


def test_ctrl_c_while_asking_stops_cleanly_with_the_file_as_it_was(tmp_path):
    system = WslSystem(tmp_path)
    system.write_config("[wsl2]\nmemory=8GB\n")
    code, io, _ = run(tmp_path, "phone", answers=[KeyboardInterrupt()], system=system)
    assert code == 1 and io.lines[-1] == say("wsl.interrupted") and system.read_config() == "[wsl2]\nmemory=8GB\n"


def test_no_command_is_run_but_the_two_windows_questions_and_wslinfo(tmp_path):
    system = WslSystem(tmp_path, wslinfo=CommandResult(0, "nat\n"))
    code, io, _ = run(tmp_path, "phone", "--yes", system=system)
    assert code == 0
    assert set(programs(system)) == {(PATH_CMD, "/c", "ver"), (PATH_CMD, "/c", "echo %USERPROFILE%"), ("/usr/bin/wslinfo", "--networking-mode")}


# ---------------------------------------------------------------- idle

def test_a_yes_sets_the_idle_timeout_keeping_the_old_file_and_says_what_it_means(tmp_path):
    system = WslSystem(tmp_path)
    system.write_config("[wsl2]\nnetworkingMode=mirrored\n")
    code, io, _ = run(tmp_path, "idle", answers=["yes"], system=system)
    assert code == 0 and io.lines == [
        say("wsl.title"), say("wsl.idle.head"), say("wsl.idle.step1"), say("wsl.change.head", path=system.config_path()),
        "     networkingMode=mirrored", "    +", "    +[general]", "    +instanceIdleTimeout=-1",
        say("wsl.change.done", backup=system.config_path() + ".bak"),
        say("wsl.idle.step2", command="wsl.exe --shutdown"), say("wsl.idle.after"), say("wsl.idle.old")]
    assert system.read_config() == "[wsl2]\nnetworkingMode=mirrored\n\n[general]\ninstanceIdleTimeout=-1\n" and slurp(system.config_path() + ".bak") == MIRRORED.encode()
    assert [p.strip() for p in io.prompts] == [say("wsl.change.question")]


def test_idle_with_no_file_makes_one_and_with_the_setting_there_changes_nothing(tmp_path):
    system = WslSystem(tmp_path)
    code, io, _ = run(tmp_path, "idle", "--yes", system=system)
    assert code == 0 and system.read_config() == "[general]\ninstanceIdleTimeout=-1\n" and say("wsl.change.done_new", path=system.config_path()) in io.lines
    code, io, _ = run(tmp_path, "idle", system=system)
    assert code == 0 and io.prompts == [] and say("wsl.idle.step1_ok") in io.lines and say("wsl.change.head", path=system.config_path()) not in io.lines
    assert os.listdir(os.path.dirname(system.config_path())) == [".wslconfig"]


def test_idle_replaces_another_value_and_shows_both_lines(tmp_path):
    system = WslSystem(tmp_path)
    system.write_config("[general]\ninstanceIdleTimeout=15000\n")
    code, io, _ = run(tmp_path, "idle", answers=["yes"], system=system)
    assert "    -instanceIdleTimeout=15000" in io.lines and "    +instanceIdleTimeout=-1" in io.lines and system.read_config() == "[general]\ninstanceIdleTimeout=-1\n"


def test_idle_declined_unasked_and_on_other_systems_changes_nothing(tmp_path):
    system = WslSystem(tmp_path)
    assert run(tmp_path, "idle", answers=["no"], system=system)[0] == 2 and not os.path.exists(system.config_path())
    assert run(tmp_path, "idle", interactive=False, system=system)[0] == 2 and not os.path.exists(system.config_path())
    code, io, _ = run(tmp_path, "idle", "--yes", system=WslSystem(tmp_path, kernel=PROC_NATIVE))
    assert code == 2 and io.lines == [say("wsl.title"), say("wsl.not_wsl")]


def test_idle_names_a_running_task_and_takes_a_user_name(tmp_path, monkeypatch):
    monkeypatch.setattr(wf.jobs, "list_jobs", lambda root: SimpleNamespace(jobs=[SimpleNamespace(status=jobs.JobStatus.RUNNING)], problems=()))
    system = WslSystem(tmp_path, users=("Anna", "Ben"), cmd=None)
    code, io, _ = run(tmp_path, "idle", "--yes", "--windows-user", "Anna", system=system)
    assert code == 0 and io.lines[-4:] == [say("wsl.idle.step2", command="wsl.exe --shutdown"), say("wsl.change.task"), say("wsl.idle.after"), say("wsl.idle.old")]
    assert slurp(system.config_path("Anna")) and not os.path.exists(system.config_path("Ben"))


def test_idle_write_failure_and_ctrl_c(tmp_path, monkeypatch):
    system = WslSystem(tmp_path)
    monkeypatch.setattr(wf.wsl, "apply_edit", lambda plan, now: (_ for _ in ()).throw(wsl.WslError("not_written", "x")))
    code, io, _ = run(tmp_path, "idle", "--yes", system=system)
    assert code == 1 and io.lines[-4:] == parts("not_written", "x")
    code, io, _ = run(tmp_path, "idle", answers=[KeyboardInterrupt()], system=system)
    assert code == 1 and io.lines[-1] == say("wsl.interrupted")


# ---------------------------------------------------------------- found by breaking the code one line at a time

def test_a_windows_that_answers_without_saying_its_build_gets_no_build_line(tmp_path):
    system = WslSystem(tmp_path, cmd=CommandResult(0, "something else\r\n"))
    code, io, _ = run(tmp_path, "check", system=system)
    assert "  " + say("wsl.check.windows_works") in io.lines and not any("The Windows build is" in line for line in io.lines)
    assert "  " + say("wsl.check.phone_old", need=22621) not in io.lines, "an unknown build is not called too old"


def test_a_long_value_in_the_file_is_cut_short_when_it_is_shown(tmp_path):
    system = WslSystem(tmp_path)
    system.write_config("[wsl2]\nnetworkingMode=%s\n[general]\ninstanceIdleTimeout=%s\n" % ("m" * 60, "9" * 60))
    code, io, _ = run(tmp_path, "check", system=system)
    assert "  " + say("wsl.check.mode_file", mode="m" * 40) in io.lines and "  " + say("wsl.check.idle_other", value="9" * 40, command=CHECK + " idle") in io.lines


def test_the_networking_mode_is_not_called_unset_for_a_file_that_cannot_be_read_or_a_home_that_is_not_known(tmp_path):
    bad = WslSystem(tmp_path)
    bad.write_config("", binary=b"\xff\xfe\x00")
    code, io, _ = run(tmp_path, "check", system=bad)
    assert "  " + say("wsl.check.mode_unset") not in io.lines and "  " + say("wsl.check.file_bad", path=bad.config_path()) in io.lines
    lost = WslSystem(tmp_path / "lost", cmd=None, users=("Anna", "Ben"))
    code, io, _ = run(tmp_path, "check", system=lost)
    assert "  " + say("wsl.check.mode_unset") not in io.lines
    there = WslSystem(tmp_path / "there")
    there.write_config("[wsl2]\nmemory=1GB\n")
    assert "  " + say("wsl.check.mode_unset") in run(tmp_path, "check", system=there)[1].lines, "a file with no mode in it is unset"
    assert "  " + say("wsl.check.mode_unset") in run(tmp_path, "check", system=WslSystem(tmp_path / "nofile"))[1].lines, "so is no file"


def test_a_command_that_is_not_known_is_named_in_at_most_sixty_characters(tmp_path):
    code, io, _ = run(tmp_path, "z" * 100)
    assert io.lines == [say("cli.bad_command", command="z" * 60)]


def test_the_time_given_names_the_copy_of_a_second_change_and_without_a_time_the_clock_is_used(tmp_path):
    system = WslSystem(tmp_path)
    system.write_config("[wsl2]\nmemory=1GB\n")
    assert run(tmp_path, "phone", "--yes", system=system)[0] == 0
    assert run(tmp_path, "idle", "--yes", system=system)[0] == 0
    assert sorted(os.listdir(os.path.dirname(system.config_path()))) == [".wslconfig", ".wslconfig.bak", ".wslconfig.bak-20261017-093015"]
    other = WslSystem(tmp_path / "clock")
    other.write_config("[wsl2]\nmemory=1GB\n")
    io = Terminal([], True)
    assert wf.run_wsl(["phone", "--yes"], DataHome(str(tmp_path / "home")), CAT, io, system=other) == 0 and other.read_config().endswith("networkingMode=mirrored\n")
    io = Terminal([], True)
    assert wf.run_wsl(["idle", "--yes"], DataHome(str(tmp_path / "home")), CAT, io, system=other) == 0, "a copy already exists, so the real time names the next one"
    assert len(os.listdir(os.path.dirname(other.config_path()))) == 3
