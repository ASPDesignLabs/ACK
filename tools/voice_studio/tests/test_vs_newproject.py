# SPDX-License-Identifier: GPL-3.0-or-later
"""The new-project form (plan task VS-2.3): everything wrong with it is said at once, nothing a person typed is silently cut, and a bad scratch place never costs the project."""
import os
import stat
from datetime import datetime, timezone
from pathlib import Path

import pytest

from voice_studio.core import newproject as np
from voice_studio.core import scratch as sc
from voice_studio.core.diskbudget import DEFAULT_TABLE, GIB, Role, person_lines
from voice_studio.core.project import (MAX_NAME, MAX_NOTE, OWN, SOMEONE_ELSE, Consent, ProjectError, ProjectPaths, load_project)

NOW = datetime(2026, 10, 10, 12, 0, tzinfo=timezone.utc)
GOOD_CONSENT = Consent("Her mother", "recording and training a voice", "1 October 2026", "just tell me and everything is deleted", "spoken")
MOUNTS = "/dev/sda1 / ext4 rw,relatime 0 0\n"


def codes(state):
    return [(p.field, p.code) for p in state.problems]


def form(**over):
    base = dict(name="Anna", whose_voice=OWN, hours="2")
    base.update(over)
    return np.FormInput(**base)


def place_facts(place, project_id, **over):
    base = dict(given=str(place), real=str(place), project_id=project_id, project_root="/somewhere/else/" + project_id, home="/home/user", exists=True, is_dir=True,
                writable=True, parent_is_dir=True, parent_writable=True, device=2, project_device=1, mounts_text=MOUNTS)
    base.update(over)
    return sc.PlaceFacts(**base)


# ---------------------------------------------------------------- the hours

@pytest.mark.parametrize("text, value, why", [
    ("1", 1.0, None), ("2.5", 2.5, None), ("1,5", 1.5, None), ("0.5", 0.5, None), ("100", 100.0, None), ("  3  ", 3.0, None), ("1e1", 10.0, None), ("٣", 3.0, None),
    ("0.49", None, "too_small"), ("0", None, "too_small"), ("-2", None, "too_small"), ("100.01", None, "too_big"), ("1e3", None, "too_big"),
    ("", None, "blank"), ("   ", None, "blank"), (None, None, "blank"),
    ("abc", None, "not_a_number"), ("1,000.5", None, "not_a_number"), ("1,5,5", None, "not_a_number"), ("nan", None, "not_a_number"), ("inf", None, "not_a_number"),
    ("-inf", None, "not_a_number"), ("1 hour", None, "not_a_number"), ("0x10", None, "not_a_number"), ("1,", 1.0, None),
])
def test_the_hours_are_read_the_way_a_person_writes_them_and_the_edges_are_exact(text, value, why):
    assert np.parse_hours(text) == (value, why)


def test_the_limits_are_the_projects_own():
    from voice_studio.core.project import MAX_HOURS, MIN_HOURS
    assert np.parse_hours(repr(MIN_HOURS))[0] == MIN_HOURS and np.parse_hours(repr(MIN_HOURS - 0.001))[1] == "too_small"
    assert np.parse_hours(repr(MAX_HOURS))[0] == MAX_HOURS and np.parse_hours(repr(MAX_HOURS + 0.001))[1] == "too_big"


# ---------------------------------------------------------------- the name

def test_a_good_form_has_no_problems_and_can_be_created():
    state = np.evaluate(form())
    assert state.problems == () and state.can_create and state.clean_name == "Anna" and state.project_id == "anna" and state.hours == 2.0


@pytest.mark.parametrize("name", ["", "   ", "\n\t ", "\x00\x07"])
def test_a_name_with_nothing_in_it_is_a_problem(name):
    assert codes(np.evaluate(form(name=name))) == [("name", "blank")]


def test_a_name_may_be_exactly_as_long_as_the_limit_and_one_more_is_a_problem_never_cut():
    assert np.evaluate(form(name="a" * MAX_NAME)).problems == ()
    state = np.evaluate(form(name="a" * (MAX_NAME + 1)))
    assert codes(state) == [("name", "too_long")] and state.problems[0].detail == str(MAX_NAME) and not state.can_create


def test_a_name_is_tidied_like_the_project_will_store_it():
    state = np.evaluate(form(name="  Anna \n  Maria\t\u0085Lopez  "))
    assert state.clean_name == "Anna Maria Lopez" and state.project_id == "anna-maria-lopez"


@pytest.mark.parametrize("name, expected_id", [("अनिल", "person"), ("محمد", "person"), ("Zoë Åström", "zoe-astrom"), ("A/B\\C..D", "a-b-c-d")])
def test_names_in_any_writing_are_allowed_and_get_a_safe_folder_name(name, expected_id):
    state = np.evaluate(form(name=name))
    assert state.problems == () and state.project_id == expected_id and state.clean_name == name.strip()


def test_a_zero_width_joiner_in_a_name_is_kept():
    name = "क्‍ष"
    assert np.evaluate(form(name=name)).clean_name == name


def test_a_second_person_with_the_same_name_gets_a_numbered_folder():
    assert np.evaluate(form(), taken_ids=["anna"]).project_id == "anna-2"
    assert np.evaluate(form(), taken_ids=["anna", "anna-2"]).project_id == "anna-3"


def test_an_absurdly_long_paste_is_a_problem_and_nothing_slow_happens():
    state = np.evaluate(form(name="x" * 5_000_000))
    assert codes(state) == [("name", "too_long")] and len(state.project_id) <= 64


# ---------------------------------------------------------------- whose voice and the consent note

@pytest.mark.parametrize("value", ["", "mine", "OWN", None])
def test_whose_voice_must_be_chosen(value):
    assert ("whose_voice", "missing") in codes(np.evaluate(form(whose_voice=value)))


def test_for_ones_own_voice_the_note_is_optional_and_a_filled_one_is_not_judged():
    assert np.evaluate(form()).problems == ()
    assert np.evaluate(form(consent=Consent(how_given="other"))).problems == ()


def test_for_someone_elses_voice_everything_missing_is_listed_together():
    state = np.evaluate(form(whose_voice=SOMEONE_ELSE))
    assert codes(state) == [("consent.given_by", "missing"), ("consent.what_to", "missing"), ("consent.when", "missing"), ("consent.withdraw", "missing"),
                            ("consent.how_given", "missing")]


def test_a_complete_note_for_someone_else_passes_and_a_note_of_spaces_does_not():
    assert np.evaluate(form(whose_voice=SOMEONE_ELSE, consent=GOOD_CONSENT)).problems == ()
    blank = Consent("   ", "\n", "\t", " ", "spoken")
    assert [c for c in codes(np.evaluate(form(whose_voice=SOMEONE_ELSE, consent=blank)))] == [("consent.given_by", "missing"), ("consent.what_to", "missing"),
                                                                                              ("consent.when", "missing"), ("consent.withdraw", "missing")]


def test_how_it_was_given_other_needs_words_and_an_unknown_way_is_missing():
    other = Consent(**{**GOOD_CONSENT.__dict__, "how_given": "other"})
    assert codes(np.evaluate(form(whose_voice=SOMEONE_ELSE, consent=other))) == [("consent.how_given_other", "missing")]
    assert np.evaluate(form(whose_voice=SOMEONE_ELSE, consent=Consent(**{**other.__dict__, "how_given_other": "she nodded"}))).problems == ()
    assert codes(np.evaluate(form(whose_voice=SOMEONE_ELSE, consent=Consent(**{**GOOD_CONSENT.__dict__, "how_given": "telepathy"})))) == [("consent.how_given", "missing")]


@pytest.mark.parametrize("name", np.CONSENT_TEXT_FIELDS)
def test_a_note_field_may_be_exactly_the_limit_and_one_more_is_a_problem_never_cut(name):
    base = dict(GOOD_CONSENT.__dict__, how_given="other", how_given_other="nodded")
    ok = np.evaluate(form(whose_voice=SOMEONE_ELSE, consent=Consent(**{**base, name: "x" * MAX_NOTE})))
    assert ok.problems == ()
    long = np.evaluate(form(whose_voice=SOMEONE_ELSE, consent=Consent(**{**base, name: "x" * (MAX_NOTE + 1)})))
    assert codes(long) == [("consent." + name, "too_long")] and long.problems[0].detail == str(MAX_NOTE)


def test_a_long_note_for_ones_own_voice_is_also_not_cut_silently():
    long = Consent(given_by="y" * (MAX_NOTE + 1))
    assert codes(np.evaluate(form(consent=long))) == [("consent.given_by", "too_long")]


# ---------------------------------------------------------------- everything at once, in a steady order

def test_every_problem_is_reported_together_in_the_order_of_the_form():
    state = np.evaluate(form(name="", whose_voice="", hours="abc", starting_voice="nobody", scratch_place="/data"), voice_ids=["voice-mike"])
    assert codes(state) == [("name", "blank"), ("whose_voice", "missing"), ("hours", "not_a_number"), ("starting_voice", "unknown"), ("scratch", "not_checked")]
    assert state.estimate is None and not state.can_create


def test_someone_elses_note_problems_come_after_the_choice_and_before_the_hours():
    state = np.evaluate(form(whose_voice=SOMEONE_ELSE, hours="0"))
    assert codes(state)[0] == ("consent.given_by", "missing") and codes(state)[-1] == ("hours", "too_small")


# ---------------------------------------------------------------- the starting voice

def test_a_starting_voice_may_be_left_for_later_or_be_a_listed_one_and_nothing_else():
    voices = ["voice-mike", "voice-amy"]
    assert np.evaluate(form(starting_voice=None), voice_ids=voices).problems == ()
    assert np.evaluate(form(starting_voice="voice-amy"), voice_ids=voices).problems == ()
    state = np.evaluate(form(starting_voice="../../etc/passwd" + "x" * 200), voice_ids=voices)
    assert codes(state) == [("starting_voice", "unknown")] and len(state.problems[0].detail) <= 80
    assert codes(np.evaluate(form(starting_voice="voice-amy"))) == [("starting_voice", "unknown")], "with no voices listed, none is known"


# ---------------------------------------------------------------- scratch

def test_the_default_place_needs_no_checking_and_has_no_assessment():
    state = np.evaluate(form())
    assert state.assessment is None and state.warnings == ()


def test_a_chosen_place_counts_as_not_checked_until_its_facts_are_given_for_this_name_and_this_place(tmp_path):
    assert codes(np.evaluate(form(scratch_place=str(tmp_path)))) == [("scratch", "not_checked")]
    wrong_project = place_facts(tmp_path, "someone-else")
    assert codes(np.evaluate(form(scratch_place=str(tmp_path)), facts=wrong_project)) == [("scratch", "not_checked")]
    wrong_place = place_facts("/data", "anna")
    assert codes(np.evaluate(form(scratch_place=str(tmp_path)), facts=wrong_place)) == [("scratch", "not_checked")]


def test_a_good_place_is_accepted_and_its_assessment_is_kept(tmp_path):
    state = np.evaluate(form(scratch_place=str(tmp_path)), facts=place_facts(tmp_path, "anna"))
    assert state.problems == () and state.assessment is not None and state.assessment.scratch_dir == "%s/ack-voice-scratch/anna" % tmp_path


def test_the_facts_may_be_for_the_same_place_typed_with_stray_spaces(tmp_path):
    state = np.evaluate(form(scratch_place="  %s  " % tmp_path), facts=place_facts(tmp_path, "anna"))
    assert state.problems == ()


def test_each_reason_a_place_is_refused_becomes_a_problem_and_warnings_do_not(tmp_path):
    bad = place_facts("/usr/share", "anna", exists=True)
    state = np.evaluate(form(scratch_place="/usr/share"), facts=bad)
    assert ("scratch", "system_folder") in codes(state) and not state.can_create
    warn = place_facts(tmp_path, "anna", mounts_text="/dev/sdb1 / ntfs rw 0 0\n")
    state = np.evaluate(form(scratch_place=str(tmp_path)), facts=warn)
    assert state.problems == () and "fs_permissive" in state.warnings and state.can_create


# ---------------------------------------------------------------- the disk estimate

def test_the_estimate_is_the_plans_arithmetic_for_the_hours_typed():
    state = np.evaluate(form(hours="3"), free={"project": 500 * GIB})
    lines = person_lines(DEFAULT_TABLE, 3.0)
    est = state.estimate
    assert est.lines == tuple(lines) and est.rough
    assert est.project_bytes == sum(l.bytes for l in lines if l.role is Role.PROJECT) and est.scratch_bytes == sum(l.bytes for l in lines if l.role is Role.SCRATCH)
    assert est.backup_bytes == sum(l.bytes for l in lines if l.role is Role.BACKUP) > 0
    assert list(est.need) == ["project"] and est.need["project"] == sum(l.bytes for l in lines) + DEFAULT_TABLE.margin and est.short_by == {"project": 0}


def test_more_hours_need_more_room_and_a_scratch_drive_is_judged_on_its_own(tmp_path):
    small = np.evaluate(form(hours="1"))
    large = np.evaluate(form(hours="10"))
    assert large.estimate.need["project"] > small.estimate.need["project"]
    state = np.evaluate(form(hours="3", scratch_place=str(tmp_path)), facts=place_facts(tmp_path, "anna"), free={"project": 500 * GIB, "scratch": 1 * GIB})
    assert set(state.estimate.need) == {"project", "scratch"} and state.estimate.short_by["project"] == 0 and state.estimate.short_by["scratch"] > 0
    assert state.estimate.need["scratch"] == state.estimate.scratch_bytes + DEFAULT_TABLE.margin


def test_what_is_missing_is_the_difference_and_a_drive_that_cannot_be_read_is_not_judged():
    state = np.evaluate(form(hours="2"), free={"project": 10 * GIB})
    assert state.estimate.short_by["project"] == state.estimate.need["project"] - 10 * GIB
    assert np.evaluate(form(), free={"project": None}).estimate.short_by == {}
    assert np.evaluate(form()).estimate.short_by == {}


def test_a_short_disk_is_information_not_a_reason_to_refuse_the_project():
    state = np.evaluate(form(hours="50"), free={"project": 1 * GIB})
    assert state.can_create and state.estimate.short_by["project"] > 0


def test_no_estimate_without_usable_hours():
    assert np.evaluate(form(hours="")).estimate is None and np.evaluate(form(hours="101")).estimate is None


# ---------------------------------------------------------------- making the project

def make(tmp_path, f, **kw):
    root = str(tmp_path / "projects")
    state = np.evaluate(f, **kw)
    return root, state, np.create(f, state, root, NOW)


def test_a_project_is_made_with_its_folders_and_can_be_read_back(tmp_path):
    f = form(starting_voice="voice-mike")
    root, state, result = make(tmp_path, f, voice_ids=["voice-mike"])
    paths = ProjectPaths(root + "/anna")
    loaded = load_project(paths)
    assert result.error is None and result.scratch_dir is None and loaded == result.project
    assert (loaded.name, loaded.whose_voice, loaded.planned_hours, loaded.starting_voice, loaded.created) == ("Anna", OWN, 2.0, "voice-mike", "2026-10-10T12:00:00Z")
    assert all(os.path.isdir(p) for p in paths.folders) and stat.S_IMODE(os.stat(paths.root).st_mode) == 0o700


def test_someone_elses_note_is_kept_exactly_as_typed_after_tidying(tmp_path):
    f = form(name="Ben", whose_voice=SOMEONE_ELSE, consent=GOOD_CONSENT)
    root, state, result = make(tmp_path, f)
    assert result.project.consent == GOOD_CONSENT and load_project(ProjectPaths(root + "/ben")).consent == GOOD_CONSENT


def test_a_note_typed_for_ones_own_voice_is_not_thrown_away(tmp_path):
    note = Consent(given_by="Me", what_to="all of it")
    root, state, result = make(tmp_path, form(consent=note))
    assert result.project.consent.given_by == "Me" and result.project.consent.what_to == "all of it"


def test_a_form_that_did_not_pass_is_refused_and_nothing_is_made(tmp_path):
    f = form(name="")
    state = np.evaluate(f)
    with pytest.raises(ProjectError) as caught:
        np.create(f, state, str(tmp_path / "projects"), NOW)
    assert caught.value.code == "bad_value" and not (tmp_path / "projects").exists()


def test_two_people_with_one_name_get_two_folders(tmp_path):
    root = str(tmp_path / "projects")
    for expected in ("anna", "anna-2"):
        f = form()
        state = np.evaluate(f, taken_ids=os.listdir(root) if os.path.isdir(root) else [])
        assert np.create(f, state, root, NOW).project.id == expected


def test_a_chosen_scratch_place_gets_its_own_folder_and_marker_and_the_project_remembers_it(tmp_path):
    place = tmp_path / "bigdrive"
    place.mkdir()
    f = form(scratch_place=str(place))
    root, state, result = make(tmp_path, f, facts=place_facts(place, "anna"))
    folder = place / "ack-voice-scratch" / "anna"
    assert result.error is None and result.scratch_dir == str(folder)
    assert sc.check_marker((folder / sc.MARKER_NAME).read_text(), "anna") is sc.MarkerState.OK
    assert stat.S_IMODE((folder / sc.MARKER_NAME).stat().st_mode) == 0o600 and stat.S_IMODE(folder.stat().st_mode) == 0o700
    loaded = load_project(ProjectPaths(root + "/anna"))
    assert loaded.scratch.mode == "custom" and loaded.scratch.place == str(place)


def test_a_place_that_stops_working_after_the_check_costs_the_project_nothing(tmp_path):
    place = tmp_path / "usb"
    place.mkdir()
    f = form(scratch_place=str(place))
    state = np.evaluate(f, facts=place_facts(place, "anna"))
    place.rmdir()                                                         # unplugged between the check and the click
    result = np.create(f, state, str(tmp_path / "projects"), NOW)
    assert result.error == "scratch_failed" and result.scratch_dir is None and result.detail
    loaded = load_project(ProjectPaths(str(tmp_path / "projects") + "/anna"))
    assert loaded.scratch.mode == "default" and loaded.scratch.place is None and not place.exists()


def test_a_scratch_folder_that_became_someone_elses_is_not_used(tmp_path):
    place = tmp_path / "usb"
    (place / "ack-voice-scratch" / "anna").mkdir(parents=True)
    f = form(scratch_place=str(place))
    state = np.evaluate(f, facts=place_facts(place, "anna"))
    (place / "ack-voice-scratch" / "anna" / sc.MARKER_NAME).write_text(sc.marker_text("ben"))      # another project's marker appeared after the check
    result = np.create(f, state, str(tmp_path / "projects"), NOW)
    assert result.error == "scratch_failed" and (place / "ack-voice-scratch" / "anna" / sc.MARKER_NAME).read_text() == sc.marker_text("ben")


def test_if_the_folder_name_was_taken_meanwhile_the_scratch_folder_uses_the_real_name(tmp_path):
    place = tmp_path / "usb"
    place.mkdir()
    f = form(scratch_place=str(place))
    state = np.evaluate(f, facts=place_facts(place, "anna"))
    (tmp_path / "projects" / "anna").mkdir(parents=True)                  # someone else made "anna" after the check
    result = np.create(f, state, str(tmp_path / "projects"), NOW)
    assert result.project.id == "anna-2" and result.scratch_dir == str(place / "ack-voice-scratch" / "anna-2") and result.error is None


def test_the_error_codes_are_listed_and_a_failed_place_is_reported_by_code():
    assert np.ERROR_CODES == ("scratch_failed",)


# ---------------------------------------------------------------- the scratch folder itself

def test_the_scratch_folder_and_the_folder_above_it_are_owner_only(tmp_path):
    folder = sc.create_scratch(str(tmp_path), "anna")
    assert folder == "%s/ack-voice-scratch/anna" % tmp_path
    assert stat.S_IMODE(os.stat(tmp_path / "ack-voice-scratch").st_mode) == 0o700 and stat.S_IMODE(os.stat(folder).st_mode) == 0o700
    assert (Path(folder) / sc.MARKER_NAME).read_text() == sc.marker_text("anna")


def test_making_it_again_reuses_what_is_there_and_changes_no_file(tmp_path):
    folder = sc.create_scratch(str(tmp_path), "anna")
    (Path(folder) / "cache.bin").write_bytes(b"1234")
    marker = (Path(folder) / sc.MARKER_NAME).read_bytes()
    assert sc.create_scratch(str(tmp_path), "anna") == folder
    assert (Path(folder) / "cache.bin").read_bytes() == b"1234" and (Path(folder) / sc.MARKER_NAME).read_bytes() == marker


def test_two_projects_share_a_place_without_touching_each_other(tmp_path):
    a, b = sc.create_scratch(str(tmp_path), "anna"), sc.create_scratch(str(tmp_path), "ben")
    assert a != b and sorted(os.listdir(tmp_path / "ack-voice-scratch")) == ["anna", "ben"]


@pytest.mark.parametrize("setup, why", [("other marker", "another marker"), ("unmarked files", "no marker"), ("damaged marker", "another marker")])
def test_a_folder_that_is_not_this_projects_is_refused_and_left_alone(tmp_path, setup, why):
    folder = tmp_path / "ack-voice-scratch" / "anna"
    folder.mkdir(parents=True)
    if setup == "other marker":
        (folder / sc.MARKER_NAME).write_text(sc.marker_text("ben"))
    elif setup == "damaged marker":
        (folder / sc.MARKER_NAME).write_text("garbage")
    else:
        (folder / "data.bin").write_bytes(b"x")
    before = sorted(os.listdir(folder))
    with pytest.raises(ValueError, match=why):
        sc.create_scratch(str(tmp_path), "anna")
    assert sorted(os.listdir(folder)) == before


@pytest.mark.parametrize("place, project_id", [("relative/path", "anna"), ("/does/not/exist", "anna"), ("", "anna"), ("/tmp", "../etc"), ("/tmp", "Anna"), ("/tmp", "")])
def test_a_place_or_name_that_is_not_usable_is_refused_before_anything_is_made(tmp_path, place, project_id):
    with pytest.raises(ValueError):
        sc.create_scratch(place if place != "/tmp" else str(tmp_path), project_id)
    assert os.listdir(tmp_path) == []


def test_the_place_itself_is_never_made_only_the_tools_folder_inside_it(tmp_path):
    with pytest.raises(ValueError):
        sc.create_scratch(str(tmp_path / "missing" / "deeper"), "anna")
    assert os.listdir(tmp_path) == []


# ---------------------------------------------------------------- every problem has a sentence

def test_every_problem_the_form_can_report_has_a_sentence_and_every_sentence_can_be_reached(tmp_path):
    seen = set()
    long_note = Consent(**{**GOOD_CONSENT.__dict__, "given_by": "x" * (MAX_NOTE + 1)})
    cases = [form(name=""), form(name="a" * (MAX_NAME + 1)), form(whose_voice=""), form(whose_voice=SOMEONE_ELSE), form(consent=long_note),
             form(hours=""), form(hours="abc"), form(hours="0"), form(hours="1000"), form(starting_voice="nobody"), form(scratch_place="/data")]
    for case in cases:
        for p in np.evaluate(case, voice_ids=["voice-mike"]).problems:
            seen.add((p.field.split(".")[0], p.code))
    assert seen == set(np.PROBLEMS)
    state = np.evaluate(form(scratch_place="/usr/share"), facts=place_facts("/usr/share", "anna"))
    assert {p.code for p in state.problems if p.field == "scratch"} <= set(sc.REFUSAL_CODES)
