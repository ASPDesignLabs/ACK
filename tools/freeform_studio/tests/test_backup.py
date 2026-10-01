import io
import json
import tarfile
from collections import namedtuple
from datetime import datetime, timedelta

import pytest

from freeform_studio import backup as bk

A = "t20260930-000001-aaaa"
B = "t20260930-000002-bbbb"
C = "t20260930-000003-cccc"
Usage = namedtuple("Usage", "total used free")


def make_take(out, take_id, raw=b"RAW AUDIO " * 100, status="ready", parts=None, extra=None):
    d = out / "_freeform" / "en-US" / "takes" / take_id
    d.mkdir(parents=True)
    (d / "take.json").write_text(json.dumps({"id": take_id, "status": status, "duration": 5.0}))
    (d / "edit.json").write_text(json.dumps({"rev": 3, "segments": [{"id": "s001", "text": "hello"}]}))
    (d / "asr.json").write_text(json.dumps({"engine": "fake"}))
    (d / "edit_history").mkdir()
    (d / "edit_history" / "edit-rev00001.json").write_text('{"rev": 1}')
    (d / "reference_history").mkdir()
    (d / "reference_history" / "ref-20260930-000000.txt").write_text("old reference")
    if raw is not None:
        (d / "raw.webm").write_bytes(raw)
    for derived in ("audio.wav", "peaks.json", "peaks_512.bin"):          # rebuilt from the raw audio, so not backed up
        (d / derived).write_bytes(b"derived " * 50)
    if parts:
        (d / "parts").mkdir()
        for i, blob in enumerate(parts):
            (d / "parts" / f"{i:06d}.bin").write_bytes(blob)
    for name, blob in (extra or {}).items():
        (d / name).write_bytes(blob)
    return d


def names(path):
    with tarfile.open(path, "r:gz") as t:
        return sorted(m.name for m in t.getmembers())


@pytest.fixture
def library(out_dir):
    make_take(out_dir, A)
    make_take(out_dir, B, raw=None, status="recording", parts=[b"one", b"two"])   # still being recorded: only loose parts exist
    return out_dir


def dest(tmp_path):
    return tmp_path / "backups"


# ------------------------------------------------------------------ what a backup holds
def test_a_backup_holds_the_raw_audio_and_every_decision_but_not_what_can_be_rebuilt(library, tmp_path):
    r = bk.create(library, "en-US", dest(tmp_path))
    assert not r.skipped and r.takes == 2 and r.path.name.startswith("freeform-backup-en-US-") and r.path.name.endswith(".tar.gz")
    got = names(r.path)
    assert got == sorted([bk.MANIFEST,
        f"takes/{A}/raw.webm", f"takes/{A}/take.json", f"takes/{A}/edit.json", f"takes/{A}/asr.json",
        f"takes/{A}/edit_history/edit-rev00001.json", f"takes/{A}/reference_history/ref-20260930-000000.txt",
        f"takes/{B}/take.json", f"takes/{B}/edit.json", f"takes/{B}/asr.json", f"takes/{B}/parts/000000.bin", f"takes/{B}/parts/000001.bin",
        f"takes/{B}/edit_history/edit-rev00001.json", f"takes/{B}/reference_history/ref-20260930-000000.txt"])
    assert not [n for n in got if "audio.wav" in n or "peaks" in n]
    problems, manifest = bk.verify(r.path)
    assert problems == [] and len(manifest["files"]) == len(got) - 1
    assert sorted(p.name for p in dest(tmp_path).iterdir()) == sorted([r.path.name, r.path.name + ".json", bk.STATE])
    assert not list(dest(tmp_path).glob("*.partial"))


def test_loose_parts_are_only_kept_until_the_audio_has_been_assembled(out_dir, tmp_path):
    make_take(out_dir, A, parts=[b"leftover"])                                     # has raw.webm AND parts
    assert not [n for n in names(bk.create(out_dir, "en-US", dest(tmp_path)).path) if "/parts/" in n]


def test_an_empty_library_makes_no_backup_and_no_folder(out_dir, tmp_path):
    r = bk.create(out_dir, "en-US", dest(tmp_path))
    assert r.skipped and "no recordings" in r.reason and not dest(tmp_path).exists()


# ------------------------------------------------------------------ doing nothing when nothing changed
def test_nothing_changed_means_no_new_backup_until_something_does_or_it_is_forced(library, tmp_path):
    first = bk.create(library, "en-US", dest(tmp_path))
    again = bk.create(library, "en-US", dest(tmp_path))
    assert again.skipped and "Nothing has changed" in again.reason and again.path == first.path
    assert len(bk.list_backups(dest(tmp_path))) == 1
    edit = library / "_freeform" / "en-US" / "takes" / A / "edit.json"
    edit.write_text(json.dumps({"rev": 4, "segments": []}))
    later = bk.create(library, "en-US", dest(tmp_path), now=datetime.now() + timedelta(seconds=5))
    assert not later.skipped and later.path != first.path
    forced = bk.create(library, "en-US", dest(tmp_path), force=True, now=datetime.now() + timedelta(seconds=9))
    assert not forced.skipped and len(bk.list_backups(dest(tmp_path))) == 3


def test_two_backups_in_the_same_second_get_different_names(library, tmp_path):
    t = datetime(2026, 9, 30, 12, 0, 0)
    a = bk.create(library, "en-US", dest(tmp_path), now=t)
    b = bk.create(library, "en-US", dest(tmp_path), force=True, now=t)
    assert a.path != b.path and b.path.name.endswith("-2.tar.gz")


# ------------------------------------------------------------------ refusing to do it badly
def test_a_backup_folder_inside_the_recordings_is_refused(library):
    with pytest.raises(bk.BackupError, match="would back itself up"):
        bk.create(library, "en-US", library / "_freeform" / "en-US" / "backups")


def test_not_enough_room_is_explained_and_nothing_is_left_behind(library, tmp_path, monkeypatch):
    monkeypatch.setattr(bk.shutil, "disk_usage", lambda p: Usage(10 ** 12, 10 ** 12 - 1000, 1000))
    with pytest.raises(bk.BackupError, match="Not enough room"):
        bk.create(library, "en-US", dest(tmp_path))
    assert not list(dest(tmp_path).glob("*.tar.gz*")) if dest(tmp_path).exists() else True


def test_a_backup_that_does_not_read_back_is_thrown_away(library, tmp_path, monkeypatch):
    monkeypatch.setattr(bk, "verify", lambda path: (["something is off"], None))
    with pytest.raises(bk.BackupError, match="thrown away"):
        bk.create(library, "en-US", dest(tmp_path))
    assert sorted(p.name for p in dest(tmp_path).iterdir()) == []                   # no partial, no half-made file, no state


def test_two_backups_at_once_are_not_allowed_but_a_crashed_lock_expires(library, tmp_path):
    dest(tmp_path).mkdir()
    lock = dest(tmp_path) / bk.LOCK
    lock.write_text("1")
    with pytest.raises(bk.BackupBusy):
        bk.create(library, "en-US", dest(tmp_path))
    import os, time
    old = time.time() - bk.STALE_LOCK_S - 5
    os.utime(lock, (old, old))
    assert not bk.create(library, "en-US", dest(tmp_path)).skipped and not lock.exists()


# ------------------------------------------------------------------ noticing damage
def test_damage_to_an_archive_is_detected(library, tmp_path):
    good = bk.create(library, "en-US", dest(tmp_path)).path
    raw = bytearray(good.read_bytes())
    bad = tmp_path / "flipped.tar.gz"
    bad.write_bytes(bytes(raw[:len(raw) // 2]) + bytes([raw[len(raw) // 2] ^ 0xFF]) + bytes(raw[len(raw) // 2 + 1:]))
    cut = tmp_path / "cut.tar.gz"
    cut.write_bytes(bytes(raw[: len(raw) - 40]))
    nope = tmp_path / "nope.tar.gz"
    nope.write_bytes(b"this is not an archive")
    for path in (bad, cut, nope):
        problems, _ = bk.verify(path)
        assert problems, path.name


def make_archive(path, members, manifest="auto"):
    """A hand-made archive: `members` is a list of (name, bytes or None for a symlink)."""
    import hashlib
    files = []
    with tarfile.open(path, "w:gz") as t:
        for name, data in members:
            info = tarfile.TarInfo(name)
            if data is None:
                info.type, info.linkname = tarfile.SYMTYPE, "/etc/passwd"
                t.addfile(info)
                continue
            info.size = len(data)
            t.addfile(info, io.BytesIO(data))
            files.append({"path": name, "size": len(data), "sha256": hashlib.sha256(data).hexdigest()})
        if manifest == "auto":
            blob = json.dumps({"schema": 1, "files": files}).encode()
            info = tarfile.TarInfo(bk.MANIFEST)
            info.size = len(blob)
            t.addfile(info, io.BytesIO(blob))
    return path


def test_a_tampered_or_incomplete_archive_is_not_trusted(tmp_path):
    ok = make_archive(tmp_path / "ok.tar.gz", [(f"takes/{A}/take.json", b"{}")])
    assert bk.verify(ok)[0] == []
    no_manifest = make_archive(tmp_path / "nm.tar.gz", [(f"takes/{A}/take.json", b"{}")], manifest=None)
    assert any("no manifest" in p for p in bk.verify(no_manifest)[0])
    twice = make_archive(tmp_path / "twice.tar.gz", [(f"takes/{A}/take.json", b"{}"), (f"takes/{A}/take.json", b"{ }")])
    assert any("more than once" in p for p in bk.verify(twice)[0])
    link = make_archive(tmp_path / "link.tar.gz", [(f"takes/{A}/take.json", b"{}"), (f"takes/{A}/edit.json", None)])
    assert any("not an ordinary file" in p for p in bk.verify(link)[0])


# ------------------------------------------------------------------ retention
def fake_backups(d, stamps, code="en-US"):
    d.mkdir(parents=True, exist_ok=True)
    for s in stamps:
        (d / f"freeform-backup-{code}-{s:%Y%m%d-%H%M%S}.tar.gz").write_bytes(b"x")
        (d / f"freeform-backup-{code}-{s:%Y%m%d-%H%M%S}.tar.gz.json").write_text("{}")


def test_old_backups_are_pruned_by_a_stated_rule_and_only_ones_this_tool_named(tmp_path):
    d = dest(tmp_path)
    start = datetime(2026, 1, 1, 12, 0, 0)
    fake_backups(d, [start + timedelta(days=i) for i in range(60)])                 # a backup every day for 60 days
    fake_backups(d, [start], code="de-DE")                                          # another language: not ours to prune here
    (d / "notes.txt").write_text("mine")
    (d / "freeform-backup-en-US-garbage.tar.gz").write_text("not a stamp")
    removed = bk.prune(d, "en-US", keep_recent=10, keep_weekly=4)
    kept = [b["name"] for b in bk.list_backups(d, "en-US")]
    assert len(kept) == 14 and len(removed) == 46                                   # the newest 10, then one per week for 4 weeks
    assert kept[0].endswith("20260301-120000.tar.gz")                               # the newest is always kept
    assert (d / "notes.txt").exists() and (d / "freeform-backup-en-US-garbage.tar.gz").exists()
    assert len(bk.list_backups(d, "de-DE")) == 1
    assert not [p for p in d.iterdir() if p.name.endswith(".json") and not (d / p.name[:-5]).exists()]   # no orphaned sidecars


def test_keep_zero_never_deletes_anything(library, tmp_path):
    d = dest(tmp_path)
    fake_backups(d, [datetime(2026, 1, 1) + timedelta(days=i) for i in range(40)])
    r = bk.create(library, "en-US", d, keep=0)
    assert r.pruned == [] and len(bk.list_backups(d)) == 41


def test_listing_shows_newest_first_with_what_each_holds(library, tmp_path):
    d = dest(tmp_path)
    bk.create(library, "en-US", d, now=datetime(2026, 9, 1, 8, 0, 0))
    bk.create(library, "en-US", d, force=True, now=datetime(2026, 9, 2, 8, 0, 0))
    (d / "freeform-backup-en-US-20260903-080000.tar.gz.partial").write_bytes(b"half")
    rows = bk.list_backups(d)
    assert [r["created"][:10] for r in rows] == ["2026-09-02", "2026-09-01"]
    assert rows[0]["takes"] == 2 and rows[0]["files"] == 13 and rows[0]["size"] > 0
    st = bk.status(d, "en-US", True)
    assert st["enabled"] and st["count"] == 2 and st["last"]["name"] == rows[0]["name"]
    assert bk.status(None, "en-US", True)["enabled"] is False


# ------------------------------------------------------------------ restoring (adds only)
def test_restore_adds_what_is_missing_and_changes_nothing_that_is_there(library, tmp_path, out_dir):
    archive = bk.create(library, "en-US", dest(tmp_path)).path
    fresh = tmp_path / "fresh_output"
    fresh.mkdir()
    dry = bk.restore(archive, fresh, "en-US", dry_run=True)
    assert len(dry.restored) == 13 and not (fresh / "_freeform").exists()          # a dry run writes nothing
    done = bk.restore(archive, fresh, "en-US")
    take = fresh / "_freeform" / "en-US" / "takes" / A
    assert (take / "raw.webm").read_bytes() == b"RAW AUDIO " * 100 and (take / "edit.json").exists()
    assert not (take / "audio.wav").exists()                                        # derived data is rebuilt separately
    assert done.takes == [A, B] and len(done.restored) == 13                      # B is still being recorded: listed, but there is nothing to rebuild yet
    again = bk.restore(archive, fresh, "en-US")
    assert again.restored == [] and len(again.same) == 13 and again.conflicts == []


def test_a_file_that_differs_is_left_alone_and_the_backups_copy_is_kept_aside(library, tmp_path):
    archive = bk.create(library, "en-US", dest(tmp_path)).path
    edit = library / "_freeform" / "en-US" / "takes" / A / "edit.json"
    mine = json.dumps({"rev": 9, "segments": ["newer work"]})
    edit.write_text(mine)
    report = bk.restore(archive, library, "en-US", now=datetime(2026, 10, 1, 9, 0, 0))
    assert edit.read_text() == mine                                                 # what you have is never overwritten
    assert report.conflicts == [f"takes/{A}/edit.json"] and report.restored == []
    kept = library / "_freeform" / "en-US" / "restored-conflicts" / "20261001-090000" / A / "edit.json"
    assert json.loads(kept.read_text())["rev"] == 3                                 # the backup's version is there to compare
    assert report.conflicts_dir == str(kept.parents[1])


def test_a_damaged_backup_restores_nothing(library, tmp_path):
    archive = bk.create(library, "en-US", dest(tmp_path)).path
    raw = bytearray(archive.read_bytes())
    raw[len(raw) // 3] ^= 0xFF
    archive.write_bytes(bytes(raw))
    fresh = tmp_path / "fresh"
    fresh.mkdir()
    with pytest.raises(bk.BackupError, match="can't be trusted"):
        bk.restore(archive, fresh, "en-US")
    assert not (fresh / "_freeform").exists()


@pytest.mark.parametrize("name", ["takes/../../evil.txt", "/etc/cron.d/evil", f"takes/{A}/../../../x.json", f"takes/{A}/audio.wav",
                                  f"takes/{A}/raw.exe", "takes/not-a-take-id/take.json", f"takes/{A}/sub/dir/take.json",
                                  f"takes\\{A}\\take.json", f"other/{A}/take.json", f"takes/{A}/edit_history/.hidden"])
def test_archives_naming_places_a_backup_never_writes_are_refused(tmp_path, name):
    evil = make_archive(tmp_path / "evil.tar.gz", [(f"takes/{A}/take.json", b"{}"), (name, b"payload")])
    target = tmp_path / "out"
    target.mkdir()
    with pytest.raises(bk.BackupError, match="don't belong|can't be trusted"):
        bk.restore(evil, target, "en-US")
    assert list(target.iterdir()) == [] and not (tmp_path / "evil.txt").exists()          # not even the harmless file was written


# ------------------------------------------------------------------ the command line
def test_the_command_line_backs_up_lists_verifies_and_restores(library, tmp_path, capsys):
    base = ["--output", str(library), "--backup-dir", str(dest(tmp_path))]
    assert bk.main(base) == 0
    assert "Backed up 2 recordings" in capsys.readouterr().out
    assert bk.main(base) == 0 and "Nothing has changed" in capsys.readouterr().out
    assert bk.main([*base, "--list"]) == 0 and "2 recordings" in capsys.readouterr().out
    archive = bk.list_backups(dest(tmp_path))[0]["path"]
    assert bk.main(["--verify", archive]) == 0 and "OK: 13 files" in capsys.readouterr().out
    fresh = tmp_path / "fresh"
    fresh.mkdir()
    assert bk.main(["--output", str(fresh), "--restore", archive, "--dry-run"]) == 0
    assert "DRY RUN" in capsys.readouterr().out and not (fresh / "_freeform").exists()
    (tmp_path / "junk.tar.gz").write_bytes(b"junk")
    assert bk.main(["--verify", str(tmp_path / "junk.tar.gz")]) == 1
    assert bk.main([*base, "--restore", str(tmp_path / "junk.tar.gz")]) == 2 and "Can't continue" in capsys.readouterr().err
