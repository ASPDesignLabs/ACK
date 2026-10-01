"""The text that was read: proposals from it, spoken-form choices, the reference card, and listening again with hints."""
import json
import time

import pytest

pytest.importorskip("playwright")
from playwright.sync_api import expect  # noqa: E402

from conftest import needs_ffmpeg  # noqa: E402
from test_review_ui import (  # noqa: E402,F401  (fixtures and helpers shared with the other review tests)
    edit, http, new_page, review, saved, seed_take, shot, status_of, take, explain_failure,
)

pytestmark = needs_ffmpeg

REFERENCE = ("The archivist keeper cataloged everything. She paid $20 for three apples. "
             "Dr. Smith sailed to the old harbour. And then she left the building quietly.")
PIECES = [
    ("s001", 0.2, 1.8, "the archive keeper cataloged everything", [], ()),
    ("s002", 2.0, 3.6, "she paid 20 dollars for three apples", ["has_digits"], ()),
    ("s003", 3.8, 5.4, "um honestly that was a pretty good one I think", [], ()),
    ("s004", 5.6, 7.2, "dr smith sailed to the old harbor", [], ()),
    ("s005", 7.4, 8.8, "and then she left the building quietly", [], ()),
]


@pytest.fixture
def read_take(server, tmp_path):
    return seed_take(server, tmp_path, PIECES, REFERENCE)


@pytest.fixture
def reading(browser, server, read_take, request, tmp_path):
    page, ctx, problems = new_page(browser, server, f"/review/{read_take}")
    expect(page.locator("#piece-title")).to_have_text("Piece 1 of 5")
    yield page, ctx, problems, read_take
    if getattr(request.node, "rep_call", None) is not None and request.node.rep_call.failed:
        explain_failure(page, problems, tmp_path)
    ctx.close()


def texts(server, take_id):
    return {s["id"]: s["text"] for s in edit(server, take_id)["segments"]}


def goto_piece(page, n):
    page.select_option("#filter", "all")
    page.locator("#list .pitem").nth(n).click()


# ------------------------------------------------------------------ the reference's wording for a piece
def test_a_close_match_shows_the_reference_wording_with_what_would_change(reading, server):
    page, _ctx, problems, take = reading
    box = page.locator("#p-ref")
    expect(box).to_be_visible(timeout=8000)
    expect(page.locator("#p-ref-text")).to_have_text("The archivist keeper cataloged everything.")
    assert page.locator("#p-ref-text mark").all_inner_texts() == ["archivist"]
    expect(page.locator("#p-ref-changes")).to_contain_text("“archive” would become “archivist”")
    expect(page.locator("#p-ref-changes")).to_contain_text("capital letters or punctuation")
    assert page.input_value("#p-text") == "the archive keeper cataloged everything"      # nothing has changed yet
    assert texts(server, take)["s001"] == "the archive keeper cataloged everything"
    shot(page, "40-reference-suggestion")
    assert problems == [], problems


def test_using_the_reference_wording_is_one_undoable_step_and_keeps_the_timing_of_untouched_words(reading, server):
    page, _ctx, _, take = reading
    expect(page.locator("#p-ref")).to_be_visible(timeout=8000)
    page.locator("#ref-use").click()
    expect(page.locator("#p-text")).to_have_value("The archivist keeper cataloged everything.")
    expect(page.locator("#lastchange")).to_contain_text("Used the reference wording")
    expect(page.locator("#p-ref")).to_be_hidden()                       # it now matches, so there is nothing left to offer
    saved(page)
    seg = {s["id"]: s for s in edit(server, take)["segments"]}["s001"]
    assert seg["text"] == "The archivist keeper cataloged everything."
    old = [w for w in seg["words"] if w["w"] in ("keeper", "cataloged")]
    assert all("ed" not in w or w["w"] == "everything." for w in old if w["w"] == "keeper")   # untouched words stay untouched
    assert status_of(server, take)["s001"] == "pending"                                       # using it does not approve anything
    page.locator("#undo").click()
    expect(page.locator("#p-text")).to_have_value("the archive keeper cataloged everything")
    saved(page)
    assert texts(server, take)["s001"] == "the archive keeper cataloged everything"
    expect(page.locator("#p-ref")).to_be_visible(timeout=8000)           # offered again, as before


def test_keep_what_i_have_hides_the_proposal_and_it_stays_hidden_after_a_reload(reading, server):
    page, _ctx, _, take = reading
    expect(page.locator("#p-ref")).to_be_visible(timeout=8000)
    page.locator("#ref-skip").click()
    expect(page.locator("#p-ref")).to_be_hidden()
    page.reload()
    expect(page.locator("#p-text")).to_have_value("the archive keeper cataloged everything")
    page.wait_for_timeout(1500)                                           # long enough for the comparison to have finished
    expect(page.locator("#p-ref")).to_be_hidden()
    assert texts(server, take)["s001"] == "the archive keeper cataloged everything"


def test_free_speech_is_not_matched_to_the_reference(reading):
    page, *_ = reading
    expect(page.locator("#p-ref")).to_be_visible(timeout=8000)           # the comparison is done once piece 1 shows
    goto_piece(page, 2)
    expect(page.locator("#p-text")).to_have_value("um honestly that was a pretty good one I think")
    page.wait_for_timeout(300)
    expect(page.locator("#p-ref")).to_be_hidden()


def test_a_proposal_made_for_old_text_is_never_applied_over_new_typing(reading, server):
    page, _ctx, _, take = reading
    expect(page.locator("#p-ref")).to_be_visible(timeout=8000)
    page.locator("#p-text").fill("the archive keeper cataloged everything today")
    page.locator("#take-title").click()                                    # leaves the box, which ends the stretch of typing
    expect(page.locator("#p-ref")).to_be_hidden()                          # the old proposal is withdrawn at once
    expect(page.locator("#p-ref")).to_be_visible(timeout=8000)             # and a fresh one is made for what is there now
    text = page.locator("#p-ref-text").inner_text()
    assert text.startswith("The archivist keeper cataloged everything") and text.endswith("today")
    assert page.locator("#p-ref-text .kept").all_inner_texts() == ["today"]   # the extra word was said, so it stays


# ------------------------------------------------------------------ numbers, symbols and abbreviations
def test_spoken_form_choices_replace_one_token_and_clear_the_warning(reading, server):
    page, _ctx, problems, take = reading
    goto_piece(page, 1)
    group = page.locator("#p-spoken li[aria-label='Ways to say 20']")
    expect(group).to_be_visible()
    assert group.locator("button").first.inner_text().startswith("twenty")
    expect(page.locator("#p-flags")).to_contain_text("Contains numbers")
    shot(page, "41-spoken")
    group.locator("button", has_text="twenty").first.click()
    expect(page.locator("#p-text")).to_have_value("she paid twenty dollars for three apples")
    expect(page.locator("#p-flags")).to_be_hidden()
    expect(page.locator("#p-spoken")).to_be_hidden()
    saved(page)
    assert texts(server, take)["s002"] == "she paid twenty dollars for three apples"
    page.locator("#undo").click()
    expect(page.locator("#p-text")).to_have_value("she paid 20 dollars for three apples")
    assert problems == [], problems


def test_an_abbreviation_offers_each_meaning_and_you_choose(reading):
    page, *_ = reading
    goto_piece(page, 3)
    group = page.locator("#p-spoken li[aria-label='Ways to say dr']")
    expect(group.locator("button")).to_have_count(2)
    assert [b.inner_text().split("\n")[0] for b in group.locator("button").all()] == ["Doctor", "Drive"]
    group.locator("button", has_text="Doctor").click()
    expect(page.locator("#p-text")).to_have_value("Doctor smith sailed to the old harbor")


def test_spoken_form_buttons_have_names_that_say_what_they_do(reading):
    page, *_ = reading
    goto_piece(page, 1)
    expect(page.locator("#p-spoken")).to_be_visible()
    for b in page.locator("#p-spoken button").all():
        assert b.inner_text().strip()
    assert page.locator("#p-spoken li").first.get_attribute("role") == "group"


# ------------------------------------------------------------------ the reference card
def test_the_card_summarises_how_the_pieces_line_up_and_applies_close_matches_after_confirming(reading, server):
    page, _ctx, problems, take = reading
    page.locator("#refcard > summary").click()
    expect(page.locator("#ref-summary")).to_contain_text("0 pieces match it exactly", timeout=8000)
    expect(page.locator("#ref-summary")).to_contain_text("2 differ only in capital letters or punctuation, 2 differ in wording, and 1 don't line up")
    expect(page.locator("#ref-bulk")).to_have_text("Use its wording on 4 close matches")
    assert page.input_value("#ref-edit") == REFERENCE
    page.evaluate("document.getElementById('ref-bulk').scrollIntoView({block: 'center'})")
    shot(page, "42-reference-card")
    before = texts(server, take)
    page.locator("#ref-bulk").click()
    expect(page.locator("#confirm-title")).to_have_text("Use the reference wording on 4 pieces?")
    page.locator("#confirm-cancel").click()
    assert texts(server, take) == before                                   # cancelled: nothing happened
    page.locator("#ref-bulk").click()
    page.locator("#confirm-ok").click()
    expect(page.locator("#ref-bulk")).to_be_disabled(timeout=8000)
    saved(page)
    got = texts(server, take)
    assert got["s001"] == "The archivist keeper cataloged everything."
    assert got["s002"] == "She paid 20 dollars for three apples."        # the digits stay: the reference's "$20" does not come over
    assert got["s003"] == before["s003"]                                    # free speech untouched
    assert got["s004"] == "Dr. Smith sailed to the old harbour."
    assert got["s005"] == "And then she left the building quietly."
    assert set(status_of(server, take).values()) == {"pending"}             # nothing was approved
    page.locator("#undo").click()                                           # all four, in one step
    saved(page)
    assert texts(server, take) == before
    assert problems == [], problems


def test_replacing_the_reference_asks_first_keeps_the_old_text_and_changes_the_proposals(reading, server):
    page, _ctx, _, take = reading
    page.locator("#refcard > summary").click()
    expect(page.locator("#ref-save")).to_be_disabled()
    page.locator("#ref-edit").fill("The archive keeper cataloged everything. Nothing else was said.")
    expect(page.locator("#ref-save")).to_be_enabled()
    page.locator("#ref-save").click()
    expect(page.locator("#confirm-title")).to_have_text("Replace the reference text?")
    page.locator("#confirm-cancel").click()
    assert http(server, f"/api/takes/{take}")["reference_text"] == REFERENCE   # cancelled: still the old text
    page.locator("#ref-save").click()
    page.locator("#confirm-ok").click()
    expect(page.locator("#ref-save-hint")).to_have_text("Saved. The text it replaced, if any, is kept on your PC.")
    assert http(server, f"/api/takes/{take}")["reference_text"].startswith("The archive keeper")
    kept = list((server["out"] / "_freeform").rglob(f"{take}/reference_history/*.txt"))
    assert len(kept) == 1 and kept[0].read_text() == REFERENCE               # the old text is on disk
    expect(page.locator("#ref-save")).to_be_disabled()
    # piece 1 now matches the new reference's capital and full stop only
    expect(page.locator("#p-ref-text")).to_have_text("The archive keeper cataloged everything.", timeout=8000)
    expect(page.locator("#p-ref-changes")).not_to_contain_text("would become")


def test_a_recording_without_reference_text_says_so_and_a_pasted_one_starts_working(browser, server, take):
    page, ctx, _ = new_page(browser, server, f"/review/{take}")
    expect(page.locator("#piece-title")).to_have_text("Piece 1 of 5")
    page.locator("#refcard > summary").click()
    expect(page.locator("#ref-summary")).to_contain_text("No reference text is saved")
    expect(page.locator("#ref-bulk")).to_be_disabled()
    expect(page.locator("#p-ref")).to_be_hidden()
    page.locator("#ref-edit").fill("Hello there, my friend. I paid twenty dollars for it.")
    page.locator("#ref-save").click()                                       # nothing to replace, so no question
    expect(page.locator("#ref-save-hint")).to_have_text("Saved. The text it replaced, if any, is kept on your PC.")
    expect(page.locator("#p-ref")).to_be_visible(timeout=8000)
    expect(page.locator("#p-ref-text")).to_have_text("Hello there, my friend.")
    ctx.close()


# ------------------------------------------------------------------ listening again with hints
def test_listening_again_is_prefilled_from_the_reference_and_asks_before_doing_anything(reading, server):
    page, _ctx, _, take = reading
    page.locator("#refcard > summary").click()
    page.locator("#hints > summary").click()
    assert "Smith" in page.input_value("#hint-words")
    assert page.input_value("#hint-prompt").startswith("The archivist keeper cataloged everything.")
    sent = []
    page.route("**/api/takes/*/transcribe", lambda route: (sent.append(json.loads(route.request.post_data)), route.continue_()))
    page.locator("#hint-words").fill("Smith, Archivist")
    page.locator("#retranscribe").scroll_into_view_if_needed()
    page.locator("#retranscribe").click()
    expect(page.locator("#confirm-title")).to_have_text("Listen to the whole recording again?")
    expect(page.locator("#confirm-body")).to_contain_text("0 approved, 0 dropped, 0 with text you changed")
    shot(page, "43-listen-again-confirm")
    page.locator("#confirm-cancel").click()
    page.wait_for_timeout(300)
    assert sent == [] and http(server, f"/api/takes/{take}")["status"] == "ready"   # cancelled: nothing started
    assert not [h for h in http(server, f"/api/takes/{take}/edit/history")["history"] if "pre-regen" in h["name"]]
    rev = edit(server, take)["rev"]
    page.locator("#retranscribe").click()
    page.locator("#confirm-ok").click()
    page.wait_for_url("**/review", timeout=15000)
    assert sent and sent[0]["hotwords"] == "Smith, Archivist" and sent[0]["regenerate"] is True and sent[0]["force"] is True
    for _ in range(300):
        if http(server, f"/api/takes/{take}")["status"] == "ready" and edit(server, take)["rev"] > rev:
            break
        time.sleep(0.1)
    else:
        pytest.fail("the recording was never transcribed again")
    names = [h["name"] for h in http(server, f"/api/takes/{take}/edit/history")["history"]]
    assert any("pre-regen" in n for n in names)                             # what was there before is kept


def test_listening_again_is_refused_while_changes_are_unsaved_and_says_how_to_fix_it(reading):
    page, ctx, _, = reading[0], reading[1], None
    page.route("**/api/takes/*/edit", lambda route: route.abort() if route.request.method == "PUT" else route.continue_())
    page.locator("#approve").click()
    expect(page.locator("#savestate")).to_contain_text("Can't reach your PC", timeout=8000)
    page.locator("#refcard > summary").click()
    page.locator("#hints > summary").click()
    page.locator("#retranscribe").click()
    page.locator("#confirm-ok").click()
    expect(page.locator("#notice")).to_contain_text("haven't reached your PC yet", timeout=15000)
    assert "/review/" in page.url                                           # still here: nothing was started


def test_the_new_controls_fit_a_narrow_phone_and_look_right_in_the_dark(browser, server, read_take):
    page, ctx, problems = new_page(browser, server, f"/review/{read_take}", viewport={"width": 320, "height": 640}, color_scheme="dark")
    expect(page.locator("#p-ref")).to_be_visible(timeout=8000)
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    page.evaluate("document.getElementById('p-ref').scrollIntoView({block: 'center'})")
    shot(page, "44-narrow-dark-reference")
    page.locator("#refcard > summary").click()
    page.locator("#hints > summary").click()
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    for sel in ("#ref-use", "#ref-skip", "#ref-bulk", "#ref-save", "#retranscribe"):
        box = page.locator(sel).bounding_box()
        assert box["x"] >= 0 and box["x"] + box["width"] <= 320 and box["height"] >= 40, sel
    assert problems == [], problems
    ctx.close()
