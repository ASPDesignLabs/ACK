# SPDX-License-Identifier: GPL-3.0-or-later
"""The terminal front for moving a project's scratch (plan task VS-6.5): what `show` says, what `move` checks, shows and asks, how it copes when a step fails, and the second question about the old
place. The flows are the real code on real folders; the computer's mount table and free room are chosen by the test."""
import os
import shutil
from pathlib import Path

import pytest

from vs_refresh_helpers import CAT, TermIO
from vs_rounds_helpers import fake_job
from vs_scratchmove_helpers import BIG, FILES, ScratchRig, ScratchSystem
from vs_startvoice_helpers import implies_permission, leaked_keys
from voice_studio.core import scratch as sc, scratchmove as sm, scratchmove_flow as smf
from voice_studio.core.project import SCRATCH_CUSTOM, SCRATCH_DEFAULT, Scratch, create_project, with_scratch_place, save_project
from voice_studio.core.text import size_text

TOTAL = sum(len(v) for v in FILES.values())


@pytest.fixture
def rig(tmp_path):
    return ScratchRig(tmp_path)


def run(rig, *argv, answers=(), interactive=True, system=None):
    io = TermIO(answers, interactive)
    code = smf.run_scratch(list(argv), system or rig.system, rig.home, CAT, io)
    assert leaked_keys(io.text + "\n".join(io.prompts)) == [], "a catalog key was printed instead of words"
    assert implies_permission(io.text) == [], "something printed says or implies that use is permitted"
    return code, io


def move_to(rig):
    return ("move", "--to", str(rig.drive))


def target_of(rig):
    return str(rig.drive) + "/ack-voice-scratch/" + rig.project.id


def moved_to_drive(rig):
    """The project already on the other drive, with its files there."""
    code, io = run(rig, *move_to(rig), "--yes", answers=["no"])
    assert code == 0
    return io


# ---------------------------------------------------------------- help and the command line

def test_no_command_and_help_list_the_two_commands_and_what_is_never_touched(rig):
    for argv in ((), ("help",), ("--help",), ("-h",)):
        code, io = run(rig, *argv)
        assert code == 0 and io.prompts == [] and io.lines[0] == "ACK Voice Studio: scratch" and "Commands:" in io.lines
        for part in ("show [--project name]:", "move --to folder | --default [--project name] [--yes]:", "No recording, round or finished voice is touched."):
            assert part in io.text, part


def test_an_unknown_command_is_named_and_nothing_is_done(rig):
    before = rig.tree(rig.paths.root)
    code, io = run(rig, "shift")
    assert code == 2 and "shift" in io.text and rig.tree(rig.paths.root) == before


def test_the_options_each_command_publishes_are_the_options_it_accepts(rig):
    assert smf.OPTIONS == {"show": frozenset({"--project"}), "move": frozenset({"--project", "--to", "--default", "--yes", "-y"})} and smf.COMMANDS == ("show", "move", "help")
    for command in ("show", "move"):
        code, io = run(rig, command, "--nonsense")
        assert code == 2 and "--nonsense" in io.text and io.prompts == [], command
        code, io = run(rig, command, "extra")
        assert code == 2 and io.prompts == [], command
    assert run(rig, "show", "--default")[0] == 2 and run(rig, "show", "--yes")[0] == 2


def test_every_usage_line_has_words():
    for key in smf.USAGE:
        assert CAT.has(key)


def test_a_move_needs_exactly_one_of_a_place_or_the_default(rig):
    for argv in (("move",), ("move", "--yes"), ("move", "--to", str(rig.drive), "--default")):
        before = rig.tree(rig.paths.root)
        code, io = run(rig, *argv)
        assert code == 2 and io.lines[-1] == "Say where to move it with --to and a folder, or with --default to move it back inside the project. Nothing was done." and io.prompts == []
        assert rig.tree(rig.paths.root) == before and os.listdir(rig.drive) == []


def test_a_project_that_cannot_be_told_is_asked_for_by_name(rig):
    rig.second_project()
    code, io = run(rig, "move", "--to", str(rig.drive))
    assert code == 2 and "voice-check" in io.text and "ben" in io.text and os.listdir(rig.drive) == []
    code, io = run(rig, "show", "--project", "nobody")
    assert code == 2 and "nobody" in io.text


# ---------------------------------------------------------------- show

def test_show_says_where_the_default_scratch_is_what_it_holds_and_how_to_move_it(rig):
    before = rig.tree(rig.paths.root)
    code, io = run(rig, "show")
    assert code == 0 and io.prompts == [] and rig.tree(rig.paths.root) == before
    assert io.lines[:4] == ["ACK Voice Studio: scratch", "Using the only project: voice-check.", "The scratch of Voice check is the folder inside the project: " + rig.paths.default_scratch,
                            "  4 files, %s." % size_text(TOTAL)]
    assert "  That drive has %s free." % size_text(BIG[1]) in io.lines and size_text(BIG[0]) != size_text(BIG[1]) and not any("not copied" in l for l in io.lines)
    assert io.lines[-1] == "To move it, run: python3 -m voice_studio.scratch move --project voice-check --to FOLDER"


def test_show_says_an_empty_scratch_is_empty_and_one_file_is_one_file(tmp_path):
    rig = ScratchRig(tmp_path, files={"datasets/a.txt": b"x"})
    shutil.rmtree(rig.paths.default_scratch + "/datasets/empty")
    assert "  1 file, 1 B." in run(rig, "show")[1].lines
    os.unlink(rig.paths.default_scratch + "/datasets/a.txt")
    assert "  It is empty." in run(rig, "show")[1].lines


def test_show_names_what_is_not_copied_in_words_that_agree(rig, tmp_path):
    os.symlink(tmp_path, rig.paths.default_scratch + "/one")
    assert "  1 link or special item is not copied." in run(rig, "show")[1].lines
    os.symlink(tmp_path, rig.paths.default_scratch + "/two")
    assert "  2 links or special items are not copied." in run(rig, "show")[1].lines


def test_show_says_a_chosen_place_and_that_it_cannot_be_used_when_its_drive_is_away(rig):
    moved_to_drive(rig)
    code, io = run(rig, "show")
    assert code == 0 and "The scratch of Voice check is in the place you chose: " + target_of(rig) in io.lines and "  4 files, %s." % size_text(TOTAL) in io.lines
    os.unlink(target_of(rig) + "/" + sc.MARKER_NAME)
    code, io = run(rig, "show")
    assert code == 0 and "Its drive does not seem to be plugged in, so no training will start until it is back." in io.lines and not any(l.startswith("  4 files") for l in io.lines)


def test_show_says_when_a_place_cannot_be_read(rig, monkeypatch):
    def refuse(root):
        raise OSError(13, "Permission denied")
    monkeypatch.setattr(sm, "read_tree", refuse)
    assert "  It could not be read." in run(rig, "show")[1].lines


def test_show_leaves_out_the_free_room_when_the_drive_cannot_be_read(rig):
    rig.system.free = lambda path: None
    assert not any("free." in l for l in run(rig, "show")[1].lines)


# ---------------------------------------------------------------- move: asking first

def test_move_shows_what_it_will_do_and_asks_once_and_a_no_changes_nothing(rig):
    before = rig.tree(rig.paths.root)
    code, io = run(rig, *move_to(rig), answers=["no"])
    assert code == 2 and "Nothing was done." in io.lines and io.prompts == ["Move the scratch now? Type yes to go on. "]
    assert rig.tree(rig.paths.root) == before and os.listdir(rig.drive) == [] and rig.saved().scratch == Scratch()
    ask = io.events.index(("ask", io.prompts[0]))
    said = [t for kind, t in io.events[:ask] if kind == "say"]
    assert "Moving the scratch of Voice check:" in said and "  From: " + rig.paths.default_scratch in said and "  To: " + target_of(rig) in said and "  4 files, %s." % size_text(TOTAL) in said
    assert "  A copy is made first, and every file is read back and checked." in said
    assert "  The project uses the new place only when the whole copy is checked. Until then nothing changes." in said
    assert "  The old place is not touched. You are asked about it at the end." in said


def test_with_nobody_to_ask_nothing_is_done(rig):
    code, io = run(rig, *move_to(rig), interactive=False)
    assert code == 2 and io.prompts == [] and "There was nobody to ask. To say yes on the command line, add --yes. Nothing was done." in io.lines
    assert os.listdir(rig.drive) == [] and rig.saved().scratch == Scratch()


def test_a_place_on_the_same_drive_is_said_to_save_no_room_but_may_still_be_chosen(rig):
    code, io = run(rig, *move_to(rig), answers=["no"])
    assert "  This is the same drive as the project, so it will not save any room." in io.lines


def test_the_warnings_about_a_place_are_shown_before_the_question(rig):
    rig.system.mounts = "/dev/sda1 / ext4 rw 0 0\n/dev/sdb1 %s ntfs rw 0 0\n" % rig.drive
    code, io = run(rig, *move_to(rig), answers=["no"])
    ask = io.events.index(("ask", io.prompts[0]))
    said = [t for kind, t in io.events[:ask] if kind == "say"]
    assert "  This drive uses a Windows-style format. It may be slower." in said and "  Other people who use this computer may be able to read files saved here." in said


def test_a_drive_of_that_kind_on_an_ordinary_computer_is_a_network_drive_and_refused_not_called_a_windows_drive(rig):
    rig.system.mounts = "/dev/sda1 / ext4 rw 0 0\nC:\\134 %s 9p rw 0 0\n" % rig.drive
    code, io = run(rig, *move_to(rig), answers=["no"])
    assert code == 2 and "  That is a network drive. The voice must not travel over a network." in io.lines and "Windows drive" not in io.text


def test_a_computer_under_wsl_says_a_windows_drive_is_slow(rig):
    rig.system.wsl = True
    rig.system.mounts = "/dev/sda1 / ext4 rw 0 0\nC:\\134 %s 9p rw 0 0\n" % rig.drive
    code, io = run(rig, *move_to(rig), answers=["no"])
    assert "  This is a Windows drive seen from WSL. It is much slower than Ubuntu's own disk." in io.lines


# ---------------------------------------------------------------- move: refusals of a place

@pytest.mark.parametrize("place, reason", [("drive", "That folder is inside this project's own folders. Choose somewhere else."), ("short", "Please choose a folder from the list rather than typing a short name."),
                                           ("file", "That is a file, not a folder."), ("root", "The whole drive cannot be used. Choose a folder."),
                                           ("system", "That folder belongs to Ubuntu itself. Choose a different one.")])
def test_a_place_that_cannot_be_used_is_refused_with_the_reason_and_nothing_is_done(rig, place, reason):
    given = {"drive": rig.paths.root + "/inside", "short": "backup", "file": str(rig.drive / "a-file"), "root": "/", "system": "/usr/share"}[place]
    if place == "file":
        (rig.drive / "a-file").write_text("x")
    before = rig.tree(rig.paths.root)
    code, io = run(rig, "move", "--to", given, "--yes")
    assert code == 2 and "That place cannot be used:" in io.lines and "  " + reason in io.lines and io.lines[-1] == "Nothing was done." and io.prompts == []
    assert rig.tree(rig.paths.root) == before and rig.saved().scratch == Scratch()


def test_a_place_that_is_a_network_or_a_read_only_drive_is_refused(rig):
    rig.system.mounts = "/dev/sda1 / ext4 rw 0 0\nserver:/x %s nfs4 rw 0 0\n" % rig.drive
    code, io = run(rig, *move_to(rig), "--yes")
    assert code == 2 and "  That is a network drive. The voice must not travel over a network." in io.lines
    rig.system.mounts = "/dev/sda1 / ext4 rw 0 0\n/dev/sdb1 %s ext4 ro 0 0\n" % rig.drive
    assert "  That drive is read-only." in run(rig, *move_to(rig), "--yes")[1].lines


def test_a_place_where_another_persons_training_files_are_is_refused(rig):
    os.makedirs(target_of(rig))
    Path(target_of(rig), sc.MARKER_NAME).write_text(sc.marker_text("somebody-else"))
    code, io = run(rig, *move_to(rig), "--yes")
    assert code == 2 and "  That place already holds another person's training files." in io.lines and os.listdir(target_of(rig)) == [sc.MARKER_NAME]


def test_a_place_inside_another_project_is_refused(rig):
    other = rig.second_project()
    code, io = run(rig, "move", "--project", "voice-check", "--to", rig.home.projects + "/" + other.id + "/recordings", "--yes")
    assert code == 2 and "  That folder belongs to another person's project." in io.lines
    code, io = run(rig, "move", "--project", "voice-check", "--to", rig.paths.recordings, "--yes")
    assert code == 2 and "  That folder is inside this project's own folders. Choose somewhere else." in io.lines and "another person's project" not in io.text, "its own folders are not another person's"


def test_every_reason_a_place_is_refused_for_is_said_not_only_the_first(rig):
    (Path(rig.paths.root) / "a-file").write_text("x")
    code, io = run(rig, "move", "--to", rig.paths.root + "/a-file", "--yes")
    assert code == 2 and "  That is a file, not a folder." in io.lines and "  That folder is inside this project's own folders. Choose somewhere else." in io.lines


def test_a_place_reached_by_a_link_is_still_the_place_the_scratch_is_in(rig, tmp_path):
    link = tmp_path / "link-to-drive"
    os.symlink(rig.drive, link)
    save_project(rig.paths, with_scratch_place(rig.project, str(link)))              # a project file written with the path as it was typed
    sm.prepare_target(sm.Plan(rig.project.id, "", str(rig.drive) + "/ack-voice-scratch/" + rig.project.id, str(rig.drive), sm.Tree((), (), ()), ""))
    code, io = run(rig, "move", "--to", str(rig.drive), "--yes")
    assert code == 2 and io.lines[-1] == "Nothing was done." and "The scratch is already in" in io.text


def test_a_place_that_is_already_where_the_scratch_is_says_so_and_does_nothing(rig):
    moved_to_drive(rig)
    code, io = run(rig, *move_to(rig), "--yes")
    assert code == 2 and "The scratch is already in %s." % target_of(rig) in io.lines and io.lines[-1] == "Nothing was done."
    code, io = run(rig, "move", "--default", "--yes", answers=["no"])
    assert code == 0
    code, io = run(rig, "move", "--default", "--yes")
    assert code == 2 and "The scratch is already in %s." % rig.paths.default_scratch in io.lines


def test_moving_back_to_a_default_folder_that_still_has_the_old_files_reuses_them_and_keeps_what_else_is_there(rig):
    moved_to_drive(rig)
    ScratchRig.put(rig.paths.default_scratch, "left.txt", b"x")
    code, io = run(rig, "move", "--default", "--yes", answers=["no"])
    assert code == 0 and rig.saved().scratch == Scratch() and "The copy is made and checked: 0 files copied now, 4 already there." in io.lines
    assert Path(rig.paths.default_scratch, "left.txt").read_bytes() == b"x"


# ---------------------------------------------------------------- move: room

def test_not_enough_room_is_said_with_the_sizes_and_nothing_is_done(rig):
    rig.system.free = lambda path: (10 ** 9, 1000)
    before = rig.tree(rig.paths.root)
    code, io = run(rig, *move_to(rig), "--yes")
    assert code == 2 and "There is not enough room there. About %s is needed, and %s is free." % (size_text(TOTAL), size_text(1000)) in io.lines and io.lines[-1] == "Nothing was done."
    assert io.prompts == [] and rig.tree(rig.paths.root) == before and os.listdir(rig.drive) == []


def test_room_that_is_little_on_the_projects_own_drive_is_said_and_it_goes_on_to_ask(rig):
    from voice_studio.core import diskbudget as db
    moved_to_drive(rig)
    floors = db.floors_for(db.DEFAULT_TABLE, True)
    for free, tight, enough in ((TOTAL + floors.stop - 1, False, False), (TOTAL + floors.stop, True, True), (TOTAL + floors.low - 1, True, True), (TOTAL + floors.low, False, True)):
        rig.system.free = lambda path, free=free: (10 ** 13, free)
        code, io = run(rig, "move", "--default", answers=["no"])
        assert ("There is room, but not much is left afterwards." in io.lines) == tight and bool(io.prompts) == enough, free
        assert ("There is not enough room there." in " ".join(io.lines)) == (not enough)


def test_on_another_drive_the_copy_and_a_margin_must_fit_and_there_is_no_little(rig, monkeypatch):
    from voice_studio.core import projectbackup as pb
    monkeypatch.setattr(pb, "same_drive", lambda a, b: False)
    for free, enough in ((TOTAL + pb.REMOTE_MARGIN - 1, False), (TOTAL + pb.REMOTE_MARGIN, True)):
        rig.system.free = lambda path, free=free: (10 ** 13, free)
        code, io = run(rig, *move_to(rig), answers=["no"])
        assert bool(io.prompts) == enough and "There is room, but not much is left afterwards." not in io.lines, free
        assert ("There is not enough room there. About %s is needed, and %s is free." % (size_text(TOTAL), size_text(free)) in io.lines) == (not enough)


def test_the_room_is_asked_about_the_place_that_exists_nearest_the_new_folder(rig):
    run(rig, *move_to(rig), answers=["no"])
    assert str(rig.drive) in rig.system.asked_free


def test_when_the_room_cannot_be_read_the_move_goes_on(rig):
    rig.system.free = lambda path: None
    code, io = run(rig, *move_to(rig), answers=["no"])
    assert code == 2 and io.prompts and "There is not enough room" not in io.text


# ---------------------------------------------------------------- move: a task, an unready place

def test_a_running_task_for_the_project_stops_the_move_before_anything_is_checked(rig):
    fake_job(rig.home.jobs, ["x"], "running", project=rig.project.id)
    code, io = run(rig, *move_to(rig), "--yes")
    assert code == 2 and io.prompts == [] and "  A task for this project is running, and it is using the scratch." in io.lines and "  Nothing was moved." in io.lines
    assert os.listdir(rig.drive) == []


def test_a_task_for_another_project_does_not_stop_it(rig):
    fake_job(rig.home.jobs, ["x"], "running", project="somebody-else")
    assert run(rig, *move_to(rig), answers=["no"])[1].prompts


def test_a_scratch_whose_drive_is_away_cannot_be_moved_from(rig):
    moved_to_drive(rig)
    os.unlink(target_of(rig) + "/" + sc.MARKER_NAME)
    code, io = run(rig, "move", "--default", "--yes")
    assert code == 2 and "  The scratch the project uses now cannot be read." in io.lines and "  If it is on a drive, plug the drive in and try again." in io.lines
    assert io.prompts == []


# ---------------------------------------------------------------- move: the whole thing

def test_a_move_copies_checks_switches_and_then_asks_about_the_old_place(rig):
    old_files = rig.contents(rig.paths.default_scratch)
    code, io = run(rig, *move_to(rig), answers=["yes", "no"])
    assert code == 0
    assert io.prompts == ["Move the scratch now? Type yes to go on. ", "Remove the old place now? It is not used any more. Type yes to delete it. "]
    assert "The copy is made and checked: 4 files copied now, 0 already there." in io.lines
    assert "Voice check now uses %s for its scratch." % target_of(rig) in io.lines
    assert "The old place still holds 4 files, about %s: %s" % (size_text(TOTAL), rig.paths.default_scratch) in io.lines
    assert rig.saved().scratch == Scratch(SCRATCH_CUSTOM, str(rig.drive)) and os.path.isfile(rig.paths.previous_json)
    new = rig.contents(target_of(rig))
    del new[sc.MARKER_NAME]
    assert new == old_files and rig.contents(rig.paths.default_scratch) == old_files, "the old place is untouched until the second yes"
    assert "The old place was kept. It is not used any more, and this tool will not list it. To remove it yourself, run: rm -r %s" % rig.paths.default_scratch in io.lines


def test_the_progress_is_told_at_most_eleven_times_and_ends_on_the_whole(tmp_path):
    files = {"datasets/set/%03d.wav" % i: b"RIFF" + bytes([i]) * 50 for i in range(25)}
    rig = ScratchRig(tmp_path, files=files)
    code, io = run(rig, *move_to(rig), answers=["yes", "no"])
    lines = [l for l in io.lines if l.startswith("  Copied ")]
    assert code == 0 and lines[0] == "  Copied 1 of 25 files." and lines[-1] == "  Copied 25 of 25 files." and len(lines) == 11
    assert lines == sorted(set(lines), key=lambda l: int(l.split()[1]))


def test_the_progress_for_a_few_files_tells_each_step_once(rig):
    code, io = run(rig, *move_to(rig), answers=["yes", "no"])
    assert [l for l in io.lines if l.startswith("  Copied ")] == ["  Copied 1 of 4 files.", "  Copied 2 of 4 files.", "  Copied 3 of 4 files.", "  Copied 4 of 4 files."]


def test_a_single_file_scratch_is_told_without_dividing_by_nothing(tmp_path):
    rig = ScratchRig(tmp_path, files={"datasets/a.txt": b"x"})
    shutil.rmtree(rig.paths.default_scratch + "/datasets/empty")
    code, io = run(rig, *move_to(rig), answers=["yes", "no"])
    assert code == 0 and "  Copied 1 of 1 files." in io.lines


def test_an_empty_scratch_moves_with_nothing_to_copy(rig):
    shutil.rmtree(rig.paths.default_scratch)
    code, io = run(rig, *move_to(rig), answers=["yes"])
    assert code == 0 and "  It is empty." in io.lines and "The copy is made and checked: 0 files copied now, 0 already there." in io.lines
    assert rig.saved().scratch.place == str(rig.drive) and not any(l.startswith("  Copied ") for l in io.lines) and len(io.prompts) == 1


def test_a_quoted_command_is_given_for_an_old_place_with_a_space_in_its_name(rig, tmp_path):
    spaced = tmp_path / "spare disk"
    spaced.mkdir()
    code, io = run(rig, "move", "--to", str(spaced), "--yes", answers=["no"])
    assert code == 0
    code, io = run(rig, "move", "--default", "--yes", answers=["no"])
    folder = str(spaced) + "/ack-voice-scratch/" + rig.project.id
    assert code == 0 and "To remove it yourself, run: rm -r '%s'" % folder in " ".join(io.lines)


def test_dash_dash_yes_answers_the_first_question_and_not_the_second(rig):
    code, io = run(rig, *move_to(rig), "--yes", answers=["no"])
    assert code == 0 and io.prompts == ["Remove the old place now? It is not used any more. Type yes to delete it. "] and os.path.isdir(rig.paths.default_scratch + "/datasets")
    assert rig.saved().scratch.place == str(rig.drive)


def test_a_yes_to_the_second_question_removes_the_old_place_and_says_how_much_came_back(rig):
    code, io = run(rig, *move_to(rig), answers=["yes", "yes"])
    assert code == 0 and "Done. The old place is removed. About %s is free again there." % size_text(TOTAL) in io.lines
    assert os.listdir(rig.paths.default_scratch) == [] and os.path.isdir(target_of(rig) + "/datasets/d1")


def test_with_nobody_to_answer_the_second_question_the_old_place_is_kept(rig):
    io = TermIO(["yes"], True)
    smf.run_scratch(list(move_to(rig)), rig.system, rig.home, CAT, io)
    assert os.path.isdir(rig.paths.default_scratch + "/datasets/d1")
    code, io = run(rig, "move", "--default", "--yes", interactive=False)
    assert code == 0 and rig.saved().scratch == Scratch() and os.path.isdir(target_of(rig) + "/datasets/d1") and "The old place was kept." in io.text


def test_the_old_place_that_cannot_be_removed_is_listed_and_the_move_still_counts_as_done_but_the_command_fails(rig, monkeypatch):
    from voice_studio.core import profiles
    monkeypatch.setattr(sm.profiles, "remove_tree", lambda path, failed: failed.append((path, "Permission denied")))
    real = sm.remove_old
    monkeypatch.setattr(sm, "remove_old", lambda place, project, jobs_root: real(place, project, jobs_root, lambda path, failed: failed.append((path, "Permission denied"))))
    code, io = run(rig, *move_to(rig), answers=["yes", "yes"])
    assert code == 1 and "These could not be removed:" in io.lines and any(l.endswith(": Permission denied") for l in io.lines) and not any(l.startswith("Done. The old place") for l in io.lines)
    assert rig.saved().scratch.place == str(rig.drive)


def test_only_ten_old_pieces_that_could_not_be_removed_are_listed(rig, monkeypatch):
    for i in range(12):
        ScratchRig.put(rig.paths.default_scratch, "extra%02d" % i, b"x")
    real = sm.remove_old
    monkeypatch.setattr(sm, "remove_old", lambda place, project, jobs_root: real(place, project, jobs_root, lambda path, failed: failed.append((path, "Permission denied"))))
    code, io = run(rig, *move_to(rig), answers=["yes", "yes"])
    assert code == 1 and len([l for l in io.lines if l.endswith(": Permission denied")]) == 10


def test_a_task_that_starts_before_the_removal_stops_it(rig):
    io = TermIO(["yes", "yes"], True)
    real = TermIO.ask

    def ask(self, prompt):
        answer = real(self, prompt)
        if prompt.startswith("Remove the old place"):
            fake_job(rig.home.jobs, ["x"], "running", project=rig.project.id)
        return answer
    TermIO.ask = ask
    try:
        code = smf.run_scratch(list(move_to(rig)), rig.system, rig.home, CAT, io)
    finally:
        TermIO.ask = real
    assert code == 1 and "  A task for this project is running, and it is using the scratch." in io.lines and os.path.isdir(rig.paths.default_scratch + "/datasets/d1")


def test_moving_back_into_the_project_copies_removes_the_chosen_folder_on_a_yes_and_leaves_the_place(rig):
    moved_to_drive(rig)
    code, io = run(rig, "move", "--default", answers=["yes", "yes"])
    assert code == 0 and rig.saved().scratch == Scratch() and "Voice check now uses %s for its scratch." % rig.paths.default_scratch in io.lines
    assert rig.contents(rig.paths.default_scratch)["datasets/d1/metadata.csv"] == FILES["datasets/d1/metadata.csv"]
    assert not os.path.exists(str(rig.drive) + "/ack-voice-scratch") and os.path.isdir(rig.drive)
    assert "The old place still holds 5 files, about %s: %s" % (size_text(TOTAL + len(sc.marker_text(rig.project.id))), target_of(rig)) in io.lines


def test_the_move_to_a_place_that_holds_an_earlier_copy_of_this_project_carries_on_from_it(rig):
    run(rig, *move_to(rig), "--yes", answers=["no"])
    shutil.rmtree(rig.paths.default_scratch)
    os.makedirs(rig.paths.default_scratch)
    run(rig, "move", "--default", "--yes", answers=["no"])
    os.unlink(rig.paths.previous_json)
    code, io = run(rig, *move_to(rig), "--yes", answers=["no"])
    assert code == 0 and "The copy is made and checked: 0 files copied now, 4 already there." in io.lines


# ---------------------------------------------------------------- move: when a step fails

def test_a_copy_that_fails_leaves_the_project_on_the_old_place_and_says_so_in_three_parts(rig, monkeypatch):
    real = sm._copy_file
    calls = {"n": 0}

    def flaky(source, target, entry):
        calls["n"] += 1
        if calls["n"] == 3:
            raise sm.MoveError("copy_failed", "datasets/d1/wav/a.wav: No space left on device")
        return real(source, target, entry)
    monkeypatch.setattr(sm, "_copy_file", flaky)
    code, io = run(rig, *move_to(rig), "--yes")
    assert code == 1 and rig.saved().scratch == Scratch() and io.prompts == []
    assert io.lines[-4:] == ["  A file could not be copied.", "  The project still uses the old place, and the old files were left as they are.",
                             "  Check that there is room and that the new place can be written to, then run the command again. It carries on from where it stopped.",
                             "  Technical detail: datasets/d1/wav/a.wav: No space left on device"]
    assert not any("now uses" in l for l in io.lines) and not any("old place" in l and "Remove" in l for l in io.lines)
    monkeypatch.setattr(sm, "_copy_file", real)
    code, io = run(rig, *move_to(rig), "--yes", answers=["no"])
    assert code == 0 and "The copy is made and checked: 2 files copied now, 2 already there." in io.lines


def test_a_copy_that_reads_back_wrong_is_reported_and_the_project_stays_on_the_old_place(rig, monkeypatch):
    real = sm._hash_of
    monkeypatch.setattr(sm, "_hash_of", lambda path: ("0" * 64, real(path)[1]) if path.endswith(sm.PARTIAL) else real(path))
    code, io = run(rig, *move_to(rig), "--yes")
    assert code == 1 and "  A file did not read back the same as it was written." in io.lines and rig.saved().scratch == Scratch()


def test_files_that_change_while_they_are_copied_stop_the_move(rig, monkeypatch):
    real = sm.copy_tree

    def changing(plan, on_file=None):
        done = real(plan, on_file)
        ScratchRig.put(plan.source, "datasets/d1/late.wav", b"RIFF late")
        return done
    monkeypatch.setattr(sm, "copy_tree", changing)
    code, io = run(rig, *move_to(rig), "--yes")
    assert code == 1 and "  The training files changed while they were being copied." in io.lines and "  Nothing was switched, and the project still uses the old place." in io.lines
    assert rig.saved().scratch == Scratch() and not any("The copy is made" in l for l in io.lines)


def test_a_task_that_starts_during_the_copy_stops_the_switch_and_the_copy_is_kept(rig, monkeypatch):
    real = sm.copy_tree

    def starting(plan, on_file=None):
        done = real(plan, on_file)
        fake_job(rig.home.jobs, ["x"], "running", project=rig.project.id)
        return done
    monkeypatch.setattr(sm, "copy_tree", starting)
    code, io = run(rig, *move_to(rig), "--yes")
    assert code == 1 and "  A task for this project is running, and it is using the scratch." in io.lines and rig.saved().scratch == Scratch()
    assert os.path.isfile(target_of(rig) + "/datasets/d1/metadata.csv") and "now uses" not in io.text


def test_a_record_that_cannot_be_saved_is_told_and_the_project_stays_on_the_old_place(rig, monkeypatch):
    def full(paths, project):
        raise OSError(28, "No space left on device")
    monkeypatch.setattr(sm, "save_project", full)
    code, io = run(rig, *move_to(rig), "--yes")
    assert code == 1 and "  The copy is made, but the project could not be told to use it." in io.lines and "  Technical detail: No space left on device" in io.lines and rig.saved().scratch == Scratch()
    assert not any("The old place still holds" in l for l in io.lines)


def test_a_target_that_is_in_the_way_when_the_copy_begins_is_told(rig, monkeypatch):
    real = sm.prepare_target

    def late(plan):
        ScratchRig.put(plan.target, "x.txt", b"x")
        return real(plan)
    monkeypatch.setattr(sm, "prepare_target", late)
    code, io = run(rig, *move_to(rig), "--yes")
    assert code == 1 and "  Something is already in the place it would move to." in io.lines and rig.saved().scratch == Scratch()


def test_the_plan_that_cannot_be_read_is_told_and_nothing_is_done(rig, monkeypatch):
    def refuse(root):
        raise OSError(5, "Input/output error")
    monkeypatch.setattr(sm, "read_tree", refuse)
    code, io = run(rig, *move_to(rig), "--yes")
    assert code == 2 and "  The scratch the project uses now cannot be read." in io.lines and "  Technical detail: Input/output error" in io.lines and os.listdir(rig.drive) == []


def test_ctrl_c_stops_cleanly_says_so_and_the_project_keeps_its_place(rig, monkeypatch):
    def interrupt(plan, on_file=None):
        raise KeyboardInterrupt
    monkeypatch.setattr(sm, "copy_tree", interrupt)
    code, io = run(rig, *move_to(rig), "--yes")
    assert code == 1 and io.lines[-1] == "Stopped. The project still uses the place it had, and the same command carries on from where it stopped." and rig.saved().scratch == Scratch()


def test_the_command_can_be_started_from_a_terminal(capsys):
    from voice_studio import scratch
    assert scratch.main(["help"]) == 0
    assert "ACK Voice Studio: scratch" in capsys.readouterr().out
