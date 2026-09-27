#!/usr/bin/env python3
"""Patch a Piper-trained .onnx voice with the metadata sherpa-onnx's VITS
loader requires (sample_rate, n_speakers, language, comment=piper, ...).

Why this is needed: piper1-gpl's own `export_onnx.py` (used to export a
trained voice) does not embed any of this metadata into the .onnx file.
sherpa-onnx's VITS loader (the on-device engine ACK's custom trained
voice feature uses -- see CLAUDE.md's "CUSTOM TRAINED VOICE" section)
reads several of these fields as *required*, with no fallback default.
Without them, it logs "'sample_rate' does not exist in the metadata"
and the app crashes shortly after trying to synthesize. This mirrors
sherpa-onnx's own official conversion script
(scripts/piper/add_meta_data.py in the k2-fsa/sherpa-onnx repo),
minus its optional `iso639` dependency -- not needed for an English
voice, which is what this is written for.

Usage (run once, on the PC where you trained the voice, against the
same .onnx/.onnx.json pair you'd import into ACK):

    pip install onnx
    python3 tools/patch_voice_for_sherpa_onnx.py my_voice.onnx my_voice.onnx.json

Patches the .onnx file in place. Re-import it into ACK afterward
(Settings > Audio Architect > RE-IMPORT CUSTOM VOICE) -- the .onnx.json
config itself does not need to change.
"""

import argparse
import json

import onnx

# Piper training in this app is always English (--data.espeak_voice
# "en-us"), so this is the only mapping actually needed. Extend if a
# non-English voice is ever trained.
_LANGUAGE_NAMES = {
    "en": "English",
}


def add_meta_data(onnx_path: str, meta_data: dict) -> None:
    model = onnx.load(onnx_path)

    while len(model.metadata_props):
        model.metadata_props.pop()

    for key, value in meta_data.items():
        meta = model.metadata_props.add()
        meta.key = key
        meta.value = str(value)

    onnx.save(model, onnx_path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("onnx_path", help="Path to your trained .onnx model (patched in place)")
    parser.add_argument("config_path", help="Path to the matching .onnx.json config")
    args = parser.parse_args()

    with open(args.config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    sample_rate = config["audio"]["sample_rate"]
    num_speakers = config.get("num_speakers", 1)
    voice = config.get("espeak", {}).get("voice", "en-us")
    lang_code = voice.split("-")[0].split("_")[0]
    language = _LANGUAGE_NAMES.get(lang_code, lang_code)

    meta_data = {
        "model_type": "vits",
        "comment": "piper",  # sherpa-onnx keys Piper-specific behavior off this
        "language": language,
        "voice": voice,
        "version": 1,
        "has_espeak": 1,
        "has_g2pw": 0,
        "n_speakers": num_speakers,
        "sample_rate": sample_rate,
    }
    print("Writing metadata:", meta_data)
    add_meta_data(args.onnx_path, meta_data)
    print(f"Patched {args.onnx_path} in place.")


if __name__ == "__main__":
    main()
