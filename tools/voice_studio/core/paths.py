# SPDX-License-Identifier: GPL-3.0-or-later
"""Where ACK Voice Studio keeps things, under one folder in the person's home (plan decision D7: the Linux home, fast and private).

    ~/ack-voice-studio/
        projects/<id>/     one folder per person (core/project.py)
        tool/              the tool's own downloads and Python environments (shared by every project)
        state/             small records: the consent record, settings
        backups/           checked backups the tool makes before it copies anything in (outside every project)

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
    def voices(self) -> str:
        """Starting voices the person chose, one folder each. A kept copy: it cannot be downloaded again if the host removes it (plan D27)."""
        return self.downloads + "/voices"

    @property
    def environments(self) -> str:
        return self.tool + "/environments"

    @property
    def state(self) -> str:
        return self.root + "/state"

    @property
    def backups(self) -> str:
        return self.root + "/backups"

    @property
    def window_file(self) -> str:
        """The window's display choices (theme, accent, text size, scale): written only after the person says yes (core/windowprefs.py)."""
        return self.state + "/window.json"

    @property
    def consent_file(self) -> str:
        return self.state + "/consent.json"

    @property
    def jobs(self) -> str:
        return self.state + "/jobs"


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
    def rounds_file(self) -> str:
        """The record of every training round (core/rounds.py)."""
        return self.rounds + "/rounds.json"

    @property
    def rounds_previous(self) -> str:
        return self.rounds + "/rounds.json.previous"

    @property
    def rounds_lock(self) -> str:
        return self.rounds + "/.rounds.lock"

    @property
    def run(self) -> str:
        """The one folder every round trains in: the trainer adds a `lightning_logs/version_N` to it for each round and the checkpoints are inside."""
        return self.rounds + "/run"

    @property
    def round_configs(self) -> str:
        """The settings file each round's trainer writes, one per round, so a later round never overwrites an earlier one's."""
        return self.rounds + "/config"

    @property
    def exports(self) -> str:
        return self.root + "/exports"

    @property
    def default_scratch(self) -> str:
        return self.root + "/scratch"

    @property
    def folders(self) -> tuple:
        return (self.recordings, self.rounds, self.exports, self.default_scratch)


@dataclass(frozen=True)
class ScratchPaths:
    """Inside a project's scratch folder (the default one, or the folder core/scratch.py made on the place the person chose): the training sets and the
    working files of each round. Both can be made again from the recordings, so both are for *Free up space* (plan P11)."""
    root: str

    @property
    def datasets(self) -> str:
        return self.root + "/datasets"

    @property
    def caches(self) -> str:
        return self.root + "/caches"
