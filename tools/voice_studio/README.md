# ACK Voice Studio

A guided, graphical way to record, train and export a custom voice for ACK, on Ubuntu LTS (22.04, 24.04) and on Windows through WSL. One command sets it up
and opens a native window (GTK 4) that walks a helper and a person through bringing in recordings, training and sending the finished voice to a phone.

**Status.** The window exists (projects, recordings, training rounds, the voice file, freeing up space, display) and every step is also a terminal command. It has been run on one
computer (Windows with WSL2, Ubuntu 22.04 and 24.04, an RTX 4060). The installation guides are the place to start:

- **Windows, with only PowerShell:** [`docs/ACK_Voice_Studio_Installation_Guide.MD`](../../docs/ACK_Voice_Studio_Installation_Guide.MD). One command (`install.ps1`) sets up WSL and Ubuntu if needed, then does the Ubuntu steps below, then opens the window.
- **Ubuntu:** [`docs/ACK_Voice_Studio_Installation_Guide_Ubuntu.MD`](../../docs/ACK_Voice_Studio_Installation_Guide_Ubuntu.MD). One command (`get.sh`) fetches ACK, sets everything up and opens the window.

The plan, every decision behind it and what is built so far: [`docs/VOICE_STUDIO_SETUP_PLAN.md`](../../docs/VOICE_STUDIO_SETUP_PLAN.md).
Picking the work up: [`docs/VOICE_STUDIO_HANDOFF.md`](../../docs/VOICE_STUDIO_HANDOFF.md) says where it stands and what is asked next.

## Getting started (Ubuntu 22.04 or 24.04, native or under WSL)

On Windows, `install.ps1` does the Windows part and then runs the Ubuntu command below inside Ubuntu (see the Windows guide). On Ubuntu, one command does everything and ends at the window:

```bash
curl -fsSL https://raw.githubusercontent.com/ASPDesignLabs/ACK/main/tools/voice_studio/get.sh | bash
```

`get.sh` installs git (after asking), fetches ACK into `~/ack-tools` (or `ACK_VOICE_DIR`) at the release in `ACK_VOICE_TAG` (default `main`), and runs `setup.sh`. It never changes a folder that is
already there except to bring an out-of-date copy of ACK up to date (`git pull --ff-only`, only after you say yes), and never edits your shell settings. The only password prompt is Ubuntu's own `sudo`, in your terminal; this program never sees it. If you already have ACK's files:

```bash
./tools/voice_studio/setup.sh              # packages, then the two sets of programs, then the window; each step asks first
./tools/voice_studio/setup.sh --check      # only look; exit 0 when ready, 1 when something needs fixing
./tools/voice_studio/setup.sh --dry-run    # show the exact commands that would run; change nothing
./tools/voice_studio/setup.sh --yes        # you have already said yes, so do not ask
./tools/voice_studio/setup.sh --no-window  # set the programs up but do not open the window
```

The steps after the Ubuntu packages are `core/guided_flow.py`: the small programs (listen to recordings, make training sets), the large ones (training), then the window. A no to one set does not stop the
next; a failure stops everything after it, because the window would open on programs that are not there. Running the command again carries on from where it stopped.

Each set of programs can also be set up on its own from a terminal (it asks once before it downloads anything, from the package site only):

```bash
PYTHONPATH=tools python3 -m voice_studio.buildenv training --check    # only look; exit 0 when ready, 1 when not
PYTHONPATH=tools python3 -m voice_studio.buildenv training            # show what it will do, ask once, build it (about 10 GB free is needed)
```

If the internet connection drops while it downloads, it says so, waits, and carries on by itself when the connection is back (it keeps trying for 30 minutes; Ctrl+C stops it).
If it still has to stop, or you stop it, run the same command again: it carries on from where it stopped and does not ask the same question twice
(`core/connection.py` has the rules; it was measured against real pip, not guessed).

Projects, starting voices and training rounds, recordings and the voice file can all be run from a terminal too. Anything you leave out is asked one question at a time, and nothing is made or changed without a yes:

```bash
PYTHONPATH=tools python3 -m voice_studio.projects list                       # the projects there are
PYTHONPATH=tools python3 -m voice_studio.projects new --own --name "Anna"    # make one (shows it first, then asks)
PYTHONPATH=tools python3 -m voice_studio.projects edit anna --hours 2        # change its details (shows what changes, then asks); also: archive / unarchive (hide and bring back, nothing removed)
PYTHONPATH=tools python3 -m voice_studio.projects delete anna                # delete one for good: lists what goes, then asks TWICE (--yes never answers the second question)
PYTHONPATH=tools python3 -m voice_studio.recordings show --project anna      # what is in the project, what the computer is doing, what to do next; changes nothing
PYTHONPATH=tools python3 -m voice_studio.recordings import ~/voice-files --kind pairs --project anna   # bring in audio files, each with a text file (shows what it found, then asks); kinds: package, pairs, table, audio
PYTHONPATH=tools python3 -m voice_studio.recordings model                      # get the listening model (about 485 MB; shows where it comes from and asks first; nothing else downloads it)
PYTHONPATH=tools python3 -m voice_studio.recordings finish --project anna    # let the computer listen to what was brought in (a job of its own; asks first)
PYTHONPATH=tools python3 -m voice_studio.recordings set --project anna       # make a training set from what was heard (--preview only shows what it would hold; asks first)
PYTHONPATH=tools python3 -m voice_studio.voices show mike                    # where a starting voice comes from; changes nothing
PYTHONPATH=tools python3 -m voice_studio.voices get mike --project anna      # confirm you read that, agree to the download, then download
PYTHONPATH=tools python3 -m voice_studio.rounds list --project anna          # the training rounds, which one is chosen; changes nothing
PYTHONPATH=tools python3 -m voice_studio.rounds free --project anna          # what could be freed up, with sizes; changes nothing (name rounds with --saved / --working to remove: it asks first)
PYTHONPATH=tools python3 -m voice_studio.rounds start --set dataset-1 --project anna    # one more round, from the chosen round (shows the plan, then asks)
PYTHONPATH=tools python3 -m voice_studio.voicefile make --project anna        # the voice file for ACK from the chosen round, in one new folder (shows the plan, then asks)
PYTHONPATH=tools /usr/bin/python3 -m voice_studio.window --check             # can the window start here? (needs the system Python: python3-gi, gir1.2-gtk-4.0)
PYTHONPATH=tools /usr/bin/python3 -m voice_studio.window                     # the window: projects, recordings, rounds, voice file, free up space; every change asks first
```

`get` keeps two things apart on purpose: **`--acknowledge`** (or answering `yes` to its first question) says you read where the voice comes from, and **`--yes`** (or its second `yes`) agrees to the download. Neither can stand in for the other.
Run either command with `help` to see all of it. `docs/VOICE_STUDIO_DEVICE_TEST.md` sections I1 (projects and voices), I2 (training rounds), I3 (freeing up space), I4 (the voice file), I5 (the window) and I6 (more than one project, and bringing in voice recordings you already have) walk through them. A round continues from the round you chose, never from the starting voice again by accident, and the commands that only look (`list`, `keep`) change nothing.

**For an IT department:** `docs/VOICE_STUDIO_IT_GUIDE.md` says what to allow (hosts, ports, packages, disk), what runs and what listens, how to install offline, and what has and has not been tested.

## Rules the code keeps

- `core/` is plain Python: no GUI toolkit, no network. The window will be a thin layer over it.
- It must run on Python 3.10 (Ubuntu 22.04). Nothing newer is used.
- The only module that may use the network is the download module, and only after the person has agreed to each download by name.
- Every source file carries `SPDX-License-Identifier: GPL-3.0-or-later`.

## Lock files (maintainers)

The environments the setup builds are installed from lock files in `data/locks/` (every package at an exact version, with checksums), and each lock's own checksum is in
`data/environments.json`. A lock is made with `tools/voice_studio_maint/make_lock.py` (outside this package on purpose: it reads the package site's public listing, so it needs a network, and
the app never runs it). Its header says which Pythons it covers; the environment's `python_min` and `python_max` must say the same. After making one, put its checksum into `environments.json`;
a test fails until the two agree. See `docs/VOICE_STUDIO_SETUP_PLAN.md`, finding F9 and task VS-0.2.

## Tests

```bash
./run_tests.sh              # needs pytest; the script says how to get it if it is missing
```
They need no network, GPU or display. Two optional libraries add checks, and without them those tests are **skipped, never failed**:

| Library | What the skipped tests check |
|---|---|
| `numpy` | importing an ACK package and reading the real output of Freeform Studio's processor and dataset builder (Freeform Studio itself needs numpy to run) |
| `onnx` | the voice zip's metadata reader against the real library and the real patcher (the reader is still tested on files built by hand) |
| `Cython` (with `numpy`, a C compiler and the Python headers) | the shipped alignment source compiles the way the environment builder compiles it, and gives the right answers |

To run everything: `pip install pytest numpy onnx Cython setuptools` in the throwaway environment above (and `sudo apt-get install build-essential python3-dev` if the compile test says it skipped). These are for testing only. Freeform Studio's own tests (`tools/freeform_studio/tests`) need what `tools/freeform_studio/requirements.txt` lists (its server tests fail, rather than skip, when `quart` is missing).
