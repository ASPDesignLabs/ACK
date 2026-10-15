# SPDX-License-Identifier: GPL-3.0-or-later
"""The list of sounds against the real sherpa-onnx (plan task VS-5.4). Skipped unless sherpa-onnx and onnx are installed and ACK_VS_ESPEAK_DATA names a folder of pronunciation data
(for example `.../site-packages/piper/espeak-ng-data` of a training environment), because nothing here may fetch anything.

A stand-in voice is built whose output is the ids it was given, so the test can see what the real engine passed to it: the real engine, the real pronunciation data and the real
patcher are in the loop; only the neural network is a stand-in. What this shows: the list of sounds the phone's rule makes is accepted; the same list without the rule is refused (the
engine stops the whole program, which is what the phone would do); the patcher's output is loadable; and the engine frames every sentence the way Piper voices expect."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from voice_studio.core import phonemes

TOOLS = Path(__file__).resolve().parents[2]
DATA = os.environ.get("ACK_VS_ESPEAK_DATA", "")
so = pytest.importorskip("sherpa_onnx")
onnx = pytest.importorskip("onnx")
np = pytest.importorskip("numpy")
pytestmark = pytest.mark.skipif(not (DATA and os.path.isfile(os.path.join(DATA, "phontab"))), reason="ACK_VS_ESPEAK_DATA does not name a folder of pronunciation data")

SOUNDS = "_^$ !'(),-.:;?abcdefhijklmnopqrstuvwxyz" + "æçðøħŋœǀǁǂǃ" + "".join(chr(c) for c in range(0x250, 0x2a0)) + "ˈˌːˑ˞βθχ"
DIPHTHONGS = ["aɪ", "aʊ", "ɔɪ", "eɪ", "oʊ"]
OK_FRAMING = "the first id is the start marker, the last the end marker, and a pad sits between every sound"


def build(folder: Path) -> Path:
    from onnx import TensorProto, helper, numpy_helper
    mapping = {s: [i] for i, s in enumerate(dict.fromkeys(SOUNDS))}
    for n, d in enumerate(DIPHTHONGS):
        mapping[d] = [len(mapping) + n]
    mapping["\n"] = [len(mapping) + 10]
    config = {"audio": {"sample_rate": 22050, "quality": "medium"}, "espeak": {"voice": "en-us"}, "inference": {"noise_scale": 0.667, "length_scale": 1, "noise_w": 0.8},
              "phoneme_type": "espeak", "num_speakers": 1, "speaker_id_map": {}, "phoneme_id_map": mapping}
    graph = helper.make_graph([helper.make_node("Cast", ["input"], ["f"], to=TensorProto.FLOAT), helper.make_node("Mul", ["f", "k"], ["output"])], "stand_in",
                              [helper.make_tensor_value_info("input", TensorProto.INT64, [1, "N"]), helper.make_tensor_value_info("input_lengths", TensorProto.INT64, [1]),
                               helper.make_tensor_value_info("scales", TensorProto.FLOAT, [3])],
                              [helper.make_tensor_value_info("output", TensorProto.FLOAT, [1, "N"])], initializer=[numpy_helper.from_array(np.array(0.001, dtype=np.float32), "k")])
    model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 13)])
    model.ir_version = 8
    path = folder / "voice.onnx"
    onnx.save(model, str(path))
    (folder / "voice.onnx.json").write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")
    done = subprocess.run([sys.executable, str(TOOLS / "patch_voice_for_sherpa_onnx.py"), str(path), str(folder / "voice.onnx.json")], capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    return path


def engine(model: Path, tokens: Path):
    config = so.OfflineTtsConfig(model=so.OfflineTtsModelConfig(vits=so.OfflineTtsVitsModelConfig(model=str(model), tokens=str(tokens), data_dir=DATA), num_threads=1, provider="cpu"))
    return so.OfflineTts(config)


def test_the_list_of_sounds_the_rule_makes_is_accepted_and_the_engine_frames_every_sentence_as_piper_voices_expect(tmp_path):
    model = build(tmp_path)
    found = phonemes.tokens_text((tmp_path / "voice.onnx.json").read_text(encoding="utf-8"))
    assert len(found.skipped) == len(DIPHTHONGS) and found.kept > 100
    (tmp_path / "tokens.txt").write_bytes(found.text.encode("utf-8"))
    audio = engine(model, tmp_path / "tokens.txt").generate("Hello there. I need some help.", sid=0, speed=1.0)
    ids = [round(v * 1000) for v in audio.samples]
    assert audio.sample_rate == 22050 and len(ids) > 20
    sentences, current = [], []
    for value in ids:
        current.append(value)
        if value == 2:                                   # the end marker; no real sound has id 2 in this voice
            sentences.append(current)
            current = []
    assert current == [] and len(sentences) == 2, "two sentences in, two framed sentences out"
    for one in sentences:
        assert one[0] == 1 and one[-1] == 2 and one[-2] == 0, OK_FRAMING
        assert all(v == 0 for v in one[1:-1:2]) and all(v > 2 for v in one[2:-1:2]), OK_FRAMING


def test_the_same_list_without_the_rule_is_refused_by_the_engine_which_stops_the_program(tmp_path):
    model = build(tmp_path)
    mapping = json.loads((tmp_path / "voice.onnx.json").read_text(encoding="utf-8"))["phoneme_id_map"]
    (tmp_path / "tokens.txt").write_text("".join("%s %d\n" % (k, v[0]) for k, v in sorted(mapping.items(), key=lambda kv: kv[1][0]) if k != "\n"), encoding="utf-8")
    code = ("import sherpa_onnx as so, sys\n"
            "c = so.OfflineTtsConfig(model=so.OfflineTtsModelConfig(vits=so.OfflineTtsVitsModelConfig(model=sys.argv[1], tokens=sys.argv[2], data_dir=sys.argv[3]), num_threads=1, provider='cpu'))\n"
            "so.OfflineTts(c)\nprint('LOADED')\n")
    done = subprocess.run([sys.executable, "-c", code, str(model), str(tmp_path / "tokens.txt"), DATA], capture_output=True, text=True)
    assert "LOADED" not in done.stdout and (done.returncode != 0 or "ReadTokens" in done.stderr), (done.returncode, done.stdout, done.stderr[-300:])
