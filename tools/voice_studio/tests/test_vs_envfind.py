# SPDX-License-Identifier: GPL-3.0-or-later
"""Finding the studio and training programs and the listening model the guided setup left: looking only (nothing is built, fetched or written), the answer is "ready" only when every file is
there and byte for byte what was agreed to, and the one lookup serves the training programs and the studio programs alike."""
import hashlib
import os
from dataclasses import replace

import pytest

from vs_fakes import FakeSystem
from vs_fetch_helpers import pinned_item
from voice_studio import rounds as rounds_front
from voice_studio.core import envfind
from voice_studio.core.envspec import load_environments
from voice_studio.core.paths import DataHome
from voice_studio.core.registry import Registry, load_registry

GIB = 2 ** 30


def model_file(payload, name, **over):
    return replace(pinned_item(payload), id="speech-" + name, kind="model", folder=envfind.SPEECH_FOLDER, filename=name, **over)


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
    found, state = envfind.speech_model(home, load_registry())
    assert (found, state) == (None, "missing") and not os.path.exists(home.home)


def test_with_every_file_there_and_exact_the_model_is_ready_and_the_answer_is_its_folder(home):
    a, b = b"first part " * 200, b"second part " * 300
    registry = Registry((model_file(a, "a.bin"), model_file(b, "b.bin")))
    put(home, "a.bin", a)
    put(home, "b.bin", b)
    found, state = envfind.speech_model(home, registry)
    assert state == "ready" and found == os.path.join(home.downloads, "models", envfind.SPEECH_FOLDER)


def test_one_file_missing_is_not_ready(home):
    a, b = b"first part " * 200, b"second part " * 300
    registry = Registry((model_file(a, "a.bin"), model_file(b, "b.bin")))
    put(home, "a.bin", a)
    assert envfind.speech_model(home, registry) == (None, "missing")


@pytest.mark.parametrize("change", ["shorter", "same_size_other_bytes", "longer"])
def test_a_file_that_is_not_what_was_agreed_to_is_not_ready(home, change):
    a = b"first part " * 200
    registry = Registry((model_file(a, "a.bin"),))
    put(home, "a.bin", {"shorter": a[:-1], "same_size_other_bytes": bytes([a[0] ^ 1]) + a[1:], "longer": a + b"x"}[change])
    assert envfind.speech_model(home, registry) == (None, "missing")


def test_a_registry_with_no_such_files_is_never_vacuously_ready(home):
    assert envfind.speech_model(home, Registry(())) == (None, "missing")
    other = replace(pinned_item(), id="other", kind="model", folder="something-else", filename="x.bin")
    put(home, "x.bin", b"anything", folder="something-else")
    assert envfind.speech_model(home, Registry((other,))) == (None, "missing")


def test_a_file_of_another_kind_or_folder_does_not_stand_in_for_the_model(home):
    a = b"first part " * 200
    voice = replace(model_file(a, "a.bin"), kind="voice")
    put(home, "a.bin", a)
    assert envfind.speech_model(home, Registry((voice,))) == (None, "missing")


def test_a_link_in_place_of_the_file_is_not_the_file(home, tmp_path):
    a = b"first part " * 200
    registry = Registry((model_file(a, "a.bin"),))
    real = tmp_path / "elsewhere.bin"
    real.write_bytes(a)
    os.makedirs(os.path.join(home.downloads, "models", envfind.SPEECH_FOLDER))
    os.symlink(str(real), os.path.join(home.downloads, "models", envfind.SPEECH_FOLDER, "a.bin"))
    assert envfind.speech_model(home, registry) == (None, "missing")


def test_looking_for_the_model_writes_nothing(home):
    a = b"first part " * 200
    registry = Registry((model_file(a, "a.bin"),))
    put(home, "a.bin", a[:10])
    before = sorted(os.listdir(os.path.join(home.downloads, "models", envfind.SPEECH_FOLDER)))
    envfind.speech_model(home, registry)
    assert sorted(os.listdir(os.path.join(home.downloads, "models", envfind.SPEECH_FOLDER))) == before


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
