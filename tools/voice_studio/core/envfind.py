# SPDX-License-Identifier: GPL-3.0-or-later
"""Finding the programs and the speech model the guided setup built or fetched: where they are if they are ready, and why not if they are not. Looks only; builds and fetches nothing.

The studio environment holds Freeform Studio's own programs (listening to recordings, building a training set); the training environment holds the trainer. Both are named in
data/environments.json. The speech model is the one pinned in data/sources.json and kept under the tool's downloads folder, where the setup put it.
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional, Tuple

from . import envbuild, fetch
from .consent import load_consent
from .envbuild import EnvPaths
from .envspec import load_environments
from .paths import DataHome
from .registry import Registry
from .setuprun import MODELS_FOLDER
from .system import RealSystem, System

SPEECH_FOLDER = "speech-small-en"                       # the registry's folder for the pinned speech model
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


def speech_model(home: DataHome, registry: Registry) -> Tuple[Optional[str], str]:
    """(the folder holding the speech model, "ready") when every file of it is there and is byte for byte what was agreed to, or (None, "missing")."""
    folder = Path(home.downloads) / MODELS_FOLDER / SPEECH_FOLDER
    files = [item for item in registry.items if item.kind == "model" and item.folder == SPEECH_FOLDER]
    if not files or not all(fetch.is_fetched(item, folder) for item in files):
        return None, "missing"
    return str(folder), "ready"
