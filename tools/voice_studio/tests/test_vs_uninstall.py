# SPDX-License-Identifier: GPL-3.0-or-later
"""Uninstall (plan task VS-6.3, decision P19): what the plan lists and what it leaves alone, what a removal touches, and what stops it. Every test works on real files in real folders, with the
refresh tests' stand-in for the computer and the network, so there is a built set of programs, a listening model, a starting voice and a state folder to protect."""
import json
import os
import shutil
from pathlib import Path

import pytest
from dataclasses import replace

from vs_refresh_helpers import VOICE_BYTES, RefreshRig
from vs_rounds_helpers import fake_job
from voice_studio.core import areas, envbuild as eb, uninstall as un
from voice_studio.core.diskbudget import Kind
from voice_studio.core.project import create_project


@pytest.fixture
def rig(tmp_path):
    return RefreshRig(tmp_path)


def tree(root):
    found = {}
    for path in sorted(Path(root).rglob("*")):
        if path.is_file() and not path.is_symlink():
            found[str(path.relative_to(root))] = (path.read_bytes(), path.stat().st_mtime_ns)
        elif path.is_dir() and not path.is_symlink():
            found[str(path.relative_to(root)) + "/"] = None
    return found


def code_of(fn, *a, **kw):
    with pytest.raises(un.UninstallError) as caught:
        fn(*a, **kw)
    return caught.value.code


def make(rig):
    return un.plan(rig.home, [rig.spec])


def keep_things(rig):
    """Things that must come through an uninstall untouched: a project with a recording, a backup, a note."""
    create_project(rig.home.projects, "Anna", "own")
    recording = Path(rig.home.projects, "anna", "recordings")
    recording.mkdir(parents=True, exist_ok=True)
    (recording / "take.wav").write_bytes(b"RIFF" + b"1" * 50)
    Path(rig.home.backups).mkdir(parents=True, exist_ok=True)
    (Path(rig.home.backups) / "anna.tar").write_bytes(b"backup bytes")


# ---------------------------------------------------------------- what the plan lists

def test_the_plan_lists_the_built_programs_and_the_downloads_with_their_sizes_and_not_the_starting_voices(rig):
    plan = make(rig)
    assert [(p.kind, p.path) for p in plan.pieces] == [("programs", rig.env.env_dir), ("downloads", rig.home.downloads + "/models")]
    assert plan.pieces[0].bytes == sum(f.stat().st_size for f in Path(rig.env.env_dir).rglob("*") if f.is_file() and not f.is_symlink()) and plan.pieces[0].files == 7
    assert plan.pieces[1].bytes == sum(f.stat().st_size for f in Path(rig.home.downloads, "models").rglob("*") if f.is_file()) and plan.pieces[1].files == 2
    assert plan.total_bytes == plan.pieces[0].bytes + plan.pieces[1].bytes and plan.total_files == 9
    assert rig.voice_path().parent.as_posix() not in [p.path for p in plan.pieces] and all("voices" not in p.path for p in plan.pieces)
    assert plan.blocked == "" and plan.left_alone == 0


def test_the_plan_says_what_is_kept_and_how_many_projects(rig):
    keep_things(rig)
    create_project(rig.home.projects, "Ben", "own")
    plan = make(rig)
    assert plan.projects == 2 and plan.kept == (("backups", rig.home.backups), ("voices", rig.home.voices), ("state", rig.home.state))


def test_a_kept_folder_that_is_empty_or_missing_is_not_named(rig):
    shutil.rmtree(rig.home.voices)
    Path(rig.home.backups).mkdir(parents=True)
    assert make(rig).kept == (("state", rig.home.state),)


def test_a_kept_folder_that_is_a_link_is_not_named(rig, tmp_path):
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (elsewhere / "x").write_text("x")
    os.symlink(elsewhere, rig.home.backups)
    assert "backups" not in [name for name, _folder in make(rig).kept]


def test_nothing_set_up_means_nothing_to_remove(tmp_path):
    rig = RefreshRig(tmp_path, built=False, speech=False, voice=False)
    plan = make(rig)
    assert plan.pieces == () and plan.total_bytes == 0 and plan.left_alone == 0 and plan.blocked == ""


def test_a_home_with_no_tool_folder_at_all_has_nothing_to_remove(tmp_path):
    from voice_studio.core.paths import DataHome
    plan = un.plan(DataHome(str(tmp_path / "empty-home")), [])
    assert plan.pieces == () and plan.projects == 0 and plan.kept == ()


def test_every_kind_of_piece_and_every_kept_name_has_words():
    from vs_refresh_helpers import CAT
    for kind in un.KINDS:
        assert CAT.has("uninstall.kind." + kind)
    for name in un.KEPT:
        assert CAT.has("uninstall.kept." + name)


# ---------------------------------------------------------------- what is left alone

def test_a_folder_in_the_programs_place_that_this_tool_did_not_make_is_counted_and_left_alone(rig):
    place = Path(rig.home.environments)
    (place / "somebody-elses").mkdir()
    (place / "demo-0123456789").mkdir()                                        # a name shaped like ours but with no record in it
    (place / "demo-aaaaaaaaaa.txt").write_text("a file")
    plan = make(rig)
    assert plan.left_alone == 3 and [p.path for p in plan.pieces if p.kind == "programs"] == [rig.env.env_dir]


def test_a_folder_whose_record_is_for_other_programs_is_left_alone(rig):
    odd = Path(rig.home.environments, "demo-0123456789")
    shutil.copytree(rig.env.env_dir, odd, symlinks=True)
    plan = make(rig)
    assert plan.left_alone == 1 and odd.as_posix() not in [p.path for p in plan.pieces], "the name says one fingerprint and the record another"
    record = json.loads((odd / eb.RECORD_NAME).read_text())
    record["fingerprint"] = "0123456789" + record["fingerprint"][10:]
    (odd / eb.RECORD_NAME).write_text(json.dumps(record))
    plan = make(rig)
    assert plan.left_alone == 0 and odd.as_posix() in [p.path for p in plan.pieces], "name and record agree"
    record["id"] = "other"
    (odd / eb.RECORD_NAME).write_text(json.dumps(record))
    plan = make(rig)
    assert plan.left_alone == 1 and odd.as_posix() not in [p.path for p in plan.pieces], "the record is for other programs than the name says"


def test_a_copy_of_programs_this_tool_can_build_is_listed_even_when_it_is_not_the_one_in_use(rig):
    older = Path(rig.home.environments, "demo-" + "0123456789")
    shutil.copytree(rig.env.env_dir, older, symlinks=True)
    record = json.loads((older / eb.RECORD_NAME).read_text())
    record["fingerprint"] = "0123456789" + record["fingerprint"][10:]
    (older / eb.RECORD_NAME).write_text(json.dumps(record))
    plan = make(rig)
    assert sorted(p.path for p in plan.pieces if p.kind == "programs") == sorted([rig.env.env_dir, older.as_posix()]) and plan.left_alone == 0


def test_programs_of_a_kind_this_tool_cannot_build_are_left_alone(rig):
    assert un.plan(rig.home, []).left_alone == 1 and [p.kind for p in un.plan(rig.home, []).pieces] == ["downloads"]


def test_programs_being_built_this_moment_are_left_alone(rig):
    Path(rig.env.env_dir, eb.BUILD_LOCK_NAME).write_text("{}")
    plan = make(rig)
    assert plan.left_alone == 1 and rig.env.env_dir not in [p.path for p in plan.pieces]


def test_a_link_in_the_programs_place_or_the_downloads_is_left_alone_and_never_followed(rig, tmp_path):
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (elsewhere / "mine.txt").write_text("mine")
    os.symlink(elsewhere, Path(rig.home.environments, "demo-bbbbbbbbbb"))
    os.symlink(elsewhere, Path(rig.home.downloads, "linked"))
    plan = make(rig)
    assert plan.left_alone == 2 and not [p for p in plan.pieces if "linked" in p.path or "bbbbbbbbbb" in p.path]
    result = un.remove(rig.home, [rig.spec], plan)
    assert (elsewhere / "mine.txt").read_text() == "mine" and os.path.islink(Path(rig.home.downloads, "linked")) and result.failed == ()


def test_anything_else_in_the_tools_own_folder_is_left_alone(rig):
    Path(rig.home.tool, "extra").mkdir()
    Path(rig.home.tool, "note.txt").write_text("a file")
    plan = make(rig)
    assert plan.left_alone == 2
    un.remove(rig.home, [rig.spec], plan)
    assert Path(rig.home.tool, "extra").is_dir() and Path(rig.home.tool, "note.txt").read_text() == "a file"


def test_more_entries_than_the_tool_would_ever_make_are_left_alone_not_listed(rig, monkeypatch):
    monkeypatch.setattr(un, "MAX_ENTRIES", 2)
    for name in ("a", "b", "c", "d"):
        Path(rig.home.downloads, name).write_text("x")
    plan = make(rig)
    listed = [p.path for p in plan.pieces if p.kind == "downloads"]
    assert len(listed) == 2 and listed == [rig.home.downloads + "/a", rig.home.downloads + "/b"]
    assert plan.left_alone == 4, "the four entries after the first two (c, d, models and voices) are counted, not listed, and not removed"
    un.remove(rig.home, [rig.spec], plan)
    assert os.path.isdir(rig.home.downloads + "/models") and not os.path.exists(rig.home.downloads + "/a")


# ---------------------------------------------------------------- what stops a removal

@pytest.mark.parametrize("status", ["starting", "running", "stopping"])
def test_a_task_that_is_starting_running_or_stopping_stops_the_removal(rig, status):
    os.makedirs(rig.home.jobs, exist_ok=True)
    fake_job(rig.home.jobs, ["x"], status, project="voice-check")
    plan = make(rig)
    before = tree(rig.home.root)
    assert plan.blocked == "job_running" and code_of(un.remove, rig.home, [rig.spec], plan) == "job_running" and tree(rig.home.root) == before


@pytest.mark.parametrize("status", ["finished", "stopped", "failed", "interrupted", "never_started"])
def test_a_task_that_has_ended_does_not_stop_it(rig, status):
    os.makedirs(rig.home.jobs, exist_ok=True)
    fake_job(rig.home.jobs, ["x"], status, project="voice-check")
    assert make(rig).blocked == ""


def test_a_list_that_changed_since_it_was_shown_removes_nothing(rig):
    shown = make(rig)
    Path(rig.home.downloads, "arrived.bin").write_bytes(b"new")
    before = tree(rig.home.root)
    assert code_of(un.remove, rig.home, [rig.spec], shown) == "changed" and tree(rig.home.root) == before


def test_a_file_that_grew_since_it_was_shown_changes_the_list(rig):
    shown = make(rig)
    Path(rig.home.downloads, "models", "a.bin").write_bytes(b"longer than before" * 100)
    assert code_of(un.remove, rig.home, [rig.spec], shown) == "changed"


def test_the_fingerprint_depends_on_each_part_of_each_piece():
    base = [un.Piece("programs", "/a", 1, 1), un.Piece("downloads", "/b", 2, 2)]
    prints = {un._fingerprint(base), un._fingerprint(base[:1]), un._fingerprint(base[::-1]), un._fingerprint([un.Piece("downloads", "/a", 1, 1), base[1]]),
              un._fingerprint([un.Piece("programs", "/c", 1, 1), base[1]]), un._fingerprint([un.Piece("programs", "/a", 9, 1), base[1]]), un._fingerprint([un.Piece("programs", "/a", 1, 9), base[1]])}
    assert len(prints) == 7 and un._fingerprint(list(base)) == un._fingerprint(base)


# ---------------------------------------------------------------- a removal

def test_a_removal_takes_the_programs_and_the_downloads_and_nothing_that_is_kept(rig):
    keep_things(rig)
    kept = {name: tree(folder) for name, folder in (("projects", rig.home.projects), ("backups", rig.home.backups), ("state", rig.home.state), ("voices", rig.home.voices))}
    plan = make(rig)
    result = un.remove(rig.home, [rig.spec], plan)
    assert result.failed == () and result.removed == plan.pieces and result.bytes == plan.total_bytes
    assert not os.path.exists(rig.env.env_dir) and not os.path.exists(rig.home.downloads + "/models") and not os.path.exists(rig.home.environments)
    assert {name: tree(folder) for name, folder in (("projects", rig.home.projects), ("backups", rig.home.backups), ("state", rig.home.state), ("voices", rig.home.voices))} == kept
    assert rig.voice_path().read_bytes() == VOICE_BYTES


def test_with_no_starting_voice_the_emptied_folders_go_too(tmp_path):
    rig = RefreshRig(tmp_path, voice=False)
    shutil.rmtree(rig.home.voices, ignore_errors=True)
    un.remove(rig.home, [rig.spec], make(rig))
    assert not os.path.exists(rig.home.tool) and os.path.isdir(rig.home.state)


def test_a_folder_with_something_left_in_it_is_not_removed(rig):
    Path(rig.home.environments, "somebody-elses").mkdir()
    un.remove(rig.home, [rig.spec], make(rig))
    assert Path(rig.home.environments, "somebody-elses").is_dir() and not os.path.exists(rig.env.env_dir)


def test_every_piece_removed_is_in_the_part_of_the_data_folder_the_areas_list_calls_the_tools_own(rig):
    plan = make(rig)
    assert plan.pieces
    for piece in plan.pieces:
        area = areas.home_area(areas.first_part(rig.home.root, piece.path))
        assert area is not None and area.kind is Kind.TOOL and not area.backed_up, piece.path
    for kept in (rig.home.projects, rig.home.backups, rig.home.state):
        assert areas.home_area(areas.first_part(rig.home.root, kept)).kind is not Kind.TOOL


def test_a_piece_that_cannot_be_removed_is_reported_and_the_others_still_go(rig):
    plan = make(rig)
    refused = rig.env.env_dir

    def remove_tree(path, failed):
        if path == refused:
            failed.append((path, "Permission denied"))
            return
        shutil.rmtree(path)
    result = un.remove(rig.home, [rig.spec], plan, remove_tree)
    assert result.failed == ((refused, "Permission denied"),) and [p.kind for p in result.removed] == ["downloads"] and os.path.isdir(refused)
    assert result.bytes == plan.pieces[1].bytes and os.path.isdir(rig.home.environments)


def test_a_piece_that_is_still_there_after_the_remover_says_nothing_is_not_counted_as_removed(rig):
    result = un.remove(rig.home, [rig.spec], make(rig), lambda path, failed: None)
    assert result.removed == () and result.failed == () and os.path.isdir(rig.env.env_dir)


def test_a_piece_outside_the_tools_own_places_is_never_removed_even_if_the_plan_says_so(rig, monkeypatch):
    keep_things(rig)
    in_projects = rig.home.projects + "/anna"
    for path in (in_projects, rig.home.backups + "/anna.tar", rig.home.voices, rig.home.state, rig.home.tool + "/downloads", rig.home.downloads + "/models/a.bin", "/"):
        crafted = un.Plan((un.Piece("downloads", path, 1, 1),), 0, 0, (), "", un._fingerprint([un.Piece("downloads", path, 1, 1)]))
        monkeypatch.setattr(un, "plan", lambda home, specs, crafted=crafted: crafted)
        before = tree(rig.home.root)
        result = un.remove(rig.home, [rig.spec], crafted)
        assert result.removed == () and result.failed == ((path, "it is not in the tool's own folder"),) and tree(rig.home.root) == before, path


def test_the_starting_voices_folder_is_never_a_piece_even_when_named_by_a_plan(rig, monkeypatch):
    piece = un.Piece("downloads", rig.home.downloads + "/" + un.KEPT_VOICES, 1, 1)
    crafted = un.Plan((piece,), 0, 0, (), "", un._fingerprint([piece]))
    monkeypatch.setattr(un, "plan", lambda home, specs: crafted)
    assert un.remove(rig.home, [rig.spec], crafted).failed and rig.voice_path().read_bytes() == VOICE_BYTES


def test_the_remover_used_when_none_is_given_is_the_one_that_unlinks_a_link_and_does_not_follow_it():
    from voice_studio.core import profiles
    assert un.remove.__defaults__[0] is profiles.remove_tree


# ---------------------------------------------------------------- what a mutation run found untested

def add_copy(rig, prefix, where=None):
    """A second, whole copy of the programs this tool made: the record says the fingerprint the name says."""
    folder = Path(where or rig.home.environments, "demo-" + prefix)
    shutil.copytree(rig.env.env_dir, folder, symlinks=True)
    record = json.loads((folder / eb.RECORD_NAME).read_text())
    record["fingerprint"] = prefix + record["fingerprint"][10:]
    (folder / eb.RECORD_NAME).write_text(json.dumps(record))
    return folder.as_posix()


def test_the_kinds_are_exactly_the_kinds_a_plan_uses(rig):
    assert un.KINDS == ("programs", "downloads") and {p.kind for p in make(rig).pieces} == set(un.KINDS)


def test_a_file_with_the_name_of_a_copy_of_the_programs_is_left_alone(rig):
    Path(rig.home.environments, "demo-0123456789").write_text("a file")
    plan = make(rig)
    assert plan.left_alone == 1 and [p.path for p in plan.pieces if p.kind == "programs"] == [rig.env.env_dir]
    un.remove(rig.home, [rig.spec], plan)
    assert Path(rig.home.environments, "demo-0123456789").read_text() == "a file"


def test_a_link_to_a_whole_copy_with_the_right_name_is_still_left_alone_and_the_copy_is_not_touched(rig, tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    target = add_copy(rig, "0123456789", where=outside)
    os.symlink(target, Path(rig.home.environments, "demo-0123456789"))
    plan = make(rig)
    assert plan.left_alone == 1 and [p.path for p in plan.pieces if p.kind == "programs"] == [rig.env.env_dir]
    un.remove(rig.home, [rig.spec], plan)
    assert os.path.islink(Path(rig.home.environments, "demo-0123456789")) and os.path.isdir(target) and (Path(target) / eb.RECORD_NAME).is_file()


def test_the_limit_on_how_many_programs_are_listed_counts_exactly(rig, monkeypatch):
    first, second = add_copy(rig, "0000000001"), add_copy(rig, "0000000002")           # these sort before the one in use
    monkeypatch.setattr(un, "MAX_ENTRIES", 2)
    plan = make(rig)
    assert [p.path for p in plan.pieces if p.kind == "programs"] == [first, second] and plan.left_alone == 1
    monkeypatch.setattr(un, "MAX_ENTRIES", 3)
    plan = make(rig)
    assert [p.path for p in plan.pieces if p.kind == "programs"] == [first, second, rig.env.env_dir] and plan.left_alone == 0
    monkeypatch.setattr(un, "MAX_ENTRIES", 1)
    plan = make(rig)
    assert [p.path for p in plan.pieces if p.kind == "programs"] == [first] and plan.left_alone == 2 + 1, "two programs folders beyond the limit, and the voices folder beyond it in the downloads"


def test_the_limit_on_how_many_downloads_are_listed_counts_exactly(rig, monkeypatch):
    for name in ("a", "b"):
        Path(rig.home.downloads, name).write_text("x")                                  # in order: a, b, models, voices
    for limit, listed, left in ((4, 3, 0), (3, 3, 1), (2, 2, 2), (1, 1, 3)):
        monkeypatch.setattr(un, "MAX_ENTRIES", limit)
        plan = make(rig)
        assert (len([p for p in plan.pieces if p.kind == "downloads"]), plan.left_alone) == (listed, left), limit


def test_the_areas_list_decides_what_is_the_tools_own_and_a_place_it_calls_precious_is_never_removed(rig, monkeypatch):
    plan = make(rig)
    monkeypatch.setattr(areas, "HOME_AREAS", tuple(replace(a, kind=Kind.PRECIOUS) if a.id == "tool" else a for a in areas.HOME_AREAS))
    before = tree(rig.home.root)
    result = un.remove(rig.home, [rig.spec], plan)
    assert result.removed == () and len(result.failed) == 2 and tree(rig.home.root) == before


def test_a_piece_that_is_reported_as_failed_is_not_counted_as_removed_even_if_it_is_gone(rig):
    plan = make(rig)

    def remove_tree(path, failed):
        shutil.rmtree(path)
        failed.append((path, "could not be flushed"))
    result = un.remove(rig.home, [rig.spec], plan, remove_tree)
    assert result.removed == () and len(result.failed) == 2


def test_two_different_lists_never_share_a_fingerprint_even_when_a_path_imitates_the_separators():
    one = [un.Piece("programs", "/a", 1, 1), un.Piece("downloads", "/b", 2, 2)]
    imitation = [un.Piece("programs", "/a|1|1downloads|/b", 2, 2)]
    assert un._fingerprint(one) != un._fingerprint(imitation)
