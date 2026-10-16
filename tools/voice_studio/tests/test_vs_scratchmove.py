# SPDX-License-Identifier: GPL-3.0-or-later
"""Moving a project's scratch (plan task VS-6.5, decision P20): what is read from the old place, how the copy is made and checked, when the project is switched, and what is removed afterwards.
Every test works on real files in real folders."""
import errno
import os
import stat
import threading
from pathlib import Path

import pytest

from vs_refresh_helpers import CAT
from vs_rounds_helpers import fake_job
from vs_scratchmove_helpers import FILES, ScratchRig
from voice_studio.core import scratch as sc, scratchmove as sm
from voice_studio.core.paths import ProjectPaths
from voice_studio.core.project import SCRATCH_CUSTOM, SCRATCH_DEFAULT, Scratch, with_scratch_place
from voice_studio.core.rounds_flow import scratch_ready, scratch_root


@pytest.fixture
def rig(tmp_path):
    return ScratchRig(tmp_path)


def code_of(fn, *a, **kw):
    with pytest.raises(sm.MoveError) as caught:
        fn(*a, **kw)
    return caught.value.code


def make_plan(rig, place=True):
    target_place = str(rig.drive) if place else ""
    target = sc.scratch_dir_for(target_place, rig.project.id) if place else rig.paths.default_scratch
    return sm.plan(rig.project, rig.paths, rig.paths.default_scratch, target, target_place, rig.home.jobs)


def ready(rig, plan):
    sm.prepare_target(plan)
    return plan


# ---------------------------------------------------------------- reading a place

def test_a_tree_lists_the_files_in_order_with_their_sizes_and_the_folders_even_when_empty(rig):
    tree = sm.read_tree(rig.paths.default_scratch)
    assert [f.rel for f in tree.files] == sorted(FILES) and [f.size for f in tree.files] == [len(FILES[r]) for r in sorted(FILES)]
    assert tree.dirs == ("caches", "caches/d1-r001", "datasets", "datasets/d1", "datasets/d1/wav", "datasets/empty") and tree.skipped == ()
    assert tree.bytes == sum(len(v) for v in FILES.values())


def test_the_marker_at_the_top_is_not_part_of_a_tree_but_a_file_of_that_name_further_down_is(rig):
    root = rig.paths.default_scratch
    Path(root, sc.MARKER_NAME).write_text("marker")
    ScratchRig.put(root, "datasets/d1/" + sc.MARKER_NAME, b"mine")
    tree = sm.read_tree(root)
    assert sc.MARKER_NAME not in [f.rel for f in tree.files] and "datasets/d1/" + sc.MARKER_NAME in [f.rel for f in tree.files]


def test_a_link_or_a_special_file_is_listed_as_skipped_and_never_followed(rig, tmp_path):
    root = rig.paths.default_scratch
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_text("not scratch")
    os.symlink(outside, root + "/linked-folder")
    os.symlink(outside / "secret.txt", root + "/linked-file")
    os.symlink(tmp_path / "gone", root + "/broken")
    os.mkfifo(root + "/pipe")
    tree = sm.read_tree(root)
    assert tree.skipped == ("broken", "linked-file", "linked-folder", "pipe")
    assert "linked-folder" not in tree.dirs and not [f for f in tree.files if "secret" in f.rel or "linked" in f.rel]


def test_a_place_that_cannot_be_read_raises(rig, tmp_path):
    with pytest.raises(OSError):
        sm.read_tree(str(tmp_path / "nothing-here"))


def test_the_fingerprint_changes_with_each_thing_a_tree_holds_and_not_with_nothing():
    base = sm.Tree((sm.FileEntry("a", 1), sm.FileEntry("b", 2)), ("d",), ("s",))
    same = sm.Tree((sm.FileEntry("a", 1), sm.FileEntry("b", 2)), ("d",), ("s",))
    others = [sm.Tree((sm.FileEntry("a", 1),), ("d",), ("s",)), sm.Tree((sm.FileEntry("a", 1), sm.FileEntry("c", 2)), ("d",), ("s",)), sm.Tree((sm.FileEntry("a", 1), sm.FileEntry("b", 3)), ("d",), ("s",)),
              sm.Tree(base.files, ("e",), ("s",)), sm.Tree(base.files, ("d",), ("t",)), sm.Tree(base.files, (), ("s",)), sm.Tree(base.files, ("d",), ())]
    assert base.fingerprint == same.fingerprint and len({base.fingerprint, *(t.fingerprint for t in others)}) == 8
    assert sm.Tree((sm.FileEntry("a", 1), sm.FileEntry("b", 2)), (), ()).fingerprint != sm.Tree((sm.FileEntry("a|1b", 2),), (), ()).fingerprint, "a name that imitates the separators"
    assert sm.Tree((), ("x",), ()).fingerprint != sm.Tree((), (), ("d|x",)).fingerprint, "a skipped item that imitates a folder"


def test_the_error_codes_are_exactly_these():
    assert sm.ERROR_CODES == ("job_running", "changed", "source_missing", "target_in_the_way", "copy_failed", "differs", "not_saved")


# ---------------------------------------------------------------- the plan

def test_a_plan_names_the_old_and_the_new_folder_and_what_would_be_copied(rig):
    plan = make_plan(rig)
    assert plan.source == rig.paths.default_scratch and plan.target == str(rig.drive) + "/ack-voice-scratch/" + rig.project.id and plan.target_place == str(rig.drive)
    assert plan.tree.bytes == sum(len(v) for v in FILES.values()) and plan.blocked == "" and plan.project_id == rig.project.id


def test_a_default_scratch_that_was_never_made_holds_nothing(rig):
    import shutil
    shutil.rmtree(rig.paths.default_scratch)
    assert make_plan(rig).tree == sm.Tree((), (), ())


def test_a_chosen_place_that_cannot_be_read_is_not_a_plan(rig):
    place = str(rig.drive / "gone")
    moved = with_scratch_place(rig.project, place)
    assert code_of(sm.plan, moved, rig.paths, sc.scratch_dir_for(place, rig.project.id), rig.paths.default_scratch, "", rig.home.jobs) == "source_missing"


@pytest.mark.parametrize("status", ["starting", "running", "stopping"])
def test_a_task_for_the_project_that_is_starting_running_or_stopping_blocks_the_move(rig, status):
    fake_job(rig.home.jobs, ["x"], status, project=rig.project.id)
    assert make_plan(rig).blocked == "job_running"


def test_a_task_that_has_ended_or_belongs_to_another_project_does_not_block_it(rig):
    fake_job(rig.home.jobs, ["x"], "finished", project=rig.project.id)
    fake_job(rig.home.jobs, ["x"], "running", project="somebody-else")
    assert make_plan(rig).blocked == ""


# ---------------------------------------------------------------- making the new folder

def test_the_new_folder_in_a_chosen_place_is_made_with_its_marker(rig):
    plan = ready(rig, make_plan(rig))
    assert os.path.isdir(plan.target) and sc.check_marker(Path(plan.target, sc.MARKER_NAME).read_text(), rig.project.id) is sc.MarkerState.OK


def test_an_earlier_folder_of_the_same_project_is_reused_and_another_projects_is_not(rig):
    plan = make_plan(rig)
    sm.prepare_target(plan)
    sm.prepare_target(plan)                                                    # twice: the second finds its own marker
    Path(plan.target, sc.MARKER_NAME).write_text(sc.marker_text("somebody-else"))
    assert code_of(sm.prepare_target, plan) == "target_in_the_way"


def test_a_folder_with_other_files_and_no_marker_is_in_the_way_and_is_left_alone(rig):
    plan = make_plan(rig)
    ScratchRig.put(plan.target, "mine.txt", b"x")
    with pytest.raises(sm.MoveError) as caught:
        sm.prepare_target(plan)
    assert caught.value.code == "target_in_the_way" and caught.value.detail.startswith("a folder with other files in it") and os.listdir(plan.target) == ["mine.txt"]


def test_a_place_that_is_not_a_folder_is_in_the_way(rig):
    plan = sm.plan(rig.project, rig.paths, rig.paths.default_scratch, str(rig.drive / "nope/ack-voice-scratch/x"), str(rig.drive / "nope"), rig.home.jobs)
    assert code_of(sm.prepare_target, plan) == "target_in_the_way"


def test_the_default_folder_inside_the_project_is_made_when_it_is_not_there_and_reused_when_something_is_in_it(rig):
    plan = sm.Plan(rig.project.id, str(rig.drive), rig.paths.default_scratch, "", sm.Tree((), (), ()), "")
    import shutil
    shutil.rmtree(rig.paths.default_scratch)
    sm.prepare_target(plan)
    assert os.path.isdir(rig.paths.default_scratch) and stat.S_IMODE(os.stat(rig.paths.default_scratch).st_mode) == 0o700
    ScratchRig.put(rig.paths.default_scratch, "left.txt", b"x")
    sm.prepare_target(plan)
    assert os.listdir(rig.paths.default_scratch) == ["left.txt"]


def test_a_folder_that_cannot_be_made_is_a_copy_failure_with_the_reason(rig, monkeypatch):
    plan = make_plan(rig)

    def refuse(path, mode=0o777, exist_ok=False):
        raise OSError(errno.EACCES, "Permission denied")
    monkeypatch.setattr(sm.os, "makedirs", refuse)
    default = sm.Plan(rig.project.id, plan.target, rig.paths.default_scratch + "/inner", "", plan.tree, "")
    with pytest.raises(sm.MoveError) as caught:
        sm.prepare_target(default)
    assert caught.value.code == "copy_failed" and caught.value.detail == "Permission denied"


# ---------------------------------------------------------------- copying

def test_everything_is_copied_exactly_and_the_old_place_is_not_touched(rig):
    before = rig.tree(rig.paths.default_scratch)
    plan = ready(rig, make_plan(rig))
    done = sm.copy_tree(plan)
    new = rig.contents(plan.target)
    del new[sc.MARKER_NAME]
    assert new == rig.contents(rig.paths.default_scratch)
    assert done == sm.Copied(4, 0, sum(len(v) for v in FILES.values())) and rig.tree(rig.paths.default_scratch) == before
    assert not [p for p in Path(plan.target).rglob("*") if p.name.endswith(sm.PARTIAL)]


def test_the_copy_is_private_to_the_person(rig):
    plan = ready(rig, make_plan(rig))
    sm.copy_tree(plan)
    for path in Path(plan.target).rglob("*"):
        if path.name == sc.MARKER_NAME:
            continue
        assert stat.S_IMODE(path.stat().st_mode) == (0o700 if path.is_dir() else 0o600), path


def test_an_empty_folder_is_copied_too(rig):
    plan = ready(rig, make_plan(rig))
    sm.copy_tree(plan)
    assert os.path.isdir(plan.target + "/datasets/empty")


def test_a_second_try_copies_nothing_that_is_already_there_and_identical(rig):
    plan = ready(rig, make_plan(rig))
    sm.copy_tree(plan)
    again = sm.copy_tree(plan)
    assert again == sm.Copied(0, 4, 0)


def test_a_file_that_is_there_but_wrong_is_replaced_whether_it_has_the_same_size_or_not(rig):
    plan = ready(rig, make_plan(rig))
    sm.copy_tree(plan)
    same_size = plan.target + "/datasets/d1/wav/a.wav"
    Path(same_size).write_bytes(b"x" * len(FILES["datasets/d1/wav/a.wav"]))
    Path(plan.target + "/caches/d1-r001/mels.bin").write_bytes(b"short")
    again = sm.copy_tree(plan)
    assert again.copied == 2 and again.already == 2 and rig.contents(plan.target)["datasets/d1/wav/a.wav"] == FILES["datasets/d1/wav/a.wav"] and Path(plan.target, "caches/d1-r001/mels.bin").read_bytes() == FILES["caches/d1-r001/mels.bin"]


def test_a_link_in_the_way_of_a_new_file_is_replaced_and_what_it_pointed_to_is_not_written(rig, tmp_path):
    plan = ready(rig, make_plan(rig))
    outside = tmp_path / "outside.bin"
    outside.write_bytes(b"mine")
    os.makedirs(plan.target + "/datasets/d1/wav", exist_ok=True)
    os.symlink(outside, plan.target + "/datasets/d1/wav/a.wav")
    sm.copy_tree(plan)
    assert outside.read_bytes() == b"mine" and not os.path.islink(plan.target + "/datasets/d1/wav/a.wav")
    assert Path(plan.target + "/datasets/d1/wav/a.wav").read_bytes() == FILES["datasets/d1/wav/a.wav"]


def test_the_progress_is_told_after_each_file_in_order(rig):
    plan = ready(rig, make_plan(rig))
    seen = []
    sm.copy_tree(plan, lambda done, total, rel: seen.append((done, total, rel)))
    assert seen == [(1, 4, "caches/d1-r001/mels.bin"), (2, 4, "datasets/d1/metadata.csv"), (3, 4, "datasets/d1/wav/a.wav"), (4, 4, "datasets/d1/wav/b.wav")]


def test_a_file_that_changed_size_after_the_plan_stops_the_copy_and_leaves_no_half_file(rig):
    plan = ready(rig, make_plan(rig))
    Path(rig.paths.default_scratch, "datasets/d1/wav/b.wav").write_bytes(b"RIFF" + b"x" * 9000)
    with pytest.raises(sm.MoveError) as caught:
        sm.copy_tree(plan)
    assert caught.value.code == "changed" and caught.value.detail == "datasets/d1/wav/b.wav"
    assert not os.path.exists(plan.target + "/datasets/d1/wav/b.wav") and not os.path.exists(plan.target + "/datasets/d1/wav/b.wav" + sm.PARTIAL)
    assert os.path.isfile(plan.target + "/datasets/d1/wav/a.wav"), "what was copied before stays"


def test_a_stale_half_file_longer_than_the_new_one_does_not_spoil_the_copy(rig):
    plan = ready(rig, make_plan(rig))
    os.makedirs(plan.target + "/datasets/d1/wav", exist_ok=True)
    Path(plan.target + "/datasets/d1/wav/a.wav" + sm.PARTIAL).write_bytes(b"old garbage " * 5000)
    sm.copy_tree(plan)
    assert Path(plan.target + "/datasets/d1/wav/a.wav").read_bytes() == FILES["datasets/d1/wav/a.wav"] and not list(Path(plan.target).rglob("*" + sm.PARTIAL))


def test_a_file_that_cannot_even_be_opened_for_writing_is_a_copy_failure_not_a_crash(rig, monkeypatch):
    plan = ready(rig, make_plan(rig))

    def refuse(path, flags, mode=0o777):
        raise OSError(errno.EACCES, "Permission denied")
    monkeypatch.setattr(sm.os, "open", refuse)
    with pytest.raises(sm.MoveError) as caught:
        sm.copy_tree(plan)
    assert caught.value.code == "copy_failed" and caught.value.detail == "caches/d1-r001/mels.bin: Permission denied"


def test_a_link_in_the_way_that_points_at_a_file_with_the_same_bytes_is_still_replaced_by_a_real_file(rig, tmp_path):
    plan = ready(rig, make_plan(rig))
    outside = tmp_path / "same.bin"
    outside.write_bytes(FILES["datasets/d1/wav/a.wav"])
    os.makedirs(plan.target + "/datasets/d1/wav", exist_ok=True)
    os.symlink(outside, plan.target + "/datasets/d1/wav/a.wav")
    done = sm.copy_tree(plan)
    assert done.copied == 4 and not os.path.islink(plan.target + "/datasets/d1/wav/a.wav") and outside.read_bytes() == FILES["datasets/d1/wav/a.wav"]


def test_a_file_that_vanished_after_the_plan_is_a_copy_failure_naming_it(rig):
    plan = ready(rig, make_plan(rig))
    os.unlink(rig.paths.default_scratch + "/datasets/d1/metadata.csv")
    with pytest.raises(sm.MoveError) as caught:
        sm.copy_tree(plan)
    assert caught.value.code == "copy_failed" and caught.value.detail.startswith("datasets/d1/metadata.csv: ")
    assert not os.path.exists(plan.target + "/datasets/d1/metadata.csv" + sm.PARTIAL)


def test_a_full_disk_while_writing_is_a_copy_failure_with_the_reason_and_leaves_no_half_file(rig, monkeypatch):
    plan = ready(rig, make_plan(rig))
    real = os.fsync

    def full(fd):
        raise OSError(errno.ENOSPC, "No space left on device")
    monkeypatch.setattr(sm.os, "fsync", full)
    with pytest.raises(sm.MoveError) as caught:
        sm.copy_tree(plan)
    assert caught.value.code == "copy_failed" and caught.value.detail.endswith(": No space left on device") and not list(Path(plan.target).rglob("*" + sm.PARTIAL))


def test_a_copy_that_does_not_read_back_the_same_is_deleted_and_reported(rig, monkeypatch):
    plan = ready(rig, make_plan(rig))
    real = sm._hash_of

    def lying(path):
        digest, size = real(path)
        return ("0" * 64, size) if path.endswith(sm.PARTIAL) else (digest, size)
    monkeypatch.setattr(sm, "_hash_of", lying)
    with pytest.raises(sm.MoveError) as caught:
        sm.copy_tree(plan)
    assert caught.value.code == "differs" and caught.value.detail == "caches/d1-r001/mels.bin" and not list(Path(plan.target).rglob("*" + sm.PARTIAL))
    assert not os.path.exists(plan.target + "/caches/d1-r001/mels.bin")


def test_a_copy_of_the_wrong_length_is_a_difference_too(rig, monkeypatch):
    plan = ready(rig, make_plan(rig))
    real = sm._hash_of
    monkeypatch.setattr(sm, "_hash_of", lambda path: (lambda d, s: (d, s - 1 if path.endswith(sm.PARTIAL) else s))(*real(path)))
    assert code_of(sm.copy_tree, plan) == "differs"


def test_a_read_back_that_fails_is_a_copy_failure(rig, monkeypatch):
    plan = ready(rig, make_plan(rig))
    real = sm._hash_of

    def broken(path):
        if path.endswith(sm.PARTIAL):
            raise OSError(errno.EIO, "Input/output error")
        return real(path)
    monkeypatch.setattr(sm, "_hash_of", broken)
    with pytest.raises(sm.MoveError) as caught:
        sm.copy_tree(plan)
    assert caught.value.code == "copy_failed" and "Input/output error" in caught.value.detail and not list(Path(plan.target).rglob("*" + sm.PARTIAL))


def test_a_file_that_cannot_be_put_in_place_is_a_copy_failure(rig, monkeypatch):
    plan = ready(rig, make_plan(rig))

    def refuse(a, b):
        raise OSError(errno.EXDEV, "Invalid cross-device link")
    monkeypatch.setattr(sm.os, "replace", refuse)
    with pytest.raises(sm.MoveError) as caught:
        sm.copy_tree(plan)
    assert caught.value.code == "copy_failed" and "Invalid cross-device link" in caught.value.detail and not list(Path(plan.target).rglob("*" + sm.PARTIAL))


def test_a_folder_that_cannot_be_made_while_copying_is_a_copy_failure(rig, monkeypatch):
    plan = ready(rig, make_plan(rig))

    def refuse(path, mode=0o777, exist_ok=False):
        raise OSError(errno.EACCES, "Permission denied")
    monkeypatch.setattr(sm.os, "makedirs", refuse)
    with pytest.raises(sm.MoveError) as caught:
        sm.copy_tree(plan)
    assert caught.value.code == "copy_failed" and caught.value.detail == "caches: Permission denied"


# ---------------------------------------------------------------- the last look

def test_a_whole_copy_passes_the_last_look(rig):
    plan = ready(rig, make_plan(rig))
    sm.copy_tree(plan)
    sm.check_copy(plan)


def test_the_last_look_refuses_an_old_place_that_is_not_what_the_plan_listed(rig):
    plan = ready(rig, make_plan(rig))
    sm.copy_tree(plan)
    for change in (lambda r: ScratchRig.put(r, "datasets/d1/new.txt", b"n"), lambda r: os.unlink(r + "/datasets/d1/metadata.csv"), lambda r: Path(r, "caches/d1-r001/mels.bin").write_bytes(b"short"),
                   lambda r: os.makedirs(r + "/more"), lambda r: os.symlink("/tmp", r + "/link")):
        root = rig.paths.default_scratch
        before = rig.tree(root)
        change(root)
        assert code_of(sm.check_copy, plan) == "changed"
        import shutil
        shutil.rmtree(root)
        for rel, data in FILES.items():
            ScratchRig.put(root, rel, data)
        os.makedirs(root + "/datasets/empty")


def test_the_last_look_refuses_a_new_place_that_is_missing_something(rig, tmp_path):
    plan = ready(rig, make_plan(rig))
    sm.copy_tree(plan)
    victim = plan.target + "/datasets/d1/wav/a.wav"
    rel = "datasets/d1/wav/a.wav"

    def says_differs(named):
        with pytest.raises(sm.MoveError) as caught:
            sm.check_copy(plan)
        assert caught.value.code == "differs" and caught.value.detail == named
    os.unlink(victim)
    says_differs(rel)
    Path(victim).write_bytes(b"short")
    says_differs(rel)
    os.unlink(victim)
    os.symlink(tmp_path, victim)
    says_differs(rel)
    os.unlink(victim)
    same = tmp_path / "same.bin"
    same.write_bytes(FILES[rel])
    os.symlink(same, victim)                                  # a link to a file of the right size and bytes is still not a copy
    says_differs(rel)
    os.unlink(victim)
    Path(victim).write_bytes(FILES[rel])
    import shutil
    shutil.rmtree(plan.target + "/datasets/empty")
    says_differs("datasets/empty")


def test_the_last_look_says_so_when_the_old_place_has_gone(rig):
    plan = ready(rig, make_plan(rig))
    import shutil
    shutil.rmtree(rig.paths.default_scratch)
    with pytest.raises(sm.MoveError) as caught:
        sm.check_copy(plan)
    assert caught.value.code == "source_missing" and caught.value.detail == "No such file or directory"


def test_the_last_look_accepts_a_default_scratch_that_never_was_and_still_is_not(rig):
    import shutil
    shutil.rmtree(rig.paths.default_scratch)
    plan = ready(rig, make_plan(rig))
    sm.check_copy(plan)
    ScratchRig.put(rig.paths.default_scratch, "late.txt", b"x")
    assert code_of(sm.check_copy, plan) == "changed"


# ---------------------------------------------------------------- switching

def test_the_project_is_switched_to_the_new_place_and_the_old_record_is_kept(rig):
    plan = ready(rig, make_plan(rig))
    moved = sm.switch(rig.project, rig.paths, plan, rig.home.jobs)
    saved = rig.saved()
    assert moved == saved and saved.scratch == Scratch(SCRATCH_CUSTOM, str(rig.drive)) and os.path.isfile(rig.paths.previous_json)
    assert scratch_root(saved, rig.paths).root == plan.target
    assert scratch_ready(saved, rig.paths)


def test_after_a_switch_the_project_can_start_a_job_only_if_the_marker_is_there(rig):
    plan = ready(rig, make_plan(rig))
    moved = sm.switch(rig.project, rig.paths, plan, rig.home.jobs)
    assert scratch_ready(moved, rig.paths)
    os.unlink(plan.target + "/" + sc.MARKER_NAME)
    assert not scratch_ready(moved, rig.paths)


def test_moving_back_to_the_default_puts_the_project_on_the_default_again(rig):
    plan = ready(rig, make_plan(rig))
    custom = sm.switch(rig.project, rig.paths, plan, rig.home.jobs)
    back = sm.Plan(rig.project.id, plan.target, rig.paths.default_scratch, "", plan.tree, "")
    sm.switch(custom, rig.paths, back, rig.home.jobs)
    assert rig.saved().scratch == Scratch(SCRATCH_DEFAULT, None) and scratch_root(rig.saved(), rig.paths).root == rig.paths.default_scratch


def test_a_task_that_started_since_the_plan_stops_the_switch_and_the_project_stays_as_it_was(rig):
    plan = ready(rig, make_plan(rig))
    fake_job(rig.home.jobs, ["x"], "running", project=rig.project.id)
    before = Path(rig.paths.project_json).read_bytes()
    assert code_of(sm.switch, rig.project, rig.paths, plan, rig.home.jobs) == "job_running" and Path(rig.paths.project_json).read_bytes() == before


def test_a_record_that_cannot_be_saved_is_reported_and_the_project_stays_as_it_was(rig, monkeypatch):
    plan = ready(rig, make_plan(rig))
    before = Path(rig.paths.project_json).read_bytes()

    def full(paths, project):
        raise OSError(errno.ENOSPC, "No space left on device")
    monkeypatch.setattr(sm, "save_project", full)
    with pytest.raises(sm.MoveError) as caught:
        sm.switch(rig.project, rig.paths, plan, rig.home.jobs)
    assert caught.value.code == "not_saved" and caught.value.detail == "No space left on device" and Path(rig.paths.project_json).read_bytes() == before


def test_a_record_the_project_file_rules_refuse_is_reported_by_its_code(rig, monkeypatch):
    from voice_studio.core.project import ProjectError
    plan = ready(rig, make_plan(rig))

    def refuse(paths, project):
        raise ProjectError("bad_value", "scratch")
    monkeypatch.setattr(sm, "save_project", refuse)
    with pytest.raises(sm.MoveError) as caught:
        sm.switch(rig.project, rig.paths, plan, rig.home.jobs)
    assert caught.value.code == "not_saved" and caught.value.detail == "bad_value"


# ---------------------------------------------------------------- the old place

def custom_project(rig):
    plan = ready(rig, make_plan(rig))
    sm.copy_tree(plan)
    return sm.switch(rig.project, rig.paths, plan, rig.home.jobs), plan


def test_the_old_default_place_is_offered_with_its_contents_when_it_holds_any(rig):
    old = sm.old_place(rig.project, rig.paths)
    assert old == sm.OldPlace(rig.paths.default_scratch, True, sum(len(v) for v in FILES.values()), 4)


def test_an_empty_or_missing_or_linked_default_place_is_not_offered(rig, tmp_path):
    import shutil
    shutil.rmtree(rig.paths.default_scratch)
    assert sm.old_place(rig.project, rig.paths) is None
    os.makedirs(rig.paths.default_scratch)
    assert sm.old_place(rig.project, rig.paths) is None
    shutil.rmtree(rig.paths.default_scratch)
    (tmp_path / "elsewhere").mkdir()
    ScratchRig.put(str(tmp_path / "elsewhere"), "x", b"x")
    os.symlink(tmp_path / "elsewhere", rig.paths.default_scratch)
    assert sm.old_place(rig.project, rig.paths) is None


def test_the_old_chosen_place_is_offered_only_while_its_marker_names_this_project(rig):
    custom, plan = custom_project(rig)
    old = sm.old_place(custom, rig.paths)
    assert old is not None and old.folder == plan.target and old.contents_only is False and old.files == 5, "the four files and the marker"
    marker = Path(plan.target, sc.MARKER_NAME)
    marker.write_text(sc.marker_text("somebody-else"))
    assert sm.old_place(custom, rig.paths) is None
    marker.write_text("{broken")
    assert sm.old_place(custom, rig.paths) is None
    marker.unlink()
    assert sm.old_place(custom, rig.paths) is None


def test_the_old_chosen_place_is_not_offered_when_it_is_a_link_or_gone(rig, tmp_path):
    import shutil
    custom, plan = custom_project(rig)
    real = tmp_path / "moved-away"
    os.rename(plan.target, real)
    os.symlink(real, plan.target)
    assert sm.old_place(custom, rig.paths) is None
    os.unlink(plan.target)
    assert sm.old_place(custom, rig.paths) is None


def test_a_project_whose_name_is_not_a_safe_folder_name_has_no_old_place_to_offer(rig):
    from dataclasses import replace
    custom, plan = custom_project(rig)
    assert sm.old_place(replace(custom, id="../x"), rig.paths) is None


def test_removing_the_old_default_place_takes_what_is_in_it_and_keeps_the_folder(rig, tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "keep.txt").write_text("keep")
    os.symlink(outside, rig.paths.default_scratch + "/link")
    old = sm.old_place(rig.project, rig.paths)
    result = sm.remove_old(old, rig.project, rig.home.jobs)
    assert result == sm.Removal(old.bytes, ()) and os.listdir(rig.paths.default_scratch) == [] and (outside / "keep.txt").read_text() == "keep"


def test_removing_an_old_chosen_place_takes_the_projects_folder_and_the_folder_that_held_it_when_empty_and_never_the_place(rig):
    custom, plan = custom_project(rig)
    old = sm.old_place(custom, rig.paths)
    result = sm.remove_old(old, custom, rig.home.jobs)
    assert result.failed == () and not os.path.exists(plan.target) and not os.path.exists(os.path.dirname(plan.target)) and os.path.isdir(rig.drive)


def test_the_folder_that_held_the_old_place_stays_when_another_project_is_in_it(rig):
    custom, plan = custom_project(rig)
    os.makedirs(os.path.dirname(plan.target) + "/somebody-else")
    sm.remove_old(sm.old_place(custom, rig.paths), custom, rig.home.jobs)
    assert not os.path.exists(plan.target) and os.path.isdir(os.path.dirname(plan.target) + "/somebody-else")


def test_a_task_that_started_stops_the_removal_and_nothing_is_removed(rig):
    old = sm.old_place(rig.project, rig.paths)
    fake_job(rig.home.jobs, ["x"], "running", project=rig.project.id)
    before = rig.tree(rig.paths.default_scratch)
    assert code_of(sm.remove_old, old, rig.project, rig.home.jobs) == "job_running" and rig.tree(rig.paths.default_scratch) == before


def test_a_piece_that_cannot_be_removed_is_reported_and_no_room_is_claimed(rig):
    old = sm.old_place(rig.project, rig.paths)

    def refuse(path, failed):
        failed.append((path, "Permission denied"))
    result = sm.remove_old(old, rig.project, rig.home.jobs, refuse)
    assert result.bytes == 0 and len(result.failed) == 2 and all(why == "Permission denied" for _p, why in result.failed)


def test_only_a_folder_named_for_scratch_is_taken_away_with_the_folder_of_the_old_place(rig, tmp_path):
    held = tmp_path / "held-by-something-else"
    (held / "mine").mkdir(parents=True)
    (held / "mine" / "x").write_text("x")
    result = sm.remove_old(sm.OldPlace(str(held / "mine"), False, 1, 1), rig.project, rig.home.jobs)
    assert result.failed == () and not (held / "mine").exists() and held.is_dir()


def test_the_chosen_place_that_could_not_be_removed_keeps_the_folder_that_held_it(rig):
    custom, plan = custom_project(rig)
    old = sm.old_place(custom, rig.paths)
    result = sm.remove_old(old, custom, rig.home.jobs, lambda path, failed: failed.append((path, "Permission denied")))
    assert result.failed == ((plan.target, "Permission denied"),) and os.path.isdir(os.path.dirname(plan.target))


def test_every_error_code_has_three_parts_in_words():
    from voice_studio.core.describe import error_text
    for code in sm.ERROR_CODES:
        parts = error_text(CAT, "scratchmove", code)
        assert parts.what and parts.changed and parts.next
