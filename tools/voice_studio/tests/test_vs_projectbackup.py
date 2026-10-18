# SPDX-License-Identifier: GPL-3.0-or-later
"""Backup now (plan task VS-6.1, decision P17): what a backup holds and leaves out, the few shapes of name it will ever write or read, the room and the destination, that an archive is
read back before it counts, that nothing earlier is ever touched, and the additive way back. Every test works on real files in a real folder."""
import errno
import hashlib
import io
import json
import os
import stat
import tarfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from vs_backup_helpers import CODE, TAKE, BackupRig, forge
from vs_listen_helpers import VOICE_FOLDER
from vs_rounds_helpers import write_checkpoint
from voice_studio.core import projectbackup as pb, rounds as rd
from voice_studio.core.diskbudget import Level
from voice_studio.core.paths import DataHome, ProjectPaths
from voice_studio.core.project import load_project

NOW = datetime(2026, 10, 16, 9, 30, 0, tzinfo=timezone.utc)
PATHS = ProjectPaths("/h/ack-voice-studio/projects/anna")
TAKE1 = TAKE % (1, 1)


@pytest.fixture
def rig(tmp_path):
    return BackupRig(tmp_path)


def code_of(fn, *a, **kw):
    with pytest.raises(pb.BackupError) as caught:
        fn(*a, **kw)
    return caught.value.code


# ---------------------------------------------------------------- the few names a backup holds

GOOD = [
    ("project/project.json", "record", PATHS.root + "/project.json"),
    ("project/project.json.previous", "record", PATHS.root + "/project.json.previous"),
    ("recordings/takes/%s/raw.webm" % TAKE1, "recordings", PATHS.recordings + "/_freeform/en-US/takes/%s/raw.webm" % TAKE1),
    ("recordings/takes/%s/take.json" % TAKE1, "recordings", PATHS.recordings + "/_freeform/en-US/takes/%s/take.json" % TAKE1),
    ("recordings/takes/%s/edit_history/edit-1.json" % TAKE1, "recordings", PATHS.recordings + "/_freeform/en-US/takes/%s/edit_history/edit-1.json" % TAKE1),
    ("recordings/incoming/p.zip", "packages", PATHS.recordings + "/_freeform/en-US/incoming/p.zip"),
    ("recordings/incoming/Morning set 1.zip", "packages", PATHS.recordings + "/_freeform/en-US/incoming/Morning set 1.zip"),
    ("rounds/rounds.json", "rounds", PATHS.rounds + "/rounds.json"),
    ("rounds/rounds.json.previous", "rounds", PATHS.rounds + "/rounds.json.previous"),
    ("rounds/config/round-003.json", "rounds", PATHS.rounds + "/config/round-003.json"),
    ("rounds/config/round-123456.json", "rounds", PATHS.rounds + "/config/round-123456.json"),
    ("rounds/run/lightning_logs/version_0/checkpoints/last.ckpt", "saved_points", PATHS.run + "/lightning_logs/version_0/checkpoints/last.ckpt"),
    ("rounds/run/lightning_logs/version_12/checkpoints/epoch=3-step=40.ckpt", "saved_points", PATHS.run + "/lightning_logs/version_12/checkpoints/epoch=3-step=40.ckpt"),
    ("exports/voice-a-round-001/voice-a-round-001.zip", "exports", PATHS.exports + "/voice-a-round-001/voice-a-round-001.zip"),
]
BAD = [
    "", "x", "/etc/passwd", "../x", "project/../x", "project/../../x", "project//project.json", "project/project.json/x", "project/Project.json", "project/sub/project.json", "project",
    "a\\b", "project/project.json\0", "project\\project.json", "recordings", "recordings/takes", "recordings/takes/%s" % TAKE1, "recordings/takes/t1/raw.webm",
    "recordings/takes/%s/raw.mp3" % TAKE1, "recordings/takes/%s/../../x" % TAKE1, "recordings/takes/%s/parts/../raw.webm" % TAKE1, "recordings/takes/%s/edit_history/a/b.json" % TAKE1,
    "recordings/takes/%s/edit_history/.hidden" % TAKE1, "recordings/takes/%s/token" % TAKE1, "recordings/token", "recordings/incoming/../x.zip", "recordings/incoming/.p.zip",
    "recordings/incoming/p.txt", "recordings/incoming/a/p.zip", "recordings/incoming/" + "x" * 200 + ".zip", "rounds/rounds.json.bak", "rounds/config/round-1.json", "rounds/config/round-001.json.bak",
    "rounds/config/sub/round-001.json", "rounds/config/round-1234567.json", "rounds/run/lightning_logs/version_x/checkpoints/last.ckpt",
    "rounds/run/lightning_logs/version_0/checkpoints/last.ckpt.bak", "rounds/run/lightning_logs/version_0/checkpoints/../x.ckpt", "rounds/run/lightning_logs/version_0/other/last.ckpt",
    "rounds/run/lightning_logs/version_0/events.out.tfevents", "rounds/run/lightning_logs/version_0/checkpoints/a/last.ckpt", "rounds/run/other/version_0/checkpoints/last.ckpt",
    "rounds/run/lightning_logs/version_1234567/checkpoints/last.ckpt", "exports/a/b.zip", "exports/a/a.zip.bak", "exports/../a/a.zip", "exports/a/a.zip/x", "exports/.hid/.hid.zip",
    "exports/a b/a b.zip", "exports/a", "scratch/datasets/d/a.wav", "listening/round-001/heard-1/clip-1.wav", "MANIFEST.json", "MANIFEST.json/x", "tool/x",
]


@pytest.mark.parametrize("name, part, dest", GOOD)
def test_a_name_a_backup_holds_says_where_it_belongs_in_the_project(name, part, dest):
    found = pb.member_target(PATHS, name)
    assert found == pb.Member(part, dest) and found.dest.startswith(PATHS.root + "/")


@pytest.mark.parametrize("name", BAD)
def test_any_other_name_is_not_held_or_written_for(name):
    assert pb.member_target(PATHS, name) is None


def test_no_name_that_is_held_can_lead_outside_the_project():
    for name, _part, _dest in GOOD:
        dest = pb.member_target(PATHS, name).dest
        assert os.path.normpath(dest) == dest and dest.startswith(PATHS.root + "/")


def test_every_part_belongs_to_a_backed_up_area_and_every_such_area_has_a_part():
    from voice_studio.core import areas
    backed = {a.id for a in areas.PROJECT_AREAS if a.backed_up}
    assert {pb.PART_AREA[p] for p in pb.PARTS} == backed and set(pb.PART_AREA) == set(pb.PARTS)


# ---------------------------------------------------------------- what is held

def test_everything_precious_is_held_with_the_name_a_restore_will_read(rig):
    items, skipped = pb.collect(rig.paths)
    assert skipped == ()
    parts = {i.part for i in items}
    assert parts == set(pb.PARTS)
    for item in items:
        assert pb.member_target(rig.paths, item.name) == pb.Member(item.part, item.source), item.name
    assert [i.name for i in items if i.part == "exports"] == ["exports/%s/%s.zip" % (VOICE_FOLDER, VOICE_FOLDER)]
    assert sorted(i.name for i in items if i.part == "packages") == ["recordings/incoming/p.zip"]
    assert sum(1 for i in items if i.part == "saved_points") == 2 and sum(1 for i in items if i.part == "record") == 1


def test_the_rebuildable_and_the_disposable_and_the_secrets_are_left_out(rig):
    names = {i.name for i in pb.collect(rig.paths)[0]}
    assert not [n for n in names if "audio.wav" in n or n.endswith("/token") or "scratch" in n or "listening" in n or "clip-1" in n or "datasets" in n]
    assert not [n for n in names if n.endswith(".onnx") or ".before-patch" in n]                      # only the finished zip of a voice file, not the three files that made it


def test_only_the_kept_saved_points_are_held_and_not_the_older_ones(rig):
    held = [i.name for i in pb.collect(rig.paths)[0] if i.part == "saved_points"]
    kept = {"rounds/run/lightning_logs/version_%d/checkpoints/last.ckpt" % v for v in (0, 1)}
    assert set(held) == kept
    retention = rd.retention(rig.paths, rd.load(rig.paths))
    assert retention.spare and not {f.path for _n, f in retention.spare} & {i.source for i in pb.collect(rig.paths)[0]}


def test_saved_points_can_be_left_out_and_nothing_else_changes(rig):
    with_points = pb.collect(rig.paths, saved_points=True)[0]
    without = pb.collect(rig.paths, saved_points=False)[0]
    assert [i for i in with_points if i.part != "saved_points"] == list(without)


def test_a_saved_point_that_is_not_whole_is_left_out_and_said(rig):
    path = next(i.source for i in pb.collect(rig.paths)[0] if i.part == "saved_points")
    write_checkpoint(path, whole=False)
    items, skipped = pb.collect(rig.paths)
    assert [s.reason for s in skipped] == ["not_whole"] and skipped[0].name.endswith("last.ckpt") and path not in {i.source for i in items}


def test_a_link_where_a_file_should_be_is_never_followed(rig, tmp_path):
    secret = tmp_path / "secret.txt"
    secret.write_text("secret")
    target = rig.recordings_root / "takes" / TAKE1 / "asr.json"
    target.unlink()
    target.symlink_to(secret)
    link_package = rig.recordings_root / "incoming" / "evil.zip"
    link_package.symlink_to(secret)
    items, skipped = pb.collect(rig.paths)
    assert not [i for i in items if i.source in (str(target), str(link_package))] and secret.read_text() == "secret"
    assert {s.name for s in skipped} >= {"recordings/incoming/evil.zip"}


def test_a_recordings_folder_that_is_a_link_to_another_drive_is_read_because_it_is_the_persons_own_data(rig, tmp_path):
    """Recordings may have been moved to a bigger drive and linked back. Leaving them out of a backup without a word would lose the one thing that cannot be made again, so the
    folder is followed (as Freeform Studio itself does); a link for any *file* in it is still never followed."""
    outside = tmp_path / "elsewhere"
    os.rename(str(rig.recordings_root / "takes"), str(outside))
    (rig.recordings_root / "takes").symlink_to(outside)
    stray = tmp_path / "stray.json"
    stray.write_text("not a recording")
    (outside / TAKE1 / "asr.json").unlink()
    (outside / TAKE1 / "asr.json").symlink_to(stray)
    held = [i.name for i in pb.collect(rig.paths)[0] if i.part == "recordings"]
    assert "recordings/takes/%s/raw.webm" % TAKE1 in held and "recordings/takes/%s/asr.json" % TAKE1 not in held


def test_a_project_with_only_its_record_still_has_something_to_hold(tmp_path):
    rig = BackupRig(tmp_path, rounds=0, voice=False, takes=0, package=False, junk=False)
    items, _skipped = pb.collect(rig.paths)
    assert [i.name for i in items] == ["project/project.json"]


def test_nothing_at_all_is_nothing_to_back_up(tmp_path):
    rig = BackupRig(tmp_path, rounds=0, voice=False, takes=0, package=False, junk=False)
    os.unlink(rig.paths.project_json)
    assert code_of(rig.project_plan) == "nothing_to_back_up"


def test_a_damaged_record_of_rounds_is_noticed_and_not_copied_over_a_good_backup(rig):
    Path(rig.paths.rounds_file).write_text("not json at all")
    with pytest.raises(rd.RoundsError):
        pb.collect(rig.paths)


def test_the_order_is_fixed_and_the_fingerprint_follows_the_files(rig):
    first = pb.collect(rig.paths)[0]
    assert first == pb.collect(rig.paths)[0] and [i.part for i in first] == sorted((i.part for i in first), key=pb.PARTS.index)
    before = pb.fingerprint(first)
    assert before == pb.fingerprint(pb.collect(rig.paths)[0])
    raw = rig.recordings_root / "takes" / TAKE1 / "raw.webm"
    raw.write_bytes(b"changed!" * 100)
    assert pb.fingerprint(pb.collect(rig.paths)[0]) != before
    rig.take(7)
    assert pb.fingerprint(pb.collect(rig.paths)[0]) != before


def test_the_fingerprint_does_not_change_when_only_what_is_left_out_changes(rig):
    before = pb.fingerprint(pb.collect(rig.paths)[0])
    Path(rig.paths.default_scratch, "datasets", "d1", "wav", "b.wav").write_bytes(b"new")
    Path(rig.paths.listening, "round-001", "heard-20261011-120000", "clip-2.wav").write_bytes(b"new")
    (rig.recordings_root / "takes" / TAKE1 / "audio.wav").write_bytes(b"decoded again")
    assert pb.fingerprint(pb.collect(rig.paths)[0]) == before


def test_the_size_estimate_is_never_less_than_the_archive(rig):
    plan = rig.project_plan()
    made = pb.create(plan, rig.paths, NOW)
    assert made.archive_bytes <= pb.archive_size(plan.items)


# ---------------------------------------------------------------- the plan, the destination and the room

def test_the_plan_adds_up_what_is_held_and_names_what_is_left_out(rig):
    plan = rig.project_plan()
    items, _ = pb.collect(rig.paths)
    assert plan.source_bytes == sum(i.size for i in items) and {p.part for p in plan.parts} == set(pb.PARTS)
    assert {p.part: (p.files, p.bytes) for p in plan.parts}["recordings"] == (10, 6256)
    assert {(l.id) for l in plan.left_out} == {"scratch", "listening", "older_saved_points"} and all(l.bytes > 0 for l in plan.left_out)
    assert plan.destination == rig.dest and plan.project_id == "voice-check" and plan.fingerprint == pb.fingerprint(items) and plan.saved_points


def test_leaving_the_saved_points_out_is_said_as_left_out(rig):
    plan = rig.project_plan(saved_points=False)
    assert "saved_points" in {l.id for l in plan.left_out} and "saved_points" not in {p.part for p in plan.parts} and not plan.saved_points
    assert "saved_points" not in {l.id for l in rig.project_plan().left_out}


def test_nothing_is_said_to_be_left_out_that_is_not_there(tmp_path):
    rig = BackupRig(tmp_path, junk=False, rounds=0, voice=False)
    assert rig.project_plan().left_out == ()


def test_planning_writes_nothing_not_even_the_folder(rig):
    before = rig.tree(rig.paths.root)
    rig.project_plan()
    assert rig.tree(rig.paths.root) == before and not os.path.exists(rig.dest)


def test_the_room_needed_is_the_archive_and_a_margin_and_is_judged_on_the_drive_it_goes_to(rig):
    plan = rig.project_plan()
    assert plan.need_bytes == pb.archive_size(plan.items) + pb.SLACK and plan.same_drive
    assert rig.project_plan(free=10).room is Level.NOT_ENOUGH and rig.project_plan(free=None).room is Level.ENOUGH


def test_on_another_drive_the_archive_and_a_margin_must_fit_with_no_in_between():
    need = 5 * 1024 ** 3
    assert pb.judge_room(need + pb.REMOTE_MARGIN, need, False) is Level.ENOUGH
    assert pb.judge_room(need + pb.REMOTE_MARGIN - 1, need, False) is Level.NOT_ENOUGH
    assert pb.judge_room(None, need, False) is Level.ENOUGH and pb.judge_room(0, 0, False) is Level.NOT_ENOUGH


def test_on_the_projects_own_drive_the_usual_floors_apply():
    from voice_studio.core.diskbudget import DEFAULT_TABLE, floors_for
    floors = floors_for(DEFAULT_TABLE, holds_recordings=True)
    need = 1024 ** 3
    assert pb.judge_room(need + floors.low, need, True) is Level.ENOUGH
    assert pb.judge_room(need + floors.low - 1, need, True) is Level.TIGHT
    assert pb.judge_room(need + floors.stop, need, True) is Level.TIGHT
    assert pb.judge_room(need + floors.stop - 1, need, True) is Level.NOT_ENOUGH


@pytest.mark.parametrize("destination", ["", "backups", "~/backups", "./b", "../b"])
def test_a_destination_that_is_not_given_in_full_is_refused(rig, destination):
    assert code_of(rig.project_plan, destination=destination) == "bad_destination"


def test_a_destination_inside_the_project_or_the_projects_folder_is_refused(rig):
    for inside in (rig.paths.root, rig.paths.root + "/exports", rig.paths.root + "/new-folder", rig.home.projects, rig.home.projects + "/another", rig.paths.root + "/../voice-check/x"):
        assert code_of(rig.project_plan, destination=inside) == "inside_project", inside


def test_a_link_into_the_project_is_seen_through(rig, tmp_path):
    link = tmp_path / "innocent"
    link.symlink_to(rig.paths.exports)
    assert code_of(rig.project_plan, destination=str(link / "sub")) == "inside_project"


def test_a_destination_that_is_a_file_or_a_link_or_under_a_file_is_refused(rig, tmp_path):
    afile = tmp_path / "afile"
    afile.write_text("x")
    folder = tmp_path / "realfolder"
    folder.mkdir()
    link = tmp_path / "linkfolder"
    link.symlink_to(folder)
    for bad in (afile, link, afile / "sub", afile / "sub" / "deeper"):
        assert code_of(rig.project_plan, destination=str(bad)) == "not_a_folder", bad
    assert rig.project_plan(destination=str(folder)).destination == str(folder)


def test_a_folder_that_is_not_there_yet_is_fine_and_the_name_is_cleaned(rig, tmp_path):
    plan = rig.project_plan(destination=str(tmp_path) + "/a/./b//c/")
    assert plan.destination == str(tmp_path / "a" / "b" / "c")


def test_a_folder_that_looks_cloud_synced_is_flagged_in_freeform_studios_words(rig, tmp_path):
    plan = rig.project_plan(destination=str(tmp_path / "OneDrive" / "Backups"))
    assert plan.sync_warning and "OneDrive" in plan.sync_warning and "may be uploaded" in plan.sync_warning
    assert rig.project_plan().sync_warning is None


# ---------------------------------------------------------------- making one

def members_of(path):
    with tarfile.open(path, "r:") as tar:
        return {m.name: tar.extractfile(m).read() for m in tar if m.isfile()}


def test_a_backup_is_one_tar_that_holds_exactly_the_planned_files_and_a_manifest_last(rig):
    made = rig.backup(NOW)
    assert made.name == "ack-project-backup-voice-check-20261016-093000.tar" and os.path.dirname(made.path) == rig.dest
    with tarfile.open(made.path, "r:") as tar:
        names = [m.name for m in tar]
    items, _ = pb.collect(rig.paths)
    assert names == [i.name for i in items] + [pb.MANIFEST] and made.files == len(items)
    got = members_of(made.path)
    for item in items:
        assert got[item.name] == Path(item.source).read_bytes(), item.name


def test_the_manifest_lists_every_file_with_its_size_and_checksum(rig):
    made = rig.backup(NOW)
    manifest = json.loads(members_of(made.path)[pb.MANIFEST])
    assert manifest["schema"] == 1 and manifest["project"] == "voice-check" and manifest["created"] == "2026-10-16T09:30:00+00:00" and manifest["app"] == "ack-voice-studio"
    items, _ = pb.collect(rig.paths)
    assert [e["path"] for e in manifest["files"]] == [i.name for i in items]
    for entry, item in zip(manifest["files"], items):
        data = Path(item.source).read_bytes()
        assert (entry["size"], entry["sha256"], entry["part"]) == (len(data), hashlib.sha256(data).hexdigest(), item.part)


def test_a_new_backup_reads_back_clean(rig):
    made = rig.backup(NOW)
    problems, manifest = pb.verify(made.path)
    assert problems == [] and manifest["project"] == "voice-check"


def test_the_made_backup_says_what_it_holds_and_how_big(rig):
    made = rig.backup(NOW)
    assert made.archive_bytes == os.stat(made.path).st_size and made.source_bytes == sum(i.size for i in pb.collect(rig.paths)[0]) and made.created == "2026-10-16T09:30:00+00:00"
    assert {p.part for p in made.parts} == set(pb.PARTS) and made.fingerprint == pb.fingerprint(pb.collect(rig.paths)[0])


def test_the_files_are_for_their_owner_only(rig):
    made = rig.backup(NOW)
    assert stat.S_IMODE(os.stat(made.path).st_mode) == 0o600 and stat.S_IMODE(os.stat(made.path + ".json").st_mode) & 0o077 == 0
    assert stat.S_IMODE(os.stat(rig.dest).st_mode) == 0o700


def test_the_folder_is_made_if_it_is_not_there_and_nothing_is_left_beside_the_backup(rig):
    made = rig.backup(NOW)
    assert sorted(os.listdir(rig.dest)) == [made.name, made.name + ".json"]


def test_the_note_beside_a_backup_is_small_and_has_no_names_of_files(rig):
    made = rig.backup(NOW)
    note = json.loads(Path(made.path + ".json").read_text())
    assert note["project"] == "voice-check" and note["files"] == made.files and note["archive_bytes"] == made.archive_bytes and note["created"] == made.created
    assert "raw.webm" not in json.dumps(note)


def test_a_second_backup_is_a_new_file_even_in_the_same_second_and_the_first_is_untouched(rig):
    first = rig.backup(NOW)
    before = Path(first.path).read_bytes()
    second = rig.backup(NOW)
    third = rig.backup(NOW)
    assert (second.name, third.name) == ("ack-project-backup-voice-check-20261016-093000-2.tar", "ack-project-backup-voice-check-20261016-093000-3.tar")
    assert Path(first.path).read_bytes() == before and len(os.listdir(rig.dest)) == 6


def test_nothing_in_the_project_is_changed_by_a_backup(rig):
    before = rig.tree()
    rig.backup(NOW)
    assert rig.tree() == before


def test_a_backup_made_from_the_files_as_they_are_now_includes_a_recording_added_after_the_plan(rig):
    plan = rig.project_plan()
    rig.take(8)
    made = pb.create(plan, rig.paths, NOW)
    assert any("t20260930-000008-0008" in n for n in members_of(made.path))


def test_progress_is_told_per_file_with_the_part_and_the_bytes_so_far(rig):
    seen = []
    pb.create(rig.project_plan(), rig.paths, NOW, lambda part, done, total: seen.append((part, done, total)))
    assert seen[-1][1] == seen[-1][2] == sum(i.size for i in pb.collect(rig.paths)[0]) and [s[0] for s in seen][:1] == ["record"]
    assert all(a[1] <= b[1] for a, b in zip(seen, seen[1:]))


def test_the_backup_can_be_taken_with_no_saved_points(rig):
    made = rig.backup(NOW, saved_points=False)
    assert not [n for n in members_of(made.path) if n.endswith(".ckpt")] and made.archive_bytes < rig.backup(NOW).archive_bytes


def test_a_project_with_nothing_to_hold_makes_no_folder(tmp_path):
    rig = BackupRig(tmp_path, rounds=0, voice=False, takes=0, package=False, junk=False)
    plan = rig.project_plan()
    os.unlink(rig.paths.project_json)
    assert code_of(pb.create, plan, rig.paths, NOW) == "nothing_to_back_up" and not os.path.exists(rig.dest)


# ---------------------------------------------------------------- when making one goes wrong

def leftovers(rig):
    return sorted(os.listdir(rig.dest)) if os.path.isdir(rig.dest) else []


@pytest.mark.parametrize("small", [16 * 1024 * 1024, 10])                      # a file read whole, and a file streamed
def test_a_file_that_is_written_to_while_it_is_read_stops_the_backup_and_keeps_nothing(rig, monkeypatch, small):
    monkeypatch.setattr(pb, "SMALL", small)
    target = rig.recordings_root / "takes" / TAKE1 / "raw.webm"
    real = tarfile.TarFile.addfile

    def addfile(self, tarinfo, fileobj=None):
        result = real(self, tarinfo, fileobj)
        if tarinfo.name.endswith(TAKE1 + "/raw.webm"):
            target.write_bytes(b"CHANGED" * 40)                                  # written after it was read, before the check that it did not change
        return result
    monkeypatch.setattr(tarfile.TarFile, "addfile", addfile)
    with pytest.raises(pb.BackupError) as caught:
        pb.create(rig.project_plan(), rig.paths, NOW)
    assert caught.value.code == "changed" and TAKE1 in caught.value.detail and leftovers(rig) == []


def test_a_file_that_shrinks_while_it_is_streamed_is_a_change_and_not_a_failed_drive(rig, monkeypatch):
    monkeypatch.setattr(pb, "SMALL", 10)
    target = rig.recordings_root / "takes" / TAKE1 / "raw.webm"
    real = pb._Hashing.read
    state = {"done": False}

    def read(self, n=-1):
        if not state["done"] and os.fstat(self._handle.fileno()).st_ino == os.stat(target).st_ino:
            state["done"] = True
            os.truncate(str(target), 5)
        return real(self, n)
    monkeypatch.setattr(pb._Hashing, "read", read)
    with pytest.raises(pb.BackupError) as caught:
        pb.create(rig.project_plan(), rig.paths, NOW)
    assert caught.value.code == "changed" and leftovers(rig) == []


def test_a_file_changed_between_the_plan_and_the_backup_is_taken_as_it_is_then(rig):
    plan = rig.project_plan()
    target = rig.recordings_root / "takes" / TAKE1 / "raw.webm"
    target.write_bytes(b"NEWER" * 50)
    made = pb.create(plan, rig.paths, NOW)
    assert members_of(made.path)["recordings/takes/%s/raw.webm" % TAKE1] == b"NEWER" * 50 and pb.verify(made.path)[0] == []


@pytest.mark.parametrize("small", [16 * 1024 * 1024, 10])
def test_big_and_small_files_are_stored_and_checked_the_same_way(rig, monkeypatch, small):
    monkeypatch.setattr(pb, "SMALL", small)
    made = rig.backup(NOW)
    assert pb.verify(made.path)[0] == [] and members_of(made.path)["recordings/takes/%s/raw.webm" % TAKE1] == (rig.recordings_root / "takes" / TAKE1 / "raw.webm").read_bytes()


def test_a_file_swapped_for_a_link_after_it_was_listed_is_refused(rig, tmp_path):
    items, _ = pb.collect(rig.paths)
    plan = rig.project_plan()
    victim = Path(next(i.source for i in items if i.name.endswith("take.json")))
    secret = tmp_path / "secret"
    secret.write_text("secret")
    real = pb.collect

    def swapped(paths, record=None, saved_points=True):
        result = real(paths, record, saved_points)
        victim.unlink()
        victim.symlink_to(secret)
        return result
    pb.collect = swapped
    try:
        with pytest.raises(pb.BackupError) as caught:
            pb.create(plan, rig.paths, NOW)
    finally:
        pb.collect = real
    assert caught.value.code == "changed" and leftovers(rig) == []


def test_a_full_drive_stops_it_with_no_partial_left(rig, monkeypatch):
    real = tarfile.TarFile.addfile
    calls = {"n": 0}

    def addfile(self, tarinfo, fileobj=None):
        calls["n"] += 1
        if calls["n"] == 3:
            raise OSError(errno.ENOSPC, "No space left on device")
        return real(self, tarinfo, fileobj)
    monkeypatch.setattr(tarfile.TarFile, "addfile", addfile)
    assert code_of(pb.create, rig.project_plan(), rig.paths, NOW) == "no_room" and leftovers(rig) == []


def test_any_other_failure_to_write_is_named_and_leaves_nothing(rig, monkeypatch):
    real = tarfile.TarFile.addfile

    def addfile(self, tarinfo, fileobj=None):
        raise OSError(errno.EIO, "Input/output error")
    monkeypatch.setattr(tarfile.TarFile, "addfile", addfile)
    with pytest.raises(pb.BackupError) as caught:
        pb.create(rig.project_plan(), rig.paths, NOW)
    assert caught.value.code == "write_failed" and "Input/output error" in caught.value.detail and leftovers(rig) == []


def test_an_archive_that_does_not_read_back_is_thrown_away_and_never_given_its_name(rig, monkeypatch):
    monkeypatch.setattr(pb, "verify", lambda path, check_names=True: (["x/raw.webm: does not match its checksum"], None))
    with pytest.raises(pb.BackupError) as caught:
        pb.create(rig.project_plan(), rig.paths, NOW)
    assert caught.value.code == "not_read_back" and caught.value.problems == ("x/raw.webm: does not match its checksum",) and leftovers(rig) == []


def test_a_stop_in_the_middle_removes_the_partial_and_is_not_swallowed(rig):
    def stop(part, done, total):
        raise KeyboardInterrupt()
    with pytest.raises(KeyboardInterrupt):
        pb.create(rig.project_plan(), rig.paths, NOW, stop)
    assert leftovers(rig) == []


def test_another_backup_running_in_the_same_folder_is_waited_for_not_mixed_with(rig):
    os.makedirs(rig.dest)
    Path(rig.dest, pb.LOCK).write_text("12345")
    with pytest.raises(pb.BackupError) as caught:
        pb.create(rig.project_plan(), rig.paths, NOW)
    assert caught.value.code == "busy" and Path(rig.dest, pb.LOCK).exists() and [n for n in leftovers(rig) if n != pb.LOCK] == []


def test_a_lock_left_by_a_crash_hours_ago_is_replaced(rig):
    os.makedirs(rig.dest)
    lock = Path(rig.dest, pb.LOCK)
    lock.write_text("12345")
    old = datetime.now().timestamp() - pb.STALE_LOCK_S - 60
    os.utime(lock, (old, old))
    made = rig.backup(NOW)
    assert os.path.isfile(made.path) and not lock.exists()


def test_the_lock_is_released_after_a_good_backup_and_after_a_bad_one(rig, monkeypatch):
    rig.backup(NOW)
    assert not Path(rig.dest, pb.LOCK).exists()
    monkeypatch.setattr(pb, "verify", lambda path, check_names=True: (["bad"], None))
    with pytest.raises(pb.BackupError):
        pb.create(rig.project_plan(), rig.paths, NOW)
    assert not Path(rig.dest, pb.LOCK).exists()


def test_a_note_that_cannot_be_written_does_not_undo_a_good_backup(rig, monkeypatch):
    def broken(path, obj):
        raise OSError(errno.EIO, "no")
    monkeypatch.setattr(pb, "atomic_write_json", broken)
    made = rig.backup(NOW)
    assert os.path.isfile(made.path) and pb.verify(made.path)[0] == [] and not os.path.exists(made.path + ".json")
    assert [b["name"] for b in pb.list_backups(rig.dest)] == [made.name]


def test_earlier_backups_are_never_pruned_replaced_or_removed(rig):
    names = []
    for minute in range(5):
        names.append(rig.backup(NOW + timedelta(minutes=minute)).name)
    assert sorted(n for n in os.listdir(rig.dest) if n.endswith(".tar")) == sorted(names)


# ---------------------------------------------------------------- reading one back (and refusing what is not one)

def edit_archive(path, changes):
    """Rewrite an archive with some members changed or dropped: {name: new bytes or None to drop}."""
    with tarfile.open(path, "r:") as tar:
        members = [(m, tar.extractfile(m).read() if m.isfile() else None) for m in tar]
    with open(path, "wb") as out, tarfile.open(fileobj=out, mode="w") as tar:
        for m, data in members:
            if m.name in changes:
                if changes[m.name] is None:
                    continue
                data = changes[m.name]
                m.size = len(data)
            tar.addfile(m, io.BytesIO(data) if data is not None else None)


def test_a_flipped_byte_is_found(rig):
    made = rig.backup(NOW)
    raw = bytearray(Path(made.path).read_bytes())
    at = raw.index(b"RAWRAWRAW")
    raw[at] ^= 0xFF
    Path(made.path).write_bytes(bytes(raw))
    problems, _ = pb.verify(made.path)
    assert len(problems) == 1 and problems[0].endswith("raw.webm: does not match its checksum")


def test_a_cut_short_archive_is_not_readable(rig):
    made = rig.backup(NOW)
    data = Path(made.path).read_bytes()
    Path(made.path).write_bytes(data[: len(data) // 2])
    problems, manifest = pb.verify(made.path)
    assert manifest is None and problems and "cannot be read" in problems[0] or any("no manifest" in p for p in problems)


def test_a_file_that_is_not_an_archive_is_not_readable(tmp_path):
    junk = tmp_path / "junk.tar"
    junk.write_bytes(b"this is not a tar file at all" * 100)
    problems, manifest = pb.verify(str(junk))
    assert manifest is None and problems


def test_a_missing_file_is_not_readable(tmp_path):
    problems, manifest = pb.verify(str(tmp_path / "nothing.tar"))
    assert manifest is None and problems


def test_a_dropped_member_is_listed_but_missing(rig):
    made = rig.backup(NOW)
    edit_archive(made.path, {"project/project.json": None})
    assert any(p == "project/project.json: listed but missing" for p in pb.verify(made.path)[0])


def test_a_member_not_in_the_manifest_is_found(rig, tmp_path):
    path = forge(tmp_path / "f.tar", [("project/project.json", b"{}")], manifest={"schema": 1, "project": "anna", "files": []})
    assert "project/project.json: in the archive but not in its manifest" in pb.verify(path)[0]


def test_a_changed_member_does_not_match_its_checksum(rig):
    made = rig.backup(NOW)
    edit_archive(made.path, {"rounds/rounds.json": b"{}"})
    assert any(p == "rounds/rounds.json: does not match its checksum" for p in pb.verify(made.path)[0])


def test_a_member_that_is_a_link_or_a_folder_is_refused(tmp_path):
    path = forge(tmp_path / "f.tar", [("project/project.json", b"{}"), ("rounds/rounds.json", b"", tarfile.SYMTYPE), ("rounds/config", b"", tarfile.DIRTYPE)])
    problems = pb.verify(path)[0]
    assert "rounds/rounds.json: not an ordinary file" in problems and "rounds/config: not an ordinary file" in problems


@pytest.mark.parametrize("name", ["../evil", "/etc/cron.d/evil", "project/../../evil", "scratch/x", "recordings/takes/x/raw.webm", "project\\project.json", "rounds/rounds.json/../x"])
def test_a_name_a_backup_never_holds_is_refused_even_when_the_manifest_lists_it(tmp_path, name):
    path = forge(tmp_path / "f.tar", [("project/project.json", b"{}"), (name, b"evil")])
    problems = pb.verify(path)[0]
    assert any("not something a backup holds" in p for p in problems)


def test_a_name_that_appears_twice_is_found(tmp_path):
    path = forge(tmp_path / "f.tar", [("project/project.json", b"{}"), ("project/project.json", b"{}")])
    assert any("appears more than once" in p for p in pb.verify(path)[0])


def test_an_archive_without_a_manifest_cannot_be_checked(tmp_path):
    path = forge(tmp_path / "f.tar", [("project/project.json", b"{}")], manifest=None)
    problems, manifest = pb.verify(path)
    assert manifest is None and "it has no manifest, so it cannot be checked" in problems


@pytest.mark.parametrize("body", [b"not json", b"[]", b"{}", b'{"schema": 2, "files": []}', b'{"schema": 1, "files": "x"}', b'{"schema": 1}'])
def test_a_manifest_this_version_does_not_read_is_refused(tmp_path, body):
    path = forge(tmp_path / "f.tar", [("project/project.json", b"{}")], manifest=body)
    problems, manifest = pb.verify(path)
    assert problems and (manifest is None or manifest.get("schema") != 1 or problems)


@pytest.mark.parametrize("project", ["", "../x", "A", "x" * 80, "a b", None, 5])
def test_a_manifest_that_does_not_name_a_project_this_tool_can_make_is_refused(tmp_path, project):
    path = forge(tmp_path / "f.tar", [("project/project.json", b"{}")], project=project)
    assert any("does not name a project" in p for p in pb.verify(path)[0])


def test_a_manifest_entry_that_is_not_understood_is_found(tmp_path):
    body = {"schema": 1, "project": "anna", "files": [{"path": 5}, {"path": "x", "size": "big", "sha256": "z"}, "text"]}
    problems = pb.verify(forge(tmp_path / "f.tar", [], manifest=body))[0]
    assert problems.count("the manifest has an entry that is not understood") == 3


def test_an_entry_listed_twice_is_found(tmp_path):
    entry = {"path": "project/project.json", "size": 2, "sha256": hashlib.sha256(b"{}").hexdigest()}
    path = forge(tmp_path / "f.tar", [("project/project.json", b"{}")], manifest={"schema": 1, "project": "anna", "files": [entry, entry]})
    assert "project/project.json: listed more than once" in pb.verify(path)[0]


def test_the_names_can_be_left_unchecked_for_a_caller_that_does_its_own(tmp_path):
    path = forge(tmp_path / "f.tar", [("project/project.json", b"{}"), ("odd/name", b"x")])
    assert pb.verify(path, check_names=False)[0] == [] and pb.verify(path, check_names=True)[0]


def test_too_many_members_stop_the_reading(tmp_path, monkeypatch):
    monkeypatch.setattr(pb, "MAX_MEMBERS", 2)
    path = forge(tmp_path / "f.tar", [("project/project.json", b"{}"), ("project/project.json.previous", b"{}"), ("rounds/rounds.json", b"{}")])
    assert "it holds more files than a backup can" in pb.verify(path)[0]


def test_a_member_larger_than_a_backup_holds_is_refused_without_reading_it(tmp_path, monkeypatch):
    monkeypatch.setattr(pb, "MAX_MEMBER_BYTES", 1)
    path = forge(tmp_path / "f.tar", [("project/project.json", b"{}")])
    assert any("larger than a backup holds" in p for p in pb.verify(path)[0])


# ---------------------------------------------------------------- listing

def test_the_backups_in_a_folder_are_listed_newest_first_with_what_the_note_says(rig):
    rig.backup(NOW)
    later = rig.backup(NOW + timedelta(days=2))
    listed = pb.list_backups(rig.dest)
    assert [b["name"] for b in listed][0] == later.name and len(listed) == 2
    assert listed[0]["created"] == "2026-10-18T09:30:00+00:00" and listed[0]["project"] == "voice-check" and listed[0]["files"] == later.files and listed[0]["size"] == later.archive_bytes


def test_only_files_this_tool_names_are_listed(rig):
    made = rig.backup(NOW)
    for name in ("notes.tar", "ack-project-backup-Voice-20261016-093000.tar", "ack-project-backup-x-2026.tar", made.name + ".partial", made.name + ".bak", "backup.zip", pb.LOCK):
        Path(rig.dest, name).write_bytes(b"x")
    os.mkdir(os.path.join(rig.dest, "ack-project-backup-folder-20261016-093000.tar"))
    Path(rig.dest, "ack-project-backup-link-20261016-093000.tar").symlink_to(made.path)
    assert [b["name"] for b in pb.list_backups(rig.dest)] == [made.name]


def test_a_backup_can_be_listed_by_project(rig, tmp_path):
    made = rig.backup(NOW)
    assert pb.list_backups(rig.dest, "voice-check") and pb.list_backups(rig.dest, "somebody-else") == []
    other = Path(rig.dest, "ack-project-backup-somebody-else-20261016-100000.tar")
    other.write_bytes(b"x")
    assert [b["project"] for b in pb.list_backups(rig.dest)] == ["somebody-else", "voice-check"] and [b["name"] for b in pb.list_backups(rig.dest, "voice-check")] == [made.name]


def test_a_missing_or_damaged_note_falls_back_to_the_time_in_the_name(rig):
    made = rig.backup(NOW)
    os.unlink(made.path + ".json")
    assert pb.list_backups(rig.dest)[0]["created"] == "2026-10-16T09:30:00" and pb.list_backups(rig.dest)[0]["files"] is None
    Path(made.path + ".json").write_text("not json")
    assert pb.list_backups(rig.dest)[0]["created"] == "2026-10-16T09:30:00"
    Path(made.path + ".json").write_text("[]")
    assert pb.list_backups(rig.dest)[0]["files"] is None
    Path(made.path + ".json").write_text('{"created": 5, "files": "many"}')
    assert pb.list_backups(rig.dest)[0]["created"] == "2026-10-16T09:30:00" and pb.list_backups(rig.dest)[0]["files"] is None


def test_a_folder_that_is_not_there_lists_nothing(tmp_path):
    assert pb.list_backups(str(tmp_path / "none")) == []


# ---------------------------------------------------------------- when each project was last backed up

def test_a_project_never_backed_up_reads_as_never(rig):
    standing = pb.standing(rig.home, rig.paths, "voice-check")
    assert standing == pb.Standing(pb.NEVER, "", "")


def test_after_a_backup_it_reads_as_current_until_something_precious_changes(rig):
    made = rig.backup(NOW)
    pb.record_backup(rig.home, made, "voice-check", rig.dest)
    assert pb.standing(rig.home, rig.paths, "voice-check") == pb.Standing(pb.CURRENT, "2026-10-16T09:30:00+00:00", rig.dest)
    (rig.recordings_root / "takes" / TAKE1 / "raw.webm").write_bytes(b"more audio" * 100)
    assert pb.standing(rig.home, rig.paths, "voice-check").state == pb.CHANGED
    Path(rig.paths.default_scratch, "datasets", "d1", "wav", "z.wav").write_bytes(b"x")
    rig.take(9)
    assert pb.standing(rig.home, rig.paths, "voice-check").state == pb.CHANGED


def test_what_is_left_out_of_a_backup_does_not_make_the_project_look_changed(rig):
    pb.record_backup(rig.home, rig.backup(NOW), "voice-check", rig.dest)
    Path(rig.paths.default_scratch, "datasets", "d1", "wav", "z.wav").write_bytes(b"x")
    (rig.recordings_root / "takes" / TAKE1 / "audio.wav").write_bytes(b"decoded differently")
    assert pb.standing(rig.home, rig.paths, "voice-check").state == pb.CURRENT


def test_a_project_with_nothing_to_lose_reads_as_current(rig):
    os.unlink(rig.paths.project_json)
    for entry in os.listdir(rig.paths.root):
        path = os.path.join(rig.paths.root, entry)
        if os.path.isdir(path):
            import shutil
            shutil.rmtree(path)
    assert pb.standing(rig.home, rig.paths, "voice-check").state == pb.CURRENT


def test_the_note_is_for_this_computer_one_project_at_a_time_and_private(rig):
    made = rig.backup(NOW)
    pb.record_backup(rig.home, made, "voice-check", rig.dest)
    pb.record_backup(rig.home, made, "another-one", "/somewhere/else")
    state = pb.read_state(rig.home)
    assert set(state) == {"voice-check", "another-one"} and state["another-one"]["folder"] == "/somewhere/else"
    path = rig.home.state + "/" + pb.STATE_FILE
    assert stat.S_IMODE(os.stat(path).st_mode) & 0o077 == 0 and "raw.webm" not in Path(path).read_text()


def test_the_state_folder_is_made_for_its_owner_only_when_it_is_not_there(rig, tmp_path):
    fresh = DataHome(str(tmp_path / "fresh-home"))
    pb.record_backup(fresh, rig.backup(NOW), "voice-check", rig.dest)
    assert stat.S_IMODE(os.stat(fresh.state).st_mode) & 0o077 == 0 and "voice-check" in pb.read_state(fresh)


def test_a_damaged_or_foreign_note_reads_as_nothing_known(rig):
    os.makedirs(rig.home.state, exist_ok=True)
    path = rig.home.state + "/" + pb.STATE_FILE
    for body in ("not json", "[]", '{"projects": []}', '{"projects": {"../x": {}, "ok-one": 5, "good": {"created": "now"}}}'):
        Path(path).write_text(body)
        assert set(pb.read_state(rig.home)) <= {"good"}
    Path(path).write_text('{"projects": {"voice-check": {"created": 5, "folder": 5, "fingerprint": "x"}}}')
    assert pb.standing(rig.home, rig.paths, "voice-check") == pb.Standing(pb.CHANGED, "", "")


def test_a_note_that_cannot_be_written_is_not_an_error(rig, monkeypatch):
    made = rig.backup(NOW)
    monkeypatch.setattr(pb, "atomic_write_json", lambda path, obj: (_ for _ in ()).throw(OSError(errno.EIO, "no")))
    pb.record_backup(rig.home, made, "voice-check", rig.dest)
    assert pb.read_state(rig.home) == {}


def test_the_note_is_not_part_of_what_a_backup_holds(rig):
    pb.record_backup(rig.home, rig.backup(NOW), "voice-check", rig.dest)
    assert not [i for i in pb.collect(rig.paths)[0] if "backups.json" in i.name or "state" in i.name]


# ---------------------------------------------------------------- the way back (additive)

import shutil


def held(rig):
    """{archive name: (destination, bytes)} of everything a backup of the project holds now."""
    return {i.name: (i.source, Path(i.source).read_bytes()) for i in pb.collect(rig.paths)[0]}


def restore_plan(rig, archive, free=10 ** 12):
    return pb.plan_restore(rig.home, archive, free)


def delete_project(rig):
    shutil.rmtree(rig.paths.root)


def test_a_project_that_was_deleted_is_made_again_from_its_backup_file_for_file(rig):
    made = rig.backup(NOW)
    before = held(rig)
    delete_project(rig)
    plan = restore_plan(rig, made.path)
    assert plan.new_project and plan.same == 0 and plan.conflicts == () and len(plan.add) == len(before) and plan.project_id == "voice-check" and plan.root == rig.paths.root
    result = pb.restore(rig.home, plan)
    assert (result.added, result.conflicts, result.failed) == (len(before), (), ()) and result.bytes == sum(len(d) for _s, d in before.values())
    for name, (source, data) in before.items():
        assert Path(source).read_bytes() == data, name
    assert load_project(rig.paths).id == "voice-check" and rd.load(rig.paths).current == 2


def test_after_a_restore_a_second_one_has_nothing_left_to_add(rig):
    made = rig.backup(NOW)
    delete_project(rig)
    pb.restore(rig.home, restore_plan(rig, made.path))
    again = restore_plan(rig, made.path)
    assert not again.new_project and again.add == () and again.conflicts == () and again.same == made.files


def test_into_a_project_that_is_there_only_what_is_missing_is_added(rig):
    made = rig.backup(NOW)
    gone = [rig.recordings_root / "takes" / TAKE1 / "raw.webm", Path(rig.paths.round_configs, "round-001.json")]
    for path in gone:
        path.unlink()
    plan = restore_plan(rig, made.path)
    assert not plan.new_project and {p.name for p in plan.add} == {"recordings/takes/%s/raw.webm" % TAKE1, "rounds/config/round-001.json"} and plan.same == made.files - 2
    result = pb.restore(rig.home, plan)
    assert result.added == 2 and all(p.exists() for p in gone)


def test_a_file_that_is_there_but_different_is_left_exactly_as_it_is_and_listed(rig):
    made = rig.backup(NOW)
    mine = rig.recordings_root / "takes" / TAKE1 / "edit.json"
    mine.write_text('{"edited": "since the backup"}')
    plan = restore_plan(rig, made.path)
    assert plan.conflicts == ("recordings/takes/%s/edit.json" % TAKE1,) and plan.add == ()
    result = pb.restore(rig.home, plan)
    assert result.added == 0 and mine.read_text() == '{"edited": "since the backup"}'


def test_files_in_the_project_that_the_backup_does_not_mention_are_never_touched(rig):
    made = rig.backup(NOW)
    rig.take(5)
    mine = Path(rig.paths.root, "my notes.txt")
    mine.write_text("mine")
    before = rig.tree()
    pb.restore(rig.home, restore_plan(rig, made.path))
    assert rig.tree() == before


def test_a_restore_writes_only_what_the_backup_holds(rig):
    made = rig.backup(NOW)
    expected = {i.source for i in pb.collect(rig.paths)[0]}
    delete_project(rig)
    pb.restore(rig.home, restore_plan(rig, made.path))
    written = {str(p) for p in Path(rig.paths.root).rglob("*") if p.is_file()}
    assert written - {rig.paths.rounds + "/.rounds.lock"} == expected


def test_a_link_where_a_file_belongs_is_a_conflict_and_what_it_points_to_is_untouched(rig, tmp_path):
    made = rig.backup(NOW)
    target = rig.recordings_root / "takes" / TAKE1 / "asr.json"
    outside = tmp_path / "outside.json"
    outside.write_text("outside")
    target.unlink()
    target.symlink_to(outside)
    plan = restore_plan(rig, made.path)
    assert "recordings/takes/%s/asr.json" % TAKE1 in plan.conflicts
    pb.restore(rig.home, plan)
    assert outside.read_text() == "outside" and target.is_symlink()


def test_planning_a_restore_changes_nothing(rig):
    made = rig.backup(NOW)
    (rig.recordings_root / "takes" / TAKE1 / "raw.webm").unlink()
    before = rig.tree()
    restore_plan(rig, made.path)
    assert rig.tree() == before


def test_restored_files_are_for_their_owner_only(rig):
    made = rig.backup(NOW)
    delete_project(rig)
    pb.restore(rig.home, restore_plan(rig, made.path))
    for path in Path(rig.paths.root).rglob("*"):
        if path.is_file():
            assert stat.S_IMODE(path.stat().st_mode) & 0o077 == 0, path
        elif path.is_dir():
            assert stat.S_IMODE(path.stat().st_mode) & 0o077 == 0, path


def test_no_temporary_file_is_left_behind(rig):
    made = rig.backup(NOW)
    delete_project(rig)
    pb.restore(rig.home, restore_plan(rig, made.path))
    assert not [p for p in Path(rig.paths.root).rglob("*") if p.name.startswith(".restore-")]


def test_the_projects_record_is_written_first_so_a_restore_that_stops_leaves_a_listed_project(rig, monkeypatch):
    made = rig.backup(NOW)
    delete_project(rig)
    plan = restore_plan(rig, made.path)
    real = pb._write_one

    def fails_after_the_record(tar, member, item):
        if item.part != "record":
            raise OSError(errno.EIO, "Input/output error")
        return real(tar, member, item)
    monkeypatch.setattr(pb, "_write_one", fails_after_the_record)
    result = pb.restore(rig.home, plan)
    assert result.added == 1 and len(result.failed) == len(plan.add) - 1 and load_project(rig.paths).id == "voice-check"
    monkeypatch.setattr(pb, "_write_one", real)
    again = restore_plan(rig, made.path)
    assert not again.new_project and again.same == 1 and len(again.add) == len(plan.add) - 1
    assert pb.restore(rig.home, again).failed == ()


def test_a_restore_that_stopped_at_its_first_file_can_be_run_again(rig):
    made = rig.backup(NOW)
    delete_project(rig)
    os.makedirs(rig.paths.root)
    plan = restore_plan(rig, made.path)
    assert plan.new_project
    assert pb.restore(rig.home, plan).failed == ()


def test_a_project_folder_that_has_something_in_it_but_no_record_is_not_a_project(rig):
    made = rig.backup(NOW)
    os.unlink(rig.paths.project_json)
    assert code_of(restore_plan, rig, made.path) == "not_a_project"


def test_a_project_folder_that_is_a_link_or_a_file_is_not_written_into(rig, tmp_path):
    made = rig.backup(NOW)
    delete_project(rig)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    os.symlink(str(elsewhere), rig.paths.root)
    assert code_of(restore_plan, rig, made.path) == "not_a_project" and os.listdir(elsewhere) == []
    os.unlink(rig.paths.root)
    Path(rig.paths.root).write_text("a file")
    assert code_of(restore_plan, rig, made.path) == "not_a_project"


def test_a_task_running_for_the_project_stops_a_restore_into_it(rig):
    from vs_rounds_helpers import fake_job
    made = rig.backup(NOW)
    fake_job(rig.home.jobs, ["x"], "running", project="voice-check")
    assert code_of(restore_plan, rig, made.path) == "job_running"
    delete_project(rig)
    assert restore_plan(rig, made.path).new_project, "a project that is not there has nothing running in it"


def test_a_task_for_another_project_does_not_stop_a_restore(rig):
    from vs_rounds_helpers import fake_job
    made = rig.backup(NOW)
    fake_job(rig.home.jobs, ["x"], "running", project="somebody-else")
    assert restore_plan(rig, made.path).project_id == "voice-check"


def test_a_backup_without_a_project_record_cannot_make_a_project(rig, tmp_path):
    path = forge(tmp_path / "f.tar", [("rounds/rounds.json", b"{}")], project="anna")
    assert code_of(pb.plan_restore, rig.home, path, 10 ** 12) == "not_a_backup"


def test_an_archive_that_is_not_whole_is_refused_with_what_is_wrong(rig):
    made = rig.backup(NOW)
    edit_archive(made.path, {"rounds/rounds.json": b"{}"})
    with pytest.raises(pb.BackupError) as caught:
        restore_plan(rig, made.path)
    assert caught.value.code == "damaged" and any("rounds/rounds.json: does not match its checksum" in p for p in caught.value.problems)


def test_an_archive_with_a_name_that_leaves_the_project_writes_nothing_anywhere(rig, tmp_path):
    escape = tmp_path / "escaped.txt"
    path = forge(tmp_path / "f.tar", [("project/project.json", b"{}"), ("../../../../escaped.txt", b"evil"), (str(escape), b"evil")], project="newcomer")
    assert code_of(pb.plan_restore, rig.home, path, 10 ** 12) == "damaged"
    assert not escape.exists() and not os.path.exists(rig.home.projects + "/newcomer")


def test_a_file_that_does_not_exist_or_is_a_link_is_not_a_backup_to_restore(rig, tmp_path):
    made = rig.backup(NOW)
    link = tmp_path / "link.tar"
    link.symlink_to(made.path)
    assert code_of(restore_plan, rig, str(tmp_path / "nothing.tar")) == "no_such_backup" and code_of(restore_plan, rig, str(link)) == "no_such_backup"


def test_without_the_room_nothing_is_written(rig):
    made = rig.backup(NOW)
    delete_project(rig)
    plan = restore_plan(rig, made.path, free=10)
    assert plan.room is Level.NOT_ENOUGH
    assert code_of(pb.restore, rig.home, plan) == "no_room" and not os.path.exists(rig.paths.root)


def test_nothing_to_add_needs_no_room(rig):
    made = rig.backup(NOW)
    assert restore_plan(rig, made.path, free=0).room is Level.ENOUGH


def test_an_archive_changed_since_the_plan_stops_the_restore(rig):
    made = rig.backup(NOW)
    delete_project(rig)
    plan = restore_plan(rig, made.path)
    edit_archive(made.path, {"rounds/rounds.json": b"{}"})
    with pytest.raises(pb.BackupError) as caught:
        pb.restore(rig.home, plan)
    assert caught.value.code in ("damaged", "changed") and not os.path.exists(rig.paths.root + "/recordings")


def test_a_project_that_changed_since_the_plan_stops_the_restore(rig):
    made = rig.backup(NOW)
    (rig.recordings_root / "takes" / TAKE1 / "raw.webm").unlink()
    plan = restore_plan(rig, made.path)
    (rig.recordings_root / "takes" / TAKE1 / "raw.webm").write_bytes(b"someone put something else here")
    assert code_of(pb.restore, rig.home, plan) == "changed"
    assert (rig.recordings_root / "takes" / TAKE1 / "raw.webm").read_bytes() == b"someone put something else here"


def test_progress_is_told_as_files_are_added(rig):
    made = rig.backup(NOW)
    delete_project(rig)
    seen = []
    plan = restore_plan(rig, made.path)
    pb.restore(rig.home, plan, lambda part, done, total: seen.append((part, done, total)))
    assert seen and seen[-1][1] == seen[-1][2] == plan.bytes_to_add and seen[0][0] == "record"


def test_the_plan_orders_the_record_first_and_then_by_part(rig):
    made = rig.backup(NOW)
    delete_project(rig)
    parts = [p.part for p in restore_plan(rig, made.path).add]
    assert parts[0] == "record" and parts == sorted(parts, key=pb.PARTS.index)


# ---- writing one file

def one_item(rig, tmp_path, data=b"hello", dest=None, name="project/project.json"):
    archive = forge(tmp_path / "one.tar", [(name, data)])
    plan = pb.Planned(name, "record", len(data), dest or str(tmp_path / "out" / "deeper" / "x.json"), hashlib.sha256(data).hexdigest())
    return archive, plan


def write_one(archive, planned):
    with tarfile.open(archive, "r:") as tar:
        return pb._write_one(tar, tar.getmember(planned.name), planned)


def test_one_file_is_written_beside_its_place_checked_and_then_given_its_name(rig, tmp_path):
    archive, planned = one_item(rig, tmp_path)
    assert write_one(archive, planned) == "added" and Path(planned.dest).read_bytes() == b"hello"
    assert os.listdir(os.path.dirname(planned.dest)) == ["x.json"] and stat.S_IMODE(os.stat(os.path.dirname(planned.dest)).st_mode) == 0o700


def test_a_file_in_the_way_is_never_replaced(rig, tmp_path):
    archive, planned = one_item(rig, tmp_path)
    os.makedirs(os.path.dirname(planned.dest))
    Path(planned.dest).write_text("mine")
    assert write_one(archive, planned) == "there" and Path(planned.dest).read_text() == "mine" and os.listdir(os.path.dirname(planned.dest)) == ["x.json"]


def test_a_file_that_appears_just_before_it_is_linked_into_place_is_not_replaced_either(rig, tmp_path, monkeypatch):
    archive, planned = one_item(rig, tmp_path)
    real = os.link

    def link(src, dst, *a, **k):
        Path(dst).write_text("appeared")
        return real(src, dst, *a, **k)
    monkeypatch.setattr(os, "link", link)
    assert write_one(archive, planned) == "there" and Path(planned.dest).read_text() == "appeared" and os.listdir(os.path.dirname(planned.dest)) == ["x.json"]


def test_bytes_that_do_not_match_the_manifest_are_not_put_in_place(rig, tmp_path):
    archive, planned = one_item(rig, tmp_path)
    bad = pb.Planned(planned.name, planned.part, planned.size, planned.dest, "0" * 64)
    assert "did not read back" in write_one(archive, bad) and not os.path.exists(planned.dest) and os.listdir(os.path.dirname(planned.dest)) == []
    short = pb.Planned(planned.name, planned.part, planned.size + 1, planned.dest, planned.sha256)
    assert "did not read back" in write_one(archive, short) and os.listdir(os.path.dirname(planned.dest)) == []


def test_where_links_cannot_be_made_the_file_is_still_written_and_still_not_replaced(rig, tmp_path, monkeypatch):
    archive, planned = one_item(rig, tmp_path)
    monkeypatch.setattr(os, "link", lambda *a, **k: (_ for _ in ()).throw(OSError(errno.EPERM, "no links here")))
    assert write_one(archive, planned) == "added" and Path(planned.dest).read_bytes() == b"hello" and os.listdir(os.path.dirname(planned.dest)) == ["x.json"]
    archive2, planned2 = one_item(rig, tmp_path, dest=str(tmp_path / "out" / "deeper" / "y.json"))
    real_lexists = os.path.lexists
    calls = {"n": 0}

    def lexists(path):
        calls["n"] += 1
        return real_lexists(path) or (str(path) == planned2.dest and calls["n"] > 1)
    monkeypatch.setattr(os.path, "lexists", lexists)
    assert write_one(archive2, planned2) == "there" and os.listdir(os.path.dirname(planned2.dest)) == ["x.json"]


def test_any_other_trouble_with_links_is_a_real_error(rig, tmp_path, monkeypatch):
    archive, planned = one_item(rig, tmp_path)
    monkeypatch.setattr(os, "link", lambda *a, **k: (_ for _ in ()).throw(OSError(errno.EIO, "disk error")))
    with pytest.raises(OSError):
        write_one(archive, planned)
    assert os.listdir(os.path.dirname(planned.dest)) == []
