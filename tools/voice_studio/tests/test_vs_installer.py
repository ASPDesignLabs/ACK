# SPDX-License-Identifier: GPL-3.0-or-later
"""The Windows setup wizard (`installer/ack-voice-studio.nsi`, `build.sh`, the workflow; plan decision D44, choices P28).

Nothing here can run the wizard: it is a Windows program and the sandbox has no Windows. What is held instead:

* the **rules it must keep**, read from its source: Windows 11 only (the same build number install.ps1 uses), no silent mode, one user and no administrator rights, nothing downloaded by the
  wizard itself, the password only ever put in the environment of the one engine step that needs it and never in a string that is printed, logged, stored or put on a command line, the temporary
  permission always taken away again, the uninstaller removing only the files the installer wrote;
* that **the wizard and the engine agree**: every step the wizard names is a step the engine knows, in the order the design gives, with the same marker and build number;
* that it **builds** (makensis, when it is installed; skipped otherwise) into a real 32-bit Windows program that asks for no administrator rights, with the same bytes every time.

What none of this shows: that the wizard looks right, that its pages work, or that it installs anything on a real Windows (checklist section I18).
"""
import hashlib
import os
import re
import shutil
import struct
import subprocess
import sys
from pathlib import Path

import pytest

PKG = Path(__file__).resolve().parents[1]
REPO = PKG.parents[1]
NSI = PKG / "installer" / "ack-voice-studio.nsi"
BUILD = PKG / "installer" / "build.sh"
ENGINE = PKG / "installer" / "engine.ps1"
INSTALL_PS1 = PKG / "install.ps1"
WORKFLOW = REPO / ".github" / "workflows" / "voice-studio-installer.yml"
MAKENSIS = shutil.which("makensis")
needs_makensis = pytest.mark.skipif(MAKENSIS is None, reason="makensis (NSIS) is not installed")


def read(path):
    return Path(path).read_text(encoding="utf-8")


def code_lines(path):
    """Source lines without a full-line comment (`;` for NSIS) and without the trailing comment."""
    out = []
    for line in read(path).splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(";"):
            continue
        out.append(re.sub(r"\s;\s.*$", "", line))
    return out


NSI_CODE = code_lines(NSI)
NSI_TEXT = "\n".join(NSI_CODE)
GOLDEN = Path(__file__).resolve().parent / "data" / "installer_wizard_golden.txt"
LOGIC_BLOCKS = [("Function", ".onInit"), ("Function", "RunEngineLogged"), ("Function", "RunEngineQuiet"), ("Function", "PasswordIn"), ("Function", "PasswordOut"), ("Function", "AddLine"),
                ("Function", "StripLevel"), ("Function", "SourcesCreate"), ("Function", "LookCreate"), ("Function", "LookNow"), ("Function", "LookLeave"), ("Function", "AccountCreate"),
                ("Function", "AccountLeave"), ("Function", "Fail"), ("Function", "MustRun"), ("Section", '"Install"'), ("Function", "OpenStudio"), ("Section", '"Uninstall"')]


def normal(line):
    """One line of the wizard with its extra spaces gone and every sentence a person reads replaced by <text>, and every position and size on a page by <box>, so that what is left is
    logic: which instruction runs, with which value, in which order."""
    s = " ".join(line.split())
    s = re.sub(r'^(StrCpy \$R0) "(?=[^"]*[A-Za-z ])[^"$]*[A-Za-z][^"]*"$', r'\1 "<text>"', s)
    s = re.sub(r'^(\$\{NSD_Create(?:Label|MLText|Text|Password)\}) [^"]+"(.*)"$', lambda m: m.group(1) + ' <box> "' + ("<text>" if m.group(2) and "$" not in m.group(2) else m.group(2)) + '"', s)
    s = re.sub(r'^(MessageBox MB_[A-Z|_]+) ".*"$', r'\1 "<text>"', s)
    s = re.sub(r'^(StrCpy \$StepText) ".*"$', r'\1 "<text>"', s)
    s = re.sub(r'^(DetailPrint) ".*(?<!\$R0)"$', lambda m: m.group(0) if m.group(0).endswith('"$R0"') else m.group(1) + ' "<text>"', s)
    s = re.sub(r'^(!insertmacro MUI_HEADER_TEXT) ".*"$', r'\1 "<text>"', s)
    return s


def logic_block(kind, name):
    start = next(i for i, l in enumerate(NSI_CODE) if l.strip() == (kind + " " + name))
    end = next(i for i in range(start + 1, len(NSI_CODE)) if NSI_CODE[i].strip() in ("FunctionEnd", "SectionEnd"))
    return [normal(l) for l in NSI_CODE[start + 1:end]]


def golden_text():
    out = []
    for kind, name in LOGIC_BLOCKS:
        out.append("### " + name)
        out += logic_block(kind, name)
    return "\n".join(out) + "\n"


# ================================================================ the source is what the other rules assume it is

def test_the_wizard_is_plain_ascii_and_carries_the_licence_header():
    text = read(NSI)
    text.encode("ascii")
    assert text.startswith("; SPDX-License-Identifier: GPL-3.0-or-later\n")
    assert read(BUILD).splitlines()[1] == "# SPDX-License-Identifier: GPL-3.0-or-later" and read(WORKFLOW).startswith("# SPDX-License-Identifier: GPL-3.0-or-later\n")


def test_it_asks_for_no_administrator_rights_and_works_for_one_user():
    assert re.search(r"^RequestExecutionLevel user$", NSI_TEXT, re.M)
    assert 'InstallDir "$LOCALAPPDATA\\ACK Voice Studio"' in NSI_TEXT
    assert "HKLM" not in NSI_TEXT.replace('HKLM "SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion" "CurrentBuildNumber"', "")      # the one read of the build number, nothing written
    assert not re.search(r"Write(Reg|INI)\w*\s+HKLM", NSI_TEXT) and "$PROGRAMFILES" not in NSI_TEXT and "SetShellVarContext all" not in NSI_TEXT


def test_it_is_windows_11_only_with_the_same_build_number_as_the_command_line_installer():
    build = re.search(r"!define MIN_BUILD (\d+)", NSI_TEXT)
    minimum = re.search(r"MinBuild\s*=\s*(\d+)", read(INSTALL_PS1))
    assert build and minimum and build.group(1) == minimum.group(1) == "22000"
    onInit = NSI_TEXT.split("Function .onInit")[1].split("FunctionEnd")[0]
    assert "CurrentBuildNumber" in onInit and "${If} $0 < ${MIN_BUILD}" in onInit
    refusal = onInit.split("${If} $0 < ${MIN_BUILD}")[1].split("${EndIf}")[0]
    assert "Windows 11" in refusal and "Abort" in refusal and "Nothing was changed" in refusal
    assert "SetRegView 64" in onInit                    # a 32-bit program must read the 64-bit view or it can see the wrong build


def test_there_is_no_silent_mode_because_the_wizard_must_ask_for_an_account_and_a_password():
    onInit = NSI_TEXT.split("Function .onInit")[1].split("FunctionEnd")[0]
    assert re.search(r"IfSilent 0 interactive\n\s*MessageBox MB_OK\|MB_ICONSTOP .*no silent mode.*\n\s*Abort\n\s*interactive:", onInit)


def test_the_wizard_downloads_nothing_and_opens_no_web_page():
    lowered = NSI_TEXT.lower()
    for forbidden in ("inetc", "nsisdl", "http://", "https://", "execshell", "urlmon", "wininet", "winhttp", "nsisdl::", "nsexec::exec \"curl", "bitsadmin", "certutil"):
        assert forbidden not in lowered, forbidden
    assert "sendkeys" not in lowered and "regsvr" not in lowered


def test_the_one_web_address_it_names_is_the_one_install_ps1_fetches_from():
    repo = re.search(r"Repo\s*=\s*'([^']+)'", read(INSTALL_PS1)).group(1)
    host = re.search(r"RawHost\s*=\s*'https://raw\.githubusercontent\.com'", read(INSTALL_PS1))
    assert host and repo == "ASPDesignLabs/ACK"
    assert ("github.com/" + repo) in NSI_TEXT
    assert re.findall(r"[a-z0-9-]+\.(?:com|org|net|io)/[A-Za-z0-9_./-]+", NSI_TEXT) == ["github.com/" + repo]


def test_it_says_before_it_goes_on_where_everything_comes_from_and_that_nothing_is_signed_yet():
    sources = NSI_TEXT.split("Function SourcesCreate")[1].split("FunctionEnd")[0]
    for need in ("holds no copy of ACK", "GPL, version 3 or later", "Ubuntu 24.04 and WSL: from Microsoft", "Ubuntu's archives", "asks before it downloads", "stay on this computer", "sends nothing about you", "is legal advice"):
        assert need in sources, need
    assert "not signed yet" in NSI_TEXT
    order = [m.group(0) for m in re.finditer(r"^(?:!insertmacro MUI_PAGE_\w+|Page custom \w+)", NSI_TEXT, re.M)]
    assert order == ["!insertmacro MUI_PAGE_WELCOME", "!insertmacro MUI_PAGE_LICENSE", "Page custom SourcesCreate", "Page custom LookCreate", "Page custom AccountCreate",
                     "!insertmacro MUI_PAGE_INSTFILES", "!insertmacro MUI_PAGE_FINISH"]


# ================================================================ the password

def password_lines():
    return [l.strip() for l in NSI_CODE if re.search(r"\$Password\b|\$PassBox|\$AgainBox|ACK_VS_PASSWORD", l)]


def test_the_password_is_only_ever_copied_compared_cleared_or_put_in_the_environment():
    allowed = (r"^Var Password\b", r"^StrCpy \$Password \"\"$", r"^\$\{NSD_GetText\} \$PassBox \$Password$", r"^\$\{NSD_GetText\} \$AgainBox \$R9$",
               r"^\$\{If\} \$Password (==|!=) (\"\"|\$R9)$", r"^StrCpy \$1 \$Password$", r"^System::Call 'kernel32::SetEnvironmentVariable\(t \"ACK_VS_PASSWORD\", (t r1|i 0)\)i'$",
               r"^\$\{NSD_CreatePassword\} 0 \d+u 60% 12u \"\"$", r"^Pop \$(PassBox|AgainBox)$")
    uses = password_lines()
    assert uses
    for use in uses:
        assert any(re.search(pattern, use) for pattern in allowed), "an unexpected use of the password: " + use


def test_the_password_is_in_no_message_no_printed_line_no_registry_value_no_file_and_no_command_line():
    for line in NSI_CODE:
        if re.search(r"\$Password|\$PassBox|\$AgainBox|\$1\b", line):
            assert not re.match(r"\s*(DetailPrint|MessageBox|WriteReg\w+|FileWrite|WriteINIStr|nsExec::\w+|ExecWait|Exec|StrCpy \$Step(Extra|Text|Name))\b", line), line
    assert "-Password" not in NSI_TEXT                      # the engine takes it from the environment, never from an option
    assert not re.search(r"\$Step(Extra|Name)\b.*\$(Password|1)\b", NSI_TEXT)


def test_the_password_is_put_in_the_environment_just_before_the_one_step_that_reads_it_and_removed_just_after():
    # two places: the question on the account page (validate) and the install step (user); nowhere else may the pair appear
    pairs = re.findall(r"Call PasswordIn\n(.*?)Call PasswordOut", NSI_TEXT, re.S)
    assert len(pairs) == 2
    assert pairs[0].strip().splitlines()[-1].strip() == "Call RunEngineQuiet" and len(pairs[0].strip().splitlines()) == 1
    assert pairs[1].strip().splitlines()[-1].strip() == "Call RunEngineLogged" and len(pairs[1].strip().splitlines()) == 1
    assert NSI_TEXT.count("Call PasswordIn") == 2 and NSI_TEXT.count("Call PasswordOut") == 2
    before = NSI_TEXT.split("Call PasswordIn")
    assert 'StrCpy $StepName "validate"' in "\n".join(before[0].splitlines()[-3:])
    assert 'StrCpy $StepName "user"' in "\n".join(before[1].splitlines()[-3:])


def test_the_password_variable_is_emptied_after_the_account_is_made_and_on_every_way_out():
    install = NSI_TEXT.split('Section "Install"')[1].split("SectionEnd")[0]
    user_step = install.split('StrCpy $StepName "user"')[1].split("${EndIf}")[0]
    assert user_step.index("Call PasswordOut") < user_step.index('StrCpy $Password ""')
    assert 'StrCpy $Password ""' in NSI_TEXT.split("Function Fail")[1].split("FunctionEnd")[0]
    must = NSI_TEXT.split("Function MustRun")[1].split("FunctionEnd")[0]
    assert 'StrCpy $Password ""' in must.split("${If} $StepCode == 3")[1].split("${EndIf}")[0]               # the restart way out
    leave = NSI_TEXT.split("Function AccountLeave")[1].split("FunctionEnd")[0]
    assert leave.count('StrCpy $R9 ""') == 2


def test_the_account_page_tells_the_person_that_this_wizard_sees_the_password_and_what_it_does_with_it():
    page = NSI_TEXT.split("Function AccountCreate")[1].split("FunctionEnd")[0]
    for need in ("sees the password you type", "once to Ubuntu", "does not save it anywhere", "not in a file, not in a log", "8 to 128", "NSD_CreatePassword"):
        assert need in page, need
    assert page.count("${NSD_CreatePassword}") == 2


def test_an_existing_account_is_used_and_its_password_is_neither_asked_for_nor_changed():
    page = NSI_TEXT.split("Function AccountCreate")[1].split("FunctionEnd")[0]
    assert re.search(r"\$\{If\} \$NeedsAccount == 0\n\s*Abort\b", page)
    install = NSI_TEXT.split('Section "Install"')[1]
    assert "${If} $NeedsAccount == 1\n    StrCpy $StepName \"user\"" in install


# ================================================================ the steps

def wizard_steps():
    install = NSI_TEXT.split('Section "Install"')[1].split("SectionEnd")[0]
    return re.findall(r'StrCpy \$StepName "([a-z-]+)"', install)


def test_every_step_the_wizard_names_is_one_the_engine_knows():
    engine_steps = re.search(r"\$validSteps = @\(([^)]*)\)", read(ENGINE)).group(1)
    known = set(re.findall(r"'([a-z-]+)'", engine_steps))
    named = set(re.findall(r'StrCpy \$StepName "([a-z-]+)"', NSI_TEXT)) | set(re.findall(r"-Step ([a-z-]+)", NSI_TEXT))
    assert named and named <= known, named - known
    assert known - named == {"help"}


def test_the_install_runs_the_steps_in_the_order_the_design_gives():
    assert wizard_steps() == ["platform", "distro", "user", "sudo-on", "setup", "sudo-off", "launcher"]
    install = NSI_TEXT.split('Section "Install"')[1].split("SectionEnd")[0]
    assert install.index('StrCpy $SudoIsOn 1') < install.index('StrCpy $StepName "setup"') < install.index("StrCpy $SudoIsOn 0")
    assert install.index('StrCpy $StepName "sudo-on"') < install.index('StrCpy $SudoIsOn 1')


def test_the_temporary_permission_is_taken_away_again_whatever_happens_to_the_set_up():
    fail = NSI_TEXT.split("Function Fail")[1].split("FunctionEnd")[0]
    assert re.search(r"\$\{If\} \$SudoIsOn == 1\n\s*StrCpy \$StepName \"sudo-off\"", fail) and "Abort" in fail
    must = NSI_TEXT.split("Function MustRun")[1].split("FunctionEnd")[0]
    assert "Call Fail" in must
    # the set-up and its permission both go through MustRun, which ends in Fail; a restart (code 3) can only come from the first two steps
    install = NSI_TEXT.split('Section "Install"')[1].split("SectionEnd")[0]
    assert re.search(r'StrCpy \$StepName "setup"\n\s*StrCpy \$StepExtra [^\n]*\n\s*Call MustRun', install)
    assert re.search(r'StrCpy \$StepName "sudo-off"\n\s*StrCpy \$StepExtra [^\n]*\n\s*Call RunEngineLogged', install)
    assert "sudo rm /etc/sudoers.d/ack-voice-studio-install" in install and "/etc/sudoers.d/ack-voice-studio-install" in read(ENGINE)


def test_a_restart_a_refusal_and_a_failure_are_each_told_apart_and_stop_the_install_with_a_way_back():
    must = NSI_TEXT.split("Function MustRun")[1].split("FunctionEnd")[0]
    assert "${If} $StepCode == 3" in must and "must restart" in must and "run this setup program again" in must
    assert "${If} $StepCode == 2" in must and "was not allowed" in must
    fail = NSI_TEXT.split("Function Fail")[1].split("FunctionEnd")[0]
    assert "Nothing you made is lost" in fail and "carry on" in fail and "installer.log" in fail
    assert "ack-voice-studio" in read(ENGINE) and "installer.log" in read(ENGINE)


def test_a_missing_start_menu_entry_does_not_fail_the_install_but_a_failed_set_up_does():
    install = NSI_TEXT.split('Section "Install"')[1].split("SectionEnd")[0]
    tail = install.split('StrCpy $StepName "launcher"')[1]
    assert "Call MustRun" not in tail and "Call Fail" not in tail and "still installed" in tail
    assert "Call MustRun" in install.split('StrCpy $StepName "setup"')[1].split('StrCpy $StepName "sudo-off"')[0]


def test_every_powershell_it_starts_is_hidden_non_interactive_and_runs_only_the_engine_file():
    runs = [l.strip() for l in NSI_CODE if "nsExec::" in l]
    assert len(runs) == 3
    for line in runs:
        assert '"$PowerShell" -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "' in line, line
        assert "engine.ps1" in line or "$Engine" in line
        assert not re.search(r"-(Command|EncodedCommand|WindowStyle)\b|Invoke-Expression|\biex\b|DownloadString|-Password", line, re.I)
    assert 'StrCpy $PowerShell "$WINDIR\\Sysnative\\WindowsPowerShell\\v1.0\\powershell.exe"' in NSI_TEXT        # a 32-bit program reaches the real System32 this way
    assert NSI_TEXT.count("Sysnative") == 2 and "$SYSDIR" in NSI_TEXT


def test_the_check_runs_in_a_page_that_changes_nothing_and_blocks_going_on_when_it_says_stop():
    look = NSI_TEXT.split("Function LookNow")[1].split("FunctionEnd")[0]
    assert 'StrCpy $StepName "check"' in look and "-ResultFile" in look and "EnableWindow $NextButton 1" in look
    for step in ("platform", "distro", "user", "sudo", "setup"):
        assert 'StrCpy $StepName "%s' % step not in look
    assert re.search(r"Function LookLeave\n\s*\$\{If\} \$Stopped != 0\n\s*Abort", NSI_TEXT)
    for key in ("stop", "needs_platform", "needs_distro", "needs_account", "distro", "user"):
        assert re.search(r'ReadINIStr \S+ "\$CheckFile" "result" "%s"' % key, look), key
        assert re.search(r"\b%s = " % key, read(ENGINE)), key                        # and it is a key the engine really writes


def test_the_files_the_wizard_installs_are_the_files_the_build_stages_and_the_engine_finds_install_ps1_beside_itself():
    install = NSI_TEXT.split('Section "Install"')[1].split("SectionEnd")[0]
    files = sorted(re.findall(r'^\s*File "\$\{STAGE\}\\([^"]+)"$', install, re.M))
    assert files == sorted(["ack.ico", "engine.ps1", "install.ps1", "LICENSE", "NOTICE"])
    assert re.search(r'cp "\$here/engine.ps1" "\$here/\.\./install.ps1" "\$root/LICENSE" "\$root/NOTICE" "\$stage/"', read(BUILD)) and "ack.ico" in read(BUILD)
    assert '$ackVsEngLibrary = Join-Path $PSScriptRoot \'install.ps1\'' in read(ENGINE) and ". $ackVsEngLibrary" in read(ENGINE)


# ================================================================ taking it away

def test_the_uninstaller_removes_only_what_the_installer_wrote_and_never_a_whole_folder_tree():
    removal = NSI_TEXT.split('Section "Uninstall"')[1]
    deletes = re.findall(r'^\s*Delete "([^"]+)"$', removal, re.M)
    assert sorted(deletes) == sorted(["$INSTDIR\\engine.ps1", "$INSTDIR\\install.ps1", "$INSTDIR\\LICENSE", "$INSTDIR\\NOTICE", "$INSTDIR\\ack.ico", "$INSTDIR\\Uninstall.exe"])
    assert [x.split(";")[0].strip() for x in re.findall(r"RMDir\s+(.*)", removal)] == ['"$INSTDIR"']                 # without /r: only if nothing else is in it
    assert "RMDir /r" not in NSI_TEXT and "/REBOOTOK" not in NSI_TEXT
    assert "DeleteRegKey HKCU" in removal and "DeleteRegKey HKLM" not in NSI_TEXT


def test_the_uninstaller_takes_away_the_start_menu_entry_through_the_engine_and_says_what_it_leaves():
    removal = NSI_TEXT.split('Section "Uninstall"')[1]
    assert "-Step unlauncher" in removal and removal.index("-Step unlauncher") < removal.index('Delete "$INSTDIR\\engine.ps1"')
    text = re.search(r'!define MUI_UNCONFIRMPAGE_TEXT_TOP "([^"]+)"', NSI_TEXT).group(1)
    for need in ("does not take away Ubuntu", "recordings, transcripts and voices", "yours and stay"):
        assert need in text, need
    assert not re.search(r"wsl\S*\s+--unregister|--unregister|wsl\.exe", NSI_TEXT)                      # the wizard never removes an Ubuntu or its data


def test_the_add_or_remove_programs_entry_is_for_this_user_only_and_has_no_modify_or_repair():
    entries = dict(re.findall(r'WriteReg(?:Str|DWORD) HKCU "\$\{UNINSTALL_KEY\}" "(\w+)" (.+)', NSI_TEXT))
    assert set(entries) == {"DisplayName", "DisplayVersion", "Publisher", "InstallLocation", "DisplayIcon", "UninstallString", "NoModify", "NoRepair"}
    assert re.search(r"!define UNINSTALL_KEY \"Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\ACKVoiceStudio\"", NSI_TEXT)


# ================================================================ the build script and the workflow

def test_the_build_script_stages_five_files_downloads_nothing_and_does_not_sign():
    text = read(BUILD)
    assert text.startswith("#!/usr/bin/env bash\n") and "set -euo pipefail" in text
    for forbidden in ("curl", "wget", "git ", "signtool", "osslsigncode", "pip ", "sudo", "apt"):
        assert forbidden not in "\n".join(l for l in text.splitlines() if not l.lstrip().startswith("#") and "sudo apt install nsis" not in l), forbidden
    assert subprocess.run(["bash", "-n", str(BUILD)], capture_output=True).returncode == 0


def test_the_build_script_reads_the_version_from_the_tool_and_it_matches_the_program():
    version = re.search(r'^__version__ = "([0-9][0-9.]*)"', read(PKG / "__init__.py"), re.M).group(1)
    assert re.fullmatch(r"\d+\.\d+\.\d+", version)
    sed = re.search(r"sed -n '([^']+)'", read(BUILD)).group(1)
    done = subprocess.run(["sed", "-n", sed, str(PKG / "__init__.py")], capture_output=True, text=True)
    assert done.stdout.strip() == version


def test_the_build_script_says_plainly_when_nsis_is_missing_and_changes_nothing(tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for tool in ("bash", "dirname"):
        (bin_dir / tool).symlink_to(shutil.which(tool))
    done = subprocess.run([str(bin_dir / "bash"), str(BUILD), str(tmp_path / "out")], capture_output=True, text=True, env={"PATH": str(bin_dir)})
    assert done.returncode == 2 and "makensis (NSIS) is not installed" in done.stderr and not (tmp_path / "out").exists()


def test_the_workflow_reads_only_pins_its_actions_signs_nothing_and_publishes_nothing():
    text = read(WORKFLOW)
    assert re.search(r"^permissions:\n  contents: read$", text, re.M)
    for forbidden in ("pull_request_target", "secrets.", "signtool", "osslsigncode", "gh release", "softprops", "contents: write", "id-token", "curl ", "Invoke-WebRequest", "irm "):
        assert forbidden not in text, forbidden
    uses = re.findall(r"uses: ([^\s]+)", text)
    assert uses and all(re.fullmatch(r"actions/[a-z-]+@v\d+", u) for u in uses), uses
    assert "retention-days: 30" in text and "build.sh" in text


# a stand-in for makensis that records what it was given and what the staging folder held, so the script can be tried without NSIS
FAKE_MAKENSIS = """#!/bin/bash
printf '%s\\n' "$@" > "$FAKE_LOG"
for arg in "$@"; do
  case "$arg" in
    -DSTAGE=*) ls -A "${arg#-DSTAGE=}" > "$FAKE_LOG.stage";;
    -DOUTFILE=*) printf 'MZ' > "${arg#-DOUTFILE=}";;
  esac
done
"""


def fake_world(tmp_path, with_python=True):
    """A bin folder with the fake makensis first and the real tools after it; returns (env, log path)."""
    bin_dir = tmp_path / "fakebin"
    bin_dir.mkdir()
    (bin_dir / "makensis").write_text(FAKE_MAKENSIS)
    (bin_dir / "makensis").chmod(0o755)
    log = tmp_path / "fake.log"
    return dict(os.environ, PATH=str(bin_dir) + os.pathsep + os.environ["PATH"], FAKE_LOG=str(log)), log, bin_dir


def test_the_build_script_gives_makensis_the_version_the_stage_and_the_output_and_asks_for_quiet_output(tmp_path):
    env, log, _ = fake_world(tmp_path)
    done = subprocess.run(["bash", str(BUILD), str(tmp_path / "out")], capture_output=True, text=True, env=env, timeout=120)
    assert done.returncode == 0, done.stderr
    version = re.search(r'^__version__ = "([^"]+)"', read(PKG / "__init__.py"), re.M).group(1)
    args = log.read_text().splitlines()
    out = (tmp_path / "out").resolve()
    assert args == ["-V2", "-DSTAGE=%s" % (out / "stage"), "-DVERSION=" + version, "-DOUTFILE=%s" % (out / ("ACK-Voice-Studio-Setup-%s.exe" % version)), str(NSI.parent / "ack-voice-studio.nsi")]
    exe = out / ("ACK-Voice-Studio-Setup-%s.exe" % version)
    assert (out / (exe.name + ".sha256")).read_text() == "%s  %s\n" % (hashlib.sha256(exe.read_bytes()).hexdigest(), exe.name)
    assert sorted(Path(str(log) + ".stage").read_text().split()) == ["LICENSE", "NOTICE", "ack.ico", "engine.ps1", "install.ps1"]


def test_the_build_script_clears_an_old_staging_folder_first_so_nothing_stale_goes_in(tmp_path):
    env, log, _ = fake_world(tmp_path)
    (tmp_path / "out" / "stage").mkdir(parents=True)
    (tmp_path / "out" / "stage" / "left-over.txt").write_text("old")
    done = subprocess.run(["bash", str(BUILD), str(tmp_path / "out")], capture_output=True, text=True, env=env, timeout=120)
    assert done.returncode == 0, done.stderr
    assert "left-over.txt" not in Path(str(log) + ".stage").read_text()


def test_the_build_script_ignores_the_callers_python_path_so_a_planted_module_cannot_run(tmp_path):
    env, _, _ = fake_world(tmp_path)
    planted = tmp_path / "planted"
    planted.mkdir()
    (planted / "struct.py").write_text("raise RuntimeError('planted')\n")
    env["PYTHONPATH"] = str(planted)
    done = subprocess.run(["bash", str(BUILD), str(tmp_path / "out")], capture_output=True, text=True, env=env, timeout=120)
    assert done.returncode == 0 and "planted" not in done.stderr, done.stderr


def test_the_build_script_stops_with_two_and_a_plain_line_when_python_is_missing(tmp_path):
    env, _, bin_dir = fake_world(tmp_path)
    for tool in ("bash", "dirname"):
        (bin_dir / tool).symlink_to(shutil.which(tool))
    env["PATH"] = str(bin_dir)
    done = subprocess.run([str(bin_dir / "bash"), str(BUILD), str(tmp_path / "out")], capture_output=True, text=True, env=env, timeout=120)
    assert done.returncode == 2 and "python3 is not installed." in done.stderr and not (tmp_path / "out").exists()


def test_the_build_script_stops_with_one_when_the_version_cannot_be_read_and_makes_nothing(tmp_path):
    tree = tmp_path / "tree"
    (tree / "tools" / "voice_studio" / "installer").mkdir(parents=True)
    for source, target in ((BUILD, "tools/voice_studio/installer/build.sh"), (ENGINE, "tools/voice_studio/installer/engine.ps1"), (INSTALL_PS1, "tools/voice_studio/install.ps1")):
        shutil.copy(source, tree / target)
    (tree / "tools" / "voice_studio" / "__init__.py").write_text("# no version here\n")
    env, _, _ = fake_world(tmp_path)
    done = subprocess.run(["bash", str(tree / "tools/voice_studio/installer/build.sh"), str(tmp_path / "out")], capture_output=True, text=True, env=env, timeout=120)
    assert done.returncode == 1 and "Could not read the version" in done.stderr and not (tmp_path / "out").exists()


def test_the_workflow_expects_the_exit_codes_the_engine_promises():
    text = read(WORKFLOW)
    calls = re.findall(r"& powershell -NoProfile -File \$engine (-Step \w+[^;\n]*); if \(\$LASTEXITCODE -ne (\d)\)", text)
    assert calls == [("-Step help", "0"), ("-Step validate -User anna", "0"), ("-Step validate -User root", "2"), ("-Step distro -Distro Ubuntu-24.04 -User anna -DryRun", "0")]
    password = re.search(r"ACK_VS_PASSWORD: '([^']+)'", text).group(1)
    assert 8 <= len(password) <= 128 and all(0x20 <= ord(c) < 0x7F for c in password)
    assert "Select-String" in text and password in text.split("Select-String")[1]               # the run looks for its own password in the log


# ================================================================ it builds

@pytest.fixture(scope="module")
def built(tmp_path_factory):
    out = tmp_path_factory.mktemp("installer_build")
    done = subprocess.run(["bash", str(BUILD), str(out)], capture_output=True, text=True, timeout=300)
    assert done.returncode == 0, done.stdout[-1500:] + done.stderr[-1500:]
    return out, done


@needs_makensis
def test_it_builds_one_unsigned_32_bit_windows_program_and_its_checksum(built):
    out, done = built
    version = re.search(r'^__version__ = "([^"]+)"', read(PKG / "__init__.py"), re.M).group(1)
    exe = out / ("ACK-Voice-Studio-Setup-%s.exe" % version)
    data = exe.read_bytes()
    assert data[:2] == b"MZ"
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    assert data[pe:pe + 4] == b"PE\0\0" and struct.unpack_from("<H", data, pe + 4)[0] == 0x14C            # 32-bit x86: what NSIS makes, and what Windows 11 runs
    assert 100_000 < len(data) < 5_000_000
    assert (out / (exe.name + ".sha256")).read_text().split()[0] == hashlib.sha256(data).hexdigest()
    assert b"WinVerifyTrust" not in data and b"Signature" not in data[-4096:]                      # nothing is signed (D44)


@needs_makensis
def test_the_program_asks_windows_for_no_administrator_rights_and_names_what_it_is(built):
    out, _ = built
    data = next(out.glob("*.exe")).read_bytes()
    assert b'level="asInvoker"' in data and b"requireAdministrator" not in data and b"highestAvailable" not in data
    assert "ACK Voice Studio setup".encode("utf-16-le") in data and "GPL-3.0-or-later".encode("utf-16-le") in data


@needs_makensis
def test_two_builds_of_the_same_files_give_the_same_bytes(built, tmp_path):
    out, _ = built
    again = subprocess.run(["bash", str(BUILD), str(tmp_path)], capture_output=True, text=True, timeout=300)
    assert again.returncode == 0, again.stderr
    first = next(out.glob("*.exe")).read_bytes()
    assert next(tmp_path.glob("*.exe")).read_bytes() == first


@needs_makensis
def test_the_staging_folder_holds_exactly_the_five_files_and_the_icon_is_a_real_icon(built):
    out, _ = built
    staged = sorted(p.name for p in (out / "stage").iterdir())
    assert staged == ["LICENSE", "NOTICE", "ack.ico", "engine.ps1", "install.ps1"]
    icon = (out / "stage" / "ack.ico").read_bytes()
    assert icon[:4] == b"\0\0\1\0" and struct.unpack_from("<H", icon, 4)[0] == 5
    for name in ("LICENSE", "NOTICE", "install.ps1"):
        source = REPO / name if name in ("LICENSE", "NOTICE") else PKG / name
        assert (out / "stage" / name).read_bytes() == source.read_bytes()
    assert (out / "stage" / "engine.ps1").read_bytes() == ENGINE.read_bytes()


@needs_makensis
def test_the_licence_the_wizard_shows_is_the_byte_identical_one_in_the_repository(built):
    out, _ = built
    assert hashlib.sha256((out / "stage" / "LICENSE").read_bytes()).hexdigest() == hashlib.sha256((REPO / "LICENSE").read_bytes()).hexdigest()


# ================================================================ the logic, line by line

def test_the_logic_of_every_function_and_section_is_exactly_what_was_read_and_approved():
    """The wizard cannot be run here, so its logic is pinned as written: the file `data/installer_wizard_golden.txt` is what each block looks like with the sentences and the page layout taken out
    (`normal`). A change to any instruction, value or order fails here, and the fix is to read the difference and, if it is meant, write the file again with
    `python3 tests/test_vs_installer.py --write`. It exists because deliberate breaks of the wizard (a flag turned over, an instruction removed, a step skipped) mostly got through every
    other test: what the other tests hold are the rules, and this holds the sequence."""
    assert GOLDEN.read_text(encoding="utf-8") == golden_text()


def test_the_start_of_the_file_sets_what_the_build_and_the_program_depend_on():
    head = [l.strip() for l in NSI_CODE[:NSI_CODE.index("!include \"MUI2.nsh\"")]]
    for need in ("Unicode true", "SetCompressor /SOLID lzma", "RequestExecutionLevel user", "ManifestSupportedOS Win10", "SetCompress auto", "SetDateSave off", "CRCCheck on",
                 "!define MIN_BUILD 22000", 'InstallDir "$LOCALAPPDATA\\ACK Voice Studio"', 'InstallDirRegKey HKCU "${UNINSTALL_KEY}" "InstallLocation"', 'VIProductVersion "${VERSION}.0"'):
        assert need in head, need
    assert [l for l in head if l.startswith("!define MUI_") or l.startswith("!insertmacro")] == []        # the page settings come after the includes, so a settings change cannot hide here


def test_the_licence_page_shows_the_licence_and_the_pages_use_the_programs_own_icon():
    assert '!insertmacro MUI_PAGE_LICENSE "${STAGE}\\LICENSE"' in NSI_TEXT
    assert '!define MUI_ICON "${STAGE}\\ack.ico"' in NSI_TEXT and '!define MUI_UNICON "${STAGE}\\ack.ico"' in NSI_TEXT


if __name__ == "__main__":
    if sys.argv[1:] == ["--write"]:
        GOLDEN.write_text(golden_text(), encoding="utf-8")
        print("wrote", GOLDEN)
    else:
        print("usage: python3 tests/test_vs_installer.py --write")
