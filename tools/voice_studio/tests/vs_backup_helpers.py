# SPDX-License-Identifier: GPL-3.0-or-later
"""Helpers for the project backup tests: a project with everything a backup holds and the things it leaves out, and a way to forge an archive to see what verifying and restoring refuse."""
import hashlib
import io
import json
import os
import tarfile
from pathlib import Path

from vs_listen_helpers import VOICE_FOLDER, ListenRig
from voice_studio.core import projectbackup as pb

CODE = "en-US"
TAKE = "t20260930-%06d-%04x"


class BackupRig(ListenRig):
    """The shared project (called Voice check), two finished rounds with their settings files and saved points, a voice file, two recordings, an ACK package, and some of everything a backup
    leaves out. The backups go to `self.dest`, outside the project."""

    def __init__(self, tmp_path, *, rounds=2, voice=True, takes=2, package=True, junk=True, **kw):
        super().__init__(tmp_path, make=False, **kw)
        self.dest = str(tmp_path / "backups")
        if rounds:
            self.finish_rounds(rounds)
        if voice:
            self.make_voice(VOICE_FOLDER)
        for number in range(1, takes + 1):
            self.take(number)
        if package:
            self.package("p.zip")
        if junk:
            self.leave_out_stuff()

    @property
    def recordings_root(self):
        return Path(self.paths.recordings) / "_freeform" / CODE

    def take(self, number, raw=None, extra=None):
        take_id = TAKE % (number, number)
        folder = self.recordings_root / "takes" / take_id
        (folder / "edit_history").mkdir(parents=True, exist_ok=True)
        (folder / "take.json").write_text(json.dumps({"id": take_id, "status": "ready", "duration": 60.0}))
        (folder / "edit.json").write_text(json.dumps({"schema": 1, "rev": 1, "segments": []}))
        (folder / "asr.json").write_text(json.dumps({"engine": "fake"}))
        (folder / "raw.webm").write_bytes(raw if raw is not None else b"RAW" * 1000 + bytes([number]))
        (folder / "edit_history" / "edit-1.json").write_text("{}")
        for name, data in (extra or {}).items():
            (folder / name).write_bytes(data)
        return folder

    def package(self, name, data=b"PK\x03\x04package"):
        folder = self.recordings_root / "incoming"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / name).write_bytes(data)
        return folder / name

    def leave_out_stuff(self):
        (self.recordings_root / "takes" / (TAKE % (1, 1)) / "audio.wav").write_bytes(b"decoded" * 50)             # the decoded copy: made again from the raw audio
        (self.recordings_root / "token").write_text("secret")
        Path(self.paths.default_scratch, "datasets", "d1", "wav").mkdir(parents=True, exist_ok=True)
        Path(self.paths.default_scratch, "datasets", "d1", "wav", "a.wav").write_bytes(b"RIFF" * 100)
        Path(self.paths.listening, "round-001", "heard-20261011-120000").mkdir(parents=True, exist_ok=True)
        Path(self.paths.listening, "round-001", "heard-20261011-120000", "clip-1.wav").write_bytes(b"RIFF" * 50)

    def project_plan(self, **kw):
        free = kw.pop("free", 10 ** 12)
        return pb.plan_backup(self.paths, self.home, "voice-check", kw.pop("destination", self.dest), free, **kw)

    def backup(self, now=None, **kw):
        plan = self.project_plan(**kw)
        return pb.create(plan, self.paths, now)

    def tree(self, root=None):
        base = Path(root or self.paths.root)
        found = {}
        for path in sorted(base.rglob("*")):
            if path.is_file() and not path.is_symlink():
                found[str(path.relative_to(base))] = hashlib.sha256(path.read_bytes()).hexdigest()
        return found


def forge(path, members, manifest="auto", project="voice-check", schema=1, extra_manifest=None):
    """A tar archive with exactly these members, `(name, data)` or `(name, data, tarinfo type)`, and a manifest that lists them (or the one given). For what verify and restore must refuse."""
    path = str(path)
    entries = []
    with open(path, "wb") as out, tarfile.open(fileobj=out, mode="w") as tar:
        for member in members:
            name, data = member[0], member[1]
            kind = member[2] if len(member) > 2 else tarfile.REGTYPE
            info = tarfile.TarInfo(name)
            info.type = kind
            if kind == tarfile.REGTYPE:
                info.size = len(data)
                tar.addfile(info, io.BytesIO(data))
                entries.append({"path": name, "part": "record", "size": len(data), "sha256": hashlib.sha256(data).hexdigest()})
            else:
                info.linkname = "/etc/passwd"
                tar.addfile(info)
        if manifest is not None:
            body = {"schema": schema, "app": "ack-voice-studio", "project": project, "created": "2026-10-16T09:00:00+00:00", "files": entries} if manifest == "auto" else manifest
            if extra_manifest:
                body = dict(body, **extra_manifest)
            blob = json.dumps(body).encode("utf-8") if not isinstance(body, bytes) else body
            info = tarfile.TarInfo(pb.MANIFEST)
            info.size = len(blob)
            tar.addfile(info, io.BytesIO(blob))
    return path
