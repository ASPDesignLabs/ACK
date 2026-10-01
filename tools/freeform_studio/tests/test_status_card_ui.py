# SPDX-License-Identifier: GPL-3.0-or-later
"""The Status and safety card: disk space, backups, and the speech model's memory."""
import json
from datetime import datetime, timedelta

import pytest

pytest.importorskip("playwright")
from playwright.sync_api import expect  # noqa: E402

from conftest import needs_ffmpeg  # noqa: E402
from freeform_studio import backup as bk  # noqa: E402
from test_review_ui import http, new_page, shot, take  # noqa: E402,F401

pytestmark = needs_ffmpeg


def test_backing_up_from_the_page_is_encouraged_checked_and_not_repeated_needlessly(browser, server, take):
    page, ctx, problems = new_page(browser, server, "/review")
    card = page.locator("#statuscard")
    expect(card).to_be_visible()
    expect(page.locator("#st-disk")).to_contain_text("GB free", timeout=10000)
    expect(page.locator("#st-backup")).to_contain_text("No backup yet. Your recordings exist only on this PC")   # a nudge, not a modal
    expect(page.locator("#st-backup-where")).to_contain_text(str(server["backups"]))
    expect(page.locator("#st-backup-where")).to_contain_text("Automatic backups are off")
    shot(page, "70-status-no-backup")
    page.locator("#st-backup-go").click()
    expect(page.locator("#st-backup-result")).to_contain_text("then read the copy back to check it", timeout=20000)
    expect(page.locator("#st-backup")).to_contain_text("Last backup just now")
    archives = list(server["backups"].glob("*.tar.gz"))
    assert len(archives) == 1
    problems_found, manifest = bk.verify(archives[0])
    assert problems_found == [] and any(f["path"].endswith(f"{take}/edit.json") for f in manifest["files"])   # the page's backup really holds this recording
    page.locator("#st-backup-go").click()
    expect(page.locator("#st-backup-result")).to_contain_text("Nothing has changed since the last backup", timeout=20000)
    assert len(list(server["backups"].glob("*.tar.gz"))) == 1
    assert problems == [], problems
    ctx.close()


def test_an_old_backup_is_pointed_out_gently(browser, server, take):
    bk_dir = server["backups"]
    side = next(bk_dir.glob("*.tar.gz.json"), None)
    if side is None:
        http(server, "/api/backup", "POST", {"force": True})
        side = next(bk_dir.glob("*.tar.gz.json"))
    doc = json.loads(side.read_text())
    doc["created"] = (datetime.now() - timedelta(days=12)).isoformat(timespec="seconds")
    side.write_text(json.dumps(doc))
    page, ctx, _ = new_page(browser, server, "/review")
    expect(page.locator("#st-backup")).to_contain_text("Last backup 12 days ago", timeout=10000)
    expect(page.locator("#st-backup")).to_contain_text("more than a week ago")
    assert page.locator("#st-backup-go").is_enabled()
    ctx.close()


def test_the_speech_model_can_be_freed_from_memory_before_training(browser, server, take):
    page, ctx, _ = new_page(browser, server, "/review")
    expect(page.locator("#st-model")).to_contain_text("(test mode): loaded in memory", timeout=10000)
    expect(page.locator("#st-model-free")).to_be_enabled()
    page.locator("#st-model-free").click()
    expect(page.locator("#st-model-result")).to_contain_text("Freed. It loads again by itself")
    expect(page.locator("#st-model")).to_contain_text("not in memory right now")
    expect(page.locator("#st-model-free")).to_be_disabled()
    assert http(server, "/api/status")["asr"]["loaded"] is False
    ctx.close()


def test_the_card_fits_a_narrow_phone_in_the_dark_and_announces_politely(browser, server, take):
    page, ctx, problems = new_page(browser, server, "/review", viewport={"width": 320, "height": 640}, color_scheme="dark")
    expect(page.locator("#st-disk")).to_contain_text("GB free", timeout=10000)
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    for sel in ("#st-backup-result", "#st-model-result"):
        assert page.get_attribute(sel, "aria-live") == "polite"
    for sel in ("#st-backup-go", "#st-model-free"):
        box = page.locator(sel).bounding_box()
        assert box["x"] >= 0 and box["x"] + box["width"] <= 320 and box["height"] >= 40, sel
    page.evaluate("document.getElementById('statuscard').scrollIntoView({block: 'start'})")
    shot(page, "71-status-narrow-dark")
    assert problems == [], problems
    ctx.close()
