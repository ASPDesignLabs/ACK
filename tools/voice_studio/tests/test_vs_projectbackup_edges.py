# SPDX-License-Identifier: GPL-3.0-or-later
"""Backup now (plan task VS-6.1): the edges the first tests did not hold. Found by breaking core/projectbackup.py on purpose, one condition at a time, and keeping a test for every
break that no test noticed: the exact limits of a name, the checks that look redundant next to the few shapes a backup holds (they are the defence if a shape ever widens), what
a file that changes in size only or in time only does, the errors the system can give, the conditions under which a restore says no, and the Windows-side folder.

Breaks that nothing can notice, because another check behind them gives the same answer (24 of the 328; each was looked at, none is a gap): a leading slash in `_plain` (an empty first part already
refuses it); a take name one level too deep or too shallow (`_allowed` refuses the parts); `len(parts) == 2` written as a range; an empty destination (`isabs("")` is already false); a file where
the folder should be (the next check refuses it with the same code); the guard that stops the walk up to a folder that is there (every path ends at one); `<=` against `<` for the size that is read whole
(both write the same bytes); a short read in either branch (the tar library refuses it first, with the same code); a member that cannot be opened (a plain file always can); `EOFError` and
`zlib.error` (a plain tar cannot raise them); `UnicodeDecodeError` (a kind of `ValueError`); an archive with no manifest and no problem (it always has one); a link or file in the project's place
(the record check refuses it with the same code); the checks of kind and size before the checksum in "already there and the same" (a folder has no checksum, and the checksum decides the rest);
the project being new in the second look at the plan (it cannot change without the files changing); a member or a stream that is gone after the read-back; and the front's own handler for a damaged
record of rounds in `list` (the command's outer handler says the same)."""
import errno
import json
import os
import shutil
import tarfile
import types
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from vs_backup_helpers import CODE, TAKE, BackupRig, forge
from voice_studio.core import projectbackup as pb, rounds as rd
from voice_studio.core.diskbudget import DEFAULT_TABLE, MIB, Level, floors_for
from voice_studio.core.paths import DataHome, ProjectPaths

NOW = datetime(2026, 10, 16, 9, 30, 0, tzinfo=timezone.utc)
PATHS = ProjectPaths("/h/ack-voice-studio/projects/anna")
TAKE1 = TAKE % (1, 1)
RAW = "recordings/takes/%s/raw.webm" % TAKE1
LOW = floors_for(DEFAULT_TABLE, holds_recordings=True).low


@pytest.fixture
def rig(tmp_path):
    return BackupRig(tmp_path)


def code_of(fn, *a, **kw):
    with pytest.raises(pb.BackupError) as caught:
        fn(*a, **kw)
    return caught.value.code


def members_of(path):
    with tarfile.open(path, "r:") as tar:
        return {m.name: tar.extractfile(m).read() for m in tar if m.isfile()}


def plan_restore(rig, path, free=10 ** 12):
    return pb.plan_restore(rig.home, path, free)


def lose_project(rig):
    shutil.rmtree(rig.paths.root)


def leftovers(rig):
    return sorted(os.listdir(rig.dest)) if os.path.isdir(rig.dest) else []


# ---------------------------------------------------------------- a name, exactly

@pytest.mark.parametrize("name", ["", "a\\b", "a\0b", "/a/b", "a//b", "a/./b", "a/../b", "a/", "./a", "../a", "a" * 401])
def test_a_name_that_could_mean_anything_but_a_place_inside_the_archive_has_no_parts(name):
    assert pb._plain(name) is None


def test_a_plain_name_is_split_into_its_parts_and_four_hundred_characters_is_the_most():
    assert pb._plain("a/b/c") == ["a", "b", "c"] and pb._plain("x") == ["x"]
    assert pb._plain("a" * 400) == ["a" * 400] and pb._plain("a" * 401) is None


def test_names_that_look_like_a_held_shape_but_are_in_the_wrong_place_are_not_held():
    for name in ("recordings/other/%s/raw.webm" % TAKE1,                     # not the takes folder
                 "recordings/takes/not-a-take/raw.webm",
                 "recordings/other/p.zip",                                   # not the incoming folder
                 "rounds/other/round-001.json",                              # not the config folder
                 "rounds/config/round-01.json", "rounds/config/round-12.json", "rounds/config/round-1234567.json", "rounds/config/notes.txt",
                 "rounds/run/lightning_logs/version_0/checkpoints/last.ckpt/extra",      # one level too deep
                 "rounds/run/other/version_0/checkpoints/last.ckpt",
                 "rounds/run/lightning_logs/version_1234567/checkpoints/last.ckpt",
                 "rounds/run/lightning_logs/version_0/other/last.ckpt",
                 "rounds/run/lightning_logs/version_0/checkpoints/" + "a" * 121 + ".ckpt",
                 "exports/voice a/voice a.zip", "exports/voice-a/other.zip"):
        assert pb.member_target(PATHS, name) is None, name


def test_the_longest_names_that_are_held_are_held():
    assert pb.member_target(PATHS, "rounds/run/lightning_logs/version_123456/checkpoints/last.ckpt").part == "saved_points"
    assert pb.member_target(PATHS, "rounds/run/lightning_logs/version_0/checkpoints/" + "a" * 120 + ".ckpt").part == "saved_points"        # 1 + 119 characters, then .ckpt
    assert pb.member_target(PATHS, "rounds/config/round-001.json").part == "rounds" and pb.member_target(PATHS, "rounds/config/round-123456.json").part == "rounds"


# ---------------------------------------------------------------- what is held, exactly

def test_the_spare_copy_of_the_projects_record_is_held_too(rig):
    Path(rig.paths.previous_json).write_text("{}")
    assert "project/project.json.previous" in {i.name for i in pb.collect(rig.paths)[0]}


def test_a_stray_file_beside_the_packages_or_the_round_settings_is_not_held(rig):
    (rig.recordings_root / "incoming" / "notes.txt").write_text("not a package")
    Path(rig.paths.round_configs, "notes.txt").write_text("not a settings file")
    names = {i.name for i in pb.collect(rig.paths)[0]}
    assert "recordings/incoming/notes.txt" not in names and "rounds/config/notes.txt" not in names
    assert "recordings/incoming/p.zip" in names and "rounds/config/round-001.json" in names


def test_inside_a_part_the_files_are_in_the_order_of_their_names_and_not_their_sizes(rig):
    items, _ = pb.collect(rig.paths)
    by_part = {}
    for item in items:
        by_part.setdefault(item.part, []).append(item.name)
    assert len(by_part["recordings"]) > 4 and len({i.size for i in items if i.part == "recordings"}) > 2
    for part, names in by_part.items():
        assert names == sorted(names), part
    assert [i.part for i in items] == sorted((i.part for i in items), key=pb.PARTS.index)


def test_a_saved_point_whose_name_leads_somewhere_else_is_not_held(rig, monkeypatch):
    elsewhere = types.SimpleNamespace(version=0, name="last.ckpt", path="/elsewhere/last.ckpt", size=1)
    monkeypatch.setattr(rd, "retention", lambda paths, record: types.SimpleNamespace(keep=[(1, elsewhere)], spare=[]))
    items, skipped = pb.collect(rig.paths)
    assert not [i for i in items if i.part == "saved_points"]
    assert [(s.name, s.reason) for s in skipped] == [("rounds/run/lightning_logs/version_0/checkpoints/last.ckpt", "not_a_file")]


def test_the_fingerprint_follows_each_of_the_name_the_size_and_the_time():
    base = pb.Item("record", "project/project.json", "/x", 5, 10)
    prints = {pb.fingerprint([base]), pb.fingerprint([replace(base, size=6)]), pb.fingerprint([replace(base, mtime_ns=11)]), pb.fingerprint([replace(base, name="project/project.json.previous")])}
    assert len(prints) == 4
    assert pb.fingerprint([base]) == pb.fingerprint([replace(base, source="/y", part="rounds")]), "where the file is, and which part it is counted in, are not what changed"


def test_the_size_estimate_follows_the_tar_blocks_and_the_manifest_to_the_byte():
    two = [pb.Item("record", "a", "/a", 0, 0), pb.Item("record", "b", "/b", 1000, 0)]
    # headers 2 x 512 + data 0 and 1024 = 2048; the manifest 4096 + 2 x 400 padded to 5120; the manifest's header 512, two empty blocks 1024, and 5120 of room for the tar's own padding
    assert pb.archive_size(two) == 2048 + 512 + 5120 + 1024 + 5120 == 13824
    assert pb.archive_size([]) == 512 + 4096 + 1024 + 5120


# ---------------------------------------------------------------- where, and how much room

def test_a_folder_beside_the_projects_folder_with_a_name_that_starts_the_same_is_not_inside_it(rig):
    sibling = rig.home.projects + "-elsewhere/backups"
    assert pb.check_destination(rig.paths, rig.home, sibling) == sibling


def test_a_project_that_is_not_under_the_projects_folder_still_has_no_backup_inside_it(rig, tmp_path):
    loose = ProjectPaths(str(tmp_path / "loose" / "anna"))
    assert code_of(pb.check_destination, loose, rig.home, str(tmp_path / "loose" / "anna" / "backups")) == "inside_project"
    assert pb.check_destination(loose, rig.home, str(tmp_path / "loose-other")) == str(tmp_path / "loose-other")


def test_a_place_that_cannot_be_read_is_not_taken_to_be_the_same_drive(tmp_path):
    assert pb.same_drive(str(tmp_path / "missing"), str(tmp_path)) is False and pb.same_drive(str(tmp_path), str(tmp_path / "missing")) is False
    assert pb.same_drive(str(tmp_path), str(tmp_path)) is True


def test_a_scratch_folder_that_is_a_link_is_not_counted_as_left_out(rig, tmp_path):
    other = tmp_path / "scratch-elsewhere"
    shutil.move(rig.paths.default_scratch, str(other))
    os.symlink(str(other), rig.paths.default_scratch)
    assert "scratch" not in {left.id for left in rig.project_plan().left_out}


def test_on_another_drive_the_archive_and_the_margin_must_fit_and_the_projects_floors_do_not_apply(rig, monkeypatch):
    monkeypatch.setattr(pb, "same_drive", lambda a, b: False)
    need = rig.project_plan().need_bytes
    just_short = rig.project_plan(free=need + pb.REMOTE_MARGIN - 1)
    just_enough = rig.project_plan(free=need + pb.REMOTE_MARGIN)
    assert (just_short.room, just_enough.room, just_enough.same_drive) == (Level.NOT_ENOUGH, Level.ENOUGH, False), "the floors that keep the recorder safe are only for the project's own drive"
    assert rig.project_plan(free=None).room is Level.ENOUGH
    assert pb.judge_room(need + LOW, need, True) is Level.ENOUGH and pb.judge_room(need + pb.REMOTE_MARGIN, need, True) is not Level.ENOUGH


def test_the_name_skips_a_number_that_a_half_made_file_holds_and_counts_up_one_at_a_time(tmp_path):
    base = "ack-project-backup-anna-20261016-093000"
    folder = str(tmp_path)
    assert pb._stamp_name("anna", folder, NOW) == base + ".tar"
    Path(folder, base + ".tar.partial").write_text("half")
    assert pb._stamp_name("anna", folder, NOW) == base + "-2.tar"
    Path(folder, base + ".tar").write_text("one")
    Path(folder, base + "-2.tar").write_text("two")
    assert pb._stamp_name("anna", folder, NOW) == base + "-3.tar"


def test_the_time_in_the_name_and_the_note_is_utc_whatever_clock_was_given(rig):
    plus_two = datetime(2026, 10, 16, 12, 0, 0, tzinfo=timezone(timedelta(hours=2)))
    made = rig.backup(plus_two)
    assert made.name == "ack-project-backup-voice-check-20261016-100000.tar" and made.created == "2026-10-16T10:00:00+00:00"


# ---------------------------------------------------------------- reading a file while it may be changing

def test_a_folder_or_a_link_where_a_file_was_listed_is_refused(tmp_path):
    folder = tmp_path / "d"
    folder.mkdir()
    assert code_of(pb._open_regular, str(folder)) == "changed"
    target = tmp_path / "t"
    target.write_text("x")
    link = tmp_path / "l"
    link.symlink_to(target)
    with pytest.raises(OSError):
        pb._open_regular(str(link))


def test_a_partial_file_that_is_already_there_is_never_written_into(rig):
    partial = os.path.join(str(rig.paths.root), "there.partial")
    Path(partial).write_text("someone else's")
    with pytest.raises(FileExistsError):
        pb._write_archive(partial, pb.collect(rig.paths)[0], "voice-check", NOW, None)
    assert Path(partial).read_text() == "someone else's"


def test_every_member_is_for_its_owner_only_and_keeps_the_time_of_the_file_it_came_from(rig):
    made = rig.backup(NOW)
    source = rig.recordings_root / "takes" / TAKE1 / "raw.webm"
    with tarfile.open(made.path, "r:") as tar:
        for member in tar:
            assert member.mode == 0o600, member.name
        assert tar.getmember(RAW).mtime == int(source.stat().st_mtime)


def _change_after_it_is_read(monkeypatch, rig, change):
    target = rig.recordings_root / "takes" / TAKE1 / "raw.webm"
    real = tarfile.TarFile.addfile

    def addfile(self, tarinfo, fileobj=None):
        result = real(self, tarinfo, fileobj)
        if tarinfo.name.endswith(TAKE1 + "/raw.webm"):
            change(target, target.stat())
        return result
    monkeypatch.setattr(tarfile.TarFile, "addfile", addfile)


def test_a_file_whose_size_alone_changed_while_it_was_read_stops_the_backup(rig, monkeypatch):
    def change(target, before):
        target.write_bytes(b"MORE" * 100)
        os.utime(str(target), ns=(before.st_atime_ns, before.st_mtime_ns))                 # the same time as before: only the size gives it away
    _change_after_it_is_read(monkeypatch, rig, change)
    assert code_of(pb.create, rig.project_plan(), rig.paths, NOW) == "changed" and leftovers(rig) == []


def test_a_file_whose_time_alone_changed_while_it_was_read_stops_the_backup(rig, monkeypatch):
    _change_after_it_is_read(monkeypatch, rig, lambda target, before: os.utime(str(target), ns=(before.st_atime_ns, before.st_mtime_ns + 10 ** 9)))
    assert code_of(pb.create, rig.project_plan(), rig.paths, NOW) == "changed" and leftovers(rig) == []


def test_a_file_that_was_removed_while_it_was_read_stops_the_backup_in_words(rig, monkeypatch):
    _change_after_it_is_read(monkeypatch, rig, lambda target, before: target.unlink())
    assert code_of(pb.create, rig.project_plan(), rig.paths, NOW) == "changed" and leftovers(rig) == []


def test_a_file_that_is_shorter_than_it_was_when_looked_at_is_a_change(rig, monkeypatch):
    real = pb._open_regular

    def longer(path):
        fd, info = real(path)
        return fd, types.SimpleNamespace(st_mode=info.st_mode, st_size=info.st_size + 5, st_mtime_ns=info.st_mtime_ns)
    monkeypatch.setattr(pb, "_open_regular", longer)
    assert code_of(pb.create, rig.project_plan(), rig.paths, NOW) == "changed" and leftovers(rig) == []


@pytest.mark.parametrize("number", [errno.ENOSPC, errno.EDQUOT])
def test_a_full_drive_or_a_used_up_quota_while_writing_a_file_is_no_room(rig, monkeypatch, number):
    real = tarfile.TarFile.addfile

    def addfile(self, tarinfo, fileobj=None):
        if tarinfo.name.endswith(RAW):
            raise OSError(number, "no room")
        return real(self, tarinfo, fileobj)
    monkeypatch.setattr(tarfile.TarFile, "addfile", addfile)
    assert code_of(pb.create, rig.project_plan(), rig.paths, NOW) == "no_room" and leftovers(rig) == []


def test_a_tar_error_while_writing_a_file_is_a_change_and_another_system_error_is_a_failed_write(rig, monkeypatch):
    real = tarfile.TarFile.addfile
    state = {"raise": tarfile.TarError("odd")}

    def addfile(self, tarinfo, fileobj=None):
        if tarinfo.name.endswith(RAW):
            raise state["raise"]
        return real(self, tarinfo, fileobj)
    monkeypatch.setattr(tarfile.TarFile, "addfile", addfile)
    assert code_of(pb.create, rig.project_plan(), rig.paths, NOW) == "changed"
    state["raise"] = OSError(errno.EIO, "disk")
    assert code_of(pb.create, rig.project_plan(), rig.paths, NOW) == "write_failed"


def test_progress_adds_up_the_bytes_of_each_file_to_the_total(rig):
    seen = []
    items, _ = pb.collect(rig.paths)
    rig.backup  # the rig is built; the plan below is for the same files
    plan = rig.project_plan()
    pb.create(plan, rig.paths, NOW, lambda part, done, total: seen.append((part, done, total)))
    total = sum(i.size for i in items)
    files = [call for call in seen if call[0] != "read_back"]
    assert [done for _, done, _ in files] == [sum(i.size for i in items[:n + 1]) for n in range(len(items))] and {t for _, _, t in seen} == {total}
    assert seen[-1] == ("read_back", total, total)


def test_a_folder_that_cannot_be_made_is_a_failed_write_and_nothing_is_left(rig, monkeypatch):
    real = os.makedirs

    def makedirs(path, *a, **k):
        if path == rig.dest:
            raise PermissionError(errno.EACCES, "no")
        return real(path, *a, **k)
    monkeypatch.setattr(os, "makedirs", makedirs)
    assert code_of(pb.create, rig.project_plan(), rig.paths, NOW) == "write_failed" and not os.path.exists(rig.dest)


def test_a_lock_older_than_six_hours_is_taken_over_and_a_younger_one_is_waited_for(rig):
    os.makedirs(rig.dest)
    lock = Path(rig.dest, pb.LOCK)
    lock.write_text("1")
    five = datetime.now().timestamp() - 5 * 3600
    os.utime(lock, (five, five))
    assert code_of(pb.create, rig.project_plan(), rig.paths, NOW) == "busy"
    seven = datetime.now().timestamp() - 7 * 3600
    os.utime(lock, (seven, seven))
    assert os.path.isfile(pb.create(rig.project_plan(), rig.paths, NOW).path) and pb.STALE_LOCK_S == 6 * 3600


def test_a_name_no_backup_holds_makes_the_read_back_fail_and_the_file_is_thrown_away(rig, monkeypatch):
    real = pb.collect

    def with_a_stranger(paths, record=None, saved_points=True):
        items, skipped = real(paths, record, saved_points)
        first = items[0]
        return items + (pb.Item("record", "elsewhere/odd.txt", first.source, first.size, first.mtime_ns),), skipped
    monkeypatch.setattr(pb, "collect", with_a_stranger)
    assert code_of(pb.create, rig.project_plan(), rig.paths, NOW) == "not_read_back" and leftovers(rig) == []


def test_only_the_first_five_problems_of_a_failed_read_back_are_kept(rig, monkeypatch):
    monkeypatch.setattr(pb, "verify", lambda path, check_names=True: (["p%d" % n for n in range(7)], None))
    with pytest.raises(pb.BackupError) as caught:
        pb.create(rig.project_plan(), rig.paths, NOW)
    assert caught.value.code == "not_read_back" and caught.value.problems == tuple("p%d" % n for n in range(5))


@pytest.mark.parametrize("number,code", [(errno.EIO, "write_failed"), (errno.ENOSPC, "no_room"), (errno.EDQUOT, "no_room")])
def test_a_drive_that_fails_when_the_backup_is_given_its_name_leaves_nothing_and_says_which(rig, monkeypatch, number, code):
    real = os.replace

    def replace(src, dst, *a, **k):
        if str(src).endswith(".partial"):
            raise OSError(number, "no")
        return real(src, dst, *a, **k)
    monkeypatch.setattr(os, "replace", replace)
    assert code_of(pb.create, rig.project_plan(), rig.paths, NOW) == code and leftovers(rig) == []


def test_the_note_beside_a_backup_holds_what_the_listing_needs_and_the_fingerprint(rig):
    made = rig.backup(NOW)
    note = json.loads(Path(made.path + ".json").read_text())
    assert note == {"schema": 1, "project": "voice-check", "created": made.created, "files": made.files, "source_bytes": made.source_bytes, "archive_bytes": made.archive_bytes,
                    "parts": {p.part: [p.files, p.bytes] for p in made.parts}, "fingerprint": made.fingerprint} and len(made.fingerprint) == 64
    assert made.archive_bytes == os.stat(made.path).st_size > 0


# ---------------------------------------------------------------- reading one back

def test_an_archive_with_exactly_the_most_members_is_read_and_one_more_is_not(tmp_path, monkeypatch):
    monkeypatch.setattr(pb, "MAX_MEMBERS", 3)
    two = forge(tmp_path / "two.tar", [("project/project.json", b"{}"), ("project/project.json.previous", b"{}")])
    assert pb.verify(two)[0] == []
    three = forge(tmp_path / "three.tar", [("project/project.json", b"{}"), ("project/project.json.previous", b"{}"), ("rounds/rounds.json", b"{}")])
    assert "it holds more files than a backup can" in pb.verify(three)[0]


def test_a_manifest_larger_than_sixty_four_megabytes_is_not_read_whole(tmp_path):
    body = '{"pad": "%s", "schema": 1}' % ("x" * (65 * MIB))
    path = forge(tmp_path / "big.tar", [("project/project.json", b"{}")], manifest=body.encode("utf-8"))
    problems, manifest = pb.verify(path)
    assert "the manifest is damaged" in problems and manifest is None or "the manifest is damaged" in problems


@pytest.mark.parametrize("blob", [b"\xff\xfe\x00\x01", b"[" * 200_000, b"{not json"])
def test_a_manifest_that_is_not_text_or_nests_without_end_is_damaged_and_never_a_crash(tmp_path, blob):
    problems, manifest = pb.verify(forge(tmp_path / "x.tar", [("project/project.json", b"{}")], manifest=blob))
    assert "the manifest is damaged" in problems and manifest is None


def test_an_archive_with_no_manifest_says_so_once(tmp_path):
    problems, manifest = pb.verify(forge(tmp_path / "x.tar", [("project/project.json", b"{}")], manifest=None))
    assert problems == ["it has no manifest, so it cannot be checked"] and manifest is None


def test_a_manifest_of_another_schema_is_not_read(tmp_path):
    problems, manifest = pb.verify(forge(tmp_path / "x.tar", [("project/project.json", b"{}")], schema=2))
    assert problems == ["the manifest is not one this version reads"] and manifest is None


@pytest.mark.parametrize("entry", [{"path": 5, "size": 2, "sha256": "x"}, {"path": "project/project.json", "size": "2", "sha256": "x"}, {"path": "project/project.json", "size": 2, "sha256": 5}, "text", 5])
def test_a_manifest_entry_that_is_not_understood_is_a_problem_and_never_a_crash(tmp_path, entry):
    manifest = {"schema": 1, "app": "ack-voice-studio", "project": "voice-check", "created": "2026-10-16T09:00:00+00:00", "files": [entry]}
    problems, _ = pb.verify(forge(tmp_path / "x.tar", [("project/project.json", b"{}")], manifest=manifest))
    assert "the manifest has an entry that is not understood" in problems


def test_a_file_with_the_right_checksum_but_not_the_listed_size_does_not_match(tmp_path):
    import hashlib
    data = b"{}"
    manifest = {"schema": 1, "app": "ack-voice-studio", "project": "voice-check", "created": "2026-10-16T09:00:00+00:00",
                "files": [{"path": "project/project.json", "part": "record", "size": 3, "sha256": hashlib.sha256(data).hexdigest()}]}
    problems, _ = pb.verify(forge(tmp_path / "x.tar", [("project/project.json", data)], manifest=manifest))
    assert problems == ["project/project.json: does not match its checksum"]


# ---------------------------------------------------------------- listing, and what the tool remembers

def test_two_backups_made_in_the_same_second_are_listed_newest_first(rig):
    first = rig.backup(NOW)
    second = rig.backup(NOW)
    third = rig.backup(NOW)
    assert [b["name"] for b in pb.list_backups(rig.dest)] == [third.name, second.name, first.name] and third.name.endswith("-3.tar")
    assert all("n" not in b for b in pb.list_backups(rig.dest))


def test_the_record_of_backups_keeps_only_what_it_can_use(tmp_path):
    home = DataHome(str(tmp_path))
    os.makedirs(home.state)
    good = {"created": "2026-10-16T09:30:00+00:00", "file": "a.tar", "folder": "/b", "fingerprint": "f"}
    Path(home.state, pb.STATE_FILE).write_text(json.dumps({"projects": {"voice-check": good, "Bad Name": good, "second": "not a record"}}))
    assert pb.read_state(home) == {"voice-check": good}
    for text in ('{"projects": []}', '[]', '"x"', "{not json", '{"projects": {"voice-check": 5}}'):
        Path(home.state, pb.STATE_FILE).write_text(text)
        assert pb.read_state(home) == {}, text


def test_a_backup_is_noted_with_where_when_and_what_it_looked_like_and_other_projects_are_kept(rig):
    made = rig.backup(NOW)
    pb.record_backup(rig.home, made, "voice-check", rig.dest)
    pb.record_backup(rig.home, made, "second-check", "/elsewhere")
    state = pb.read_state(rig.home)
    assert state["voice-check"] == {"created": made.created, "file": made.name, "folder": rig.dest, "fingerprint": made.fingerprint}
    assert state["second-check"]["folder"] == "/elsewhere" and set(state) == {"voice-check", "second-check"}
    assert (os.stat(rig.home.state + "/" + pb.STATE_FILE).st_mode & 0o077) == 0


def test_a_note_that_cannot_be_kept_is_not_an_error(rig, monkeypatch):
    made = rig.backup(NOW)
    real = os.makedirs

    def makedirs(path, *a, **k):
        if path == rig.home.state:
            raise PermissionError(errno.EACCES, "no")
        return real(path, *a, **k)
    monkeypatch.setattr(os, "makedirs", makedirs)
    shutil.rmtree(rig.home.state, ignore_errors=True)
    pb.record_backup(rig.home, made, "voice-check", rig.dest)
    assert pb.read_state(rig.home) == {}


# ---------------------------------------------------------------- the way back, exactly

def test_an_archive_with_many_problems_names_only_the_first_five(rig, tmp_path):
    path = forge(tmp_path / "bad.tar", [("odd%d.txt" % n, b"x") for n in range(7)])
    with pytest.raises(pb.BackupError) as caught:
        plan_restore(rig, path)
    assert caught.value.code == "damaged" and len(caught.value.problems) == 5


def test_a_task_that_has_ended_does_not_stop_a_restore_but_one_for_another_project_never_did(rig):
    from vs_rounds_helpers import fake_job
    made = rig.backup(NOW)
    fake_job(rig.home.jobs, ["x"], "finished", project="voice-check", exit_code=0)
    fake_job(rig.home.jobs, ["x"], "running", project="second-check")
    assert plan_restore(rig, made.path).same > 0


def test_a_name_that_passed_the_read_back_but_is_no_shape_a_backup_holds_is_refused_as_unsafe(rig, tmp_path, monkeypatch):
    path = forge(tmp_path / "x.tar", [("project/project.json", b"{}")])
    manifest = {"schema": 1, "project": "voice-check", "created": "", "files": [{"path": "../outside", "size": 1, "sha256": "x"}]}
    monkeypatch.setattr(pb, "verify", lambda archive, check_names=True: ([], manifest))
    assert code_of(plan_restore, rig, path) == "unsafe"


def test_a_file_of_the_same_size_with_other_contents_is_a_difference_not_a_match(rig):
    made = rig.backup(NOW)
    raw = rig.recordings_root / "takes" / TAKE1 / "raw.webm"
    original = raw.read_bytes()
    raw.write_bytes(bytes(b ^ 1 for b in original))
    plan = plan_restore(rig, made.path)
    assert plan.conflicts == (RAW,) and plan.add == () and raw.read_bytes() != original


def test_the_room_a_restore_needs_is_what_it_adds_and_a_margin_judged_with_the_projects_floors(rig):
    made = rig.backup(NOW)
    lose_project(rig)
    base = plan_restore(rig, made.path)
    need = base.bytes_to_add + pb.SLACK
    assert plan_restore(rig, made.path, need + LOW).room is Level.ENOUGH
    assert plan_restore(rig, made.path, need + LOW - 1).room is Level.TIGHT, "the margin is part of what is needed"
    assert plan_restore(rig, made.path, need + pb.REMOTE_MARGIN).room is not Level.ENOUGH, "a restore goes onto the project's own drive, whatever drive the backup is on"
    assert plan_restore(rig, made.path, None).room is Level.ENOUGH


def test_nothing_to_add_needs_no_room(rig):
    made = rig.backup(NOW)
    assert plan_restore(rig, made.path, 0).room is Level.ENOUGH


def test_a_file_that_appears_after_the_plan_is_left_alone_and_counted_as_left(rig, monkeypatch):
    made = rig.backup(NOW)
    (rig.recordings_root / "takes" / TAKE1 / "raw.webm").unlink()
    plan = plan_restore(rig, made.path)
    real = pb._write_one

    def appears(tar, member, item):
        if item.name == RAW:
            Path(item.dest).write_bytes(b"made meanwhile")
        return real(tar, member, item)
    monkeypatch.setattr(pb, "_write_one", appears)
    result = pb.restore(rig.home, plan)
    assert result.conflicts == (RAW,) and result.added == 0 and Path(rig.recordings_root / "takes" / TAKE1 / "raw.webm").read_bytes() == b"made meanwhile"


def test_a_file_put_back_by_hand_after_the_plan_stops_the_restore_because_the_plan_is_out_of_date(rig):
    made = rig.backup(NOW)
    raw = rig.recordings_root / "takes" / TAKE1 / "raw.webm"
    original = raw.read_bytes()
    raw.unlink()
    plan = plan_restore(rig, made.path)
    assert [p.name for p in plan.add] == [RAW]
    raw.write_bytes(original)                                  # now identical to the backup's copy: no longer something to add
    assert code_of(pb.restore, rig.home, plan) == "changed"


def test_a_difference_put_right_by_hand_after_the_plan_stops_the_restore_too(rig):
    made = rig.backup(NOW)
    edit = rig.recordings_root / "takes" / TAKE1 / "edit.json"
    original = edit.read_bytes()
    edit.write_text('{"mine": true}')
    Path(rig.paths.round_configs, "round-001.json").unlink()   # something to add as well, so the restore has work to do
    plan = plan_restore(rig, made.path)
    assert plan.conflicts == ("recordings/takes/%s/edit.json" % TAKE1,) and len(plan.add) == 1
    edit.write_bytes(original)                                 # the difference is gone: the plan's list of differences is out of date
    assert code_of(pb.restore, rig.home, plan) == "changed"


def test_a_restore_is_not_done_while_another_change_to_the_rounds_is_in_progress(rig, monkeypatch):
    made = rig.backup(NOW)
    Path(rig.paths.round_configs, "round-001.json").unlink()
    plan = plan_restore(rig, made.path)
    monkeypatch.setattr(rd, "LOCK_WAIT_S", 0.1)
    with rd.exclusive(rig.paths):
        assert code_of(pb.restore, rig.home, plan) == "busy"
    assert not Path(rig.paths.round_configs, "round-001.json").exists()


def test_the_projects_record_is_written_before_the_lock_is_asked_for(rig, monkeypatch):
    made = rig.backup(NOW)
    lose_project(rig)
    plan = plan_restore(rig, made.path)

    def locked(paths):
        raise rd.RoundsError("busy", "record")
    monkeypatch.setattr(rd, "exclusive", locked)
    assert code_of(pb.restore, rig.home, plan) == "busy"
    assert os.path.isfile(rig.paths.project_json), "a restore that stops at the lock still leaves a project that is listed"
    assert not os.path.exists(rig.paths.rounds_file)


def test_a_read_that_fails_half_way_is_a_damaged_backup(rig, monkeypatch):
    made = rig.backup(NOW)
    lose_project(rig)
    plan = plan_restore(rig, made.path)
    monkeypatch.setattr(pb, "_write_one", lambda tar, member, item: (_ for _ in ()).throw(tarfile.ReadError("cut short")))
    assert code_of(pb.restore, rig.home, plan) == "damaged"


def test_a_projects_folder_that_cannot_be_made_is_a_failed_write(rig, monkeypatch):
    made = rig.backup(NOW)
    lose_project(rig)
    plan = plan_restore(rig, made.path)
    real = os.makedirs

    def makedirs(path, *a, **k):
        if path == rig.home.projects:
            raise PermissionError(errno.EACCES, "no")
        return real(path, *a, **k)
    monkeypatch.setattr(os, "makedirs", makedirs)
    assert code_of(pb.restore, rig.home, plan) == "write_failed"


@pytest.mark.parametrize("number", [errno.EPERM, errno.ENOTSUP, errno.EOPNOTSUPP, errno.EXDEV, errno.EMLINK, errno.ENOSYS])
def test_where_links_are_not_possible_a_file_is_still_put_back_without_replacing_anything(rig, monkeypatch, number):
    made = rig.backup(NOW)
    lose_project(rig)
    plan = plan_restore(rig, made.path)
    monkeypatch.setattr(os, "link", lambda *a, **k: (_ for _ in ()).throw(OSError(number, "no links here")))
    result = pb.restore(rig.home, plan)
    assert result.failed == () and result.added == len(plan.add) > 0


def test_a_folder_in_the_way_when_links_are_not_possible_is_not_replaced(rig, monkeypatch):
    made = rig.backup(NOW)
    (rig.recordings_root / "takes" / TAKE1 / "raw.webm").unlink()
    plan = plan_restore(rig, made.path)
    monkeypatch.setattr(os, "link", lambda *a, **k: (_ for _ in ()).throw(OSError(errno.EPERM, "no links here")))
    real = os.path.lexists
    monkeypatch.setattr(os.path, "lexists", lambda p: True if str(p).endswith("take/raw.webm") else real(p))
    item = next(i for i in plan.add)
    with tarfile.open(made.path, "r:") as tar:
        outcome = pb._write_one(tar, tar.getmember(item.name), replace(item, dest=item.dest + "/take/raw.webm"))
    assert outcome == "there"


def test_every_file_put_back_is_flushed_to_the_drive(rig, monkeypatch):
    made = rig.backup(NOW)
    lose_project(rig)
    plan = plan_restore(rig, made.path)
    calls = []
    real = os.fsync
    monkeypatch.setattr(os, "fsync", lambda fd: (calls.append(fd), real(fd))[1])
    result = pb.restore(rig.home, plan)
    assert len(calls) >= result.added > 0


def test_the_temporary_file_is_made_beside_the_place_it_is_for(tmp_path):
    fd, path = pb._temp_in(str(tmp_path))
    os.close(fd)
    try:
        assert os.path.dirname(path) == str(tmp_path) and os.path.basename(path).startswith(".restore-")
    finally:
        os.unlink(path)


# ---------------------------------------------------------------- a folder on the Windows side

class Computer:
    """What the Windows-side folder is chosen from: whether this is WSL, the folders under /mnt/c/Users, and which of them are files."""

    def __init__(self, people, wsl=True, files=(), listing=True):
        self.people, self.wsl, self.files, self.listing = tuple(people), wsl, tuple(files), listing

    def read_text(self, path):
        return "Linux version 5.15.0-microsoft-standard-WSL2" if self.wsl and path == "/proc/version" else "Linux version 6.8.0-generic"

    def listdir(self, path):
        return list(self.people) if self.listing and path == pb.WINDOWS_USERS else None

    def is_dir(self, path):
        return os.path.basename(path) not in self.files


ANNA = pb.WINDOWS_USERS + "/anna/ACK Voice Studio backups"


def test_under_wsl_with_one_real_windows_user_that_users_folder_is_named():
    assert pb.windows_side_folder(Computer(["anna"])) == ANNA


@pytest.mark.parametrize("others", [["Public"], ["DEFAULT"], ["Default User"], ["All Users"], ["defaultapppool"], [".hidden"], ["$Recycle.Bin"], ["notes.txt"]])
def test_folders_that_are_not_a_person_are_not_counted(others):
    assert pb.windows_side_folder(Computer(["anna"] + others, files=["notes.txt"])) == ANNA


def test_it_is_named_only_when_the_user_can_be_told_and_this_is_wsl():
    assert pb.windows_side_folder(Computer(["anna"], wsl=False)) is None
    assert pb.windows_side_folder(Computer(["anna", "ben"])) is None and pb.windows_side_folder(Computer([])) is None
    assert pb.windows_side_folder(Computer(["anna"], listing=False)) is None


def test_a_folder_that_looks_synchronised_is_never_the_example():
    assert pb.windows_side_folder(Computer(["Dropbox"])) is None
