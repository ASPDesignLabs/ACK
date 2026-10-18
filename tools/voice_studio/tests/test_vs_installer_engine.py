# SPDX-License-Identifier: GPL-3.0-or-later
"""The setup wizard's Windows-side engine (`installer/engine.ps1`, plan decision D44, choices P28): one step per run, called hidden by the wizard.

Held to: every step is walked with stand-ins for wsl.exe, the permission question and the facts about the computer (PowerShell itself runs them: set ACK_VS_PWSH or have `pwsh` on the path;
skipped otherwise): Windows 10 stops it before it touches WSL, no WSL, WSL without Ubuntu, an Ubuntu with an account and one without, the permission refused, a restart, an install that fails.
**The password** is held to the strongest checks here: it is refused unless it is printable ASCII of 8 to 128 characters, it reaches Ubuntu on the standard input of one command and nowhere else (a
real process is started and its bytes are compared), it is in no argument list, no printed line and no log, an existing account's password is never changed, and the environment variable it came in is
removed. The two shell commands that change files in Ubuntu (the default account, the install-time permission) are run for real, against temporary files. The rest is read from the file: plain ASCII,
no syntax newer than 5.1, no web request, no console prompt, no change to the execution policy or the registry. What no test here can show: that it works on a real Windows (checklist section I18).
"""
import json
import os
import re
import stat
import subprocess
from pathlib import Path

import pytest

from test_vs_install_ps1 import PWSH, lit, needs_pwsh

PKG = Path(__file__).resolve().parents[1]
ENGINE = PKG / "installer" / "engine.ps1"
INSTALL_PS1 = PKG / "install.ps1"
PASSWORD = "Correct-Horse_9!"
FACTS_OK = {"Build": 22631, "Is64": True, "Hypervisor": True, "FirmwareVirt": False, "GpuName": "NVIDIA GeForce RTX 4060", "GpuDriver": "560.94", "FreeGiB": 200, "Drive": "C:"}
LISTING = ["  NAME            STATE           VERSION", "* Ubuntu-24.04    Running         2"]
PASSWD_ROOT_ONLY = ["root:x:0:0:root:/root:/bin/bash", "daemon:x:1:1:daemon:/usr/sbin:/usr/sbin/nologin", "nobody:x:65534:65534:nobody:/nonexistent:/usr/sbin/nologin"]
PASSWD_ANNA = PASSWD_ROOT_ONLY + ["anna:x:1000:1000:Anna,,,:/home/anna:/bin/bash"]


def run_ps(body, tmp_path, env=None):
    driver = tmp_path / "driver.ps1"
    driver.write_text("$ErrorActionPreference = 'Stop'\n$env:ACK_VOICE_NO_AUTORUN = '1'\n$env:ACK_VS_ENGINE_LOG = %s\n$env:ACK_VS_ENGINE_STATE = %s\n. %s\n%s\n"
                      % (lit(str(tmp_path / "engine.log")), lit(str(tmp_path / "state.ini")), lit(str(ENGINE)), body), encoding="utf-8")
    done = subprocess.run([PWSH, "-NoProfile", "-NonInteractive", "-File", str(driver)], capture_output=True, text=True, timeout=180, env=dict(os.environ, **(env or {})))
    assert done.returncode == 0, done.stdout[-1500:] + done.stderr[-1500:]
    return json.loads(done.stdout.strip().splitlines()[-1])


def call(expression, tmp_path, env=None):
    return run_ps("ConvertTo-Json -InputObject (%s) -Depth 6 -Compress" % expression, tmp_path, env)


# A stand-in for wsl.exe: `replies` maps the joined arguments (or a fragment of them) to a reply; everything else answers "ran, code 0, no lines".
PRELUDE = """
$said = New-Object System.Collections.ArrayList
$calls = New-Object System.Collections.ArrayList
$elevated = New-Object System.Collections.ArrayList
$events = New-Object System.Collections.ArrayList
$files = @{}
$say = { param($line) [void]$said.Add([string]$line) }
$replies = %(replies)s
$wsl = { param($r)
    $key = (@($r.Arguments) -join ' ')
    [void]$calls.Add(@{ Arguments = @($r.Arguments); Input = $r.Input; Key = $key })
    [void]$events.Add('wsl: ' + $key)
    foreach ($fragment in $replies.Keys) { if ($key -like ('*' + $fragment + '*')) { return $replies[$fragment] } }
    return @{ Ran = $true; Code = 0; Lines = @() }
}
$elevate = { param($r) [void]$elevated.Add($r); [void]$events.Add('elevate'); return %(elevate)s }
$getFacts = { %(facts)s }
$fileExists = { param($p) [void]$events.Add('exists? ' + $p); return $files.ContainsKey($p) }
$writeFile = { param($p, $t) [void]$events.Add('write ' + $p); $files[$p] = $t }
$removeFile = { param($p) [void]$events.Add('remove ' + $p); $files.Remove($p) }
$findProgram = { param($n) [void]$events.Add('find ' + $n); return %(found)s }
$runProgram = { param($r) [void]$events.Add('run ' + $r.Program + ' ' + $r.ArgumentLine); return %(program)s }
$started = New-Object System.Collections.ArrayList
$start = { param($r) [void]$started.Add($r); return @{ Ran = $true; Code = 0 } }
"""


def profile_of(tmp_path):
    return str(tmp_path / "profile")


def user_data_of(tmp_path, name="Ubuntu-24.04"):
    """Where the first-start account file goes: the person's profile folder, then `.cloud-init`, then a file named for the Ubuntu."""
    return str(tmp_path / "profile" / ".cloud-init" / (name + ".user-data"))


def table(mapping):
    """A PowerShell hashtable whose keys are quoted (the keys here are command lines, which are not names)."""
    return "@{" + "; ".join("%s = %s" % (lit(str(k)), lit(v)) for k, v in mapping.items()) + "}"


def engine(tmp_path, step, *, replies=None, elevate=None, facts=None, found="''", program=None, files=None, extra="", options="", password=None, env=None, boot=None, state=None):
    """Run Invoke-AckVsEngine for one step with the stand-ins above; returns the code, what it said, every wsl request, and the other events. `boot` is when Windows "started" (the stand-in
    for the boot stamp); `state` is what an earlier run left (written to the state file first)."""
    if state is not None:
        (tmp_path / "state.ini").write_text("".join("%s=%s\r\n" % kv for kv in state.items()), encoding="ascii")
    elevate = elevate or {"Ran": True, "Code": 0, "Declined": False}
    program = program or {"Ran": True, "Code": 0, "Lines": []}
    body = PRELUDE % {"replies": table(replies or {}), "elevate": lit(elevate), "facts": lit(facts or FACTS_OK), "found": found, "program": lit(program)}
    for path, text in (files or {}).items():
        body += "$files[%s] = %s\n" % (lit(path), lit(text))
    body += extra
    pw = "-Password %s" % lit(password) if password is not None else ""
    body += """
$code = @(Invoke-AckVsEngine -Step %(step)s %(options)s %(pw)s -Say $say -Wsl $wsl -Elevate $elevate -Start $start -GetFacts $getFacts -FileExists $fileExists -WriteFile $writeFile -RemoveFile $removeFile -FindProgram $findProgram -RunProgram $runProgram -ProfileFolder %(profile)s %(boot)s)[-1]
ConvertTo-Json -InputObject @{ code = $code; said = @($said); calls = @($calls); elevated = @($elevated); events = @($events); files = @($files.Keys); started = @($started) } -Depth 8 -Compress
""" % {"step": lit(step), "options": options, "pw": pw, "profile": lit(profile_of(tmp_path)), "boot": ("-BootStamp { return %s }" % lit(boot)) if boot is not None else ""}
    return run_ps(body, tmp_path, env)


def reply(lines=(), code=0, ran=True):
    return {"Ran": ran, "Code": code, "Lines": list(lines)}


def no_wsl(first="Windows Subsystem for Linux is not installed."):
    """WSL answers none of the three questions the engine asks (`wsl -l -v`, `wsl --status`, `wsl --version`)."""
    return {"-l -v": reply([first], code=1), "--status": reply([], code=1), "--version": reply([], code=1)}


def state_of(tmp_path):
    path = tmp_path / "state.ini"
    if not path.exists():
        return {}
    return dict(line.split("=", 1) for line in path.read_text(encoding="ascii").splitlines() if "=" in line)


def args_of(result):
    return [c["Key"] for c in result["calls"]]


def doing(result):
    """The wsl requests that are not just looking at the list of Ubuntus."""
    return [k for k in args_of(result) if k not in ("-l -v", "-l -q")]


# ================================================================ what may be typed

@needs_pwsh
@pytest.mark.parametrize("name, ok", [("anna", True), ("a", True), ("_x", True), ("a_b-c1", True), ("a" * 31, True), ("a" * 32, False), ("", False), ("Anna", False), ("1abc", False),
                                      ("-abc", False), ("an na", False), ("an:na", False), ("an\nna", False), ("anna\n", False), ("ännä", False), ("root", False), ("ubuntu", False),
                                      ("daemon", False), ("systemd-foo", False), ("nobody", False)])
def test_an_ubuntu_account_name_is_a_plain_lower_case_name_that_ubuntu_does_not_already_use(tmp_path, name, ok):
    assert call("Test-AckVsEngUser -Name %s" % lit(name), tmp_path) is ok


@needs_pwsh
@pytest.mark.parametrize("password, ok", [("abcdefgh", True), ("a" * 128, True), ("a" * 129, False), ("a" * 7, False), ("", False), (" " * 8, True), ("pass word 1", True), ("with:colon1", True),
                                          ("tab\tinside1", False), ("line\nbreak1", False), ("cr\rreturn1", False), ("accent\u00e9abc", False), ("emoji\U0001F600abc", False), ("nul\x00abc12", False),
                                          ("del\x7fabcdef", False), ("~tilde-ok!", True)])
def test_a_password_is_printable_ascii_of_8_to_128_characters_and_nothing_else(tmp_path, password, ok):
    # the NUL cannot travel through a PowerShell literal in a file, so it is built inside PowerShell
    expression = "Test-AckVsEngPassword -Password ('nul' + [string][char]0 + 'abc12')" if "\x00" in password else "Test-AckVsEngPassword -Password %s" % lit(password)
    assert call(expression, tmp_path) is ok


@needs_pwsh
def test_no_password_at_all_is_refused(tmp_path):
    assert call("Test-AckVsEngPassword -Password $null", tmp_path) is False


@needs_pwsh
@pytest.mark.parametrize("path, ok", [("", True), ("C:\\Users\\anna\\AppData\\Local\\Temp\\r.ini", True), ("a\nb", False), ("a\rb", False), ("x" * 241, False), ("x" * 240, True)])
def test_a_result_file_path_with_a_line_break_or_an_absurd_length_is_refused(tmp_path, path, ok):
    assert call("Test-AckVsEngResultPath -Path %s" % lit(path), tmp_path) is ok


# ================================================================ lines, log, result file

@needs_pwsh
@pytest.mark.parametrize("raw, shown", [("plain", "plain"), ("trailing   ", "trailing"), ("a\rb", "ab"), ("caf\u00e9", "caf?"), ("dots\u2026", "dots?"), ("", ""), ("\x1b[31;1mred\x1b[0m", "red"),
                                        ("\x1b[?25lhidden\x1b[?25h", "hidden")])
def test_a_line_is_cleaned_for_the_wizard(tmp_path, raw, shown):
    assert call("ConvertTo-AckVsEngLine -Raw %s" % lit(raw), tmp_path) == shown


@needs_pwsh
def test_the_nul_between_the_letters_of_wsl_s_utf_16_text_is_taken_out_and_a_long_line_is_cut(tmp_path):
    assert call("ConvertTo-AckVsEngLine -Raw (('Ubuntu'.ToCharArray() | ForEach-Object { [string]$_ + [string][char]0 }) -join '')", tmp_path) == "Ubuntu"
    assert len(call("ConvertTo-AckVsEngLine -Raw ('x' * 1000)", tmp_path)) == 400
    assert call("ConvertTo-AckVsEngLine -Raw $null", tmp_path) == ""


@needs_pwsh
def test_the_result_file_is_ascii_with_windows_line_ends_and_sorted_keys(tmp_path):
    target = tmp_path / "r.ini"
    run_ps("Write-AckVsEngResult -Path %s -Values @{ zeta = 1; alpha = 'caf\u00e9'; stop = 0 } -Lines @('ok|first', 'warn|se\u00e7ond'); 'null' | ConvertTo-Json" % lit(str(target)), tmp_path)
    raw = target.read_bytes()
    assert raw == b"[result]\r\nalpha=caf?\r\nstop=0\r\nzeta=1\r\n[lines]\r\n1=ok|first\r\n2=warn|se?ond\r\ncount=2\r\n"


@needs_pwsh
def test_without_a_result_path_nothing_is_written(tmp_path):
    run_ps("Write-AckVsEngResult -Path '' -Values @{ a = 1 } -Lines @(); 'null' | ConvertTo-Json", tmp_path)
    assert not [p for p in tmp_path.iterdir() if p.name.endswith(".ini")]


@needs_pwsh
def test_the_log_keeps_what_happened_and_never_the_password(tmp_path):
    log = tmp_path / "engine.log"
    run_ps("$env:ACK_VS_PASSWORD = %s\nWrite-AckVsEngLog -Step 'user' -Message ('chpasswd said ' + %s + ' and caf\u00e9')\nWrite-AckVsEngLog -Step 'platform' -Message 'fine'\n'null' | ConvertTo-Json" % (lit(PASSWORD), lit(PASSWORD)),
           tmp_path)
    body = log.read_text(encoding="ascii")
    assert PASSWORD not in body and "chpasswd said *** and caf?" in body and re.search(r"^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d platform fine$", body, re.M)


@needs_pwsh
def test_a_log_that_has_grown_past_its_limit_is_set_aside_not_deleted(tmp_path):
    log = tmp_path / "engine.log"
    log.write_text("x" * 1048577, encoding="ascii")
    run_ps("Write-AckVsEngLog -Step 'check' -Message 'again'\n'null' | ConvertTo-Json", tmp_path)
    assert (tmp_path / "engine.log.old").read_text(encoding="ascii") == "x" * 1048577 and "again" in log.read_text(encoding="ascii")


# ================================================================ a real process: the password's road

def fake_program(tmp_path, body):
    program = tmp_path / "fake-wsl"
    program.write_text("#!/bin/bash\n" + body)
    program.chmod(program.stat().st_mode | stat.S_IXUSR)
    return program


@needs_pwsh
def test_the_input_reaches_the_program_byte_for_byte_and_the_arguments_hold_none_of_it(tmp_path):
    program = fake_program(tmp_path, 'printf "%s\\n" "$@" > ' + str(tmp_path / "argv") + '\ncat > ' + str(tmp_path / "stdin") + '\necho done\n')
    got = call("Invoke-AckVsEngProcess -Program %s -ArgumentLine '-d Ubuntu-24.04 -u root --exec chpasswd' -InputText %s -TimeoutSec 30" % (lit(str(program)), lit("anna:" + PASSWORD + "\n")), tmp_path)
    assert got["Ran"] and got["Code"] == 0 and got["Lines"] == ["done"]
    assert (tmp_path / "stdin").read_bytes() == ("anna:" + PASSWORD + "\n").encode("ascii")           # no carriage return, no byte order mark
    assert PASSWORD not in (tmp_path / "argv").read_text()
    assert (tmp_path / "argv").read_text().split() == ["-d", "Ubuntu-24.04", "-u", "root", "--exec", "chpasswd"]


@needs_pwsh
def test_a_program_that_reads_input_it_was_not_given_sees_the_end_instead_of_waiting(tmp_path):
    program = fake_program(tmp_path, 'if read -r line; then echo "got: $line"; else echo "no input"; fi\n')
    got = call("Invoke-AckVsEngProcess -Program %s -ArgumentLine '' -TimeoutSec 30" % lit(str(program)), tmp_path)
    assert got["Lines"] == ["no input"] and got["Code"] == 0


@needs_pwsh
def test_lines_from_both_streams_are_collected_cleaned_and_handed_on_as_they_come_and_the_exit_code_is_kept(tmp_path):
    program = fake_program(tmp_path, 'echo "out one"; echo "err one" >&2; printf "caf\\xc3\\xa9\\n"; printf "\\x1b[1mbold\\x1b[0m\\n"; exit 7\n')
    got = run_ps("$seen = New-Object System.Collections.ArrayList\n$r = Invoke-AckVsEngProcess -Program %s -ArgumentLine '' -TimeoutSec 30 -OnLine { param($l) [void]$seen.Add($l) }\n"
                 "ConvertTo-Json -InputObject @{ r = $r; seen = @($seen) } -Depth 5 -Compress" % lit(str(program)), tmp_path)
    assert got["r"]["Code"] == 7 and sorted(got["r"]["Lines"]) == sorted(["out one", "err one", "caf?", "bold"]) and sorted(got["seen"]) == sorted(got["r"]["Lines"])


@needs_pwsh
def test_a_program_that_runs_too_long_is_stopped_and_says_so(tmp_path):
    program = fake_program(tmp_path, "sleep 30\n")
    got = call("Invoke-AckVsEngProcess -Program %s -ArgumentLine '' -TimeoutSec 1" % lit(str(program)), tmp_path)
    assert got["Ran"] is True and got["TimedOut"] is True and got["Code"] == 1


@needs_pwsh
def test_a_program_that_is_not_there_is_reported_as_not_run(tmp_path):
    assert call("Invoke-AckVsEngProcess -Program %s -ArgumentLine ''" % lit(str(tmp_path / "missing")), tmp_path)["Ran"] is False
    assert call("Invoke-AckVsEngProcess -Program '' -ArgumentLine ''", tmp_path)["Ran"] is False


@needs_pwsh
def test_a_wsl_request_is_turned_into_a_command_line_with_spaces_quoted(tmp_path):
    program = fake_program(tmp_path, 'printf "%s\\n" "$@" > ' + str(tmp_path / "argv") + "\n")
    run_ps("$null = Invoke-AckVsEngProcess -Program %s -ArgumentLine (Format-AckVsCommandLine -CommandArguments @('-d', 'Ubuntu-24.04', 'a b')) -TimeoutSec 30\n'null' | ConvertTo-Json" % lit(str(program)), tmp_path)
    assert (tmp_path / "argv").read_text().splitlines() == ["-d", "Ubuntu-24.04", "a b"]


# ================================================================ the commands run inside Ubuntu, run for real

def run_bash(script, tmp_path, path_extra=None):
    env = dict(os.environ)
    if path_extra:
        env["PATH"] = str(path_extra) + os.pathsep + env["PATH"]
    return subprocess.run(["bash", "-c", script], capture_output=True, text=True, timeout=30, env=env, cwd=str(tmp_path))


def command_text(expression, tmp_path):
    return call(expression, tmp_path)


def is_valid_shell(command, tmp_path):
    """bash -n on the command written to a file: syntax only, nothing runs."""
    script = tmp_path / "command.sh"
    script.write_text(command + "\n")
    return subprocess.run(["bash", "-n", str(script)], capture_output=True, text=True, timeout=30).returncode == 0


@needs_pwsh
@pytest.mark.parametrize("start, expected", [
    ("", "\n[user]\ndefault=anna\n"),
    ("[boot]\nsystemd=true\n", "[boot]\nsystemd=true\n\n[user]\ndefault=anna\n"),
    ("[user]\ndefault=bob\n", "[user]\ndefault=anna\n"),
    ("[user]\ndefault=bob\n[boot]\nsystemd=true\n", "[user]\ndefault=anna\n[boot]\nsystemd=true\n"),
    ("[user]\n[boot]\nsystemd=true\n", "[user]\ndefault=anna\n[boot]\nsystemd=true\n"),
    ("[user]\ndefault=anna\n", "[user]\ndefault=anna\n"),
])
def test_the_default_account_is_set_in_wsl_conf_and_everything_else_in_it_is_kept(tmp_path, start, expected):
    command = command_text("Get-AckVsEngWslConfCommand -User 'anna'", tmp_path)
    target = tmp_path / "wsl.conf"
    target.write_text(start)
    done = run_bash(command.replace("/etc/wsl.conf", str(target)), tmp_path)
    assert done.returncode == 0, done.stderr
    assert target.read_text() == expected


@needs_pwsh
def test_the_wsl_conf_command_holds_no_double_quote_so_windows_passes_it_on_as_one_piece(tmp_path):
    for expression in ("Get-AckVsEngWslConfCommand -User 'anna'", "Get-AckVsEngSudoOnCommand -User 'anna'", "Get-AckVsEngSudoOffCommand"):
        text = command_text(expression, tmp_path)
        assert '"' not in text and "\n" not in text and is_valid_shell(text, tmp_path)


def fake_visudo(tmp_path, ok=True):
    folder = tmp_path / "bin"
    folder.mkdir(exist_ok=True)
    program = folder / "visudo"
    program.write_text("#!/bin/bash\n" + ("exit 0\n" if ok else "exit 1\n"))
    program.chmod(0o755)
    return folder


@needs_pwsh
def test_the_install_permission_is_a_checked_file_for_that_account_only_and_not_world_readable(tmp_path):
    command = command_text("Get-AckVsEngSudoOnCommand -User 'anna'", tmp_path)
    target = tmp_path / "sudoers-file"
    done = run_bash(command.replace("/etc/sudoers.d/ack-voice-studio-install", str(target)), tmp_path, fake_visudo(tmp_path))
    assert done.returncode == 0, done.stderr
    assert target.read_text() == "# written by the ACK Voice Studio installer; removed when it ends\nanna ALL=(ALL) NOPASSWD:ALL\n"
    assert stat.S_IMODE(target.stat().st_mode) == 0o440


@needs_pwsh
def test_a_permission_file_that_visudo_does_not_accept_is_removed_and_the_step_fails(tmp_path):
    command = command_text("Get-AckVsEngSudoOnCommand -User 'anna'", tmp_path)
    target = tmp_path / "sudoers-file"
    done = run_bash(command.replace("/etc/sudoers.d/ack-voice-studio-install", str(target)), tmp_path, fake_visudo(tmp_path, ok=False))
    assert done.returncode == 1 and not target.exists()


@needs_pwsh
def test_taking_the_permission_away_removes_the_file_and_checks_it_is_gone_and_is_safe_to_repeat(tmp_path):
    command = command_text("Get-AckVsEngSudoOffCommand", tmp_path)
    target = tmp_path / "sudoers-file"
    target.write_text("x")
    script = command.replace("/etc/sudoers.d/ack-voice-studio-install", str(target))
    assert run_bash(script, tmp_path).returncode == 0 and not target.exists()
    assert run_bash(script, tmp_path).returncode == 0


@needs_pwsh
def test_the_permission_file_is_named_for_the_installer_so_nothing_else_is_ever_touched(tmp_path):
    assert "/etc/sudoers.d/ack-voice-studio-install" in command_text("Get-AckVsEngSudoOnCommand -User 'anna'", tmp_path)
    assert command_text("Get-AckVsEngSudoOffCommand", tmp_path) == "rm -f /etc/sudoers.d/ack-voice-studio-install && test ! -e /etc/sudoers.d/ack-voice-studio-install"


@needs_pwsh
@pytest.mark.parametrize("lines, expected", [
    (PASSWD_ROOT_ONLY, ""),
    (PASSWD_ANNA, "anna"),
    (PASSWD_ROOT_ONLY + ["a:x:999:999::/home/a:/bin/bash"], ""),
    (PASSWD_ROOT_ONLY + ["a:x:1000:1000::/home/a:/bin/bash"], "a"),
    (PASSWD_ROOT_ONLY + ["a:x:59999:1000::/home/a:/bin/bash"], "a"),
    (PASSWD_ROOT_ONLY + ["a:x:60000:1000::/home/a:/bin/bash"], ""),
    (PASSWD_ROOT_ONLY + ["svc:x:1001:1001::/home/svc:/usr/sbin/nologin"], ""),
    (PASSWD_ROOT_ONLY + ["svc:x:1001:1001::/home/svc:/bin/false"], ""),
    (PASSWD_ROOT_ONLY + ["zed:x:1002:1002::/home/zed:/bin/bash", "amy:x:1001:1001::/home/amy:/bin/bash"], "amy"),
    (PASSWD_ROOT_ONLY + ["Bad Name:x:1001:1001::/h:/bin/bash"], ""),
    (["short:line", "", "x:x:notanumber:1:::/bin/bash"], ""),
    ([], ""),
])
def test_the_first_ordinary_account_is_found_in_a_passwd_listing(tmp_path, lines, expected):
    assert call("ConvertFrom-AckVsEngPasswd -Lines %s" % lit(lines), tmp_path) == expected


# ================================================================ the check

def result_ini(tmp_path):
    raw = (tmp_path / "result.ini").read_text(encoding="ascii")
    values, lines, section = {}, {}, ""
    for line in raw.splitlines():
        if line.startswith("["):
            section = line
        elif "=" in line:
            key, value = line.split("=", 1)
            (values if section == "[result]" else lines)[key] = value
    return values, lines


def check(tmp_path, *, facts=None, replies=None, options=""):
    result = engine(tmp_path, "check", facts=facts, replies=replies, options="-ResultFile %s %s" % (lit(str(tmp_path / "result.ini")), options))
    return result, result_ini(tmp_path)


@needs_pwsh
def test_windows_10_stops_the_check_before_wsl_is_touched(tmp_path):
    result, (values, lines) = check(tmp_path, facts=dict(FACTS_OK, Build=19045))
    assert result["code"] == 1 and values["stop"] == "1" and args_of(result) == []
    assert any(l.startswith("stop|ACK Voice Studio needs Windows 11") for l in lines.values())
    assert any("needs Windows 11" in s for s in result["said"])


@needs_pwsh
def test_the_first_windows_11_passes_the_check(tmp_path):
    result, (values, lines) = check(tmp_path, facts=dict(FACTS_OK, Build=22000), replies=no_wsl())
    assert result["code"] == 0 and values["stop"] == "0" and values["windows_build"] == "22000"


@needs_pwsh
def test_a_computer_that_is_not_64_bit_stops_the_check(tmp_path):
    result, (values, _lines) = check(tmp_path, facts=dict(FACTS_OK, Is64=False))
    assert result["code"] == 1 and values["stop"] == "1"


@needs_pwsh
def test_with_no_wsl_the_check_says_all_three_things_are_needed_and_changes_nothing(tmp_path):
    result, (values, lines) = check(tmp_path, replies=no_wsl())
    assert result["code"] == 0 and (values["wsl"], values["needs_platform"], values["needs_distro"], values["needs_account"], values["distro"], values["user"]) == ("none", "1", "1", "1", "", "")
    assert args_of(result) == ["-l -v", "--status", "--version"]                  # the three questions, and nothing that changes anything


@needs_pwsh
def test_with_wsl_and_no_ubuntu_only_ubuntu_and_the_account_are_needed(tmp_path):
    result, (values, _lines) = check(tmp_path, replies={"-l -v": reply([], code=0)})
    assert (values["wsl"], values["needs_platform"], values["needs_distro"], values["needs_account"]) == ("ready", "0", "1", "1")


@needs_pwsh
def test_an_ubuntu_with_an_ordinary_account_needs_nothing_and_that_account_is_named(tmp_path):
    result, (values, lines) = check(tmp_path, replies={"-l -v": reply(LISTING), "getent passwd": reply(PASSWD_ANNA)})
    assert (values["distro"], values["user"], values["needs_distro"], values["needs_account"], values["needs_platform"]) == ("Ubuntu-24.04", "anna", "0", "0", "0")
    assert any("Ubuntu account found: anna. It will be used, and its password is not touched." in l for l in lines.values())
    assert "-d Ubuntu-24.04 -u root --exec bash -c getent passwd" in args_of(result)


@needs_pwsh
def test_an_ubuntu_with_only_root_needs_an_account(tmp_path):
    result, (values, _lines) = check(tmp_path, replies={"-l -v": reply(LISTING), "getent passwd": reply(PASSWD_ROOT_ONLY)})
    assert (values["distro"], values["user"], values["needs_distro"], values["needs_account"]) == ("Ubuntu-24.04", "", "0", "1")


@needs_pwsh
def test_an_ubuntu_that_will_not_list_its_accounts_is_treated_as_needing_one_and_never_as_stopping(tmp_path):
    result, (values, _lines) = check(tmp_path, replies={"-l -v": reply(LISTING), "getent passwd": reply([], code=1)})
    assert result["code"] == 0 and values["needs_account"] == "1"


@needs_pwsh
def test_wsl_version_one_stops_the_check_with_the_command_that_changes_it(tmp_path):
    result, (values, lines) = check(tmp_path, replies={"-l -v": reply(["  NAME            STATE           VERSION", "* Ubuntu-24.04    Running         1"])})
    assert result["code"] == 1 and values["stop"] == "1" and any("wsl --set-version Ubuntu-24.04 2" in l for l in lines.values())


@needs_pwsh
def test_a_named_ubuntu_that_is_not_there_is_not_picked(tmp_path):
    result, (values, _lines) = check(tmp_path, replies={"-l -v": reply(LISTING)}, options="-Distro 'Ubuntu-22.04'")
    assert values["distro"] == "" and values["needs_distro"] == "1"


@needs_pwsh
def test_the_check_writes_every_finding_with_its_level_and_a_count(tmp_path):
    result, (values, lines) = check(tmp_path, replies={"-l -v": reply(LISTING), "getent passwd": reply(PASSWD_ANNA)})
    assert int(lines["count"]) == len([k for k in lines if k != "count"]) and lines["1"].startswith("ok|Windows: ok (build 22631)")
    assert all(re.match(r"^(ok|warn|stop|info)\|", v) for k, v in lines.items() if k != "count")


@needs_pwsh
def test_a_computer_with_no_graphics_driver_gets_a_note_and_goes_on(tmp_path):
    result, (values, lines) = check(tmp_path, facts=dict(FACTS_OK, GpuName="", GpuDriver=""), replies={"-l -v": reply(LISTING)})
    assert result["code"] == 0 and values["gpu"] == "0" and any(l.startswith("warn|No Nvidia graphics driver") for l in lines.values())


# ================================================================ WSL itself

@needs_pwsh
def test_when_wsl_already_works_nothing_is_set_up_and_no_permission_is_asked(tmp_path):
    result = engine(tmp_path, "platform", replies={"-l -v": reply(LISTING)})
    assert result["code"] == 0 and result["elevated"] == [] and "WSL is already set up." in result["said"]


@needs_pwsh
def test_setting_up_wsl_asks_windows_once_for_exactly_the_platform_and_no_distribution(tmp_path):
    result = engine(tmp_path, "platform", replies=no_wsl())
    assert result["elevated"][0]["ArgumentLine"] == "--install --no-distribution" and len(result["elevated"]) == 1
    assert result["code"] == 3 and any("must restart" in s for s in result["said"])


@needs_pwsh
def test_wsl_that_works_straight_after_the_install_needs_no_restart(tmp_path):
    extra = "$flip = @{ n = 0 }\n"
    body_replies = None
    # the stand-in answers "not working" until the permission step has run, and "working" after it
    result = run_ps(PRELUDE % {"replies": "@{}", "elevate": lit({"Ran": True, "Code": 0, "Declined": False}), "facts": lit(FACTS_OK), "found": "''", "program": lit({"Ran": True, "Code": 0, "Lines": []})} + """
$wsl = { param($r) $key = (@($r.Arguments) -join ' '); [void]$calls.Add($key); if ($elevated.Count -gt 0) { return @{ Ran = $true; Code = 0; Lines = @('  NAME STATE VERSION') } }; return @{ Ran = $true; Code = 1; Lines = @() } }
$code = @(Invoke-AckVsEngine -Step 'platform' -Say $say -Wsl $wsl -Elevate $elevate)[-1]
ConvertTo-Json -InputObject @{ code = $code; said = @($said); elevated = @($elevated).Count } -Compress
""", tmp_path)
    assert result["code"] == 0 and result["elevated"] == 1


@needs_pwsh
def test_a_no_from_windows_is_a_no_and_nothing_else_is_tried(tmp_path):
    result = engine(tmp_path, "platform", replies=no_wsl(), elevate={"Ran": False, "Code": 1, "Declined": True})
    assert result["code"] == 2 and any("Windows was not allowed to set up WSL, so nothing was changed" in s for s in result["said"]) and len(result["elevated"]) == 1


@needs_pwsh
@pytest.mark.parametrize("code, expected", [(0, 3), (3010, 3), (1, 1), (-1, 1), (5, 1)])
def test_the_exit_code_of_the_wsl_install_decides_between_a_restart_and_a_failure(tmp_path, code, expected):
    result = engine(tmp_path, "platform", replies=no_wsl(), elevate={"Ran": True, "Code": code, "Declined": False})
    assert result["code"] == expected
    if expected == 1:
        assert any("Windows could not set up WSL (code %d)" % code in s for s in result["said"])


@needs_pwsh
def test_the_dry_run_of_the_wsl_step_shows_the_command_and_asks_for_nothing(tmp_path):
    result = engine(tmp_path, "platform", replies=no_wsl(), options="-DryRun")
    assert result["code"] == 0 and result["elevated"] == [] and any("wsl.exe --install --no-distribution" in s for s in result["said"])


# ================================================================ Ubuntu

@needs_pwsh
def test_an_ubuntu_that_is_already_there_is_not_installed_again(tmp_path):
    result = engine(tmp_path, "distro", replies={"-l -v": reply(LISTING)}, options="-User anna")
    assert result["code"] == 0 and args_of(result) == ["-l -v"] and result["files"] == []


@needs_pwsh
def test_ubuntu_is_installed_without_launching_then_started_once_and_checked(tmp_path):
    result = engine(tmp_path, "distro", replies={"-l -v": reply([], code=0)}, options="-User anna")
    assert result["code"] == 0
    keys = doing(result)
    assert keys == ["--install -d Ubuntu-24.04 --no-launch", "-d Ubuntu-24.04 -u root --exec bash -c cloud-init status --wait; true", "-d Ubuntu-24.04 -u root --exec bash -c true"]
    assert "Ubuntu is installed and starts." in result["said"]


@needs_pwsh
def test_the_first_start_account_file_is_written_before_the_install_and_removed_after_and_names_only_the_account(tmp_path):
    result = engine(tmp_path, "distro", replies={"-l -v": reply([], code=0)}, options="-User anna")
    target = user_data_of(tmp_path)
    events = result["events"]
    assert events.index("write " + target) < events.index("wsl: --install -d Ubuntu-24.04 --no-launch") < events.index("remove " + target)
    assert result["files"] == []


@needs_pwsh
def test_the_account_file_holds_no_password_and_no_sudo_without_a_password(tmp_path):
    text = call("New-AckVsEngCloudInit -User 'anna'", tmp_path)
    assert text.startswith("#cloud-config\n") and "name: anna" in text and "default=anna" in text and "groups: [sudo]" in text
    assert "NOPASSWD" not in text and "passwd" not in text.lower() and "plain_text" not in text


@needs_pwsh
def test_an_account_file_of_the_persons_own_is_never_overwritten_or_removed(tmp_path):
    target = user_data_of(tmp_path)
    result = engine(tmp_path, "distro", replies={"-l -v": reply([], code=0)}, options="-User anna", files={target: "their own"})
    assert result["code"] == 0 and not any(e.startswith("write ") or e.startswith("remove ") for e in result["events"]) and result["files"] == [target]


@needs_pwsh
def test_no_account_file_is_written_without_a_valid_account_name(tmp_path):
    for option in ("", "-User root", "-User 'Anna'"):
        result = engine(tmp_path, "distro", replies={"-l -v": reply([], code=0)}, options=option)
        assert not any(e.startswith("write ") for e in result["events"])


@needs_pwsh
def test_a_failed_install_stops_before_the_first_start_and_still_cleans_up_its_own_file(tmp_path):
    result = engine(tmp_path, "distro", replies={"-l -v": reply([], code=0), "--install -d": reply([], code=1)}, options="-User anna")
    assert result["code"] == 1 and not any("cloud-init status" in k for k in args_of(result)) and result["files"] == []
    assert any("Ubuntu could not be installed or started (code 1)" in s for s in result["said"])


@needs_pwsh
def test_an_ubuntu_that_does_not_start_is_tried_once_through_its_store_program_and_then_given_up(tmp_path):
    result = engine(tmp_path, "distro", replies={"-l -v": reply([], code=0), "exec bash -c true": reply([], code=1)}, options="-User anna", found="'C:\\WindowsApps\\ubuntu2404.exe'")
    assert result["code"] == 1
    assert "run C:\\WindowsApps\\ubuntu2404.exe install --root" in result["events"] and "find ubuntu2404.exe" in result["events"]
    assert args_of(result).count("-d Ubuntu-24.04 -u root --exec bash -c true") == 2


@needs_pwsh
def test_the_store_program_that_registers_ubuntu_rescues_a_start_that_did_not_work(tmp_path):
    extra = ""
    body = PRELUDE % {"replies": table({"-l -v": reply([], code=0)}), "elevate": "@{}", "facts": lit(FACTS_OK), "found": "'ubuntu2404.exe'", "program": lit({"Ran": True, "Code": 0, "Lines": []})} + """
$ok = @{ after = $false }
$runProgram = { param($r) $ok.after = $true; return @{ Ran = $true; Code = 0; Lines = @() } }
$wsl = { param($r) $key = (@($r.Arguments) -join ' '); [void]$calls.Add($key); if ($key -like '*exec bash -c true') { if ($ok.after) { return @{ Ran = $true; Code = 0; Lines = @() } } else { return @{ Ran = $true; Code = 1; Lines = @() } } }; return @{ Ran = $true; Code = 0; Lines = @() } }
$code = @(Invoke-AckVsEngine -Step 'distro' -User 'anna' -Say $say -Wsl $wsl -FindProgram $findProgram -RunProgram $runProgram -FileExists $fileExists -WriteFile $writeFile -RemoveFile $removeFile -ProfileFolder PROFILE)[-1]
ConvertTo-Json -InputObject @{ code = $code; said = @($said) } -Compress
""".replace("PROFILE", lit(profile_of(tmp_path)))
    result = run_ps(body, tmp_path)
    assert result["code"] == 0 and "Ubuntu is installed and starts." in result["said"]


@needs_pwsh
def test_a_name_with_no_store_program_pattern_gets_no_store_program(tmp_path):
    assert call("Get-AckVsEngLauncherName -Distro 'Ubuntu'", tmp_path) == "" and call("Get-AckVsEngLauncherName -Distro 'Ubuntu-22.04'", tmp_path) == "ubuntu2204.exe"
    assert call("Get-AckVsEngLauncherName -Distro 'Ubuntu-24.04.1'", tmp_path) == "" and call("Get-AckVsEngLauncherName -Distro 'Ubuntu-2404'", tmp_path) == ""


@needs_pwsh
def test_the_dry_run_of_the_ubuntu_step_shows_the_commands_and_changes_nothing(tmp_path):
    result = engine(tmp_path, "distro", replies={"-l -v": reply([], code=0)}, options="-User anna -DryRun")
    assert result["code"] == 0 and result["files"] == [] and doing(result) == []
    assert any("wsl.exe --install -d Ubuntu-24.04 --no-launch" in s for s in result["said"])


# ================================================================ the account and its password

def user_step(tmp_path, *, user="anna", password=PASSWORD, replies=None, options=""):
    return engine(tmp_path, "user", options="-Distro Ubuntu-24.04 -User %s %s" % (lit(user), options), password=password, replies=replies)


@needs_pwsh
def test_the_account_is_made_its_password_is_set_on_standard_input_and_it_becomes_the_default(tmp_path):
    result = user_step(tmp_path, replies={"id -u anna": reply([], code=1)})
    assert result["code"] == 0
    keys = args_of(result)
    assert keys[0] == "-d Ubuntu-24.04 -u root --exec bash -c id -u anna"
    assert keys[1] == "-d Ubuntu-24.04 -u root --exec bash -c useradd -m -s /bin/bash -G sudo anna"
    assert keys[2] == "-d Ubuntu-24.04 -u root --exec bash -c passwd -S anna | awk '{print $2}'"
    assert keys[3] == "-d Ubuntu-24.04 -u root --exec chpasswd"
    assert "default=anna" in keys[4] and keys[5] == "--terminate Ubuntu-24.04"
    assert result["calls"][3]["Input"] == "anna:" + PASSWORD + "\n"


@needs_pwsh
def test_the_password_is_in_no_argument_list_and_no_other_input_and_no_printed_line(tmp_path):
    result = user_step(tmp_path, replies={"id -u anna": reply([], code=1)})
    for index, request in enumerate(result["calls"]):
        assert PASSWORD not in request["Key"], request["Key"]
        if index != 3:
            assert request["Input"] is None
    assert not any(PASSWORD in line for line in result["said"])
    assert PASSWORD not in (tmp_path / "engine.log").read_text(encoding="ascii")


@needs_pwsh
def test_the_password_is_not_in_the_log_even_when_a_program_echoes_it_back(tmp_path):
    result = user_step(tmp_path, replies={"id -u anna": reply([], code=1), "chpasswd": reply(["bad password: " + PASSWORD], code=1)}, options="")
    # the stand-in answers do not go to the log, but the failure path does: nothing in it may hold the password
    assert result["code"] == 1 and PASSWORD not in (tmp_path / "engine.log").read_text(encoding="ascii")
    assert not any(PASSWORD in line for line in result["said"])


@needs_pwsh
def test_an_account_that_already_has_a_password_keeps_it(tmp_path):
    result = user_step(tmp_path, replies={"id -u anna": reply(["1000"], code=0), "passwd -S": reply(["P"])})
    assert result["code"] == 0 and "The Ubuntu account anna is already there and has a password. Its password was not changed." in result["said"]
    assert not any("chpasswd" in k or "useradd" in k for k in args_of(result)) and all(c["Input"] is None for c in result["calls"])
    assert any("default=anna" in k for k in args_of(result))


@needs_pwsh
@pytest.mark.parametrize("state", ["L", "NP", ""])
def test_an_account_with_no_usable_password_gets_one_because_it_is_nobodys_yet(tmp_path, state):
    """The account Ubuntu's own first start makes has no password; without this the wizard's password would never be set."""
    result = user_step(tmp_path, replies={"id -u anna": reply(["1000"], code=0), "passwd -S": reply([state] if state else [])})
    assert result["code"] == 0 and "The Ubuntu account anna is already there and has no password yet." in result["said"]
    assert not any("useradd" in k for k in args_of(result)) and [c["Input"] for c in result["calls"] if c["Input"]] == ["anna:" + PASSWORD + "\n"]


@needs_pwsh
def test_a_password_status_that_cannot_be_read_counts_as_no_password_only_when_it_says_nothing_of_a_usable_one(tmp_path):
    result = user_step(tmp_path, replies={"id -u anna": reply(["1000"], code=0), "passwd -S": reply(["P"], code=1)})
    assert [c["Input"] for c in result["calls"] if c["Input"]] == ["anna:" + PASSWORD + "\n"]


@needs_pwsh
def test_the_password_status_command_asks_only_for_the_state_word_and_is_valid_shell(tmp_path):
    command = command_text("Get-AckVsEngPasswordStatusCommand -User 'anna'", tmp_path)
    assert command == "passwd -S anna | awk '{print $2}'" and is_valid_shell(command, tmp_path)


@needs_pwsh
@pytest.mark.parametrize("user, password", [("root", PASSWORD), ("Anna", PASSWORD), ("an na", PASSWORD), ("anna", "short"), ("anna", "accent\u00e9abcd"), ("anna", "tab\there1"), ("anna", ""), ("", PASSWORD)])
def test_a_refused_name_or_password_makes_nothing_and_touches_nothing(tmp_path, user, password):
    result = user_step(tmp_path, user=user, password=password)
    assert result["code"] == 2 and result["calls"] == []
    assert not any(password and password in line for line in result["said"] if len(password) >= 4)


@needs_pwsh
def test_a_missing_password_is_refused_with_its_own_words(tmp_path):
    body = PRELUDE % {"replies": "@{}", "elevate": "@{}", "facts": lit(FACTS_OK), "found": "''", "program": "@{}"} + """
$code = @(Invoke-AckVsEngine -Step 'user' -Distro 'Ubuntu-24.04' -User 'anna' -Say $say -Wsl $wsl)[-1]
ConvertTo-Json -InputObject @{ code = $code; said = @($said); calls = @($calls).Count } -Compress
"""
    result = run_ps(body, tmp_path)
    assert result["code"] == 2 and result["calls"] == 0 and "No password was given, so the Ubuntu account was not made." in result["said"]


@needs_pwsh
def test_if_the_account_cannot_be_made_the_password_is_never_sent(tmp_path):
    result = user_step(tmp_path, replies={"id -u anna": reply([], code=1), "useradd": reply(["useradd: failure"], code=9)})
    assert result["code"] == 1 and not any(k.endswith("chpasswd") for k in args_of(result)) and all(c["Input"] is None for c in result["calls"])
    assert not any("passwd -S" in k for k in args_of(result))
    assert any("The Ubuntu account could not be made (code 9)" in s for s in result["said"])


@needs_pwsh
def test_if_the_password_cannot_be_set_the_step_fails_and_default_account_is_not_changed(tmp_path):
    result = user_step(tmp_path, replies={"id -u anna": reply([], code=1), "chpasswd": reply([], code=1)})
    assert result["code"] == 1 and not any("wsl.conf" in k for k in args_of(result)) and "--terminate Ubuntu-24.04" not in args_of(result)


@needs_pwsh
def test_if_the_default_account_cannot_be_set_the_step_fails(tmp_path):
    result = user_step(tmp_path, replies={"id -u anna": reply([], code=1), "wsl.conf": reply([], code=1)})
    assert result["code"] == 1


@needs_pwsh
def test_the_dry_run_of_the_account_step_shows_commands_without_the_password_and_runs_none(tmp_path):
    result = user_step(tmp_path, options="-DryRun")
    assert result["code"] == 0 and result["calls"] == [] and not any(PASSWORD in s for s in result["said"])
    assert any("standard input" in s for s in result["said"])


# ================================================================ the install-time permission

@needs_pwsh
def test_the_install_permission_is_given_and_taken_away_as_root_for_the_account_only(tmp_path):
    on = engine(tmp_path, "sudo-on", options="-Distro Ubuntu-24.04 -User anna")
    off = engine(tmp_path, "sudo-off", options="-Distro Ubuntu-24.04")
    assert on["code"] == 0 and off["code"] == 0
    assert args_of(on)[0].startswith("-d Ubuntu-24.04 -u root --exec bash -c umask 077; printf") and "anna ALL=(ALL) NOPASSWD:ALL" in args_of(on)[0]
    assert args_of(off) == ["-d Ubuntu-24.04 -u root --exec bash -c rm -f /etc/sudoers.d/ack-voice-studio-install && test ! -e /etc/sudoers.d/ack-voice-studio-install"]


@needs_pwsh
def test_the_permission_is_never_given_to_a_refused_name(tmp_path):
    for user in ("root", "Anna", "a b", ""):
        result = engine(tmp_path, "sudo-on", options="-Distro Ubuntu-24.04 -User %s" % lit(user))
        assert result["code"] == 2 and result["calls"] == []


@needs_pwsh
def test_taking_the_permission_away_needs_no_account_name_and_reports_a_failure(tmp_path):
    result = engine(tmp_path, "sudo-off", options="-Distro Ubuntu-24.04", replies={"rm -f": reply([], code=1)})
    assert result["code"] == 1 and any("The permission for the install could not be set (code 1)" in s for s in result["said"])


# ================================================================ the set-up inside Ubuntu

@needs_pwsh
def test_the_setup_runs_the_hand_over_as_the_account_answered_yes_and_without_opening_the_window(tmp_path):
    result = engine(tmp_path, "setup", options="-Distro Ubuntu-24.04 -User anna -Ref main")
    assert result["code"] == 0 and len(result["calls"]) == 1
    arguments = result["calls"][0]["Arguments"]
    assert arguments[:6] == ["-d", "Ubuntu-24.04", "-u", "anna", "--cd", "~"] and arguments[6:9] == ["--exec", "bash", "-c"]
    command = arguments[9]
    assert "--yes --no-window" in command and "ACK_VOICE_TAG='main'" in command and '"' not in command and "\n" not in command
    assert "https://raw.githubusercontent.com/ASPDesignLabs/ACK/main/tools/voice_studio/get.sh" in command


@needs_pwsh
def test_the_hand_over_is_the_one_install_ps1_builds_with_only_yes_added(tmp_path):
    ours = call("(Get-AckVsEngSetupArguments -Distro 'Ubuntu-24.04' -User 'anna' -Ref 'v1.2')[-1]", tmp_path)
    theirs = call("New-AckVsHandover -Ref 'v1.2'", tmp_path)
    assert ours == theirs.replace("--no-window", "--yes --no-window") and "ACK_VOICE_TAG='v1.2'" in ours


@needs_pwsh
def test_the_hand_over_command_is_valid_shell(tmp_path):
    command = call("(Get-AckVsEngSetupArguments -Distro 'Ubuntu-24.04' -User 'anna' -Ref 'main')[-1]", tmp_path)
    assert is_valid_shell(command, tmp_path)


@needs_pwsh
def test_a_failed_setup_names_its_code_and_says_how_to_carry_on(tmp_path):
    result = engine(tmp_path, "setup", options="-Distro Ubuntu-24.04 -User anna", replies={"--yes --no-window": reply(["it stopped"], code=4)})
    assert result["code"] == 1 and any("stopped with code 4" in s and "carry on from where it stopped" in s for s in result["said"])


@needs_pwsh
def test_a_setup_that_could_not_even_start_is_a_failure_too(tmp_path):
    result = engine(tmp_path, "setup", options="-Distro Ubuntu-24.04 -User anna", replies={"--yes --no-window": reply([], code=0, ran=False)})
    assert result["code"] == 1 and any("stopped with code 1" in s for s in result["said"])


@needs_pwsh
def test_a_release_name_with_anything_odd_in_it_is_refused_before_anything_runs(tmp_path):
    for ref in ("a b", "x;rm", "..", "a//b", "-x", "x/"):
        result = engine(tmp_path, "setup", options="-Distro Ubuntu-24.04 -User anna -Ref %s" % lit(ref))
        assert result["code"] == 2 and result["calls"] == []


@needs_pwsh
def test_the_setup_without_a_release_uses_the_one_install_ps1_names(tmp_path):
    result = engine(tmp_path, "setup", options="-Distro Ubuntu-24.04 -User anna")
    assert "ACK_VOICE_TAG='main'" in result["calls"][0]["Arguments"][9]


@needs_pwsh
def test_the_dry_run_of_the_setup_shows_the_command_and_runs_nothing(tmp_path):
    result = engine(tmp_path, "setup", options="-Distro Ubuntu-24.04 -User anna -DryRun")
    assert result["code"] == 0 and result["calls"] == [] and any("wsl.exe -d Ubuntu-24.04 -u anna" in s for s in result["said"])


# ================================================================ the Start menu entry and the window

@needs_pwsh
def test_the_start_menu_entry_is_made_by_the_tool_itself_in_ubuntu_answered_yes(tmp_path):
    result = engine(tmp_path, "launcher", options="-Distro Ubuntu-24.04 -User anna")
    command = result["calls"][0]["Arguments"][-1]
    assert result["code"] == 0 and command == "PYTHONPATH=$HOME/ack-tools/tools /usr/bin/python3 -m voice_studio.window --install-launcher --yes"
    assert "ACK Voice Studio is in the Start menu." in result["said"]


@needs_pwsh
def test_a_start_menu_entry_that_could_not_be_made_is_a_note_and_not_a_failure(tmp_path):
    result = engine(tmp_path, "launcher", options="-Distro Ubuntu-24.04 -User anna", replies={"--install-launcher": reply([], code=1)})
    assert result["code"] == 0 and any("The Start menu entry could not be made (code 1)" in s and "still installed" in s for s in result["said"])


@needs_pwsh
def test_opening_the_window_starts_a_hidden_session_that_is_not_waited_for(tmp_path):
    result = engine(tmp_path, "open", options="-Distro Ubuntu-24.04 -User anna")
    assert result["code"] == 0 and result["calls"] == [] and len(result["started"]) == 1
    line = result["started"][0]["ArgumentLine"]
    assert line.startswith("-d Ubuntu-24.04 -u anna --cd ~ --exec bash -c ") and "voice_studio.window" in line and "exec /usr/bin/python3" in line


@needs_pwsh
def test_the_account_name_is_checked_for_every_step_that_runs_as_it(tmp_path):
    for step in ("setup", "launcher", "open"):
        result = engine(tmp_path, step, options="-Distro Ubuntu-24.04 -User 'Bad Name'")
        assert result["code"] == 2 and result["calls"] == [] and result["started"] == []


# ================================================================ the whole thing, and the file run on its own

@needs_pwsh
def test_an_unknown_step_a_bad_ubuntu_name_and_a_bad_result_path_are_refused(tmp_path):
    assert engine(tmp_path, "nonsense")["code"] == 2
    assert engine(tmp_path, "check", options="-Distro 'Debian'")["code"] == 2
    assert engine(tmp_path, "check", options="-ResultFile ('a' + [char]10 + 'b')")["code"] == 2


@needs_pwsh
def test_help_names_every_step(tmp_path):
    result = engine(tmp_path, "help")
    assert result["code"] == 0
    for step in ("check", "platform", "distro", "validate", "user", "sudo-on", "sudo-off", "setup", "launcher", "open", "unlauncher"):
        assert step in result["said"][0]


@needs_pwsh
def test_the_file_run_on_its_own_exits_with_the_code_and_takes_the_password_out_of_the_environment(tmp_path):
    for step, code in (("help", 0), ("nonsense", 2)):
        done = subprocess.run([PWSH, "-NoProfile", "-NonInteractive", "-File", str(ENGINE), "-Step", step], capture_output=True, text=True, timeout=120,
                              env=dict(os.environ, ACK_VS_ENGINE_LOG=str(tmp_path / "e.log")))
        assert done.returncode == code, done.stdout + done.stderr
    wrapper = tmp_path / "wrap.ps1"
    wrapper.write_text("$env:ACK_VS_PASSWORD = 'secret-secret'\n& %s -Step help | Out-Null\n'env=[' + $env:ACK_VS_PASSWORD + ']'\n" % lit(str(ENGINE)), encoding="utf-8")
    done = subprocess.run([PWSH, "-NoProfile", "-NonInteractive", "-File", str(wrapper)], capture_output=True, text=True, timeout=120, env=dict(os.environ, ACK_VS_ENGINE_LOG=str(tmp_path / "e.log")))
    assert done.stdout.strip().splitlines()[-1] == "env=[]"


@needs_pwsh
def test_the_dry_run_of_the_account_step_as_a_file_never_prints_the_password_from_the_environment(tmp_path):
    done = subprocess.run([PWSH, "-NoProfile", "-NonInteractive", "-File", str(ENGINE), "-Step", "user", "-Distro", "Ubuntu-24.04", "-User", "anna", "-DryRun"],
                          capture_output=True, text=True, timeout=120, env=dict(os.environ, ACK_VS_PASSWORD=PASSWORD, ACK_VS_ENGINE_LOG=str(tmp_path / "e.log")))
    assert done.returncode == 0 and PASSWORD not in done.stdout + done.stderr and "standard input" in done.stdout


@needs_pwsh
def test_the_account_step_as_a_file_refuses_a_bad_password_from_the_environment(tmp_path):
    done = subprocess.run([PWSH, "-NoProfile", "-NonInteractive", "-File", str(ENGINE), "-Step", "user", "-Distro", "Ubuntu-24.04", "-User", "anna", "-DryRun"],
                          capture_output=True, text=True, timeout=120, env=dict(os.environ, ACK_VS_PASSWORD="short", ACK_VS_ENGINE_LOG=str(tmp_path / "e.log")))
    assert done.returncode == 2 and "That password is not allowed" in done.stdout


@needs_pwsh
def test_the_password_in_the_environment_is_only_read_by_the_account_step(tmp_path):
    done = subprocess.run([PWSH, "-NoProfile", "-NonInteractive", "-File", str(ENGINE), "-Step", "help"], capture_output=True, text=True, timeout=120,
                          env=dict(os.environ, ACK_VS_PASSWORD=PASSWORD, ACK_VS_ENGINE_LOG=str(tmp_path / "e.log")))
    assert done.returncode == 0 and PASSWORD not in done.stdout + done.stderr


# ================================================================ read from the file

def code_lines(path):
    """The file's lines without comments and blank lines (a here-string's text is code, which is why this is lines and not a parse)."""
    return [l for l in path.read_text(encoding="ascii").splitlines() if l.strip() and not l.strip().startswith("#")]


def test_the_engine_is_plain_ascii_so_windows_powershell_5_1_reads_it_the_same(tmp_path):
    data = ENGINE.read_bytes()
    assert all(b < 128 for b in data) and not data.startswith(b"\xef\xbb\xbf")


def test_the_engine_uses_no_syntax_newer_than_windows_powershell_5_1():
    body = "\n".join(code_lines(ENGINE))
    assert not re.search(r"\?\?|\?\.|\?\[|&&|\|\||\bclean\s*\{|::new\(|\bForEach-Object\s+-Parallel\b|\bforeach\s*\(.*\)\s*\{.*\}\s*-", re.sub(r"'[^']*'|\"[^\"]*\"", "''", body))


def test_the_engine_makes_no_web_request_and_asks_no_question_in_a_console():
    body = "\n".join(code_lines(ENGINE))
    for forbidden in ("Invoke-WebRequest", "Invoke-RestMethod", "irm ", "iwr ", "curl", "wget", "Net.WebClient", "Start-BitsTransfer", "http://", "https://", "Read-Host", "Get-Credential", "ReadLine()", "ReadKey"):
        assert forbidden not in body, forbidden


def test_the_engine_changes_no_windows_setting():
    body = "\n".join(code_lines(ENGINE))
    for forbidden in ("Set-ExecutionPolicy", "Set-ItemProperty", "New-ItemProperty", "Remove-ItemProperty", "HKLM:", "HKCU:", "reg.exe", "reg add", "schtasks", "New-Service", "Enable-WindowsOptionalFeature", "dism"):
        assert forbidden.lower() not in body.lower(), forbidden


def test_the_password_is_only_ever_named_where_it_is_checked_sent_masked_or_taken_from_the_environment():
    lines = code_lines(ENGINE)
    uses = [l.strip() for l in lines if re.search(r"\$Password|\$ackVsEngPassword|ACK_VS_PASSWORD", l)]
    allowed = (r"param\(\[string\]\$Password\)", r"\$Password\.Length|\$Password\.ToCharArray|\$null -eq \$Password", r"\[string\]\$Password,", r"\[string\]\$Password = \$null",
               r"if \(\[string\]::IsNullOrEmpty\(\$Password\)\)", r"Test-AckVsEngPassword -Password \$Password", r"Input = \(\$User \+ ':' \+ \$Password", r"\$secret = \$env:ACK_VS_PASSWORD",
               r"\$ackVsEngPassword", r"-Password \$ackVsEngPassword", r"\$env:ACK_VS_PASSWORD = \$null", r"Env:ACK_VS_PASSWORD", r"\$Password,", r"-Password \$Password -DryRun", r"'validate'\s+\{ \$code = Step-AckVsEngValidate -User \$User -Password \$Password -Say \$Say \}")
    for use in uses:
        assert any(re.search(pattern, use) for pattern in allowed), "an unexpected use of the password: " + use


def test_the_password_is_never_put_in_an_argument_list_a_log_call_or_a_say():
    lines = code_lines(ENGINE)
    carrying = r"(Arguments\s*=[^;\n]*|ArgumentLine[^;\n]*|Write-AckVsEngLog[^;\n]*|& \$Say[^;}\n]*|Write-Host[^;\n]*|Write-Output[^;\n]*|Add-Content[^;\n]*|Out-File[^;\n]*|Set-Content[^;\n]*)\$(Password|ackVsEngPassword)\b"
    for line in lines:
        if "$Password" in line or "$ackVsEngPassword" in line:
            assert not re.search(carrying, line), line
    sending = [l for l in lines if "Input = (" in l]
    assert len(sending) == 1 and "$User + ':' + $Password" in sending[0]


def test_the_only_command_that_is_given_input_is_the_one_that_sets_the_password():
    lines = code_lines(ENGINE)
    given = [l for l in lines if re.search(r"\bInput\s*=", l)]
    assert len(given) == 1 and "$set = & $Wsl @{ Arguments = @('-d', $Distro, '-u', 'root', '--exec', 'chpasswd')" in given[0]


def test_the_engine_stands_on_install_ps1_and_does_not_copy_it():
    body = ENGINE.read_text(encoding="ascii")
    for name in ("Get-AckVsFacts", "Get-AckVsFindings", "Read-AckVsDistros", "Select-AckVsDistro", "New-AckVsHandover", "Format-AckVsCommandLine", "Test-AckVsRefName", "Test-AckVsDistroName"):
        assert name in body and ("function " + name) not in body
    assert "function Get-AckVsSettings" not in body and "MinBuild" not in body


def test_the_floor_is_windows_11_through_install_ps1():
    assert re.search(r"MinBuild\s*=\s*22000\b", INSTALL_PS1.read_text(encoding="ascii"))


# ================================================================ asking before going on: the same rules, from one place

@needs_pwsh
def test_the_wizard_asks_the_engine_whether_an_account_name_and_password_are_fine_and_nothing_is_touched(tmp_path):
    ok = engine(tmp_path, "validate", options="-User anna", password=PASSWORD)
    assert ok["code"] == 0 and ok["said"] == ["That account name and password are fine."] and ok["calls"] == []
    for user, password, said in (("root", PASSWORD, "That Ubuntu account name is not allowed"), ("anna", "short", "That password is not allowed"), ("anna", None, "That password is not allowed")):
        body = PRELUDE % {"replies": "@{}", "elevate": "@{}", "facts": lit(FACTS_OK), "found": "''", "program": "@{}"} + """
$code = @(Invoke-AckVsEngine -Step 'validate' -User %s %s -Say $say -Wsl $wsl)[-1]
ConvertTo-Json -InputObject @{ code = $code; said = @($said); calls = @($calls).Count } -Compress
""" % (lit(user), "-Password %s" % lit(password) if password is not None else "")
        refused = run_ps(body, tmp_path)
        assert refused["code"] == 2 and refused["calls"] == 0 and refused["said"][0].startswith(said)


@needs_pwsh
def test_the_validate_step_run_as_a_file_reads_the_password_from_the_environment_and_never_prints_it(tmp_path):
    for password, code in ((PASSWORD, 0), ("short", 2)):
        done = subprocess.run([PWSH, "-NoProfile", "-NonInteractive", "-File", str(ENGINE), "-Step", "validate", "-User", "anna"], capture_output=True, text=True, timeout=120,
                              env=dict(os.environ, ACK_VS_PASSWORD=password, ACK_VS_ENGINE_LOG=str(tmp_path / "e.log")))
        assert done.returncode == code and password not in done.stdout + done.stderr


# ================================================================ taking the Start menu entry away

def shortcuts(tmp_path, names):
    folder = tmp_path / "Programs"
    folder.mkdir(exist_ok=True)
    for name in names:
        (folder / name).write_text("lnk")
    return folder


def unlauncher(tmp_path, descriptions, options=""):
    folder = shortcuts(tmp_path, list(descriptions) + ["Something Else.lnk"])
    body = PRELUDE % {"replies": "@{}", "elevate": "@{}", "facts": lit(FACTS_OK), "found": "''", "program": "@{}"} + """
$descriptions = %s
$describe = { param($p) $n = Split-Path -Leaf $p; if ($descriptions.ContainsKey($n)) { $descriptions[$n] } else { 'unrelated' } }
$code = @(Invoke-AckVsEngine -Step 'unlauncher' %s -Say $say -ProgramsFolder %s -Describe $describe)[-1]
ConvertTo-Json -InputObject @{ code = $code; said = @($said) } -Compress
""" % (table(descriptions), options, lit(str(folder)))
    return run_ps(body, tmp_path), sorted(p.name for p in folder.iterdir())


@needs_pwsh
def test_only_start_menu_entries_that_carry_this_tools_marker_are_taken_away(tmp_path):
    result, left = unlauncher(tmp_path, {"ACK Voice Studio (Ubuntu-24.04).lnk": "Opens the window. [ack-voice-studio-launcher]", "ACK Voice Studio (Mine).lnk": "my own shortcut"})
    assert result["code"] == 0 and left == ["ACK Voice Studio (Mine).lnk", "Something Else.lnk"]
    assert "The Start menu entry ACK Voice Studio (Ubuntu-24.04).lnk was taken away." in result["said"]
    assert "The Start menu entry ACK Voice Studio (Mine).lnk was not made by this tool, so it was left alone." in result["said"]


@needs_pwsh
def test_with_no_entry_of_this_tool_nothing_is_removed_and_the_step_still_succeeds(tmp_path):
    result, left = unlauncher(tmp_path, {})
    assert result["code"] == 0 and left == ["Something Else.lnk"] and result["said"] == ["No Start menu entry of this tool was found."]


@needs_pwsh
def test_the_dry_run_of_taking_the_entry_away_removes_nothing(tmp_path):
    result, left = unlauncher(tmp_path, {"ACK Voice Studio (Ubuntu-24.04).lnk": "[ack-voice-studio-launcher]"}, options="-DryRun")
    assert result["code"] == 0 and "ACK Voice Studio (Ubuntu-24.04).lnk" in left and any("remove ACK Voice Studio (Ubuntu-24.04).lnk" in s for s in result["said"])


@needs_pwsh
def test_a_missing_programs_folder_is_no_entry_not_an_error(tmp_path):
    body = PRELUDE % {"replies": "@{}", "elevate": "@{}", "facts": lit(FACTS_OK), "found": "''", "program": "@{}"} + """
$code = @(Invoke-AckVsEngine -Step 'unlauncher' -Say $say -ProgramsFolder %s)[-1]
ConvertTo-Json -InputObject @{ code = $code; said = @($said) } -Compress
""" % lit(str(tmp_path / "nowhere"))
    result = run_ps(body, tmp_path)
    assert result["code"] == 0 and result["said"] == ["No Start menu entry of this tool was found."]


def test_the_marker_and_the_name_pattern_are_the_ones_the_tool_itself_puts_on_its_entry():
    from voice_studio.core import winshortcut
    body = ENGINE.read_text(encoding="ascii")
    assert "ShortcutMarker  = '%s'" % winshortcut.MARKER in body
    assert "ShortcutPattern = 'ACK Voice Studio (*).lnk'" in body and winshortcut.shortcut_name("ACK Voice Studio", "Ubuntu-24.04") == "ACK Voice Studio (Ubuntu-24.04)"


# ================================================================ a restart, and carrying on after it (found on the first real run: the wizard asked for a restart and, run again, started over)

T1, T2 = "2026-10-18T08:00:00Z", "2026-10-18T09:30:00Z"


@needs_pwsh
@pytest.mark.parametrize("answers", [{"-l -v": 1, "--status": 0, "--version": 1}, {"-l -v": 1, "--status": 1, "--version": 0}, {"-l -v": 0, "--status": 1, "--version": 1}])
def test_wsl_that_answers_any_one_of_its_three_questions_is_set_up_even_with_no_ubuntu_installed(tmp_path, answers):
    """`wsl -l -v` fails when WSL is fine and no Ubuntu is there yet; taking that for "no WSL" is what asked for a restart again and again."""
    replies = {k: reply(["x"] if c == 0 else [], code=c) for k, c in answers.items()}
    result = engine(tmp_path, "platform", replies=replies)
    assert result["code"] == 0 and result["elevated"] == [] and "WSL is already set up." in result["said"]
    assert state_of(tmp_path)["platform"] == "done"


@needs_pwsh
def test_the_questions_are_asked_in_order_and_stop_at_the_first_answer(tmp_path):
    result = engine(tmp_path, "platform", replies={"-l -v": reply([], code=1), "--status": reply(["Default Version: 2"])})
    assert args_of(result) == ["-l -v", "--status"]


@needs_pwsh
def test_what_each_question_got_is_kept_in_the_log_for_reading_a_stop_afterwards(tmp_path):
    engine(tmp_path, "platform", replies=no_wsl("Windows Subsystem for Linux is not installed."), elevate={"Ran": True, "Code": 3010, "Declined": False}, boot=T1)
    log = (tmp_path / "engine.log").read_text()
    assert "wsl wsl.exe -l -v -> ran=True code=1 first=Windows Subsystem for Linux is not installed." in log
    assert "wsl wsl.exe --status -> ran=True code=1" in log and "wsl wsl.exe --version -> ran=True code=1" in log
    assert re.search(r"platform restart asked for \(install code 3010, Windows started %s\)" % T1, log)


@needs_pwsh
@pytest.mark.parametrize("code", [0, 3010])
def test_a_restart_that_is_asked_for_is_remembered_with_the_time_windows_started(tmp_path, code):
    result = engine(tmp_path, "platform", replies=no_wsl(), elevate={"Ran": True, "Code": code, "Declined": False}, boot=T1)
    assert result["code"] == 3
    assert state_of(tmp_path)["platform"] == "restart" and state_of(tmp_path)["platform_boot"] == T1


@needs_pwsh
def test_run_again_before_the_restart_waits_and_does_not_set_up_wsl_again(tmp_path):
    result = engine(tmp_path, "platform", replies=no_wsl(), state={"platform": "restart", "platform_boot": T1}, boot=T1)
    assert result["code"] == 3 and result["elevated"] == []
    assert any("has not restarted since" in s and "choose Restart, not Shut down" in s for s in result["said"])
    assert state_of(tmp_path)["platform"] == "restart"                       # still waiting, nothing forgotten


@needs_pwsh
def test_run_again_after_the_restart_carries_on_when_wsl_answers(tmp_path):
    result = engine(tmp_path, "platform", replies={"-l -v": reply([], code=1), "--status": reply(["Default Version: 2"])}, state={"platform": "restart", "platform_boot": T1}, boot=T2)
    assert result["code"] == 0 and result["elevated"] == []
    assert state_of(tmp_path)["platform"] == "done" and "platform_boot" not in state_of(tmp_path)


@needs_pwsh
def test_run_again_after_the_restart_with_wsl_still_silent_says_why_and_does_not_ask_for_another_restart(tmp_path):
    result = engine(tmp_path, "platform", replies=no_wsl(), state={"platform": "restart", "platform_boot": T1}, boot=T2)
    assert result["code"] == 1 and result["elevated"] == []
    message = " ".join(result["said"])
    assert "restarted since, but WSL still does not answer" in message and "must restart" not in message and "virtualization" in message and "installer.log" in message
    assert state_of(tmp_path)["platform"] == "failed"


@needs_pwsh
def test_after_that_stop_the_next_run_tries_the_set_up_once_more(tmp_path):
    result = engine(tmp_path, "platform", replies=no_wsl(), state={"platform": "failed"}, boot=T2, elevate={"Ran": True, "Code": 3010, "Declined": False})
    assert result["code"] == 3 and len(result["elevated"]) == 1
    assert state_of(tmp_path)["platform"] == "restart" and state_of(tmp_path)["platform_boot"] == T2


@needs_pwsh
@pytest.mark.parametrize("before, now, restarted", [(T1, T1, False), (T1, T2, True), ("", T2, True), (T1, "", True), ("", "", True)])
def test_a_restart_is_told_by_the_time_windows_started_and_an_unknown_time_never_waits_for_ever(tmp_path, before, now, restarted):
    assert call("Test-AckVsEngRestarted -Before %s -Now %s" % (lit(before), lit(now)), tmp_path) is restarted


@needs_pwsh
def test_the_boot_stamp_is_utc_text_or_nothing(tmp_path):
    stamp = call("Get-AckVsEngBootStamp", tmp_path)
    assert stamp == "" or re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", stamp)


@needs_pwsh
def test_a_dry_run_of_the_wsl_step_remembers_nothing(tmp_path):
    engine(tmp_path, "platform", replies=no_wsl(), options="-DryRun", boot=T1)
    engine(tmp_path, "platform", replies={"-l -v": reply(["x"])}, options="-DryRun", boot=T1)
    assert state_of(tmp_path) == {}


@needs_pwsh
def test_a_declined_permission_and_a_failed_install_leave_no_restart_waiting(tmp_path):
    engine(tmp_path, "platform", replies=no_wsl(), elevate={"Ran": False, "Code": 1, "Declined": True}, boot=T1)
    engine(tmp_path, "platform", replies=no_wsl(), elevate={"Ran": True, "Code": 5, "Declined": False}, boot=T1)
    assert "platform" not in state_of(tmp_path)


# ---------------------------------------------------------------- the check reads it

@needs_pwsh
def test_the_check_after_an_unfinished_restart_says_so_before_an_account_and_a_password_are_asked_for(tmp_path):
    result, (values, lines) = check(tmp_path, replies=no_wsl(), options="-BootStamp { return %s }" % lit(T1))
    # (no state yet: an ordinary computer without WSL)
    assert values["restart_needed"] == "0" and values["needs_platform"] == "1"
    (tmp_path / "state.ini").write_text("platform=restart\r\nplatform_boot=%s\r\n" % T1, encoding="ascii")
    result, (values, lines) = check(tmp_path, replies=no_wsl(), options="-BootStamp { return %s }" % lit(T1))
    assert result["code"] == 0 and values["restart_needed"] == "1" and values["stop"] == "0"
    assert any(line.startswith("warn|") and "has not restarted since" in line for line in lines.values())
    assert args_of(result) == ["-l -v", "--status", "--version"]               # it does not go on to look for Ubuntu or an account


@needs_pwsh
def test_the_check_after_the_restart_goes_on_and_needs_no_restart(tmp_path):
    (tmp_path / "state.ini").write_text("platform=restart\r\nplatform_boot=%s\r\n" % T1, encoding="ascii")
    result, (values, lines) = check(tmp_path, replies={"-l -v": reply([], code=1), "--status": reply(["Default Version: 2"])}, options="-BootStamp { return %s }" % lit(T2))
    assert (values["restart_needed"], values["needs_platform"], values["wsl"], values["needs_distro"], values["needs_account"]) == ("0", "0", "ready", "1", "1")


@needs_pwsh
def test_the_check_after_the_restart_with_wsl_silent_does_not_wait_again_and_leaves_the_stop_to_the_step(tmp_path):
    (tmp_path / "state.ini").write_text("platform=restart\r\nplatform_boot=%s\r\n" % T1, encoding="ascii")
    result, (values, _lines) = check(tmp_path, replies=no_wsl(), options="-BootStamp { return %s }" % lit(T2))
    assert (values["restart_needed"], values["needs_platform"]) == ("0", "1")


@needs_pwsh
def test_the_check_names_the_step_the_last_run_got_to_and_the_account_and_ubuntu_it_used(tmp_path):
    (tmp_path / "state.ini").write_text("stage=distro\r\naccount=anna\r\ndistro=Ubuntu-24.04\r\n", encoding="ascii")
    result, (values, lines) = check(tmp_path, replies={"-l -v": reply(["x"], code=1), "--status": reply(["Default Version: 2"])})
    assert (values["state_stage"], values["state_account"], values["state_distro"]) == ("distro", "anna", "Ubuntu-24.04")
    assert any("An earlier run of this setup got as far as the step distro. This run carries on from there." in line for line in lines.values())


@needs_pwsh
def test_with_nothing_left_by_an_earlier_run_the_check_says_nothing_about_one(tmp_path):
    result, (values, lines) = check(tmp_path, replies={"-l -v": reply([])})
    assert (values["state_stage"], values["state_account"], values["state_distro"]) == ("", "", "")
    assert not any("earlier run" in line for line in lines.values())


# ---------------------------------------------------------------- what is written down

@needs_pwsh
def test_a_step_that_succeeds_writes_down_how_far_it_got_and_what_it_was_given(tmp_path):
    engine(tmp_path, "user", replies={"id -u anna": reply(["1000"]), "passwd -S": reply(["P"])}, options="-Distro Ubuntu-24.04 -User anna", password=PASSWORD)
    state = state_of(tmp_path)
    assert (state["stage"], state["account"]) == ("user", "anna") and re.fullmatch(r"\d{4}-\d\d-\d\d \d\d:\d\d:\d\d", state["updated"])
    engine(tmp_path, "distro", replies={"-l -v": reply(LISTING)}, options="-Distro Ubuntu-24.04")
    assert (state_of(tmp_path)["stage"], state_of(tmp_path)["distro"]) == ("distro", "Ubuntu-24.04")
    engine(tmp_path, "setup", options="-Distro Ubuntu-24.04 -User anna")
    assert state_of(tmp_path)["stage"] == "setup" and state_of(tmp_path)["account"] == "anna"


@needs_pwsh
@pytest.mark.parametrize("step, options, program_replies", [("user", "-Distro Ubuntu-24.04 -User anna", {"useradd": reply([], code=9), "id -u anna": reply([], code=1)}),
                                                            ("setup", "-Distro Ubuntu-24.04 -User anna", {"bash -c": reply([], code=1)})])
def test_a_step_that_fails_changes_nothing_in_what_was_written_down(tmp_path, step, options, program_replies):
    engine(tmp_path, step, replies=program_replies, options=options, password=PASSWORD, state={"stage": "platform"})
    assert state_of(tmp_path).get("stage") == "platform" and "account" not in state_of(tmp_path)


@needs_pwsh
def test_the_password_is_never_in_what_was_written_down_whatever_the_key_is_called(tmp_path):
    engine(tmp_path, "user", replies={"id -u anna": reply(["1000"]), "passwd -S": reply(["P"])}, options="-Distro Ubuntu-24.04 -User anna", password=PASSWORD)
    run_ps("Update-AckVsEngState -Values @{ password = %s; ack_secret = %s; account_pass = %s; stage = 'x' }\n'null' | ConvertTo-Json -Compress" % (lit(PASSWORD), lit(PASSWORD), lit(PASSWORD)), tmp_path)
    text = (tmp_path / "state.ini").read_text(encoding="ascii")
    assert PASSWORD not in text and "password" not in text and "secret" not in text and "pass" not in text.replace("passwd", "")
    assert state_of(tmp_path)["stage"] == "x"


@needs_pwsh
def test_the_state_file_is_ascii_sorted_with_windows_line_ends_and_leaves_no_scratch_file(tmp_path):
    run_ps("Update-AckVsEngState -Values @{ b = 'two'; a = 'one' }\nUpdate-AckVsEngState -Values @{ c = 'three' }\n'null' | ConvertTo-Json -Compress", tmp_path)
    raw = (tmp_path / "state.ini").read_bytes()
    assert raw.isascii() and raw.endswith(b"\r\n") and b"\n" not in raw.replace(b"\r\n", b"")
    keys = [line.split("=")[0] for line in raw.decode().splitlines()]
    assert keys == sorted(keys) and set(keys) == {"a", "b", "c", "updated"}
    assert not (tmp_path / "state.ini.tmp").exists()


@needs_pwsh
def test_an_empty_value_takes_a_key_away_and_a_bad_key_is_ignored(tmp_path):
    run_ps("Update-AckVsEngState -Values @{ a = 'one'; platform_boot = 'x' }\nUpdate-AckVsEngState -Values @{ platform_boot = ''; 'Bad Key' = 'no'; 'x=y' = 'no' }\n'null' | ConvertTo-Json -Compress", tmp_path)
    assert set(state_of(tmp_path)) == {"a", "updated"}


@needs_pwsh
def test_a_damaged_state_file_reads_as_what_is_good_in_it_and_is_mended_by_the_next_write(tmp_path):
    (tmp_path / "state.ini").write_bytes(b"stage=distro\r\n\xff\xfe junk\r\nBAD KEY=1\r\naccount=" + b"a" * 300 + b"\r\nplatform=restart\r\n")
    state = call("Read-AckVsEngState", tmp_path)
    assert state == {"stage": "distro", "platform": "restart"}                 # the long value and the junk lines are not taken
    run_ps("Update-AckVsEngState -Values @{ stage = 'user' }\n'null' | ConvertTo-Json -Compress", tmp_path)
    assert state_of(tmp_path)["stage"] == "user" and state_of(tmp_path)["platform"] == "restart" and "account" not in state_of(tmp_path)


@needs_pwsh
def test_with_no_place_to_keep_it_nothing_is_written_and_nothing_fails(tmp_path):
    body = "$env:ACK_VS_ENGINE_STATE = ''\n$env:LOCALAPPDATA = ''\nUpdate-AckVsEngState -Values @{ a = '1' }\n$s = Read-AckVsEngState\nConvertTo-Json -InputObject @{ count = $s.Count; path = (Get-AckVsEngStatePath) } -Compress"
    assert run_ps(body, tmp_path) == {"count": 0, "path": ""}


@needs_pwsh
def test_the_state_lives_beside_the_log_in_the_users_local_folder(tmp_path):
    body = "$env:ACK_VS_ENGINE_STATE = ''\n$env:ACK_VS_ENGINE_LOG = ''\n$env:LOCALAPPDATA = %s\nConvertTo-Json -InputObject @{ state = (Get-AckVsEngStatePath); log = (Get-AckVsEngLogPath) } -Compress" % lit(str(tmp_path / "Local"))
    got = run_ps(body, tmp_path)
    assert got["state"].replace("\\", "/").endswith("Local/ack-voice-studio/installer-state.ini") and os.path.dirname(got["state"]) == os.path.dirname(got["log"])


@needs_pwsh
def test_the_state_file_takes_a_key_of_32_letters_and_a_value_of_200_characters_and_nothing_longer(tmp_path):
    (tmp_path / "state.ini").write_bytes(("a" * 32 + "=" + "v" * 200 + "\r\n" + "b" * 33 + "=x\r\n" + "c=" + "v" * 201 + "\r\n").encode("ascii"))
    assert call("Read-AckVsEngState", tmp_path) == {"a" * 32: "v" * 200}
    run_ps("Update-AckVsEngState -Values @{ %s = 'one'; %s = 'two' }\n'null' | ConvertTo-Json -Compress" % ("d" * 32, "e" * 33), tmp_path)
    keys = set(state_of(tmp_path))
    assert "d" * 32 in keys and "e" * 33 not in keys
