# SPDX-License-Identifier: GPL-3.0-or-later
"""Preflight: what this computer is, and whether the guided setup can go ahead.

Everything here is a decision made from facts that a `System` supplies (core/system.py), so it is tested with captured output and needs
no GPU, no Windows and no display. Words never appear in this file: a check carries a status, a text key and plain values, and the
screens (and the terminal prompt) turn those into sentences from the text catalog.

A check is OK, INFO (worth knowing), WARN (the person can go on) or BLOCK (setup cannot go on). **No GPU is a state, not an error** (plan
decision D4): it is a WARN and `PreflightReport.gpu.state` says NONE, so recording, review and dataset export still work.

Numbers marked PROVISIONAL are guesses until the spike on a real GPU (plan task VS-0.2) measures them.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Dict, List, Mapping, Optional, Sequence, Tuple, Union

from .system import System

# ---------------------------------------------------------------- limits

MIN_PYTHON = (3, 10)                     # Ubuntu 22.04's system Python
SUPPORTED_UBUNTU = (("ubuntu", "22.04"), ("ubuntu", "24.04"))     # plan decision D8
GPU_MIN_MIB = 7900                       # PROVISIONAL. "An 8 GB card": the card reports 8188 or 8192 MiB, never exactly 8000
RAM_WARN_MIB = 7000                      # PROVISIONAL. An 8 GB computer reports about 7,500 to 7,900 MiB
WSL_NVIDIA_SMI = "/usr/lib/wsl/lib/nvidia-smi"      # where WSL puts it when the Windows driver supports the GPU


class Status(Enum):
    OK = "ok"
    INFO = "info"
    WARN = "warn"
    BLOCK = "block"


class Platform(Enum):
    NATIVE = "native"
    WSL2 = "wsl2"
    WSL1 = "wsl1"


class GpuState(Enum):
    OK = "ok"                # an NVIDIA GPU with enough memory
    SMALL = "small"          # an NVIDIA GPU below the verified size: unverified, not refused (P8)
    UNKNOWN = "unknown"      # a GPU whose memory could not be read
    NONE = "none"            # no NVIDIA GPU, or no working driver for it
    ERROR = "error"          # nvidia-smi ran and reported a failure (driver and library out of step, for example)


Value = Union[str, int, float]


@dataclass(frozen=True)
class Check:
    id: str
    status: Status
    key: str                                      # text catalog key
    args: Dict[str, Value] = field(default_factory=dict)


@dataclass(frozen=True)
class OsInfo:
    id: str = ""
    version_id: str = ""
    name: str = ""
    id_like: Tuple[str, ...] = ()


@dataclass(frozen=True)
class Gpu:
    name: str
    memory_mib: Optional[int]
    driver: str


@dataclass(frozen=True)
class GpuReport:
    state: GpuState
    gpus: Tuple[Gpu, ...] = ()
    error: str = ""                               # the first line nvidia-smi said, only when state is ERROR

    @property
    def best(self) -> Optional[Gpu]:
        known = [g for g in self.gpus if g.memory_mib is not None]
        return max(known, key=lambda g: g.memory_mib or 0) if known else (self.gpus[0] if self.gpus else None)


# ---------------------------------------------------------------- parsers (pure)

def parse_os_release(text: Optional[str]) -> OsInfo:
    """/etc/os-release: KEY=value lines, values optionally quoted, comments and blank lines allowed."""
    values: Dict[str, str] = {}
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        values[key.strip()] = value
    return OsInfo(id=values.get("ID", "").lower(), version_id=values.get("VERSION_ID", ""), name=values.get("PRETTY_NAME", values.get("NAME", "")),
                  id_like=tuple(values.get("ID_LIKE", "").lower().split()))


def is_supported_os(info: OsInfo) -> bool:
    return (info.id, info.version_id) in SUPPORTED_UBUNTU


def detect_platform(proc_version: Optional[str], environ: Mapping[str, str]) -> Platform:
    """WSL 2 runs a real Linux kernel ("...-microsoft-standard-WSL2"); WSL 1 translates calls ("4.4.0-19041-Microsoft") and has no GPU or WSLg."""
    text = (proc_version or "").lower()
    if "microsoft" in text:
        return Platform.WSL2 if ("wsl2" in text or "microsoft-standard" in text) else Platform.WSL1
    if environ.get("WSL_DISTRO_NAME") or environ.get("WSL_INTEROP"):
        return Platform.WSL2          # no readable kernel string, but WSL says it is there; WSL 1 is the old case and shows in the kernel string
    return Platform.NATIVE


def parse_nvidia_smi(returncode: int, stdout: str, stderr: str = "") -> GpuReport:
    """Output of: nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader,nounits"""
    if returncode != 0:
        first = next((ln.strip() for ln in (stdout + "\n" + stderr).splitlines() if ln.strip()), "")
        return GpuReport(GpuState.ERROR, error=first[:200])
    gpus: List[Gpu] = []
    for line in stdout.splitlines():
        if not line.strip():
            continue
        parts = [p.strip() for p in line.rsplit(",", 2)]
        if len(parts) != 3 or not parts[0]:
            continue
        digits = re.fullmatch(r"\d+", parts[1])
        gpus.append(Gpu(parts[0], int(parts[1]) if digits else None, parts[2]))
    if not gpus:
        return GpuReport(GpuState.NONE)
    return GpuReport(classify_gpus(gpus), tuple(gpus))


def classify_gpus(gpus: Sequence[Gpu]) -> GpuState:
    sizes = [g.memory_mib for g in gpus if g.memory_mib is not None]
    if not sizes:
        return GpuState.UNKNOWN
    return GpuState.OK if max(sizes) >= GPU_MIN_MIB else GpuState.SMALL


def parse_meminfo_mib(text: Optional[str]) -> Optional[int]:
    match = re.search(r"^MemTotal:\s+(\d+)\s*kB", text or "", re.MULTILINE)
    return int(match.group(1)) // 1024 if match else None


def parse_dpkg_status(stdout: str) -> set:
    """Lines of "<package> <status>" from: dpkg-query -W -f='${Package} ${db:Status-Status}\\n' <packages>"""
    installed = set()
    for line in stdout.splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[1] == "installed":
            installed.add(parts[0])
    return installed


# ---------------------------------------------------------------- what the setup needs installed

@dataclass(frozen=True)
class Requirement:
    package: str                                  # the Ubuntu package that provides it
    why_key: str                                  # text catalog key: one plain line on why it is needed
    probe: Optional[Callable[[System], bool]] = None     # proof it is already there some other way (not from apt)


def _tool(*names: str) -> Callable[[System], bool]:
    return lambda s: all(s.which(n) for n in names)


def _python_runs(code: str) -> Callable[[System], bool]:
    def probe(system: System) -> bool:
        result = system.run([system.python_executable(), "-c", code])
        return bool(result and result.returncode == 0)
    return probe


REQUIREMENTS: Tuple[Requirement, ...] = (
    Requirement("python3-venv", "apt.why.python3_venv", _python_runs("import venv, ensurepip")),
    Requirement("python3-dev", "apt.why.python3_dev"),
    Requirement("build-essential", "apt.why.build_essential", _tool("gcc", "g++", "make")),
    Requirement("cmake", "apt.why.cmake", _tool("cmake")),
    Requirement("ninja-build", "apt.why.ninja_build", _tool("ninja")),
    Requirement("git", "apt.why.git", _tool("git")),
    Requirement("ffmpeg", "apt.why.ffmpeg", _tool("ffmpeg", "ffprobe")),
    Requirement("python3-gi", "apt.why.python3_gi", _python_runs("import gi")),
    Requirement("gir1.2-gtk-4.0", "apt.why.gtk4", _python_runs("import gi; gi.require_version('Gtk', '4.0')")),
)


def missing_requirements(system: System) -> Tuple[Requirement, ...]:
    """The packages still to install. One dpkg query for all of them; a probe that proves the thing is there by another route wins over dpkg."""
    result = system.run(["dpkg-query", "-W", "-f=${Package} ${db:Status-Status}\\n"] + [r.package for r in REQUIREMENTS])
    installed = parse_dpkg_status(result.stdout) if result else set()
    missing = []
    for req in REQUIREMENTS:
        if req.probe is not None and req.probe(system):
            continue
        if req.package not in installed:
            missing.append(req)
    return tuple(missing)


# ---------------------------------------------------------------- the report

@dataclass(frozen=True)
class PreflightReport:
    checks: Tuple[Check, ...]
    os: OsInfo
    platform: Platform
    gpu: GpuReport
    ram_mib: Optional[int]
    disks: Dict[str, Tuple[int, int]]                       # path -> (total bytes, free bytes)
    missing: Tuple[Requirement, ...]

    def with_status(self, status: Status) -> Tuple[Check, ...]:
        return tuple(c for c in self.checks if c.status is status)

    @property
    def blockers(self) -> Tuple[Check, ...]:
        return self.with_status(Status.BLOCK)

    @property
    def warnings(self) -> Tuple[Check, ...]:
        return self.with_status(Status.WARN)

    @property
    def can_continue(self) -> bool:
        return not self.blockers

    def check(self, check_id: str) -> Check:
        return next(c for c in self.checks if c.id == check_id)


def run_preflight(system: System, measure: Sequence[str] = ()) -> PreflightReport:
    """Read the facts and judge them. `measure` are extra folders whose free space is wanted (the project folder, a scratch drive)."""
    environ = system.environ()
    os_info = parse_os_release(system.read_text("/etc/os-release"))
    platform = detect_platform(system.read_text("/proc/version"), environ)
    home = system.home()
    checks: List[Check] = []

    def add(check_id: str, status: Status, key: str, **args: Value) -> None:
        checks.append(Check(check_id, status, key, dict(args)))

    # run as the person, not as root: a root-owned environment breaks the trainer's build (the guide's "never use sudo" rule)
    if system.geteuid() == 0:
        add("root", Status.BLOCK, "preflight.root.blocked")
    else:
        add("root", Status.OK, "preflight.root.ok")

    # which Ubuntu
    if not os_info.id:
        add("os", Status.WARN, "preflight.os.unknown")
    elif is_supported_os(os_info):
        add("os", Status.OK, "preflight.os.supported", name=os_info.name)
    else:
        add("os", Status.WARN, "preflight.os.untested", name=os_info.name or os_info.id)

    # native or WSL
    if platform is Platform.WSL1:
        add("platform", Status.BLOCK, "preflight.platform.wsl1")
    elif platform is Platform.WSL2:
        add("platform", Status.OK, "preflight.platform.wsl2")
    else:
        add("platform", Status.OK, "preflight.platform.native")

    # a desktop to open the window on
    if environ.get("DISPLAY") or environ.get("WAYLAND_DISPLAY"):
        add("display", Status.OK, "preflight.display.ok")
    elif platform is Platform.NATIVE:
        add("display", Status.BLOCK, "preflight.display.none")
    else:
        add("display", Status.BLOCK, "preflight.display.none_wsl", wslg_folder=1 if system.exists("/mnt/wslg") else 0)

    # Python
    version = system.python_version()
    if version >= MIN_PYTHON:
        add("python", Status.OK, "preflight.python.ok", version="%d.%d.%d" % version)
    else:
        add("python", Status.BLOCK, "preflight.python.old", version="%d.%d.%d" % version, needed="%d.%d" % MIN_PYTHON)

    # apt, which the setup uses for the few system packages
    if system.which("apt-get"):
        add("apt", Status.OK, "preflight.apt.ok")
    else:
        add("apt", Status.BLOCK, "preflight.apt.missing")

    missing = missing_requirements(system)
    if not missing:
        add("packages", Status.OK, "preflight.packages.ok")
    else:
        add("packages", Status.INFO, "preflight.packages.missing", count=len(missing))
        if system.geteuid() != 0 and not system.which("sudo"):
            add("sudo", Status.BLOCK, "preflight.sudo.missing")

    # the GPU (a state, not an error: D4)
    smi = system.which("nvidia-smi") or (WSL_NVIDIA_SMI if system.exists(WSL_NVIDIA_SMI) else None)
    if smi is None:
        gpu = GpuReport(GpuState.NONE)
    else:
        result = system.run([smi, "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader,nounits"])
        gpu = GpuReport(GpuState.NONE) if result is None else parse_nvidia_smi(result.returncode, result.stdout, result.stderr)
    best = gpu.best
    if gpu.state is GpuState.OK:
        add("gpu", Status.OK, "preflight.gpu.ok", name=best.name if best else "", memory_mib=(best.memory_mib or 0) if best else 0)
    elif gpu.state is GpuState.SMALL:
        add("gpu", Status.WARN, "preflight.gpu.small", name=best.name if best else "", memory_mib=(best.memory_mib or 0) if best else 0)
    elif gpu.state is GpuState.UNKNOWN:
        add("gpu", Status.WARN, "preflight.gpu.unknown", name=best.name if best else "")
    elif gpu.state is GpuState.ERROR:
        add("gpu", Status.WARN, "preflight.gpu.error")
    else:
        add("gpu", Status.WARN, "preflight.gpu.none")

    # memory
    ram = parse_meminfo_mib(system.read_text("/proc/meminfo"))
    if ram is None:
        add("ram", Status.INFO, "preflight.ram.unknown")
    elif ram < RAM_WARN_MIB:
        add("ram", Status.WARN, "preflight.ram.low", memory_mib=ram)
    else:
        add("ram", Status.OK, "preflight.ram.ok", memory_mib=ram)

    # a home folder on the Windows drive is slow and has loose permissions
    if home == "/mnt" or home.startswith("/mnt/"):
        add("home", Status.WARN, "preflight.home.on_windows_drive")

    # free space: facts only, judged against the budget later (VS-1.10)
    disks: Dict[str, Tuple[int, int]] = {}
    wanted = [home] + list(measure)
    if platform is Platform.WSL2 and system.exists("/mnt/c"):
        wanted.append("/mnt/c")        # the Windows system drive: the virtual disk the distro lives in normally sits there
    for path in wanted:
        free = system.disk_free(path)
        if free is not None:
            disks[path] = free
    add("disk", Status.INFO, "preflight.disk.facts", folders=len(disks))

    return PreflightReport(tuple(checks), os_info, platform, gpu, ram, disks, missing)
