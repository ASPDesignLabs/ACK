# SPDX-License-Identifier: GPL-3.0-or-later
"""The list of what the tool keeps (plan P11, task VS-6.3's catalogue): every path the tool names is in an area, and the areas agree with the rules the rest of the tool already keeps."""
import dataclasses

import pytest

from voice_studio.core import areas, profiles
from voice_studio.core.diskbudget import Kind
from voice_studio.core.paths import DataHome, ProjectPaths, ScratchPaths


def properties_of(cls):
    return sorted(name for name in dir(cls) if isinstance(getattr(cls, name), property))


def test_every_path_a_project_names_is_in_an_area_and_a_new_one_fails_here():
    paths = ProjectPaths("/p/projects/anna")
    unclaimed = []
    for name in properties_of(ProjectPaths):
        value = getattr(paths, name)
        if isinstance(value, str) and value.startswith(paths.root + "/"):
            if areas.project_area(areas.first_part(paths.root, value)) is None:
                unclaimed.append(name)
        elif isinstance(value, tuple):
            for item in value:
                if areas.project_area(areas.first_part(paths.root, item)) is None:
                    unclaimed.append(name)
    assert unclaimed == [], "a path of a project is in no area; decide how it is backed up and removed, then add it to core/areas.py: %s" % unclaimed


def test_the_project_file_itself_is_in_the_record_area():
    paths = ProjectPaths("/p/projects/anna")
    for path in (paths.project_json, paths.previous_json):
        assert areas.project_area(areas.first_part(paths.root, path)).id == "record"


def test_every_path_the_data_home_names_is_in_an_area_and_a_new_one_fails_here():
    home = DataHome("/h")
    unclaimed = [name for name in properties_of(DataHome) if name not in ("root",)
                 and areas.home_area(areas.first_part(home.root, getattr(home, name))) is None]
    assert unclaimed == [], "a place of the tool is in no area; decide how it is backed up and removed, then add it to core/areas.py: %s" % unclaimed


def test_every_name_belongs_to_one_area_only():
    for table in (areas.PROJECT_AREAS, areas.HOME_AREAS):
        names = [e for a in table for e in a.entries]
        assert len(names) == len(set(names)) and len({a.id for a in table}) == len(table)


def test_the_folders_a_project_is_made_with_are_all_claimed():
    paths = ProjectPaths("/p/projects/anna")
    for folder in paths.folders:
        assert areas.project_area(areas.first_part(paths.root, folder)) is not None, folder


def test_what_the_budget_calls_precious_is_what_a_backup_holds_and_nothing_else_is():
    for area in areas.PROJECT_AREAS:
        assert area.backed_up == (area.kind is Kind.PRECIOUS), area.id


def test_scratch_is_rebuildable_and_listening_is_disposable_as_the_disk_budget_says():
    kinds = {a.id: a.kind for a in areas.PROJECT_AREAS}
    assert kinds["scratch"] is Kind.REBUILDABLE and kinds["listening"] is Kind.DISPOSABLE
    assert kinds["recordings"] is kinds["rounds"] is kinds["exports"] is kinds["record"] is Kind.PRECIOUS


def test_backups_are_precious_and_never_inside_a_backup():
    backups = areas.home_area("backups")
    assert backups.kind is Kind.PRECIOUS and not backups.backed_up
    assert areas.home_area("projects").backed_up


def test_the_tools_own_places_are_not_backed_up():
    for name in ("tool", "state"):
        assert not areas.home_area(name).backed_up


def test_an_unknown_name_is_in_no_area():
    assert areas.project_area("notes.txt") is None and areas.home_area("notes") is None and areas.project_area("") is None


def test_first_part_reads_only_text():
    assert areas.first_part("/a/b", "/a/b/c/d") == "c" and areas.first_part("/a/b/", "/a/b/c") == "c" and areas.first_part("/a/b", "/a/bc/d") == ""
    assert areas.first_part("/a/b", "/a/b") == "" and areas.first_part("/a/b", "/x/y") == ""


def test_the_delete_plan_names_each_part_by_its_area(tmp_path):
    from voice_studio.core.project import create_project
    home = DataHome(str(tmp_path / "home"))
    project = create_project(home.projects, "Anna", "own")
    paths = ProjectPaths(home.projects + "/" + project.id)
    import os
    for name in ("recordings", "rounds", "exports", "listening", "scratch"):
        os.makedirs("%s/%s" % (paths.root, name), exist_ok=True)
        with open("%s/%s/x" % (paths.root, name), "w") as handle:
            handle.write("x")
    with open(paths.root + "/notes.txt", "w") as handle:
        handle.write("mine")
    plan = profiles.plan_delete(home, project)
    kinds = {p.path.rsplit("/", 1)[1]: p.kind for p in plan.parts}
    assert kinds == {"recordings": "recordings", "rounds": "rounds", "exports": "exports", "listening": "listening", "scratch": "scratch", "project.json": "record", "notes.txt": "other"}
