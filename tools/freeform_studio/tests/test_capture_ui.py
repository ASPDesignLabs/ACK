# SPDX-License-Identifier: GPL-3.0-or-later
"""Drives the real server with headless Chromium at phone size and a fake microphone."""
import json
import os
import urllib.request
from pathlib import Path

import pytest

pytest.importorskip("playwright")
from playwright.sync_api import expect  # noqa: E402

from conftest import needs_ffmpeg  # noqa: E402

pytestmark = needs_ffmpeg
SHOTS = os.environ.get("FS_SHOTS")


@pytest.fixture
def phone(browser, server):
    ctx = browser.new_context(viewport={"width": 412, "height": 915}, device_scale_factor=2, is_mobile=True,
                              has_touch=True, permissions=["microphone"])
    page = ctx.new_page()
    problems = []
    page.on("console", lambda m: problems.append(m.text) if m.type in ("error", "warning") else None)
    page.on("pageerror", lambda e: problems.append(str(e)))
    page.on("dialog", lambda d: d.accept())
    page.goto(server["base"] + "/")
    yield page, ctx, problems
    ctx.close()


def api(server, path):
    with urllib.request.urlopen(server["base"] + path, timeout=5) as r:
        return json.loads(r.read())


def shot(page, name):
    if SHOTS:
        Path(SHOTS).mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(Path(SHOTS) / f"{name}.png"))


def wait_ready(page, timeout=40000):
    expect(page.locator(".take .chip").first).to_have_text("Ready to review", timeout=timeout)


def test_idle_page_is_usable_at_phone_size_and_clean(phone, server):
    page, ctx, problems = phone
    expect(page.locator("#conn")).to_contain_text("Connected to your PC")
    start = page.locator("#start")
    box = start.bounding_box()
    assert box["height"] >= 48 and box["width"] >= 120
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")  # no sideways scrolling
    assert page.get_attribute("html", "lang") == "en" and page.locator("#state[aria-live='polite']").count() == 1
    for btn in page.locator("button").all():
        assert btn.inner_text().strip(), "every button needs a text label"
    # the start button sits in the bottom thumb zone
    assert box["y"] > 915 * 0.7
    shot(page, "01-idle")
    assert problems == [], problems  # includes any Content-Security-Policy violations
    page.emulate_media(reduced_motion="reduce")
    assert page.evaluate("getComputedStyle(document.getElementById('meterbar')).transitionDuration") in ("0s", "")
    r = ctx.request.get(server["base"] + "/static/js/main.js")
    csp = r.headers["content-security-policy"]
    assert "script-src 'self'" in csp and "frame-ancestors 'none'" in csp and r.headers["x-content-type-options"] == "nosniff"


def test_record_pause_stop_becomes_a_reviewable_take(phone, server):
    page, _ctx, problems = phone
    page.locator(".ref summary").click()  # the optional reference-text box starts collapsed
    page.locator("#ref").fill("one two three four five six seven eight nine ten")
    page.locator("#start").click()
    expect(page.locator("#state")).to_contain_text("Recording")
    expect(page.locator("#micinfo")).to_contain_text("echo cancel off")  # the phone honoured our request
    expect(page.locator("#pause")).to_be_visible()
    page.wait_for_timeout(2500)
    shot(page, "02-recording")
    assert page.locator("#timer").inner_text() != "00:00"
    expect(page.locator("#sent")).to_contain_text("parts")

    page.locator("#pause").click()
    expect(page.locator("#state")).to_contain_text("Paused")
    frozen = page.locator("#timer").inner_text()
    page.wait_for_timeout(1300)
    assert page.locator("#timer").inner_text() == frozen  # the clock stops while paused
    page.locator("#pause").click()
    expect(page.locator("#state")).to_contain_text("Recording")
    page.wait_for_timeout(1500)

    page.locator("#stop").click()
    expect(page.locator("#state")).to_contain_text("Saved", timeout=20000)
    wait_ready(page)
    page.locator(".take summary").first.click()
    expect(page.locator(".take .segs li").first).to_be_visible()
    shot(page, "03-ready")
    take = api(server, "/api/takes")["takes"][0]
    assert take["status"] == "ready" and take["chunks"]["missing"] == [] and 3.0 < take["duration"] < 9.0
    assert take["reference_text"].startswith("one two")
    assert page.locator("#start").inner_text() == "Start another recording"
    assert problems == [], problems


def test_wifi_drop_mid_recording_loses_nothing(phone, server):
    page, ctx, _ = phone
    before = len(api(server, "/api/takes")["takes"])
    page.locator("#start").click()
    expect(page.locator("#state")).to_contain_text("Recording")
    page.wait_for_timeout(2000)
    ctx.set_offline(True)
    page.wait_for_timeout(3500)
    expect(page.locator("#waiting")).to_contain_text("retrying")
    shot(page, "04-offline")
    ctx.set_offline(False)
    page.wait_for_timeout(2500)
    page.locator("#stop").click()
    expect(page.locator("#state")).to_contain_text("Saved", timeout=45000)
    wait_ready(page)
    takes = api(server, "/api/takes")["takes"]
    assert len(takes) == before + 1
    newest = takes[0]
    assert newest["chunks"]["missing"] == [] and newest["duration"] > 6.5  # the offline stretch is all there


def test_crash_or_refresh_with_unsent_audio_can_be_finished_later(phone, server):
    page, _ctx, _ = phone
    before = len(api(server, "/api/takes")["takes"])
    page.route("**/api/takes/*/chunks/*", lambda route: route.abort())  # the PC "cannot be reached" for audio
    page.locator("#start").click()
    expect(page.locator("#state")).to_contain_text("Recording")
    page.wait_for_timeout(3500)
    page.reload()  # the recorder dies with the page; the audio saved on the phone does not
    page.unroute("**/api/takes/*/chunks/*")
    banner = page.locator("#resume")
    expect(banner).to_be_visible(timeout=10000)
    expect(page.locator("#resume-text")).to_contain_text("Nothing is lost")
    shot(page, "05-resume")
    page.locator("#resume-go").click()
    expect(banner).to_be_hidden(timeout=30000)
    wait_ready(page)
    newest = api(server, "/api/takes")["takes"][0]
    assert len(api(server, "/api/takes")["takes"]) == before + 1
    assert newest["chunks"]["missing"] == [] and 2.0 < newest["duration"] < 6.5


def test_blocked_or_missing_microphone_gets_plain_advice(browser, server):
    for script, expect_text in (
        ("navigator.mediaDevices.getUserMedia = () => Promise.reject(new DOMException('no', 'NotAllowedError'));", "blocked"),
        ("Object.defineProperty(navigator, 'mediaDevices', {value: undefined});", "https"),
    ):
        ctx = browser.new_context(viewport={"width": 412, "height": 915})
        page = ctx.new_page()
        page.add_init_script(script)
        page.goto(server["base"] + "/")
        page.locator("#start").click()
        expect(page.locator("#notice")).to_contain_text(expect_text)
        assert page.locator("#start").is_enabled() and page.locator("#state").inner_text() != ""
        shot(page, f"06-mic-{expect_text}")
        ctx.close()
