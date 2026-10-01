"""Drives the review screens in headless Chromium at phone size, against the real server and a real (generated) recording."""
import json
import os
import time
import urllib.request
from pathlib import Path

import pytest

pytest.importorskip("playwright")
from playwright.sync_api import expect  # noqa: E402

from conftest import make_live_webm, make_wav, needs_ffmpeg  # noqa: E402

pytestmark = needs_ffmpeg
SHOTS = os.environ.get("FS_SHOTS")

# id, start, end, text, flags, indexes of words the recognizer was unsure about
PIECES = [
    ("s001", 0.2, 1.8, "Hello there my friend.", [], ()),
    ("s002", 2.0, 3.6, "I paid twenty dollars.", [], ()),
    ("s003", 3.8, 5.4, "Shaky word here.", ["low_confidence"], (0,)),
    ("s004", 5.6, 7.2, "It cost 20 dollars.", ["has_digits"], ()),
    ("s005", 7.4, 8.8, "And that is all.", [], ()),
]
SAVED = "All changes are saved on your PC."


def http(server, path, method="GET", payload=None, raw=None):
    data, headers = raw, {}
    if payload is not None:
        data, headers = json.dumps(payload).encode(), {"content-type": "application/json"}
    req = urllib.request.Request(server["base"] + path, data=data, method=method, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as r:
        body = r.read()
    return json.loads(body) if body else None


def make_words(text, start, end, low):
    toks = text.split()
    step = (end - start - 0.2) / len(toks)
    return [{"w": tok, "s": round(start + 0.1 + i * step, 3), "e": round(start + 0.1 + i * step + step * 0.9, 3),
             "p": 0.3 if i in low else 0.95} for i, tok in enumerate(toks)]


@pytest.fixture
def take(server, tmp_path):
    """A finished recording whose pieces are known, so the tests can check exactly what the screens do to them."""
    wav = make_wav(tmp_path / "in.wav", 9.5, [(p[1], p[2]) for p in PIECES])
    blob = make_live_webm(wav, tmp_path / "in.webm").read_bytes()
    t = http(server, "/api/takes", "POST", {"label": "ui test"})
    http(server, f"/api/takes/{t['id']}/chunks/0", "PUT", raw=blob)
    http(server, f"/api/takes/{t['id']}/finish", "POST", raw=b"")
    for _ in range(300):
        if http(server, f"/api/takes/{t['id']}")["status"] == "ready":
            break
        time.sleep(0.1)
    else:
        pytest.fail("take never became ready")
    doc = http(server, f"/api/takes/{t['id']}/edit")
    segs = [{"id": i, "start": a, "end": b, "text": text, "words": make_words(text, a, b, low), "status": "pending",
             "tags": [], "note": "", "flags": flags, "auto": None} for i, a, b, text, flags, low in PIECES]
    http(server, f"/api/takes/{t['id']}/edit", "PUT", {"rev": doc["rev"], "segments": segs})
    return t["id"]


def new_page(browser, server, path, **ctx_args):
    ctx = browser.new_context(**{"viewport": {"width": 412, "height": 915}, "device_scale_factor": 2, "is_mobile": True,
                                 "has_touch": True, **ctx_args})
    page = ctx.new_page()
    problems = []
    page.on("console", lambda m: problems.append(m.text) if m.type in ("error", "warning") else None)
    page.on("pageerror", lambda e: problems.append(str(e)))
    page.on("dialog", lambda d: d.accept())  # the browser's own "leave this page?" prompt
    page.goto(server["base"] + path)
    return page, ctx, problems


def explain_failure(page, problems, directory):
    """When a browser test fails, say what the page looked like (these are timing-sensitive, so the log must be enough)."""
    try:
        shot_path = Path(directory) / "failure.png"
        page.screenshot(path=str(shot_path))
        state = page.evaluate("""() => ({
            url: location.href, scrollY, saveState: document.getElementById('savestate')?.innerText,
            hint: document.getElementById('p-hint')?.innerText, draftShown: !document.getElementById('draft')?.hidden,
            piece: document.getElementById('piece-title')?.innerText, active: document.activeElement?.id || document.activeElement?.tagName,
            dialogOpen: document.getElementById('confirm')?.open, barHidden: document.getElementById('bar')?.hidden })""")
        print(f"\n--- page state at failure ---\n{json.dumps(state, indent=1)}\nconsole problems: {problems}\nscreenshot: {shot_path}")
    except Exception as err:  # the page may be gone; never hide the real failure behind this one
        print(f"(could not describe the page: {err})")


@pytest.fixture
def review(browser, server, take, request, tmp_path):
    page, ctx, problems = new_page(browser, server, f"/review/{take}")
    expect(page.locator("#piece-title")).to_have_text("Piece 1 of 5")
    yield page, ctx, problems, take
    if getattr(request.node, "rep_call", None) is not None and request.node.rep_call.failed:
        explain_failure(page, problems, tmp_path)
    ctx.close()


def shot(page, name):
    if SHOTS:
        Path(SHOTS).mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(Path(SHOTS) / f"{name}.png"))


def saved(page):
    expect(page.locator("#savestate")).to_have_text(SAVED)


def edit(server, take):
    return http(server, f"/api/takes/{take}/edit")


def status_of(server, take):
    return {s["id"]: s["status"] for s in edit(server, take)["segments"]}


# ------------------------------------------------------------------ inbox
def test_inbox_lists_ready_recordings_and_opens_one(browser, server, take):
    page, ctx, problems = new_page(browser, server, "/review")
    expect(page.locator("#inbox-list .take").first).to_be_visible()
    card = page.locator("#inbox-list .take", has_text="5 pieces").first
    expect(card).to_contain_text("0 approved")
    expect(card).to_contain_text("5 to review")
    expect(card.locator(".chip")).to_have_text("Ready to review")
    shot(page, "10-inbox")
    page.locator(f"a[href='/review/{take}']").click()
    expect(page.locator("#piece-title")).to_have_text("Piece 1 of 5")
    assert problems == [], problems
    ctx.close()


def test_unknown_or_unfinished_recordings_say_so_plainly(browser, server):
    page, ctx, _ = new_page(browser, server, "/review/t20200101-000000-abcd")
    expect(page.locator("#notice")).to_contain_text("wasn't found")
    assert page.locator("#work").is_hidden()
    ctx.close()


# ------------------------------------------------------------------ the piece screen
def test_piece_screen_is_usable_at_phone_size_and_accessible(review, server):
    page, ctx, problems, take = review
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    expect(page.locator("#p-status")).to_have_text("To review")
    assert page.locator("#p-words button").all_inner_texts() == ["Hello", "there", "my", "friend."]
    assert page.input_value("#p-text") == "Hello there my friend."
    # the three main controls sit in the bottom thumb zone and are comfortably big
    for sel in ("#drop", "#play", "#approve"):
        box = page.locator(sel).bounding_box()
        assert box["y"] > 915 * 0.8 and box["height"] >= 48 and box["width"] >= 56, sel
    for btn in page.locator("button:visible").all():
        assert btn.inner_text().strip() or btn.get_attribute("aria-label"), "every button needs a name"
    assert page.evaluate("[...document.querySelectorAll('[id]')].map(n => n.id).length === new Set([...document.querySelectorAll('[id]')].map(n => n.id)).size")
    assert page.locator("label[for='p-text']").count() == 1 and page.get_attribute("html", "lang") == "en"
    assert page.locator("main").count() == 1 and page.locator("#announce[aria-live='polite']").count() == 1
    shot(page, "11-piece")
    assert problems == [], problems  # includes any Content-Security-Policy violations


def test_a_phone_this_narrow_still_fits(browser, server, take):
    page, ctx, _ = new_page(browser, server, f"/review/{take}", viewport={"width": 320, "height": 640})
    expect(page.locator("#piece-title")).to_have_text("Piece 1 of 5")
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    box = page.locator("#approve").bounding_box()
    assert box["x"] >= 0 and box["x"] + box["width"] <= 320
    shot(page, "12-narrow")
    ctx.close()


def test_dark_mode_and_reduced_motion_render(browser, server, take):
    page, ctx, problems = new_page(browser, server, f"/review/{take}", color_scheme="dark", reduced_motion="reduce")
    expect(page.locator("#piece-title")).to_have_text("Piece 1 of 5")
    assert page.evaluate("getComputedStyle(document.body).backgroundColor") == "rgb(20, 24, 28)"
    page.locator("#p-words button").nth(1).click()
    expect(page.locator(".w.now")).to_be_visible()
    shot(page, "13-dark-playing")
    assert problems == [], problems
    ctx.close()


# ------------------------------------------------------------------ approving, dropping, undo
def test_approve_moves_on_saves_and_can_be_undone(review, server):
    page, _ctx, problems, take = review
    page.locator("#approve").click()
    expect(page.locator("#piece-title")).to_have_text("Piece 1 of 4")
    expect(page.locator("#p-text")).to_have_value("I paid twenty dollars.")
    expect(page.locator("#summary")).to_contain_text("1 approved")
    expect(page.locator("#lastchange")).to_have_text("Approved the piece at 00:00")
    saved(page)
    assert status_of(server, take)["s001"] == "approved"
    page.locator("#undo").click()
    expect(page.locator("#p-text")).to_have_value("Hello there my friend.")
    expect(page.locator("#lastchange")).to_contain_text("Undid: Approved")
    saved(page)
    assert status_of(server, take)["s001"] == "pending"
    page.locator("#redo").click()
    saved(page)
    assert status_of(server, take)["s001"] == "approved"
    assert problems == [], problems


def test_drop_and_restore_and_the_views_follow(review, server):
    page, _ctx, _, take = review
    page.locator("#drop").click()
    expect(page.locator("#filter option[value='dropped']")).to_have_text("Dropped (1)")
    page.select_option("#filter", "dropped")
    expect(page.locator("#piece-title")).to_have_text("Piece 1 of 1")
    expect(page.locator("#p-status")).to_have_text("Dropped")
    expect(page.locator("#drop")).to_have_text("Restore")
    page.locator("#drop").click()
    expect(page.locator("#piece-empty")).to_be_visible()  # nothing is dropped any more
    saved(page)
    assert set(status_of(server, take).values()) == {"pending"}
    shot(page, "14-empty-view")


def test_an_approved_piece_can_have_its_approval_taken_back(review, server):
    page, _ctx, _, take = review
    page.select_option("#filter", "all")
    page.locator("#approve").click()
    expect(page.locator("#piece-title")).to_have_text("Piece 2 of 5")
    page.locator("#prev").click()
    expect(page.locator("#p-status")).to_have_text("Approved")
    expect(page.locator("#approve")).to_have_text("Next piece")
    page.locator("#reset").click()
    expect(page.locator("#p-status")).to_have_text("To review")
    saved(page)
    assert status_of(server, take)["s001"] == "pending"


def test_a_piece_with_no_words_cannot_be_approved(review):
    page, *_ = review
    page.locator("#p-text").fill("")
    expect(page.locator("#approve")).to_be_disabled()
    expect(page.locator("#p-flags")).to_contain_text("No words in this piece")
    page.locator("#p-text").fill("Something.")
    expect(page.locator("#approve")).to_be_enabled()


# ------------------------------------------------------------------ editing text
def test_changing_a_word_keeps_the_timing_of_the_others_and_saves(review, server):
    page, _ctx, problems, take = review
    page.locator("#p-text").fill("Hello there my dear friend.")
    expect(page.locator("#p-words button")).to_have_count(5)
    saved(page)
    seg = {s["id"]: s for s in edit(server, take)["segments"]}["s001"]
    assert seg["text"] == "Hello there my dear friend."
    original = make_words("Hello there my friend.", 0.2, 1.8, ())
    for new, old in zip(seg["words"][:3], original[:3]):
        assert (new["s"], new["e"]) == (old["s"], old["e"])  # untouched words keep their timing
    assert seg["words"][3]["w"] == "dear" and seg["words"][3].get("ed") is True
    assert all(a["e"] <= b["s"] + 1e-6 for a, b in zip(seg["words"], seg["words"][1:]))
    # the whole stretch of typing is one step in the undo list, not one per letter
    page.locator("#approve").focus()
    page.locator("#undo").click()
    expect(page.locator("#p-text")).to_have_value("Hello there my friend.")
    assert problems == [], problems


def test_the_column_separator_and_line_breaks_cannot_get_into_the_text(review, server):
    page, _ctx, _, take = review
    page.locator("#p-text").fill("one|two\nthree")
    expect(page.locator("#p-hint")).to_contain_text("can't be used")
    assert "|" not in page.input_value("#p-text") and "\n" not in page.input_value("#p-text")
    saved(page)
    assert edit(server, take)["segments"][0]["text"] == "one two three"


def test_fixing_the_shaky_word_clears_its_warning(review, server):
    page, _ctx, _, take = review
    page.select_option("#filter", "warn")
    expect(page.locator("#piece-title")).to_have_text("Piece 1 of 2")
    expect(page.locator("#p-flags")).to_contain_text("hard to hear")
    expect(page.locator("#p-words button.low")).to_have_count(1)
    assert page.locator("#p-words button.low").get_attribute("aria-label") == "Shaky (unsure)"
    page.locator("#p-text").fill("Flaky word here.")  # the unsure word itself
    expect(page.locator("#p-flags")).to_be_hidden()
    expect(page.locator("#p-words button.low")).to_have_count(0)
    saved(page)


# ------------------------------------------------------------------ playing
def test_play_highlights_words_and_stops_at_the_end_of_the_piece(review):
    page, *_ = review
    page.locator("#play").click()
    expect(page.locator("#play")).to_have_text("Stop")
    expect(page.locator(".w.now")).to_be_visible()
    assert page.locator(".w.now").get_attribute("aria-current") == "true"
    expect(page.locator("#p-time")).to_contain_text("Playing")
    expect(page.locator("#play")).to_have_text("Play", timeout=6000)  # it stopped by itself
    t = page.evaluate("document.getElementById('audio').currentTime")
    assert 1.7 <= t <= 2.1, t  # at the end of piece 1 (1.8 s), not running on into the next
    assert page.locator(".w.now").count() == 0


def test_tapping_a_word_plays_from_that_word(review):
    page, *_ = review
    page.locator("#p-words button", has_text="friend.").click()
    expect(page.locator("#play")).to_have_text("Stop")
    t = page.evaluate("document.getElementById('audio').currentTime")
    start = make_words("Hello there my friend.", 0.2, 1.8, ())[3]["s"]
    assert start - 0.3 <= t <= start + 0.6, (t, start)


def test_moving_to_another_piece_stops_the_audio_and_can_autoplay(review):
    page, *_ = review
    page.locator("#play").click()
    expect(page.locator("#play")).to_have_text("Stop")
    page.locator("#next").click()
    page.wait_for_timeout(250)
    assert page.evaluate("document.getElementById('audio').paused")
    page.locator("#autoplay").check()
    page.locator("#next").click()
    expect(page.locator("#play")).to_have_text("Stop")
    page.reload()  # the choice is remembered
    expect(page.locator("#autoplay")).to_be_checked()


# ------------------------------------------------------------------ bulk approve
def test_bulk_approve_asks_first_leaves_flagged_pieces_alone_and_undoes(review, server):
    page, _ctx, _, take = review
    expect(page.locator("#bulk")).to_have_text("Approve all clean pieces (3)")
    page.locator("#bulk").click()
    dialog = page.locator("#confirm")
    expect(dialog).to_be_visible()
    expect(page.locator("#confirm-title")).to_have_text("Approve 3 pieces?")
    expect(dialog).to_contain_text("doesn't mean you checked them")
    shot(page, "15-confirm")
    page.locator("#confirm-cancel").click()
    expect(dialog).to_be_hidden()
    assert set(status_of(server, take).values()) == {"pending"}  # nothing happened
    page.locator("#bulk").click()
    page.locator("#confirm-ok").click()
    expect(page.locator("#bulk")).to_have_text("Approve all clean pieces (0)")  # the change has been made on screen...
    saved(page)                                                                   # ...and now it has reached the PC
    assert status_of(server, take) == {"s001": "approved", "s002": "approved", "s003": "pending", "s004": "pending", "s005": "approved"}
    page.locator("#undo").click()
    expect(page.locator("#bulk")).to_have_text("Approve all clean pieces (3)")
    saved(page)
    assert set(status_of(server, take).values()) == {"pending"}


def test_tagged_pieces_are_not_counted_as_clean(review, server):
    page, _ctx, _, take = review
    page.locator("#p-tags button", has_text="laugh").click()
    expect(page.locator("#p-tags button", has_text="laugh")).to_have_attribute("aria-pressed", "true")
    expect(page.locator("#bulk")).to_have_text("Approve all clean pieces (2)")
    saved(page)
    assert edit(server, take)["segments"][0]["tags"] == ["laugh"]


# ------------------------------------------------------------------ moving around
def test_views_next_to_check_and_the_piece_list(review):
    page, *_ = review
    page.locator("#approve").click()
    page.select_option("#filter", "all")
    expect(page.locator("#list li")).to_have_count(5)
    page.locator("#list .pitem").nth(3).click()
    expect(page.locator("#piece-title")).to_have_text("Piece 4 of 5")
    assert page.evaluate("document.activeElement.id") == "piece-title"
    expect(page.locator("#list .pitem[aria-current='true']")).to_have_count(1)
    page.locator("#next-check").click()
    expect(page.locator("#p-text")).to_have_value("And that is all.")
    page.locator("#next-check").click()  # nothing later is pending, so it wraps and says so
    expect(page.locator("#p-text")).to_have_value("I paid twenty dollars.")
    expect(page.locator("#p-hint")).to_contain_text("went back to the start")


def test_where_you_left_off_is_remembered(review, browser, server):
    page, ctx, _, take = review
    page.select_option("#filter", "all")
    page.locator("#list .pitem").nth(2).click()
    page.reload()
    expect(page.locator("#p-text")).to_have_value("Shaky word here.")


# ------------------------------------------------------------------ keyboard
def test_keyboard_shortcuts_and_the_switch_to_turn_them_off(review, server):
    page, _ctx, _, take = review
    page.locator("#take-title").click()
    page.keyboard.press("j")
    expect(page.locator("#p-text")).to_have_value("I paid twenty dollars.")
    page.keyboard.press("k")
    expect(page.locator("#p-text")).to_have_value("Hello there my friend.")
    page.keyboard.press("a")
    expect(page.locator("#p-text")).to_have_value("I paid twenty dollars.")
    page.keyboard.press("d")
    expect(page.locator("#p-text")).to_have_value("Shaky word here.")
    page.keyboard.press("Control+z")
    expect(page.locator("#p-text")).to_have_value("I paid twenty dollars.")  # undo takes you to what it changed
    page.keyboard.press("e")
    assert page.evaluate("document.activeElement.id") == "p-text"
    page.keyboard.type("ad")  # typing letters is typing, not shortcuts
    assert page.input_value("#p-text").endswith("ad")
    page.keyboard.press("Control+Enter")  # works while typing
    saved(page)
    assert status_of(server, take)["s002"] == "approved"
    page.locator("#take-title").click()
    page.locator("summary", has_text="Keyboard shortcuts").click()
    page.locator("#keys-on").uncheck()
    before = status_of(server, take)
    page.locator("#take-title").click()
    page.keyboard.press("a")
    page.keyboard.press("d")
    page.wait_for_timeout(900)
    assert status_of(server, take) == before  # shortcuts are off
    page.reload()
    page.locator("summary", has_text="Keyboard shortcuts").click()
    expect(page.locator("#keys-on")).not_to_be_checked()


def test_word_buttons_move_with_the_arrow_keys(review):
    page, *_ = review
    page.locator("#p-words button").first.focus()
    page.keyboard.press("ArrowRight")
    page.keyboard.press("ArrowRight")
    assert page.evaluate("document.activeElement.textContent") == "my"
    assert page.locator("#p-words button[tabindex='0']").count() == 1
    page.keyboard.press("End")
    assert page.evaluate("document.activeElement.textContent") == "friend."
    page.keyboard.press("Enter")
    expect(page.locator("#play")).to_have_text("Stop")


# ------------------------------------------------------------------ never losing work
def test_a_change_made_elsewhere_is_merged_and_neither_side_is_lost(review, server):
    page, _ctx, _, take = review
    doc = edit(server, take)
    segs = doc["segments"]
    segs[4]["text"] = "And that is all, friends."
    segs[4]["words"] = make_words(segs[4]["text"], 7.4, 8.8, ())
    http(server, f"/api/takes/{take}/edit", "PUT", {"rev": doc["rev"], "segments": segs})  # another device saves first
    page.locator("#approve").click()  # this page still holds the old revision
    saved(page)
    final = {s["id"]: s for s in edit(server, take)["segments"]}
    assert final["s001"]["status"] == "approved" and final["s005"]["text"] == "And that is all, friends."
    page.select_option("#filter", "all")
    expect(page.locator("#list .pitem").nth(4)).to_contain_text("friends.")  # the screen shows the merged result too


def test_edits_made_offline_are_kept_and_sent_when_the_pc_returns(review, server):
    page, ctx, _, take = review
    ctx.set_offline(True)
    page.locator("#approve").click()
    expect(page.locator("#savestate")).to_contain_text("Can't reach your PC", timeout=8000)
    expect(page.locator("#summary")).to_contain_text("1 approved")  # the screen carries on regardless
    shot(page, "16-offline")
    assert status_of(server, take)["s001"] == "pending"
    ctx.set_offline(False)
    saved(page)
    assert status_of(server, take)["s001"] == "approved"


def test_changes_that_never_reached_the_pc_are_offered_back_after_a_reload(review, browser, server):
    page, ctx, _, take = review
    page.route("**/api/takes/*/edit", lambda route: route.abort() if route.request.method == "PUT" else route.continue_())
    page.locator("#approve").click()
    expect(page.locator("#savestate")).to_contain_text("Can't reach your PC", timeout=8000)
    page.reload()
    page.unroute("**/api/takes/*/edit")
    banner = page.locator("#draft")
    expect(banner).to_be_visible()
    expect(page.locator("#draft-text")).to_contain_text("1 change from earlier never reached your PC")
    shot(page, "17-draft")
    page.locator("#approve").click()  # editing waits until the choice is made, so the saved copy can't be overwritten by accident
    expect(page.locator("#p-hint")).to_contain_text("Restore or Discard")
    assert status_of(server, take)["s001"] == "pending"
    page.locator("#draft-restore").click()
    expect(banner).to_be_hidden()
    expect(page.locator("#summary")).to_contain_text("1 approved")
    saved(page)
    assert status_of(server, take)["s001"] == "approved"
    # and the other choice leaves things exactly as the PC has them
    page.route("**/api/takes/*/edit", lambda route: route.abort() if route.request.method == "PUT" else route.continue_())
    page.locator("#approve").click()
    expect(page.locator("#savestate")).to_contain_text("Can't reach your PC", timeout=8000)
    page.reload()
    page.unroute("**/api/takes/*/edit")
    expect(banner).to_be_visible()
    page.locator("#draft-discard").click()
    expect(banner).to_be_hidden()
    page.reload()
    expect(page.locator("#piece-title")).to_be_visible()  # loaded again, so "hidden" below means "nothing to offer", not "not drawn yet"
    expect(banner).to_be_hidden()
    assert status_of(server, take)["s002"] == "pending"


def test_earlier_versions_can_be_restored_only_after_confirming(review, server):
    page, _ctx, _, take = review
    page.locator("#approve").click()
    saved(page)
    page.locator("#approve").click()
    saved(page)
    assert list(status_of(server, take).values()).count("approved") == 2
    page.locator("summary", has_text="Earlier versions").click()
    items = page.locator("#history-list .take")
    expect(items).to_have_count(3)  # the original, and what each save replaced
    oldest = items.last
    expect(oldest).to_contain_text("0 approved")
    shot(page, "18-history")
    oldest.locator("button").click()
    expect(page.locator("#confirm-title")).to_have_text("Go back to this version?")
    page.locator("#confirm-cancel").click()
    assert list(status_of(server, take).values()).count("approved") == 2  # cancelled: nothing changed
    oldest.locator("button").click()
    page.locator("#confirm-ok").click()
    expect(page.locator("#summary")).to_contain_text("0 approved")
    assert set(status_of(server, take).values()) == {"pending"}
    expect(page.locator("#history-list .take", has_text="kept before a restore")).to_have_count(1)  # the version just left is not lost
    expect(page.locator("#undo")).to_be_disabled()
    page.locator("#history-list .take", has_text="kept before a restore").locator("button").click()
    page.locator("#confirm-ok").click()
    expect(page.locator("#summary")).to_contain_text("2 approved")


def test_a_refused_save_is_explained_and_can_be_retried(review, server):
    page, _ctx, _, take = review
    page.route("**/api/takes/*/edit", lambda route: route.fulfill(status=400, content_type="application/json",
               body=json.dumps({"error": "invalid edit", "details": ["segment 1: shorter than 0.05s"]})) if route.request.method == "PUT" else route.continue_())
    page.locator("#approve").click()
    expect(page.locator("#savestate")).to_contain_text("refused the last save: segment 1")
    page.unroute("**/api/takes/*/edit")
    page.locator("#savestate button", has_text="Try saving again").click()
    saved(page)
    assert status_of(server, take)["s001"] == "approved"
