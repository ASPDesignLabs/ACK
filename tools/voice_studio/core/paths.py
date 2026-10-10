# SPDX-License-Identifier: GPL-3.0-or-later
"""Where ACK Voice Studio keeps things, under one folder in the person's home (plan decision D7: the Linux home, fast and private).

    ~/ack-voice-studio/
        projects/<id>/     one folder per person (core/project.py)
        tool/              the tool's own downloads and Python environments (shared by every project)
        state/             small records: the consent record, settings

Nothing here touches the disk; it only names places.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath

DATA_HOME_NAME = "ack-voice-studio"


@dataclass(frozen=True)
class DataHome:
    home: str

    @property
    def root(self) -> str:
        return str(PurePosixPath(self.home) / DATA_HOME_NAME)

    @property
    def projects(self) -> str:
        return self.root + "/projects"

    @property
    def tool(self) -> str:
        return self.root + "/tool"

    @property
    def downloads(self) -> str:
        return self.tool + "/downloads"

    @property
    def environments(self) -> str:
        return self.tool + "/environments"

    @property
    def state(self) -> str:
        return self.root + "/state"

    @property
    def consent_file(self) -> str:
        return self.state + "/consent.json"


@dataclass(frozen=True)
class ProjectPaths:
    root: str                       # <projects>/<id>

    @property
    def project_json(self) -> str:
        return self.root + "/project.json"

    @property
    def previous_json(self) -> str:
        return self.root + "/project.json.previous"

    @property
    def recordings(self) -> str:
        return self.root + "/recordings"

    @property
    def rounds(self) -> str:
        return self.root + "/rounds"

    @property
    def exports(self) -> str:
        return self.root + "/exports"

    @property
    def default_scratch(self) -> str:
        return self.root + "/scratch"

    @property
    def folders(self) -> tuple:
        return (self.recordings, self.rounds, self.exports, self.default_scratch)
