# SPDX-License-Identifier: GPL-3.0-or-later
"""Brings a folder of voice recordings (or a .zip of one) into Freeform Studio, for a person who already has recordings and did not make them with ACK.

    python -m freeform_studio.files_import ~/my-voice --kind pairs --dry-run      # look, write nothing
    python -m freeform_studio.files_import ~/my-voice --kind table                # shows the plan, then asks

What the sentences are is the person's choice of --kind, never a guess:
  pairs   an audio file with a text file of the same name beside it (`001.wav` and `001.txt`)
  table   one table in the folder (`metadata.csv`, ...), a row for each file: the file's name, then its sentence
  audio   audio only; whatever sentences there are in the folder are ignored, and the PC listens and writes them for the person to read

Files that come with a sentence become **one recording per batch** (up to 20 minutes or 150 files, in name order, with a short quiet gap between them), exactly the way ACK's script sessions are joined,
and the sentence of each travels with its file: the PC still listens and writes what it hears, and a file whose sentence does not match what was heard is flagged, so it stays out of a training set
until a person has looked. A file with no sentence is its own recording, cut into pieces the usual way.

Safe by design, like importing an ACK package: the folder is only ever read (a .zip is unpacked into this program's own `incoming` folder, never into the person's), every file is checked and its
content fingerprinted before anything is written, importing only ever adds, a file that was imported before is recognised by its content and skipped (so running it twice is harmless, and so is a
renamed copy), and a file that cannot be read is reported and left out without stopping the rest. Nothing here uses the network, and no sentence or file name is ever logged.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import unicodedata
import wave
import zipfile
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from .ack_import import GAP_S, ImportProblem, NotEnoughRoom, PartWriter, Created, _move_aside, _reference_text, wav_header
from .config import Config
from .health import free_mb
from .privacy import private_umask, sync_warning
from .storage import TAKE_ID_RE, TakeStore, now_iso, read_json

KINDS = ("pairs", "table", "audio")
AUDIO_EXTENSIONS = (".wav", ".flac", ".mp3", ".m4a", ".ogg", ".oga", ".opus", ".aac", ".wma", ".webm", ".aif", ".aiff")
TEXT_EXTENSIONS = (".txt", ".csv", ".tsv")
TABLE_NAMES = ("metadata.csv", "metadata.tsv", "metadata.txt", "transcript.csv", "transcripts.csv", "transcript.tsv", "transcripts.tsv", "transcript.txt", "transcripts.txt")
HEADER_FILE_CELLS = ("file", "filename", "file_name", "id", "audio", "audio_file", "path", "wav", "wav_file", "name", "clip")
HEADER_TEXT_CELLS = ("text", "transcript", "transcription", "sentence", "normalized", "normalised", "utterance", "label")

WORK_RATE = 48000                   # the rate Freeform Studio decodes every recording to (audio.WORK_RATE; a test keeps the two equal). This file imports no numpy, so the window can use it.
MAX_FILES = 20_000                  # audio files in one import: more than a person records by hand, a firewall against a wrong folder
MAX_DEPTH = 6                       # folders below the chosen one
MAX_FILE_BYTES = 2 * 1024 ** 3
MAX_TABLE_BYTES = 20 * 1024 ** 2
MAX_SIDECAR_BYTES = 64 * 1024
MAX_UNPACKED_BYTES = 40 * 1024 ** 3
MAX_TEXT = 500                      # a sentence for one clip; longer is not a clip's sentence
MIN_SECONDS = 0.5                   # shorter than this is no use as a clip (the job that listens refuses under 0.3 s)
BATCH_MAX_S = 20 * 60
BATCH_MAX_CLIPS = 150
UNKNOWN_BYTES_PER_SECOND = 16_000   # a compressed file whose length cannot be read: about 128 kbit/s, which makes the room estimate cautious
PROBE_WORKERS = 4
CHUNK = 1 << 20
LANGUAGE = "en-US"
SKIP_NAMES = ("__MACOSX", ".DS_Store", "Thumbs.db")

Progress = Callable[[str, int, int], None]          # (stage, done, total): stage is "scan", "fingerprint" or "unpack"


class FilesImportProblem(ImportProblem):
    """Something that stops the import, in words a person can act on. `code` is a short word the screens turn into a sentence."""

    def __init__(self, code: str, detail: str = ""):
        super().__init__(detail or code)
        self.code = code
        self.detail = detail


@dataclass
class Item:
    rel: str                        # the path under the chosen folder, with '/'
    path: Path
    size: int
    sha256: str = ""
    text: str = ""                  # the sentence that came with it ("" when none)
    text_from: str = ""             # "sidecar" or "table"
    seconds: Optional[float] = None
    state: str = "new"              # new | already | duplicate | unusable
    reason: str = ""                # why unusable: too_big, too_short, unreadable, text_too_long


@dataclass
class Problem:
    code: str                       # a short word; see PROBLEM_CODES
    what: str = ""                  # the file or row it is about, by name; "" when it is about the whole folder
    detail: str = ""


PROBLEM_CODES = ("link_skipped", "text_unreadable", "text_too_long", "table_missing", "table_unreadable", "table_many", "table_row_no_audio", "table_row_ambiguous", "table_row_repeated",
                 "table_bad_rows", "too_big", "too_short", "unreadable")
STOP_CODES = ("bad_kind", "not_a_folder", "no_audio", "too_many_files", "unreadable", "too_big")              # what stops an import before anything is looked at or written


@dataclass
class Plan:
    source: Path
    source_name: str
    kind: str
    table: str
    items: List[Item]
    problems: List[Problem]
    output: Path
    code: str
    takes_dir: Path
    free_mb: float
    min_free_mb: float
    unpacked: bool = False          # the source was a .zip, unpacked into this program's own incoming folder

    @property
    def to_import(self) -> List[Item]:
        return [i for i in self.items if i.state == "new"]

    @property
    def need_mb(self) -> float:
        return sum(estimated_need_mb(i) for i in self.to_import)

    @property
    def enough_room(self) -> bool:
        return self.free_mb - self.need_mb >= self.min_free_mb

    @property
    def seconds_new(self) -> float:
        return sum(item_seconds(i) for i in self.to_import)

    @property
    def with_text(self) -> int:
        return sum(1 for i in self.to_import if i.text)

    def count(self, state: str) -> int:
        return sum(1 for i in self.items if i.state == state)


def item_seconds(item: Item) -> float:
    return item.seconds if item.seconds is not None else item.size / UNKNOWN_BYTES_PER_SECOND


def estimated_need_mb(item: Item) -> float:
    """The room one file needs while it is brought in: the parts, the joined copy, and the decoded copy the listening step makes (all 48 kHz, 16 bit)."""
    return (item_seconds(item) * WORK_RATE * 2 * 3) / (1024 * 1024)


# ---------------------------------------------------------------- reading text

def clean_sentence(text: str) -> str:
    """One line, single spaces, no control characters. Nothing else is changed: the sentence stays what the person wrote."""
    joined = " ".join(str(text).split())
    return "".join(ch for ch in joined if unicodedata.category(ch) not in ("Cc", "Cs")).strip()


def read_small_text(path: Path, limit: int) -> Optional[str]:
    """The text of a small UTF-8 file (a byte order mark is fine), or None when it is too big, not UTF-8 or cannot be read."""
    try:
        if path.stat().st_size > limit:
            return None
        return path.read_bytes().decode("utf-8-sig")
    except (OSError, UnicodeDecodeError):
        return None


@dataclass(frozen=True)
class TableRows:
    rows: Tuple[Tuple[str, str], ...]       # (the file's name as written, its sentence)
    delimiter: str
    header: bool
    bad_rows: int                           # rows with no second cell, left out


def _delimiter(lines: Sequence[str]) -> str:
    """The first of `|`, a tab and a comma that is on at least four lines in five of the first lines (a stray line without one is a row to leave out, not a reason to refuse the table)."""
    for candidate in ("|", "\t", ","):
        if lines and sum(1 for line in lines if candidate in line) * 5 >= len(lines) * 4:
            return candidate
    return ""


def parse_table(text: str) -> Optional[TableRows]:
    """The rows of a table: one row per file, the file's name first and its sentence second (a third cell, as LJSpeech's normalised text, is ignored). The delimiter is `|`, a tab or a comma, the
    first of them that is on every one of the first lines; a first row that names its columns (file, text) is a header and is not a row. None when it does not look like a table at all."""
    lines = [line for line in text.splitlines() if line.strip()]
    if not lines:
        return None
    delimiter = _delimiter(lines[:20])
    if not delimiter:
        return None
    if delimiter == "|":
        reader = csv.reader(io.StringIO("\n".join(lines)), delimiter="|", quoting=csv.QUOTE_NONE)
    else:
        reader = csv.reader(io.StringIO("\n".join(lines)), delimiter=delimiter)
    rows: List[List[str]] = [list(row) for row in reader]
    header = bool(rows) and len(rows[0]) >= 2 and rows[0][0].strip().lower() in HEADER_FILE_CELLS and rows[0][1].strip().lower() in HEADER_TEXT_CELLS
    body = rows[1:] if header else rows
    good: List[Tuple[str, str]] = []
    bad = 0
    for row in body:
        if len(row) < 2 or not row[0].strip():
            bad += 1
            continue
        good.append((row[0].strip(), row[1]))
    return TableRows(tuple(good), delimiter, header, bad)


# ---------------------------------------------------------------- finding the files

def natural_key(rel: str) -> List[Any]:
    return [int(part) if part.isdigit() else part for part in re.split(r"(\d+)", rel.lower())]


def _walk(folder: Path, problems: List[Problem]) -> Tuple[List[Tuple[str, Path]], List[Tuple[str, Path]]]:
    """(audio files, other candidate files: text and tables) under `folder` as (relative path, path), links and hidden or system files left out."""
    audio: List[Tuple[str, Path]] = []
    other: List[Tuple[str, Path]] = []
    stack: List[Tuple[Path, int]] = [(folder, 0)]
    while stack:
        current, depth = stack.pop()
        try:
            entries = sorted(os.scandir(current), key=lambda e: e.name)
        except OSError:
            continue
        for entry in entries:
            if entry.name.startswith(".") or entry.name in SKIP_NAMES:
                continue
            rel = entry.path[len(str(folder)):].lstrip("/")
            if entry.is_symlink():
                problems.append(Problem("link_skipped", rel))
                continue
            if entry.is_dir(follow_symlinks=False):
                if depth < MAX_DEPTH:
                    stack.append((Path(entry.path), depth + 1))
                continue
            if not entry.is_file(follow_symlinks=False):
                continue
            ext = os.path.splitext(entry.name)[1].lower()
            if ext in AUDIO_EXTENSIONS:
                audio.append((rel, Path(entry.path)))
            elif ext in TEXT_EXTENSIONS:
                other.append((rel, Path(entry.path)))
    audio.sort(key=lambda pair: natural_key(pair[0]))
    return audio, other


def _find_table(folder: Path, other: Sequence[Tuple[str, Path]], wanted: str, problems: List[Problem]) -> Optional[Tuple[str, Path]]:
    if wanted:
        for rel, path in other:
            if rel == wanted or path.name == wanted:
                return rel, path
        problems.append(Problem("table_missing", wanted))
        return None
    found = [(rel, path) for rel, path in other if path.name.lower() in TABLE_NAMES]
    if not found:
        problems.append(Problem("table_missing"))
        return None
    found.sort(key=lambda pair: (pair[0].count("/"), natural_key(pair[0])))              # the one nearest the top
    if len(found) > 1 and found[0][0].count("/") == found[1][0].count("/"):
        problems.append(Problem("table_many", found[0][0], ", ".join(rel for rel, _ in found[1:4])))
    return found[0]


def _index(items: Sequence[Item]) -> Dict[str, Dict[str, List[Item]]]:
    by: Dict[str, Dict[str, List[Item]]] = {"rel": {}, "rel_noext": {}, "name": {}, "stem": {}}
    for item in items:
        noext = os.path.splitext(item.rel)[0]
        name = os.path.basename(item.rel)
        for key, value in (("rel", item.rel), ("rel_noext", noext), ("name", name), ("stem", os.path.splitext(name)[0])):
            by[key].setdefault(value, []).append(item)
    return by


def _match(ref: str, by: Dict[str, Dict[str, List[Item]]]) -> Tuple[Optional[Item], bool]:
    """(the file a table row means, whether the row is ambiguous). A name is tried as a path, then as a path without its extension, then as a bare file name, then as a bare name without it."""
    clean = ref.replace("\\", "/").lstrip("/")
    for key, value in (("rel", clean), ("rel_noext", clean), ("name", clean), ("stem", clean), ("name", os.path.basename(clean)), ("stem", os.path.basename(clean))):
        found = by[key].get(value)
        if found:
            return (found[0], False) if len(found) == 1 else (None, True)
    return None, False


def fingerprint(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(CHUNK), b""):
            digest.update(block)
    return digest.hexdigest()


def probe_seconds(path: Path) -> Optional[float]:
    """The length of an audio file, or None when it cannot be read from the file itself. A wav is read from its header; anything else is asked of ffprobe when it is there."""
    if path.suffix.lower() == ".wav":
        try:
            with wave.open(str(path), "rb") as handle:
                rate = handle.getframerate()
                return handle.getnframes() / rate if rate else None
        except (wave.Error, EOFError, OSError):
            pass
    exe = shutil.which("ffprobe")
    if not exe:
        return None
    try:
        done = subprocess.run([exe, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)], capture_output=True, text=True, timeout=60, stdin=subprocess.DEVNULL)
        value = float(done.stdout.strip().splitlines()[0])
        return value if value >= 0 else None
    except (OSError, ValueError, IndexError, subprocess.SubprocessError):
        return None


def _already_imported(takes_dir: Path) -> Dict[str, str]:
    """content fingerprint -> the recording that holds it, for every file this program has brought in from a folder before. A recording whose import was cut short does not count."""
    found: Dict[str, str] = {}
    if not takes_dir.is_dir():
        return found
    for folder in sorted(takes_dir.iterdir()):
        if not folder.is_dir() or not TAKE_ID_RE.match(folder.name):
            continue
        try:
            take = read_json(folder / "take.json") or {}
            if take.get("status") == "importing":
                continue
            notes = read_json(folder / "ack_clips.json") or {}
        except (OSError, ValueError):
            continue
        sha = (take.get("client") or {}).get("source_sha256")
        if isinstance(sha, str) and sha:
            found[sha] = folder.name
        for clip in (notes.get("clips") or []) if isinstance(notes, dict) else []:
            if isinstance(clip, dict) and isinstance(clip.get("source_sha256"), str):
                found[clip["source_sha256"]] = folder.name
    return found


def _free_mb(path: Path) -> float:
    probe = Path(path)
    while not probe.exists() and probe != probe.parent:
        probe = probe.parent
    return free_mb(probe)


def make_plan(source: Path, kind: str, output: Path, code: str = LANGUAGE, table: str = "", progress: Optional[Progress] = None) -> Plan:
    """Look at a folder (or a .zip) and say what would be added. Writes nothing, except that a .zip is unpacked into this program's own `incoming` folder first."""
    if kind not in KINDS:
        raise FilesImportProblem("bad_kind", kind)
    source = Path(source).expanduser()
    cfg = Config(output_dir=Path(output), code=code)
    unpacked = False
    try:
        if source.is_file():
            if not zipfile.is_zipfile(source):
                raise FilesImportProblem("not_a_folder", source.name)
            folder = unpack_zip(source, cfg.root / "incoming", progress)
            unpacked = True
        elif source.is_dir() and not source.is_symlink():
            folder = source
        else:
            raise FilesImportProblem("not_a_folder", source.name)
    except OSError as exc:
        raise FilesImportProblem("unreadable", exc.strerror or type(exc).__name__)
    problems: List[Problem] = []
    audio, other = _walk(folder, problems)
    if not audio:
        raise FilesImportProblem("no_audio", source.name)
    if len(audio) > MAX_FILES:
        raise FilesImportProblem("too_many_files", str(len(audio)))
    items: List[Item] = []
    for rel, path in audio:
        try:
            size = path.stat().st_size
        except OSError:
            problems.append(Problem("unreadable", rel))
            continue
        item = Item(rel, path, size)
        if size > MAX_FILE_BYTES:
            item.state, item.reason = "unusable", "too_big"
        elif size == 0:
            item.state, item.reason = "unusable", "unreadable"
        items.append(item)

    table_name = ""
    if kind == "pairs":
        for item in items:
            sidecar = item.path.with_suffix(".txt")
            if not sidecar.is_file() or sidecar.is_symlink():
                continue
            raw = read_small_text(sidecar, MAX_SIDECAR_BYTES)
            if raw is None:
                problems.append(Problem("text_unreadable", item.rel))
                continue
            _give_text(item, raw, "sidecar")
    elif kind == "table":
        found = _find_table(folder, other, table, problems)
        if found is not None:
            table_name = found[0]
            raw = read_small_text(found[1], MAX_TABLE_BYTES)
            parsed = parse_table(raw) if raw is not None else None
            if parsed is None:
                problems.append(Problem("table_unreadable", table_name))
            else:
                if parsed.bad_rows:
                    problems.append(Problem("table_bad_rows", table_name, str(parsed.bad_rows)))
                by = _index(items)
                seen: Dict[int, str] = {}
                for ref, sentence in parsed.rows:
                    item, ambiguous = _match(ref, by)
                    if ambiguous:
                        problems.append(Problem("table_row_ambiguous", ref))
                    elif item is None:
                        problems.append(Problem("table_row_no_audio", ref))
                    elif id(item) in seen:
                        problems.append(Problem("table_row_repeated", ref))
                    else:
                        seen[id(item)] = ref
                        _give_text(item, sentence, "table")

    imported = _already_imported(cfg.takes_dir)
    first_seen: Dict[str, Item] = {}
    live = [i for i in items if i.state == "new"]
    for done, item in enumerate(live, 1):
        try:
            item.sha256 = fingerprint(item.path)
        except OSError:
            item.state, item.reason = "unusable", "unreadable"
            continue
        if progress:
            progress("fingerprint", done, len(live))
        if item.sha256 in imported:
            item.state = "already"
        elif item.sha256 in first_seen:
            item.state = "duplicate"
        else:
            first_seen[item.sha256] = item
    with ThreadPoolExecutor(max_workers=PROBE_WORKERS) as pool:
        for item, seconds in zip([i for i in items if i.state == "new"], pool.map(probe_seconds, [i.path for i in items if i.state == "new"])):
            item.seconds = seconds
            if seconds is not None and seconds < MIN_SECONDS:
                item.state, item.reason = "unusable", "too_short"
    for item in items:
        if item.state == "unusable":
            problems.append(Problem(item.reason, item.rel))
    return Plan(folder, source.name, kind, table_name, items, problems, Path(output), code, cfg.takes_dir, _free_mb(Path(output)), float(cfg.min_free_mb), unpacked)


def _give_text(item: Item, raw: str, origin: str) -> None:
    sentence = clean_sentence(raw)
    if len(sentence) > MAX_TEXT:
        item.state, item.reason = "unusable", "text_too_long"
        return
    item.text, item.text_from = sentence, origin if sentence else ""


# ---------------------------------------------------------------- decoding

class DecodeError(Exception):
    """A file could not be turned into audio: it is not audio, is damaged, or ffmpeg is not there."""


def decode_to_wav(src: Path, dst: Path, sample_rate: int = WORK_RATE) -> None:
    """Decode any audio ffmpeg knows to mono 16-bit PCM wav, written under a temporary name first and then moved into place (the same command Freeform Studio's own decoder runs)."""
    exe = shutil.which("ffmpeg")
    if not exe:
        raise DecodeError("ffmpeg is not installed")
    tmp = dst.with_name(dst.name + ".tmp.wav")
    command = [exe, "-nostdin", "-y", "-loglevel", "error", "-i", str(src), "-vn", "-ac", "1", "-ar", str(sample_rate), "-c:a", "pcm_s16le", str(tmp)]
    try:
        done = subprocess.run(command, capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=3600)
    except (OSError, subprocess.SubprocessError) as exc:
        raise DecodeError(type(exc).__name__)
    if done.returncode != 0 or not tmp.exists():
        try:
            tmp.unlink()
        except OSError:
            pass
        raise DecodeError((done.stderr or "ffmpeg failed").strip()[-200:])
    tmp.replace(dst)


def wav_frames(path: Path) -> int:
    with wave.open(str(path), "rb") as handle:
        return handle.getnframes()


# ---------------------------------------------------------------- a .zip

def unpack_zip(archive: Path, incoming: Path, progress: Optional[Progress] = None) -> Path:
    """Unpack the audio and text files of a .zip into `incoming/files-<first part of its fingerprint>/` and return that folder. The .zip is only read. A name that is absolute, climbs out with `..`,
    names a link, or is not a file this import uses is not unpacked; sizes are counted as they are written, not trusted from the header. An earlier complete unpacking of the same .zip is reused."""
    sha = fingerprint(archive)
    destination = incoming / ("files-" + sha[:16])
    done_marker = destination / ".complete"
    if done_marker.is_file():
        return destination
    destination.mkdir(parents=True, exist_ok=True, mode=0o700)
    total = 0
    count = 0
    with zipfile.ZipFile(archive) as zf:
        infos = [i for i in zf.infolist() if not i.is_dir()]
        if len(infos) > MAX_FILES * 2:
            raise FilesImportProblem("too_many_files", str(len(infos)))
        for number, info in enumerate(infos, 1):
            name = info.filename
            pure = PurePosixPath(name.replace("\\", "/"))
            if (pure.is_absolute() or ".." in pure.parts or "\x00" in name or any(p.startswith(".") or p in SKIP_NAMES for p in pure.parts)
                    or stat.S_ISLNK(info.external_attr >> 16) or pure.suffix.lower() not in AUDIO_EXTENSIONS + TEXT_EXTENSIONS):
                continue
            if info.file_size > MAX_FILE_BYTES:
                continue
            target = destination.joinpath(*pure.parts)
            target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            written = 0
            fd = os.open(str(target), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with zf.open(info) as source, os.fdopen(fd, "wb") as out:
                for block in iter(lambda: source.read(CHUNK), b""):
                    written += len(block)
                    total += len(block)
                    if written > info.file_size or total > MAX_UNPACKED_BYTES:
                        raise FilesImportProblem("too_big", archive.name)
                    out.write(block)
                out.flush()
                os.fsync(out.fileno())
            count += 1
            if progress:
                progress("unpack", number, len(infos))
    if not count:
        raise FilesImportProblem("no_audio", archive.name)
    fd = os.open(str(done_marker), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    os.close(fd)
    return destination


# ---------------------------------------------------------------- adding

def _patch_wav_header(store: TakeStore, take_id: str, frames: int) -> None:
    """The first part holds the wav header written before the length was known: put the real lengths in it."""
    first = store.path(take_id, "parts", "000000.bin")
    data = bytearray(first.read_bytes())
    data[0:44] = wav_header(WORK_RATE, frames * 2)
    store.write_chunk(take_id, 0, bytes(data))


def _copy_decoded(wav: Path, writer: PartWriter) -> int:
    """Put the samples of a decoded 48 kHz mono wav into the take's parts. Returns the number of frames."""
    frames = 0
    with wave.open(str(wav), "rb") as handle:
        if handle.getsampwidth() != 2 or handle.getnchannels() != 1 or handle.getframerate() != WORK_RATE:
            raise DecodeError("the decoded copy is not 48 kHz mono 16 bit")
        while True:
            block = handle.readframes(1 << 18)
            if not block:
                return frames
            writer.write(block)
            frames += len(block) // 2


@dataclass
class Skipped:
    rel: str
    reason: str                     # unreadable, too_short


@dataclass
class Result:
    created: List[Created] = field(default_factory=list)
    skipped: List[Skipped] = field(default_factory=list)
    clips: int = 0                  # files that were added


def _batches(items: Sequence[Item]) -> List[List[Item]]:
    """The files that come with a sentence, in name order, in groups that become one recording each. A file with no sentence is a group of its own."""
    groups: List[List[Item]] = []
    current: List[Item] = []
    seconds = 0.0
    for item in items:
        if not item.text:
            groups.append([item])
            continue
        length = item_seconds(item) + GAP_S
        if current and (len(current) >= BATCH_MAX_CLIPS or seconds + length > BATCH_MAX_S):
            groups.append(current)
            current, seconds = [], 0.0
        current.append(item)
        seconds += length
    if current:
        groups.append(current)
    return groups


def _retire_leftovers(plan: Plan, say: Callable[[str], None]) -> None:
    """A recording this import began and did not finish (the computer stopped, say) is moved aside, never deleted, and its files are brought in again."""
    if not plan.takes_dir.is_dir():
        return
    for folder in sorted(plan.takes_dir.iterdir()):
        if not folder.is_dir() or not TAKE_ID_RE.match(folder.name):
            continue
        take = read_json(folder / "take.json") or {}
        if take.get("status") == "importing" and (take.get("client") or {}).get("source") == "files":
            moved = _move_aside(plan, folder.name)             # type: ignore[arg-type]
            say("An earlier import was cut short. Its leftovers were moved to " + str(moved))


def apply_import(plan: Plan, progress: Optional[Callable[[str], None]] = None) -> Result:
    """Add the files the plan lists as new. A file that cannot be decoded is left out and reported; the rest are added. If there is not room, nothing is written."""
    say = progress or (lambda _msg: None)
    if not plan.enough_room:
        raise NotEnoughRoom("There is not enough free space: this needs about %.0f MB and keeping %.0f MB spare, but only %.0f MB is free. Free some up and run the import again; nothing was written."
                            % (plan.need_mb, plan.min_free_mb, plan.free_mb))
    store = TakeStore(plan.takes_dir)
    _retire_leftovers(plan, say)
    result = Result()
    groups = _batches(plan.to_import)
    with tempfile.TemporaryDirectory(prefix="files-import-", dir=str(plan.takes_dir.parent)) as scratch:
        for number, group in enumerate(groups, 1):
            say("Adding recording %d of %d (%d file%s) ..." % (number, len(groups), len(group), "" if len(group) == 1 else "s"))
            made = _add_group(plan, store, group, number, len(groups), Path(scratch), result)
            if made is not None:
                result.created.append(made)
    return result


def _add_group(plan: Plan, store: TakeStore, group: List[Item], number: int, total: int, scratch: Path, result: Result) -> Optional[Created]:
    with_text = bool(group[0].text)
    if not with_text:
        label = os.path.splitext(os.path.basename(group[0].rel))[0]
    elif total == 1:
        label = plan.source_name
    else:
        label = "%s (%d of %d)" % (plan.source_name, number, total)
    label = label[:120]
    client = {"source": "files", "files_kind": plan.kind, "files_source": plan.source_name[:60], "files_group": number}
    if not with_text:
        client["source_sha256"] = group[0].sha256
    take = store.create({"label": label or "Imported files", "status": "importing", "reference_text": "", "mime": "audio/wav", "client": client,
                         "imported_from": plan.source_name[:120], "imported_at": now_iso()})
    take_id = take["id"]
    writer = PartWriter(store, take_id)
    writer.write(wav_header(WORK_RATE, 0))
    clips: List[Dict[str, Any]] = []
    position = 0
    gap = int(round(GAP_S * WORK_RATE))
    for index, item in enumerate(group):
        decoded = scratch / ("item-%d.wav" % index)
        try:
            decode_to_wav(item.path, decoded, WORK_RATE)
            rate_frames = wav_frames(decoded)
            if rate_frames < WORK_RATE * MIN_SECONDS:
                result.skipped.append(Skipped(item.rel, "too_short"))
                continue
            before = position + (gap if clips else 0)
            if clips:
                writer.write(b"\x00" * (gap * 2))
            frames = _copy_decoded(decoded, writer)
        except (DecodeError, OSError, wave.Error, EOFError):
            result.skipped.append(Skipped(item.rel, "unreadable"))
            continue
        finally:
            try:
                decoded.unlink()
            except OSError:
                pass
        clips.append({"index": len(clips), "text": item.text, "text_from": item.text_from, "start_s": round(before / WORK_RATE, 3), "end_s": round((before + frames) / WORK_RATE, 3),
                      "duration_s": round(frames / WORK_RATE, 3), "source_name": os.path.basename(item.rel)[:120], "source_sha256": item.sha256})
        position = before + frames
    writer.close()
    if not clips:
        _move_aside(plan, take_id)                                    # type: ignore[arg-type]
        return None
    _patch_wav_header(store, take_id, position)
    seconds = position / WORK_RATE
    if with_text:
        reference, _used = _reference_text([c for c in clips if c["text"]])
        notes: Dict[str, Any] = {"schema": 1, "mode": "files", "source": plan.source_name[:60], "files_kind": plan.kind, "imported": now_iso(), "sample_rate": WORK_RATE, "gap_s": GAP_S,
                                 "clips": clips}
    else:
        reference = ""
        notes = {"schema": 1, "mode": "free", "source": plan.source_name[:60], "files_kind": plan.kind, "imported": now_iso(), "sample_rate": WORK_RATE,
                 "recording": {"duration_s": round(seconds, 3), "metrics": {}}, "proposed_segments": [], "clips": clips}
    store.write(take_id, "ack_clips.json", notes)
    store.update(take_id, status="finishing", error=None, reference_text=reference)
    result.clips += len(clips)
    return Created(session=take_id, take_id=take_id, seconds=seconds)


# ---------------------------------------------------------------- the command

def _hms(seconds: float) -> str:
    m, s = divmod(int(round(seconds)), 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def print_plan(plan: Plan, dry_run: bool) -> None:
    print(f"\nFolder: {plan.source_name}  ({plan.kind})" + (f"  table: {plan.table}" if plan.table else ""))
    print(f"  Found {len(plan.items)} audio file(s): {len(plan.to_import)} to add ({_hms(plan.seconds_new)}), {plan.count('already')} already added, "
          f"{plan.count('duplicate')} repeated in this folder, {plan.count('unusable')} that cannot be used.")
    if plan.kind != "audio":
        print(f"  {plan.with_text} of the files to add come with a sentence.")
    for problem in plan.problems[:20]:
        print(f"  Note: {problem.code} {problem.what}".rstrip())
    if len(plan.problems) > 20:
        print(f"  And {len(plan.problems) - 20} more notes.")
    if plan.to_import:
        print(f"\n{'Would add' if dry_run else 'Will add'} {len(_batches(plan.to_import))} recording(s) to {plan.takes_dir}.")
        print(f"Needs about {plan.need_mb:.0f} MB; {plan.free_mb:.0f} MB is free." + ("" if plan.enough_room else "  THAT IS NOT ENOUGH: free some space first."))
    else:
        print("\nNothing new to add.")
    warning = sync_warning(plan.output, "Your recordings folder")
    if warning:
        print("\nNote: " + warning)
    print()


def main(argv: Optional[List[str]] = None) -> int:
    with private_umask():
        return _main(argv)


def _main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="freeform_studio.files_import", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source", help="the folder (or a .zip of it)")
    ap.add_argument("--kind", required=True, choices=KINDS, help="where the sentences are: pairs (a .txt beside each file), table (one metadata.csv) or audio (none)")
    ap.add_argument("--table", default="", help="the table's name, when the folder has more than one (kind table)")
    ap.add_argument("--output", default="~/piper-recording-studio/output", help="the recordings folder")
    ap.add_argument("--code", default=LANGUAGE)
    ap.add_argument("--dry-run", action="store_true", help="look and show what would be added; write nothing")
    ap.add_argument("--yes", action="store_true", help="don't ask before writing")
    args = ap.parse_args(argv)
    output = Path(args.output).expanduser()
    try:
        print("Looking at the folder ...")
        plan = make_plan(Path(args.source), args.kind, output, args.code, args.table)
        print_plan(plan, args.dry_run)
        if args.dry_run or not plan.to_import:
            return 0
        if not args.yes:
            if not sys.stdin.isatty():
                print("Not at a terminal, so it won't write without being told to: add --yes (or use --dry-run to look).\n", file=sys.stderr)
                return 2
            if input("Add these recordings? [y/N] ").strip().lower() not in ("y", "yes"):
                print("Nothing written.\n")
                return 0
        result = apply_import(plan, progress=print)
    except ImportProblem as err:
        print(f"\nCan't continue: {err}\n", file=sys.stderr)
        return 2
    print(f"\nAdded {result.clips} file(s) as {len(result.created)} recording(s) to {plan.takes_dir}.")
    for skipped in result.skipped:
        print(f"  Left out: {skipped.rel} ({skipped.reason})")
    print("Next: run `python -m freeform_studio.process` (or start Freeform Studio) so the PC listens and writes what it hears. Your folder was not changed.\n")
    return 0 if not result.skipped else 1


if __name__ == "__main__":
    sys.exit(main())
