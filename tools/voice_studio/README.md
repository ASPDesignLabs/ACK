# ACK Voice Studio

A guided, graphical way to record, train and export a custom voice for ACK, on Ubuntu LTS (22.04, 24.04) and on WSL. One command
sets it up; a native window (GTK 4) walks a helper and a person through recording, training and sending the finished voice to a phone.

**Status: foundations only.** Nothing here runs a window yet. The first terminal step exists: it looks at the computer, lists what is missing, asks once
and installs it. The plan, every decision behind it and what is built so far:
[`docs/VOICE_STUDIO_SETUP_PLAN.md`](../../docs/VOICE_STUDIO_SETUP_PLAN.md).

## Getting started (Ubuntu 22.04 or 24.04, native or under WSL)

If you already have ACK's files:

```bash
./tools/voice_studio/setup.sh              # look at this computer, list what is missing, ask once, install it
./tools/voice_studio/setup.sh --check      # only look; exit 0 when ready, 1 when something needs fixing
./tools/voice_studio/setup.sh --dry-run    # show the exact commands that would run; change nothing
./tools/voice_studio/setup.sh --yes        # you have already said yes, so do not ask
```

If you have neither git nor ACK's files, `get.sh` installs git (after asking), fetches one named release of ACK into `~/ack-tools` (or `ACK_VOICE_DIR`), and
starts the step above. It needs `ACK_VOICE_TAG` set to a release name; there are no releases of this tool yet, so there is nothing to run it against.
It never touches a folder that is already there and never edits your shell settings. The only password prompt is Ubuntu's own `sudo`, in your terminal;
this program never sees it.

Until the window exists, the training programs are set up from a terminal (it asks once before it downloads anything, from the package site only):

```bash
PYTHONPATH=tools python3 -m voice_studio.buildenv training --check    # only look; exit 0 when ready, 1 when not
PYTHONPATH=tools python3 -m voice_studio.buildenv training            # show what it will do, ask once, build it (about 10 GB free is needed)
```

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
