# SPDX-License-Identifier: GPL-3.0-or-later
"""One background worker runs the heavy jobs (assemble+decode, transcribe) strictly one at a time."""
from __future__ import annotations

import asyncio
import logging
import threading
import time
from typing import Any, Callable, Dict, Optional

from .asr import AsrEngine, AsrOptions, EngineError, make_engine
from .audio import FfmpegError, compute_peaks, decode_to_wav, wav_info
from .config import Config
from .edit import new_edit_doc
from .pipeline import propose_segments
from .repair import needs_repair, raw_file, write_derived
from .segmenter import SegOptions
from .storage import ChunkGap, NoChunks, TakeStore, atomic_write_bytes, ext_for_mime, now_iso

_LOG = logging.getLogger(__name__)


class JobError(Exception):
    """A failure whose message is safe and useful to show to the user."""


class EngineManager:
    def __init__(self, cfg: Config, factory: Optional[Callable[[Config, Optional[str]], AsrEngine]] = None):
        self.cfg = cfg
        self._factory = factory or make_engine
        self._engine: Optional[AsrEngine] = None
        self._lock = threading.Lock()

    def get(self, model: Optional[str] = None) -> AsrEngine:
        model = model or self.cfg.asr_model
        with self._lock:
            if self._engine is None or self._engine.model != model:
                if self._engine is not None:
                    self._engine.unload()
                self._engine = self._factory(self.cfg, model)
            return self._engine

    def unload(self) -> None:
        with self._lock:
            if self._engine is not None:
                self._engine.unload()

    @property
    def loaded(self) -> bool:
        return bool(self._engine and self._engine.loaded)

    def status(self) -> Dict[str, Any]:
        return {"engine": self.cfg.asr_engine, "model": (self._engine.model if self._engine else self.cfg.asr_model),
                "device": self.cfg.asr_device, "compute_type": self.cfg.compute_type, "loaded": self.loaded}


class JobRunner:
    def __init__(self, cfg: Config, store: TakeStore, engines: EngineManager):
        self.cfg = cfg
        self.store = store
        self.engines = engines
        self._q: Optional["asyncio.Queue[tuple]"] = None  # created in start(), inside the running loop
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._tasks: list = []
        self._busy = False
        self._last = time.monotonic()

    @property
    def busy(self) -> bool:
        return self._busy

    @property
    def pending(self) -> int:
        return (self._q.qsize() if self._q else 0) + (1 if self._busy else 0)

    async def start(self) -> None:
        self._loop = asyncio.get_running_loop()
        self._q = asyncio.Queue()
        self._tasks = [asyncio.create_task(self._worker())]
        if self.cfg.asr_idle_unload_s > 0:
            self._tasks.append(asyncio.create_task(self._idle_unloader()))
        self._recover()

    async def stop(self) -> None:
        for t in self._tasks:
            t.cancel()
        for t in self._tasks:
            try:
                await t
            except (asyncio.CancelledError, Exception):
                pass
        self._tasks = []

    async def wait_idle(self) -> None:
        if self._q is not None:
            await self._q.join()

    def enqueue(self, kind: str, take_id: str, opts: Optional[Dict[str, Any]] = None) -> None:
        item = (kind, take_id, opts or {})
        if self._loop is None or self._q is None:
            raise RuntimeError("job runner not started")
        try:
            running = asyncio.get_running_loop()
        except RuntimeError:
            running = None
        if running is self._loop:
            self._q.put_nowait(item)
        else:  # called from the worker thread
            self._loop.call_soon_threadsafe(self._q.put_nowait, item)

    def _recover(self) -> None:
        """After a crash or restart, pick up work that was in flight."""
        for take_id in self.store.ids():
            doc = self.store.get(take_id) or {}
            status = doc.get("status")
            if status == "finishing":
                self.enqueue("finish", take_id, {})
            elif status in ("queued", "transcribing"):
                self.enqueue("transcribe", take_id, {})
            elif needs_repair(self.store.path(take_id)):
                self.enqueue("repair", take_id, {})     # e.g. restored from a backup, or the decoded copy was deleted

    async def _worker(self) -> None:
        while True:
            kind, take_id, opts = await self._q.get()
            self._busy = True
            try:
                await asyncio.to_thread(self._run, kind, take_id, opts)
            except asyncio.CancelledError:
                raise
            except Exception:  # _run already records the failure on the take
                _LOG.exception("job %s failed for %s", kind, take_id)
            finally:
                self._busy = False
                self._last = time.monotonic()
                self._q.task_done()

    async def _idle_unloader(self) -> None:
        while True:
            await asyncio.sleep(10)
            if (self.engines.loaded and not self._busy and self._q.empty()
                    and time.monotonic() - self._last > self.cfg.asr_idle_unload_s):
                _LOG.info("unloading idle ASR model")
                await asyncio.to_thread(self.engines.unload)

    # ------------------------------------------------------------------ job bodies (worker thread)
    def _run(self, kind: str, take_id: str, opts: Dict[str, Any]) -> None:
        try:
            if kind == "finish":
                self._finish(take_id, opts)
            elif kind == "transcribe":
                self._transcribe(take_id, opts)
            elif kind == "repair":
                self._repair(take_id)
            else:
                raise JobError(f"unknown job {kind!r}")
        except (JobError, EngineError) as e:
            self.store.update(take_id, status="error", error=str(e), error_stage=kind)
        except FfmpegError as e:
            self.store.update(take_id, status="error", error=f"audio decode failed: {e}", error_stage=kind)
        except Exception as e:
            self.store.update(take_id, status="error", error=f"{type(e).__name__}: {e}", error_stage=kind)
            raise

    def _finish(self, take_id: str, opts: Dict[str, Any]) -> None:
        take = self.store.get(take_id) or {}
        self.store.update(take_id, status="finishing", error=None, error_stage=None)
        try:
            info = self.store.assemble(take_id, ext=ext_for_mime(take.get("mime", "")), salvage=bool(opts.get("salvage")))
        except NoChunks:
            raise JobError("no audio was received")
        except ChunkGap as gap:
            raise JobError(f"{len(gap.missing)} audio chunk(s) never arrived (first missing: {gap.missing[0]}). "
                           "Re-send them and finish again, or finish with 'salvage' to keep everything before the gap.")
        raw = self.store.path(take_id, info["file"])
        wav = self.store.path(take_id, "audio.wav")
        decode_to_wav(raw, wav)
        frames, rate = wav_info(wav)
        if frames < rate * 0.3:
            raise JobError("the recording is too short to use")
        peaks = compute_peaks(wav)
        for spp, data in peaks.items():
            atomic_write_bytes(self.store.path(take_id, f"peaks_{spp}.bin"), data)
        self.store.write(take_id, "peaks.json", {"sample_rate": rate, "frames": frames, "levels": sorted(peaks)})
        self.store.update(take_id, duration=round(frames / rate, 3), sample_rate=rate,
                          chunks={"count": info["count"], "bytes": info["bytes"], "missing": info["missing"]},
                          status="queued" if self.cfg.auto_transcribe else "decoded")
        self.store.remove_parts(take_id)  # raw file is assembled and decoded; the loose parts are scratch
        if self.cfg.auto_transcribe:
            self.enqueue("transcribe", take_id, {})

    def _repair(self, take_id: str) -> None:
        """Rebuild the decoded copy and waveform from the raw audio. A failure is noted, not made fatal: the raw audio is untouched."""
        take_dir = self.store.path(take_id)
        raw = raw_file(take_dir)
        if raw is None or not needs_repair(take_dir):
            return
        try:
            write_derived(take_dir, raw)
            if (self.store.get(take_id) or {}).get("repair_error"):
                self.store.update(take_id, repair_error=None)
        except FfmpegError as err:
            _LOG.warning("could not rebuild the audio for %s: %s", take_id, err)
            self.store.update(take_id, repair_error=f"could not rebuild the decoded audio: {err}"[:400])

    def _transcribe(self, take_id: str, opts: Dict[str, Any]) -> None:
        take = self.store.get(take_id) or {}
        audio = self.store.path(take_id, "audio.wav")
        if not audio.exists():
            raise JobError("there is no decoded audio to transcribe yet")
        self.store.update(take_id, status="transcribing", progress=0.0, error=None, error_stage=None)

        last = [0.0]

        def progress(frac: float) -> None:
            now = time.monotonic()
            if now - last[0] >= 0.5:
                last[0] = now
                self.store.update(take_id, progress=round(frac, 3))

        engine = self.engines.get(opts.get("model"))
        result = engine.transcribe(audio, AsrOptions(
            language=opts.get("language") or "en",
            initial_prompt=opts.get("initial_prompt") or "",
            hotwords=opts.get("hotwords") or "",
            reference_text=take.get("reference_text") or "",
        ), progress=progress)

        tag = time.strftime("%Y%m%d-%H%M%S")
        with self.store.lock:
            self.store.archive(take_id, "asr.json", "asr_history", tag)
            self.store.prune(take_id, "asr_history", 10)
            self.store.write(take_id, "asr.json", result)
            edit = self.store.read(take_id, "edit.json")
            if edit is None or opts.get("regenerate"):
                segs, refine_stats = propose_segments(
                    result, audio, float(take.get("duration") or result.get("duration") or 0.0), SegOptions(
                        max_s=self.cfg.max_segment_s, min_s=self.cfg.min_segment_s,
                        pad_lead_s=self.cfg.pad_lead_s, pad_tail_s=self.cfg.pad_tail_s))
                result["refine"] = refine_stats
                self.store.write(take_id, "asr.json", result)
                if edit is not None:
                    self.store.archive(take_id, "edit.json", "edit_history", f"pre-regen-{tag}")
                self.store.write(take_id, "edit.json", new_edit_doc(segs, rev=(edit or {}).get("rev", 0) + 1))
        n_words = sum(len(s["words"]) for s in result["segments"])
        self.store.update(take_id, status="ready", progress=1.0, asr={
            "engine": result["engine"], "model": result["model"], "ran_at": result["ran_at"],
            "elapsed_s": result["elapsed_s"], "segments": len(result["segments"]), "words": n_words})
