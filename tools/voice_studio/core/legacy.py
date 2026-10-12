# SPDX-License-Identifier: GPL-3.0-or-later
"""Finding the manual setup that came before (plan decision D13). Read-only: it looks and reports, it never changes or removes anything.

What it finds is shown to the person, who can then ask for a checked copy of the recordings into a project (a later task). The old
folders are never moved or deleted by anything here.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

from .system import System

MAX_DATASETS_LISTED = 20


@dataclass(frozen=True)
class LegacyFindings:
    recorder_output: Optional[str] = None          # ~/piper-recording-studio/output
    prompted_languages: Tuple[str, ...] = ()       # language folders inside it (en-US, ...)
    prompted_groups: int = 0                       # prompt-file folders of recorded takes
    freeform_takes: int = 0                        # takes made with Freeform Studio (output/_freeform/<code>/takes)
    trainer_repo: Optional[str] = None             # ~/piper1-gpl
    trainer_env: bool = False                      # its .venv works
    trainer_runs: bool = False                     # lightning_logs: it has trained something, so there are checkpoints
    freeform_env: bool = False                     # ~/freeform-studio-venv
    piper_folder: Optional[str] = None             # ~/piper: datasets, caches, exported voices
    datasets: Tuple[str, ...] = ()                 # folder names inside ~/piper
    tools_clone: Optional[str] = None              # ~/ack-tools

    @property
    def any_found(self) -> bool:
        return any([self.recorder_output, self.trainer_repo, self.freeform_env, self.piper_folder, self.tools_clone])

    @property
    def has_recordings(self) -> bool:
        return self.prompted_groups > 0 or self.freeform_takes > 0


def detect_legacy(system: System, home: str) -> LegacyFindings:
    base = home.rstrip("/")

    def folder(name: str) -> Optional[str]:
        path = base + "/" + name
        return path if system.is_dir(path) else None

    output = folder("piper-recording-studio/output")
    languages, groups, takes = [], 0, 0
    if output:
        for entry in sorted(system.listdir(output) or []):
            if entry.startswith("_") or not system.is_dir(output + "/" + entry):
                continue
            languages.append(entry)
            groups += sum(1 for g in (system.listdir(output + "/" + entry) or []) if system.is_dir(output + "/" + entry + "/" + g))
        for code in system.listdir(output + "/_freeform") or []:
            takes += len(system.listdir(output + "/_freeform/" + code + "/takes") or [])
    repo = folder("piper1-gpl")
    piper = folder("piper")
    datasets = tuple(sorted(n for n in (system.listdir(piper) or []) if system.is_dir(piper + "/" + n))[:MAX_DATASETS_LISTED]) if piper else ()
    return LegacyFindings(
        recorder_output=output, prompted_languages=tuple(languages), prompted_groups=groups, freeform_takes=takes,
        trainer_repo=repo, trainer_env=bool(repo) and system.exists(repo + "/.venv/bin/python"), trainer_runs=bool(repo) and system.is_dir(repo + "/lightning_logs"),
        freeform_env=system.exists(base + "/freeform-studio-venv/bin/python"), piper_folder=piper, datasets=datasets, tools_clone=folder("ack-tools"))
