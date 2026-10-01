# SPDX-License-Identifier: GPL-3.0-or-later
"""Keeping what you record on this computer, and noticing the ways it could end up somewhere else.

Three small jobs live here so every command in the package behaves the same way:

* `private_umask()`: files and folders this program creates are readable by you alone.
* `apply_offline_defaults()`: the speech-model libraries are told not to contact the internet (the only place that is
  allowed to is `python -m freeform_studio.models fetch`, which asks first).
* `loose_permissions()` / `sync_risk()`: the checks `doctor` and the server's start-up message use to point out a
  recordings or backups folder that other accounts can read, or that a cloud-sync program may be uploading.
"""
from __future__ import annotations

import os
import re
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, List, Optional, Union

PathLike = Union[str, Path]


@contextmanager
def private_umask() -> Iterator[None]:
    """New files get mode 0600 and new folders 0700 inside this block, then the old setting comes back.

    It only affects what is created from now on: existing files keep whatever permissions they have (the doctor says so,
    and prints the one command that tightens them; nothing here changes your data by itself)."""
    previous = os.umask(0o077)
    try:
        yield
    finally:
        os.umask(previous)


def apply_offline_defaults(allow_model_download: bool = False) -> None:
    """Tell Hugging Face's libraries not to use the network, and not to report usage. Must run before they are imported.

    `setdefault`, so a person who deliberately exported something else keeps what they chose."""
    os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
    os.environ.setdefault("DO_NOT_TRACK", "1")
    if not allow_model_download:
        os.environ.setdefault("HF_HUB_OFFLINE", "1")


def loose_permissions(root: PathLike, limit: int = 3, scan: int = 5000) -> List[str]:
    """Up to `limit` paths under `root` that other accounts on this computer could read (group or world access).

    Looks at no more than `scan` entries so it stays quick on a big library. Returns [] on systems without Unix modes."""
    base = Path(root)
    if os.name != "posix" or not base.exists():
        return []
    found: List[str] = []
    seen = 0
    for dirpath, dirnames, filenames in os.walk(base):
        for name in dirnames + filenames:
            seen += 1
            p = Path(dirpath) / name
            try:
                if p.is_symlink():
                    continue
                if p.stat().st_mode & 0o077:
                    found.append(str(p))
                    if len(found) >= limit:
                        return found
            except OSError:
                continue
            if seen >= scan:
                return found
    try:
        if base.stat().st_mode & 0o077 and not found:
            found.append(str(base))
    except OSError:
        pass
    return found


# Folders that cloud-sync programs commonly watch. The names are matched against each part of the path, case-insensitively,
# and a match is only ever a "may": the program can't see whether sync is actually switched on.
_SYNC_PARTS = [
    (re.compile(r"^onedrive( .*)?$"), "OneDrive"),
    (re.compile(r"^dropbox( .*)?$"), "Dropbox"),
    (re.compile(r"^(google[ _-]?drive|my drive)$"), "Google Drive"),
    (re.compile(r"^(icloud ?drive|iclouddrive|icloud)$"), "iCloud Drive"),
    (re.compile(r"^(box|box sync)$"), "Box"),
    (re.compile(r"^(pcloud|pcloud drive|megasync|nextcloud|owncloud|syncthing|resilio sync)$"), "a file-sync program"),
]
# On Windows, OneDrive can quietly take over these folders ("Known Folder Backup"), so a path through them may be uploaded
# even though its name says nothing about OneDrive.
_WINDOWS_KNOWN_FOLDERS = {"documents", "desktop", "pictures", "music", "videos"}


def sync_risk(path: PathLike) -> Optional[str]:
    """If `path` looks like it is inside a cloud-synced folder, a plain-words reason; otherwise None."""
    try:
        expanded = Path(path).expanduser()
        text = str(expanded.resolve() if expanded.exists() else expanded)
    except (OSError, RuntimeError):
        text = str(path)
    parts = [p for p in re.split(r"[\\/]+", text) if p]
    lowered = [p.lower() for p in parts]
    for part in lowered:
        for pattern, label in _SYNC_PARTS:
            if pattern.match(part):
                return f"it is inside a folder that looks like {label} ('{part}')"
    for i, part in enumerate(lowered):
        # C:\Users\<name>\Documents\...  (Windows)   or   /mnt/c/Users/<name>/Documents/...  (WSL)
        if part != "users" or i < 1:
            continue
        before = lowered[i - 1]
        on_a_windows_drive = bool(re.fullmatch(r"[a-z]:", before)) or (len(before) == 1 and i >= 2 and lowered[i - 2] == "mnt")
        if on_a_windows_drive and len(lowered) > i + 2 and lowered[i + 2] in _WINDOWS_KNOWN_FOLDERS:
            return f"it is in your Windows '{parts[i + 2]}' folder, which OneDrive often uploads automatically"
    return None


def sync_warning(path: PathLike, what: str) -> Optional[str]:
    """One sentence for the start-up message and the doctor, or None when nothing looks wrong."""
    reason = sync_risk(path)
    if not reason:
        return None
    return (f"{what} {path} may be uploaded to a cloud service: {reason}. Recordings of a voice are personal data, so "
            f"choose a folder that is not synced (or switch syncing off for it) if you want them to stay on this computer.")
