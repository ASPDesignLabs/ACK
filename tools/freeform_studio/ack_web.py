# SPDX-License-Identifier: GPL-3.0-or-later
"""The pages' side of importing from ACK: put a package where Freeform Studio can see it, look inside it, add it.

The command line does all of this too (ack_import.py); these routes exist so the same steps work from the browser, which matters
when the server runs somewhere the package file isn't easy to reach (for example inside WSL while the file sits in Windows).

    <output>/_freeform/<code>/incoming/      packages live here. Nothing in this folder is ever deleted or changed by the program.

Everything is checked the same way as on the command line: a package is verified completely before it is looked at, and importing only
adds. Only one package is being checked or imported at a time.
"""
from __future__ import annotations

import asyncio
import os
import re
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Type

from quart import jsonify, request

from . import ack_import
from .ack_package import PackageError, open_package
from .config import Config
from .health import free_mb
from .jobs import JobRunner
from .storage import TakeStore

NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._ -]{0,100}\.zip$")
MAX_UPLOAD_BYTES = 4 * 1024 ** 3        # more than a package ACK writes (it stays under 2 GB)
ZIP_STARTS = (b"PK\x03\x04", b"PK\x05\x06")


def incoming_dir(cfg: Config) -> Path:
    return cfg.root / "incoming"


def _iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def register(app: Any, cfg: Config, store: TakeStore, runner: JobRunner, ApiError: Type[Exception]) -> None:
    busy = asyncio.Lock()

    def named(name: Any) -> Path:
        if not isinstance(name, str) or not NAME_RE.match(name) or ".." in name:
            raise ApiError(400, "that is not a package name: use letters, numbers, spaces, dots, dashes or underscores, ending in .zip")
        return incoming_dir(cfg) / name

    def existing(name: Any) -> Path:
        path = named(name)
        if path.is_symlink() or not path.is_file():
            raise ApiError(404, f"there is no package called {name} in the incoming folder")
        return path

    # ------------------------------------------------------------------ what is waiting
    @app.route("/api/ack/incoming")
    async def ack_list():
        d = incoming_dir(cfg)
        packages: List[Dict[str, Any]] = []
        partial: List[Dict[str, Any]] = []
        if d.is_dir():
            for p in sorted(d.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
                if p.is_symlink() or not p.is_file():
                    continue
                st = p.stat()
                if NAME_RE.match(p.name):
                    packages.append({"name": p.name, "bytes": st.st_size, "modified": _iso(st.st_mtime)})
                elif p.name.endswith(".part") and NAME_RE.match(p.name[:-5]):
                    partial.append({"name": p.name[:-5], "bytes": st.st_size})
        return jsonify(folder=str(d), packages=packages, partial=partial, busy=busy.locked())

    # ------------------------------------------------------------------ bringing a package in from this browser
    @app.route("/api/ack/incoming/<name>", methods=["PUT"])
    async def ack_upload(name: str):
        """One piece of a package, appended at `offset`. Offset 0 starts the upload over; any other offset must be exactly where the
        last piece ended (the reply says where that was, so an interrupted upload carries on instead of starting again)."""
        final = named(name)
        part = final.with_name(final.name + ".part")
        if final.exists():
            raise ApiError(409, f"a package called {name} is already in the incoming folder")
        offset = request.args.get("offset", type=int)
        if offset is None or offset < 0:
            raise ApiError(400, "offset is missing")
        data = await request.get_data()
        if not data:
            raise ApiError(400, "empty piece")
        if offset + len(data) > MAX_UPLOAD_BYTES:
            raise ApiError(413, "that file is larger than a package from ACK can be")
        have = part.stat().st_size if part.exists() else 0
        if offset != 0 and offset != have:
            raise ApiError(409, "the upload is out of step", received=have)
        free = free_mb(cfg.output_dir)
        if free < cfg.min_free_mb + len(data) / (1024 * 1024):
            raise ApiError(507, f"Your PC is almost out of disk space ({free:.0f} MB free). Free some up and send the file again.")
        part.parent.mkdir(parents=True, exist_ok=True)

        def write() -> None:
            with open(part, "wb" if offset == 0 else "r+b") as f:
                f.seek(offset)
                f.write(data)
        await asyncio.to_thread(write)
        return jsonify(received=offset + len(data))

    @app.route("/api/ack/incoming/<name>/done", methods=["POST"])
    async def ack_upload_done(name: str):
        final = named(name)
        part = final.with_name(final.name + ".part")
        if not part.is_file():
            raise ApiError(404, "nothing was uploaded under that name")
        if final.exists():
            raise ApiError(409, f"a package called {name} is already in the incoming folder")
        body = await request.get_json(silent=True) or {}
        size = part.stat().st_size
        if isinstance(body.get("size"), int) and body["size"] != size:
            raise ApiError(409, f"only {size} of {body['size']} bytes arrived. Send the file again.", received=size)
        with open(part, "rb") as f:
            head = f.read(4)
        if head not in ZIP_STARTS:
            part.unlink()                                   # our own temporary upload, not the person's file
            raise ApiError(400, "that file is not a zip file, so it cannot be a package from ACK")

        def finish() -> None:
            with open(part, "rb+") as f:
                os.fsync(f.fileno())
            os.replace(part, final)
        await asyncio.to_thread(finish)
        return jsonify(name=name, bytes=size)

    # ------------------------------------------------------------------ looking inside, then adding
    def _check(path: Path, only: Optional[List[str]] = None):
        pkg = open_package(path)
        return pkg, ack_import.make_plan(pkg, cfg.output_dir, cfg.code, only)

    @app.route("/api/ack/check", methods=["POST"])
    async def ack_check():
        body = await request.get_json(silent=True) or {}
        path = existing(body.get("name"))
        if busy.locked():
            raise ApiError(409, "another package is being checked or imported right now; try again in a moment")
        async with busy:
            try:
                pkg, plan = await asyncio.to_thread(_check, path)
            except (PackageError, ack_import.ImportProblem) as err:
                raise ApiError(400, str(err))
        return jsonify(package=pkg.summary(), warnings=pkg.warnings, created=pkg.manifest["created"],
                       sessions=[asdict(s) for s in plan.sessions], takes_dir=str(plan.takes_dir), to_import=len(plan.to_import),
                       need_mb=round(plan.need_mb), free_mb=round(plan.free_mb), min_free_mb=round(plan.min_free_mb),
                       enough_room=plan.enough_room)

    @app.route("/api/ack/import", methods=["POST"])
    async def ack_import_now():
        body = await request.get_json(silent=True) or {}
        path = existing(body.get("name"))
        only = body.get("sessions")
        if only is not None and (not isinstance(only, list) or not all(isinstance(s, str) for s in only)):
            raise ApiError(400, "sessions should be a list of session ids")
        if busy.locked():
            raise ApiError(409, "another package is being checked or imported right now; try again in a moment")
        async with busy:
            def work():
                pkg, plan = _check(path, only or None)
                return ack_import.apply_import(plan)
            try:
                created = await asyncio.to_thread(work)
            except ack_import.NotEnoughRoom as err:
                raise ApiError(507, str(err))
            except (PackageError, ack_import.ImportProblem) as err:
                raise ApiError(400, str(err))
        for c in created:
            runner.enqueue("finish", c.take_id, {})            # decode, listen, transcribe: the same steps as any recording
        return jsonify(created=[asdict(c) for c in created])

    # ------------------------------------------------------------------ the phone's notes for one recording
    @app.route("/api/takes/<take_id>/ack")
    async def ack_notes(take_id: str):
        notes = store.read(take_id, "ack_clips.json")
        if notes is None:
            raise ApiError(404, "this recording did not come from ACK")
        return jsonify(notes=notes, checks=store.read(take_id, "ack_checks.json"))
