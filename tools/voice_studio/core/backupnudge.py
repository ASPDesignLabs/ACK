# SPDX-License-Identifier: GPL-3.0-or-later
"""The reminder to back up (plan decisions D7 and P17: "nudged hard" after recording and before training).

A project that has never been backed up on this computer, or that has changed in anything precious since its last backup, gets one short reminder and the command to run, printed by
`rounds start` before it asks, and by bringing recordings in after it adds them. It is a reminder and nothing more: it never writes a file, never blocks, and says nothing when the project
is up to date or has nothing to lose. It lives in its own small file so the commands that print it do not need the backup command's own front.
"""
from __future__ import annotations

from typing import List, Optional

from . import projectbackup as pb, rounds as rd
from .paths import DataHome, ProjectPaths
from .project import Project
from .text import Catalog

BACKUP_COMMAND = "python3 -m voice_studio.backup"


def when_text(stamp: str) -> str:
    return stamp.replace("T", " ").replace("+00:00", " UTC")


def delete_line(home: DataHome, project: Project, paths: ProjectPaths, cat: Catalog) -> Optional[str]:
    """The sentence that goes under "copy anything you may want later" when a project is about to be deleted: whether there is a backup, and where it is. Looks only. A damaged record of
    rounds is for the delete to say, so nothing is added; a project with nothing to hold (no project record at all) gets no sentence either."""
    try:
        standing = pb.standing(home, paths, project.id)
    except rd.RoundsError:
        return None
    command = "%s now --project %s" % (BACKUP_COMMAND, project.id)
    if standing.state == pb.NEVER:
        return cat.t("projects.delete.backup_never", name=project.name, command=command)
    if standing.state == pb.CHANGED:
        return cat.t("projects.delete.backup_changed", name=project.name, when=when_text(standing.last), folder=standing.folder, command=command)
    if standing.last:
        return cat.t("projects.delete.backup_current", name=project.name, when=when_text(standing.last), folder=standing.folder)
    return None


def nudge_lines(home: DataHome, project: Project, paths: ProjectPaths, cat: Catalog, record: Optional[rd.Record] = None) -> List[str]:
    """What to say before going on. Looks only. A damaged record of rounds is for the command that reads it to say, not for a reminder."""
    try:
        standing = pb.standing(home, paths, project.id, record)
    except rd.RoundsError:
        return []
    command = "%s now --project %s" % (BACKUP_COMMAND, project.id)
    if standing.state == pb.NEVER:
        return [cat.t("backup.nudge_never", name=project.name, command=command)]
    if standing.state == pb.CHANGED:
        return [cat.t("backup.nudge_changed", name=project.name, when=when_text(standing.last), command=command)]
    return []
