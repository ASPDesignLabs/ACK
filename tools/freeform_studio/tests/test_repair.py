import json
import shutil

import pytest

from conftest import needs_ffmpeg
from freeform_studio import backup as bk
from freeform_studio import repair as rp
from freeform_studio.app import create_app
from test_api import make_cfg, run, upload, wait_for, webm_chunks

pytestmark = needs_ffmpeg


def take_dir(out_dir, tid):
    return out_dir / "_freeform" / "en-US" / "takes" / tid


def make_ready_take(out_dir, tmp_path):
    chunks, _ = webm_chunks(tmp_path)

    async def main():
        app = create_app(make_cfg(out_dir))
        async with app.test_app():
            c = app.test_client()
            tid = await upload(c, chunks)
            await c.post(f"/api/takes/{tid}/finish")
            await wait_for(c, tid, ("ready",))
            return tid

    return run(main())


def derived(d):
    return {n: (d / n).read_bytes() for n in ("audio.wav", "peaks.json", "peaks_512.bin", "peaks_2048.bin", "peaks_8192.bin")}


def test_derived_files_are_rebuilt_from_the_raw_audio_exactly(out_dir, tmp_path):
    tid = make_ready_take(out_dir, tmp_path)
    d = take_dir(out_dir, tid)
    before = derived(d)
    assert not rp.needs_repair(d)
    for name in before:
        (d / name).unlink()
    assert rp.needs_repair(d)
    assert rp.rebuild_missing(out_dir, "en-US") == [tid]
    assert derived(d) == before                                                  # identical, so nothing about review changes
    assert not rp.needs_repair(d) and rp.rebuild_missing(out_dir, "en-US") == []
    (d / "peaks_2048.bin").unlink()                                               # a single missing level counts too
    assert rp.needs_repair(d)
    rp.rebuild_missing(out_dir, "en-US", [tid])
    assert derived(d) == before


def test_recordings_in_the_middle_of_something_or_without_raw_audio_are_left_alone(out_dir, tmp_path):
    tid = make_ready_take(out_dir, tmp_path)
    d = take_dir(out_dir, tid)
    (d / "audio.wav").unlink()
    doc = json.loads((d / "take.json").read_text())
    for status in ("transcribing", "queued", "finishing", "recording", "error"):
        (d / "take.json").write_text(json.dumps({**doc, "status": status}))
        assert not rp.needs_repair(d), status
    (d / "take.json").write_text(json.dumps(doc))
    raw = next(d.glob("raw.*"))
    held = raw.read_bytes()
    raw.unlink()
    assert not rp.needs_repair(d)                                                 # nothing to rebuild it from
    raw.write_bytes(held)
    assert rp.needs_repair(d)
    (d / "take.json").write_text("{ broken")
    assert not rp.needs_repair(d)                                                 # an unreadable record is not guessed at


def test_the_server_rebuilds_missing_audio_when_it_starts(out_dir, tmp_path):
    tid = make_ready_take(out_dir, tmp_path)
    d = take_dir(out_dir, tid)
    before = derived(d)
    for name in before:
        (d / name).unlink()

    async def main():
        app = create_app(make_cfg(out_dir))
        async with app.test_app():
            c = app.test_client()
            await app.freeform.runner.wait_idle()
            r = await c.get(f"/api/takes/{tid}/audio")
            assert r.status_code == 200
            assert (await c.get(f"/api/takes/{tid}/peaks")).status_code == 200

    run(main())
    assert derived(d) == before


def test_a_recording_that_cannot_be_rebuilt_is_noted_not_broken(out_dir, tmp_path):
    tid = make_ready_take(out_dir, tmp_path)
    d = take_dir(out_dir, tid)
    (d / "audio.wav").unlink()
    next(d.glob("raw.*")).write_bytes(b"this is not audio at all")

    async def main():
        app = create_app(make_cfg(out_dir))
        async with app.test_app():
            await app.freeform.runner.wait_idle()
            doc = await (await app.test_client().get(f"/api/takes/{tid}")).get_json()
            assert doc["status"] == "ready" and "could not rebuild" in doc["repair_error"]

    run(main())


def test_a_backup_then_a_restore_then_a_repair_brings_a_recording_all_the_way_back(out_dir, tmp_path):
    tid = make_ready_take(out_dir, tmp_path)
    d = take_dir(out_dir, tid)
    before = derived(d)
    edit_before = (d / "edit.json").read_bytes()
    archive = bk.create(out_dir, "en-US", tmp_path / "backups").path
    shutil.rmtree(d)                                                              # the recording is lost entirely
    report = bk.restore(archive, out_dir, "en-US")
    assert report.takes == [tid] and not (d / "audio.wav").exists()
    assert (d / "edit.json").read_bytes() == edit_before                          # every decision is back exactly
    assert rp.rebuild_missing(out_dir, "en-US", report.takes) == [tid]
    assert derived(d) == before                                                   # and it can be reviewed again


def test_the_repair_command_reports_what_it_did(out_dir, tmp_path, capsys):
    tid = make_ready_take(out_dir, tmp_path)
    (take_dir(out_dir, tid) / "audio.wav").unlink()
    assert rp.main(["--output", str(out_dir)]) == 0
    assert tid in capsys.readouterr().out
    assert rp.main(["--output", str(out_dir)]) == 0 and "Nothing needed rebuilding" in capsys.readouterr().out


# ---------------------------------------------------------------- one bad recording must not stop the rest, or crash a restore

def good_and_bad(out_dir, tmp_path):
    """A recording that can be rebuilt and a copy of it whose raw audio is garbage; both are missing their decoded audio."""
    good = make_ready_take(out_dir, tmp_path)
    g = take_dir(out_dir, good)
    bad = good[:-4] + ("ffff" if not good.endswith("ffff") else "eeee")
    b = take_dir(out_dir, bad)
    shutil.copytree(g, b)
    next(b.glob("raw.*")).write_bytes(b"this is not audio at all")
    for d in (g, b):
        for f in d.glob("peaks*"):
            f.unlink()
        (d / "audio.wav").unlink()
    return good, bad


def test_rebuild_carries_on_past_a_recording_that_cannot_be_decoded(out_dir, tmp_path):
    good, bad = good_and_bad(out_dir, tmp_path)
    failures = {}
    assert rp.rebuild_missing(out_dir, "en-US", failures=failures) == [good]
    assert list(failures) == [bad] and "Invalid data" in failures[bad] and "\n" not in failures[bad]
    assert (take_dir(out_dir, good) / "audio.wav").exists()
    assert not (take_dir(out_dir, bad) / "audio.wav").exists(), "no half-written copy is left behind"
    assert rp.needs_repair(take_dir(out_dir, bad)), "it stays on the list, so a later run tries again"


def test_rebuild_without_a_place_to_note_failures_still_raises(out_dir, tmp_path):
    good_and_bad(out_dir, tmp_path)
    with pytest.raises(rp.FfmpegError):
        rp.rebuild_missing(out_dir, "en-US")


def test_the_repair_command_names_the_bad_recording_and_still_fixes_the_others(out_dir, tmp_path, capsys):
    good, bad = good_and_bad(out_dir, tmp_path)
    assert rp.main(["--output", str(out_dir)]) == 1
    out = capsys.readouterr().out
    assert "Rebuilt the decoded audio for 1 recording(s)" in out and good in out
    assert "1 recording(s) could not be rebuilt" in out and f"{bad}:" in out
    assert "Nothing needed rebuilding" not in out
    assert "Traceback" not in out


def test_a_restore_that_works_is_not_turned_into_a_crash_by_one_bad_recording(out_dir, tmp_path, capsys):
    good, bad = good_and_bad(out_dir, tmp_path)
    archive = bk.create(out_dir, "en-US", tmp_path / "backups", force=True).path
    shutil.rmtree(take_dir(out_dir, good))
    shutil.rmtree(take_dir(out_dir, bad))
    assert bk.main(["--output", str(out_dir), "--restore", str(archive)]) == 1       # 1: something still needs attention
    out = capsys.readouterr().out
    assert "added:" in out and "rebuilt the decoded audio for 1 recording(s)" in out
    assert f"could not rebuild {bad}:" in out
    assert "The restore itself worked and every file is back" in out
    assert (take_dir(out_dir, good) / "audio.wav").exists()
    assert next(take_dir(out_dir, bad).glob("raw.*")).read_bytes() == b"this is not audio at all", "the raw audio is restored exactly as it was"
    assert (take_dir(out_dir, good) / "edit.json").exists() and (take_dir(out_dir, bad) / "edit.json").exists()


def test_a_missing_ffmpeg_is_one_clear_message_for_repair_and_never_undoes_a_restore(out_dir, tmp_path, capsys, monkeypatch):
    good, bad = good_and_bad(out_dir, tmp_path)
    archive = bk.create(out_dir, "en-US", tmp_path / "backups", force=True).path
    monkeypatch.setenv("PATH", str(tmp_path / "nowhere"))
    assert rp.main(["--output", str(out_dir)]) == 2
    err = capsys.readouterr().err
    assert err.count("ffmpeg not found") == 1, "one message, not one per recording"

    shutil.rmtree(take_dir(out_dir, good))
    assert bk.main(["--output", str(out_dir), "--restore", str(archive)]) == 1
    out = capsys.readouterr().out
    assert "could not rebuild the decoded audio: ffmpeg not found" in out and "The restore itself worked" in out
    assert (take_dir(out_dir, good) / "edit.json").exists(), "the restored files are in place"
