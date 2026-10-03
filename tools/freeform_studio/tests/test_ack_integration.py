# SPDX-License-Identifier: GPL-3.0-or-later
"""Recordings that came from ACK in the program's safety nets: backups hold the phone's notes, a restore brings the recording back
as the phone cut it, the doctor knows about waiting packages, and the packages themselves are not swept into backups."""
import asyncio
import json
import tarfile

import freeform_studio.ack_import as imp
from ack_package_builder import ClipSpec, PackageBuilder
from conftest import needs_ffmpeg
from freeform_studio import backup as bk
from freeform_studio import doctor
from freeform_studio.ack_package import open_package
from freeform_studio.app import create_app
from freeform_studio.config import Config
from freeform_studio.storage import TakeStore

CARDS = ["The tide came in slowly.", "It rained all day. We stayed inside until dark.", "Gulls circled overhead again."]


def package(tmp_path):
    b = PackageBuilder()
    b.script_session([ClipSpec(CARDS[0], speech=2.5), ClipSpec(CARDS[1], speech=4.5), ClipSpec(CARDS[2], speech=2.5)])
    return b, b.write(tmp_path / "p.zip")


def names(archive):
    with tarfile.open(archive, "r:gz") as tar:
        return sorted(m.name for m in tar.getmembers())


def test_a_backup_holds_the_phones_notes_and_leaves_the_packages_out(tmp_path, out_dir):
    _b, path = package(tmp_path)
    created = imp.apply_import(imp.make_plan(open_package(path), out_dir, "en-US"))
    tid = created[0].take_id
    folder = Config(output_dir=out_dir).takes_dir / tid
    (folder / "ack_checks.json").write_text(json.dumps({"schema": 1, "pieces": {}}))
    incoming = Config(output_dir=out_dir).root / "incoming"
    incoming.mkdir(parents=True)
    (incoming / "p.zip").write_bytes(path.read_bytes())

    result = bk.create(out_dir, "en-US", tmp_path / "bk", force=True)
    inside = names(result.path)
    assert f"takes/{tid}/ack_clips.json" in inside and f"takes/{tid}/ack_checks.json" in inside
    assert not any("incoming" in n or n.endswith(".zip") for n in inside)
    problems, _manifest = bk.verify(result.path)
    assert problems == []


@needs_ffmpeg
def test_a_restored_recording_is_still_cut_where_the_phone_recorded_its_clips(tmp_path, out_dir):
    _b, path = package(tmp_path)
    created = imp.apply_import(imp.make_plan(open_package(path), out_dir, "en-US"))
    tid = created[0].take_id
    original = (Config(output_dir=out_dir).takes_dir / tid / "ack_clips.json").read_bytes()
    archive = bk.create(out_dir, "en-US", tmp_path / "bk", force=True).path

    fresh = tmp_path / "fresh"
    fresh.mkdir()
    report = bk.restore(archive, fresh, "en-US")
    assert tid in report.takes
    restored = Config(output_dir=fresh).takes_dir / tid
    assert (restored / "ack_clips.json").read_bytes() == original

    async def main():
        app = create_app(Config(output_dir=fresh, asr_engine="fake", asr_idle_unload_s=0))
        async with app.test_app():
            c = app.test_client()
            for _ in range(300):
                doc = await (await c.get(f"/api/takes/{tid}")).get_json()
                if doc["status"] in ("ready", "error"):
                    break
                await asyncio.sleep(0.1)
            assert doc["status"] == "ready", doc.get("error")
            segs = (await (await c.get(f"/api/takes/{tid}/edit")).get_json())["segments"]
            # three cards -> three pieces; cutting by sentences alone would have made four from this recording
            assert len(segs) == 3
            notes = await (await c.get(f"/api/takes/{tid}/ack")).get_json()
            assert [c["text"] for c in notes["notes"]["clips"]] == CARDS
    asyncio.run(main())


def test_restoring_only_ever_adds_and_never_overwrites_the_phones_notes(tmp_path, out_dir):
    _b, path = package(tmp_path)
    created = imp.apply_import(imp.make_plan(open_package(path), out_dir, "en-US"))
    tid = created[0].take_id
    archive = bk.create(out_dir, "en-US", tmp_path / "bk", force=True).path
    notes = Config(output_dir=out_dir).takes_dir / tid / "ack_clips.json"
    notes.write_text('{"edited": "after the backup"}')
    report = bk.restore(archive, out_dir, "en-US")
    assert notes.read_text() == '{"edited": "after the backup"}'                 # kept; the backup's copy is set aside
    assert any(tid in str(p) and p.endswith("ack_clips.json") for p in report.conflicts)


def test_the_doctor_mentions_packages_waiting_and_says_they_are_not_backed_up(tmp_path, capsys):
    out = tmp_path / "out"
    incoming = out / "_freeform" / "en-US" / "incoming"
    incoming.mkdir(parents=True)
    (incoming / "ack-training-1.zip").write_bytes(b"PK\x03\x04" + b"x" * 3000)
    (incoming / "ack-training-1.zip.part").write_bytes(b"PK\x03\x04")                 # an unfinished upload is not a package
    doctor.main(["--output", str(out), "--port", "59999"])
    text = capsys.readouterr().out
    assert "1 package(s) saved by ACK are in" in text and "not part of the backups" in text and "delete the files yourself" in text


def test_the_doctor_says_nothing_about_packages_when_there_are_none(tmp_path, capsys):
    out = tmp_path / "out"
    (out / "_freeform" / "en-US" / "takes").mkdir(parents=True)
    doctor.main(["--output", str(out), "--port", "59999"])
    assert "saved by ACK" not in capsys.readouterr().out
