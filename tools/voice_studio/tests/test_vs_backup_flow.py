# SPDX-License-Identifier: GPL-3.0-or-later
"""The terminal front for backing up a project (plan task VS-6.1): what it shows before it asks, that a no (or nobody to ask) writes nothing, what it says when something fails, the
folder it chooses, listing, verifying and putting a backup back, and the reminder other commands print. The backups are real files in a real folder."""
import os
import shutil
import tarfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from vs_backup_helpers import CODE, TAKE, BackupRig, forge
from vs_listen_helpers import ListenSystem
from vs_rounds_helpers import end_job, stamp
from vs_startvoice_helpers import Terminal, implies_permission, leaked_keys
from voice_studio.core import backup_flow as bf, projectbackup as pb, rounds as rd, text
from voice_studio.core.paths import DataHome

CAT = text.load_catalog("en")
NOW = datetime(2026, 10, 16, 9, 30, 0, tzinfo=timezone.utc)
TAKE1 = TAKE % (1, 1)
ARCHIVE = "ack-project-backup-voice-check-20261016-093000.tar"


@pytest.fixture
def rig(tmp_path):
    return BackupRig(tmp_path)


def run(rig, *argv, answers=(), interactive=True, system=None, now=NOW):
    io = Terminal(answers, interactive)
    code = bf.run_backup(list(argv), rig.home, CAT, io, now=now, system=system or rig.system)
    assert leaked_keys(io.text + "\n".join(io.prompts)) == [], "a catalog key was printed instead of words"
    assert implies_permission(io.text) == [], "something printed says or implies that use is permitted"
    return code, io


def now_args(rig, *more):
    return ("now", "--to", rig.dest) + more


class WslSystem(ListenSystem):
    """A computer under WSL with the Windows user folders `people`."""

    def __init__(self, *a, people=("Public", "anna"), **kw):
        super().__init__(*a, wsl=True, **kw)
        self.people = people

    def listdir(self, path):
        return list(self.people) if path == "/mnt/c/Users" else super().listdir(path)

    def is_dir(self, path):
        return path.startswith("/mnt/c/Users/") or super().is_dir(path)


# ---------------------------------------------------------------- help

def test_no_command_and_help_list_the_four_commands_and_the_options(rig):
    for argv in ((), ("help",), ("--help",), ("-h",)):
        code, io = run(rig, *argv)
        assert code == 0
        for part in ("now [--to folder] [--project name] [--yes] [--without-saved-points]:", "list [--to folder] [--project name]:", "verify file:", "restore file [--yes]:", "--to names the folder"):
            assert part in io.text, part


def test_an_unknown_command_is_named_and_nothing_is_done(rig):
    code, io = run(rig, "frobnicate")
    assert code == 2 and "frobnicate" in io.text and rig.tree(rig.dest if os.path.isdir(rig.dest) else rig.paths.root)


def test_the_options_each_command_publishes_are_the_options_it_accepts():
    assert set(bf.OPTIONS) == {"now", "list", "verify", "restore"}
    assert bf.OPTIONS["now"] == {"--yes", "-y", "--project", "--to", "--without-saved-points"} and bf.OPTIONS["list"] == {"--project", "--to"} and bf.OPTIONS["verify"] == frozenset()
    assert bf.OPTIONS["restore"] == {"--yes", "-y"}


# ---------------------------------------------------------------- now: the plan, the question and the work

def test_it_shows_the_whole_plan_before_it_asks_and_asks_once(rig):
    code, io = run(rig, *now_args(rig), answers=["yes"])
    first_ask = next(i for i, (kind, _t) in enumerate(io.events) if kind == "ask")
    before = "\n".join(t for kind, t in io.events[:first_ask] if kind == "say")
    assert code == 0 and io.prompts == ["Make this backup now? Type yes to go on. "]
    for part in ("A backup of Voice check would be made like this:", "Voice check has not been backed up on this computer yet.", "keep these, one file at a time:",
                 "The project record and the consent note: 1 file,", "Recordings and what was done to them: 10 files,", "The recording packages from the phone: 1 file,",
                 "The record of training rounds and each round's settings: 4 files,", "The saved points that are kept: 2 files,", "Finished voice files: 1 file,",
                 "leave these out, because they can be made again or are not needed:", "Training sets and working files:", "Test sounds and the voices made to hear them:", "Older saved points:",
                 "write it into %s as a new file, and change nothing that is already there" % rig.dest, "read it all the way back and check every file before it counts",
                 "never remove or replace an earlier backup", "Checked before starting:", "write at most about"):
        assert part in before, part


def test_a_yes_makes_the_backup_and_says_where_how_big_and_how_to_check_and_put_it_back(rig):
    code, io = run(rig, *now_args(rig), answers=["yes"])
    path = os.path.join(rig.dest, ARCHIVE)
    assert code == 0 and os.path.isfile(path) and pb.verify(path)[0] == []
    for part in ("The backup is made and checked: " + path, "It holds 19 files. Every file was read back and matched.", "Earlier backups in that folder were not touched. This tool never removes a backup.",
                 "To check it again later, run: python3 -m voice_studio.backup verify " + path, "To put it back, run: python3 -m voice_studio.backup restore " + path):
        assert part in io.text, part
    assert io.lines.index("Reading the backup back and checking every file.") > io.lines.index("Writing Finished voice files.")


def test_each_kind_of_file_is_announced_once_as_it_is_written(rig):
    _code, io = run(rig, *now_args(rig), answers=["yes"])
    writing = [l for l in io.lines if l.startswith("Writing ")]
    assert writing == ["Writing The project record and the consent note.", "Writing Recordings and what was done to them.", "Writing The recording packages from the phone.",
                       "Writing The record of training rounds and each round's settings.", "Writing The saved points that are kept.", "Writing Finished voice files."]


def test_a_no_writes_nothing_and_notes_nothing(rig):
    code, io = run(rig, *now_args(rig), answers=["no"])
    assert code == 2 and "Nothing was done." in io.text and not os.path.exists(rig.dest) and pb.read_state(rig.home) == {}


def test_nobody_to_ask_writes_nothing(rig):
    code, io = run(rig, *now_args(rig), interactive=False)
    assert code == 2 and not os.path.exists(rig.dest) and io.prompts == []


def test_dash_dash_yes_skips_only_the_question(rig):
    code, io = run(rig, *now_args(rig, "--yes"))
    assert code == 0 and io.prompts == [] and os.path.isfile(os.path.join(rig.dest, ARCHIVE))


def test_the_project_is_not_changed_by_a_backup(rig):
    before = rig.tree()
    run(rig, *now_args(rig, "--yes"))
    assert rig.tree() == before


def test_without_saved_points_says_so_and_leaves_them_out(rig):
    code, io = run(rig, *now_args(rig, "--without-saved-points", "--yes"))
    assert "The saved points, because you asked:" in io.text and "The saved points that are kept:" not in io.text
    with tarfile.open(os.path.join(rig.dest, ARCHIVE)) as tar:
        assert not [n for n in tar.getnames() if n.endswith(".ckpt")]


def test_a_second_backup_is_a_new_file_beside_the_first(rig):
    run(rig, *now_args(rig, "--yes"))
    first = Path(rig.dest, ARCHIVE).read_bytes()
    run(rig, *now_args(rig, "--yes"))
    assert Path(rig.dest, ARCHIVE).read_bytes() == first and {n for n in os.listdir(rig.dest) if n.endswith(".tar")} == {ARCHIVE, ARCHIVE.replace(".tar", "-2.tar")}


# ---- where it goes

def test_with_no_folder_named_the_tools_own_backups_folder_is_used_and_said(rig):
    code, io = run(rig, "now", "--yes")
    assert code == 0 and "No folder was named, so this tool's own backups folder is used. Name another with --to." in io.text
    assert os.path.isfile(os.path.join(rig.home.backups, ARCHIVE))


def test_a_folder_named_with_a_tilde_is_the_persons_home(rig, monkeypatch):
    monkeypatch.setenv("HOME", str(rig.tmp))
    code, io = run(rig, "now", "--to", "~/mine", "--yes")
    assert code == 0 and os.path.isfile(str(rig.tmp / "mine" / ARCHIVE))


def test_the_folder_used_last_is_used_again_without_a_word_about_defaults(rig):
    run(rig, *now_args(rig, "--yes"))
    code, io = run(rig, "now", "--yes")
    assert code == 0 and "No folder was named" not in io.text and {n for n in os.listdir(rig.dest) if n.endswith(".tar")} == {ARCHIVE, ARCHIVE.replace(".tar", "-2.tar")}


def test_a_relative_folder_is_refused_in_three_parts_and_nothing_is_asked(rig):
    code, io = run(rig, "now", "--to", "backups", "--yes")
    assert code == 1 and "The backup folder was not given in full." in io.text and "Nothing was made." in io.text and "Give the whole path after --to, starting with a slash." in io.text and io.prompts == []


def test_a_folder_inside_the_project_is_refused_and_why(rig):
    code, io = run(rig, "now", "--to", rig.paths.exports, "--yes")
    assert code == 1 and "That folder is inside a project, so deleting the project would delete its backup too." in io.text and not os.path.exists(rig.paths.exports + "/ack-project-backup")


def test_a_file_where_the_folder_should_be_is_refused(rig, tmp_path):
    afile = tmp_path / "afile"
    afile.write_text("x")
    code, io = run(rig, "now", "--to", str(afile), "--yes")
    assert code == 1 and "That place is a file or a link, not a folder." in io.text and afile.read_text() == "x"


def test_a_folder_on_the_same_drive_says_what_that_does_and_does_not_protect(rig):
    _code, io = run(rig, *now_args(rig), answers=["no"])
    assert "That folder is on the same drive as the project. It protects against a mistake, not against a drive that fails." in io.text


def test_a_folder_that_looks_cloud_synced_is_flagged_in_freeform_studios_words(rig, tmp_path):
    _code, io = run(rig, "now", "--to", str(tmp_path / "OneDrive" / "Backups"), answers=["no"])
    assert "The backup folder %s may be uploaded to a cloud service" % (tmp_path / "OneDrive" / "Backups") in io.text and "OneDrive" in io.text


def test_under_wsl_a_windows_side_folder_is_suggested_when_the_user_can_be_told(rig):
    system = WslSystem(rig.studio.python)
    _code, io = run(rig, "now", answers=["no"], system=system)
    assert "A folder on the Windows side, outside Documents and OneDrive, also works. For example: /mnt/c/Users/anna/ACK Voice Studio backups" in io.text


@pytest.mark.parametrize("case", ["named", "two_people", "not_wsl"])
def test_the_windows_suggestion_is_not_made_when_it_would_be_a_guess_or_is_not_needed(rig, case):
    system = WslSystem(rig.studio.python, people=("Public", "anna", "ben")) if case == "two_people" else (rig.system if case == "not_wsl" else WslSystem(rig.studio.python))
    argv = now_args(rig) if case == "named" else ("now",)
    _code, io = run(rig, *argv, answers=["no"], system=system)
    assert "Windows side" not in io.text


# ---- the standing of the project, in the plan

def test_the_plan_says_when_the_last_backup_was_and_whether_the_project_changed(rig):
    run(rig, *now_args(rig, "--yes"))
    _code, io = run(rig, *now_args(rig), answers=["no"])
    assert "Nothing precious in Voice check has changed since the last backup, made on 2026-10-16 09:30:00 UTC." in io.text
    rig.take(7)
    _code, io = run(rig, *now_args(rig), answers=["no"])
    assert "Voice check has changed since the last backup, made on 2026-10-16 09:30:00 UTC in %s." % rig.dest in io.text


# ---- room

def test_not_enough_room_says_so_in_three_parts_and_asks_nothing(rig):
    rig.system.free = (10 ** 12, 1000)
    code, io = run(rig, *now_args(rig), answers=["yes"])
    assert code == 1 and "There is not enough free space for this backup." in io.text and "Free up space, or choose a folder on a drive with more room." in io.text
    assert io.prompts == [] and not os.path.exists(rig.dest)


def test_the_room_check_is_on_the_drive_the_backup_goes_to(rig, tmp_path):
    os.makedirs(rig.dest)
    system = rig.system
    system.free = {rig.dest: (10 ** 12, 1000), rig.paths.root: (10 ** 12, 10 ** 12)}
    code, io = run(rig, *now_args(rig), answers=["yes"])
    assert code == 1 and "not enough free space" in io.text
    system.free = {rig.dest: (10 ** 12, 10 ** 12), rig.paths.root: (10 ** 12, 1000)}
    code, io = run(rig, *now_args(rig), answers=["yes"])
    assert code == 0


def test_a_drive_that_cannot_be_read_says_so_and_goes_on(rig):
    rig.system.free = None
    class Unreadable(ListenSystem):
        def disk_free(self, path):
            return None
    system = Unreadable(rig.studio.python)
    code, io = run(rig, *now_args(rig), answers=["yes"], system=system)
    assert code == 0 and "The free space of the disk could not be read, so it was not checked." in io.text and os.path.isfile(os.path.join(rig.dest, ARCHIVE))


def test_a_tight_fit_is_said_and_goes_on_after_the_question(rig):
    plan = pb.plan_backup(rig.paths, rig.home, "voice-check", rig.dest, 10 ** 12)
    from voice_studio.core.diskbudget import DEFAULT_TABLE, floors_for
    floors = floors_for(DEFAULT_TABLE, holds_recordings=True)
    rig.system.free = (10 ** 13, plan.need_bytes + floors.stop + 1)
    code, io = run(rig, *now_args(rig), answers=["yes"])
    assert code == 0 and "Free space is getting tight: about" in io.text and "It can go on." in io.text and os.path.isfile(os.path.join(rig.dest, ARCHIVE))


# ---- things that go wrong

def test_a_project_with_nothing_to_back_up_says_so(tmp_path, monkeypatch):
    rig = BackupRig(tmp_path, rounds=0, voice=False, takes=0, package=False, junk=False)
    monkeypatch.setattr(pb, "collect", lambda paths, record=None, saved_points=True: ((), ()))
    code, io = run(rig, *now_args(rig), answers=["yes"])
    assert code == 1 and "There is nothing in this project to back up yet." in io.text and io.prompts == []


def test_a_project_with_only_its_record_is_backed_up_and_no_record_of_rounds_or_lock_is_made_for_it(tmp_path):
    rig = BackupRig(tmp_path, rounds=0, voice=False, takes=0, package=False, junk=False)
    before = rig.tree()
    code, io = run(rig, *now_args(rig, "--yes"))
    assert code == 0 and rig.tree() == before and not os.path.exists(rig.paths.rounds_file) and not os.path.exists(rig.paths.rounds_lock), "a backup must write nothing in the project"
    assert "The project record and the consent note: 1 file," in io.text and "It holds 1 file." in io.text


def test_another_backup_running_in_the_folder_is_named_in_three_parts(rig):
    os.makedirs(rig.dest)
    Path(rig.dest, pb.LOCK).write_text("12345")
    code, io = run(rig, *now_args(rig, "--yes"))
    assert code == 1 and "Another backup is running in that folder." in io.text and "remove the lock file named in the details" in io.text and pb.LOCK in io.text


def test_a_file_that_changes_while_it_is_read_is_named_and_nothing_is_kept(rig, monkeypatch):
    real = tarfile.TarFile.addfile

    def addfile(self, tarinfo, fileobj=None):
        result = real(self, tarinfo, fileobj)
        if tarinfo.name.endswith(TAKE1 + "/raw.webm"):
            (rig.recordings_root / "takes" / TAKE1 / "raw.webm").write_bytes(b"CHANGED" * 40)
        return result
    monkeypatch.setattr(tarfile.TarFile, "addfile", addfile)
    code, io = run(rig, *now_args(rig, "--yes"))
    assert code == 1 and "A file changed while it was being backed up." in io.text and "nothing in the project was changed" in io.text
    assert sorted(os.listdir(rig.dest)) == [] and pb.read_state(rig.home) == {}


def test_a_backup_that_does_not_read_back_says_so_and_notes_nothing(rig, monkeypatch):
    monkeypatch.setattr(pb, "verify", lambda path, check_names=True: (["raw.webm: does not match its checksum"], None))
    code, io = run(rig, *now_args(rig, "--yes"))
    assert code == 1 and "The backup did not read back correctly." in io.text and "    - raw.webm: does not match its checksum" in io.text
    assert os.listdir(rig.dest) == [] and pb.read_state(rig.home) == {}


def test_a_stop_in_the_middle_says_what_happened_to_the_files(rig, monkeypatch):
    def stop(*a, **k):
        raise KeyboardInterrupt()
    monkeypatch.setattr(pb, "create", stop)
    code, io = run(rig, *now_args(rig, "--yes"))
    assert code == 1 and "Stopped. An unfinished backup was removed, and earlier backups were left as they are." in io.text


def test_a_stop_at_the_question_does_nothing(rig):
    code, io = run(rig, *now_args(rig), answers=[KeyboardInterrupt()])
    assert code == 1 and "Nothing was done." in io.text and not os.path.exists(rig.dest)


def test_files_left_out_because_they_are_not_whole_files_are_named_in_the_plan_and_after(rig, tmp_path):
    (rig.recordings_root / "incoming" / "evil.zip").symlink_to(tmp_path / "secret")
    code, io = run(rig, *now_args(rig, "--yes"))
    assert code == 0 and "1 file was left out because it is not a whole, ordinary file." in io.text and io.text.count("1 file was left out") == 2


def test_a_round_that_ended_since_the_record_was_written_is_brought_up_to_date_first_and_its_saved_point_is_kept(rig):
    plan = rig.world.begin()
    info = rig.world.job_for(plan, "running")
    rd.attach_job(rig.paths, plan.number, info.id)
    rig.world.trainer_makes(2)
    end_job(info.dir, "finished", ended_at=stamp(26))
    assert rd.active(rd.load(rig.paths)) is not None
    code, io = run(rig, *now_args(rig, "--yes"))
    assert code == 0 and rd.active(rd.load(rig.paths)) is None and "Noticed: round 3 is now: Finished." in io.text
    with tarfile.open(os.path.join(rig.dest, ARCHIVE)) as tar:
        assert "rounds/run/lightning_logs/version_2/checkpoints/last.ckpt" in tar.getnames()


def test_no_project_or_an_unknown_one_is_said_the_usual_way(rig):
    code, io = run(rig, *now_args(rig, "--project", "nobody", "--yes"))
    assert code == 2 and "nobody" in io.text and not os.path.exists(rig.dest)


def test_a_damaged_record_of_rounds_is_said_and_nothing_is_backed_up(rig):
    Path(rig.paths.rounds_file).write_text("not json")
    code, io = run(rig, *now_args(rig, "--yes"))
    assert code == 1 and not os.path.exists(rig.dest)


# ---------------------------------------------------------------- list

def test_list_says_there_are_none_and_how_to_make_one(rig):
    code, io = run(rig, "list", "--to", rig.dest)
    assert code == 0 and "There are no backups of Voice check in %s." % rig.dest in io.text and "To make one, run: python3 -m voice_studio.backup now --project voice-check" in io.text
    assert "Voice check has not been backed up on this computer yet." in io.text


def test_list_shows_the_backups_newest_first_with_size_and_name(rig):
    run(rig, *now_args(rig, "--yes"), now=NOW)
    run(rig, *now_args(rig, "--yes"), now=NOW + timedelta(days=2))
    code, io = run(rig, "list", "--to", rig.dest)
    rows = [l.strip() for l in io.lines if l.strip().startswith("2026-")]
    assert code == 0 and len(rows) == 2 and rows[0].startswith("2026-10-18 09:30:00 UTC:") and "ack-project-backup-voice-check-20261018-093000.tar" in rows[0] and rows[1].startswith("2026-10-16")
    assert "Backups of Voice check in %s:" % rig.dest in io.text


def test_list_looks_in_the_folder_used_last_when_none_is_named(rig):
    run(rig, *now_args(rig, "--yes"))
    code, io = run(rig, "list")
    assert "Backups of Voice check in %s:" % rig.dest in io.text


def test_list_changes_nothing(rig):
    run(rig, *now_args(rig, "--yes"))
    before = {**rig.tree(rig.dest), **rig.tree()}
    run(rig, "list", "--to", rig.dest)
    assert {**rig.tree(rig.dest), **rig.tree()} == before


# ---------------------------------------------------------------- verify

def test_verify_says_a_good_backup_is_whole(rig):
    run(rig, *now_args(rig, "--yes"))
    code, io = run(rig, "verify", os.path.join(rig.dest, ARCHIVE))
    assert code == 0 and ARCHIVE + " is whole. Every file in it matched, and nothing is missing or extra." in io.text


def test_verify_names_what_is_wrong_with_a_damaged_one(rig):
    run(rig, *now_args(rig, "--yes"))
    path = os.path.join(rig.dest, ARCHIVE)
    raw = bytearray(Path(path).read_bytes())
    raw[raw.index(b"RAWRAWRAW")] ^= 0xFF
    Path(path).write_bytes(bytes(raw))
    code, io = run(rig, "verify", path)
    assert code == 1 and ARCHIVE + " is not whole:" in io.text and "raw.webm: does not match its checksum" in io.text


def test_verify_of_a_file_that_is_not_there_says_so(rig, tmp_path):
    code, io = run(rig, "verify", str(tmp_path / "nothing.tar"))
    assert code == 1 and "That backup file was not found." in io.text


def test_verify_with_no_file_says_how_and_does_nothing(rig):
    code, io = run(rig, "verify")
    assert code == 2 and "verify file:" in io.text


def test_verify_changes_nothing(rig):
    run(rig, *now_args(rig, "--yes"))
    before = rig.tree(rig.dest)
    run(rig, "verify", os.path.join(rig.dest, ARCHIVE))
    assert rig.tree(rig.dest) == before


# ---------------------------------------------------------------- restore

def delete_project(rig):
    shutil.rmtree(rig.paths.root)


def test_restore_shows_what_it_will_do_asks_and_makes_the_project_again(rig):
    run(rig, *now_args(rig, "--yes"))
    held = {i.source: Path(i.source).read_bytes() for i in pb.collect(rig.paths)[0]}
    delete_project(rig)
    code, io = run(rig, "restore", os.path.join(rig.dest, ARCHIVE), answers=["yes"])
    first_ask = next(i for i, (kind, _t) in enumerate(io.events) if kind == "ask")
    before = "\n".join(t for kind, t in io.events[:first_ask] if kind == "say")
    assert code == 0 and "Putting back the backup made on 2026-10-16 09:30:00 UTC would do this:" in before
    assert "make the project voice-check again, because it is not on this computer" in before and "add 19 files that are missing (" in before
    assert io.prompts == ["Put these back now? Type yes to go on. "] and "Done. 19 files were added (" in io.text
    assert "Look at the project with: python3 -m voice_studio.rounds list --project voice-check" in io.text
    assert {source: Path(source).read_bytes() for source in held} == held


def test_restore_into_a_project_that_is_there_adds_only_what_is_missing_and_lists_what_it_left(rig):
    run(rig, *now_args(rig, "--yes"))
    (rig.recordings_root / "takes" / TAKE1 / "raw.webm").unlink()
    (rig.recordings_root / "takes" / TAKE1 / "edit.json").write_text('{"mine": true}')
    code, io = run(rig, "restore", os.path.join(rig.dest, ARCHIVE), answers=["yes"])
    assert code == 0 and "add to the project voice-check, which is on this computer, and change nothing in it that is already there" in io.text
    assert "add 1 file that is missing (" in io.text and "skip 17 files that are already there and the same" in io.text
    assert "leave 1 file exactly as it is, because it differs from the backup's copy. The backup still holds its copy." in io.text and "recordings/takes/%s/edit.json" % TAKE1 in io.text
    assert "Done. 1 file was added" in io.text and (rig.recordings_root / "takes" / TAKE1 / "edit.json").read_text() == '{"mine": true}'


def test_restore_with_nothing_missing_says_so_and_asks_nothing(rig):
    run(rig, *now_args(rig, "--yes"))
    code, io = run(rig, "restore", os.path.join(rig.dest, ARCHIVE))
    assert code == 0 and "Nothing needs putting back. Everything in the backup is already in the project." in io.text and io.prompts == []


def test_restore_declined_or_with_nobody_to_ask_writes_nothing(rig):
    run(rig, *now_args(rig, "--yes"))
    delete_project(rig)
    code, io = run(rig, "restore", os.path.join(rig.dest, ARCHIVE), answers=["no"])
    assert code == 2 and not os.path.exists(rig.paths.root)
    code, io = run(rig, "restore", os.path.join(rig.dest, ARCHIVE), interactive=False)
    assert code == 2 and not os.path.exists(rig.paths.root)


def test_restore_with_dash_dash_yes_does_not_ask(rig):
    run(rig, *now_args(rig, "--yes"))
    delete_project(rig)
    code, io = run(rig, "restore", os.path.join(rig.dest, ARCHIVE), "--yes")
    assert code == 0 and io.prompts == [] and os.path.isfile(rig.paths.project_json)


def test_restore_of_a_damaged_backup_names_the_problem_and_writes_nothing(rig):
    run(rig, *now_args(rig, "--yes"))
    path = os.path.join(rig.dest, ARCHIVE)
    raw = bytearray(Path(path).read_bytes())
    raw[raw.index(b"RAWRAWRAW")] ^= 0xFF
    Path(path).write_bytes(bytes(raw))
    delete_project(rig)
    code, io = run(rig, "restore", path, "--yes")
    assert code == 1 and "That backup is not whole, so it was not used." in io.text and "raw.webm: does not match its checksum" in io.text and not os.path.exists(rig.paths.root)


def test_restore_of_a_forged_backup_with_a_name_that_leaves_the_project_writes_nothing(rig, tmp_path):
    path = forge(tmp_path / "forged.tar", [("project/project.json", b"{}"), ("../../../escaped.txt", b"evil")], project="newcomer")
    code, io = run(rig, "restore", path, "--yes")
    assert code == 1 and not os.path.exists(rig.home.projects + "/newcomer") and not (tmp_path / "escaped.txt").exists()


def test_restore_with_no_file_or_a_file_that_is_not_there_says_so(rig, tmp_path):
    code, io = run(rig, "restore")
    assert code == 2 and "restore file [--yes]:" in io.text
    code, io = run(rig, "restore", str(tmp_path / "nothing.tar"))
    assert code == 1 and "That backup file was not found." in io.text


def test_restore_without_the_room_says_so_and_writes_nothing(rig):
    run(rig, *now_args(rig, "--yes"))
    delete_project(rig)
    rig.system.free = (10 ** 12, 1000)
    code, io = run(rig, "restore", os.path.join(rig.dest, ARCHIVE), "--yes")
    assert code == 1 and "There is not enough free space for this backup." in io.text and not os.path.exists(rig.paths.root)


def test_restore_into_a_project_with_a_task_running_is_refused(rig):
    from vs_rounds_helpers import fake_job
    run(rig, *now_args(rig, "--yes"))
    fake_job(rig.home.jobs, ["x"], "running", project="voice-check")
    code, io = run(rig, "restore", os.path.join(rig.dest, ARCHIVE), "--yes")
    assert code == 1 and "A task for that project is running." in io.text


def test_restore_that_could_not_add_some_files_lists_them_and_fails(rig, monkeypatch):
    run(rig, *now_args(rig, "--yes"))
    delete_project(rig)
    real = pb._write_one

    def write(tar, member, item):
        if item.part == "exports":
            raise OSError(5, "Input/output error")
        return real(tar, member, item)
    monkeypatch.setattr(pb, "_write_one", write)
    code, io = run(rig, "restore", os.path.join(rig.dest, ARCHIVE), "--yes")
    assert code == 1 and "These could not be added:" in io.text and "Input/output error" in io.text and "Done. 18 files were added" in io.text


def test_restore_that_is_stopped_says_so(rig, monkeypatch):
    run(rig, *now_args(rig, "--yes"))
    delete_project(rig)
    monkeypatch.setattr(pb, "restore", lambda *a, **k: (_ for _ in ()).throw(KeyboardInterrupt()))
    code, io = run(rig, "restore", os.path.join(rig.dest, ARCHIVE), "--yes")
    assert code == 1 and "Stopped." in io.text


# ---------------------------------------------------------------- the reminder

def ctx_of(rig):
    from voice_studio.core.rounds_flow import Open, scratch_root
    from voice_studio.core.project import load_project
    project = load_project(rig.paths)
    return Open(project, rig.paths, scratch_root(project, rig.paths), rig.home.jobs)


def test_a_project_never_backed_up_gets_a_reminder_with_the_command(rig):
    lines = bf.nudge_lines(rig.home, ctx_of(rig), CAT)
    assert lines == ["Voice check has not been backed up yet. A backup keeps the recordings and notes safe if something goes wrong with this computer. To make one, run: python3 -m voice_studio.backup now --project voice-check"]


def test_a_project_that_changed_since_the_last_backup_gets_a_reminder_with_the_date(rig):
    run(rig, *now_args(rig, "--yes"))
    assert bf.nudge_lines(rig.home, ctx_of(rig), CAT) == []
    rig.take(7)
    assert bf.nudge_lines(rig.home, ctx_of(rig), CAT) == ["Voice check has changed since the last backup, made on 2026-10-16 09:30:00 UTC. To back up again, run: python3 -m voice_studio.backup now --project voice-check"]


def test_a_project_with_nothing_to_lose_or_a_damaged_record_gets_no_reminder(rig):
    Path(rig.paths.rounds_file).write_text("not json")
    assert bf.nudge_lines(rig.home, ctx_of(rig), CAT) == []


# ---------------------------------------------------------------- the edges found by breaking the front on purpose

def test_a_remembered_folder_that_is_not_a_full_path_is_not_used(rig):
    made = rig.backup(NOW)
    pb.record_backup(rig.home, made, "voice-check", "relative/folder")
    code, io = run(rig, "list")
    assert "There are no backups of Voice check in %s." % rig.home.backups in io.text


def test_free_space_is_asked_for_only_where_the_folder_is_a_full_path():
    system = type("S", (), {"disk_free": lambda self, path: (100, 42)})()
    assert bf._free_at(system, "relative") is None and bf._free_at(system, "/") == 42


def test_a_project_with_nothing_to_lose_gets_no_line_about_its_last_backup():
    io = Terminal(())
    bf._say_standing(pb.Standing(pb.CURRENT, "", ""), "Voice check", CAT, io)
    assert io.lines == []


def test_nothing_is_said_to_be_left_out_or_skipped_when_it_is_not(tmp_path):
    (tmp_path / "clean").mkdir()
    clean = BackupRig(tmp_path / "clean", rounds=0, junk=False)
    code, io = run(clean, *now_args(clean, "--yes"))
    assert code == 0 and "leave these out" not in io.text and "left out because" not in io.text


def test_only_ten_of_the_names_left_out_are_shown_and_all_are_counted(tmp_path):
    many = BackupRig(tmp_path)
    outside = tmp_path / "outside.bin"
    outside.write_bytes(b"x")
    for number in range(1, 13):
        (many.recordings_root / "incoming" / ("link%d.zip" % number)).symlink_to(outside)
    code, io = run(many, *now_args(many, "--yes"))
    assert code == 0 and io.text.count("(not_a_file)") == 10 and io.text.count("12 files were left out because they are not whole, ordinary files.") == 2


def test_a_folder_on_another_drive_is_not_told_it_is_on_the_projects_drive(rig, monkeypatch):
    monkeypatch.setattr(pb, "same_drive", lambda a, b: False)
    system = WslSystem(rig.studio.python)
    code, io = run(rig, "now", answers=["no"], system=system)
    assert "same drive" not in io.text and "Windows side" not in io.text


def test_listing_does_not_bring_the_record_of_rounds_up_to_date(rig):
    plan = rig.world.begin()
    info = rig.world.job_for(plan, "running")
    rd.attach_job(rig.paths, plan.number, info.id)
    rig.world.trainer_makes(2)
    end_job(info.dir, "finished", ended_at=stamp(26))
    before = Path(rig.paths.rounds_file).read_bytes()
    code, io = run(rig, "list", "--to", rig.dest)
    assert code == 0 and Path(rig.paths.rounds_file).read_bytes() == before and rd.active(rd.load(rig.paths)) is not None


def test_verify_shows_ten_problems_at_most(rig, tmp_path):
    path = forge(tmp_path / "bad.tar", [("odd%d.txt" % n, b"x") for n in range(15)])
    code, io = run(rig, "verify", path)
    assert code == 1 and len([line for line in io.lines if line.startswith("  - ")]) == 10


def test_a_restore_says_nothing_about_what_there_is_none_of(rig):
    run(rig, *now_args(rig, "--yes"))
    path = os.path.join(rig.dest, ARCHIVE)
    delete_project(rig)
    code, io = run(rig, "restore", path, answers=["yes"])
    assert code == 0 and "skip" not in io.text and "differs from the backup" not in io.text and "could not be added" not in io.text and "left as" not in io.text
    code, io = run(rig, "restore", path)
    assert code == 0 and "that is missing" not in io.text and "that are missing" not in io.text and "add 0" not in io.text and "differs" not in io.text and "skip 19 files that are already there and the same" in io.text


def test_a_restore_lists_at_most_ten_of_the_files_it_leaves(rig):
    run(rig, *now_args(rig, "--yes"))
    path = os.path.join(rig.dest, ARCHIVE)
    for item in pb.collect(rig.paths)[0][:12]:
        with open(item.source, "ab") as handle:
            handle.write(b"changed since")
    code, io = run(rig, "restore", path)
    rows = [line for line in io.lines if line.startswith("    ") and "/" in line]
    assert code == 0 and len(rows) == 10 and "leave 12 files exactly as they are" in io.text


def test_a_restore_that_cannot_add_more_than_ten_lists_ten_and_fails(rig, monkeypatch):
    run(rig, *now_args(rig, "--yes"))
    delete_project(rig)
    monkeypatch.setattr(pb, "_write_one", lambda tar, member, item: "the disk said no")
    code, io = run(rig, "restore", os.path.join(rig.dest, ARCHIVE), "--yes")
    assert code == 1 and len([line for line in io.lines if line.endswith(": the disk said no")]) == 10 and "These could not be added:" in io.text


def test_a_file_that_appeared_while_putting_back_is_said_to_be_left_as_it_was(rig, monkeypatch):
    run(rig, *now_args(rig, "--yes"))
    (rig.recordings_root / "takes" / TAKE1 / "raw.webm").unlink()
    real = pb._write_one

    def appears(tar, member, item):
        if item.name.endswith("raw.webm"):
            Path(item.dest).write_bytes(b"made meanwhile")
        return real(tar, member, item)
    monkeypatch.setattr(pb, "_write_one", appears)
    code, io = run(rig, "restore", os.path.join(rig.dest, ARCHIVE), "--yes")
    assert code == 0 and "1 file was left as it was, because it differs from the backup's copy." in io.text


def test_a_restore_without_the_room_is_refused_before_it_asks(rig):
    run(rig, *now_args(rig, "--yes"))
    delete_project(rig)
    rig.system.free = (10 ** 12, 1000)
    code, io = run(rig, "restore", os.path.join(rig.dest, ARCHIVE), answers=["yes"])
    assert code == 1 and io.prompts == [] and not os.path.exists(rig.paths.root)

