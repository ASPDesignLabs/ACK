import json
import os
import time

import pytest

from conftest import needs_ffmpeg
from freeform_studio import build_dataset as bd
from freeform_studio.edit import clean_words, normalize_edit, validate_edit
from freeform_studio.storage import TakeStore
from test_api import make_cfg, run, upload, wait_for, webm_chunks
from freeform_studio.app import create_app


# ------------------------------------------------------------------ words
def test_words_keep_only_known_keys_and_valid_entries():
    raw = [{"w": "Hello", "s": 0.1234, "e": 0.5, "p": 0.98765, "j": True, "evil": "<b>"},
           {"w": 5, "s": 0, "e": 1}, {"w": "x", "s": "a", "e": 1}, "junk", {"w": "y", "s": 2.0, "e": 1.0, "ed": True},
           {"w": "z", "s": float("nan"), "e": 1}, {"w": "w", "s": 0, "e": 1, "p": 7}]
    out = clean_words(raw)
    assert out[0] == {"w": "Hello", "s": 0.123, "e": 0.5, "p": 0.988, "j": True}
    assert out[1] == {"w": "y", "s": 2.0, "e": 2.0, "p": 1.0, "ed": True}  # an end before its start is clamped
    assert out[2]["p"] == 1.0 and len(out) == 3  # malformed ones are dropped; out-of-range confidence is clamped
    assert clean_words("nope") == [] and len(clean_words([{"w": "a", "s": 0, "e": 1}] * 999)) == 400
    assert clean_words([{"w": "q" * 500, "s": 0, "e": 1}])[0]["w"] == "q" * 80


def test_normalize_applies_word_cleaning_per_segment():
    seg = {"id": "s001", "start": 0, "end": 1, "text": "a", "words": [{"w": "a", "s": 0, "e": 1, "x": 1}, "bad"],
           "status": "pending", "tags": [], "note": ""}
    out = normalize_edit({"rev": 1, "segments": [seg]})
    assert out["segments"][0]["words"] == [{"w": "a", "s": 0.0, "e": 1.0, "p": 1.0}]
    assert validate_edit(out, 5.0) == []


# ------------------------------------------------------------------ history retention
def make_history(store, tid, ages_minutes):
    d = store.path(tid, "edit_history")
    d.mkdir(parents=True, exist_ok=True)
    now = time.time()
    for i, age in enumerate(ages_minutes):
        p = d / f"edit-rev{i:05d}.json"
        p.write_text(json.dumps({"rev": i, "segments": []}))
        os.utime(p, (now - age * 60, now - age * 60))
    return d


def test_history_keeps_recent_snapshots_then_thins_old_ones(tmp_path):
    store = TakeStore(tmp_path)
    tid = store.create({})["id"]
    d = make_history(store, tid, [i * 0.5 for i in range(200)])  # 200 snapshots over ~100 minutes, one every 30 s
    store.prune_thinned(tid, "edit_history")
    left = sorted(d.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
    ages = [(time.time() - p.stat().st_mtime) / 60 for p in left]
    assert sum(1 for a in ages if a <= 15) >= 30  # the newest 30 are all there (about 15 minutes' worth)
    older = [a for a in ages if a > 16]
    assert 1 <= len(older) <= 4 and len(left) <= 40  # beyond that, roughly one per half hour


def test_history_never_prunes_safety_snapshots_and_respects_the_cap(tmp_path):
    store = TakeStore(tmp_path)
    tid = store.create({})["id"]
    d = make_history(store, tid, [i for i in range(400)])
    (d / "edit-pre-regen-20260101-000000.json").write_text("{}")
    (d / "edit-before-restore-20260101-000000.json").write_text("{}")
    for p in (d / "edit-pre-regen-20260101-000000.json", d / "edit-before-restore-20260101-000000.json"):
        os.utime(p, (1000, 1000))  # ancient
    store.prune_thinned(tid, "edit_history")
    names = {p.name for p in d.iterdir()}
    assert "edit-pre-regen-20260101-000000.json" in names and "edit-before-restore-20260101-000000.json" in names
    assert len(names) <= 102


# ------------------------------------------------------------------ restore, over the real API
@needs_ffmpeg
def test_history_lists_versions_and_restore_brings_one_back_safely(tmp_path, out_dir):
    chunks, _ = webm_chunks(tmp_path)

    async def main():
        app = create_app(make_cfg(out_dir))
        async with app.test_app():
            c = app.test_client()
            tid = await upload(c, chunks)
            await c.post(f"/api/takes/{tid}/finish")
            await wait_for(c, tid, {"ready"})
            edit = await (await c.get(f"/api/takes/{tid}/edit")).get_json()
            original = edit["segments"][0]["text"]
            for n, text in enumerate(["first change.", "second change.", "third change."]):
                edit["segments"][0]["text"] = text
                edit["segments"][0]["status"] = "approved"
                edit["rev"] = (await (await c.put(f"/api/takes/{tid}/edit", json=edit)).get_json())["rev"]

            hist = (await (await c.get(f"/api/takes/{tid}/edit/history")).get_json())["history"]
            assert len(hist) == 3 and hist[0]["counts"]["segments"] == len(edit["segments"])
            assert {h["name"] for h in hist} == {"edit-rev00001.json", "edit-rev00002.json", "edit-rev00003.json"}

            # restore the very first version (the untouched proposal)
            r = await c.post(f"/api/takes/{tid}/edit/restore", json={"name": "edit-rev00001.json", "rev": edit["rev"]})
            body = await r.get_json()
            assert r.status_code == 200 and body["rev"] == edit["rev"] + 1
            assert body["segments"][0]["text"] == original and body["segments"][0]["status"] == "pending"
            names = [h["name"] for h in (await (await c.get(f"/api/takes/{tid}/edit/history")).get_json())["history"]]
            assert any(n.startswith("edit-before-restore-") for n in names)  # what was there is recoverable too

            # stale revision, bad names, traversal attempts and unknown versions are all refused
            assert (await c.post(f"/api/takes/{tid}/edit/restore", json={"name": "edit-rev00001.json", "rev": 1})).status_code == 409
            for bad in ("../edit.json", "edit-rev00001.json/../../take.json", "take.json", "", None, 5):
                r = await c.post(f"/api/takes/{tid}/edit/restore", json={"name": bad, "rev": body["rev"]})
                assert r.status_code == 400, bad
            r = await c.post(f"/api/takes/{tid}/edit/restore", json={"name": "edit-rev99999.json", "rev": body["rev"]})
            assert r.status_code == 404

    run(main())


@needs_ffmpeg
def test_review_pages_are_served_with_the_strict_policy(out_dir):
    async def main():
        app = create_app(make_cfg(out_dir))
        async with app.test_app():
            c = app.test_client()
            for path in ("/review", "/review/t20260101-000000-abcd", "/"):
                r = await c.get(path)
                assert r.status_code == 200 and "text/html" in r.headers["content-type"]
                assert "script-src 'self'" in r.headers["content-security-policy"]

    run(main())


# ------------------------------------------------------------------ tags drive what gets exported
def test_pieces_tagged_laugh_or_noise_are_left_out_even_when_approved():
    base = {"start": 0.0, "end": 3.0, "text": "Fine words.", "flags": [], "tags": []}
    p = bd.Policy()
    assert bd.why_excluded({**base, "status": "pending"}, p) is None
    assert bd.why_excluded({**base, "status": "approved", "tags": ["laugh"]}, p) == "tagged: laugh"
    assert bd.why_excluded({**base, "status": "pending", "tags": ["noise", "cough"]}, p) == "tagged: cough, noise"
    assert bd.why_excluded({**base, "status": "approved", "tags": ["breath"]}, p) is None  # breath is allowed
    assert bd.why_excluded({**base, "status": "approved", "tags": ["laugh"]}, bd.Policy(exclude_tags=set())) is None
