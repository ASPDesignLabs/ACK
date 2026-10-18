# SPDX-License-Identifier: GPL-3.0-or-later
"""Refresh (plan task VS-6.6, decision P18): what a look finds in the programs, the downloads and the notes, what a repair is made of, the second copy of the programs, and the old copies.
Every test works on real files in real folders, with the builder tests' stand-in for the computer and the network."""
import errno
import json
import os
import shutil
import stat
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import pytest

from vs_envfind_hub import put_hub
from vs_refresh_helpers import SPEECH, VOICE_BYTES, RefreshRig
from vs_rounds_helpers import fake_job
from voice_studio.core import envbuild as eb, envgen, envfind, projectbackup as pb, refresh as rf
from voice_studio.core.project import create_project
from voice_studio.core.paths import ProjectPaths

NOW = datetime(2026, 10, 17, 9, 30, 0, tzinfo=timezone.utc)


@pytest.fixture
def rig(tmp_path):
    return RefreshRig(tmp_path)


def finding(report, ident):
    return next(f for f in report.findings if f.id == ident)


def tree(root):
    found = {}
    for path in sorted(Path(root).rglob("*")):
        if path.is_file() and not path.is_symlink():
            found[str(path.relative_to(root))] = (path.read_bytes(), path.stat().st_mtime_ns)
    return found


def code_of(fn, *a, **kw):
    with pytest.raises(rf.RefreshError) as caught:
        fn(*a, **kw)
    return caught.value.code


# ---------------------------------------------------------------- the programs

def test_programs_that_are_whole_pass_their_own_check_and_are_good(rig):
    f = finding(rig.look(), "programs:demo")
    assert (f.area, f.subject, f.status, f.reason, f.fix, f.detail, f.steps) == (rf.PROGRAMS, "demo", rf.GOOD, "ready", "", "", ())


def test_a_probe_that_needs_a_card_this_computer_does_not_have_is_named_as_not_tried(tmp_path):
    rig = RefreshRig(tmp_path, gpu=False)
    f = finding(rig.look(), "programs:demo")
    assert (f.status, f.reason, f.detail) == (rf.GOOD, "ready_untried", "card")


def test_a_quick_look_does_not_run_the_programs_own_check(rig):
    rig.system.probe_runs.clear()
    rig.system.launcher_runs.clear()
    assert finding(rig.look(probes=False), "programs:demo").reason == "ready"
    assert rig.system.probe_runs == [] and rig.system.launcher_runs == []
    finding(rig.look(), "programs:demo")
    assert rig.system.probe_runs and rig.system.launcher_runs


def test_a_probe_that_fails_while_every_record_is_in_order_is_found_and_needs_a_rebuild(rig):
    rig.system.bad_probe_codes = {"import os"}
    f = finding(rig.look(), "programs:demo")
    assert (f.status, f.reason, f.fix, f.detail) == (rf.PROBLEM, "probe_failed", "rebuild", "imports")
    assert finding(rig.look(probes=False), "programs:demo").status == rf.GOOD, "without the check the files cannot be seen to be broken"


def test_a_helper_that_does_not_start_is_found_and_needs_a_rebuild(rig):
    rig.system.fail_launcher = True
    f = finding(rig.look(), "programs:demo")
    assert (f.status, f.reason, f.fix) == (rf.PROBLEM, "launcher_failed", "rebuild")


def test_a_step_that_was_lost_is_named_and_finishing_it_is_the_repair(rig):
    shutil.rmtree(rig.env.paths.venv)
    f = finding(rig.look(), "programs:demo")
    assert (f.status, f.reason, f.fix) == (rf.PROBLEM, "needs_work", "resume") and "venv" in f.steps and f.steps == tuple(sorted(f.steps, key=eb.STEP_IDS.index))


def test_programs_that_were_never_checked_after_their_last_step_say_so(rig):
    record = json.loads(Path(rig.env.paths.record).read_text())
    record["state"] = "building"
    Path(rig.env.paths.record).write_text(json.dumps(record))
    f = finding(rig.look(), "programs:demo")
    assert (f.reason, f.fix, f.steps) == ("not_checked", "resume", ())


def test_a_build_that_failed_is_named_with_the_steps_left(rig):
    shutil.rmtree(rig.env.paths.venv)
    rig.env.doors.pip_fail["lock"] = 1
    assert not rig.env.build().ok
    f = finding(rig.look(), "programs:demo")
    assert (f.reason, f.fix) == ("failed", "resume") and f.steps


def test_programs_that_are_not_there_are_not_a_problem_and_are_pointed_to_the_setup(tmp_path):
    rig = RefreshRig(tmp_path, built=False)
    f = finding(rig.look(), "programs:demo")
    assert (f.status, f.reason, f.fix) == (rf.ABSENT, "not_set_up", "setup") and not rig.look().problems


def test_a_record_that_is_damaged_or_missing_or_newer_is_each_named_and_never_touched(rig):
    record = Path(rig.env.paths.record)
    good = record.read_text()
    record.write_text("{not json")
    f = finding(rig.look(), "programs:demo")
    assert (f.reason, f.fix) == ("damaged_record", "rebuild") and record.read_text() == "{not json"
    record.unlink()
    f = finding(rig.look(), "programs:demo")
    assert (f.reason, f.fix) == ("not_ours", "rebuild")
    record.write_text(json.dumps(dict(json.loads(good), schema=99)))
    f = finding(rig.look(), "programs:demo")
    assert (f.status, f.reason, f.fix) == (rf.PROBLEM, "newer_record", "")


def test_programs_that_cannot_be_built_here_say_why(tmp_path):
    rig = RefreshRig(tmp_path, built=False, system_kw={"python": (3, 9, 0)})
    f = finding(rig.look(), "programs:demo")
    assert (f.status, f.reason, f.fix, f.detail) == (rf.PROBLEM, "cannot_build", "", "python_old")


# ---------------------------------------------------------------- the downloads

def test_a_listening_model_that_is_whole_in_the_tools_folder_is_good(rig):
    f = finding(rig.look(), "download:speech")
    assert (f.area, f.subject, f.status, f.reason, f.fix) == (rf.DOWNLOAD, rf.SPEECH, rf.GOOD, "fetched", "")


def test_a_listening_model_that_was_never_fetched_is_not_a_problem(tmp_path):
    rig = RefreshRig(tmp_path, speech=False)
    f = finding(rig.look(), "download:speech")
    assert (f.status, f.reason, f.fix) == (rf.ABSENT, "not_fetched", "")


def test_a_listening_model_with_a_file_missing_or_changed_is_incomplete_and_is_fetched_again(tmp_path):
    rig = RefreshRig(tmp_path, speech=False)
    rig.put_speech(["a.bin"])
    f = finding(rig.look(), "download:speech")
    assert (f.status, f.reason, f.fix) == (rf.PROBLEM, "incomplete", "fetch")
    rig.put_speech()
    assert finding(rig.look(), "download:speech").status == rf.GOOD
    (Path(envfind.speech_places(rig.home)[0]) / "b.bin").write_bytes(b"x" * len(SPEECH["b.bin"]))
    assert finding(rig.look(), "download:speech").reason == "incomplete"


def test_a_listening_model_that_Freeform_Studio_fetched_is_good_and_said_to_be_elsewhere(tmp_path, monkeypatch):
    rig = RefreshRig(tmp_path, speech=False)
    hub = tmp_path / "hub"
    monkeypatch.setenv("HF_HUB_CACHE", str(hub))
    put_hub(hub, SPEECH)
    f = finding(rig.look(), "download:speech")
    assert (f.status, f.reason) == (rf.GOOD, "fetched_elsewhere")


def test_a_starting_voice_is_good_damaged_or_unfinished_and_one_never_fetched_is_not_mentioned(tmp_path):
    rig = RefreshRig(tmp_path, voice=False)
    assert not [f for f in rig.look().findings if f.id == "download:voice-mike"]
    rig.put_voice()
    f = finding(rig.look(), "download:voice-mike")
    assert (f.status, f.reason, f.fix) == (rf.GOOD, "fetched", "")
    rig.voice_path().write_bytes(b"y" * len(VOICE_BYTES))
    f = finding(rig.look(), "download:voice-mike")
    assert (f.status, f.reason, f.fix) == (rf.PROBLEM, "damaged", "fetch")
    rig.voice_path().unlink()
    Path(str(rig.voice_path()) + ".part").write_bytes(VOICE_BYTES[:10])
    f = finding(rig.look(), "download:voice-mike")
    assert (f.reason, f.fix) == ("unfinished", "fetch")


def test_only_voices_the_registry_can_fetch_are_looked_at(rig):
    unpinned = replace(rig.voice_item, id="voice-ghost", sha256=None)
    registry = replace(rig.registry, items=rig.registry.items + (unpinned,))
    assert [i.id for i in rf.voice_items(registry)] == ["voice-mike"]


# ---------------------------------------------------------------- the notes

@pytest.mark.parametrize("note", rf.NOTES)
def test_a_note_that_is_not_there_is_not_a_problem_and_one_that_cannot_be_read_is_set_aside(tmp_path, note):
    rig = RefreshRig(tmp_path)
    path = Path(rf.note_path(rig.home, note))
    if path.exists():
        path.unlink()
    f = finding(rig.look(), "note:" + note)
    assert (f.area, f.subject, f.status, f.reason, f.fix) == (rf.NOTE, note, rf.ABSENT, "no_note", "")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{ this is not a note")
    f = finding(rig.look(), "note:" + note)
    assert (f.status, f.reason, f.fix) == (rf.PROBLEM, "unreadable", "set_aside")


def test_notes_that_can_be_read_are_good(rig):
    os.makedirs(rig.home.state, exist_ok=True)
    Path(rf.note_path(rig.home, "window")).write_text(json.dumps({"schema": 1, "theme": "dark"}))
    for note in ("backups", "copies"):
        Path(rf.note_path(rig.home, note)).write_text(json.dumps({"schema": 1}))
    report = rig.look()
    assert [finding(report, "note:" + n).status for n in rf.NOTES] == [rf.GOOD] * 4 and all(finding(report, "note:" + n).reason == "readable" for n in rf.NOTES)


def test_the_notes_are_where_the_rest_of_the_tool_keeps_them(rig):
    assert rf.note_path(rig.home, "consent") == rig.home.consent_file and rf.note_path(rig.home, "window") == rig.home.window_file
    assert rf.note_path(rig.home, "backups") == rig.home.state + "/" + pb.STATE_FILE and rf.note_path(rig.home, "copies") == envgen.path_of(rig.home)


# ---------------------------------------------------------------- a look

def test_a_look_goes_through_the_programs_then_the_downloads_then_the_notes_and_says_where_it_is(rig):
    seen = []
    report = rig.look(announce=lambda area, subject: seen.append((area, subject)))
    assert seen == [(rf.PROGRAMS, "demo"), (rf.DOWNLOAD, rf.SPEECH), (rf.DOWNLOAD, "voice-mike")] + [(rf.NOTE, n) for n in rf.NOTES]
    assert [f.id for f in report.findings] == ["programs:demo", "download:speech", "download:voice-mike"] + ["note:" + n for n in rf.NOTES]
    assert report.in_order and report.problems == ()


def test_a_look_changes_nothing_not_even_the_log_of_the_programs(rig):
    before = {**tree(rig.home.root)}
    rig.system.bad_probe_codes = {"import sys"}
    rig.look()
    rig.system.bad_probe_codes = set()
    rig.look()
    rig.look(probes=False)
    assert tree(rig.home.root) == before


def test_the_report_groups_problems_by_what_mends_them(rig):
    rig.system.bad_probe_codes = {"import os"}
    rig.voice_path().write_bytes(b"z" * len(VOICE_BYTES))
    Path(rf.note_path(rig.home, "window")).parent.mkdir(parents=True, exist_ok=True)
    Path(rf.note_path(rig.home, "window")).write_text("garbage")
    report = rig.look()
    assert [f.id for f in report.of("rebuild")] == ["programs:demo"] and [f.id for f in report.of("fetch")] == ["download:voice-mike"]
    assert [f.id for f in report.of("set_aside")] == ["note:window"] and report.of("resume") == () and not report.in_order


# ---------------------------------------------------------------- a repair

def test_a_repair_is_made_of_what_can_be_mended_and_names_what_cannot(rig):
    shutil.rmtree(rig.env.paths.venv)
    rig.voice_path().write_bytes(b"z" * len(VOICE_BYTES))
    Path(rf.note_path(rig.home, "backups")).parent.mkdir(parents=True, exist_ok=True)
    Path(rf.note_path(rig.home, "backups")).write_text("[")
    plan = rf.plan_repair(rig.look())
    assert [f.id for f in plan.resume] == ["programs:demo"] and [f.id for f in plan.fetch] == ["download:voice-mike"] and [f.id for f in plan.set_aside] == ["note:backups"]
    assert plan.needs_more == () and plan.work
    rig.system.bad_probe_codes = {"import os"}
    again = rf.plan_repair(rig.look())
    assert [f.id for f in again.needs_more] == []                                   # the lost step is found first; the files are only seen once it is finished
    assert not rf.plan_repair(rf.Report(())).work


def test_what_needs_a_rebuild_or_the_setup_or_an_update_is_listed_as_needing_more(tmp_path):
    rig = RefreshRig(tmp_path, built=False)
    plan = rf.plan_repair(rig.look())
    assert plan.needs_more == () and not plan.work, "programs that are not set up are not a problem"
    record = Path(rig.env.build().env_dir) / eb.RECORD_NAME
    record.write_text("{broken")
    plan = rf.plan_repair(rig.look())
    assert [f.reason for f in plan.needs_more] == ["damaged_record"] and not plan.work


def test_a_note_that_cannot_be_read_is_set_aside_beside_itself_with_its_contents_and_never_replaces_anything(rig):
    path = Path(rf.note_path(rig.home, "window"))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("what was there")
    moved = rf.set_aside(rig.home, "window", NOW)
    assert moved == str(path) + ".damaged-20261017-093000" and Path(moved).read_text() == "what was there" and not path.exists()
    path.write_text("another")
    again = rf.set_aside(rig.home, "window", NOW)
    assert again == moved + "-2" and Path(moved).read_text() == "what was there" and Path(again).read_text() == "another"
    path.write_text("a third")
    assert rf.set_aside(rig.home, "window", NOW).endswith("-3")


def test_setting_aside_a_note_that_is_not_there_is_an_error_and_changes_nothing(rig):
    with pytest.raises(OSError):
        rf.set_aside(rig.home, "window", NOW)


def test_what_is_fetched_again_is_the_speech_files_that_are_not_right_and_the_voice_file(tmp_path):
    rig = RefreshRig(tmp_path, speech=False)
    rig.put_speech(["a.bin"])
    speech = finding(rig.look(), "download:speech")
    wanted = rf.items_to_fetch(rig.home, rig.registry, [speech])
    assert [(i.filename, str(f)) for i, f in wanted] == [("b.bin", envfind.speech_places(rig.home)[0])]
    rig.voice_path().write_bytes(b"q")
    voice = finding(rig.look(), "download:voice-mike")
    (item, folder), = rf.items_to_fetch(rig.home, rig.registry, [voice])
    assert item.id == "voice-mike" and folder == rig.voice_path().parent
    ghost = replace(voice, subject="voice-ghost")
    assert rf.items_to_fetch(rig.home, rig.registry, [ghost]) == []


# ---------------------------------------------------------------- a second copy

def test_the_next_copy_is_one_higher_than_the_one_in_use_and_there_is_a_last_one(rig):
    assert rf.next_generation(rig.home, "demo") == 1
    envgen.write(rig.home, "demo", 3)
    assert rf.next_generation(rig.home, "demo") == 4 and rf.next_generation(rig.home, "other") == 1
    envgen.write(rig.home, "demo", envgen.MAX_GENERATION)
    assert code_of(rf.next_generation, rig.home, "demo") == "no_more_copies"


def test_a_context_for_the_next_copy_changes_only_that_set_of_programs(rig):
    envgen.write(rig.home, "other", 2)
    ctx = rf.with_generation(rig.env.ctx, "demo", 5)
    assert ctx.generations(rig.home, "demo") == 5 and ctx.generations(rig.home, "other") == 2 and ctx.generations(rig.home, "third") == 0
    assert rig.env.ctx.generations(rig.home, "demo") == 0, "the context it was made from is not changed"


def test_the_switch_is_noted_and_a_note_that_cannot_be_written_is_said_and_leaves_the_old_copy_in_use(rig):
    rf.note_generation(rig.home, "demo", 1)
    assert envgen.generation_of(rig.home, "demo") == 1
    shutil.rmtree(rig.home.state)
    Path(rig.home.state).write_text("a file where the folder should be")
    assert code_of(rf.note_generation, rig.home, "demo", 2) == "not_noted"
    assert envgen.generation_of(rig.home, "demo") == 0


def build_next(rig, number=1):
    ctx = rf.with_generation(rig.env.ctx, "demo", number)
    result = eb.build(rig.spec, ctx)
    assert result.ok
    return result.env_dir


# ---------------------------------------------------------------- the old copies

def test_a_copy_that_is_in_use_is_never_old_and_a_copy_beside_it_is(rig):
    old = rig.env.env_dir
    new = build_next(rig)
    envgen.write(rig.home, "demo", 1)
    older = rf.older_copies(rig.home, [rig.spec], rig.env.ctx)
    (copy,) = older.copies
    assert copy.folder == old and copy.env_id == "demo" and copy.state == "ready" and older.in_use == (new,) and older.left_alone == 0
    assert copy.files == len([p for p in Path(old).rglob("*") if p.is_file() and not p.is_symlink()]) and copy.bytes == sum(p.stat().st_size for p in Path(old).rglob("*") if p.is_file() and not p.is_symlink())
    assert copy.updated and copy.updated == json.loads(Path(old, eb.RECORD_NAME).read_text())["updated_at"]


def test_with_one_copy_there_is_nothing_old(rig):
    older = rf.older_copies(rig.home, [rig.spec], rig.env.ctx)
    assert older.copies == () and older.left_alone == 0 and older.in_use == (rig.env.env_dir,)


def test_a_copy_that_was_never_finished_is_listed_with_what_its_record_says(rig):
    old = rig.env.env_dir
    ctx = rf.with_generation(rig.env.ctx, "demo", 1)
    rig.env.doors.pip_fail["lock"] = 1
    assert not eb.build(rig.spec, ctx).ok
    rig.env.doors.pip_fail.clear()
    older = rf.older_copies(rig.home, [rig.spec], rig.env.ctx)
    assert [(c.folder, c.state) for c in older.copies] == [(eb.environment_dir(rig.spec, ctx), "failed")] and old not in [c.folder for c in older.copies]


def test_folders_this_tool_did_not_make_are_counted_and_never_listed(rig):
    envs = Path(rig.home.environments)
    (envs / "demo-0123456789").mkdir()                                          # a name like ours, no record
    (envs / "somebody-elses").mkdir()
    (envs / "demo-notaprint").mkdir()
    (envs / "other-0123456789").mkdir()
    os.symlink(str(rig.env.env_dir), str(envs / "demo-aaaaaaaaaa"))             # a link to the copy in use
    (envs / "a-file").write_text("x")
    older = rf.older_copies(rig.home, [rig.spec], rig.env.ctx)
    assert older.copies == () and older.left_alone == 6


def test_a_record_that_belongs_to_another_name_is_not_trusted(rig):
    old = Path(rig.env.env_dir)
    new = build_next(rig)
    envgen.write(rig.home, "demo", 1)
    wrong = Path(rig.home.environments) / "demo-bbbbbbbbbb"
    shutil.copytree(old, wrong, symlinks=True)
    older = rf.older_copies(rig.home, [rig.spec], rig.env.ctx)
    assert [c.folder for c in older.copies] == [str(old)] and older.left_alone == 1 and str(wrong) not in [c.folder for c in older.copies]
    record = json.loads(Path(old, eb.RECORD_NAME).read_text())
    record["id"] = "other"
    Path(old, eb.RECORD_NAME).write_text(json.dumps(record))
    assert rf.older_copies(rig.home, [rig.spec], rig.env.ctx).copies == ()


def test_a_copy_that_is_being_built_right_now_is_left_out(rig):
    old = rig.env.env_dir
    build_next(rig)
    envgen.write(rig.home, "demo", 1)
    Path(old, eb.BUILD_LOCK_NAME).write_text("1")
    assert rf.older_copies(rig.home, [rig.spec], rig.env.ctx).copies == ()


def test_when_what_is_in_use_cannot_be_told_nothing_is_offered(tmp_path):
    rig = RefreshRig(tmp_path, built=False, system_kw={"python": (3, 9, 0)})
    (Path(rig.home.environments) / "demo-0123456789").mkdir(parents=True)
    older = rf.older_copies(rig.home, [rig.spec], rig.env.ctx)
    assert older.copies == () and older.in_use == ()


def test_copies_are_listed_in_the_order_of_their_names_and_no_more_than_the_limit(rig, monkeypatch):
    old = Path(rig.env.env_dir)
    build_next(rig, 1)
    build_next(rig, 2)
    envgen.write(rig.home, "demo", 2)
    older = rf.older_copies(rig.home, [rig.spec], rig.env.ctx)
    assert [c.folder for c in older.copies] == sorted(c.folder for c in older.copies) and len(older.copies) == 2 and str(old) in [c.folder for c in older.copies]
    monkeypatch.setattr(rf, "MAX_OLDER", 1)
    assert len(rf.older_copies(rig.home, [rig.spec], rig.env.ctx).copies) == 1


# ---------------------------------------------------------------- removing them

def two_copies(rig):
    old = rig.env.env_dir
    new = build_next(rig)
    envgen.write(rig.home, "demo", 1)
    return old, new


def test_only_the_copies_that_were_shown_are_removed_and_the_one_in_use_is_untouched(rig):
    old, new = two_copies(rig)
    shown = rf.older_copies(rig.home, [rig.spec], rig.env.ctx).copies
    before = tree(new)
    result = rf.remove_older(rig.home, [rig.spec], rig.env.ctx, shown)
    assert [c.folder for c in result.removed] == [old] and result.failed == () and result.bytes == shown[0].bytes
    assert not os.path.exists(old) and tree(new) == before and eb.inspect(rig.spec, rig.env.ctx).state == "ready"


def test_nothing_is_removed_while_a_task_is_running(rig):
    old, new = two_copies(rig)
    shown = rf.older_copies(rig.home, [rig.spec], rig.env.ctx).copies
    os.makedirs(rig.home.jobs, exist_ok=True)
    fake_job(rig.home.jobs, ["x"], "running", project="voice-check")
    assert code_of(rf.remove_older, rig.home, [rig.spec], rig.env.ctx, shown) == "job_running" and os.path.isdir(old)
    fake_job(rig.home.jobs, ["x"], "stopping", project="voice-check")
    assert code_of(rf.remove_older, rig.home, [rig.spec], rig.env.ctx, shown) == "job_running"


def test_a_task_that_has_ended_does_not_stop_the_removal(rig):
    old, new = two_copies(rig)
    shown = rf.older_copies(rig.home, [rig.spec], rig.env.ctx).copies
    os.makedirs(rig.home.jobs, exist_ok=True)
    fake_job(rig.home.jobs, ["x"], "finished", project="voice-check", exit_code=0)
    assert [c.folder for c in rf.remove_older(rig.home, [rig.spec], rig.env.ctx, shown).removed] == [old]


def test_a_list_that_is_not_the_one_shown_removes_nothing(rig):
    old, new = two_copies(rig)
    shown = rf.older_copies(rig.home, [rig.spec], rig.env.ctx).copies
    build_next(rig, 2)                                                         # another copy has appeared since
    envgen.write(rig.home, "demo", 2)
    assert code_of(rf.remove_older, rig.home, [rig.spec], rig.env.ctx, shown) == "changed" and os.path.isdir(old)
    assert code_of(rf.remove_older, rig.home, [rig.spec], rig.env.ctx, ()) == "changed"


def test_a_copy_whose_state_changed_since_it_was_shown_is_not_removed(rig):
    old, new = two_copies(rig)
    shown = rf.older_copies(rig.home, [rig.spec], rig.env.ctx).copies
    record = json.loads(Path(old, eb.RECORD_NAME).read_text())
    record["state"] = "failed"
    Path(old, eb.RECORD_NAME).write_text(json.dumps(record))
    assert code_of(rf.remove_older, rig.home, [rig.spec], rig.env.ctx, shown) == "changed" and os.path.isdir(old)


def test_a_folder_that_cannot_be_removed_is_reported_and_the_rest_go(rig):
    old = rig.env.env_dir
    build_next(rig, 1)
    mid = build_next(rig, 2)
    envgen.write(rig.home, "demo", 2)
    shown = rf.older_copies(rig.home, [rig.spec], rig.env.ctx).copies
    assert len(shown) == 2
    removed = []

    def remove(folder):
        if folder == old:
            raise OSError(errno.EACCES, "Permission denied")
        removed.append(folder)
        shutil.rmtree(folder)
    result = rf.remove_older(rig.home, [rig.spec], rig.env.ctx, shown, remove)
    assert result.failed == ((old, "Permission denied"),) and [c.folder for c in result.removed] == removed and os.path.isdir(old) and not os.path.isdir(removed[0])
    assert mid not in removed


def test_a_copy_swapped_for_a_link_or_a_file_after_the_list_was_made_is_not_followed(rig):
    old, new = two_copies(rig)
    shown = rf.older_copies(rig.home, [rig.spec], rig.env.ctx).copies
    real = rf.older_copies

    def swapped(home, specs, ctx):
        found = real(home, specs, ctx)
        shutil.rmtree(old)
        os.symlink(new, old)
        return found
    rf.older_copies = swapped
    try:
        result = rf.remove_older(rig.home, [rig.spec], rig.env.ctx, shown)
    finally:
        rf.older_copies = real
    assert result.removed == () and result.failed == ((old, "it is no longer an old copy"),) and os.path.isdir(new) and os.path.islink(old)


def test_removing_the_old_copy_does_not_touch_what_the_projects_hold(rig):
    old, new = two_copies(rig)
    create_project(rig.home.projects, "Anna", "own")
    keep = Path(rig.home.projects, "anna", "recordings")
    keep.mkdir(parents=True, exist_ok=True)
    (keep / "x.wav").write_bytes(b"RIFF")
    before = tree(rig.home.projects)
    rf.remove_older(rig.home, [rig.spec], rig.env.ctx, rf.older_copies(rig.home, [rig.spec], rig.env.ctx).copies)
    assert tree(rig.home.projects) == before


# ---------------------------------------------------------------- the projects, before a rebuild

def backed_up(rig, project_id):
    paths = ProjectPaths(rig.home.projects + "/" + project_id)
    dest = str(rig.home.root + "-backups")
    made = pb.create(pb.plan_backup(paths, rig.home, project_id, dest, 10 ** 12), paths, NOW)
    pb.record_backup(rig.home, made, project_id, dest)


def test_projects_with_no_up_to_date_backup_are_listed_with_why(rig):
    create_project(rig.home.projects, "Anna", "own")
    create_project(rig.home.projects, "Ben", "own")
    create_project(rig.home.projects, "Cara", "own")
    backed_up(rig, "ben")
    backed_up(rig, "cara")
    later = os.stat(ProjectPaths(rig.home.projects + "/cara").project_json).st_mtime + 5
    os.utime(ProjectPaths(rig.home.projects + "/cara").project_json, (later, later))
    assert [(p.id, why) for p, why in rf.unprotected(rig.home)] == [("anna", "never"), ("cara", "changed")]


def test_a_project_whose_record_of_rounds_cannot_be_read_is_left_out(rig):
    create_project(rig.home.projects, "Anna", "own")
    paths = ProjectPaths(rig.home.projects + "/anna")
    os.makedirs(paths.rounds, exist_ok=True)
    Path(paths.rounds_file).write_text("{broken")
    assert rf.unprotected(rig.home) == ()


def test_with_no_projects_there_is_nobody_to_advise(rig):
    assert rf.unprotected(rig.home) == ()


# ---------------------------------------------------------------- the edges found by breaking the library on purpose

def test_a_note_that_is_a_link_to_nothing_is_there_and_cannot_be_read(rig):
    path = Path(rf.note_path(rig.home, "window"))
    path.parent.mkdir(parents=True, exist_ok=True)
    os.symlink(str(path) + ".missing", str(path))
    f = finding(rig.look(), "note:window")
    assert (f.status, f.reason, f.fix) == (rf.PROBLEM, "unreadable", "set_aside")


def test_a_repair_is_planned_from_the_fix_each_problem_names_and_never_from_what_is_not_a_problem():
    def problem(fix, n):
        return rf.Finding("programs:p%d" % n, rf.PROGRAMS, "p%d" % n, rf.PROBLEM, "damaged_record", fix)
    absent = rf.Finding("programs:gone", rf.PROGRAMS, "gone", rf.ABSENT, "not_set_up", "setup")
    report = rf.Report(tuple(problem(fix, n) for n, fix in enumerate(rf.FIXES)) + (absent,))
    plan = rf.plan_repair(report)
    assert tuple(f.fix for f in plan.resume) == ("resume",) and tuple(f.fix for f in plan.fetch) == ("fetch",) and tuple(f.fix for f in plan.set_aside) == ("set_aside",)
    assert sorted(f.fix for f in plan.needs_more) == ["", "rebuild", "setup"], "a problem nothing here can mend is named, whatever fix it carries"
    assert report.of("setup") == tuple(f for f in report.problems if f.fix == "setup") and len(report.of("setup")) == 1 and absent not in report.of("setup") and absent not in plan.needs_more and plan.work


def test_a_problem_that_nothing_here_can_mend_is_named_by_a_repair(tmp_path):
    rig = RefreshRig(tmp_path, built=False, system_kw={"python": (3, 9, 0)})
    plan = rf.plan_repair(rig.look())
    assert [(f.reason, f.fix) for f in plan.needs_more] == [("cannot_build", "")] and not plan.work
    ok = RefreshRig(tmp_path / "second")
    record = Path(ok.env.paths.record)
    record.write_text(json.dumps(dict(json.loads(record.read_text()), schema=99)))
    assert [(f.reason, f.fix) for f in rf.plan_repair(ok.look()).needs_more] == [("newer_record", "")]


def test_the_time_in_the_name_of_a_set_aside_note_is_utc_whatever_clock_was_given(rig):
    from datetime import timedelta
    path = Path(rf.note_path(rig.home, "window"))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("x")
    plus_two = datetime(2026, 10, 17, 12, 0, 0, tzinfo=timezone(timedelta(hours=2)))
    assert rf.set_aside(rig.home, "window", plus_two).endswith(".damaged-20261017-100000")


def test_with_no_folder_of_programs_at_all_nothing_is_old_and_nothing_is_left_alone(tmp_path):
    rig = RefreshRig(tmp_path, built=False)
    older = rf.older_copies(rig.home, [rig.spec], rig.env.ctx)
    assert older.copies == () and older.left_alone == 0


def test_a_link_with_the_name_of_a_copy_is_left_alone_even_when_what_it_points_to_is_a_whole_copy(rig):
    old = Path(rig.env.env_dir)
    elsewhere = Path(rig.home.root) / "elsewhere"
    shutil.copytree(old, elsewhere, symlinks=True)
    build_next(rig)
    envgen.write(rig.home, "demo", 1)
    record = json.loads((old / eb.RECORD_NAME).read_text())
    link = Path(rig.home.environments) / ("demo-" + record["fingerprint"][:10])
    shutil.rmtree(old)
    os.symlink(str(elsewhere), str(link))
    older = rf.older_copies(rig.home, [rig.spec], rig.env.ctx)
    assert older.copies == () and older.left_alone == 1 and elsewhere.is_dir()


def test_a_folder_with_the_name_and_record_of_programs_this_tool_is_not_asked_about_is_left_alone(rig):
    other = Path(rig.home.environments) / "other-0123456789"
    other.mkdir()
    (other / eb.RECORD_NAME).write_text(json.dumps({"schema": 1, "id": "other", "fingerprint": "0123456789" + "a" * 54, "steps": {}, "patches": {}, "state": "ready"}))
    older = rf.older_copies(rig.home, [rig.spec], rig.env.ctx)
    assert older.copies == () and older.left_alone == 1 and other.is_dir()


def test_what_a_copy_takes_counts_plain_files_only_and_never_follows_a_link(rig, tmp_path):
    old = Path(rig.env.env_dir)
    base_size, base_files = rf._tree(str(old))
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "big.bin").write_bytes(b"x" * 5000)
    (old / "link-to-a-file").symlink_to(outside / "big.bin")
    (old / "link-to-a-folder").symlink_to(outside)
    (old / "plain.txt").write_bytes(b"y" * 10)
    assert rf._tree(str(old)) == (base_size + 10, base_files + 1)


def test_copies_are_listed_in_the_order_of_their_names_whatever_order_the_disk_gives(rig, monkeypatch):
    build_next(rig, 1)
    build_next(rig, 2)
    envgen.write(rig.home, "demo", 2)
    real = os.listdir
    monkeypatch.setattr(os, "listdir", lambda path: list(reversed(real(path))) if str(path) == rig.home.environments else real(path))
    names = [c.folder for c in rf.older_copies(rig.home, [rig.spec], rig.env.ctx).copies]
    assert names == sorted(names) and len(names) == 2


@pytest.mark.parametrize("status", ["starting", "running", "stopping"])
def test_a_task_that_is_starting_running_or_stopping_each_stops_the_removal(rig, status):
    old, new = two_copies(rig)
    shown = rf.older_copies(rig.home, [rig.spec], rig.env.ctx).copies
    os.makedirs(rig.home.jobs, exist_ok=True)
    fake_job(rig.home.jobs, ["x"], status, project="voice-check")
    assert code_of(rf.remove_older, rig.home, [rig.spec], rig.env.ctx, shown) == "job_running" and os.path.isdir(old)


def test_a_copy_swapped_for_a_file_after_the_list_was_made_is_not_removed_and_is_said_not_to_be_an_old_copy(rig):
    old, new = two_copies(rig)
    shown = rf.older_copies(rig.home, [rig.spec], rig.env.ctx).copies
    real = rf.older_copies

    def swapped(home, specs, ctx):
        found = real(home, specs, ctx)
        shutil.rmtree(old)
        Path(old).write_text("a file now")
        return found
    rf.older_copies = swapped
    try:
        result = rf.remove_older(rig.home, [rig.spec], rig.env.ctx, shown)
    finally:
        rf.older_copies = real
    assert result.removed == () and result.failed == ((old, "it is no longer an old copy"),) and Path(old).read_text() == "a file now"


def test_a_copy_that_the_second_look_says_is_now_the_one_in_use_is_not_removed(rig, monkeypatch):
    old, new = two_copies(rig)
    shown = rf.older_copies(rig.home, [rig.spec], rig.env.ctx).copies
    real = rf.older_copies
    monkeypatch.setattr(rf, "older_copies", lambda home, specs, ctx: rf.Older(real(home, specs, ctx).copies, 0, (old,)))
    result = rf.remove_older(rig.home, [rig.spec], rig.env.ctx, shown)
    assert result.removed == () and result.failed == ((old, "it is no longer an old copy"),) and os.path.isdir(old)


def test_the_room_that_comes_back_is_what_the_copies_take_when_they_are_removed_not_when_they_were_shown(rig):
    old, new = two_copies(rig)
    shown = rf.older_copies(rig.home, [rig.spec], rig.env.ctx).copies
    Path(old, "more.bin").write_bytes(b"z" * 7000)
    result = rf.remove_older(rig.home, [rig.spec], rig.env.ctx, shown)
    assert result.bytes == shown[0].bytes + 7000 and [c.bytes for c in result.removed] == [shown[0].bytes + 7000]

