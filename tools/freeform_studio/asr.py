"""Speech-to-text engines. Every engine returns the same plain-dict shape so the rest of the app is engine-agnostic.

Result shape:
    {"engine", "model", "language", "duration", "params", "ran_at", "elapsed_s",
     "segments": [{"id", "start", "end", "text", "avg_logprob", "no_speech_prob",
                   "compression_ratio", "words": [{"w", "s", "e", "p"}]}]}
"""
from __future__ import annotations

import gc
import re
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .audio import rms_envelope, voiced_regions, wav_info
from .storage import now_iso

Progress = Optional[Callable[[float], None]]


class EngineError(Exception):
    """A speech-model failure whose message is written for a person, not a stack trace."""


def explain_load_error(model: str, device: str, err: Exception) -> str:
    first = (str(err).strip().splitlines() or [""])[0][:200]
    low = str(err).lower()
    if device != "cpu" and any(k in low for k in ("libcudnn", "libcublas", "cudnn", "cublas", "cuda")):
        hint = ("The GPU libraries look missing or mismatched. Try --device cpu, or follow "
                "'GPU (optional)' in the README.")
    elif any(k in low for k in ("proxy", "connection", "resolve", "network", "offline", "forbidden", "403",
                                "timed out", "timeout", "ssl", "huggingface", "hf.co", "no space")):
        hint = ("The first run downloads the model from Hugging Face (about 500 MB for small.en), so it needs "
                "internet access and free disk space. Check your connection and try again; a partial download resumes.")
    else:
        hint = ""
    return f"Could not load the speech model '{model}' on {device}. {hint} [{type(err).__name__}: {first}]".replace("  ", " ")

_TERMINAL = re.compile(r"[.!?][\"'”’)]*$")
FAKE_WORDS = ["so", "there", "was", "this", "idea", "about", "how", "language", "really", "works",
              "when", "you", "stop", "thinking", "about", "it", "and", "just", "let", "it", "flow"]


@dataclass
class AsrOptions:
    language: str = "en"
    initial_prompt: str = ""
    hotwords: str = ""
    reference_text: str = ""  # used by the fake engine only
    vad_min_silence_ms: int = 500
    hallucination_silence_s: float = 2.0

    def as_params(self) -> Dict[str, Any]:
        return {"language": self.language, "initial_prompt": self.initial_prompt, "hotwords": self.hotwords,
                "vad_min_silence_ms": self.vad_min_silence_ms,
                "hallucination_silence_s": self.hallucination_silence_s}


class AsrEngine:
    name = "base"
    model = ""

    @property
    def loaded(self) -> bool:
        return False

    def transcribe(self, audio_path: Path, opts: AsrOptions, progress: Progress = None) -> Dict[str, Any]:
        raise NotImplementedError

    def unload(self) -> None:
        pass


# --------------------------------------------------------------------------- fake
class FakeEngine(AsrEngine):
    """Deterministic stand-in: finds speech bursts by energy and spreads words across them.

    Uses the take's reference text when there is one, so the whole pipeline (segmenting, review,
    export) can be exercised without a model or a GPU.
    """
    name = "fake"

    def __init__(self, model: str = "fake") -> None:
        self.model = model
        self._loaded = False

    @property
    def loaded(self) -> bool:
        return self._loaded

    def unload(self) -> None:
        self._loaded = False

    def transcribe(self, audio_path: Path, opts: AsrOptions, progress: Progress = None) -> Dict[str, Any]:
        self._loaded = True            # like the real model: it is read into memory the first time it is used
        t0 = time.monotonic()
        frames, rate = wav_info(audio_path)
        duration = frames / rate
        db, hop = rms_envelope(audio_path)
        regions = voiced_regions(db, hop, thresh_db=-45.0, min_silence_s=0.3, min_len_s=0.2)
        tokens = opts.reference_text.split() or list(FAKE_WORDS)

        total_len = sum(b - a for a, b in regions) or 1.0
        counts = [max(1, int(round(len(tokens) * (b - a) / total_len))) for a, b in regions]
        segments: List[Dict[str, Any]] = []
        cursor = 0
        gi = 0
        for si, ((a, b), n) in enumerate(zip(regions, counts)):
            picked = [tokens[(cursor + k) % len(tokens)] for k in range(n)]
            cursor += n
            weights = [len(t) + 1 for t in picked]
            span = (b - a)
            words = []
            t = a
            for tok, wt in zip(picked, weights):
                d = span * wt / sum(weights)
                words.append({"w": tok, "s": round(t, 3), "e": round(t + d * 0.92, 3),
                              "p": 0.42 if gi % 7 == 3 else 0.93})
                t += d
                gi += 1
            if not _TERMINAL.search(words[-1]["w"]):
                words[-1]["w"] += "."
            segments.append({"id": si, "start": round(a, 3), "end": round(b, 3),
                             "text": " ".join(w["w"] for w in words),
                             "avg_logprob": -0.2, "no_speech_prob": 0.01, "compression_ratio": 1.2,
                             "words": words})
            if progress:
                progress((si + 1) / max(1, len(regions)))
        return {"engine": self.name, "model": self.model, "language": opts.language, "duration": duration,
                "params": opts.as_params(), "ran_at": now_iso(), "elapsed_s": round(time.monotonic() - t0, 3),
                "segments": segments}


# --------------------------------------------------------------------------- faster-whisper
class FasterWhisperEngine(AsrEngine):
    name = "faster-whisper"

    def __init__(self, model: str, device: str = "cpu", compute_type: str = "int8",
                 model_factory: Optional[Callable[..., Any]] = None) -> None:
        self.model = model
        self.device = device
        self.compute_type = compute_type
        self._factory = model_factory
        self._model: Any = None
        self._lock = threading.Lock()

    @property
    def loaded(self) -> bool:
        return self._model is not None

    def _load(self) -> Any:
        with self._lock:
            if self._model is None:
                factory = self._factory
                if factory is None:
                    try:
                        from faster_whisper import WhisperModel  # heavy import, only when first needed
                    except ImportError as e:
                        raise RuntimeError("faster-whisper is not installed in this environment "
                                           "(pip install faster-whisper)") from e
                    factory = WhisperModel
                try:
                    self._model = factory(self.model, device=self.device, compute_type=self.compute_type)
                except Exception as e:
                    raise EngineError(explain_load_error(self.model, self.device, e)) from e
            return self._model

    def unload(self) -> None:
        with self._lock:
            self._model = None
        gc.collect()

    def transcribe(self, audio_path: Path, opts: AsrOptions, progress: Progress = None) -> Dict[str, Any]:
        t0 = time.monotonic()
        model = self._load()
        seg_iter, info = model.transcribe(
            str(audio_path),
            language=opts.language or None,
            beam_size=5,
            word_timestamps=True,
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": opts.vad_min_silence_ms},
            initial_prompt=opts.initial_prompt or None,
            hotwords=opts.hotwords or None,
            condition_on_previous_text=False,  # stops one bad phrase from poisoning the rest
            hallucination_silence_threshold=opts.hallucination_silence_s,
        )
        duration = float(getattr(info, "duration", 0.0) or 0.0)
        segments: List[Dict[str, Any]] = []
        for i, seg in enumerate(seg_iter):
            words = []
            for w in (getattr(seg, "words", None) or []):
                raw = w.word or ""
                text = raw.strip()
                if not text:
                    continue
                entry = {"w": text, "s": round(float(w.start), 3), "e": round(float(w.end), 3),
                         "p": round(float(w.probability), 3)}
                if words and not raw.startswith(" "):
                    entry["j"] = True  # continuation piece (e.g. ",000" after "11"): no space before it
                words.append(entry)
            segments.append({"id": i, "start": round(float(seg.start), 3), "end": round(float(seg.end), 3),
                             "text": (seg.text or "").strip(),
                             "avg_logprob": _f(getattr(seg, "avg_logprob", None)),
                             "no_speech_prob": _f(getattr(seg, "no_speech_prob", None)),
                             "compression_ratio": _f(getattr(seg, "compression_ratio", None)),
                             "words": words})
            if progress and duration > 0:
                progress(min(1.0, float(seg.end) / duration))
        return {"engine": self.name, "model": self.model, "language": getattr(info, "language", opts.language),
                "duration": duration, "params": {**opts.as_params(), "device": self.device,
                                                 "compute_type": self.compute_type},
                "ran_at": now_iso(), "elapsed_s": round(time.monotonic() - t0, 3), "segments": segments}


def _f(x: Any) -> Optional[float]:
    return None if x is None else round(float(x), 4)


def make_engine(cfg: Any, model: Optional[str] = None) -> AsrEngine:
    model = model or cfg.asr_model
    if cfg.asr_engine == "fake":
        return FakeEngine(model)
    if cfg.asr_engine == "faster-whisper":
        return FasterWhisperEngine(model, device=cfg.asr_device, compute_type=cfg.compute_type)
    raise ValueError(f"unknown ASR engine: {cfg.asr_engine!r}")
