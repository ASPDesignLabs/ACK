# SPDX-License-Identifier: GPL-3.0-or-later
"""Cut points, waveform, trimming, splitting and joining, driven in headless Chromium at phone size."""
import json

import pytest

pytest.importorskip("playwright")
from playwright.sync_api import expect  # noqa: E402

from conftest import needs_ffmpeg  # noqa: E402
from test_review_ui import (  # noqa: E402,F401  (fixtures and helpers shared with the other review tests)
    edit, http, make_words, new_page, review, saved, shot, status_of, take, explain_failure,
)

pytestmark = needs_ffmpeg


def segs(server, take_id):
    return {s["id"]: s for s in edit(server, take_id)["segments"]}


def open_timing(page):
    page.locator("#timing summary").click()
    expect(page.locator("#wave-canvas")).to_be_visible()


def view_of(page, take_duration):
    """The stretch of the recording the waveform shows: the piece plus room around it (mirrors wavegeo.viewWindow)."""
    s, e = (float(page.get_attribute(f"#h-{k}", "aria-valuenow")) for k in ("start", "end"))
    room = max(0.6, (e - s) * 0.35)
    return max(0.0, s - room), min(take_duration, e + room)


def canvas_x(page, t, vs, ve):
    # the fixed action bar covers the bottom of the screen, so bring the picture to the middle before using the mouse
    page.evaluate("document.getElementById('wave').scrollIntoView({block: 'center'})")
    page.wait_for_timeout(100)
    box = page.locator("#wave").bounding_box()
    return box["x"] + (t - vs) / (ve - vs) * box["width"], box["y"] + box["height"] / 2


def has_bar(page, t, vs, ve):
    """Whether the waveform has drawn solid ink just above the centre line at time t."""
    return page.evaluate("""([t, vs, ve]) => {
        const c = document.getElementById('wave-canvas'); const dpr = window.devicePixelRatio || 1;
        const copy = document.createElement('canvas'); copy.width = c.width; copy.height = c.height;
        const g = copy.getContext('2d', { willReadFrequently: true }); g.drawImage(c, 0, 0);
        const x = Math.round((t - vs) / (ve - vs) * c.width), mid = Math.round(c.height / 2);
        const d = g.getImageData(x, mid - Math.round(20 * dpr), 1, Math.round(15 * dpr)).data;
        for (let i = 3; i < d.length; i += 4) if (d[i] > 200) return true; return false; }""", [t, vs, ve])


# ------------------------------------------------------------------ the picture and the handles
def test_cut_points_start_closed_then_show_a_real_waveform_and_labelled_handles(review, server):
    page, _ctx, problems, take = review
    assert not page.locator("#timing").evaluate("n => n.open")
    open_timing(page)
    dur = http(server, f"/api/takes/{take}")["duration"]
    vs, ve = view_of(page, dur)
    for _ in range(80):                                                             # speech is drawn...
        if has_bar(page, 1.0, vs, ve):
            break
        page.wait_for_timeout(100)
    else:
        pytest.fail("the waveform was never drawn")
    assert not has_bar(page, 0.1, vs, ve)                                           # ...and the silence before it is not
    for which, value in (("start", "0.20"), ("end", "1.80")):
        h = page.locator(f"#h-{which}")
        assert h.get_attribute("role") == "slider" and h.get_attribute("aria-label")
        assert h.get_attribute("aria-valuenow") == value
        assert "seconds" in h.get_attribute("aria-valuetext")
        assert h.bounding_box()["width"] >= 40                                        # a finger-sized target
    expect(page.locator("#wave-read")).to_contain_text("Starts at 0:00.20, ends at 0:01.80, 1.60 seconds long")
    page.evaluate("document.getElementById('wave').scrollIntoView({block: 'center'})")
    shot(page, "20-wave")
    page.evaluate("document.getElementById('g-cut').scrollIntoView({block: 'start'})")
    shot(page, "20b-nudge")
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    assert problems == [], problems


def test_the_open_section_survives_a_reload_and_fits_a_narrow_phone(browser, server, take):
    page, ctx, problems = new_page(browser, server, f"/review/{take}", viewport={"width": 320, "height": 640})
    expect(page.locator("#piece-title")).to_have_text("Piece 1 of 5")
    open_timing(page)
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    for sel in ("[data-nudge='start'][data-dir='-1']", "#trim", "#join-next", "#split-word"):
        box = page.locator(sel).bounding_box()
        assert box["x"] >= 0 and box["x"] + box["width"] <= 320 and box["height"] >= 40, sel
    page.locator("#split-word").scroll_into_view_if_needed()
    shot(page, "21-narrow-open")
    page.reload()
    expect(page.locator("#wave-canvas")).to_be_visible()
    assert problems == [], problems
    ctx.close()


# ------------------------------------------------------------------ moving a cut point
def test_nudge_buttons_move_a_cut_point_stop_at_neighbours_and_undo_as_one_step(review, server):
    page, _ctx, _, take = review
    open_timing(page)
    page.locator("[data-nudge='start'][data-dir='-1']").click()
    page.locator("[data-nudge='start'][data-dir='-1']").click()
    expect(page.locator("#wave-read")).to_contain_text("Starts at 0:00.10")
    assert page.get_attribute("#h-start", "aria-valuenow") == "0.10"
    page.locator("[data-nudge='start'][data-dir='-1']").click()
    page.locator("[data-nudge='start'][data-dir='-1']").click()
    page.locator("[data-nudge='start'][data-dir='-1']").click()    # the recording begins at 0: it stops there
    expect(page.locator("#wave-hint")).to_contain_text("edge of the recording")
    saved(page)
    assert segs(server, take)["s001"]["start"] == 0.0
    page.locator("#undo").click()                                  # all those nudges were one adjustment
    expect(page.locator("#wave-read")).to_contain_text("Starts at 0:00.20")
    saved(page)
    assert segs(server, take)["s001"]["start"] == 0.2

    for _ in range(6):
        page.locator("[data-nudge='end'][data-dir='1']").click()   # s001 ends at 1.8; the next piece starts at 2.0
    expect(page.locator("#wave-hint")).to_contain_text("next piece starts there")
    saved(page)
    assert segs(server, take)["s001"]["end"] == 2.0


def test_the_step_size_applies_to_buttons_and_is_remembered(review, server):
    page, _ctx, _, take = review
    open_timing(page)
    page.select_option("#step", "0.25")
    page.locator("[data-nudge='end'][data-dir='-1']").click()
    expect(page.locator("#wave-read")).to_contain_text("ends at 0:01.55")
    page.reload()
    page.locator("#timing summary").wait_for()
    assert page.input_value("#step") == "0.25"


def test_arrow_keys_on_a_handle_move_it_and_do_not_change_piece(review, server):
    page, _ctx, _, take = review
    open_timing(page)
    page.locator("#h-start").focus()
    page.keyboard.press("ArrowRight")                              # 50 ms, the default step
    assert page.get_attribute("#h-start", "aria-valuenow") == "0.25"
    page.keyboard.press("Shift+ArrowRight")                        # five steps
    assert page.get_attribute("#h-start", "aria-valuenow") == "0.50"
    page.keyboard.press("ArrowLeft")
    expect(page.locator("#wave-read")).to_contain_text("Starts at 0:00.45")
    expect(page.locator("#piece-title")).to_have_text("Piece 1 of 5")  # arrows belong to the handle, not the shortcuts
    page.locator("#h-end").focus()
    page.keyboard.press("PageDown")                                # half a second earlier
    assert page.get_attribute("#h-end", "aria-valuenow") == "1.30"
    saved(page)
    s = segs(server, take)["s001"]
    assert (s["start"], s["end"]) == (0.45, 1.3)


def test_dragging_a_handle_with_a_pointer_moves_it_and_clamps(review, server):
    page, _ctx, _, take = review
    open_timing(page)
    dur = http(server, f"/api/takes/{take}")["duration"]
    vs, ve = view_of(page, dur)
    x, y = canvas_x(page, 1.8, vs, ve)
    page.mouse.move(x, y)
    page.mouse.down()
    page.mouse.move(x - 40, y, steps=6)
    now = float(page.get_attribute("#h-end", "aria-valuenow"))
    assert 1.3 < now < 1.7, now                                    # it follows the pointer while dragging...
    assert segs(server, take)["s001"]["end"] == 1.8                # ...but nothing is saved until it's let go
    page.mouse.up()
    saved(page)
    end = segs(server, take)["s001"]["end"]
    assert end == pytest.approx(now, abs=0.006)                     # the display rounds to 10 ms; what is saved is exact
    page.locator("#undo").click()
    saved(page)
    assert segs(server, take)["s001"]["end"] == 1.8                # one drag, one undo step
    x, y = canvas_x(page, 1.8, vs, ve)
    page.mouse.move(x, y)
    page.mouse.down()
    page.mouse.move(x + 150, y, steps=6)                           # far past where the next piece starts
    page.mouse.up()
    saved(page)
    assert segs(server, take)["s001"]["end"] == 2.0


def test_cutting_into_a_word_is_flagged_and_goes_away_when_undone(review, server):
    page, _ctx, _, take = review
    open_timing(page)
    page.select_option("#step", "0.25")
    for _ in range(3):
        page.locator("[data-nudge='start'][data-dir='1']").click()   # 0.2 -> 0.95: "Hello" and half of "there" are gone
    expect(page.locator("#wave-hint")).to_contain_text("falls inside a word")
    expect(page.locator("#p-flags")).to_contain_text("cut point falls inside a word")
    expect(page.locator("#bulk")).to_have_text("Approve all clean pieces (2)")   # it is no longer "clean"
    page.locator("#undo").click()
    expect(page.locator("#p-flags")).to_be_hidden()
    expect(page.locator("#bulk")).to_have_text("Approve all clean pieces (3)")


# ------------------------------------------------------------------ listening to the edges
def test_hear_the_start_and_the_end_play_short_clips_that_stop_by_themselves(review):
    page, *_ = review
    open_timing(page)
    page.locator("#hear-start").click()
    expect(page.locator("#play")).to_have_text("Stop")
    expect(page.locator("#play")).to_have_text("Play", timeout=4000)
    assert 0.9 <= page.evaluate("document.getElementById('audio').currentTime") <= 1.2   # 0.2 + 0.8 s
    page.locator("#hear-end").click()
    expect(page.locator("#play")).to_have_text("Stop")
    expect(page.locator("#play")).to_have_text("Play", timeout=4000)
    assert 1.7 <= page.evaluate("document.getElementById('audio').currentTime") <= 2.0   # ends at 1.8


def test_a_clip_after_each_change_is_off_unless_asked_for_and_remembered(review):
    page, *_ = review
    open_timing(page)
    page.locator("[data-nudge='start'][data-dir='1']").click()
    page.wait_for_timeout(400)
    assert page.evaluate("document.getElementById('audio').paused")      # no surprise sound
    page.locator("#audition").check()
    page.locator("[data-nudge='start'][data-dir='1']").click()
    expect(page.locator("#play")).to_have_text("Stop")
    page.reload()
    expect(page.locator("#audition")).to_be_checked()


# ------------------------------------------------------------------ trimming silence
def with_extra_silence(server, take):
    doc = edit(server, take)
    for s in doc["segments"]:
        if s["id"] == "s001":
            s["start"] = 0.0
        if s["id"] == "s005":
            s["end"] = 9.4
    http(server, f"/api/takes/{take}/edit", "PUT", {"rev": doc["rev"], "segments": doc["segments"]})


def test_trim_silence_tightens_the_piece_keeps_room_and_undoes(browser, server, take):
    with_extra_silence(server, take)
    page, ctx, problems = new_page(browser, server, f"/review/{take}")
    expect(page.locator("#piece-title")).to_have_text("Piece 1 of 5")
    open_timing(page)
    page.locator("#trim").click()
    expect(page.locator("#wave-hint")).to_contain_text("Trimmed")
    saved(page)
    s = segs(server, take)["s001"]
    assert 0.04 <= s["start"] <= 0.14, s["start"]                   # speech begins at 0.2; some room is left before it
    assert s["end"] == 1.8
    first_word = s["words"][0]["s"]
    assert s["start"] <= first_word - 0.05                            # never closer to a word than the safety margin
    page.locator("#undo").click()
    saved(page)
    assert segs(server, take)["s001"]["start"] == 0.0
    page.locator("#next").click()
    page.locator("#trim").click()                                    # piece 2 is already tight
    expect(page.locator("#wave-hint")).to_contain_text("Nothing to trim")
    assert problems == [], problems
    ctx.close()


# ------------------------------------------------------------------ split
def test_split_before_a_tapped_word_then_undo_and_redo(review, server):
    page, _ctx, problems, take = review
    open_timing(page)
    expect(page.locator("#split-word")).to_be_disabled()
    page.locator("#p-words button", has_text="my").click()           # also plays from there
    expect(page.locator("#split-word")).to_have_text("Split before “my”")
    page.locator("#play").click()                                      # stop the audio; it isn't what we are testing
    page.locator("#split-word").click()
    expect(page.locator("#wave-hint")).to_contain_text("Split in two")
    expect(page.locator("#summary")).to_contain_text("6 pieces")
    expect(page.locator("#p-text")).to_have_value("Hello there")       # stays on the first half
    saved(page)
    got = segs(server, take)
    a, b = got["s001"], got["s006"]
    assert (a["text"], b["text"]) == ("Hello there", "my friend.")
    assert a["end"] == b["start"] and (a["start"], b["end"]) == (0.2, 1.8)
    assert 0.96 < a["end"] < 1.0                                        # the middle of the pause between "there" and "my"
    assert a["status"] == b["status"] == "pending"
    assert a["flags"] == b["flags"] == ["too_short"]                    # each half is under a second: honest about it
    shot(page, "22-split")
    page.locator("#undo").click()
    expect(page.locator("#summary")).to_contain_text("5 pieces")
    expect(page.locator("#p-text")).to_have_value("Hello there my friend.")
    saved(page)
    assert set(segs(server, take)) == {"s001", "s002", "s003", "s004", "s005"}
    page.locator("#redo").click()
    expect(page.locator("#summary")).to_contain_text("6 pieces")
    saved(page)
    assert problems == [], problems


def test_splitting_an_approved_piece_resets_both_halves_and_keeps_the_view_on_it(review, server):
    page, _ctx, _, take = review
    page.select_option("#filter", "all")
    page.locator("#approve").click()
    page.locator("#prev").click()
    expect(page.locator("#p-status")).to_have_text("Approved")
    open_timing(page)
    page.locator("#p-words button", has_text="my").click()
    page.locator("#play").click()
    page.locator("#split-word").click()
    expect(page.locator("#p-status")).to_have_text("To review")
    saved(page)
    got = segs(server, take)
    assert got["s001"]["status"] == got["s006"]["status"] == "pending"


def test_tapping_the_waveform_places_a_marker_that_splits_there(review, server):
    page, _ctx, _, take = review
    open_timing(page)
    dur = http(server, f"/api/takes/{take}")["duration"]
    vs, ve = view_of(page, dur)
    x, y = canvas_x(page, 2.2, vs, ve)
    page.mouse.click(x, y)                                              # outside the piece: refused politely
    expect(page.locator("#wave-hint")).to_contain_text("inside the shaded part")
    expect(page.locator("#h-marker")).to_be_hidden()
    x, y = canvas_x(page, 1.0, vs, ve)
    page.mouse.click(x, y)
    expect(page.locator("#h-marker")).to_be_visible()
    marker = float(page.get_attribute("#h-marker", "aria-valuenow"))
    assert 0.97 < marker < 1.03
    expect(page.locator("#split-marker")).to_have_text(f"Split at 0:0{marker:.2f}")
    page.locator("#h-marker").focus()
    page.keyboard.press("ArrowRight")
    assert float(page.get_attribute("#h-marker", "aria-valuenow")) == pytest.approx(marker + 0.05, abs=0.011)   # the display rounds to 10 ms
    page.locator("#hear-marker").click()
    expect(page.locator("#play")).to_have_text("Stop")
    page.locator("#play").click()
    page.locator("#split-marker").click()
    expect(page.locator("#summary")).to_contain_text("6 pieces")
    saved(page)
    got = segs(server, take)
    assert got["s001"]["end"] == got["s006"]["start"] == pytest.approx(marker + 0.05, abs=0.011)
    assert got["s001"]["text"] + " " + got["s006"]["text"] == "Hello there my friend."


def test_the_marker_cannot_be_moved_to_the_very_edge_of_a_piece(review, server):
    page, _ctx, _, take = review
    open_timing(page)
    dur = http(server, f"/api/takes/{take}")["duration"]
    vs, ve = view_of(page, dur)
    x, y = canvas_x(page, 1.0, vs, ve)
    page.mouse.click(x, y)
    page.locator("#h-marker").focus()
    for _ in range(3):
        page.keyboard.press("PageDown")                                 # half a second earlier, three times
    assert float(page.get_attribute("#h-marker", "aria-valuenow")) == pytest.approx(0.3, abs=0.001)   # 0.1 s inside the start
    for _ in range(5):
        page.keyboard.press("PageUp")
    assert float(page.get_attribute("#h-marker", "aria-valuenow")) == pytest.approx(1.7, abs=0.001)   # 0.1 s inside the end
    assert len(segs(server, take)) == 5                                  # moving a marker changes nothing


# ------------------------------------------------------------------ join
def test_join_with_the_next_and_previous_piece_and_undo(review, server):
    page, _ctx, problems, take = review
    open_timing(page)
    expect(page.locator("#join-prev")).to_be_disabled()                 # nothing before the first piece
    page.locator("#join-next").click()
    expect(page.locator("#wave-hint")).to_contain_text("Joined")
    expect(page.locator("#summary")).to_contain_text("4 pieces")
    expect(page.locator("#p-text")).to_have_value("Hello there my friend. I paid twenty dollars.")
    saved(page)
    got = segs(server, take)
    assert "s002" not in got and (got["s001"]["start"], got["s001"]["end"]) == (0.2, 3.6)
    assert len(got["s001"]["words"]) == 8 and got["s001"]["status"] == "pending"
    shot(page, "23-joined")
    page.locator("#undo").click()
    expect(page.locator("#summary")).to_contain_text("5 pieces")
    saved(page)
    assert segs(server, take)["s002"]["text"] == "I paid twenty dollars."
    page.select_option("#filter", "all")
    page.locator("#next").click()                                       # now on piece 2
    page.locator("#join-prev").click()
    expect(page.locator("#p-text")).to_have_value("Hello there my friend. I paid twenty dollars.")
    saved(page)
    assert "s002" not in segs(server, take)
    page.select_option("#filter", "all")
    page.locator("#list .pitem").last.click()
    expect(page.locator("#join-next")).to_be_disabled()                 # nothing after the last piece
    assert problems == [], problems


def test_pieces_made_by_splitting_survive_a_reload(review, server):
    page, _ctx, _, take = review
    open_timing(page)
    page.locator("#p-words button", has_text="friend.").click()
    page.locator("#play").click()
    page.locator("#split-word").click()
    saved(page)
    page.reload()
    expect(page.locator("#filter option[value='all']")).to_have_text("All (6)")


# ------------------------------------------------------------------ no waveform available
def test_everything_still_works_when_the_waveform_cannot_be_loaded(browser, server, take):
    def block(page):
        page.route("**/api/takes/*/peaks*", lambda route: route.fulfill(status=404, content_type="application/json", body='{"error":"no"}'))
    page, ctx, _ = new_page(browser, server, f"/review/{take}", before=block)
    expect(page.locator("#piece-title")).to_have_text("Piece 1 of 5")
    open_timing(page)
    page.locator("[data-nudge='start'][data-dir='1']").click()
    expect(page.locator("#wave-read")).to_contain_text("Starts at 0:00.25")
    page.locator("#trim").click()
    expect(page.locator("#wave-hint")).to_contain_text("waveform isn't available")
    shot(page, "24-no-wave")
    ctx.close()


def test_the_new_controls_are_named_and_do_not_break_the_other_shortcuts(review):
    page, *_ = review
    open_timing(page)
    for btn in page.locator("#timing button:visible, #timing select:visible").all():
        name = btn.inner_text().strip() or btn.get_attribute("aria-label") or ""
        assert name, "every control in the cut-points section needs a name"
    page.locator("#take-title").click()
    page.keyboard.press("j")
    expect(page.locator("#piece-title")).to_have_text("Piece 2 of 5")  # the letter shortcuts still work with the section open
