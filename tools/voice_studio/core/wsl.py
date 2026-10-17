# SPDX-License-Identifier: GPL-3.0-or-later
"""Help for the Windows side of Ubuntu under WSL (plan task VS-3.6, decision D17, choices P26; findings F3 and F4).

Two things about Ubuntu in Windows get in the way of this tool, and both are settings in one Windows file, `.wslconfig`, in the person's Windows home folder:

* **A phone cannot reach Ubuntu** in WSL's default networking (the address Ubuntu sees is a private one inside Windows). `networkingMode=mirrored` in `[wsl2]` makes Ubuntu share the
  Windows network, and Windows' firewall for WSL (the Hyper-V firewall) then has to allow the port the phone will use.
* **Ubuntu stops about a minute after the last window or terminal closes**, taking a running round with it (F3). `instanceIdleTimeout=-1` in `[general]` stops that (it worked on the
  developer's machine, WSL 2.7.14.0).

What this module keeps to, and what the tests hold it to:
* It looks first and changes nothing. The file is read through the Windows drive that WSL mounts (`/mnt/c/...`); asking Windows for the folder's name (a Windows program started from
  Ubuntu) is tried first but is never needed, because that does not always work (F4): without it the only user folder is used, or the person names one.
* An edit is a change of one value in one section. Everything else in the file, its comments, its order and its line endings, is kept. A file that is not plain text, or that sets the same
  value twice, is refused rather than guessed at.
* A file that is there is copied first to a name that does not exist yet (`.wslconfig.bak`, or one with the time), the new text goes to a temporary file and replaces the old one in one
  step, and the result is read back. An earlier copy is never replaced.
* Nothing here restarts WSL, runs a firewall command or changes anything on Windows beyond that one file. The commands for the firewall and for the restart are only given as text.
"""
from __future__ import annotations

import difflib
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional, Sequence, Tuple

from . import preflight
from .system import System

CONFIG_NAME = ".wslconfig"
SECTION_NETWORK, KEY_NETWORK, MIRRORED = "wsl2", "networkingMode", "mirrored"
SECTION_IDLE, KEY_IDLE, NEVER = "general", "instanceIdleTimeout", "-1"
HYPERV_VM_CREATOR = "{40E0AC32-46A5-438A-A0B2-2B479E8F2E90}"           # the number Microsoft gives for WSL's virtual machine in the Hyper-V firewall
FIREWALL_RULE = "ACK-Voice-Studio-send"
MIRRORED_MIN_BUILD = 22621                                              # Windows 11 version 22H2, the first that has mirrored networking
INTEROP_TIMEOUT_S = 10.0
KNOWN_CMD = "/mnt/c/Windows/System32/cmd.exe"                           # where Windows keeps it, for a computer whose WSL does not add Windows programs to the search path
SYSTEM_FOLDERS = frozenset({"public", "default", "default user", "all users", "defaultuser0", "wsiaccount"})        # a loose file such as desktop.ini is left out because only folders are looked at
ERROR_CODES = ("no_windows_home", "several_users", "no_such_user", "bad_text", "duplicate", "not_written")

IDLE_NEVER, IDLE_STOPS, IDLE_UNKNOWN = "never", "stops", "unknown"
INTEROP_WORKS, INTEROP_FAILED, INTEROP_MISSING = "works", "failed", "missing"
HOW_ASKED, HOW_ONLY, HOW_NAMED = "asked", "only", "named"

_SECTION = re.compile(r"^\s*\[([^\]]+)\]\s*\Z")
_ASSIGN = re.compile(r"^(\s*)([A-Za-z0-9_.-]+)(\s*=\s*)(.*?)\s*\Z")
_USER_NAME = re.compile(r'^[^\\/:*?"<>|\x00-\x1f]{1,64}\Z')
_WINDOWS_PATH = re.compile(r"^([A-Za-z]):\\([^\r\n\"<>|?*%]{1,200})\Z")
_BUILD = re.compile(r"\[Version (\d+)\.(\d+)\.(\d+)")


class WslError(Exception):
    def __init__(self, code: str, detail: str = ""):
        super().__init__(code)
        self.code = code
        self.detail = detail


# ---------------------------------------------------------------- reading and changing the text of .wslconfig

def _without_mark(text: str) -> str:
    return text[1:] if text.startswith("\ufeff") else text


def _split(text: str) -> Tuple[List[str], str, bool]:
    """(lines without their line ends, the line end the file uses, whether it ends with one)."""
    if "\x00" in text:
        raise WslError("bad_text")
    eol = "\r\n" if "\r\n" in text else "\n"
    lines = text.replace("\r\n", "\n").split("\n") if text else []
    final = bool(lines) and lines[-1] == ""
    if final:
        lines.pop()
    return lines, eol, final


def find(text: str, section: str, key: str) -> List[str]:
    """Every value the file gives `key` inside `[section]` (names compare without regard to case), in file order. A comment line, which begins with # or ;, gives nothing."""
    values: List[str] = []
    current = ""
    for line in _without_mark(text).split("\n"):                 # a comment line, which begins with # or ;, matches neither pattern, and the patterns take a trailing CR in their stride
        header = _SECTION.match(line)
        if header:
            current = header.group(1).strip().lower()
            continue
        assign = _ASSIGN.match(line)
        if assign and current == section.lower() and assign.group(2).lower() == key.lower():
            values.append(assign.group(4))
    return values


def with_setting(text: str, section: str, key: str, value: str) -> str:
    """`text` with `key` in `[section]` set to `value`: the value changed where the file already has the key, the key added to the section where the file has only the section, and the section
    added at the end where it has neither. The same text comes back when the value is already right. A file that sets the key twice is refused."""
    bom = text[:len(text) - len(_without_mark(text))]
    lines, eol, final = _split(_without_mark(text))
    if len(find(text, section, key)) > 1:
        raise WslError("duplicate", key)
    current, section_at, key_at, last_at = "", None, None, None
    for i, line in enumerate(lines):
        if line.lstrip().startswith(("#", ";")):
            continue
        header = _SECTION.match(line)
        if header:
            current = header.group(1).strip().lower()
            if current == section.lower():
                if section_at is not None:
                    raise WslError("duplicate", section)
                section_at = last_at = i
            continue
        if current == section.lower():
            if line.strip():
                last_at = i
            assign = _ASSIGN.match(line)
            if assign and assign.group(2).lower() == key.lower():
                key_at = i
    if key_at is not None:
        assign = _ASSIGN.match(lines[key_at])
        if assign.group(4).strip().lower() == value.lower():
            return text
        lines[key_at] = assign.group(1) + assign.group(2) + assign.group(3) + value
    elif section_at is not None:
        lines.insert(last_at + 1, "%s=%s" % (key, value))
    else:
        if lines and lines[-1].strip():
            lines.append("")
        lines.extend(["[%s]" % section, "%s=%s" % (key, value)])
        final = True
    return bom + eol.join(lines) + (eol if final else "")


def changes(old: str, new: str) -> List[str]:
    """The lines that differ, as a short listing: `- old` and `+ new` with a line of the file either side."""
    def lines(text: str) -> List[str]:
        parts = text.replace("\r\n", "\n").split("\n")
        return parts[:-1] if parts and parts[-1] == "" else parts            # the empty piece after the last line end is not a line
    shown = difflib.unified_diff(lines(old), lines(new), lineterm="", n=1)
    return [line for line in shown if not line.startswith(("---", "+++", "@@"))]


# ---------------------------------------------------------------- where the file is

@dataclass(frozen=True)
class WindowsHome:
    path: str                       # the person's Windows home folder as Ubuntu sees it, for example /mnt/c/Users/Anna
    how: str                        # HOW_ASKED (Windows told us), HOW_ONLY (the one user folder there is) or HOW_NAMED (the person named it)


def automount_root(system: System) -> str:
    """Where WSL puts the Windows drives: /mnt unless /etc/wsl.conf says otherwise."""
    text = system.read_text("/etc/wsl.conf") or ""
    section = ""
    for line in text.split("\n"):
        header = _SECTION.match(line)
        if header:
            section = header.group(1).strip().lower()
            continue
        assign = _ASSIGN.match(line)
        if assign and section == "automount" and assign.group(2).lower() == "root":
            root = assign.group(4).strip().strip('"').rstrip("/")
            if root.startswith("/") and ".." not in root.split("/"):
                return root
    return "/mnt"


def _cmd_program(system: System) -> Optional[str]:
    return system.which("cmd.exe") or (KNOWN_CMD if system.exists(KNOWN_CMD) else None)


def interop(system: System) -> Tuple[str, Optional[int]]:
    """(whether a Windows program can be started from Ubuntu now, the Windows build number when it told us). Asked at the moment it is needed, with a short time limit: it does not always work (F4)."""
    program = _cmd_program(system)
    if not program:
        return INTEROP_MISSING, None
    done = system.run([program, "/c", "ver"], timeout=INTEROP_TIMEOUT_S)
    if done is None or done.returncode != 0:
        return INTEROP_FAILED, None
    found = _BUILD.search(done.stdout)
    return INTEROP_WORKS, int(found.group(3)) if found else None


def _from_windows_path(path: str, root: str) -> Optional[str]:
    match = _WINDOWS_PATH.match(path.strip())
    if not match or ".." in match.group(2).split("\\"):
        return None
    return "%s/%s/%s" % (root, match.group(1).lower(), match.group(2).replace("\\", "/"))


def windows_home(system: System, *, asked: bool, named: Optional[str] = None) -> WindowsHome:
    """The Windows home folder. A name the person gave wins; then what Windows says (only when a Windows program can be started); then the one user folder on the C drive. Raises
    `no_such_user` for a name that is not a folder there, `several_users` (the names in the detail) when it cannot tell, and `no_windows_home` when there is nothing to find."""
    root = automount_root(system)
    users = "%s/c/Users" % root
    if named is not None:
        if not _USER_NAME.match(named) or named in (".", "..") or not system.is_dir("%s/%s" % (users, named)):
            raise WslError("no_such_user", named[:60])
        return WindowsHome("%s/%s" % (users, named), HOW_NAMED)
    program = _cmd_program(system)
    if asked and program:
        done = system.run([program, "/c", "echo %USERPROFILE%"], timeout=INTEROP_TIMEOUT_S)
        if done is not None and done.returncode == 0:
            path = _from_windows_path(done.stdout.strip().splitlines()[0] if done.stdout.strip() else "", root)
            if path and system.is_dir(path):
                return WindowsHome(path, HOW_ASKED)
    names = sorted(n for n in (system.listdir(users) or []) if n.lower() not in SYSTEM_FOLDERS and system.is_dir("%s/%s" % (users, n)))
    if len(names) == 1:
        return WindowsHome("%s/%s" % (users, names[0]), HOW_ONLY)
    if names:
        raise WslError("several_users", ", ".join(names)[:200])
    raise WslError("no_windows_home")


# ---------------------------------------------------------------- what is true now

@dataclass(frozen=True)
class Facts:
    platform: preflight.Platform
    interop: str                                    # INTEROP_WORKS, INTEROP_FAILED or INTEROP_MISSING
    build: Optional[int]                            # the Windows build number, when Windows told us
    runtime_mode: Optional[str]                     # how this running Ubuntu is networked ("nat", "mirrored"...) when `wslinfo` says
    home: Optional[WindowsHome]
    home_error: Optional[WslError]                  # why `home` is None
    config_path: Optional[str]
    config_text: Optional[str]                      # None: there is no file (or no home)
    file_mode: Optional[str]                        # what the file says for networkingMode
    file_idle: Optional[str]                        # what the file says for instanceIdleTimeout
    config_bad: bool                                # the file is there but is not plain UTF-8 text


def runtime_networking_mode(system: System) -> Optional[str]:
    """The networking mode of this running Ubuntu, from `wslinfo --networking-mode` where WSL has that program; None when it is not there or says something unexpected."""
    program = system.which("wslinfo")
    if not program:
        return None
    done = system.run([program, "--networking-mode"], timeout=INTEROP_TIMEOUT_S)
    if done is None or done.returncode != 0:
        return None
    word = done.stdout.strip().lower()
    return word if re.match(r"^[a-z]{1,20}\Z", word) else None


def read_exact(path: str) -> Optional[str]:
    """The file's text with its line ends and any byte order mark as they are (a read in text mode would turn CRLF into LF); None when it cannot be read or is not UTF-8."""
    try:
        with open(path, "rb") as source:
            return source.read().decode("utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def look(system: System, *, named: Optional[str] = None) -> Facts:
    """Read the facts. Starts one short Windows program to ask what works, and changes nothing."""
    platform = preflight.detect_platform(system.read_text("/proc/version"), system.environ())
    if platform is preflight.Platform.NATIVE:
        return Facts(platform, INTEROP_MISSING, None, None, None, None, None, None, None, None, False)
    state, build = interop(system)
    home: Optional[WindowsHome] = None
    error: Optional[WslError] = None
    try:
        home = windows_home(system, asked=state == INTEROP_WORKS, named=named)
    except WslError as caught:
        error = caught
    path = text = None
    bad = False
    if home:
        path = "%s/%s" % (home.path, CONFIG_NAME)
        if system.exists(path):
            text = read_exact(path)
            bad = text is None or "\x00" in text
            text = None if bad else text
    mode = idle = None
    if text is not None:
        modes, idles = find(text, SECTION_NETWORK, KEY_NETWORK), find(text, SECTION_IDLE, KEY_IDLE)
        mode = modes[-1].lower() if modes else None
        idle = idles[-1] if idles else None
    return Facts(platform, state, build, runtime_networking_mode(system), home, error, path, text, mode, idle, bad)


def idle_state(system: System) -> Optional[str]:
    """For a command that is about to start something long (a round): None when this is not Ubuntu in Windows; otherwise IDLE_NEVER when the Windows settings file keeps Ubuntu running after the last
    window closes, IDLE_STOPS when it does not say so, and IDLE_UNKNOWN when the file could not be found or read. It starts no Windows program: the folder is found by looking and the file is read as a file."""
    if preflight.detect_platform(system.read_text("/proc/version"), system.environ()) is preflight.Platform.NATIVE:
        return None
    try:
        path = "%s/%s" % (windows_home(system, asked=False).path, CONFIG_NAME)
    except WslError:
        return IDLE_UNKNOWN
    if not system.exists(path):
        return IDLE_STOPS
    text = system.read_text(path)
    if text is None or "\x00" in text:
        return IDLE_UNKNOWN
    values = find(text, SECTION_IDLE, KEY_IDLE)
    return IDLE_NEVER if values and values[-1] == NEVER else IDLE_STOPS


# ---------------------------------------------------------------- what to do about it

def firewall_commands(port: int) -> Tuple[str, str]:
    """(the PowerShell command that lets a phone reach `port` on Ubuntu, and the one that takes the rule away again). For the person to run themselves in a PowerShell opened as administrator."""
    if not isinstance(port, int) or isinstance(port, bool) or not 1024 <= port <= 65535:
        raise ValueError
    add = ("New-NetFirewallHyperVRule -Name '%s' -DisplayName 'ACK Voice Studio: send the voice file' -Direction Inbound -VMCreatorId '%s' -Protocol TCP -LocalPorts %d"
           % (FIREWALL_RULE, HYPERV_VM_CREATOR, port))
    return add, "Remove-NetFirewallHyperVRule -Name '%s'" % FIREWALL_RULE


def mirrored_possible(build: Optional[int]) -> Optional[bool]:
    """Whether this Windows can do mirrored networking; None when the build is not known."""
    return None if build is None else build >= MIRRORED_MIN_BUILD


@dataclass(frozen=True)
class EditPlan:
    path: str
    section: str
    key: str
    value: str
    old: Optional[str]                              # the file's text now (None: no file yet)
    new: str
    listing: Tuple[str, ...]                        # what would change, line by line
    creates: bool                                   # the file does not exist yet


def plan_edit(facts: Facts, section: str, key: str, value: str) -> Optional[EditPlan]:
    """The change that would set `key` to `value`; None when the file already says so. Raises `no_windows_home` or `several_users` when the file cannot be located, and `bad_text` or `duplicate` for a file that
    cannot be edited safely."""
    if facts.home is None:
        raise facts.home_error or WslError("no_windows_home")
    if facts.config_bad:
        raise WslError("bad_text")
    old = facts.config_text
    new = with_setting(old or "", section, key, value)
    if old is not None and new == old:
        return None
    return EditPlan(facts.config_path or "", section, key, value, old, new, tuple(changes(old or "", new)), old is None)


def backup_name(path: str, now: datetime) -> str:
    """A name beside `path` that does not exist yet: `.bak`, then `.bak-` with the time, then that with a number."""
    candidate = path + ".bak"
    stamp = now.astimezone(timezone.utc).strftime("%Y%m%d-%H%M%S") if now.tzinfo else now.strftime("%Y%m%d-%H%M%S")
    if os.path.lexists(candidate):
        candidate = "%s.bak-%s" % (path, stamp)
        n = 1
        while os.path.lexists(candidate):
            n += 1
            candidate = "%s.bak-%s-%d" % (path, stamp, n)
    return candidate


def apply_edit(plan: EditPlan, now: datetime) -> Optional[str]:
    """Write the change. Returns the name of the copy made of the old file (None when there was no file). The old file is copied first, the new text goes to a temporary file and replaces the old
    in one step, and the result is read back; anything that goes wrong leaves the old file as it was and raises `not_written`."""
    kept: Optional[str] = None
    temporary = "%s.new-%d" % (plan.path, os.getpid())
    try:
        if plan.old is None and os.path.lexists(plan.path):
            raise OSError("the file appeared while this was waiting")
        if plan.old is not None:
            with open(plan.path, "rb") as source:
                original = source.read()
            kept = backup_name(plan.path, now)
            with open(kept, "xb") as copy:
                copy.write(original)
            with open(kept, "rb") as copy:
                if copy.read() != original:
                    raise OSError("the copy differs")
        data = plan.new.encode("utf-8")
        with open(temporary, "wb") as out:
            out.write(data)
            out.flush()
            os.fsync(out.fileno())
        os.replace(temporary, plan.path)
        with open(plan.path, "rb") as back:
            if back.read() != data:
                raise OSError("the file read back differs")
    except OSError as error:
        try:
            os.remove(temporary)
        except OSError:
            pass
        raise WslError("not_written", (error.strerror or str(error))[:100])
    return kept
