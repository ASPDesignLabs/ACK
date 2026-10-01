import json
import os
import time
import wave
from pathlib import Path

import numpy as np
import pytest

from conftest import needs_ffmpeg
from freeform_studio import export as ex
from test_build_dataset import read_wav, seg, write_take

pytestmark = needs_ffmpeg
A = "t20260930-000001-aaaa"
B = "t20260930-000002-bbbb"


def folder(out_dir):
    return out_dir / "en-US" / "freeform"


def retired(out_dir):
    return out_dir / "_freeform" / "en-US" / "retired"


def approved(i, a, b, text="hello there.", **kw):
    s = seg(i, a, b, text, status="approved")
    s.update(kw)
    return s


def edit_take(out_dir, take_id, change):
    path = out_dir / "_freeform" / "en-US" / "takes" / take_id / "edit.json"
    doc = json.loads(path.read_text())
    change(doc["segments"])
    path.write_text(json.dumps(doc))


def by_id(segs, sid):
    return next(s for s in segs if s["id"] == sid)


def files(d):
    return sorted(p.name for p in d.iterdir()) if d.exists() else []


@pytest.fixture
def take_a(out_dir):
    write_take(out_dir, A, [
        approved(1, 0.0, 3.0, "First clip."),
        seg(2, 3.0, 6.0, "Not approved yet."),
        approved(3, 6.0, 9.0, "Tagged as a laugh.", tags=["laugh"]),
        approved(4, 9.0, 9.5, "Too short."),
        seg(5, 10.0, 13.0, "Dropped one.", status="dropped"),
        approved(6, 13.0, 16.0, "Cut through a word.", flags=["cuts_word"]),
        approved(7, 16.0, 20.0, "Second good clip, with | removed? no."),
    ], seconds=30.0)
    edit_take(out_dir, A, lambda s: by_id(s, "s007").update(text="Second good clip."))
    return A


# ------------------------------------------------------------------ what gets written
def test_only_approved_qualifying_pieces_are_written_in_the_recorders_layout(out_dir, take_a):
    plan = ex.apply(out_dir, "en-US")
    stems = [f"{A}_s001", f"{A}_s007"]
    assert files(folder(out_dir)) == sorted([".presplit", "manifest.json"] + [f"{s}.{e}" for s in stems for e in ("txt", "wav")])
    for stem, text in zip(stems, ("First clip.", "Second good clip.")):
        x, rate, channels, width = read_wav(folder(out_dir) / f"{stem}.wav")
        assert (rate, channels, width) == (22050, 1, 2)
        assert (folder(out_dir) / f"{stem}.txt").read_text() == text + "\n"
    assert plan.counts() == {"new": 2, "updated": 0, "unchanged": 0, "retired": 0, "left_out": 3}
    left = {e["seg"]: e["reason"] for e in plan.left_out}
    assert "tagged: laugh" in left["s003"] and left["s004"].startswith("too short") and "inside a word" in left["s006"]
    assert plan.report()["left_out_by_reason"]["tagged: laugh"] == 1
    manifest = json.loads((folder(out_dir) / "manifest.json").read_text())
    assert set(manifest["items"]) == set(stems) and manifest["items"][stems[0]]["take"] == A
    assert all(ex.STEM_RE.match(s) for s in stems)                    # names are predictable and safe


def test_a_preview_writes_nothing_and_matches_what_the_export_then_does(out_dir, take_a):
    before = sorted(str(p) for p in out_dir.rglob("*"))
    preview = ex.make_plan(out_dir, "en-US")
    assert sorted(str(p) for p in out_dir.rglob("*")) == before        # not even the folder
    assert not folder(out_dir).exists()
    done = ex.apply(out_dir, "en-US")
    assert preview.counts() == done.counts()
    assert [i["stem"] for i in preview.new] == [i["stem"] for i in done.new]


def test_running_again_changes_nothing(out_dir, take_a):
    ex.apply(out_dir, "en-US")
    stamps = {p.name: p.stat().st_mtime_ns for p in folder(out_dir).iterdir() if p.suffix in (".wav", ".txt")}
    again = ex.apply(out_dir, "en-US")
    assert again.counts()["new"] == again.counts()["updated"] == again.counts()["retired"] == 0 and again.counts()["unchanged"] == 2
    assert {p.name: p.stat().st_mtime_ns for p in folder(out_dir).iterdir() if p.suffix in (".wav", ".txt")} == stamps
    assert not retired(out_dir).exists()


# ------------------------------------------------------------------ nothing is ever deleted
def test_a_changed_piece_replaces_its_clip_and_the_old_version_is_kept(out_dir, take_a):
    ex.apply(out_dir, "en-US")
    edit_take(out_dir, A, lambda s: by_id(s, "s001").update(text="First clip, corrected.", end=2.5))
    plan = ex.apply(out_dir, "en-US")
    assert plan.counts()["updated"] == 1 and plan.counts()["unchanged"] == 1
    assert (folder(out_dir) / f"{A}_s001.txt").read_text() == "First clip, corrected.\n"
    with wave.open(str(folder(out_dir) / f"{A}_s001.wav")) as w:
        assert abs(w.getnframes() / w.getframerate() - 2.5) < 0.02
    kept = list(retired(out_dir).rglob(f"{A}_s001.txt"))
    assert len(kept) == 1 and kept[0].read_text() == "First clip.\n"
    assert json.loads((kept[0].parent / "index.json").read_text())[f"{A}_s001"] == "replaced by a newer version"


def test_a_piece_that_stops_qualifying_is_moved_aside_with_the_reason_and_can_come_back(out_dir, take_a):
    ex.apply(out_dir, "en-US")
    edit_take(out_dir, A, lambda s: by_id(s, "s007").update(status="pending"))
    edit_take(out_dir, A, lambda s: by_id(s, "s001").update(tags=["noise"]))
    plan = ex.apply(out_dir, "en-US")
    assert plan.counts()["retired"] == 2
    assert files(folder(out_dir)) == [".presplit", "manifest.json"]                  # nothing left that would be trained on
    aside = list(retired(out_dir).iterdir())[0]
    assert sorted(p.name for p in aside.iterdir() if p.suffix == ".wav") == [f"{A}_s001.wav", f"{A}_s007.wav"]
    why = json.loads((aside / "index.json").read_text())
    assert why[f"{A}_s007"] == "not approved yet" and why[f"{A}_s001"].startswith("tagged")
    assert set(json.loads((folder(out_dir) / "manifest.json").read_text())["items"]) == set()
    edit_take(out_dir, A, lambda s: by_id(s, "s007").update(status="approved"))      # approve again
    assert ex.apply(out_dir, "en-US").counts()["new"] == 1
    assert (folder(out_dir) / f"{A}_s007.wav").exists()


def test_files_you_put_in_the_folder_yourself_are_never_touched(out_dir, take_a):
    ex.apply(out_dir, "en-US")
    (folder(out_dir) / "my_own.wav").write_bytes(b"RIFF....")
    (folder(out_dir) / "my_own.txt").write_text("Hand made.\n")
    (folder(out_dir) / "notes.md").write_text("mine\n")
    edit_take(out_dir, A, lambda s: by_id(s, "s001").update(status="pending"))
    ex.apply(out_dir, "en-US")
    assert (folder(out_dir) / "my_own.wav").read_bytes() == b"RIFF...." and (folder(out_dir) / "my_own.txt").read_text() == "Hand made.\n"
    assert (folder(out_dir) / "notes.md").exists()
    assert "my_own" not in json.dumps(json.loads((folder(out_dir) / "manifest.json").read_text()))


def test_files_left_by_an_interrupted_run_are_archived_before_being_replaced(out_dir, take_a):
    folder(out_dir).mkdir(parents=True)
    (folder(out_dir) / f"{A}_s001.wav").write_bytes(b"half written")
    (folder(out_dir) / f"{A}_s001.txt").write_text("old text\n")                      # no manifest knows about these
    plan = ex.apply(out_dir, "en-US")
    assert plan.counts()["updated"] == 1 and plan.counts()["new"] == 1
    assert (folder(out_dir) / f"{A}_s001.txt").read_text() == "First clip.\n"
    assert list(retired(out_dir).rglob(f"{A}_s001.wav"))[0].read_bytes() == b"half written"


def test_a_damaged_manifest_is_treated_as_empty_and_nothing_is_lost(out_dir, take_a):
    ex.apply(out_dir, "en-US")
    (folder(out_dir) / "manifest.json").write_text("{ not json")
    plan = ex.apply(out_dir, "en-US")
    assert plan.counts()["updated"] == 2                                               # re-made, with the old files archived
    assert len(list(retired(out_dir).rglob("*.wav"))) == 2
    assert list(retired(out_dir).rglob("manifest.damaged.json"))[0].read_text() == "{ not json"   # and the damaged one is kept too
    assert len(json.loads((folder(out_dir) / "manifest.json").read_text())["items"]) == 2
    (folder(out_dir) / "manifest.json").write_text(json.dumps({"items": {"x": 5, "y": {"take": 1}}}))
    assert ex.read_manifest(folder(out_dir))["items"] == {}


def test_a_recording_that_is_being_transcribed_again_is_not_emptied(out_dir, take_a):
    ex.apply(out_dir, "en-US")
    take_json = out_dir / "_freeform" / "en-US" / "takes" / A / "take.json"
    doc = json.loads(take_json.read_text())
    doc["status"] = "transcribing"
    take_json.write_text(json.dumps(doc))
    plan = ex.apply(out_dir, "en-US")
    assert plan.counts()["retired"] == 0 and plan.skipped_takes == [(A, "transcribing")]
    assert (folder(out_dir) / f"{A}_s001.wav").exists()


# ------------------------------------------------------------------ scope, audio checks, safety
def test_one_recording_can_be_exported_without_touching_the_others(out_dir, take_a):
    write_take(out_dir, B, [approved(1, 0.0, 3.0, "From the second recording.")], seconds=10.0)
    ex.apply(out_dir, "en-US", [B])
    assert files(folder(out_dir)) == sorted([".presplit", "manifest.json", f"{B}_s001.txt", f"{B}_s001.wav"])
    ex.apply(out_dir, "en-US", [A])
    edit_take(out_dir, B, lambda s: s[0].update(status="dropped"))
    ex.apply(out_dir, "en-US", [A])                                                    # B is out of scope: its clip stays
    assert (folder(out_dir) / f"{B}_s001.wav").exists()
    ex.apply(out_dir, "en-US", [B])
    assert not (folder(out_dir) / f"{B}_s001.wav").exists() and (folder(out_dir) / f"{A}_s001.wav").exists()


def test_approved_pieces_with_bad_audio_are_reported_not_exported(out_dir):
    write_take(out_dir, A, [approved(1, 0.0, 3.0, "Quiet.")], seconds=5.0, amp=0.0001)
    write_take(out_dir, B, [approved(1, 0.0, 3.0, "Distorted.")], seconds=5.0, amp=1.0)
    plan = ex.apply(out_dir, "en-US")
    reasons = sorted(e["reason"] for e in plan.left_out)
    assert any("too quiet" in r for r in reasons) and any("clips" in r for r in reasons)
    assert plan.counts()["new"] == 0 and not list(folder(out_dir).glob("*.wav"))


def test_levels_are_matched_by_default_and_left_alone_on_request(out_dir):
    write_take(out_dir, A, [approved(1, 0.0, 3.0, "Level check.")], seconds=5.0, amp=0.3)
    ex.apply(out_dir, "en-US")
    x, *_ = read_wav(folder(out_dir) / f"{A}_s001.wav")
    assert 0.6 < np.abs(x).max() < 0.8                                                 # about -3 dBFS, like build_dataset
    ex.apply(out_dir, "en-US", policy=ex.default_policy(normalize=False))
    y, *_ = read_wav(folder(out_dir) / f"{A}_s001.wav")
    assert 0.25 < np.abs(y).max() < 0.35                                               # untouched
    assert len(list(retired(out_dir).rglob("*.wav"))) == 1                             # the normalized one was kept


def test_a_second_export_cannot_start_while_one_is_running_but_a_crashed_lock_expires(out_dir, take_a):
    folder(out_dir).mkdir(parents=True)
    lock = folder(out_dir) / ex.LOCK
    lock.write_text("123")
    with pytest.raises(ex.ExportError, match="Another export is running"):
        ex.apply(out_dir, "en-US")
    assert lock.exists()                                                               # someone else's lock is left alone
    old = time.time() - ex.STALE_LOCK_S - 60
    os.utime(lock, (old, old))
    assert ex.apply(out_dir, "en-US").counts()["new"] == 2
    assert not lock.exists()                                                           # and it never leaves its own behind


def test_no_temporary_files_are_left_behind_even_when_it_fails(out_dir, take_a, monkeypatch):
    monkeypatch.setattr(ex, "atomic_write_bytes", lambda *a, **k: (_ for _ in ()).throw(OSError("disk full")))
    with pytest.raises(OSError):
        ex.apply(out_dir, "en-US")
    assert not [p for p in folder(out_dir).iterdir() if p.name.startswith(".tmp-export") or p.name == ex.LOCK]


def test_a_missing_recordings_folder_is_explained(tmp_path):
    with pytest.raises(ex.ExportError, match="no recordings folder"):
        ex.make_plan(tmp_path, "en-US")


# ------------------------------------------------------------------ the command line
def test_the_command_line_previews_asks_and_will_not_write_without_being_told(out_dir, take_a, capsys):
    args = ["--output", str(out_dir)]
    assert ex.main([*args, "--dry-run"]) == 0
    shown = capsys.readouterr().out
    assert "DRY RUN" in shown and "new: 2" in shown and "APPROVED BUT LEFT OUT: 3" in shown and "tagged: laugh" in shown
    assert not folder(out_dir).exists()
    assert ex.main(args) == 2                                                          # not a terminal: refuses rather than guessing
    assert "--yes" in capsys.readouterr().err and not folder(out_dir).exists()
    assert ex.main([*args, "--yes"]) == 0
    done = capsys.readouterr().out
    assert "Wrote 2 new" in done and "split_long_takes.py" in done
    assert ex.main([*args, "--yes"]) == 0 and "Already up to date" in capsys.readouterr().out
    assert ex.main(["--output", str(out_dir / "nowhere")]) == 2


def test_a_recording_folder_with_an_unexpected_name_is_left_out_rather_than_written_under_that_name(out_dir):
    write_take(out_dir, "t20260930-000001-aaaa", [approved(1, 0.0, 3.0)], seconds=5.0)
    odd = out_dir / "_freeform" / "en-US" / "takes" / "t20260930-000009-zzzz"
    (out_dir / "_freeform" / "en-US" / "takes" / "t20260930-000001-aaaa").rename(odd)
    plan = ex.apply(out_dir, "en-US")
    assert plan.counts()["new"] == 0 and "name isn't one this tool makes" in plan.left_out[0]["reason"]


def test_a_folder_that_already_holds_someone_elses_recordings_is_not_taken_over(out_dir, take_a):
    folder(out_dir).mkdir(parents=True)
    (folder(out_dir) / "0.webm").write_bytes(b"a prompted recording")
    (folder(out_dir) / "0.txt").write_text("A long prompt. With several sentences.\n")
    with pytest.raises(ex.ExportError, match="holds recordings that this tool didn't write"):
        ex.make_plan(out_dir, "en-US")
    with pytest.raises(ex.ExportError):
        ex.apply(out_dir, "en-US")
    assert files(folder(out_dir)) == ["0.txt", "0.webm"]                              # nothing added, nothing marked
    # once it is ours (marker or manifest present) it is fine, even with hand-placed files beside the clips
    (folder(out_dir) / ex.MARKER).write_text("ours\n")
    assert ex.make_plan(out_dir, "en-US").counts()["new"] == 2
