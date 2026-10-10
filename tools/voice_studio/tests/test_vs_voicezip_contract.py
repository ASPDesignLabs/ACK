# SPDX-License-Identifier: GPL-3.0-or-later
"""The zip's names and limits are ACK's (plan task VS-5.3): this reads ACK's own source, so a change on the phone side fails here instead of on a person's phone."""
import re
from pathlib import Path

import pytest

from voice_studio.core import voicezip as vz

ROOT = Path(__file__).resolve().parents[3]
OUTPUT = ROOT / "app" / "src" / "main" / "java" / "com" / "example" / "besu" / "output"
MANAGER = OUTPUT / "CustomVoiceBackupManager.kt"
REPOSITORY = OUTPUT / "CustomVoiceRepository.kt"
ENGINE = OUTPUT / "PiperVoiceEngine.kt"


def source(path):
    if not path.is_file():
        pytest.fail("ACK's source file %s is not where this test expects it: if it moved, this test and voicezip.py must follow" % path.relative_to(ROOT))
    return path.read_text(encoding="utf-8")


def constant(text, name):
    match = re.search(r"const val %s\s*=\s*([^\n]+)" % re.escape(name), text)
    assert match, "%s is no longer a constant in ACK's source" % name
    return match.group(1).strip()


def megabytes(expression):
    """`300L * 1024L * 1024L` or `1L * 1024L * 1024L`, in bytes."""
    total = 1
    for part in expression.split("*"):
        total *= int(part.strip().rstrip("L"))
    return total


def test_the_entry_names_are_the_ones_acks_import_looks_for():
    text = source(MANAGER)
    assert constant(text, "MODEL_ENTRY_NAME") == '"%s"' % vz.MODEL_ENTRY
    assert constant(text, "CONFIG_ENTRY_NAME") == '"%s"' % vz.CONFIG_ENTRY


def test_the_zip_limit_is_acks():
    assert megabytes(constant(source(MANAGER), "MAX_ZIP_FILE_SIZE")) == vz.MAX_ZIP_BYTES


def test_the_model_and_config_limits_are_acks():
    text = source(REPOSITORY)
    assert megabytes(constant(text, "MAX_MODEL_SIZE_BYTES")) == vz.MAX_MODEL_BYTES
    assert megabytes(constant(text, "MAX_CONFIG_SIZE_BYTES")) == vz.MAX_CONFIG_BYTES


def test_the_config_keys_acks_import_requires_are_the_ones_checked_here():
    text = source(REPOSITORY)
    body = text[text.index("fun looksLikePiperConfig"):]
    keys = tuple(re.findall(r'containsKey\("([a-z_]+)"\)', body.split("}", 1)[0]))
    assert keys == vz.CONFIG_KEYS


def test_acks_import_reads_exactly_the_two_entries_and_nothing_about_a_manifest():
    text = source(MANAGER)
    assert text.count("zipFile.getEntry(") == 2 and "manifest" not in text.lower().replace("no manifest needed", "")


def test_acks_export_writes_the_same_two_entries_in_the_same_order():
    text = source(MANAGER)
    assert text.index("MODEL_ENTRY_NAME))") < text.index("CONFIG_ENTRY_NAME))")


def test_the_metadata_acks_engine_leans_on_is_what_the_patcher_writes_and_this_checks():
    engine = source(ENGINE)
    assert "piper" in engine.lower() and "sample_rate" in source(Path(__file__).resolve().parents[2] / "patch_voice_for_sherpa_onnx.py")
    patcher = source(Path(__file__).resolve().parents[2] / "patch_voice_for_sherpa_onnx.py")
    for key in vz.REQUIRED_METADATA:
        assert '"%s"' % key in patcher, key


def test_the_symbols_the_phone_leaves_out_are_the_ones_counted_for_the_details():
    engine = source(ENGINE)
    assert "codePointCount(0, it.key.length) != 1" in engine and 'it.key == "\\n"' in engine
