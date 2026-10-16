# ACK Voice Studio: Installation Guide for Ubuntu

This guide gets ACK Voice Studio running on Ubuntu with one command and a few questions. At the end, the Voice Studio window opens.

It stands on its own: you do not need any other file to follow it. If you are on Windows, use the separate Windows guide instead: `ACK_Voice_Studio_Installation_Guide.MD`. It sets up Ubuntu inside Windows for you and then does the same Ubuntu steps as this guide.

**What it is for.** ACK Voice Studio helps you make a voice for the ACK app from your own recordings, on your own computer. Your recordings, the text it writes from them and the finished voice stay on your computer. The only things it downloads are programs and models, and it asks before each download.

**Where it has been tested.** Ubuntu 22.04 and 24.04 running inside Windows (WSL) on one computer. A normal Ubuntu desktop on its own hardware has not been tried yet. The steps are the same, and the tool checks each one, but treat the first run as a test and tell the developer what you see.

---

## 1. Before you start

| You need | Details |
|---|---|
| Ubuntu | 22.04 or 24.04 (the long-term releases). On a newer Ubuntu the tool stops with `The system software that runs this tool is newer than this part has been tried with.` |
| A desktop | The window needs a graphical session. Over SSH, or on Ubuntu Server, the programs still install and the terminal commands work, but no window opens. |
| Python | The Python that comes with Ubuntu: version 3.10, 3.11 or 3.12. |
| Free room | At least 25 GB free in your home folder's drive. About 63 GB is comfortable for two people's projects and both starting voices. |
| Memory | About 8 GB of memory (RAM) or more. |
| Graphics card | To train a voice: an Nvidia card with 8 GB or more of its own memory, and Nvidia's driver installed in Ubuntu. Without one you can still bring in recordings, let the computer listen to them and make training sets. |
| Internet | For downloads: about 5 GB in all. |
| Administrator rights | Once, for a few Ubuntu programs. Ubuntu asks for your password in your own terminal. The tool never sees it. |

The tool never installs a graphics driver. If you have an Nvidia card and no driver, install it yourself in Ubuntu's Software & Updates under Additional Drivers, restart, and run the command again. The tool then finds the card and says so.

---

## 2. The one command

Open a terminal (press Ctrl+Alt+T) and paste this line, then press Enter:

```bash
curl -fsSL https://raw.githubusercontent.com/ASPDesignLabs/ACK/main/tools/voice_studio/get.sh | bash
```

If your Ubuntu has no `curl`, this does the same with `wget`:

```bash
wget -qO- https://raw.githubusercontent.com/ASPDesignLabs/ACK/main/tools/voice_studio/get.sh | bash
```

The script it fetches is short. It fetches ACK's files into `ack-tools` in your home folder, and hands over to the setup. It never changes a folder that is already there unless you say yes to updating it (step 1), and it never edits your shell settings.

It is safe to run the command again at any point. It finds what is done and carries on.

### What it does, in order

1. **It fetches ACK's files.** If `git` is missing it says so and asks before installing it: `Install git now? Type y for yes, or press Enter for no:`. If ACK is already at `ack-tools`, it uses that copy and fetches nothing. If that copy is not the release you asked for (an older copy, for example, which can stop with `Unknown option`), it says so and asks `Update the copy now? Type y for yes, or press Enter to use it as it is:`. A yes runs `git pull --ff-only` in that folder and nothing else; your projects and recordings are in `ack-voice-studio`, not there. A copy with changes of your own is never updated, and with nobody to ask it is left as it is.
2. **It looks at the computer** and lists the few Ubuntu programs it needs. It asks once. Ubuntu then asks for your password in your own terminal.
3. **It sets up the programs that listen to your recordings and make training sets.** They are small. It shows the size and asks first.
4. **It sets up the programs that train the voice.** They are large (about 10 GB free is needed while they are built). It asks first, and you can say no now and do it later.
5. **It checks that the window can open here, and opens it.**

### Looking first, changing nothing

```bash
curl -fsSL https://raw.githubusercontent.com/ASPDesignLabs/ACK/main/tools/voice_studio/get.sh | bash -s -- --dry-run
```

It prints the exact commands it would run, and runs none of them. `--check` does the same. Once ACK's files are in place, you can look at this computer without changing anything:

```bash
PYTHONPATH=~/ack-tools/tools python3 -m voice_studio --check
```

It says what is missing and exits with code 1 if something needs fixing, or `Ready: nothing needs fixing.` if not.

### If you want to read the script before running it

```bash
curl -fsSL https://raw.githubusercontent.com/ASPDesignLabs/ACK/main/tools/voice_studio/get.sh -o ~/get-ack-voice-studio.sh
less ~/get-ack-voice-studio.sh
bash ~/get-ack-voice-studio.sh
```

### If you already have ACK's files

If you have cloned ACK yourself, run its setup from the ACK folder:

```bash
./tools/voice_studio/setup.sh
```

---

## 3. What you will see and what to type

The sentences below are what the tool prints, word for word. Your names and numbers will differ.

| You see | What it means | What to do |
|---|---|---|
| `Looking at this computer. Nothing is changed at this step.` | The first look. | Wait. |
| `Install these now? Type y for yes, or press Enter for no:` | The list of Ubuntu programs to install. | Read the list. Type `y` to go on. |
| `Installing programs needs administrator rights. Ubuntu will ask for your password here, in this window. This tool never sees it.` | Ubuntu's own password question comes next. | Type your password. Nothing shows as you type: that is normal. |
| `This computer is ready.` | The Ubuntu programs are in. | Wait for the next step. |
| `Next: the programs that listen to your recordings and make training sets. They are small.` | The first set of programs. | Read what it shows, then type `yes` at `Download and set it up now? Type yes to go on.` |
| `Next: the programs that train the voice. They are large, and the next question says how much room they need. You can say no now and do this later: everything before training works without them.` | The second set. | Type `yes` to set them up now, or `no` to do it later. |
| `The internet connection stopped. Nothing is lost and you do not need to do anything.` | A download was cut off. | Wait. It tries again by itself, and carries on from where it stopped. |
| `Opening the window.` | The last step. | The Voice Studio window appears. |

If you press Ctrl+C at any time, it stops cleanly, keeps what was finished, and the same command carries on later.

---

## 4. Your first hour in the window

The window has pages for Projects, Recordings, Training rounds, Voice file, Free up space and Display. Do these in order.

1. **Projects, then `New project…`.** Give the project a name and the hours of recording you expect. Say whose voice it is. Under `Starting voice` you can choose a voice to start from, or `Choose later`. It shows what it will make and asks first.
2. **Bring in recordings.** On the Recordings page press `Bring in recordings…`. You choose the kind: an ACK package from the phone (a zip file), a folder of audio files with a text file for each, a folder of audio files with one table, or audio files alone. It shows what it found and asks before it adds anything. It only reads your files; it never changes or removes them.
3. **`Get the listening model…`** (once, about 485 MB). It shows where the model comes from and asks before it downloads anything.
4. **`Let the computer listen…`** The computer writes down what it hears and marks where each piece begins and ends. Your recordings are not changed. This can take a while, and it carries on by itself if you close the window.
5. **`Make a training set…`** (or `See what a training set would hold` to only look first). It makes the set in a new folder.
6. **Get the starting voice, in a terminal.** This one step is still typed, because the window has no screen for it yet. Run the commands below, with your project's name in place of `voice-check`. The first lists your projects so you can copy the name exactly. The second shows where the voice comes from, asks you to confirm that you read it, and asks again before it downloads about 846 MB. The tool says nothing about whether your use of a voice is allowed: read what it shows.

   ```bash
   PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.projects list
   PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.voices get mike --project voice-check
   ```

7. **Training rounds, then `Start a round…`.** This needs the training programs (section 2, step 4) and a graphics card. It shows the plan and asks first. You can stop a round and start another from the one you choose.
8. **Voice file, then `Make the voice file…`.** This makes the zip file ACK takes, from the round you chose, in a new folder. Press `Show the folder` to open it. Copy the zip file to your phone. In ACK, open AUDIO ARCHITECT, find CUSTOM VOICE and press IMPORT, then pick the zip file.

Every button that changes something shows you what it will do and asks first. Anything that deletes shows what goes. Deleting a whole project asks twice.

---

## 5. Opening it again later

- **From your applications list.** Run this once. It shows exactly what it will write, writes only in your own folders, and needs no administrator rights. Then look for ACK Voice Studio in the applications list of your desktop.

  ```bash
  PYTHONPATH=~/ack-tools/tools /usr/bin/python3 -m voice_studio.window --install-launcher
  ```

  To take it away, run the same line with `--remove-launcher`.
- **From a terminal.**

  ```bash
  PYTHONPATH=~/ack-tools/tools /usr/bin/python3 -m voice_studio.window
  ```

- **Or run the one command again.** It checks everything, finds it all in place, and opens the window.

Your projects are in `ack-voice-studio` in your home folder. Do not move that folder into a synced folder such as Dropbox or OneDrive.

---

## 6. Without a desktop: the terminal commands

On a computer with no desktop session, set up the programs without the window:

```bash
PYTHONPATH=~/ack-tools/tools python3 -m voice_studio --no-window
```

Everything the window does can also be done from the terminal, one command at a time, and each asks before it changes anything. The file `tools/voice_studio/README.md` inside the folder `ack-tools` lists them all. Start with `python3 -m voice_studio.projects help` and `python3 -m voice_studio.recordings help`, run as in section 4.

---

## 7. When something goes wrong

Run the same command again first: it carries on from where it stopped and does not repeat what is done.

| Message or problem | What to do |
|---|---|
| `Unknown option:` | A word after the command was not understood. The options are `--check`, `--dry-run`, `--yes` and `--no-window`. |
| `This cannot ask you a question here, so it did nothing. To go ahead, run it again and add --yes.` | There was no terminal to type in (for example a script). Run it in a terminal, or add `--yes` once you have read what it will do. |
| `Nothing was changed. Fix the problems above, then run this again.` | The first look found something that blocks it. Read the lines above this one. |
| `The Python on this computer is too old (3.10 or newer is needed). Updating Ubuntu will fix this.` | Update Ubuntu, or use 22.04 or 24.04. |
| `The system software that runs this tool is newer than this part has been tried with.` | Use Ubuntu 22.04 or 24.04, or wait for an update to this tool that supports yours. |
| `The installation did not finish. Your files were not changed. Look at the messages above, then try again.` | Read the messages above it (often the internet connection or a locked package manager), then run the command again. |
| `It stopped at this step, and what was finished is kept. Run the same command again to carry on from here.` | Read the three-part message just above. Run the command again. |
| `There is no desktop to show a window on.` | You are not in a desktop session. Start it from the desktop, or use section 6. |
| `GTK 4 is not installed.` | The message shows the command that installs it. Then run the one command again. |
| `Everything above was set up, but the window cannot open here. The reason is above.` | Everything is installed. Fix what the lines above say, then run the one command again. |
| `No supported graphics card was found, so training is switched off.` | Everything else works. For an Nvidia card, install its driver (section 1), restart, and run the command again. |
| A web address cannot be reached | Check the internet connection. On a work network, a proxy may be in the way: ask whoever looks after it. |

---

## 8. Updating, and removing

**Updating.**

```bash
cd ~/ack-tools && git pull
PYTHONPATH=~/ack-tools/tools python3 -m voice_studio
```

The second line checks everything and asks before it rebuilds anything that changed. Nothing updates by itself.

If `git pull` says you are not on a branch, you installed a fixed release: to use a newer one, run the one command with `ACK_VOICE_TAG` set to the new release name and `ACK_VOICE_DIR` set to a new folder, and your old folder stays as it was.

**Looking at the releases.** To see whether ACK has a named release and fetch one into a new folder beside this one, without changing this one:

```bash
PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.update check
PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.update get RELEASE
```

Each says first what it will ask github.com and shows the exact commands, then asks before it contacts anything. `get` never touches this copy: it prints two commands, one for trying the new copy and one for using it under the usual name, and you type them. Your projects and recordings stay in `ack-voice-studio` whichever copy you use. If ACK has not named a release yet, `check` says so.

**Removing.** One command takes the programs the tool built and the files it downloaded off the disk. It does not touch your projects, your recordings, your backups or the starting voices you chose. Look first, then remove:

```bash
PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.uninstall show
PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.uninstall remove
```

`show` only looks. `remove` shows the same list, asks once, and removes only what it showed. It cannot remove the tool's own files or the entry in the applications list, so it prints the command for each and you run them:

- To take the applications-list entry away, run the `--remove-launcher` line from section 5 (`show` prints it too).
- To remove the tool's own files, delete the folder `ack-tools` in your home folder: `rm -r ~/ack-tools`. Do this last, because the commands above need it.
- Your projects and recordings stay in `ack-voice-studio` in your home folder. To delete one project, use `PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.projects delete`: it asks twice and names a backup first.
- To delete everything, make a copy of your projects first: copy the folder `ack-voice-studio` from your home folder to a USB drive or an external disk that you control. Do not copy it into Dropbox, OneDrive or a similar synced folder. Then delete the folder `ack-voice-studio`. **This deletes your projects and recordings.** The backups the tool made are inside that folder too, in `backups`, so copy those out as well.
- The Ubuntu programs it installed stay (they are ordinary Ubuntu programs and can be removed with `apt`).

---

## 9. What it contacts, and what stays on your computer

Nothing you record leaves your computer. There are no accounts, no usage reports and no automatic update checks. Each place below is contacted only for the reason given.

| Place | Why | When |
|---|---|---|
| `raw.githubusercontent.com` and `github.com` | To fetch the setup script and ACK's files. | The first run, and when you run the update command in section 8 and say yes. |
| Ubuntu's package servers | The few Ubuntu programs in section 2. | Once, with your yes. |
| The Python package site (`pypi.org` and `files.pythonhosted.org`) | The programs the tool runs on. | When you say yes to each set. |
| `huggingface.co` | The listening model and a starting voice. | Only when you press the button or run the command, after you agree. |

Every file the tool downloads is checked against a fixed size and fingerprint before it is used. A file that does not match is never used.

---

## 10. Reference

**Options.**

| Where | Option | What it does |
|---|---|---|
| The one command, or `setup.sh` | `--check` | Only look. Exit code 0 when ready, 1 when something needs fixing. |
| The one command, or `setup.sh` | `--dry-run` | Show the exact commands that would run. Change nothing. |
| The one command, or `setup.sh` | `--yes` | You have already said yes, so it does not ask. |
| `python3 -m voice_studio` and `setup.sh` | `--no-window` | Set the programs up and do not open the window. |
| Setting before the one command | `ACK_VOICE_TAG` | Which release, tag or branch of ACK to fetch. The default is `main`. |
| Setting before the one command | `ACK_VOICE_DIR` | Where to put ACK's files. The default is `ack-tools` in your home folder. |

Put a setting on the `bash` side of the pipe, so that it reaches the script. For example, to fetch into another folder:

```bash
curl -fsSL https://raw.githubusercontent.com/ASPDesignLabs/ACK/main/tools/voice_studio/get.sh | ACK_VOICE_DIR=~/my-ack bash
```
