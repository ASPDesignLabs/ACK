# SPDX-License-Identifier: GPL-3.0-or-later
"""The browser side of importing from ACK, at phone size against the real server: bring a package in, look inside it, add it,
and see the phone's notes on a piece."""
import json
import time
import urllib.request

import pytest

pytest.importorskip("playwright")
from playwright.sync_api import expect  # noqa: E402

from ack_package_builder import ClipSpec, PackageBuilder  # noqa: E402
from conftest import needs_ffmpeg  # noqa: E402
from test_review_ui import explain_failure, http, new_page, shot  # noqa: E402,F401

pytestmark = needs_ffmpeg

CARD = "The tide came in slowly."
_serial = [0]


def build(tmp_path, name="ack-training-1.zip", damaged=False):
    """A package whose session ids are new to the (shared) server, so one test's import is never another's 'already added'."""
    _serial[0] += 1
    n = _serial[0]
    b = PackageBuilder()
    b.script_session([ClipSpec(CARD, speech=2.5), ClipSpec("We walked along the shore.", speech=3.0)], label="closet test",
                     sid=f"s20261002-19{n:02d}00-{0xb000 + n:04x}")
    b.free_session([(0.4, 3.0), (0.5, 7.0)], topic="morning", sid=f"s20261002-19{n:02d}01-{0xc000 + n:04x}")
    path = b.write(tmp_path / name)
    if damaged:
        data = bytearray(path.read_bytes())
        data[len(data) // 2] ^= 0xFF
        path.write_bytes(bytes(data))
    return path, b


def from_session(server, b):
    ids = {s["id"] for s in b.sessions}
    return [t for t in http(server, "/api/takes")["takes"] if t["client"].get("ack_session") in ids]


def put_in_incoming(server, path, name=None):
    """Hands a package to the server the way the page does: in pieces, over HTTP."""
    data = path.read_bytes()
    name = name or path.name
    base = f"/api/ack/incoming/{name}"
    req = urllib.request.Request(server["base"] + f"{base}?offset=0", data=data, method="PUT")
    urllib.request.urlopen(req, timeout=30).read()
    http(server, f"{base}/done", "POST", {"size": len(data)})


def import_all(server, name):
    done = http(server, "/api/ack/import", "POST", {"name": name})
    ids = [c["take_id"] for c in done["created"]]
    for tid in ids:
        for _ in range(300):
            doc = http(server, f"/api/takes/{tid}")
            if doc["status"] in ("ready", "error"):
                break
            time.sleep(0.1)
        assert doc["status"] == "ready", doc.get("error")
    return done["created"]


@pytest.fixture
def page_on(browser, server, request, tmp_path):
    opened = []

    def open_page(path):
        page, ctx, problems = new_page(browser, server, path)
        opened.append((page, ctx, problems))
        return page, problems
    yield open_page
    for page, ctx, problems in opened:
        if getattr(request.node, "rep_call", None) is not None and request.node.rep_call.failed:
            explain_failure(page, problems, tmp_path)
        ctx.close()


def test_a_package_is_chosen_looked_inside_and_added(page_on, server, tmp_path):
    path, b = build(tmp_path, "ack-training-ui-1.zip")
    page, problems = page_on("/review")
    page.locator("#ackcard > summary").click()
    expect(page.locator("#ack-empty")).to_be_visible()
    page.locator("#ack-file").set_input_files(str(path))
    expect(page.locator("#ack-upload")).to_contain_text("ack-training-ui-1.zip is on your PC", timeout=15000)
    expect(page.locator("#ack-list")).to_contain_text("ack-training-ui-1.zip")
    expect(page.locator("#ack-plan")).to_be_visible(timeout=15000)
    expect(page.locator("#ack-plan-summary")).to_contain_text("2 sessions")
    expect(page.locator("#ack-plan-summary")).to_contain_text("checked against its checksum")
    expect(page.locator("#ack-plan-sessions")).to_contain_text("closet test · 2 clips")
    expect(page.locator("#ack-plan-sessions")).to_contain_text("free speech")
    expect(page.locator("#ack-go")).to_have_text("Add 2 recordings")
    expect(page.locator("#ack-go")).to_be_enabled()
    page.locator("#ack-plan").scroll_into_view_if_needed()
    shot(page, "60-ack-plan")
    assert from_session(server, b) == []                                  # looking inside added nothing

    page.locator("#ack-go").click()
    expect(page.locator("#confirm-title")).to_have_text("Add these recordings?")
    expect(page.locator("#confirm-body")).to_contain_text("your package file stays exactly as it is")
    page.locator("#confirm-ok").click()
    expect(page.locator("#ack-result")).to_contain_text("Added 2 recordings", timeout=15000)
    assert len(from_session(server, b)) == 2
    for t in from_session(server, b):                                     # they are processed by the same pipeline as any recording
        for _ in range(300):
            if http(server, f"/api/takes/{t['id']}")["status"] in ("ready", "error"):
                break
            time.sleep(0.1)
        assert http(server, f"/api/takes/{t['id']}")["status"] == "ready"
    assert problems == [], problems


def test_a_damaged_package_is_explained_and_cannot_be_added(page_on, server, tmp_path):
    path, b = build(tmp_path, "ack-training-ui-bad.zip", damaged=True)
    page, problems = page_on("/review")
    page.locator("#ackcard > summary").click()
    page.locator("#ack-file").set_input_files(str(path))
    expect(page.locator("#ack-result")).to_contain_text("Nothing was imported.", timeout=15000)
    expect(page.locator("#ack-plan")).to_be_hidden()
    expect(page.locator("#ack-list")).to_contain_text("ack-training-ui-bad.zip")
    shot(page, "61-ack-damaged")
    assert from_session(server, b) == []


def test_a_package_already_added_says_so_and_offers_nothing(page_on, server, tmp_path):
    path, _ = build(tmp_path, "ack-training-ui-again.zip")
    put_in_incoming(server, path)
    import_all(server, path.name)
    page, _ = page_on("/review")
    page.locator("#ackcard > summary").click()
    page.get_by_role("button", name="Look inside ack-training-ui-again.zip").click()
    expect(page.locator("#ack-plan-sessions")).to_contain_text("already added, skipped", timeout=15000)
    expect(page.locator("#ack-plan-room")).to_have_text("Everything in this package is already here.")
    expect(page.locator("#ack-go")).to_be_disabled()


def test_a_piece_shows_the_card_it_was_read_from_and_can_take_its_words(page_on, server, tmp_path):
    path, b = build(tmp_path, "ack-training-ui-card.zip")
    put_in_incoming(server, path)
    created = import_all(server, path.name)
    script_id = next(c["take_id"] for c in created if c["session"] == b.sessions[0]["id"])
    page, problems = page_on(f"/review/{script_id}")
    expect(page.locator("#p-ack")).to_be_visible(timeout=15000)
    expect(page.locator("#p-ack-text")).to_have_text(CARD)
    expect(page.locator("#p-ack-facts")).to_contain_text("Card 1")
    expect(page.locator("#p-ack-facts")).to_contain_text("loudest point")
    expect(page.locator("#ack-use")).to_be_hidden()                     # the words already match the card
    page.locator("#p-ack").scroll_into_view_if_needed()
    page.evaluate("window.scrollBy(0, 260)")                     # clear of the fixed action bar
    shot(page, "62-ack-piece")

    page.locator("#p-text").fill("some completely different words")
    expect(page.locator("#ack-use")).to_be_visible(timeout=5000)
    page.locator("#ack-use").click()
    expect(page.locator("#p-text")).to_have_value(CARD)
    expect(page.locator("#ack-use")).to_be_hidden()
    assert problems == [], problems


def test_a_recording_that_did_not_come_from_ack_has_no_such_panel(page_on, server, tmp_path):
    from test_review_ui import seed_take
    plain = seed_take(server, tmp_path)
    page, _ = page_on(f"/review/{plain}")
    expect(page.locator("#piece-title")).to_be_visible(timeout=15000)
    expect(page.locator("#p-ack")).to_be_hidden()


def test_a_disk_too_full_to_take_the_package_is_said_plainly_and_adding_is_disabled(page_on, server, tmp_path):
    path, _ = build(tmp_path, "ack-training-ui-full.zip")
    put_in_incoming(server, path)

    def squeeze(route):
        response = route.fetch()
        body = response.json()
        body.update(enough_room=False, free_mb=120, need_mb=900)
        route.fulfill(response=response, json=body)
    page, _ = page_on("/review")
    page.route("**/api/ack/check", squeeze)
    page.locator("#ackcard > summary").click()
    page.get_by_role("button", name="Look inside ack-training-ui-full.zip").click()
    expect(page.locator("#ack-plan-room")).to_contain_text("Not enough room", timeout=15000)
    expect(page.locator("#ack-plan-room")).to_contain_text("only 120 MB is free")
    expect(page.locator("#ack-go")).to_be_disabled()


def test_a_card_that_became_several_pieces_is_shown_but_cannot_overwrite_just_one(page_on, server, tmp_path):
    path, b = build(tmp_path, "ack-training-ui-many.zip")
    put_in_incoming(server, path)
    created = import_all(server, path.name)
    script_id = next(c["take_id"] for c in created if c["session"] == b.sessions[0]["id"])

    def one_clip_covers_everything(route):
        response = route.fetch()
        body = response.json()
        body["notes"]["clips"][0].update(start_s=0.0, end_s=999.0, text="A card whose words are not what the piece says.")
        route.fulfill(response=response, json=body)
    page, _ = page_on("/review/placeholder")
    page.route(f"**/api/takes/{script_id}/ack", one_clip_covers_everything)
    page.goto(server["base"] + f"/review/{script_id}")
    expect(page.locator("#p-ack")).to_be_visible(timeout=15000)
    expect(page.locator("#p-ack-text")).to_have_text("A card whose words are not what the piece says.")
    expect(page.locator("#p-ack-facts")).to_contain_text("this card became 2 pieces")
    expect(page.locator("#ack-use")).to_be_hidden()                  # the words differ, but one piece must not take the whole card's words


def test_when_the_words_differ_from_a_single_piece_the_button_is_offered(page_on, server, tmp_path):
    path, b = build(tmp_path, "ack-training-ui-differ.zip")
    put_in_incoming(server, path)
    created = import_all(server, path.name)
    script_id = next(c["take_id"] for c in created if c["session"] == b.sessions[0]["id"])

    def different_card(route):
        response = route.fetch()
        body = response.json()
        body["notes"]["clips"][0]["text"] = "A different card sentence entirely."
        route.fulfill(response=response, json=body)
    page, _ = page_on("/review/placeholder")
    page.route(f"**/api/takes/{script_id}/ack", different_card)
    page.goto(server["base"] + f"/review/{script_id}")
    expect(page.locator("#ack-use")).to_be_visible(timeout=15000)
    page.locator("#ack-use").click()
    expect(page.locator("#p-text")).to_have_value("A different card sentence entirely.")
