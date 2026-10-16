# ACK Voice Studio: Installation Guide for Windows

This guide gets ACK Voice Studio running on a Windows computer when all you have is PowerShell. It is one command, then a few questions. At the end, the Voice Studio window opens.

It stands on its own: you do not need any other file to follow it. If you use Ubuntu directly (not inside Windows), use the separate Ubuntu guide instead: `ACK_Voice_Studio_Installation_Guide_Ubuntu.MD`.

**What it is for.** ACK Voice Studio helps you make a voice for the ACK app from your own recordings, on your own computer. Your recordings, the text it writes from them and the finished voice stay on your computer. The only things it downloads are programs and models, and it asks before each download.

**How it runs on Windows.** The tool is a Linux program. Windows can run Linux inside itself with a feature called WSL. The command below sets up WSL and Ubuntu if you do not have them, then installs and opens Voice Studio inside Ubuntu. The window appears on your Windows desktop like any other window.

---

## 1. Before you start

| You need | Details |
|---|---|
| Windows | Windows 11. Windows 10 version 21H2 or newer (the last Windows 10 is 22H2) should work too, but it has not been tried here and Windows 10 is past its standard support. It must be the 64-bit kind. |
| PowerShell | The one that comes with Windows is fine. To open it: press the Start button, type `PowerShell`, press Enter. |
| Free room | At least 25 GB free on the drive Windows is installed on. About 63 GB is comfortable for two people's projects and both starting voices. |
| Memory | About 8 GB of memory (RAM) or more. |
| Graphics card | To train a voice you need an Nvidia graphics card with 8 GB or more of its own memory, and the Nvidia driver installed in Windows. Without one you can still bring in recordings, let the computer listen to them and make training sets. |
| Virtualization | Switched on in the computer's startup settings (the firmware). Most computers have it on. If it is off, the command tells you. |
| Internet | For downloads: about 5 GB in all, plus Ubuntu itself if you do not have it yet. |
| Administrator rights | Only if WSL is not installed yet. Windows asks for them once, for WSL itself. If WSL is already there, you need none. |

You will choose an Ubuntu user name and password the first time Ubuntu starts. They are for Ubuntu only and are not your Windows ones. Remember the password: Ubuntu asks for it again during the install.

---

## 2. The one command

Open PowerShell and paste this line, then press Enter:

```powershell
irm https://raw.githubusercontent.com/ASPDesignLabs/ACK/main/tools/voice_studio/install.ps1 | iex
```

`irm` fetches the script, which is a short text file, and `iex` runs it. The script never asks for your Windows password, never changes PowerShell's script rules, and makes no web request of its own.

It is safe to run the command again at any point. It looks at what is already done and carries on from there.

### What it does, in order

1. **It looks at the computer.** It reads the Windows version, whether virtualization is on, whether an Nvidia driver is installed and how much room is free. It changes nothing. A note about a missing Nvidia driver or low room does not stop it.
2. **It looks for Ubuntu inside WSL.** It uses Ubuntu 24.04 if it is there, then Ubuntu 22.04. If you have neither, it offers to install Ubuntu 24.04 (see section 3).
3. **It makes sure Ubuntu has a user.** If you have never opened Ubuntu, it tells you to do that once (see section 3).
4. **It starts the Ubuntu part, in the same window.** From here the questions are Ubuntu's and Voice Studio's, in this same PowerShell window:
   - It fetches ACK's files into `ack-tools` in your Ubuntu home folder. It asks before it installs `git`, a small standard program that does this.
   - It lists the few Ubuntu programs it needs and asks once. Ubuntu then asks for your Ubuntu password, here in this window. The tool never sees it.
   - It sets up the programs that listen to your recordings and make training sets. They are small. It shows the size and asks first.
   - It sets up the programs that train the voice. They are large (about 10 GB free is needed while they are built). It asks first, and you can say no now and do it later.
5. **It opens the window.** The Ubuntu part does not open the window itself: PowerShell does, as the very last step, so that Windows keeps a session open to Ubuntu. While the window is open, this PowerShell window stays busy and shows nothing. Leave it open: closing it closes the Voice Studio window. When you close the Voice Studio window, PowerShell is free again.

### Looking first, changing nothing

To see what would happen without doing any of it, set one thing and run the same command:

```powershell
$env:ACK_VOICE_DRYRUN = '1'
irm https://raw.githubusercontent.com/ASPDesignLabs/ACK/main/tools/voice_studio/install.ps1 | iex
Remove-Item Env:ACK_VOICE_DRYRUN
```

It prints what it found and the exact commands it would run, and runs none of them. The last line puts things back (a setting like this lasts only as long as that PowerShell window anyway). Use `ACK_VOICE_CHECK` instead of `ACK_VOICE_DRYRUN` to only look and say whether it is ready.

### If you want to read the script before running it

This saves the script, lets you open it, and runs your saved copy for this one time without changing any PowerShell setting:

```powershell
irm https://raw.githubusercontent.com/ASPDesignLabs/ACK/main/tools/voice_studio/install.ps1 -OutFile $env:USERPROFILE\Downloads\install-ack-voice-studio.ps1
notepad $env:USERPROFILE\Downloads\install-ack-voice-studio.ps1
powershell -ExecutionPolicy Bypass -File $env:USERPROFILE\Downloads\install-ack-voice-studio.ps1
```

The same script is in ACK's source files at `tools/voice_studio/install.ps1`.

---

## 3. A Windows that has never run Linux

If WSL or Ubuntu is not there yet, the command stops at step 2 and walks you through this. You do each part once.

1. **Open PowerShell as administrator.** Right-click the Start button, choose `Terminal (Admin)` or `Windows PowerShell (Admin)`, and answer Windows' question with Yes. That question is Windows asking, not this tool. If you started as an ordinary user, the command says `Installing WSL needs PowerShell opened as administrator.` and stops without changing anything.
2. **Paste the same command again.** It asks:
   `Install WSL and Ubuntu 24.04 now? It downloads Ubuntu from Microsoft, needs administrator rights, and needs a restart afterwards. Type yes to go on.`
   Type `yes`. Anything else, including pressing Enter, means no, and nothing is installed.
3. **Windows installs Ubuntu** and shows its own progress. If Ubuntu then asks for a user name and a password, choose them now.
4. **Restart if it asks.** If WSL needs a restart, the command says `WSL is installed but needs the computer to restart first. Restart it, then run the same command again. It carries on from here.` Restart, open an ordinary PowerShell and paste the one command again.
5. **If Ubuntu has no user yet,** the command says so: `Ubuntu is installed but has no user yet. Open Ubuntu 24.04 from the Start menu once. Choose a user name and a password, which are for Ubuntu only. Close it, then run the same command again.` Do that, then paste the one command again.

After this, the command goes on to step 4 above without any more Windows steps.

---

## 4. What you will see and what to type

The sentences below are what the tool prints, word for word. Your numbers and names will differ.

| You see | What it means | What to do |
|---|---|---|
| `Looking at this computer. Nothing is changed at this step.` | The first look. | Wait. |
| `Starting the Ubuntu part. Ubuntu will ask for the password you chose, in this window, to install a few Ubuntu programs.` | The hand-over to Ubuntu. | Wait for its questions. |
| `Install these now? Type y for yes, or press Enter for no:` | The list of Ubuntu programs to install. | Read the list. Type `y` to go on. |
| `Installing programs needs administrator rights. Ubuntu will ask for your password here, in this window. This tool never sees it.` | Ubuntu's own password question comes next. | Type your Ubuntu password. Nothing shows as you type: that is normal. |
| `This computer is ready.` | The Ubuntu programs are in. | Wait for the next step. |
| `Next: the programs that listen to your recordings and make training sets. They are small.` | The first set of programs. | Read what it shows, then type `yes` at `Download and set it up now? Type yes to go on.` |
| `Next: the programs that train the voice. They are large, and the next question says how much room they need. You can say no now and do this later: everything before training works without them.` | The second set. | Type `yes` to set them up now, or `no` to do it later. |
| `The internet connection stopped. Nothing is lost and you do not need to do anything.` | A download was cut off. | Wait. It tries again by itself, and carries on from where it stopped. |
| `Opening the window. Leave this PowerShell window open while you use Voice Studio: closing it closes the Voice Studio window. When you close the Voice Studio window, this PowerShell window is free again.` | The last step. | The Voice Studio window appears. Leave PowerShell open while you use it. |
| `The Voice Studio window was closed.` | You closed the window. | Nothing. PowerShell is free again. |

If you press Ctrl+C at any time, it stops cleanly, keeps what was finished, and the same command carries on later.

---

## 5. Your first hour in the window

The window has pages for Projects, Recordings, Training rounds, Voice file, Free up space and Display. Do these in order.

1. **Projects, then `New project…`.** Give the project a name and the hours of recording you expect. Say whose voice it is. Under `Starting voice` you can choose a voice to start from, or `Choose later`. Press the button that makes the project. It shows what it will make and asks first.
2. **Bring in recordings.** On the Recordings page press `Bring in recordings…`. You choose the kind: an ACK package from the phone (a zip file), a folder of audio files with a text file for each, a folder of audio files with one table, or audio files alone. It shows what it found and asks before it adds anything. It only reads your files; it never changes or removes them.
3. **`Get the listening model…`** (once, about 485 MB). It shows where the model comes from and asks before it downloads anything.
4. **`Let the computer listen…`** The computer writes down what it hears and marks where each piece begins and ends. Your recordings are not changed. This can take a while, and it carries on by itself if you close the window.
5. **`Make a training set…`** (or `See what a training set would hold` to only look first). It makes the set in a new folder.
6. **Get the starting voice, in Ubuntu.** This one step is still typed, because the window has no screen for it yet. Open Ubuntu from the Start menu and run the command below, with your project's name in place of `voice-check`. It shows where the voice comes from, asks you to confirm that you read it, and asks again before it downloads about 846 MB. The tool says nothing about whether your use of a voice is allowed: read what it shows.

   ```bash
   PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.projects list
   PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.voices get mike --project voice-check
   ```

   The first line lists your projects so you can copy the project's name exactly.
7. **Training rounds, then `Start a round…`.** This needs the training programs (section 2, step 4) and a graphics card. It shows the plan and asks first. You can stop a round and start another from the one you choose.
8. **Voice file, then `Make the voice file…`.** This makes the zip file ACK takes, from the round you chose, in a new folder. Press `Show the folder` to open it in Windows File Explorer. Copy the zip file to your phone. In ACK, open AUDIO ARCHITECT, find CUSTOM VOICE and press IMPORT, then pick the zip file.

Every button that changes something shows you what it will do and asks first. Anything that deletes shows what goes. Deleting a whole project asks twice.

---

## 6. Opening it again later

- **From the Start menu.** In Ubuntu, run the line below once. It shows exactly what it will write, writes only in your own folders, and needs no administrator rights and no password. Then look for ACK Voice Studio in the Start menu.

  ```bash
  PYTHONPATH=~/ack-tools/tools /usr/bin/python3 -m voice_studio.window --install-launcher
  ```

  The first start after Windows has stopped WSL can take a little while. Nothing shows until the window is ready. To take the shortcut away, run the same line with `--remove-launcher`.
- **From Ubuntu.** Open Ubuntu from the Start menu and run:

  ```bash
  PYTHONPATH=~/ack-tools/tools /usr/bin/python3 -m voice_studio.window
  ```

- **Or run the one command again.** It checks everything, finds it all in place, and opens the window. PowerShell stays busy until you close the window.

Your projects are in `ack-voice-studio` in your Ubuntu home folder. In the window, the `Show the folder` buttons open the right folder in File Explorer. Do not move the folder into OneDrive, Dropbox or other synced folders.

---

## 7. Long jobs, and closing windows

On WSL, Ubuntu stops by itself about a minute after the last Ubuntu window is closed, and it takes a running job with it. This was found on the developer's computer. A job stopped this way is reported as interrupted.

While a round trains, leave an Ubuntu window open: a session that stays open keeps Ubuntu running. The PowerShell window that opened Voice Studio counts too, as long as the Voice Studio window is open. A Voice Studio window opened from the Start menu keeps Ubuntu running by itself.

One setting stops this, and it worked in one test on WSL 2.7.14 (other people report that it did not always work on older versions). It is a Windows setting, so it is your choice. First make a copy of your settings file if you have one, then add the two lines:

```powershell
if (Test-Path $env:USERPROFILE\.wslconfig) { Copy-Item $env:USERPROFILE\.wslconfig $env:USERPROFILE\.wslconfig.bak }
notepad $env:USERPROFILE\.wslconfig
```

```text
[general]
instanceIdleTimeout=-1
```

Then run `wsl.exe --shutdown` in PowerShell. **Do not do this while a job is running:** it stops everything in Ubuntu. With this setting, Ubuntu keeps running in the background until you run `wsl.exe --shutdown` or restart Windows.

---

## 8. When something goes wrong

Run the same command again first: it carries on from where it stopped and does not repeat what is done.

| Message or problem | What to do |
|---|---|
| `This version of Windows is too old to show Linux windows. It needs Windows 10 version 21H2 or newer, or Windows 11. Update Windows, then run this again.` | Update Windows, then run the command again. |
| `Virtualization looks switched off.` | Switch it on in the computer's startup settings (the firmware). Where that is differs from one computer to the next: search for your computer maker's name and `enable virtualization`. |
| `Installing WSL needs PowerShell opened as administrator.` | See section 3, step 1. |
| `WSL is installed but needs the computer to restart first.` | Restart, then run the command again. |
| `Ubuntu is installed but has no user yet.` | See section 3, step 5. |
| `Ubuntu was found, but as WSL version 1. This needs version 2.` | Run the `wsl --set-version` line the message shows. It can take a while. Then run the command again. |
| `The install did not finish. Windows said the lines above. Nothing else was changed. Run the same command again to try once more.` | Read the lines above it. If they mention virtualization or a missing feature, see those rows. |
| `The window stopped with code`, then a number | Read what the window said just above. Run the command again to open it again. If it says there is no desktop, see that row below. |
| `The Ubuntu part stopped with code`, then a number | Read what Ubuntu said just above. Run the command again to carry on. |
| `It stopped at this step, and what was finished is kept. Run the same command again to carry on from here.` | Read the three-part message just above. Run the command again. |
| `There is no desktop to show a window on.` | Windows needs a version with graphical Linux programs. Updating WSL is Microsoft's usual advice, though it has not been tried here on a computer that showed this message: in PowerShell run `wsl --update`, then `wsl --shutdown`, then the one command again. |
| `Everything above was set up, but the window cannot open here. The reason is above.` | Everything is installed. Fix what the lines above say, then run the one command again to open the window. |
| PowerShell says running scripts is disabled | The one-line command is not a script file, so it is not stopped by that. If you saved the file, run it with `powershell -ExecutionPolicy Bypass -File` as in section 2. That affects only that one run. |
| PowerShell cannot connect to the web address | Check the internet connection. On an older Windows 10, running `[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12` first is the usual fix. On a work computer, a proxy may be in the way: ask whoever looks after it. |
| No supported graphics card was found | Training is switched off. Everything else works. Install the Nvidia driver in **Windows** (not inside Ubuntu), restart, and run the command again. |

**If you want a helper to look.** A command that fails after it began ends with two lines about a problem report. A problem report is a plain text file: the versions, the checks on this computer, the problem and how a task ended, with your names and folders blanked and no recordings, no text you made and no phrases. You see all of it first, and it is saved only where you say:

```bash
PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.report show
PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.report save --to ~/problem-report.txt
```

`show` prints the report and changes nothing. `save` prints it again, asks once, and writes exactly that text to the file you name. It never replaces a file unless you add `--replace`, and the tool never sends it anywhere: read it, then give the file to the helper yourself.

If Ubuntu already works and only the PowerShell part gives you trouble, you do not need it: open Ubuntu from the Start menu and follow the separate Ubuntu guide from its one command.

---

## 9. Updating, and removing

**Updating.** In Ubuntu:

```bash
cd ~/ack-tools && git pull
PYTHONPATH=~/ack-tools/tools python3 -m voice_studio
```

The second line checks everything and asks before it rebuilds anything that changed. Nothing updates by itself.

**Looking at the releases.** To see whether ACK has a named release and fetch one into a new folder beside this one, without changing this one:

```bash
PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.update check
PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.update get RELEASE
```

Each says first what it will ask github.com and shows the exact commands, then asks before it contacts anything. `get` never touches this copy: it prints two commands, one for trying the new copy and one for using it under the usual name, and you type them. Your projects and recordings stay in `ack-voice-studio` whichever copy you use. If ACK has not named a release yet, `check` says so.

**Removing.** In Ubuntu, one command takes the programs the tool built and the files it downloaded off the disk. It does not touch your projects, your recordings, your backups or the starting voices you chose. Look first, then remove:

```bash
PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.uninstall show
PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.uninstall remove
```

`show` only looks. `remove` shows the same list, asks once, and removes only what it showed. It cannot remove the tool's own files or the Start menu shortcut, so it prints the command for each and you run them:

- To take the Start menu shortcut away, run the `--remove-launcher` line from section 6 (`show` prints it too).
- To remove the tool's own files, delete the folder `ack-tools` in your Ubuntu home folder: `rm -r ~/ack-tools`. Do this last, because the commands above need it.
- Your projects and recordings stay in `ack-voice-studio` in your Ubuntu home folder. To delete one project, use `PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.projects delete`: it asks twice and names a backup first.
- To delete everything, make a copy of your projects first: copy `ack-voice-studio` from your Ubuntu home folder to a USB drive or an external disk that you control. In Ubuntu, a Windows drive appears under `/mnt`, for example `/mnt/d`. Do not copy it into OneDrive, Dropbox or Documents, which may be synced. Then delete the folder `ack-voice-studio`. **This deletes your projects and recordings.** The backups the tool made are inside that folder too, in `backups`, so copy those out as well.
- The Ubuntu programs it installed stay (they are ordinary Ubuntu programs and can be removed with `apt`).
- To remove Ubuntu from Windows completely, run `wsl --unregister Ubuntu-24.04` in PowerShell. **This deletes everything inside that Ubuntu, with no way back.**

---

## 10. What it contacts, and what stays on your computer

Nothing you record leaves your computer. There are no accounts, no usage reports and no automatic update checks. Each place below is contacted only for the reason given.

| Place | Why | When |
|---|---|---|
| `raw.githubusercontent.com` and `github.com` | To fetch this script and ACK's files. | The first run, and when you run the update command in section 9 and say yes. |
| Microsoft | To install WSL and Ubuntu. | Only if they are not installed yet. |
| Ubuntu's package servers | The few Ubuntu programs in section 2. | Once, with your yes. |
| The Python package site (`pypi.org` and `files.pythonhosted.org`) | The programs the tool runs on. | When you say yes to each set. |
| `huggingface.co` | The listening model and a starting voice. | Only when you press the button or run the command, after you agree. |

Every file the tool downloads is checked against a fixed size and fingerprint before it is used. A file that does not match is never used.

---

## 11. Reference

**Options.** Add them after the file name when you run a saved copy, or set the matching setting before the one-line command (a pipe cannot take options).

| Option | Setting | What it does |
|---|---|---|
| `-Ref name` | `ACK_VOICE_TAG` | Which release, tag or branch of ACK to fetch. The default is `main`. |
| `-Distro name` | `ACK_VOICE_DISTRO` | Use this Ubuntu (for example `Ubuntu-22.04`). It must start with Ubuntu. |
| `-Check` | `ACK_VOICE_CHECK` = `1` | Only look. Say whether it is ready. |
| `-DryRun` | `ACK_VOICE_DRYRUN` = `1` | Only look, and print the exact commands it would run. |
| `-Yes` | `ACK_VOICE_YES` = `1` | You have already said yes to its questions. It still needs administrator rights to install WSL. |
| `-Help` | | Print the options. |

**Exit codes**, for scripts: `0` done (or only looked), `1` something stopped it, `2` nothing was done (you said no, nobody could be asked, or an option was not understood), `3` a step is left for you (restart, or open Ubuntu once): do it, then run the same command again.

**Ubuntu-side options.** After the PowerShell part, the Ubuntu part is the command `python3 -m voice_studio` with `--check` (only look), `--dry-run` (show the commands), `--yes` and `--no-window`. They are described in the Ubuntu guide.

---

## 12. What has been tested

- **On a real computer** (the developer's: Windows 11, WSL 2.7.14, Ubuntu 22.04 and 24.04, an Nvidia RTX 4060 with 8 GB): the Ubuntu steps, including the Ubuntu programs, both sets of programs, the window through WSL's graphics, the Start menu shortcut, the listening model, a training round and the voice file. The voice file was imported into ACK on a phone.
- **With stand-ins, not on Windows:** every decision the PowerShell script makes was run with PowerShell. It used stand-ins for `wsl.exe`, for your answers and for the facts about the computer. The cases were: Windows too old, no WSL, no Ubuntu, no user, version 1, a no, nobody to ask, a failed install, a restart, a failed hand-over, a window that stops, `-Check` and `-DryRun`.
- **Not yet run on a real, clean Windows:** the PowerShell script itself from start to finish, including the real `wsl --install`, the restart and Ubuntu's first run. If it stops with a message you cannot follow, the Ubuntu guide's route works without it.
