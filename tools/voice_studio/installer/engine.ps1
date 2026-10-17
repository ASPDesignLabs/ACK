# SPDX-License-Identifier: GPL-3.0-or-later
# ACK Voice Studio installer engine (plan decision D44, choices P28): the Windows-side work of the setup wizard (ack-voice-studio.nsi), one step per run.
#
# The wizard runs this file hidden, once for each step, and reads what it prints and an optional result file. It stands on install.ps1 (the file next to it): the facts about the
# computer, the findings, the way WSL's listing is read and the Ubuntu command that fetches ACK are that file's functions, tested there. What is new here is what a wizard needs and
# a terminal does not: no question is asked in a console, the Ubuntu account is made from the name and password typed into the wizard, and the steps run apart so the wizard can show
# each one.
#
#   -Step check      look at this computer and Ubuntu; change nothing; write the result file
#   -Step platform   set up WSL itself (Windows asks once for permission); needs a restart sometimes
#   -Step distro     install Ubuntu 24.04 (no first-run questions)
#   -Step validate   check an account name and a password (the wizard asks this before it goes on; changes nothing)
#   -Step user       make the Ubuntu account and set its password (a password is only ever set on an account that has none)
#   -Step sudo-on    let that account run the install without asking for the password again, until sudo-off
#   -Step sudo-off   take that permission away again (safe to run at any time)
#   -Step setup      fetch ACK from its source and set up its programs inside Ubuntu (the one command install.ps1 uses, answered yes)
#   -Step launcher   put the Start menu entry in place
#   -Step open       open the window
#   -Step unlauncher take this tool's own Start menu entry away (the uninstaller asks for it)
#   Options: -Distro NAME  -Ref NAME  -User NAME  -ResultFile PATH  -DryRun (show the commands, run none)
#
# The password: typed into the wizard, handed to this file in the environment variable ACK_VS_PASSWORD (never on a command line, where any program could read it), sent to Ubuntu on
# the standard input of one command that sets it, and never written to a file, a log or the screen. It is only read by -Step validate and -Step user, and removed from the environment at once.
# Exit codes: 0 done, 1 something stopped it, 2 not allowed (a name or password that is refused, or a no from Windows), 3 a step is left for the person (restart the computer).
#
# Written for Windows PowerShell 5.1 as well as PowerShell 7: no newer syntax is used, and the file is plain ASCII.
param(
    [string]$Step = 'help',
    [string]$Distro = '',
    [string]$Ref = '',
    [string]$User = '',
    [string]$ResultFile = '',
    [switch]$DryRun
)

$ackVsEngPrevious = $env:ACK_VOICE_NO_AUTORUN
$env:ACK_VOICE_NO_AUTORUN = '1'
$ackVsEngLibrary = Join-Path $PSScriptRoot 'install.ps1'                         # beside this file in the installed copy
if (-not (Test-Path -LiteralPath $ackVsEngLibrary)) { $ackVsEngLibrary = Join-Path (Split-Path -Parent $PSScriptRoot) 'install.ps1' }          # one folder up in the repository
. $ackVsEngLibrary
if ($null -eq $ackVsEngPrevious) { Remove-Item -Path 'Env:ACK_VOICE_NO_AUTORUN' -ErrorAction SilentlyContinue } else { $env:ACK_VOICE_NO_AUTORUN = $ackVsEngPrevious }

function Get-AckVsEngSettings {
    @{
        UserPattern     = '^[a-z_][a-z0-9_-]{0,30}\z'                  # \z, not $: in PowerShell a $ also matches before a trailing line break
        ReservedUsers   = @('root', 'daemon', 'bin', 'sys', 'sync', 'games', 'man', 'lp', 'mail', 'news', 'uucp', 'proxy', 'www-data', 'backup', 'list', 'irc', 'gnats', 'nobody', 'sshd', 'systemd-network', 'systemd-resolve', 'syslog', 'messagebus', 'ubuntu')
        MinPassword     = 8
        MaxPassword     = 128
        SudoFile        = '/etc/sudoers.d/ack-voice-studio-install'
        PlatformSeconds = 1800
        DistroSeconds   = 1800
        StartSeconds    = 600
        SetupSeconds    = 10800
        ShortSeconds    = 120
        LogMaxBytes     = 1048576
        ShortcutMarker  = 'ack-voice-studio-launcher'
        ShortcutPattern = 'ACK Voice Studio (*).lnk'
    }
}

function Get-AckVsEngText {
    @{
        looking         = 'Looking at this computer. Nothing is changed at this step.'
        wsl_ready       = 'WSL is set up.'
        wsl_none        = 'WSL is not set up on this computer yet.'
        distro_none     = 'Ubuntu is not installed yet.'
        distro_found    = 'Ubuntu found: {name}.'
        account_found   = 'Ubuntu account found: {user}. It will be used, and its password is not touched.'
        account_needed  = 'An Ubuntu account will be made from the name and password you give.'
        platform_have   = 'WSL is already set up.'
        platform_run    = 'Setting up WSL. Windows may ask you to allow this. It can take a few minutes.'
        platform_no     = 'Windows was not allowed to set up WSL, so nothing was changed. Run the installer again and choose Yes when Windows asks.'
        platform_failed = 'Windows could not set up WSL (code {code}). Nothing else was changed. Install the latest Windows 11 updates, then run the installer again.'
        platform_restart = 'WSL is set up, but this computer must restart before it can be used. Restart it, then run the installer again. It carries on from here.'
        distro_have     = 'Ubuntu is already installed: {name}.'
        distro_run      = 'Installing Ubuntu from Microsoft. This can take several minutes.'
        distro_start    = 'Starting Ubuntu for the first time.'
        distro_failed   = 'Ubuntu could not be installed or started (code {code}). Nothing else was changed. Run the installer again to try once more.'
        distro_ready    = 'Ubuntu is installed and starts.'
        bad_user        = 'That Ubuntu account name is not allowed. Use lower-case letters, numbers, - and _, start with a letter, and not a name Ubuntu already uses.'
        bad_password    = 'That password is not allowed. Use 8 to 128 letters, numbers and ordinary symbols (no accents, no tabs or line breaks).'
        no_password     = 'No password was given, so the Ubuntu account was not made.'
        user_exists     = 'The Ubuntu account {user} is already there and has a password. Its password was not changed.'
        user_found      = 'The Ubuntu account {user} is already there and has no password yet.'
        valid           = 'That account name and password are fine.'
        unlauncher_gone = 'The Start menu entry {name} was taken away.'
        unlauncher_none = 'No Start menu entry of this tool was found.'
        unlauncher_kept = 'The Start menu entry {name} was not made by this tool, so it was left alone.'
        user_made       = 'The Ubuntu account {user} was made.'
        user_password   = 'Its password was set.'
        user_failed     = 'The Ubuntu account could not be made (code {code}). Nothing else was changed.'
        user_default    = 'Ubuntu will open as {user} from now on.'
        sudo_on         = 'The account may run the install without asking for its password again, until the install ends.'
        sudo_off        = 'That permission was taken away again.'
        sudo_failed     = 'The permission for the install could not be set (code {code}).'
        setup_run       = 'Fetching ACK from its source and setting up its programs inside Ubuntu. This is the long step: it downloads several gigabytes.'
        setup_failed    = 'The set-up inside Ubuntu stopped with code {code}. What it said is above. Run the installer again to carry on from where it stopped.'
        setup_done      = 'The set-up inside Ubuntu is done.'
        launcher_run    = 'Putting ACK Voice Studio in the Start menu.'
        launcher_ok     = 'ACK Voice Studio is in the Start menu.'
        launcher_failed = 'The Start menu entry could not be made (code {code}). ACK Voice Studio is still installed; the Finish page can open it.'
        open_run        = 'Opening ACK Voice Studio.'
        open_failed     = 'ACK Voice Studio could not be opened from here (code {code}). Open it from the Start menu.'
        bad_step        = 'I do not know the step {step}.'
        bad_distro      = 'The Ubuntu name {name} is not allowed.'
        bad_ref         = 'The release name {name} is not allowed.'
        dry_header      = 'Nothing was changed. This is what would run:'
        usage           = 'Steps: check, platform, distro, validate, user, sudo-on, sudo-off, setup, launcher, open, unlauncher. Options: -Distro, -Ref, -User, -ResultFile, -DryRun.'
    }
}

# ---------------------------------------------------------------- what may be typed

function Test-AckVsEngUser {
    param([string]$Name)
    $settings = Get-AckVsEngSettings
    if ([string]::IsNullOrEmpty($Name)) { return $false }
    if ($Name -cnotmatch $settings.UserPattern) { return $false }
    if ($settings.ReservedUsers -contains $Name) { return $false }
    if ($Name -like 'systemd-*') { return $false }
    $true
}

function Test-AckVsEngPassword {
    <# Printable ASCII only, 8 to 128 characters. Anything else is refused rather than guessed at: the password goes through Windows, WSL and Linux, and each could read an accent differently. #>
    param([string]$Password)
    $settings = Get-AckVsEngSettings
    if ($null -eq $Password) { return $false }
    if ($Password.Length -lt $settings.MinPassword -or $Password.Length -gt $settings.MaxPassword) { return $false }
    foreach ($ch in $Password.ToCharArray()) {
        $code = [int]$ch
        if ($code -lt 32 -or $code -gt 126) { return $false }
    }
    $true
}

function Test-AckVsEngResultPath {
    param([string]$Path)
    if ([string]::IsNullOrEmpty($Path)) { return $true }
    ($Path.IndexOfAny([char[]]@([char]0, [char]10, [char]13)) -lt 0) -and ($Path.Length -le 240)
}

# ---------------------------------------------------------------- lines, log, result file

function ConvertTo-AckVsEngLine {
    <# One line as the wizard may show it: no NUL (wsl.exe writes UTF-16), no colour codes, no carriage return, plain ASCII, not endless. #>
    param([string]$Raw)
    if ($null -eq $Raw) { return '' }
    $line = $Raw.Replace([string][char]0, '')
    $line = [regex]::Replace($line, "\x1b\[[0-9;?]*[ -/]*[@-~]", '')
    $line = $line.Replace("`r", '')
    $line = [regex]::Replace($line, '[^\x20-\x7e]', '?')
    $line = $line.TrimEnd()
    if ($line.Length -gt 400) { $line = $line.Substring(0, 400) }
    $line
}

function Get-AckVsEngLogPath {
    if ($env:ACK_VS_ENGINE_LOG) { return $env:ACK_VS_ENGINE_LOG }
    $base = $env:LOCALAPPDATA
    if (-not $base) { return '' }
    Join-Path (Join-Path $base 'ack-voice-studio') 'installer.log'
}

function Write-AckVsEngLog {
    <# A line of what happened, kept so that a helper can read it. Never a password: if the one in the environment appears in a line it is replaced. #>
    param([string]$Step, [string]$Message)
    try {
        $path = Get-AckVsEngLogPath
        if (-not $path) { return }
        $folder = Split-Path -Parent $path
        if ($folder -and -not (Test-Path -LiteralPath $folder)) { New-Item -ItemType Directory -Path $folder -Force | Out-Null }
        $settings = Get-AckVsEngSettings
        if ((Test-Path -LiteralPath $path) -and ((Get-Item -LiteralPath $path).Length -gt $settings.LogMaxBytes)) {
            Move-Item -LiteralPath $path -Destination ($path + '.old') -Force
        }
        $text = ConvertTo-AckVsEngLine -Raw $Message
        $secret = $env:ACK_VS_PASSWORD
        if ($secret -and $text.Contains($secret)) { $text = $text.Replace($secret, '***') }
        $stamp = (Get-Date).ToString('yyyy-MM-dd HH:mm:ss')
        Add-Content -LiteralPath $path -Value ('{0} {1} {2}' -f $stamp, $Step, $text) -Encoding ASCII
    } catch { }
}

function Write-AckVsEngResult {
    <# The result file the wizard reads (an .ini file): [result] key=value, then [lines] with the findings. ASCII, one line each. #>
    param([string]$Path, [hashtable]$Values, [object[]]$Lines)
    if ([string]::IsNullOrEmpty($Path)) { return }
    $out = New-Object System.Text.StringBuilder
    [void]$out.Append("[result]`r`n")
    foreach ($key in ($Values.Keys | Sort-Object)) { [void]$out.Append(('{0}={1}' -f $key, (ConvertTo-AckVsEngLine -Raw ([string]$Values[$key]))) + "`r`n") }
    [void]$out.Append("[lines]`r`n")
    $count = 0
    foreach ($line in @($Lines)) {
        $count++
        [void]$out.Append(('{0}={1}' -f $count, (ConvertTo-AckVsEngLine -Raw ([string]$line))) + "`r`n")
    }
    [void]$out.Append(('count={0}' -f $count) + "`r`n")
    [System.IO.File]::WriteAllText($Path, $out.ToString(), [System.Text.Encoding]::ASCII)
}

# ---------------------------------------------------------------- running programs

function Get-AckVsEngWslProgram {
    $found = Get-Command -Name 'wsl.exe' -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($null -eq $found) { return '' }
    $found.Source
}

function Invoke-AckVsEngProcess {
    <# Runs a program with no window, feeds it InputText on its standard input (and then closes it, so a program that reads input never waits), and returns every line it printed. The lines
       are cleaned (ConvertTo-AckVsEngLine) and, when OnLine is given, passed to it as they arrive. A program still running after TimeoutSec is stopped. #>
    param([string]$Program, [string]$ArgumentLine, [string]$InputText = $null, [int]$TimeoutSec = 600, [scriptblock]$OnLine = $null)
    if (-not $Program) { return @{ Ran = $false; Code = 1; Lines = @() } }
    try {
        $info = New-Object System.Diagnostics.ProcessStartInfo
        $info.FileName = $Program
        $info.Arguments = $ArgumentLine
        $info.UseShellExecute = $false
        $info.CreateNoWindow = $true
        $info.RedirectStandardInput = $true
        $info.RedirectStandardOutput = $true
        $info.RedirectStandardError = $true
        $utf8 = New-Object System.Text.UTF8Encoding($false)
        $info.StandardOutputEncoding = $utf8
        $info.StandardErrorEncoding = $utf8
        $process = New-Object System.Diagnostics.Process
        $process.StartInfo = $info
        [void]$process.Start()
        if ($null -ne $InputText) {
            $bytes = $utf8.GetBytes($InputText)
            $process.StandardInput.BaseStream.Write($bytes, 0, $bytes.Length)
            $process.StandardInput.BaseStream.Flush()
        }
        $process.StandardInput.Close()
        $lines = New-Object System.Collections.ArrayList
        $outTask = $process.StandardOutput.ReadLineAsync()
        $errTask = $process.StandardError.ReadLineAsync()
        $outDone = $false
        $errDone = $false
        $clock = [System.Diagnostics.Stopwatch]::StartNew()
        $timedOut = $false
        while (-not ($outDone -and $errDone)) {
            $moved = $false
            if (-not $outDone -and $outTask.IsCompleted) {
                $raw = $outTask.Result
                if ($null -eq $raw) { $outDone = $true } else {
                    $clean = ConvertTo-AckVsEngLine -Raw $raw
                    [void]$lines.Add($clean)
                    if ($OnLine) { & $OnLine $clean }
                    $outTask = $process.StandardOutput.ReadLineAsync()
                }
                $moved = $true
            }
            if (-not $errDone -and $errTask.IsCompleted) {
                $raw = $errTask.Result
                if ($null -eq $raw) { $errDone = $true } else {
                    $clean = ConvertTo-AckVsEngLine -Raw $raw
                    [void]$lines.Add($clean)
                    if ($OnLine) { & $OnLine $clean }
                    $errTask = $process.StandardError.ReadLineAsync()
                }
                $moved = $true
            }
            if ($clock.Elapsed.TotalSeconds -gt $TimeoutSec) { $timedOut = $true; try { $process.Kill() } catch { }; break }
            if (-not $moved) { Start-Sleep -Milliseconds 40 }
        }
        if (-not $timedOut) { $process.WaitForExit() }
        $code = 1
        if (-not $timedOut -and $null -ne $process.ExitCode) { $code = [int]$process.ExitCode }
        return @{ Ran = $true; Code = $code; Lines = @($lines.ToArray()); TimedOut = $timedOut }
    } catch {
        return @{ Ran = $false; Code = 1; Lines = @() }
    }
}

function Invoke-AckVsEngWsl {
    <# The default way the steps talk to wsl.exe. A request is a hashtable: Arguments (the words after wsl.exe), Input (text for its standard input, or none), TimeoutSec, OnLine. #>
    param([hashtable]$Request)
    $line = Format-AckVsCommandLine -CommandArguments @($Request.Arguments)
    $seconds = 600
    if ($Request.TimeoutSec) { $seconds = [int]$Request.TimeoutSec }
    Invoke-AckVsEngProcess -Program (Get-AckVsEngWslProgram) -ArgumentLine $line -InputText $Request.Input -TimeoutSec $seconds -OnLine $Request.OnLine
}

function Invoke-AckVsEngElevated {
    <# Runs one program with the permission Windows asks the person for. A no, or anything that stops it from starting, is Declined. #>
    param([string]$Program, [string]$ArgumentLine, [int]$TimeoutSec = 1800)
    try {
        $process = Start-Process -FilePath $Program -ArgumentList $ArgumentLine -Verb RunAs -WindowStyle Hidden -PassThru -ErrorAction Stop
        $held = $process.Handle
        if (-not $process.WaitForExit($TimeoutSec * 1000)) { try { $process.Kill() } catch { }; return @{ Ran = $true; Code = 1; Declined = $false } }
        $code = 1
        if ($null -ne $process.ExitCode) { $code = [int]$process.ExitCode }
        return @{ Ran = $true; Code = $code; Declined = $false }
    } catch {
        return @{ Ran = $false; Code = 1; Declined = $true }
    }
}

# ---------------------------------------------------------------- the commands run inside Ubuntu

function New-AckVsEngAsRoot {
    <# wsl.exe arguments that run one bash command in the named Ubuntu as root. The command holds no double quote, so Windows passes it on as one piece. #>
    param([string]$Distro, [string]$Command)
    @('-d', $Distro, '-u', 'root', '--exec', 'bash', '-c', $Command)
}

function New-AckVsEngAsUser {
    param([string]$Distro, [string]$User, [string]$Command)
    @('-d', $Distro, '-u', $User, '--cd', '~', '--exec', 'bash', '-c', $Command)
}

function Get-AckVsEngWslConfCommand {
    <# Makes Ubuntu open as this account from now on, keeping everything else in /etc/wsl.conf. The name has already passed Test-AckVsEngUser. #>
    param([string]$User)
    $script = @'
f=/etc/wsl.conf; touch $f; if grep -q '^\[user\]' $f; then if grep -q '^default=' $f; then sed -i 's/^default=.*/default=USER/' $f; else sed -i '/^\[user\]/a default=USER' $f; fi; else printf '\n[user]\ndefault=USER\n' >> $f; fi
'@
    ($script.Replace('USER', $User) -replace '\r?\n', ' ').Trim()
}

function Get-AckVsEngSudoOnCommand {
    param([string]$User)
    $file = (Get-AckVsEngSettings).SudoFile
    $script = @'
umask 077; printf '# written by the ACK Voice Studio installer; removed when it ends\nUSER ALL=(ALL) NOPASSWD:ALL\n' > FILE && chmod 0440 FILE && visudo -cf FILE >/dev/null || { rm -f FILE; exit 1; }
'@
    ($script.Replace('USER', $User).Replace('FILE', $file) -replace '\r?\n', ' ').Trim()
}

function Get-AckVsEngSudoOffCommand {
    $file = (Get-AckVsEngSettings).SudoFile
    'rm -f ' + $file + ' && test ! -e ' + $file
}

function Get-AckVsEngUsersCommand {
    <# Lists the ordinary accounts: name, id and shell, one per line. #>
    'getent passwd'
}

function ConvertFrom-AckVsEngPasswd {
    <# The first ordinary account (id 1000 to 59999 with a real shell) in a passwd listing, or an empty string. #>
    param([string[]]$Lines)
    $best = $null
    foreach ($raw in @($Lines)) {
        $parts = ([string]$raw).Split(':')
        if ($parts.Count -lt 7) { continue }
        if ($parts[2] -notmatch '^[0-9]+\z') { continue }
        $id = [int]$parts[2]
        if ($id -lt 1000 -or $id -gt 59999) { continue }
        if ($parts[6] -match 'nologin|/false\z') { continue }
        if ($parts[0] -notmatch '^[a-z_][a-z0-9_-]*\z') { continue }
        if ($null -eq $best -or $id -lt $best.Id) { $best = @{ Name = $parts[0]; Id = $id } }
    }
    if ($null -eq $best) { return '' }
    $best.Name
}

function Get-AckVsEngPasswordStatusCommand {
    <# The state of the account's password as Ubuntu keeps it: P (a usable password), L (locked), NP (none). Only P is somebody's. #>
    param([string]$User)
    'passwd -S ' + $User + ' | awk ''{print $2}'''
}

function New-AckVsEngCloudInit {
    <# The file Ubuntu reads on its first start to make the account without asking anything (Canonical's cloud-init for WSL). It sets no password: that is set afterwards, on standard input. #>
    param([string]$User)
    "#cloud-config`nusers:`n  - name: $User`n    groups: [sudo]`n    shell: /bin/bash`nwrite_files:`n  - path: /etc/wsl.conf`n    append: true`n    content: |`n      [user]`n      default=$User`n"
}

function Get-AckVsEngLauncherName {
    <# The Store program that registers an Ubuntu by itself (Ubuntu-24.04 is ubuntu2404.exe), or nothing for a name that does not follow the pattern. #>
    param([string]$Distro)
    if ($Distro -match '^Ubuntu-([0-9]{2})\.([0-9]{2})\z') { return ('ubuntu{0}{1}.exe' -f $Matches[1], $Matches[2]) }
    ''
}

# ---------------------------------------------------------------- the steps

function Get-AckVsEngDefaultWsl {
    { param($r) Invoke-AckVsEngWsl -Request $r }
}

function Step-AckVsEngCheck {
    param([string]$Distro, [string]$ResultFile, [scriptblock]$Say, [scriptblock]$Wsl, [scriptblock]$GetFacts)
    $text = Get-AckVsEngText
    & $Say $text.looking
    $lines = @()
    $stop = $false
    $facts = & $GetFacts
    foreach ($finding in @(Get-AckVsFindings -Facts $facts)) {
        & $Say $finding.Text
        $lines += ($finding.Level + '|' + $finding.Text)
        if ($finding.Level -eq 'stop') { $stop = $true }
    }
    $values = @{ stop = $(if ($stop) { 1 } else { 0 }); wsl = 'none'; distro = ''; user = ''; needs_account = 1; needs_platform = 1; needs_distro = 1; windows_build = $facts.Build; free_gib = $facts.FreeGiB; gpu = $(if ($facts.GpuName) { 1 } else { 0 }) }
    if (-not $stop) {
        $listed = & $Wsl @{ Arguments = @('-l', '-v'); TimeoutSec = 60 }
        $ready = ($listed.Ran -and $listed.Code -eq 0)
        if ($ready) { $values.wsl = 'ready'; $values.needs_platform = 0; $lines += ('ok|' + $text.wsl_ready) } else { $lines += ('info|' + $text.wsl_none) }
        & $Say $(if ($ready) { $text.wsl_ready } else { $text.wsl_none })
        $distros = @(Read-AckVsDistros -Listed $listed -WslCapture { param($a) & $Wsl @{ Arguments = @($a); TimeoutSec = 60 } })
        $pick = Select-AckVsDistro -Distros $distros -Wanted $Distro
        if ($pick.Name -ne '' -and $pick.Why -eq 'old_version') {
            $message = Format-AckVsText (Get-AckVsText).old_wsl_only @{ name = $pick.Name }
            & $Say $message
            $lines += ('stop|' + $message)
            $values.stop = 1
        } elseif ($pick.Name -ne '') {
            $values.distro = $pick.Name
            $values.needs_distro = 0
            $message = Format-AckVsText $text.distro_found @{ name = $pick.Name }
            & $Say $message
            $lines += ('ok|' + $message)
            $passwd = & $Wsl @{ Arguments = (New-AckVsEngAsRoot -Distro $pick.Name -Command (Get-AckVsEngUsersCommand)); TimeoutSec = 60 }
            $existing = ''
            if ($passwd.Ran -and $passwd.Code -eq 0) { $existing = ConvertFrom-AckVsEngPasswd -Lines $passwd.Lines }
            if ($existing -ne '') {
                $values.user = $existing
                $values.needs_account = 0
                $message = Format-AckVsText $text.account_found @{ user = $existing }
            } else {
                $message = $text.account_needed
            }
            & $Say $message
            $lines += ('info|' + $message)
        } else {
            & $Say $text.distro_none
            $lines += ('info|' + $text.distro_none)
            & $Say $text.account_needed
            $lines += ('info|' + $text.account_needed)
        }
    }
    Write-AckVsEngResult -Path $ResultFile -Values $values -Lines $lines
    if ($values.stop -eq 1) { return 1 }
    0
}

function Step-AckVsEngPlatform {
    param([bool]$DryRun, [scriptblock]$Say, [scriptblock]$Wsl, [scriptblock]$Elevate)
    $text = Get-AckVsEngText
    $listed = & $Wsl @{ Arguments = @('-l', '-v'); TimeoutSec = 60 }
    if ($listed.Ran -and $listed.Code -eq 0) { & $Say $text.platform_have; return 0 }
    $arguments = @('--install', '--no-distribution')
    if ($DryRun) { & $Say $text.dry_header; & $Say ('  (with permission) wsl.exe ' + (Format-AckVsCommandLine $arguments)); return 0 }
    & $Say $text.platform_run
    $done = & $Elevate @{ Program = (Get-AckVsEngWslProgram); ArgumentLine = (Format-AckVsCommandLine $arguments); TimeoutSec = (Get-AckVsEngSettings).PlatformSeconds }
    Write-AckVsEngLog -Step 'platform' -Message ('wsl.exe ' + (Format-AckVsCommandLine $arguments) + ' -> ran=' + $done.Ran + ' code=' + $done.Code + ' declined=' + $done.Declined)
    if ($done.Declined) { & $Say $text.platform_no; return 2 }
    if (-not $done.Ran -or ($done.Code -ne 0 -and $done.Code -ne 3010)) { & $Say (Format-AckVsText $text.platform_failed @{ code = $done.Code }); return 1 }
    $listed = & $Wsl @{ Arguments = @('-l', '-v'); TimeoutSec = 60 }
    if ($listed.Ran -and $listed.Code -eq 0) { return 0 }
    & $Say $text.platform_restart
    3
}

function Step-AckVsEngDistro {
    param([string]$Distro, [string]$User, [bool]$DryRun, [scriptblock]$Say, [scriptblock]$Wsl, [scriptblock]$FileExists, [scriptblock]$WriteFile, [scriptblock]$RemoveFile, [string]$ProfileFolder, [scriptblock]$FindProgram, [scriptblock]$RunProgram)
    $text = Get-AckVsEngText
    $settings = Get-AckVsSettings
    $name = $Distro
    if (-not $name) { $name = $settings.InstallDistro }
    $listed = & $Wsl @{ Arguments = @('-l', '-v'); TimeoutSec = 60 }
    $distros = @(Read-AckVsDistros -Listed $listed -WslCapture { param($a) & $Wsl @{ Arguments = @($a); TimeoutSec = 60 } })
    $pick = Select-AckVsDistro -Distros $distros -Wanted $Distro
    if ($pick.Name -ne '') { & $Say (Format-AckVsText $text.distro_have @{ name = $pick.Name }); return 0 }
    $install = @('--install', '-d', $name, '--no-launch')
    $initFile = ''
    if ($User -and (Test-AckVsEngUser -Name $User) -and $ProfileFolder) { $initFile = Join-Path (Join-Path $ProfileFolder '.cloud-init') ($name + '.user-data') }
    if ($DryRun) {
        & $Say $text.dry_header
        if ($initFile) { & $Say ('  write ' + $initFile + ' (only if there is none)') }
        & $Say ('  wsl.exe ' + (Format-AckVsCommandLine $install))
        & $Say ('  wsl.exe ' + (Format-AckVsCommandLine (New-AckVsEngAsRoot -Distro $name -Command 'cloud-init status --wait; true')))
        return 0
    }
    $wrote = $false
    if ($initFile -and -not (& $FileExists $initFile)) { & $WriteFile $initFile (New-AckVsEngCloudInit -User $User); $wrote = $true }
    & $Say $text.distro_run
    $done = & $Wsl @{ Arguments = $install; TimeoutSec = $settings.DistroSeconds; OnLine = { param($l) & $Say $l } }
    Write-AckVsEngLog -Step 'distro' -Message ('wsl.exe ' + (Format-AckVsCommandLine $install) + ' -> ran=' + $done.Ran + ' code=' + $done.Code)
    $code = $done.Code
    $up = $false
    if ($done.Ran -and $done.Code -eq 0) {
        & $Say $text.distro_start
        $first = & $Wsl @{ Arguments = (New-AckVsEngAsRoot -Distro $name -Command 'cloud-init status --wait; true'); TimeoutSec = $settings.StartSeconds; OnLine = { param($l) & $Say $l } }
        Write-AckVsEngLog -Step 'distro' -Message ('first start -> ran=' + $first.Ran + ' code=' + $first.Code)
        $check = & $Wsl @{ Arguments = (New-AckVsEngAsRoot -Distro $name -Command 'true'); TimeoutSec = $settings.ShortSeconds }
        if ($check.Ran -and $check.Code -eq 0) { $up = $true } else { $code = $check.Code }
    }
    if (-not $up) {
        # The Store program of this Ubuntu can register it without asking anything (`install --root`); tried only when the plain start did not work.
        $launcher = Get-AckVsEngLauncherName -Distro $name
        $program = ''
        if ($launcher) { $program = [string](& $FindProgram $launcher) }
        if ($program) {
            $registered = & $RunProgram @{ Program = $program; ArgumentLine = 'install --root'; TimeoutSec = $settings.StartSeconds; OnLine = { param($l) & $Say $l } }
            Write-AckVsEngLog -Step 'distro' -Message ($launcher + ' install --root -> ran=' + $registered.Ran + ' code=' + $registered.Code)
            $check = & $Wsl @{ Arguments = (New-AckVsEngAsRoot -Distro $name -Command 'true'); TimeoutSec = $settings.ShortSeconds }
            if ($check.Ran -and $check.Code -eq 0) { $up = $true } else { $code = $check.Code }
        }
    }
    if ($wrote) { & $RemoveFile $initFile }
    if (-not $up) { & $Say (Format-AckVsText $text.distro_failed @{ code = $code }); return 1 }
    & $Say $text.distro_ready
    0
}

function Step-AckVsEngUser {
    param([string]$Distro, [string]$User, [string]$Password, [bool]$DryRun, [scriptblock]$Say, [scriptblock]$Wsl)
    $text = Get-AckVsEngText
    $settings = Get-AckVsEngSettings
    if (-not (Test-AckVsEngUser -Name $User)) { & $Say $text.bad_user; return 2 }
    if ([string]::IsNullOrEmpty($Password)) { & $Say $text.no_password; return 2 }
    if (-not (Test-AckVsEngPassword -Password $Password)) { & $Say $text.bad_password; return 2 }
    if ($DryRun) {
        & $Say $text.dry_header
        & $Say ('  wsl.exe ' + (Format-AckVsCommandLine (New-AckVsEngAsRoot -Distro $Distro -Command ('id -u ' + $User))))
        & $Say ('  wsl.exe ' + (Format-AckVsCommandLine (New-AckVsEngAsRoot -Distro $Distro -Command ('useradd -m -s /bin/bash -G sudo ' + $User))))
        & $Say ('  wsl.exe ' + (Format-AckVsCommandLine (@('-d', $Distro, '-u', 'root', '--exec', 'chpasswd'))) + '   (the password is sent on standard input)')
        return 0
    }
    $have = & $Wsl @{ Arguments = (New-AckVsEngAsRoot -Distro $Distro -Command ('id -u ' + $User)); TimeoutSec = $settings.ShortSeconds }
    $present = ($have.Ran -and $have.Code -eq 0)
    if (-not $present) {
        $made = & $Wsl @{ Arguments = (New-AckVsEngAsRoot -Distro $Distro -Command ('useradd -m -s /bin/bash -G sudo ' + $User)); TimeoutSec = $settings.ShortSeconds }
        Write-AckVsEngLog -Step 'user' -Message ('useradd -> ran=' + $made.Ran + ' code=' + $made.Code)
        if (-not $made.Ran -or $made.Code -ne 0) { & $Say (Format-AckVsText $text.user_failed @{ code = $made.Code }); return 1 }
        & $Say (Format-AckVsText $text.user_made @{ user = $User })
    }
    # A password is only ever set on an account that has none: the account just made, or one that Ubuntu's own first start made without asking. One with a password is somebody's.
    $status = & $Wsl @{ Arguments = (New-AckVsEngAsRoot -Distro $Distro -Command (Get-AckVsEngPasswordStatusCommand -User $User)); TimeoutSec = $settings.ShortSeconds }
    $word = ''
    if ($status.Ran -and $status.Code -eq 0) { foreach ($raw in @($status.Lines)) { if (([string]$raw).Trim() -ne '') { $word = ([string]$raw).Trim() } } }
    if ($word -eq 'P') {
        & $Say (Format-AckVsText $text.user_exists @{ user = $User })
    } else {
        if ($present) { & $Say (Format-AckVsText $text.user_found @{ user = $User }) }
        $set = & $Wsl @{ Arguments = @('-d', $Distro, '-u', 'root', '--exec', 'chpasswd'); Input = ($User + ':' + $Password + "`n"); TimeoutSec = $settings.ShortSeconds }
        Write-AckVsEngLog -Step 'user' -Message ('chpasswd -> ran=' + $set.Ran + ' code=' + $set.Code)
        if (-not $set.Ran -or $set.Code -ne 0) { & $Say (Format-AckVsText $text.user_failed @{ code = $set.Code }); return 1 }
        & $Say $text.user_password
    }
    $conf = & $Wsl @{ Arguments = (New-AckVsEngAsRoot -Distro $Distro -Command (Get-AckVsEngWslConfCommand -User $User)); TimeoutSec = $settings.ShortSeconds }
    if (-not $conf.Ran -or $conf.Code -ne 0) { & $Say (Format-AckVsText $text.user_failed @{ code = $conf.Code }); return 1 }
    [void](& $Wsl @{ Arguments = @('--terminate', $Distro); TimeoutSec = 60 })
    & $Say (Format-AckVsText $text.user_default @{ user = $User })
    0
}

function Step-AckVsEngValidate {
    param([string]$User, [string]$Password, [scriptblock]$Say)
    $text = Get-AckVsEngText
    if (-not (Test-AckVsEngUser -Name $User)) { & $Say $text.bad_user; return 2 }
    if (-not (Test-AckVsEngPassword -Password $Password)) { & $Say $text.bad_password; return 2 }
    & $Say $text.valid
    0
}

function Step-AckVsEngSudo {
    param([string]$Distro, [string]$User, [bool]$On, [bool]$DryRun, [scriptblock]$Say, [scriptblock]$Wsl)
    $text = Get-AckVsEngText
    if ($On -and -not (Test-AckVsEngUser -Name $User)) { & $Say $text.bad_user; return 2 }
    $command = $(if ($On) { Get-AckVsEngSudoOnCommand -User $User } else { Get-AckVsEngSudoOffCommand })
    $arguments = New-AckVsEngAsRoot -Distro $Distro -Command $command
    if ($DryRun) { & $Say $text.dry_header; & $Say ('  wsl.exe ' + (Format-AckVsCommandLine $arguments)); return 0 }
    $done = & $Wsl @{ Arguments = $arguments; TimeoutSec = (Get-AckVsEngSettings).ShortSeconds }
    Write-AckVsEngLog -Step 'sudo' -Message ('on=' + $On + ' -> ran=' + $done.Ran + ' code=' + $done.Code)
    if (-not $done.Ran -or $done.Code -ne 0) { & $Say (Format-AckVsText $text.sudo_failed @{ code = $done.Code }); return 1 }
    & $Say $(if ($On) { $text.sudo_on } else { $text.sudo_off })
    0
}

function Get-AckVsEngSetupArguments {
    <# The hand-over install.ps1 builds (fetch get.sh, run it for the chosen release without opening the window), answered yes: the wizard has already asked. #>
    param([string]$Distro, [string]$User, [string]$Ref)
    $command = (New-AckVsHandover -Ref $Ref).Replace('--no-window', '--yes --no-window')
    New-AckVsEngAsUser -Distro $Distro -User $User -Command $command
}

function Step-AckVsEngSetup {
    param([string]$Distro, [string]$User, [string]$Ref, [bool]$DryRun, [scriptblock]$Say, [scriptblock]$Wsl)
    $text = Get-AckVsEngText
    $arguments = Get-AckVsEngSetupArguments -Distro $Distro -User $User -Ref $Ref
    if ($DryRun) { & $Say $text.dry_header; & $Say ('  wsl.exe ' + (Format-AckVsCommandLine $arguments)); return 0 }
    & $Say $text.setup_run
    $done = & $Wsl @{ Arguments = $arguments; TimeoutSec = (Get-AckVsEngSettings).SetupSeconds; OnLine = { param($l) & $Say $l } }
    Write-AckVsEngLog -Step 'setup' -Message ('hand-over -> ran=' + $done.Ran + ' code=' + $done.Code + ' timedout=' + $done.TimedOut)
    if (-not $done.Ran -or $done.Code -ne 0) {
        $code = 1
        if ($done.Ran) { $code = $done.Code }
        & $Say (Format-AckVsText $text.setup_failed @{ code = $code })
        return 1
    }
    & $Say $text.setup_done
    0
}

function Step-AckVsEngLauncher {
    param([string]$Distro, [string]$User, [bool]$DryRun, [scriptblock]$Say, [scriptblock]$Wsl)
    $text = Get-AckVsEngText
    $command = 'PYTHONPATH=$HOME/ack-tools/tools /usr/bin/python3 -m voice_studio.window --install-launcher --yes'
    $arguments = New-AckVsEngAsUser -Distro $Distro -User $User -Command $command
    if ($DryRun) { & $Say $text.dry_header; & $Say ('  wsl.exe ' + (Format-AckVsCommandLine $arguments)); return 0 }
    & $Say $text.launcher_run
    $done = & $Wsl @{ Arguments = $arguments; TimeoutSec = (Get-AckVsEngSettings).StartSeconds; OnLine = { param($l) & $Say $l } }
    Write-AckVsEngLog -Step 'launcher' -Message ('install-launcher -> ran=' + $done.Ran + ' code=' + $done.Code)
    if (-not $done.Ran -or $done.Code -ne 0) {
        $code = 1
        if ($done.Ran) { $code = $done.Code }
        & $Say (Format-AckVsText $text.launcher_failed @{ code = $code })
        return 0                                                 # the programs are installed; the Finish page can still open them, so this is a note and not a failure
    }
    & $Say $text.launcher_ok
    0
}

function Step-AckVsEngOpen {
    <# Opens the window the way the Start menu entry does. The window is held up by a wsl.exe session that stays attached while it is open; this one is started with no window of its own and not waited for. #>
    param([string]$Distro, [string]$User, [bool]$DryRun, [scriptblock]$Say, [scriptblock]$Start)
    $text = Get-AckVsEngText
    $arguments = @('-d', $Distro, '-u', $User, '--cd', '~', '--exec', 'bash', '-c', 'PYTHONPATH=$HOME/ack-tools/tools exec /usr/bin/python3 -m voice_studio.window')
    if ($DryRun) { & $Say $text.dry_header; & $Say ('  wsl.exe ' + (Format-AckVsCommandLine $arguments)); return 0 }
    & $Say $text.open_run
    $done = & $Start @{ Program = (Get-AckVsEngWslProgram); ArgumentLine = (Format-AckVsCommandLine $arguments) }
    if (-not $done.Ran) { & $Say (Format-AckVsText $text.open_failed @{ code = 1 }); return 1 }
    0
}

function Step-AckVsEngUnlauncher {
    <# Takes away the Start menu entry this tool made (and only that: the entry must carry the tool's marker in its description; another with the same name is left alone). #>
    param([string]$ProgramsFolder, [bool]$DryRun, [scriptblock]$Say, [scriptblock]$Describe, [scriptblock]$Remove)
    $text = Get-AckVsEngText
    $settings = Get-AckVsEngSettings
    $names = @()
    if ($ProgramsFolder -and (Test-Path -LiteralPath $ProgramsFolder)) {
        $names = @(Get-ChildItem -LiteralPath $ProgramsFolder -Filter $settings.ShortcutPattern -ErrorAction SilentlyContinue | ForEach-Object { $_.FullName })
    }
    $removed = 0
    foreach ($path in $names) {
        $name = Split-Path -Leaf $path
        $description = [string](& $Describe $path)
        if ($description.Contains($settings.ShortcutMarker)) {
            if ($DryRun) { & $Say $text.dry_header; & $Say ('  remove ' + $name); continue }
            & $Remove $path
            & $Say (Format-AckVsText $text.unlauncher_gone @{ name = $name })
            $removed++
        } else {
            & $Say (Format-AckVsText $text.unlauncher_kept @{ name = $name })
        }
    }
    if ($removed -eq 0 -and -not $DryRun -and @($names).Count -eq 0) { & $Say $text.unlauncher_none }
    0
}

function Start-AckVsEngDetached {
    param([hashtable]$Request)
    try {
        $null = Start-Process -FilePath $Request.Program -ArgumentList $Request.ArgumentLine -WindowStyle Hidden -ErrorAction Stop
        return @{ Ran = $true; Code = 0 }
    } catch { return @{ Ran = $false; Code = 1 } }
}

# ---------------------------------------------------------------- the whole thing

function Invoke-AckVsEngine {
    param(
        [string]$Step, [string]$Distro, [string]$Ref, [string]$User, [string]$ResultFile, [switch]$DryRun,
        [scriptblock]$Say = { param($line) Write-Host $line },
        [scriptblock]$Wsl = (Get-AckVsEngDefaultWsl),
        [scriptblock]$Elevate = { param($r) Invoke-AckVsEngElevated -Program $r.Program -ArgumentLine $r.ArgumentLine -TimeoutSec $r.TimeoutSec },
        [scriptblock]$Start = { param($r) Start-AckVsEngDetached -Request $r },
        [scriptblock]$GetFacts = { Get-AckVsFacts },
        [scriptblock]$FileExists = { param($p) Test-Path -LiteralPath $p },
        [scriptblock]$WriteFile = { param($p, $t) $d = Split-Path -Parent $p; if (-not (Test-Path -LiteralPath $d)) { New-Item -ItemType Directory -Path $d -Force | Out-Null }; [System.IO.File]::WriteAllText($p, $t, (New-Object System.Text.UTF8Encoding($false))) },
        [scriptblock]$RemoveFile = { param($p) Remove-Item -LiteralPath $p -Force -ErrorAction SilentlyContinue },
        [scriptblock]$FindProgram = { param($n) $c = Get-Command -Name $n -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1; if ($c) { $c.Source } else { '' } },
        [scriptblock]$RunProgram = { param($r) Invoke-AckVsEngProcess -Program $r.Program -ArgumentLine $r.ArgumentLine -TimeoutSec $r.TimeoutSec -OnLine $r.OnLine },
        [string]$ProfileFolder = $env:USERPROFILE,
        [string]$ProgramsFolder = [Environment]::GetFolderPath('Programs'),
        [scriptblock]$Describe = { param($p) try { (New-Object -ComObject WScript.Shell).CreateShortcut($p).Description } catch { '' } },
        [scriptblock]$Remove = { param($p) Remove-Item -LiteralPath $p -Force -ErrorAction SilentlyContinue },
        [string]$Password = $null
    )
    $text = Get-AckVsEngText
    $settings = Get-AckVsSettings
    $validSteps = @('help', 'check', 'platform', 'distro', 'validate', 'user', 'sudo-on', 'sudo-off', 'setup', 'launcher', 'open', 'unlauncher')
    if ($validSteps -notcontains $Step) { & $Say (Format-AckVsText $text.bad_step @{ step = $Step }); return 2 }
    if ($Step -eq 'help') { & $Say $text.usage; return 0 }
    if (-not $Ref) { $Ref = $settings.DefaultRef }
    if (-not (Test-AckVsRefName $Ref)) { & $Say (Format-AckVsText $text.bad_ref @{ name = $Ref }); return 2 }
    if ($Distro -and -not (Test-AckVsDistroName $Distro)) { & $Say (Format-AckVsText $text.bad_distro @{ name = $Distro }); return 2 }
    if (-not (Test-AckVsEngResultPath $ResultFile)) { & $Say 'The result file path is not allowed.'; return 2 }
    if ($User -and -not (Test-AckVsEngUser -Name $User) -and $Step -in @('user', 'validate', 'sudo-on', 'setup', 'launcher', 'open')) { & $Say $text.bad_user; return 2 }
    $dry = [bool]$DryRun.IsPresent
    Write-AckVsEngLog -Step $Step -Message ('start distro=' + $Distro + ' ref=' + $Ref + ' user=' + $User + ' dry=' + $dry)
    $code = 1
    switch ($Step) {
        'check'     { $code = Step-AckVsEngCheck -Distro $Distro -ResultFile $ResultFile -Say $Say -Wsl $Wsl -GetFacts $GetFacts }
        'platform'  { $code = Step-AckVsEngPlatform -DryRun $dry -Say $Say -Wsl $Wsl -Elevate $Elevate }
        'distro'    { $code = Step-AckVsEngDistro -Distro $Distro -User $User -DryRun $dry -Say $Say -Wsl $Wsl -FileExists $FileExists -WriteFile $WriteFile -RemoveFile $RemoveFile -ProfileFolder $ProfileFolder -FindProgram $FindProgram -RunProgram $RunProgram }
        'validate'  { $code = Step-AckVsEngValidate -User $User -Password $Password -Say $Say }
        'user'      { $code = Step-AckVsEngUser -Distro $Distro -User $User -Password $Password -DryRun $dry -Say $Say -Wsl $Wsl }
        'sudo-on'   { $code = Step-AckVsEngSudo -Distro $Distro -User $User -On $true -DryRun $dry -Say $Say -Wsl $Wsl }
        'sudo-off'  { $code = Step-AckVsEngSudo -Distro $Distro -User $User -On $false -DryRun $dry -Say $Say -Wsl $Wsl }
        'setup'     { $code = Step-AckVsEngSetup -Distro $Distro -User $User -Ref $Ref -DryRun $dry -Say $Say -Wsl $Wsl }
        'launcher'  { $code = Step-AckVsEngLauncher -Distro $Distro -User $User -DryRun $dry -Say $Say -Wsl $Wsl }
        'open'      { $code = Step-AckVsEngOpen -Distro $Distro -User $User -DryRun $dry -Say $Say -Start $Start }
        'unlauncher' { $code = Step-AckVsEngUnlauncher -ProgramsFolder $ProgramsFolder -DryRun $dry -Say $Say -Describe $Describe -Remove $Remove }
    }
    Write-AckVsEngLog -Step $Step -Message ('end code=' + $code)
    [int]$code
}

# Run it, unless a test only wants the functions. The password is taken from the environment here, once, and removed from it before anything else runs.
if (-not $env:ACK_VOICE_NO_AUTORUN) {
    $ackVsEngPassword = $null
    if ($Step -eq 'user' -or $Step -eq 'validate') { $ackVsEngPassword = $env:ACK_VS_PASSWORD }
    $env:ACK_VS_PASSWORD = $null
    Remove-Item -Path 'Env:ACK_VS_PASSWORD' -ErrorAction SilentlyContinue
    $ackVsEngCode = [int]@(Invoke-AckVsEngine -Step $Step -Distro $Distro -Ref $Ref -User $User -ResultFile $ResultFile -DryRun:$DryRun -Password $ackVsEngPassword)[-1]
    $ackVsEngPassword = $null
    exit $ackVsEngCode
}
