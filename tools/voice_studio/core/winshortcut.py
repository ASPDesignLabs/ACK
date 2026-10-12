# SPDX-License-Identifier: GPL-3.0-or-later
"""A Start menu shortcut for the window, made on the Windows side, for ACK Voice Studio running inside WSL.

WSLg builds the Start menu entry itself, but only from the system folders of the Linux side, and copying a file there needs `sudo`. Nobody should be asked to do that, so this module makes
the same kind of shortcut that WSLg makes (the same program, the same arguments, minimised, an icon next to it) in the person's own Start menu folder, through the Windows program
that WSL already lets Linux start. That needs no administrator rights and no password.

What it keeps to, and what the tests hold it to:
* It shows what it will write, first (the caller asks). Nothing is written until the person says yes.
* The three scripts it sends are fixed text. The only values that go in are the shortcut's name, the distribution's name, the arguments and the icon, each passed as base64 so that no
  quote, space or symbol in a name can become part of the script. The names are checked first; a name that is not plain is refused rather than quoted.
* No path that Windows reported is ever sent back. The scripts work out their own folders again, so a wrong or odd answer from Windows cannot make them write somewhere else.
* A shortcut is only replaced or removed when it carries this tool's marker in its description. One of the same name that something else made is left exactly as it is.
* The scripts read and write only the Start menu folder of the person and one small folder of their own application data. They use no network, start no other program and contain no
  password prompt.
"""
from __future__ import annotations

import base64
import hashlib
import re
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

from .launcher import LauncherError, SAFE_PATH
from .system import CommandResult, System

POWERSHELL = "powershell.exe"
KNOWN_POWERSHELL = "/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe"      # where Windows keeps it, for a computer whose WSL does not add Windows programs to the search path
MARKER = "ack-voice-studio-launcher"                      # in the shortcut's description: how a shortcut of ours is told from anyone else's
FOLDER = "ack-voice-studio"                               # the tool's own folder in the person's application data
ICON_FILE = "AckVoiceStudio.ico"
PREVIOUS_FILE = "previous-shortcut.lnk"                   # an older shortcut of ours that was replaced
DISTRO_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,64}\Z")                  # \Z, not $: a $ also matches before a trailing line break
FILE_NAME_PATTERN = re.compile(r'^[^\\/:*?"<>|\x00-\x1f]{1,80}\Z')
MAX_DESCRIPTION = 250                                     # Windows keeps 260 characters
MAX_COMMAND_CHARS = 30000                                 # Windows stops at 32767 for the whole command line
PROBE_TIMEOUT_S = 40.0
CHANGE_TIMEOUT_S = 90.0
ERROR_CODES = ("no_wslg", "shortcut_failed", "shortcut_not_removed")      # each has words in the text catalog (foreign_file and odd_path are the launcher's)


@dataclass(frozen=True)
class Route:
    """How to reach Windows from here: the program that runs the scripts, and which Linux system this is."""
    distro: str
    powershell: str


def route(system: System) -> Optional[Route]:
    """None when this tool cannot reach the Windows side: Windows programs cannot be started from WSL, or the system's name is not plain."""
    distro = system.environ().get("WSL_DISTRO_NAME", "")
    program = system.which(POWERSHELL) or (KNOWN_POWERSHELL if system.exists(KNOWN_POWERSHELL) else None)
    if not program or not DISTRO_PATTERN.match(distro):
        return None
    return Route(distro, program)


# ---------------------------------------------------------------- what is wanted

@dataclass(frozen=True)
class Wanted:
    name: str                 # the shortcut's file name without .lnk
    distro: str
    arguments: str
    description: str
    icon: bytes

    @property
    def icon_sha256(self) -> str:
        return hashlib.sha256(self.icon).hexdigest()


def shortcut_name(label: str, distro: str) -> str:
    """"ACK Voice Studio (Ubuntu-22.04)": the same name WSLg gives its own entry, so the two read alike."""
    if not FILE_NAME_PATTERN.match(label) or not DISTRO_PATTERN.match(distro):
        raise LauncherError("odd_path", "name")
    return "%s (%s)" % (label, distro)


def window_arguments(distro: str, tools_dir: str, python: str) -> str:
    """Exactly the shape WSLg uses for its own entry: `-d <system> --cd "~" -- env PYTHONPATH=<tools> <program> -m voice_studio.window`."""
    for path in (tools_dir, python):
        if not SAFE_PATH.match(path):
            raise LauncherError("odd_path", path)
    if not DISTRO_PATTERN.match(distro):
        raise LauncherError("odd_path", "name")
    return '-d %s --cd "~" -- env PYTHONPATH=%s %s -m voice_studio.window' % (distro, tools_dir, python)


def wanted(distro: str, tools_dir: str, python: str, label: str, comment: str, icon: bytes) -> Wanted:
    description = "%s [%s]" % (comment, MARKER)
    if len(description) > MAX_DESCRIPTION or any(ord(c) < 32 for c in description):
        raise LauncherError("odd_path", "text")
    return Wanted(shortcut_name(label, distro), distro, window_arguments(distro, tools_dir, python), description, icon)


# ---------------------------------------------------------------- the scripts

_PREAMBLE = r"""
$ErrorActionPreference = 'Stop'
function Decode([string]$text) { [System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String($text)) }
function Emit([string]$key, [string]$value) { Write-Output ($key + '=' + [System.Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes($value))) }
$name = Decode '@@NAME@@'
$distro = Decode '@@DISTRO@@'
$marker = '@@MARKER@@'
$programs = [System.Environment]::GetFolderPath('Programs')
$local = [System.Environment]::GetFolderPath('LocalApplicationData')
$lnk = Join-Path $programs ($name + '.lnk')
$folder = Join-Path $local '@@FOLDER@@'
$ico = Join-Path $folder '@@ICON_FILE@@'
$wslg = ''
foreach ($candidate in @((Join-Path $env:ProgramFiles 'WSL\wslg.exe'), (Join-Path $env:SystemRoot 'System32\wslg.exe'))) {
  if ((-not $wslg) -and (Test-Path -LiteralPath $candidate)) { $wslg = $candidate }
}
"""

_PROBE = _PREAMBLE + r"""
try {
  $state = 'missing'
  $target = ''
  $arguments = ''
  $location = ''
  if (Test-Path -LiteralPath $lnk) {
    $state = 'foreign'
    try {
      $found = (New-Object -ComObject WScript.Shell).CreateShortcut($lnk)
      $target = [string]$found.TargetPath
      $arguments = [string]$found.Arguments
      $location = [string]$found.IconLocation
      if (([string]$found.Description).Contains($marker)) { $state = 'ours' }
    } catch { $state = 'foreign' }
  }
  $present = 'no'
  $hash = ''
  if (Test-Path -LiteralPath $ico) {
    $present = 'yes'
    $hash = (Get-FileHash -LiteralPath $ico -Algorithm SHA256).Hash
  }
  $own = ''
  $ownPath = Join-Path (Join-Path $programs $distro) ($name + '.lnk')
  if (Test-Path -LiteralPath $ownPath) { $own = $ownPath }
  Emit 'wslg' $wslg
  Emit 'shortcut_path' $lnk
  Emit 'icon_path' $ico
  Emit 'shortcut' $state
  Emit 'target' $target
  Emit 'arguments' $arguments
  Emit 'icon_location' $location
  Emit 'icon_present' $present
  Emit 'icon_sha256' $hash
  Emit 'wslg_shortcut' $own
  Emit 'done' '1'
} catch {
  Emit 'error' $_.Exception.Message
  exit 1
}
"""

_INSTALL = _PREAMBLE + r"""
$arguments = Decode '@@ARGUMENTS@@'
$description = Decode '@@DESCRIPTION@@'
try {
  if (-not $wslg) { Emit 'result' 'no_wslg'; exit 3 }
  $shell = New-Object -ComObject WScript.Shell
  $existing = Test-Path -LiteralPath $lnk
  if ($existing) {
    $old = $shell.CreateShortcut($lnk)
    if (-not (([string]$old.Description).Contains($marker))) { Emit 'result' 'foreign'; exit 4 }
  }
  New-Item -ItemType Directory -Force -Path $folder | Out-Null
  if ($existing) { Copy-Item -LiteralPath $lnk -Destination (Join-Path $folder '@@PREVIOUS_FILE@@') -Force }
  $part = $ico + '.part'
  [System.IO.File]::WriteAllBytes($part, [System.Convert]::FromBase64String('@@ICON@@'))
  Move-Item -LiteralPath $part -Destination $ico -Force
  $made = $shell.CreateShortcut($lnk)
  $made.TargetPath = $wslg
  $made.Arguments = $arguments
  $made.WorkingDirectory = Join-Path $env:SystemRoot 'System32'
  $made.IconLocation = $ico + ',0'
  $made.WindowStyle = 7
  $made.Description = $description
  $made.Save()
  $back = $shell.CreateShortcut($lnk)
  $differs = @()
  if ($back.TargetPath -ne $wslg) { $differs += 'TargetPath' }
  if ($back.Arguments -ne $arguments) { $differs += 'Arguments' }
  if ($back.IconLocation -ne ($ico + ',0')) { $differs += 'IconLocation' }
  if (-not (([string]$back.Description).Contains($marker))) { $differs += 'Description' }
  if ($differs.Count -gt 0) {
    if ($existing) { Copy-Item -LiteralPath (Join-Path $folder '@@PREVIOUS_FILE@@') -Destination $lnk -Force } else { Remove-Item -LiteralPath $lnk -Force }
    Emit 'result' 'mismatch'
    Emit 'detail' ('Windows kept a different value for: ' + ($differs -join ', '))
    exit 5
  }
  Emit 'result' 'done'
} catch {
  Emit 'result' 'failed'
  Emit 'detail' $_.Exception.Message
  exit 1
}
"""

_REMOVE = _PREAMBLE + r"""
try {
  $shell = New-Object -ComObject WScript.Shell
  if (Test-Path -LiteralPath $lnk) {
    $old = $shell.CreateShortcut($lnk)
    if (-not (([string]$old.Description).Contains($marker))) { Emit 'result' 'foreign'; exit 4 }
    Remove-Item -LiteralPath $lnk -Force
  }
  if (Test-Path -LiteralPath $ico) { Remove-Item -LiteralPath $ico -Force }
  if ((Test-Path -LiteralPath $folder) -and (-not (Get-ChildItem -LiteralPath $folder -Force))) { Remove-Item -LiteralPath $folder -Force }
  Emit 'result' 'done'
} catch {
  Emit 'result' 'failed'
  Emit 'detail' $_.Exception.Message
  exit 1
}
"""


def _b64(text: str) -> str:
    return base64.b64encode(text.encode("utf-8")).decode("ascii")


def _fill(template: str, values: Dict[str, str]) -> str:
    out = template
    for key, value in values.items():
        out = out.replace("@@%s@@" % key, value)
    if "@@" in out:
        raise LauncherError("shortcut_failed", "script")
    return out


def _common(name: str, distro: str) -> Dict[str, str]:
    return {"NAME": _b64(name), "DISTRO": _b64(distro), "MARKER": MARKER, "FOLDER": FOLDER, "ICON_FILE": ICON_FILE}


def probe_script(name: str, distro: str) -> str:
    return _fill(_PROBE, _common(name, distro))


def install_script(want: Wanted) -> str:
    values = _common(want.name, want.distro)
    values.update({"ARGUMENTS": _b64(want.arguments), "DESCRIPTION": _b64(want.description), "ICON": base64.b64encode(want.icon).decode("ascii"), "PREVIOUS_FILE": PREVIOUS_FILE})
    return _fill(_INSTALL, values)


def remove_script(name: str, distro: str) -> str:
    return _fill(_REMOVE, _common(name, distro))


def command(route_: Route, script: str) -> Tuple[str, ...]:
    """The command line that runs a script: Windows PowerShell takes it as base64 of UTF-16, which needs no quoting at all."""
    encoded = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
    if len(encoded) > MAX_COMMAND_CHARS:
        raise LauncherError("shortcut_failed", "script too long")
    return (route_.powershell, "-NoLogo", "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded)


def _run(system: System, route_: Route, script: str, timeout: float) -> Optional[CommandResult]:
    return system.run(command(route_, script), timeout=timeout, cwd="/mnt/c" if system.exists("/mnt/c") else None)


# ---------------------------------------------------------------- what comes back

_BASE64 = r"(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?"      # whole groups of four, then at most one short group with exactly the padding it needs: Python 3.12 and older accept more than that
_LINE = re.compile(r"^([a-z0-9_]{1,40})=(" + _BASE64 + r")\Z")


def values(stdout: str) -> Dict[str, str]:
    """The `key=base64` lines of a script's output. Any other line (a warning, a banner) is ignored, and a line that is not valid is dropped rather than guessed at."""
    found: Dict[str, str] = {}
    for line in (stdout or "").replace("\ufeff", "").splitlines():
        hit = _LINE.match(line.strip())
        if not hit:
            continue
        try:
            found[hit.group(1)] = base64.b64decode(hit.group(2), validate=True).decode("utf-8")
        except ValueError:
            continue
    return found


def _tidy(text: str, limit: int = 200) -> str:
    one_line = " ".join("".join(c if c.isprintable() else " " for c in (text or "")).split())
    return one_line[:limit]


@dataclass(frozen=True)
class Probe:
    """What the Windows side looks like now. The paths are for showing to the person; no script is ever given one."""
    wslg: str                 # where Windows keeps wslg.exe; empty when it is not there
    shortcut_path: str
    icon_path: str
    shortcut: str             # "missing", "ours" or "foreign"
    target: str
    arguments: str
    icon_location: str
    icon_present: bool
    icon_sha256: str
    wslg_shortcut: str        # the path of the entry WSL made itself, empty when there is none


def probe(system: System, route_: Route, name: str, distro: str) -> Optional[Probe]:
    """None when the Windows side could not be read (the program did not start, failed, or answered in a way that is not understood): the caller falls back."""
    done = _run(system, route_, probe_script(name, distro), PROBE_TIMEOUT_S)
    if done is None or done.returncode != 0:
        return None
    got = values(done.stdout)
    if got.get("done") != "1" or got.get("shortcut") not in ("missing", "ours", "foreign") or got.get("icon_present") not in ("yes", "no"):
        return None
    for key in ("wslg", "shortcut_path", "icon_path", "target", "arguments", "icon_location", "icon_sha256", "wslg_shortcut"):
        if key not in got:
            return None
    return Probe(got["wslg"], got["shortcut_path"], got["icon_path"], got["shortcut"], got["target"], got["arguments"], got["icon_location"], got["icon_present"] == "yes",
                 got["icon_sha256"], got["wslg_shortcut"])


# ---------------------------------------------------------------- the plan

PLAN_STATES = ("new", "same", "update", "foreign", "wslg", "no_wslg")


@dataclass(frozen=True)
class ShortcutPlan:
    state: str                # one of PLAN_STATES
    shortcut_change: str      # "new", "update" or "same"
    icon_change: str
    shortcut_path: str
    icon_path: str
    folder: str               # where an older shortcut of ours is kept when it is replaced
    wslg_shortcut: str

    @property
    def changes(self) -> bool:
        return self.state in ("new", "update")


def _same(a: str, b: str) -> bool:
    return a.lower() == b.lower()


def plan_install(found: Probe, want: Wanted) -> ShortcutPlan:
    folder = found.icon_path.rsplit("\\", 1)[0] if "\\" in found.icon_path else ""
    if not found.wslg:
        state, shortcut, icon = "no_wslg", "same", "same"
    elif found.wslg_shortcut:
        state, shortcut, icon = "wslg", "same", "same"
    elif found.shortcut == "foreign":
        state, shortcut, icon = "foreign", "same", "same"
    else:
        if found.shortcut == "missing":
            shortcut = "new"
        elif _same(found.target, found.wslg) and found.arguments == want.arguments and _same(found.icon_location, found.icon_path + ",0"):
            shortcut = "same"
        else:
            shortcut = "update"
        if not found.icon_present:
            icon = "new"
        else:
            icon = "same" if found.icon_sha256.lower() == want.icon_sha256 else "update"
        if shortcut == "same" and icon == "same":
            state = "same"
        elif shortcut == "new":
            state = "new"
        else:
            state = "update"
    return ShortcutPlan(state, shortcut, icon, found.shortcut_path, found.icon_path, folder, found.wslg_shortcut)


@dataclass(frozen=True)
class RemovalPlan:
    state: str                # "ours" (something of ours is there), "none" or "foreign" (a shortcut of that name is there and is not ours: everything is left alone)
    paths: Tuple[str, ...]    # what would go, for showing
    foreign: str = ""


def plan_remove(found: Probe) -> RemovalPlan:
    if found.shortcut == "foreign":
        return RemovalPlan("foreign", (), found.shortcut_path)
    paths = []
    if found.shortcut == "ours":
        paths.append(found.shortcut_path)
    if found.icon_present:
        paths.append(found.icon_path)
    return RemovalPlan("ours" if paths else "none", tuple(paths))


# ---------------------------------------------------------------- doing it

def _outcome(done: Optional[CommandResult]) -> Tuple[str, str]:
    """(what the script said, a short technical detail). A script that did not start, or did not say `done` and exit cleanly, is a failure."""
    if done is None:
        return "failed", "no answer from powershell.exe"
    got = values(done.stdout)
    text = got.get("detail") or got.get("error") or ""
    if not text:
        lines = (done.stderr or "").strip().splitlines()
        text = lines[0] if lines else ""
    detail = _tidy(text)
    result = got.get("result", "")
    if result == "done" and done.returncode == 0:
        return "done", ""
    if result in ("foreign", "no_wslg"):
        return result, detail
    return "failed", detail or "exit code %d" % done.returncode


def install(system: System, route_: Route, want: Wanted) -> None:
    """Make the shortcut. Raises LauncherError (foreign_file, no_wslg, shortcut_failed); nothing the person made is replaced."""
    kind, detail = _outcome(_run(system, route_, install_script(want), CHANGE_TIMEOUT_S))
    if kind == "done":
        return
    if kind == "foreign":
        raise LauncherError("foreign_file", want.name)
    if kind == "no_wslg":
        raise LauncherError("no_wslg")
    raise LauncherError("shortcut_failed", detail)


def remove(system: System, route_: Route, name: str, distro: str) -> None:
    """Remove the shortcut and the icon this tool made. A shortcut of that name that is not ours stays."""
    kind, detail = _outcome(_run(system, route_, remove_script(name, distro), CHANGE_TIMEOUT_S))
    if kind == "done":
        return
    if kind == "foreign":
        raise LauncherError("foreign_file", name)
    raise LauncherError("shortcut_not_removed", detail)
