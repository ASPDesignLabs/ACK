# SPDX-License-Identifier: GPL-3.0-or-later
"""The maintainers' pin maker (tools/voice_studio_maint/make_pins.py): how it reads the host's listing, what it refuses to guess, and that what it writes is a
registry the app accepts. The maker is not part of the app, but what it writes decides which exact files the app may download.

No network here: the host is a stand-in that answers in the shape the host documents for its listing (a list of entries with `type`, `path`, `size`, and for a large
file `lfs.oid`, the SHA-256 of its content)."""
import hashlib
import http.server
import importlib.util
import json
import socket
import socketserver
import sys
import threading
import urllib.parse
from pathlib import Path

import pytest

from voice_studio.core import registry as reg

PKG = Path(__file__).resolve().parents[1]
MAKER = PKG.parent / "voice_studio_maint" / "make_pins.py"
spec = importlib.util.spec_from_file_location("make_pins_under_test", MAKER)
mp = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mp                 # the maker uses dataclasses, which look their own module up by name
spec.loader.exec_module(mp)

COMMIT = "0123456789abcdef0123456789abcdef01234567"
BIG = "ab" * 32
BIG2 = "cd" * 32
SMALL_BODY = b'{"alignment_heads": []}'


def entry(path, size, lfs=None, kind="file"):
    raw = {"type": kind, "oid": "f" * 40, "path": path}
    if kind == "file":
        raw["size"] = size
    if lfs:
        raw["lfs"] = {"oid": lfs, "size": size, "pointerSize": 134}
    return raw


MODEL_TREE = [entry("config.json", len(SMALL_BODY)), entry("README.md", 900), entry("model.bin", 484_000_000, BIG), entry("tokenizer.json", 2_100_000),
              entry("vocabulary.txt", 800_000), entry(".gitattributes", 100), entry("extra", 0, kind="directory")]
VOICE_TREE = [entry("en/en_US/mike/medium/epoch=5449-step=2000000.ckpt", 845_890_641, BIG2), entry("en/en_US/mike/medium/config.json", 4_000),
              entry("en/en_US/mike/medium/MODEL_CARD", 1_200), entry("en/en_US/mike/low/epoch=1-step=2.ckpt", 5, "ee" * 32)]


class FakeHub:
    def __init__(self, trees, headers=None, bodies=None, commit=COMMIT):
        self.trees, self.headers, self.bodies, self.commit_sha = trees, headers or {}, bodies or {}, commit
        self.calls = []

    def commit(self, repo, revision):
        self.calls.append(("commit", repo, revision))
        return self.commit_sha

    def tree(self, repo, commit, directory):
        self.calls.append(("tree", repo, commit, directory))
        return json.dumps(self.trees[repo])

    def linked(self, repo, commit, path):
        self.calls.append(("linked", repo, path))
        return self.headers.get(path, {})

    def hash_of(self, repo, commit, path):
        self.calls.append(("hash", repo, path))
        body = self.bodies[path]
        return hashlib.sha256(body).hexdigest(), len(body)


def agreeing(tree):
    return {e["path"]: {"x-linked-etag": '"%s"' % e["lfs"]["oid"], "x-linked-size": str(e["size"])} for e in tree if e.get("lfs")}


MODEL_SPEC = {"id": "speech-model-small-en", "kind": "model", "why_key": "fetch.why.speech_model", "license_id": "whisper-mit", "repo": "Systran/faster-whisper-small.en",
              "revision": "main", "directory": "", "folder": "speech-small-en", "id_per_file": True,
              "files": ["config.json", "preprocessor_config.json", "model.bin", "tokenizer.json", "vocabulary.*"], "optional": ["preprocessor_config.json"]}
VOICE_SPEC = {"id": "voice-mike", "kind": "voice", "why_key": "fetch.why.voice_mike", "license_id": "voice-mike-card", "approx_size_bytes": 846_000_000,
              "repo": "datasets/rhasspy/piper-checkpoints", "revision": "main", "directory": "en/en_US/mike/medium", "files": ["*.ckpt"]}


def model_hub():
    return FakeHub({MODEL_SPEC["repo"]: MODEL_TREE}, agreeing(MODEL_TREE),
                   {"config.json": SMALL_BODY, "tokenizer.json": b"t" * 2_100_000, "vocabulary.txt": b"v" * 800_000})


# ---------------------------------------------------------------- reading the listing

def test_a_listing_gives_the_files_with_their_sizes_and_the_hosts_own_sha256_for_large_ones():
    files = {e.path: e for e in mp.parse_tree(json.dumps(MODEL_TREE))}
    assert "extra" not in files and len(files) == 6                      # a folder is not a file
    assert files["model.bin"] == mp.Entry("model.bin", 484_000_000, BIG) and files["config.json"].lfs_sha256 is None


@pytest.mark.parametrize("text, said", [("nope", "not JSON"), ('{"a": 1}', "not a list"), ('[{"path": "a"}]', "no type or path"), ('[{"type": "file"}]', "no type or path"),
                                        ('[{"type": "file", "path": "a"}]', "no usable size"), ('[{"type": "file", "path": "a", "size": 0}]', "no usable size"),
                                        ('[{"type": "file", "path": "a", "size": true}]', "no usable size"),
                                        ('[{"type": "file", "path": "a", "size": 5, "lfs": {"oid": "short"}}]', "no SHA-256"),
                                        ('[{"type": "file", "path": "a", "size": 5, "lfs": {"oid": "%s", "size": 6}}]' % BIG, "two sizes"),
                                        ('[{"type": "file", "path": "a", "size": 5, "lfs": "x"}]', "no SHA-256"), ('[5]', "no type or path")])
def test_a_listing_in_a_shape_it_does_not_know_is_refused_with_what_was_received(text, said):
    with pytest.raises(mp.PinError, match=said):
        mp.parse_tree(text)


def test_a_large_file_entry_without_its_own_size_is_still_read_from_the_top_level_size():
    (only,) = mp.parse_tree(json.dumps([{"type": "file", "path": "a", "size": 5, "lfs": {"oid": BIG}}]))
    assert only == mp.Entry("a", 5, BIG)


def test_the_next_page_of_a_long_listing_is_found_in_the_link_header():
    assert mp.next_page('<https://h/api/x?cursor=abc>; rel="next"') == "https://h/api/x?cursor=abc"
    assert mp.next_page('<https://h/a>; rel="prev", <https://h/b>; rel="next"') == "https://h/b"
    assert mp.next_page('<https://h/a>; rel="prev"') is None and mp.next_page(None) is None and mp.next_page("") is None


# ---------------------------------------------------------------- choosing files

def entries(tree):
    return mp.parse_tree(json.dumps(tree))


def test_only_files_directly_in_the_folder_whose_names_match_are_chosen():
    chosen = mp.select(entries(VOICE_TREE), "en/en_US/mike/medium", "*.ckpt")
    assert [e.path for e in chosen] == ["en/en_US/mike/medium/epoch=5449-step=2000000.ckpt"]        # not the one in /low


def test_the_top_of_a_repository_and_a_folder_with_slashes_are_both_understood():
    assert [e.name for e in mp.select(entries(MODEL_TREE), "", "vocabulary.*")] == ["vocabulary.txt"]
    assert [e.name for e in mp.select(entries(VOICE_TREE), "/en/en_US/mike/medium/", "MODEL_CARD")] == ["MODEL_CARD"]


def test_a_file_in_a_deeper_folder_is_not_matched_by_the_folder_above():
    tree = [entry("a/b/model.bin", 5), entry("a/model.bin", 5)]
    assert [e.path for e in mp.select(entries(tree), "a", "model.bin")] == ["a/model.bin"]


def test_a_pattern_is_case_sensitive_and_results_are_sorted():
    tree = [entry("z.ckpt", 5), entry("a.ckpt", 5), entry("B.CKPT", 5)]
    assert [e.name for e in mp.select(entries(tree), "", "*.ckpt")] == ["a.ckpt", "z.ckpt"]


def test_ids_for_a_model_of_several_files_name_each_file_and_a_single_file_keeps_the_id():
    model = mp.Entry("tokenizer.json", 5, None)
    assert mp.item_id(MODEL_SPEC, model) == "speech-model-small-en-tokenizer-json"
    assert mp.item_id(VOICE_SPEC, mp.Entry("x/epoch=5449-step=1.ckpt", 5, None)) == "voice-mike"
    with pytest.raises(mp.PinError):
        mp.item_id(dict(MODEL_SPEC, id="a" * 60), mp.Entry("model.bin", 5, None))              # more than 64 characters


def test_an_address_names_the_commit_and_keeps_the_equals_sign_of_a_checkpoints_name():
    assert mp.address("r/o", COMMIT, "en/x/epoch=5449-step=1.ckpt") == "https://huggingface.co/r/o/resolve/%s/en/x/epoch=5449-step=1.ckpt" % COMMIT
    assert mp.address("r/o", COMMIT, "a b#c.bin").endswith("/a%20b%23c.bin")


def test_a_model_and_a_dataset_are_asked_for_in_their_own_places_and_downloaded_from_their_own_addresses():
    assert mp.api_base("Org/model") == mp.HOST + "/api/models/Org/model"
    assert mp.api_base("datasets/Org/data") == mp.HOST + "/api/datasets/Org/data"
    assert mp.address("Org/model", COMMIT, "a.bin") == "%s/Org/model/resolve/%s/a.bin" % (mp.HOST, COMMIT)
    assert mp.address("datasets/Org/data", COMMIT, "d/a.bin") == "%s/datasets/Org/data/resolve/%s/d/a.bin" % (mp.HOST, COMMIT)


def test_a_dataset_entry_is_pinned_by_the_apps_own_rules_with_its_dataset_address():
    item = mp.build_item(VOICE_SPEC, mp.Entry("en/en_US/mike/medium/epoch=5460-val_mos=4.2686.ckpt", 845_891_981, None), COMMIT, BIG2, 845_891_981)
    assert item["url"] == "https://huggingface.co/datasets/rhasspy/piper-checkpoints/resolve/%s/en/en_US/mike/medium/epoch=5460-val_mos=4.2686.ckpt" % COMMIT
    assert item["filename"] == "epoch=5460-val_mos=4.2686.ckpt" and reg.parse_registry(json.dumps({"schema": 1, "items": [item]})).items[0].pinned


# ---------------------------------------------------------------- entries the app accepts

def test_a_built_entry_is_fully_pinned_by_the_apps_own_rules():
    item = mp.build_item(MODEL_SPEC, mp.Entry("model.bin", 484_000_000, BIG), COMMIT, BIG, 484_000_000)
    assert item == {"id": "speech-model-small-en-model-bin", "kind": "model", "why_key": "fetch.why.speech_model", "license_id": "whisper-mit",
                    "approx_size_bytes": 484_000_000, "folder": "speech-small-en", "filename": "model.bin",
                    "url": "https://huggingface.co/Systran/faster-whisper-small.en/resolve/%s/model.bin" % COMMIT, "revision": COMMIT, "size_bytes": 484_000_000, "sha256": BIG}
    registry = reg.parse_registry(json.dumps({"schema": 1, "items": [item]}))
    assert registry.get(item["id"]).pinned and registry.get(item["id"]).pin_problems() == []


def test_a_voice_keeps_the_round_number_the_host_shows_for_the_disk_estimate_and_gets_the_exact_size_once_pinned():
    item = mp.build_item(VOICE_SPEC, mp.Entry("en/en_US/mike/medium/epoch=5449-step=2000000.ckpt", 845_890_641, BIG2), COMMIT, BIG2, 845_890_641)
    assert item["approx_size_bytes"] == 846_000_000 and item["size_bytes"] == 845_890_641 and "folder" not in item
    assert item["filename"] == "epoch=5449-step=2000000.ckpt" and reg.parse_registry(json.dumps({"schema": 1, "items": [item]})).items[0].pinned


@pytest.mark.parametrize("commit, sha, size, name", [("main", BIG, 5, "a.bin"), (COMMIT[:39], BIG, 5, "a.bin"), (COMMIT, "xyz", 5, "a.bin"), (COMMIT, BIG.upper(), 5, "a.bin"),
                                                    (COMMIT, BIG, 0, "a.bin"), (COMMIT, BIG, 5, "../a.bin"), (COMMIT, BIG, 5, "a b.bin"), (COMMIT, BIG, 5, "-a.bin"), (COMMIT, BIG, 5, "./a.bin"), (COMMIT, BIG, 5, "x//a.bin"), (COMMIT, BIG, 5, "a..b.bin")])
def test_an_entry_the_app_would_refuse_is_never_written(commit, sha, size, name):
    with pytest.raises(mp.PinError):
        mp.build_item(VOICE_SPEC, mp.Entry("d/" + name, 5, None), commit, sha, size)


# ---------------------------------------------------------------- the second view of a large file

@pytest.mark.parametrize("headers, result", [({"x-linked-etag": '"%s"' % BIG, "x-linked-size": "10"}, "agreed"), ({"x-linked-etag": 'W/"%s"' % BIG, "x-linked-size": "10"}, "agreed"),
                                             ({"x-linked-etag": BIG.upper(), "x-linked-size": "10"}, "agreed"), ({}, "not stated"),
                                             ({"x-linked-etag": BIG}, "agreed"), ({"x-linked-size": "10"}, "agreed")])
def test_the_download_address_agreeing_with_the_listing_is_noted_and_silence_is_noted_too(headers, result):
    assert mp.cross_check(mp.Entry("a", 10, BIG), headers) == result


@pytest.mark.parametrize("headers", [{"x-linked-etag": '"%s"' % BIG2, "x-linked-size": "10"}, {"x-linked-etag": '"%s"' % BIG, "x-linked-size": "11"}, {"x-linked-size": "9"},
                                     {"x-linked-etag": '"%s"' % BIG2}])
def test_the_two_views_disagreeing_stops_everything(headers):
    with pytest.raises(mp.PinError):
        mp.cross_check(mp.Entry("a", 10, BIG), headers)


# ---------------------------------------------------------------- one wanted thing

def test_a_model_of_several_files_pins_each_one_and_hashes_the_small_ones_itself():
    hub = model_hub()
    pinned = mp.pin_spec(MODEL_SPEC, hub, {})
    by_id = {p.item["id"]: p for p in pinned}
    assert sorted(by_id) == ["speech-model-small-en-config-json", "speech-model-small-en-model-bin", "speech-model-small-en-tokenizer-json", "speech-model-small-en-vocabulary-txt"]
    assert by_id["speech-model-small-en-model-bin"].item["sha256"] == BIG and "agreed" in by_id["speech-model-small-en-model-bin"].how
    small = by_id["speech-model-small-en-config-json"]
    assert small.item["sha256"] == hashlib.sha256(SMALL_BODY).hexdigest() and small.how == "downloaded and hashed here"
    assert all(p.item["revision"] == COMMIT and COMMIT in p.item["url"] and p.item["folder"] == "speech-small-en" for p in pinned)
    assert ("commit", "Systran/faster-whisper-small.en", "main") in hub.calls


def test_a_missing_optional_file_is_skipped_and_a_missing_required_one_stops_with_what_the_folder_holds():
    pinned = mp.pin_spec(MODEL_SPEC, model_hub(), {})
    assert not any("preprocessor" in p.item["id"] for p in pinned)
    hub = FakeHub({MODEL_SPEC["repo"]: [e for e in MODEL_TREE if e["path"] != "model.bin"]}, {}, {"config.json": SMALL_BODY, "tokenizer.json": b"t" * 2_100_000, "vocabulary.txt": b"v" * 800_000})
    with pytest.raises(mp.PinError) as caught:
        mp.pin_spec(MODEL_SPEC, hub, {})
    assert "model.bin" in str(caught.value) and "config.json" in str(caught.value)


def test_a_small_file_whose_download_is_not_the_size_the_listing_gave_is_refused():
    hub = model_hub()
    hub.bodies["config.json"] = SMALL_BODY + b"x"
    with pytest.raises(mp.PinError, match="listing says"):
        mp.pin_spec(MODEL_SPEC, hub, {})


def test_a_large_file_where_the_two_views_disagree_is_refused():
    hub = model_hub()
    hub.headers["model.bin"] = {"x-linked-etag": '"%s"' % BIG2}
    with pytest.raises(mp.PinError, match="download address says"):
        mp.pin_spec(MODEL_SPEC, hub, {})


def test_a_voice_is_one_checkpoint_and_its_folder_is_asked_for_by_name():
    hub = FakeHub({VOICE_SPEC["repo"]: VOICE_TREE}, agreeing(VOICE_TREE))
    (pinned,) = mp.pin_spec(VOICE_SPEC, hub, {})
    assert pinned.item["id"] == "voice-mike" and pinned.item["filename"] == "epoch=5449-step=2000000.ckpt" and pinned.item["sha256"] == BIG2
    assert ("tree", "datasets/rhasspy/piper-checkpoints", COMMIT, "en/en_US/mike/medium") in hub.calls


def test_two_checkpoints_are_never_guessed_between_and_a_pick_settles_it():
    tree = VOICE_TREE + [entry("en/en_US/mike/medium/epoch=6000-step=3000000.ckpt", 845_890_641, "12" * 32)]
    hub = FakeHub({VOICE_SPEC["repo"]: tree}, agreeing(tree))
    with pytest.raises(mp.NeedsChoice) as caught:
        mp.pin_spec(VOICE_SPEC, hub, {})
    assert [e.name for e in caught.value.candidates] == ["epoch=5449-step=2000000.ckpt", "epoch=6000-step=3000000.ckpt"]
    (pinned,) = mp.pin_spec(VOICE_SPEC, hub, {"voice-mike": "epoch=6000-step=3000000.ckpt"})
    assert pinned.item["filename"] == "epoch=6000-step=3000000.ckpt" and pinned.item["sha256"] == "12" * 32


def test_a_pick_that_matches_nothing_is_an_error_not_a_quiet_choice_of_another_file():
    hub = FakeHub({VOICE_SPEC["repo"]: VOICE_TREE}, agreeing(VOICE_TREE))
    with pytest.raises(mp.PinError, match="nothing named"):
        mp.pin_spec(VOICE_SPEC, hub, {"voice-mike": "nope.ckpt"})


def test_a_folder_with_no_checkpoint_says_what_it_does_hold():
    hub = FakeHub({VOICE_SPEC["repo"]: [entry("en/en_US/mike/medium/config.json", 5)]}, {})
    with pytest.raises(mp.PinError) as caught:
        mp.pin_spec(VOICE_SPEC, hub, {})
    assert "nothing named '*.ckpt'" in str(caught.value) and "config.json" in str(caught.value)


def test_a_single_file_spec_that_would_take_two_files_is_refused():
    with pytest.raises(mp.PinError, match="names one file"):
        mp.pin_spec(dict(VOICE_SPEC, files=["*.ckpt", "MODEL_CARD"]), FakeHub({VOICE_SPEC["repo"]: VOICE_TREE}, agreeing(VOICE_TREE)), {})


def test_a_large_file_is_not_downloaded_here():
    hub = model_hub()
    mp.pin_spec(MODEL_SPEC, hub, {})
    assert ("hash", "Systran/faster-whisper-small.en", "model.bin") not in hub.calls


def test_a_model_spec_that_carries_a_round_number_still_gets_each_files_exact_size():
    item = mp.build_item(dict(MODEL_SPEC, approx_size_bytes=480_000_000), mp.Entry("config.json", 23, None), COMMIT, BIG, 23)
    assert item["approx_size_bytes"] == 23 and item["size_bytes"] == 23


def test_a_model_takes_every_file_a_pattern_matches_and_each_becomes_its_own_entry():
    tree = MODEL_TREE + [entry("vocabulary.json", 700_000)]
    hub = FakeHub({MODEL_SPEC["repo"]: tree}, agreeing(tree), {"config.json": SMALL_BODY, "tokenizer.json": b"t" * 2_100_000, "vocabulary.txt": b"v" * 800_000,
                                                              "vocabulary.json": b"j" * 700_000})
    ids = sorted(p.item["id"] for p in mp.pin_spec(MODEL_SPEC, hub, {}))
    assert "speech-model-small-en-vocabulary-txt" in ids and "speech-model-small-en-vocabulary-json" in ids


def test_a_spec_whose_every_file_is_optional_and_absent_pins_nothing_and_says_so():
    spec = dict(MODEL_SPEC, files=["preprocessor_config.json"], optional=["preprocessor_config.json"])
    with pytest.raises(mp.PinError, match="no files were chosen"):
        mp.pin_spec(spec, model_hub(), {})


def test_a_spec_with_no_revision_asks_for_the_main_branch():
    spec = {k: v for k, v in MODEL_SPEC.items() if k != "revision"}
    hub = model_hub()
    mp.pin_spec(spec, hub, {})
    assert ("commit", "Systran/faster-whisper-small.en", "main") in hub.calls
    hub = model_hub()
    mp.pin_spec(dict(spec, revision="v1"), hub, {})
    assert ("commit", "Systran/faster-whisper-small.en", "v1") in hub.calls


# ---------------------------------------------------------------- the registry

REGISTRY = json.dumps({"schema": 1, "note": "n", "items": [
    {"id": "voice-mike", "kind": "voice", "why_key": "fetch.why.voice_mike", "license_id": "voice-mike-card", "approx_size_bytes": 846000000, "filename": None, "url": None,
     "revision": None, "size_bytes": None, "sha256": None},
    {"id": "speech-model-small-en", "kind": "model", "why_key": "fetch.why.speech_model", "license_id": "whisper-mit", "approx_size_bytes": 480000000, "folder": "speech-small-en",
     "filename": None, "url": None, "revision": None, "size_bytes": None, "sha256": None},
    {"id": "other", "kind": "file", "why_key": "fetch.why.x", "license_id": "x", "approx_size_bytes": 5}]})


def pinned_items():
    return [p.item for p in mp.pin_spec(MODEL_SPEC, model_hub(), {})] + [p.item for p in mp.pin_spec(VOICE_SPEC, FakeHub({VOICE_SPEC["repo"]: VOICE_TREE}, agreeing(VOICE_TREE)), {})]


def test_merging_replaces_in_place_adds_at_the_end_drops_the_old_placeholder_and_touches_nothing_else():
    merged = json.loads(mp.merge_registry(REGISTRY, pinned_items(), ["speech-model-small-en"]))
    ids = [i["id"] for i in merged["items"]]
    assert ids[0] == "voice-mike" and "speech-model-small-en" not in ids and ids[1] == "other"
    assert ids[2:] == ["speech-model-small-en-config-json", "speech-model-small-en-model-bin", "speech-model-small-en-tokenizer-json", "speech-model-small-en-vocabulary-txt"]
    assert merged["items"][1] == json.loads(REGISTRY)["items"][2] and merged["note"] == "n" and merged["schema"] == 1


def test_what_is_merged_loads_in_the_app_and_every_new_entry_is_pinned():
    merged = reg.parse_registry(mp.merge_registry(REGISTRY, pinned_items(), ["speech-model-small-en"]))
    assert merged.get("voice-mike").pinned and merged.get("speech-model-small-en-model-bin").pinned and not merged.get("other").pinned


def test_merging_twice_gives_the_same_registry():
    once = mp.merge_registry(REGISTRY, pinned_items(), ["speech-model-small-en"])
    assert mp.merge_registry(once, pinned_items(), ["speech-model-small-en"]) == once


def test_two_new_entries_with_the_same_id_and_a_registry_in_another_shape_are_refused():
    items = pinned_items()
    with pytest.raises(mp.PinError):
        mp.merge_registry(REGISTRY, items + [items[0]])
    with pytest.raises(mp.PinError):
        mp.merge_registry('{"items": 5}', items)


# ---------------------------------------------------------------- the command line

def write_wanted(tmp_path, specs):
    path = tmp_path / "wanted.json"
    path.write_text(json.dumps({"schema": 1, "specs": specs}))
    return path


def run(argv, hub=None):
    said = []
    code = mp.main(argv, hub, said.append)
    return code, "\n".join(said)


def test_pin_writes_every_entry_and_says_where_each_checksum_came_from(tmp_path):
    wanted = write_wanted(tmp_path, [dict(MODEL_SPEC, replaces=["speech-model-small-en"])])
    code, out = run(["pin", "--wanted", str(wanted), "--out", str(tmp_path / "pins.json")], model_hub())
    pins = json.loads((tmp_path / "pins.json").read_text())
    assert code == 0 and len(pins["items"]) == 4 and pins["drop"] == ["speech-model-small-en"]
    assert "downloaded and hashed here" in out and "agreed" in out and "Wrote 4 entries" in out


def test_pin_that_needs_a_choice_prints_the_candidates_writes_nothing_and_exits_with_three(tmp_path):
    tree = VOICE_TREE + [entry("en/en_US/mike/medium/epoch=6000-step=3000000.ckpt", 845_890_641, "12" * 32)]
    hub = FakeHub({VOICE_SPEC["repo"]: tree}, agreeing(tree))
    code, out = run(["pin", "--wanted", str(write_wanted(tmp_path, [VOICE_SPEC])), "--out", str(tmp_path / "pins.json")], hub)
    assert code == 3 and not (tmp_path / "pins.json").exists()
    assert "epoch=5449-step=2000000.ckpt" in out and "epoch=6000-step=3000000.ckpt" in out and "--pick voice-mike=FILENAME" in out


def test_pin_with_a_pick_goes_through(tmp_path):
    tree = VOICE_TREE + [entry("en/en_US/mike/medium/epoch=6000-step=3000000.ckpt", 845_890_641, "12" * 32)]
    hub = FakeHub({VOICE_SPEC["repo"]: tree}, agreeing(tree))
    code, _ = run(["pin", "--wanted", str(write_wanted(tmp_path, [VOICE_SPEC])), "--out", str(tmp_path / "p.json"), "--pick", "voice-mike=epoch=6000-step=3000000.ckpt"], hub)
    assert code == 0 and json.loads((tmp_path / "p.json").read_text())["items"][0]["filename"] == "epoch=6000-step=3000000.ckpt"


def test_a_failure_part_way_writes_nothing_at_all(tmp_path):
    hub = FakeHub({MODEL_SPEC["repo"]: MODEL_TREE, VOICE_SPEC["repo"]: [entry("en/en_US/mike/medium/config.json", 5)]}, agreeing(MODEL_TREE),
                  {"config.json": SMALL_BODY, "tokenizer.json": b"t" * 2_100_000, "vocabulary.txt": b"v" * 800_000})
    code, out = run(["pin", "--wanted", str(write_wanted(tmp_path, [MODEL_SPEC, VOICE_SPEC])), "--out", str(tmp_path / "pins.json")], hub)
    assert code == 1 and out.splitlines()[-1].startswith("Nothing was written.") and not (tmp_path / "pins.json").exists()


def test_a_wanted_list_with_nothing_in_it_writes_nothing(tmp_path):
    code, out = run(["pin", "--wanted", str(write_wanted(tmp_path, [])), "--out", str(tmp_path / "pins.json")], model_hub())
    assert code == 1 and "nothing was pinned" in out and not (tmp_path / "pins.json").exists()


def test_only_limits_the_run_and_an_unknown_name_is_an_error(tmp_path):
    wanted = write_wanted(tmp_path, [MODEL_SPEC, VOICE_SPEC])
    hub = FakeHub({MODEL_SPEC["repo"]: MODEL_TREE}, agreeing(MODEL_TREE), {"config.json": SMALL_BODY, "tokenizer.json": b"t" * 2_100_000, "vocabulary.txt": b"v" * 800_000})
    code, _ = run(["pin", "--wanted", str(wanted), "--out", str(tmp_path / "p.json"), "--only", "speech-model-small-en"], hub)
    assert code == 0 and len(json.loads((tmp_path / "p.json").read_text())["items"]) == 4
    code, out = run(["pin", "--wanted", str(wanted), "--out", str(tmp_path / "q.json"), "--only", "nope"], hub)
    assert code == 1 and "nope" in out and not (tmp_path / "q.json").exists()


def test_list_shows_the_commit_each_file_with_its_kind_and_the_folders_to_look_into(tmp_path):
    code, out = run(["list", MODEL_SPEC["repo"]], model_hub())
    assert code == 0 and COMMIT in out and "model.bin" in out and "large file" in out and "small file" in out
    assert "extra/" in out and "folder" in out                                    # a folder is shown, so the person can look inside it


def test_list_of_an_empty_place_says_so():
    code, out = run(["list", "x/y", "nothing"], FakeHub({"x/y": []}))
    assert code == 0 and "nothing directly in nothing" in out


def test_folders_of_a_listing_in_another_shape_are_none():
    assert mp.folders("nope") == [] and mp.folders('{"a": 1}') == [] and mp.folders('[1, {"type": "directory"}]') == []
    assert mp.folders(json.dumps(MODEL_TREE)) == ["extra"]


def test_merge_puts_the_pins_into_a_registry_file(tmp_path):
    registry = tmp_path / "sources.json"
    registry.write_text(REGISTRY)
    pins = tmp_path / "pins.json"
    pins.write_text(json.dumps({"schema": 1, "items": pinned_items(), "drop": ["speech-model-small-en"]}))
    code, out = run(["merge", str(pins), "--registry", str(registry)])
    assert code == 0 and "removed: speech-model-small-en" in out
    merged = reg.parse_registry(registry.read_text())
    assert merged.get("speech-model-small-en-model-bin").pinned
    assert "speech-model-small-en" not in [i.id for i in merged.items]                       # the old placeholder is gone


def test_merge_of_a_file_this_did_not_write_changes_nothing(tmp_path):
    registry = tmp_path / "sources.json"
    registry.write_text(REGISTRY)
    pins = tmp_path / "pins.json"
    pins.write_text('{"x": 1}')
    code, out = run(["merge", str(pins), "--registry", str(registry)])
    assert code == 1 and registry.read_text() == REGISTRY and out.startswith("Nothing was written.")


# ---------------------------------------------------------------- the wanted list that ships

def test_the_shipped_wanted_list_loads_and_names_the_speech_model_and_both_voices():
    specs = mp.load_wanted(mp.WANTED.read_text(encoding="utf-8"))
    assert [s["id"] for s in specs] == ["speech-model-small-en", "voice-mike", "voice-amy"]
    ids = {i.id for i in reg.load_registry().items}
    for s in specs:
        assert reg.SLUG.match(s["license_id"]) and s["files"] and s["repo"].removeprefix("datasets/").count("/") == 1 and s["kind"] in reg.KINDS


def test_the_speech_model_asks_for_exactly_the_files_the_listening_library_downloads_for_itself():
    model = next(s for s in mp.load_wanted(mp.WANTED.read_text(encoding="utf-8")) if s["id"] == "speech-model-small-en")
    assert model["files"] == ["config.json", "preprocessor_config.json", "model.bin", "tokenizer.json", "vocabulary.*"]
    assert model["optional"] == ["preprocessor_config.json"] and model["id_per_file"] is True and model["folder"] == "speech-small-en"
    assert model["replaces"] == ["speech-model-small-en"] and model["repo"] == "Systran/faster-whisper-small.en"


def test_the_voices_are_the_medium_quality_checkpoints_of_the_two_named_voices():
    voices = {s["id"]: s for s in mp.load_wanted(mp.WANTED.read_text(encoding="utf-8")) if s["kind"] == "voice"}
    assert voices["voice-mike"]["directory"] == "en/en_US/mike/medium" and voices["voice-amy"]["directory"] == "en/en_US/amy/medium"
    assert all(v["repo"] == "datasets/rhasspy/piper-checkpoints" and v["files"] == ["*.ckpt"] and v["approx_size_bytes"] == 846_000_000 for v in voices.values())


@pytest.mark.parametrize("text", ['{"schema": 2, "specs": []}', '{"schema": 1}', '{"schema": 1, "specs": [{"id": "a"}]}', 'nope'])
def test_a_wanted_list_in_another_shape_is_refused(text):
    with pytest.raises((mp.PinError, ValueError)):
        mp.load_wanted(text)


def test_a_wanted_list_naming_an_id_twice_is_refused(tmp_path):
    with pytest.raises(mp.PinError, match="twice"):
        mp.load_wanted(write_wanted(tmp_path, [VOICE_SPEC, VOICE_SPEC]).read_text())


# ---------------------------------------------------------------- the part that talks to the host, against a local stand-in for it

class HostStandIn:
    """Answers the host's routes on this computer: a branch becomes a commit, a listing comes in two pages, and a download address redirects (to "the CDN")."""

    def __init__(self):
        self.requests, self.fail_with = [], {}
        stand_in = self
        files = {"/Org/model/resolve/%s/model.bin" % COMMIT: b"B" * 1000, "/Org/model/resolve/%s/config.json" % COMMIT: SMALL_BODY,
                 "/Org/model/resolve/%s/dir/sub file.txt" % COMMIT: b"spaces"}
        self.files = files

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def reply(self, status, body=b"", headers=None):
                self.send_response(status)
                for key, value in (headers or {}).items():
                    self.send_header(key, value)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                if self.command != "HEAD":
                    self.wfile.write(body)

            def serve(self):
                path = self.path
                stand_in.requests.append((self.command, path))
                if path in stand_in.fail_with:
                    return self.reply(stand_in.fail_with[path])
                if path == "/api/models/Org/model/revision/main":
                    return self.reply(200, json.dumps({"id": "Org/model", "sha": COMMIT}).encode(), {"Content-Type": "application/json"})
                if path == "/api/datasets/Org/data/revision/main":
                    return self.reply(200, json.dumps({"id": "Org/data", "sha": COMMIT}).encode())
                if path == "/api/models/Org/model/revision/odd":
                    return self.reply(200, json.dumps({"id": "Org/model"}).encode())
                if path == "/api/models/Org/model/tree/%s" % COMMIT:
                    page = json.dumps([entry("config.json", len(SMALL_BODY)), entry("model.bin", 1000, "ab" * 32)]).encode()
                    return self.reply(200, page, {"Link": '<http://127.0.0.1:%d/api/models/Org/model/tree/%s?cursor=2>; rel="next"' % (self.server.server_port, COMMIT)})
                if path == "/api/models/Org/model/tree/%s?cursor=2" % COMMIT:
                    return self.reply(200, json.dumps([entry("tokenizer.json", 5)]).encode())
                if path == "/api/models/Org/model/tree/%s/dir" % COMMIT:
                    return self.reply(200, json.dumps([entry("dir/sub file.txt", 6)]).encode())
                plain = urllib.parse.unquote(path)
                if plain in stand_in.files and not path.startswith("/cdn"):
                    headers = {"Location": "/cdn" + path}
                    if path.endswith("model.bin"):
                        headers.update({"X-Linked-ETag": '"%s"' % ("ab" * 32), "X-Linked-Size": "1000"})
                    return self.reply(302, b"", headers)
                if path.startswith("/cdn") and plain[len("/cdn"):] in stand_in.files:
                    return self.reply(200, stand_in.files[plain[len("/cdn"):]])
                return self.reply(404, b"no")

            do_GET = do_HEAD = serve

        class Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
            daemon_threads = True
            allow_reuse_address = True

        self.server = Server(("127.0.0.1", 0), Handler)
        self.address = "http://127.0.0.1:%d" % self.server.server_port
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()


@pytest.fixture
def host(monkeypatch):
    stand_in = HostStandIn()
    monkeypatch.setattr(mp, "HOST", stand_in.address)
    yield stand_in
    stand_in.close()


def test_a_branch_becomes_the_commit_it_points_at(host):
    assert mp.Hub().commit("Org/model", "main") == COMMIT
    assert ("GET", "/api/models/Org/model/revision/main") in host.requests


def test_a_reply_with_no_commit_is_an_error_that_shows_what_came(host):
    with pytest.raises(mp.PinError, match="gave no commit"):
        mp.Hub().commit("Org/model", "odd")


def test_a_listing_in_two_pages_is_read_to_the_end(host):
    names = [e.name for e in mp.parse_tree(mp.Hub().tree("Org/model", COMMIT, ""))]
    assert names == ["config.json", "model.bin", "tokenizer.json"]


def test_a_folder_name_with_spaces_is_asked_for_properly_and_a_slash_at_either_end_is_ignored(host):
    mp.Hub().tree("Org/model", COMMIT, "/dir/")
    assert ("GET", "/api/models/Org/model/tree/%s/dir" % COMMIT) in host.requests


def test_the_download_addresss_own_headers_are_read_without_following_it_anywhere(host):
    headers = mp.Hub().linked("Org/model", COMMIT, "model.bin")
    assert headers["x-linked-etag"] == '"%s"' % ("ab" * 32) and headers["x-linked-size"] == "1000"
    assert [r for r in host.requests if r[1].startswith("/cdn")] == []                        # it stopped at the redirect


def test_a_file_is_followed_through_the_redirect_and_hashed_while_it_streams(host):
    sha, size = mp.Hub().hash_of("Org/model", COMMIT, "config.json")
    assert (sha, size) == (hashlib.sha256(SMALL_BODY).hexdigest(), len(SMALL_BODY))
    assert mp.Hub().hash_of("Org/model", COMMIT, "dir/sub file.txt")[1] == 6                   # a name with a space is quoted on the way out


def test_the_host_saying_no_or_being_unreachable_is_a_plain_error(host):
    host.fail_with["/api/models/Org/model/revision/main"] = 503
    with pytest.raises(mp.PinError, match="503"):
        mp.Hub().commit("Org/model", "main")
    probe = socket.socket()
    probe.bind(("127.0.0.1", 0))
    closed = probe.getsockname()[1]
    probe.close()
    import unittest.mock as mock
    with mock.patch.object(mp, "HOST", "http://127.0.0.1:%d" % closed):
        with pytest.raises(mp.PinError, match="could not reach"):
            mp.Hub().commit("Org/model", "main")


def test_a_missing_file_is_a_plain_error(host):
    with pytest.raises(mp.PinError, match="404"):
        mp.Hub().hash_of("Org/model", COMMIT, "nope.bin")
    with pytest.raises(mp.PinError, match="404"):
        mp.Hub().linked("Org/model", COMMIT, "nope.bin")


def test_a_whole_pin_through_the_real_hub_code_against_the_stand_in(host):
    spec = dict(MODEL_SPEC, repo="Org/model", files=["config.json", "model.bin"], optional=[])
    pinned = mp.pin_spec(spec, mp.Hub(), {})
    by_id = {p.item["id"]: p.item for p in pinned}
    assert by_id["speech-model-small-en-model-bin"]["sha256"] == "ab" * 32 and by_id["speech-model-small-en-model-bin"]["size_bytes"] == 1000
    assert by_id["speech-model-small-en-config-json"]["sha256"] == hashlib.sha256(SMALL_BODY).hexdigest()
    assert by_id["speech-model-small-en-model-bin"]["url"] == host.address + "/Org/model/resolve/%s/model.bin" % COMMIT


def test_a_dataset_is_asked_for_under_datasets_and_the_listing_comes_from_there(host):
    assert mp.Hub().commit("datasets/Org/data", "main") == COMMIT
    assert ("GET", "/api/datasets/Org/data/revision/main") in host.requests


# ---------------------------------------------------------------- pages to read before a voice is downloaded

PAGES = {"lessac": "https://example.org/licence.html", "mike": "https://github.com/example/recordings"}


def test_a_spec_with_pages_puts_them_on_the_entry_it_builds_and_the_app_loads_them():
    spec = {**VOICE_SPEC, "pages": PAGES}
    item = mp.build_item(spec, mp.Entry("en/en_US/mike/medium/epoch=5460-val_mos=4.2686.ckpt", 845_891_981, None), COMMIT, BIG2, 845_891_981)
    assert item["pages"] == PAGES and item["pages"] is not spec["pages"]
    loaded = reg.parse_registry(json.dumps({"schema": 1, "items": [item]})).items[0]
    assert loaded.pinned and dict(loaded.pages) == PAGES


def test_a_spec_without_pages_builds_an_entry_without_the_field():
    item = mp.build_item(VOICE_SPEC, mp.Entry("en/en_US/mike/medium/epoch=5460-val_mos=4.2686.ckpt", 845_891_981, None), COMMIT, BIG2, 845_891_981)
    assert "pages" not in item


def test_pinning_again_does_not_drop_the_pages_of_a_voice_because_merge_replaces_a_whole_entry():
    """merge_registry puts the new entry where the old one stood, so anything the maker does not write is lost: the shipped wanted list must carry the pages."""
    shipped = json.loads((PKG / "data" / "sources.json").read_text(encoding="utf-8"))
    wanted = {s["id"]: s for s in mp.load_wanted(mp.WANTED.read_text(encoding="utf-8"))}
    for entry in shipped["items"]:
        if entry["kind"] == "voice":
            assert wanted[entry["id"]].get("pages") == entry["pages"], entry["id"]
            rebuilt = mp.build_item(wanted[entry["id"]], mp.Entry("en/en_US/x/medium/" + entry["filename"], entry["size_bytes"], None), entry["revision"], entry["sha256"], entry["size_bytes"])
            assert rebuilt == {**entry, "url": rebuilt["url"]}, entry["id"]
            assert rebuilt["pages"] == entry["pages"]
