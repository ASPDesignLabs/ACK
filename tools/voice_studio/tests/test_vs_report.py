# SPDX-License-Identifier: GPL-3.0-or-later
"""The problem report (plan task VS-1.8, decision D22): what it holds, what it can never hold, and canary strings that must not survive.

A canary is a made-up name, folder, address or token planted everywhere a real one could turn up. If any is still readable in the report, the
test fails: that is the whole point of the file.
"""
import os
import stat
import unicodedata
from dataclasses import fields, replace
from datetime import datetime, timezone
from pathlib import Path

import pytest

from vs_fakes import FakeSystem, wsl2
from voice_studio.core import jobs, preflight, report as rp
from voice_studio.core.jobs import JobInfo, JobSpec, JobStatus
from voice_studio.core.report import Identity, Redactor, ReportInput
from voice_studio.core.system import RealSystem
from voice_studio.core.text import load_catalog

CAT = load_catalog("en")
NOW = datetime(2026, 10, 10, 12, 30, 5, tzinfo=timezone.utc)
ID = Identity(user="zephyr9", home="/home/zephyr9", hostname="fortress-lab", data_home="/home/zephyr9/ack-voice-studio", windows_users=("Kowalczyk",),
              people=(("marigold-q", "Marigold Q"), ("jose", "Jos\u00E9"), ("al", "Al"), ("anna-maria", "Anna Maria"), ("anna", "Anna")))

CANARIES = ["zephyr9", "fortress-lab", "kowalczyk", "marigold", "jose", "marigold@example.org", "192.168.1.77", "abcdefgh12345", "backup-drive-x", "10.0.0.5",
            "fe80::1ff:fe23:4567:890a", "aa:bb:cc:dd:ee:ff", "nas-share-7", "anna maria"]


def leaks(text):
    folded = unicodedata.normalize("NFC", text).casefold()
    return [c for c in CANARIES if c in folded or unicodedata.normalize("NFD", c) in unicodedata.normalize("NFD", folded)]


DIRTY = ("/home/zephyr9/ack-voice-studio/projects/marigold-q/scratch/x.bin failed on fortress-lab: Marigold Q, JOS\u00C9 and Jose\u0301 and ANNA MARIA wrote "
         "to marigold@example.org from 192.168.1.77 and 10.0.0.5 and fe80::1ff:fe23:4567:890a (aa:bb:cc:dd:ee:ff) with https://x/?token=AbCdEfGh12345 "
         "at /media/zephyr9/BACKUP-DRIVE-X/ack-voice-scratch/marigold-q and /run/media/zephyr9/BACKUP-DRIVE-X/y and /mnt/NAS-SHARE-7/z "
         "and C:\\Users\\Kowalczyk\\Documents and /mnt/c/Users/Kowalczyk/Desktop, user zephyr9 (ZEPHYR9)")


def make_input(**over):
    base = dict(now=NOW, identity=ID, step="download voice-mike for marigold-q", python_version=(3, 12, 3))
    base.update(over)
    return ReportInput(**base)


def job_info(**over):
    base = dict(id="20261010-120000-train-ab12", dir="/home/zephyr9/ack-voice-studio/state/jobs/x", spec=JobSpec("train", "marigold-q", ("x",)), started_at="t",
                status=JobStatus.FAILED, exit_code=1, signal=None, error="", runner_pid=1)
    base.update(over)
    return JobInfo(**base)


# ---------------------------------------------------------------- the redactor

def test_every_canary_planted_in_one_dirty_line_is_gone():
    out = Redactor(ID).apply(DIRTY)
    assert leaks(out) == [], out
    assert "<person-1>" in out and "<computer>" in out and "<email>" in out and "<address>" in out and "token=<token>" in out and "<user>" in out


def test_paths_keep_their_shape_so_the_report_still_makes_sense():
    out = Redactor(ID).apply("/home/zephyr9/Documents /home/someoneelse/x /mnt/c/Users/Kowalczyk/Desktop C:\\Users\\Kowalczyk\\x /media/zephyr9/BACKUP-DRIVE-X/y")
    assert out == "~/Documents ~/x /mnt/c/Users/<windows-user>/Desktop C:\\Users\\<windows-user>\\x /media/<user>/<drive>/y"
    assert Redactor(ID).apply("/home/zephyr9/ack-voice-studio/projects/marigold-q") == "<voice-studio>/projects/<person-1>"
    assert Redactor(ID).apply("/mnt/c/Windows /mnt/d/data") == "/mnt/c/Windows /mnt/d/data"       # a Windows drive letter is not a label


@pytest.mark.parametrize("text", ["Marigold Q", "MARIGOLD Q", "marigold q", "marigold-q", "MARIGOLD-Q"])
def test_a_name_is_found_in_any_case(text):
    assert Redactor(ID).apply("hello " + text + " there") == "hello <person-1> there"


def test_an_accented_name_is_found_however_it_was_typed():
    for form in ("Jos\u00E9", "Jose\u0301", "JOS\u00C9", "jos\u00E9"):
        assert Redactor(ID).apply("to " + form + " now") == "to <person-2> now", repr(form)


def test_a_name_stored_in_one_form_is_found_in_text_written_in_the_other():
    decomposed_name = Identity(people=(("j", "Jose\u0301"),))
    composed_name = Identity(people=(("j", "Jos\u00E9"),))
    assert Redactor(decomposed_name).apply("to Jos\u00E9 now") == "to <person-1> now"
    assert Redactor(decomposed_name).apply("to Jose\u0301 now") == "to <person-1> now"
    assert Redactor(composed_name).apply("to Jose\u0301 now") == "to <person-1> now"


def test_one_thing_handed_to_the_redactor_is_cut_to_a_fixed_length_first():
    assert len(Redactor(ID).apply("a" * 100_000)) == rp.MAX_PIECE_CHARS


def test_the_whole_report_is_cut_at_its_limit_on_a_character_boundary(monkeypatch):
    monkeypatch.setattr(rp, "MAX_REPORT_BYTES", 400)
    out = rp.build_report(make_input(step="\u00E9" * 1000), CAT)
    assert len(out.to_bytes()) <= 400 and out.text.endswith("\n")
    out.to_bytes().decode("utf-8")


def test_the_longest_name_wins_so_no_stray_part_of_a_longer_name_is_left():
    assert Redactor(ID).apply("Anna Maria and Anna") == "<person-4> and <person-5>"


def test_a_short_name_is_only_hidden_as_a_whole_word_and_a_single_letter_is_left_alone():
    assert Redactor(ID).apply("Al said total and altitude") == "<person-3> said total and altitude"
    one = Identity(people=(("a", "A"),))
    assert Redactor(one).apply("A name and a cat") == "A name and a cat"       # a known, stated limit: hiding one letter would blank the report


def test_a_four_letter_login_cannot_damage_ordinary_words_and_a_longer_name_is_hidden_inside_words_too():
    ident = Identity(user="user", people=(("sam", "Sam"), ("rosemary", "Rosemary")))
    out = Redactor(ident).apply("Users and user")
    assert out == "Users and <user>"
    assert Redactor(ident).apply("rosemarys-notes and Same") == "<person-2>s-notes and Same"


def test_markers_are_never_damaged_by_a_name_that_appears_inside_them():
    nasty = Identity(user="user", home="/home/user", hostname="windows", windows_users=("Drive", "Person"), people=(("p", "person"),))
    out = Redactor(nasty).apply("user /home/user/x /mnt/c/Users/Drive/y /media/user/DRV/z windows person")
    assert out == "<user> ~/x /mnt/c/Users/<windows-user>/y /media/<user>/<drive>/z <computer> <person-1>", out
    assert "<<" not in out and ">>" not in out


def test_names_with_characters_that_mean_something_in_a_pattern_are_matched_literally():
    ident = Identity(people=(("x", "A+B (x) [y] .*"),))
    assert Redactor(ident).apply("hello A+B (x) [y] .* there and AAB") == "hello <person-1> there and AAB"


def test_a_forged_marker_in_the_text_cannot_become_a_name():
    out = Redactor(ID).apply("\ue0000\ue001 and \ue001 zephyr9")
    assert "\ue000" not in out and "\ue001" not in out and leaks(out) == []


def test_nothing_to_hide_changes_nothing_and_counts_zero():
    r = Redactor(Identity())
    assert r.apply("Training stopped at epoch 12 with loss 0.31") == "Training stopped at epoch 12 with loss 0.31" and r.count == 0


def test_the_count_says_how_many_things_were_hidden():
    r = Redactor(ID)
    r.apply("zephyr9 and zephyr9 and fortress-lab")
    assert r.count == 3


def test_version_numbers_and_driver_numbers_are_not_mistaken_for_addresses():
    r = Redactor(ID)
    for text in ("Python 3.12.3", "driver 560.35.03", "version 1.2.3.4.5", "999.1.1.1", "build 12.0.1"):
        assert r.apply(text) == text, text


# ---------------------------------------------------------------- what the report holds

def test_the_report_has_no_place_for_a_recording_a_transcript_or_a_phrase():
    assert {f.name for f in fields(ReportInput)} == {"now", "identity", "step", "error", "preflight", "job", "log_lines", "app_version", "python_version"}


def test_a_report_for_a_failed_download_is_complete_and_has_no_canary_anywhere():
    system = wsl2(hostname="fortress-lab", environ={"USER": "zephyr9", "DISPLAY": ":0"}, home="/home/zephyr9",
                  disks={"/home/zephyr9": (500 * 2**30, 300 * 2**30), "/mnt/c": (1000 * 2**30, 400 * 2**30), "/media/zephyr9/BACKUP-DRIVE-X": (10 * 2**30, 5 * 2**30)})
    pre = preflight.run_preflight(system, measure=["/media/zephyr9/BACKUP-DRIVE-X"])
    inp = make_input(error=("fetch", "checksum", DIRTY), preflight=pre, job=job_info(error=DIRTY), log_lines=(DIRTY,))
    for include in (False, True):
        out = rp.build_report(inp, CAT, include_log=include)
        assert leaks(out.text) == [], out.text
        for must in ("ACK Voice Studio problem report", "Nothing in it was sent anywhere", "What happened", "Versions", "This computer", "Checks", "Free space", "The job",
                     "The file that arrived did not match", "The bad file was deleted", "Python: 3.12.3", "NVIDIA GeForce RTX 4060, 8188 MiB, 560.35.03", "Time (UTC): 2026-10-10 12:30:05",
                     "Not included: recordings"):
            assert must in out.text, must
        assert out.hidden > 0 and ("Things that were hidden: %d" % out.hidden) in out.text


def test_every_route_a_computer_supplied_string_can_enter_by_is_redacted():
    from voice_studio.core.preflight import Check, Status
    from voice_studio.core.system import CommandResult
    system = FakeSystem(os_release='PRETTY_NAME="Ubuntu for zephyr9 at fortress-lab"\nID=ubuntu\nVERSION_ID="24.04"\n',
                        smi=CommandResult(0, "NVIDIA card of marigold-q, 8188, driver-192.168.1.77\n"))
    pre = preflight.run_preflight(system)
    pre = replace(pre, checks=pre.checks + (Check("odd", Status.INFO, "preflight.odd", {"value": DIRTY, "other": "kowalczyk"}),))
    out = rp.build_report(make_input(preflight=pre, step=DIRTY, error=("job", "gpu_busy", DIRTY), job=job_info(error=DIRTY, spec=JobSpec("train", "marigold-q", ("x",)))), CAT).text
    assert leaks(out) == [], out
    assert "Operating system: Ubuntu for <user> at <computer>" in out and "<person-1>" in out


def test_every_check_is_listed_with_its_status_and_key():
    pre = preflight.run_preflight(FakeSystem(smi=None))
    out = rp.build_report(make_input(preflight=pre), CAT).text
    for check in pre.checks:
        assert check.key in out and check.id in out and check.status.value in out
    assert "none found" in out


def test_the_log_is_left_out_unless_it_is_asked_for():
    inp = make_input(job=job_info(), log_lines=("epoch 3 loss 0.2", "saw zephyr9 at /home/zephyr9/x"))
    off = rp.build_report(inp, CAT, include_log=False)
    assert "epoch 3 loss" not in off.text and "The job's log was left out" in off.text and not off.included_log
    on = rp.build_report(inp, CAT, include_log=True)
    assert "| epoch 3 loss 0.2" in on.text and "| saw <user> at ~/x" in on.text and "may contain words from recordings" in on.text and on.included_log


def test_asking_for_the_log_when_there_is_none_changes_nothing():
    assert not rp.build_report(make_input(job=job_info()), CAT, include_log=True).included_log
    assert "The end of the job's log" not in rp.build_report(make_input(job=job_info()), CAT, include_log=True).text
    assert "The end of the job's log" not in rp.build_report(make_input(log_lines=("x",)), CAT, include_log=True).text      # no job: no log section


def test_the_log_is_cut_to_the_last_lines_and_each_line_is_cut_short():
    lines = tuple("line %d" % i for i in range(200))
    out = rp.build_report(make_input(job=job_info(), log_lines=lines), CAT, include_log=True).text
    assert "| line 199" in out and "| line 140" in out and "| line 139" not in out and out.count("\n  | ") == rp.MAX_LOG_LINES
    long = rp.build_report(make_input(job=job_info(), log_lines=("x" * 1000,)), CAT, include_log=True).text
    assert "| " + "x" * rp.MAX_LINE_CHARS + "\n" in long and "x" * (rp.MAX_LINE_CHARS + 1) not in long


def test_a_report_with_no_error_says_so_and_a_job_shows_how_it_ended():
    assert "No error was recorded." in rp.build_report(make_input(step=""), CAT).text
    out = rp.build_report(make_input(job=job_info(status=JobStatus.STOPPED, exit_code=None, signal=15)), CAT).text
    assert "How it ended: stopped" in out and "Ended by signal: 15" in out and "Exit status" not in out
    assert "Exit status: 3" in rp.build_report(make_input(job=job_info(exit_code=3)), CAT).text


def test_hardware_names_are_kept_because_they_identify_a_machine_model_not_a_person():
    out = rp.build_report(make_input(preflight=preflight.run_preflight(FakeSystem())), CAT).text
    assert "NVIDIA GeForce RTX 4060" in out and "Ubuntu 24.04.1 LTS" in out


def test_the_report_is_never_bigger_than_its_limit_and_is_cut_on_a_character_boundary():
    out = rp.build_report(make_input(job=job_info(), log_lines=("\u00E9" * 290,) * 200), CAT, include_log=True)
    assert len(out.to_bytes()) <= rp.MAX_REPORT_BYTES
    out.to_bytes().decode("utf-8")
    huge = rp.build_report(make_input(step="\u00E9" * 200_000), CAT)
    assert len(huge.to_bytes()) <= rp.MAX_REPORT_BYTES and huge.text.endswith("\n")


def test_the_time_is_shown_in_utc_whatever_zone_it_came_in():
    from datetime import timedelta
    zoned = datetime(2026, 10, 10, 14, 30, 5, tzinfo=timezone(timedelta(hours=2)))
    assert "Time (UTC): 2026-10-10 12:30:05" in rp.build_report(make_input(now=zoned), CAT).text


def test_the_real_computer_can_be_reported_on():
    system = RealSystem()
    ident = rp.gather_identity(system)
    out = rp.build_report(make_input(identity=ident, preflight=preflight.run_preflight(system), python_version=system.python_version()), CAT)
    assert "ACK Voice Studio problem report" in out.text and "Versions" in out.text


# ---------------------------------------------------------------- who is hidden

def test_the_identity_is_read_from_the_computer_including_every_windows_profile():
    system = FakeSystem(environ={"USER": "zephyr9"}, home="/home/zephyr9", hostname="fortress-lab",
                        listings={"/mnt/c/Users": ["Kowalczyk", "Public", "Default", "All Users", "desktop.ini", "Nowak"]})
    ident = rp.gather_identity(system, [("anna", "Anna")])
    assert (ident.user, ident.home, ident.hostname, ident.data_home) == ("zephyr9", "/home/zephyr9", "fortress-lab", "/home/zephyr9/ack-voice-studio")
    assert ident.windows_users == ("Kowalczyk", "Nowak") and ident.people == (("anna", "Anna"),)


def test_without_a_user_variable_the_home_folders_name_is_used_and_logname_is_tried_first():
    assert rp.gather_identity(FakeSystem(environ={}, home="/home/zephyr9")).user == "zephyr9"
    assert rp.gather_identity(FakeSystem(environ={"LOGNAME": "lname"}, home="/home/zephyr9")).user == "lname"
    assert rp.gather_identity(FakeSystem(environ={}, home="/home/zephyr9", listings={})).windows_users == ()


# ---------------------------------------------------------------- saving exactly what was shown

def test_the_file_holds_exactly_the_text_that_was_shown_and_only_its_owner_can_read_it(tmp_path):
    out = rp.build_report(make_input(error=("fetch", "http", "caf\u00E9 \u4E2D\u6587")), CAT)
    path = str(tmp_path / "report.txt")
    rp.write_report(path, out)
    assert Path(path).read_bytes() == out.text.encode("utf-8") and stat.S_IMODE(os.stat(path).st_mode) == 0o600


def test_an_existing_file_is_never_replaced_unless_the_person_said_so(tmp_path):
    path = tmp_path / "report.txt"
    path.write_text("my notes")
    out = rp.build_report(make_input(), CAT)
    with pytest.raises(FileExistsError):
        rp.write_report(str(path), out)
    assert path.read_text() == "my notes"
    rp.write_report(str(path), out, overwrite=True)
    assert path.read_bytes() == out.to_bytes() and stat.S_IMODE(os.stat(path).st_mode) == 0o600
    assert sorted(os.listdir(tmp_path)) == ["report.txt"]


def test_a_failed_overwrite_keeps_the_old_file_and_leaves_no_temporary_one(tmp_path, monkeypatch):
    path = tmp_path / "report.txt"
    path.write_text("old")

    def boom(*_):
        raise OSError("disk full")
    monkeypatch.setattr(rp.os, "replace", boom)
    with pytest.raises(OSError):
        rp.write_report(str(path), rp.build_report(make_input(), CAT), overwrite=True)
    monkeypatch.undo()
    assert path.read_text() == "old" and os.listdir(tmp_path) == ["report.txt"]


def test_a_folder_that_does_not_exist_is_an_error_and_makes_nothing(tmp_path):
    with pytest.raises(FileNotFoundError):
        rp.write_report(str(tmp_path / "nope" / "report.txt"), rp.build_report(make_input(), CAT))
    assert os.listdir(tmp_path) == []
