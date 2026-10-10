# SPDX-License-Identifier: GPL-3.0-or-later
"""Bringing an ACK package into a project (plan task VS-2.4), with real packages made the way ACK writes them (Freeform Studio's own test builder)."""
import hashlib
import os
import stat
import sys
from pathlib import Path

import pytest

pytest.importorskip("numpy", reason="the package builder used here needs numpy (it is installed with Freeform Studio's environment)")
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "freeform_studio" / "tests"))

from ack_package_builder import ClipSpec, PackageBuilder, write_zip      # noqa: E402

from freeform_studio.config import Config                                  # noqa: E402
from freeform_studio.storage import TakeStore                              # noqa: E402
from voice_studio.core import ackimport as ai                              # noqa: E402

TEXTS = ["The tide came in.", "We walked along the shore.", "Gulls circled overhead."]


def make_package(tmp_path, name="p.zip", free=True):
    b = PackageBuilder()
    b.script_session([ClipSpec(TEXTS[0], speech=2.0), ClipSpec(TEXTS[1], speech=3.0), ClipSpec(TEXTS[2], speech=1.5)])
    if free:
        b.free_session([(0.4, 3.0), (0.5, 7.0), (0.4, 4.0)], topic="my morning")
    folder = tmp_path / "phone"
    folder.mkdir(parents=True, exist_ok=True)
    return b.write(folder / name)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


@pytest.fixture
def recordings(tmp_path):
    return tmp_path / "project" / "recordings"


def takes(recordings):
    return TakeStore(Config(output_dir=recordings).takes_dir)


# ---------------------------------------------------------------- the file name

@pytest.mark.parametrize("given, expected", [
    ("/phone/ack-training-20261002-193000.zip", "ack-training-20261002-193000.zip"), ("/a/B C.zip", "B C.zip"), ("/a/b.ZIP", "b.zip"),
    ("/a/we!rd*name?.zip", "we-rd-name.zip"), ("/a/.hidden.zip", "hidden.zip"), ("/a/.zip", "ack-package.zip"), ("/a/---.zip", "ack-package.zip"),
    ("/a/noextension", "noextension.zip"), ("/a/ünï.zip", "n.zip"), ("", "package.zip"), ("/a/" + "x" * 300 + ".zip", "x" * 96 + ".zip"), ("/a/b/", "b.zip"),
])
def test_the_copys_name_is_a_safe_version_of_the_original_and_always_passes_the_incoming_rule(given, expected):
    name = ai.safe_name(given)
    assert ai.NAME_RE.match(name), name
    assert name == expected or (expected == "n.zip" and name in ("n.zip", "ack-package.zip"))


# ---------------------------------------------------------------- looking

def test_a_good_package_is_copied_in_checked_and_summarised_without_adding_anything(tmp_path, recordings):
    path = make_package(tmp_path)
    before = path.read_bytes()
    prepared = ai.prepare(str(path), recordings)
    s = prepared.summary
    assert prepared.copy_was_new and prepared.copy.parent == ai.incoming_dir(recordings) and prepared.copy.name == "p.zip"
    assert prepared.copy.read_bytes() == before == path.read_bytes(), "a byte-for-byte copy, and the original untouched"
    assert [(x.mode, x.state, x.clips) for x in s.sessions] == [("script", "new", 3), ("free", "new", 0)]
    assert s.to_add == 2 and s.audio_files == 4 and s.package_bytes > 0 and s.app_version and s.created
    assert abs(s.minutes_total - s.minutes_new) < 1e-9 and s.minutes_total > 0.4 and s.enough_room and s.need_mb > 0 and s.free_mb > s.need_mb
    assert not takes(recordings).ids(), "looking added no recording"


def test_the_summary_lists_the_sessions_in_the_packages_order_with_their_minutes_and_labels(tmp_path, recordings):
    s = ai.prepare(str(make_package(tmp_path)), recordings).summary
    script, free = s.sessions
    assert script.seconds > 6 and free.seconds > 13 and free.label.strip() != ""
    assert s.to_add == 2 and round(sum(x.seconds for x in s.sessions) / 60, 2) == s.minutes_total


def test_the_copy_and_the_checks_report_their_progress(tmp_path, recordings):
    seen = []
    ai.prepare(str(make_package(tmp_path)), recordings, progress=lambda stage, done, total: seen.append((stage, done, total)))
    stages = [s for s, _, _ in seen]
    assert stages[0] == "copy" and "check" in stages and stages.index("check") > max(i for i, s in enumerate(stages) if s == "copy")
    copy = [(d, t) for s, d, t in seen if s == "copy"]
    assert copy[-1][0] == copy[-1][1] > 0
    check = [(d, t) for s, d, t in seen if s == "check"]
    assert check[-1][0] == check[-1][1] > 0


def test_nothing_the_package_made_is_readable_by_other_accounts(tmp_path, recordings):
    old = os.umask(0o022)
    try:
        prepared = ai.prepare(str(make_package(tmp_path)), recordings)
    finally:
        os.umask(old)
    assert stat.S_IMODE(prepared.copy.stat().st_mode) == 0o600
    assert stat.S_IMODE(prepared.copy.parent.stat().st_mode) & 0o077 == 0


def test_only_some_sessions_can_be_chosen(tmp_path, recordings):
    path = make_package(tmp_path)
    full = ai.prepare(str(path), recordings)
    first = full.summary.sessions[0].id
    part = ai.prepare(str(path), recordings, only=[first])
    assert [s.id for s in part.summary.sessions] == [first] and part.summary.to_add == 1


def test_an_unknown_session_is_a_problem_and_the_copy_that_call_made_is_removed(tmp_path, recordings):
    path = make_package(tmp_path)
    with pytest.raises(ai.AckImportError) as caught:
        ai.prepare(str(path), recordings, only=["s20990101-000000-ffff"])
    assert caught.value.code == "problem" and "no session" in caught.value.detail
    assert not list(ai.incoming_dir(recordings).glob("*.zip"))


# ---------------------------------------------------------------- the copy

def test_the_same_package_chosen_again_reuses_its_copy(tmp_path, recordings):
    path = make_package(tmp_path)
    first = ai.prepare(str(path), recordings)
    again = ai.prepare(str(path), recordings)
    assert again.copy == first.copy and not again.copy_was_new and len(list(ai.incoming_dir(recordings).glob("*.zip"))) == 1


def test_a_different_package_with_the_same_name_never_replaces_the_first(tmp_path, recordings):
    first_path = make_package(tmp_path / "one", free=True)
    second_path = make_package(tmp_path / "two", free=False)
    assert sha(first_path) != sha(second_path)
    a = ai.prepare(str(first_path), recordings)
    b = ai.prepare(str(second_path), recordings)
    assert a.copy.name == "p.zip" and b.copy.name == "p-2.zip" and sha(a.copy) == sha(first_path) and sha(b.copy) == sha(second_path)


def test_a_symlink_or_stray_file_with_the_name_is_never_overwritten(tmp_path, recordings):
    path = make_package(tmp_path)
    folder = ai.incoming_dir(recordings)
    folder.mkdir(parents=True)
    victim = tmp_path / "victim.txt"
    victim.write_text("keep me")
    (folder / "p.zip").symlink_to(victim)
    prepared = ai.prepare(str(path), recordings)
    assert prepared.copy.name == "p-2.zip" and victim.read_text() == "keep me" and (folder / "p.zip").is_symlink()


def test_a_leftover_half_copy_from_a_stopped_attempt_is_replaced_by_the_next_one(tmp_path, recordings):
    path = make_package(tmp_path)
    folder = ai.incoming_dir(recordings)
    folder.mkdir(parents=True)
    (folder / "p.zip.part").write_bytes(b"half of a")
    prepared = ai.prepare(str(path), recordings)
    assert prepared.copy.read_bytes() == path.read_bytes() and not (folder / "p.zip.part").exists()


def test_a_file_that_changes_while_being_copied_is_not_trusted(tmp_path, recordings, monkeypatch):
    path = make_package(tmp_path)
    real = ai._sha256
    calls = {"n": 0}

    def lying(p):
        calls["n"] += 1
        digest, size = real(p)
        return ("0" * 64, size) if calls["n"] == 2 else (digest, size)          # the second look (the copy, read back) does not match

    monkeypatch.setattr(ai, "_sha256", lying)
    with pytest.raises(ai.AckImportError) as caught:
        ai.prepare(str(path), recordings)
    assert caught.value.code == "copy_failed" and not list(ai.incoming_dir(recordings).glob("p.zip*"))


def test_a_copy_that_cannot_be_written_is_a_plain_failure_and_leaves_no_part_file(tmp_path, recordings, monkeypatch):
    path = make_package(tmp_path)
    real_replace = os.replace

    def broken(src, dst):
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(ai.os, "replace", broken)
    with pytest.raises(ai.AckImportError) as caught:
        ai.prepare(str(path), recordings)
    monkeypatch.setattr(ai.os, "replace", real_replace)
    assert caught.value.code == "copy_failed" and caught.value.detail == "No space left on device" and not list(ai.incoming_dir(recordings).glob("*"))


def test_there_must_be_room_for_the_copy_and_the_margin_at_the_exact_edge(tmp_path, recordings, monkeypatch):
    path = make_package(tmp_path)
    size_mb = path.stat().st_size / (1024 * 1024)
    margin = Config(output_dir=recordings).min_free_mb
    monkeypatch.setattr(ai, "_free_mb", lambda p: margin + size_mb - 0.001)
    with pytest.raises(ai.AckImportError) as caught:
        ai.prepare(str(path), recordings)
    assert caught.value.code == "no_room" and not list(ai.incoming_dir(recordings).glob("*.zip"))
    monkeypatch.setattr(ai, "_free_mb", lambda p: margin + size_mb)
    assert ai.prepare(str(path), recordings).copy.exists()


# ---------------------------------------------------------------- what is not a good package

def test_a_path_that_is_not_a_file_is_named(tmp_path, recordings):
    with pytest.raises(ai.AckImportError) as caught:
        ai.prepare(str(tmp_path / "nope.zip"), recordings)
    assert caught.value.code == "not_a_file" and caught.value.detail == "nope.zip"
    with pytest.raises(ai.AckImportError) as caught:
        ai.prepare(str(tmp_path), recordings)
    assert caught.value.code == "not_a_file"
    assert not recordings.exists()


def test_a_file_that_is_not_a_zip_is_refused_before_anything_is_copied(tmp_path, recordings):
    bad = tmp_path / "notes.zip"
    bad.write_text("this is not a zip")
    with pytest.raises(ai.AckImportError) as caught:
        ai.prepare(str(bad), recordings)
    assert caught.value.code == "not_a_zip" and not recordings.exists()


def test_a_zip_that_is_not_an_ack_package_is_refused_with_the_reason_and_leaves_nothing(tmp_path, recordings):
    other = tmp_path / "photos.zip"
    write_zip(other, [("holiday.jpg", b"not a picture")])
    with pytest.raises(ai.AckImportError) as caught:
        ai.prepare(str(other), recordings)
    assert caught.value.code == "package" and "holiday.jpg" in caught.value.detail and "Nothing was imported" in caught.value.detail
    assert not list(ai.incoming_dir(recordings).glob("*")) and other.exists()


def test_a_package_with_a_damaged_audio_file_says_which_and_leaves_nothing(tmp_path, recordings):
    path = make_package(tmp_path)
    import zipfile
    damaged = tmp_path / "phone" / "damaged.zip"
    with zipfile.ZipFile(path) as src, zipfile.ZipFile(damaged, "w") as dst:
        for info in src.infolist():
            data = src.read(info.filename)
            if info.filename.endswith("session.wav"):
                data = data[:-10] + b"0123456789"
            dst.writestr(info, data)
    with pytest.raises(ai.AckImportError) as caught:
        ai.prepare(str(damaged), recordings)
    assert caught.value.code == "package" and caught.value.detail
    assert not list(ai.incoming_dir(recordings).glob("*.zip")) and not takes(recordings).ids()


def test_a_bad_package_whose_copy_was_not_made_by_this_call_leaves_that_copy_alone(tmp_path, recordings):
    other = tmp_path / "phone" / "photos.zip"
    other.parent.mkdir(parents=True)
    write_zip(other, [("holiday.jpg", b"not a picture")])
    folder = ai.incoming_dir(recordings)
    folder.mkdir(parents=True)
    (folder / "photos.zip").write_bytes(other.read_bytes())              # an identical copy was put there earlier
    with pytest.raises(ai.AckImportError) as caught:
        ai.prepare(str(other), recordings)
    assert caught.value.code == "package" and (folder / "photos.zip").read_bytes() == other.read_bytes()


def test_too_big_a_file_is_refused(tmp_path, recordings, monkeypatch):
    path = make_package(tmp_path)
    monkeypatch.setattr(ai, "MAX_PACKAGE_BYTES", path.stat().st_size - 1)
    with pytest.raises(ai.AckImportError) as caught:
        ai.prepare(str(path), recordings)
    assert caught.value.code == "too_big"
    monkeypatch.setattr(ai, "MAX_PACKAGE_BYTES", path.stat().st_size)
    assert ai.prepare(str(path), recordings).copy.exists()


def test_a_file_that_cannot_be_read_is_unreadable(tmp_path, recordings, monkeypatch):
    path = make_package(tmp_path)
    real_stat = Path.stat

    def broken(self, *a, **k):
        if self.name == "p.zip" and "phone" in str(self):
            raise OSError(13, "Permission denied")
        return real_stat(self, *a, **k)

    monkeypatch.setattr(Path, "stat", broken)
    with pytest.raises(ai.AckImportError) as caught:
        ai.prepare(str(path), recordings)
    assert caught.value.code == "unreadable" and caught.value.detail == "Permission denied" and not recordings.exists()


# ---------------------------------------------------------------- adding

def test_adding_makes_one_recording_per_session_ready_for_the_server_to_finish(tmp_path, recordings):
    prepared = ai.prepare(str(make_package(tmp_path)), recordings)
    created = ai.add(prepared)
    assert len(created) == 2 and sorted(c.session for c in created) == sorted(s.id for s in prepared.summary.sessions)
    store = takes(recordings)
    assert sorted(store.ids()) == sorted(c.take_id for c in created)
    assert {store.get(c.take_id)["status"] for c in created} == {"finishing"}


def test_what_adding_writes_is_readable_by_the_owner_only(tmp_path, recordings):
    prepared = ai.prepare(str(make_package(tmp_path)), recordings)
    old = os.umask(0o022)
    try:
        created = ai.add(prepared)
    finally:
        os.umask(old)
    folder = Config(output_dir=recordings).takes_dir / created[0].take_id
    for p in folder.iterdir():
        assert stat.S_IMODE(p.stat().st_mode) & 0o077 == 0, p


def test_adding_twice_adds_nothing_the_second_time(tmp_path, recordings):
    path = make_package(tmp_path)
    ai.add(ai.prepare(str(path), recordings))
    again = ai.prepare(str(path), recordings)
    assert again.summary.to_add == 0 and [s.state for s in again.summary.sessions] == ["already", "already"] and again.summary.minutes_new == 0
    assert ai.add(again) == [] and len(takes(recordings).ids()) == 2
    assert all(s.take_id for s in again.summary.sessions)


def test_a_package_with_one_old_session_and_one_new_adds_only_the_new_one(tmp_path, recordings):
    b = PackageBuilder()
    first = b.script_session([ClipSpec(TEXTS[0], speech=2.0)])
    second = b.script_session([ClipSpec(TEXTS[1], speech=2.0)])
    path = b.write(tmp_path / "two.zip")
    ai.add(ai.prepare(str(path), recordings, only=[first]))
    again = ai.prepare(str(path), recordings)
    assert [(s.id, s.state) for s in again.summary.sessions] == [(first, "already"), (second, "new")] and again.summary.to_add == 1
    assert 0 < again.summary.minutes_new < again.summary.minutes_total
    created = ai.add(again)
    assert [c.session for c in created] == [second] and len(takes(recordings).ids()) == 2


def test_not_enough_room_to_add_writes_nothing(tmp_path, recordings):
    prepared = ai.prepare(str(make_package(tmp_path)), recordings)
    prepared.plan.free_mb = 1.0
    with pytest.raises(ai.AckImportError) as caught:
        ai.add(prepared)
    assert caught.value.code == "no_room" and "nothing was written" in caught.value.detail.lower() and not takes(recordings).ids()


def test_the_error_codes_are_listed_once_each():
    assert len(set(ai.ERROR_CODES)) == len(ai.ERROR_CODES) == 8
    assert str(ai.AckImportError("package", "why")) == "package: why" and ai.AckImportError("package", "", ["a", "b"]).problems == ("a", "b")
