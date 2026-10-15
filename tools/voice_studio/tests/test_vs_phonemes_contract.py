# SPDX-License-Identifier: GPL-3.0-or-later
"""The list of sounds is the phone's (plan task VS-5.4): this reads ACK's own source, so a change to the phone's rule fails here instead of making a preview say something the phone will not."""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
ENGINE = ROOT / "app" / "src" / "main" / "java" / "com" / "example" / "besu" / "output" / "PiperVoiceEngine.kt"


def engine_text():
    if not ENGINE.is_file():
        pytest.fail("ACK's source file %s is not where this test expects it: if it moved, this test and core/phonemes.py must follow" % ENGINE.relative_to(ROOT))
    return ENGINE.read_text(encoding="utf-8")


def rule_body():
    """The code of generateTokensFile with its comments taken out, so a word inside a comment cannot satisfy a check."""
    text = engine_text()
    start = text.index("private fun generateTokensFile")
    end = text.index("// Lazily builds the native engine", start)
    body = text[start:end]
    return "\n".join(re.sub(r"//.*", "", line) for line in body.splitlines())


def squeeze(text):
    return re.sub(r"\s+", " ", text)


def test_the_phone_reads_the_phoneme_id_map_of_the_voices_own_settings_file():
    body = squeeze(rule_body())
    assert "CustomVoiceRepository.configFile(context).readText()" in body and '.jsonObject["phoneme_id_map"]' in body


def test_the_phone_leaves_out_the_line_break_entry_and_any_sound_that_is_not_exactly_one_code_point():
    body = squeeze(rule_body())
    assert 'it.key == "\\n"' in body and "it.key.codePointCount(0, it.key.length) != 1" in body
    assert body.count("filterNot") == 1 and "||" in body.split("filterNot", 1)[1].split("sortedBy", 1)[0]


def test_the_phone_leaves_them_out_before_it_sorts_by_the_first_id_of_each_entry():
    body = squeeze(rule_body())
    assert body.index("filterNot") < body.index("sortedBy")
    assert "sortedBy { it.value.jsonArray.first().jsonPrimitive.int }" in body


def test_the_phone_writes_one_line_per_sound_as_the_sound_a_space_and_the_first_id():
    body = squeeze(rule_body())
    assert 'val id = ids.jsonArray.first().jsonPrimitive.int' in body and 'writer.write("$symbol $id")' in body and "writer.newLine()" in body


def test_the_phone_writes_the_file_next_to_the_model_and_hands_the_engine_that_file():
    text = engine_text()
    assert 'File(CustomVoiceRepository.modelFile(context).parentFile, "tokens.txt")' in squeeze(text)
    assert "tokens = tokensFile(context).absolutePath" in squeeze(text)


def test_the_phone_gives_the_engine_the_model_the_tokens_and_a_folder_of_pronunciation_data_and_no_other_setting_that_changes_the_sound():
    body = squeeze(engine_text())
    block = body[body.index("OfflineTtsVitsModelConfig("):body.index("numThreads = 2")]
    names = set(re.findall(r"(\w+) = ", block))
    assert names == {"model", "tokens", "dataDir"}, "the phone now passes %s to sherpa-onnx: the preview must pass the same" % sorted(names)


def test_the_phone_asks_for_the_first_speaker_at_normal_speed_by_not_passing_anything_else():
    text = squeeze(engine_text())
    assert "engine.generate(text = text)" in text
