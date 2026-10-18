# SPDX-License-Identifier: GPL-3.0-or-later
"""Which copy of a set of programs is in use (plan task VS-6.6, decision P18).

An environment's folder is named for what it is built from (core/envbuild.py), so the same inputs always mean the same folder. A *rebuild* wants a second, complete copy of the same
programs beside the first, so that nothing is lost if it fails and nothing is switched until it works. The copy's number is kept here: `state/environments.json` holds, for each set of
programs, its generation, and the builder puts a generation above 0 into the folder's name. Generation 0 is what every computer has until a rebuild has finished, and it adds nothing to
the name, so no existing folder changes name. The number is only raised after the new copy has passed its self-test: until then the old copy is still the one in use.

Plain Python, no words. A missing or damaged file reads as "no rebuild has happened", which is the safe reading: the old copy stays the one in use.
"""
from __future__ import annotations

import os
import re
from typing import Dict

from . import jobs
from .paths import DataHome

FILE = "environments.json"
SCHEMA = 1
MAX_GENERATION = 9999
ENV_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}\Z")


def path_of(home: DataHome) -> str:
    return home.state + "/" + FILE


def read(home: DataHome) -> Dict[str, int]:
    """Every generation above 0 that is noted. Never raises; anything that is not understood is left out."""
    data = jobs.read_json(path_of(home))
    found = data.get("generations") if isinstance(data, dict) else None
    if not isinstance(found, dict):
        return {}
    return {k: v for k, v in found.items() if isinstance(k, str) and ENV_ID.match(k) and isinstance(v, int) and not isinstance(v, bool) and 0 < v <= MAX_GENERATION}


def generation_of(home: DataHome, env_id: str) -> int:
    return read(home).get(env_id, 0)


def write(home: DataHome, env_id: str, generation: int) -> None:
    """Note that this set of programs is now at `generation`, keeping every other note. Atomic and for the owner only. Raises OSError when it cannot be written (the caller says so:
    the new copy is whole, and the old one stays in use until the note is made)."""
    if not ENV_ID.match(env_id) or not 0 <= generation <= MAX_GENERATION:
        raise ValueError("not a generation of an environment: %r %r" % (env_id, generation))
    noted = read(home)
    if generation:
        noted[env_id] = generation
    else:
        noted.pop(env_id, None)
    os.makedirs(home.state, mode=0o700, exist_ok=True)
    jobs.write_json(path_of(home), {"schema": SCHEMA, "generations": noted})
