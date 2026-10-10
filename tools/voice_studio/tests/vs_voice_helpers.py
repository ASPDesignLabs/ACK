# SPDX-License-Identifier: GPL-3.0-or-later
"""A voice to test with: an ONNX-shaped file written by hand (the real format's top level: a version, a graph, and metadata entries), and a Piper-style config."""
import json
from pathlib import Path
from typing import Dict, Optional


def varint(n: int) -> bytes:
    out = bytearray()
    while True:
        byte = n & 0x7F
        n >>= 7
        if n:
            out.append(byte | 0x80)
        else:
            out.append(byte)
            return bytes(out)


def field_bytes(field: int, payload: bytes) -> bytes:
    return varint((field << 3) | 2) + varint(len(payload)) + payload


def meta_entry(key: str, value: str) -> bytes:
    return field_bytes(14, field_bytes(1, key.encode()) + field_bytes(2, value.encode()))


PATCHED = {"model_type": "vits", "comment": "piper", "language": "English", "voice": "en-us", "version": "1", "has_espeak": "1", "has_g2pw": "0",
           "n_speakers": "1", "sample_rate": "22050"}


def onnx_bytes(metadata: Optional[Dict[str, str]] = None, graph: int = 5000, metadata_first: bool = False, extra: bytes = b"") -> bytes:
    """ModelProto's top level: ir_version (field 1), producer (2), the graph (7, weights and all), opset (8), then the metadata entries (14)."""
    meta = b"".join(meta_entry(k, v) for k, v in (metadata or {}).items())
    graph_field = field_bytes(7, (bytes(range(256)) * (graph // 256 + 1))[:graph])
    body = b"\x08\x08" + field_bytes(2, b"pytorch") + (meta if metadata_first else b"") + graph_field + field_bytes(8, b"\x0a\x00\x10\x11")
    return body + extra + (b"" if metadata_first else meta)


def piper_config(rate: int = 22050, speakers: Optional[int] = None, symbols: Optional[Dict[str, list]] = None) -> dict:
    config = {"audio": {"sample_rate": rate, "quality": "medium"}, "espeak": {"voice": "en-us"}, "inference": {"noise_scale": 0.667},
              "phoneme_type": "espeak", "phoneme_id_map": symbols if symbols is not None else {"_": [0], "^": [1], "$": [2], " ": [3], "a": [4], "b": [5]}}
    if speakers is not None:
        config["num_speakers"] = speakers
    return config


def write_voice(folder: Path, metadata: Optional[Dict[str, str]] = None, config: Optional[dict] = None, name: str = "voice", **kw):
    """(model path, config path) for a voice that ACK will take, unless the arguments say otherwise."""
    folder.mkdir(parents=True, exist_ok=True)
    model, conf = folder / (name + ".onnx"), folder / (name + ".onnx.json")
    model.write_bytes(onnx_bytes(PATCHED if metadata is None else metadata, **kw))
    conf.write_text(json.dumps(piper_config() if config is None else config))
    return model, conf
