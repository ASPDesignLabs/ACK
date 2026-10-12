# SPDX-License-Identifier: GPL-3.0-or-later
"""Projects (plan task VS-1.5): one folder per person, a consent note for someone else's voice, a file that is never lost or silently rewritten."""
import json
import os
import random
import stat
from dataclasses import replace
from pathlib import Path
from datetime import datetime, timezone

import pytest

from voice_studio.core import project as pj
from voice_studio.core.paths import DataHome, ProjectPaths
from voice_studio.core.project import Consent, Project, ProjectError
from voice_studio.core.scratch import PROJECT_ID

NOW = datetime(2026, 10, 10, 9, 30, 0, tzinfo=timezone.utc)
FULL = Consent("Anna's mother", "recording Anna's voice to make her speaking voice", "9 Oct 2026", "tell me and we delete it", "spoken")


def make(**over):
    base = dict(id="anna", name="Anna", whose_voice=pj.OWN, created="2026-10-10T09:30:00Z")
    base.update(over)
    return Project(**base)


# ---------------------------------------------------------------- paths

def test_places_are_named_under_one_folder_in_the_home():
    home = DataHome("/home/user")
    assert home.root == "/home/user/ack-voice-studio" and home.projects == home.root + "/projects" and home.consent_file == home.root + "/state/consent.json"
    assert home.downloads == home.root + "/tool/downloads" and home.environments == home.root + "/tool/environments"
    p = ProjectPaths(home.projects + "/anna")
    assert p.project_json.endswith("/anna/project.json") and p.default_scratch.endswith("/anna/scratch")
    assert set(p.folders) == {p.recordings, p.rounds, p.exports, p.default_scratch}


# ---------------------------------------------------------------- text the person typed

@pytest.mark.parametrize("raw, expected", [
    ("  Anna  ", "Anna"), ("Anna\nSmith", "Anna Smith"), ("a\r\nb", "a b"), ("a\u0085b", "a b"), ("a b c", "a b c"), ("a\tb", "a b"),
    ("a\x00b\x07c", "abc"), ("   ", ""), (None, ""), (12, "12"), ("a   b    c", "a b c"),
])
def test_typed_text_is_tidied(raw, expected):
    assert pj.clean_text(raw, 100) == expected


def test_writing_that_needs_format_characters_keeps_them():
    family = "\U0001F468‍\U0001F469‍\U0001F467"
    hindi = "क्‍ष"
    persian = "می‌خواهم"
    assert pj.clean_text(family, 50) == family and pj.clean_text(hindi, 50) == hindi and pj.clean_text(persian, 50) == persian


def test_text_is_cut_at_the_limit_and_the_cut_is_trimmed():
    assert pj.clean_text("abcdef", 3) == "abc" and pj.clean_text("abc def", 4) == "abc" and pj.clean_text("abcdef", 6) == "abcdef" and pj.clean_text("abcdef", 0) == ""


# ---------------------------------------------------------------- names for folders

@pytest.mark.parametrize("name, slug", [("Anna", "anna"), ("José Müller", "jose-muller"), ("Anna  &  Ben!", "anna-ben"), ("李雷", "person"), ("!!!", "person"),
                                         ("", "person"), ("  --x--  ", "x"), ("3rd Person", "3rd-person")])
def test_a_folder_name_comes_from_the_persons_name(name, slug):
    assert pj.slugify(name) == slug


def test_two_people_with_the_same_name_get_different_folders():
    assert pj.slugify("Anna", ["anna"]) == "anna-2" and pj.slugify("Anna", ["anna", "anna-2"]) == "anna-3"
    assert pj.slugify("李雷", ["person", "person-2"]) == "person-3"


def test_a_long_name_is_shortened_without_a_trailing_hyphen_and_every_slug_is_a_safe_folder_name():
    long = pj.slugify("a" * 39 + " " + "b" * 30)
    assert len(long) <= 40 and not long.endswith("-") and PROJECT_ID.match(long)
    rng = random.Random(7)
    for _ in range(300):
        text = "".join(chr(rng.choice([rng.randrange(32, 127), rng.randrange(0x80, 0x2FF), rng.randrange(0x4E00, 0x4E40), 0x200D, 10, 0])) for _ in range(rng.randrange(0, 60)))
        assert PROJECT_ID.match(pj.slugify(text, ["person"]))


# ---------------------------------------------------------------- the consent note (D21)

def test_your_own_voice_needs_no_note_and_someone_elses_needs_all_of_it():
    assert pj.consent_problems(make()) == () and pj.may_record(make())
    other = make(whose_voice=pj.SOMEONE_ELSE)
    assert set(pj.consent_problems(other)) == {"given_by", "what_to", "when", "withdraw", "how_given"} and not pj.may_record(other)
    assert pj.consent_problems(replace(other, consent=FULL)) == () and pj.may_record(replace(other, consent=FULL))


@pytest.mark.parametrize("field", ["given_by", "what_to", "when", "withdraw"])
def test_each_part_of_the_note_is_needed_and_white_space_does_not_count(field):
    other = make(whose_voice=pj.SOMEONE_ELSE, consent=replace(FULL, **{field: "   "}))
    assert pj.consent_problems(other) == (field,)


@pytest.mark.parametrize("how", list(pj.HOW_GIVEN[:-1]))
def test_each_way_consent_can_be_given_is_accepted_including_spoken_guardian_and_aac(how):
    assert pj.consent_problems(make(whose_voice=pj.SOMEONE_ELSE, consent=replace(FULL, how_given=how))) == ()


def test_other_needs_words_and_an_unknown_way_is_a_problem():
    assert pj.consent_problems(make(whose_voice=pj.SOMEONE_ELSE, consent=replace(FULL, how_given="other"))) == ("how_given_other",)
    assert pj.consent_problems(make(whose_voice=pj.SOMEONE_ELSE, consent=replace(FULL, how_given="other", how_given_other="by letter"))) == ()
    assert pj.consent_problems(make(whose_voice=pj.SOMEONE_ELSE, consent=replace(FULL, how_given="telepathy"))) == ("how_given",)


@pytest.mark.parametrize("over, detail", [
    (dict(id="Bad Id"), "id"), (dict(id=""), "id"), (dict(name=""), None), (dict(name="x" * 81), None), (dict(whose_voice="robot"), "whose_voice"),
    (dict(planned_hours=0.49), "planned_hours"), (dict(planned_hours=100.01), "planned_hours"),
    (dict(scratch=pj.Scratch("custom", None)), "scratch"), (dict(scratch=pj.Scratch("default", "/x")), "scratch"), (dict(scratch=pj.Scratch("weird", None)), "scratch"),
    (dict(consent=Consent(how_given="telepathy")), "how_given"),
])
def test_a_project_that_breaks_a_rule_does_not_validate(over, detail):
    with pytest.raises(ProjectError) as caught:
        pj.validate(make(**over))
    assert caught.value.code in ("bad_value", "bad_name")


def test_the_limits_of_hours_and_name_length_are_inclusive():
    for ok in (make(planned_hours=pj.MIN_HOURS), make(planned_hours=pj.MAX_HOURS), make(name="x" * 80)):
        pj.validate(ok)


# ---------------------------------------------------------------- the file

def test_a_project_survives_a_round_trip_with_every_field():
    p = make(whose_voice=pj.SOMEONE_ELSE, consent=FULL, planned_hours=2.5, starting_voice="voice-mike", scratch=pj.Scratch("custom", "/media/x"),
             acknowledgments=(pj.Acknowledgment("voice-mike", "2026-10-10T09:31:00Z", "abc123"),))
    assert pj.project_from_text(json.dumps(pj.project_to_dict(p))) == p


def test_fields_a_newer_version_added_are_kept_when_this_one_saves(tmp_path):
    paths = ProjectPaths(str(tmp_path / "p"))
    os.makedirs(paths.root)
    raw = pj.project_to_dict(make())
    raw["future_setting"] = {"a": [1, 2]}
    with open(paths.project_json, "w") as handle:
        json.dump(raw, handle)
    loaded = pj.load_project(paths)
    assert loaded.extra == {"future_setting": {"a": [1, 2]}}
    pj.save_project(paths, replace(loaded, name="Anna B"))
    assert json.loads(Path(paths.project_json).read_text())["future_setting"] == {"a": [1, 2]} and pj.load_project(paths).name == "Anna B"


def test_missing_optional_fields_mean_no_change():
    p = pj.project_from_text(json.dumps({"schema": 1, "id": "anna", "name": "Anna", "whose_voice": "own", "created": "2026-10-10T09:30:00Z"}))
    assert p.planned_hours == 1.0 and p.starting_voice is None and p.scratch == pj.Scratch() and p.acknowledgments == () and p.consent == Consent()


def test_whole_number_hours_are_accepted_and_unicode_is_written_readably(tmp_path):
    p = pj.project_from_text(json.dumps({"schema": 1, "id": "anna", "name": "Anaïs", "whose_voice": "own", "created": "t", "planned_hours": 2}))
    assert p.planned_hours == 2.0 and isinstance(p.planned_hours, float)
    paths = ProjectPaths(str(tmp_path))
    pj.save_project(paths, p)
    assert "Anaïs" in Path(paths.project_json).read_text(encoding="utf-8")


@pytest.mark.parametrize("text, code", [
    ("not json", "damaged"), ("[]", "damaged"), ("{}", "damaged"), (json.dumps({"schema": True}), "damaged"), (json.dumps({"schema": "1"}), "damaged"),
    (json.dumps({"schema": 2, "id": "a"}), "newer"),
    (json.dumps({"schema": 1, "id": "anna", "name": "A", "whose_voice": "own", "created": "t", "planned_hours": "x"}), "damaged"),
    (json.dumps({"schema": 1, "id": "anna", "name": "A", "whose_voice": "own", "created": "t", "planned_hours": True}), "damaged"),
    (json.dumps({"schema": 1, "id": "anna", "name": "A", "whose_voice": "own", "created": "t", "consent": []}), "damaged"),
    (json.dumps({"schema": 1, "id": "anna", "name": "A", "whose_voice": "own", "created": "t", "scratch": []}), "damaged"),
    (json.dumps({"schema": 1, "id": "anna", "name": "A", "whose_voice": "own", "created": "t", "acknowledgments": "yes"}), "damaged"),
    (json.dumps({"schema": 1, "id": "anna", "name": "A", "whose_voice": "own", "created": "t", "scratch": {"place": 5}}), "damaged"),
    (json.dumps({"schema": 1, "id": "anna", "name": "A", "whose_voice": "own", "created": "t", "starting_voice": 5}), "damaged"),
    (json.dumps({"schema": 1, "id": "anna", "name": "A", "whose_voice": "own", "created": "t", "acknowledgments": [{"voice": 1}]}), "damaged"),
    (json.dumps({"schema": 1, "id": "../x", "name": "A", "whose_voice": "own", "created": "t"}), "damaged"),
    (json.dumps({"schema": 1, "id": "anna", "name": "", "whose_voice": "own", "created": "t"}), "damaged"),
    (json.dumps({"schema": 1, "id": "anna", "name": "A", "whose_voice": "robot", "created": "t"}), "damaged"),
])
def test_a_file_that_cannot_be_trusted_is_reported_not_repaired(text, code):
    with pytest.raises(ProjectError) as caught:
        pj.project_from_text(text)
    assert caught.value.code == code


def test_saving_is_atomic_owner_only_and_keeps_the_version_it_replaces(tmp_path):
    paths = ProjectPaths(str(tmp_path))
    pj.save_project(paths, make(name="First"))
    assert stat.S_IMODE(os.stat(paths.project_json).st_mode) == 0o600 and not os.path.exists(paths.previous_json)
    first_bytes = Path(paths.project_json).read_bytes()
    pj.save_project(paths, make(name="Second"))
    assert Path(paths.previous_json).read_bytes() == first_bytes and pj.load_project(paths).name == "Second"
    assert stat.S_IMODE(os.stat(paths.previous_json).st_mode) == 0o600
    assert sorted(os.listdir(tmp_path)) == ["project.json", "project.json.previous"]


def test_a_damaged_file_is_copied_byte_for_byte_before_it_is_replaced(tmp_path):
    paths = ProjectPaths(str(tmp_path))
    junk = b"\xff\xfe not json at all \x00"
    Path(paths.project_json).write_bytes(junk)
    pj.save_project(paths, make())
    assert Path(paths.previous_json).read_bytes() == junk


def test_a_failed_save_leaves_the_old_file_and_no_temporary_one(tmp_path, monkeypatch):
    paths = ProjectPaths(str(tmp_path))
    pj.save_project(paths, make(name="Keep"))
    real = os.replace

    def boom(src, dst):
        if dst == paths.project_json:
            raise OSError("disk full")
        return real(src, dst)
    monkeypatch.setattr(pj.os, "replace", boom)
    with pytest.raises(OSError):
        pj.save_project(paths, make(name="Lost"))
    monkeypatch.undo()
    assert pj.load_project(paths).name == "Keep" and not [n for n in os.listdir(tmp_path) if n.endswith(".tmp")]


def test_saving_an_invalid_project_writes_nothing(tmp_path):
    paths = ProjectPaths(str(tmp_path))
    with pytest.raises(ProjectError):
        pj.save_project(paths, make(planned_hours=0))
    assert os.listdir(tmp_path) == []


def test_loading_a_missing_or_unreadable_file_is_an_error_not_a_crash(tmp_path):
    with pytest.raises(ProjectError) as caught:
        pj.load_project(ProjectPaths(str(tmp_path / "nothing")))
    assert caught.value.code == "unreadable"
    paths = ProjectPaths(str(tmp_path))
    Path(paths.project_json).write_bytes(b"\xff\xfe\xfd")
    with pytest.raises(ProjectError) as caught:
        pj.load_project(paths)
    assert caught.value.code in ("unreadable", "damaged")


# ---------------------------------------------------------------- making projects

def test_a_project_is_made_with_its_folders_owner_only(tmp_path):
    root = str(tmp_path / "projects")
    p = pj.create_project(root, "  Anna\nSmith ", pj.OWN, planned_hours=2, now=NOW)
    paths = ProjectPaths(root + "/" + p.id)
    assert (p.id, p.name, p.created, p.planned_hours) == ("anna-smith", "Anna Smith", "2026-10-10T09:30:00Z", 2.0)
    for folder in (root, paths.root) + paths.folders:
        assert stat.S_IMODE(os.stat(folder).st_mode) == 0o700, folder
    assert pj.load_project(paths) == p


def test_someone_elses_voice_cannot_be_started_without_the_whole_note(tmp_path):
    root = str(tmp_path / "projects")
    with pytest.raises(ProjectError) as caught:
        pj.create_project(root, "Ben", pj.SOMEONE_ELSE, Consent(given_by="his dad"), now=NOW)
    assert caught.value.code == "consent" and "what_to" in caught.value.detail and "how_given" in caught.value.detail
    assert not os.path.exists(root + "/ben"), "nothing is made when the note is incomplete"
    ok = pj.create_project(root, "Ben", pj.SOMEONE_ELSE, FULL, now=NOW)
    assert ok.consent == FULL and pj.may_record(ok)


def test_the_note_is_tidied_like_other_typed_text(tmp_path):
    messy = replace(FULL, given_by="  his\n dad ", what_to="x" * 600)
    p = pj.create_project(str(tmp_path), "Ben", pj.SOMEONE_ELSE, messy, now=NOW)
    assert p.consent.given_by == "his dad" and len(p.consent.what_to) == pj.MAX_NOTE


def test_a_second_person_with_the_same_name_gets_their_own_folder(tmp_path):
    a = pj.create_project(str(tmp_path), "Anna", pj.OWN, now=NOW)
    b = pj.create_project(str(tmp_path), "Anna", pj.OWN, now=NOW)
    assert (a.id, b.id) == ("anna", "anna-2") and sorted(os.listdir(tmp_path)) == ["anna", "anna-2"]


def test_an_existing_folder_is_never_touched(tmp_path, monkeypatch):
    os.makedirs(tmp_path / "anna")
    (tmp_path / "anna" / "keep.txt").write_text("mine")
    monkeypatch.setattr(pj, "slugify", lambda name, taken=(): "anna")      # a race: the name was free a moment ago
    with pytest.raises(ProjectError) as caught:
        pj.create_project(str(tmp_path), "Anna", pj.OWN, now=NOW)
    assert caught.value.code == "exists" and (tmp_path / "anna" / "keep.txt").read_text() == "mine" and os.listdir(tmp_path / "anna") == ["keep.txt"]


@pytest.mark.parametrize("kwargs", [dict(name="   "), dict(name=""), dict(planned_hours=True), dict(planned_hours="2"), dict(planned_hours=0.4), dict(whose_voice="robot")])
def test_a_project_with_a_bad_name_hours_or_owner_is_refused_and_leaves_nothing(tmp_path, kwargs):
    args = dict(name="Anna", whose_voice=pj.OWN, planned_hours=1.0)
    args.update(kwargs)
    with pytest.raises(ProjectError):
        pj.create_project(str(tmp_path), args["name"], args["whose_voice"], planned_hours=args["planned_hours"], now=NOW)
    assert os.listdir(tmp_path) == []


# ---------------------------------------------------------------- listing

def test_projects_are_listed_oldest_first_and_trouble_is_reported_not_hidden(tmp_path):
    root = str(tmp_path)
    pj.create_project(root, "Zed", pj.OWN, now=datetime(2026, 1, 1, tzinfo=timezone.utc))
    pj.create_project(root, "Amy", pj.OWN, now=datetime(2026, 2, 1, tzinfo=timezone.utc))
    os.makedirs(tmp_path / "broken")
    (tmp_path / "broken" / "project.json").write_text("{nope")
    os.makedirs(tmp_path / "future")
    (tmp_path / "future" / "project.json").write_text(json.dumps({"schema": 9}))
    os.makedirs(tmp_path / "no-file")
    (tmp_path / "loose.txt").write_text("x")
    listing = pj.list_projects(root)
    assert [p.id for p in listing.projects] == ["zed", "amy"]
    assert listing.problems == (("broken", "damaged"), ("future", "newer"))
    assert (tmp_path / "broken" / "project.json").read_text() == "{nope"


def test_listing_a_missing_folder_is_empty():
    assert pj.list_projects("/no/such/folder") == pj.ProjectList((), ())


# ---------------------------------------------------------------- small updates

def test_updates_return_new_projects_and_do_not_change_the_old_one():
    p = make()
    assert pj.with_starting_voice(p, "voice-amy").starting_voice == "voice-amy" and p.starting_voice is None
    moved = pj.with_scratch_place(p, "/media/user/BIG")
    assert moved.scratch == pj.Scratch("custom", "/media/user/BIG") and pj.with_scratch_place(moved, None).scratch == pj.Scratch()
    pj.validate(moved)


def test_an_acknowledgment_is_recorded_once_per_voice_and_revision():
    p = pj.with_acknowledgment(make(), "voice-mike", "abc", NOW)
    assert p.acknowledgments == (pj.Acknowledgment("voice-mike", "2026-10-10T09:30:00Z", "abc"),)
    assert pj.with_acknowledgment(p, "voice-mike", "abc", NOW) is p
    again = pj.with_acknowledgment(p, "voice-mike", "def", NOW)
    assert [a.revision for a in again.acknowledgments] == ["abc", "def"]
    assert len(pj.with_acknowledgment(p, "voice-amy", "abc", NOW).acknowledgments) == 2
