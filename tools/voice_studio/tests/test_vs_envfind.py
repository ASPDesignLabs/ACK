# SPDX-License-Identifier: GPL-3.0-or-later
"""Finding the studio and training programs and the listening model the guided setup left: looking only (nothing is built, fetched or written), the answer is "ready" only when every file is
there and byte for byte what was agreed to, and the one lookup serves the training programs and the studio programs alike."""
import hashlib
import os
from dataclasses import replace
from pathlib import Path as Path_

import pytest

from vs_fakes import FakeSystem
from vs_fetch_helpers import pinned_item
import vs_envfind_hub as hubmaker
from vs_envfind_hub import A, B, REV, model_file, registry_for
from voice_studio import rounds as rounds_front
from voice_studio.core import envfind
from voice_studio.core.envspec import load_environments
from voice_studio.core.paths import DataHome
from voice_studio.core.registry import Registry, load_registry
from urllib.parse import urlparse

GIB = 2 ** 30
NO_ENV = {}                                  # the lookup is given an empty environment, so it never reads the machine the tests run on


def put(home, name, payload, folder=envfind.SPEECH_FOLDER):
    path = os.path.join(home.downloads, "models", folder, name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as handle:
        handle.write(payload)
    return path


@pytest.fixture
def home(tmp_path):
    return DataHome(str(tmp_path / "home"))


# ---------------------------------------------------------------- the listening model

def test_the_folder_name_is_the_one_the_real_registry_keeps_the_speech_model_in():
    items = [i for i in load_registry().items if i.kind == "model" and i.folder == envfind.SPEECH_FOLDER]
    assert len(items) >= 1, "the listening model is pinned in the registry under this folder name"


def test_with_nothing_downloaded_the_model_is_missing_and_nothing_is_created(home):
    found, state = envfind.speech_model(home, load_registry(), NO_ENV)
    assert (found, state) == (None, "missing") and not os.path.exists(home.home)


def test_with_every_file_there_and_exact_the_model_is_ready_and_the_answer_is_its_folder(home):
    a, b = b"first part " * 200, b"second part " * 300
    registry = Registry((model_file(a, "a.bin"), model_file(b, "b.bin")))
    put(home, "a.bin", a)
    put(home, "b.bin", b)
    found, state = envfind.speech_model(home, registry, NO_ENV)
    assert state == "ready" and found == os.path.join(home.downloads, "models", envfind.SPEECH_FOLDER)


def test_one_file_missing_is_not_ready_and_is_called_incomplete(home):
    a, b = b"first part " * 200, b"second part " * 300
    registry = Registry((model_file(a, "a.bin"), model_file(b, "b.bin")))
    put(home, "a.bin", a)
    assert envfind.speech_model(home, registry, NO_ENV) == (None, "incomplete")


@pytest.mark.parametrize("change", ["shorter", "same_size_other_bytes", "longer"])
def test_a_file_that_is_not_what_was_agreed_to_is_not_ready_and_is_called_incomplete(home, change):
    a = b"first part " * 200
    registry = Registry((model_file(a, "a.bin"),))
    put(home, "a.bin", {"shorter": a[:-1], "same_size_other_bytes": bytes([a[0] ^ 1]) + a[1:], "longer": a + b"x"}[change])
    assert envfind.speech_model(home, registry, NO_ENV) == (None, "incomplete")


def test_a_folder_with_nothing_of_the_model_in_it_is_missing_not_incomplete(home):
    a = b"first part " * 200
    registry = Registry((model_file(a, "a.bin"),))
    os.makedirs(os.path.join(home.downloads, "models", envfind.SPEECH_FOLDER))
    put(home, "a.bin.part", a[:10])                                  # an interrupted download is not a finished file
    assert envfind.speech_model(home, registry, NO_ENV) == (None, "missing")


def test_a_registry_with_no_such_files_is_never_vacuously_ready(home):
    assert envfind.speech_model(home, Registry(()), NO_ENV) == (None, "missing")
    other = replace(pinned_item(), id="other", kind="model", folder="something-else", filename="x.bin")
    put(home, "x.bin", b"anything", folder="something-else")
    assert envfind.speech_model(home, Registry((other,)), NO_ENV) == (None, "missing")


def test_a_file_of_another_kind_or_folder_does_not_stand_in_for_the_model(home):
    a = b"first part " * 200
    voice = replace(model_file(a, "a.bin"), kind="voice")
    put(home, "a.bin", a)
    assert envfind.speech_model(home, Registry((voice,)), NO_ENV) == (None, "missing")


def test_a_link_in_place_of_the_file_is_not_the_file(home, tmp_path):
    a = b"first part " * 200
    registry = Registry((model_file(a, "a.bin"),))
    real = tmp_path / "elsewhere.bin"
    real.write_bytes(a)
    os.makedirs(os.path.join(home.downloads, "models", envfind.SPEECH_FOLDER))
    os.symlink(str(real), os.path.join(home.downloads, "models", envfind.SPEECH_FOLDER, "a.bin"))
    assert envfind.speech_model(home, registry, NO_ENV) == (None, "incomplete")


def test_looking_for_the_model_writes_nothing(home):
    a = b"first part " * 200
    registry = Registry((model_file(a, "a.bin"),))
    put(home, "a.bin", a[:10])
    before = sorted(os.listdir(os.path.join(home.downloads, "models", envfind.SPEECH_FOLDER)))
    envfind.speech_model(home, registry, NO_ENV)
    assert sorted(os.listdir(os.path.join(home.downloads, "models", envfind.SPEECH_FOLDER))) == before


# ---------------------------------------------------------------- the same model in the Hugging Face folder

def hub_registry(a, b, revision=REV):
    return registry_for(a, b, revision)


def put_hub(home, files, revision=REV, link=True, hub=None):
    return hubmaker.put_hub(hub or envfind.hf_hub_folder(home, NO_ENV), files, revision, link)


def test_the_hugging_face_folder_is_found_by_the_rules_those_tools_use(home):
    base = Path_(home.home)
    assert envfind.hf_hub_folder(home, {}) == base / ".cache" / "huggingface" / "hub"
    assert envfind.hf_hub_folder(home, {"XDG_CACHE_HOME": "/x"}) == Path_("/x/huggingface/hub")
    assert envfind.hf_hub_folder(home, {"XDG_CACHE_HOME": "/x", "HF_HOME": "/h"}) == Path_("/h/hub")
    assert envfind.hf_hub_folder(home, {"HF_HOME": "/h", "HUGGINGFACE_HUB_CACHE": "/old"}) == Path_("/old")
    assert envfind.hf_hub_folder(home, {"HF_HOME": "/h", "HUGGINGFACE_HUB_CACHE": "/old", "HF_HUB_CACHE": "/d"}) == Path_("/d")
    assert envfind.hf_hub_folder(home, {"HF_HUB_CACHE": ""}) == base / ".cache" / "huggingface" / "hub"          # an empty setting is not a place


def test_the_repository_folder_name_is_the_one_the_registrys_address_makes():
    items = [i for i in load_registry().items if i.kind == "model" and i.folder == envfind.SPEECH_FOLDER]
    owner, repo = urlparse(items[0].url).path.strip("/").split("/")[:2]
    assert envfind.HF_REPO_FOLDER == "models--%s--%s" % (owner, repo)
    assert all(urlparse(i.url).path.strip("/").split("/")[:2] == [owner, repo] for i in items), "every file of the model comes from the one repository"
    assert len({i.revision for i in items}) == 1


def test_the_two_places_are_named_in_the_order_they_are_looked_in(home):
    own, hub = envfind.speech_places(home, {"HF_HOME": "/h"})
    assert own == os.path.join(home.downloads, "models", envfind.SPEECH_FOLDER) and hub == "/h/hub/" + envfind.HF_REPO_FOLDER


def test_a_complete_copy_in_the_hugging_face_folder_makes_the_model_ready_and_the_answer_is_its_snapshot(home):
    folder = put_hub(home, {"a.bin": A, "b.bin": B})
    assert envfind.speech_model(home, hub_registry(A, B), NO_ENV) == (folder, "ready")


def test_the_model_found_there_is_a_copy_made_of_real_files_too(home):
    folder = put_hub(home, {"a.bin": A, "b.bin": B}, link=False)
    assert envfind.speech_model(home, hub_registry(A, B), NO_ENV) == (folder, "ready")


def test_the_tools_own_folder_wins_when_both_are_complete(home):
    put_hub(home, {"a.bin": A, "b.bin": B})
    put(home, "a.bin", A)
    put(home, "b.bin", B)
    assert envfind.speech_model(home, hub_registry(A, B), NO_ENV) == (os.path.join(home.downloads, "models", envfind.SPEECH_FOLDER), "ready")


def test_a_half_finished_own_folder_does_not_stop_a_complete_copy_being_used(home):
    folder = put_hub(home, {"a.bin": A, "b.bin": B})
    put(home, "a.bin", A)
    assert envfind.speech_model(home, hub_registry(A, B), NO_ENV) == (folder, "ready")


def test_a_copy_there_that_is_missing_a_file_is_not_enough_and_does_not_make_the_own_folder_incomplete(home):
    put_hub(home, {"a.bin": A})
    assert envfind.speech_model(home, hub_registry(A, B), NO_ENV) == (None, "missing")


@pytest.mark.parametrize("change", ["shorter", "same_size_other_bytes", "longer"])
def test_a_copy_there_that_is_not_what_was_agreed_to_is_not_used(home, change):
    other = {"shorter": B[:-1], "same_size_other_bytes": bytes([B[0] ^ 1]) + B[1:], "longer": B + b"x"}[change]
    put_hub(home, {"a.bin": A, "b.bin": other})
    assert envfind.speech_model(home, hub_registry(A, B), NO_ENV) == (None, "missing")


def test_another_revision_is_used_when_its_files_are_exactly_the_agreed_ones(home):
    folder = put_hub(home, {"a.bin": A, "b.bin": B}, revision="some-newer-revision")
    assert envfind.speech_model(home, hub_registry(A, B), NO_ENV) == (folder, "ready")


def test_the_agreed_revision_is_the_one_used_when_two_are_good_whatever_their_names_sort_as(home):
    put_hub(home, {"a.bin": A, "b.bin": B}, revision="0000-older-name")
    folder = put_hub(home, {"a.bin": A, "b.bin": B}, revision="zzzz-the-agreed-one")
    assert envfind.speech_model(home, hub_registry(A, B, revision="zzzz-the-agreed-one"), NO_ENV) == (folder, "ready")


def test_a_bad_revision_does_not_hide_a_good_one(home):
    put_hub(home, {"a.bin": A, "b.bin": B[:-1]}, revision="0000-bad")
    folder = put_hub(home, {"a.bin": A, "b.bin": B}, revision="1111-good")
    assert envfind.speech_model(home, hub_registry(A, B), NO_ENV) == (folder, "ready")


def test_a_link_that_leaves_the_repository_is_never_followed_even_to_the_right_bytes(home, tmp_path):
    repo = Path_(envfind.hf_hub_folder(home, NO_ENV)) / envfind.HF_REPO_FOLDER
    snapshot = repo / "snapshots" / REV
    snapshot.mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.mkdir()
    for name, payload in (("a.bin", A), ("b.bin", B)):
        (outside / name).write_bytes(payload)
        os.symlink(str(outside / name), str(snapshot / name))
    assert envfind.speech_model(home, hub_registry(A, B), NO_ENV) == (None, "missing")


def test_a_link_to_a_folder_is_not_a_snapshot(home, tmp_path):
    repo = Path_(envfind.hf_hub_folder(home, NO_ENV)) / envfind.HF_REPO_FOLDER
    (repo / "snapshots").mkdir(parents=True)
    real = repo / "elsewhere"
    real.mkdir()
    (real / "a.bin").write_bytes(A)
    (real / "b.bin").write_bytes(B)
    os.symlink(str(real), str(repo / "snapshots" / REV))
    assert envfind.speech_model(home, hub_registry(A, B), NO_ENV) == (None, "missing")


def test_one_file_of_a_snapshot_linked_out_of_the_repository_spoils_the_whole_snapshot(home, tmp_path):
    folder = put_hub(home, {"a.bin": A, "b.bin": B})
    os.remove(os.path.join(folder, "b.bin"))
    (tmp_path / "outside-b.bin").write_bytes(B)
    os.symlink(str(tmp_path / "outside-b.bin"), os.path.join(folder, "b.bin"))
    assert envfind.speech_model(home, hub_registry(A, B), NO_ENV) == (None, "missing")


def test_a_loop_of_links_in_a_snapshot_is_skipped_and_never_stops_the_lookup(home):
    bad = put_hub(home, {"a.bin": A, "b.bin": B}, revision="0000-loop")
    os.remove(os.path.join(bad, "a.bin"))
    os.symlink(os.path.join(bad, "a.bin"), os.path.join(bad, "a.bin"))       # a link to itself
    good = put_hub(home, {"a.bin": A, "b.bin": B}, revision="1111-good")
    assert envfind.speech_model(home, hub_registry(A, B), NO_ENV) == (good, "ready")


def test_a_loop_of_links_in_the_own_folder_is_a_file_that_is_not_right_not_a_crash(home):
    registry = hub_registry(A, B)
    folder = os.path.join(home.downloads, "models", envfind.SPEECH_FOLDER)
    os.makedirs(folder)
    os.symlink(os.path.join(folder, "a.bin"), os.path.join(folder, "a.bin"))
    assert envfind.speech_model(home, registry, NO_ENV) == (None, "incomplete")


def test_a_link_with_nothing_at_its_end_is_something_there_that_is_not_right(home, tmp_path):
    folder = os.path.join(home.downloads, "models", envfind.SPEECH_FOLDER)
    os.makedirs(folder)
    os.symlink(str(tmp_path / "gone.bin"), os.path.join(folder, "a.bin"))
    assert envfind.speech_model(home, hub_registry(A, B), NO_ENV) == (None, "incomplete")


def test_a_file_the_pin_does_not_allow_is_never_taken_even_when_its_bytes_are_right(home):
    """The same rule as for a download: an entry whose address is not allowed cannot stand in for the agreed file, in either place."""
    registry = hub_registry(A, B)
    odd = Registry(tuple(replace(item, url=item.url.replace("huggingface.co", "example.com")) for item in registry.items))
    put_hub(home, {"a.bin": A, "b.bin": B})
    put(home, "a.bin", A)
    put(home, "b.bin", B)
    assert envfind.speech_model(home, odd, NO_ENV) == (None, "incomplete")
    assert envfind.speech_model(home, registry, NO_ENV)[1] == "ready"


def test_a_file_of_the_wrong_size_is_not_read_through(home, monkeypatch):
    from voice_studio.core import fetch
    put_hub(home, {"a.bin": A, "b.bin": B + b"x"})
    read = []
    real = fetch._sha256_of
    monkeypatch.setattr(fetch, "_sha256_of", lambda path: read.append(str(path)) or real(path))
    assert envfind.speech_model(home, hub_registry(A, B), NO_ENV) == (None, "missing")
    assert [name for name in read if name.endswith("b.bin")] == [], "a file of the wrong size is turned down by its size alone"


def test_the_folder_the_environment_names_is_the_one_looked_in(home, tmp_path):
    elsewhere = tmp_path / "moved-cache"
    folder = put_hub(home, {"a.bin": A, "b.bin": B}, hub=str(elsewhere))
    assert envfind.speech_model(home, hub_registry(A, B), NO_ENV) == (None, "missing")
    assert envfind.speech_model(home, hub_registry(A, B), {"HF_HUB_CACHE": str(elsewhere)}) == (folder, "ready")


def test_the_real_environment_is_read_when_none_is_given(home, monkeypatch, tmp_path):
    folder = put_hub(home, {"a.bin": A, "b.bin": B}, hub=str(tmp_path / "from-the-environment"))
    monkeypatch.setenv("HF_HUB_CACHE", str(tmp_path / "from-the-environment"))
    assert envfind.speech_model(home, hub_registry(A, B)) == (folder, "ready")


def test_looking_in_the_hugging_face_folder_writes_nothing(home):
    put_hub(home, {"a.bin": A, "b.bin": B[:-1]})
    root = Path_(envfind.hf_hub_folder(home, NO_ENV))
    before = sorted(str(p) for p in root.rglob("*"))
    envfind.speech_model(home, hub_registry(A, B), NO_ENV)
    assert sorted(str(p) for p in root.rglob("*")) == before and not os.path.exists(home.root)


# ---------------------------------------------------------------- the programs

def test_an_environment_that_is_not_in_the_list_cannot_be_built(home):
    found, state = envfind.resolver("nonsense", home, load_registry(), FakeSystem(disks={home.home: (500 * GIB, 400 * GIB)}))()
    assert found is None and state == "not_buildable"


@pytest.mark.parametrize("env_id", ["training", "studio"])
def test_an_environment_nobody_built_reads_as_not_there_and_nothing_is_built_or_written(home, env_id):
    found, state = envfind.resolver(env_id, home, load_registry(), FakeSystem(disks={home.home: (500 * GIB, 400 * GIB)}))()
    assert found is None and state in ("absent", "not_buildable") and not os.path.exists(home.home)


def test_the_training_front_uses_this_very_lookup(home, monkeypatch):
    registry = load_registry()
    system = FakeSystem(disks={home.home: (500 * GIB, 400 * GIB)})
    monkeypatch.setattr(rounds_front, "RealSystem", lambda: system)
    assert rounds_front.training_environment(home, registry)() == envfind.resolver("training", home, registry, system)()


def test_both_environments_the_tool_looks_for_are_in_the_list_of_environments():
    assert {"training", "studio"} <= {spec.id for spec in load_environments()}
