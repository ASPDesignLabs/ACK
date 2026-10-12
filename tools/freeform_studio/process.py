# SPDX-License-Identifier: GPL-3.0-or-later
"""Finish the recordings that are waiting, with no browser and no server: decode them, listen for speech, transcribe, and propose the pieces.

    python -m freeform_studio.process --output ~/ack-voice-studio/projects/anna/recordings
    python -m freeform_studio.process --output DIR --json        # one JSON object per line, for a program to read

This is the work the server does by itself after a recording arrives (jobs.py), run once and then stopped. It is what lets a recording imported from ACK
(ack_import.py) reach the same state as one made in the browser, ready for Review and for building a dataset, without anyone having to start the server.

Safe to stop and run again: a recording that was part-way is picked up where it was. It changes nothing but the recordings that were waiting, uses no
network (the speech model must already be on this computer; see models.py), and the audio files you recorded are never altered.

Exit codes: 0 everything that was waiting is finished, 1 some recordings could not be finished (each says why), 2 the command was wrong, 3 the speech model
is not on this computer (nothing was started).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .asr import make_engine
from .config import Config
from .jobs import EngineManager, JobRunner
from .models import is_available, size_phrase
from .privacy import apply_offline_defaults, private_umask
from .storage import TakeStore

WAITING = ("finishing", "queued", "transcribing")      # statuses that mean "not finished yet"; one still "importing" is not waiting, its import is not complete
Reporter = Callable[[Dict[str, Any]], None]


def waiting_takes(store: TakeStore) -> List[str]:
    """Recordings that still need work: their status is one of WAITING. One that is still being imported is left alone, and so is one that failed or is ready."""
    found = []
    for take_id in store.ids():
        doc = store.get(take_id) or {}
        if doc.get("status") in WAITING:
            found.append(take_id)
    return found


def snapshot(store: TakeStore, ids: List[str]) -> Dict[str, Dict[str, Any]]:
    out = {}
    for take_id in ids:
        doc = store.get(take_id) or {}
        out[take_id] = {"take": take_id, "status": doc.get("status", "unknown"), "progress": doc.get("progress"), "error": doc.get("error"),
                        "label": doc.get("label", ""), "duration": doc.get("duration")}
    return out


async def process(cfg: Config, store: TakeStore, engines: EngineManager, report: Reporter, poll_s: float = 0.5) -> Dict[str, Dict[str, Any]]:
    """Run everything that is waiting to the end. Calls `report` whenever a recording's status or progress changes."""
    ids = waiting_takes(store)
    if not ids:
        return {}
    runner = JobRunner(cfg, store, engines)
    await runner.start()
    last: Dict[str, Any] = {}

    async def watch() -> None:
        while True:
            for take_id, state in snapshot(store, ids).items():
                key = (state["status"], state["progress"])
                if last.get(take_id) != key:
                    last[take_id] = key
                    report(state)
            await asyncio.sleep(poll_s)

    watcher = asyncio.create_task(watch())
    try:
        await runner.wait_idle()
    finally:
        watcher.cancel()
        try:
            await watcher
        except asyncio.CancelledError:
            pass
        await runner.stop()
        engines.unload()
    final = snapshot(store, ids)
    for take_id, state in final.items():
        if last.get(take_id) != (state["status"], state["progress"]):
            report(state)
    return final


def main(argv: Optional[List[str]] = None) -> int:
    with private_umask():
        return _main(argv)


def _main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="freeform_studio.process", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--output", required=True, help="the recordings folder (the same --output the server uses)")
    ap.add_argument("--code", default="en-US")
    ap.add_argument("--asr-engine", choices=["faster-whisper", "fake"], default="faster-whisper")
    ap.add_argument("--asr-model", default="small.en", help="a model name already on this computer, or the path of a model folder")
    ap.add_argument("--asr-device", choices=["cpu", "cuda", "auto"], default="cpu", help="cpu while training runs; cuda when the GPU is free")
    ap.add_argument("--asr-compute-type", default="auto")
    ap.add_argument("--json", action="store_true", help="print one JSON object per line instead of sentences")
    args = ap.parse_args(argv)

    apply_offline_defaults(False)                                       # before anything imports the Hugging Face libraries
    cfg = Config(output_dir=Path(args.output), code=args.code, asr_engine=args.asr_engine, asr_model=args.asr_model, asr_device=args.asr_device,
                 asr_compute_type=args.asr_compute_type, asr_allow_download=False, asr_idle_unload_s=0)

    def emit(obj: Dict[str, Any]) -> None:
        print(json.dumps(obj, ensure_ascii=False) if args.json else _sentence(obj), flush=True)

    store = TakeStore(cfg.takes_dir)
    if not waiting_takes(store):
        emit({"done": True, "ready": 0, "error": 0, "nothing_waiting": True})
        return 0
    if cfg.asr_engine != "fake" and not is_available(cfg.asr_model):
        emit({"done": True, "ready": 0, "error": 0, "model_missing": cfg.asr_model, "size": size_phrase(cfg.asr_model)})
        return 3
    final = asyncio.run(process(cfg, store, EngineManager(cfg, make_engine), emit))
    ready = sum(1 for s in final.values() if s["status"] == "ready")
    failed = [s for s in final.values() if s["status"] != "ready"]
    emit({"done": True, "ready": ready, "error": len(failed), "failed": [{"take": s["take"], "status": s["status"], "error": s["error"]} for s in failed]})
    return 0 if not failed else 1


def _sentence(obj: Dict[str, Any]) -> str:
    if obj.get("done"):
        if obj.get("nothing_waiting"):
            return "Nothing is waiting: every recording is already finished."
        if obj.get("model_missing"):
            name = obj["model_missing"]
            if name.startswith(("/", "~", ".")):
                return f"The speech model folder '{name}' does not exist, so nothing was started. Check the path."
            return (f"The speech model '{name}' ({obj['size']}) is not on this computer, so nothing was started. Fetch it once with: "
                    f"python -m freeform_studio.models fetch {name}")
        if obj["error"]:
            return f"Finished {obj['ready']} recording(s); {obj['error']} could not be finished."
        return f"Finished {obj['ready']} recording(s)."
    pct = f" {int(100 * obj['progress'])}%" if isinstance(obj.get("progress"), (int, float)) else ""
    return f"  {obj['take']}: {obj['status']}{pct}" + (f" ({obj['error']})" if obj.get("error") else "")


if __name__ == "__main__":
    sys.exit(main())
