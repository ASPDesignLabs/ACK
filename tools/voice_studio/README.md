# ACK Voice Studio

A guided, graphical way to record, train and export a custom voice for ACK, on Ubuntu LTS (22.04, 24.04) and on WSL. One command
sets it up; a native window (GTK 4) walks a helper and a person through recording, training and sending the finished voice to a phone.

**Status: foundations only.** Nothing here runs a window yet. The plan, every decision behind it and what is built so far:
[`docs/VOICE_STUDIO_SETUP_PLAN.md`](../../docs/VOICE_STUDIO_SETUP_PLAN.md).

## Rules the code keeps

- `core/` is plain Python: no GUI toolkit, no network. The window will be a thin layer over it.
- It must run on Python 3.10 (Ubuntu 22.04). Nothing newer is used.
- The only module that may use the network is the download module, and only after the person has agreed to each download by name.
- Every source file carries `SPDX-License-Identifier: GPL-3.0-or-later`.

## Tests

```bash
./run_tests.sh              # needs pytest; the script says how to get it if it is missing
```
They need no network, GPU or display.
