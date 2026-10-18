# ACK Voice Studio: the Windows setup program

A wizard for **Windows 11** (build 22000 or newer; Windows 10 is not supported) that sets up ACK Voice Studio without a terminal. It asks in ordinary windows and runs a PowerShell
engine one step at a time. It is **not signed yet** (plan decision D44) and has **no silent mode**, because it asks for an Ubuntu account name and password.

**Never run on a real Windows computer.** It was built and tested in a build sandbox: the wizard compiles, and the engine's PowerShell was run for real against stand-ins for `wsl.exe`.
What is and is not known is in `docs/VOICE_STUDIO_DEVICE_TEST.md`, section I18. The design is in `docs/VOICE_STUDIO_SETUP_PLAN.md` (D44, P28, VS-7.4).

| File | What it is |
|---|---|
| `ack-voice-studio.nsi` | The wizard (NSIS). Pages: Welcome, licence, where everything comes from, a look at this computer, the Ubuntu account and password, the install, Finish. |
| `engine.ps1` | What the wizard runs, hidden, once per step: `check`, `platform`, `distro`, `validate`, `user`, `sudo-on`, `setup`, `sudo-off`, `launcher`, `open`, `unlauncher`. It builds on `../install.ps1`. |
| `build.sh` | Builds `ACK-Voice-Studio-Setup-<version>.exe` and its `.sha256` into `installer/dist/` (ignored by git), or into the folder you name. Needs `makensis` and `python3`. |
| `../../../.github/workflows/voice-studio-installer.yml` | Builds the unsigned file on a push that touches the installer, and checks the PowerShell on a Windows runner. Signs and publishes nothing. |

## Build it

```bash
sudo apt install nsis      # once
tools/voice_studio/installer/build.sh
```

The file is the same bytes every time for the same sources. It holds **no copy of ACK**: the program is fetched from its source while the wizard runs.

## What it fetches, and from where

The wizard names these before it goes on. The program comes from `github.com/ASPDesignLabs/ACK` (the files as they are there at run time), Ubuntu 24.04 and WSL from Microsoft,
Ubuntu's own programs from Ubuntu's archives, and the training programs and the starting voice from the places the tool lists, each with its own terms.

**To fetch from somewhere else** (a mirror, or a self-hosted source), change these and rebuild:

* `install.ps1`, in `Get-AckVsSettings`: `Repo`, `RawHost` (and `OneLiner`);
* `get.sh`: `REPO_URL`;
* `data/sources.json`: the registry of what the tool downloads (a test holds it to an allowed-host list, which the new host must join);
* the page text in `ack-voice-studio.nsi` ("Where everything comes from"), which names the source.

A test (`tests/test_vs_installer.py`) fails when the wizard names a place `install.ps1` does not fetch from, so changing one side alone is caught.

## Signing (postponed)

The build does not sign. When there is a solution, signing is one more step after `build.sh` (for example `osslsigncode` on Linux, or `signtool` on Windows) on the `.exe`; the `.sha256`
file then has to be made again. Until then Windows shows its warning for an unknown publisher, and the checklist asks the person running it to write down exactly what it said.

## A restart, and carrying on

WSL itself sometimes needs a restart. The wizard then asks `Restart now?` (a Restart, 20 seconds to cancel, only after Yes) and, either way, leaves one `RunOnce` value for this user that starts a copy of itself
(`Resume.exe`) at the next sign-in. The engine writes down in `%LOCALAPPDATA%\ack-voice-studio\installer-state.ini` that a restart is waited for and when Windows last started, so a run before the restart says
so and a run after it carries on from there without asking for a second restart; every step that succeeds is written down too, and the account name (never the password) is offered again. WSL counts as set
up when any one of `wsl -l -v`, `wsl --status` and `wsl --version` succeeds. If something stops, `installer.log` and `installer-state.ini` in the same folder are what to send.

## The password

The wizard sees the Ubuntu password the person types (the command-line installer never does). It puts it in the environment of the one engine step that needs it, the engine sends it to Ubuntu
on the standard input of one `chpasswd`, and it is written to no file, log, message or command line. It is set only on an account that has none; an account that is already there is used, and
its password is not asked for or changed. Tests hold each of these (`tests/test_vs_installer.py`, `tests/test_vs_installer_engine.py`).
