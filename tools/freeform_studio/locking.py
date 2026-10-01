"""A lock file that only one process (or request) can hold at a time."""
from __future__ import annotations

import os
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Callable, Iterator


@contextmanager
def exclusive(path: Path, stale_s: float, busy: Callable[[Path], Exception]) -> Iterator[None]:
    """Hold `path` as a lock for the duration. If someone else holds it, raise `busy(path)`. A lock older than
    `stale_s` seconds is taken to be left behind by a crash and is replaced. The lock is always released."""
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        if path.exists() and time.time() - path.stat().st_mtime > stale_s:
            path.unlink()
        fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        raise busy(path) from None
    try:
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
        yield
    finally:
        path.unlink(missing_ok=True)
