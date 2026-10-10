# SPDX-License-Identifier: GPL-3.0-or-later
"""Where scratch may live (plan decision D24): the rules for a place the person chooses, and the checks before every job.

Scratch holds the dataset, the caches and older checkpoints: the voice in another form, so it follows the privacy rules the recordings do.
The person chooses a *place*; the tool makes its own folder inside it, `<place>/ack-voice-scratch/<project id>/`, with a marker file in it.
Everything that decides is pure and takes captured facts (a mount table, `lsblk` output, what a path resolves to), so it is tested without
a USB stick. A place is ACCEPTed, ACCEPTed WITH WARNINGS, or REFUSEd, and every reason is a short code the screens turn into a sentence.

Nothing falls back to another place on its own, and a job never starts unless the marker proves this really is the person's scratch (an
unplugged USB drive leaves an empty folder on the main disk, and writing into that would quietly fill it).
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import PurePosixPath
from typing import Callable, Dict, FrozenSet, List, Optional, Protocol, Sequence, Tuple

from .system import System

SCRATCH_DIRNAME = "ack-voice-scratch"
MARKER_NAME = ".ack-voice-scratch"
MARKER_SCHEMA = 1
PROJECT_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")

SYSTEM_PREFIXES = ("/proc", "/sys", "/dev", "/run", "/boot", "/etc", "/usr", "/bin", "/sbin", "/lib", "/lib32", "/lib64", "/libx32", "/snap",
                   "/var", "/root")
EXTERNAL_PREFIXES = ("/media/", "/run/media/", "/mnt/")        # where an external drive is mounted: a folder here on the main disk means "not mounted"

GOOD_FS = frozenset({"ext2", "ext3", "ext4", "xfs", "btrfs", "f2fs", "zfs", "jfs"})
PERMISSIVE_FS = frozenset({"ntfs", "ntfs3", "fuseblk", "exfat", "fuse.exfat"})
FAT_FS = frozenset({"vfat", "msdos", "fat", "fat32"})
NETWORK_FS = frozenset({"nfs", "nfs4", "cifs", "smb3", "smbfs", "sshfs", "fuse.sshfs", "davfs", "fuse.davfs", "ceph", "glusterfs", "fuse.glusterfs",
                        "afs", "lustre", "fuse.s3fs", "fuse.rclone", "fuse.gcsfuse"})
MEMORY_FS = frozenset({"tmpfs", "ramfs", "devtmpfs"})
WSL_WINDOWS_FS = frozenset({"9p", "drvfs"})

REFUSAL_CODES = ("not_absolute", "root_folder", "system_folder", "not_a_folder", "cannot_create", "not_writable", "read_only", "fs_fat", "fs_network", "fs_memory",
                 "synced_folder", "not_mounted", "inside_project", "inside_other_project", "marker_other_project", "marker_damaged", "not_empty_unmarked",
                 "bad_project_id")
WARNING_CODES = ("fs_permissive", "perms_loose", "windows_drive", "fs_unknown", "removable", "same_device_as_project")
SPEED_CODES = ("slow_write", "slow_read", "slow_small_files")           # each has words in the text catalog

SLOW_WRITE_MBPS = 30.0              # PROVISIONAL (plan task VS-0.2 sets the real ones): about a USB 2.0 stick
SLOW_READ_MBPS = 30.0
SLOW_SMALL_FILES_PER_S = 200.0      # the training cache is many small files, which is what a Windows drive seen from WSL is slow at


class Verdict(Enum):
    ACCEPT = "accept"
    WARN = "warn"
    REFUSE = "refuse"


class FsGroup(Enum):
    GOOD = "good"
    PERMISSIVE = "permissive"
    WINDOWS = "windows"             # a Windows drive seen from WSL
    FAT = "fat"
    NETWORK = "network"
    MEMORY = "memory"
    UNKNOWN = "unknown"


# ---------------------------------------------------------------- mounts and filesystems

@dataclass(frozen=True)
class Mount:
    device: str
    point: str
    fstype: str
    options: FrozenSet[str]


def _unescape(field_text: str) -> str:
    return re.sub(r"\\([0-7]{3})", lambda m: chr(int(m.group(1), 8)), field_text)


def parse_mounts(text: Optional[str]) -> List[Mount]:
    """/proc/mounts: device, mount point, type, options, two numbers; spaces in a name are written \\040."""
    mounts = []
    for line in (text or "").splitlines():
        parts = line.split()
        if len(parts) < 4:
            continue
        mounts.append(Mount(_unescape(parts[0]), _unescape(parts[1]), parts[2].lower(), frozenset(parts[3].split(","))))
    return mounts


def _under(path: str, base: str) -> bool:
    path, base = path.rstrip("/") or "/", base.rstrip("/") or "/"
    return path == base or base == "/" or path.startswith(base + "/")


def mount_for(path: str, mounts: Sequence[Mount]) -> Optional[Mount]:
    """The mount a path lives on: the deepest mount point above it; when two share a point the later one covers the earlier (as the kernel does)."""
    best: Optional[Mount] = None
    for m in mounts:
        if _under(path, m.point) and (best is None or len(m.point.rstrip("/")) >= len(best.point.rstrip("/"))):
            best = m
    return best


def fs_group(fstype: str, *, wsl: bool) -> FsGroup:
    name = fstype.lower()
    if name in WSL_WINDOWS_FS:
        return FsGroup.WINDOWS if wsl else FsGroup.NETWORK        # off WSL, 9p is a share from a virtual machine
    if name in GOOD_FS:
        return FsGroup.GOOD
    if name in PERMISSIVE_FS:
        return FsGroup.PERMISSIVE
    if name in FAT_FS:
        return FsGroup.FAT
    if name in NETWORK_FS:
        return FsGroup.NETWORK
    if name in MEMORY_FS:
        return FsGroup.MEMORY
    return FsGroup.UNKNOWN


def parse_lsblk_removable(text: Optional[str]) -> Optional[Dict[str, bool]]:
    """From `lsblk -J -o NAME,MOUNTPOINTS,FSTYPE,RM,TRAN,TYPE`: mount point -> is it on a removable or USB drive. None if the output cannot be read."""
    try:
        data = json.loads(text or "")
        devices = data["blockdevices"]
    except (ValueError, KeyError, TypeError):
        return None
    result: Dict[str, bool] = {}

    def truthy(value) -> bool:
        return value is True or str(value).strip() in {"1", "true", "True"}

    def walk(node, inherited: bool) -> None:
        if not isinstance(node, dict):
            return
        removable = inherited or truthy(node.get("rm")) or str(node.get("tran") or "").lower() == "usb"
        points = list(node.get("mountpoints") or []) + ([node["mountpoint"]] if node.get("mountpoint") else [])
        for point in points:
            if isinstance(point, str) and point:
                result[point] = removable
        for child in node.get("children") or []:
            walk(child, removable)
    for device in devices if isinstance(devices, list) else []:
        walk(device, False)
    return result


# ---------------------------------------------------------------- the marker

class MarkerState(Enum):
    OK = "ok"
    MISSING = "missing"
    OTHER_PROJECT = "other_project"
    DAMAGED = "damaged"


def marker_text(project_id: str) -> str:
    return json.dumps({"schema": MARKER_SCHEMA, "project": project_id}) + "\n"


def check_marker(text: Optional[str], project_id: str) -> MarkerState:
    if text is None:
        return MarkerState.MISSING
    try:
        data = json.loads(text)
        if data["schema"] != MARKER_SCHEMA or not isinstance(data["project"], str):
            return MarkerState.DAMAGED
    except (ValueError, KeyError, TypeError, RecursionError):        # it was read from another drive; one nested far too deep is damaged too
        return MarkerState.DAMAGED
    return MarkerState.OK if data["project"] == project_id else MarkerState.OTHER_PROJECT


def scratch_dir_for(place: str, project_id: str) -> str:
    if not PROJECT_ID.match(project_id):
        raise ValueError("unsafe project id")
    return str(PurePosixPath(place) / SCRATCH_DIRNAME / project_id)


def create_scratch(place: str, project_id: str) -> str:
    """Make `<place>/ack-voice-scratch/<project id>/` with its marker, and return that folder. The place must already be a folder (the tool makes
    its own folder inside it, never the place itself). Safe to repeat: an existing folder with this project's marker is reused; one with any other
    marker, or one that is not empty and has none, is refused. Raises ValueError for a name or place that is not usable and OSError when writing fails."""
    if not PROJECT_ID.match(project_id) or not place.startswith("/") or not os.path.isdir(place):
        raise ValueError("not a usable place or project name")
    folder = scratch_dir_for(place, project_id)
    parent = os.path.dirname(folder)
    for path in (parent, folder):
        try:
            os.mkdir(path, 0o700)
        except FileExistsError:
            pass
    marker_path = folder + "/" + MARKER_NAME
    try:
        with open(marker_path, encoding="utf-8") as handle:
            state = check_marker(handle.read(), project_id)
    except FileNotFoundError:
        if os.listdir(folder):
            raise ValueError("a folder with other files in it and no marker is already there")
        fd = os.open(marker_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(marker_text(project_id))
        return folder
    if state is not MarkerState.OK:
        raise ValueError("a folder with another marker is already there")
    return folder


def may_start_job(marker: MarkerState) -> bool:
    """Every job start: only a marker that names this project proves the folder is the person's own scratch and not an empty mount point."""
    return marker is MarkerState.OK


# ---------------------------------------------------------------- judging a place

@dataclass(frozen=True)
class PlaceFacts:
    given: str                              # what the person chose, as typed or picked
    real: str                               # with symbolic links resolved
    project_id: str
    project_root: str
    home: str = "/home/user"
    wsl: bool = False
    exists: bool = False
    is_dir: bool = False
    writable: bool = False
    parent_is_dir: bool = False
    parent_writable: bool = False
    device: Optional[int] = None            # the filesystem of the nearest part of the place that exists
    project_device: Optional[int] = None
    mounts_text: Optional[str] = None
    lsblk_json: Optional[str] = None
    other_project_roots: Tuple[str, ...] = ()
    sync_reason: Optional[str] = None       # why the place looks cloud-synced, if it does (freeform_studio.privacy.sync_risk)
    scratch_exists: bool = False            # <place>/ack-voice-scratch/<id> is already there
    scratch_nonempty: bool = False
    marker: Optional[str] = None            # the text of its marker file, if it has one


@dataclass(frozen=True)
class Assessment:
    verdict: Verdict
    refusals: Tuple[str, ...]
    warnings: Tuple[str, ...]
    scratch_dir: str
    fstype: str = ""
    fs_group: FsGroup = FsGroup.UNKNOWN
    mount_point: str = ""
    removable: Optional[bool] = None
    reusing: bool = False                   # an earlier scratch of this same project is there and will be picked up again


def assess_scratch(f: PlaceFacts) -> Assessment:
    refuse: List[str] = []
    warn: List[str] = []
    real = f.real.rstrip("/") or "/"
    absolute = f.real.startswith("/") and f.given.strip().startswith(("/", "~")) and not any(ord(c) < 32 for c in f.given)
    if not absolute:
        refuse.append("not_absolute")
    scratch = scratch_dir_for(real, f.project_id) if (absolute and PROJECT_ID.match(f.project_id)) else ""
    if not PROJECT_ID.match(f.project_id):
        refuse.append("bad_project_id")                 # nothing may be built from a name that is not a safe folder name

    external = real.startswith("/run/media/") or any(real.startswith(p) for p in EXTERNAL_PREFIXES)
    if absolute:
        if real == "/":
            refuse.append("root_folder")
        elif any(_under(real, p) for p in SYSTEM_PREFIXES) and not real.startswith("/run/media/"):
            refuse.append("system_folder")
        if f.exists and not f.is_dir:
            refuse.append("not_a_folder")
        elif not f.exists and not (f.parent_is_dir and f.parent_writable):
            refuse.append("cannot_create")
        elif f.exists and not f.writable:
            refuse.append("not_writable")

    mounts = parse_mounts(f.mounts_text)
    mount = mount_for(real, mounts) if absolute else None
    group, fstype = FsGroup.UNKNOWN, ""
    if mount is not None:
        fstype, group = mount.fstype, fs_group(mount.fstype, wsl=f.wsl)
        if "ro" in mount.options:
            refuse.append("read_only")
        if group is FsGroup.FAT:
            refuse.append("fs_fat")
        elif group is FsGroup.NETWORK:
            refuse.append("fs_network")
        elif group is FsGroup.MEMORY:
            refuse.append("fs_memory")
        elif group is FsGroup.PERMISSIVE:
            warn += ["fs_permissive", "perms_loose"]
        elif group is FsGroup.WINDOWS:
            warn += ["windows_drive", "perms_loose"]
        elif group is FsGroup.UNKNOWN:
            warn.append("fs_unknown")
        if mount.point == "/" and external and absolute:
            refuse.append("not_mounted")           # under /media, /mnt ... but on the main disk: the drive that belongs here is not plugged in
    elif absolute:
        warn.append("fs_unknown")

    if f.sync_reason:
        refuse.append("synced_folder")

    if absolute and scratch:
        if f.project_root and _under(scratch, f.project_root):          # the default place, <project>/scratch, is not judged here; a chosen one cannot be inside it
            refuse.append("inside_project")
        for other in f.other_project_roots:
            if other and _under(real, other):
                refuse.append("inside_other_project")

    state = check_marker(f.marker, f.project_id) if f.scratch_exists else MarkerState.MISSING
    reusing = False
    if f.scratch_exists:
        if state is MarkerState.OK:
            reusing = True
        elif state is MarkerState.OTHER_PROJECT:
            refuse.append("marker_other_project")
        elif state is MarkerState.DAMAGED:
            refuse.append("marker_damaged")
        elif f.scratch_nonempty:
            refuse.append("not_empty_unmarked")

    removable: Optional[bool] = None
    table = parse_lsblk_removable(f.lsblk_json)
    if table is not None and mount is not None:
        removable = table.get(mount.point)
        if removable:
            warn.append("removable")

    if f.device is not None and f.project_device is not None and f.device == f.project_device and "not_mounted" not in refuse:
        warn.append("same_device_as_project")

    refusals = tuple(dict.fromkeys(refuse))
    warnings = tuple(dict.fromkeys(warn))
    verdict = Verdict.REFUSE if refusals else (Verdict.WARN if warnings else Verdict.ACCEPT)
    return Assessment(verdict, refusals, warnings, scratch, fstype, group, mount.point if mount else "", removable, reusing)


def gather_place_facts(system: System, given: str, *, project_id: str, project_root: str, other_project_roots: Sequence[str] = (), wsl: bool = False,
                       project_device: Optional[int] = None) -> PlaceFacts:
    """Read the facts about a place from the computer. Looks, never writes."""
    from freeform_studio.privacy import sync_risk       # stdlib only; the two tools travel together in one repository

    home = system.home()
    typed = given.strip()
    expanded = home + typed[1:] if typed == "~" or typed.startswith("~/") else typed
    real = system.realpath(expanded) if expanded else ""
    nearest = real
    while nearest and nearest != "/" and not system.is_dir(nearest):
        nearest = os.path.dirname(nearest)
    exists = bool(real) and system.exists(real)
    is_dir = exists and system.is_dir(real)
    parent = os.path.dirname(real) if real else ""
    scratch = scratch_dir_for(real, project_id) if (real.startswith("/") and PROJECT_ID.match(project_id)) else ""
    marker = system.read_text(scratch + "/" + MARKER_NAME) if scratch else None
    lsblk = system.run(["lsblk", "-J", "-o", "NAME,MOUNTPOINTS,FSTYPE,RM,TRAN,TYPE"])
    return PlaceFacts(
        given=given, real=real, project_id=project_id, project_root=project_root, home=home, wsl=wsl, exists=exists, is_dir=is_dir,
        writable=is_dir and system.writable(real), parent_is_dir=bool(parent) and system.is_dir(parent), parent_writable=bool(parent) and system.writable(parent),
        device=system.device_of(nearest) if nearest else None, project_device=project_device, mounts_text=system.read_text("/proc/mounts"),
        lsblk_json=lsblk.stdout if lsblk and lsblk.returncode == 0 else None, other_project_roots=tuple(other_project_roots),
        sync_reason=sync_risk(real) if real else None, scratch_exists=bool(scratch) and system.is_dir(scratch),
        scratch_nonempty=bool(scratch) and bool(system.listdir(scratch)),
        marker=marker)


# ---------------------------------------------------------------- speed

class Disk(Protocol):
    def write(self, name: str, nbytes: int) -> None: ...
    def read(self, name: str) -> int: ...
    def remove(self, name: str) -> None: ...


@dataclass(frozen=True)
class Speed:
    write_mbps: float
    read_mbps: float
    small_files_per_s: float


def measure_speed(disk: Disk, clock: Callable[[], float], big_bytes: int = 64 * 2**20, small_files: int = 100, small_bytes: int = 64 * 2**10) -> Speed:
    """One big file written and read back, then many small ones (what the training cache is made of). Everything it writes it removes."""
    def span(action: Callable[[], None]) -> float:
        start = clock()
        action()
        return max(clock() - start, 1e-9)
    mb = big_bytes / 1e6
    write_s = span(lambda: disk.write("speed-big", big_bytes))
    read_s = span(lambda: disk.read("speed-big"))
    disk.remove("speed-big")

    def small() -> None:
        for i in range(small_files):
            disk.write("speed-small-%d" % i, small_bytes)
        for i in range(small_files):
            disk.read("speed-small-%d" % i)
    small_s = span(small)
    for i in range(small_files):
        disk.remove("speed-small-%d" % i)
    return Speed(mb / write_s, mb / read_s, small_files / small_s)


def judge_speed(speed: Speed) -> Tuple[str, ...]:
    codes = []
    if speed.write_mbps < SLOW_WRITE_MBPS:
        codes.append("slow_write")
    if speed.read_mbps < SLOW_READ_MBPS:
        codes.append("slow_read")
    if speed.small_files_per_s < SLOW_SMALL_FILES_PER_S:
        codes.append("slow_small_files")
    return tuple(codes)


class RealDisk:
    """Writes and reads real files in one folder, flushing each to the disk so the cache of memory cannot flatter the result."""

    def __init__(self, folder: str):
        self.folder = folder
        self._block = os.urandom(1 << 20)           # not zeros: some filesystems compress those

    def _path(self, name: str) -> str:
        return os.path.join(self.folder, name)

    def write(self, name: str, nbytes: int) -> None:
        fd = os.open(self._path(name), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "wb") as handle:
            left = nbytes
            while left > 0:
                chunk = self._block[:min(left, len(self._block))]
                handle.write(chunk)
                left -= len(chunk)
            handle.flush()
            os.fsync(handle.fileno())

    def read(self, name: str) -> int:
        total = 0
        with open(self._path(name), "rb") as handle:
            for block in iter(lambda: handle.read(1 << 20), b""):
                total += len(block)
        return total

    def remove(self, name: str) -> None:
        try:
            os.unlink(self._path(name))
        except OSError:
            pass
