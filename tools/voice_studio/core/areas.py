# SPDX-License-Identifier: GPL-3.0-or-later
"""What ACK Voice Studio keeps, and how precious each part is (plan P11; the storage catalogue of task VS-6.3, first used by the backup, task VS-6.1).

Every folder the tool makes inside a project, and every folder it keeps in its own place, is listed here once, with its kind (core/diskbudget.py::Kind: precious, rebuildable, disposable,
or the tool's own) and whether a project backup holds it. Backup, delete, refresh and uninstall decide "what is data" from this list instead of each keeping its own idea, and
`tests/test_vs_areas.py` fails when a path the tool names (core/paths.py) is in no area, so a new folder cannot be added without deciding how it is backed up and removed.

Nothing here touches the disk or says a word: the words for each area are in the text catalog under `areas.<id>`.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional, Tuple

from .diskbudget import Kind
from .paths import ProjectPaths


@dataclass(frozen=True)
class Area:
    id: str                         # also the end of its text in the catalog: `areas.<id>`
    kind: Kind
    backed_up: bool                 # a project backup holds (the precious part of) it
    entries: Tuple[str, ...]        # the names directly under the project's folder (or the tool's data home) that belong to it


PRECIOUS, REBUILDABLE, DISPOSABLE, TOOL = Kind.PRECIOUS, Kind.REBUILDABLE, Kind.DISPOSABLE, Kind.TOOL
_HERE = ProjectPaths("/x")
RECORD_FILES = (os.path.basename(_HERE.project_json), os.path.basename(_HERE.previous_json))       # named by core/paths.py, once

# Inside a project's folder (core/paths.py::ProjectPaths). A backup holds only the precious *parts* of an area that is backed up: of `recordings` the takes and the ACK packages (not the
# decoded copies), of `rounds` the record, each round's settings file and the saved points that are kept (not older ones, not the trainer's logs), of `exports` the finished zip files.
PROJECT_AREAS: Tuple[Area, ...] = (
    Area("record", PRECIOUS, True, RECORD_FILES),
    Area("recordings", PRECIOUS, True, ("recordings",)),
    Area("rounds", PRECIOUS, True, ("rounds",)),
    Area("exports", PRECIOUS, True, ("exports",)),
    Area("listening", DISPOSABLE, False, ("listening",)),
    Area("scratch", REBUILDABLE, False, ("scratch",)),
)

# Directly under the data home (core/paths.py::DataHome): the tool's own places and the people's projects.
HOME_AREAS: Tuple[Area, ...] = (
    Area("projects", PRECIOUS, True, ("projects",)),
    Area("backups", PRECIOUS, False, ("backups",)),             # never removed by the tool, and never inside a backup
    Area("tool", TOOL, False, ("tool",)),                       # the programs, the downloads and the starting voices: made again by setup (the voices are kept, never offered for removal)
    Area("state", PRECIOUS, False, ("state",)),                 # the consent record, the window's choices and the record of jobs: small
)


def project_area(entry: str) -> Optional[Area]:
    """The area of a name directly under a project's folder, or None when no area claims it."""
    return next((a for a in PROJECT_AREAS if entry in a.entries), None)


def home_area(entry: str) -> Optional[Area]:
    return next((a for a in HOME_AREAS if entry in a.entries), None)


def first_part(root: str, path: str) -> str:
    """The first name of `path` under `root` ("" when it is not under it). Text only: no disk is read."""
    prefix = root.rstrip("/") + "/"
    if not path.startswith(prefix):
        return ""
    return path[len(prefix):].split("/", 1)[0]
