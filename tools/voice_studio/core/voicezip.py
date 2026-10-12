# SPDX-License-Identifier: GPL-3.0-or-later
"""The finished voice as ACK wants it: one `.zip` holding `model.onnx` and `model.onnx.json` (plan tasks VS-2.8 and VS-5.3).

ACK's IMPORT VOICE BACKUP (output/CustomVoiceBackupManager.kt, CustomVoiceRepository.kt) takes exactly this file. The rules it applies are written down here as
checks that run on the PC *before* the file is made, so a voice that the phone would refuse, or that would crash it on the first word, is explained here and never
reaches the phone: the sizes ACK allows, a config that looks like a Piper config, and the model metadata that sherpa-onnx requires and that Piper's own export does
not write (see tools/patch_voice_for_sherpa_onnx.py and CLAUDE.md, "CUSTOM TRAINED VOICE"). `tests/test_vs_voicezip_contract.py` reads ACK's source so a change on the
phone side fails here.

The writer is careful the way the rest of the tool is: it checks everything before writing a byte, writes to a `.part` file, reads the zip back and compares every byte of both
entries with the files they came from, only then moves it into place, refuses to replace a file that is already there, and leaves the files it was given untouched. The same
inputs always give the same bytes. Nothing here uses the network.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
import stat
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Dict, List, Optional, Tuple

MODEL_ENTRY = "model.onnx"
CONFIG_ENTRY = "model.onnx.json"
MAX_ZIP_BYTES = 400 * 1024 * 1024         # CustomVoiceBackupManager.MAX_ZIP_FILE_SIZE
MAX_MODEL_BYTES = 300 * 1024 * 1024       # CustomVoiceRepository.MAX_MODEL_SIZE_BYTES
MAX_CONFIG_BYTES = 1 * 1024 * 1024        # CustomVoiceRepository.MAX_CONFIG_SIZE_BYTES
CONFIG_KEYS = ("phoneme_id_map", "audio")  # CustomVoiceRepository.looksLikePiperConfig
REQUIRED_METADATA = ("sample_rate", "n_speakers", "language", "comment")      # what sherpa-onnx's VITS loader reads with no fallback
ROOM_MARGIN_BYTES = 256 * 1024 * 1024
FIXED_TIME = (2020, 1, 1, 0, 0, 0)        # so the same input is the same file
MAX_META_ENTRY = 64 * 1024                # one metadata entry larger than this is not a real one
CHUNK = 1 << 20

# why a voice cannot be sent to the phone yet, each with words in the text catalog
PROBLEM_CODES = ("model_missing", "model_empty", "model_too_big", "not_onnx", "not_patched", "wrong_comment", "config_missing", "config_empty",
                 "config_too_big", "config_not_json", "config_not_piper", "rate_mismatch", "speakers_mismatch",
                 "zip_missing", "zip_unreadable", "zip_wrong_entries", "zip_too_big")         # the last four come from checking a finished zip
ERROR_CODES = ("not_ready", "exists", "no_room", "write_failed", "verify_failed")             # each has words in the text catalog


class VoiceZipError(Exception):
    """`code` is one of ERROR_CODES. `problems` are PROBLEM_CODES when the code is not_ready."""

    def __init__(self, code: str, detail: str = "", problems: Tuple[str, ...] = ()):
        super().__init__(code + (": " + detail if detail else ""))
        self.code = code
        self.detail = detail
        self.problems = tuple(problems)


# ---------------------------------------------------------------- reading an ONNX file's metadata without the onnx library

class _Malformed(Exception):
    pass


def _varint(handle: BinaryIO) -> int:
    value, shift = 0, 0
    for _ in range(10):
        byte = handle.read(1)
        if not byte:
            raise _Malformed("ended inside a number")
        value |= (byte[0] & 0x7F) << shift
        if not byte[0] & 0x80:
            return value
        shift += 7
    raise _Malformed("a number is too long")


def _string_pair(data: bytes) -> Optional[Tuple[str, str]]:
    """A StringStringEntryProto: field 1 the key, field 2 the value."""
    handle = io.BytesIO(data)
    key = value = None
    while handle.tell() < len(data):
        tag = _varint(handle)
        field, wire = tag >> 3, tag & 7
        if wire == 2:
            size = _varint(handle)
            chunk = handle.read(size)
            if len(chunk) != size:
                raise _Malformed("an entry ends early")
            if field == 1:
                key = chunk.decode("utf-8", "replace")
            elif field == 2:
                value = chunk.decode("utf-8", "replace")
        elif wire == 0:
            _varint(handle)
        elif wire == 1:
            handle.read(8)
        elif wire == 5:
            handle.read(4)
        else:
            raise _Malformed("an entry has a field this reader does not know")
    return (key, value) if key is not None and value is not None else None


def read_onnx_metadata(handle: BinaryIO, size: int) -> Optional[Dict[str, str]]:
    """The model's metadata (key to text), read from the top level of the file only, so the weights are skipped over, not read. None when the file is not
    shaped like an ONNX model: a file starts with the model's `ir_version`, and every length has to fit in the file."""
    try:
        handle.seek(0)
        first = handle.read(1)
        if first != b"\x08":
            return None
        handle.seek(0)
        found: Dict[str, str] = {}
        while True:
            if handle.tell() >= size:
                break
            tag = _varint(handle)
            field, wire = tag >> 3, tag & 7
            if field == 0:
                raise _Malformed("field zero")
            if wire == 0:
                _varint(handle)
            elif wire == 1:
                handle.seek(8, os.SEEK_CUR)
            elif wire == 5:
                handle.seek(4, os.SEEK_CUR)
            elif wire == 2:
                length = _varint(handle)
                if handle.tell() + length > size:
                    raise _Malformed("a part is longer than the file")
                if field == 14:
                    if length > MAX_META_ENTRY:
                        raise _Malformed("a metadata entry is too large")
                    pair = _string_pair(handle.read(length))
                    if pair is not None:
                        found[pair[0]] = pair[1]
                else:
                    handle.seek(length, os.SEEK_CUR)
            else:
                raise _Malformed("a field of a kind ONNX does not use")
        if handle.tell() != size:
            raise _Malformed("the file ends in the middle of a field")
        return found
    except (_Malformed, OSError, ValueError):
        return None


# ---------------------------------------------------------------- the checks

@dataclass(frozen=True)
class VoiceCheck:
    problems: Tuple[str, ...]           # PROBLEM_CODES; empty means ACK will take it
    metadata: Dict[str, str]
    sample_rate: Optional[int]
    skipped_symbols: int                # phoneme symbols that are more than one character; the phone leaves them out (CLAUDE.md), listed for the details

    @property
    def ok(self) -> bool:
        return not self.problems


def _config_problems(raw: bytes) -> Tuple[List[str], Optional[dict]]:
    if not raw:
        return ["config_empty"], None
    if len(raw) > MAX_CONFIG_BYTES:
        return ["config_too_big"], None
    try:
        data = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError, RecursionError):      # a settings file nested far too deep is not JSON a phone could read either
        return ["config_not_json"], None
    if not isinstance(data, dict) or not all(k in data for k in CONFIG_KEYS):
        return ["config_not_piper"], None
    return [], data


def check_voice(model: Path, config: Path) -> VoiceCheck:
    """Everything ACK would refuse, and the one thing it would crash on: a model nobody patched. Reads the files, changes nothing."""
    problems: List[str] = []
    metadata: Dict[str, str] = {}
    try:
        size = Path(model).stat().st_size
    except OSError:
        size = -1
    if size < 0:
        problems.append("model_missing")
    elif size == 0:
        problems.append("model_empty")
    elif size > MAX_MODEL_BYTES:
        problems.append("model_too_big")
    else:
        with open(model, "rb") as handle:
            read = read_onnx_metadata(handle, size)
        if read is None:
            problems.append("not_onnx")
        else:
            metadata = read
            if any(k not in metadata for k in REQUIRED_METADATA):
                problems.append("not_patched")
            elif "piper" not in metadata["comment"]:
                problems.append("wrong_comment")

    data: Optional[dict] = None
    try:
        raw = Path(config).read_bytes()
    except OSError:
        problems.append("config_missing")
    else:
        found, data = _config_problems(raw)
        problems += found

    rate: Optional[int] = None
    skipped = 0
    if data is not None:
        audio = data.get("audio")
        rate = audio.get("sample_rate") if isinstance(audio, dict) and isinstance(audio.get("sample_rate"), int) and not isinstance(audio.get("sample_rate"), bool) else None
        if rate is None:
            problems.append("config_not_piper")
        elif "sample_rate" in metadata and metadata["sample_rate"] != str(rate):
            problems.append("rate_mismatch")
        speakers = data.get("num_speakers", 1)
        if "n_speakers" in metadata and metadata["n_speakers"] != str(speakers):
            problems.append("speakers_mismatch")
        symbols = data.get("phoneme_id_map")
        if isinstance(symbols, dict):
            skipped = sum(1 for key in symbols if isinstance(key, str) and len(key) != 1 and key != "\n")
    return VoiceCheck(tuple(dict.fromkeys(problems)), metadata, rate, skipped)


# ---------------------------------------------------------------- writing and reading back

def _sha256(handle: BinaryIO) -> str:
    digest = hashlib.sha256()
    for block in iter(lambda: handle.read(CHUNK), b""):
        digest.update(block)
    return digest.hexdigest()


@dataclass(frozen=True)
class ZipReport:
    path: str
    zip_bytes: int
    model_bytes: int
    config_bytes: int
    model_sha256: str
    config_sha256: str
    skipped_symbols: int


def _write_entry(zf: zipfile.ZipFile, name: str, source: Path, compress: int) -> None:
    info = zipfile.ZipInfo(name, FIXED_TIME)
    info.compress_type = compress
    info.external_attr = (stat.S_IFREG | 0o600) << 16
    with open(source, "rb") as src, zf.open(info, "w") as out:
        shutil.copyfileobj(src, out, CHUNK)


def write_voice_zip(model: Path, config: Path, dest: Path) -> ZipReport:
    """Check the voice, then make `dest` from it. Raises VoiceZipError and leaves nothing behind (not even a half-written file) on any failure; never replaces `dest`."""
    model, config, dest = Path(model), Path(config), Path(dest)
    found = check_voice(model, config)
    if found.problems:
        raise VoiceZipError("not_ready", problems=found.problems)
    if dest.exists() or dest.is_symlink():
        raise VoiceZipError("exists", dest.name)
    folder = dest.parent
    if not folder.is_dir():
        raise VoiceZipError("write_failed", "the folder is not there")
    needed = model.stat().st_size + config.stat().st_size + ROOM_MARGIN_BYTES
    if shutil.disk_usage(str(folder)).free < needed:
        raise VoiceZipError("no_room", "%d bytes needed" % needed)
    part = dest.with_name(dest.name + ".part")
    try:
        fd = os.open(str(part), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "wb") as handle, zipfile.ZipFile(handle, "w") as zf:
            _write_entry(zf, MODEL_ENTRY, model, zipfile.ZIP_STORED)
            _write_entry(zf, CONFIG_ENTRY, config, zipfile.ZIP_DEFLATED)
        report = _verify(part, model, config, found)
        with open(part, "rb+") as handle:
            os.fsync(handle.fileno())
        os.replace(str(part), str(dest))
    except VoiceZipError:
        _remove_quietly(part)
        raise
    except OSError as exc:
        _remove_quietly(part)
        raise VoiceZipError("write_failed", exc.strerror or type(exc).__name__)
    return ZipReport(str(dest), report.zip_bytes, report.model_bytes, report.config_bytes, report.model_sha256, report.config_sha256, found.skipped_symbols)


def _verify(zip_path: Path, model: Path, config: Path, found: VoiceCheck) -> ZipReport:
    """Read the zip back: exactly the two entries, ACK's size limits, and every byte equal to the file it came from."""
    zip_bytes = zip_path.stat().st_size
    if zip_bytes > MAX_ZIP_BYTES:
        raise VoiceZipError("verify_failed", "the zip is larger than ACK accepts")
    try:
        with zipfile.ZipFile(zip_path) as zf:
            if [i.filename for i in zf.infolist()] != [MODEL_ENTRY, CONFIG_ENTRY]:
                raise VoiceZipError("verify_failed", "the entries are not exactly the two ACK expects")
            if zf.testzip() is not None:
                raise VoiceZipError("verify_failed", "an entry did not read back")
            hashes = []
            for name, source in ((MODEL_ENTRY, model), (CONFIG_ENTRY, config)):
                with zf.open(name) as inside, open(source, "rb") as original:
                    a, b = _sha256(inside), _sha256(original)
                if a != b:
                    raise VoiceZipError("verify_failed", "%s does not match the file it came from" % name)
                hashes.append((a, zf.getinfo(name).file_size))
    except zipfile.BadZipFile:
        raise VoiceZipError("verify_failed", "the zip did not open")
    return ZipReport(str(zip_path), zip_bytes, hashes[0][1], hashes[1][1], hashes[0][0], hashes[1][0], found.skipped_symbols)


def verify_voice_zip(path: Path) -> Tuple[str, ...]:
    """Would ACK take this zip? PROBLEM_CODES or 'zip_*' facts, from the same rules the phone applies. Reads the file, changes nothing."""
    path = Path(path)
    problems: List[str] = []
    try:
        size = path.stat().st_size
    except OSError:
        return ("zip_missing",)
    if size > MAX_ZIP_BYTES:
        problems.append("zip_too_big")
    try:
        with zipfile.ZipFile(path) as zf:
            names = {i.filename: i for i in zf.infolist()}
            if MODEL_ENTRY not in names or CONFIG_ENTRY not in names:
                return tuple(problems + ["zip_wrong_entries"])
            model_info, config_info = names[MODEL_ENTRY], names[CONFIG_ENTRY]
            if model_info.file_size == 0:
                problems.append("model_empty")
            elif model_info.file_size > MAX_MODEL_BYTES:
                problems.append("model_too_big")
            else:
                with zf.open(MODEL_ENTRY) as inside:
                    meta = read_onnx_metadata(_Seekable(inside), model_info.file_size)
                if meta is None:
                    problems.append("not_onnx")
                elif any(k not in meta for k in REQUIRED_METADATA):
                    problems.append("not_patched")
                elif "piper" not in meta["comment"]:
                    problems.append("wrong_comment")
            if config_info.file_size > MAX_CONFIG_BYTES:
                problems.append("config_too_big")
            else:
                found, _ = _config_problems(zf.read(CONFIG_ENTRY))
                problems += found
    except zipfile.BadZipFile:
        return tuple(problems + ["zip_unreadable"])
    return tuple(dict.fromkeys(problems))


class _Seekable:
    """A zip entry as a file `read_onnx_metadata` can seek in (the library's own entry object seeks, but slowly backwards; this reads forward only)."""

    def __init__(self, inside: BinaryIO):
        self._inside = inside
        self._pos = 0

    def tell(self) -> int:
        return self._pos

    def read(self, n: int = -1) -> bytes:
        data = self._inside.read(n)
        self._pos += len(data)
        return data

    def seek(self, offset: int, whence: int = os.SEEK_SET) -> int:
        target = offset if whence == os.SEEK_SET else self._pos + offset
        if target < self._pos:
            self._inside.seek(target)
            self._pos = target
            return target
        remaining = target - self._pos
        while remaining > 0:
            chunk = self._inside.read(min(remaining, CHUNK))
            if not chunk:
                break
            remaining -= len(chunk)
            self._pos += len(chunk)
        return self._pos


def _remove_quietly(path: Path) -> None:
    try:
        path.unlink()
    except OSError:
        pass
