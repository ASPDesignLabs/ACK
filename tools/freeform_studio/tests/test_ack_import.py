# SPDX-License-Identifier: GPL-3.0-or-later
"""Importing an ACK package: sessions become recordings the existing pipeline can finish; it only ever adds; it can be run twice;
a package that fails its checks, or a disk that is too full, changes nothing."""
import asyncio
import hashlib
import json
import os
import stat
import wave

import pytest

import freeform_studio.ack_import as imp
from ack_package_builder import ClipSpec, PackageBuilder
from conftest import needs_ffmpeg
from freeform_studio.ack_package import open_package
from freeform_studio.app import create_app
from freeform_studio.config import Config
from freeform_studio.storage import TakeStore

TEXTS = ["The tide came in.", "We walked along the shore.", "Gulls circled overhead."]


def standard(tmp_path, with_free=True):
    b = PackageBuilder()
    sid1 = b.script_session([ClipSpec(TEXTS[0], speech=2.0), ClipSpec(TEXTS[1], speech=3.0), ClipSpec(TEXTS[2], speech=1.5)])
    sid2 = b.free_session([(0.4, 3.0), (0.5, 7.0), (0.4, 4.0)], topic="my morning") if with_free else None
    (tmp_path / "pkg").mkdir(exist_ok=True)
    return b, b.write(tmp_path / "pkg" / "p.zip"), sid1, sid2


def plan_for(path, out_dir, **kw):
    return imp.make_plan(open_package(path), out_dir, "en-US", **kw)


def takes_of(out_dir):
    return TakeStore(Config(output_dir=out_dir).takes_dir)


def joined_pcm(store, take_id):
    info = store.assemble(take_id, ext="wav")
    with wave.open(str(store.path(take_id, info["file"])), "rb") as w:
        return w.getframerate(), w.getnchannels(), w.getsampwidth(), w.readframes(w.getnframes())


def pcm_of(wav_file_bytes):
    return wav_file_bytes[44:]


# ------------------------------------------------------------------ planning writes nothing
def test_the_plan_describes_each_session_and_writes_nothing(tmp_path, out_dir, capsys):
    _b, path, sid1, sid2 = standard(tmp_path)
    plan = plan_for(path, out_dir)
    assert [s.state for s in plan.sessions] == ["new", "new"] and plan.enough_room
    assert plan.sessions[0].clips == 3 and plan.sessions[1].mode == "free"
    assert not (out_dir / "_freeform").exists()


def test_dry_run_prints_the_plan_and_creates_nothing(tmp_path, out_dir, capsys):
    _b, path, sid1, sid2 = standard(tmp_path)
    assert imp.main([str(path), "--output", str(out_dir), "--dry-run"]) == 0
    text = capsys.readouterr().out
    assert sid1 in text and sid2 in text and "Would add 2 recording(s)" in text and "every checksum matches" in text
    assert not (out_dir / "_freeform").exists()


# ------------------------------------------------------------------ what gets written
def test_a_script_session_becomes_one_recording_with_its_clips_joined_by_a_gap(tmp_path, out_dir, monkeypatch):
    monkeypatch.setattr(imp, "PART_BYTES", 50_000)             # several parts, as a long session would have
    b, path, sid1, _ = standard(tmp_path, with_free=False)
    plan = plan_for(path, out_dir)
    created = imp.apply_import(plan)
    assert len(created) == 1
    store = takes_of(out_dir)
    tid = created[0].take_id
    take = store.get(tid)
    assert take["status"] == "finishing" and take["mime"] == "audio/wav" and take["label"] == "closet, phone on stand, 30 cm"
    assert take["client"]["source"] == "ack" and take["client"]["ack_session"] == sid1 and take["client"]["ack_mode"] == "script"
    assert take["reference_text"] == "\n".join(TEXTS)
    assert len(store.received(tid)) > 1

    rate, channels, width, pcm = joined_pcm(store, tid)
    assert (rate, channels, width) == (48000, 1, 2)
    gap = int(round(imp.GAP_S * rate)) * 2
    parts = [pcm_of(b.audio[f"sessions/{sid1}/clips/{i:04d}.wav"]) for i in (1, 2, 3)]
    assert pcm == parts[0] + b"\x00" * gap + parts[1] + b"\x00" * gap + parts[2]

    notes = store.read(tid, "ack_clips.json")
    assert notes["mode"] == "script" and notes["gap_s"] == 0.4 and notes["reference_clips"] == 3
    spans = [(c["start_frame"], c["end_frame"]) for c in notes["clips"]]
    assert spans[0][0] == 0 and spans[1][0] == spans[0][1] + gap // 2 and spans[2][0] == spans[1][1] + gap // 2
    assert spans[2][1] * 2 == len(pcm)
    assert [c["text"] for c in notes["clips"]] == TEXTS and notes["clips"][1]["speech"]["start_s"] == 0.5
    assert notes["clips"][0]["start_s"] == 0.0 and notes["clips"][1]["metrics"]["clipped_samples"] == 0


def test_a_free_session_is_stored_as_the_whole_recording_unchanged(tmp_path, out_dir, monkeypatch):
    monkeypatch.setattr(imp, "PART_BYTES", 64_000)
    b, path, _sid1, sid2 = standard(tmp_path)
    created = imp.apply_import(plan_for(path, out_dir))
    store = takes_of(out_dir)
    tid = next(c.take_id for c in created if c.session == sid2)
    info = store.assemble(tid, ext="wav")
    assert store.path(tid, info["file"]).read_bytes() == b.audio[f"sessions/{sid2}/session.wav"]
    take = store.get(tid)
    assert take["client"]["ack_mode"] == "free" and take["reference_text"] == "" and take["label"] == "kitchen"
    notes = store.read(tid, "ack_clips.json")
    assert notes["mode"] == "free" and notes["topic"] == "my morning" and len(notes["proposed_segments"]) >= 1
    assert notes["proposed_segments"][0]["end_kind"] in ("pause", "forced", "end")


def test_the_package_file_is_never_changed(tmp_path, out_dir):
    _b, path, *_ = standard(tmp_path)
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    imp.apply_import(plan_for(path, out_dir))
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before


def test_a_session_with_no_label_is_named_by_its_date(tmp_path, out_dir):
    b = PackageBuilder()
    b.script_session(["Short one here."], label="")
    path = b.write(tmp_path / "p.zip")
    created = imp.apply_import(plan_for(path, out_dir))
    assert takes_of(out_dir).get(created[0].take_id)["label"].startswith("ACK 2026-10-02")


def test_reference_text_is_kept_within_the_review_pages_limit(tmp_path, out_dir):
    long_text = ("word " * 119).strip() + "."                      # 599 characters
    b = PackageBuilder()
    b.script_session([ClipSpec(long_text, speech=0.5, lead=0.2, tail=0.2) for _ in range(40)])
    path = b.write(tmp_path / "p.zip")
    created = imp.apply_import(plan_for(path, out_dir))
    store = takes_of(out_dir)
    take = store.get(created[0].take_id)
    notes = store.read(created[0].take_id, "ack_clips.json")
    assert len(take["reference_text"]) <= imp.REFERENCE_MAX
    assert 0 < notes["reference_clips"] < 40 and take["reference_text"].count("\n") == notes["reference_clips"] - 1
    assert len(notes["clips"]) == 40                                  # every clip's own text is still kept with its notes


def test_files_are_readable_by_the_owner_only(tmp_path, out_dir):
    _b, path, *_ = standard(tmp_path)
    assert imp.main([str(path), "--output", str(out_dir), "--yes"]) == 0
    root = Config(output_dir=out_dir).root
    for p in [root, *root.rglob("*")]:
        assert stat.S_IMODE(p.stat().st_mode) & 0o077 == 0, f"{p} can be read by other accounts"


# ------------------------------------------------------------------ running it twice, and recovering
def test_a_session_already_imported_is_recognised_and_skipped(tmp_path, out_dir, capsys):
    _b, path, sid1, sid2 = standard(tmp_path)
    first = imp.apply_import(plan_for(path, out_dir))
    again = plan_for(path, out_dir)
    assert [s.state for s in again.sessions] == ["already", "already"] and again.to_import == []
    assert {s.id: s.take_id for s in again.sessions} == {c.session: c.take_id for c in first}
    assert imp.apply_import(again) == []
    assert len(takes_of(out_dir).ids()) == 2
    assert imp.main([str(path), "--output", str(out_dir), "--yes"]) == 0
    assert "already imported" in capsys.readouterr().out and len(takes_of(out_dir).ids()) == 2


def test_importing_only_the_sessions_asked_for(tmp_path, out_dir):
    _b, path, sid1, sid2 = standard(tmp_path)
    created = imp.apply_import(plan_for(path, out_dir, only=[sid2]))
    assert [c.session for c in created] == [sid2]
    with pytest.raises(imp.ImportProblem, match="no session s2026"):
        plan_for(path, out_dir, only=["s20261002-999999-ffff"])


def test_a_half_finished_import_is_moved_aside_and_redone_not_deleted(tmp_path, out_dir):
    _b, path, sid1, _ = standard(tmp_path, with_free=False)
    store = takes_of(out_dir)
    left = store.create({"status": "importing", "client": {"source": "ack", "ack_session": sid1}})
    store.write_chunk(left["id"], 0, b"half a file")
    plan = plan_for(path, out_dir)
    assert plan.sessions[0].state == "aborted" and plan.sessions[0].take_id == left["id"]
    created = imp.apply_import(plan)
    kept = Config(output_dir=out_dir).root / "retired" / "aborted-imports" / left["id"]
    assert (kept / "parts" / "000000.bin").read_bytes() == b"half a file"      # moved, not deleted
    assert store.get(left["id"]) is None and store.get(created[0].take_id)["status"] == "finishing"


# ------------------------------------------------------------------ refusing, with nothing written
def test_not_enough_disk_space_stops_before_writing(tmp_path, out_dir, monkeypatch):
    _b, path, *_ = standard(tmp_path)
    monkeypatch.setattr(imp, "free_mb", lambda _p: 100.0)
    plan = plan_for(path, out_dir)
    assert not plan.enough_room
    with pytest.raises(imp.ImportProblem, match="not enough free space"):
        imp.apply_import(plan)
    assert not (out_dir / "_freeform").exists()


def test_a_session_too_big_for_one_recording_is_refused_by_name(tmp_path, out_dir, monkeypatch):
    _b, path, sid1, _ = standard(tmp_path, with_free=False)
    monkeypatch.setattr(imp, "MAX_WAV_DATA", 1000)
    with pytest.raises(imp.ImportProblem, match=sid1):
        plan_for(path, out_dir)


def test_a_package_that_fails_its_checks_changes_nothing(tmp_path, out_dir, capsys):
    _b, path, *_ = standard(tmp_path)
    data = bytearray(path.read_bytes())
    data[len(data) // 2] ^= 0xFF                                       # damage somewhere in the middle of the zip
    path.write_bytes(bytes(data))
    assert imp.main([str(path), "--output", str(out_dir), "--yes"]) == 2
    err = capsys.readouterr().err
    assert "Can't continue" in err and "Nothing was imported." in err
    assert not (out_dir / "_freeform").exists()


def test_it_will_not_write_without_being_asked_when_not_at_a_terminal(tmp_path, out_dir, capsys):
    _b, path, *_ = standard(tmp_path)
    assert imp.main([str(path), "--output", str(out_dir)]) == 2
    assert "add --yes" in capsys.readouterr().err and not (out_dir / "_freeform").exists()


def test_a_yes_run_says_what_to_do_next(tmp_path, out_dir, capsys):
    _b, path, *_ = standard(tmp_path)
    assert imp.main([str(path), "--output", str(out_dir), "--yes"]) == 0
    out = capsys.readouterr().out
    assert "Added 2 recording(s)" in out and "start Freeform Studio" in out


# ------------------------------------------------------------------ the real pipeline picks them up
@needs_ffmpeg
def test_imported_recordings_go_through_the_existing_pipeline_to_reviewable(tmp_path, out_dir):
    b, path, sid1, sid2 = standard(tmp_path)
    created = imp.apply_import(plan_for(path, out_dir))
    want = {c.take_id: c.seconds for c in created}

    async def main():
        cfg = Config(output_dir=out_dir, asr_engine="fake", asr_idle_unload_s=0)
        app = create_app(cfg)
        async with app.test_app():
            client = app.test_client()
            for tid in want:
                for _ in range(300):
                    doc = await (await client.get(f"/api/takes/{tid}")).get_json()
                    if doc["status"] in ("ready", "error"):
                        break
                    await asyncio.sleep(0.1)
                assert doc["status"] == "ready", doc.get("error")
                assert abs(doc["duration"] - want[tid]) < 0.1
                edit = await (await client.get(f"/api/takes/{tid}/edit")).get_json()
                assert edit["segments"], "no pieces were proposed"
                assert doc["client"]["source"] == "ack"
    asyncio.run(main())
