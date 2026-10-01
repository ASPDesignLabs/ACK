# SPDX-License-Identifier: GPL-3.0-or-later
"""The HTTP API. Phase 1 is API-only; the capture and review pages arrive in later phases."""
from __future__ import annotations

import asyncio
import hmac
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable, Dict, Optional
from urllib.parse import urlencode

from quart import Quart, Response, g, jsonify, redirect, request, send_file, send_from_directory

from . import __version__
from . import backup as backup_mod
from . import export as export_mod
from . import health
from .asr import AsrEngine
from .config import Config
from .edit import new_edit_doc, normalize_edit, validate_edit
from .jobs import EngineManager, JobRunner
from .storage import InvalidTakeId, TakeStore, atomic_write_bytes, read_json

MODEL_RE = re.compile(r"^[A-Za-z0-9._/-]{1,80}$")
LANG_RE = re.compile(r"^[a-z]{2,3}$")
COOKIE = "fs_token"
HISTORY_NAME_RE = re.compile(r"^edit-[A-Za-z0-9._-]{1,80}\.json$")
REFERENCE_MAX = 20000
_REFERENCE_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
STATIC_DIR = Path(__file__).parent / "static"
# The pages load only their own files: no inline scripts or styles, nothing from other sites.
CSP = ("default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; media-src 'self' blob:; "
       "connect-src 'self'; font-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'")


def address_without_token(path: str, pairs) -> str:
    """The same page's address with `token` taken out of the query. Always a path on this server, never `//host`, so it can't
    be turned into a jump to another site."""
    rest = [(k, v) for k, v in pairs if k != "token"]
    return "/" + path.lstrip("/") + (("?" + urlencode(rest)) if rest else "")


class ApiError(Exception):
    def __init__(self, status: int, message: str, **extra: Any):
        super().__init__(message)
        self.status = status
        self.message = message
        self.extra = extra


def create_app(cfg: Config, engine_factory: Optional[Callable[[Config, Optional[str]], AsrEngine]] = None) -> Quart:
    app = Quart("freeform_studio")
    app.config["MAX_CONTENT_LENGTH"] = cfg.max_chunk_bytes + 4096
    store = TakeStore(cfg.takes_dir)
    engines = EngineManager(cfg, engine_factory)
    runner = JobRunner(cfg, store, engines)
    backups = backup_mod.BackupScheduler(cfg, lambda: bool(store.ids()))
    app.freeform = SimpleNamespace(cfg=cfg, store=store, engines=engines, runner=runner, backups=backups)  # type: ignore[attr-defined]

    # ------------------------------------------------------------------ lifecycle
    @app.before_serving
    async def _start() -> None:
        await runner.start()
        await backups.start()

    @app.after_serving
    async def _stop() -> None:
        await backups.stop()
        await runner.stop()

    # ------------------------------------------------------------------ auth + errors
    def _authorized() -> bool:
        if not cfg.token:
            return True
        want = cfg.token.encode()
        header = request.headers.get("Authorization", "")
        candidates = [header[7:] if header.startswith("Bearer ") else "", request.cookies.get(COOKIE, ""),
                      request.args.get("token", "")]
        return any(c and hmac.compare_digest(c.encode(), want) for c in candidates)

    @app.before_request
    async def _gate() -> Optional[Response]:
        if request.path == "/healthz":
            return None
        if not _authorized():
            return jsonify(error="unauthorized: open the URL printed when the server started"), 401  # type: ignore[return-value]
        # Remember the login in a cookie only when it arrived as ?token= (a person opening the printed link).
        q = request.args.get("token", "")
        valid_link = bool(cfg.token and q) and hmac.compare_digest(q.encode(), cfg.token.encode())
        g.set_cookie = valid_link and request.cookies.get(COOKIE) != cfg.token
        if valid_link and request.method == "GET" and not request.path.startswith(("/api/", "/static/")):
            # Take the token out of the address bar: a link with the token in it would otherwise stay in the browser's
            # history, bookmarks and (if sync is on) the browser account's cloud. The cookie, set on this very response,
            # carries the login from here on.
            resp = redirect(address_without_token(request.path, request.args.items(multi=True)), 303)
            resp.headers["Cache-Control"] = "no-store"
            return resp
        return None

    @app.after_request
    async def _after(resp: Response) -> Response:
        if getattr(g, "set_cookie", False):
            resp.set_cookie(COOKIE, cfg.token or "", httponly=True, samesite="Strict",
                            secure=request.is_secure, max_age=60 * 60 * 24 * 90)
        resp.headers["Content-Security-Policy"] = CSP
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["Referrer-Policy"] = "no-referrer"
        if request.path.startswith("/api/"):
            # Recordings, transcripts and waveforms: the browser (and anything between it and this PC) must not keep a copy.
            resp.headers["Cache-Control"] = "private, no-store"
        return resp

    @app.errorhandler(ApiError)
    async def _api_error(err: ApiError):
        return jsonify(error=err.message, **err.extra), err.status

    @app.errorhandler(InvalidTakeId)
    async def _bad_id(_err: InvalidTakeId):
        return jsonify(error="unknown take"), 404

    def take_or_404(take_id: str) -> Dict[str, Any]:
        doc = store.get(take_id)
        if doc is None:
            raise ApiError(404, "unknown take")
        return doc

    # ------------------------------------------------------------------ basics
    @app.route("/healthz")
    async def healthz():
        return "ok"

    @app.route("/")
    async def index():
        return await send_from_directory(STATIC_DIR, "index.html", cache_timeout=0)

    @app.route("/review")
    @app.route("/review/<take_id>")
    async def review_page(take_id: str = ""):
        return await send_from_directory(STATIC_DIR, "review.html", cache_timeout=0)

    @app.route("/static/<path:filename>")
    async def static_files(filename: str):
        # no-cache: the browser re-checks each time, so a `git pull` shows up on the next reload
        return await send_from_directory(STATIC_DIR, filename, cache_timeout=0)

    @app.route("/api/status")
    async def status():
        return jsonify(version=__version__, code=cfg.code, output=str(cfg.output_dir), asr=engines.status(),
                       queue=runner.pending, busy=runner.busy,
                       disk=health.disk_status(cfg.output_dir, cfg.min_free_mb, cfg.warn_free_mb))

    # ------------------------------------------------------------------ takes
    @app.route("/api/takes", methods=["POST"])
    async def create_take():
        body = await request.get_json(silent=True) or {}
        fields: Dict[str, Any] = {}
        if isinstance(body.get("label"), str):
            fields["label"] = body["label"][:120]
        if isinstance(body.get("reference_text"), str):
            fields["reference_text"] = body["reference_text"][:20000]
        if isinstance(body.get("mime"), str):
            fields["mime"] = body["mime"][:80]
        client = body.get("client")
        if isinstance(client, dict):
            fields["client"] = {str(k)[:40]: (v if isinstance(v, (bool, int, float)) else str(v)[:200])
                                for k, v in list(client.items())[:20]}
        return jsonify(store.create(fields)), 201

    @app.route("/api/takes")
    async def list_takes():
        return jsonify(takes=store.list())

    @app.route("/api/takes/<take_id>")
    async def get_take(take_id: str):
        return jsonify(take_or_404(take_id))

    # ------------------------------------------------------------------ chunk upload
    @app.route("/api/takes/<take_id>/chunks", methods=["GET"])
    async def chunk_status(take_id: str):
        take_or_404(take_id)
        got = store.received(take_id)
        have = set(got)
        missing = [i for i in range(got[-1] + 1) if i not in have] if got else []
        return jsonify(received=len(got), highest=got[-1] if got else -1, missing=missing)

    @app.route("/api/takes/<take_id>/chunks/<int:n>", methods=["PUT"])
    async def put_chunk(take_id: str, n: int):
        take = take_or_404(take_id)
        if take["status"] not in ("recording", "error"):
            raise ApiError(409, f"take is {take['status']}; it no longer accepts audio")
        if n < 0 or n >= cfg.max_chunks:
            raise ApiError(400, "chunk index out of range")
        free = health.free_mb(cfg.output_dir)
        if free < cfg.min_free_mb and not store.path(take_id, "parts", f"{n:06d}.bin").exists():   # a repeat of a stored part is harmless
            raise ApiError(507, f"Your PC is almost out of disk space ({free:.0f} MB free). Free some up and sending carries on by "
                                "itself; what you have recorded is safe on this phone until then.")
        data = await request.get_data()
        if not data:
            raise ApiError(400, "empty chunk")
        if len(data) > cfg.max_chunk_bytes:
            raise ApiError(413, "chunk too large")
        store.write_chunk(take_id, n, data)
        return jsonify(ok=True, n=n, size=len(data))

    @app.route("/api/takes/<take_id>/finish", methods=["POST"])
    async def finish(take_id: str):
        take = take_or_404(take_id)
        if take["status"] not in ("recording", "error"):
            return jsonify(take), 200  # already finished or in progress: idempotent
        salvage = request.args.get("salvage") in ("1", "true", "yes")
        store.update(take_id, status="finishing", error=None)
        runner.enqueue("finish", take_id, {"salvage": salvage})
        return jsonify(store.get(take_id)), 202

    # ------------------------------------------------------------------ audio + waveform
    @app.route("/api/takes/<take_id>/audio")
    async def audio(take_id: str):
        take_or_404(take_id)
        path = store.path(take_id, "audio.wav")
        if not path.exists():
            raise ApiError(404, "audio is not ready yet")
        return await send_file(str(path), mimetype="audio/wav", conditional=True)  # honours Range: phones need it

    @app.route("/api/takes/<take_id>/peaks")
    async def peaks_meta(take_id: str):
        take_or_404(take_id)
        meta = store.read(take_id, "peaks.json")
        if meta is None:
            raise ApiError(404, "waveform is not ready yet")
        return jsonify(meta)

    @app.route("/api/takes/<take_id>/peaks/<int:spp>")
    async def peaks_data(take_id: str, spp: int):
        take_or_404(take_id)
        meta = store.read(take_id, "peaks.json")
        if meta is None or spp not in meta.get("levels", []):
            raise ApiError(404, "no such waveform level")
        return Response(store.path(take_id, f"peaks_{spp}.bin").read_bytes(), mimetype="application/octet-stream")

    # ------------------------------------------------------------------ transcript + edits
    @app.route("/api/takes/<take_id>/asr")
    async def get_asr(take_id: str):
        take_or_404(take_id)
        doc = store.read(take_id, "asr.json")
        if doc is None:
            raise ApiError(404, "not transcribed yet")
        return jsonify(doc)

    @app.route("/api/takes/<take_id>/edit", methods=["GET"])
    async def get_edit(take_id: str):
        take_or_404(take_id)
        doc = store.read(take_id, "edit.json")
        if doc is None:
            raise ApiError(404, "no edit document yet (transcription has not finished)")
        return jsonify(doc)

    @app.route("/api/takes/<take_id>/edit", methods=["PUT"])
    async def put_edit(take_id: str):
        take = take_or_404(take_id)
        body = await request.get_json(silent=True)
        if not isinstance(body, dict):
            raise ApiError(400, "expected a JSON object")
        norm = normalize_edit(body)
        rev = norm["rev"]
        if isinstance(rev, bool) or not isinstance(rev, int):
            raise ApiError(400, "rev must be the integer you last received")
        with store.lock:
            current = store.read(take_id, "edit.json")
            if current is None:
                raise ApiError(404, "no edit document yet")
            if rev != current["rev"]:
                raise ApiError(409, "someone else changed this take; reload to see their edits", current=current)
            errors = validate_edit(norm, float(take.get("duration") or 0.0))
            if errors:
                raise ApiError(400, "invalid edit", details=errors[:20])
            store.archive(take_id, "edit.json", "edit_history", f"rev{current['rev']:05d}")
            store.prune_thinned(take_id, "edit_history")
            new = new_edit_doc(norm["segments"], current["rev"] + 1)
            store.write(take_id, "edit.json", new)
        return jsonify(rev=new["rev"])

    @app.route("/api/takes/<take_id>/edit/history")
    async def edit_history(take_id: str):
        take_or_404(take_id)
        d = store.path(take_id, "edit_history")
        items = []
        if d.is_dir():
            for p in sorted(d.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)[:100]:
                try:
                    doc = json.loads(p.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    continue
                segs = doc.get("segments") or []
                items.append({"name": p.name, "time": datetime.fromtimestamp(p.stat().st_mtime, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                              "rev": doc.get("rev"), "counts": {
                                  "segments": len(segs), "approved": sum(1 for x in segs if x.get("status") == "approved"),
                                  "dropped": sum(1 for x in segs if x.get("status") == "dropped")}})
        return jsonify(history=items)

    @app.route("/api/takes/<take_id>/edit/restore", methods=["POST"])
    async def edit_restore(take_id: str):
        take = take_or_404(take_id)
        body = await request.get_json(silent=True) or {}
        name, rev = body.get("name"), body.get("rev")
        if not isinstance(name, str) or not HISTORY_NAME_RE.match(name):
            raise ApiError(400, "bad version name")
        if isinstance(rev, bool) or not isinstance(rev, int):
            raise ApiError(400, "rev must be the integer you last received")
        with store.lock:
            current = store.read(take_id, "edit.json")
            if current is None:
                raise ApiError(404, "no edit document yet")
            if rev != current["rev"]:
                raise ApiError(409, "someone else changed this take; reload first", current=current)
            snap = store.read(take_id, f"edit_history/{name}")
            if snap is None:
                raise ApiError(404, "that version no longer exists")
            norm = normalize_edit(snap)
            errors = validate_edit(norm, float(take.get("duration") or 0.0))
            if errors:
                raise ApiError(400, "that version can't be restored", details=errors[:10])
            store.archive(take_id, "edit.json", "edit_history", f"before-restore-{time.strftime('%Y%m%d-%H%M%S')}")
            new = new_edit_doc(norm["segments"], current["rev"] + 1)
            store.write(take_id, "edit.json", new)
        return jsonify(new)

    @app.route("/api/takes/<take_id>/reference", methods=["PUT"])
    async def put_reference(take_id: str):
        """Save or replace the text that was being read. The text it replaces is kept in reference_history/."""
        take_or_404(take_id)
        body = await request.get_json(silent=True)
        if not isinstance(body, dict) or not isinstance(body.get("text"), str):
            raise ApiError(400, "text must be a string")
        text = _REFERENCE_CONTROL.sub("", body["text"].replace("\r\n", "\n").replace("\r", "\n"))
        if len(text) > REFERENCE_MAX:
            raise ApiError(400, f"the text is longer than {REFERENCE_MAX} characters")
        with store.lock:
            old = store.get(take_id).get("reference_text") or ""
            if old.strip() and old != text:
                stamp = time.strftime("%Y%m%d-%H%M%S")
                name, n = f"ref-{stamp}.txt", 1
                while store.path(take_id, "reference_history", name).exists():
                    n += 1
                    name = f"ref-{stamp}-{n}.txt"
                atomic_write_bytes(store.path(take_id, "reference_history", name), old.encode("utf-8"))
                store.prune(take_id, "reference_history", 20)
            doc = store.update(take_id, reference_text=text)
        return jsonify(reference_text=doc["reference_text"])

    # ------------------------------------------------------------------ backups
    @app.route("/api/backup", methods=["GET"])
    async def backup_status():
        return jsonify(backups.status())

    @app.route("/api/backup", methods=["POST"])
    async def backup_now():
        body = await request.get_json(silent=True)
        force = isinstance(body, dict) and body.get("force") is True
        try:
            result = await backups.run_now(force)
        except backup_mod.BackupBusy as err:
            raise ApiError(409, str(err))
        except backup_mod.BackupError as err:
            raise ApiError(400, str(err))
        return jsonify(skipped=result.skipped, reason=result.reason, name=result.path.name if result.path else None, takes=result.takes,
                       files=result.files, archive_bytes=result.archive_bytes, pruned=result.pruned, status=backups.status())

    # ------------------------------------------------------------------ training clips
    async def run_export(take_ids: Optional[list], apply_it: bool):
        """Preview or perform an export, off the event loop (it reads audio and runs ffmpeg)."""
        try:
            work = export_mod.apply if apply_it else export_mod.make_plan
            plan = await asyncio.to_thread(work, cfg.output_dir, cfg.code, take_ids)
        except export_mod.ExportBusy as err:
            raise ApiError(409, str(err))
        except export_mod.ExportError as err:
            raise ApiError(400, str(err))
        return jsonify(plan.report())

    @app.route("/api/export", methods=["GET", "POST"])
    async def export_all():
        return await run_export(None, request.method == "POST")

    @app.route("/api/takes/<take_id>/export", methods=["GET", "POST"])
    async def export_take(take_id: str):
        take_or_404(take_id)
        return await run_export([take_id], request.method == "POST")

    @app.route("/api/takes/<take_id>/transcribe", methods=["POST"])
    async def transcribe(take_id: str):
        take = take_or_404(take_id)
        if take["status"] in ("recording", "finishing", "queued", "transcribing"):
            raise ApiError(409, f"take is {take['status']}")
        if not store.path(take_id, "audio.wav").exists():
            raise ApiError(409, "there is no decoded audio yet")
        body = await request.get_json(silent=True) or {}
        opts: Dict[str, Any] = {}
        if body.get("model"):
            if not isinstance(body["model"], str) or not MODEL_RE.match(body["model"]):
                raise ApiError(400, "bad model name")
            opts["model"] = body["model"]
        if body.get("language"):
            if not isinstance(body["language"], str) or not LANG_RE.match(body["language"]):
                raise ApiError(400, "bad language code")
            opts["language"] = body["language"]
        for key, limit in (("initial_prompt", 1000), ("hotwords", 500)):
            if isinstance(body.get(key), str):
                opts[key] = body[key][:limit]
        if body.get("regenerate"):
            edit = store.read(take_id, "edit.json") or {}
            approved = sum(1 for s in edit.get("segments", []) if s.get("status") == "approved")
            if approved and not body.get("force"):
                raise ApiError(409, "regenerating would replace segments you already approved; "
                                    "pass force to confirm (the current edits are archived first)", approved=approved)
            opts["regenerate"] = True
        store.update(take_id, status="queued", progress=0.0, error=None)
        runner.enqueue("transcribe", take_id, opts)
        return jsonify(store.get(take_id)), 202

    @app.route("/api/asr/release", methods=["POST"])
    async def release():
        if runner.busy:
            raise ApiError(409, "a job is running; try again when it finishes")
        engines.unload()
        return jsonify(engines.status())

    return app
