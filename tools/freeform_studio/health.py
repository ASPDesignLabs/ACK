"""How much room is left on the PC, and what to say about it."""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any, Dict, Union

MB = 1024 * 1024
HOUR_MB = 400  # roughly what an hour of recording takes once it is decoded for review (raw + 48 kHz copy + waveform)


def free_mb(path: Union[str, Path]) -> float:
    """Free space in MB where `path` lives. If it can't be measured, say there is plenty rather than block recording."""
    try:
        return shutil.disk_usage(path).free / MB
    except OSError:
        return float("inf")


def disk_status(path: Union[str, Path], min_free_mb: int, warn_free_mb: int) -> Dict[str, Any]:
    try:
        usage = shutil.disk_usage(path)
    except OSError:
        return {"known": False, "free_mb": None, "total_mb": None, "low": False, "critical": False,
                "min_free_mb": min_free_mb, "warn_free_mb": warn_free_mb, "hours_left": None}
    free = usage.free / MB
    return {"known": True, "free_mb": round(free), "total_mb": round(usage.total / MB), "low": free < warn_free_mb,
            "critical": free < min_free_mb, "min_free_mb": min_free_mb, "warn_free_mb": warn_free_mb,
            "hours_left": round(max(0.0, free - min_free_mb) / HOUR_MB, 1)}
