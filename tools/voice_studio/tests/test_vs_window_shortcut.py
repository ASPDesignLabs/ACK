# SPDX-License-Identifier: GPL-3.0-or-later
"""The Start menu shortcut made on the Windows side (core/winshortcut.py) and the icon drawn for it (core/iconmake.py).

Three layers, because each catches what the others miss: the decisions and the words (plain Python, always run); the scripts' own text (parsed by a real PowerShell when one is
installed, scanned for what they must never contain either way); and the scripts actually run by PowerShell against a stand-in for Windows' shortcut object, on a throw-away folder
(only when PowerShell is installed: set ACK_VS_PWSH to its path). None of these can show what a real Windows does with a shortcut: that is the developer's check (checklist I5).
"""
import base64
import dataclasses
import hashlib
import json
import os
import re
import shutil
import struct
import subprocess
import xml.etree.ElementTree as ET
import zlib
from pathlib import Path

import pytest

from vs_fakes import FakeSystem, wsl2
from vs_startvoice_helpers import Terminal, implies_permission, leaked_keys
from voice_studio.core import iconmake, launcher, text, windowcli as wc, winshortcut as ws
from voice_studio.core.system import CommandResult

PKG = Path(__file__).resolve().parents[1]
POWERSHELL_PATH = "/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe"
TOOLS, PYTHON = "/home/anna/ack-tools/tools", "/usr/bin/python3"
CAT = text.load_catalog("en")
SVG = '<?xml version="1.0"?><!-- ack-voice-studio-icon --><svg/>\n'
LABEL, COMMENT = "ACK Voice Studio", "Make a voice for ACK from your own recordings, on this computer"
WSLG = r"C:\Program Files\WSL\wslg.exe"
SHORTCUT = r"C:\Users\anna\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\ACK Voice Studio (Ubuntu-22.04).lnk"
ICON = r"C:\Users\anna\AppData\Local\ack-voice-studio\AckVoiceStudio.ico"
WSLG_OWN = r"C:\Users\anna\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Ubuntu-22.04\ACK Voice Studio (Ubuntu-22.04).lnk"
_REAL_ICON = []


def real_icon():
    if not _REAL_ICON:
        _REAL_ICON.append(iconmake.ico_bytes())
    return _REAL_ICON[0]


def want(icon=b"tiny icon", distro="Ubuntu-22.04", tools=TOOLS, python=PYTHON, label=LABEL, comment=COMMENT):
    return ws.wanted(distro, tools, python, label, comment, icon)


def reply(**kv):
    """What a script prints: key=base64(value) lines, with Windows line ends."""
    return "".join("%s=%s\r\n" % (k, base64.b64encode(v.encode("utf-8")).decode("ascii")) for k, v in kv.items())


def probe_reply(**over):
    base = dict(wslg=WSLG, shortcut_path=SHORTCUT, icon_path=ICON, shortcut="missing", target="", arguments="", icon_location="", icon_present="no", icon_sha256="", wslg_shortcut="", done="1")
    base.update(over)
    return reply(**base)


def probe_of(**over):
    base = dict(wslg=WSLG, shortcut_path=SHORTCUT, icon_path=ICON, shortcut="missing", target="", arguments="", icon_location="", icon_present=False, icon_sha256="", wslg_shortcut="")
    base.update(over)
    return ws.Probe(**base)


def ours_probe(w, **over):
    return probe_of(shortcut="ours", target=WSLG, arguments=w.arguments, icon_location=ICON + ",0", icon_present=True, icon_sha256=w.icon_sha256, **over)


def decoded(argv):
    return base64.b64decode(argv[argv.index("-EncodedCommand") + 1]).decode("utf-16-le")


class Canned(FakeSystem):
    """A computer whose Windows PowerShell says what the test says, and remembers what it was asked to run."""

    def __init__(self, outputs=(), **kw):
        kw.setdefault("tools", {"powershell.exe": POWERSHELL_PATH})
        kw.setdefault("present", {"/mnt/c"})
        kw.setdefault("environ", {"WSL_DISTRO_NAME": "Ubuntu-22.04"})
        super().__init__(**kw)
        self.outputs, self.scripts, self.timeouts, self.cwds = list(outputs), [], [], []

    def run(self, argv, timeout=15.0, cwd=None, env=None):
        if os.path.basename(argv[0]) == "powershell.exe":
            self.ran.append(tuple(argv))
            self.scripts.append(decoded(argv))
            self.timeouts.append(timeout)
            self.cwds.append(cwd)
            return self.outputs.pop(0) if self.outputs else None
        return super().run(argv, timeout, cwd, env)


def route_of(system):
    return ws.route(system)


# ---------------------------------------------------------------- the icon

def read_ico(data):
    reserved, kind, count = struct.unpack_from("<HHH", data, 0)
    assert (reserved, kind) == (0, 1)
    entries = []
    for i in range(count):
        w, h, colours, zero, planes, bits, size, offset = struct.unpack_from("<BBBBHHII", data, 6 + 16 * i)
        entries.append((w or 256, h or 256, planes, bits, size, offset))
    return entries


def read_png(data):
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    position, chunks = 8, []
    while position < len(data):
        length, kind = struct.unpack_from(">I4s", data, position)
        body = data[position + 8:position + 8 + length]
        crc, = struct.unpack_from(">I", data, position + 8 + length)
        assert crc == zlib.crc32(kind + body) & 0xFFFFFFFF, kind
        chunks.append((kind, body))
        position += 12 + length
    assert [k for k, _ in chunks][0] == b"IHDR" and [k for k, _ in chunks][-1] == b"IEND"
    width, height, depth, colour, _c, _f, _i = struct.unpack(">IIBBBBB", chunks[0][1])
    assert (depth, colour) == (8, 6)
    raw = zlib.decompress(b"".join(b for k, b in chunks if k == b"IDAT"))
    assert len(raw) == height * (1 + 4 * width)
    rows = [raw[y * (1 + 4 * width):(y + 1) * (1 + 4 * width)] for y in range(height)]
    assert all(r[0] == 0 for r in rows)
    return width, height, [[tuple(r[1 + 4 * x:5 + 4 * x]) for x in range(width)] for r in rows]


def test_the_icon_is_a_real_ico_with_five_png_images_of_the_sizes_windows_asks_for():
    data = real_icon()
    entries = read_ico(data)
    assert [(w, h) for w, h, *_ in entries] == [(16, 16), (32, 32), (48, 48), (64, 64), (256, 256)] and all(p == 1 and b == 32 for _w, _h, p, b, *_ in entries)
    position = 6 + 16 * len(entries)
    for w, h, _p, _b, size, offset in entries:
        assert offset == position
        width, height, _pixels = read_png(data[offset:offset + size])
        assert (width, height) == (w, h)
        position += size
    assert position == len(data) and len(data) < 8000


def test_the_icon_is_the_same_bytes_every_time_and_needs_no_image_library():
    assert iconmake.ico_bytes((16, 32)) == iconmake.ico_bytes((16, 32))
    source = (PKG / "core" / "iconmake.py").read_text()
    assert not re.search(r"^\s*(import|from)\s+(PIL|numpy|cairosvg|wand)", source, re.M)


def test_the_icon_is_drawn_from_the_same_shapes_and_colours_as_the_svg():
    root = ET.parse(PKG / "data" / "icons" / "org.aspdesignlabs.AckVoiceStudio.svg").getroot()
    ns = "{http://www.w3.org/2000/svg}"
    square = root.find(ns + "rect")
    bars = root.find(ns + "g").findall(ns + "rect")
    assert tuple(float(square.get(k)) for k in ("x", "y", "width", "height", "rx")) == iconmake.SQUARE
    assert tuple(tuple(float(b.get(k)) for k in ("x", "y", "width", "height")) for b in bars) == iconmake.BARS
    assert all(float(b.get("rx")) == float(b.get("width")) / 2 for b in bars)
    assert "#%02x%02x%02x" % iconmake.BACKGROUND == square.get("fill") and "#%02x%02x%02x" % iconmake.BARS_COLOUR == root.find(ns + "g").get("fill")
    assert root.get("viewBox") == "0 0 128 128" and iconmake.VIEW == 128.0


def test_the_big_image_has_a_clear_corner_a_dark_square_and_light_bars_where_the_svg_has_them():
    data = real_icon()
    w, h, _p, _b, size, offset = read_ico(data)[-1]
    _w, _h, pixels = read_png(data[offset:offset + size])
    scale = 256 / 128.0
    at = lambda x, y: pixels[int(y * scale)][int(x * scale)]
    assert at(1, 1)[3] == 0                                                      # outside the rounded square
    assert at(12, 64) == iconmake.BACKGROUND + (255,)                            # in the square, between nothing and the first bar
    assert at(27, 64) == iconmake.BARS_COLOUR + (255,)                           # the middle of the first bar
    assert at(63, 64) == iconmake.BARS_COLOUR + (255,)                           # the middle of the tall bar
    assert at(63, 14)[:3] == iconmake.BACKGROUND and at(63, 14)[3] == 255        # above the tall bar, still in the square
    assert at(99, 64) == iconmake.BARS_COLOUR + (255,) and at(99, 40) == iconmake.BACKGROUND + (255,)      # the shortest bar is short
    assert at(22.6, 52.6) == iconmake.BACKGROUND + (255,) and at(31.4, 75.4) == iconmake.BACKGROUND + (255,)      # the ends of a bar are round: its corners are not light


def test_the_edge_of_a_bar_is_smoothed_a_pixel_half_covered_is_half_way_between_the_two_colours():
    data = real_icon()
    entry = [e for e in read_ico(data) if e[0] == 48][0]
    _w, _h, pixels = read_png(data[entry[5]:entry[5] + entry[4]])
    edge = pixels[24][8][:3]                                                             # the first bar's left edge falls inside this pixel
    low, high = iconmake.BACKGROUND, iconmake.BARS_COLOUR
    assert edge != low and edge != high and all(min(a, b) < c < max(a, b) for a, b, c in zip(low, high, edge)), edge


# ---------------------------------------------------------------- the words in a name

def test_the_shortcut_is_named_like_the_one_wsl_makes_and_the_arguments_are_exactly_its_shape():
    w = want()
    assert w.name == "ACK Voice Studio (Ubuntu-22.04)"
    assert w.arguments == '-d Ubuntu-22.04 --cd "~" -- env PYTHONPATH=/home/anna/ack-tools/tools /usr/bin/python3 -m voice_studio.window'
    assert w.description == COMMENT + " [" + ws.MARKER + "]" and len(w.description) < ws.MAX_DESCRIPTION


@pytest.mark.parametrize("tools, python", [("/home/an na/tools", PYTHON), (TOOLS, "/usr/bin/python 3"), (TOOLS + ";rm", PYTHON), ("/home/anna/$HOME", PYTHON), (TOOLS, "python3"),
                                           ("/home/anna/\ntools", PYTHON), ('/home/anna/"tools"', PYTHON), ("/home/anna/`x`", PYTHON), (TOOLS, "/usr/bin/python3 -c x"), (TOOLS + "\n", PYTHON), (TOOLS, PYTHON + "\n")])
def test_a_path_with_a_space_or_a_symbol_is_refused_not_quoted(tools, python):
    with pytest.raises(launcher.LauncherError) as caught:
        want(tools=tools, python=python)
    assert caught.value.code == "odd_path"


@pytest.mark.parametrize("distro", ["My Distro", "a;b", "", "x" * 65, "Ubuntu\n", "a'b", "$(x)", "a&b", "é"])
def test_a_system_name_that_is_not_plain_is_refused(distro):
    with pytest.raises(launcher.LauncherError):
        want(distro=distro)


@pytest.mark.parametrize("label", ['a"b', "a/b", "a\\b", "a:b", "a*b", "a?b", "a<b", "a>b", "a|b", "a\nb", "ab\n", "", "x" * 81])
def test_a_name_that_windows_would_not_accept_in_a_file_name_is_refused(label):
    with pytest.raises(launcher.LauncherError):
        want(label=label)


def test_the_arguments_are_checked_on_their_own_too_and_not_only_through_the_other_checks():
    for distro in ("My Distro", "Ubuntu\n", "", "a;b"):
        with pytest.raises(launcher.LauncherError):
            ws.window_arguments(distro, TOOLS, PYTHON)
    assert ws.window_arguments("Debian", TOOLS, PYTHON).startswith('-d Debian --cd "~" -- env PYTHONPATH=')


def test_a_description_with_a_line_break_or_too_long_is_refused():
    for comment in ("a\nb", "x" * 300, "a\x00b"):
        with pytest.raises(launcher.LauncherError):
            want(comment=comment)


# ---------------------------------------------------------------- reaching Windows

def test_the_windows_side_is_reachable_only_on_wsl_with_windows_programs_and_a_plain_system_name():
    system = wsl2(tools={"powershell.exe": POWERSHELL_PATH})
    system._environ["WSL_DISTRO_NAME"] = "Ubuntu-22.04"
    assert ws.route(system) == ws.Route("Ubuntu-22.04", POWERSHELL_PATH)
    assert ws.route(wsl2(tools={})) is None                                                        # Windows programs cannot be started from here
    off_the_path = wsl2(tools={}, present={"/mnt/c", ws.KNOWN_POWERSHELL})                         # WSL set not to add Windows programs to the search path
    off_the_path._environ["WSL_DISTRO_NAME"] = "Ubuntu-22.04"
    assert ws.route(off_the_path) == ws.Route("Ubuntu-22.04", ws.KNOWN_POWERSHELL)
    no_name = wsl2(tools={"powershell.exe": POWERSHELL_PATH})
    no_name._environ.pop("WSL_DISTRO_NAME")
    assert ws.route(no_name) is None
    for odd in ("My Distro", "a;b", "$(x)"):
        system._environ["WSL_DISTRO_NAME"] = odd
        assert ws.route(system) is None


# ---------------------------------------------------------------- the scripts' text

def all_scripts():
    w = want(b"icon bytes")
    return {"probe": ws.probe_script(w.name, w.distro), "install": ws.install_script(w), "remove": ws.remove_script(w.name, w.distro)}


def test_the_source_of_the_new_modules_has_no_invisible_or_look_alike_characters_in_it():
    for name in ("winshortcut.py", "iconmake.py", "windowcli.py"):
        assert (PKG / "core" / name).read_text(encoding="utf-8").isascii(), name


def test_the_scripts_are_plain_ascii_with_no_unfilled_place_and_no_power_shell_7_only_syntax():
    for kind, script in all_scripts().items():
        assert script.isascii() and "@@" not in script, kind
        assert not re.search(r"\?\?|\?\.|&&|\|\||\?\s*\S+\s*:\s*\S", script), kind


def test_a_script_can_only_look_where_it_should_and_only_the_install_and_remove_scripts_change_anything():
    scripts = all_scripts()
    changing = re.compile(r"Remove-Item|Copy-Item|Move-Item|New-Item|WriteAllBytes|\.Save\(|Set-Content|Out-File|Add-Content|Rename-Item|Clear-")
    assert not changing.search(scripts["probe"])
    for kind in ("install", "remove"):
        for hit in re.finditer(r"Remove-Item\s+-LiteralPath\s+(\$\w+)", scripts[kind]):
            assert hit.group(1) in ("$lnk", "$ico", "$folder"), hit.group(0)
        assert len(re.findall(r"Remove-Item", scripts[kind])) == len(re.findall(r"Remove-Item\s+-LiteralPath\s+\$(lnk|ico|folder)\b", scripts[kind]))
    assert re.findall(r"Remove-Item[^\n]*", scripts["install"]) == ["Remove-Item -LiteralPath $lnk -Force }"]                 # only to take back a shortcut it has just made and could not verify
    assert not re.search(r"WriteAllBytes|Copy-Item|Move-Item|New-Item|\.Save\(", scripts["remove"])
    install = scripts["install"]
    assert re.findall(r"WriteAllBytes\((\$\w+)", install) == ["$part"] and re.findall(r"Move-Item -LiteralPath \$part -Destination (\$\w+)", install) == ["$ico"]
    assert re.findall(r"Copy-Item -LiteralPath (\$\w+) -Destination \(Join-Path \$folder", install) == ["$lnk"]
    assert re.findall(r"New-Item -ItemType Directory -Force -Path (\$\w+)", install) == ["$folder"]


def test_the_scripts_hold_nothing_that_could_reach_the_network_run_another_program_or_ask_for_a_password():
    barred = re.compile(r"Invoke-|Start-Process|\biex\b|Net\.|System\.Net|WebClient|WebRequest|http|ftp|Add-Type|Credential|Read-Host|Set-ExecutionPolicy|Register-|schtasks|\breg\b|"
                        r"Start-Job|Start-Sleep|\bcmd\b|wsl\.exe|Get-WmiObject|Get-CimInstance|\[Environment\]::SetEnvironmentVariable|Out-GridView|Write-Host|\bsudo\b|Get-Content|Set-Item", re.I)
    for kind, script in all_scripts().items():
        assert not barred.search(script), (kind, barred.search(script).group(0))
    assert "$env:" in all_scripts()["probe"] and set(re.findall(r"\$env:(\w+)", all_scripts()["install"])) == {"ProgramFiles", "SystemRoot"}


def test_what_a_person_or_a_name_supplies_enters_only_as_base64_and_never_as_script_text():
    w = want(b"\x00\x01icon", label="Bob's $(Get-Date) `x` ;", comment="It's a \"quote\" $(calc) `tick`")
    scripts = {"probe": ws.probe_script(w.name, w.distro), "install": ws.install_script(w), "remove": ws.remove_script(w.name, w.distro)}
    for kind, script in scripts.items():
        for raw in ("Bob", "$(Get-Date)", "calc", "quote", "tick", "Ubuntu", "ack-tools", "voice_studio", "PYTHONPATH"):
            assert raw not in script, (kind, raw)
    assert base64.b64encode(w.name.encode()).decode() in scripts["install"] and base64.b64encode(w.arguments.encode()).decode() in scripts["install"]
    assert base64.b64encode(w.icon).decode() in scripts["install"]


def test_the_command_hands_the_script_over_as_base64_of_utf_16_and_asks_nothing_of_the_person():
    system = Canned([CommandResult(0, probe_reply())])
    argv = ws.command(ws.Route("Ubuntu-22.04", POWERSHELL_PATH), "Write-Output 'é'")
    assert argv[:5] == (POWERSHELL_PATH, "-NoLogo", "-NoProfile", "-NonInteractive", "-EncodedCommand") and len(argv) == 6
    assert base64.b64decode(argv[5]).decode("utf-16-le") == "Write-Output 'é'"
    assert "-ExecutionPolicy" not in argv and "-Command" not in argv and "-File" not in argv


def test_the_longest_command_with_the_real_icon_stays_well_under_the_limit_windows_has_for_a_command_line():
    w = want(real_icon())
    argv = ws.command(ws.Route("Ubuntu-22.04", POWERSHELL_PATH), ws.install_script(w))
    assert len(argv[-1]) < 22000 < ws.MAX_COMMAND_CHARS < 32767
    with pytest.raises(launcher.LauncherError):
        ws.command(ws.Route("Ubuntu-22.04", POWERSHELL_PATH), "x" * 12000)


def pwsh():
    found = os.environ.get("ACK_VS_PWSH") or shutil.which("pwsh")
    if not found or not Path(found).exists():
        pytest.skip("no PowerShell here (set ACK_VS_PWSH to run the scripts)")
    return found


PARSE = r"""
param([string]$Path)
$tokens = $null; $errors = $null
[void][System.Management.Automation.Language.Parser]::ParseInput((Get-Content -Raw -LiteralPath $Path), [ref]$tokens, [ref]$errors)
Write-Output $errors.Count
foreach ($e in $errors) { Write-Output ('line {0}: {1}' -f $e.Extent.StartLineNumber, $e.Message) }
"""


def pwsh_run(args, **kw):
    env = dict(os.environ, DOTNET_SYSTEM_GLOBALIZATION_INVARIANT="1", DOTNET_CLI_TELEMETRY_OPTOUT="1", POWERSHELL_TELEMETRY_OPTOUT="1", POWERSHELL_UPDATECHECK="Off")
    return subprocess.run([pwsh(), "-NoProfile", "-NonInteractive"] + args, capture_output=True, text=True, timeout=120, env=env, stdin=subprocess.DEVNULL, **kw)


def syntax_errors(tmp_path, script):
    path = tmp_path / "script.ps1"
    path.write_text(script, encoding="utf-8")
    checker = tmp_path / "parse.ps1"
    checker.write_text(PARSE, encoding="utf-8")
    done = pwsh_run(["-File", str(checker), "-Path", str(path)])
    assert done.returncode == 0, done.stderr
    lines = done.stdout.strip().splitlines()
    return int(lines[0]), lines[1:]


def test_every_script_is_valid_power_shell_and_the_check_does_catch_a_broken_one(tmp_path):
    for kind, script in all_scripts().items():
        assert syntax_errors(tmp_path, script) == (0, []), kind
    count, _lines = syntax_errors(tmp_path, all_scripts()["install"].replace("} catch {", "} catch"))
    assert count >= 1
    assert syntax_errors(tmp_path, all_scripts()["probe"] + "\nif (")[0] >= 1


# ---------------------------------------------------------------- reading the answer

def test_the_answer_is_key_value_lines_in_base64_and_anything_else_is_ignored_not_guessed():
    text = "\ufeff" + reply(a="one", b="é ü 日本") + "some banner\r\nWARNING: something\r\nc=%%%\r\nd=Zm9v==\r\n e = x\r\n" + reply(f="")        # a byte order mark may start the first line
    assert ws.values(text) == {"a": "one", "b": "é ü 日本", "f": ""}
    assert ws.values("") == {} and ws.values(None) == {}
    assert ws.values("A=" + base64.b64encode(b"\xff\xfe").decode() + "\n") == {}                      # not UTF-8: dropped


def test_a_good_answer_gives_the_probe_and_every_way_it_can_be_wrong_gives_none():
    system = Canned([CommandResult(0, probe_reply(shortcut="ours", target=WSLG, arguments="x", icon_present="yes", icon_sha256="AB"))])
    got = ws.probe(system, route_of(system), "ACK Voice Studio (Ubuntu-22.04)", "Ubuntu-22.04")
    assert got == probe_of(shortcut="ours", target=WSLG, arguments="x", icon_present=True, icon_sha256="AB")
    good = probe_reply()
    bad_answers = [None, CommandResult(1, good), CommandResult(0, ""), CommandResult(0, good.replace("done=", "dune=")), CommandResult(0, probe_reply(shortcut="mine")),
                   CommandResult(0, probe_reply(icon_present="maybe")), CommandResult(0, probe_reply()[:-30])] + [CommandResult(0, probe_reply().replace(k + "=", "x" + k + "=")) for k in
                   ("wslg", "shortcut_path", "icon_path", "target", "arguments", "icon_location", "icon_sha256", "wslg_shortcut")]
    for answer in bad_answers:
        system = Canned([answer] if answer is not None else [])
        assert ws.probe(system, route_of(system), "n", "Ubuntu-22.04") is None, answer


def test_the_probe_runs_one_fixed_read_only_script_from_the_windows_drive_and_nothing_else():
    system = Canned([CommandResult(0, probe_reply())])
    ws.probe(system, route_of(system), "ACK Voice Studio (Ubuntu-22.04)", "Ubuntu-22.04")
    assert len(system.ran) == 1 and system.ran[0][0] == POWERSHELL_PATH and system.scripts == [ws.probe_script("ACK Voice Studio (Ubuntu-22.04)", "Ubuntu-22.04")]
    assert system.cwds == ["/mnt/c"] and system.timeouts == [ws.PROBE_TIMEOUT_S]
    no_drive = Canned([CommandResult(0, probe_reply())], present=set())
    ws.probe(no_drive, route_of(no_drive), "n", "Ubuntu-22.04")
    assert no_drive.cwds == [None]


# ---------------------------------------------------------------- the plan

def test_a_shortcut_that_is_not_there_is_a_new_one_with_a_new_icon():
    plan = ws.plan_install(probe_of(), want())
    assert (plan.state, plan.shortcut_change, plan.icon_change, plan.changes) == ("new", "new", "new", True)
    assert plan.shortcut_path == SHORTCUT and plan.icon_path == ICON and plan.folder == r"C:\Users\anna\AppData\Local\ack-voice-studio"


def test_a_shortcut_and_icon_that_are_already_right_are_left_alone_whatever_the_capitals():
    w = want()
    plan = ws.plan_install(ours_probe(w), w)
    assert (plan.state, plan.changes) == ("same", False)
    shouting = dataclasses.replace(ours_probe(w), target=WSLG.upper(), icon_location=(ICON + ",0").lower(), icon_sha256=w.icon_sha256.upper())
    assert ws.plan_install(shouting, w).state == "same"


@pytest.mark.parametrize("field, value, shortcut_change, icon_change", [
    ("target", r"C:\Windows\System32\wslg.exe", "update", "same"), ("arguments", "-d Other", "update", "same"), ("icon_location", r"C:\elsewhere.ico,0", "update", "same"),
    ("icon_sha256", "00" * 32, "same", "update"), ("icon_present", False, "same", "new"), ("arguments", "", "update", "same")])
def test_anything_of_ours_that_differs_is_an_update_of_only_what_differs(field, value, shortcut_change, icon_change):
    w = want()
    plan = ws.plan_install(dataclasses.replace(ours_probe(w), **{field: value}), w)
    assert (plan.state, plan.shortcut_change, plan.icon_change) == ("update", shortcut_change, icon_change) and plan.changes


def test_a_shortcut_of_that_name_that_is_not_ours_is_never_planned_over_and_neither_is_wsls_own_or_a_missing_wslg():
    w = want()
    assert ws.plan_install(probe_of(shortcut="foreign"), w).state == "foreign" and not ws.plan_install(probe_of(shortcut="foreign"), w).changes
    assert ws.plan_install(probe_of(wslg_shortcut=WSLG_OWN), w).state == "wslg" and ws.plan_install(probe_of(wslg_shortcut=WSLG_OWN), w).wslg_shortcut == WSLG_OWN
    assert ws.plan_install(probe_of(wslg=""), w).state == "no_wslg"
    assert ws.plan_install(probe_of(wslg="", wslg_shortcut=WSLG_OWN), w).state == "no_wslg"                          # no graphical Linux support: nothing else matters
    assert ws.plan_install(ours_probe(w, wslg_shortcut=WSLG_OWN), w).state == "wslg"                                   # WSL has made its own: do not add a second
    assert not any(ws.plan_install(probe_of(shortcut="foreign", wslg_shortcut=WSLG_OWN, wslg=""), w).changes for _ in range(1))


def test_removal_takes_what_is_ours_and_nothing_when_the_shortcut_is_someone_elses():
    w = want()
    assert ws.plan_remove(ours_probe(w)) == ws.RemovalPlan("ours", (SHORTCUT, ICON))
    assert ws.plan_remove(probe_of()) == ws.RemovalPlan("none", ())
    assert ws.plan_remove(probe_of(icon_present=True)) == ws.RemovalPlan("ours", (ICON,))                       # a shortcut already gone, its icon left
    assert ws.plan_remove(probe_of(shortcut="foreign", icon_present=True)) == ws.RemovalPlan("foreign", (), SHORTCUT)


# ---------------------------------------------------------------- doing it, with answers the test chooses

def test_a_made_shortcut_is_reported_done_and_the_script_that_ran_is_the_one_for_these_values():
    system = Canned([CommandResult(0, reply(result="done"))])
    w = want()
    ws.install(system, route_of(system), w)
    assert system.scripts == [ws.install_script(w)] and system.timeouts == [ws.CHANGE_TIMEOUT_S] and len(system.ran) == 1


@pytest.mark.parametrize("answer, code", [
    (CommandResult(4, reply(result="foreign")), "foreign_file"), (CommandResult(3, reply(result="no_wslg")), "no_wslg"),
    (CommandResult(5, reply(result="mismatch")), "shortcut_failed"), (CommandResult(1, reply(result="failed", detail="Access is denied")), "shortcut_failed"),
    (CommandResult(0, reply(result="mismatch")), "shortcut_failed"), (CommandResult(1, reply(result="done")), "shortcut_failed"), (CommandResult(0, ""), "shortcut_failed"),
    (CommandResult(1, "", "some error\nsecond line"), "shortcut_failed"), (None, "shortcut_failed")])
def test_every_way_making_it_can_end_is_a_named_error_and_only_a_clean_done_is_success(answer, code):
    system = Canned([answer] if answer is not None else [])
    with pytest.raises(launcher.LauncherError) as caught:
        ws.install(system, route_of(system), want())
    assert caught.value.code == code


def test_the_technical_line_is_one_short_clean_line_of_what_windows_said():
    system = Canned([CommandResult(1, reply(result="failed", detail="Access\r\nto the path\x07 'C:\\x' is denied.  " + "z" * 400))])
    with pytest.raises(launcher.LauncherError) as caught:
        ws.install(system, route_of(system), want())
    assert "\n" not in caught.value.detail and "\x07" not in caught.value.detail and caught.value.detail.startswith("Access to the path 'C:\\x' is denied.") and len(caught.value.detail) <= 200
    system = Canned([CommandResult(1, "", "first stderr line\nsecond")])
    with pytest.raises(launcher.LauncherError) as caught:
        ws.install(system, route_of(system), want())
    assert caught.value.detail == "first stderr line"
    system = Canned([CommandResult(7, "")])
    with pytest.raises(launcher.LauncherError) as caught:
        ws.install(system, route_of(system), want())
    assert caught.value.detail == "exit code 7"
    system = Canned([])                                                                                  # it did not start, or it ran out of time
    with pytest.raises(launcher.LauncherError) as caught:
        ws.install(system, route_of(system), want())
    assert caught.value.detail == "no answer from powershell.exe"


def test_removing_runs_its_own_script_and_a_shortcut_that_is_not_ours_is_a_refusal_not_a_failure():
    system = Canned([CommandResult(0, reply(result="done"))])
    ws.remove(system, route_of(system), "ACK Voice Studio (Ubuntu-22.04)", "Ubuntu-22.04")
    assert system.scripts == [ws.remove_script("ACK Voice Studio (Ubuntu-22.04)", "Ubuntu-22.04")]
    for answer, code in ((CommandResult(4, reply(result="foreign")), "foreign_file"), (CommandResult(1, reply(result="failed", detail="busy")), "shortcut_not_removed"), (None, "shortcut_not_removed"),
                         (CommandResult(0, ""), "shortcut_not_removed")):
        system = Canned([answer] if answer is not None else [])
        with pytest.raises(launcher.LauncherError) as caught:
            ws.remove(system, route_of(system), "n", "Ubuntu-22.04")
        assert caught.value.code == code


def test_only_windows_powershell_is_ever_started_and_never_with_sudo_or_a_shell():
    for name in ("winshortcut.py", "iconmake.py"):
        source = (PKG / "core" / name).read_text()
        assert not re.search(r"^\s*(import|from)\s+(subprocess|os\b.*system)|os\.system|shell=True|\.start\(", source, re.M), name
    assert (PKG / "core" / "winshortcut.py").read_text().count("system.run(") == 1                       # the one place a program is started


# ---------------------------------------------------------------- the scripts, run by PowerShell against a stand-in for Windows' shortcut object

FAKE_SHORTCUT_OBJECT = r"""
function Get-FileHash {
  param([string]$LiteralPath, [string]$Algorithm)
  if ($env:FAKE_FAIL_HASH) { throw 'The process cannot access the file because it is being used by another process.' }
  Microsoft.PowerShell.Utility\Get-FileHash -LiteralPath $LiteralPath -Algorithm $Algorithm
}
function New-Object {
  param([string]$ComObject)
  if ($ComObject -ne 'WScript.Shell') { throw 'unexpected object' }
  $shell = [PSCustomObject]@{ Kind = 'stand-in' }
  $shell | Add-Member -MemberType ScriptMethod -Name CreateShortcut -Value {
    param([string]$path)
    $item = [PSCustomObject]@{ Path = $path; TargetPath = ''; Arguments = ''; WorkingDirectory = ''; IconLocation = ''; WindowStyle = 1; Description = '' }
    if (Test-Path -LiteralPath $path -PathType Leaf) {
      try {
        $data = Get-Content -Raw -LiteralPath $path | ConvertFrom-Json
        foreach ($n in 'TargetPath', 'Arguments', 'WorkingDirectory', 'IconLocation', 'WindowStyle', 'Description') { $item.$n = $data.$n }
      } catch { }
    }
    $item | Add-Member -MemberType ScriptMethod -Name Save -Value {
      $copy = $this | Select-Object TargetPath, Arguments, WorkingDirectory, IconLocation, WindowStyle, Description
      if ($env:FAKE_CORRUPT) { $copy.($env:FAKE_CORRUPT) = 'tampered' }
      ($copy | ConvertTo-Json) | Set-Content -LiteralPath $this.Path -Encoding UTF8
    }
    $item
  }
  $shell
}
"""


class PowerShellSystem(Canned):
    """Runs the scripts for real, in PowerShell, with the Windows folders replaced by folders under `root` and the shortcut object replaced by one that keeps a small JSON file."""

    def __init__(self, root, corrupt="", fail_hash=False, **kw):
        super().__init__(**kw)
        self.root, self.corrupt, self.fail_hash = root, corrupt, fail_hash
        for folder in ("Programs", "Local", "PF", "Win"):
            (root / folder).mkdir(parents=True, exist_ok=True)
        self.count = 0

    def with_wslg(self):
        (self.root / "PF" / "WSL").mkdir(exist_ok=True)
        (self.root / "PF" / "WSL" / "wslg.exe").write_text("stand-in")                  # PowerShell on Linux reads the script's WSL\\wslg.exe as WSL/wslg.exe
        return self

    def run(self, argv, timeout=15.0, cwd=None, env=None):
        if os.path.basename(argv[0]) != "powershell.exe":
            return super().run(argv, timeout, cwd, env)
        self.ran.append(tuple(argv))
        script = decoded(argv)
        self.scripts.append(script)
        root = self.root
        script = script.replace("[System.Environment]::GetFolderPath('Programs')", "'%s'" % (root / "Programs")).replace("[System.Environment]::GetFolderPath('LocalApplicationData')", "'%s'" % (root / "Local"))
        assert "GetFolderPath" not in script
        prelude = FAKE_SHORTCUT_OBJECT + "\n$env:ProgramFiles = '%s'\n$env:SystemRoot = '%s'\n$env:FAKE_CORRUPT = '%s'\n$env:FAKE_FAIL_HASH = '%s'\n" % (root / "PF", root / "Win", self.corrupt, "1" if self.fail_hash else "")
        self.count += 1
        path = root / ("run%d.ps1" % self.count)
        path.write_text(prelude + script, encoding="utf-8")
        done = pwsh_run(["-File", str(path)])
        return CommandResult(done.returncode, done.stdout, done.stderr)

    def shortcut(self, name="ACK Voice Studio (Ubuntu-22.04)"):
        path = self.root / "Programs" / (name + ".lnk")
        return json.loads(path.read_text(encoding="utf-8-sig")) if path.exists() else None

    def tree(self):
        return sorted(str(p.relative_to(self.root)) for p in self.root.rglob("*") if p.is_file() and not p.name.startswith(("run", "parse", "script")))


def put_shortcut(system, name, description, **fields):
    data = {"TargetPath": "x", "Arguments": "y", "WorkingDirectory": "", "IconLocation": "", "WindowStyle": 1, "Description": description}
    data.update(fields)
    path = system.root / "Programs" / (name + ".lnk")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


NAME = "ACK Voice Studio (Ubuntu-22.04)"


def test_run_for_real_a_new_shortcut_is_made_with_the_right_fields_and_a_second_look_says_it_is_in_place(tmp_path):
    system = PowerShellSystem(tmp_path).with_wslg()
    w = want(real_icon())
    route_ = route_of(system)
    first = ws.probe(system, route_, w.name, w.distro)
    assert first is not None and first.shortcut == "missing" and not first.icon_present and first.wslg.endswith("wslg.exe") and first.wslg_shortcut == ""
    assert first.shortcut_path == str(tmp_path / "Programs" / (NAME + ".lnk")) and first.icon_path == str(tmp_path / "Local" / "ack-voice-studio" / "AckVoiceStudio.ico")
    ws.install(system, route_, w)
    made = system.shortcut()
    assert made["TargetPath"] == first.wslg and made["Arguments"] == w.arguments and made["WindowStyle"] == 7 and made["IconLocation"] == first.icon_path + ",0"
    assert made["Description"] == w.description and made["WorkingDirectory"] == str(tmp_path / "Win" / "System32")
    assert Path(first.icon_path).read_bytes() == real_icon()
    assert system.tree() == ["Local/ack-voice-studio/AckVoiceStudio.ico", "PF/WSL/wslg.exe", "Programs/" + NAME + ".lnk"]               # and nothing else was left
    again = ws.probe(system, route_, w.name, w.distro)
    assert again.shortcut == "ours" and again.icon_present and again.icon_sha256.lower() == hashlib.sha256(real_icon()).hexdigest()
    assert ws.plan_install(again, w).state == "same"


def test_run_for_real_a_shortcut_that_is_not_ours_is_refused_by_the_script_itself_and_nothing_is_touched(tmp_path):
    system = PowerShellSystem(tmp_path).with_wslg()
    mine = put_shortcut(system, NAME, "my own shortcut")
    before = mine.read_bytes()
    w = want()
    assert ws.probe(system, route_of(system), w.name, w.distro).shortcut == "foreign"
    with pytest.raises(launcher.LauncherError) as caught:
        ws.install(system, route_of(system), w)                                    # even though the caller never checked: the script checks again
    assert caught.value.code == "foreign_file" and mine.read_bytes() == before and not (tmp_path / "Local" / "ack-voice-studio").exists()
    with pytest.raises(launcher.LauncherError) as caught:
        ws.remove(system, route_of(system), w.name, w.distro)
    assert caught.value.code == "foreign_file" and mine.read_bytes() == before
    mine.write_text("not even json {{{")                                          # a file that is no shortcut at all, with that name
    assert ws.probe(system, route_of(system), w.name, w.distro).shortcut == "foreign"
    with pytest.raises(launcher.LauncherError):
        ws.install(system, route_of(system), w)
    assert mine.read_text() == "not even json {{{"


def test_run_for_real_an_older_shortcut_of_ours_is_replaced_and_kept_in_the_tools_own_folder(tmp_path):
    system = PowerShellSystem(tmp_path).with_wslg()
    route_ = route_of(system)
    old = want(b"old icon", tools="/home/anna/old/tools")
    ws.install(system, route_, old)
    new = want(b"new icon")
    found = ws.probe(system, route_, new.name, new.distro)
    plan = ws.plan_install(found, new)
    assert (plan.state, plan.shortcut_change, plan.icon_change) == ("update", "update", "update")
    ws.install(system, route_, new)
    assert system.shortcut()["Arguments"] == new.arguments and Path(found.icon_path).read_bytes() == b"new icon"
    kept = json.loads((tmp_path / "Local" / "ack-voice-studio" / ws.PREVIOUS_FILE).read_text(encoding="utf-8-sig"))
    assert kept["Arguments"] == old.arguments and not list((tmp_path / "Programs").glob("*.previous"))
    assert ws.plan_install(ws.probe(system, route_, new.name, new.distro), new).state == "same"


@pytest.mark.parametrize("field", ["TargetPath", "Arguments", "IconLocation", "Description"])
def test_run_for_real_a_shortcut_that_windows_did_not_keep_as_asked_is_taken_back_and_the_field_is_named(tmp_path, field):
    good = PowerShellSystem(tmp_path).with_wslg()
    old = want(b"old icon", tools="/home/anna/old/tools")
    ws.install(good, route_of(good), old)
    before = good.shortcut()
    system = PowerShellSystem(tmp_path, corrupt=field)
    with pytest.raises(launcher.LauncherError) as caught:
        ws.install(system, route_of(system), want(b"new icon"))
    assert caught.value.code == "shortcut_failed" and caught.value.detail == "Windows kept a different value for: " + field
    assert good.shortcut() == before                                                                    # the earlier shortcut of ours is back exactly as it was
    fresh = tmp_path / "second"
    fresh.mkdir()
    system = PowerShellSystem(fresh, corrupt=field).with_wslg()
    with pytest.raises(launcher.LauncherError) as caught:
        ws.install(system, route_of(system), want())
    assert caught.value.detail == "Windows kept a different value for: " + field and system.shortcut() is None          # no shortcut is left that was not as asked


def test_run_for_real_when_the_look_itself_fails_the_script_says_so_and_exits_with_an_error_and_the_probe_is_none(tmp_path):
    good = PowerShellSystem(tmp_path).with_wslg()
    w = want()
    ws.install(good, route_of(good), w)
    system = PowerShellSystem(tmp_path, fail_hash=True)
    route_ = route_of(system)
    done = system.run(ws.command(route_, ws.probe_script(w.name, w.distro)))
    got = ws.values(done.stdout)
    assert done.returncode == 1 and "being used by another process" in got["error"] and "done" not in got
    assert ws.probe(system, route_, w.name, w.distro) is None


def test_run_for_real_without_wslg_nothing_is_written_at_all(tmp_path):
    system = PowerShellSystem(tmp_path)
    w = want()
    assert ws.probe(system, route_of(system), w.name, w.distro).wslg == ""
    with pytest.raises(launcher.LauncherError) as caught:
        ws.install(system, route_of(system), w)
    assert caught.value.code == "no_wslg" and system.tree() == []
    (tmp_path / "Win" / "System32").mkdir()
    (tmp_path / "Win" / "System32" / "wslg.exe").write_text("x")                      # the older place for it is found too
    assert ws.probe(system, route_of(system), w.name, w.distro).wslg.endswith("wslg.exe")


def test_run_for_real_the_entry_wsl_made_itself_is_seen(tmp_path):
    system = PowerShellSystem(tmp_path).with_wslg()
    (tmp_path / "Programs" / "Ubuntu-22.04").mkdir()
    (tmp_path / "Programs" / "Ubuntu-22.04" / (NAME + ".lnk")).write_text("{}")
    w = want()
    found = ws.probe(system, route_of(system), w.name, w.distro)
    assert found.wslg_shortcut.endswith("Ubuntu-22.04/" + NAME + ".lnk") and ws.plan_install(found, w).state == "wslg"
    elsewhere = want(distro="Debian")
    assert ws.probe(system, route_of(system), elsewhere.name, elsewhere.distro).wslg_shortcut == ""


def test_run_for_real_removing_takes_the_shortcut_and_the_icon_and_the_empty_folder_but_keeps_what_it_kept(tmp_path):
    system = PowerShellSystem(tmp_path).with_wslg()
    route_ = route_of(system)
    w = want()
    ws.install(system, route_, w)
    found = ws.probe(system, route_, w.name, w.distro)
    assert ws.plan_remove(found) == ws.RemovalPlan("ours", (found.shortcut_path, found.icon_path))
    ws.remove(system, route_, w.name, w.distro)
    assert system.tree() == ["PF/WSL/wslg.exe"] and not (tmp_path / "Local" / "ack-voice-studio").exists()
    assert ws.plan_remove(ws.probe(system, route_, w.name, w.distro)).state == "none"
    ws.remove(system, route_, w.name, w.distro)                                      # taking away what is not there is not an error
    ws.install(system, route_, want(b"another", tools="/home/anna/x/tools"))
    ws.install(system, route_, w)                                                    # leaves a kept older shortcut behind
    ws.remove(system, route_, w.name, w.distro)
    assert system.tree() == ["Local/ack-voice-studio/" + ws.PREVIOUS_FILE, "PF/WSL/wslg.exe"]


def test_run_for_real_a_name_full_of_symbols_makes_exactly_that_file_and_runs_nothing(tmp_path):
    system = PowerShellSystem(tmp_path).with_wslg()
    label = "Bob's $(New-Item -Path pwned.txt) `x` ; (1) [2]"
    w = want(label=label, comment="It's $(New-Item -Path pwned2.txt) `tick`")
    ws.install(system, route_of(system), w)
    assert system.shortcut(label + " (Ubuntu-22.04)")["Description"] == w.description
    assert not list(tmp_path.rglob("pwned*")) and not list(Path(os.getcwd()).glob("pwned*"))
    assert ws.plan_install(ws.probe(system, route_of(system), w.name, w.distro), w).state == "same"
    ws.remove(system, route_of(system), w.name, w.distro)
    assert system.tree() == ["PF/WSL/wslg.exe"]


# ---------------------------------------------------------------- the command line on WSL

def cli(home, *argv, system, answers=(), interactive=True, system_entry=False, tools=TOOLS, python=PYTHON, wsl=True, icon=b"tiny icon"):
    io = Terminal(answers, interactive)
    code = wc.run_window_cli(list(argv), str(home), python, tools, SVG, CAT, io, toolkit=lambda: wc.Toolkit(True, version="4.6.9"), start=lambda: 0, on_wsl=wsl,
                             exists=lambda path: system_entry and path == launcher.SYSTEM_ENTRY, system=system, icon_bytes=lambda: icon)
    assert leaked_keys(io.text + "\n".join(io.prompts)) == [] and implies_permission(io.text) == []
    return code, io


def linux_files(home):
    return sorted(str(p.relative_to(home)) for p in Path(home).rglob("*") if p.is_file())


def in_place(w=None, **over):
    w = w or want()
    return probe_reply(shortcut="ours", target=WSLG, arguments=w.arguments, icon_location=ICON + ",0", icon_present="yes", icon_sha256=w.icon_sha256, **over)


def test_on_wsl_the_install_looks_first_shows_what_it_would_write_asks_and_writes_nothing_on_a_no(tmp_path):
    system = Canned([CommandResult(0, probe_reply())])
    code, io = cli(tmp_path, "--install-launcher", system=system, answers=["no"])
    assert code == 2 and system.scripts == [ws.probe_script(NAME, "Ubuntu-22.04")] and linux_files(tmp_path) == [] and "Nothing was done." in io.lines
    asked = next(i for i, e in enumerate(io.events) if e[0] == "ask")
    said = [e[1] for e in io.events[:asked] if e[0] == "say"]
    assert said == ["ACK Voice Studio: menu entry", "Looking at your Windows Start menu first. This can take a few seconds.", "This would write, on the Windows side, in your own folders:",
                    "  a new Start menu shortcut: " + SHORTCUT, "  a new icon file: " + ICON, "It changes nothing else, and it needs no administrator rights and no password."]
    assert io.prompts == ["Write these files now? Type yes to write them. "]
    assert "sudo" not in io.text and "password" not in " ".join(said[:-1])


def test_on_wsl_a_yes_makes_the_shortcut_and_says_how_to_find_it_and_how_long_the_first_start_can_take_and_how_to_undo(tmp_path):
    system = Canned([CommandResult(0, probe_reply()), CommandResult(0, reply(result="done"))])
    code, io = cli(tmp_path, "--install-launcher", system=system, answers=["yes"])
    w = want()
    assert code == 0 and system.scripts == [ws.probe_script(NAME, "Ubuntu-22.04"), ws.install_script(w)] and linux_files(tmp_path) == []
    assert io.lines[-5:] == ["Making the shortcut. This can take a few seconds.", "Done. The shortcut is in place.", "Look for ACK Voice Studio (Ubuntu-22.04) in your Start menu.",
                             "The first start after Windows has stopped WSL can take a little while. Nothing shows until the window is ready.",
                             "To take it away again later, run this program again with --remove-launcher."]
    assert "sudo" not in io.text and all(c[0] == POWERSHELL_PATH for c in system.ran)                    # the only program started was the Windows one


def test_with_yes_on_the_line_nothing_is_asked_and_a_terminal_with_nobody_at_it_is_never_asked(tmp_path):
    system = Canned([CommandResult(0, probe_reply()), CommandResult(0, reply(result="done"))])
    code, io = cli(tmp_path, "--install-launcher", "--yes", system=system)
    assert code == 0 and io.prompts == [] and len(system.scripts) == 2
    system = Canned([CommandResult(0, probe_reply()), CommandResult(0, reply(result="done"))])
    code, io = cli(tmp_path, "--install-launcher", system=system, answers=["yes"], interactive=False)
    assert code == 2 and io.prompts == [] and len(system.scripts) == 1                                  # it looked, and wrote nothing


@pytest.mark.parametrize("answers", [[], [""], ["n"], ["maybe"]])
def test_anything_but_a_yes_writes_nothing(tmp_path, answers):
    system = Canned([CommandResult(0, probe_reply()), CommandResult(0, reply(result="done"))])
    code, _io = cli(tmp_path, "--install-launcher", system=system, answers=answers)
    assert code == 2 and len(system.scripts) == 1


def test_when_the_shortcut_is_already_right_nothing_is_written_and_nothing_is_asked(tmp_path):
    system = Canned([CommandResult(0, in_place())])
    code, io = cli(tmp_path, "--install-launcher", system=system)
    assert code == 0 and io.prompts == [] and len(system.scripts) == 1
    assert io.lines[-2:] == ["The menu entry is already in place and up to date. Nothing was changed.", "Look for ACK Voice Studio (Ubuntu-22.04) in your Start menu."]


def test_a_shortcut_that_points_somewhere_else_is_updated_with_the_old_one_kept_and_only_what_differs_is_listed(tmp_path):
    system = Canned([CommandResult(0, in_place().replace(base64.b64encode(want().arguments.encode()).decode(), base64.b64encode(b"-d Old").decode())), CommandResult(0, reply(result="done"))])
    code, io = cli(tmp_path, "--install-launcher", "--yes", system=system)
    assert code == 0 and "  a newer version of the Start menu shortcut this tool made earlier: %s (the old one is kept in C:\\Users\\anna\\AppData\\Local\\ack-voice-studio)" % SHORTCUT in io.lines
    assert not any("icon file" in line for line in io.lines) and len(system.scripts) == 2


def test_when_wsl_has_made_its_own_entry_or_the_system_copy_is_there_no_second_one_is_made(tmp_path):
    system = Canned([CommandResult(0, probe_reply(wslg_shortcut=WSLG_OWN))])
    code, io = cli(tmp_path, "--install-launcher", "--yes", system=system)
    assert code == 0 and len(system.scripts) == 1 and linux_files(tmp_path) == []
    assert io.lines[-2:] == ["WSL has already made a Start menu entry for the window: " + WSLG_OWN, "Nothing was written."]
    system = Canned([])
    code, io = cli(tmp_path, "--install-launcher", "--yes", system=system, system_entry=True)
    assert code == 0 and system.scripts == [] and system.ran == [] and io.lines[-2:] == ["The copy that WSL reads is already in the system folder: " + launcher.SYSTEM_ENTRY, "Nothing was written."]


def test_a_shortcut_of_that_name_that_is_not_ours_is_reported_and_left_and_it_is_a_problem(tmp_path):
    system = Canned([CommandResult(0, probe_reply(shortcut="foreign"))])
    code, io = cli(tmp_path, "--install-launcher", "--yes", system=system)
    assert code == 1 and len(system.scripts) == 1 and io.lines[-2:] == ["A file that this tool did not make is already at %s." % SHORTCUT, "Nothing was written."]
    system = Canned([CommandResult(0, probe_reply()), CommandResult(4, reply(result="foreign"))])               # it appeared between the look and the writing: the script refuses
    code, io = cli(tmp_path, "--install-launcher", "--yes", system=system)
    assert code == 1 and "  A file with the same name is there, and this tool did not make it." in io.lines and "  Nothing was written, and that file was left as it is." in io.lines


def test_without_graphical_linux_support_it_says_so_in_plain_words_and_writes_nothing(tmp_path):
    system = Canned([CommandResult(0, probe_reply(wslg=""))])
    code, io = cli(tmp_path, "--install-launcher", "--yes", system=system)
    assert code == 1 and len(system.scripts) == 1 and linux_files(tmp_path) == []
    assert io.lines[-3:] == ["  The graphical Linux support that Windows needs for a window was not found, so a shortcut cannot be made.", "  Nothing was written.", "  Update Windows and WSL, then try again."]


def test_a_failed_shortcut_says_what_may_have_been_left_and_gives_the_technical_line(tmp_path):
    system = Canned([CommandResult(0, probe_reply()), CommandResult(1, reply(result="failed", detail="Access to the path is denied."))])
    code, io = cli(tmp_path, "--install-launcher", "--yes", system=system)
    assert code == 1 and io.lines[-4:] == ["  The Start menu shortcut could not be made.", "  At most the small icon file was written. Nothing else was changed.",
                                          "  Try again. If it fails again, the technical line below says why.", "  Technical detail: Access to the path is denied."]


@pytest.mark.parametrize("make_system", [lambda: Canned([], tools={}), lambda: Canned([CommandResult(1, "")]), lambda: Canned([]), lambda: Canned([CommandResult(0, "nonsense")])],
                         ids=["no windows program", "powershell fails", "powershell cannot run", "unreadable answer"])
def test_when_the_windows_side_cannot_be_reached_the_older_menu_entry_and_the_printed_steps_follow_and_a_no_still_writes_nothing(tmp_path, make_system):
    code, io = cli(tmp_path, "--install-launcher", "--yes", system=make_system())
    assert code == 0 and "This tool cannot reach your Windows Start menu from here. It can still make a menu entry on the Linux side." in io.lines
    assert "Done. The menu entry is in place." in io.lines and any(l.startswith("  sudo install -D") for l in io.lines) and len(linux_files(tmp_path)) == 2
    other = tmp_path / "other"
    other.mkdir()
    code, io = cli(other, "--install-launcher", system=make_system(), answers=["no"])
    assert code == 2 and linux_files(other) == [] and not any("sudo" in l for l in io.lines)


def test_nothing_of_the_windows_side_is_touched_off_wsl_or_without_a_way_to_reach_it(tmp_path):
    system = Canned([])
    code, io = cli(tmp_path, "--install-launcher", "--yes", system=system, wsl=False)
    assert code == 0 and system.scripts == [] and system.ran == [] and "It appears in the applications list of your desktop." in io.lines
    other = tmp_path / "other"
    other.mkdir()
    code, io = cli(other, "--install-launcher", "--yes", system=None)
    assert code == 0 and any(l.startswith("  sudo install -D") for l in io.lines)


def test_removing_off_wsl_never_looks_at_the_windows_side_either(tmp_path):
    launcher.install(launcher.plan_install(str(tmp_path), PYTHON, TOOLS, "ACK Voice Studio", COMMENT, SVG))
    system = Canned([CommandResult(0, in_place())])
    code, io = cli(tmp_path, "--remove-launcher", "--yes", system=system, wsl=False)
    assert code == 0 and system.scripts == [] and system.ran == [] and linux_files(tmp_path) == []
    assert not any("Windows" in line for line in io.lines)


def test_an_odd_folder_name_is_refused_before_anything_is_run_on_either_side(tmp_path):
    system = Canned([])
    code, io = cli(tmp_path, "--install-launcher", "--yes", system=system, tools="/home/an na/tools")
    assert code == 1 and system.scripts == [] and "  A folder name has a space or a symbol that a menu entry cannot hold safely." in io.lines and linux_files(tmp_path) == []


def test_removing_on_wsl_lists_both_sides_together_asks_once_and_removes_both(tmp_path):
    lc = launcher
    lc.install(lc.plan_install(str(tmp_path), PYTHON, TOOLS, "ACK Voice Studio", COMMENT, SVG))                      # the files an earlier version of the tool wrote on the Linux side
    system = Canned([CommandResult(0, in_place()), CommandResult(0, reply(result="done"))])
    code, io = cli(tmp_path, "--remove-launcher", system=system, answers=["yes"])
    assert code == 0 and system.scripts == [ws.probe_script(NAME, "Ubuntu-22.04"), ws.remove_script(NAME, "Ubuntu-22.04")] and linux_files(tmp_path) == []
    head = io.lines.index("This would remove these files that this tool made:")
    assert io.lines[head + 1:head + 5] == ["  " + SHORTCUT, "  " + ICON, "  " + lc.desktop_path(str(tmp_path)), "  " + lc.icon_path(str(tmp_path))] and io.prompts == ["Remove them now? Type yes to remove them. "]
    assert io.lines[-2:] == ["Removing them. This can take a few seconds.", "Done. The menu entry is removed. Nothing else was changed."]


def test_a_no_to_the_removal_removes_nothing_on_either_side(tmp_path):
    launcher.install(launcher.plan_install(str(tmp_path), PYTHON, TOOLS, "ACK Voice Studio", COMMENT, SVG))
    system = Canned([CommandResult(0, in_place())])
    code, io = cli(tmp_path, "--remove-launcher", system=system, answers=["no"])
    assert code == 2 and len(system.scripts) == 1 and len(linux_files(tmp_path)) == 2


def test_removing_when_there_is_nothing_of_ours_says_so_and_a_shortcut_of_someone_elses_is_left_alone(tmp_path):
    system = Canned([CommandResult(0, probe_reply())])
    code, io = cli(tmp_path, "--remove-launcher", "--yes", system=system)
    assert code == 0 and "There is no menu entry made by this tool to remove." in io.lines and len(system.scripts) == 1
    system = Canned([CommandResult(0, probe_reply(shortcut="foreign", icon_present="yes"))])
    code, io = cli(tmp_path, "--remove-launcher", "--yes", system=system)
    assert code == 0 and "Left alone, because this tool did not make it: " + SHORTCUT in io.lines and "There is no menu entry made by this tool to remove." in io.lines and len(system.scripts) == 1


def test_removing_when_the_windows_side_cannot_be_looked_at_still_removes_the_linux_files_and_says_so(tmp_path):
    launcher.install(launcher.plan_install(str(tmp_path), PYTHON, TOOLS, "ACK Voice Studio", COMMENT, SVG))
    code, io = cli(tmp_path, "--remove-launcher", "--yes", system=Canned([], tools={}))
    assert code == 0
    assert "This tool cannot reach your Windows Start menu from here, so it cannot look for a shortcut there." in io.lines and linux_files(tmp_path) == []


def test_a_failed_removal_is_a_problem_with_words_and_the_linux_files_are_left_for_another_try(tmp_path):
    launcher.install(launcher.plan_install(str(tmp_path), PYTHON, TOOLS, "ACK Voice Studio", COMMENT, SVG))
    system = Canned([CommandResult(0, in_place()), CommandResult(1, reply(result="failed", detail="The process cannot access the file."))])
    code, io = cli(tmp_path, "--remove-launcher", "--yes", system=system)
    assert code == 1 and len(linux_files(tmp_path)) == 2
    assert io.lines[-4:] == ["  The Start menu shortcut could not be removed.", "  Nothing else was changed.", "  Try again. If it fails again, the technical line below says why.",
                             "  Technical detail: The process cannot access the file."]


def test_a_copy_in_the_system_folder_that_an_older_version_asked_for_is_still_pointed_out_and_never_removed(tmp_path):
    system = Canned([CommandResult(0, in_place()), CommandResult(0, reply(result="done"))])
    code, io = cli(tmp_path, "--remove-launcher", "--yes", system=system, system_entry=True)
    assert code == 0 and any(l.startswith("A copy in the system folder is still there, and this tool does not remove it. To remove it, run: sudo rm ") for l in io.lines)


def test_run_for_real_the_whole_install_and_remove_through_the_command_line(tmp_path):
    system = PowerShellSystem(tmp_path / "windows").with_wslg()
    home = tmp_path / "home"
    home.mkdir()
    code, io = cli(home, "--install-launcher", "--yes", system=system, icon=real_icon())
    assert code == 0 and system.tree() == ["Local/ack-voice-studio/AckVoiceStudio.ico", "PF/WSL/wslg.exe", "Programs/" + NAME + ".lnk"] and linux_files(home) == []
    code, io = cli(home, "--install-launcher", "--yes", system=system, icon=real_icon())
    assert code == 0 and "The menu entry is already in place and up to date. Nothing was changed." in io.lines
    code, io = cli(home, "--remove-launcher", "--yes", system=system)
    assert code == 0 and system.tree() == ["PF/WSL/wslg.exe"] and io.lines[-1] == "Done. The menu entry is removed. Nothing else was changed."
    code, io = cli(home, "--remove-launcher", "--yes", system=system)
    assert code == 0 and "There is no menu entry made by this tool to remove." in io.lines
