# SPDX-License-Identifier: GPL-3.0-or-later
"""The Training clips card: preview, confirm, write, and what happens when things change afterwards."""
import json

import pytest

pytest.importorskip("playwright")
from playwright.sync_api import expect  # noqa: E402

from conftest import needs_ffmpeg  # noqa: E402
from test_review_ui import (  # noqa: E402,F401  (fixtures and helpers shared with the other review tests)
    PIECES, edit, explain_failure, http, new_page, review, saved, seed_take, shot, take,
)

pytestmark = needs_ffmpeg


def mark(server, take_id, approved=(), tags=None):
    doc = edit(server, take_id)
    for s in doc["segments"]:
        if s["id"] in approved:
            s["status"] = "approved"
        if tags and s["id"] in tags:
            s["tags"] = tags[s["id"]]
    http(server, f"/api/takes/{take_id}/edit", "PUT", {"rev": doc["rev"], "segments": doc["segments"]})


def folder(server):
    return server["out"] / "en-US" / "freeform"


def stems(server, take_id):
    return sorted(p.stem for p in folder(server).glob(f"{take_id}_*.wav")) if folder(server).exists() else []


@pytest.fixture
def approving(browser, server, take, request, tmp_path):
    mark(server, take, approved=("s001", "s002", "s003", "s004"), tags={"s004": ["laugh"]})
    page, ctx, problems = new_page(browser, server, f"/review/{take}")
    expect(page.locator("#piece-title")).to_have_text("Piece 1 of 1")        # only s005 is still waiting
    yield page, ctx, problems, take
    if getattr(request.node, "rep_call", None) is not None and request.node.rep_call.failed:
        explain_failure(page, problems, tmp_path)
    ctx.close()


def open_card(page):
    page.locator("#exportcard > summary").click()


def test_the_card_says_what_would_be_exported_and_why_approved_pieces_are_left_out(approving, server):
    page, _ctx, problems, take = approving
    open_card(page)
    expect(page.locator("#export-summary")).to_contain_text("3 new clips to write", timeout=10000)
    expect(page.locator("#export-summary")).to_contain_text("The folder would hold 5 seconds of speech")
    expect(page.locator("#export-details")).to_contain_text("1 approved piece is not included")
    expect(page.locator("#export-details .reasons").first).to_contain_text("tagged: laugh")
    expect(page.locator("#export-go")).to_have_text("Export (3 new, 0 replaced, 0 moved aside)")
    assert stems(server, take) == [] and not folder(server).joinpath(".presplit").exists()   # looking changes nothing
    page.locator("#exportcard").scroll_into_view_if_needed()
    shot(page, "50-export-preview")
    assert problems == [], problems


def test_exporting_asks_first_writes_the_clips_and_says_where(approving, server):
    page, _ctx, _, take = approving
    open_card(page)
    expect(page.locator("#export-go")).to_be_enabled(timeout=10000)
    page.locator("#export-go").click()
    expect(page.locator("#confirm-title")).to_have_text("Write these training clips?")
    expect(page.locator("#confirm-body")).to_contain_text("en\u2011US/freeform")
    expect(page.locator("#confirm-body")).to_contain_text("Full path: ")
    expect(page.locator("#confirm-body")).to_contain_text("Your recordings are never changed")
    shot(page, "51-export-confirm")
    page.locator("#confirm-cancel").click()
    page.wait_for_timeout(300)
    assert stems(server, take) == []                                         # cancelled: nothing written
    page.locator("#export-go").click()
    page.locator("#confirm-ok").click()
    expect(page.locator("#export-result")).to_contain_text("Wrote 3 new clips", timeout=15000)
    assert stems(server, take) == [f"{take}_s001", f"{take}_s002", f"{take}_s003"]      # the laugh-tagged one is not among them
    for stem in stems(server, take):
        assert (folder(server) / f"{stem}.txt").read_text().strip() == next(p[3] for p in PIECES if p[0] == stem.split("_")[1])
    assert (folder(server) / ".presplit").exists() and (folder(server) / "manifest.json").exists()
    expect(page.locator("#export-summary")).to_contain_text("Everything approved is already exported")
    expect(page.locator("#export-go")).to_be_disabled()
    expect(page.locator("#export-go")).to_have_text("Nothing to export")


def test_changes_after_an_export_are_offered_and_the_old_versions_are_kept(approving, server):
    page, _ctx, _, take = approving
    open_card(page)
    expect(page.locator("#export-go")).to_be_enabled(timeout=10000)
    page.locator("#export-go").click()
    page.locator("#confirm-ok").click()
    expect(page.locator("#export-result")).to_contain_text("Wrote 3 new clips", timeout=15000)
    page.select_option("#filter", "all")                                     # now un-approve one and correct another
    page.locator("#list .pitem").nth(1).click()
    page.locator("#reset").click()
    page.locator("#list .pitem").nth(0).click()
    page.locator("#p-text").fill("Hello there, my dear friend.")
    page.locator("#take-title").click()
    page.locator("#export-check").click()                                    # unsaved edits are saved first, so they count
    expect(page.locator("#export-summary")).to_contain_text("1 clip to replace with a newer version", timeout=10000)
    expect(page.locator("#export-summary")).to_contain_text("1 clip that no longer qualify")
    expect(page.locator("#export-go")).to_have_text("Export (0 new, 1 replaced, 1 moved aside)")
    page.locator("#export-details summary", has_text="to move aside").click()
    expect(page.locator("#export-details")).to_contain_text("not approved yet")
    page.locator("#export-go").click()
    expect(page.locator("#confirm-body")).to_contain_text("moves 2 older clips aside")
    page.locator("#confirm-ok").click()
    expect(page.locator("#export-result")).to_contain_text("moved 1 aside", timeout=15000)
    assert stems(server, take) == [f"{take}_s001", f"{take}_s003"]
    assert (folder(server) / f"{take}_s001.txt").read_text() == "Hello there, my dear friend.\n"
    kept = list((server["out"] / "_freeform" / "en-US" / "retired").rglob(f"{take}_s0*.txt"))
    assert sorted(p.name for p in kept) == [f"{take}_s001.txt", f"{take}_s002.txt"]
    assert next(p for p in kept if p.name.endswith("s001.txt")).read_text() == "Hello there my friend.\n"


def test_nothing_approved_is_said_plainly_and_there_is_nothing_to_press(review, server):
    page, _ctx, _, take = review
    page.locator("#exportcard > summary").click()
    expect(page.locator("#export-summary")).to_contain_text("Nothing is approved yet", timeout=10000)
    expect(page.locator("#export-go")).to_be_disabled()


def test_the_recordings_list_exports_every_recording_at_once(browser, server, tmp_path_factory):
    ids = [seed_take(server, tmp_path_factory.mktemp("t"), PIECES) for _ in range(2)]
    for i in ids:
        mark(server, i, approved=("s001", "s002"))
    page, ctx, problems = new_page(browser, server, "/review")
    expect(page.locator("#inbox-list .take").first).to_be_visible()
    page.locator("#exportcard > summary").click()
    expect(page.locator("#export-summary")).to_contain_text("new clips to write", timeout=15000)
    page.locator("#export-go").click()
    page.locator("#confirm-ok").click()
    expect(page.locator("#export-result")).to_contain_text("Wrote", timeout=20000)
    for i in ids:
        assert stems(server, i) == [f"{i}_s001", f"{i}_s002"]
    expect(page.locator("#export-summary")).to_contain_text("Everything approved is already exported")
    assert problems == [], problems
    ctx.close()


def test_the_card_fits_a_narrow_phone_in_both_themes_and_is_announced_politely(browser, server, take):
    mark(server, take, approved=("s001", "s002", "s003"), tags={"s003": ["noise"]})
    page, ctx, problems = new_page(browser, server, f"/review/{take}", viewport={"width": 320, "height": 640}, color_scheme="dark")
    expect(page.locator("#piece-title")).to_be_visible()
    page.locator("#exportcard > summary").click()
    expect(page.locator("#export-go")).to_be_enabled(timeout=10000)
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    assert page.get_attribute("#export-summary", "aria-live") == "polite" and page.get_attribute("#export-result", "aria-live") == "polite"
    for sel in ("#export-go", "#export-check"):
        box = page.locator(sel).bounding_box()
        assert box["x"] >= 0 and box["x"] + box["width"] <= 320 and box["height"] >= 40, sel
    page.evaluate("document.getElementById('exportcard').scrollIntoView({block: 'center'})")
    shot(page, "52-export-narrow-dark")
    assert problems == [], problems
    ctx.close()


def test_the_manifest_records_where_each_clip_came_from(approving, server):
    page, _ctx, _, take = approving
    open_card(page)
    expect(page.locator("#export-go")).to_be_enabled(timeout=10000)
    page.locator("#export-go").click()
    page.locator("#confirm-ok").click()
    expect(page.locator("#export-result")).to_contain_text("Wrote", timeout=15000)
    manifest = json.loads((folder(server) / "manifest.json").read_text())["items"]
    item = manifest[f"{take}_s002"]
    assert (item["take"], item["seg"], item["start"], item["end"]) == (take, "s002", 2.0, 3.6) and item["text"] == "I paid twenty dollars."
