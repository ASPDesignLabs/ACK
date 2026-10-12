# SPDX-License-Identifier: GPL-3.0-or-later
"""Managing profiles (plan task VS-2.10): details that are changed only when the form is whole, a flag that puts a profile away without touching a file, and a delete that is worked out first,
refuses when anything changed, never follows a link out of the profile's folder, and removes `project.json` last."""
import json
import os
import stat
from dataclasses import replace

import pytest

from voice_studio.core import jobs, profiles as pf, project as pj
from voice_studio.core.paths import DataHome, ProjectPaths
from voice_studio.core.project import Consent, OWN, SOMEONE_ELSE, Project, ProjectError, Scratch
from voice_studio.core.scratch import MARKER_NAME, create_scratch

from vs_rounds_helpers import fake_job

FULL = Consent("Anna's mother", "recording Anna's voice", "9 Oct 2026", "tell me and we delete it", "spoken")


@pytest.fixture
def home(tmp_path):
    return DataHome(str(tmp_path))


def make(home, name="Anna", whose=OWN, consent=None):
    project = pj.create_project(home.projects, name, whose, consent)
    return project, ProjectPaths(home.projects + "/" + project.id)


def put(path, size=10):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as handle:
        handle.write(b"x" * size)
    return path


# ---------------------------------------------------------------- the archived flag

def test_a_profile_that_was_never_put_away_keeps_exactly_the_same_file(home):
    project, paths = make(home)
    before = open(paths.project_json, "rb").read()
    pj.save_project(paths, project)
    assert open(paths.project_json, "rb").read() == before and b"archived" not in before


def test_putting_a_profile_away_writes_one_flag_and_bringing_it_back_removes_it(home):
    project, paths = make(home)
    away = pj.with_archived(project, True)
    pj.save_project(paths, away)
    assert json.load(open(paths.project_json))["archived"] is True and pj.load_project(paths).archived is True
    pj.save_project(paths, pj.with_archived(away, False))
    assert "archived" not in json.load(open(paths.project_json)) and pj.load_project(paths).archived is False


@pytest.mark.parametrize("bad", ["yes", 1, 0, None, [], {}])
def test_a_flag_that_is_not_true_or_false_is_a_damaged_file_not_a_guess(home, bad):
    project, paths = make(home)
    data = json.load(open(paths.project_json))
    data["archived"] = bad
    open(paths.project_json, "w").write(json.dumps(data))
    with pytest.raises(ProjectError) as caught:
        pj.load_project(paths)
    assert caught.value.code == "damaged"


def test_fields_a_newer_version_wrote_survive_putting_a_profile_away(home):
    project, paths = make(home)
    data = json.load(open(paths.project_json))
    data["future_field"] = {"a": 1}
    open(paths.project_json, "w").write(json.dumps(data))
    loaded = pj.load_project(paths)
    pj.save_project(paths, pj.with_archived(loaded, True))
    assert json.load(open(paths.project_json))["future_field"] == {"a": 1}


def test_the_lists_split_into_in_use_and_put_away_in_the_order_given():
    a = Project("a", "A", OWN, "t")
    b = replace(Project("b", "B", OWN, "t"), archived=True)
    c = Project("c", "C", OWN, "t")
    assert pf.split([a, b, c]) == ((a, c), (b,))


# ---------------------------------------------------------------- changing details

def edit(project, **over):
    base = dict(name=project.name, hours="%g" % project.planned_hours, consent=project.consent)
    base.update(over)
    return pf.evaluate_edit(project, pf.EditInput(**base))


def test_a_form_nobody_touched_has_nothing_to_save(home):
    project, _ = make(home)
    state = edit(project)
    assert state.problems == () and state.changes == () and not state.can_save and state.project == project


def test_a_new_name_and_hours_are_a_change_listed_before_anything_is_saved(home):
    project, _ = make(home)
    state = edit(project, name="  Anna   B\n", hours="2,5")
    assert state.can_save and state.project.name == "Anna B" and state.project.planned_hours == 2.5 and state.project.id == project.id
    assert state.changes == (pf.Change("name", "Anna", "Anna B"), pf.Change("hours", "1", "2.5"))


def test_every_problem_is_found_at_once_and_nothing_typed_is_cut(home):
    project, _ = make(home)
    state = edit(project, name="x" * 81, hours="lots")
    assert state.project is None and not state.can_save
    assert {(p.field, p.code) for p in state.problems} == {("name", "too_long"), ("hours", "not_a_number")}
    assert edit(project, name="   ").problems[0] == pf.Problem("name", "blank")
    assert {(p.field, p.code) for p in edit(project, hours="0").problems} == {("hours", "too_small")} and {(p.field, p.code) for p in edit(project, hours="101").problems} == {("hours", "too_big")}


def test_a_note_over_its_limit_is_refused_not_shortened(home):
    project, _ = make(home, whose=SOMEONE_ELSE, consent=FULL)
    state = edit(project, consent=replace(FULL, what_to="y" * (pj.MAX_NOTE + 1)))
    assert state.project is None and [(p.field, p.code) for p in state.problems] == [("consent.what_to", "too_long")]
    assert edit(project, consent=replace(FULL, what_to="y" * pj.MAX_NOTE)).can_save


def test_someone_elses_note_can_be_changed_but_never_made_incomplete(home):
    project, _ = make(home, whose=SOMEONE_ELSE, consent=FULL)
    changed = edit(project, consent=replace(FULL, withdraw="phone me"))
    assert changed.can_save and changed.changes == (pf.Change("consent.withdraw", "tell me and we delete it", "phone me"),)
    for part in ("given_by", "what_to", "when", "withdraw"):
        state = edit(project, consent=replace(FULL, **{part: "  "}))
        assert state.project is None and [(p.field, p.code) for p in state.problems] == [("consent." + part, "missing")]
    assert [(p.field, p.code) for p in edit(project, consent=replace(FULL, how_given="")).problems] == [("consent.how_given", "missing")]
    assert [(p.field, p.code) for p in edit(project, consent=replace(FULL, how_given="other")).problems] == [("consent.how_given_other", "missing")]


def test_a_persons_own_voice_may_have_an_empty_or_a_filled_note(home):
    project, _ = make(home)
    assert edit(project, consent=Consent()).problems == ()
    assert edit(project, consent=replace(FULL, how_given="")).problems == ()


def test_whose_voice_and_the_starting_voice_and_the_place_are_never_changed_by_an_edit(home):
    project, _ = make(home)
    project = replace(project, starting_voice="voice-mike", scratch=Scratch("custom", "/mnt/d"))
    state = edit(project, name="Anna B")
    assert state.project.whose_voice == OWN and state.project.starting_voice == "voice-mike" and state.project.scratch == Scratch("custom", "/mnt/d")
    assert state.project.created == project.created and state.project.acknowledgments == project.acknowledgments


def test_saving_an_edit_keeps_the_file_it_replaces(home):
    project, paths = make(home)
    old = open(paths.project_json, "rb").read()
    pj.save_project(paths, edit(project, name="Anna B").project)
    assert open(paths.previous_json, "rb").read() == old and pj.load_project(paths).name == "Anna B"


# ---------------------------------------------------------------- what a delete would remove

def fill(paths, voice=True):
    put(paths.recordings + "/_freeform/en-US/takes/t1/raw.wav", 1000)
    put(paths.recordings + "/_freeform/en-US/takes/t1/take.json", 20)
    put(paths.rounds + "/rounds.json", 30)
    put(paths.rounds + "/run/lightning_logs/version_0/checkpoints/last.ckpt", 5000)
    put(paths.default_scratch + "/datasets/dataset-1/wav/a.wav", 700)
    if voice:
        put(paths.exports + "/anna-round-001/anna-round-001.zip", 400)
        put(paths.exports + "/anna-round-001/model.onnx", 300)


def test_the_plan_lists_every_part_with_its_size_and_removes_nothing(home):
    project, paths = make(home)
    fill(paths)
    plan = pf.plan_delete(home, project)
    kinds = {p.kind: p for p in plan.parts}
    assert set(kinds) >= {"recordings", "rounds", "exports", "scratch", "record"}
    assert kinds["recordings"].bytes == 1020 and kinds["recordings"].files == 2
    assert kinds["rounds"].bytes == 5030 and kinds["exports"].bytes == 700 and kinds["scratch"].bytes == 700
    assert plan.total_bytes == sum(p.bytes for p in plan.parts) and plan.total_files == sum(p.files for p in plan.parts)
    assert plan.voice_files == ("anna-round-001",) and plan.blocked == "" and plan.outside_scratch == "" and plan.left_scratch == ""
    assert all(p.path.startswith(paths.root + "/") for p in plan.parts)
    assert os.path.isfile(paths.project_json) and os.path.isfile(paths.recordings + "/_freeform/en-US/takes/t1/raw.wav")


def test_a_task_that_is_running_for_this_profile_blocks_it_but_another_profiles_does_not(home):
    project, _ = make(home)
    os.makedirs(home.jobs)
    fake_job(home.jobs, ["x"], "running", project="somebody-else")
    assert pf.plan_delete(home, project).blocked == ""
    fake_job(home.jobs, ["x"], "finished", project=project.id)
    assert pf.plan_delete(home, project).blocked == ""
    fake_job(home.jobs, ["x"], "running", project=project.id)
    assert pf.plan_delete(home, project).blocked == "job_running"


@pytest.mark.parametrize("status", ["starting", "running", "stopping"])
def test_a_task_that_is_starting_or_stopping_also_blocks_it(home, status):
    project, _ = make(home)
    os.makedirs(home.jobs)
    fake_job(home.jobs, ["x"], status, project=project.id)
    assert pf.plan_delete(home, project).blocked == "job_running"


def test_a_folder_that_is_a_link_or_has_no_project_file_is_not_planned(home, tmp_path):
    project, paths = make(home)
    os.unlink(paths.project_json)
    with pytest.raises(pf.ProfileError) as caught:
        pf.plan_delete(home, project)
    assert caught.value.code == "unsafe"
    other = tmp_path / "elsewhere"
    other.mkdir()
    (other / "project.json").write_text("{}")
    linked = replace(project, id="linked")
    os.symlink(str(other), home.projects + "/linked")
    with pytest.raises(pf.ProfileError) as caught:
        pf.plan_delete(home, linked)
    assert caught.value.code == "unsafe" and (other / "project.json").exists()


def test_a_project_whose_id_climbs_out_of_the_projects_folder_is_never_planned_or_deleted(home):
    project, paths = make(home)
    victim = os.path.dirname(home.projects) + "/victim"
    put(victim + "/project.json", 20)
    put(victim + "/precious.wav", 50)
    sneaky = replace(project, id="../victim")
    with pytest.raises(pf.ProfileError) as caught:
        pf.plan_delete(home, sneaky)
    assert caught.value.code == "unsafe"
    with pytest.raises(pf.ProfileError) as caught:
        pf.delete_project(home, sneaky, pf.plan_delete(home, project))
    assert caught.value.code == "unsafe" and os.path.isfile(victim + "/precious.wav") and os.path.isfile(victim + "/project.json") and os.path.isfile(paths.project_json)


def test_a_link_inside_the_profile_is_counted_as_a_link_and_its_target_is_not_walked(home, tmp_path):
    project, paths = make(home)
    big = tmp_path / "big"
    put(str(big / "a.wav"), 9999)
    os.rmdir(paths.recordings)
    os.symlink(str(big), paths.recordings)
    plan = pf.plan_delete(home, project)
    part = [p for p in plan.parts if p.kind == "recordings"][0]
    assert part.bytes == 0 and part.files == 1


def test_a_scratch_folder_on_another_drive_goes_only_if_its_marker_names_this_profile(home, tmp_path):
    project, paths = make(home)
    place = tmp_path / "bigdisk"
    place.mkdir()
    folder = create_scratch(str(place), project.id)
    put(folder + "/datasets/d1/wav/a.wav", 600)
    mine = pj.with_scratch_place(project, str(place))
    plan = pf.plan_delete(home, mine)
    assert plan.outside_scratch == folder and plan.left_scratch == "" and any(p.path == folder and p.bytes >= 600 for p in plan.parts)
    open(folder + "/" + MARKER_NAME, "w").write(json.dumps({"schema": 1, "project": "someone-else"}) + "\n")
    plan = pf.plan_delete(home, mine)
    assert plan.outside_scratch == "" and plan.left_scratch == folder and not any(p.path == folder for p in plan.parts)
    os.unlink(folder + "/" + MARKER_NAME)
    assert pf.plan_delete(home, mine).left_scratch == folder


# ---------------------------------------------------------------- deleting

def test_a_delete_removes_the_profile_and_only_the_profile(home):
    project, paths = make(home)
    other, other_paths = make(home, "Ben")
    fill(paths)
    fill(other_paths)
    plan = pf.plan_delete(home, project)
    result = pf.delete_project(home, project, plan)
    assert result.gone and result.failed == () and result.bytes == plan.total_bytes and result.files == plan.total_files
    assert not os.path.lexists(paths.root) and os.path.isfile(other_paths.project_json) and os.path.isfile(other_paths.rounds + "/rounds.json")
    assert [p.id for p in pj.list_projects(home.projects).projects] == ["ben"]


def test_the_scratch_folder_made_for_this_profile_goes_with_it_and_the_place_itself_stays(home, tmp_path):
    project, paths = make(home)
    place = tmp_path / "bigdisk"
    place.mkdir()
    folder = create_scratch(str(place), project.id)
    put(folder + "/caches/c1/x", 50)
    mine = pj.with_scratch_place(project, str(place))
    pj.save_project(paths, mine)
    result = pf.delete_project(home, mine, pf.plan_delete(home, mine))
    assert result.gone and not os.path.exists(folder) and place.is_dir() and not os.path.exists(paths.root)


def test_if_anything_changed_since_the_plan_nothing_is_removed(home):
    project, paths = make(home)
    fill(paths)
    plan = pf.plan_delete(home, project)
    put(paths.recordings + "/_freeform/en-US/takes/t2/raw.wav", 5)
    with pytest.raises(pf.ProfileError) as caught:
        pf.delete_project(home, project, plan)
    assert caught.value.code == "changed" and os.path.isfile(paths.project_json) and os.path.isfile(paths.recordings + "/_freeform/en-US/takes/t1/raw.wav")


def test_a_task_that_started_since_the_plan_stops_the_delete(home):
    project, paths = make(home)
    fill(paths)
    plan = pf.plan_delete(home, project)
    os.makedirs(home.jobs, exist_ok=True)
    fake_job(home.jobs, ["x"], "running", project=project.id)
    with pytest.raises(pf.ProfileError) as caught:
        pf.delete_project(home, project, plan)
    assert caught.value.code == "job_running" and os.path.isfile(paths.rounds + "/rounds.json")


def test_a_plan_made_for_another_profile_cannot_be_used(home):
    first, first_paths = make(home)
    second, second_paths = make(home, "Ben")
    fill(first_paths)
    fill(second_paths)
    with pytest.raises(pf.ProfileError) as caught:
        pf.delete_project(home, second, pf.plan_delete(home, first))
    assert caught.value.code == "changed" and os.path.isfile(second_paths.project_json) and os.path.isfile(first_paths.project_json)


def test_a_link_inside_the_profile_is_removed_as_a_link_and_what_it_pointed_at_is_left(home, tmp_path):
    project, paths = make(home)
    big = tmp_path / "big"
    put(str(big / "a.wav"), 123)
    os.rmdir(paths.recordings)
    os.symlink(str(big), paths.recordings)
    result = pf.delete_project(home, project, pf.plan_delete(home, project))
    assert result.gone and (big / "a.wav").read_bytes() == b"x" * 123 and not os.path.lexists(paths.root)


def test_project_json_is_removed_last_so_a_failed_delete_leaves_a_profile_that_is_still_listed(home, monkeypatch):
    project, paths = make(home)
    fill(paths)
    real = pf._remove_tree

    def breaks_on_rounds(path, failed):
        if path == paths.rounds:
            failed.append((path, "Device or resource busy"))
            return
        real(path, failed)
    monkeypatch.setattr(pf, "_remove_tree", breaks_on_rounds)
    result = pf.delete_project(home, project, pf.plan_delete(home, project))
    assert not result.gone and result.failed == ((paths.rounds, "Device or resource busy"),)
    assert os.path.isfile(paths.project_json) and [p.id for p in pj.list_projects(home.projects).projects] == [project.id]
    monkeypatch.setattr(pf, "_remove_tree", real)
    again = pf.delete_project(home, project, pf.plan_delete(home, project))
    assert again.gone and again.failed == () and not os.path.lexists(paths.root)


def test_a_part_that_cannot_be_removed_stops_the_delete_before_the_parts_after_it(home, monkeypatch):
    project, paths = make(home)
    fill(paths)
    real = pf._remove_tree

    def breaks_on_recordings(path, failed):
        if path == paths.recordings:
            failed.append((path, "Device or resource busy"))
            return
        real(path, failed)
    monkeypatch.setattr(pf, "_remove_tree", breaks_on_recordings)
    result = pf.delete_project(home, project, pf.plan_delete(home, project))
    assert not result.gone and result.failed == ((paths.recordings, "Device or resource busy"),)
    assert os.path.isfile(paths.rounds_file) and os.path.isfile(paths.project_json), "nothing after the part that failed was touched, and the project file is still there"


def test_a_file_that_no_longer_exists_when_the_delete_reaches_it_is_not_an_error(home):
    project, paths = make(home)
    fill(paths)
    plan = pf.plan_delete(home, project)
    result = pf.delete_project(home, project, plan)
    assert result.gone
    with pytest.raises(pf.ProfileError) as caught:
        pf.delete_project(home, project, plan)
    assert caught.value.code == "unsafe"                       # the folder is gone: there is nothing left to delete, and nothing is touched


def test_an_unreadable_entry_makes_the_delete_stop_before_project_json_and_say_which(home):
    if os.getuid() == 0:
        pytest.skip("root can remove anything, so a folder cannot be made unremovable")
    project, paths = make(home)
    fill(paths)
    os.chmod(paths.rounds, stat.S_IRUSR | stat.S_IXUSR)
    try:
        result = pf.delete_project(home, project, pf.plan_delete(home, project))
    finally:
        os.chmod(paths.rounds, stat.S_IRWXU)
    assert not result.gone and result.failed and os.path.isfile(paths.project_json)


def test_the_parts_are_added_together_by_kind_in_the_order_the_screens_show_them(home):
    project, paths = make(home)
    fill(paths)
    pj.save_project(paths, project)                                      # a second save leaves project.json.previous beside project.json
    plan = pf.plan_delete(home, project)
    kinds = [k for k, _b, _f in plan.by_kind]
    assert kinds == ["recordings", "rounds", "exports", "scratch", "record"] and len(kinds) == len(set(kinds))
    record = dict((k, (b, f)) for k, b, f in plan.by_kind)["record"]
    assert record[1] == 2 and sum(b for _k, b, _f in plan.by_kind) == plan.total_bytes and sum(f for _k, _b, f in plan.by_kind) == plan.total_files
