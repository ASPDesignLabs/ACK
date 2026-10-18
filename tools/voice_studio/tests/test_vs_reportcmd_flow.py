# SPDX-License-Identifier: GPL-3.0-or-later
"""The terminal front for the problem report (plan task VS-6.4): what `show` and `save` say, what they ask, what the file holds, and what they leave alone.
The flows are the real code on a real folder; the computer is a stand-in with names the tests plant and look for."""
import os
import stat
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

import pytest

from vs_fakes import FakeSystem
from vs_refresh_helpers import CAT, TermIO
from vs_rounds_helpers import fake_job
from vs_startvoice_helpers import implies_permission
from voice_studio.core import describe, reportcmd as rc, reportcmd_flow as rf
from voice_studio.core.paths import DataHome
from voice_studio.core.project import Consent, create_project
from voice_studio.core.report import MAX_LOG_LINES

NOW = datetime(2026, 10, 10, 12, 30, 5, tzinfo=timezone.utc)
START, END = "---- the report starts on the next line ----", "---- the report ends on the line before this one ----"
CANARIES = ["zephyr9", "fortress-lab", "marigold", "zelda quartermain", "10.1.2.3"]


class Rig:
    def __init__(self, tmp_path):
        self.tmp = Path(tmp_path)
        self.home_dir = self.tmp / "zephyr9-home"
        self.home = DataHome(str(self.home_dir))
        os.makedirs(self.home.jobs)
        self.project = create_project(self.home.projects, "Marigold Q", "someone_else", Consent("Zelda Quartermain", "a voice for ACK", "today", "ask me", "spoken"))
        self.system = FakeSystem(home=str(self.home_dir), environ={"USER": "zephyr9", "DISPLAY": ":0"}, hostname="fortress-lab", disks={self.home.root: (500 * 2**30, 300 * 2**30)})

    def tree(self):
        found = {}
        for path in sorted(self.tmp.rglob("*")):
            found[str(path.relative_to(self.tmp))] = path.read_bytes() if path.is_file() and not path.is_symlink() else None
        return found


@pytest.fixture(autouse=True)
def nothing_shown_yet():
    describe.forget_errors_shown()
    yield
    describe.forget_errors_shown()


@pytest.fixture
def rig(tmp_path):
    return Rig(tmp_path)


def run(rig, *argv, answers=(), interactive=True):
    io = TermIO(answers, interactive)
    code = rf.run_report(list(argv), rig.home, CAT, io, system=rig.system, now=NOW)
    return code, io


def shown(io):
    """The lines between the two rules, as the file would hold them."""
    start, end = io.lines.index(START), io.lines.index(END)
    return "\n".join(io.lines[start + 1:end]) + "\n"


def leaks(text):
    folded = unicodedata.normalize("NFC", text).casefold()
    return [c for c in CANARIES if c in folded]


# ---------------------------------------------------------------- help and the command line

def test_no_command_and_help_list_the_two_commands_and_what_the_report_leaves_out(rig):
    before = rig.tree()
    for argv in ((), ("help",), ("--help",), ("-h",)):
        code, io = run(rig, *argv)
        assert code == 0 and io.prompts == [] and io.lines[0] == "ACK Voice Studio: problem report" and "Commands:" in io.lines
        assert io.lines[2].startswith("  show [--problem name]") and io.lines[3].startswith("  save --to file")
        assert "  Names, folders and the computer's name are blanked, and there are no recordings, no text you made and no phrases." in io.lines
    assert rig.tree() == before


def test_an_unknown_command_is_named_and_nothing_is_built(rig):
    code, io = run(rig, "send")
    assert code == 2 and "send" in io.text and START not in io.lines


def test_the_options_each_command_publishes_are_the_options_it_accepts(rig):
    assert rf.COMMANDS == ("show", "save", "help")
    assert rf.OPTIONS["show"] == frozenset({"--problem", "--detail", "--step", "--job", "--include-log"})
    assert rf.OPTIONS["save"] == rf.OPTIONS["show"] | frozenset({"--to", "--replace", "--yes", "-y"})
    for option in ("--to", "--replace", "--yes", "-y"):
        code, io = run(rig, "show", option, "x")
        assert code == 2 and option in io.text and START not in io.lines, option
    code, io = run(rig, "save", "--nonsense", "--to", str(rig.tmp / "r.txt"))
    assert code == 2 and "--nonsense" in io.text and not (rig.tmp / "r.txt").exists()
    assert run(rig, "show", "extra")[0] == 2 and run(rig, "save", "extra", "--to", str(rig.tmp / "r.txt"), "--yes")[0] == 2 and not (rig.tmp / "r.txt").exists()


def test_every_usage_line_has_words():
    for key in rf.USAGE:
        assert CAT.has(key)


# ---------------------------------------------------------------- show

def test_show_prints_the_whole_report_between_two_rules_and_changes_nothing(rig):
    before = rig.tree()
    code, io = run(rig, "show")
    assert code == 0 and io.prompts == []
    assert io.lines[:2] == ["ACK Voice Studio: problem report", START] and io.lines[-3] == END and io.lines[-2] == "Nothing was saved and nothing was sent."
    report = shown(io)
    assert report.startswith("ACK Voice Studio problem report\n") and "Time (UTC): 2026-10-10 12:30:05" in report and "\nVersions\n" in report and "\nThis computer\n" in report
    assert CAT.t("report.no_error") in report
    assert rig.tree() == before, "show wrote nothing"


def test_show_says_how_to_keep_it_with_a_whole_path_example(rig):
    code, io = run(rig, "show")
    assert io.lines[-1] == ("To keep it as a file, run the same command again with save instead of show, and --to with the whole path of the file. "
                            "For example: python3 -m voice_studio.report save --to ~/problem-report.txt")


def test_the_step_the_problem_and_its_detail_are_in_the_report_with_the_words_for_the_problem(rig):
    code, io = run(rig, "show", "--step", "update get v1.1", "--problem", "update/unreachable", "--detail", "fatal: unable to access the place")
    report = shown(io)
    assert code == 0 and "Step: update get v1.1" in report and "Problem: update / unreachable" in report
    assert "The place the releases are kept could not be asked, or it did not give the release." in report and "More detail: fatal: unable to access the place" in report


def test_the_computers_facts_come_from_the_computer_and_the_time_is_the_one_given(rig):
    code, io = run(rig, "show")
    report = shown(io)
    assert "Time (UTC): 2026-10-10 12:30:05" in report and "Python: 3.12.3" in report and "Operating system: Ubuntu 24.04" in report
    assert "300.0 GiB free of 500.0 GiB" in report


def test_the_real_clock_is_used_when_none_is_given(rig):
    io = TermIO()
    assert rf.run_report(["show"], rig.home, CAT, io, system=rig.system) == 0
    assert "Time (UTC): %d-" % datetime.now(timezone.utc).year in shown(io)


def test_no_name_the_computer_or_the_projects_know_is_in_what_is_shown_however_it_was_typed(rig):
    rig.system.listings["/mnt/c/Users"] = []
    code, io = run(rig, "show", "--step", "MARIGOLD Q failed for Zelda Quartermain on fortress-lab as zephyr9 at 10.1.2.3 in %s" % rig.home_dir,
                   "--problem", "update/unreachable", "--detail", "cannot reach %s/projects/marigold-q from 10.1.2.3 (zephyr9@fortress-lab)" % rig.home.root)
    assert code == 0 and leaks(io.text) == [], leaks(io.text)
    assert "<person-1>" in shown(io) and "<computer>" in shown(io)


def test_who_agreed_is_blanked_as_a_name_as_well_as_the_project_name(rig):
    code, io = run(rig, "show", "--step", "Zelda Quartermain's voice")
    assert code == 0 and "zelda" not in io.text.lower() and "quartermain" not in io.text.lower()


def test_the_kind_of_voice_is_not_taken_for_a_name(rig):
    create_project(rig.home.projects, "Second one", "own")
    code, io = run(rig, "show", "--step", "my own voice, someone_else asked")
    assert "my own voice, someone_else asked" in shown(io), "the words own and someone_else are not names"


def test_a_bad_problem_name_builds_nothing(rig):
    code, io = run(rig, "show", "--problem", "update/nothing_like_it")
    assert code == 2 and START not in io.lines
    assert io.lines[-4:] == ["That is not a problem name the tool knows.", "Nothing was built or saved.", "Use the name the failure screen gave, written like update/unreachable, or leave --problem out.",
                             "  Technical detail: update/nothing_like_it"]


def test_a_problem_with_no_detail_has_no_more_detail_line(rig):
    code, io = run(rig, "show", "--problem", "update/unreachable")
    assert code == 0 and "More detail" not in shown(io) and "Problem: update / unreachable" in shown(io)


def test_a_detail_without_a_problem_builds_nothing(rig):
    code, io = run(rig, "show", "--detail", "fatal: x")
    assert code == 2 and START not in io.lines and io.lines[-3] == "--detail goes with --problem."


@pytest.mark.parametrize("argv, line", [(("--problem=",), "That is not a problem name the tool knows."), (("--detail=",), "--detail goes with --problem."), (("--job=",), "There is no such task."),
                                         (("--problem=", "--detail=x"), "That is not a problem name the tool knows.")])
def test_an_option_given_with_nothing_after_it_is_still_that_option_and_is_not_skipped(rig, argv, line):
    code, io = run(rig, "show", *argv)
    assert code == 2 and START not in io.lines and line in io.lines


def test_a_step_is_cut_to_its_limit_before_it_is_read(rig):
    code, io = run(rig, "show", "--step", "w" * (rc.MAX_STEP + 50))
    assert "Step: " + "w" * 200 + "\n" in shown(io) and "w" * 201 not in shown(io) and rc.MAX_STEP == 200


def test_a_log_asked_for_without_a_task_builds_nothing(rig):
    code, io = run(rig, "show", "--include-log")
    assert code == 2 and START not in io.lines and io.lines[-3] == "--include-log goes with --job."


# ---------------------------------------------------------------- show: a task

def failed_task(rig, **over):
    kw = dict(name="20261011-000001-train-0001", exit_code=1, error="the trainer stopped in /home/zephyr9/x for fortress-lab")
    kw.update(over)
    return fake_job(rig.home.jobs, ["x"], "failed", **kw)


def test_a_task_is_added_by_its_id_or_as_the_last_one_with_how_it_ended(rig):
    info = failed_task(rig)
    for wanted in (info.id, "last"):
        code, io = run(rig, "show", "--job", wanted)
        report = shown(io)
        assert code == 0 and "\n%s\n" % CAT.t("report.section.job") in report
        for label, value in (("job_kind", "train"), ("job_status", info.status.value), ("exit_code", "1")):
            assert "  %s: %s" % (CAT.t("report.label." + label), value) in report
        assert leaks(report) == []


def test_without_the_log_asked_for_the_end_of_the_log_is_left_out_and_says_so(rig):
    info = failed_task(rig)
    Path(info.dir, "log.txt").write_text("epoch 1\nMarigold Q said hello to fortress-lab\n")
    code, io = run(rig, "show", "--job", "last")
    report = shown(io)
    assert "epoch 1" not in report and "hello" not in report and CAT.t("report.log_left_out") in report


def test_with_the_log_asked_for_its_end_is_in_it_with_names_blanked_and_a_warning(rig):
    info = failed_task(rig)
    Path(info.dir, "log.txt").write_text("epoch 1\nMarigold Q said hello to fortress-lab\n")
    code, io = run(rig, "show", "--job", "last", "--include-log")
    report = shown(io)
    assert CAT.t("report.log_note") in report and "  | epoch 1" in report and "  | <person-1> said hello to <computer>" in report and leaks(io.text) == []


def test_only_the_last_lines_of_a_long_log_are_taken(rig):
    info = failed_task(rig)
    Path(info.dir, "log.txt").write_text("".join("line %03d\n" % i for i in range(MAX_LOG_LINES + 30)))
    code, io = run(rig, "show", "--job", "last", "--include-log")
    report = shown(io)
    assert "  | line %03d" % (MAX_LOG_LINES + 29) in report and "  | line 029" not in report and "  | line 030" in report


def test_no_such_task_builds_nothing(rig):
    code, io = run(rig, "show", "--job", "last")
    assert code == 2 and START not in io.lines and io.lines[-4] == "There is no such task."
    failed_task(rig)
    code, io = run(rig, "show", "--job", "20261011-000001")
    assert code == 2 and io.lines[-4] == "There is no such task." and io.lines[-1] == "  Technical detail: 20261011-000001"


# ---------------------------------------------------------------- save: asks first

def test_save_shows_the_report_then_asks_once_and_a_no_writes_nothing(rig):
    target = rig.tmp / "r.txt"
    before = rig.tree()
    code, io = run(rig, "save", "--to", str(target), answers=["no"])
    assert code == 2 and io.prompts == ["Save exactly this report to %s now? Type yes to go on. " % target] and io.lines[-1] == "Nothing was done."
    assert START in io.lines and io.lines.index(END) < io.events.index(("ask", io.prompts[0])) and rig.tree() == before


def test_with_nobody_to_ask_nothing_is_written(rig):
    target = rig.tmp / "r.txt"
    code, io = run(rig, "save", "--to", str(target), interactive=False)
    assert code == 2 and not target.exists() and io.lines[-1] == "There was nobody to ask. To say yes on the command line, add --yes. Nothing was done."


def test_a_yes_saves_exactly_the_text_that_was_shown_and_only_the_owner_can_read_it(rig):
    target = rig.tmp / "r.txt"
    code, io = run(rig, "save", "--to", str(target), "--step", "update get", answers=["yes"])
    assert code == 0 and target.read_bytes() == shown(io).encode("utf-8") and stat.S_IMODE(target.stat().st_mode) == 0o600
    assert io.lines[-2] == "Saved %d bytes to %s. It holds exactly the text shown above, and only you can read it. Nothing was sent anywhere." % (target.stat().st_size, target)
    assert io.lines[-1] == "Give the file to the helper yourself. The tool does not send it."


def test_dash_dash_yes_and_dash_y_answer_the_question(rig):
    for option, name in (("--yes", "a.txt"), ("-y", "b.txt")):
        code, io = run(rig, "save", "--to", str(rig.tmp / name), option)
        assert code == 0 and io.prompts == [] and (rig.tmp / name).exists()


def test_save_writes_only_the_one_file(rig):
    before = set(rig.tree())
    code, io = run(rig, "save", "--to", str(rig.tmp / "r.txt"), "--yes")
    assert code == 0 and set(rig.tree()) - before == {"r.txt"}


def test_the_saved_file_has_no_name_the_computer_or_the_projects_know(rig):
    target = rig.tmp / "r.txt"
    code, io = run(rig, "save", "--to", str(target), "--yes", "--step", "Marigold Q at fortress-lab as zephyr9", "--problem", "update/unreachable", "--detail", "10.1.2.3 refused Zelda Quartermain")
    assert code == 0 and leaks(target.read_text(encoding="utf-8")) == []


# ---------------------------------------------------------------- save: where

def test_save_needs_a_place_and_builds_nothing_without_one(rig):
    code, io = run(rig, "save", "--yes")
    assert code == 2 and START not in io.lines and io.lines[-3] == "Say where to save the report."


def test_a_place_that_is_not_a_whole_path_or_has_no_folder_is_refused_before_anything_is_shown(rig):
    code, io = run(rig, "save", "--to", "r.txt", "--yes")
    assert code == 2 and START not in io.lines and io.lines[-4] == "Give the whole path of the file, starting with a slash or with ~."
    code, io = run(rig, "save", "--to", str(rig.tmp / "nowhere" / "r.txt"), "--yes")
    assert code == 2 and START not in io.lines and io.lines[-4] == "The folder for that file does not exist." and not (rig.tmp / "nowhere").exists()


def test_an_empty_place_is_not_a_whole_path(rig):
    code, io = run(rig, "save", "--to=", "--yes")
    assert code == 2 and START not in io.lines and io.lines[-3] == "Give the whole path of the file, starting with a slash or with ~."
    assert "Say where to save the report." not in io.lines


def test_whether_an_existing_file_may_be_replaced_is_passed_on_to_the_writer_as_it_was_given(rig, monkeypatch):
    asked = []
    real = rc.write_report

    def watching(path, report, overwrite=False):
        asked.append(overwrite)
        return real(path, report, overwrite=overwrite)
    monkeypatch.setattr(rc, "write_report", watching)
    assert run(rig, "save", "--to", str(rig.tmp / "a.txt"), "--yes")[0] == 0 and run(rig, "save", "--to", str(rig.tmp / "b.txt"), "--yes", "--replace")[0] == 0
    assert asked == [False, True]


def test_a_file_that_is_there_is_left_alone(rig):
    target = rig.tmp / "r.txt"
    target.write_text("mine")
    code, io = run(rig, "save", "--to", str(target), "--yes")
    assert code == 2 and target.read_text() == "mine" and START not in io.lines
    assert io.lines[-4:-1] == ["There is already a file at that place.", "It was left as it is and nothing was saved.", "Choose another name, or add --replace to replace it."]


def test_replace_says_the_file_will_be_replaced_asks_and_replaces_only_after_a_yes(rig):
    target = rig.tmp / "r.txt"
    target.write_text("mine")
    code, io = run(rig, "save", "--to", str(target), "--replace", answers=["no"])
    assert code == 2 and target.read_text() == "mine" and "The file %s is there already and will be replaced." % target in io.lines
    code, io = run(rig, "save", "--to", str(target), "--replace", answers=["yes"])
    assert code == 0 and target.read_bytes() == shown(io).encode("utf-8")


def test_replace_does_not_touch_a_folder_or_a_link_and_the_plain_save_says_nothing_about_replacing(rig):
    (rig.tmp / "dir").mkdir()
    (rig.tmp / "real.txt").write_text("real")
    os.symlink(rig.tmp / "real.txt", rig.tmp / "link.txt")
    for name in ("dir", "link.txt"):
        code, io = run(rig, "save", "--to", str(rig.tmp / name), "--replace", "--yes")
        assert code == 2 and io.lines[-4] == "That place is a folder or something that is not a plain file.", name
    assert (rig.tmp / "real.txt").read_text() == "real"
    code, io = run(rig, "save", "--to", str(rig.tmp / "new.txt"), "--yes")
    assert not any("will be replaced" in line for line in io.lines)


def test_replace_on_a_place_with_nothing_there_is_an_ordinary_save(rig):
    code, io = run(rig, "save", "--to", str(rig.tmp / "r.txt"), "--replace", "--yes")
    assert code == 0 and (rig.tmp / "r.txt").exists() and not any("will be replaced" in line for line in io.lines)


def test_a_folder_a_cloud_service_copies_gets_a_warning_and_is_still_the_persons_to_choose(rig):
    (rig.tmp / "OneDrive").mkdir()
    code, io = run(rig, "save", "--to", str(rig.tmp / "OneDrive" / "r.txt"), answers=["yes"])
    assert code == 0 and (rig.tmp / "OneDrive" / "r.txt").exists()
    warning = [l for l in io.lines if l.startswith("Take care: ")]
    assert len(warning) == 1 and "OneDrive" in warning[0] and io.lines.index(warning[0]) > io.lines.index(END)
    code, io = run(rig, "save", "--to", str(rig.tmp / "plain.txt"), "--yes")
    assert not any(l.startswith("Take care: ") for l in io.lines)


def test_a_log_in_the_report_is_named_in_the_question_s_lead_up(rig):
    info = failed_task(rig)
    Path(info.dir, "log.txt").write_text("epoch 1\n")
    code, io = run(rig, "save", "--to", str(rig.tmp / "r.txt"), "--job", "last", "--include-log", answers=["no"])
    assert "This report includes the end of a task's log, which may contain words from your recordings. Read it above before you say yes." in io.lines
    code, io = run(rig, "save", "--to", str(rig.tmp / "r.txt"), "--job", "last", answers=["no"])
    assert not any("includes the end of a task's log" in line for line in io.lines)
    code, io = run(rig, "save", "--to", str(rig.tmp / "r.txt"), "--job", "last", "--include-log", "--yes")
    assert code == 0, "asking for a log that is empty is not an error"


def test_a_log_asked_for_when_the_task_has_none_is_not_warned_about(rig):
    failed_task(rig)
    code, io = run(rig, "save", "--to", str(rig.tmp / "r.txt"), "--job", "last", "--include-log", answers=["no"])
    assert not any("includes the end of a task's log" in line for line in io.lines)


# ---------------------------------------------------------------- save: when it goes wrong

def test_a_file_that_cannot_be_written_says_so_in_three_parts_and_leaves_none(rig, monkeypatch):
    target = rig.tmp / "r.txt"

    def half(path, report, overwrite=False):
        Path(path).write_bytes(b"half")
        raise OSError(28, "No space left on device")
    monkeypatch.setattr(rc, "write_report", half)
    code, io = run(rig, "save", "--to", str(target), "--yes")
    assert code == 1 and not target.exists()
    assert io.lines[-4:] == ["The report could not be saved.", "No half-written file was kept.", "Check that the folder can be written to and has room, or choose another place.",
                             "  Technical detail: No space left on device"]


def test_ctrl_c_while_saving_says_so_and_leaves_no_half_file(rig, monkeypatch):
    target = rig.tmp / "r.txt"

    def interrupted(path, report, overwrite=False):
        Path(path).write_bytes(b"half")
        raise KeyboardInterrupt
    monkeypatch.setattr(rc, "write_report", interrupted)
    code, io = run(rig, "save", "--to", str(target), "--yes")
    assert code == 1 and io.lines[-1] == "Stopped. A report file that was being written was removed again." and not target.exists()


def test_ctrl_c_while_showing_stops_cleanly(rig, monkeypatch):
    def interrupted(*a, **kw):
        raise KeyboardInterrupt
    monkeypatch.setattr(rf.rp, "build_report", interrupted)
    code, io = run(rig, "show")
    assert code == 1 and io.lines[-1] == "Stopped. A report file that was being written was removed again."


# ---------------------------------------------------------------- the words

def test_nothing_the_command_says_outside_the_report_implies_permission_or_prints_a_key(rig):
    from vs_startvoice_helpers import leaked_keys
    code, io = run(rig, "save", "--to", str(rig.tmp / "r.txt"), "--yes", "--problem", "update/unreachable")
    start, end = io.lines.index(START), io.lines.index(END)
    outside = "\n".join(io.lines[:start] + io.lines[end + 1:])
    assert implies_permission(outside) == [] and leaked_keys(outside) == []


def test_the_command_can_be_started_from_a_terminal(capsys, monkeypatch, tmp_path):
    from voice_studio import report
    monkeypatch.setenv("HOME", str(tmp_path))
    assert report.main(["help"]) == 0
    assert "ACK Voice Studio: problem report" in capsys.readouterr().out
