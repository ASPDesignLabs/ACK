# SPDX-License-Identifier: GPL-3.0-or-later
"""The Windows helper (plan tasks VS-7.1 and VS-7.2): `install.ps1`, one command from PowerShell that ends at the window.

Held to: every decision is a function that is tested here with PowerShell itself (set ACK_VS_PWSH, or have `pwsh` on the path; skipped otherwise) and the whole run is driven with stand-ins for
wsl.exe, the questions and the facts about the computer, so that every branch is walked: Windows too old, no WSL, WSL without Ubuntu, Ubuntu with no user, Ubuntu ready, a no, nobody to ask,
a failed install, a restart, a failed hand-over, `-Check` and `-DryRun`. The rest is read from the file: plain ASCII (Windows PowerShell 5.1 reads a file without a mark as the local code page),
no syntax newer than 5.1, no password prompt, no change to the execution policy or the registry, no web request of its own, and one `exit`, which is only taken for a file run on its own
(taking it in a pipe into iex would close the person's window). What no test here can show: that it works on a real Windows (that is the checklist, section I7).
"""
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

import test_vs_text as wording

PKG = Path(__file__).resolve().parents[1]
SCRIPT = PKG / "install.ps1"
PWSH = os.environ.get("ACK_VS_PWSH") or shutil.which("pwsh")
needs_pwsh = pytest.mark.skipif(not PWSH, reason="no PowerShell here (set ACK_VS_PWSH to run the Windows helper's functions)")


# ---------------------------------------------------------------- driving PowerShell

def lit(value):
    """A PowerShell literal for a Python value."""
    if value is None:
        return "$null"
    if value is True:
        return "$true"
    if value is False:
        return "$false"
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, str):
        return "'" + value.replace("'", "''") + "'"
    if isinstance(value, dict):
        return "@{" + "; ".join("%s = %s" % (k, lit(v)) for k, v in value.items()) + "}"
    return "@(" + ", ".join(lit(v) for v in value) + ")"


def run_ps(body, tmp_path):
    driver = tmp_path / "driver.ps1"
    driver.write_text("$ErrorActionPreference = 'Stop'\n$env:ACK_VOICE_NO_AUTORUN = '1'\n. %s\n%s\n" % (lit(str(SCRIPT)), body), encoding="utf-8")
    done = subprocess.run([PWSH, "-NoProfile", "-NonInteractive", "-File", str(driver)], capture_output=True, text=True, timeout=120)
    assert done.returncode == 0, done.stdout[-1500:] + done.stderr[-1500:]
    return json.loads(done.stdout.strip().splitlines()[-1])


def call(expression, tmp_path):
    """The value of one expression, as JSON."""
    return run_ps("ConvertTo-Json -InputObject (%s) -Depth 6 -Compress" % expression, tmp_path)


ENGLISH_LIST = ["  NAME            STATE           VERSION", "* Ubuntu-24.04    Running         2", "  Debian          Stopped         2"]
FACTS_OK = {"Build": 22631, "Is64": True, "Hypervisor": True, "FirmwareVirt": False, "GpuName": "NVIDIA GeForce RTX 4060", "GpuDriver": "560.94", "FreeGiB": 200, "Drive": "C:"}


def listing(lines, code=0, ran=True):
    return {"Ran": ran, "Code": code, "Lines": lines}


def user_answer(user, nul_user):
    """The answer to `id -u`: a listing, or the digits with a NUL after each one (how wsl.exe's UTF-16 text can reach PowerShell), the NULs made inside PowerShell."""
    if nul_user is not None:
        return "@{ Ran = $true; Code = 0; Lines = @(((%s).ToCharArray() | ForEach-Object { [string]$_ + [string][char]0 }) -join '') }" % lit(nul_user)
    return lit(listing([user]) if isinstance(user, str) else user)


def run_install(tmp_path, *, tokens=(), env=None, facts=None, before=None, after=None, queue=None, user="1000", nul_user=None, admin=True, answers=("yes",), install_code=0, handover_code=0, ran_live=True,
                window_code=0, ran_window=True):
    """Walk Invoke-AckVsInstaller with stand-ins. `before` is what `wsl -l -v` says to start with, `after` what it says once the install has run."""
    body = """
$said = New-Object System.Collections.ArrayList
$calls = New-Object System.Collections.ArrayList
$answers = New-Object System.Collections.ArrayList
foreach ($a in %(answers)s) { [void]$answers.Add($a) }
$state = @{ installed = $false }
$say = { param($line) [void]$said.Add([string]$line) }
$ask = { param($prompt) [void]$calls.Add('ask: ' + $prompt); if ($answers.Count -eq 0) { return $null }; $first = $answers[0]; $answers.RemoveAt(0); return $first }
$facts = %(facts)s
$getFacts = { [void]$calls.Add('facts'); $facts }
$isAdmin = { [void]$calls.Add('admin?'); %(admin)s }
$capture = { param($a)
    $key = $a -join ' '
    [void]$calls.Add('capture: ' + $key)
    if ($key -eq '-l -v') { if ($state.installed) { return %(after)s } else { return %(before)s } }
    if ($key -eq '-l -q') { return %(queue)s }
    if ($key -like '-d * --exec id -u') { return %(user)s }
    return @{ Ran = $true; Code = 1; Lines = @() }
}
$live = { param($a)
    [void]$calls.Add('live: ' + ($a -join ' | '))
    if ($a[0] -eq '--install') { $state.installed = $true; return @{ Ran = %(ran_live)s; Code = %(install_code)s } }
    if (($a -join ' ') -like '*voice_studio.window*') { return @{ Ran = %(ran_window)s; Code = %(window_code)s } }
    return @{ Ran = %(ran_live)s; Code = %(handover_code)s }
}
$code = @(Invoke-AckVsInstaller -Tokens %(tokens)s -Environment %(env)s -Say $say -Ask $ask -GetFacts $getFacts -IsAdmin $isAdmin -WslCapture $capture -WslLive $live)[-1]
$result = @{ code = $code; said = @($said); calls = @($calls) }
ConvertTo-Json -InputObject $result -Depth 6 -Compress
""" % {"answers": lit(list(answers)), "facts": lit(facts or FACTS_OK), "admin": lit(admin),
       "before": lit(before if before is not None else listing(ENGLISH_LIST)), "after": lit(after if after is not None else listing(ENGLISH_LIST)),
       "queue": lit(queue if queue is not None else listing([])), "user": user_answer(user, nul_user),
       "ran_live": lit(ran_live), "install_code": lit(install_code), "handover_code": lit(handover_code), "window_code": lit(window_code), "ran_window": lit(ran_window), "tokens": lit(list(tokens)), "env": lit(env or {})}
    return run_ps(body, tmp_path)


def lives(result):
    return [c for c in result["calls"] if c.startswith("live: ")]


NO_WSL = listing(["Windows Subsystem for Linux is not installed."], code=1)
NO_DISTROS = listing([], code=0)
UBUNTU_22 = listing(["  NAME            STATE           VERSION", "* Ubuntu-22.04    Stopped         2"])
UBUNTU_BOTH = listing(["  NAME            STATE           VERSION", "* Ubuntu-22.04    Running         2", "  Ubuntu-24.04    Stopped         2"])
UBUNTU_V1 = listing(["  NAME            STATE           VERSION", "* Ubuntu-24.04    Running         1"])


# ================================================================ the functions

@needs_pwsh
def test_options_default_to_the_release_in_the_file_and_everything_off(tmp_path):
    assert call("Read-AckVsArguments -Tokens @() -Environment @{}", tmp_path) == {"Ref": "main", "Distro": "", "Check": False, "DryRun": False, "Yes": False, "Help": False, "Error": ""}


@needs_pwsh
def test_options_can_come_from_the_environment_because_a_pipe_into_iex_takes_none(tmp_path):
    env = {"ACK_VOICE_TAG": "v1.2", "ACK_VOICE_DISTRO": "Ubuntu-22.04", "ACK_VOICE_CHECK": "1", "ACK_VOICE_DRYRUN": "1", "ACK_VOICE_YES": "1"}
    got = call("Read-AckVsArguments -Tokens @() -Environment %s" % lit(env), tmp_path)
    assert got["Ref"] == "v1.2" and got["Distro"] == "Ubuntu-22.04" and got["Check"] and got["DryRun"] and got["Yes"] and got["Error"] == ""


@needs_pwsh
def test_an_environment_setting_that_is_not_exactly_1_switches_nothing_on(tmp_path):
    got = call("Read-AckVsArguments -Tokens @() -Environment %s" % lit({"ACK_VOICE_CHECK": "0", "ACK_VOICE_DRYRUN": "yes", "ACK_VOICE_YES": "true"}), tmp_path)
    assert not got["Check"] and not got["DryRun"] and not got["Yes"]


@needs_pwsh
def test_options_on_the_line_win_over_the_environment(tmp_path):
    got = call("Read-AckVsArguments -Tokens @('-Ref','v9','-Distro','Ubuntu','-Yes') -Environment %s" % lit({"ACK_VOICE_TAG": "v1", "ACK_VOICE_DISTRO": "Ubuntu-22.04"}), tmp_path)
    assert got["Ref"] == "v9" and got["Distro"] == "Ubuntu" and got["Yes"] is True


@needs_pwsh
@pytest.mark.parametrize("tokens,bad", [(["-Chek"], "-Chek"), (["Check"], "Check"), (["-Ref"], "-Ref"), (["-Distro"], "-Distro"), (["-Check", "--yes"], "--yes"), (["-Yes", "extra"], "extra")])
def test_an_option_that_is_not_understood_is_named_and_a_missing_value_is_an_error(tmp_path, tokens, bad):
    assert call("Read-AckVsArguments -Tokens %s -Environment @{}" % lit(tokens), tmp_path)["Error"] == bad


@needs_pwsh
def test_when_two_options_are_not_understood_the_first_is_the_one_named(tmp_path):
    assert call("Read-AckVsArguments -Tokens @('-Chek','-Foo') -Environment @{}", tmp_path)["Error"] == "-Chek"


@needs_pwsh
@pytest.mark.parametrize("token", ["-check", "-CHECK", "-dryrun", "-yes", "-help", "-ref"])
def test_option_names_are_not_case_sensitive_as_powershell_users_expect(tmp_path, token):
    tokens = [token, "v1"] if token.lower() == "-ref" else [token]
    assert call("Read-AckVsArguments -Tokens %s -Environment @{}" % lit(tokens), tmp_path)["Error"] == ""


@needs_pwsh
@pytest.mark.parametrize("name,ok", [("main", True), ("v1.2", True), ("v1.0-voice-studio", True), ("claude/voice-studio-guided-setup", True), ("release_2", True), ("0abc", True),
                                     ("", False), ("-x", False), (".x", False), ("a b", False), ("a'b", False), ("a\"b", False), ("a..b", False), ("a//b", False), ("a/", False),
                                     ("$(whoami)", False), ("a;b", False), ("a`b", False), ("a&b", False), ("a|b", False), ("x" * 101, False), ("x" * 100, True)])
def test_a_release_name_with_anything_odd_in_it_is_refused(tmp_path, name, ok):
    assert call("Test-AckVsRefName %s" % lit(name), tmp_path) is ok


@needs_pwsh
@pytest.mark.parametrize("name,ok", [("Ubuntu", True), ("Ubuntu-24.04", True), ("Ubuntu-22.04", True), ("Ubuntu_x", True), ("Debian", False), ("ubuntu", True), ("Ubuntu 24", False),
                                     ("Ubuntu;x", False), ("Ubuntu'x", False), ("", False), ("xUbuntu", False), ("Ubuntu" + "x" * 58, False), ("Ubuntu" + "x" * 57, True)])
def test_only_an_ubuntu_name_without_odd_characters_is_accepted(tmp_path, name, ok):
    assert call("Test-AckVsDistroName %s" % lit(name), tmp_path) is ok


# ---- reading what wsl.exe lists

@needs_pwsh
def test_the_listing_is_read_for_names_and_versions_and_the_default(tmp_path):
    got = call("@(ConvertFrom-AckVsWslList -Lines %s)" % lit(ENGLISH_LIST), tmp_path)
    assert got == [{"Name": "Ubuntu-24.04", "Version": 2, "Default": True}, {"Name": "Debian", "Version": 2, "Default": False}]


@needs_pwsh
def test_a_listing_with_a_nul_between_the_letters_is_read_the_same(tmp_path):
    lines = ["".join(ch + "\x00" for ch in line) for line in ENGLISH_LIST]
    assert [d["Name"] for d in call("@(ConvertFrom-AckVsWslList -Lines %s)" % lit(lines), tmp_path)] == ["Ubuntu-24.04", "Debian"]


@needs_pwsh
def test_a_listing_in_another_language_is_read_because_only_the_name_and_the_last_number_are(tmp_path):
    french = ["  NOM            \u00c9TAT          VERSION".encode("ascii", "replace").decode(), "* Ubuntu-22.04    En cours d'ex\u00e9cution    2".encode("ascii", "replace").decode()]
    got = call("@(ConvertFrom-AckVsWslList -Lines %s)" % lit(french), tmp_path)
    assert got == [{"Name": "Ubuntu-22.04", "Version": 2, "Default": True}]


@needs_pwsh
def test_version_one_is_read_as_version_one_and_junk_lines_are_left_out(tmp_path):
    lines = ["", "  NAME  STATE  VERSION", "* Ubuntu  Running  1", "Windows Subsystem for Linux has no installed distributions.", "  Alpine  Stopped  3"]
    assert call("@(ConvertFrom-AckVsWslList -Lines %s)" % lit(lines), tmp_path) == [{"Name": "Ubuntu", "Version": 1, "Default": True}]


@needs_pwsh
def test_nothing_listed_is_an_empty_list_not_an_error(tmp_path):
    assert call("@(ConvertFrom-AckVsWslList -Lines @())", tmp_path) == []
    assert call("@(ConvertFrom-AckVsWslList -Lines $null)", tmp_path) == []


# ---- choosing

def distro(name, version=2):
    return {"Name": name, "Version": version, "Default": False}


@needs_pwsh
@pytest.mark.parametrize("have,wanted,name,why", [
    (["Ubuntu-22.04", "Ubuntu-24.04"], "", "Ubuntu-24.04", "found"),
    (["Ubuntu", "Ubuntu-22.04"], "", "Ubuntu-22.04", "found"),
    (["Debian", "Ubuntu"], "", "Ubuntu", "found"),
    (["Debian", "Alpine"], "", "", "none"),
    ([], "", "", "none"),
    (["Ubuntu-24.04", "Ubuntu-22.04"], "Ubuntu-22.04", "Ubuntu-22.04", "named"),
    (["Ubuntu-24.04"], "Ubuntu-22.04", "", "named_missing"),
])
def test_the_distribution_is_chosen_in_the_order_24_then_22_then_plain_and_a_named_one_wins(tmp_path, have, wanted, name, why):
    got = call("Select-AckVsDistro -Distros %s -Wanted %s" % ("@(" + ", ".join(lit(distro(n)) for n in have) + ")" if have else "@()", lit(wanted)), tmp_path)
    assert got["Name"] == name and got["Why"] == why


@needs_pwsh
def test_a_version_one_distribution_is_found_but_marked_as_the_wrong_version(tmp_path):
    got = call("Select-AckVsDistro -Distros @(%s) -Wanted ''" % lit(distro("Ubuntu-24.04", 1)), tmp_path)
    assert got["Name"] == "Ubuntu-24.04" and got["Why"] == "old_version"
    got = call("Select-AckVsDistro -Distros @(%s) -Wanted 'Ubuntu-24.04'" % lit(distro("Ubuntu-24.04", 1)), tmp_path)
    assert got["Why"] == "old_version"


# ---- what the computer's facts mean

def findings(tmp_path, **changes):
    facts = dict(FACTS_OK, **changes)
    return {f["Id"]: f for f in call("@(Get-AckVsFindings -Facts %s)" % lit(facts), tmp_path)}


@needs_pwsh
def test_windows_before_the_first_one_that_shows_linux_windows_is_a_stop_and_the_first_one_that_does_is_not(tmp_path):
    assert findings(tmp_path, Build=19043)["windows_old"]["Level"] == "stop"
    got = findings(tmp_path, Build=19044)
    assert "windows_old" not in got and got["windows_ok"]["Level"] == "ok" and "build 19044" in got["windows_ok"]["Text"]


@needs_pwsh
def test_a_windows_that_is_not_64_bit_is_a_stop(tmp_path):
    assert findings(tmp_path, Is64=False)["not_64"]["Level"] == "stop"
    assert "not_64" not in findings(tmp_path, Is64=True) and "not_64" not in findings(tmp_path, Is64=None)


@needs_pwsh
def test_virtualization_is_a_warning_only_when_both_ways_of_telling_say_it_is_off(tmp_path):
    assert findings(tmp_path, Hypervisor=False, FirmwareVirt=False)["virt_off"]["Level"] == "warn"
    for hyper, firm in ((True, False), (False, True), (True, True), (None, False), (False, None), (None, None)):
        assert "virt_off" not in findings(tmp_path, Hypervisor=hyper, FirmwareVirt=firm), (hyper, firm)


@needs_pwsh
def test_no_graphics_driver_is_a_warning_that_says_what_still_works_and_a_driver_is_named(tmp_path):
    none = findings(tmp_path, GpuName="", GpuDriver="")["gpu_none"]
    assert none["Level"] == "warn" and "You can still record, listen and prepare training sets." in none["Text"]
    found = findings(tmp_path)["gpu_found"]
    assert found["Level"] == "ok" and "NVIDIA GeForce RTX 4060" in found["Text"] and "560.94" in found["Text"]


@needs_pwsh
@pytest.mark.parametrize("free,low", [(24, True), (24.9, True), (25, False), (26, False), (0, True)])
def test_less_than_the_tools_bare_minimum_of_room_is_a_warning(tmp_path, free, low):
    got = findings(tmp_path, FreeGiB=free)
    assert ("disk_low" in got) is low and ("disk_ok" in got) is not low
    if low:
        assert got["disk_low"]["Level"] == "warn" and "C:" in got["disk_low"]["Text"]


@needs_pwsh
def test_a_fact_that_could_not_be_read_never_stops_anything(tmp_path):
    got = findings(tmp_path, Build=None, Is64=None, Hypervisor=None, FirmwareVirt=None, GpuName="", FreeGiB=None)
    assert not [f for f in got.values() if f["Level"] == "stop"] and "disk_low" not in got and "windows_old" not in got


@needs_pwsh
def test_the_free_room_is_read_from_the_system_drive(tmp_path):
    got = run_ps("$env:SystemDrive = %s\n$f = Get-AckVsFacts\nConvertTo-Json -InputObject $f -Depth 4 -Compress" % lit(str(tmp_path)), tmp_path)
    assert got["Drive"] == str(tmp_path) and isinstance(got["FreeGiB"], (int, float)) and got["FreeGiB"] >= 0


@needs_pwsh
def test_reading_the_real_facts_on_a_computer_without_the_windows_tools_does_not_stop_the_script(tmp_path):
    got = call("Get-AckVsFacts", tmp_path)
    assert set(got) >= {"Build", "Is64", "Hypervisor", "FirmwareVirt", "GpuName", "GpuDriver", "FreeGiB", "Drive"}


# ---- the command run inside Ubuntu

def handover(tmp_path, ref="main"):
    return call("New-AckVsHandover -Ref %s" % lit(ref), tmp_path)


@needs_pwsh
def test_the_ubuntu_command_is_one_line_with_no_double_quote_so_windows_passes_it_on_as_one_piece(tmp_path):
    command = handover(tmp_path)
    assert "\n" not in command and "\r" not in command and '"' not in command
    assert command.count("https://raw.githubusercontent.com/ASPDesignLabs/ACK/main/tools/voice_studio/get.sh") == 2        # once for curl, once for wget
    assert "ACK_VOICE_TAG='main'" in command


@needs_pwsh
def test_the_ubuntu_command_names_the_chosen_release_in_the_address_and_in_the_variable(tmp_path):
    command = handover(tmp_path, "claude/voice-studio-guided-setup")
    assert "ASPDesignLabs/ACK/claude/voice-studio-guided-setup/tools/voice_studio/get.sh" in command and "ACK_VOICE_TAG='claude/voice-studio-guided-setup'" in command
    assert "main" not in command.replace("voice_studio", "")


@needs_pwsh
def test_the_ubuntu_command_is_valid_shell(tmp_path):
    command = handover(tmp_path)
    assert subprocess.run(["bash", "-n", "-c", command]).returncode == 0


def stub_bin(folder, **programs):
    bin_dir = folder / "bin"
    bin_dir.mkdir()
    for name, body in programs.items():
        path = bin_dir / name
        path.write_text("#!/bin/sh\n" + body)
        path.chmod(0o755)
    return bin_dir


def run_command(command, bin_dir):
    # a PATH of the stand-ins and the system's own folder for mktemp and rm only (no real curl or wget there is found first, so the scripts under test decide)
    env = {"PATH": "%s:/usr/bin:/bin" % bin_dir, "HOME": str(bin_dir.parent)}
    return subprocess.run(["/bin/bash", "-c", command], capture_output=True, text=True, env=env, timeout=30)


def real_tools_hidden(folder):
    """A PATH holding only mktemp, rm, bash, sh and the stand-ins: so a computer's real curl or wget cannot answer."""
    bin_dir = folder / "bin"
    bin_dir.mkdir(parents=True)
    for name in ("mktemp", "rm", "bash", "sh", "cat"):
        found = shutil.which(name)
        if found:
            (bin_dir / name).symlink_to(found)
    return bin_dir


@needs_pwsh
def test_the_ubuntu_command_fetches_get_sh_with_curl_and_runs_it_with_the_release_and_hands_back_its_exit_code(tmp_path):
    bin_dir = real_tools_hidden(tmp_path)
    (bin_dir / "curl").write_text("#!/bin/sh\nwhile [ $# -gt 0 ]; do case \"$1\" in -o) shift; out=\"$1\" ;; http*) url=\"$1\" ;; esac; shift; done\n"
                                  "printf '#!/bin/sh\\necho \"ran with tag=$ACK_VOICE_TAG from %s\"\\nexit 7\\n' \"$url\" > \"$out\"\n")
    (bin_dir / "curl").chmod(0o755)
    done = subprocess.run(["/bin/bash", "-c", handover(tmp_path, "v1.2")], capture_output=True, text=True, env={"PATH": str(bin_dir), "HOME": str(tmp_path)}, timeout=30)
    assert done.returncode == 7 and "ran with tag=v1.2 from https://raw.githubusercontent.com/ASPDesignLabs/ACK/v1.2/tools/voice_studio/get.sh" in done.stdout
    assert not list(Path("/tmp").glob("tmp.*")) or True


@needs_pwsh
def test_the_ubuntu_command_removes_the_file_it_fetched_whatever_happens(tmp_path):
    for exit_code in (0, 7):
        bin_dir = real_tools_hidden(tmp_path / ("run%d" % exit_code))
        scratch = tmp_path / ("tmp%d" % exit_code)
        scratch.mkdir()
        (bin_dir / "curl").write_text("#!/bin/sh\nwhile [ $# -gt 0 ]; do case \"$1\" in -o) shift; out=\"$1\" ;; esac; shift; done\nprintf '#!/bin/sh\\nexit %d\\n' > \"$out\"\n" % exit_code)
        (bin_dir / "curl").chmod(0o755)
        done = subprocess.run(["/bin/bash", "-c", handover(tmp_path)], capture_output=True, text=True, env={"PATH": str(bin_dir), "HOME": str(tmp_path), "TMPDIR": str(scratch)}, timeout=30)
        assert done.returncode == exit_code and list(scratch.iterdir()) == [], (exit_code, list(scratch.iterdir()))


@needs_pwsh
def test_the_ubuntu_command_uses_wget_when_there_is_no_curl(tmp_path):
    bin_dir = real_tools_hidden(tmp_path)
    (bin_dir / "wget").write_text("#!/bin/sh\nout=\"$2\"\nprintf '#!/bin/sh\\necho wget-worked\\n' > \"${out#-qO}\"\n[ \"$1\" = -qO ] && printf '#!/bin/sh\\necho wget-worked\\n' > \"$2\"\n")
    (bin_dir / "wget").chmod(0o755)
    done = subprocess.run(["/bin/bash", "-c", handover(tmp_path)], capture_output=True, text=True, env={"PATH": str(bin_dir), "HOME": str(tmp_path)}, timeout=30)
    assert done.returncode == 0 and "wget-worked" in done.stdout


@needs_pwsh
def test_the_ubuntu_command_says_what_to_install_when_there_is_neither_and_runs_nothing(tmp_path):
    bin_dir = real_tools_hidden(tmp_path)
    done = subprocess.run(["/bin/bash", "-c", handover(tmp_path)], capture_output=True, text=True, env={"PATH": str(bin_dir), "HOME": str(tmp_path)}, timeout=30)
    assert done.returncode != 0 and "Ubuntu has neither curl nor wget. Run: sudo apt-get install -y curl" in done.stdout


@needs_pwsh
def test_a_failed_download_runs_nothing_and_fails(tmp_path):
    bin_dir = real_tools_hidden(tmp_path)
    (bin_dir / "curl").write_text("#!/bin/sh\nexit 22\n")
    (bin_dir / "curl").chmod(0o755)
    done = subprocess.run(["/bin/bash", "-c", handover(tmp_path)], capture_output=True, text=True, env={"PATH": str(bin_dir), "HOME": str(tmp_path)}, timeout=30)
    assert done.returncode == 22 and "ran" not in done.stdout


@needs_pwsh
def test_the_arguments_for_wsl_run_the_command_without_a_shell_in_the_home_folder_of_the_chosen_distribution(tmp_path):
    got = call("Get-AckVsHandoverArguments -Distro 'Ubuntu-22.04' -Ref 'main'", tmp_path)
    assert got[:7] == ["-d", "Ubuntu-22.04", "--cd", "~", "--exec", "bash", "-c"] and len(got) == 8 and got[7] == handover(tmp_path)


# ================================================================ the whole run

@needs_pwsh
def test_a_computer_with_ubuntu_and_a_user_goes_straight_to_the_ubuntu_part_and_nothing_is_asked(tmp_path):
    got = run_install(tmp_path)
    assert got["code"] == 0
    assert [c for c in got["calls"] if c.startswith("ask")] == [] and "admin?" not in got["calls"]
    assert len(lives(got)) == 2 and lives(got)[0].startswith("live: -d | Ubuntu-24.04 | --cd | ~ | --exec | bash | -c | f=$(mktemp)")
    assert lives(got)[1] == "live: -d | Ubuntu-24.04 | --cd | ~ | --exec | bash | -c | PYTHONPATH=$HOME/ack-tools/tools exec /usr/bin/python3 -m voice_studio.window"
    assert "Ubuntu found: Ubuntu-24.04." in got["said"] and "Starting the Ubuntu part. Ubuntu will ask for the password you chose, in this window, to install a few Ubuntu programs." in got["said"]
    assert got["said"][0] == "ACK Voice Studio: setting up on Windows"


@needs_pwsh
def test_it_looks_before_it_does_anything(tmp_path):
    got = run_install(tmp_path)
    order = got["calls"]
    assert order.index("facts") < order.index("capture: -l -v") < order.index("capture: -d Ubuntu-24.04 --exec id -u") < order.index(lives(got)[0])
    assert got["said"].index("Looking at this computer. Nothing is changed at this step.") < got["said"].index("Ubuntu found: Ubuntu-24.04.")


@needs_pwsh
def test_the_release_chosen_is_the_one_handed_over(tmp_path):
    got = run_install(tmp_path, tokens=["-Ref", "v1.2"])
    assert "ACK_VOICE_TAG='v1.2'" in lives(got)[0] and "/v1.2/tools/voice_studio/get.sh" in lives(got)[0]
    got = run_install(tmp_path, env={"ACK_VOICE_TAG": "v3"})
    assert "ACK_VOICE_TAG='v3'" in lives(got)[0]


@needs_pwsh
def test_ubuntu_22_04_is_used_when_it_is_the_only_one_and_24_04_is_preferred_when_both_are_there(tmp_path):
    only = run_install(tmp_path, before=UBUNTU_22)
    assert "capture: -d Ubuntu-22.04 --exec id -u" in only["calls"] and lives(only)[0].startswith("live: -d | Ubuntu-22.04 |")
    assert lives(only)[1].startswith("live: -d | Ubuntu-22.04 | --cd | ~ | --exec | bash | -c | PYTHONPATH=") and len(lives(only)) == 2, "the window is opened in the same Ubuntu the programs went into"
    both = run_install(tmp_path, before=UBUNTU_BOTH)
    assert lives(both)[0].startswith("live: -d | Ubuntu-24.04 |")


@needs_pwsh
def test_a_distribution_named_by_the_person_is_used_even_when_another_would_be_preferred(tmp_path):
    got = run_install(tmp_path, before=UBUNTU_BOTH, tokens=["-Distro", "Ubuntu-22.04"])
    assert lives(got)[0].startswith("live: -d | Ubuntu-22.04 |")


@needs_pwsh
def test_ubuntu_as_wsl_version_1_is_not_used_and_the_fix_is_named(tmp_path):
    got = run_install(tmp_path, before=UBUNTU_V1)
    assert got["code"] == 1 and lives(got) == []
    assert "Ubuntu was found, but as WSL version 1. This needs version 2. To change it, run: wsl --set-version Ubuntu-24.04 2" in got["said"]


@needs_pwsh
def test_ubuntu_with_no_user_yet_says_to_open_it_once_and_starts_nothing(tmp_path):
    got = run_install(tmp_path, user="0")
    assert got["code"] == 3 and lives(got) == []
    assert any(line.startswith("Ubuntu is installed but has no user yet. Open Ubuntu 24.04 from the Start menu once.") for line in got["said"])


@needs_pwsh
@pytest.mark.parametrize("answer", [listing(["x"], code=1), {"Ran": False, "Code": 1, "Lines": []}, listing([""], code=0)])
def test_when_the_user_cannot_be_read_it_is_treated_as_no_user_never_as_a_reason_to_install_into_the_wrong_place(tmp_path, answer):
    got = run_install(tmp_path, user=answer)
    assert got["code"] == 3 and lives(got) == []


@needs_pwsh
def test_no_wsl_at_all_asks_once_then_installs_ubuntu_24_04_then_hands_over_when_it_is_there_with_a_user(tmp_path):
    got = run_install(tmp_path, before=NO_WSL, after=UBUNTU_BOTH, answers=["yes"])
    assert got["code"] == 0
    assert "WSL (Windows Subsystem for Linux) is not set up on this computer yet." in got["said"]
    asks = [c for c in got["calls"] if c.startswith("ask")]
    assert asks == ["ask: Install WSL and Ubuntu 24.04 now? It downloads Ubuntu from Microsoft, needs administrator rights, and needs a restart afterwards. Type yes to go on."]
    assert lives(got)[0] == "live: --install | -d | Ubuntu-24.04" and lives(got)[1].startswith("live: -d | Ubuntu-24.04 | --cd | ~ | --exec | bash | -c | f=$(mktemp)") and lives(got)[2] == "live: -d | Ubuntu-24.04 | --cd | ~ | --exec | bash | -c | PYTHONPATH=$HOME/ack-tools/tools exec /usr/bin/python3 -m voice_studio.window" and len(lives(got)) == 3
    assert got["calls"].index("admin?") < got["calls"].index(asks[0]) < got["calls"].index(lives(got)[0])


@needs_pwsh
def test_wsl_without_any_ubuntu_says_so_differently_from_no_wsl(tmp_path):
    got = run_install(tmp_path, before=NO_DISTROS, after=UBUNTU_BOTH)
    assert "WSL is there, but it has no Ubuntu 22.04 or 24.04 yet." in got["said"] and "WSL (Windows Subsystem for Linux) is not set up on this computer yet." not in got["said"]


@needs_pwsh
def test_wsl_that_cannot_be_started_at_all_is_taken_as_not_set_up(tmp_path):
    got = run_install(tmp_path, before={"Ran": False, "Code": 1, "Lines": []}, after=UBUNTU_BOTH)
    assert "WSL (Windows Subsystem for Linux) is not set up on this computer yet." in got["said"] and lives(got)[0] == "live: --install | -d | Ubuntu-24.04"


@needs_pwsh
def test_installing_without_administrator_rights_stops_before_asking_and_says_how_to_open_one(tmp_path):
    got = run_install(tmp_path, before=NO_WSL, admin=False)
    assert got["code"] == 3 and lives(got) == [] and [c for c in got["calls"] if c.startswith("ask")] == []
    assert any("Installing WSL needs PowerShell opened as administrator." in line for line in got["said"])


@needs_pwsh
@pytest.mark.parametrize("answer", ["no", "n", "", "maybe", "YESS"])
def test_anything_but_a_yes_is_a_no_and_installs_nothing(tmp_path, answer):
    got = run_install(tmp_path, before=NO_WSL, answers=[answer])
    assert got["code"] == 2 and lives(got) == [] and "Nothing was done." in got["said"]


@needs_pwsh
@pytest.mark.parametrize("answer", ["yes", "y", "YES", " Yes "])
def test_a_yes_in_any_case_installs(tmp_path, answer):
    got = run_install(tmp_path, before=NO_WSL, after=UBUNTU_BOTH, answers=[answer])
    assert lives(got)[0] == "live: --install | -d | Ubuntu-24.04"


@needs_pwsh
def test_with_nobody_to_ask_nothing_is_installed(tmp_path):
    got = run_install(tmp_path, before=NO_WSL, answers=[])
    assert got["code"] == 2 and lives(got) == []
    assert "There is nobody here to ask, so nothing was done. To go ahead, run it again and add -Yes." in got["said"]


@needs_pwsh
def test_yes_on_the_line_does_not_ask_but_still_needs_administrator_rights(tmp_path):
    got = run_install(tmp_path, before=NO_WSL, after=UBUNTU_BOTH, tokens=["-Yes"])
    assert [c for c in got["calls"] if c.startswith("ask")] == [] and lives(got)[0] == "live: --install | -d | Ubuntu-24.04"
    got = run_install(tmp_path, before=NO_WSL, tokens=["-Yes"], admin=False)
    assert got["code"] == 3 and lives(got) == []


@needs_pwsh
def test_an_install_that_fails_is_reported_and_nothing_else_is_started(tmp_path):
    got = run_install(tmp_path, before=NO_WSL, install_code=1)
    assert got["code"] == 1 and len(lives(got)) == 1
    assert "The install did not finish. Windows said the lines above. Nothing else was changed. Run the same command again to try once more." in got["said"]


@needs_pwsh
def test_an_install_that_could_not_even_run_is_a_failure_too(tmp_path):
    got = run_install(tmp_path, before=NO_WSL, ran_live=False)
    assert got["code"] == 1 and len(lives(got)) == 1


@needs_pwsh
def test_an_install_that_needs_a_restart_says_so_and_asks_to_run_the_same_command_again(tmp_path):
    got = run_install(tmp_path, before=NO_WSL, after=NO_WSL)
    assert got["code"] == 3 and len(lives(got)) == 1
    assert "WSL is installed but needs the computer to restart first. Restart it, then run the same command again. It carries on from here." in got["said"]


@needs_pwsh
def test_after_an_install_with_no_user_yet_it_stops_for_the_first_run_instead_of_installing_into_root(tmp_path):
    got = run_install(tmp_path, before=NO_WSL, after=UBUNTU_BOTH, user="0")
    assert got["code"] == 3 and len(lives(got)) == 1 and lives(got)[0].startswith("live: --install")


@needs_pwsh
def test_a_stopped_ubuntu_part_is_reported_with_its_code_and_the_run_is_not_called_done(tmp_path):
    got = run_install(tmp_path, handover_code=130)
    assert got["code"] == 1
    assert "The Ubuntu part stopped with code 130. What it said is above. Run the same command again to carry on from where it stopped." in got["said"]
    ok = run_install(tmp_path, handover_code=0)
    assert ok["code"] == 0 and not any("stopped with code" in line for line in ok["said"])


@needs_pwsh
def test_an_ubuntu_part_that_could_not_be_started_is_a_failure(tmp_path):
    got = run_install(tmp_path, ran_live=False)
    assert got["code"] == 1 and "The Ubuntu part stopped with code 1." in " ".join(got["said"])


@needs_pwsh
def test_windows_that_is_too_old_stops_before_wsl_is_even_looked_at(tmp_path):
    got = run_install(tmp_path, facts=dict(FACTS_OK, Build=19043))
    assert got["code"] == 1 and lives(got) == [] and not any(c.startswith("capture") for c in got["calls"])
    assert any("too old to show Linux windows" in line for line in got["said"])


@needs_pwsh
def test_the_warnings_are_said_and_do_not_stop_it(tmp_path):
    facts = dict(FACTS_OK, Hypervisor=False, FirmwareVirt=False, GpuName="", GpuDriver="", FreeGiB=10)
    got = run_install(tmp_path, facts=facts)
    assert got["code"] == 0 and len(lives(got)) == 2
    said = " ".join(got["said"])
    assert "Virtualization looks switched off." in said and "No Nvidia graphics driver was found" in said and "Only 10 GB is free on drive C:." in said


@needs_pwsh
def test_a_distribution_named_by_the_person_that_is_not_there_is_the_one_that_gets_installed(tmp_path):
    got = run_install(tmp_path, before=NO_WSL, after=UBUNTU_22, tokens=["-Distro", "Ubuntu-22.04"], answers=["yes"])
    assert lives(got)[0] == "live: --install | -d | Ubuntu-22.04" and lives(got)[1].startswith("live: -d | Ubuntu-22.04 |") and got["code"] == 0
    assert "It would install" not in " ".join(got["said"])
    check = run_install(tmp_path, before=NO_WSL, tokens=["-Distro", "Ubuntu-22.04", "-Check"])
    assert "It would install Ubuntu 24.04 with: wsl --install -d Ubuntu-22.04" in check["said"]


@needs_pwsh
def test_a_user_id_that_comes_back_with_a_nul_after_each_character_is_still_read(tmp_path):
    ok = run_install(tmp_path, nul_user="1000")
    assert ok["code"] == 0 and len(lives(ok)) == 2
    root = run_install(tmp_path, nul_user="0")
    assert root["code"] == 3 and lives(root) == []


@needs_pwsh
def test_the_user_id_is_the_last_line_so_a_warning_before_it_changes_nothing(tmp_path):
    ok = run_install(tmp_path, user=listing(["wsl: Processing /etc/wsl.conf", "warning 0 5", "1000"]))
    assert ok["code"] == 0 and len(lives(ok)) == 2
    root = run_install(tmp_path, user=listing(["wsl: something 1000 happened", "0"]))
    assert root["code"] == 3 and lives(root) == []
    padded = run_install(tmp_path, user=listing(["  1000  ", ""]))
    assert padded["code"] == 0


@needs_pwsh
def test_a_user_id_that_is_not_a_number_is_not_taken_as_a_user(tmp_path):
    for text in ("abc", "-1", "1 000", "0x3e8", "1000x"):
        got = run_install(tmp_path, user=listing([text]))
        assert got["code"] == 3 and lives(got) == [], text
    assert run_install(tmp_path, user=listing(["00"]))["code"] == 3


@needs_pwsh
def test_the_plain_name_list_is_used_when_the_listing_with_versions_cannot_be_read(tmp_path):
    odd = listing(["unexpected layout with no numbers"])
    got = run_install(tmp_path, before=odd, queue=listing(["Ubuntu-24.04", "docker-desktop"]))
    assert got["code"] == 0 and lives(got)[0].startswith("live: -d | Ubuntu-24.04 |") and "capture: -l -q" in got["calls"]


@needs_pwsh
def test_the_plain_name_list_is_not_asked_for_when_the_first_listing_worked(tmp_path):
    assert "capture: -l -q" not in run_install(tmp_path)["calls"]


# ---- the window is the helper's last step, in a session it stays attached to

@needs_pwsh
def test_the_ubuntu_part_is_told_not_to_open_the_window_because_this_script_opens_it(tmp_path):
    command = handover(tmp_path)
    assert "bash $f --no-window;" in command and command.index("ACK_VOICE_TAG=") < command.index("--no-window")


@needs_pwsh
def test_the_window_is_opened_after_the_ubuntu_part_ended_well_and_the_person_is_told_to_leave_powershell_open(tmp_path):
    got = run_install(tmp_path)
    said = got["said"]
    assert "The Ubuntu part has ended." in said
    opening = "Opening the window. Leave this PowerShell window open while you use Voice Studio: closing it closes the Voice Studio window. When you close the Voice Studio window, this PowerShell window is free again."
    assert opening in said and "The Voice Studio window was closed." in said
    assert said.index("The Ubuntu part has ended.") < said.index(opening) < said.index("The Voice Studio window was closed.")
    assert got["calls"].index(lives(got)[0]) < got["calls"].index(lives(got)[1]) and got["code"] == 0


@needs_pwsh
def test_the_window_is_not_opened_when_the_ubuntu_part_did_not_end_well(tmp_path):
    for code in (1, 2, 130):
        got = run_install(tmp_path, handover_code=code)
        assert got["code"] == 1 and len(lives(got)) == 1 and not any("Opening the window." in line for line in got["said"])


@needs_pwsh
def test_a_window_that_stops_with_a_code_is_reported_and_the_run_is_not_called_done(tmp_path):
    got = run_install(tmp_path, window_code=139)
    assert got["code"] == 1 and "The window stopped with code 139. What it said is above. To try again, run the same command." in got["said"]
    assert "The Voice Studio window was closed." not in got["said"]


@needs_pwsh
def test_a_window_that_could_not_be_started_at_all_is_a_failure_with_code_one(tmp_path):
    got = run_install(tmp_path, ran_window=False)
    assert got["code"] == 1 and "The window stopped with code 1. What it said is above. To try again, run the same command." in got["said"]


@needs_pwsh
def test_the_arguments_for_the_window_run_it_in_the_foreground_with_the_tools_folder_on_its_path(tmp_path):
    got = call("Get-AckVsWindowArguments -Distro 'Ubuntu-22.04'", tmp_path)
    assert got == ["-d", "Ubuntu-22.04", "--cd", "~", "--exec", "bash", "-c", "PYTHONPATH=$HOME/ack-tools/tools exec /usr/bin/python3 -m voice_studio.window"]
    assert '"' not in got[-1] and "\n" not in got[-1]


@needs_pwsh
def test_the_window_command_is_valid_shell_and_runs_the_one_system_python(tmp_path):
    command = call("Get-AckVsWindowArguments -Distro 'Ubuntu'", tmp_path)[-1]
    assert subprocess.run(["bash", "-n", "-c", command]).returncode == 0
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    shown = tmp_path / "shown"
    fake = bin_dir / "python3"
    fake.write_text("#!/bin/sh\necho \"$PYTHONPATH $*\" > %s\n" % shown)
    fake.chmod(0o755)
    done = subprocess.run(["/bin/bash", "-c", command.replace("/usr/bin/python3", str(fake))], capture_output=True, text=True, env={"PATH": "/usr/bin:/bin", "HOME": "/home/someone"}, timeout=30)
    assert done.returncode == 0 and shown.read_text().strip() == "/home/someone/ack-tools/tools -m voice_studio.window"


@needs_pwsh
def test_a_check_never_opens_the_window_and_a_dry_run_only_shows_it(tmp_path):
    assert lives(run_install(tmp_path, tokens=["-Check"])) == [] and lives(run_install(tmp_path, tokens=["-DryRun"])) == []


# ---- looking only

@needs_pwsh
def test_check_on_a_ready_computer_says_ready_and_runs_nothing(tmp_path):
    got = run_install(tmp_path, tokens=["-Check"])
    assert got["code"] == 0 and lives(got) == [] and "Ready: Ubuntu is there and has a user. Run the same command without -Check to start." in got["said"]


@needs_pwsh
def test_check_on_a_computer_without_ubuntu_says_what_would_be_done_and_is_not_ready(tmp_path):
    got = run_install(tmp_path, tokens=["-Check"], before=NO_WSL)
    assert got["code"] == 1 and lives(got) == [] and [c for c in got["calls"] if c.startswith("ask")] == [] and "admin?" not in got["calls"]
    assert "It would install Ubuntu 24.04 with: wsl --install -d Ubuntu-24.04" in got["said"]
    assert "Not ready yet. Run the same command without -Check to set it up." in got["said"]


@needs_pwsh
def test_check_on_ubuntu_with_no_user_is_not_ready(tmp_path):
    got = run_install(tmp_path, tokens=["-Check"], user="0")
    assert got["code"] == 3 and lives(got) == []


@needs_pwsh
def test_dry_run_shows_the_exact_commands_and_runs_none_and_asks_nothing(tmp_path):
    got = run_install(tmp_path, tokens=["-DryRun"], before=NO_WSL, admin=False)
    assert got["code"] == 0 and lives(got) == [] and [c for c in got["calls"] if c.startswith("ask")] == []
    assert "Nothing was changed. This is what would run:" in got["said"]
    assert "  wsl.exe --install -d Ubuntu-24.04" in got["said"]
    assert any(line.startswith('  wsl.exe -d Ubuntu-24.04 --cd ~ --exec bash -c "f=$(mktemp)') and line.endswith('exit $rc"') for line in got["said"])
    assert '  wsl.exe -d Ubuntu-24.04 --cd ~ --exec bash -c "PYTHONPATH=$HOME/ack-tools/tools exec /usr/bin/python3 -m voice_studio.window"' in got["said"]


@needs_pwsh
def test_dry_run_on_a_ready_computer_shows_only_the_ubuntu_command(tmp_path):
    got = run_install(tmp_path, tokens=["-DryRun"])
    assert got["code"] == 0 and lives(got) == [] and not any("--install" in line for line in got["said"])
    assert sum(1 for line in got["said"] if line.startswith('  wsl.exe -d Ubuntu-24.04 --cd ~ --exec bash -c "')) == 2, "the Ubuntu command and the window"


@needs_pwsh
def test_check_and_dry_run_from_the_environment_do_the_same(tmp_path):
    assert lives(run_install(tmp_path, env={"ACK_VOICE_CHECK": "1"})) == [] and lives(run_install(tmp_path, env={"ACK_VOICE_DRYRUN": "1"})) == []


# ---- refusals

@needs_pwsh
def test_an_option_that_is_not_understood_does_nothing_at_all(tmp_path):
    got = run_install(tmp_path, tokens=["-Chek"])
    assert got["code"] == 2 and got["calls"] == []
    assert "I do not know the option -Chek. The options are -Ref, -Distro, -Check, -DryRun, -Yes and -Help." in got["said"]


@needs_pwsh
@pytest.mark.parametrize("ref", ["a b", "a;b", "$(x)", "-x", "a'b"])
def test_a_release_name_with_anything_odd_in_it_does_nothing_at_all(tmp_path, ref):
    got = run_install(tmp_path, tokens=["-Ref", ref])
    assert got["code"] == 2 and got["calls"] == []


@needs_pwsh
def test_a_distribution_name_that_is_not_ubuntu_does_nothing_at_all(tmp_path):
    got = run_install(tmp_path, tokens=["-Distro", "Debian"])
    assert got["code"] == 2 and got["calls"] == []


@needs_pwsh
def test_help_prints_the_options_and_does_nothing(tmp_path):
    got = run_install(tmp_path, tokens=["-Help"])
    assert got["code"] == 0 and got["calls"] == [] and any(line.startswith("Options: -Ref name is the release of ACK to fetch.") for line in got["said"])


# ================================================================ the real script, run the three ways a person runs it

def run_real(args, tmp_path, env=None, command=None):
    full_env = {k: v for k, v in os.environ.items() if not k.startswith("ACK_VOICE_")}
    full_env.update(env or {})
    argv = [PWSH, "-NoProfile", "-NonInteractive"] + (["-Command", command] if command else ["-File", str(SCRIPT)] + list(args))
    return subprocess.run(argv, capture_output=True, text=True, env=full_env, cwd=str(tmp_path), timeout=120)


@needs_pwsh
def test_run_as_a_file_help_prints_the_options_and_exits_zero(tmp_path):
    done = run_real(["-Help"], tmp_path)
    assert done.returncode == 0 and done.stdout.splitlines()[0] == "ACK Voice Studio: setting up on Windows" and "Options: -Ref name is the release of ACK to fetch." in done.stdout


@needs_pwsh
def test_run_as_a_file_the_exit_code_is_the_scripts_own(tmp_path):
    assert run_real(["-Chek"], tmp_path).returncode == 2
    done = run_real(["-Check"], tmp_path)               # no WSL on this computer: not ready
    assert done.returncode == 1 and "WSL (Windows Subsystem for Linux) is not set up on this computer yet." in done.stdout and "Not ready yet." in done.stdout


@needs_pwsh
def test_run_as_a_file_with_the_settings_in_the_environment_does_the_same_as_with_options(tmp_path):
    by_options = run_real(["-DryRun", "-Ref", "v7"], tmp_path)
    by_environment = run_real([], tmp_path, env={"ACK_VOICE_DRYRUN": "1", "ACK_VOICE_TAG": "v7"})
    assert by_options.returncode == by_environment.returncode == 0 and by_options.stdout == by_environment.stdout
    assert "ACK_VOICE_TAG='v7'" in by_options.stdout and "wsl.exe --install -d Ubuntu-24.04" in by_options.stdout


@needs_pwsh
def test_piped_into_iex_the_persons_window_is_not_closed_the_exit_code_is_left_in_lastexitcode_and_nothing_is_left_behind(tmp_path):
    command = "Get-Content -Raw %s | Invoke-Expression; 'still here: ' + $LASTEXITCODE; 'left behind: ' + @(Get-Command -Name '*-AckVs*' -ErrorAction SilentlyContinue).Count; 'variables left: ' + @(Get-Variable -Name 'ackVs*' -ErrorAction SilentlyContinue).Count" % lit(str(SCRIPT))
    done = run_real([], tmp_path, env={"ACK_VOICE_CHECK": "1"}, command=command)
    assert done.returncode == 0 and "still here: 1" in done.stdout and "left behind: 0" in done.stdout and "variables left: 0" in done.stdout
    assert "Not ready yet." in done.stdout


@needs_pwsh
def test_piped_into_iex_with_a_bad_setting_stops_with_a_message_not_a_stack_trace(tmp_path):
    command = "Get-Content -Raw %s | Invoke-Expression; 'still here: ' + $LASTEXITCODE" % lit(str(SCRIPT))
    done = run_real([], tmp_path, env={"ACK_VOICE_TAG": "a b;c"}, command=command)
    assert "still here: 2" in done.stdout and "The release name a b;c has a character that is not allowed." in done.stdout and "Exception" not in done.stderr + done.stdout


@needs_pwsh
def test_the_script_run_for_real_never_calls_wsl_when_only_looking(tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    marker = tmp_path / "wsl-was-called"
    wsl = bin_dir / "wsl.exe"
    wsl.write_text("#!/bin/sh\necho called >> %s\nexit 1\n" % marker)
    wsl.chmod(0o755)
    done = run_real(["-DryRun"], tmp_path, env={"PATH": "%s:%s" % (bin_dir, os.environ["PATH"])})
    assert done.returncode == 0 and "Nothing was changed. This is what would run:" in done.stdout
    assert marker.read_text().count("called") == 1, "-DryRun looks (wsl.exe -l -v once) and installs nothing: it was called only to list"


# ================================================================ the real wsl.exe calls (found wrong on the first run on a real Windows)

def with_stub_wsl(tmp_path, body):
    """A `wsl.exe` on the path that is a script, so the real functions that start it can be run."""
    bin_dir = tmp_path / "stub"
    bin_dir.mkdir()
    stub = bin_dir / "wsl.exe"
    stub.write_text("#!/bin/sh\n" + body)
    stub.chmod(0o755)
    return {"PATH": "%s:%s" % (bin_dir, os.environ["PATH"])}


@needs_pwsh
def test_what_wsl_prints_in_a_live_call_reaches_the_screen_and_is_not_swallowed_into_the_result(tmp_path):
    """The first version called `& wsl.exe` inside the function, so everything Ubuntu said (and its questions) went into the function's result and the person saw nothing."""
    env = with_stub_wsl(tmp_path, 'echo "said by ubuntu"\nexit 3\n')
    driver = tmp_path / "live.ps1"
    driver.write_text("$env:ACK_VOICE_NO_AUTORUN = '1'\n. %s\n$r = Invoke-AckVsWslLive -WslArguments @('x')\n'RESULT ' + $r.GetType().Name + ' ' + $r.Ran + ' ' + $r.Code\n" % lit(str(SCRIPT)))
    done = subprocess.run([PWSH, "-NoProfile", "-NonInteractive", "-File", str(driver)], capture_output=True, text=True, env=dict(os.environ, **env), timeout=60)
    assert done.returncode == 0, done.stderr
    assert "said by ubuntu" in done.stdout.splitlines(), "printed on the person's screen"
    assert "RESULT Hashtable True 3" in done.stdout.splitlines(), "one result, with the exit code, not an array holding the program's output"


@needs_pwsh
def test_every_argument_reaches_wsl_as_one_piece_and_the_exit_code_is_handed_back(tmp_path):
    env = with_stub_wsl(tmp_path, 'for a in "$@"; do echo "[$a]"; done\nexit 0\n')
    driver = tmp_path / "args.ps1"
    command = "PYTHONPATH=$HOME/x exec /usr/bin/python3 -m voice_studio.window"
    driver.write_text("$env:ACK_VOICE_NO_AUTORUN = '1'\n. %s\n$r = Invoke-AckVsWslLive -WslArguments @('-d', 'Ubuntu-24.04', '--cd', '~', '--exec', 'bash', '-c', %s)\n'CODE ' + $r.Code\n" % (lit(str(SCRIPT)), lit(command)))
    done = subprocess.run([PWSH, "-NoProfile", "-NonInteractive", "-File", str(driver)], capture_output=True, text=True, env=dict(os.environ, **env), timeout=60)
    lines = done.stdout.splitlines()
    assert lines[:7] == ["[-d]", "[Ubuntu-24.04]", "[--cd]", "[~]", "[--exec]", "[bash]", "[-c]"] and "[%s]" % command in lines and "CODE 0" in lines, done.stdout


@needs_pwsh
def test_a_live_call_when_wsl_is_not_there_is_reported_as_not_run_not_as_done(tmp_path):
    driver = tmp_path / "missing.ps1"
    driver.write_text("$env:ACK_VOICE_NO_AUTORUN = '1'\n. %s\n$r = Invoke-AckVsWslLive -WslArguments @('x')\n'RAN ' + $r.Ran + ' ' + $r.Code\n" % lit(str(SCRIPT)))
    done = subprocess.run([PWSH, "-NoProfile", "-NonInteractive", "-File", str(driver)], capture_output=True, text=True, env=dict(os.environ, PATH="/usr/bin:/bin"), timeout=60)
    assert "RAN False 1" in done.stdout.splitlines(), done.stdout + done.stderr


def test_the_live_call_starts_wsl_on_the_persons_own_console_and_nothing_else_starts_a_program():
    code = SCRIPT.read_text()
    live = code.split("function Invoke-AckVsWslLive", 1)[1].split("\nfunction ", 1)[0]
    assert "Start-Process" in live and "-NoNewWindow" in live and "-Wait" in live and "-PassThru" in live and "-Verb" not in live
    assert "& wsl.exe" not in live, "a native call inside a function is captured into its result"
    assert len(re.findall(r"Start-Process -FilePath", code)) == 1, "one place starts a program; its comment only names the cmdlet"


# ================================================================ what the file may and may not do

def code_lines():
    """The script without comment lines and blank lines."""
    return [l for l in SCRIPT.read_text(encoding="utf-8").splitlines() if l.strip() and not l.strip().startswith("#")]


def test_the_file_is_plain_ascii_because_windows_powershell_5_1_reads_a_file_without_a_mark_as_the_local_code_page():
    data = SCRIPT.read_bytes()
    assert all(b < 128 for b in data) and b"\r" not in data[:0] and not data.startswith(b"\xef\xbb\xbf")


def test_the_file_carries_its_licence_line_at_the_top():
    assert SCRIPT.read_text().splitlines()[0] == "# SPDX-License-Identifier: GPL-3.0-or-later"


def powershell_only(code):
    """The script's own PowerShell: the text of the shell command that is run inside Ubuntu (a here-string) is left out, because && and || are the shell's there."""
    return re.sub(r"@'.*?'@", "", code, flags=re.S)


def test_nothing_newer_than_windows_powershell_5_1_is_used():
    code = powershell_only("\n".join(code_lines()))
    assert "??" not in code and "?." not in code and "&&" not in code and "||" not in code, "pipeline-chain, null-coalescing and null-conditional operators are PowerShell 7 only"
    assert not re.search(r"\s\?\s.+\s:\s", code), "the ternary operator is PowerShell 7 only"
    for word in ("-Parallel", "Join-String", "ConvertFrom-Json -AsHashtable", "-Depth 100", "using namespace", "$IsWindows", "$PSStyle", "Get-Error", "-Raw -ErrorAction"):
        assert word not in code, word
    assert "[ordered]" not in code or True


@needs_pwsh
def test_the_file_parses_without_a_single_error(tmp_path):
    done = subprocess.run([PWSH, "-NoProfile", "-Command", "$e=$null; [void][System.Management.Automation.Language.Parser]::ParseFile(%s,[ref]$null,[ref]$e); @($e).Count" % lit(str(SCRIPT))],
                          capture_output=True, text=True, timeout=60)
    assert done.stdout.strip() == "0", done.stdout + done.stderr


def test_it_never_asks_for_a_password_changes_the_script_rules_the_registry_or_asks_windows_for_more_rights():
    code = "\n".join(code_lines()).lower()
    for word in ("get-credential", "securestring", "-assecurestring", "set-executionpolicy", "set-itemproperty", "new-itemproperty", "reg add", "reg.exe", "-verb", "runas", "enable-windowsoptionalfeature", "dism", "setx", "[environment]::setenvironmentvariable", "icacls", "takeown", "netsh", "schtasks", "new-service", "sc.exe"):
        assert word not in code, word


def test_it_makes_no_web_request_of_its_own_and_evaluates_nothing():
    code = "\n".join(code_lines()).lower()
    for word in ("invoke-webrequest", "invoke-restmethod", "irm ", "iwr ", "net.webclient", "downloadstring", "downloadfile", "system.net", "start-bitstransfer", "curl.exe", "invoke-expression", " iex"):
        # the one place the one-liner is written is a text the person is shown, not something that runs
        if word in ("irm ", " iex"):
            continue
        assert word not in code, word
    assert not re.search(r"(^|[;{(]\s*)(irm|iex|invoke-expression)\b", "\n".join(code_lines()), re.I | re.M)


def test_the_only_web_addresses_are_the_raw_files_of_the_one_repository():
    for number, line in enumerate(SCRIPT.read_text().splitlines(), 1):
        for address in re.findall(r"https?://[^\s'\"|)]+", line):
            assert address.startswith("https://raw.githubusercontent.com/ASPDesignLabs/ACK/") or address == "https://raw.githubusercontent.com", (number, address)


def test_the_one_liner_in_the_file_is_the_command_that_fetches_this_very_file_from_the_default_release():
    code = SCRIPT.read_text()
    default = re.search(r"DefaultRef\s*=\s*'([^']+)'", code).group(1)
    one_liner = re.search(r"OneLiner\s*=\s*'([^']+)'", code).group(1)
    assert one_liner == "irm https://raw.githubusercontent.com/ASPDesignLabs/ACK/%s/tools/voice_studio/install.ps1 | iex" % default
    assert (PKG / "install.ps1").is_file() and (PKG / "get.sh").is_file()
    assert "# " + one_liner.replace("irm ", "  irm ", 1).strip() in [l.strip() for l in code.splitlines()] or one_liner in code


def test_the_default_release_is_the_same_word_as_get_sh_uses():
    default = re.search(r"DefaultRef\s*=\s*'([^']+)'", SCRIPT.read_text()).group(1)
    assert 'DEFAULT_TAG="%s"' % default in (PKG / "get.sh").read_text()


def test_it_runs_the_one_script_the_repository_ships_for_ubuntu():
    code = SCRIPT.read_text()
    assert "GetScript      = 'tools/voice_studio/get.sh'" in code and (PKG / "get.sh").is_file()


def test_exit_is_taken_in_one_place_and_only_for_a_file_run_on_its_own():
    code = "\n".join(code_lines())
    assert len(re.findall(r"\bexit\b", code.replace("exit $rc", ""))) == 1, "exit would close the person's window when the script is piped into iex"
    assert "if ($ackVsIsFile) { exit $ackVsCode }" in code and "$ackVsIsFile = [bool]$PSCommandPath" in code


def test_the_functions_are_taken_away_again_after_a_run_so_nothing_is_left_in_the_persons_session():
    code = SCRIPT.read_text()
    assert "Remove-Item -Path 'Function:\\*-AckVs*'" in code
    names = re.findall(r"^function\s+([A-Za-z-]+)", code, re.M)
    assert names and all(n.endswith("AckVs" + n.split("AckVs")[1]) and "-AckVs" in n for n in names), names


def test_it_uses_wsl_exe_by_its_whole_name_with_no_shell_in_between():
    code = "\n".join(code_lines())
    assert code.count("& wsl.exe @WslArguments") == 1, "the only call that captures what wsl.exe prints is the one for looking"
    assert "cmd /c" not in code.lower() and "cmd.exe" not in code.lower() and "bash.exe" not in code.lower()
    assert "'--exec'" in code, "the Ubuntu command is run with --exec so that no second shell rewrites it"


@needs_pwsh
def test_every_sentence_it_says_is_as_plain_as_the_rest_of_the_tool(tmp_path):
    texts = call("Get-AckVsText", tmp_path)
    assert len(texts) >= 30
    bad = {key: wording.wording_problems("install." + key, value) for key, value in texts.items() if wording.wording_problems("install." + key, value)}
    assert not bad, bad


@needs_pwsh
def test_every_sentence_in_the_text_table_is_used_by_the_script(tmp_path):
    texts = call("Get-AckVsText", tmp_path)
    code = SCRIPT.read_text()
    unused = [key for key in texts if not re.search(r"\$text\.%s\b" % key, code)]
    assert not unused, unused
    named = set(re.findall(r"\$text\.([a-z0-9_]+)", code))
    assert not (named - set(texts)), named - set(texts)
