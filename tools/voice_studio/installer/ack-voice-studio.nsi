; SPDX-License-Identifier: GPL-3.0-or-later
; ACK Voice Studio setup wizard (plan decision D44, choices P28).
;
; What it is: a small Windows program that asks a few questions in ordinary windows and then runs the PowerShell engine (engine.ps1, beside it) one step at a time. The engine does the
; work; this file only asks, shows what the engine said, and stops when a step fails. It holds no copy of ACK: the program is fetched from its source (GitHub, see install.ps1) while
; it runs, so what is installed is always what that source holds, with its licence.
;
; Built with NSIS (makensis), for Windows 11 only, for one user (no administrator rights; Windows asks once, inside the engine, when WSL itself is set up). Not signed yet. It has no
; silent mode: a person must be there to choose the Ubuntu account and its password.
;
; Build: installer/build.sh. Needs /DSTAGE=<folder holding engine.ps1, install.ps1, LICENSE, NOTICE and ack.ico> /DVERSION=<x.y.z> /DOUTFILE=<path of the .exe to write>.

Unicode true
SetCompressor /SOLID lzma
RequestExecutionLevel user
ManifestSupportedOS Win10                                               ; Windows 11 reports itself as 10 and is told apart by its build number
SetCompress auto
SetDateSave off                                                           ; the build then does not depend on when the staged files were copied: the same files give the same program
CRCCheck on

!ifndef STAGE
  !error "Give /DSTAGE=<folder>"
!endif
!ifndef VERSION
  !define VERSION "0.0.0"
!endif
!ifndef OUTFILE
  !define OUTFILE "ACK-Voice-Studio-Setup.exe"
!endif

!define NAME "ACK Voice Studio"
!define PUBLISHER "ASP Design Labs"
!define UNINSTALL_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\ACKVoiceStudio"
!define MIN_BUILD 22000                                                 ; the first Windows 11 build; install.ps1's MinBuild is the same number

Name "${NAME}"
OutFile "${OUTFILE}"
InstallDir "$LOCALAPPDATA\ACK Voice Studio"
InstallDirRegKey HKCU "${UNINSTALL_KEY}" "InstallLocation"
BrandingText "${NAME} ${VERSION}"
VIProductVersion "${VERSION}.0"
VIAddVersionKey "ProductName" "${NAME}"
VIAddVersionKey "FileDescription" "${NAME} setup"
VIAddVersionKey "FileVersion" "${VERSION}"
VIAddVersionKey "LegalCopyright" "GPL-3.0-or-later"
VIAddVersionKey "CompanyName" "${PUBLISHER}"

!include "MUI2.nsh"
!include "nsDialogs.nsh"
!include "LogicLib.nsh"
!include "WinMessages.nsh"
!include "FileFunc.nsh"

Var Dialog
Var Edit
Var NextButton
Var NameBox
Var PassBox
Var AgainBox
Var Distro                  ; the Ubuntu that is there, or the one that will be installed
Var UserName                ; the Ubuntu account: found, or typed
Var Password                ; typed; sent to the engine through the environment; cleared as soon as it has been used
Var NeedsPlatform
Var NeedsDistro
Var NeedsAccount
Var Stopped                 ; 1 when the check says this computer cannot be used
Var SudoIsOn                ; 1 while the temporary permission for the install is in place, so a failure can take it away
Var PowerShell
Var Engine
Var CheckFile
Var StepName
Var StepExtra
Var StepCode
Var StepText

!define MUI_ICON "${STAGE}\ack.ico"
!define MUI_UNICON "${STAGE}\ack.ico"
!define MUI_ABORTWARNING
!define MUI_WELCOMEPAGE_TITLE "Set up ${NAME}"
!define MUI_WELCOMEPAGE_TEXT "This sets up ACK Voice Studio on this computer, for recording and training a voice of your own.$\r$\n$\r$\nIt works only on Windows 11. It uses Ubuntu inside Windows (WSL), and sets that up too if it is not there yet.$\r$\n$\r$\nThe next pages say where everything comes from and ask you for an Ubuntu account name and password. You need to be here: it asks, and it takes a while (it downloads several gigabytes).$\r$\n$\r$\nThis setup program is not signed yet, so Windows may warn you when you start it."
!define MUI_LICENSEPAGE_TEXT_TOP "This is the licence the program is shared under (GPL version 3 or later). Read it if you like; pressing Next does not change what you may do."
!define MUI_LICENSEPAGE_BUTTON "&Next >"
!define MUI_LICENSEPAGE_TEXT_BOTTOM "Press Next to go on."
!define MUI_FINISHPAGE_TITLE "${NAME} is set up"
!define MUI_FINISHPAGE_TEXT "ACK Voice Studio is in the Start menu. Your recordings and voices stay on this computer, in Ubuntu, and go nowhere unless you send them."
!define MUI_FINISHPAGE_RUN
!define MUI_FINISHPAGE_RUN_TEXT "Open ${NAME} now"
!define MUI_FINISHPAGE_RUN_FUNCTION OpenStudio
!define MUI_UNCONFIRMPAGE_TEXT_TOP "This takes away the setup program's own files and the Start menu entry made for ${NAME}. It does not take away Ubuntu, the programs inside it, or your recordings, transcripts and voices: those are yours and stay where they are. The guide says how to remove them yourself."

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "${STAGE}\LICENSE"
Page custom SourcesCreate "" ""
Page custom LookCreate LookLeave ""
Page custom AccountCreate AccountLeave ""
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

!insertmacro MUI_LANGUAGE "English"

; ------------------------------------------------------------------------------------------------ before anything is shown

Function .onInit
  IfSilent 0 interactive
  MessageBox MB_OK|MB_ICONSTOP "This setup program has no silent mode: it asks for an Ubuntu account name and password."
  Abort
  interactive:
  SetRegView 64
  ReadRegStr $0 HKLM "SOFTWARE\Microsoft\Windows NT\CurrentVersion" "CurrentBuildNumber"
  ${If} $0 == ""
    StrCpy $0 0
  ${EndIf}
  ${If} $0 < ${MIN_BUILD}
    MessageBox MB_OK|MB_ICONSTOP "ACK Voice Studio works only on Windows 11 for now. This computer has Windows build $0; Windows 11 starts at build ${MIN_BUILD}.$\r$\n$\r$\nNothing was changed."
    Abort
  ${EndIf}
  StrCpy $Distro ""
  StrCpy $UserName ""
  StrCpy $Password ""
  StrCpy $NeedsPlatform 1
  StrCpy $NeedsDistro 1
  StrCpy $NeedsAccount 1
  StrCpy $Stopped 0
  StrCpy $SudoIsOn 0
  ; a 32-bit program on 64-bit Windows would reach the 32-bit PowerShell and a System32 without wsl.exe; Sysnative is the way to the real one
  StrCpy $PowerShell "$WINDIR\Sysnative\WindowsPowerShell\v1.0\powershell.exe"
  IfFileExists "$PowerShell" ps_ok 0
  StrCpy $PowerShell "$SYSDIR\WindowsPowerShell\v1.0\powershell.exe"
  ps_ok:
FunctionEnd

; ------------------------------------------------------------------------------------------------ running the engine

; In: $StepName (the engine's -Step), $StepExtra (more options, never a password). Out: $StepCode (its exit code), and its lines in the details list.
Function RunEngineLogged
  DetailPrint "[$StepName]"
  nsExec::ExecToLog '"$PowerShell" -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "$Engine" -Step $StepName $StepExtra'
  Pop $StepCode
FunctionEnd

; The same, with the output kept as text in $StepText (for a question asked on a page, where there is no details list).
Function RunEngineQuiet
  nsExec::ExecToStack '"$PowerShell" -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "$Engine" -Step $StepName $StepExtra'
  Pop $StepCode
  Pop $StepText
FunctionEnd

; The password goes to the engine in the environment of the one program started, never on a command line. These two set it and clear it again.
Function PasswordIn
  StrCpy $1 $Password
  System::Call 'kernel32::SetEnvironmentVariable(t "ACK_VS_PASSWORD", t r1)i'
FunctionEnd

Function PasswordOut
  System::Call 'kernel32::SetEnvironmentVariable(t "ACK_VS_PASSWORD", i 0)i'
  StrCpy $1 ""
FunctionEnd

; Appends a line to the box on a page. $R0 = the line.
Function AddLine
  SendMessage $Edit ${EM_SETSEL} -1 -1
  SendMessage $Edit ${EM_REPLACESEL} 0 "STR:$R0$\r$\n"
FunctionEnd

; $0 = "level|text" -> $0 = text
Function StripLevel
  StrCpy $R5 0
  strip_loop:
    StrCpy $R6 $0 1 $R5
    StrCmp $R6 "" strip_done
    StrCmp $R6 "|" strip_found
    IntOp $R5 $R5 + 1
    Goto strip_loop
  strip_found:
    IntOp $R5 $R5 + 1
    StrCpy $0 $0 "" $R5
  strip_done:
FunctionEnd

; ------------------------------------------------------------------------------------------------ page: where everything comes from

Function SourcesCreate
  !insertmacro MUI_HEADER_TEXT "Where everything comes from" "Read this before you go on."
  nsDialogs::Create 1018
  Pop $Dialog
  ${If} $Dialog == error
    Abort
  ${EndIf}
  ${NSD_CreateMLText} 0 0 100% 100% ""
  Pop $Edit
  SendMessage $Edit ${EM_SETREADONLY} 1 0
  StrCpy $R0 "This setup program holds no copy of ACK. It fetches the program from its source while it runs:"
  Call AddLine
  StrCpy $R0 ""
  Call AddLine
  StrCpy $R0 "- ACK and ACK Voice Studio: from github.com/ASPDesignLabs/ACK, the files as they are there now. They are shared under the GPL, version 3 or later (the licence on the previous page)."
  Call AddLine
  StrCpy $R0 "- Ubuntu 24.04 and WSL: from Microsoft, through Windows. Windows asks you once to allow setting up WSL."
  Call AddLine
  StrCpy $R0 "- Ubuntu's own programs: from Ubuntu's archives, inside Ubuntu."
  Call AddLine
  StrCpy $R0 "- The training programs and the starting voice: from the places the tool lists, each with its own terms. The tool shows them and asks before it downloads anything."
  Call AddLine
  StrCpy $R0 ""
  Call AddLine
  StrCpy $R0 "Your recordings, transcripts and voices stay on this computer, inside Ubuntu. This setup program sends nothing about you anywhere."
  Call AddLine
  StrCpy $R0 ""
  Call AddLine
  StrCpy $R0 "Nothing here is legal advice, and the terms of each place named above are theirs, not ours. If you or your organisation need a different place to fetch from, the guide says where it is set."
  Call AddLine
  nsDialogs::Show
FunctionEnd

; ------------------------------------------------------------------------------------------------ page: looking at this computer (changes nothing)

Function LookCreate
  !insertmacro MUI_HEADER_TEXT "Looking at this computer" "Nothing is changed at this step."
  nsDialogs::Create 1018
  Pop $Dialog
  ${If} $Dialog == error
    Abort
  ${EndIf}
  ${NSD_CreateMLText} 0 0 100% 100% ""
  Pop $Edit
  SendMessage $Edit ${EM_SETREADONLY} 1 0
  GetDlgItem $NextButton $HWNDPARENT 1
  EnableWindow $NextButton 0
  StrCpy $R0 "Looking at this computer..."
  Call AddLine
  ${NSD_CreateTimer} LookNow 100
  nsDialogs::Show
FunctionEnd

Function LookNow
  ${NSD_KillTimer} LookNow
  InitPluginsDir
  ; the engine and install.ps1 sit beside each other; before the install step they are in the plugins folder
  File "/oname=$PLUGINSDIR\engine.ps1" "${STAGE}\engine.ps1"
  File "/oname=$PLUGINSDIR\install.ps1" "${STAGE}\install.ps1"
  StrCpy $Engine "$PLUGINSDIR\engine.ps1"
  StrCpy $CheckFile "$PLUGINSDIR\check.ini"
  StrCpy $StepName "check"
  StrCpy $StepExtra '-ResultFile "$CheckFile"'
  Call RunEngineQuiet
  ReadINIStr $0 "$CheckFile" "result" "stop"
  ${If} $StepCode == "error"
  ${OrIf} $0 == ""
    StrCpy $Stopped 1
    SendMessage $Edit ${EM_SETSEL} 0 -1
    StrCpy $R0 "The computer could not be looked at. PowerShell did not run the check ($StepCode). Nothing was changed."
    SendMessage $Edit ${EM_REPLACESEL} 0 "STR:$R0$\r$\n"
    Return
  ${EndIf}
  SendMessage $Edit ${EM_SETSEL} 0 -1
  SendMessage $Edit ${EM_REPLACESEL} 0 "STR:"
  ReadINIStr $1 "$CheckFile" "lines" "count"
  ${If} $1 == ""
    StrCpy $1 0
  ${EndIf}
  StrCpy $2 1
  ${While} $2 <= $1
    ReadINIStr $0 "$CheckFile" "lines" "$2"
    Call StripLevel
    StrCpy $R0 $0
    Call AddLine
    IntOp $2 $2 + 1
  ${EndWhile}
  ReadINIStr $Stopped "$CheckFile" "result" "stop"
  ReadINIStr $NeedsPlatform "$CheckFile" "result" "needs_platform"
  ReadINIStr $NeedsDistro "$CheckFile" "result" "needs_distro"
  ReadINIStr $NeedsAccount "$CheckFile" "result" "needs_account"
  ReadINIStr $0 "$CheckFile" "result" "distro"
  ${If} $0 != ""
    StrCpy $Distro $0
  ${Else}
    StrCpy $Distro "Ubuntu-24.04"
  ${EndIf}
  ReadINIStr $0 "$CheckFile" "result" "user"
  ${If} $0 != ""
    StrCpy $UserName $0
  ${EndIf}
  ${If} $Stopped == 1
    StrCpy $R0 ""
    Call AddLine
    StrCpy $R0 "This computer cannot be used as it is. Nothing was changed. Close this window, then see the guide."
    Call AddLine
  ${Else}
    EnableWindow $NextButton 1
  ${EndIf}
FunctionEnd

Function LookLeave
  ${If} $Stopped != 0
    Abort
  ${EndIf}
FunctionEnd

; ------------------------------------------------------------------------------------------------ page: the Ubuntu account

Function AccountCreate
  ${If} $NeedsAccount == 0
    Abort                                  ; an account is already there: it is used, and its password is not touched
  ${EndIf}
  !insertmacro MUI_HEADER_TEXT "An account for Ubuntu" "Ubuntu has its own account and password, separate from Windows."
  nsDialogs::Create 1018
  Pop $Dialog
  ${If} $Dialog == error
    Abort
  ${EndIf}
  ${NSD_CreateLabel} 0 0 100% 36u "Ubuntu runs inside Windows and needs an account of its own. Choose a name (lower-case letters, numbers, - and _, starting with a letter) and a password (8 to 128 letters, numbers and ordinary symbols). Ubuntu asks for the password only when something needs administrator rights."
  Pop $0
  ${NSD_CreateLabel} 0 40u 100% 10u "Account name:"
  Pop $0
  ${NSD_CreateText} 0 50u 60% 12u "$UserName"
  Pop $NameBox
  ${NSD_CreateLabel} 0 66u 100% 10u "Password:"
  Pop $0
  ${NSD_CreatePassword} 0 76u 60% 12u ""
  Pop $PassBox
  ${NSD_CreateLabel} 0 92u 100% 10u "Password again:"
  Pop $0
  ${NSD_CreatePassword} 0 102u 60% 12u ""
  Pop $AgainBox
  ${NSD_CreateLabel} 0 120u 100% 36u "This setup program sees the password you type. It sends it once to Ubuntu, to set it, and does not save it anywhere: not in a file, not in a log. The command-line installer never asks for one; this wizard does so you do not have to type commands."
  Pop $0
  nsDialogs::Show
FunctionEnd

Function AccountLeave
  ${NSD_GetText} $NameBox $UserName
  ${NSD_GetText} $PassBox $Password
  ${NSD_GetText} $AgainBox $R9
  ${If} $UserName == ""
    MessageBox MB_OK|MB_ICONEXCLAMATION "Type a name for the Ubuntu account."
    Goto refuse
  ${EndIf}
  ${If} $Password == ""
    MessageBox MB_OK|MB_ICONEXCLAMATION "Type a password for the Ubuntu account."
    Goto refuse
  ${EndIf}
  ${If} $Password != $R9
    MessageBox MB_OK|MB_ICONEXCLAMATION "The two passwords are not the same. Type them again."
    Goto refuse
  ${EndIf}
  ; the same rules as everywhere else: the engine decides, and changes nothing here
  StrCpy $R9 ""
  StrCpy $StepName "validate"
  StrCpy $StepExtra '-User "$UserName"'
  Call PasswordIn
  Call RunEngineQuiet
  Call PasswordOut
  ${If} $StepCode != 0
    ${If} $StepText == ""
      StrCpy $StepText "The name or password was not accepted."
    ${EndIf}
    MessageBox MB_OK|MB_ICONEXCLAMATION "$StepText"
    Goto refuse
  ${EndIf}
  Return
  refuse:
  StrCpy $R9 ""
  Abort
FunctionEnd

; ------------------------------------------------------------------------------------------------ the install

; Stops the install: takes the temporary permission away if it is in place, says so, and aborts. $R0 = the sentence to show.
Function Fail
  ${If} $SudoIsOn == 1
    StrCpy $StepName "sudo-off"
    StrCpy $StepExtra '-Distro "$Distro" -User "$UserName"'
    Call RunEngineLogged
    StrCpy $SudoIsOn 0
  ${EndIf}
  StrCpy $Password ""
  DetailPrint "$R0"
  MessageBox MB_OK|MB_ICONEXCLAMATION "$R0$\r$\n$\r$\nNothing you made is lost. Run this setup program again to carry on; it picks up from where it stopped. What it did is in the list and in $LOCALAPPDATA\ack-voice-studio\installer.log."
  Abort
FunctionEnd

; Runs one step and stops the install if it fails. $StepName and $StepExtra are set by the caller.
Function MustRun
  Call RunEngineLogged
  ${If} $StepCode == 0
    Return
  ${EndIf}
  ${If} $StepCode == 3
    StrCpy $R0 "This computer must restart before it can go on."
    DetailPrint "$R0"
    MessageBox MB_OK|MB_ICONINFORMATION "$R0$\r$\n$\r$\nRestart it now, then run this setup program again. It carries on from here."
    StrCpy $Password ""
    Abort
  ${EndIf}
  ${If} $StepCode == 2
    StrCpy $R0 "The step $StepName was not allowed, so it was not done."
  ${Else}
    StrCpy $R0 "The step $StepName stopped (code $StepCode)."
  ${EndIf}
  Call Fail
FunctionEnd

Section "Install"
  SetOutPath "$INSTDIR"
  File "${STAGE}\engine.ps1"
  File "${STAGE}\install.ps1"
  File "${STAGE}\LICENSE"
  File "${STAGE}\NOTICE"
  File "${STAGE}\ack.ico"
  WriteUninstaller "$INSTDIR\Uninstall.exe"
  StrCpy $Engine "$INSTDIR\engine.ps1"
  WriteRegStr HKCU "${UNINSTALL_KEY}" "DisplayName" "${NAME}"
  WriteRegStr HKCU "${UNINSTALL_KEY}" "DisplayVersion" "${VERSION}"
  WriteRegStr HKCU "${UNINSTALL_KEY}" "Publisher" "${PUBLISHER}"
  WriteRegStr HKCU "${UNINSTALL_KEY}" "InstallLocation" "$INSTDIR"
  WriteRegStr HKCU "${UNINSTALL_KEY}" "DisplayIcon" "$INSTDIR\ack.ico"
  WriteRegStr HKCU "${UNINSTALL_KEY}" "UninstallString" '"$INSTDIR\Uninstall.exe"'
  WriteRegDWORD HKCU "${UNINSTALL_KEY}" "NoModify" 1
  WriteRegDWORD HKCU "${UNINSTALL_KEY}" "NoRepair" 1

  ${If} $NeedsPlatform == 1
    StrCpy $StepName "platform"
    StrCpy $StepExtra ""
    Call MustRun
  ${EndIf}
  ${If} $NeedsDistro == 1
    StrCpy $StepName "distro"
    StrCpy $StepExtra '-Distro "$Distro" -User "$UserName"'
    Call MustRun
  ${EndIf}
  ${If} $NeedsAccount == 1
    StrCpy $StepName "user"
    StrCpy $StepExtra '-Distro "$Distro" -User "$UserName"'
    Call PasswordIn
    Call RunEngineLogged
    Call PasswordOut
    StrCpy $Password ""
    ${If} $StepCode != 0
      StrCpy $R0 "The Ubuntu account could not be set up (code $StepCode)."
      Call Fail
    ${EndIf}
  ${EndIf}

  StrCpy $StepName "sudo-on"
  StrCpy $StepExtra '-Distro "$Distro" -User "$UserName"'
  StrCpy $SudoIsOn 1
  Call MustRun
  StrCpy $StepName "setup"
  StrCpy $StepExtra '-Distro "$Distro" -User "$UserName"'
  Call MustRun
  StrCpy $StepName "sudo-off"
  StrCpy $StepExtra '-Distro "$Distro" -User "$UserName"'
  Call RunEngineLogged
  StrCpy $SudoIsOn 0
  ${If} $StepCode != 0
    StrCpy $R0 "The temporary permission for the install could not be taken away (code $StepCode). Open Ubuntu and run: sudo rm /etc/sudoers.d/ack-voice-studio-install"
    DetailPrint "$R0"
    MessageBox MB_OK|MB_ICONEXCLAMATION "$R0"
  ${EndIf}
  StrCpy $StepName "launcher"
  StrCpy $StepExtra '-Distro "$Distro" -User "$UserName"'
  Call RunEngineLogged                                  ; a missing Start menu entry is not a failed install: the finish page can still open it
  ${If} $StepCode != 0
    DetailPrint "The Start menu entry was not made (code $StepCode). ACK Voice Studio is still installed."
  ${EndIf}
SectionEnd

Function OpenStudio
  StrCpy $StepName "open"
  StrCpy $StepExtra '-Distro "$Distro" -User "$UserName"'
  Call RunEngineQuiet
FunctionEnd

; ------------------------------------------------------------------------------------------------ taking the setup program away

Section "Uninstall"
  IfFileExists "$INSTDIR\engine.ps1" 0 files
  StrCpy $PowerShell "$WINDIR\Sysnative\WindowsPowerShell\v1.0\powershell.exe"
  IfFileExists "$PowerShell" ps_found 0
  StrCpy $PowerShell "$SYSDIR\WindowsPowerShell\v1.0\powershell.exe"
  ps_found:
  nsExec::ExecToLog '"$PowerShell" -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "$INSTDIR\engine.ps1" -Step unlauncher'
  Pop $0
  files:
  Delete "$INSTDIR\engine.ps1"
  Delete "$INSTDIR\install.ps1"
  Delete "$INSTDIR\LICENSE"
  Delete "$INSTDIR\NOTICE"
  Delete "$INSTDIR\ack.ico"
  Delete "$INSTDIR\Uninstall.exe"
  RMDir "$INSTDIR"                                         ; only if it is empty
  DeleteRegKey HKCU "${UNINSTALL_KEY}"
SectionEnd
