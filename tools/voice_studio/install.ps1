# SPDX-License-Identifier: GPL-3.0-or-later
# ACK Voice Studio on Windows: one command from PowerShell that ends at the window (plan task VS-7.1 and VS-7.2).
#
#   irm https://raw.githubusercontent.com/ASPDesignLabs/ACK/main/tools/voice_studio/install.ps1 | iex
#
# What it does, in order, and asks before each change:
#   1. Looks at this computer (Windows version, virtualization, graphics driver, free room). Changes nothing.
#   2. Looks for WSL with an Ubuntu 22.04 or 24.04 in it. If there is none, it offers to install Ubuntu 24.04 (needs PowerShell opened as administrator, and a restart).
#   3. Makes sure Ubuntu has a user (the Ubuntu first run), then starts the Ubuntu part inside it: the one command of tools/voice_studio/get.sh, which fetches ACK, installs the few
#      Ubuntu programs it lists (Ubuntu asks for its own password, in this window) and sets up the programs. It is told not to open the window itself (--no-window).
#   4. Opens the window as a second wsl.exe session that this script stays attached to until the window is closed. WSL stops an Ubuntu that has no session open from Windows, about a
#      minute after the last one ends, and the window would go with it; a window started and left behind by the first session would not be held up.
#
# It never asks for or sees a password, never changes PowerShell's execution policy or any Windows setting, installs nothing on Windows beyond what `wsl --install` itself does, and
# makes no web request of its own. It is safe to run again: it carries on from where it stopped.
#
# Settings: the options below, or the same as environment variables (a pipe into iex cannot take options):
#   -Ref NAME      ACK_VOICE_TAG       the release, tag or branch of ACK to fetch (default: the one written in this file)
#   -Distro NAME   ACK_VOICE_DISTRO    use this WSL distribution (default: an Ubuntu 24.04 or 22.04 that is already there, else install Ubuntu-24.04)
#   -Check         ACK_VOICE_CHECK=1   only look: say what is missing and what would be done; change nothing
#   -DryRun        ACK_VOICE_DRYRUN=1  as -Check, and also print the exact commands that would run
#   -Yes           ACK_VOICE_YES=1     you have already said yes to the questions it asks (it still needs administrator rights to install WSL)
#   -Help
# Exit codes: 0 done (or only looked), 1 something stopped it, 2 nothing was done (declined, nobody to ask, an option not understood),
#             3 a step is left for you (restart the computer, or open Ubuntu once); do it, then run the same command again.
#
# Written for Windows PowerShell 5.1 as well as PowerShell 7: no newer syntax is used, and the file is plain ASCII.

function Get-AckVsSettings {
    @{
        Repo           = 'ASPDesignLabs/ACK'
        DefaultRef     = 'main'              # what is fetched when nothing is chosen; get.sh holds the same word. A release name replaces it when one is cut.
        InstallDistro  = 'Ubuntu-24.04'
        Accepted       = @('Ubuntu-24.04', 'Ubuntu-22.04', 'Ubuntu')
        MinBuild       = 22000               # Windows 11 (version 21H2), the first Windows 11. Windows 10 is not supported: virtualization and WSL cannot be counted on there.
        MinFreeGiB     = 25                  # the tool's own bare minimum (docs/VOICE_STUDIO_IT_GUIDE.md section 3)
        GetScript      = 'tools/voice_studio/get.sh'
        RawHost        = 'https://raw.githubusercontent.com'
        OneLiner       = 'irm https://raw.githubusercontent.com/ASPDesignLabs/ACK/main/tools/voice_studio/install.ps1 | iex'
    }
}

function Get-AckVsText {
    @{
        title          = 'ACK Voice Studio: setting up on Windows'
        intro          = 'This sets up ACK Voice Studio inside Ubuntu on this computer and then opens it. It asks before it changes anything. It never asks for your Windows password and never changes PowerShell''s script rules.'
        looking        = 'Looking at this computer. Nothing is changed at this step.'
        windows_old    = 'ACK Voice Studio needs Windows 11, and this computer has an older Windows. Nothing was changed. Update to Windows 11 if this computer can, then run this again.'
        windows_ok     = 'Windows: ok (build {build}).'
        not_64         = 'This is not a 64-bit Windows, so Ubuntu cannot be set up here.'
        virt_off       = 'Virtualization looks switched off. Linux in Windows needs it. It is a setting in the computer''s startup settings (the firmware), and where it is differs from one computer to the next.'
        gpu_found      = 'Nvidia graphics driver: {name}, version {driver}.'
        gpu_none       = 'No Nvidia graphics driver was found on the Windows side. You can still record, listen and prepare training sets. Training the voice needs an Nvidia graphics card and its Windows driver.'
        disk_low       = 'Only {free} GB is free on drive {drive}. The tool needs at least 25 GB free and works best with more.'
        disk_ok        = 'Free room on drive {drive} is {free} GB.'
        no_wsl         = 'WSL (Windows Subsystem for Linux) is not set up on this computer yet.'
        no_ubuntu      = 'WSL is there, but it has no Ubuntu 22.04 or 24.04 yet.'
        old_wsl_only   = 'Ubuntu was found, but as WSL version 1. This needs version 2. To change it, run: wsl --set-version {name} 2'
        found          = 'Ubuntu found: {name}.'
        would_install  = 'It would install Ubuntu 24.04 with: wsl --install -d {name}'
        check_not_ready = 'Not ready yet. Run the same command without -Check to set it up.'
        check_ready    = 'Ready: Ubuntu is there and has a user. Run the same command without -Check to start.'
        ask_install    = 'Install WSL and Ubuntu 24.04 now? It downloads Ubuntu from Microsoft, needs administrator rights, and needs a restart afterwards. Type yes to go on.'
        need_admin     = 'Installing WSL needs PowerShell opened as administrator. Close this window, right-click the Start button, choose Terminal (Admin) or Windows PowerShell (Admin), and paste the same command again.'
        declined       = 'Nothing was done.'
        cannot_ask     = 'There is nobody here to ask, so nothing was done. To go ahead, run it again and add -Yes.'
        installing     = 'Installing Ubuntu. Windows shows its own progress. When Ubuntu asks for a user name and a password, choose them: they are for Ubuntu only.'
        install_failed = 'The install did not finish. Windows said the lines above. Nothing else was changed. Run the same command again to try once more.'
        restart        = 'WSL is installed but needs the computer to restart first. Restart it, then run the same command again. It carries on from here.'
        first_run      = 'Ubuntu is installed but has no user yet. Open Ubuntu 24.04 from the Start menu once. Choose a user name and a password, which are for Ubuntu only. Close it, then run the same command again.'
        handing_over   = 'Starting the Ubuntu part. Ubuntu will ask for the password you chose, in this window, to install a few Ubuntu programs.'
        handed_back    = 'The Ubuntu part has ended.'
        window_opening = 'Opening the window. Leave this PowerShell window open while you use Voice Studio: closing it closes the Voice Studio window. When you close the Voice Studio window, this PowerShell window is free again.'
        window_closed  = 'The Voice Studio window was closed.'
        window_failed  = 'The window stopped with code {code}. What it said is above. To try again, run the same command.'
        handover_failed = 'The Ubuntu part stopped with code {code}. What it said is above. Run the same command again to carry on from where it stopped.'
        dry_header     = 'Nothing was changed. This is what would run:'
        bad_option     = 'I do not know the option {option}. The options are -Ref, -Distro, -Check, -DryRun, -Yes and -Help.'
        bad_ref        = 'The release name {name} has a character that is not allowed. Use letters, numbers and . _ - / only.'
        bad_distro     = 'The name {name} is not an Ubuntu name. It must start with Ubuntu and then use only letters, numbers and . _ - (for example Ubuntu-24.04).'
        usage          = 'Options: -Ref name is the release of ACK to fetch. -Distro name is the WSL distribution to use. -Check only looks. -DryRun only looks and shows the commands. -Yes answers yes to the questions.'
    }
}

function Format-AckVsText {
    param([string]$Template, [hashtable]$Values)
    $out = $Template
    if ($Values) {
        foreach ($key in $Values.Keys) { $out = $out.Replace('{' + $key + '}', [string]$Values[$key]) }
    }
    $out
}

# ---------------------------------------------------------------- options

function Test-AckVsRefName {
    param([string]$Name)
    ($Name -match '^[A-Za-z0-9][A-Za-z0-9._/-]{0,99}\z') -and ($Name -notmatch '\.\.') -and ($Name -notmatch '//') -and ($Name -notmatch '/$')
}

function Test-AckVsDistroName {
    param([string]$Name)
    $Name -match '^Ubuntu[A-Za-z0-9._-]{0,57}\z'
}

function Read-AckVsArguments {
    <# Options from the command line, with the same settings from the environment as the fallback. Returns a hashtable; Error holds the first thing not understood. #>
    param([string[]]$Tokens, $Environment)
    $settings = Get-AckVsSettings
    $result = @{ Ref = $settings.DefaultRef; Distro = ''; Check = $false; DryRun = $false; Yes = $false; Help = $false; Error = '' }
    $given = $Environment
    if ($null -eq $given) { $given = @{} }
    if ($given['ACK_VOICE_TAG'])    { $result.Ref = [string]$given['ACK_VOICE_TAG'] }
    if ($given['ACK_VOICE_DISTRO']) { $result.Distro = [string]$given['ACK_VOICE_DISTRO'] }
    if ($given['ACK_VOICE_CHECK'] -eq '1')  { $result.Check = $true }
    if ($given['ACK_VOICE_DRYRUN'] -eq '1') { $result.DryRun = $true }
    if ($given['ACK_VOICE_YES'] -eq '1')    { $result.Yes = $true }
    $list = @($Tokens | Where-Object { $_ -ne $null -and $_ -ne '' })
    $i = 0
    while ($i -lt $list.Count) {
        $token = [string]$list[$i]
        switch -Regex ($token) {
            '^-Ref$'    { if ($i + 1 -lt $list.Count) { $result.Ref = [string]$list[$i + 1]; $i++ } else { $result.Error = $token } }
            '^-Distro$' { if ($i + 1 -lt $list.Count) { $result.Distro = [string]$list[$i + 1]; $i++ } else { $result.Error = $token } }
            '^-Check$'  { $result.Check = $true }
            '^-DryRun$' { $result.DryRun = $true }
            '^-Yes$'    { $result.Yes = $true }
            '^-Help$'   { $result.Help = $true }
            default     { if (-not $result.Error) { $result.Error = $token } }
        }
        $i++
    }
    $result
}

# ---------------------------------------------------------------- what the computer says

function ConvertFrom-AckVsWslList {
    <# `wsl.exe -l -v` writes UTF-16, which PowerShell may show with a NUL between letters. Take those out, read the name (first word) and the WSL version (last word) of each line.
       The header and the state words are in the language of Windows, so they are not read. #>
    param([string[]]$Lines)
    $found = @()
    foreach ($raw in @($Lines)) {
        if ($null -eq $raw) { continue }
        $line = ([string]$raw).Replace([string][char]0, '').TrimEnd()
        if ($line.Trim() -eq '') { continue }
        $isDefault = $line.TrimStart().StartsWith('*')
        $parts = @(($line.Trim().TrimStart('*').Trim()) -split '\s+')
        if ($parts.Count -lt 3) { continue }
        $version = $parts[$parts.Count - 1]
        if ($version -notmatch '^[12]$') { continue }                    # the header line ends in a word, not a number
        $found += @{ Name = $parts[0]; Version = [int]$version; Default = $isDefault }
    }
    $found
}

function Read-AckVsDistros {
    <# The distributions, from the listing with versions; if that gave none (a listing laid out some way not expected), from the plain list of names, assuming WSL 2. #>
    param($Listed, [scriptblock]$WslCapture)
    $found = @()
    if ($Listed.Ran -and $Listed.Code -eq 0) { $found = @(ConvertFrom-AckVsWslList -Lines $Listed.Lines) }
    if ($found.Count -eq 0 -and $Listed.Ran -and $Listed.Code -eq 0) {
        $names = & $WslCapture @('-l', '-q')
        if ($names.Ran -and $names.Code -eq 0) {
            foreach ($raw in @($names.Lines)) {
                $name = ([string]$raw).Replace([string][char]0, '').Trim()
                if ($name -match '^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$') { $found += @{ Name = $name; Version = 2; Default = $false } }
            }
        }
    }
    $found
}

function Select-AckVsDistro {
    <# Which distribution to use, or nothing. A name given by the person wins (and must exist). Otherwise Ubuntu-24.04, then Ubuntu-22.04, then plain Ubuntu. #>
    param($Distros, [string]$Wanted)
    $list = @($Distros)
    $accepted = (Get-AckVsSettings).Accepted
    if ($Wanted) {
        $match = @($list | Where-Object { $_.Name -eq $Wanted })
        if ($match.Count -eq 0) { return @{ Name = ''; Version = 0; Why = 'named_missing' } }
        return @{ Name = $match[0].Name; Version = $match[0].Version; Why = $(if ($match[0].Version -eq 2) { 'named' } else { 'old_version' }) }
    }
    foreach ($name in $accepted) {
        $match = @($list | Where-Object { $_.Name -eq $name })
        if ($match.Count -gt 0) {
            return @{ Name = $match[0].Name; Version = $match[0].Version; Why = $(if ($match[0].Version -eq 2) { 'found' } else { 'old_version' }) }
        }
    }
    @{ Name = ''; Version = 0; Why = 'none' }
}

function Get-AckVsFindings {
    <# What the facts about this computer mean. Level: stop (cannot go on), warn (go on, but say so), ok. #>
    param($Facts)
    $text = Get-AckVsText
    $settings = Get-AckVsSettings
    $found = @()
    if ($null -ne $Facts.Is64 -and -not $Facts.Is64) {
        $found += @{ Id = 'not_64'; Level = 'stop'; Text = $text.not_64 }
    }
    if ($null -ne $Facts.Build) {
        if ([int]$Facts.Build -lt $settings.MinBuild) {
            $found += @{ Id = 'windows_old'; Level = 'stop'; Text = $text.windows_old }
        } else {
            $found += @{ Id = 'windows_ok'; Level = 'ok'; Text = (Format-AckVsText $text.windows_ok @{ build = $Facts.Build }) }
        }
    }
    if (($Facts.Hypervisor -eq $false) -and ($Facts.FirmwareVirt -eq $false)) {
        $found += @{ Id = 'virt_off'; Level = 'warn'; Text = $text.virt_off }
    }
    if ($Facts.GpuName) {
        $found += @{ Id = 'gpu_found'; Level = 'ok'; Text = (Format-AckVsText $text.gpu_found @{ name = $Facts.GpuName; driver = $Facts.GpuDriver }) }
    } else {
        $found += @{ Id = 'gpu_none'; Level = 'warn'; Text = $text.gpu_none }
    }
    if ($null -ne $Facts.FreeGiB) {
        $free = [math]::Floor([double]$Facts.FreeGiB)
        if ($free -lt $settings.MinFreeGiB) {
            $found += @{ Id = 'disk_low'; Level = 'warn'; Text = (Format-AckVsText $text.disk_low @{ free = $free; drive = $Facts.Drive }) }
        } else {
            $found += @{ Id = 'disk_ok'; Level = 'ok'; Text = (Format-AckVsText $text.disk_ok @{ free = $free; drive = $Facts.Drive }) }
        }
    }
    $found
}

function Get-AckVsFacts {
    <# Reads this computer. Each fact that cannot be read is left empty, and an empty fact never stops anything. #>
    $facts = @{ Build = $null; Is64 = $null; Hypervisor = $null; FirmwareVirt = $null; GpuName = ''; GpuDriver = ''; FreeGiB = $null; Drive = '' }
    try {
        $os = Get-CimInstance -ClassName Win32_OperatingSystem -ErrorAction Stop
        $facts.Build = [int]$os.BuildNumber
        $facts.Is64 = ($os.OSArchitecture -like '64*')
    } catch { }
    try {
        $system = Get-CimInstance -ClassName Win32_ComputerSystem -ErrorAction Stop
        $facts.Hypervisor = [bool]$system.HypervisorPresent
    } catch { }
    try {
        $cpu = @(Get-CimInstance -ClassName Win32_Processor -ErrorAction Stop)[0]
        $facts.FirmwareVirt = [bool]$cpu.VirtualizationFirmwareEnabled
    } catch { }
    try {
        $smi = Get-Command 'nvidia-smi.exe' -ErrorAction Stop
        $line = @(& $smi.Source '--query-gpu=name,driver_version' '--format=csv,noheader' 2>$null)[0]
        if ($line) {
            $bits = ([string]$line).Split(',')
            if ($bits.Count -ge 2) { $facts.GpuName = $bits[0].Trim(); $facts.GpuDriver = $bits[1].Trim() }
        }
    } catch { }
    try {
        $drive = $env:SystemDrive
        if ($drive) {
            $info = New-Object System.IO.DriveInfo($drive)
            $facts.FreeGiB = [math]::Floor($info.AvailableFreeSpace / 1GB)
            $facts.Drive = $drive
        }
    } catch { }
    $facts
}

function Test-AckVsAdministrator {
    try {
        $principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
        return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    } catch { return $false }
}

# ---------------------------------------------------------------- talking to wsl.exe

function Invoke-AckVsWslCapture {
    <# Runs wsl.exe and returns what it printed. Used for looking only. #>
    param([string[]]$WslArguments)
    try {
        $lines = @(& wsl.exe @WslArguments 2>&1 | ForEach-Object { [string]$_ })
        return @{ Ran = $true; Code = $LASTEXITCODE; Lines = $lines }
    } catch {
        return @{ Ran = $false; Code = 1; Lines = @() }
    }
}

function Invoke-AckVsWslLive {
    <# Runs wsl.exe on the person's own console: they see everything it says and can type to it (the Ubuntu first run, the password prompt, the answers). It is started with Start-Process
       and -NoNewWindow so that it shares this console. A native program called inside a function has its output captured into the function's result (and gets a pipe, not a console),
       which swallowed everything Ubuntu said and left it no terminal to ask on; that was found on the first run on a real Windows. The command line is built here, quoting only what has a space. #>
    param([string[]]$WslArguments)
    try {
        $program = Get-Command -Name 'wsl.exe' -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($null -eq $program) { return @{ Ran = $false; Code = 1 } }
        $line = Format-AckVsCommandLine -CommandArguments $WslArguments
        $process = Start-Process -FilePath $program.Source -ArgumentList $line -NoNewWindow -Wait -PassThru -ErrorAction Stop
        $process.WaitForExit()
        $code = 1
        if ($null -ne $process.ExitCode) { $code = [int]$process.ExitCode }
        return @{ Ran = $true; Code = $code }
    } catch {
        return @{ Ran = $false; Code = 1 }
    }
}

function New-AckVsHandover {
    <# The one command run inside Ubuntu: fetch get.sh with curl (or wget), then run it with the chosen release and without opening the window (this script opens it, so that a session from Windows stays attached). It holds no double quote, so Windows passes it on as one piece. #>
    param([string]$Ref)
    $settings = Get-AckVsSettings
    $url = '{0}/{1}/{2}/{3}' -f $settings.RawHost, $settings.Repo, $Ref, $settings.GetScript
    $script = @'
f=$(mktemp) && { if command -v curl >/dev/null 2>&1; then curl -fsSL 'URL' -o $f; elif command -v wget >/dev/null 2>&1; then wget -qO $f 'URL'; else echo 'Ubuntu has neither curl nor wget. Run: sudo apt-get install -y curl'; false; fi; } && ACK_VOICE_TAG='REF' bash $f --no-window; rc=$?; rm -f $f; exit $rc
'@
    ($script.Replace('URL', $url).Replace('REF', $Ref) -replace '\r?\n', ' ').Trim()
}

function Format-AckVsCommandLine {
    <# How a command would be typed: an argument with a space in it is put in double quotes (the handover holds none, which is why that is always enough). #>
    param([string[]]$CommandArguments)
    ($CommandArguments | ForEach-Object { if ($_ -match '\s') { '"' + $_ + '"' } else { $_ } }) -join ' '
}

function Get-AckVsHandoverArguments {
    param([string]$Distro, [string]$Ref)
    @('-d', $Distro, '--cd', '~', '--exec', 'bash', '-c', (New-AckVsHandover -Ref $Ref))
}

function Get-AckVsWindowArguments {
    <# The window, run in the foreground of its own wsl.exe session. $HOME is worked out by Ubuntu's bash; there is no double quote, so Windows passes it on as one piece. #>
    param([string]$Distro)
    @('-d', $Distro, '--cd', '~', '--exec', 'bash', '-c', 'PYTHONPATH=$HOME/ack-tools/tools exec /usr/bin/python3 -m voice_studio.window')
}

# ---------------------------------------------------------------- the whole thing

function Invoke-AckVsInstaller {
    param(
        [string[]]$Tokens,
        $Environment,
        [scriptblock]$Say = { param($line) Write-Host $line },
        [scriptblock]$Ask = { param($prompt) if ([Environment]::UserInteractive) { Read-Host $prompt } else { $null } },
        [scriptblock]$GetFacts = { Get-AckVsFacts },
        [scriptblock]$IsAdmin = { Test-AckVsAdministrator },
        [scriptblock]$WslCapture = { param($a) Invoke-AckVsWslCapture -WslArguments $a },
        [scriptblock]$WslLive = { param($a) Invoke-AckVsWslLive -WslArguments $a }
    )
    $text = Get-AckVsText
    $settings = Get-AckVsSettings
    $opts = Read-AckVsArguments -Tokens $Tokens -Environment $Environment
    & $Say $text.title
    if ($opts.Error) { & $Say (Format-AckVsText $text.bad_option @{ option = $opts.Error }); return 2 }
    if ($opts.Help) { & $Say $text.usage; return 0 }
    if (-not (Test-AckVsRefName $opts.Ref)) { & $Say (Format-AckVsText $text.bad_ref @{ name = $opts.Ref }); return 2 }
    if ($opts.Distro -and -not (Test-AckVsDistroName $opts.Distro)) { & $Say (Format-AckVsText $text.bad_distro @{ name = $opts.Distro }); return 2 }
    & $Say $text.intro
    & $Say ''
    & $Say $text.looking

    $facts = & $GetFacts
    $findings = @(Get-AckVsFindings -Facts $facts)
    foreach ($finding in $findings) { & $Say $finding.Text }
    if (@($findings | Where-Object { $_.Level -eq 'stop' }).Count -gt 0) { return 1 }

    $listed = & $WslCapture @('-l', '-v')
    $distros = @(Read-AckVsDistros -Listed $listed -WslCapture $WslCapture)
    $pick = Select-AckVsDistro -Distros $distros -Wanted $opts.Distro
    $installName = $settings.InstallDistro
    if ($opts.Distro) { $installName = $opts.Distro }

    if ($pick.Why -eq 'old_version') {
        & $Say (Format-AckVsText $text.old_wsl_only @{ name = $pick.Name })
        return 1
    }

    if ($pick.Name -eq '') {
        if (-not ($listed.Ran -and $listed.Code -eq 0)) { & $Say $text.no_wsl } else { & $Say $text.no_ubuntu }
        $install = @('--install', '-d', $installName)
        if ($opts.Check) { & $Say (Format-AckVsText $text.would_install @{ name = $installName }); & $Say $text.check_not_ready; return 1 }
        if ($opts.DryRun) {
            & $Say $text.dry_header
            & $Say ('  wsl.exe ' + (Format-AckVsCommandLine $install))
            & $Say ('  wsl.exe ' + (Format-AckVsCommandLine (Get-AckVsHandoverArguments -Distro $installName -Ref $opts.Ref)))
            & $Say ('  wsl.exe ' + (Format-AckVsCommandLine (Get-AckVsWindowArguments -Distro $installName)))
            return 0
        }
        if (-not (& $IsAdmin)) { & $Say $text.need_admin; return 3 }
        if (-not $opts.Yes) {
            $answer = & $Ask $text.ask_install
            if ($null -eq $answer) { & $Say $text.cannot_ask; return 2 }
            if (([string]$answer).Trim().ToLower() -notin @('y', 'yes')) { & $Say $text.declined; return 2 }
        }
        & $Say $text.installing
        $done = & $WslLive $install
        if (-not $done.Ran -or $done.Code -ne 0) { & $Say $text.install_failed; return 1 }
        $listed = & $WslCapture @('-l', '-v')
        $distros = @(Read-AckVsDistros -Listed $listed -WslCapture $WslCapture)
        $pick = Select-AckVsDistro -Distros $distros -Wanted $installName
        if ($pick.Name -eq '') { & $Say $text.restart; return 3 }
    }

    & $Say (Format-AckVsText $text.found @{ name = $pick.Name })
    $who = & $WslCapture @('-d', $pick.Name, '--exec', 'id', '-u')
    $userId = ''
    if ($who.Ran -and $who.Code -eq 0) {
        $lastLine = ''
        foreach ($raw in @($who.Lines)) {
            $clean = ([string]$raw).Replace([string][char]0, '').Trim()
            if ($clean -ne '') { $lastLine = $clean }
        }
        if ($lastLine -match '^[0-9]+$') { $userId = $lastLine }               # the id is the last line; a warning before it, or a NUL between its letters, does not change it
    }
    if ($userId -eq '' -or $userId -match '^0+$') {
        & $Say $text.first_run
        return 3
    }
    if ($opts.Check) { & $Say $text.check_ready; return 0 }
    $handover = Get-AckVsHandoverArguments -Distro $pick.Name -Ref $opts.Ref
    if ($opts.DryRun) {
        & $Say $text.dry_header
        & $Say ('  wsl.exe ' + (Format-AckVsCommandLine $handover))
        & $Say ('  wsl.exe ' + (Format-AckVsCommandLine (Get-AckVsWindowArguments -Distro $pick.Name)))
        return 0
    }
    & $Say ''
    & $Say $text.handing_over
    $ran = & $WslLive $handover
    & $Say $text.handed_back
    if (-not $ran.Ran -or $ran.Code -ne 0) {
        $code = 1
        if ($ran.Ran) { $code = $ran.Code }
        & $Say (Format-AckVsText $text.handover_failed @{ code = $code })
        return 1
    }
    & $Say ''
    & $Say $text.window_opening
    $shown = & $WslLive (Get-AckVsWindowArguments -Distro $pick.Name)
    if (-not $shown.Ran -or $shown.Code -ne 0) {
        $closed = 1
        if ($shown.Ran) { $closed = $shown.Code }
        & $Say (Format-AckVsText $text.window_failed @{ code = $closed })
        return 1
    }
    & $Say $text.window_closed
    0
}

# Run it, unless a test only wants the functions. `exit` is used only when this is a file run on its own: in a pipe into iex it would close the person's PowerShell window.
if (-not $env:ACK_VOICE_NO_AUTORUN) {
    $ackVsEnvironment = @{}
    foreach ($ackVsName in 'ACK_VOICE_TAG', 'ACK_VOICE_DISTRO', 'ACK_VOICE_CHECK', 'ACK_VOICE_DRYRUN', 'ACK_VOICE_YES') {
        $ackVsEnvironment[$ackVsName] = [Environment]::GetEnvironmentVariable($ackVsName)
    }
    $ackVsCode = [int]@(Invoke-AckVsInstaller -Tokens $args -Environment $ackVsEnvironment)[-1]
    $ackVsIsFile = [bool]$PSCommandPath
    $global:LASTEXITCODE = $ackVsCode
    Remove-Item -Path 'Function:\*-AckVs*' -ErrorAction SilentlyContinue
    if ($ackVsIsFile) { exit $ackVsCode }
    Remove-Variable -Name 'ackVs*' -ErrorAction SilentlyContinue
}
