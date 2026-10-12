# SPDX-License-Identifier: GPL-3.0-or-later
"""The registry of downloads (plan task VS-1.3): what an entry must be to be fetchable, and that nothing is half pinned."""
import json
import re
from dataclasses import replace
from urllib.parse import quote, urlparse

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


def test_everything_in_the_shipped_registry_is_fully_pinned_to_one_commit_one_size_and_one_checksum():
    for item in reg.load_registry().items:
        assert item.pin_problems() == [] and item.pinned, item.id
        assert re.fullmatch(r"[0-9a-f]{40}", item.revision) and item.revision in item.url, item.id          # a commit, never a branch name that can move
        assert re.fullmatch(r"[0-9a-f]{64}", item.sha256) and 0 < item.size_bytes <= reg.MAX_FILE_BYTES, item.id
        assert urlparse(item.url).hostname == "huggingface.co" and item.url.endswith("/" + quote(item.filename, safe="=+-._")), item.id


def test_the_starting_voices_are_the_medium_checkpoints_of_mike_and_amy_in_the_original_hosts_dataset():
    registry = reg.load_registry()
    base = "https://huggingface.co/datasets/rhasspy/piper-checkpoints/resolve/"
    for voice in ("mike", "amy"):
        item = registry.get("voice-" + voice)
        assert item.kind == "voice" and item.url.startswith(base) and ("/en/en_US/%s/medium/" % voice) in item.url and item.filename.endswith(".ckpt"), voice
        assert item.approx_size_bytes == 846_000_000 and abs(item.size_bytes - item.approx_size_bytes) < 1_000_000, "the round number the host shows is close to the exact one"


def test_mikes_pin_is_the_file_the_developer_trained_from():
    """The developer's own mike.ckpt (copied between two computers and compared by fingerprint) is byte for byte the file the pin names."""
    assert reg.load_registry().get("voice-mike").sha256 == "9a8389c2d733f94e2acc3b4e8264b4ba3c063612217780e4be21c0ccaff18b9b"


def test_the_speech_model_is_four_files_pinned_one_by_one_in_one_folder():
    files = [i for i in reg.load_registry().items if i.kind == "model"]
    assert sorted(i.filename for i in files) == ["config.json", "model.bin", "tokenizer.json", "vocabulary.txt"]
    assert {i.folder for i in files} == {"speech-small-en"} and len({i.revision for i in files}) == 1
    assert all(i.url.startswith("https://huggingface.co/Systran/faster-whisper-small.en/resolve/") for i in files)
    assert 480_000_000 < sum(i.size_bytes for i in files) < 490_000_000, "about the 480 MB the plan has always said"


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


# ---------------------------------------------------------------- a model of several files shares a folder

def test_an_item_may_name_the_folder_it_shares_with_others_and_defaults_to_none():
    item = reg.parse_registry(doc(dict(GOOD, folder="speech-small-en"))).items[0]
    assert item.folder == "speech-small-en" and reg.parse_registry(doc(GOOD)).items[0].folder is None


@pytest.mark.parametrize("folder", ["../x", "a/b", "A", "", "-x", "a b", "x" * 70])
def test_a_folder_that_is_not_a_plain_lower_case_name_is_refused(folder):
    with pytest.raises(reg.RegistryError, match="bad folder|folder"):
        reg.parse_registry(doc(dict(GOOD, folder=folder)))


def test_the_folder_is_not_part_of_what_makes_an_item_pinned():
    assert reg.Item("a", "model", "k", "l", approx_size_bytes=5, folder="f").pin_problems() == ["unpinned"]


def test_the_old_single_placeholder_for_the_speech_model_is_gone():
    with pytest.raises(KeyError):
        reg.load_registry().get("speech-model-small-en")


# ---------------------------------------------------------------- pages to read before a download (shown, never opened)

PAGE = "https://example.org/licence.html"


def one(**over):
    return parse_registry(doc({**GOOD, **over})).items[0]


def test_an_entry_may_carry_pages_to_read_and_they_are_kept_in_name_order_and_found_by_name():
    item = one(pages={"zeta": "https://example.org/z", "alpha": PAGE})
    assert item.pages == (("alpha", PAGE), ("zeta", "https://example.org/z")) and item.page("alpha") == PAGE and item.page("nope") is None
    assert one().pages == () and one(pages={}).pages == ()


def test_pages_are_no_part_of_a_pin_so_they_neither_make_an_entry_fetchable_nor_stop_it_being_so():
    unpinned = {"id": "voice-y", "kind": "voice", "why_key": "fetch.why.x", "license_id": "voice-y-card", "approx_size_bytes": 5, "pages": {"a": PAGE}}
    item = parse_registry(doc(unpinned)).items[0]
    assert item.pin_problems() == ["unpinned"] and not item.any_pin_field and not item.pinned
    assert one(pages={"a": PAGE}).pinned and one(pages={"a": "https://not-an-allowed-host.example/p"}).pinned, "a page is shown, so its host is not limited to the download hosts"


@pytest.mark.parametrize("pages", ["https://example.org/p", ["https://example.org/p"], 5, {"A": PAGE}, {"": PAGE}, {"a b": PAGE}, {"a": 5}, {"a": None}, {"a": ""},
                                   {"a": "http://example.org/p"}, {"a": "ftp://example.org/p"}, {"a": "example.org/p"}, {"a": "https://"},
                                   {"a": "https://user:secret@example.org/p"}, {"a": "https://user@example.org/p"}, {"a": "https://example.org/a b"},
                                   {"a": "https://example.org/a\nb"}, {"a": "https://example.org/\u00e9"}, {"a": "https://example.org/" + "x" * 300}])
def test_a_page_that_is_not_a_plain_https_address_without_credentials_is_refused(pages):
    with pytest.raises(RegistryError):
        parse_registry(doc({**GOOD, "pages": pages}))


def test_a_page_at_the_longest_length_is_accepted_and_one_more_is_not():
    longest = "https://example.org/" + "x" * (reg.MAX_PAGE_LENGTH - len("https://example.org/"))
    assert len(longest) == reg.MAX_PAGE_LENGTH and one(pages={"a": longest}).page("a") == longest
    assert reg.page_problem(longest + "x") == "not_an_address"


def test_the_reasons_a_page_is_refused_are_told_apart():
    assert reg.page_problem(PAGE) is None and reg.page_problem(5) == "not_text" and reg.page_problem("") == "not_an_address"
    assert reg.page_problem("http://example.org/p") == "not_https" and reg.page_problem("https://u:p@example.org/p") == "has_credentials"
    assert reg.page_problem("https:///p") == "not_https"


def test_the_shipped_pages_are_https_addresses_on_the_hosts_the_notices_name_and_only_the_voices_have_them():
    registry = reg.load_registry()
    hosts = {urlparse(a).hostname for i in registry.items for _, a in i.pages}
    assert hosts == {"github.com", "www.cstr.ed.ac.uk"}
    assert [i.id for i in registry.items if i.pages] == ["voice-mike", "voice-amy"]
