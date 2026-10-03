# SPDX-License-Identifier: GPL-3.0-or-later
"""RECORD TRAINING DATA's HELP walkthrough points at controls by tag. The Android build is not run in tests, so this keeps the
three places that must agree from drifting: the tags (AckTags.kt), the controls that carry them (voicecapture/*.kt and
AudioView.kt), and the walkthrough that highlights them (help/RecordTrainingDataHelp.kt), plus its registration."""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
APP = ROOT / "app/src/main/java/com/example/besu"
pytestmark = pytest.mark.skipif(not APP.exists(), reason="not inside the full ACK repository")


def text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def train_tags():
    return sorted(set(re.findall(r'const val (TRAIN_[A-Z_]+) = "\1"', text(APP / "AckTags.kt"))))


def screens_source() -> str:
    return "\n".join(text(p) for p in sorted((APP / "voicecapture").glob("*.kt"))) + text(APP / "settings/AudioView.kt")


def test_tag_values_match_their_names():
    for m in re.finditer(r'const val (TRAIN_[A-Z_]+) = "([A-Z_]+)"', text(APP / "AckTags.kt")):
        assert m.group(1) == m.group(2)


def test_every_tag_is_on_a_control_that_carries_testtag_and_helptarget_together():
    src = screens_source()
    for tag in train_tags():
        assert f".testTag(AckTags.{tag})" in src, f"{tag} is never used as a test tag"
        assert f".helpTarget(AckTags.{tag}," in src, f"{tag} is never a help target"


def test_the_walkthrough_only_points_at_tags_a_screen_carries_and_covers_the_main_ones():
    help_src = text(APP / "help/RecordTrainingDataHelp.kt")
    used = set(re.findall(r"AckTags\.(TRAIN_[A-Z_]+)", help_src))
    assert used, "the walkthrough points at nothing"
    assert used <= set(train_tags())
    for tag in ("TRAIN_ENTRY_BTN", "TRAIN_NEW_SCRIPT_BTN", "TRAIN_SCRIPT_RECORD_BTN", "TRAIN_CARD_TEXT", "TRAIN_REDO_BTN", "TRAIN_END_BTN", "TRAIN_SAVE_ALL_BTN"):
        assert tag in used, f"{tag} is not explained"


def test_gated_steps_wait_for_taps_that_are_always_possible():
    help_src = text(APP / "help/RecordTrainingDataHelp.kt")
    gated = re.findall(r"HelpAction\.Interact\(AckTags\.(TRAIN_[A-Z_]+)\)", help_src)
    assert sorted(gated) == ["TRAIN_ENTRY_BTN", "TRAIN_NEW_SCRIPT_BTN"]
    src = screens_source()
    for tag in gated:
        assert f"HelpEvent.Interacted(AckTags.{tag})" in src or f"reportHelpInteraction(AckTags.{tag})" in src, f"{tag} never reports a tap"


def test_the_module_is_registered_once_and_its_id_is_unique():
    registry = text(APP / "help/HelpRegistry.kt")
    assert registry.count("RecordTrainingDataHelp.module") == 1
    ids = []
    for p in sorted((APP / "help").glob("*.kt")):
        ids += re.findall(r'HelpModule\(\s*id = "([a-z_0-9]+)"', text(p))
    assert ids.count("record_training_data") == 1


def test_every_step_id_is_unique_inside_the_module_and_has_text():
    src = text(APP / "help/RecordTrainingDataHelp.kt")
    step_ids = re.findall(r'HelpStep\(\s*id = "([a-z_]+)"', src)
    assert len(step_ids) == len(set(step_ids)) >= 10
    assert step_ids[0] == "intro" and step_ids[-1] == "complete"
