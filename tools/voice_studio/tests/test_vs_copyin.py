# SPDX-License-Identifier: GPL-3.0-or-later
"""Bringing recordings in from an older hand-built setup (plan task VS-3.4): the older folder is never touched, the copy comes from a checked backup,
copying only adds, and everything is checked afterwards."""
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import pytest

from voice_studio.core import commands, copyin as ci
from voice_studio.core import diskbudget as db
from voice_studio.core.envbuild import EnvPaths
from voice_studio.core.jobs import _check_spec
from voice_studio.core.paths import DataHome
from voice_studio.core.text import load_catalog

TOOLS = Path(__file__).resolve().parents[2]
CAT = load_catalog("en")
MIB = 1024 * 1024


def write_tone(path, seconds, rate=48000):
    """A steady tone, mono 16-bit, with no extra library."""
    import array
    import math
    import wave
    samples = array.array("h", (int(12000 * math.sin(2 * math.pi * 200 * n / rate)) for n in range(int(seconds * rate))))
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(samples.tobytes())
    return path


def tree(root):
    """Everything under `root` that can change: names, kinds, sizes, times and contents. Two equal trees mean nothing was touched."""
    seen = {}
    for path in sorted(Path(root).rglob("*")):
        rel = str(path.relative_to(root))
        st = path.lstat()
        seen[rel] = (stat.S_IFMT(st.st_mode), st.st_size, st.st_mtime_ns, hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() and not path.is_symlink() else "")
    return seen


def make_take(output, code, number, *, status="ready", seconds=60.0, raw=b"RAW" * 1000, extra=None, edit=None):
    take_id = "t20260930-%06d-%04x" % (number, number)
    folder = Path(output) / "_freeform" / code / "takes" / take_id
    (folder / "edit_history").mkdir(parents=True)
    (folder / "take.json").write_text(json.dumps({"id": take_id, "status": status, "duration": seconds}))
    (folder / "edit.json").write_text(json.dumps(edit or {"schema": 1, "rev": 1, "segments": []}))
    (folder / "asr.json").write_text(json.dumps({"engine": "fake"}))
    (folder / "raw.webm").write_bytes(raw + bytes([number]))
    (folder / "edit_history" / "edit-1.json").write_text("{}")
    for name, data in (extra or {}).items():
        (folder / name).write_bytes(data)
    return take_id, folder


@pytest.fixture
def old(tmp_path):
    """An older output folder with three recordings (one still being listened to), things a backup leaves out, and a second language."""
    out = tmp_path / "old-output"
    make_take(out, "en-US", 1, seconds=1800.0)
    make_take(out, "en-US", 2, seconds=900.0, extra={"audio.wav": b"decoded" * 50, "peaks.json": b"{}"})
    make_take(out, "en-US", 3, status="transcribing", seconds=0.0)
    make_take(out, "en-GB", 1, seconds=3600.0)
    (out / "_freeform" / "en-US" / "token").write_text("secret")
    (out / "_freeform" / "en-US" / "incoming").mkdir()
    (out / "_freeform" / "en-US" / "incoming" / "p.zip").write_bytes(b"PK")
    return out


def found_en_us(old):
    return next(f for f in ci.survey(str(old)) if f.code == "en-US")


# ---------------------------------------------------------------- looking

def test_each_language_folder_with_recordings_is_counted_by_what_a_backup_would_hold(old):
    found = ci.survey(str(old))
    assert [f.code for f in found] == ["en-GB", "en-US"]
    us, gb = found[1], found[0]
    assert (us.takes, us.unfinished, gb.takes, gb.unfinished) == (3, 1, 1, 0)
    assert us.hours == round((1800 + 900) / 3600, 3) and gb.hours == 1.0
    expected = [p for p in (old / "_freeform" / "en-US" / "takes").rglob("*") if p.is_file() and p.name not in ("audio.wav", "peaks.json")]
    assert us.files == len(expected) and us.bytes == sum(p.stat().st_size for p in expected), "the decoded copy is rebuilt, so it is not counted"


def test_nothing_found_is_an_empty_answer_not_an_error(tmp_path):
    assert ci.survey(str(tmp_path / "nowhere")) == [] and ci.survey(str(tmp_path)) == []
    (tmp_path / "_freeform" / "en-US" / "takes").mkdir(parents=True)
    assert ci.survey(str(tmp_path)) == []


def test_a_recording_whose_notes_are_odd_still_counts(tmp_path):
    take_id, folder = make_take(tmp_path, "en-US", 1)
    for odd in ('{"duration": "long"}', '{"duration": true}', '{"duration": -5}', "not json", '["x"]'):
        (folder / "take.json").write_text(odd)
        found = ci.survey(str(tmp_path))
        assert found[0].takes == 1 and found[0].hours == 0.0 and found[0].unfinished == 1, odd


def test_a_duration_is_a_positive_number_and_nothing_else(tmp_path):
    notes = tmp_path / "take.json"
    for value, expected in ((90, 90.0), (0.5, 0.5), (0, 0.0), (-3, 0.0), (True, 0.0), (False, 0.0), ("90", 0.0), (None, 0.0), ([1], 0.0)):
        notes.write_text(json.dumps({"duration": value}))
        assert ci._read_duration(notes) == expected, value
    assert ci._read_duration(tmp_path / "missing.json") == 0.0


def test_a_language_folder_that_is_a_link_is_followed_because_it_is_only_read(tmp_path):
    real = tmp_path / "elsewhere"
    make_take(real, "en-US", 1)
    out = tmp_path / "out"
    (out / "_freeform").mkdir(parents=True)
    (out / "_freeform" / "en-US").symlink_to(real / "_freeform" / "en-US")
    assert [(f.code, f.takes) for f in ci.survey(str(out))] == [("en-US", 1)]


def test_looking_changes_nothing(old):
    before = tree(old)
    ci.survey(str(old))
    ci.backup_warning(str(old))
    assert tree(old) == before


@pytest.mark.parametrize("a, b, same", [("/x/y", "/x/y", True), ("/x/y", "/x/y/z", True), ("/x/y/z", "/x/y", True), ("/x/y", "/x/yy", False), ("/x/yy", "/x/y", False), ("/x/y", "/x/z", False), ("/x/y/", "/x/y", True)])
def test_a_folder_inside_the_other_or_the_same_is_the_same_place(a, b, same):
    assert ci.same_place(a, b) is same


def test_a_link_to_the_older_folder_is_the_same_place(tmp_path):
    (tmp_path / "real").mkdir()
    (tmp_path / "link").symlink_to(tmp_path / "real")
    assert ci.same_place(str(tmp_path / "link"), str(tmp_path / "real"))


def test_the_found_line_says_how_much_in_words(old):
    us = found_en_us(old)
    line = ci.found_line(us, CAT)
    assert line.startswith("Found 3 recordings (") and "about 0.8 hours" in line and line.endswith("in %s." % old)
    one = ci.OldRecordings("/o", "en-US", 1, 4, 5 * MIB, 3.0, 0)
    assert ci.found_line(one, CAT) == "Found 1 recording (5.2 MB, about 3 hours) in /o."
    assert "about 0 hours" in ci.found_line(ci.OldRecordings("/o", "en-US", 2, 4, 5 * MIB, 0.0, 0), CAT)
    assert "about 12 hours" in ci.found_line(ci.OldRecordings("/o", "en-US", 2, 4, 5 * MIB, 12.0, 0), CAT)


# ---------------------------------------------------------------- room

def vol(bytes_, hours):
    return ci.OldRecordings("/o", "en-US", 1, 1, bytes_, hours, 0)


def test_the_backup_and_the_copy_each_need_what_the_recordings_weigh_and_the_copy_also_the_decoded_audio():
    verdict = ci.room_check(vol(10 * MIB, 2.0), {"backup": 10 ** 12, "project": 10 ** 12})
    assert verdict.need == {"backup": int(10 * MIB * 1.05) + 50 * MIB, "project": 10 * MIB + int(2.0 * 48000 * 2 * 3600)}
    assert verdict.level is db.Level.ENOUGH and verdict.short_by == {"backup": 0, "project": 0}


def test_the_room_is_judged_at_the_exact_edges_on_each_place():
    found = vol(10 * MIB, 2.0)
    need = ci.room_check(found, {}).need
    low_b, stop_b = db.floors_for(db.DEFAULT_TABLE, False).low, db.floors_for(db.DEFAULT_TABLE, False).stop
    low_p, stop_p = db.floors_for(db.DEFAULT_TABLE, True).low, db.floors_for(db.DEFAULT_TABLE, True).stop
    roomy = {"backup": need["backup"] + low_b, "project": need["project"] + low_p}
    assert ci.room_check(found, roomy).level is db.Level.ENOUGH
    assert ci.room_check(found, dict(roomy, backup=roomy["backup"] - 1)).level is db.Level.TIGHT
    assert ci.room_check(found, dict(roomy, project=need["project"] + stop_p)).level is db.Level.TIGHT
    assert ci.room_check(found, dict(roomy, project=need["project"] + stop_p - 1)).level is db.Level.NOT_ENOUGH
    assert ci.room_check(found, dict(roomy, backup=need["backup"] + stop_b - 1)).level is db.Level.NOT_ENOUGH, "the backup drive has its own floors, without the recorder's"
    short = ci.room_check(found, dict(roomy, backup=roomy["backup"] - 7))
    assert short.short_by == {"backup": 7, "project": 0} and short.free == {"backup": roomy["backup"] - 7, "project": roomy["project"]}
    not_enough_first = dict(roomy, backup=need["backup"] + stop_b - 1, project=roomy["project"] - 1)       # backup is listed first and is the worse of the two
    assert ci.room_check(found, not_enough_first).level is db.Level.NOT_ENOUGH, "a milder verdict later does not undo a worse one earlier"


def test_a_shared_drive_is_judged_once_for_both():
    found = vol(10 * MIB, 2.0)
    both = ci.room_check(found, {"project": 10 ** 13}, same_drive=True)
    separate = ci.room_check(found, {"backup": 10 ** 13, "project": 10 ** 13})
    assert set(both.need) == {"project"} and both.need["project"] == sum(separate.need.values())
    low = db.floors_for(db.DEFAULT_TABLE, True).low
    assert ci.room_check(found, {"project": both.need["project"] + low}, same_drive=True).level is db.Level.ENOUGH
    assert ci.room_check(found, {"project": both.need["project"] + low - 1}, same_drive=True).level is db.Level.TIGHT


def test_a_place_that_cannot_be_read_is_not_judged():
    v = ci.room_check(vol(10 * MIB, 2.0), {"backup": None})
    assert v.level is db.Level.ENOUGH and v.short_by == {"backup": 0, "project": 0}


def test_not_enough_room_stops_the_step_before_anything_is_written_and_tight_does_not():
    found = vol(10 * MIB, 2.0)
    with pytest.raises(ci.CopyInError) as caught:
        ci.require_room(ci.room_check(found, {"backup": 1, "project": 10 ** 13}))
    assert caught.value.code == "no_room" and "backup" in caught.value.detail and "project" not in caught.value.detail
    need = ci.room_check(found, {}).need
    tight = ci.room_check(found, {"backup": need["backup"] + db.floors_for(db.DEFAULT_TABLE, False).low - 1, "project": 10 ** 13})
    assert tight.level is db.Level.TIGHT
    ci.require_room(tight)
    ci.require_room(ci.room_check(found, {"backup": 10 ** 13, "project": 10 ** 13}))


# ---------------------------------------------------------------- the checked backup

def test_the_backup_is_made_checked_and_holds_exactly_the_recordings(old, tmp_path):
    from freeform_studio import backup as ffb
    us = found_en_us(old)
    info = ci.make_backup(us, str(tmp_path / "backups"))
    assert Path(info.path).is_file() and info.takes == 3 and info.files == us.files and info.archive_bytes == Path(info.path).stat().st_size
    problems, manifest = ffb.verify(Path(info.path))
    assert problems == [] and sorted(e["path"] for e in manifest["files"]) == sorted(n for _, n, _, _ in ffb.collect(old, "en-US"))
    assert not any("token" in e["path"] or "audio.wav" in e["path"] or "incoming" in e["path"] for e in manifest["files"])


def test_making_the_backup_never_touches_the_older_folder(old, tmp_path):
    before = tree(old)
    ci.make_backup(found_en_us(old), str(tmp_path / "backups"))
    assert tree(old) == before


def test_a_new_backup_is_made_every_time_and_no_old_backup_is_ever_pruned(old, tmp_path):
    folder = tmp_path / "backups"
    folder.mkdir()
    names = ["freeform-backup-en-US-2020%02d%02d-120000.tar.gz" % (m, d) for m in range(1, 5) for d in range(1, 11)]
    for name in names:
        (folder / name).write_bytes(b"an earlier backup")
    first = ci.make_backup(found_en_us(old), str(folder))
    second = ci.make_backup(found_en_us(old), str(folder))
    assert first.path != second.path and Path(first.path).is_file() and Path(second.path).is_file(), "nothing changed, and still a fresh one is made"
    assert all((folder / name).read_bytes() == b"an earlier backup" for name in names), "keep=0: not one earlier backup is removed"


def test_a_backup_folder_inside_the_recordings_is_refused_in_plain_words(old):
    with pytest.raises(ci.CopyInError) as caught:
        ci.make_backup(found_en_us(old), str(old / "_freeform" / "backups"))
    assert caught.value.code == "backup_failed" and "would back itself up" in caught.value.detail
    assert not (old / "_freeform" / "backups").exists()


def test_a_backup_folder_that_cannot_be_made_is_a_plain_failure_not_a_crash(old, tmp_path):
    (tmp_path / "a-file").write_text("not a folder")
    with pytest.raises(ci.CopyInError) as caught:
        ci.make_backup(found_en_us(old), str(tmp_path / "a-file" / "backups"))
    assert caught.value.code == "backup_failed"


def test_a_folder_with_nothing_to_back_up_says_so(tmp_path):
    with pytest.raises(ci.CopyInError) as caught:
        ci.make_backup(ci.OldRecordings(str(tmp_path), "en-US", 1, 1, 1, 0.0, 0), str(tmp_path / "backups"))
    assert caught.value.code == "no_recordings" and not (tmp_path / "backups").exists()


def test_a_backup_that_does_not_read_back_the_second_time_is_refused(old, tmp_path, monkeypatch):
    real = ci.ffbackup.verify
    calls = []

    def second_look_fails(path):
        calls.append(path)
        return (["x.bin: does not match its checksum"], None) if len(calls) >= 2 else real(path)

    monkeypatch.setattr(ci.ffbackup, "verify", second_look_fails)
    with pytest.raises(ci.CopyInError) as caught:
        ci.make_backup(found_en_us(old), str(tmp_path / "backups"))
    assert caught.value.code == "backup_failed" and caught.value.problems == ("x.bin: does not match its checksum",) and len(calls) == 2


def test_the_backup_is_readable_by_its_owner_only(old, tmp_path):
    previous = os.umask(0o022)
    try:
        info = ci.make_backup(found_en_us(old), str(tmp_path / "backups"))
    finally:
        os.umask(previous)
    assert stat.S_IMODE(Path(info.path).stat().st_mode) & 0o077 == 0


# ---------------------------------------------------------------- copying, adding only

@pytest.fixture
def backed_up(old, tmp_path):
    us = found_en_us(old)
    return us, ci.make_backup(us, str(tmp_path / "backups")), str(tmp_path / "project" / "recordings")


def project_files(recordings, code="en-US"):
    root = Path(recordings) / "_freeform" / code / "takes"
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(root.rglob("*")) if p.is_file()} if root.is_dir() else {}


def old_files(old, code="en-US"):
    root = Path(old) / "_freeform" / code / "takes"
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(root.rglob("*")) if p.is_file() and p.name not in ("audio.wav", "peaks.json")}


def test_the_preview_says_what_would_be_added_and_writes_nothing(backed_up):
    us, info, project = backed_up
    plan = ci.preview_copy(info.path, project, "en-US")
    assert plan == ci.CopyPlan(us.files, 0, 0, tuple(sorted(plan.takes))) and len(plan.takes) == 3
    assert not Path(project).exists(), "looking creates nothing, not even the folder"


def test_the_copy_puts_exactly_the_backups_recordings_in_the_project_and_checks_them(old, backed_up):
    us, info, project = backed_up
    before = tree(old)
    result = ci.copy_in(us, info.path, project)
    assert (result.added, result.same, result.kept_aside, result.aside_dir, result.checked) == (us.files, 0, 0, None, us.files)
    assert project_files(project) == old_files(old), "byte for byte, and without the decoded copy, the token or the packages"
    assert tree(old) == before, "the older folder is exactly as it was"


def test_copying_again_adds_nothing_and_checks_everything_again(backed_up):
    us, info, project = backed_up
    ci.copy_in(us, info.path, project)
    again = ci.copy_in(us, info.path, project)
    assert (again.added, again.same, again.kept_aside, again.checked) == (0, us.files, 0, us.files) and again.takes == ()


def test_a_file_the_project_already_has_in_another_form_is_kept_and_the_older_one_is_put_beside_it(old, backed_up):
    us, info, project = backed_up
    take_id = sorted(p.name for p in (old / "_freeform" / "en-US" / "takes").iterdir())[0]
    mine = Path(project) / "_freeform" / "en-US" / "takes" / take_id / "edit.json"
    mine.parent.mkdir(parents=True)
    mine.write_text('{"schema": 1, "rev": 9, "segments": ["my own edit"]}')
    plan = ci.preview_copy(info.path, project, "en-US")
    assert plan.differ == 1 and plan.to_add == us.files - 1
    result = ci.copy_in(us, info.path, project)
    assert result.kept_aside == 1 and result.added == us.files - 1 and result.checked == us.files
    assert mine.read_text() == '{"schema": 1, "rev": 9, "segments": ["my own edit"]}', "the project's own file is never replaced"
    assert (Path(result.aside_dir) / take_id / "edit.json").read_text() == (old / "_freeform" / "en-US" / "takes" / take_id / "edit.json").read_text()


def test_the_copy_is_readable_by_its_owner_only(backed_up):
    us, info, project = backed_up
    previous = os.umask(0o022)
    try:
        ci.copy_in(us, info.path, project)
    finally:
        os.umask(previous)
    for path in Path(project).rglob("*"):
        if path.is_file():
            assert stat.S_IMODE(path.stat().st_mode) & 0o077 == 0, path


def test_copying_into_the_older_folder_or_from_inside_it_is_refused_before_anything_is_written(old, backed_up):
    us, info, _ = backed_up
    before = tree(old)
    for place in (old, old / "_freeform", old / "_freeform" / "en-US" / "takes", old.parent):
        with pytest.raises(ci.CopyInError) as caught:
            ci.copy_in(us, info.path, str(place))
        assert caught.value.code == "same_place"
    assert tree(old) == before


def test_a_backup_that_is_not_there_or_is_damaged_copies_nothing(backed_up, tmp_path):
    us, info, project = backed_up
    with pytest.raises(ci.CopyInError) as caught:
        ci.copy_in(us, str(tmp_path / "gone.tar.gz"), project)
    assert caught.value.code == "copy_failed" and not Path(project).exists()
    damaged = tmp_path / "damaged.tar.gz"
    data = bytearray(Path(info.path).read_bytes())
    data[len(data) // 2] ^= 1
    damaged.write_bytes(data)
    with pytest.raises(ci.CopyInError) as caught:
        ci.copy_in(us, str(damaged), project)
    assert caught.value.code == "copy_failed" and not Path(project).exists()
    with pytest.raises(ci.CopyInError) as caught:
        ci.preview_copy(str(damaged), project, "en-US")
    assert caught.value.code == "copy_failed"


# ---------------------------------------------------------------- the check afterwards

def test_the_check_finds_a_file_that_is_missing_changed_or_cut_short(backed_up):
    us, info, project = backed_up
    ci.copy_in(us, info.path, project)
    files = sorted((Path(project) / "_freeform" / "en-US" / "takes").rglob("raw.webm"))
    files[0].write_bytes(files[0].read_bytes() + b"x")
    files[1].unlink()
    with pytest.raises(ci.CopyInError) as caught:
        ci.verify_copy(info.path, project, "en-US", None)
    assert caught.value.code == "verify_failed" and "2 file(s)" in caught.value.detail and len(caught.value.problems) == 2
    assert all("raw.webm" in p for p in caught.value.problems)


def test_a_file_kept_beside_the_project_s_own_counts_only_if_it_is_the_backups_copy(old, backed_up):
    us, info, project = backed_up
    take_id = sorted(p.name for p in (old / "_freeform" / "en-US" / "takes").iterdir())[0]
    mine = Path(project) / "_freeform" / "en-US" / "takes" / take_id / "edit.json"
    mine.parent.mkdir(parents=True)
    mine.write_text("different")
    result = ci.copy_in(us, info.path, project)
    assert ci.verify_copy(info.path, project, "en-US", result.aside_dir) == us.files
    with pytest.raises(ci.CopyInError):
        ci.verify_copy(info.path, project, "en-US", None), "without the place the older copy was put, the file counts as different"
    (Path(result.aside_dir) / take_id / "edit.json").write_text("tampered")
    with pytest.raises(ci.CopyInError):
        ci.verify_copy(info.path, project, "en-US", result.aside_dir)


def test_the_list_of_what_is_wrong_is_short_but_the_count_is_whole(backed_up):
    us, info, project = backed_up
    ci.copy_in(us, info.path, project)
    for path in list((Path(project) / "_freeform" / "en-US" / "takes").rglob("*.json"))[:7]:
        path.unlink()
    with pytest.raises(ci.CopyInError) as caught:
        ci.verify_copy(info.path, project, "en-US", None)
    assert "7 file(s)" in caught.value.detail and len(caught.value.problems) == 5


def test_a_backup_that_cannot_be_read_back_fails_the_check(backed_up, tmp_path):
    us, info, project = backed_up
    ci.copy_in(us, info.path, project)
    bad = tmp_path / "bad.tar.gz"
    bad.write_bytes(b"not an archive")
    with pytest.raises(ci.CopyInError) as caught:
        ci.verify_copy(str(bad), project, "en-US", None)
    assert caught.value.code == "verify_failed"


# ---------------------------------------------------------------- the pieces around it

def test_the_backups_have_their_own_default_place_outside_every_project():
    home = DataHome("/home/anna")
    assert home.backups == "/home/anna/ack-voice-studio/backups" and not home.backups.startswith(home.projects)


def test_the_repair_command_runs_freeform_studios_repair_from_the_tools_folder():
    studio = EnvPaths("/data/environments/studio-abc")
    c = commands.repair_command(studio, str(TOOLS), "/p/anna/recordings")
    assert c.argv == (studio.python, "-m", "freeform_studio.repair", "--output", "/p/anna/recordings", "--code", "en-US")
    assert c.kind == "repair" and c.cwd == str(TOOLS) and c.gpu is False
    _check_spec(c.job("anna"))
    with pytest.raises(commands.CommandError):
        commands.repair_command(studio, "/t", "relative/recordings")


def test_what_is_found_here_is_the_same_as_what_the_detector_counts(old, tmp_path):
    from voice_studio.core import legacy
    from voice_studio.core.system import System
    # the detector counts take folders per language under the older recorder's output folder; the survey counts the same ones
    home = tmp_path / "home"
    (home / "piper-recording-studio").mkdir(parents=True)
    shutil.copytree(old, home / "piper-recording-studio" / "output")

    class Real(System):
        def is_dir(self, path): return os.path.isdir(path)
        def exists(self, path): return os.path.exists(path)
        def listdir(self, path):
            try: return os.listdir(path)
            except OSError: return None

    findings = legacy.detect_legacy(Real.__new__(Real), str(home))
    assert findings.freeform_takes == sum(f.takes for f in ci.survey(str(home / "piper-recording-studio" / "output")))


# ---------------------------------------------------------------- with real audio, end to end

def test_recordings_copied_in_can_be_rebuilt_and_reviewed_with_the_repair_command(tmp_path):
    pytest.importorskip("numpy", reason="the repair command needs numpy (it is installed with Freeform Studio's environment)")
    if shutil.which("ffmpeg") is None:
        pytest.skip("ffmpeg is not installed")
    out = tmp_path / "old-output"
    _, folder = make_take(out, "en-US", 1, seconds=3.0, raw=b"")
    wav = write_tone(tmp_path / "tone.wav", 3.0)
    subprocess.run(["ffmpeg", "-nostdin", "-y", "-loglevel", "error", "-i", str(wav), "-c:a", "libopus", "-f", "webm", str(folder / "raw.webm")], check=True)
    (folder / "audio.wav").write_bytes(wav.read_bytes())
    found = ci.survey(str(out))[0]
    info = ci.make_backup(found, str(tmp_path / "backups"))
    project = tmp_path / "project" / "recordings"
    result = ci.copy_in(found, info.path, str(project))
    copied = project / "_freeform" / "en-US" / "takes" / folder.name
    assert result.takes == (folder.name,) and not (copied / "audio.wav").exists(), "the decoded copy is not part of the backup"
    env = tmp_path / "env"
    (env / "venv" / "bin").mkdir(parents=True)
    launcher = env / "venv" / "bin" / "python"
    launcher.write_text('#!/bin/sh\nexec "%s" "$@"\n' % sys.executable)          # a link would lose the test environment's libraries; this keeps them
    launcher.chmod(0o755)
    command = commands.repair_command(EnvPaths(str(env)), str(TOOLS), str(project))
    done = subprocess.run(command.argv, cwd=command.cwd, capture_output=True, text=True, timeout=120, env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
    assert done.returncode == 0 and "Rebuilt the decoded audio for 1 recording(s)." in done.stdout, (done.stdout, done.stderr)
    assert (copied / "audio.wav").is_file() and (copied / "peaks.json").is_file()
    assert (out / "_freeform" / "en-US" / "takes" / folder.name / "audio.wav").read_bytes() == wav.read_bytes(), "the older folder still has its own decoded copy"
