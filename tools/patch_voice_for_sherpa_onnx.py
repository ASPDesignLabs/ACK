#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later AND Apache-2.0
#
# This script follows scripts/piper/add_meta_data.py from k2-fsa/sherpa-onnx:
#     Copyright 2025  Xiaomi Corp.  (authors: Fangjun Kuang)
#     Licensed under the Apache License, Version 2.0 (the full text is in LICENSES/Apache-2.0.txt).
# Changes made here, as that license asks to be stated: rewritten and shortened to patch one English voice in place,
# without the original's command-line options for other voices and without its `iso639` dependency; it also checks its
# arguments and keeps a copy of the original model. The metadata keys it writes are the ones sherpa-onnx's VITS loader
# requires. The rest of this file is part of ACK (see NOTICE) and is licensed under the GNU General Public License,
# version 3 or (at your option) any later version.
"""Patch a Piper-trained .onnx voice with the metadata sherpa-onnx's VITS
loader requires (sample_rate, n_speakers, language, comment=piper, ...).

Why this is needed: piper1-gpl's own `export_onnx.py` (used to export a
trained voice) does not embed any of this metadata into the .onnx file.
sherpa-onnx's VITS loader (the on-device engine ACK's custom trained
voice feature uses -- see CLAUDE.md's "CUSTOM TRAINED VOICE" section)
reads several of these fields as *required*, with no fallback default.
Without them, it logs "'sample_rate' does not exist in the metadata"
and the app crashes shortly after trying to synthesize. This follows
sherpa-onnx's own official conversion script
(scripts/piper/add_meta_data.py in the k2-fsa/sherpa-onnx repo),
minus its optional `iso639` dependency -- not needed for an English
voice, which is what this is written for.

Usage (run once per exported voice, on the PC where you trained it):

    pip install onnx
    cp config.json my_voice.onnx.json          # the voice's config, named like the model plus .json
    python3 tools/patch_voice_for_sherpa_onnx.py my_voice.onnx my_voice.onnx.json

The config is the file piper1-gpl wrote to --data.config_path during training
(often config.json). It must sit next to the model, named <model>.onnx.json,
because ACK's importer needs both files. If you leave the second argument out, that
name is assumed.

The model is patched in place, but a copy of the original is kept first
(my_voice.onnx.before-patch), and the new file is written beside it and only then
swapped in, so a failure at any point leaves your model exactly as it was.
Afterwards, import BOTH files together (Settings > Audio Architect > IMPORT
CUSTOM VOICE). The .onnx.json itself does not change.
"""

import argparse
import filecmp
import json
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Tuple

# Piper training in this app is always English (--data.espeak_voice
# "en-us"), so this is the only mapping actually needed. Extend if a
# non-English voice is ever trained.
_LANGUAGE_NAMES = {
    "en": "English",
}

BACKUP_SUFFIX = ".before-patch"


class UsageProblem(Exception):
    """Something to fix before patching, explained for a person. Nothing has been changed when this is raised."""


def _script() -> str:
    return f"python3 {sys.argv[0]}"          # exactly how the person ran it, so a suggested command can be pasted back


def resolve_arguments(onnx_arg: str, config_arg: Optional[str]) -> Tuple[Path, Path]:
    """The model and its config, checked. Raises UsageProblem with the fix, naming the exact commands, if something is off."""
    model = Path(onnx_arg).expanduser()
    config = Path(config_arg).expanduser() if config_arg else None

    if config is not None and model.name.endswith(".json") and config.name.endswith(".onnx"):
        raise UsageProblem(
            "The two files are the wrong way round. The model (the .onnx) comes first, then its config (the .json):\n"
            f"  {_script()} {config} {model}")
    if not model.is_file():
        raise UsageProblem(f"The model file doesn't exist: {model}\nCheck the path (ls -l {model.parent or '.'}).")

    if config is None:
        config = model.with_name(model.name + ".json")
    same = config.exists() and model.exists() and os.path.samefile(config, model)
    if same or (config.name.endswith(".onnx") and not config.name.endswith(".onnx.json")):
        raise UsageProblem(
            f"The second file you gave is a model, not a config: {config}\n"
            "The second file must be the voice's config: the .json file that goes with the model, named like the model plus .json "
            f"({model.name}.json).\n"
            f"If you don't have that file yet, copy the config training wrote (it is whatever --data.config_path pointed at, often "
            f"config.json next to the model):\n  cp {model.with_name('config.json')} {model}.json\n"
            f"then run:\n  {_script()} {model} {model}.json")
    if not config.is_file():
        sibling = model.with_name("config.json")
        hint = (f"There is a config.json next to the model. Copy it to the name the importer needs:\n  cp {sibling} {model}.json\n"
                if sibling.is_file() else
                "It is the file piper1-gpl wrote to --data.config_path when you trained the voice (often config.json). "
                f"Copy it next to the model as {model.name}.json.\n")
        raise UsageProblem(f"The config file doesn't exist: {config}\n{hint}Then run the command again. Nothing was changed.")
    return model, config


def read_config(config: Path) -> dict:
    try:
        text = config.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        raise UsageProblem(f"{config} isn't a text file (it looks like a model or another binary file). The second file must be "
                           f"the voice's .json config, e.g. {config.name.split('.onnx')[0]}.onnx.json. Nothing was changed.")
    try:
        data = json.loads(text)
    except json.JSONDecodeError as err:
        raise UsageProblem(f"{config} isn't valid JSON ({err.msg}, line {err.lineno}). The second file must be the voice's "
                           "config as piper1-gpl wrote it. Nothing was changed.")
    audio = data.get("audio") if isinstance(data, dict) else None
    rate = audio.get("sample_rate") if isinstance(audio, dict) else None
    if not isinstance(rate, int) or isinstance(rate, bool) or rate <= 0:
        raise UsageProblem(f"{config} doesn't look like a Piper voice config (it has no audio -> sample_rate). Use the file training "
                           "wrote to --data.config_path. Nothing was changed.")
    return data


def build_metadata(config: dict) -> Dict[str, object]:
    voice = config.get("espeak", {}).get("voice", "en-us")
    lang_code = voice.split("-")[0].split("_")[0]
    return {
        "model_type": "vits",
        "comment": "piper",  # sherpa-onnx keys Piper-specific behavior off this
        "language": _LANGUAGE_NAMES.get(lang_code, lang_code),
        "voice": voice,
        "version": 1,
        "has_espeak": 1,
        "has_g2pw": 0,
        "n_speakers": config.get("num_speakers", 1),
        "sample_rate": config["audio"]["sample_rate"],
    }


def _backup_path(model: Path) -> Path:
    first = model.with_name(model.name + BACKUP_SUFFIX)
    if not first.exists() or filecmp.cmp(first, model, shallow=False):
        return first                                  # none yet, or it is already a copy of exactly this file
    return model.with_name(model.name + BACKUP_SUFFIX + "-" + datetime.now().strftime("%Y%m%d-%H%M%S"))   # an older export's backup stays


def patch_model(model: Path, meta_data: Dict[str, object]) -> Optional[Path]:
    """Add the metadata. Returns the backup's path, or None if the model already had exactly this metadata (nothing was written)."""
    try:
        import onnx
    except ImportError:
        raise UsageProblem("The 'onnx' package isn't installed in this Python. Run:  pip install onnx   (in the same environment you "
                           "train in, the one with (.venv) in the prompt), then run this again.")
    try:
        loaded = onnx.load(str(model))
    except Exception as err:  # noqa: BLE001 - onnx raises several different types for a file that isn't a model
        first = (str(err).strip().splitlines() or [""])[0][:160]
        raise UsageProblem(f"{model} can't be read as an ONNX model ({type(err).__name__}: {first}). Is it the file you exported with "
                           "piper.train.export_onnx? Nothing was changed.")

    wanted = {k: str(v) for k, v in meta_data.items()}
    if {p.key: p.value for p in loaded.metadata_props} == wanted:
        return None

    backup = _backup_path(model)
    if not backup.exists():
        shutil.copy2(model, backup)
    while len(loaded.metadata_props):
        loaded.metadata_props.pop()
    for key, value in wanted.items():
        meta = loaded.metadata_props.add()
        meta.key, meta.value = key, value

    scratch = model.with_name(model.name + ".patching")
    try:
        onnx.save(loaded, str(scratch))
        check = {p.key: p.value for p in onnx.load(str(scratch)).metadata_props}
        if check != wanted:
            raise RuntimeError("the patched file did not read back with the metadata that was written")
        os.replace(scratch, model)                    # the only moment the model changes, and it is a single swap
    finally:
        if scratch.exists():
            scratch.unlink()
    return backup


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("onnx_path", help="your exported voice, the .onnx file (patched in place; a copy of the original is kept)")
    parser.add_argument("config_path", nargs="?",
                        help="its config, the .json file; if left out, <model>.json next to it (e.g. my_voice.onnx.json)")
    args = parser.parse_args(argv)
    try:
        model, config = resolve_arguments(args.onnx_path, args.config_path)
        meta_data = build_metadata(read_config(config))
        print("Writing metadata:", meta_data)
        backup = patch_model(model, meta_data)
    except UsageProblem as problem:
        print(f"\n{problem}\n", file=sys.stderr)
        return 2
    except Exception as err:  # noqa: BLE001 - say what happened and that the model is safe, not a stack trace
        print(f"\nPatching failed ({type(err).__name__}: {err}). Your model was not changed.\n", file=sys.stderr)
        return 1
    if backup is None:
        print(f"\n{model} already has this metadata, so nothing was changed.")
    else:
        print(f"\nPatched {model} in place.\nA copy of the original is kept at {backup}")
    print(f"Next, in ACK: Settings > Audio Architect > IMPORT CUSTOM VOICE, and pick BOTH files together:\n  {model.name}\n  {config.name}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
