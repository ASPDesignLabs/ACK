# SPDX-License-Identifier: GPL-3.0-or-later
"""Consent (plan task VS-1.3): agreement is for exactly the file that was shown, and a damaged record means no agreement."""
import json
import os
import stat
from dataclasses import replace
from datetime import datetime, timezone

import pytest

from vs_fetch_helpers import pinned_item
from voice_studio.core import consent as cs
from voice_studio.core.registry import Item


def test_consent_covers_a_pinned_item_it_was_made_for():
    item = pinned_item()
    record = cs.make_consent([item])
    assert record.covers(item) and not record.covers_id("apt:git")


def test_an_unpinned_item_is_never_covered_so_nothing_is_agreed_to_before_it_is_checked():
    unpinned = Item("voice-mike", "voice", "k", "l", approx_size_bytes=846_000_000)
    record = cs.make_consent([unpinned, pinned_item()])
    assert not record.covers(unpinned) and len(record.entries) == 1


@pytest.mark.parametrize("change", [dict(sha256="b" * 64), dict(size_bytes=2049), dict(url="https://huggingface.co/datasets/example/store/resolve/0123abcd/other.ckpt")])
def test_if_the_registry_later_points_at_a_different_file_the_old_consent_does_not_cover_it(change):
    item = pinned_item()
    record = cs.make_consent([item])
    assert not record.covers(replace(item, **change))


def test_names_with_no_file_behind_them_are_consented_to_by_name():
    record = cs.make_consent([], extra_ids=["apt:git", "pip:lock"])
    assert record.covers_id("apt:git") and record.covers_id("pip:lock") and not record.covers_id("apt:cmake")


def test_the_time_is_recorded_in_utc():
    stamp = datetime(2026, 10, 10, 12, 30, 5, tzinfo=timezone.utc)
    assert cs.make_consent([], now=stamp).given_at == "2026-10-10T12:30:05Z"


def test_a_record_survives_saving_and_loading_and_is_owner_only(tmp_path):
    path = tmp_path / "state" / "consent.json"
    record = cs.make_consent([pinned_item()], extra_ids=["apt:git"])
    cs.save_consent(path, record)
    assert cs.load_consent(path) == record
    assert stat.S_IMODE(os.stat(path).st_mode) == 0o600
    assert [p.name for p in path.parent.iterdir()] == ["consent.json"]       # no temporary file left behind


def test_a_failed_save_keeps_the_old_record_and_leaves_nothing_behind(tmp_path, monkeypatch):
    path = tmp_path / "consent.json"
    old = cs.make_consent([], extra_ids=["apt:git"])
    cs.save_consent(path, old)

    def boom(*_):
        raise OSError("disk full")
    monkeypatch.setattr(cs.os, "replace", boom)
    with pytest.raises(OSError):
        cs.save_consent(path, cs.make_consent([], extra_ids=["apt:cmake"]))
    monkeypatch.undo()
    assert cs.load_consent(path) == old and [p.name for p in tmp_path.iterdir()] == ["consent.json"]


@pytest.mark.parametrize("content", [
    "not json", "[]", "{}", json.dumps({"schema": 9, "given_at": "x", "entries": []}),
    json.dumps({"schema": 1, "given_at": "x"}), json.dumps({"schema": 1, "given_at": "x", "entries": [{"id": 5}]}),
    json.dumps({"schema": 1, "given_at": "x", "entries": [{"id": "a", "size_bytes": "big"}]}),
    json.dumps({"schema": 1, "given_at": "x", "entries": [{"id": "a", "size_bytes": True}]}), json.dumps({"schema": 1, "given_at": "x", "entries": [3]}),
])
def test_a_damaged_record_is_no_agreement_and_never_an_exception(tmp_path, content):
    path = tmp_path / "consent.json"
    path.write_text(content)
    assert cs.load_consent(path) is None


def test_no_file_is_no_agreement(tmp_path):
    assert cs.load_consent(tmp_path / "missing.json") is None


def test_unknown_fields_are_ignored_so_a_newer_record_still_reads(tmp_path):
    path = tmp_path / "consent.json"
    path.write_text(json.dumps({"schema": 1, "given_at": "t", "future": 1, "entries": [{"id": "apt:git", "extra": "x"}]}))
    assert cs.load_consent(path).covers_id("apt:git")


# ---------------------------------------------------------------- adding a new yes to an old one

def test_a_new_agreement_adds_to_the_saved_one_and_never_forgets_an_earlier_yes():
    old = cs.ConsentRecord((cs.ConsentEntry("apt:git"), cs.ConsentEntry("voice-a", "https://huggingface.co/o/a", 5, "a" * 64)), "2026-01-01T00:00:00Z")
    new = cs.ConsentRecord((cs.ConsentEntry("pip:training"),), "2026-02-02T00:00:00Z")
    merged = cs.merge_consent(old, new)
    assert [e.id for e in merged.entries] == ["apt:git", "voice-a", "pip:training"] and merged.given_at == "2026-02-02T00:00:00Z"


def test_an_id_agreed_to_again_takes_the_entry_just_shown_not_the_old_one():
    old = cs.ConsentRecord((cs.ConsentEntry("voice-a", "https://huggingface.co/o/a", 5, "a" * 64), cs.ConsentEntry("apt:git")), "2026-01-01T00:00:00Z")
    new = cs.ConsentRecord((cs.ConsentEntry("voice-a", "https://huggingface.co/o/b", 6, "b" * 64),), "2026-02-02T00:00:00Z")
    merged = cs.merge_consent(old, new)
    assert merged.entries == (cs.ConsentEntry("apt:git"), cs.ConsentEntry("voice-a", "https://huggingface.co/o/b", 6, "b" * 64))
    assert cs.ConsentEntry("voice-a", "https://huggingface.co/o/a", 5, "a" * 64) not in merged.entries


def test_merging_with_nothing_saved_gives_the_new_agreement_as_it_is():
    new = cs.ConsentRecord((cs.ConsentEntry("pip:x"),), "2026-02-02T00:00:00Z")
    assert cs.merge_consent(None, new) is new


def test_merging_does_not_change_the_records_it_was_given():
    old = cs.ConsentRecord((cs.ConsentEntry("a"),), "t1")
    new = cs.ConsentRecord((cs.ConsentEntry("b"),), "t2")
    cs.merge_consent(old, new)
    assert old.entries == (cs.ConsentEntry("a"),) and new.entries == (cs.ConsentEntry("b"),)
