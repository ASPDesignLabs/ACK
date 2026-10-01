# SPDX-License-Identifier: GPL-3.0-or-later
import asyncio
import json

import pytest

from conftest import needs_ffmpeg
from freeform_studio import export as ex
from freeform_studio.app import create_app
from test_build_dataset import seg, write_take
from test_export import approved, folder
from test_api import make_cfg, run

pytestmark = needs_ffmpeg
A = "t20260930-000001-aaaa"
B = "t20260930-000002-bbbb"


def test_preview_then_export_one_recording_and_all(out_dir):
    write_take(out_dir, A, [approved(1, 0.0, 3.0, "From A."), seg(2, 3.0, 6.0, "Pending."), approved(3, 6.0, 6.4, "Short.")], seconds=10.0)
    write_take(out_dir, B, [approved(1, 0.0, 3.0, "From B.")], seconds=10.0)

    async def main():
        app = create_app(make_cfg(out_dir))
        async with app.test_app():
            c = app.test_client()
            r = await c.get(f"/api/takes/{A}/export")
            body = await r.get_json()
            assert r.status_code == 200 and body["counts"] == {"new": 1, "updated": 0, "unchanged": 0, "retired": 0, "left_out": 1}
            assert body["new"][0]["text"] == "From A." and body["left_out"][0]["reason"].startswith("too short")
            assert body["folder_name"] == "en-US/freeform"
            assert not folder(out_dir).exists()                               # a preview writes nothing

            r = await c.post(f"/api/takes/{A}/export")
            assert r.status_code == 200 and (await r.get_json())["counts"]["new"] == 1
            assert sorted(p.name for p in folder(out_dir).glob("*.wav")) == [f"{A}_s001.wav"]    # only that recording

            r = await c.get("/api/export")
            assert (await r.get_json())["counts"] == {"new": 1, "updated": 0, "unchanged": 1, "retired": 0, "left_out": 1}
            r = await c.post("/api/export")
            assert (await r.get_json())["counts"]["unchanged"] == 1
            assert sorted(p.name for p in folder(out_dir).glob("*.wav")) == [f"{A}_s001.wav", f"{B}_s001.wav"]

            r = await c.post(f"/api/takes/{A}/export")                        # nothing changed since
            body = await r.get_json()
            assert body["counts"]["new"] == body["counts"]["updated"] == body["counts"]["retired"] == 0

    run(main())


def test_unknown_recordings_and_busy_exports_are_explained_and_an_empty_library_is_fine(out_dir, tmp_path):
    write_take(out_dir, A, [approved(1, 0.0, 3.0)], seconds=5.0)

    async def main():
        app = create_app(make_cfg(out_dir))
        async with app.test_app():
            c = app.test_client()
            assert (await c.get("/api/takes/t20260101-000000-abcd/export")).status_code == 404
            assert (await c.post("/api/takes/not-an-id/export")).status_code in (400, 404)
            folder(out_dir).mkdir(parents=True)
            (folder(out_dir) / ex.LOCK).write_text("1")
            r = await c.post("/api/export")
            assert r.status_code == 409 and "Another export is running" in (await r.get_json())["error"]
            (await c.get("/api/export"))                                       # looking is still fine while another export runs
        empty = tmp_path / "empty"
        empty.mkdir()
        app = create_app(make_cfg(empty))
        async with app.test_app():
            r = await app.test_client().get("/api/export")                      # nothing recorded yet: an empty plan, not an error
            assert r.status_code == 200 and (await r.get_json())["counts"] == {"new": 0, "updated": 0, "unchanged": 0, "retired": 0, "left_out": 0}

    run(main())


def test_a_recording_that_is_still_being_processed_is_skipped_not_exported(out_dir):
    write_take(out_dir, A, [approved(1, 0.0, 3.0)], seconds=5.0, status="transcribing")

    async def main():
        app = create_app(make_cfg(out_dir))
        async with app.test_app():
            c = app.test_client()
            body = await (await c.get(f"/api/takes/{A}/export")).get_json()
            assert body["counts"]["new"] == 0 and body["skipped_takes"] == [{"take": A, "status": "transcribing"}]

    run(main())


def test_the_export_pages_need_the_same_token_as_everything_else(out_dir):
    write_take(out_dir, A, [approved(1, 0.0, 3.0)], seconds=5.0)

    async def main():
        app = create_app(make_cfg(out_dir, token="secret"))
        async with app.test_app():
            c = app.test_client()
            assert (await c.get("/api/export")).status_code == 401
            assert (await c.post("/api/export")).status_code == 401
            assert (await c.get("/api/export", headers={"Authorization": "Bearer secret"})).status_code == 200
            assert not folder(out_dir).exists()

    run(main())
