"""The HTTP API. Phase 1 is API-only; the capture and review pages arrive in later phases."""
from __future__ import annotations

import hmac
import re
from types import SimpleNamespace
from typing import Any, Callable, Dict, Optional

from quart import Quart, Response, g, jsonify, request, send_file

from . import __version__
from .asr import AsrEngine
from .config import Config
from .edit import new_edit_doc, normalize_edit, validate_edit
from .jobs import EngineManager, JobRunner
from .storage import InvalidTakeId, TakeStore, read_json

MODEL_RE = re.compile(r"^[A-Za-z0-9._/-]{1,80}$")
LANG_RE = re.compile(r"^[a-z]{2,3}$")
COOKIE = "fs_token"


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
    app.freeform = SimpleNamespace(cfg=cfg, store=store, engines=engines, runner=runner)  # type: ignore[attr-defined]

    # ------------------------------------------------------------------ lifecycle
    @app.before_serving
    async def _start() -> None:
        await runner.start()

    @app.after_serving
    async def _stop() -> None:
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
        g.set_cookie = bool(cfg.token and q) and hmac.compare_digest(q.encode(), cfg.token.encode()) \
            and request.cookies.get(COOKIE) != cfg.token
        return None

    @app.after_request
    async def _cookie(resp: Response) -> Response:
        if getattr(g, "set_cookie", False):
            resp.set_cookie(COOKIE, cfg.token or "", httponly=True, samesite="Strict",
                            secure=request.is_secure, max_age=60 * 60 * 24 * 90)
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
        return ("<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width'>"
                "<title>Freeform Studio</title><body style='font:16px system-ui;padding:1rem'>"
                "<h1>Freeform Studio</h1><p>Backend is running (API only in this version). "
                "<a href='/api/status'>Status</a> &middot; <a href='/api/takes'>Takes</a></p></body>")

    @app.route("/api/status")
    async def status():
        return jsonify(version=__version__, code=cfg.code, output=str(cfg.output_dir), asr=engines.status(),
                       queue=runner.pending, busy=runner.busy)

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
            store.prune(take_id, "edit_history", 30)
            new = new_edit_doc(norm["segments"], current["rev"] + 1)
            store.write(take_id, "edit.json", new)
        return jsonify(rev=new["rev"])

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
