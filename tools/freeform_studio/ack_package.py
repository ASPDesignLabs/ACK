# SPDX-License-Identifier: GPL-3.0-or-later
"""Reads a training-capture package written by ACK (format: docs/ACK_TRAINING_CAPTURE_FORMAT.md).

This module only ever READS. It opens the zip, checks that it is exactly what the format allows, checks every audio file against
its checksum, and says in plain words what is wrong if anything is. It writes nothing anywhere, so a package that fails these
checks has changed nothing on this computer. Importing is a separate step (ack_import.py) that only runs on a package that passed.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import stat
import struct
import zipfile
import zlib
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, BinaryIO, Callable, Dict, Iterator, List, Optional, Tuple, Union

from .config import CODE_RE
from .edit import FLAG_RE

SCHEMA = "ack-training-capture/1"

# Limits from section 11 of the format document (a test keeps these equal to the document's).
MAX_ENTRIES = 20000
MAX_MANIFEST_BYTES = 8388608
MAX_SESSIONS = 200
MAX_CLIPS_PER_SESSION = 5000
MAX_FREE_SESSION_S = 5400
MAX_CARD_CHARS = 600
MAX_CLIP_S = 11.5
MIN_RATE, MAX_RATE = 16000, 96000
MAX_TOTAL_BYTES = 16 * 1024 ** 3        # what the entries may add up to (the reader's own choice; the format says 16 GiB by default)
DURATION_TOLERANCE_S = 0.05

SESSION_ID = r"s\d{8}-\d{6}-[0-9a-f]{4}"
_SESSION_ID_RE = re.compile(rf"^{SESSION_ID}$")
_AUDIO_PATH_RE = re.compile(rf"^sessions/({SESSION_ID})/(clips/(\d{{4,5}})\.wav|session\.wav)$")
_DIR_PATH_RE = re.compile(rf"^sessions/(?:{SESSION_ID}/(?:clips/)?)?$")
_TIME_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_SHA_RE = re.compile(r"^[0-9a-f]{64}$")
_SCRIPT_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,40}$")
_SOURCE_RE = re.compile(r"^[A-Z][A-Z_]{0,31}$")
_CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")
END_KINDS = ("pause", "forced", "end")

PathLike = Union[str, Path]


class PackageError(Exception):
    """The package can't be used. The message says what is wrong, in words a person can act on. Nothing was changed."""

    def __init__(self, message: str, problems: Optional[List[str]] = None):
        self.problems = problems or []
        shown = self.problems[:8]
        more = len(self.problems) - len(shown)
        text = message
        if shown:
            text += "\n" + "\n".join(f"  - {p}" for p in shown)
            if more > 0:
                text += f"\n  - ...and {more} more"
        super().__init__(text + "\nNothing was imported.")


@dataclass
class WavInfo:
    sample_rate: int
    frames: int
    data_offset: int

    @property
    def seconds(self) -> float:
        return self.frames / self.sample_rate


@dataclass
class Package:
    path: Path
    manifest: Dict[str, Any]
    wav: Dict[str, WavInfo] = field(default_factory=dict)          # zip entry name -> what its header says
    warnings: List[str] = field(default_factory=list)

    @property
    def sessions(self) -> List[Dict[str, Any]]:
        return self.manifest["sessions"]

    def session(self, session_id: str) -> Dict[str, Any]:
        for s in self.sessions:
            if s["id"] == session_id:
                return s
        raise KeyError(session_id)

    @contextmanager
    def open_file(self, name: str) -> Iterator[BinaryIO]:
        """`with package.open_file(name) as stream:` reads one audio file. Only names the manifest lists can be opened."""
        if name not in self.wav:
            raise KeyError(name)
        with zipfile.ZipFile(self.path) as archive, archive.open(name) as stream:
            yield stream

    def summary(self) -> Dict[str, Any]:
        sessions = []
        for s in self.sessions:
            if s["mode"] == "script":
                files = [c["file"] for c in s["clips"]]
                seconds = sum(c["duration_s"] for c in s["clips"])
                count = len(s["clips"])
            else:
                files = [s["recording"]["file"]]
                seconds = s["recording"]["duration_s"]
                count = len(s["recording"].get("proposed_segments") or [])
            size = sum(f["bytes"] for f in self.manifest["files"] if f["path"] in files)
            sessions.append({"id": s["id"], "mode": s["mode"], "label": s.get("label") or "", "started": s.get("started"),
                             "clips": len(s["clips"]) if s["mode"] == "script" else None, "proposed_segments": count if s["mode"] == "free" else None,
                             "seconds": round(seconds, 1), "bytes": size, "sample_rate": s["audio"]["sample_rate"]})
        return {"created": self.manifest["created"], "app_version": self.manifest["app"].get("version", ""),
                "sessions": sessions, "bytes": sum(f["bytes"] for f in self.manifest["files"]),
                "seconds": round(sum(x["seconds"] for x in sessions), 1)}


# ---------------------------------------------------------------------------------------------------- the manifest
def _num(x: Any) -> Optional[float]:
    if isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x):
        return None
    return float(x)


def _int(x: Any) -> Optional[int]:
    return x if isinstance(x, int) and not isinstance(x, bool) else None


def _time_ok(x: Any) -> bool:
    if not isinstance(x, str) or not _TIME_RE.match(x):
        return False
    try:
        datetime.strptime(x, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return False
    return True


def _metrics_problems(where: str, m: Any, out: List[str]) -> None:
    if not isinstance(m, dict):
        out.append(f"{where}: the loudness notes are missing")
        return
    for key in ("peak_dbfs", "rms_dbfs"):
        v = _num(m.get(key))
        if v is None or not -120.0 <= v <= 1.0:
            out.append(f"{where}: {key} should be a level between -120 and 0")
    clipped = _int(m.get("clipped_samples"))
    if clipped is None or clipped < 0:
        out.append(f"{where}: clipped_samples should be a count")


def _session_problems(s: Any, n: int, warnings: List[str]) -> Tuple[List[str], List[str]]:
    """(problems, audio files this session uses)"""
    out: List[str] = []
    used: List[str] = []
    if not isinstance(s, dict):
        return [f"session {n}: not an object"], used
    sid = s.get("id")
    where = f"session {sid if isinstance(sid, str) else n}"
    if not isinstance(sid, str) or not _SESSION_ID_RE.match(sid):
        return [f"session {n}: its id is not in the form s20261002-180411-a3f9"], used
    mode = s.get("mode")
    if mode not in ("script", "free"):
        out.append(f"{where}: mode must be \"script\" or \"free\"")
    label = s.get("label", "")
    if not isinstance(label, str) or len(label) > 120 or _CONTROL_RE.search(label):
        out.append(f"{where}: the label must be text up to 120 characters on one line")
    for key in ("started", "ended"):
        if not _time_ok(s.get(key)):
            out.append(f"{where}: {key} should be a UTC time like 2026-10-02T18:04:11Z")
    if not isinstance(s.get("language"), str) or not CODE_RE.match(s["language"]):
        out.append(f"{where}: language should look like en-US")
    audio = s.get("audio")
    rate = None
    if not isinstance(audio, dict):
        out.append(f"{where}: the audio settings are missing")
    else:
        rate = _int(audio.get("sample_rate"))
        if rate is None or not MIN_RATE <= rate <= MAX_RATE:
            out.append(f"{where}: sample_rate must be a whole number from {MIN_RATE} to {MAX_RATE}")
        for key in ("source", "source_requested"):
            if not isinstance(audio.get(key), str) or not _SOURCE_RE.match(audio[key]):
                out.append(f"{where}: audio {key} should be a short upper-case word such as UNPROCESSED")
    nf = s.get("noise_floor_dbfs")
    if nf is not None and (_num(nf) is None or not -120.0 <= nf <= 0.0):
        out.append(f"{where}: noise_floor_dbfs should be empty or a level between -120 and 0")
    th = _num(s.get("threshold_dbfs"))
    if th is None or not -120.0 <= th <= 0.0:
        out.append(f"{where}: threshold_dbfs should be a level between -120 and 0")
    device = s.get("device")
    if device is not None:
        if not isinstance(device, dict) or not isinstance(device.get("model", ""), str) or len(device.get("model", "")) > 60 \
                or (device.get("sdk") is not None and _int(device.get("sdk")) is None):
            out.append(f"{where}: device should be only a model name (up to 60 characters) and an Android version number")
        elif set(device) - {"model", "sdk"}:
            warnings.append(f"{where}: ignored extra device details ({', '.join(sorted(set(device) - {'model', 'sdk'}))}); only model and Android version are kept")

    if mode == "script":
        script = s.get("script")
        if not isinstance(script, dict) or not isinstance(script.get("id"), str) or not _SCRIPT_ID_RE.match(script["id"]) \
                or not isinstance(script.get("title", ""), str) or len(script.get("title", "")) > 120 \
                or (_int(script.get("cards_total")) or 0) < 1:
            out.append(f"{where}: the script details (id, title, cards_total) are missing or not valid")
        clips = s.get("clips")
        if not isinstance(clips, list) or not 1 <= len(clips) <= MAX_CLIPS_PER_SESSION:
            out.append(f"{where}: it should hold 1 to {MAX_CLIPS_PER_SESSION} clips")
            return out, used
        last = 0
        for c in clips:
            idx = _int(c.get("index")) if isinstance(c, dict) else None
            cw = f"{where}, clip {idx if idx is not None else '?'}"
            if not isinstance(c, dict) or idx is None or idx < 1:
                out.append(f"{where}: a clip has no valid index")
                continue
            if idx <= last:
                out.append(f"{cw}: clips must be in increasing order of index")
            last = max(last, idx)
            for key in ("card", "attempt"):
                v = _int(c.get(key))
                if v is None or v < 1:
                    out.append(f"{cw}: {key} should be a whole number from 1")
            expect = f"sessions/{sid}/clips/{idx:04d}.wav"
            if c.get("file") != expect:
                out.append(f"{cw}: its file should be named {expect}")
            else:
                used.append(expect)
            text = c.get("text")
            if not isinstance(text, str) or not text.strip() or len(text) > MAX_CARD_CHARS or _CONTROL_RE.search(text):
                out.append(f"{cw}: the text should be 1 to {MAX_CARD_CHARS} characters on one line")
            if not _time_ok(c.get("recorded")):
                out.append(f"{cw}: recorded should be a UTC time")
            dur = _num(c.get("duration_s"))
            if dur is None or dur <= 0:
                out.append(f"{cw}: duration_s should be a positive number")
            sp = c.get("speech")
            if sp is not None:
                a, b = (_num(sp.get("start_s")), _num(sp.get("end_s"))) if isinstance(sp, dict) else (None, None)
                if a is None or b is None or not 0 <= a < b or (dur is not None and b > dur + DURATION_TOLERANCE_S):
                    out.append(f"{cw}: the speech start and end are not valid")
            _metrics_problems(cw, c.get("metrics"), out)
            flags = c.get("flags", [])
            if not isinstance(flags, list):
                out.append(f"{cw}: flags should be a list")
            elif any(not isinstance(f, str) or not FLAG_RE.match(f) for f in flags):
                warnings.append(f"{cw}: ignored a flag that is not a short lower-case word")
    elif mode == "free":
        topic = s.get("topic", "")
        if not isinstance(topic, str) or len(topic) > 200 or _CONTROL_RE.search(topic):
            out.append(f"{where}: the topic must be text up to 200 characters on one line")
        rec = s.get("recording")
        if not isinstance(rec, dict):
            out.append(f"{where}: the recording details are missing")
            return out, used
        expect = f"sessions/{sid}/session.wav"
        if rec.get("file") != expect:
            out.append(f"{where}: its recording should be named {expect}")
        else:
            used.append(expect)
        dur = _num(rec.get("duration_s"))
        if dur is None or not 0 < dur <= MAX_FREE_SESSION_S:
            out.append(f"{where}: the recording length should be more than 0 and at most {MAX_FREE_SESSION_S} seconds")
        _metrics_problems(f"{where} recording", rec.get("metrics"), out)
        segs = rec.get("proposed_segments", [])
        if not isinstance(segs, list):
            out.append(f"{where}: proposed_segments should be a list")
        else:
            prev_end = 0.0
            for i, p in enumerate(segs, start=1):
                pw = f"{where}, suggested piece {i}"
                a, b = (_num(p.get("start_s")), _num(p.get("end_s"))) if isinstance(p, dict) else (None, None)
                if a is None or b is None or not 0 <= a < b:
                    out.append(f"{pw}: its start and end are not valid")
                    continue
                if dur is not None and b > dur + DURATION_TOLERANCE_S:
                    out.append(f"{pw}: it runs past the end of the recording")
                if b - a > MAX_CLIP_S + 0.001:
                    out.append(f"{pw}: it is longer than {MAX_CLIP_S} seconds")
                if a < prev_end - 1e-6:
                    out.append(f"{pw}: it overlaps the one before")
                prev_end = max(prev_end, b)
                if p.get("end_kind") not in END_KINDS:
                    out.append(f"{pw}: end_kind should be one of {', '.join(END_KINDS)}")
                if p.get("metrics") is not None:
                    _metrics_problems(pw, p["metrics"], out)
    return out, used


def validate_manifest(m: Any) -> Tuple[List[str], List[str]]:
    """(problems, warnings). An empty problems list means the manifest is acceptable. Checks the structure only; the zip and the
    audio files are checked by open_package()."""
    problems: List[str] = []
    warnings: List[str] = []
    if not isinstance(m, dict):
        return ["manifest.json is not a JSON object"], warnings
    schema = m.get("schema")
    if schema != SCHEMA:
        if isinstance(schema, str) and schema.startswith("ack-training-capture/"):
            return [f"this package is format \"{schema}\"; this version of Freeform Studio reads \"{SCHEMA}\". Update Freeform Studio "
                    "(or re-export from a matching version of ACK)."], warnings
        return ["manifest.json does not say it is an ACK training capture (schema is missing or different)"], warnings
    if not _time_ok(m.get("created")):
        problems.append("created should be a UTC time like 2026-10-02T18:30:00Z")
    app = m.get("app")
    if not isinstance(app, dict) or not isinstance(app.get("version", ""), str) or len(app.get("version", "")) > 40:
        problems.append("app.version should be text up to 40 characters")
    sessions = m.get("sessions")
    files = m.get("files")
    if not isinstance(sessions, list) or not 1 <= len(sessions) <= MAX_SESSIONS:
        problems.append(f"it should hold 1 to {MAX_SESSIONS} sessions")
        sessions = []
    if not isinstance(files, list):
        problems.append("the list of files is missing")
        files = []

    listed: Dict[str, Dict[str, Any]] = {}
    for f in files:
        if not isinstance(f, dict) or not isinstance(f.get("path"), str) or not _AUDIO_PATH_RE.match(f["path"]):
            problems.append(f"a listed file has a name the format does not allow: {str(f.get('path') if isinstance(f, dict) else f)[:80]!r}")
            continue
        if f["path"] in listed:
            problems.append(f"{f['path']} is listed twice")
            continue
        size = _int(f.get("bytes"))
        if size is None or size < 44:
            problems.append(f"{f['path']}: bytes should be a whole number of at least 44")
        if not isinstance(f.get("sha256"), str) or not _SHA_RE.match(f["sha256"]):
            problems.append(f"{f['path']}: sha256 should be 64 lower-case hex characters")
        listed[f["path"]] = f

    ids = set()
    used: List[str] = []
    for n, s in enumerate(sessions, start=1):
        sp, su = _session_problems(s, n, warnings)
        problems.extend(sp)
        used.extend(su)
        sid = s.get("id") if isinstance(s, dict) else None
        if sid is not None and sid in ids:
            problems.append(f"session {sid} appears twice")
        ids.add(sid)
    if len(used) != len(set(used)):
        problems.append("two clips share one audio file")
    for path in used:
        if path not in listed:
            problems.append(f"{path} is used by a session but not listed in files")
    for path in listed:
        if path not in used:
            problems.append(f"{path} is listed in files but no session uses it")
    return problems, warnings


# ---------------------------------------------------------------------------------------------------- audio files
def parse_wav_header(head: bytes, total: int, name: str) -> WavInfo:
    """Check a WAV file's header against the format (PCM, 16-bit, mono) and against how long the file really is."""
    if len(head) < 44 or head[:4] != b"RIFF" or head[8:12] != b"WAVE":
        raise PackageError(f"{name} is not a WAV file.")
    riff_size = struct.unpack("<I", head[4:8])[0]
    pos, fmt, data = 12, None, None
    while pos + 8 <= len(head):
        cid, size = struct.unpack("<4sI", head[pos:pos + 8])
        if cid == b"fmt ":
            if size < 16 or pos + 8 + 16 > len(head):
                raise PackageError(f"{name}: its audio format block is damaged.")
            fmt = struct.unpack("<HHIIHH", head[pos + 8:pos + 24])
        elif cid == b"data":
            data = (pos + 8, size)
            break
        pos += 8 + size + (size & 1)
    if fmt is None or data is None:
        raise PackageError(f"{name}: it has no readable audio data (the recording may have been interrupted).")
    tag, channels, rate, _byte_rate, _align, bits = fmt
    if tag != 1 or channels != 1 or bits != 16:
        raise PackageError(f"{name}: it should be plain 16-bit mono audio, but this is format {tag}, {channels} channel(s), {bits}-bit.")
    if not MIN_RATE <= rate <= MAX_RATE:
        raise PackageError(f"{name}: its sample rate ({rate} Hz) is outside {MIN_RATE} to {MAX_RATE}.")
    offset, size = data
    data_end_ok = offset + size == total or offset + size + (size & 1) == total
    riff_ok = riff_size + 8 == total or riff_size + 9 == total
    if not (data_end_ok and riff_ok):
        raise PackageError(f"{name}: its header says the audio is {size} bytes, but the file holds {total - offset}. "
                           "A recording that was interrupted looks like this; export it again from ACK after it has been closed properly.")
    if size % 2:
        raise PackageError(f"{name}: the audio length is not a whole number of samples.")
    return WavInfo(sample_rate=rate, frames=size // 2, data_offset=offset)


def _verify_file(archive: zipfile.ZipFile, name: str, entry: Dict[str, Any],
                 progress: Optional[Callable[[int], None]]) -> WavInfo:
    declared = int(entry["bytes"])
    sha = hashlib.sha256()
    head = b""
    seen = 0
    try:
        with archive.open(name) as stream:
            while True:
                block = stream.read(min(1 << 20, declared + 1 - seen))
                if not block:
                    break
                if not head:
                    head = block[:4096]
                sha.update(block)
                seen += len(block)
                if progress:
                    progress(len(block))
                if seen > declared:
                    raise PackageError(f"{name} is bigger than the manifest says ({declared} bytes). The file may have been altered.")
    except zipfile.BadZipFile as err:
        raise PackageError(f"{name} is damaged inside the zip file ({err}). Copy the package again, or export it again from ACK.")
    except (OSError, EOFError, zlib.error) as err:
        raise PackageError(f"{name} could not be read from the zip file ({err}).")
    if seen != declared:
        raise PackageError(f"{name} is {seen} bytes but the manifest says {declared}. The copy may have been cut short; copy the package again.")
    if sha.hexdigest() != entry["sha256"]:
        raise PackageError(f"{name} does not match its checksum, so it was changed or damaged after ACK wrote it. "
                           "Copy the package again (check the USB drive or the copy), or export it again from ACK.")
    return parse_wav_header(head, declared, name)


# ---------------------------------------------------------------------------------------------------- opening a package
def _check_entries(archive: zipfile.ZipFile) -> Dict[str, zipfile.ZipInfo]:
    infos = archive.infolist()
    if len(infos) > MAX_ENTRIES:
        raise PackageError(f"The package holds {len(infos)} files; the most a package may hold is {MAX_ENTRIES}.")
    seen: Dict[str, zipfile.ZipInfo] = {}
    problems: List[str] = []
    total = 0
    for info in infos:
        name = info.filename
        if name in seen:
            problems.append(f"{name!r} appears more than once")
            continue
        seen[name] = info
        if "\\" in name:
            problems.append(f"{name!r} has a backslash in its path; zip files use forward slashes, so it was made by a tool that does not follow the format")
            continue
        if name.startswith("/") or ".." in name.split("/") or "\x00" in name:
            problems.append(f"{name!r} has a path that could write outside the import folder")
            continue
        if name.endswith("/"):
            if not _DIR_PATH_RE.match(name):
                problems.append(f"{name!r} is a folder the format does not use")
            continue
        if name not in ("manifest.json", "README.txt") and not _AUDIO_PATH_RE.match(name):
            problems.append(f"{name!r} is not a file the format allows")
            continue
        if info.flag_bits & 0x1:
            problems.append(f"{name!r} is password-protected")
        if stat.S_IFMT(info.external_attr >> 16) == stat.S_IFLNK:
            problems.append(f"{name!r} is a link, not a file")
        if info.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
            problems.append(f"{name!r} uses a compression method this tool does not read")
        total += info.file_size
    if total > MAX_TOTAL_BYTES:
        problems.append(f"the files add up to {total / 1024 ** 3:.1f} GiB, more than the {MAX_TOTAL_BYTES // 1024 ** 3} GiB limit")
    if problems:
        raise PackageError("This is not a package Freeform Studio can read:", problems)
    return seen


def open_package(path: PathLike, progress: Optional[Callable[[int, int], None]] = None) -> Package:
    """Open, check and verify a package. Raises PackageError (with nothing changed) unless everything is in order.

    `progress(done_bytes, total_bytes)` is called while the audio files are checked, which is the slow part of a big package."""
    path = Path(path).expanduser()
    if not path.is_file():
        raise PackageError(f"There is no file at {path}.")
    try:
        archive = zipfile.ZipFile(path)
    except (zipfile.BadZipFile, OSError) as err:
        raise PackageError(f"{path.name} is not a zip file Freeform Studio can open ({err}). "
                           "If it was copied from a phone, copy it again and make sure the copy finished.")
    with archive:
        entries = _check_entries(archive)
        if "manifest.json" not in entries:
            raise PackageError(f"{path.name} has no manifest.json, so it is not an ACK training capture.")
        with archive.open("manifest.json") as f:
            raw = f.read(MAX_MANIFEST_BYTES + 1)
        if len(raw) > MAX_MANIFEST_BYTES:
            raise PackageError(f"manifest.json is larger than the {MAX_MANIFEST_BYTES // 1024 // 1024} MiB limit.")
        try:
            manifest = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as err:
            raise PackageError(f"manifest.json could not be read ({err}).")
        problems, warnings = validate_manifest(manifest)
        if problems:
            raise PackageError("The package's manifest has problems:", problems)

        listed = {f["path"]: f for f in manifest["files"]}
        in_zip = {n for n in entries if _AUDIO_PATH_RE.match(n)}
        missing = sorted(set(listed) - in_zip)
        extra = sorted(in_zip - set(listed))
        if missing or extra:
            raise PackageError("The files in the zip and the files the manifest lists do not match:",
                               [f"{n} is listed but missing from the zip" for n in missing] +
                               [f"{n} is in the zip but not listed" for n in extra])

        sizes = [f"{n}: the zip says {entries[n].file_size} bytes, the manifest says {listed[n]['bytes']}"
                 for n in sorted(listed) if entries[n].file_size != listed[n]["bytes"]]
        if sizes:
            raise PackageError("The zip and the manifest disagree about file sizes, so the copy may be damaged:", sizes)

        total = sum(f["bytes"] for f in manifest["files"])
        done = [0]

        def tick(n: int) -> None:
            done[0] += n
            if progress:
                progress(done[0], total)

        wav: Dict[str, WavInfo] = {}
        for name in sorted(listed):
            wav[name] = _verify_file(archive, name, listed[name], tick)

    # the audio has to agree with what the manifest says about it
    problems = []
    for s in manifest["sessions"]:
        rate = s["audio"]["sample_rate"]
        items = [(c["file"], c["duration_s"]) for c in s["clips"]] if s["mode"] == "script" else [(s["recording"]["file"], s["recording"]["duration_s"])]
        for name, declared in items:
            info = wav[name]
            if info.sample_rate != rate:
                problems.append(f"{name} is {info.sample_rate} Hz but its session says {rate} Hz")
            if abs(info.seconds - declared) > DURATION_TOLERANCE_S:
                problems.append(f"{name} is {info.seconds:.2f} s long but the manifest says {declared:.2f} s")
    if problems:
        raise PackageError("The audio and the notes about it disagree:", problems)
    return Package(path=path, manifest=manifest, wav=wav, warnings=warnings)
