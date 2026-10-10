# SPDX-License-Identifier: GPL-3.0-or-later
"""The registry of downloads (plan task VS-1.3): what an entry must be to be fetchable, and that nothing is half pinned."""
import json
from dataclasses import replace

import pytest

from vs_fetch_helpers import ADDRESS, pinned_item
from voice_studio.core import registry as reg
from voice_studio.core.registry import Item, RegistryError, parse_registry

GOOD = {"id": "voice-x", "kind": "voice", "why_key": "fetch.why.x", "license_id": "voice-x-card", "approx_size_bytes": 5,
        "url": ADDRESS, "filename": "model.ckpt", "revision": "0123abcd", "size_bytes": 5, "sha256": "a" * 64}


def doc(*items, schema=1):
    return json.dumps({"schema": schema, "items": list(items)})


# ---------------------------------------------------------------- the shipped file

def test_the_shipped_registry_loads_and_lists_the_starting_voices():
    registry = reg.load_registry()
    ids = [i.id for i in registry.items]
    assert len(ids) == len(set(ids)) and {"voice-mike", "voice-amy"} <= set(ids)
    assert registry.get("voice-mike").approx_size_bytes == 846_000_000 == registry.get("voice-amy").approx_size_bytes


def test_nothing_in_the_shipped_registry_is_fetchable_until_it_has_been_checked_on_a_real_machine():
    for item in reg.load_registry().items:
        assert item.pin_problems() == ["unpinned"] and not item.pinned and item.url is None, item.id


def test_every_shipped_entry_has_a_reason_a_license_id_and_a_size_for_the_disk_estimate():
    for item in reg.load_registry().items:
        assert item.why_key.startswith("fetch.why.") and reg.SLUG.match(item.license_id) and (item.size_for_budget or 0) > 0, item.id


def test_an_unknown_id_is_a_key_error():
    with pytest.raises(KeyError):
        reg.load_registry().get("nope")


# ---------------------------------------------------------------- pinning

def test_a_fully_pinned_entry_has_no_problems():
    assert pinned_item().pin_problems() == [] and pinned_item().pinned


def test_a_size_for_the_budget_prefers_the_exact_one():
    assert replace(pinned_item(), approx_size_bytes=1, size_bytes=99).size_for_budget == 99
    assert Item("a", "file", "k", "l", approx_size_bytes=7).size_for_budget == 7
    assert Item("a", "file", "k", "l").size_for_budget is None


@pytest.mark.parametrize("field", reg.PIN_FIELDS)
def test_leaving_out_any_one_pin_field_is_a_problem_and_a_half_pinned_file_will_not_load(field):
    item = replace(pinned_item(), **{field: None})
    assert "missing_" + field in item.pin_problems() and not item.pinned
    bad = {k: v for k, v in GOOD.items() if k != field}
    with pytest.raises(RegistryError, match="half pinned"):
        parse_registry(doc(bad))


@pytest.mark.parametrize("overrides, code", [
    (dict(url=ADDRESS.replace("https", "http")), "url_not_https"),
    (dict(url="https://example.org/a/0123abcd/model.ckpt"), "url_host_not_allowed"),
    (dict(url="https://huggingface.co.evil.example/0123abcd/model.ckpt"), "url_host_not_allowed"),
    (dict(url="https://user:pw@huggingface.co/0123abcd/model.ckpt"), "url_has_credentials"),
    (dict(revision="ffff"), "revision_not_in_url"),
    (dict(filename="../model.ckpt"), "unsafe_filename"),
    (dict(filename="a/b.ckpt"), "unsafe_filename"),
    (dict(filename=".hidden"), "unsafe_filename"),
    (dict(filename="a..b"), "unsafe_filename"),
    (dict(filename=""), "unsafe_filename"),
    (dict(size_bytes=0), "size_out_of_range"),
    (dict(size_bytes=-1), "size_out_of_range"),
    (dict(size_bytes=reg.MAX_FILE_BYTES + 1), "size_out_of_range"),
    (dict(sha256="A" * 64), "bad_sha256"),
    (dict(sha256="a" * 63), "bad_sha256"),
    (dict(sha256="a" * 65), "bad_sha256"),
])
def test_each_way_an_entry_can_be_unsafe_is_named(overrides, code):
    assert code in pinned_item(**overrides).pin_problems()


def test_the_edges_of_the_limits():
    assert pinned_item(size_bytes=reg.MAX_FILE_BYTES).pin_problems() == []
    assert pinned_item(size_bytes=1).pin_problems() == []
    assert pinned_item(filename="a" * 150).pin_problems() == [] and "unsafe_filename" in pinned_item(filename="a" * 151).pin_problems()
    assert pinned_item(filename="epoch=2218-step=1383502.ckpt").pin_problems() == []


# ---------------------------------------------------------------- reading the file

@pytest.mark.parametrize("text, match", [
    ("not json", "not valid JSON"),
    (json.dumps([1]), "understands"),
    (doc(GOOD, schema=2), "understands"),
    (json.dumps({"schema": 1, "items": "x"}), "understands"),
    (doc("string"), "not an object"),
    (doc(dict(GOOD, id="Bad Id")), "bad id"),
    (doc(dict(GOOD, id=5)), "bad id"),
    (doc(GOOD, GOOD), "listed twice"),
    (doc(dict(GOOD, kind="movie")), "unknown kind"),
    (doc(dict(GOOD, why_key="")), "why_key"),
    (doc({k: v for k, v in GOOD.items() if k != "license_id"}), "license_id"),
    (doc(dict(GOOD, license_id="Not A Slug")), "license_id"),
    (doc(dict(GOOD, size_bytes="5")), "not a int"),
    (doc(dict(GOOD, size_bytes=True)), "not a int"),
    (doc(dict(GOOD, url=5)), "not a str"),
    (doc(dict(GOOD, url="http://huggingface.co/0123abcd/x")), "wrongly pinned"),
])
def test_a_registry_that_is_wrong_in_any_way_refuses_to_load_and_says_which_entry(text, match):
    with pytest.raises(RegistryError, match=match):
        parse_registry(text)


def test_a_good_file_loads_and_an_unpinned_entry_is_allowed():
    unpinned = {"id": "voice-y", "kind": "voice", "why_key": "k", "license_id": "l", "approx_size_bytes": 9}
    loaded = parse_registry(doc(GOOD, unpinned))
    assert [i.pinned for i in loaded.items] == [True, False]


def test_a_missing_file_is_a_plain_error(tmp_path):
    with pytest.raises(RegistryError, match="cannot read"):
        reg.load_registry(tmp_path / "nothing.json")
