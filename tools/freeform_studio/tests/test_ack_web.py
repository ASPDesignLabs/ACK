# SPDX-License-Identifier: GPL-3.0-or-later
"""The browser's side of importing from ACK: getting a package onto the PC, looking inside it, adding it."""
import asyncio
import hashlib

import pytest

import freeform_studio.ack_import as imp
import freeform_studio.ack_web as web
from ack_package_builder import ClipSpec, PackageBuilder
from conftest import needs_ffmpeg
from freeform_studio.app import create_app
from freeform_studio.config import Config

pytestmark = needs_ffmpeg


def package_bytes(tmp_path, free=True):
    b = PackageBuilder()
    b.script_session([ClipSpec("The tide came in slowly.", speech=2.5), ClipSpec("We walked along the shore.", speech=3.0)])
    if free:
        b.free_session([(0.4, 3.0), (0.5, 7.0)], topic="morning")
    path = b.write(tmp_path / "built.zip")
    return path.read_bytes(), b


def run(coro):
    return asyncio.run(coro)


def app_for(out_dir, **kw):
    return create_app(Config(output_dir=out_dir, asr_engine="fake", asr_idle_unload_s=0, **kw))


async def upload(client, name, data, piece=40_000):
    sent = 0
    while sent < len(data):
        r = await client.put(f"/api/ack/incoming/{name}?offset={sent}", data=data[sent:sent + piece])
        assert r.status_code == 200, await r.get_json()
        sent = (await r.get_json())["received"]
    return await client.post(f"/api/ack/incoming/{name}/done", json={"size": len(data)})


async def settle(client, tid, timeout=30):
    for _ in range(int(timeout / 0.1)):
        doc = await (await client.get(f"/api/takes/{tid}")).get_json()
        if doc["status"] in ("ready", "error"):
            return doc
        await asyncio.sleep(0.1)
    raise AssertionError("timed out")


# ------------------------------------------------------------------ getting a package onto the PC
def test_the_list_is_empty_before_anything_is_there_and_creates_nothing(tmp_path, out_dir):
    async def main():
        async with (app := app_for(out_dir)).test_app():
            r = await app.test_client().get("/api/ack/incoming")
            body = await r.get_json()
            assert r.status_code == 200 and body["packages"] == [] and body["partial"] == [] and body["folder"].endswith("incoming")
    run(main())
    assert not (out_dir / "_freeform" / "en-US" / "incoming").exists()


def test_a_package_uploaded_in_pieces_arrives_whole_and_is_listed(tmp_path, out_dir):
    data, _ = package_bytes(tmp_path)

    async def main():
        async with (app := app_for(out_dir)).test_app():
            c = app.test_client()
            r = await upload(c, "ack training 1.zip", data)
            assert r.status_code == 200 and (await r.get_json())["bytes"] == len(data)
            listing = await (await c.get("/api/ack/incoming")).get_json()
            assert [p["name"] for p in listing["packages"]] == ["ack training 1.zip"] and listing["partial"] == []
    run(main())
    got = (out_dir / "_freeform" / "en-US" / "incoming" / "ack training 1.zip").read_bytes()
    assert hashlib.sha256(got).digest() == hashlib.sha256(data).digest()


def test_an_interrupted_upload_says_where_it_stopped_and_carries_on(tmp_path, out_dir):
    data, _ = package_bytes(tmp_path)
    half = len(data) // 2

    async def main():
        async with (app := app_for(out_dir)).test_app():
            c = app.test_client()
            assert (await c.put("/api/ack/incoming/p.zip?offset=0", data=data[:half])).status_code == 200
            listing = await (await c.get("/api/ack/incoming")).get_json()
            assert listing["packages"] == [] and listing["partial"] == [{"name": "p.zip", "bytes": half}]
            out_of_step = await c.put("/api/ack/incoming/p.zip?offset=99999", data=data[half:])
            assert out_of_step.status_code == 409 and (await out_of_step.get_json())["received"] == half
            assert (await c.put(f"/api/ack/incoming/p.zip?offset={half}", data=data[half:])).status_code == 200
            assert (await c.post("/api/ack/incoming/p.zip/done", json={"size": len(data)})).status_code == 200
            # starting over from the beginning is always allowed
            await c.put("/api/ack/incoming/q.zip?offset=0", data=b"PK\x03\x04junk")
            assert (await c.put("/api/ack/incoming/q.zip?offset=0", data=b"PK\x03\x04other")).status_code == 200
    run(main())
    assert (out_dir / "_freeform" / "en-US" / "incoming" / "q.zip.part").read_bytes() == b"PK\x03\x04other"
    assert (out_dir / "_freeform" / "en-US" / "incoming" / "p.zip").read_bytes() == data


@pytest.mark.parametrize("name", ["notes.txt", "evil.zip.exe", "a..b.zip", ".hidden.zip", "x" * 120 + ".zip", "sp ace;rm.zip"])
def test_names_that_are_not_package_names_are_refused(tmp_path, out_dir, name):
    async def main():
        async with (app := app_for(out_dir)).test_app():
            r = await app.test_client().put(f"/api/ack/incoming/{name}?offset=0", data=b"PK\x03\x04x")
            assert r.status_code in (400, 404)
    run(main())
    assert not (out_dir / "_freeform" / "en-US" / "incoming").exists()


def test_a_file_that_is_not_a_zip_is_refused_and_its_temporary_copy_removed(tmp_path, out_dir):
    async def main():
        async with (app := app_for(out_dir)).test_app():
            c = app.test_client()
            assert (await c.put("/api/ack/incoming/p.zip?offset=0", data=b"this is a text file")).status_code == 200
            r = await c.post("/api/ack/incoming/p.zip/done", json={})
            assert r.status_code == 400 and "not a zip" in (await r.get_json())["error"]
            assert (await (await c.get("/api/ack/incoming")).get_json())["partial"] == []
    run(main())


def test_a_short_upload_is_caught_when_it_is_finished(tmp_path, out_dir):
    async def main():
        async with (app := app_for(out_dir)).test_app():
            c = app.test_client()
            await c.put("/api/ack/incoming/p.zip?offset=0", data=b"PK\x03\x04" + b"x" * 100)
            r = await c.post("/api/ack/incoming/p.zip/done", json={"size": 5000})
            assert r.status_code == 409 and "only 104 of 5000" in (await r.get_json())["error"]
    run(main())


def test_an_upload_never_replaces_a_package_that_is_already_there(tmp_path, out_dir):
    data, _ = package_bytes(tmp_path)

    async def main():
        async with (app := app_for(out_dir)).test_app():
            c = app.test_client()
            await upload(c, "p.zip", data)
            r = await c.put("/api/ack/incoming/p.zip?offset=0", data=b"PK\x03\x04other")
            assert r.status_code == 409 and "already" in (await r.get_json())["error"]
    run(main())
    assert (out_dir / "_freeform" / "en-US" / "incoming" / "p.zip").read_bytes() == data


def test_upload_limits_and_a_full_disk(tmp_path, out_dir, monkeypatch):
    async def main():
        async with (app := app_for(out_dir)).test_app():
            c = app.test_client()
            monkeypatch.setattr(web, "MAX_UPLOAD_BYTES", 10)
            assert (await c.put("/api/ack/incoming/p.zip?offset=0", data=b"PK\x03\x04" + b"x" * 20)).status_code == 413
            monkeypatch.setattr(web, "MAX_UPLOAD_BYTES", 4 * 1024 ** 3)
            assert (await c.put("/api/ack/incoming/p.zip?offset=0", data=b"")).status_code == 400
            assert (await c.put("/api/ack/incoming/p.zip", data=b"x")).status_code == 400            # no offset
            monkeypatch.setattr(web, "free_mb", lambda _p: 10.0)
            r = await c.put("/api/ack/incoming/p.zip?offset=0", data=b"PK\x03\x04x")
            assert r.status_code == 507 and "almost out of disk space" in (await r.get_json())["error"]
    run(main())
    assert not (out_dir / "_freeform" / "en-US" / "incoming").exists()


def test_the_routes_need_the_access_token_like_everything_else(tmp_path, out_dir):
    async def main():
        async with (app := app_for(out_dir, token="secret")).test_app():
            c = app.test_client()
            for method, path in (("get", "/api/ack/incoming"), ("post", "/api/ack/check"), ("post", "/api/ack/import")):
                assert (await getattr(c, method)(path)).status_code == 401
            assert (await c.get("/api/ack/incoming", headers={"Authorization": "Bearer secret"})).status_code == 200
    run(main())


# ------------------------------------------------------------------ looking inside, then adding
def test_checking_shows_what_would_be_added_and_changes_nothing(tmp_path, out_dir):
    data, b = package_bytes(tmp_path)

    async def main():
        async with (app := app_for(out_dir)).test_app():
            c = app.test_client()
            await upload(c, "p.zip", data)
            r = await c.post("/api/ack/check", json={"name": "p.zip"})
            body = await r.get_json()
            assert r.status_code == 200 and body["to_import"] == 2 and body["enough_room"] is True
            assert [s["state"] for s in body["sessions"]] == ["new", "new"] and body["sessions"][0]["clips"] == 2
            assert body["package"]["sessions"][0]["id"] == b.sessions[0]["id"] and body["need_mb"] >= 1
            assert (await (await c.get("/api/takes")).get_json())["takes"] == []
    run(main())


def test_checking_a_missing_or_damaged_package_says_so(tmp_path, out_dir):
    data, _ = package_bytes(tmp_path)
    damaged = bytearray(data)
    damaged[len(damaged) // 2] ^= 0xFF

    async def main():
        async with (app := app_for(out_dir)).test_app():
            c = app.test_client()
            assert (await c.post("/api/ack/check", json={"name": "nope.zip"})).status_code == 404
            assert (await c.post("/api/ack/check", json={})).status_code == 400
            await upload(c, "bad.zip", bytes(damaged))
            r = await c.post("/api/ack/check", json={"name": "bad.zip"})
            assert r.status_code == 400 and (await r.get_json())["error"].endswith("Nothing was imported.")
    run(main())


def test_importing_adds_the_recordings_and_starts_processing_them(tmp_path, out_dir):
    data, b = package_bytes(tmp_path)

    async def main():
        async with (app := app_for(out_dir)).test_app():
            c = app.test_client()
            await upload(c, "p.zip", data)
            r = await c.post("/api/ack/import", json={"name": "p.zip"})
            created = (await r.get_json())["created"]
            assert r.status_code == 200 and {x["session"] for x in created} == {s["id"] for s in b.sessions}
            for x in created:
                doc = await settle(c, x["take_id"])
                assert doc["status"] == "ready", doc.get("error")
                assert doc["client"]["source"] == "ack"
            again = await (await c.post("/api/ack/import", json={"name": "p.zip"})).get_json()
            assert again["created"] == []                                     # already imported: nothing added twice
            assert len((await (await c.get("/api/takes")).get_json())["takes"]) == 2
    run(main())


def test_importing_only_some_sessions(tmp_path, out_dir):
    data, b = package_bytes(tmp_path)

    async def main():
        async with (app := app_for(out_dir)).test_app():
            c = app.test_client()
            await upload(c, "p.zip", data)
            r = await c.post("/api/ack/import", json={"name": "p.zip", "sessions": [b.sessions[1]["id"]]})
            assert [x["session"] for x in (await r.get_json())["created"]] == [b.sessions[1]["id"]]
            assert (await c.post("/api/ack/import", json={"name": "p.zip", "sessions": "all"})).status_code == 400
            assert (await c.post("/api/ack/import", json={"name": "p.zip", "sessions": ["s20261002-999999-ffff"]})).status_code == 400
    run(main())


def test_a_full_disk_stops_the_import_with_a_clear_message_and_nothing_is_written(tmp_path, out_dir, monkeypatch):
    data, _ = package_bytes(tmp_path)

    async def main():
        async with (app := app_for(out_dir)).test_app():
            c = app.test_client()
            await upload(c, "p.zip", data)
            monkeypatch.setattr(imp, "free_mb", lambda _p: 100.0)
            r = await c.post("/api/ack/import", json={"name": "p.zip"})
            assert r.status_code == 507 and "not enough free space" in (await r.get_json())["error"]
            assert (await (await c.get("/api/takes")).get_json())["takes"] == []
    run(main())


# ------------------------------------------------------------------ the phone's notes for one recording
def test_a_recording_from_ack_reports_the_phones_notes_and_a_normal_one_does_not(tmp_path, out_dir):
    data, b = package_bytes(tmp_path, free=False)

    async def main():
        async with (app := app_for(out_dir)).test_app():
            c = app.test_client()
            await upload(c, "p.zip", data)
            tid = (await (await c.post("/api/ack/import", json={"name": "p.zip"})).get_json())["created"][0]["take_id"]
            await settle(c, tid)
            r = await c.get(f"/api/takes/{tid}/ack")
            body = await r.get_json()
            assert r.status_code == 200 and body["notes"]["mode"] == "script" and len(body["notes"]["clips"]) == 2
            assert body["notes"]["clips"][0]["text"] == "The tide came in slowly." and set(body["checks"]["pieces"]) == {"s001", "s002"}
            plain = (await (await c.post("/api/takes", json={})).get_json())["id"]
            assert (await c.get(f"/api/takes/{plain}/ack")).status_code == 404
            assert (await c.get("/api/takes/not-a-take/ack")).status_code == 404
    run(main())
