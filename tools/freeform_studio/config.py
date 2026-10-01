# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

CODE_RE = re.compile(r"^[A-Za-z]{2,3}([-_][A-Za-z0-9]{2,8})?$")


@dataclass
class Config:
    output_dir: Path
    code: str = "en-US"
    token: Optional[str] = None
    asr_engine: str = "faster-whisper"  # "faster-whisper" | "fake"
    asr_model: str = "small.en"
    asr_device: str = "cpu"  # "cpu" | "cuda" | "auto"
    asr_compute_type: str = "auto"  # auto: int8 on cpu, float16 on cuda
    asr_allow_download: bool = False  # False: only ever load a speech model that is already on this computer (see models.py)
    asr_idle_unload_s: int = 300
    auto_transcribe: bool = True
    max_segment_s: float = 11.5
    min_segment_s: float = 1.0
    pad_lead_s: float = 0.12
    pad_tail_s: float = 0.20
    backup_dir: Optional[Path] = None   # where backups go; None means the page and server don't offer them
    backup_every_hours: float = 6.0     # automatic backups, only when something has changed; 0 turns them off
    backup_keep: int = 30
    backup_first_delay_s: float = 120.0
    min_free_mb: int = 500        # below this, new audio is refused (it stays safe on the phone) instead of risking a half-written file
    warn_free_mb: int = 3000      # below this, the pages warn
    max_chunk_bytes: int = 16 * 1024 * 1024
    max_chunks: int = 100_000

    def __post_init__(self) -> None:
        if not CODE_RE.match(self.code):
            raise ValueError(f"invalid language code: {self.code!r}")
        self.output_dir = Path(self.output_dir).expanduser()
        if self.backup_dir is not None:
            self.backup_dir = Path(self.backup_dir).expanduser()

    @property
    def root(self) -> Path:
        # Deliberately OUTSIDE output/<code>/ so split_long_takes.py can never
        # pick up half-reviewed audio.
        return self.output_dir / "_freeform" / self.code

    @property
    def takes_dir(self) -> Path:
        return self.root / "takes"

    @property
    def compute_type(self) -> str:
        if self.asr_compute_type != "auto":
            return self.asr_compute_type
        return "float16" if self.asr_device == "cuda" else "int8"
