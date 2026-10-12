# SPDX-License-Identifier: GPL-3.0-or-later
"""Finding the programs and the speech model the guided setup built or fetched: where they are if they are ready, and why not if they are not. Looks only; builds and fetches nothing.

The studio environment holds Freeform Studio's own programs (listening to recordings, building a training set); the training environment holds the trainer. Both are named in
data/environments.json. The speech model is the one pinned in data/sources.json and kept under the tool's downloads folder, where the setup put it; a byte-for-byte copy in the Hugging Face folder (where Freeform Studio's own `models fetch` puts it) is used too.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Callable, List, Mapping, Optional, Tuple

from . import envbuild, fetch
from .consent import load_consent
from .envbuild import EnvPaths
from .envspec import load_environments
from .paths import DataHome
from .registry import Item, Registry
from .setuprun import MODELS_FOLDER
from .system import RealSystem, System

SPEECH_FOLDER = "speech-small-en"                       # the registry's folder for the pinned speech model
HF_REPO_FOLDER = "models--Systran--faster-whisper-small.en"   # the Hugging Face folder for that model's repository (a test holds it equal to the registry's address)
Resolver = Callable[[], Tuple[Optional[EnvPaths], str]]


def resolver(env_id: str, home: DataHome, registry: Registry, system: Optional[System] = None) -> Resolver:
    """The environment with this id, if it is built and in order: (its places, "ready"), or (None, why not)."""
    def resolve() -> Tuple[Optional[EnvPaths], str]:
        spec = next((s for s in load_environments() if s.id == env_id), None)
        if spec is None:
            return None, "not_buildable"
        ctx = envbuild.Context(system=system or RealSystem(), home=home, registry=registry, consent=load_consent(Path(home.consent_file)))
        found = envbuild.inspect(spec, ctx)
        return (EnvPaths(found.env_dir), found.state) if found.state == "ready" else (None, found.state)
    return resolve


def hf_hub_folder(home: DataHome, environ: Optional[Mapping[str, str]] = None) -> Path:
    """Where the Hugging Face tools keep what they downloaded, by the rules they use: HF_HUB_CACHE, else HF_HOME/hub, else XDG_CACHE_HOME/huggingface/hub, else ~/.cache/huggingface/hub."""
    env = os.environ if environ is None else environ
    direct = env.get("HF_HUB_CACHE") or env.get("HUGGINGFACE_HUB_CACHE")
    if direct:
        return Path(direct)
    hf_home = env.get("HF_HOME") or str(Path(env.get("XDG_CACHE_HOME") or str(Path(home.home) / ".cache")) / "huggingface")
    return Path(hf_home) / "hub"


def speech_places(home: DataHome, environ: Optional[Mapping[str, str]] = None) -> Tuple[str, str]:
    """The two places the speech model is looked for, in order: the tool's own downloads folder, then the folder Freeform Studio's `models fetch` uses. Names only; reads nothing."""
    return str(Path(home.downloads) / MODELS_FOLDER / SPEECH_FOLDER), str(hf_hub_folder(home, environ) / HF_REPO_FOLDER)


def speech_files(registry: Registry) -> List[Item]:
    """The files the listening model is made of, as the registry pins them."""
    return [item for item in registry.items if item.kind == "model" and item.folder == SPEECH_FOLDER]


def _own_folder_state(folder: Path, files: List[Item]) -> str:
    if all(fetch.is_fetched(item, folder) for item in files):
        return "ready"
    seen = any(os.path.lexists(folder / (item.filename or "")) for item in files if item.filename)
    return "incomplete" if seen else "missing"


def _hub_snapshot(repo: Path, files: List[Item]) -> Optional[Path]:
    """A snapshot folder in the Hugging Face folder whose every file is byte for byte what was agreed, or None. A file there is a link into the same repository's blobs
    folder; a link that leads anywhere else is not followed. The pinned revision is tried first, any other only has to hold the same bytes."""
    snapshots = repo / "snapshots"
    try:
        names = sorted(entry.name for entry in snapshots.iterdir() if entry.is_dir() and not entry.is_symlink())
        base = repo.resolve()
    except OSError:
        return None
    pinned = {item.revision for item in files}
    for name in sorted(names, key=lambda n: (n not in pinned, n)):
        folder = snapshots / name
        try:
            inside = all(item.filename and base in (folder / item.filename).resolve().parents for item in files)
        except (OSError, RuntimeError):
            continue
        if inside and all(item.filename and fetch.file_is_agreed(folder / item.filename, item) for item in files):
            return folder
    return None


def speech_model(home: DataHome, registry: Registry, environ: Optional[Mapping[str, str]] = None) -> Tuple[Optional[str], str]:
    """(the folder holding the speech model, "ready") when every file of it is there and is byte for byte what was agreed to, or (None, why not).

    The tool's own downloads folder (where the guided setup puts it) is looked in first, then the Hugging Face folder, where Freeform Studio's own `models fetch` puts the
    same model; a copy there counts only when each file has exactly the agreed size and checksum. The why is "incomplete" when the tool's own folder holds some of the files
    (or a file that is not what was agreed) and "missing" when nothing is there. Looks only: nothing is fetched, moved, repaired or deleted.
    """
    own, hub = speech_places(home, environ)
    files = speech_files(registry)
    if not files:
        return None, "missing"
    state = _own_folder_state(Path(own), files)
    if state == "ready":
        return own, "ready"
    found = _hub_snapshot(Path(hub), files)
    if found is not None:
        return str(found), "ready"
    return None, state
