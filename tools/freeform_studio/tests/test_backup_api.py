import asyncio
import json
import os

import pytest

from freeform_studio import backup as bk
from freeform_studio.app import create_app
from test_api import make_cfg, run
from test_backup import A, B, make_take


def lib(out_dir):
    make_take(out_dir, A)
    make_take(out_dir, B, raw=None, status="recording", parts=[b"one"])
    return out_dir


def test_without_a_backup_folder_the_api_says_so_and_refuses(out_dir):
    async def main():
        app = create_app(make_cfg(out_dir))
        async with app.test_app():
            c = app.test_client()
            st = await (await c.get("/api/backup")).get_json()
            assert st["enabled"] is False and st["auto"]["enabled"] is False
            r = await c.post("/api/backup")
            assert r.status_code == 400 and "--backup-dir" in (await r.get_json())["error"]

    run(main())


def test_backing_up_by_hand_reports_what_happened_and_skips_when_nothing_changed(out_dir, tmp_path):
    lib(out_dir)

    async def main():
        app = create_app(make_cfg(out_dir, backup_dir=tmp_path / "bk", backup_every_hours=0))
        async with app.test_app():
            c = app.test_client()
            st = await (await c.get("/api/backup")).get_json()
            assert st["enabled"] and st["count"] == 0 and st["last"] is None and st["takes_present"] is True and st["auto"]["enabled"] is False
            r = await c.post("/api/backup")
            body = await r.get_json()
            assert r.status_code == 200 and not body["skipped"] and body["takes"] == 2 and body["archive_bytes"] > 0
            assert body["status"]["count"] == 1 and body["status"]["last"]["name"] == body["name"]
            assert 0 <= body["status"]["age_hours"] < 1
            again = await (await c.post("/api/backup")).get_json()
            assert again["skipped"] and "Nothing has changed" in again["reason"] and again["name"] == body["name"]
            forced = await (await c.post("/api/backup", json={"force": True})).get_json()
            assert not forced["skipped"] and forced["status"]["count"] == 2
            assert bk.verify(tmp_path / "bk" / forced["name"])[0] == []

    run(main())


def test_busy_and_unsafe_backups_are_explained(out_dir, tmp_path):
    lib(out_dir)

    async def main():
        dest = tmp_path / "bk"
        dest.mkdir()
        (dest / bk.LOCK).write_text("1")
        app = create_app(make_cfg(out_dir, backup_dir=dest, backup_every_hours=0))
        async with app.test_app():
            r = await app.test_client().post("/api/backup")
            assert r.status_code == 409 and "Another backup is running" in (await r.get_json())["error"]
        inside = out_dir / "_freeform" / "en-US" / "bk"
        app = create_app(make_cfg(out_dir, backup_dir=inside, backup_every_hours=0))
        async with app.test_app():
            c = app.test_client()
            r = await c.post("/api/backup")
            assert r.status_code == 400 and "would back itself up" in (await r.get_json())["error"]
            assert "would back itself up" in (await (await c.get("/api/backup")).get_json())["error"]   # the page can show why

    run(main())


def test_the_timer_backs_up_only_when_something_changed_and_a_failure_does_not_stop_it(out_dir, tmp_path, monkeypatch):
    lib(out_dir)
    calls = []
    real = bk.create

    def flaky(*a, **k):
        calls.append(1)
        if len(calls) == 2:
            raise bk.BackupError("the backup disk is full")
        return real(*a, **k)

    monkeypatch.setattr(bk, "create", flaky)

    async def main():
        dest = tmp_path / "bk"
        app = create_app(make_cfg(out_dir, backup_dir=dest, backup_every_hours=0.0004, backup_first_delay_s=0))   # about every 1.4 s
        async with app.test_app():
            c = app.test_client()
            await asyncio.sleep(0.6)
            assert len(bk.list_backups(dest)) == 1                                  # the first pass backed up
            await asyncio.sleep(1.6)                                                # second pass fails
            st = await (await c.get("/api/backup")).get_json()
            assert st["error"] == "the backup disk is full" and st["auto"]["enabled"] is True
            (out_dir / "_freeform" / "en-US" / "takes" / A / "edit.json").write_text(json.dumps({"rev": 8}))   # something changes
            await asyncio.sleep(1.6)                                                # the loop carried on, and the change was backed up
            assert len(bk.list_backups(dest)) == 2
            assert (await (await c.get("/api/backup")).get_json())["error"] is None
            n = len(calls)
            await asyncio.sleep(1.6)
            assert len(bk.list_backups(dest)) == 2 and len(calls) > n                # it keeps looking, but writes nothing when nothing changed

    run(main())


def test_the_backup_status_needs_the_same_token_as_everything_else(out_dir, tmp_path):
    async def main():
        app = create_app(make_cfg(out_dir, token="secret", backup_dir=tmp_path / "bk", backup_every_hours=0))
        async with app.test_app():
            c = app.test_client()
            assert (await c.get("/api/backup")).status_code == 401 and (await c.post("/api/backup")).status_code == 401
            assert (await c.get("/api/backup", headers={"Authorization": "Bearer secret"})).status_code == 200
            assert not (tmp_path / "bk").exists()

    run(main())
