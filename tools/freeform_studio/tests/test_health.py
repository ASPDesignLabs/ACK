# SPDX-License-Identifier: GPL-3.0-or-later
from collections import namedtuple

import pytest

from conftest import needs_ffmpeg
from freeform_studio import health
from freeform_studio.app import create_app
from test_api import make_cfg, run

Usage = namedtuple("Usage", "total used free")
MB = health.MB


def test_disk_status_reports_free_space_and_the_two_thresholds(monkeypatch, tmp_path):
    monkeypatch.setattr(health.shutil, "disk_usage", lambda p: Usage(100_000 * MB, 99_000 * MB, 1_000 * MB))
    d = health.disk_status(tmp_path, min_free_mb=500, warn_free_mb=3000)
    assert d["known"] and d["free_mb"] == 1000 and d["low"] and not d["critical"] and d["hours_left"] == 1.2
    monkeypatch.setattr(health.shutil, "disk_usage", lambda p: Usage(100_000 * MB, 99_800 * MB, 200 * MB))
    d = health.disk_status(tmp_path, 500, 3000)
    assert d["low"] and d["critical"] and d["hours_left"] == 0.0
    monkeypatch.setattr(health.shutil, "disk_usage", lambda p: Usage(100_000 * MB, 10_000 * MB, 90_000 * MB))
    d = health.disk_status(tmp_path, 500, 3000)
    assert not d["low"] and not d["critical"]


def test_when_the_disk_cannot_be_measured_nothing_is_blocked(monkeypatch, tmp_path):
    def boom(_p):
        raise OSError("no such device")
    monkeypatch.setattr(health.shutil, "disk_usage", boom)
    assert health.free_mb(tmp_path) == float("inf")
    d = health.disk_status(tmp_path, 500, 3000)
    assert d["known"] is False and not d["low"] and not d["critical"]


@needs_ffmpeg
def test_a_nearly_full_disk_refuses_new_audio_but_not_repeats_and_recovers(out_dir, monkeypatch):
    space = {"mb": 50_000.0}
    monkeypatch.setattr(health, "free_mb", lambda _p: space["mb"])

    async def main():
        app = create_app(make_cfg(out_dir))
        async with app.test_app():
            c = app.test_client()
            take = await (await c.post("/api/takes", json={})).get_json()
            tid = take["id"]
            assert (await c.put(f"/api/takes/{tid}/chunks/0", data=b"first part")).status_code == 200
            space["mb"] = 120.0                                                        # the disk fills up
            r = await c.put(f"/api/takes/{tid}/chunks/1", data=b"second part")
            body = await r.get_json()
            assert r.status_code == 507 and "almost out of disk space" in body["error"] and "safe on this phone" in body["error"]
            assert not list((out_dir / "_freeform").rglob("000001.bin"))               # nothing half-written
            assert (await c.put(f"/api/takes/{tid}/chunks/0", data=b"first part")).status_code == 200   # a repeat of a stored part is harmless
            assert "disk" in await (await c.get("/api/status")).get_json()               # the status still answers while it is refusing audio
            space["mb"] = 50_000.0                                                      # space freed
            assert (await c.put(f"/api/takes/{tid}/chunks/1", data=b"second part")).status_code == 200
            assert (await (await c.get(f"/api/takes/{tid}/chunks")).get_json())["received"] == 2

    run(main())


def test_the_status_reports_disk_space_in_a_stable_shape(out_dir):
    async def main():
        app = create_app(make_cfg(out_dir, min_free_mb=1, warn_free_mb=2))
        async with app.test_app():
            d = (await (await app.test_client().get("/api/status")).get_json())["disk"]
            assert set(d) >= {"known", "free_mb", "total_mb", "low", "critical", "min_free_mb", "warn_free_mb", "hours_left"}
            assert d["min_free_mb"] == 1 and d["warn_free_mb"] == 2 and d["known"] is True and d["low"] is False

    run(main())
