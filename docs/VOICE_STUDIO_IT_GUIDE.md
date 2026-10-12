# ACK Voice Studio: what an IT department needs to know, allow and check

**For:** a system administrator, IT support or a security reviewer who has been asked to approve this on a computer.
**From:** whoever handed you this page. They want to make a personal synthetic voice from their own recordings, for a speech-generating
phone app (ACK, an AAC app), and the set-up has to reach a few internet addresses that a careful network policy may block.
**This page is meant to be read in ten minutes and answered with a yes, a no, or a list of changes.**

> **Status, said plainly.** Today ACK Voice Studio is a set of terminal programs with a first, small window for training rounds, the voice file and freeing up space (section 7); the rest of the friendly window is not built yet, and this page describes
> what the terminal programs do. It has been run on **Ubuntu 22.04 and Ubuntu 24.04 under WSL2 (Windows), with an NVIDIA RTX 4060 (8 GB)**, by
> the developer. It has **not** yet been run on native Ubuntu by anyone, not on a managed or locked-down network, and not by a second person.
> Where this page says a thing was *tested*, it was; where it says *by design*, nobody has measured it. Section 11 lists both.

## 1. What it is, in thirty seconds

* The person records their own voice on their phone with the ACK app. The recordings go to the computer on a cable or USB drive.
* This program turns the recordings into a *voice file* by training a small neural network **on the computer's own graphics card**.
  Nothing is uploaded to train it. The result is one `.zip` file that goes back to the phone the same way.
* It is open source (GPL-3.0-or-later): `https://github.com/ASPDesignLabs/ACK`, folder `tools/voice_studio`.

## 2. The short version: what to approve

Tick what you will allow. Sections 3 to 9 give the detail for each line.

- [ ] **The computer** (section 3): Ubuntu 22.04 or 24.04 (WSL2 on Windows is what was tested), the system Python 3.10 to 3.12, an NVIDIA graphics
  card with 8 GB or more and its normal driver, and about **63 GiB** of free disk (25 GiB is the bare minimum).
- [ ] **One-time administrator rights** (section 4) to install seven Ubuntu packages.
- [ ] **Outbound HTTPS, port 443 only** (section 5) to the hosts in the table, during set-up. *Or* use one of the offline routes in section 6.
- [ ] **No inbound ports** from Voice Studio itself (section 7). One *separate, optional* tool (Freeform Studio) can open a port on the local network, and
  you may leave that unapproved.
- [ ] **Where it writes and what runs** (section 7): one folder in the user's home, long-running programs started by the user, no services.
- [ ] **Data handling** (section 9): recordings, transcripts and the trained voice stay on the computer.
- [ ] **Licences** (section 10): someone who handles licensing should read it before the voice is used beyond the person's own phone.

## 3. The computer

| Needed | Detail |
|---|---|
| Operating system | Ubuntu 22.04 or 24.04. Tested under **WSL2** with the Windows NVIDIA driver (no Linux driver is installed inside Ubuntu). |
| Python | The Ubuntu system Python: **3.10, 3.11 or 3.12**. The tool refuses anything older, and its locked programs are verified up to 3.12. |
| Graphics card | NVIDIA, **8 GB or more** (the tool treats under 7,900 MiB as too small). Without a usable card, training is switched off. |
| Memory | About 8 GB of RAM or more (the tool warns below about 7,000 MiB). |
| Disk | **About 63 GiB free** for two people's projects and both starting voices (the tool's own figure); **25 GiB** is the bare minimum it will start with. A single training round keeps about 4.8 GB of checkpoints. The tool shows these numbers and refuses to start without room. |
| Administrator rights | **Once**, for section 4. Afterwards everything runs as the ordinary user. |

## 4. One-time installation with administrator rights

The set-up script (`tools/voice_studio/setup.sh`) looks first, lists what is missing, asks once, and then runs exactly this (installing only the packages that are not already present) and nothing else:

```text
sudo apt-get update
sudo apt-get install -y python3-venv python3-dev build-essential git ffmpeg python3-gi gir1.2-gtk-4.0
```

| Package | Why |
|---|---|
| `python3-venv`, `python3-dev`, `build-essential` | Keep the tool's Python programs separate from the system's, and build **one** tiny part locally (a one-kilobyte C source file shipped with the tool and checked by SHA-256; this is the only place anything is compiled). |
| `git` | To fetch the tool itself and its updates. |
| `ffmpeg` | Reads and converts the audio recordings. |
| `python3-gi`, `gir1.2-gtk-4.0` | For the window (`python3 -m voice_studio.window`, section 7). Not needed to build or train. |

On a freshly installed Ubuntu 24.04 this pulled **206 new packages and upgraded 15** (233 MB to download, 552 MB on disk), mostly `ffmpeg` and
the GTK toolkit with their dependencies. The script runs `--check` (changes nothing) and `--dry-run` (prints the commands) first if you ask it to.

## 5. Network: what is contacted, when and why

All of it is **HTTPS on port 443**, outbound, during set-up. By design nothing is contacted by timer or in the background, and only one module of the tool (`core/fetch.py`) may use the network at all (a test enforces that). The tool shows every download, with its
address, size and checksum, and asks **before** it starts; the person's yes is saved in `~/ack-voice-studio/state/consent.json`.

| Host | What for | Size | When |
|---|---|---|---|
| `pypi.org` | The Python package index (pip looks packages up here) | small | set-up |
| `files.pythonhosted.org` | The Python packages themselves: the training programs (about 3.2 GB, 91 packages) and the studio programs (about 130 MB, 44 packages) | about 3.3 GB | set-up |
| `huggingface.co` | File listings and downloads of the listening model and the starting voices (table in section 8) | 4 small files, one 483 MB file, two 846 MB files | set-up; a starting voice when the person chooses it |
| `*.hf.co` (observed: `us.aws.cdn.hf.co`) | The large files are served from here after a redirect from `huggingface.co` | included above | same |
| `archive.ubuntu.com`, `security.ubuntu.com` (or the organisation's own Ubuntu mirror) | The Ubuntu packages in section 4 | about 233 MB | once, with administrator rights |
| `github.com` | To fetch the tool itself (`git clone`) and its updates | about 7 MB | install; updates only when someone runs `git pull` |

**About the redirect host.** Hugging Face decides where the large files are served from, and that can differ by region and over time. `us.aws.cdn.hf.co` is
what was observed from one place on 2026-10-11. If a large download is blocked, the tool's error names what failed; you can see where an address
leads with `curl -sI "<address>"` and reading the `location:` line. Allowing `huggingface.co` and `*.hf.co` is the simple rule.

**Addresses that are shown but never contacted.** Before a starting voice is fetched, the tool will show the web addresses of the pages that state its licence (section 10), so the person can read them. It **never opens
those pages**; nothing in the tool can: its only network code downloads the pinned files in section 8. They need no firewall rule for the tool to work.

**What it does not contact.** No telemetry, no analytics, no update check, no cloud service, no account. Programs the tool starts for training and for
listening to recordings are started with `HF_HUB_OFFLINE=1`, `HF_HUB_DISABLE_TELEMETRY=1`, `DO_NOT_TRACK=1` and `TRANSFORMERS_OFFLINE=1`, and the one thing in the trainer
that would have fetched code from the internet at run time (an optional quality scorer) is switched off. *Tested:* a run with the scorer off logged **zero** lines about it.
*By design, not measured:* that a training round succeeds with the network cut off completely.

**Proxies and inspection.** The tool runs the ordinary `pip` and Python's standard downloader, so `HTTPS_PROXY`, `pip.conf` and the system certificate store apply as
they do for any other Python program. A TLS-inspecting proxy needs its certificate authority in the system store. *Not tested here.*

**If the connection drops** mid-download, the tool waits (5, 10, 20, 30, then 60 seconds, for up to 30 minutes) and carries on by itself.

## 6. If outbound access cannot be opened: offline routes

1. **Hand over the listening-model files.** Download the four files in section 8 on an approved machine, check their SHA-256, and put them in
   `~/ack-voice-studio/tool/downloads/models/speech-small-en/` with exactly those names. The tool checks size and SHA-256 of a file that is already there
   and **skips the download** when it is right. A starting voice is fetched by the person with `python3 -m voice_studio.voices get <voice>` into `~/ack-voice-studio/tool/downloads/voices/<voice>/`, and the same rule applies: a file placed there with the exact pinned name, size and checksum is used with no download. The person still has to read and acknowledge where the voice comes from (section 10).
2. **An internal Python mirror.** The tool installs with `pip install --require-hashes --only-binary=:all: --no-deps`, so every wheel is pinned by SHA-256 in
   `tools/voice_studio/data/locks/training.lock.txt` and `studio.lock.txt`. A mirror must carry those exact files. Point pip at it with its usual
   settings (`PIP_INDEX_URL` or `pip.conf`). *Not tested here.*
3. **Ubuntu packages from the organisation's own repository,** as for any other machine.

## 7. What gets installed, where, and what runs

* **Everything is under one folder in the user's home:** `~/ack-voice-studio/`: `projects/` (one folder per person), `tool/` (the two Python environments, about 6.6 GiB, and the downloaded
  files, about 2.2 GB once the listening model and both voices are fetched), `state/` (small records), `backups/`. Nothing is installed system-wide except the packages in section 4.
* **pip also keeps its normal download cache** in `~/.cache/pip` (roughly the size of the downloads). It can be deleted at any time.
* **Long-running programs.** Training and listening to recordings run as the user's own ordinary Python processes, for minutes to hours, using the graphics
  card. They keep running if the terminal is closed, by design, and the tool can stop them on request. **There are no services, daemons, cron jobs or start-up items.**
* **Training rounds write a lot, in one place.** Each round keeps about 4.8 GB of saved files (six of about 807 MiB) under the project's `rounds/run/` folder, and a small working folder under the project's scratch folder (`scratch/caches/`, which the tool never reuses between rounds). The tool never deletes, moves or renames any of it by itself. A person who runs many rounds will see the disk fill: `python3 -m voice_studio.rounds keep` lists what is kept for sure and what is spare, with sizes, and removes nothing; `python3 -m voice_studio.rounds free` lists what could be freed (spare saved files and the working files of rounds that have ended, never recordings, notes, backups, voice files or the starting voices) and, only when told which rounds, shows exactly what it will remove and asks first. What it removes cannot be brought back. `python3 -m voice_studio.voicefile make` writes one new folder under the project's `exports` (about 1 GB at most, usually far less) holding the voice, its settings file, the original before it was prepared and the zip file for the phone; it changes and removes nothing that was there. A small record of the rounds, `rounds/rounds.json`, is the only file the tool itself keeps about them.
* **A disk guard runs inside the job's own supervisor.** A training round is started with a free-space floor for the drive it writes to; the small detached supervisor program looks every five seconds and, if the free space falls below the floor, asks the training program to stop the way Ctrl+C does (it saves what it can), and records that the reason was the disk. It only reads free space; it deletes nothing. A drive that cannot be read is not judged. Before a round starts the tool also reads the graphics card's memory use with `nvidia-smi` and refuses a round that would not fit.
* **Ports.** By design the programs the tool starts open no listening port (single-card training uses local pipes only). *Not measured with a port scanner.*
* **The window (first version, untested on a person's computer yet).** `/usr/bin/python3 -m voice_studio.window` opens one window with the project's training rounds, the voice file and Free up space. It needs the system Python (the one Ubuntu's `python3-gi` belongs to; a virtual environment's Python cannot see GTK) and a desktop (on WSL, graphical Linux programs). It is only a front for the same commands the terminal runs: every change is shown and asked about first, and the window writes no file of its own and opens no network connection or web address (a test reads its source for this). `--check` says why it cannot start. `--install-launcher` puts the window in the menu, after showing exactly what it will write and asking. On a Linux desktop it writes two small files, a menu entry and its icon, under `~/.local/share`. On WSL, whose Start menu is made from system folders that only an administrator can write to, it makes one shortcut in the person's **own Windows Start menu folder** and one small icon file under their Windows application data (`ack-voice-studio`), through `powershell.exe`, which WSL lets Linux start: no `sudo`, no password and no administrator rights. It runs three fixed commands (look, make, remove) passed on the command line as an encoded command; it changes no execution policy, writes no script file, uses no network and starts no other program, and a test reads the commands for all of that. If an organisation's policy blocks Windows programs from WSL, or blocks COM objects in PowerShell, the tool says it cannot reach the Start menu and prints the older steps instead (two `sudo` commands for the person to run themselves; the tool never runs `sudo`). `--remove-launcher` removes only a shortcut, an icon and files that carry this tool's own marker; one of the same name that someone else made is left alone. Nothing starts at login and nothing runs in the background when the window is closed.
* **The one exception, optional and separate:** *Freeform Studio*, the web tool for recording and reviewing in a browser, listens on `127.0.0.1` port 8001 by default (this
  computer only). Its helper script `start.sh` starts it on **`0.0.0.0` (the local network)**, over HTTPS when a certificate is provided and with a private token, so that a phone's browser can record. Voice Studio
  does not start it, and the ACK phone app records without any network. If your policy forbids a listening service, simply do not approve that use.

## 8. How the downloads are protected (for a security reviewer)

* **Every file the tool downloads is pinned** to a commit, a size and a SHA-256 in `tools/voice_studio/data/sources.json`. A file that does not match is never used (a wrong checksum deletes it).
  Addresses must be HTTPS on an allowed host (`huggingface.co`, `github.com`) and a redirect must stay on HTTPS.
* **The pinned files** (all from `huggingface.co`):

| Address (pinned to one commit) | Size (bytes) | SHA-256 |
|---|---|---|
| `https://huggingface.co/Systran/faster-whisper-small.en/resolve/d1d751a5f8271d482d14ca55d9e2deeebbae577f/config.json` | 2657 | `666a9605530ac1f61fa8177f3702b4dacec9966749e42610839fcc32661d5fae` |
| `https://huggingface.co/Systran/faster-whisper-small.en/resolve/d1d751a5f8271d482d14ca55d9e2deeebbae577f/model.bin` | 483545366 | `62b2a45b05ee59acb4a5341b33ee35e041395d378d418a18acfe4c9e768ee37a` |
| `https://huggingface.co/Systran/faster-whisper-small.en/resolve/d1d751a5f8271d482d14ca55d9e2deeebbae577f/tokenizer.json` | 2128466 | `929c5252409436dce1b38a75d1abbcb5e132d170d8e324e4e04ed915fa2d22df` |
| `https://huggingface.co/Systran/faster-whisper-small.en/resolve/d1d751a5f8271d482d14ca55d9e2deeebbae577f/vocabulary.txt` | 422309 | `ff77588746d3a2595d32ab5b69ffd7b95ce2441ac57533cb66fc3eb575a115cf` |
| `https://huggingface.co/datasets/rhasspy/piper-checkpoints/resolve/37d1bea250e21ca0d617818d2bef1db724edb80c/en/en_US/mike/medium/epoch=5460-val_mos=4.2686.ckpt` | 845891981 | `9a8389c2d733f94e2acc3b4e8264b4ba3c063612217780e4be21c0ccaff18b9b` |
| `https://huggingface.co/datasets/rhasspy/piper-checkpoints/resolve/37d1bea250e21ca0d617818d2bef1db724edb80c/en/en_US/amy/medium/epoch=6679-step=1554200.ckpt` | 845898392 | `6573ebd94b0610555ef34a1684cb89cae86ab9a7372d16f74bab35932879ef5a` |

* **Python packages are installed from a hash-checked list** (`--require-hashes`), wheels only, no dependency resolution at install time, no build scripts from the internet.
  The training list has **91** packages and the studio list **44**. **15** of the training packages are NVIDIA's CUDA libraries, under NVIDIA's own (proprietary) licences; the studio list has none.
* **Nothing downloads without a yes by name.** Each environment and each file is on the list the person agrees to, and the downloader refuses anything the list does not cover.
* **Tested:** the whole test suite runs without a network, including a real `pip` against a local server that cuts, resets, stalls, refuses and lies, and the downloader
  against the real host (the speech model and a voice, size and checksum verified).

## 9. Data handling

* Recordings, transcripts, edits, training data and the trained voice **stay on devices the person controls.** Nothing is uploaded, and there is no account.
* The ACK phone app has **no network permission** and its cloud backup is switched off; recordings leave it only when the person saves a file with the system file picker.
* The data folder is in the Linux home directory (under WSL, inside the Linux disk image), not in a OneDrive or other synchronised Windows folder. Back it up the way you
  back up any user data; the tool never deletes a recording by itself.

## 10. Licences: for whoever handles them (this is not legal advice)

* The tool is **GPL-3.0-or-later**. The full list of outside code and data, with each licence and *how it was checked*, is `THIRD_PARTY_NOTICES.md`.
* **The listening model** (`Systran/faster-whisper-small.en`) is MIT, as its repository states.
* **The starting voices** (Mike and Amy) are checkpoints that were themselves fine-tuned from a third voice (lessac), trained on the **Blizzard 2013** data. Mike's dataset is
  stated to be CC0. **Amy's dataset licence is not established** by what was read. The Blizzard 2013 data is distributed under a *research-only* agreement that excludes commercial use,
  does not allow sub-licensing and names the person or organisation it is granted to. **Whether any of that reaches a voice trained from it is not settled here.** The tool is designed to show the person this chain and ask for
  their acknowledgment before each voice is fetched. Today that is the terminal command `python3 -m voice_studio.voices get`; the window's screen for it is not built yet.
  The rules behind that screen are built and tested: a voice is not downloaded until the person's project has recorded the acknowledgment (with its date and the exact file's revision) **and** this
  computer has a saved yes to that one download; a changed file asks again. The pages the screen will point to are `https://github.com/OHF-Voice/voice-datasets` (Mike's recordings),
  `https://github.com/MycroftAI/mimic3-voices` (Amy's) and `https://www.cstr.ed.ac.uk/projects/blizzard/2013/lessac_blizzard2013/license.html` (lessac and the Blizzard 2013 data). They were read on 2026-10-11;
  the tool only shows these addresses and never opens them. The project hosts, mirrors and sublicenses none of it. **Nothing in this project says or implies that use is permitted.**
* The training programs include NVIDIA's CUDA libraries (15 packages) under NVIDIA's licences.

## 11. What was tested and what was not

| Tested | Not yet |
|---|---|
| Set-up, training, resume, stop with Ctrl+C, export and packing, on Ubuntu 22.04 and 24.04 under WSL2 with an RTX 4060 | Native Ubuntu (no WSL); a second person; any other graphics card |
| A dropped connection during the download (Wi-Fi switched off) | A proxy, TLS inspection, or an internal package mirror |
| The downloader and the pins, against the real hosts | A training round with the network cut off completely |
| That the voice zip imports into the phone app | Port-scanning the running programs |
| The `projects` and `voices` terminal commands: in the sandbox with a stand-in network, and on a real Ubuntu 22.04 computer including the real download of a starting voice (the developer's report; its logs were not sent) | The same commands on Ubuntu 24.04 and on a computer that is not the developer's |
| Training rounds (`python3 -m voice_studio.rounds`): the record, the chosen round, going back, what is kept, starting and ending a round through real detached jobs with a stand-in trainer; what `free` offers and removes, against files written the way a round leaves them | The same commands with the real trainer and the graphics card (checklist section I2), whether the tool's check that a saved file is whole is right about real files, and `free` on real rounds (section I3) |
| The voice file from the chosen round (`python3 -m voice_studio.voicefile`): the plan, the refusals, the five steps in one new folder, and what is left when one fails, with stand-ins for the export and the patcher that write what they write | The same command with the real export and patcher on a real round's saved file (checklist section I4), and the zip on the phone (section K) |

## 12. Removing it

Delete `~/ack-voice-studio/` (the recordings in `projects/` are the person's own: **copy them out first**) and `~/.cache/pip`. The Ubuntu packages in section 4 are ordinary
packages and can be removed with `apt`. Nothing else is installed.

## 13. Who to ask

The project and its issue tracker: `https://github.com/ASPDesignLabs/ACK`. The longer technical record is `docs/VOICE_STUDIO_SETUP_PLAN.md`, and the privacy statement is `docs/DATA_SOVEREIGNTY.md`.
