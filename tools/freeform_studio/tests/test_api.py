import asyncio
import json
import random

import pytest

from conftest import fake_whisper_model, make_live_webm, make_wav, needs_ffmpeg
from freeform_studio.app import create_app
from freeform_studio.asr import FasterWhisperEngine
from freeform_studio.config import Config

pytestmark = needs_ffmpeg
REF = "So here is a thing I wanted to say out loud today. And here is another one right after it."


def run(coro):
    return asyncio.run(coro)


def make_cfg(out_dir, **kw):
    kw.setdefault("asr_engine", "fake")
    kw.setdefault("asr_idle_unload_s", 0)
    return Config(output_dir=out_dir, **kw)


def webm_chunks(tmp_path, n=5):
    wav = make_wav(tmp_path / "in.wav", 9.0, [(0.5, 3.5), (5.0, 8.0)], rate=44100)
    data = make_live_webm(wav, tmp_path / "in.webm").read_bytes()
    cuts = sorted(random.Random(4).sample(range(1, len(data)), n - 1))
    return [data[a:b] for a, b in zip([0] + cuts, cuts + [len(data)])], data


async def wait_for(client, take_id, want, timeout=30):
    for _ in range(int(timeout / 0.1)):
        doc = await (await client.get(f"/api/takes/{take_id}")).get_json()
        if doc["status"] in want:
            return doc
        await asyncio.sleep(0.1)
    raise AssertionError(f"timed out; last status {doc['status']}: {doc.get('error')}")


async def upload(client, chunks, ref=REF, shuffle=True):
    take = await (await client.post("/api/takes", json={"reference_text": ref, "label": "test",
                                                        "client": {"ua": "pytest", "nested": {"x": 1}}})).get_json()
    tid = take["id"]
    order = list(range(len(chunks)))
    if shuffle:
        random.Random(1).shuffle(order)
    for n in order + [order[0]]:  # one duplicate, as a retry would send
        r = await client.put(f"/api/takes/{tid}/chunks/{n}", data=chunks[n])
        assert r.status_code == 200
    return tid


def test_full_pipeline_out_of_order_upload_to_reviewable_take(tmp_path, out_dir):
    chunks, original = webm_chunks(tmp_path)

    async def main():
        app = create_app(make_cfg(out_dir))
        async with app.test_app():
            c = app.test_client()
            tid = await upload(c, chunks)
            st = await (await c.get(f"/api/takes/{tid}/chunks")).get_json()
            assert st["received"] == 5 and st["missing"] == []
            assert (await c.post(f"/api/takes/{tid}/finish")).status_code == 202
            take = await wait_for(c, tid, {"ready", "error"})
            assert take["status"] == "ready", take.get("error")
            assert abs(take["duration"] - 9.0) < 0.15 and take["chunks"]["count"] == 5
            assert take["client"]["ua"] == "pytest" and isinstance(take["client"]["nested"], str)
            # reassembled bytes are exactly what the phone recorded
            assert (out_dir / "_freeform" / "en-US" / "takes" / tid / "raw.webm").read_bytes() == original
            assert not (out_dir / "_freeform" / "en-US" / "takes" / tid / "parts").exists()

            edit = await (await c.get(f"/api/takes/{tid}/edit")).get_json()
            assert edit["rev"] == 1 and len(edit["segments"]) >= 2
            spoken = " ".join(s["text"] for s in edit["segments"]).replace(".", "").split()
            assert spoken[:6] == REF.replace(".", "").split()[:6]
            asr = await (await c.get(f"/api/takes/{tid}/asr")).get_json()
            assert asr["engine"] == "fake" and asr["segments"]

            # audio honours Range (phones need this to seek)
            r = await c.get(f"/api/takes/{tid}/audio", headers={"Range": "bytes=1000-1099"})
            assert r.status_code == 206 and r.headers["Content-Range"].startswith("bytes 1000-1099/")
            assert len(await r.get_data()) == 100 and r.headers["Accept-Ranges"] == "bytes"

            meta = await (await c.get(f"/api/takes/{tid}/peaks")).get_json()
            assert meta["levels"] == [512, 2048, 8192] and meta["sample_rate"] == 48000
            level = await c.get(f"/api/takes/{tid}/peaks/512")
            assert len(await level.get_data()) == 2 * -(-meta["frames"] // 512)
            assert (await c.get(f"/api/takes/{tid}/peaks/999")).status_code == 404

            listed = (await (await c.get("/api/takes")).get_json())["takes"]
            assert listed[0]["id"] == tid and listed[0]["counts"]["segments"] == len(edit["segments"])

    run(main())


def test_edit_save_conflicts_validation_and_history(tmp_path, out_dir):
    chunks, _ = webm_chunks(tmp_path)

    async def main():
        app = create_app(make_cfg(out_dir))
        async with app.test_app():
            c = app.test_client()
            tid = await upload(c, chunks)
            await c.post(f"/api/takes/{tid}/finish")
            await wait_for(c, tid, {"ready"})
            edit = await (await c.get(f"/api/takes/{tid}/edit")).get_json()

            edit["segments"][0]["text"] = "corrected words here."
            edit["segments"][0]["status"] = "approved"
            ok = await c.put(f"/api/takes/{tid}/edit", json=edit)
            assert ok.status_code == 200 and (await ok.get_json())["rev"] == 2

            stale = await c.put(f"/api/takes/{tid}/edit", json=edit)  # same rev again = someone else got in first
            body = await stale.get_json()
            assert stale.status_code == 409 and body["current"]["rev"] == 2
            assert body["current"]["segments"][0]["text"] == "corrected words here."

            edit["rev"] = 2
            edit["segments"][0]["text"] = "bad | pipe"
            bad = await c.put(f"/api/takes/{tid}/edit", json=edit)
            assert bad.status_code == 400 and any("|" in d for d in (await bad.get_json())["details"])
            assert (await (await c.get(f"/api/takes/{tid}/edit")).get_json())["rev"] == 2  # rejected edit changed nothing

            hist = list((out_dir / "_freeform" / "en-US" / "takes" / tid / "edit_history").iterdir())
            assert [p.name for p in hist] == ["edit-rev00001.json"]

            assert (await c.put(f"/api/takes/{tid}/edit", json={"segments": []})).status_code == 400  # no rev

    run(main())


def test_regenerate_needs_force_when_work_would_be_lost_and_archives_first(tmp_path, out_dir):
    chunks, _ = webm_chunks(tmp_path)

    async def main():
        app = create_app(make_cfg(out_dir))
        async with app.test_app():
            c = app.test_client()
            tid = await upload(c, chunks)
            await c.post(f"/api/takes/{tid}/finish")
            await wait_for(c, tid, {"ready"})
            edit = await (await c.get(f"/api/takes/{tid}/edit")).get_json()
            edit["segments"][0]["status"] = "approved"
            await c.put(f"/api/takes/{tid}/edit", json=edit)

            refused = await c.post(f"/api/takes/{tid}/transcribe", json={"regenerate": True})
            assert refused.status_code == 409 and (await refused.get_json())["approved"] == 1

            # re-running the transcript WITHOUT regenerate leaves the reviewer's edits alone
            assert (await c.post(f"/api/takes/{tid}/transcribe", json={"model": "other"})).status_code == 202
            await wait_for(c, tid, {"ready"})
            kept = await (await c.get(f"/api/takes/{tid}/edit")).get_json()
            assert kept["rev"] == 2 and kept["segments"][0]["status"] == "approved"

            forced = await c.post(f"/api/takes/{tid}/transcribe", json={"regenerate": True, "force": True})
            assert forced.status_code == 202
            await wait_for(c, tid, {"ready"})
            new = await (await c.get(f"/api/takes/{tid}/edit")).get_json()
            assert new["rev"] == 3 and all(s["status"] == "pending" for s in new["segments"])
            archived = [p.name for p in (out_dir / "_freeform" / "en-US" / "takes" / tid / "edit_history").iterdir()]
            assert any(n.startswith("edit-pre-regen-") for n in archived)  # the approved version is recoverable
            assert (await c.post(f"/api/takes/{tid}/transcribe", json={"model": "bad name!"})).status_code == 400

    run(main())


def test_missing_chunk_gives_a_clear_error_and_recovers_when_sent(tmp_path, out_dir):
    chunks, original = webm_chunks(tmp_path)

    async def main():
        app = create_app(make_cfg(out_dir))
        async with app.test_app():
            c = app.test_client()
            tid = (await (await c.post("/api/takes", json={})).get_json())["id"]
            for n in (0, 1, 3, 4):
                await c.put(f"/api/takes/{tid}/chunks/{n}", data=chunks[n])
            await c.post(f"/api/takes/{tid}/finish")
            take = await wait_for(c, tid, {"error", "ready"})
            assert take["status"] == "error" and "never arrived" in take["error"] and take["error_stage"] == "finish"
            assert (await (await c.get(f"/api/takes/{tid}/chunks")).get_json())["missing"] == [2]

            await c.put(f"/api/takes/{tid}/chunks/2", data=chunks[2])  # the phone re-sends what was lost
            await c.post(f"/api/takes/{tid}/finish")
            take = await wait_for(c, tid, {"ready", "error"})
            assert take["status"] == "ready", take.get("error")

    run(main())


def test_undecodable_audio_becomes_a_readable_error_not_a_crash(tmp_path, out_dir):
    async def main():
        app = create_app(make_cfg(out_dir))
        async with app.test_app():
            c = app.test_client()
            tid = (await (await c.post("/api/takes", json={})).get_json())["id"]
            await c.put(f"/api/takes/{tid}/chunks/0", data=b"not audio" * 100)
            await c.post(f"/api/takes/{tid}/finish")
            take = await wait_for(c, tid, {"error", "ready"})
            assert take["status"] == "error" and "decode" in take["error"]
            assert (await c.get("/api/status")).status_code == 200  # server is still healthy

    run(main())


def test_input_validation_and_unknown_takes(out_dir):
    async def main():
        app = create_app(make_cfg(out_dir))
        async with app.test_app():
            c = app.test_client()
            assert (await c.get("/api/takes/nope")).status_code == 404
            assert (await c.get("/api/takes/t20260101-000000-abcd")).status_code == 404
            assert (await c.put("/api/takes/..%2f..%2fetc/chunks/0", data=b"x")).status_code == 404
            tid = (await (await c.post("/api/takes", json={})).get_json())["id"]
            assert (await c.put(f"/api/takes/{tid}/chunks/0", data=b"")).status_code == 400
            assert (await c.put(f"/api/takes/{tid}/chunks/999999", data=b"x")).status_code == 400
            assert (await c.get(f"/api/takes/{tid}/audio")).status_code == 404
            assert (await c.post(f"/api/takes/{tid}/transcribe", json={})).status_code == 409  # still recording
            assert (await c.post("/api/asr/release")).status_code == 200

    run(main())


def test_token_gate(out_dir):
    async def main():
        app = create_app(make_cfg(out_dir, token="s3cret-token"))
        async with app.test_app():
            api = app.test_client()
            assert (await api.get("/healthz")).status_code == 200
            assert (await api.get("/api/takes")).status_code == 401
            assert (await api.get("/api/takes?token=wrong")).status_code == 401
            ok = await api.get("/api/takes", headers={"Authorization": "Bearer s3cret-token"})
            assert ok.status_code == 200 and "set-cookie" not in ok.headers  # API clients don't need a cookie

            browser = app.test_client()
            r = await browser.get("/?token=s3cret-token")
            cookie = r.headers["set-cookie"]
            assert r.status_code == 200 and "fs_token=s3cret-token" in cookie
            assert "HttpOnly" in cookie and "SameSite=Strict" in cookie
            # the browser then sends the cookie back; no token in the URL needed
            r2 = await app.test_client().get("/api/takes", headers={"Cookie": "fs_token=s3cret-token"})
            assert r2.status_code == 200
            assert (await app.test_client().get("/api/takes", headers={"Cookie": "fs_token=nope"})).status_code == 401

    run(main())


def test_restart_resumes_interrupted_transcription(tmp_path, out_dir):
    chunks, _ = webm_chunks(tmp_path)
    holder = {}

    async def first():
        app = create_app(make_cfg(out_dir))
        async with app.test_app():
            c = app.test_client()
            holder["tid"] = await upload(c, chunks)
            await c.post(f"/api/takes/{holder['tid']}/finish")
            await wait_for(c, holder["tid"], {"ready"})

    run(first())
    tdir = out_dir / "_freeform" / "en-US" / "takes" / holder["tid"]
    for name in ("asr.json", "edit.json"):  # simulate: server died mid-transcription
        (tdir / name).unlink()
    doc = json.loads((tdir / "take.json").read_text())
    doc["status"] = "transcribing"
    (tdir / "take.json").write_text(json.dumps(doc))

    async def second():
        app = create_app(make_cfg(out_dir))
        async with app.test_app():
            take = await wait_for(app.test_client(), holder["tid"], {"ready", "error"})
            assert take["status"] == "ready"
            assert (await (await app.test_client().get(f"/api/takes/{holder['tid']}/edit")).get_json())["segments"]

    run(second())


def test_model_failure_is_readable_on_the_take_and_a_retry_succeeds(tmp_path, out_dir):
    chunks, _ = webm_chunks(tmp_path)
    attempts = []

    def flaky(name, **kw):  # first load fails like a dropped download, second works
        attempts.append(name)
        if len(attempts) == 1:
            raise ConnectionError("network unreachable")
        return fake_whisper_model()

    async def main():
        app = create_app(make_cfg(out_dir, asr_engine="faster-whisper"),
                         engine_factory=lambda cfg, model: FasterWhisperEngine(model, model_factory=flaky))
        async with app.test_app():
            c = app.test_client()
            tid = await upload(c, chunks)
            await c.post(f"/api/takes/{tid}/finish")
            take = await wait_for(c, tid, {"error", "ready"})
            assert take["status"] == "error" and take["error_stage"] == "transcribe"
            assert "Could not load the speech model" in take["error"] and "Traceback" not in take["error"]
            assert (out_dir / "_freeform" / "en-US" / "takes" / tid / "audio.wav").exists()  # nothing recorded was lost

            assert (await c.post(f"/api/takes/{tid}/transcribe", json={})).status_code == 202
            take = await wait_for(c, tid, {"ready", "error"})
            assert take["status"] == "ready" and take["asr"]["words"] == 2
            assert (await (await c.get(f"/api/takes/{tid}/edit")).get_json())["segments"]
            assert len(attempts) == 2

    run(main())
