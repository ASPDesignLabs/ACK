# SPDX-License-Identifier: GPL-3.0-or-later
"""What the phone page says when the PC is short of space, and that nothing is lost."""
import json

import pytest

pytest.importorskip("playwright")
from playwright.sync_api import expect  # noqa: E402

from conftest import needs_ffmpeg  # noqa: E402
from test_capture_ui import api, phone, shot, wait_ready  # noqa: E402,F401

pytestmark = needs_ffmpeg


def test_a_full_pc_makes_the_phone_wait_and_explain_then_everything_arrives(phone, server):
    page, _ctx, problems = phone
    before = len(api(server, "/api/takes")["takes"])
    refuse = lambda route: route.fulfill(status=507, content_type="application/json", body=json.dumps(
        {"error": "Your PC is almost out of disk space (120 MB free). Free some up and sending carries on by itself."}))
    page.route("**/api/takes/*/chunks/*", refuse)
    page.locator("#start").click()
    expect(page.locator("#state")).to_contain_text("Recording")
    expect(page.locator("#waiting")).to_contain_text("out of disk space", timeout=15000)
    shot(page, "60-disk-full")
    assert page.locator("#start").count() == 1 and "Recording" in page.locator("#state").inner_text()   # still recording: nothing was stopped
    page.unroute("**/api/takes/*/chunks/*")                                      # space is freed
    page.wait_for_timeout(2500)
    page.locator("#stop").click()
    expect(page.locator("#state")).to_contain_text("Saved", timeout=45000)
    wait_ready(page)
    newest = api(server, "/api/takes")["takes"][0]
    assert len(api(server, "/api/takes")["takes"]) == before + 1
    assert newest["chunks"]["missing"] == [] and newest["duration"] > 3.0       # every part that was refused arrived afterwards


def test_a_low_disk_warning_appears_on_the_record_page_with_plain_numbers(phone, server):
    page, ctx, _ = phone
    def low(route):
        real = route.fetch()
        body = real.json()
        body["disk"] = {"known": True, "free_mb": 1400, "total_mb": 500000, "low": True, "critical": False,
                        "min_free_mb": 500, "warn_free_mb": 3000, "hours_left": 2.2}
        route.fulfill(response=real, json=body)
    page.route("**/api/status", low)
    page.reload()
    banner = page.locator("#diskwarn")
    expect(banner).to_be_visible(timeout=10000)
    expect(banner).to_contain_text("about 1.4 GB of disk space left")
    expect(banner).to_contain_text("roughly 2.2 hours")
    assert page.get_attribute("#diskwarn", "role") == "status"
    shot(page, "61-disk-low")
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    page.unroute("**/api/status")
    page.reload()
    expect(page.locator("#conn")).to_contain_text("Connected")
    expect(banner).to_be_hidden()


def test_a_critical_disk_warning_says_new_audio_is_refused_and_stays_on_the_phone(phone):
    page, *_ = phone
    def critical(route):
        real = route.fetch()
        body = real.json()
        body["disk"] = {"known": True, "free_mb": 200, "total_mb": 500000, "low": True, "critical": True,
                        "min_free_mb": 500, "warn_free_mb": 3000, "hours_left": 0.0}
        route.fulfill(response=real, json=body)
    page.route("**/api/status", critical)
    page.reload()
    expect(page.locator("#diskwarn")).to_contain_text("refusing new audio", timeout=10000)
    expect(page.locator("#diskwarn")).to_contain_text("stays on this phone")
