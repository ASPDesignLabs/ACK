# SPDX-License-Identifier: GPL-3.0-or-later
"""The phone's package writer (Kotlin) and Freeform Studio's reader (Python) must agree.

The Kotlin unit test PackageWriterTest.writesPackagesForFreeformStudioToOpenWhenAskedTo writes three packages (script.zip, free.zip,
mixed.zip) into the folder named by ACK_KOTLIN_PACKAGES. This file opens each with the real reader and importer. It is skipped when
that folder is not set, so the normal test run is unaffected; to run the round trip from the repository root:

    ACK_KOTLIN_PACKAGES=/tmp/ack-packages ./gradlew :app:cleanTestDebugUnitTest :app:testDebugUnitTest --tests '*PackageWriterTest*'
    ACK_KOTLIN_PACKAGES=/tmp/ack-packages python -m pytest tools/freeform_studio/tests/test_kotlin_package_contract.py

(`clean...Test` is needed because Gradle does not know the folder variable changes what the test does.)
"""
import os
from pathlib import Path

import pytest

import freeform_studio.ack_import as imp
from freeform_studio.ack_package import open_package
from freeform_studio.config import Config
from freeform_studio.storage import TakeStore

FOLDER = os.environ.get("ACK_KOTLIN_PACKAGES", "")
pytestmark = pytest.mark.skipif(not (FOLDER and (Path(FOLDER) / "script.zip").exists()),
                                reason="set ACK_KOTLIN_PACKAGES to the folder PackageWriterTest wrote (see this file's docstring)")

TEXTS = ["The tide came in.", "We walked along the shore.", "Gulls circled overhead."]


def package(name):
    return open_package(Path(FOLDER) / name)


@pytest.mark.parametrize("name", ["script.zip", "free.zip", "mixed.zip"])
def test_every_package_the_phone_code_writes_passes_every_check_of_the_reader(name):
    p = package(name)
    assert p.manifest["schema"] == "ack-training-capture/1"
    assert p.warnings == [], p.warnings
    assert p.manifest["created"] == "2026-10-02T19:30:00Z"


def test_a_script_package_says_what_was_recorded():
    (s,) = package("script.zip").sessions
    assert s["mode"] == "script" and s["label"] == "closet, phone on stand, 30 cm" and s["device"] == {"model": "Pixel 8", "sdk": 35}
    assert [c["text"] for c in s["clips"]] == TEXTS
    assert [c["index"] for c in s["clips"]] == [1, 2, 3]
    assert [c["speech"] for c in s["clips"]] == [{"start_s": 0.5, "end_s": 2.5}, {"start_s": 0.5, "end_s": 3.0}, {"start_s": 0.5, "end_s": 3.5}]
    assert s["audio"] == {"sample_rate": 48000, "source": "UNPROCESSED", "source_requested": "UNPROCESSED"}
    assert s["threshold_dbfs"] == -52.3 and s["noise_floor_dbfs"] == -62.3


def test_a_free_package_carries_the_whole_recording_and_the_suggested_cuts():
    (s,) = package("free.zip").sessions
    assert s["mode"] == "free" and s["topic"] == "my day" and s["noise_floor_dbfs"] is None and "device" not in s
    pieces = s["recording"]["proposed_segments"]
    assert len(pieces) >= 2 and all(p["end_kind"] in ("pause", "forced", "end") for p in pieces)
    assert all(b["start_s"] >= a["end_s"] - 1e-6 for a, b in zip(pieces, pieces[1:]))


def test_the_summary_the_import_screen_shows_is_filled_in():
    summary = package("mixed.zip").summary()
    assert summary["app_version"] == "1.0-beta.9" and len(summary["sessions"]) == 2
    assert {x["sample_rate"] for x in summary["sessions"]} == {44100, 48000}
    assert summary["bytes"] > 0 and summary["seconds"] > 0


def test_the_importer_accepts_them_adds_one_recording_each_and_is_repeatable(tmp_path):
    out = tmp_path / "output"
    out.mkdir()
    plan = imp.make_plan(package("mixed.zip"), out, "en-US")
    assert [s.state for s in plan.sessions] == ["new", "new"] and plan.enough_room
    created = imp.apply_import(plan)
    assert len(created) == 2
    store = TakeStore(Config(output_dir=out).takes_dir)
    script_take = next(store.get(c.take_id) for c in created if store.get(c.take_id)["client"]["ack_mode"] == "script")
    assert script_take["reference_text"] == "\n".join(TEXTS) and script_take["client"]["source"] == "ack"
    again = imp.make_plan(package("mixed.zip"), out, "en-US")
    assert [s.state for s in again.sessions] == ["already", "already"] and not again.to_import
