# ACK VOICE STUDIO: checking the first slice on your own computers (terminal only)

Everything in ACK Voice Studio's first slice was written and tested **without** the things that matter most in the end: a real graphics card,
a real WSL, a real phone, and a real training run. Most of this list uses the terminal; the window is checked in sections I5 to I7. It follows the path a voice takes:
**recordings from the phone → this computer → a training set → one short training round → a voice file → ACK on the phone.** Each
line is *do this → expect that*. If something does not match, the last section says what to send back.

Take your time; none of it is timed, and you can stop at any line. Nothing here changes anything you already have. Everything this list
makes goes into two folders, **`~/ack-voice-check`** and **`~/piper/voice-check`**; the only deleting step is the last one, and it says so.
Where a step could take a while or use the graphics card, it says that first.

**Do it twice if you can: once on Ubuntu itself and once under WSL.** Write down any line that differs between them; the differences are what
the window will have to handle.

The folders and names used below (change them if yours differ):

| What | Where |
|---|---|
| This tool's files (a checkout of the branch `claude/voice-studio-guided-setup`: **section 0**) | `~/ack-tools` |
| Freeform Studio's environment (from its own `install.sh`) | `~/freeform-studio-venv` |
| The training programs (built by the tool in section I0; the hand-built `~/piper1-gpl` is not used) | `~/ack-voice-studio/tool/environments/training-…` |
| The starting voice's checkpoint (a download from the training guide) | `~/piper/checkpoints/mike.ckpt` (or the file you have there) |
| Recordings folder used by this list | `~/ack-voice-check/recordings` |

**Contents.** Every section of this list, in the order they are written. A section says when it needs an earlier one.

| Section | Title | In a few words |
|---|---|---|
| 0 | Get this branch (a clone of the main branch does not have this tool) | Make sure your copy of the tool has the tool in it. |
| A | Write down the computer first | Note which Ubuntu, kernel and Python you are on. |
| B | The tool's own tests, on your Python | Run the tool's own tests once on your computer. |
| C | The first terminal step | Ask the setup script to look. It changes nothing. |
| D | A job that outlives its terminal | Start a job, close every terminal, and see that it kept going. |
| E | The speech model and the first recognition | Fetch the listening model (asks first) and try it on a recording. |
| F | Bringing in a package from the phone | Bring in a recording package that ACK saved on the phone. |
| G | Finishing the recordings (listening to them) | Let the computer write down what it hears in the recordings. |
| H | The training set | Build the training set from the recordings that are ready. |
| I0 | Set up the training programs with the tool (before the round) | Let the tool build the training programs, after it asks. |
| I1 | Make a project and get a starting voice with the tool | Make a project and fetch a starting voice, one step at a time. |
| I | One short training round, on the graphics card | Run one short round on the graphics card and write down the numbers. |
| I2 | Training rounds with the tool | Run rounds with the tool, each continuing from the one you chose. |
| I3 | Freeing up space | Free the space old rounds use, slowly: the one section that removes files you made. |
| I4 | Making the voice file with one command | Make the zip that ACK takes, from the round you chose. |
| I5 | The window (WSL only for now) | Try the first window. |
| I6 | More than one project, and bringing in voice recordings you already have (terminal first, then the window) | Keep several projects and bring in recordings you already have. |
| I7 | Installing from scratch, with the two installation guides | Follow the installation guides on a computer with nothing set up. |
| I8 | Hearing the voice before it goes to the phone | Play three sentences in the finished voice on this computer. |
| I9 | Backing up a project | Back a project up, check the backup, and put it back. |
| I10 | Checking the tool, and refreshing it | Look at the tool's own programs and mend or rebuild them. |
| I11 | Removing the tool's programs and downloads | Take the tool's programs and downloads off the disk and keep your own work. |
| I12 | Moving a project's scratch to another place | Move a project's working files to another place. |
| I13 | Updating the tool | Look for newer releases and fetch one beside this copy. |
| I14 | The problem report | Make a report a helper can read. |
| I15 | The window's pages for hearing, backup, checking, updates and problem reports | Press every button on the five pages that came after the first six, and answer what they ask. |
| I16 | Giving the voice file to the phone over Wi-Fi | Put a certificate on the phone once, then send the voice file over the home network. |
| I17 | Ubuntu under Windows: the phone and the idle stop | Keep Ubuntu running when the last window closes, and let a phone reach it. |
| I18 | The Windows setup program | Start from one file you double-click: no terminal; an Ubuntu account and password asked in a window. |
| J | Making the voice file | The same as I4, done by hand. |
| K | On the phone | Put the voice on the phone and hear it in ACK. |
| L | What to send back | What to write down and send back. |
| M | Clean up (only the folders this list made) | Remove what this list made, and only that. |

## 0. Get this branch (a clone of the main branch does not have this tool)

Voice Studio is only on the branch `claude/voice-studio-guided-setup` until it is merged. A `~/ack-tools` you made from the main branch (the Freeform Studio
install steps do that) has no `tools/voice_studio` folder, and the first command in section B then says "No such file or directory". Start every section in
your own home folder (`cd ~`), not in a Windows folder under `/mnt/c`: it is much faster there, and the paths below assume it.

- [ ] Look first. These only read:
  ```bash
  cd ~
  git -C ~/ack-tools branch --show-current
  ls ~/ack-tools/tools/voice_studio/run_tests.sh
  ```
  → On the right branch: the branch name `claude/voice-studio-guided-setup` and the file name printed. On a clone of main: `main`, then "No such file or directory".
- [ ] If it is not the right branch, **move the old folder aside (it keeps everything, and your Freeform Studio install in `~/freeform-studio-venv` does not live in
  it), then clone this branch.** This is the same advice Freeform Studio's own README gives for a clone from another branch:
  ```bash
  mv ~/ack-tools ~/ack-tools.old
  git clone --branch claude/voice-studio-guided-setup https://github.com/ASPDesignLabs/ACK.git ~/ack-tools
  ls ~/ack-tools/tools/voice_studio/run_tests.sh
  ```
  → The last line prints the file's name. If `mv` says `~/ack-tools.old` exists, choose another name; nothing is replaced. If you had changed files inside the old
  folder, they are still in `~/ack-tools.old`.

## A. Write down the computer first

- [ ] Run these and keep the output with your notes:
  ```bash
  lsb_release -d; uname -r; python3 --version
  grep -qi microsoft /proc/version && echo "this is WSL" || echo "this is not WSL"
  nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv
  df -h ~
  ```
  → One line each. `nvidia-smi` is the only one that may fail (no card, or no driver in WSL): note which.

## B. The tool's own tests, on your Python

The tests have only been run on Python 3.11 to 3.13. Ubuntu 22.04 ships 3.10, which is the lowest this tool promises to work on, so this
is the first time the whole suite meets it.

- [ ] Make a throwaway environment and run the tests:
  ```bash
  python3 -m venv ~/voice-studio-test-venv
  ~/voice-studio-test-venv/bin/pip install pytest numpy onnx
  cd ~/ack-tools && PYTHON=~/voice-studio-test-venv/bin/python ./tools/voice_studio/run_tests.sh
  ```
  → Ends with a line of passes and no failures. A few tests build real virtual environments, so it takes about a minute; it needs no network
  except for `pip install` above. **On Python 3.10, any failure is a finding**: send back the first red line.

## C. The first terminal step

- [ ] `~/ack-tools/tools/voice_studio/setup.sh --check`. → It looks and prints what is fine, what needs fixing (`[FIX]`) and what is only
  worth knowing (`[note]`). Nothing is changed. The exit code (`echo $?`) is 0 only when nothing needs fixing.
  - On **Ubuntu with its desktop**: no line about a missing desktop.
  - On **WSL with a window system (WSLg)**: the same. On WSL without one, a `[FIX]` says there is no desktop. Write down which you have.
  - With **no graphics card or driver**: a `[note]` that training is switched off. With one: no such note.
- [ ] `~/ack-tools/tools/voice_studio/setup.sh --dry-run`. → The exact commands it would run, if any, and the words "Nothing was changed".
- [ ] `sudo ~/ack-tools/tools/voice_studio/setup.sh --check`. → A `[FIX]` says it was started with administrator rights and to start it
  again as your normal user. Nothing is changed.
- [ ] If anything was missing: `~/ack-tools/tools/voice_studio/setup.sh`, then say **no** when it asks. → Nothing is installed.
  Run it again and say **yes**: the only password prompt is Ubuntu's own `sudo` in this terminal, and afterwards `--check` is clean.

## D. A job that outlives its terminal

The window will start long jobs (training, listening to recordings) so that closing the window does not stop them. This is the part that
may behave differently under WSL, so **do it on both**. The job here only prints a line and waits; it uses no graphics card.

- [ ] Start it:
  <!-- snippet: jobs-start -->
  ```bash
  PYTHONPATH=~/ack-tools/tools python3 - <<'EOF'
  import os, sys
  from voice_studio.core import jobs

  root = os.path.expanduser("~/ack-voice-check/jobs")
  code = "import time\nprint('hello from the check job', flush=True)\nfor i in range(600):\n    time.sleep(1)\n"
  info = jobs.start_job(root, jobs.JobSpec("check", "", (sys.executable, "-c", code)))
  print("started", info.id, info.status.value, "runner", info.runner_pid)
  EOF
  ```
  → One line: `started …-check-… running runner <number>`.
- [ ] Look at it:
  <!-- snippet: jobs-list -->
  ```bash
  PYTHONPATH=~/ack-tools/tools python3 - <<'EOF'
  import os
  from voice_studio.core import jobs

  for j in jobs.list_jobs(os.path.expanduser("~/ack-voice-check/jobs")).jobs:
      print(j.id, j.status.value, "exit", j.exit_code)
      for line in jobs.tail_log(j.dir, 3):
          print("   log:", line)
  EOF
  ```
  → `running`, and the log line `hello from the check job`.
- [ ] **Close this terminal window completely** (on WSL: the whole Windows Terminal window, not just a tab). Wait **one minute**. Open a new
  terminal and run the "look at it" step again. → Still `running`. **This is the finding that matters here:** if it says `interrupted`, or
  the runner is gone, WSL stopped the job when the last terminal closed. Write down your Windows and WSL versions
  (`wsl.exe --version` in PowerShell) and whether anything else was open.
- [ ] **If it said `interrupted`:** find out whether WSL stopped its whole virtual machine or only killed the job. These only read (put your Windows user name where
  `<you>` is; the last one may say there is no such file, which is an answer too):
  ```bash
  cat ~/ack-voice-check/jobs/*-check-*/runner.json
  cat /proc/sys/kernel/random/boot_id
  uptime -s
  ps -p 1 -o comm=
  cat /etc/wsl.conf
  cat /mnt/c/Users/<you>/.wslconfig
  ```
  → `runner.json` holds the `boot_id` the job started under. **If it differs from the current one, WSL stopped its whole virtual machine** (every process, without a
  warning); if it is the same, only the job was killed. `uptime -s` is when this WSL started; `ps -p 1` says `systemd` or `init`. Keep all of it with your notes.
- [ ] **Known result on the developer's machine** (WSL 2.7.14.0): the journal says `System is powering down` about a minute after the last terminal closes, with the same `boot_id` (only
  the Ubuntu instance stops). Look for the same on yours: `journalctl -b --no-pager | grep -iE "powering down|new session"` and compare the times with when you closed the windows.
- [ ] **Does `instanceIdleTimeout` stop it?** This edits a Windows file and restarts WSL, so make sure **no job is running** and nothing in Ubuntu is unsaved. Keep a copy, add the setting,
  restart WSL, and try again:
  ```bash
  cp -n /mnt/c/Users/<you>/.wslconfig /mnt/c/Users/<you>/.wslconfig.bak
  printf '\n[general]\ninstanceIdleTimeout=-1\n' >> /mnt/c/Users/<you>/.wslconfig
  cat /mnt/c/Users/<you>/.wslconfig
  ```
  Then in PowerShell: `wsl.exe --shutdown`. Open Ubuntu, start a check job, close **every** window, wait three minutes, open a new one and look. → `running` means this setting holds the
  instance up. **On the developer's machine (WSL 2.7.14.0) it did**: still `running` after more than five minutes with every window closed. (If WSL printed a complaint about the file when it started, send it to me.) **To undo it:** put the copy back with `cp /mnt/c/Users/<you>/.wslconfig.bak /mnt/c/Users/<you>/.wslconfig`
  and run `wsl.exe --shutdown` again.
- [ ] **Can Ubuntu start Windows programs?** `cmd.exe /c ver` → a Windows version line. On the developer's machine it first said `cannot execute binary file: Exec format error` (which also breaks
  `explorer.exe`, and `ls /proc/sys/fs/binfmt_misc/` lacked `WSLInterop`) and, after `wsl.exe --shutdown` and a restart, worked: **it is intermittent**. Write down what yours says, and try again after a restart.
- [ ] **Does a session you leave open keep jobs alive?** (Only if it said `interrupted`.) Start a new check job. In PowerShell run `wsl.exe -l -v` and note the distribution's
  name, then `wsl.exe -d <name> --exec sleep infinity` and **leave that PowerShell window open**. Close every Ubuntu terminal window, wait a minute, open a new one and look
  again. → `running` means a session held open from Windows keeps jobs alive. Ask the job to stop (next step) **before** you close the PowerShell window.
- [ ] Ask it to stop, then look again after a few seconds:
  <!-- snippet: jobs-stop -->
  ```bash
  PYTHONPATH=~/ack-tools/tools python3 - <<'EOF'
  import os
  from voice_studio.core import jobs

  for j in jobs.list_jobs(os.path.expanduser("~/ack-voice-check/jobs")).jobs:
      if j.status in jobs.ACTIVE:
          print(j.id, jobs.request_stop(j.dir))
  EOF
  ```
  → `asked`, and a few seconds later the "look at it" step says `stopped`.
- [ ] **Restart the computer** (or, on WSL, `wsl.exe --shutdown` from PowerShell) while a *new* check job is running, then look again.
  → `interrupted`, not `running` and not an error. Then stop looking: nothing else to do for it.

## E. The speech model and the first recognition

Needs the internet once, only for the model, and asks first. About 480 MB.

- [ ] `cd ~/ack-tools/tools && source ~/freeform-studio-venv/bin/activate`
  then `python -m freeform_studio.models list`. → Says which models are on this computer (probably none). No network.
- [ ] `python -m freeform_studio.models fetch small.en`. → It says what it will download and from where, that nothing you recorded is sent,
  and **asks before doing anything**. Say no first, and check that nothing was downloaded (`models list` again). Then run it again and say yes.
- [ ] `python -m freeform_studio.asr_smoke ~/some-recording.m4a --model small.en --device cpu` (any 20 to 60 seconds of speech).
  → What was heard, how fast, and how it would be cut. Write down the seconds it took.
- [ ] With the network off if you can (turn Wi-Fi off, or unplug), run the last step again. → The same result. Nothing here needs the internet.

## F. Bringing in a package from the phone

On the phone, make a package with three or four cards: ACK → Audio Architect → Custom Voice → **RECORD TRAINING DATA**, read a few cards,
then save the package to a file (the steps are in `docs/TRAINING_CAPTURE_DEVICE_TEST.md`, sections D and I). Move the `.zip` to this
computer. On WSL a Windows folder works (`/mnt/c/Users/<you>/Downloads/…`); note whether the copy-in felt slow.

- [ ] Look first, with Freeform Studio's own command, writing nothing:
  `python -m freeform_studio.ack_import ~/Downloads/ack-training-….zip --output ~/ack-voice-check/recordings --dry-run`
  → The sessions, minutes, whether there is room, and "nothing was written". `ls ~/ack-voice-check` shows **no** `recordings` folder yet.
- [ ] Now the tool's own wrapper, which copies the package into the project first, checks the copy byte for byte, and **only adds when you put the word `add` at the end of the command**.
  Run it exactly as it is the first time (it only looks):
  <!-- snippet: package-summary -->
  ```bash
  source ~/freeform-studio-venv/bin/activate
  PYTHONPATH=~/ack-tools/tools python3 - ~/Downloads/ack-training-XXXX.zip ~/ack-voice-check/recordings <<'EOF'
  import sys
  from voice_studio.core import ackimport
  from voice_studio.core.text import load_catalog

  cat = load_catalog("en")
  try:
      prepared = ackimport.prepare(sys.argv[1], sys.argv[2])
  except ackimport.AckImportError as err:
      for part in ("what", "changed", "next"):
          print(cat.t("ackimport.error.%s.%s" % (err.code, part)))
      print("details:", err.code, err.detail)
      for line in err.problems:
          print("   -", line)
      sys.exit(1)
  s = prepared.summary
  print("copy kept at:", prepared.copy, "(new copy)" if prepared.copy_was_new else "(already there)")
  print("made by ACK", s.app_version, "on", s.created)
  for x in s.sessions:
      print("  session", x.id, x.mode, cat.t("ackimport.state." + x.state), "%.0f s" % x.seconds)
  print("to add:", s.to_add, "| new minutes: %.1f" % s.minutes_new, "| room: need %.0f MB, free %.0f MB" % (s.need_mb, s.free_mb))
  for note in s.warnings:
      print("  note:", note)
  adding = len(sys.argv) > 3 and sys.argv[3] == "add"
  if not s.to_add:
      print("Nothing to add: everything in this package is already in.")
  elif not s.enough_room:
      print("There is not enough room, so nothing was added.")
  elif adding:
      for made in ackimport.add(prepared):
          print("  added", made.take_id)
  else:
      print("Nothing was added. To add them, run this again with the word add at the end.")
  EOF
  ```
  → The sessions and minutes match what you recorded; then "Nothing was added." The copy is kept in
  `~/ack-voice-check/recordings/_freeform/en-US/incoming/`, and `ls ~/ack-voice-check/recordings/_freeform/en-US/takes` shows nothing.
- [ ] Run it again with `add` after the recordings folder (`… ~/ack-voice-check/recordings add`). → "added …" once per session. Run it a third time, still with `add`. →
  The sessions now read "Already added", it says there is nothing to add, and "to add: 0".
- [ ] **A damaged package must be refused in plain words, and leave nothing behind.** Make a copy and change one byte in the middle of it:
  <!-- snippet: flip-a-byte -->
  ```bash
  cp ~/Downloads/ack-training-XXXX.zip ~/ack-voice-check/damaged.zip
  python3 - <<'EOF'
  import os
  p = os.path.expanduser("~/ack-voice-check/damaged.zip")
  data = bytearray(open(p, "rb").read())
  data[len(data) // 2] ^= 1
  open(p, "wb").write(data)
  EOF
  ```
  Run the wrapper above on `~/ack-voice-check/damaged.zip`. → Three plain sentences ("This file is not a complete ACK package…",
  "Nothing was added…", "Copy the file from the phone again…") and the exit code 1. `ls …/incoming/` has **no** `damaged.zip` in it, and the
  original in Downloads is unchanged (`ls -l`, same size and date).

## G. Finishing the recordings (listening to them)

Uses the processor, with no browser and no server. On the computer's own processor, not the graphics card.

- [ ] `python -m freeform_studio.process --output ~/ack-voice-check/recordings --asr-model /nowhere`; then `echo $?`. → A plain sentence
  that the folder does not exist, **exit code 3**, and nothing started (`take.json` in each take still says `finishing`).
- [ ] `python -m freeform_studio.process --output ~/ack-voice-check/recordings`. → One line per recording as it changes, then
  "Finished N recording(s).", exit code 0. Write down how long it took for how many minutes of speech.
- [ ] Run it again. → "Nothing is waiting", exit code 0, and nothing in the takes folder changes.
- [ ] `python -m freeform_studio.process --output ~/ack-voice-check/recordings --json` on a fresh import, if you have one. → Each line
  is a JSON object; the last has `"done": true`.

## H. The training set

Each build needs a folder name that does not exist yet: the tool never overwrites one. If you build more than once (for example after changing `--max-gain-db`), use `dataset-2`, `dataset-3`
and so on, and use the one you built last in section I (its commands say `dataset-1`).

- [ ] `python -m freeform_studio.build_dataset --output ~/ack-voice-check/recordings --out ~/ack-voice-check/dataset-1 --dry-run`. →
  A report with what would go in, what would be left out and why. `ls ~/ack-voice-check` shows **no** `dataset-1`.
- [ ] The same without `--dry-run`. → `~/ack-voice-check/dataset-1/` holds `wav/`, `metadata.csv`, `manifest.json`, `excluded.txt`. A few
  cards are enough to check the plumbing; they are far too little for a good voice, and the advice about length will say so.
- [ ] **If every piece was left out as `quiet`** (a phone recording that sounds fine when you play it can still be far below full level): look at the levels first. This only reads:
  ```bash
  python3 - <<'EOF'
  import glob, json, os
  for path in sorted(glob.glob(os.path.expanduser("~/ack-voice-check/recordings/_freeform/en-US/takes/*/ack_checks.json"))):
      r = json.load(open(path))
      print(os.path.basename(os.path.dirname(path)), "room", r.get("noise_floor_dbfs"), "dBFS, speech threshold", r.get("threshold_dbfs"), "dBFS")
      for sid, p in r.get("pieces", {}).items():
          print("  ", sid, "peak", p.get("peak_dbfs"), "speech", p.get("speech_db"), "snr", p.get("snr_db"))
  EOF
  ```
  → The peak of each piece (full level is 0; the training set aims for -3), how loud the speech is, and how far above the room it is (`snr`; below 20 flags `noisy`, which stays left out).
  The gain needed is the distance from the peak to -3. Then preview with a limit that covers it, for example `… --dry-run --max-gain-db 36`. → A `LOUDNESS:` line says how far the clips were turned up, and a
  warning says if some are still softer than full level. Your recordings are not changed; the gain is applied to the copies in the training set.
- [ ] The same command again. → Refused, exit code 2, "never overwrites a dataset"; nothing in `dataset-1` changed.
- [ ] `… --json | python3 -m json.tool` (with `--dry-run`). → Valid JSON with `result`, `included`, `left_out`.

## I0. Set up the training programs with the tool (before the round)

The training programs are no longer built by hand. The tool builds them itself from a list of exact versions with checksums, from the package site only (no GitHub). **This is the first time
that has run on a real computer**, so write down everything that surprises you. It needs the packages from section C (`python3-venv`, `python3-dev`, `build-essential`) and about 10 GB free.
Run it in a terminal you keep open, not through a window that closes.

- [ ] Only look. This changes nothing and downloads nothing:
  ```bash
  PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.buildenv training --check; echo "exit code: $?"
  ```
  → `Now: Not set up yet.`, then `This is not ready.`, `exit code: 1`. (If it says some programs are missing, run `setup.sh` from section C again.)
- [ ] Set it up:
  ```bash
  PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.buildenv training
  ```
  → It says where it will put things, how much space it needs and how much is free, where the programs come from, that it includes Nvidia's libraries, and asks `Download and set it up now?`.
  Type `yes`. Then each step prints, with how long it took, and at the end `Ready, after …`. Write down: the total time, the time of **Installing the programs this part needs** and of
  **Building the part made for this computer**, and the folder it printed. Press **Ctrl+C once** during the install step if you want to check the stop (it says how to carry on; run the same command again and
  it should say `You already said yes to this, so it carries on from where it stopped and does not ask again.`, then that the finished steps are `already done`). If it fails, copy the message, **Technical detail** and the last lines it printed, and the end of `build.log` in the folder it named.
- [ ] Run the same command again. → `Nothing needs doing.`, no question, nothing downloaded.
- [ ] **A dropped connection (optional, but it is how real life goes).** Run the set-up again from scratch if you can (a new folder, or after the step above is ready, pick the studio programs instead: `buildenv studio`), and while it is
  downloading turn the Wi-Fi off, or pull the cable, for about a minute, then turn it back on. Type nothing. → `The internet connection stopped. Nothing is lost and you do not need to do anything. It will try again in 5 seconds, and keep trying
  for up to 30 minutes. To stop, press Ctrl+C.`, then every so often `Still no connection. Trying again in … seconds. It has been away for ….`, and once it is back `The connection is back. Carrying on.` and the build goes on to
  `Ready` with nothing typed. Write down: how long the connection was away, and whether it carried on by itself. If you keep it off for more than 30 minutes: `The internet connection did not come back in time, so this stopped.`; turn it
  back on and run the same command again → `You already said yes to this, so it carries on …` and it finishes, with no question.
- [ ] Look inside (this only reads):
  ```bash
  TRAIN=$(ls -d ~/ack-voice-studio/tool/environments/training-* | head -1); echo "$TRAIN"
  ls "$TRAIN"; du -sh "$TRAIN"
  "$TRAIN/venv/bin/python" -c "import piper.train.vits.monotonic_align as m; print(m.__file__)"
  ```
  If the third command says `venv/bin/python: No such file or directory`, the environment's own Python link points at something that was deleted (on Python 3.10 an environment built while another
  one is active is linked to *that* one; found on a real 22.04). Update the tool (`git pull`) and run `buildenv training` again with no options: it finds the broken links, replaces only those, keeps the installed packages and finishes without downloading them again.
  → The folder holds `venv`, `ack_run.py`, `ack-env.json`, `lock.txt` and `build.log` (no `native-work`, no `source`). Its size is what to write down (the tool assumed 6.1 GiB installed). The last line is a path
  ending in `…/piper/train/vits/monotonic_align/__init__.py`, with no error.
- [ ] Check the card is seen: `"$TRAIN/venv/bin/python" -c "import torch; print(torch.cuda.is_available(), torch.version.cuda)"`. → `True 13.0` (or the CUDA version the lock names).

## I1. Make a project and get a starting voice with the tool

**New, and not yet run on a real computer.** This is how the window will make a person's project and fetch a starting voice, done from the terminal: read where the voice comes from, confirm that
you read it, agree to the download, and only then download. Two things are kept apart on purpose: **`--acknowledge`** (or typing `yes` to the first question) says you read the notes, and **`--yes`** (or
typing `yes` to the second) agrees to the download. Neither can stand in for the other. Nothing here deletes anything, and every step that changes a file asks first and keeps the earlier project file as
`project.json.previous`. You need about 1 GB free beyond the 846 MB. Run one command at a time, and wait for it to finish before you type the next.

- [ ] Look at what exists. This changes nothing:
  ```bash
  PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.projects list
  ```
  → `There are no projects yet.` and the command to make one (or a line for each project you already have).
- [ ] Make a project for this check. It asks one question for what you did not give:
  ```bash
  PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.projects new --own --name "Voice check" --voice mike
  ```
  → `About how many hours of recording do you expect? Press Enter for 1.` (press **Enter**). Then the whole project it would make (its name, its folder, the hours, the starting voice), how much room the whole plan needs against what is free,
  and `Make this project? Type yes to make it.` Type **`no`**: `Nothing was made.`, and `ls ~/ack-voice-studio/projects` shows no new folder. Run the same command again and type **`yes`**: `Made the project voice-check.`
  (If you would rather paste one line and have nobody asked, add `--yes` to the end.)
- [ ] Look at the project: `PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.projects show`. → `Using the only project: voice-check.`, its folder, `Starting voice: voice-mike`, and `No starting voice has been acknowledged yet.`
- [ ] **Read the notes. This changes nothing and downloads nothing:**
  ```bash
  PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.voices show mike
  ```
  → The voice, then where it comes from (Mike, then the lessac voice behind it), the address of the page to read for each, the date the pages were read, `This project gives no legal advice. Whether your use is allowed is for you to decide.`
  and that this project does not host the voice. **Read it as the person it is for would, and write down:** any sentence that is hard to follow, any that sounds as if it says you may use the voice, and any statement you think is wrong
  (these are summaries of pages read on 2026-10-11; the pages themselves are the thing to trust).
- [ ] See where each voice stands for this project: `PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.voices list --project voice-check`. → Both voices, `On this computer: no.`, and for each the next step
  (`Read where this voice comes from, then confirm that you have read it.`). Mike also says `This is the starting voice of project voice-check.`
- [ ] **The refusals.** In the terminal, give only the download's yes and see that it is not enough:
  ```bash
  PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.voices get mike --project voice-check --yes
  ```
  → The notes again, and it **still asks** `Have you read where this voice comes from? Type yes to confirm that you have.` Type **`no`**: `Nothing was done.` Check that nothing changed: `projects show` still says no starting voice has been
  acknowledged, and `ls ~/ack-voice-studio/tool/downloads` has no `voices` folder. Then the same with nobody to ask:
  `PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.voices get mike --project voice-check --yes < /dev/null`. → `There was nobody to ask, and --acknowledge was not given. Nothing was done.`
- [ ] **The real thing.** About 846 MB over the internet, kept for good:
  ```bash
  PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.voices get mike --project voice-check
  ```
  → The notes, then `Have you read where this voice comes from? Type yes to confirm that you have.` (type **`yes`**), `Saved: project voice-check has acknowledged this voice …`, then `Download this voice now? It is 846 MB from huggingface.co and will be kept in …`
  (type **`yes`**), `Saved your agreement to download this one file.`, and a line at about every 10% (no moving bar). It ends `Done. The voice is on this computer, and the file was checked against the one that was agreed to.`
  Write down: how long it took, and anything odd. **Optional:** press Ctrl+C part-way, then run the same command: it does not show the notes again, says `You already agreed to download this file, so it carries on.` and finishes. Or turn the Wi-Fi off for a minute while
  it downloads, and see `The internet connection stopped.` and then `The connection is back. Carrying on.`
- [ ] Look inside (this only reads):
  ```bash
  ls -l ~/ack-voice-studio/tool/downloads/voices/voice-mike/; sha256sum ~/ack-voice-studio/tool/downloads/voices/voice-mike/*.ckpt
  ```
  → One file, `epoch=5460-val_mos=4.2686.ckpt`, 845891981 bytes, with the fingerprint `9a8389c2d733f94e2acc3b4e8264b4ba3c063612217780e4be21c0ccaff18b9b`: the same as your own `mike.ckpt`
  (`sha256sum ~/piper/checkpoints/mike.ckpt`, if you still have it).
- [ ] Run the get command again. → `This voice is already on this computer, and project voice-check has acknowledged it. Nothing to download.` and no question.
- [ ] **Change the starting voice, and back** (this edits the project file, so it asks, and keeps the earlier one):
  ```bash
  PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.voices choose amy --project voice-check
  ```
  → `Set the starting voice of project voice-check to voice-amy? Only that line of its file changes, and the earlier file is kept as project.json.previous. Type yes to do it.` Type **`yes`**: `Done. Project voice-check now starts from voice-amy.`
  `ls ~/ack-voice-studio/projects/voice-check` shows `project.json.previous`. Choosing it only names it: nothing is downloaded and nothing is acknowledged. Do the same with `mike` to put it back.
- [ ] **Amy, and the check nobody has been able to make.** Get her the same way (`… voices get amy --project voice-check`, **read her notes first**: her licence is not established by what was read). Then see whether her checkpoint trains:
  the tool does not check this yet, and it has never been loaded with this trainer. Do section I's round with `--ckpt_path` pointing at her file in `~/ack-voice-studio/tool/downloads/voices/voice-amy/`, with `max_time` of about three minutes.
  → It either starts training or fails at once. Write down which, and the last five lines. (Done once, 2026-10-11, on 22.04: the developer reported that Amy's checkpoint trained; no lines were sent back, so do send them if you run it again.)

## I. One short training round, on the graphics card

**This is the part nobody has been able to check.** It uses the graphics card and can take several minutes to load. Close other programs
that use it. The numbers you write down here replace the guesses in the code (batch size 12, 4 workers, check every 10 epochs, a 25-minute
round).

- [ ] Start a round that stops itself after five minutes, with the programs the tool built in I0 (`ack_run.py` applies the documented workarounds first). It starts from your Mike
  checkpoint (use the file you have in `~/piper/checkpoints`) and runs from a **new, empty folder**, because the tool will start it that way. A background logger writes the card's memory
  to a file every five seconds, so no second terminal is needed, and the whole output is also saved in `round1.log`. Use the training set you built last (`dataset-2` if you built twice):
  ```bash
  mkdir -p ~/piper/voice-check/run && cd ~/piper/voice-check/run
  TRAIN=$(ls -d ~/ack-voice-studio/tool/environments/training-* | head -1)
  nvidia-smi --query-gpu=timestamp,memory.used,memory.total,utilization.gpu --format=csv,noheader -l 5 > ~/piper/voice-check/gpu.csv &
  GPU_LOG=$!
  date +%T
  "$TRAIN/venv/bin/python" "$TRAIN/ack_run.py" piper.train fit \
    --data.voice_name "my_voice" \
    --data.csv_path ~/ack-voice-check/dataset-1/metadata.csv \
    --data.audio_dir ~/ack-voice-check/dataset-1/wav \
    --model.sample_rate 22050 \
    --data.espeak_voice "en-us" \
    --data.cache_dir ~/piper/voice-check/cache \
    --data.config_path ~/piper/voice-check/config.json \
    --data.batch_size 12 \
    --data.num_workers 4 \
    --trainer.check_val_every_n_epoch 10 \
    --trainer.log_every_n_steps 1 \
    --trainer.max_time 00:00:05:00 \
    --ckpt_path ~/piper/checkpoints/mike.ckpt 2>&1 | tee ~/piper/voice-check/round1.log
  echo "exit code: ${PIPESTATUS[0]}"
  date +%T
  kill $GPU_LOG
  echo "---- summary"
  ls -l --block-size=M ~/piper/voice-check/run/lightning_logs/*/checkpoints/
  awk -F, '{gsub(/ MiB/,"",$2); if ($2+0>m) m=$2+0} END{print "peak graphics memory used (MiB):", m}' ~/piper/voice-check/gpu.csv
  tail -1 ~/piper/voice-check/gpu.csv
  tr '\r' '\n' < ~/piper/voice-check/round1.log | grep -i -E "error|traceback|warning|restor|max_time|time limit|Epoch [0-9]+:.*it/s" | tail -25
  ```
  → It starts, prints progress, and **stops by itself** about five minutes after it started (not counting loading): the log says `Time limit reached. Elapsed time is 0:05:00.` Then `exit code: 0`. **There is no `val_mos` score, on purpose** (see below).
  The findings, each of which decides something:
  - Did `--trainer.max_time` stop it by itself? How long after five minutes?
  - Is there a file `~/piper/voice-check/run/lightning_logs/version_0/checkpoints/last.ckpt`? (`ls -l` it.) It should be **there, in the
    folder you started from**, and about 800 MB.
  - Was the exit code 0?
  - The peak memory in the summary (it includes whatever else the card was doing; the last line shows what was left over afterwards), the card's total memory, and the epochs per second the trainer printed.
  - If it ran out of memory, try `--data.batch_size 8` and write that down. If steps took tens of seconds, the batch is too big for the card.
  - If it says `No module named piper`, the wheel did not install properly; write that down with the last lines of `build.log`.
  - **The log must not mention `SpeechMOS` or `MOS predictor`**: `grep -c -E "SpeechMOS|MOS predictor" ~/piper/voice-check/round1.log` → `0`. If it prints more, the quality score was loaded, which on a computer that has never run it means a download from GitHub.
  - **Why the quality score is off.** The trainer's optional `val_mos` score downloads a scorer's code and weights from GitHub (through `torch.hub`) and *runs* them, and needs `torchaudio`, which the locked programs do not carry. The
    first real round ended with `MisconfigurationException: ModelCheckpoint(monitor='val_mos')`. Passing `--model.mos_metric none` does **not** switch it off when resuming: Lightning's command line tool lays the settings saved inside the
    checkpoint over the command line (`hparams.yaml` and `config.yaml` in `lightning_logs/version_0/` still said `mos_metric: utmos`). So the launcher (`ack_run.py`) stops the scorer from loading and makes the trainer skip that one
    checkpoint rule when its score was never logged. The best checkpoints are still kept by `val_mel`; you choose by listening.
- [ ] Resume from the checkpoint the round just wrote, with **no time limit**, and stop it yourself with **Ctrl+C once**. The output goes to a file, so nothing is shown while it runs (if it went through `tee`, Ctrl+C
  would end `tee` too and could break the shutdown). The tool will always resume the highest `version_N`, with a **new** cache folder:
  ```bash
  V=~/piper/voice-check; cd $V/run
  TRAIN=$(ls -d ~/ack-voice-studio/tool/environments/training-* | head -1)
  date +%T
  "$TRAIN/venv/bin/python" "$TRAIN/ack_run.py" piper.train fit \
    --data.voice_name "my_voice" \
    --data.csv_path ~/ack-voice-check/dataset-1/metadata.csv \
    --data.audio_dir ~/ack-voice-check/dataset-1/wav \
    --model.sample_rate 22050 \
    --data.espeak_voice "en-us" \
    --data.cache_dir $V/cache-2 \
    --data.config_path $V/config.json \
    --data.batch_size 12 \
    --data.num_workers 4 \
    --trainer.check_val_every_n_epoch 10 \
    --trainer.log_every_n_steps 1 \
    --ckpt_path $V/run/lightning_logs/version_0/checkpoints/last.ckpt > $V/round2.log 2>&1
  echo "exit code: $?"
  date +%T
  ls -l --block-size=M $V/run/lightning_logs/*/checkpoints/ | tail -12
  tr '\r' '\n' < $V/round2.log | grep -i -E "restor|resum|interrupt|graceful|exception|traceback|error" | tail -15
  ```
  Press Enter, wait about 90 seconds (it loads for about 20 seconds, then trains), press **Ctrl+C once**, and wait. → `Restoring states from the checkpoint path … version_0/checkpoints/last.ckpt`, `Restored all states`, then
  `Detected KeyboardInterrupt, attempting graceful shutdown ...`, back at the prompt within a few seconds, a new `version_1/checkpoints/` folder with a `last.ckpt`, and `exit code: 1`. Write down how many seconds the stop took
  and whether the newest `last.ckpt` is older than the moment you pressed Ctrl+C (a stop by hand loses what was trained since the last check, at most ten epochs here).

- [ ] **A short round after a long one still trains for its whole time.** Start a one-minute round from the checkpoint the five-minute round wrote (the clock saved inside a checkpoint is not restored; the launcher sees to that).
  The output goes to a file, as above:
  ```bash
  V=~/piper/voice-check; cd $V/run
  TRAIN=$(ls -d ~/ack-voice-studio/tool/environments/training-* | head -1)
  date +%T
  "$TRAIN/venv/bin/python" "$TRAIN/ack_run.py" piper.train fit \
    --data.voice_name "my_voice" \
    --data.csv_path ~/ack-voice-check/dataset-1/metadata.csv \
    --data.audio_dir ~/ack-voice-check/dataset-1/wav \
    --model.sample_rate 22050 \
    --data.espeak_voice "en-us" \
    --data.cache_dir $V/cache-3 \
    --data.config_path $V/config.json \
    --data.batch_size 12 \
    --data.num_workers 4 \
    --trainer.check_val_every_n_epoch 10 \
    --trainer.log_every_n_steps 1 \
    --trainer.max_time 00:00:01:00 \
    --ckpt_path $V/run/lightning_logs/version_0/checkpoints/last.ckpt > $V/round3.log 2>&1
  echo "exit code: $?"
  date +%T
  echo "scorer lines in the log (want 0): $(grep -c -E 'SpeechMOS|MOS predictor' $V/round3.log)"
  tr '\r' '\n' < $V/round3.log | grep -i -E "time limit|traceback|error|exception" | tail -8
  ls $V/run/lightning_logs/
  ```
  → About a minute and a half in all, `exit code: 0`, `scorer lines … 0`, and `Time limit reached. Elapsed time is 0:01:00` (**not** `0:04:57`, which is what it said before the launcher kept the clock from being restored: the round
  then stopped after eight seconds).

## I2. Training rounds with the tool

**New, and not yet run on a real computer.** This is how the window will run a person's training: one round after another, each continuing from the round the person chose, and never from the starting voice
again by accident. It uses the project from section I1 (`voice-check`, with Mike chosen, acknowledged and on this computer), the training programs from I0 and the training set from H. Every step that changes
something shows what it will do and asks first. Nothing here deletes or moves a file. Run one command at a time. Keep the rounds short, two or three minutes each: they only have to prove the plumbing, and each
round keeps about 4.8 GB of saved files, so have about 25 GB free for the whole section.

- [ ] **First bring your copy of the tool up to date.** Section I2 was added after the earlier sections, and a copy made before that has no `rounds` command: Python then says there is no module named `voice_studio.rounds`.
  This only moves your copy forward, and it refuses (changing nothing) if you have edited files in it:
  ```bash
  git -C ~/ack-tools pull --ff-only
  ls ~/ack-tools/tools/voice_studio/rounds.py
  ```
  → Git lists the files it brought, or says it is already up to date; the `ls` prints the file's name. If `pull` refuses, copy what it says and stop there.
- [ ] Put a copy of the training set where the project keeps its own (the original stays where it is), and look. Looking changes nothing:
  ```bash
  mkdir -p ~/ack-voice-studio/projects/voice-check/scratch/datasets
  cp -r ~/ack-voice-check/dataset-1 ~/ack-voice-studio/projects/voice-check/scratch/datasets/
  PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.rounds list --project voice-check
  ls ~/ack-voice-studio/projects/voice-check/rounds
  ```
  → `There are no rounds yet. The first round starts from the starting voice.` and `No round is chosen yet, so the next round starts from the starting voice.` The `ls` shows no `rounds.json`: looking wrote nothing.
- [ ] The first round starts from the project's starting voice, which must be Mike here (section I1 ends by choosing him back). If `start` says another voice is not ready, put Mike back and ask again; this edits the project file, so it asks,
  and keeps the earlier one as `project.json.previous`:
  ```bash
  PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.voices choose mike --project voice-check
  ```
- [ ] Ask for the first round, and say no:
  ```bash
  PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.rounds start --set dataset-1 --minutes 3 --project voice-check
  ```
  → `Round 1 would:` and, under it, that it would continue from the starting voice `voice-mike`, train on the training set with its number of clips, run for about 3 minutes, train 12 clips at a time (and that this number was
  measured on a card with 8 GB), save its progress about every so many seconds (and that a round that ends loses that much at most), use the graphics card, stop by itself if the free space falls below a size it names, and keep its files
  under the project's `rounds` folder. Then `Checked before starting:` and two lines: how much of the graphics card is free against what this needs, and how much the round writes against the free space on the disk. Then
  `Start round 1 now? Type yes to start.` Type **`no`**: `Nothing was done.` and the `ls` above still shows no `rounds.json`. **Write down the two checks' numbers**: the card's free memory is the first real reading of what
  else is holding it (the Windows desktop, a browser, a speech model left loaded), and with less than about 5.4 GB free (5,184 MiB) the round is refused, with 5.4 to 6.0 GB (5,760 MiB) it is warned. These two numbers are guesses worked out from the one measured run.
- [ ] The same command, and type **`yes`**: `Round 1 started (job …).` Write down how long it took to start training (`tail -3 ~/ack-voice-studio/state/jobs/*/log.txt`). From another terminal, look:
  ```bash
  PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.rounds list --project voice-check
  ```
  → `Round 1: Training now.` while it runs, and how to stop it.
- [ ] When it has ended (about four minutes in all), look again. → `Round 1 (chosen): Finished.`, a line saying the saved point is there, and `Chosen: round 1. The next round continues from it. About 3 minutes of training so far.`
  If it says `Ended with an error`, or `It ended, but it did not save a whole point to carry on from.`, **send back the last 20 lines of the job's log** and `ls -l ~/ack-voice-studio/projects/voice-check/rounds/run/lightning_logs/version_0/checkpoints`:
  the second sentence can also mean that the tool's check of a saved file is wrong about real files (see the check below).
- [ ] Round 2 continues from round 1. Start it the same way, say `yes`, and **close the terminal while it runs**: it must go on by itself. Open a new terminal when it should be over and run `list`. → `Round 2 would:` said
  that it would continue from round 1, the chosen round; now `Round 2 (chosen): Finished.` Then look at what each round was started from:
  ```bash
  grep -h -o -- '"--ckpt_path", "[^"]*"' ~/ack-voice-studio/state/jobs/*/job.json
  ```
  → One line for each round. Round 1's ends in Mike's own file name, `epoch=5460-val_mos=4.2686.ckpt`. Round 2's ends in `rounds/run/lightning_logs/version_0/checkpoints/last.ckpt`. **Round 2's must never be the voice file.**
- [ ] Stop a round by hand. Start round 3 with `--minutes 10`, wait a minute, then:
  ```bash
  PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.rounds stop --project voice-check
  ```
  → `Stop round 3? It saves what it can first, but the last few minutes of training can be lost. Type yes to stop it.` Type **`yes`**: `Asked round 3 to stop. It may take a little while to finish saving. Look again with: …`
  Write down the seconds until `list` shows `Round 3: Stopped by you.` and whether it says the saved point is there. A round stopped before its first check has none; it is then not chosen, and the next round
  still continues from round 2.
- [ ] Go back, and branch. `PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.rounds back --project voice-check` → `Go back to round …` with both numbers in it. Type **`no`**: `Nothing was done.` Run it again and type **`yes`**:
  `Done. Round 2 is chosen now. Round 3 is still in the list, and its files are untouched.` (If round 3 had no saved point, round 2 was already chosen and `back` goes to round 1: the numbers in the sentence follow what the list says.)
  Then start another round. → It says it would continue from the round you went back to, and `list` shows the new round as `continuing from round 2` (or 1). `ls ~/ack-voice-studio/projects/voice-check/rounds/run/lightning_logs` still shows every `version_` folder.
- [ ] See what is kept. This changes nothing:
  ```bash
  PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.rounds keep --project voice-check
  ```
  → `Kept for sure (2 files …` (the chosen round's saved point and the one before it), a line for the spare files and their size, and `This command removes nothing.` Compare the sizes with
  `ls -l ~/ack-voice-studio/projects/voice-check/rounds/run/lightning_logs/*/checkpoints/` (every round has the `last.ckpt` and five more, about 807 MiB each).
- [ ] **Try the disk guard without filling a disk.** This starts a harmless job that only waits, with a free-space floor set *above* what your disk has, so the job's own runner sees the disk as too full. It uses no graphics card
  and no round:
  <!-- snippet: disk-guard -->
  ```bash
  PYTHONPATH=~/ack-tools/tools python3 - <<'EOF'
  import os, shutil, sys, time
  from voice_studio.core import jobs

  home = os.path.expanduser("~")
  folder = os.path.join(home, "ack-voice-check", "jobs")
  os.makedirs(folder, exist_ok=True)
  free = shutil.disk_usage(home).free
  code = "import time\nprint('waiting', flush=True)\ntime.sleep(60)\n"
  info = jobs.start_job(folder, jobs.JobSpec("guard", "", (sys.executable, "-c", code), watch=((home, free + 10 ** 9),)))
  for _ in range(60):
      time.sleep(1)
      now = jobs.job_info(info.dir)
      if now.status not in jobs.ACTIVE:
          break
  print(now.status.value, "stop reason:", now.stop_reason or "none")
  EOF
  ```
  → `stopped stop reason: disk`, within a few seconds (the runner looks every five). That is the real runner, on your computer, stopping a command the gentle way because a drive was below its floor.
- [ ] Write a note, and take it away:
  ```bash
  PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.rounds note 1 --text "first try" --project voice-check
  PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.rounds note 1 --text= --project voice-check
  ```
  → `Set the note on round 1 to this? first try Type yes to save it.` Type **`yes`**; `list` shows `Note: first try`. Then `Remove the note on round 1? Type yes to remove it.`
- [ ] **Is the tool's check of a saved file right about real files?** The tool calls a saved point whole when it opens as a zip and holds the state, which is how PyTorch writes one; nobody has run that on a real file.
  This only reads:
  <!-- snippet: checkpoint-check -->
  ```bash
  PYTHONPATH=~/ack-tools/tools python3 - <<'EOF'
  import glob, os
  from voice_studio.core.rounds import checkpoint_complete
  home = os.path.expanduser("~/ack-voice-studio")
  files = sorted(glob.glob(home + "/tool/downloads/voices/voice-mike/*.ckpt"))
  files += sorted(glob.glob(home + "/projects/voice-check/rounds/run/lightning_logs/version_*/checkpoints/last.ckpt"))
  for path in files:
      print(checkpoint_complete(path), path)
  EOF
  ```
  → `True` on every line. A `False` for a file that trained fine means the check is wrong about real files and every round would be called failed: send that back first.
- [ ] **Does a round that ends at its time limit save its last moment?** Each round's log says which epoch it reached; the saved file says which epoch it holds. This only reads:
  ```bash
  TRAIN=$(ls -d ~/ack-voice-studio/tool/environments/training-* | head -1)
  "$TRAIN/venv/bin/python" - <<'EOF'
  import glob, os, torch
  for path in sorted(glob.glob(os.path.expanduser("~/ack-voice-studio/projects/voice-check/rounds/run/lightning_logs/version_*/checkpoints/last.ckpt"))):
      saved = torch.load(path, map_location="cpu", weights_only=False)
      print(os.path.basename(os.path.dirname(os.path.dirname(path))), "holds epoch", saved.get("epoch"), "step", saved.get("global_step"))
  EOF
  for log in ~/ack-voice-studio/state/jobs/*/log.txt; do echo "$log"; tr '\r' '\n' < "$log" | grep -o "Epoch [0-9]*" | tail -1; done
  ```
  → For a round that ended at its time limit: is the epoch in the file the same as the last epoch in the log, or older (by up to 10)? Write both down for every round.

## I3. Freeing up space

**New, and not yet run on a real computer. This is the one section that removes files you made**, so it is written to be done slowly, and the first steps remove nothing. `free` offers two things from rounds
that have ended: a round's spare saved files (every saved file of it except the chosen round's saved point and the one before it), and a round's working files (the training program's scratch folder, which is never read again). Once section I8 has been done it also offers the test clips and the voices made for hearing a round, which are kept in the project's `listening` folder (last step below).
It never offers recordings, notes, the project file, backups, finished voice files, the starting voices, the files of a round that is running, or anything the tool did not make. It always shows exactly what it will remove and asks first,
and what was removed cannot be brought back, so **if you want every round kept as it is, stop after the first two steps.** It uses the project from section I2 and needs at least two rounds there.

- [ ] Look. This changes nothing:
  ```bash
  df -h ~
  PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.rounds free --project voice-check
  ```
  → `What could be freed up for Voice check:`, then a line for each round whose saved files could go, with their size, and for each ended round whose working files are still there, with theirs. The chosen round's line says `Its own saved point is kept.`
  A round that is neither the chosen one nor the one it continued from says, if its saved point is on the list, that the round could not be chosen again. Then the total, `Kept for sure, never on this list: …`, and
  `Recordings, notes, the project file, backups, exports and the starting voices are never on this list.` and how to name rounds. Write down the sizes and the output of `df`. (`df -h` counts in 1,024s and this tool counts in 1,000s, the way drives are sold, so the tool's numbers read about 7% bigger: `872G` in `df` is about 936 GB in the tool. Same space, different unit.) If it says `There is nothing to free up. Every saved file that is left is kept for sure, in use, or not made by a round.`, there is nothing to try yet: run more rounds, or stop here.
- [ ] Ask to remove one round's spare saved files, and say no. Pick a round whose line does **not** say it could not be chosen again:
  ```bash
  PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.rounds free --saved 1 --project voice-check
  ls -l ~/ack-voice-studio/projects/voice-check/rounds/run/lightning_logs/version_0/checkpoints/
  ```
  → `This removes:` and that round's line, then `Remove all of that, about …` and, in the same question, that it cannot be undone. Type **`no`**: `Nothing was done.` and the `ls` still lists every file. (Round 1 is normally `version_0`, round 2 `version_1`, and so on in the order the rounds ran. If you picked another round, `ls` the `version_` folders and use the one that has the files the list described.)
- [ ] Ask for something that is not on the list. Nothing may be removed, and nothing is asked:
  ```bash
  PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.rounds free --saved 99 --project voice-check
  PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.rounds free --all --saved 1 --project voice-check
  PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.rounds free --saved one --project voice-check
  ```
  → `The list has nothing for --saved 99. Nothing was removed. See the list with: …`, then `Give either --all or a list of rounds, not both. Nothing was removed.`, then `I did not understand one. Give round numbers separated by commas, for example 1,3. Nothing was removed.`
- [ ] **Only if you are willing to lose it:** remove the working files of one ended round. They are rebuilt by the next round that needs them, so this is the least precious thing on the list (if the list has no working files, skip this step). Type **`yes`**:
  ```bash
  PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.rounds free --working 1 --project voice-check
  df -h ~
  ```
  → `Done. Saved files removed: …`, which says 0 saved files and 1 round whose working files were removed, and how much was freed; the free space on the drive of this project. The `df` shows about that much more room (on WSL the room is free inside Ubuntu at once, but Windows only gets it back when the virtual disk is shrunk, which the tool does not do).
  Look again with `free --project voice-check`: that line is gone and nothing else changed.
- [ ] **Only if you are willing to lose it:** remove one older round's spare saved files (a round that is not the chosen one and not the one it continued from, and whose line does not say it could not be chosen again). Type **`yes`**, then check that the voice you are building on is still whole:
  ```bash
  PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.rounds free --saved 1 --project voice-check
  PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.rounds list --project voice-check
  PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.rounds keep --project voice-check
  ```
  → `Done. Saved files removed: …`; then `list` still says `The saved point is there` under the chosen round, and `keep` still lists the chosen round's `last.ckpt` and the one before it. The `ls -l` of the `version_` folder you picked shows only `last.ckpt` is left if that round's saved point was not on the list.
  If `list` says `The saved point is missing` for the **chosen** round, stop and send it back: that is the one thing this command must never do.
- [ ] **Test clips and the voices made for hearing** (only after section I8 part E has been done with a **no** to the last question, so a voice copy was kept; these can be made again, so they are the least precious files on the list). Look:
  ```bash
  PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.rounds free --project voice-check
  ```
  → A line `Test clips of round …, made on … UTC: …` for each time you listened to a round or to its voice file, `The voice made for hearing round … on … UTC: …` and `The test clips stay.` for each voice copy that was kept, and `Test clips and the voices made for hearing a round are chosen by round too, with --clips and --copies.` with an example. Ask to remove one round's voice copies, say **no**, then **yes**:
  ```bash
  PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.rounds free --copies 2 --project voice-check
  ls -l ~/ack-voice-studio/projects/voice-check/listening/round-*/*/
  ```
  → `This removes:` and the line for that copy, the question (about the size shown), and after the **yes** `Test clips and voices made for hearing, removed:` and a number of files. The `ls` still lists the sound files, `job.json` and `tokens.txt` and no longer lists `my_voice.onnx`. Then the clips, the same way:
  ```bash
  PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.rounds free --clips 2 --project voice-check
  ls ~/ack-voice-studio/projects/voice-check/listening
  ```
  → The folder for that listening is gone, and `listening` itself is still there. A file you put in one of those folders yourself is never listed and is still there afterwards, and its folder stays.
- [ ] **Old listenings (30 days).** A listening made 30 or more days ago is marked old: its row ends `This is more than 30 days old and should be removed.`, `free` prints, for two of them, `2 earlier listenings are more than 30 days old and should be removed.` (or `1 earlier listening is more than 30 days old and should be removed.`) with `To remove them, run:` and the command, and `listen` says the same before it shows its plan. Nothing is removed because of it. You will not have anything that old yet, so make one: rename a listening's folder to a date more than 30 days back (only its `heard-` name changes; the files inside are untouched), for example
  ```bash
  cd ~/ack-voice-studio/projects/voice-check/listening/round-*/ && mv heard-2026* heard-20260101-090000
  PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.rounds free --project voice-check
  PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.rounds free --old --project voice-check
  ```
  → The first lists it with the notice. The second says `This removes:` with only the old listening, asks, and a **no** removes nothing; with nothing old it says `Nothing is more than 30 days old. Nothing was removed.` Put the name back (or say yes) when done. `--old` on its own: `--old --all` says `Give --old on its own, without --all or a list of rounds.`
- [ ] In the window (section I5), the Free up space page shows the same items, each with a tick box and its size, and the old notice at the top when there is one.
- [ ] Write down: how long it took, whether any wording confused you (the lines for a round's files, the question, the `Done.` line), whether you wanted a way to see the files before choosing, and whether the numbers in `--saved` were easy to read off the list.

## I4. Making the voice file with one command

**New, and not yet run on a real computer.** This does what section J does by hand, from the round you chose, in one command: it makes the voice from that round's saved file, gives it that round's own settings file, prepares it for the phone, makes the zip
file ACK takes, and reads the zip back as the phone would. Last, it writes a **card** (`MODEL_CARD.txt`) beside the zip that says where the voice comes from and how it was made (part of the plan's decisions D21 and D27; the card is not inside the zip). It writes only into **one new folder** under the project's `exports` and never changes, replaces or removes anything that was there. It needs the project from section I2 with at least one finished
round that is chosen (`rounds list` says which), and it does not run while a round is training. About 1 GB of free space is needed at most (the tool says how much it checked). Run one command at a time.

- [ ] Look. This changes nothing:
  ```bash
  PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.voicefile list --project voice-check
  ```
  → `No voice file has been made for this project yet.` and how to make one.
- [ ] Ask for the voice file, and say no. The command shows what it will do and checks the room before it asks:
  ```bash
  PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.voicefile make --project voice-check
  ls ~/ack-voice-studio/projects/voice-check/exports
  ```
  → `The voice file would be made like this:` and under it that it would take the saved point of the chosen round (with its size and how many minutes of training are in it), take that round's own settings file, make the voice, make the zip file and read it back, and write
  everything into a new folder. Then `Checked before starting:` and a line about the free space. Then `Make the voice file from round` and the chosen round's number. Type **`no`**: `Nothing was done.` and the `ls` shows nothing new. **Write down the saved point's size and the minutes.**
- [ ] The same command, and type **`yes`**. Write down how long it takes (the export is the slow step; on the developer's computer the whole thing took 11 seconds, which is not a promise for yours):
  ```bash
  time PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.voicefile make --project voice-check
  ```
  → `Step 1 of 5: making the voice from the saved point.`, then steps 2 to 5, then `Last: writing the card that says where the voice comes from, beside the zip file.`, then `Done. The file to give to ACK is: …` with the path of the zip file, the folder it is all in, and where the card is. If a step stops, it says which, what was left (`What was made so far is in …`) and that nothing was deleted;
  **copy the whole output**, and the `ls -l` of that folder. If the export stops with `GuardOnDataDependentSymNode` or asks for `onnxscript`, that decides whether the lock needs another package, as in section J.
- [ ] Look at what it made, and compare the settings file with the round's own:
  ```bash
  ls -l ~/ack-voice-studio/projects/voice-check/exports/*/
  python3 -m zipfile -l ~/ack-voice-studio/projects/voice-check/exports/*/*.zip
  ls ~/ack-voice-studio/projects/voice-check/rounds/config
  ```
  → The folder holds `my_voice.onnx`, `my_voice.onnx.json`, `my_voice.onnx.before-patch`, the zip file and `MODEL_CARD.txt`. `python3 -m zipfile -l` lists exactly `model.onnx` and `model.onnx.json` (the card is not in the zip). The settings file is a copy of the chosen round's file in `rounds/config`: `cmp` that file with `my_voice.onnx.json`
  (give `cmp` both paths); it prints nothing when they are the same.
- [ ] **Read the card.** New, and not yet run on a real computer. `MODEL_CARD.txt` is a plain text file that says where the voice comes from, written from what your project recorded and nothing else. Read it here, or press `Show the folder` on the window's Voice file page and double-click it in Windows:
  ```bash
  cat ~/ack-voice-studio/projects/voice-check/exports/*/MODEL_CARD.txt
  ls -l ~/ack-voice-studio/projects/voice-check/exports/*/MODEL_CARD.txt
  ```
  → It starts `Voice file card` and has six headings in this order: `The voice file`, `Where it comes from`, `How it was trained`, `Whose voice it is`, `Made with` and `What this card holds`. The `ls` shows `-rw-------` (only you can read it). Check each part:
  `The voice file` gives `Zip file for ACK:` with the zip's size, `Made on:` with the time in UTC, and two check codes. `Where it comes from` names the starting voice your project began from (Mike or Amy), says what the voice's own pages say about its recordings and about Lessac, gives a `Page to read:` address for each, and ends with the date of the read, that nothing is hosted here and `no legal advice`. It also shows either `acknowledged in this project on` a date `for revision` a number, or `This project has no acknowledgment recorded for that voice.`; a project made before acknowledgments were kept should say the second, and that is the right answer, not a fault. `How it was trained` gives the round and how many rounds and minutes are behind it: compare with `rounds list`. `Whose voice it is` matches how you set the project up; for someone else's voice it names only *how* the agreement was given (for example `They said so`), never a name, a date or a word of the note. `Made with` gives the tool's version and the training programs' build.
  **Read every sentence for anything that sounds like permission to use the voice, and write down any you find: there should be none.** The card must not say that use is allowed, only that the question is yours and is separate.
- [ ] Check the card against the files, and search it for names. The first command takes the two files out of the zip into a new folder in `/tmp` and prints their check codes; they must be the two codes in the card. The second prints nothing if neither the project's folder name nor your own name is in the card (change `yourname` first):
  ```bash
  mkdir /tmp/ack-card-check && python3 -m zipfile -e ~/ack-voice-studio/projects/voice-check/exports/*/*.zip /tmp/ack-card-check && sha256sum /tmp/ack-card-check/model.onnx /tmp/ack-card-check/model.onnx.json
  grep -i -e voice-check -e yourname ~/ack-voice-studio/projects/voice-check/exports/*/MODEL_CARD.txt
  ```
  → The two codes match. The `grep` prints nothing. The new folder in `/tmp` can be deleted when you are done; nothing else uses it.
- [ ] Look again, and make a second one a minute later. The first must not change:
  ```bash
  PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.voicefile list --project voice-check
  ```
  → `Voice files made for Voice check:` and a line for the file with its size and where it is. Run `make` and `yes` again after a minute: the list now shows two, with different time stamps in their names, and the first one's files have the same dates as before.
- [ ] **Only if you want to see a refusal.** This moves one of your files aside for a minute and puts it back. With the chosen round's settings file out of the way, `make` must refuse before it writes anything. The commands below use round 3: change `003` in all three to the chosen round's number, with leading zeros to make three digits:
  ```bash
  mv ~/ack-voice-studio/projects/voice-check/rounds/config/round-003.json ~/ack-voice-studio/projects/voice-check/rounds/config/round-003.json.aside
  PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.voicefile make --project voice-check --yes
  mv ~/ack-voice-studio/projects/voice-check/rounds/config/round-003.json.aside ~/ack-voice-studio/projects/voice-check/rounds/config/round-003.json
  ls ~/ack-voice-studio/projects/voice-check/exports
  ```
  → `The chosen round has no settings file.` and under it `Nothing was made.` and what to do next. The `ls` shows only the folders from before. **Put the file back (the third command) even if something looks wrong.**
- [ ] Take the zip file to the phone and import it, as in section K. Write down whether ACK took it the first time, and whether it speaks in the voice.
  *Confirmed on the developer's computer and phone (2026-10-11): `make` ran the real export, patcher and zip in 10.7 seconds and produced a 64 MB zip that read back clean; the folder held exactly the four files, the zip held exactly `model.onnx` and `model.onnx.json`, the settings file was identical to round 3's own; the phone took the zip the first time and MY VOICE spoke, better than the earlier runs. The refusal step (moving the settings file aside) was not run.*
- [ ] Write down: how long it took, whether any wording confused you (the plan, the five steps, the `Done.` lines, the card), whether you wanted the file somewhere else than the project's `exports` folder, whether you wanted a name of your own for it, and whether you would hand the card to someone who is given the voice.

## I5. The window (WSL only for now)

**New, and not yet run on a real computer.** This is the first window: the same steps as the terminal commands in sections I2 to I4, with buttons. It does nothing the terminal does not do: every button runs the very command, shows what it will do and asks first, in a box
with **No** where the keyboard focus starts (Enter and Escape both mean no) and **Yes** beside it. It runs on **WSL with its graphical support (WSLg)**, which you have; a native Ubuntu desktop and the Orca screen reader are **not tested yet** (no computer for it at the moment) and are marked as pending in the plan.
It needs the system Python, the one that has Ubuntu's GTK package, so the commands below say `/usr/bin/python3` and **not** `python3`: if your terminal has a virtual environment switched on, plain `python3` is that environment's Python and cannot see GTK. It uses the project from section I2, and
`make` in it writes a new folder like section I4 does. Run one block at a time, and write down what the paragraph after it asks.

- [ ] Can the window start here? This only looks:
  ```bash
  PYTHONPATH=~/ack-tools/tools /usr/bin/python3 -m voice_studio.window --check
  ```
  → `The program running this check: …`, `GTK: 4.6.9` and `Yes. Start the window with: …`. If it says `This program cannot find the GTK bindings. Use the system one, or install them with: …` or `There is no desktop to show a window on.`, copy the whole output and stop there.
- [ ] Start the window. Leave the terminal open (closing it closes the window; the menu entry below is for starting without one):
  ```bash
  PYTHONPATH=~/ack-tools/tools /usr/bin/python3 -m voice_studio.window
  ```
  → A window titled `ACK Voice Studio - Voice check` with eleven pages on the left (Projects, Recordings, Training rounds, Hear the voice, Voice file, Backup, Free up space, Check the tool, Updates, Problem report, Display; the five in the middle and at the end that were added later are section I15's, and the developer's run of this step, below, was made when there were six) and `Last result` at the bottom with `Nothing has been done in this window yet.` Write down: **how many seconds until it appeared**, whether anything is garbled, black or flickering,
  whether the text is easy to read at your Windows scaling, and whether it opened on the Recordings page by itself (it should, because there is only one project; the Recordings page is new, see section I6). If the picture is garbled, close it, run the same command with `GSK_RENDERER=cairo` in front of `PYTHONPATH` and say whether that fixes it.
- [ ] Use it with the keyboard only (no mouse): Tab and Shift+Tab move between controls, the arrow keys move in a list, Enter or Space press a button. Visit every page. Write down: any control you could not reach, any place where you could not see where the focus was, and any button whose purpose was not clear from its words alone.
  *Confirmed on the developer's computer (2026-10-12): `--check` said yes with GTK 4.6.9; the window opened with no warning or error; the text felt a little small (the look and feel was done after this: see the next two items); Enter and Escape in a question both meant no; Free up space worked by keyboard alone and the focus was always visible. Make the voice file worked from the window (the bar moved, about ten seconds), Show the folder opened Windows File Explorer, and Copy the path pasted correctly into a Windows program. The dialogues felt wordy: the language pass shortened 14 sentences afterwards (plan, VS-2.1b); say whether the boxes now read well.*
- [ ] **The look.** The window now looks like ACK on the phone: a black background, cyan lines and text, buttons and panels with the top left and bottom right corners cut, headings and buttons in a monospace font, sentences in the system's font, and a header with `ACK`, `Voice Studio`, the project's name and the two text size buttons `Smaller text` and `Bigger text`. Write down: whether the corners are cut cleanly or look jagged (they are drawn by the style sheet alone), whether any text is cut off or overlaps, whether you can tell where the focus is on every kind of control (buttons, the page list, tick boxes, the number boxes), and whether any grey text is too faint for you to read. Press `Bigger text` twice and then `Smaller text` twice: the text should grow and shrink at once, and the layout should keep up.
- [ ] **The Display page.** Open it from the page list. It has `Colours` (`ACK colours` and `System colours`), the ten accent colours, `Text size`, `Size of the whole window`, and `Your choices` with two buttons that keep or forget the file. Try, one at a time, and write down what you see:
  (These steps start with no choices file. If `~/ack-voice-studio/state/window.json` exists from an earlier try, do step 6 first.)
  1. Pick a different accent colour. → A box asks `Keep your choices in this file?`, names the file and says what it holds. Say **No**. The colours change anyway, and the result says `Your choices last until you close this window.` Choose the red, the blue and the magenta ones in turn (nothing asks again): write down any colour whose text is hard to read.
  2. Press **System colours**. → The window takes Windows' or Ubuntu's own colours, the accent row is hidden and a note says the accent colour then has no effect. Press **ACK colours** to go back.
  3. Set `Size of the whole window` to 150% and then 200%. → Everything grows together, not only the text: the page list, the buttons, the spacing. Write down whether anything is cut off at 200% and whether the window still fits your screen. Then put it back to 100%. (If you already scale Windows itself, say what that is: the two multiply.)
  4. Close the window and open it again. → The standard look: nothing was written, because you said no.
  5. Change something and say **Yes** to the question this time. From then on every change is kept without asking. Look at the file, then change one more thing and look again:
  ```bash
  ls -l ~/ack-voice-studio/state/
  cat ~/ack-voice-studio/state/window.json
  ```
  → `window.json` is owner-only (`-rw-------`), a few lines long, and holds only the theme, the accent, the text size and the scale. After the second change a file called `window.json.previous` sits beside it. Close and open the window: your choices are still there.
  6. Press the button that stops keeping your choices. → A box lists the file or files that would be removed and asks; **No** removes nothing. Press it again and say **Yes**: the files are gone and the window keeps its look until you close it.
  7. Turn on a high-contrast theme in Windows (Settings, Accessibility, Contrast themes), choose **System colours** and look at every page: the colours should follow the theme. Write down anything unreadable.
- [ ] **Training rounds.** Press `Look again`. The list is the same as `rounds list` and a round that is chosen says so. Press **Write a note…** on round 1, type `first window try`, press Save. → A box shows what will be saved and asks; press **Yes**. `Last result` says it was done and the round's lines now show the note. Then do it again with an empty note to remove it.
- [ ] **Choose a round, and say no.** Press `Choose this round` on a round that is not the chosen one. → A box with the plan lines and the question `Choose round 1? The next round will continue from it. …` (with your round's number, and that every round and all their files stay where they are). Press **No**: `Nothing was done.` in `Last result`, and the list is unchanged.
  Pressing Enter or Escape in that box must also be a no. (Choosing a different round for good is a real edit: it only changes which round the next one continues from, and choosing the old one again undoes it. Do it only if you want to.)
- [ ] **Free up space, and say no.** On Free up space, tick one box (clicking the words ticks it too). `Remove the ticked items…` becomes usable and `Ticked: about …` appears. Press it. → A box that begins `This removes:` and names exactly the ticked items, then a question with the size and that it cannot be undone. Close the box with the window's close button or Escape: that is a no.
  Nothing is removed: look again at the list. Untick the box.
- [ ] **Make the voice file.** On Voice file press `Make the voice file…`. → A box with `The voice file would be made like this:` and the room check, and the question `Make the voice file from round`, then your round's number. Press **Yes**. Write down whether the bar at the bottom moves while it works, and how long it takes (about 11 seconds in section I4).
  Afterwards `Last result` says where the file is and the list `Voice files made so far` has one more row.
- [ ] **Show the folder, and copy the path.** On that new row press `Show the folder`. → Windows File Explorer opens on the folder with the zip in it. If it does not, `Last result` says the path instead (`The folder could not be opened from here. Its path is: …`); write down which happened. Then press `Copy the path`, open Notepad in Windows and paste (Ctrl+V): write down whether the path is there.
- [ ] **The Start menu.** On WSL this makes one shortcut in **your own Windows Start menu folder**, through the Windows program that WSL already lets Linux start. It needs no `sudo`, no password and no administrator rights, and it shows you what it will write and asks first:
  ```bash
  PYTHONPATH=~/ack-tools/tools /usr/bin/python3 -m voice_studio.window --install-launcher
  ```
  → `Looking at your Windows Start menu first. This can take a few seconds.`, then `This would write, on the Windows side, in your own folders:`, a line `a new Start menu shortcut: …` (a path under your Windows `Start Menu\Programs`, named `ACK Voice Studio (Ubuntu-22.04)`) and a line `a new icon file: …` (a path under your Windows application data, in a folder called `ack-voice-studio`),
  `It changes nothing else, and it needs no administrator rights and no password.` and `Write these files now?`. Type **`no`**: `Nothing was done.` and the Start menu has nothing new. Run it again and type **`yes`**: `Making the shortcut. This can take a few seconds.`, `Done. The shortcut is in place.`,
  `Look for ACK Voice Studio (Ubuntu-22.04) in your Start menu.`, a note that the first start after Windows has stopped WSL can take a little while, and how to take it away again.
  Write down: how many seconds the tool took to look and to make it (a Windows program has to start each time), whether the entry is found by typing its name in the Start menu, whether it has the icon (five cyan bars in a black square with two cut corners and a cyan outline), whether it starts the window with no terminal open, how long the first start takes, and whether Windows showed any warning of its own.
  Then run the same command again: `The menu entry is already in place and up to date. Nothing was changed.` and no question.
  **If you still have the two files that the earlier version asked you to copy with `sudo`** (the developer does), the tool sees them and says `The copy that WSL reads is already in the system folder: …` and `Nothing was written.`: WSL already makes its own Start menu entry from them, so a second one is not added. To try the new way, take the old copy away first: `--remove-launcher` below prints the one `sudo rm` line for it,
  which only a computer that went through the earlier version needs. Look in the Start menu again after a minute (write down whether WSL's own entry went), then run `--install-launcher` again.
  *Confirmed on the developer's computer (2026-10-12): after taking the earlier files and the system copy away, `--install-launcher` made the shortcut, and the developer reported that it worked. Not yet reported: the exact output, whether the entry has the icon, how long the first start took, whether Windows showed a warning, the second run's "already in place" answer, and the new `--remove-launcher` path.*
  *Why this exists (2026-10-12): with the earlier way the entry only appeared in the Start menu after two `sudo install` commands were run by hand; the developer's verdict was that no one else should be asked to do that. WSL's own entry, made from those two files, showed the icon, started the window with no terminal open, and took about fifteen seconds on the first start after `wsl --shutdown`.*
  If Windows programs cannot be started from WSL on a computer, or the Windows side gives an answer the tool does not understand, it says `This tool cannot reach your Windows Start menu from here. It can still make a menu entry on the Linux side.` and the earlier steps follow, with the `sudo` commands printed for you to run and never run by the tool.
- [ ] **Take the menu entry away again** (only if you want to; a shortcut or file is only ever removed if this tool made it, and a copy made with `sudo` is never removed by the tool, which prints the command for it):
  ```bash
  PYTHONPATH=~/ack-tools/tools /usr/bin/python3 -m voice_studio.window --remove-launcher
  ```
  → `Looking at your Windows Start menu first. This can take a few seconds.`, `This would remove these files that this tool made:`, the shortcut and the icon (and, if an earlier version wrote them, the two files under `~/.local/share`), and a question. Type **`yes`**: `Removing them. This can take a few seconds.` and `Done. The menu entry is removed. Nothing else was changed.`
  If a copy is in the system folder it adds `A copy in the system folder is still there, and this tool does not remove it. To remove it, run: …` with the command. A shortcut of the same name that you made yourself is left where it is: `Left alone, because this tool did not make it: …`.
- [ ] **A screen reader, if you use one on Windows.** Start Narrator (Windows logo key + Ctrl + Enter) or NVDA, click into the window and move with Tab. Write down what is read for: a page name, a button such as `Choose round 1`, a tick box, the box that asks a question, and the `Last result` text after something finishes. This is the question the plan needs answered for WSLg;
  it is fine if the answer is "nothing is read".
- [ ] Write down: anything that felt slow, anything that moved or flashed (the window is meant to have no animation except the bar), any word that was hard to understand, and whether you would rather the pages were arranged another way.

## I6. More than one project, and bringing in voice recordings you already have (terminal first, then the window)

**New, and not yet run on a real computer.** Two things the window could not do before. The first is to keep several projects (one per voice) and to change, put away, bring back or delete one. The second is to bring in voice data that ACK did not make: a package ACK saved on the phone, a folder of
audio files with a text file for each, a folder of audio files with one table of sentences (such as a `metadata.csv`), or a folder of audio files alone. Then to let the computer listen to them and make a training set from what it heard. **You always say which kind it is** (`--kind`, or the choice in the window): the tool never guesses,
because a wrong guess would quietly give a recording the wrong words. Everything that changes something shows what it will do and asks first. A folder you choose is **only read**; nothing in it is moved, renamed or deleted, and the copies go inside the project. Every command takes `--project voice-check` so that it works on the project from
section I1. Run one command at a time, and wait for it to finish before you type the next. The second project this section makes (`second-check`) is made and deleted by the section itself. **Nothing here uses the internet.**

### Projects, from the terminal

- [ ] Make a second project, only for this check: `PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.projects new --own --name "Second check" --yes`. → `Made the project second-check.` Then `PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.projects list` shows both.
- [ ] **Change a detail.** This asks first and keeps the earlier file:
  ```bash
  PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.projects edit second-check --hours 2
  ```
  → `These details of second-check would change:` and a line `Planned hours: from 1 to 2`, then `Save these changes? Type yes to save them.` Type **`no`**: `Nothing was changed.` Run it again and type **`yes`**: `Saved. The details of second-check are changed.` and the line that the version from before is kept as `project.json.previous`.
- [ ] **Put it away, and bring it back.** Putting away only hides it; nothing is removed:
  ```bash
  PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.projects archive second-check
  ```
  → `Put Second check away? Nothing is removed. It leaves the list, and no command uses it until you bring it back. Type yes to put it away.` Type **`yes`**: `Done. second-check is put away. To bring it back, run: …` Then `PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.projects list` shows only voice-check and ends with `1 project is put away. To see it, run: …`; `PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.projects list --away` shows it. Try a command that changes things on it, such as
  `PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.projects edit second-check --hours 3`: it refuses and says to bring it back first, and `ls ~/ack-voice-studio/projects/second-check` still shows its files. Bring it back with `PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.projects unarchive second-check`: `Bring Second check back? It returns to the list exactly as it was. Type yes to bring it back.` Type **`yes`**: `Done. second-check is back in the list.`
- [ ] **Delete it, which asks twice.** This one cannot be undone, so it lists what goes and says to copy anything you want first:
  ```bash
  PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.projects delete second-check
  ```
  → `This would remove the project second-check: Second check. It cannot be brought back.` then what is in it (a project file and empty folders), `Before you go on, copy anything you may want later. Nothing here can be brought back.`, then, once section I9 exists, whether the project has been backed up (`Second check has not been backed up on this computer. To make a backup first, run:` and the command, or when and where the last backup was made) and `Delete the project Second check for good? Type yes to go on.` Type **`no`**: `Nothing was removed.` and the folder is still there. Run it again, type **`yes`**, and see that it asks
  **a second time**: `Last question. Remove Second check, …` Type **`no`**: `Nothing was removed.` Run it a third time and answer **yes** and **yes**: `Done. The project second-check is deleted. About …` and `ls ~/ack-voice-studio/projects` shows only voice-check. **`--yes` on the line answers the first question only; the second is always asked.** Write down: any sentence that was hard to follow, and whether you were ever unsure what a command was about to remove.

### Voice recordings, from the terminal

- [ ] Make some made-up test files, so that you can try the four kinds without using your own recordings. This writes only a new folder, and refuses if it is already there:
  <!-- snippet: make-test-files -->
  ```bash
  python3 - ~/ack-voice-check/import-test <<'EOF'
  import math, struct, sys, wave
  from pathlib import Path

  root = Path(sys.argv[1]).expanduser()
  if root.exists():
      print("This folder is already there, so nothing was made:", root)
      sys.exit(1)
  SENTENCES = ["The tide came in slowly.", "It rained all day long.", "Gulls circled over the pier."]

  def tone(path, pitch):
      path.parent.mkdir(parents=True, exist_ok=True)
      rate, seconds, frames = 22050, 2.4, bytearray()
      for n in range(int(rate * seconds)):
          t = n / rate
          frames += struct.pack("<h", int(math.sin(2 * math.pi * pitch * t) * 0.4 * 32767) if 0.3 <= t < seconds - 0.3 else 0)
      with wave.open(str(path), "wb") as handle:
          handle.setnchannels(1)
          handle.setsampwidth(2)
          handle.setframerate(rate)
          handle.writeframes(bytes(frames))

  for i, sentence in enumerate(SENTENCES, 1):
      tone(root / "pairs" / ("%03d.wav" % i), 200 + 20 * i)
      (root / "pairs" / ("%03d.txt" % i)).write_text(sentence + "\n", encoding="utf-8")
      tone(root / "table" / "wavs" / ("%03d.wav" % i), 300 + 20 * i)
  (root / "table" / "metadata.csv").write_text("".join("%03d|%s\n" % (i, s) for i, s in enumerate(SENTENCES, 1)), encoding="utf-8")
  for i in (1, 2):
      tone(root / "audio" / ("clip%d.wav" % i), 400 + 20 * i)
  tone(root / "mixed" / "good.wav", 560)
  (root / "mixed" / "broken.wav").write_bytes(b"This is not really sound. " * 40)
  print("made:", root)
  EOF
  ```
  → `made: …/ack-voice-check/import-test`: four folders, `pairs` (three `.wav` and three `.txt`), `table` (three `.wav` in `wavs` and one `metadata.csv`), `audio` (two `.wav`) and `mixed` (one good `.wav` and one `broken.wav` that is not sound at all). They are tones, not speech: they are enough to see how the tool brings files in, not how the computer hears them (that needs your own voice, below).
- [ ] Look at the project's recordings. This changes nothing:
  ```bash
  PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.recordings show --project voice-check
  ```
  → `There are no recordings in this project yet.` (or what the project already has) and `To bring recordings in, run: …`
- [ ] **The kind is never guessed.** Leave `--kind` out:
  ```bash
  PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.recordings import ~/ack-voice-check/import-test/pairs --project voice-check
  ```
  → `Say what kind of data it is, with --kind. The choices are:` and four lines, `package`, `pairs`, `table` and `audio`, each with what it means. Nothing is read and nothing is written.
- [ ] **Audio files with a text file each, and say no.** The tool shows what it found before it asks:
  ```bash
  PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.recordings import ~/ack-voice-check/import-test/pairs --kind pairs --project voice-check
  ```
  → `Looked at pairs (Audio files, each with a text file).`, `Found 3 audio files.`, `3 audio files would be added, about 0.1 minutes.`, `3 of them come with a sentence.`, `The sentences you give are kept as a check. The computer listens too, and marks a piece if it hears something different.` and `Add 3 files to Voice check? Type yes to go on.`
  Type **`no`**: `Nothing was done.` Check that the project has nothing new: `PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.recordings show --project voice-check` still says there are none, and the folder you chose is exactly as it was (`ls -l ~/ack-voice-check/import-test/pairs`).
- [ ] Run the same command and type **`yes`**. → `3 audio files were added.`, `1 recording was made from them.` and `Next, let the computer listen to them. Run: …` (the three short files are joined, with a short quiet gap, into one recording, as ACK does for a script). Then run it a **third** time: it should say `3 files are already in this project and will be skipped.` and
  `There is nothing new to add. Nothing was done.` with **no question**: a file is recognised by its content, so a second run or a renamed copy adds nothing.
- [ ] **A table of sentences.** Name the kind `table`; the tool finds `metadata.csv` by itself:
  ```bash
  PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.recordings import ~/ack-voice-check/import-test/table --kind table --project voice-check
  ```
  → `Looked at table (Audio files with one table of sentences).` and `3 of them come with a sentence.` Type **`yes`**. Then the same folder with the **wrong** kind, `--kind audio`, and say **no**: it says `The computer will listen to them and write down what it hears.` and shows no sentences, so a wrong choice is visible before anything is added.
  And `--kind pairs` on the `audio` folder says `None of them came with a sentence, so the computer will write them all itself. Check that you chose the right kind.`
- [ ] **Audio only.** `PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.recordings import ~/ack-voice-check/import-test/audio --kind audio --project voice-check`, **yes**. → `2 audio files were added.` and `2 recordings were made from them.` (a file with no sentence is a recording of its own). Look: `PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.recordings show --project voice-check`. → the counts, each recording with `waiting to be listened to`, and
  `To let the computer listen to the waiting recordings, run: …`
- [ ] **A file that cannot be used.** The `mixed` folder holds one good file and one that is not sound at all:
  ```bash
  PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.recordings import ~/ack-voice-check/import-test/mixed --kind audio --project voice-check
  ```
  Type **`yes`**. → It adds what it can and names what it left out: `1 audio file was added.`, then `broken.wav: the computer could not read the sound` and `1 file was left out.` The one good file is not stopped by the bad one, and the bad one is left where it was.
- [ ] **Your own voice, the real test.** Put three or more of your own recordings (any common audio format: `.wav`, `.mp3`, `.m4a`, `.ogg`, `.flac`), each saying one sentence, in `~/ack-voice-check/import-test/real`, and beside each a text file of the same name that holds that sentence. Import it as `--kind pairs`. Write down: whether your file formats were accepted, and
  what happened with any that were not. **An ACK package from the phone** is brought in with `--kind package` and the zip file's path: it shows each session (Script or Free speech) and asks as above; the same package a second time says there is nothing new, and a package you decline leaves no copy of itself inside the project.
- [ ] **Get the listening model.** The guided setup step (`python3 -m voice_studio`) only checks this computer's system packages; it does not download the model. The listening model is looked for in two places, in this order: the tool's own folder (`~/ack-voice-studio/tool/downloads/models/speech-small-en`) and the Hugging Face folder (`~/.cache/huggingface/hub`, where section E's `models fetch small.en` puts it); a copy in the second is used only if every file has exactly the agreed size and checksum, and nothing is copied, moved or changed. To see what is there, or to get it:
  ```bash
  PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.recordings model
  ```
  → If it is already on this computer: `The listening model is already on this computer, in …` and `Nothing was downloaded.` Otherwise it says what it is and where it comes from (`The listening model lets the computer write down what it hears in your recordings.`, then its size, the site and the folder it will be kept in, and `Your recordings are not sent anywhere.`) and asks `Download the listening model now? Type yes to go on.` Type **`no`**: `Nothing was done.` and nothing is downloaded or saved. Run it again and type **`yes`**: `Saved your agreement to download these files.`, then a line for every 10 percent, then `Done. The listening model is on this computer, in …` and `Every file was checked against the one that was agreed to.` Run it a third time: it says it is already there and downloads nothing. Press Ctrl+C in the middle of a download and run it again: it carries on from what had arrived. Write down: how long it took, and whether a line was too long for your screen.
- [ ] **Let the computer listen.** This needs the studio programs (section I0 or the guided setup) and the listening model (the step above); if one is missing the tool says which, and what to run, and does nothing. If the model is in neither place: `The listening model is not on this computer yet. To get it, run: python3 -m voice_studio.recordings model`, then `It was looked for in …`. If the tool's own folder holds some of the files, or one that is not what was agreed (for example a download that was cut short), it says `The listening model in ~/ack-voice-studio/tool/downloads/models/speech-small-en is not complete, or a file in it is not what was agreed to. Nothing was changed or deleted. To fetch what is missing, run: python3 -m voice_studio.recordings model` (with the folder's full path):
  ```bash
  PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.recordings finish --project voice-check
  ```
  → `5 recordings are waiting to be listened to.` (the test files make five; yours may differ), what it will do, `Start listening now? Type yes to go on.` Type **`no`**: `Nothing was done.` Run it again and type **`yes`**: `Listening has started (…).` and `To see how it is going, run: …`. You can close the terminal: it carries on by itself. Run `PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.recordings show --project voice-check` every minute: `The computer is listening to the recordings now.` and, for the one it is on,
  how far through it is. Run `finish` while it is still going: `The computer is already listening to this project's recordings. To see how it is going, run: …` and no second job starts. When it ends, `show` says `Ready:` with the number it finished. Write down: how long it took for how many minutes of audio, and what happened to the recordings made of tones (they have no speech, so expect
  them to be marked and left out of the training set).
- [ ] **See what a training set would hold.** This only looks:
  ```bash
  PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.recordings set --preview --project voice-check
  ```
  → `This is what the training set would hold. Nothing was written.`, `Pieces in it:` and the minutes of speech, `Pieces left out:` and for each reason how many (for example `left out, because they were flagged as doubtful`), how much usable speech there is against the hours you planned, and `That was only a preview. Nothing was written. To make the training set, run: …` Check that `ls ~/ack-voice-studio/projects/voice-check/scratch/datasets` shows nothing new.
- [ ] **Make it.** Without `--preview`, it shows the same and then asks, and writes only a new folder named from the time:
  ```bash
  PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.recordings set --project voice-check
  ```
  → `Make this training set now? It is written to a new folder. Type yes to go on.` Type **`yes`**: `The training set is ready.`, `The training set is in …` and the new folder named `dataset-` with the date and time, how many pieces it holds, and `To train on it, run: …` with the `rounds start --set` command from section I2, which now lists this set. Run `set` again: a **new** folder is made each time, and the earlier one is untouched.
  If the studio programs are not ready, the tool says so and what to run, and writes nothing.

### The same things in the window

- [ ] Start the window as in section I5. → **Eleven** pages on the left: Projects, Recordings, Training rounds, Hear the voice, Voice file, Backup, Free up space, Check the tool, Updates, Problem report and Display. It opens on **Recordings** when a project is opened.
- [ ] **Projects.** Press `New project…`, leave it empty and press `Make this project…`: the form stays open and says `Please fix these first:` with what is missing; what you typed is kept. Make `Second check` again (my own voice). A box shows the project and asks `Make this project?` with **No** where the focus starts. Then, with it chosen in the list, try `Edit details…`, `Put away…` (it leaves the list; tick `Show projects that are put away` and use `Bring back…`),
  `Show the folder`, and `Delete…`: it asks **twice**, and the first box lists what goes. Answer **No** to the second, then do it for real. Write down any button whose purpose was not clear, and whether a box ever left you unsure what would be changed.
- [ ] **Recordings.** Open the Recordings page. → `Recordings in Voice check`, the counts, one sentence on what to do next, and seven buttons: `Bring in recordings…`, `Get the listening model…`, `Let the computer listen…`, `See what a training set would hold`, `Make a training set…`, `Look again` and `Show the folder`. The two steps that need recordings are greyed out until there are some. `Get the listening model…` is never greyed out: press it, and the result window shows the same question as the terminal command (`Download the listening model now? Type yes to go on.`) with Yes and No buttons; answer **No** first and check that nothing was downloaded.
- [ ] Press `Bring in recordings…`. → A form: `What kind of data is it?` with four choices **and none chosen for you**, each with one line on what it is; `Where is it?`. Press `Look at it…` with nothing chosen: the form stays open and says `Choose what kind of data it is.` and `Choose where it is.` Choose **Audio files with one table of sentences**: a box for the table's file name appears (leave it empty).
  Choose **An ACK package**: only one button is left, for the zip file; choose **Audio files, each with a text file** again and the place you picked before is forgotten, so a folder is never taken for a package.
- [ ] Press `Choose the folder…`. → The system's own file chooser, in your Windows or Ubuntu look. Choose `~/ack-voice-check/import-test/pairs` (a folder that was already imported is fine: it will say there is nothing new; try `real` if you made it). The form shows the path. `Choose a zip file instead…` takes a zip of the same files.
  Press `Look at it…`. → The form closes, and the same box as in the terminal appears with what was found, then the terminal's question, `Add 3 files to Voice check? Type yes to go on.`, without its last sentence (the box has Yes and No buttons), with **No** where the focus starts. Press **No**: `Nothing was done.` Press it all again and **Yes**.
- [ ] After a yes the page lists the new recording as `waiting to be listened to` and `Let the computer listen…` is usable. Press it: the same questions as the terminal. While it listens the page says `The computer is listening now. This page looks again by itself every few seconds.` and shows how far it has got; nothing else starts by itself. When it ends, press `See what a training set would hold`, then `Make a training set…`.
  → Same words as the terminal. Open **Training rounds**: the new set is in the list of sets. Write down: whether the file chooser was easy to use, how long the page took to notice the listening had ended, anything that moved or flashed, and whether any word was hard to understand.
- [ ] **A screen reader, if you use one:** move through the form with Tab. Write down what is read for each of the four kinds, `Choose the folder…`, and the problems that appear when the form is not whole.
- [ ] Clean up what this section made: `rm -r ~/ack-voice-check/import-test`. The recordings you imported are inside the project, `~/ack-voice-studio/projects/voice-check/recordings`, and stay until you delete the project or remove them yourself; `second-check` is already gone (section M has the rest).

## I7. Installing from scratch, with the two installation guides

**New, and not yet run on a clean Windows or on a native Ubuntu.** The guides are `docs/ACK_Voice_Studio_Installation_Guide.MD` (Windows, from PowerShell) and `docs/ACK_Voice_Studio_Installation_Guide_Ubuntu.MD`. They stand on their own, so do this
section **with only the guide open**, as a person who has nothing else would. Write down every sentence in a guide that is unclear, and every command that did not do what the guide said. Until a release is tagged the commands fetch
`main`, so this can only be run after the branch is merged; before that, use `-Ref claude/voice-studio-guided-setup` (Windows) or `ACK_VOICE_TAG=claude/voice-studio-guided-setup` (Ubuntu), and say so when you write results down.

**A. A Windows that has never had WSL** (a spare computer, or one where `wsl --list` says there is none). Everything here is the Windows guide's section 2 and 3.

- [ ] **Look only.** In an ordinary (not administrator) PowerShell:
  ```powershell
  $env:ACK_VOICE_CHECK = '1'
  irm https://raw.githubusercontent.com/ASPDesignLabs/ACK/main/tools/voice_studio/install.ps1 | iex
  Remove-Item Env:ACK_VOICE_CHECK
  ```
  → `Looking at this computer. Nothing is changed at this step.`, a line for the Windows build, the Nvidia driver (or the note that there is none) and the free room, then `WSL (Windows Subsystem for Linux) is not set up on this computer yet.`,
  `It would install Ubuntu 24.04 with: wsl --install -d Ubuntu-24.04` and `Not ready yet. Run the same command without -Check to set it up.` **Your PowerShell window must still be open afterwards** (the script must not close it). Check that nothing was installed: `wsl --list` still says there is nothing.
- [ ] **Dry run.** The same with `ACK_VOICE_DRYRUN` instead. → `Nothing was changed. This is what would run:` and the `wsl.exe` lines, one of them the Ubuntu command in double quotes. Nothing runs.
- [ ] **Without administrator rights.** Run the one command with no setting. → The first look, then `Installing WSL needs PowerShell opened as administrator.` and it stops. Nothing was installed.
- [ ] **A no.** In an administrator PowerShell, run the one command and type `no` (or press Enter) at `Install WSL and Ubuntu 24.04 now? It downloads Ubuntu from Microsoft, needs administrator rights, and needs a restart afterwards. Type yes to go on.` → `Nothing was done.`
- [ ] **The real install.** Again in the administrator window, type `yes`. → `Installing Ubuntu. Windows shows its own progress. When Ubuntu asks for a user name and a password, choose them: they are for Ubuntu only.` Write down: whether Windows asked for a restart, whether Ubuntu opened by itself and asked for a user name,
  and the exact lines Windows printed. If it says `WSL is installed but needs the computer to restart first. Restart it, then run the same command again. It carries on from here.`, restart.
- [ ] **No user yet.** If you did not finish Ubuntu's first run, run the command in an ordinary PowerShell. → `Ubuntu is installed but has no user yet.` and the instructions; it starts nothing. Open Ubuntu 24.04 from the Start menu, choose a user, close it.
- [ ] **The hand-over.** (The first real run, 2026-10-12, printed nothing between "Starting the Ubuntu part" and "The Ubuntu part has ended" and stopped with code 2; the cause was found and fixed, so this is the first check of the fix: everything Ubuntu says must now appear in your window as it happens.) If an older copy of ACK is already in Ubuntu (a computer that has been used for testing), expect a sentence saying the copy is not the same as the release asked for, then `Update the copy now? Type y for yes, or press Enter to use it as it is:`; answer y and write down what it printed. Run the one command in an ordinary PowerShell. → `Ubuntu found: Ubuntu-24.04.`, then `Starting the Ubuntu part. Ubuntu will ask for the password you chose, in this window, to install a few Ubuntu programs.` Write down, in this order: whether `git` was offered,
  whether the password prompt accepted typing, whether `y` and `yes` reach the questions (the Ubuntu script reads its answers from the terminal), whether Ctrl+C stops it and the same command carries on, how long each set of programs took, and where it first looked slow.
- [ ] **The window.** → `The Ubuntu part has ended.`, then `Opening the window. Leave this PowerShell window open while you use Voice Studio: closing it closes the Voice Studio window. When you close the Voice Studio window, this PowerShell window is free again.` The Voice Studio window appears on the Windows desktop and the PowerShell prompt does **not** come back yet. Write down how long after that line the window appeared. Close the Voice Studio window: → `The Voice Studio window was closed.` and the prompt returns.
- [x] **Why PowerShell stays busy.** Result (2026-10-12, the developer's own Windows, build 26200, Ubuntu 24.04): the window appeared on its own, PowerShell stayed busy while it was open, and closing only the PowerShell window closed the Voice Studio window at once. So the design is needed as it is: PowerShell must stay attached, and the helper must not let it go free after opening the window. Repeat once on a clean Windows (section A) to see whether it is the same there.
- [ ] **Again.** Run the one command a second time. → It finds Ubuntu, finds everything in place and opens the window without installing or downloading anything.

**B. A Windows that already has Ubuntu (the developer's own).**

- [ ] The one command goes straight to `Ubuntu found: …` with no question before the Ubuntu part, and the Ubuntu part ends at the window.
- [ ] `-Distro Ubuntu-22.04` (or the other one) uses that one; `-Distro Debian` is refused with `The name Debian is not an Ubuntu name. …` and nothing runs.

**C. A native Ubuntu desktop, 22.04 and then 24.04.** This is the Ubuntu guide's section 2.

- [ ] Run its one command in a terminal. → `Looking at this computer. Nothing is changed at this step.`, the list of Ubuntu programs, `Install these now? Type y for yes, or press Enter for no:`, then the steps in the guide's section 3. Write down every difference from the guide.
- [ ] `--dry-run` after `bash -s --` prints what would run and installs nothing.
- [ ] After the window opens, run `PYTHONPATH=~/ack-tools/tools /usr/bin/python3 -m voice_studio.window --install-launcher`. → The applications list gets an entry. Does it open the window?
- [ ] A job that trains, with the terminal closed: does it keep running? (This was not tested on native Ubuntu; on WSL it stops by default.)

**D. The guides.** Read each guide once more from the top and tick: every command worked as typed; every quoted sentence appeared; every button has the name the guide gives it; nothing needed another file.

## I8. Hearing the voice before it goes to the phone

**New, and not yet run on a real computer.** This plays three short sentences in the voice file you made in section I4, on this computer, with the same speech engine (sherpa-onnx 1.13.8), the same list of sounds and the same settings file that ACK uses on the phone. It is for judging a round and for checking the voice file by ear before it is sent. It makes one new folder of small sound files in the project's own `listening` folder (kept with the project and the training they came from: one folder for each round or voice file, and inside it one for each time), changes nothing that was there, and uses no network after the engine is installed. It can also write down what the computer hears in each sound and show it beside the sentence (part D), and listen straight to a round with no zip file (part E). It needs two things: the studio programs rebuilt (they gained the speech engine; part A) and the training programs (they carry the pronunciation data). **Nothing about sound from this tool has been seen on a real computer yet, so part B comes first: it decides how the tool plays.**

*Built and tried in the build sandbox only, with a stand-in for the voice's network and a real public-domain voice: the real engine, the real patcher and the real pronunciation data made three sentences that the listening model heard back word for word, offline, in about 45 seconds. Round mode (part E) was tried only with stand-ins for the export and the patcher. Not heard by a person, and not played through a speaker.*

**A. The studio programs gained the speech engine.**

- [ ] Look, then build. The studio lock changed, so the programs are built again beside the old ones (nothing is deleted). It asks once and downloads about 145 MB from the package site only:
  ```bash
  PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.buildenv studio --check
  PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.buildenv studio
  ```
  → The first says the studio programs need setting up (the lock changed); the second shows what it will do, asks, and ends ready with the self-test passing. Write down how long it took and the size of the new folder (`du -sh ~/ack-voice-studio/tool/environments/studio-*`). Your old studio folder is still there; say whether that surprised you.

**B. Does sound come out of this computer at all?** One block. It makes a one-second tone in a temporary folder, plays it each way the tool might play it, and removes the folder. A line saying `command not found` only means that way is not installed here. Write down, for each way, whether you **heard** the tone and what `exit` number it printed (0 is a normal end; hearing it is what matters).

- [ ] Run it with your speakers on and the volume up a little:
  ```bash
  T=$(mktemp -d) && ffmpeg -v error -f lavfi -i "sine=frequency=440:duration=1" "$T/tone.wav" && ls -l "$T/tone.wav"
  pw-play "$T/tone.wav"; echo "pw-play exit: $?"
  ffplay -nodisp -autoexit -loglevel error -i "$T/tone.wav"; echo "ffplay exit: $?"
  paplay "$T/tone.wav"; echo "paplay exit: $?"
  aplay -q "$T/tone.wav"; echo "aplay exit: $?"
  powershell.exe -NoProfile -NonInteractive -Command "(New-Object System.Media.SoundPlayer '$(wslpath -w "$T/tone.wav")').PlaySync()"; echo "windows exit: $?"
  rm -r "$T"
  ```
  → A tone of one second for each way that works. The last line is for WSL only (it asks Windows' own player, which needs Ubuntu to be able to start Windows programs). Write down: which ones you heard, which printed something other than 0, any words they printed, and (WSL) whether Windows showed anything.

**C. The command.**

- [ ] Look, and say no:
  ```bash
  PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.voicefile listen --project voice-check
  ls ~/ack-voice-studio/projects/voice-check/listening
  ```
  → `The voice file would be heard like this:` and under it the voice file it will use, the three sentences (Hello, my name is Anna. I need some help, please. Thank you, that is all.), the new folder, and the room check. Then `Make the sound files and play them now? Type yes to go on.` Type **`no`**: `Nothing was done.` and the `ls` finds nothing new. **Write down whether you want different sentences** (they are proposals, see the plan) and whether the plan read clearly.
- [ ] Run it and say yes:
  ```bash
  time PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.voicefile listen --project voice-check
  ```
  → `Getting the voice ready.`, `Making the sounds. This takes a few seconds.`, `The sound files are ready in …`, a line for each sentence with how long it is, then `Playing 1 of 3: Hello, my name is Anna.` and the sentence is heard, then 2 and 3. A line that starts `Technical detail:` says `played with` and the name of the way that played them, and then `Did you hear them all? Type yes if you did.` Answer honestly: **no** is a fine answer and tells the tool nothing is wrong with the voice. Write down: the seconds it took in all, which way played (it should be one of the ways you heard in part B), whether it was clear and in the voice you expect, and anything it mispronounced.
  If it says `No way of playing sound worked on this computer.`, copy that line and the `tried:` line under it, and open the folder from Windows (File Explorer) to play the files there.
- [ ] Look at what it made, and what it left alone:
  ```bash
  ls -l ~/ack-voice-studio/projects/voice-check/listening/*/*/
  head -3 ~/ack-voice-studio/projects/voice-check/listening/*/*/tokens.txt
  ls -l ~/ack-voice-studio/projects/voice-check/exports/*/
  ```
  → The new folder (named `heard-` and the date and time, inside a folder named after the voice file) holds `clip-1.wav`, `clip-2.wav`, `clip-3.wav`, `job.json` and `tokens.txt` (and `hear-job.json` once part D has run), all readable by you only (`-rw-------`). The first lines of `tokens.txt` are the voice's first sounds with their numbers. The voice file folder under `exports` has exactly the files it had (the model, its settings file, the original, the zip): nothing added, nothing changed.
- [ ] **The honest test: say the same sentences on the phone.** Take the zip to the phone (section K), choose MY VOICE, and say the same three sentences. Write down any word that sounds different on the phone from the computer. The phone has its own copy of the pronunciation data; for English the two were identical on thousands of words in the build sandbox, but nobody has compared them on your phone.
- [ ] Listen to a named voice file, and to a second run a minute later:
  ```bash
  PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.voicefile listen --project voice-check --folder voice-check-round-003-20261011-130000 --yes
  ```
  → Replace the folder name with one from `python3 -m voice_studio.voicefile list`. `--yes` skips the first question only; the question about hearing is still asked. A second run makes a second folder with a different time in its name, and the first is untouched. An unknown name says `That voice file folder was not found.`
- [ ] Write down: anything that felt slow, any sentence that was hard to follow, whether three sentences is the right number, whether you wanted to hear a sentence of your own, and whether you would use this before every export or only now and then.

**D. Writing down what the computer hears.** The same listening model that writes down your recordings (section E, `recordings model`) can listen to the sounds just made and show what it heard under each sentence. It is a hint, not a verdict: it can mishear names and unusual words, and what you hear matters more. It works for English voices only, runs on this computer only, and is skipped, with the reason, when the model is not here.

- [ ] Without the model (skip this if you already fetched it): run `listen` and say **no**. → `skip writing down what the computer hears, because the program that does it has no model here yet.` and `To get it, run:` followed by the command `python3 -m voice_studio.recordings model`. Nothing else about the run changes.
- [ ] With the model: run `listen` and say **no** first. → the plan has the line `write down what the computer hears in each sound, so you can read it.` Then run it and say yes:
  ```bash
  time PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.voicefile listen --project voice-check
  ```
  → After `The sound files are ready in …` comes `Writing down what the computer hears in them. This takes up to a minute.` and then, before any sound is played, each sentence with a line under it that starts `The computer heard:` and ends `The same words.` or `Different words.` (or says `The computer could not write down any words here.`). If any line is not the same, `This is a hint, not a verdict.` follows once. Write down: how long this part took (the first time is the slowest), what it wrote for each sentence, and whether a line that said different was a real mispronunciation when you listened.
- [ ] If the listening step fails, the run goes on: `The computer could not write down what it heard.` and `The sound files were kept as they are.` are followed by the sounds being played as before. You are not asked to break anything on purpose; if you ever see it, copy the `Technical detail:` line under it.

**E. Listening straight to a round, with no zip file.** This makes the voice from a round's saved point in the new listening folder (the same three steps as the make command, so the export is the slow part), plays it, and then asks whether to remove the large voice copy it made. Nothing under `exports` is made or changed, and the round record is not touched.

- [ ] Look, and say no:
  ```bash
  PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.voicefile listen --project voice-check --round chosen
  ```
  → `would be heard like this:` with the round's number, the saved point's size and the minutes of training, `It uses the same steps as the make command, but makes no zip file`, the new folder, `at the end, ask whether to remove the voice it made here, which is large.`, and the room check (about 664 MB at most). Type **`no`**: `Nothing was done.`
- [ ] Run it, answer yes, hear them, and say **no** to the last question:
  ```bash
  time PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.voicefile listen --project voice-check --round chosen
  ```
  → `Making the voice from the saved point. This is the slow step.`, `Preparing it for the phone.`, then the same as part C, and last `Remove the voice made for this (…` Say **no**: `Kept. The voice made for this is still in …` with how big it is, `Free up space can remove it later.` and the command to run (`To remove it later from here, run:`). Look: `ls -l ~/ack-voice-studio/projects/voice-check/listening/round-*/*/` → the three sound files, `job.json`, `tokens.txt`, and `my_voice.onnx`, `my_voice.onnx.before-patch` and `my_voice.onnx.json`. Write down how long the export took and the size of the copy.
- [ ] Run it again with a round number (`--round 1`, or any other round), and this time say **yes** to the last question. → `Removed. The sound files are still in …`, and the folder holds only the sounds, `job.json` and `tokens.txt`. The first run's folder is untouched.
- [ ] Check that nothing else moved: `ls -l ~/ack-voice-studio/projects/voice-check/exports/*/` is as it was, and `python3 -m voice_studio.rounds list --project voice-check` shows the same chosen round.
- [ ] Mistakes are refused before anything is written: `--round 0`, `--round x` and `--round 99` each print a plain sentence (`I did not understand …` or `There is no round with that number in this project.`) and make nothing; `--round chosen --folder anything` says `Give --folder or --round, not both.`
- [ ] Write down: whether you would use this instead of making the voice file first, and whether the copy question was clear.

## I9. Backing up a project

**New, and not yet run on a real computer.** `backup` keeps the part of a project that cannot be made again in one checked file, in a folder you choose, away from the project: the project record and the consent note, the recordings and what was done to them, the packages that came from the phone, the record of training rounds and each round's settings, the saved points that are kept, and the finished voice files. It leaves out what can be made again or is only for listening: training sets and working files, the test sounds from section I8 and the voices made to hear them, older saved points, the trainer's logs, the tool's own programs, the starting voices and earlier backups.
**Nothing here removes or changes anything of yours.** A backup is always a **new** file in a folder outside every project, it is read all the way back before it counts, and an earlier backup is never replaced or removed by this tool. Putting a backup back only **adds** what is missing and never replaces a file; the step that does it is done in a pretend home folder, so your real project is not touched. The first steps write nothing. It uses the project from section I2 (any project that has a project record will do, and a small one is fine).

*Built and tried in the build sandbox only, with made-up recordings, rounds and saved points and a stand-in for the disk. Not tried on a real computer, on a Windows folder from WSL, or on a folder that a cloud service really syncs.*

**A. Look first. Nothing is written.**

- [ ] Read what it offers, then ask what is backed up so far:
  ```bash
  PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.backup help
  PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.backup list --project voice-check
  ```
  → The first prints `Commands:` and one line each for `now`, `list`, `verify` and `restore`. The second says `There are no backups of Voice check in …` and `To make one, run:` with the command, then `has not been backed up on this computer yet` (the project's own name first). Say whether the four lines were clear to you.

**B. The reminder, before a round and after recordings.** The tool reminds you, and nothing more: it never makes a backup by itself and never stops what you were doing.

- [ ] Ask to start a round, and say no. Do this only if section I2 left the project ready to start one; otherwise bring a package in again (section I6) and look at the end of what it prints:
  ```bash
  PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.rounds start --project voice-check
  ```
  → Before it asks whether to start, a line says the project `has not been backed up yet.` and `A backup keeps the recordings and notes safe if something goes wrong with this computer.`, and `To make one, run:` with the exact command. Type **`no`**. Write down whether the reminder was easy to notice or got lost among the other lines.

**C. See the plan, and say no.**

- [ ] Ask for a backup into a folder that is not there yet. `~/ack-voice-check-backups` is a folder only this list uses; on WSL a folder on the Windows side outside Documents and OneDrive is better (see part J):
  ```bash
  PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.backup now --project voice-check --to ~/ack-voice-check-backups
  ```
  → `A backup of Voice check would be made like this:`, then `keep these, one file at a time:` with a line for each part that is there (for example `The project record and the consent note`, with how many files and how big), then `leave these out, because they can be made again or are not needed:` with the training sets, the test sounds and older saved points and their sizes, when there are any, then where it will be written, that it will be `read it all the way back and check every file before it counts`, that it will `never remove or replace an earlier backup`, the room check, and `Make this backup now? Type yes to go on.` Type **`no`**: `Nothing was done.` and `ls ~/ack-voice-check-backups` says there is no such folder. Write down the sizes, the room figures, and whether the left-out list matches what you know is in the project.

**D. Make one.**

- [ ] Run the same command and type **`yes`**:
  ```bash
  PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.backup now --project voice-check --to ~/ack-voice-check-backups
  ls -l ~/ack-voice-check-backups
  ```
  → A line for each part as it is written, then `Reading the backup back and checking every file.`, then `The backup is made and checked:` with its path, how many files it holds, `Every file was read back and matched.` and its size, `Earlier backups in that folder were not touched. This tool never removes a backup.`, and the two commands to check it again and to put it back. The folder holds one `ack-project-backup-voice-check-<date>-<time>.tar` and a small `.tar.json` note beside it, both readable by you alone. Write down how long it took and the size of the file. A project with many hours of recordings is where the time will show.
- [ ] Look inside it. It is a plain `tar` file, so it does not need this tool to be opened, and the last thing in it is the list the tool checks it against:
  ```bash
  F=$(ls -t ~/ack-voice-check-backups/ack-project-backup-voice-check-*.tar | head -1)
  tar -tvf "$F" | head -20
  tar -tf "$F" | tail -n 1
  ```
  → The first lists paths such as `project/project.json`, `recordings/takes/…`, `rounds/rounds.json` and `exports/…`; the second prints `MANIFEST.json`. Nothing about scratch, `listening` or older saved points is in it.

**E. Look at it again, and at what the tool knows.**

- [ ] Check it, then list the backups:
  ```bash
  PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.backup verify "$F"
  PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.backup list --project voice-check --to ~/ack-voice-check-backups
  ```
  → `is whole. Every file in it matched, and nothing is missing or extra.` Then `Backups of Voice check in …` with one row for the file, and `Nothing precious in Voice check has changed since the last backup, made on …`. Run the part B command again: the reminder is gone.

**F. A backup with one byte changed must not pass.** This changes a **copy**, not the backup itself.

- [ ] Change one byte of a copy and check it:
  ```bash
  cp "$F" ~/ack-voice-check-backups/damaged-copy.tar
  printf 'X' | dd of=~/ack-voice-check-backups/damaged-copy.tar bs=1 seek=600 conv=notrunc 2>/dev/null
  PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.backup verify ~/ack-voice-check-backups/damaged-copy.tar
  ```
  → `damaged-copy.tar is not whole:` and a line that names `project/project.json` and says it `does not match its checksum`. Exit code 1 (`echo $?`). The copy is not listed by the `list` command (its name is not one the tool gives). Delete the copy: `rm ~/ack-voice-check-backups/damaged-copy.tar`.

**G. It notices that something changed.**

- [ ] Change the time on the project file (its contents stay the same; this is only a way to make the tool see a change), then look:
  ```bash
  touch ~/ack-voice-studio/projects/voice-check/project.json
  PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.backup list --project voice-check --to ~/ack-voice-check-backups
  ```
  → `has changed since the last backup` with the time of the last one and the folder it went to. (Bringing in recordings or finishing a round does the same.) Run the part B command again: the reminder now says the project has changed since the last backup, and when that was. A new backup is a new file; the earlier one is still there.

**H. It refuses clearly.** Neither command writes anything.

- [ ] Try a folder inside the project and a folder given without its full path:
  ```bash
  PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.backup now --project voice-check --to ~/ack-voice-studio/projects/voice-check/backups-here
  PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.backup now --project voice-check --to backups
  ls ~/ack-voice-studio/projects/voice-check
  ```
  → The first: `That folder is inside a project, so deleting the project would delete its backup too.`, `Nothing was made.` and `Choose a folder outside every project, such as a folder on another drive.` The second: `The backup folder was not given in full.` and `Give the whole path after --to, starting with a slash.` The `ls` shows no `backups-here` folder.

**I. Putting it back.** Nothing is replaced. The second command uses a pretend home folder, so it is the whole of a restore on a computer that has never seen this project, without touching yours.

- [ ] Put it back into the project that is there, then into the pretend home, and type **`yes`** to the second:
  ```bash
  T=$(mktemp -d)
  PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.backup restore "$F"
  PYTHONPATH=~/ack-tools/tools HOME="$T" python3 -m voice_studio.backup restore "$F"
  ```
  → The first says `Nothing needs putting back. Everything in the backup is already in the project.` and asks nothing. The second shows `make the project voice-check again, because it is not on this computer` and how many files it would add, asks `Put these back now? Type yes to go on.`, and after `yes` says `Done.` with the count and `Look at the project with:`.
- [ ] Compare what came back with what you have:
  ```bash
  cmp ~/ack-voice-studio/projects/voice-check/project.json "$T/ack-voice-studio/projects/voice-check/project.json" && echo same project record
  diff <(ls ~/ack-voice-studio/projects/voice-check/recordings/_freeform/en-US/takes) <(ls "$T/ack-voice-studio/projects/voice-check/recordings/_freeform/en-US/takes") && echo same takes
  ```
  → `same project record`, and `same takes` (or no output from `ls` on both sides if the project has no recordings). If you have rounds, `rounds list` in the pretend home shows the same rounds: `PYTHONPATH=~/ack-tools/tools HOME="$T" python3 -m voice_studio.rounds list --project voice-check`.
- [ ] Make the restored copy different, then put the backup back again. A file that differs is left exactly as it is:
  ```bash
  echo " " >> "$T/ack-voice-studio/projects/voice-check/project.json"
  PYTHONPATH=~/ack-tools/tools HOME="$T" python3 -m voice_studio.backup restore "$F"
  tail -c 3 "$T/ack-voice-studio/projects/voice-check/project.json" | od -c | head -2
  ```
  → A line saying it would `leave 1 file exactly as it is, because it differs from the backup's copy. The backup still holds its copy.` and `Nothing needs putting back. Everything in the backup is already in the project.` The `od` output still ends in the space you added. When you have looked: `rm -r "$T"`.

**J. Where to keep it.** A backup on the same drive as the project protects against a mistake, not against that drive failing.

- [ ] Ask for a backup without naming a folder, and say no. The folder used last is used (the first time, the tool's own folder, `~/ack-voice-studio/backups`):
  ```bash
  PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.backup now --project voice-check
  ```
  → `That folder is on the same drive as the project. It protects against a mistake, not against a drive that fails.` Under WSL, when exactly one Windows user is on this computer, the next line is `A folder on the Windows side, outside Documents and OneDrive, also works. For example:` with that user's folder; with two or more it says nothing about it. Write down which you got and whether the example folder is one you would use.
- [ ] **WSL only.** Ask for a folder inside OneDrive or Documents, and say no:
  ```bash
  PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.backup now --project voice-check --to /mnt/c/Users/YOU/Documents/ack-check
  ```
  → A line beginning `Note:` says the folder may be uploaded to a cloud service, because recordings of a voice are personal data. Nothing is written. Replace `YOU` with your Windows user name.

## I10. Checking the tool, and refreshing it

**New, and not yet run on a real computer.** `refresh` is a reinstall that does not wipe data. It looks at the tool's own programs, the files it downloaded and the small notes it keeps, mends only what is broken, and can build a second whole copy of the programs beside the one in use. **It never touches a project, a recording, a round, a finished voice file or a backup.** It has four commands: `check` only looks; `repair` mends what `check` found; `rebuild` builds the second copy; `older` lists the copies that are no longer in use and removes them when you say so. The first three parts below use a pretend home folder, so nothing of yours is damaged on purpose. Parts E to G use your real programs and need section I0 done (the small set of programs, the studio ones, is enough; the large training set is optional and says how much room it needs).

*Built and tried in the build sandbox only, with a stand-in for the computer and the network. The sandbox's own Python is newer than the programs accept, so the real command was only seen saying so there. Not run on a real computer.*

**A. Look. Nothing is written.**

- [ ] Look at everything, then look again without the programs' own check:
  ```bash
  time PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.refresh check
  PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.refresh check --quick
  ```
  → `Looking at the programs, the downloaded files and the tool's own notes. This changes nothing.`, a `Looking at …` line before each set of programs, the listening model and each starting voice you fetched, then one line for each thing: `[ok]`, `[problem]` or `[not here]` and a sentence such as `Every step is in place and its own check passed.` or `It is here and exactly what was agreed.` The last line is `Everything that is here is in order.` (or, if not, how many things need attention and the command to run). The second command has no `Looking at` line for the programs, because it does not run their own check. Write down how long the first took, and every line that surprised you.

**B. A note that cannot be read, in a pretend home.** `T` is a new empty folder; nothing in it is yours.

- [ ] Make a damaged note there and look:
  ```bash
  T=$(mktemp -d)
  mkdir -p "$T/ack-voice-studio/state"
  echo '{' > "$T/ack-voice-studio/state/environments.json"
  PYTHONPATH=~/ack-tools/tools HOME="$T" python3 -m voice_studio.refresh check
  echo "exit: $?"
  ```
  → `[problem] The note of which copy of the programs is in use: It cannot be read.`, `1 thing needs attention.` and `To mend what can be mended, run:` with the command. The programs and the downloads are `[not here]`, because this home has none (and the way to set the programs up is named). `exit: 1`.

**C. Mending it, which asks first.**

- [ ] Ask for the repair and say no, then yes:
  ```bash
  PYTHONPATH=~/ack-tools/tools HOME="$T" python3 -m voice_studio.refresh repair
  cat "$T/ack-voice-studio/state/environments.json"
  PYTHONPATH=~/ack-tools/tools HOME="$T" python3 -m voice_studio.refresh repair
  ls "$T/ack-voice-studio/state"
  ```
  → The first: `A repair would do this:` and `Set the note of which copy of the programs is in use aside under another name, beside itself. It is not deleted.`, then `Repair these now? Type yes to go on.` Type **`no`**: `Nothing was done.` and `cat` still prints `{`. The second, with **`yes`**: `Looking again.`, the note `was set aside as …environments.json.damaged-<date>-<time>`, and `Everything that is here is in order.` `ls` shows `environments.json.damaged-…` and no `environments.json`: the damaged note is kept, never deleted. With nobody to ask (a pipe, for instance) the command says `There was nobody to ask. To say yes on the command line, add --yes. Nothing was done.`

**D. A damaged download is not hidden, and is not replaced without the agreement.** Still the pretend home.

- [ ] Make a starting voice file that is not what was agreed (the real file is 846 MB; this one is 1,000 bytes of nothing) and ask for the repair:
  ```bash
  mkdir -p "$T/ack-voice-studio/tool/downloads/voices/voice-mike"
  head -c 1000 /dev/zero > "$T/ack-voice-studio/tool/downloads/voices/voice-mike/epoch=5460-val_mos=4.2686.ckpt"
  PYTHONPATH=~/ack-tools/tools HOME="$T" python3 -m voice_studio.refresh check --quick
  PYTHONPATH=~/ack-tools/tools HOME="$T" python3 -m voice_studio.refresh repair --yes
  ls -l "$T/ack-voice-studio/tool/downloads/voices/voice-mike"
  ```
  → `[problem] The starting voice Mike: The file is not what was agreed.` The repair says it would `Fetch the starting voice Mike again. The file in the way is replaced only after the new one has been checked.` and then `The download was not started because it has not been agreed to yet.` (this home has never agreed to the download), `The starting voice Mike could not be fetched again. The file that was there is as it was.` `ls` still shows the 1,000-byte file. Nothing was downloaded. When you have looked: `rm -r "$T"`.

**E. A second copy of the studio programs, beside the first.** Real. It downloads the studio programs again (the question says how much and from where) and needs that much free room.

- [ ] Note what is there now, then ask for the rebuild and say no:
  ```bash
  find ~/ack-voice-studio/projects -type f -printf '%p %s %T@\n' | sort | sha256sum
  du -sh ~/ack-voice-studio/tool/environments/*
  PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.refresh rebuild --programs studio
  ```
  → `A rebuild of the programs that listen to recordings would work like this:` and `It builds a second, whole copy beside the one in use, from the same list as before.`, `The copy in use keeps working until the new one is built and its own check has passed. If anything fails, nothing changes.` and `No project, recording, round, finished voice or backup is touched.` If a project has no up-to-date backup it says which, with the command (`These projects have no up-to-date backup. A rebuild does not touch them, but a backup costs little:`). Then the same plan and question the first setup gave: where, how much room, from which site. Type **`no`**: `The new copy of the programs that listen to recordings is not in use. The copy that was in use still is.` The first command's output is one line of letters and numbers; write it down.
- [ ] Do it, with **`yes`**:
  ```bash
  PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.refresh rebuild --programs studio
  du -sh ~/ack-voice-studio/tool/environments/*
  ```
  → The steps, each with how long it took, `Ready, after …`, then `The new copy of the programs that listen to recordings is now the one in use. The old copy is still on the disk.`, `1 old copy of the programs is on the disk:` with its folder and size, and `Remove this old copy, about …` Type **`no`**: `The old copy was kept. To remove it later, run:` and the command. `du` now shows two studio folders. Write down how long it took and how big each folder is.
- [ ] Check that everything works on the new copy and that no project was touched:
  ```bash
  PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.refresh check
  PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.buildenv studio --check
  find ~/ack-voice-studio/projects -type f -printf '%p %s %T@\n' | sort | sha256sum
  ```
  → `check` ends `Everything that is here is in order.` and its line for the note of which copy of the programs is in use says `It can be read.`; `buildenv` says `Nothing needs doing. It is in` the **new** folder; the last line of letters and numbers is the same as the one you wrote down.
- [ ] See the old copy, then remove it:
  ```bash
  PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.refresh older
  PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.refresh older --remove
  ```
  → The first lists the old copy, `it was complete`, and `To remove them, run:` the command. The second asks `Remove this old copy, about …`: type **`yes`**: `Done. 1 old copy was removed. About …` and how much room came back. `du -sh ~/ack-voice-studio/tool/environments/*` shows only the new folder. If a training round is running, the command refuses with `A task is running, and it may be using one of the old copies.` and removes nothing.

**F. Stopping a rebuild.** Optional.

- [ ] Start the rebuild again, say **`yes`**, and press Ctrl+C during a step. `check` still says the copy in use is fine. Run the rebuild again: it says `You already said yes to this, so it carries on from where it stopped and does not ask again. Press Ctrl+C to stop.`, and ends the same way as in part E. Write down whether the old copy was ever not usable.

**G. The training programs.** Optional, and only with a lot of free room (the question says how much; two copies exist until the old one is removed).

- [ ] The same as part E with `--programs training`. The old copy of the training programs is about 6.6 GB; write down the figure `older` prints.

## I11. Removing the tool's programs and downloads

**New, and not yet run on a real computer.** `uninstall` takes the programs the tool built and the files it downloaded off the disk, and nothing else. **It never touches a project, a recording, a round, a finished voice file, a backup, the starting voices you chose or the tool's small notes.** It has two commands: `show` only looks; `remove` shows the same list, asks once, and removes only what it showed. It cannot remove its own files or the menu entry itself, so it prints the commands that do. The first three parts below use a pretend home folder, so nothing of yours is at risk; the last part is real and optional, because the programs have to be built again afterwards.

*Built and tried in the build sandbox only, with a stand-in for the computer. Not run on a real computer.*

**A. Look at your real home. Nothing is written.**

- [ ] Write down what is in your projects, look, and write it down again:
  ```bash
  find ~/ack-voice-studio/projects -type f -printf '%p %s %T@\n' | sort | sha256sum
  PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.uninstall show
  find ~/ack-voice-studio/projects -type f -printf '%p %s %T@\n' | sort | sha256sum
  ```
  → `No project, recording, round, finished voice or backup is touched.`, `An uninstall would remove these programs and downloaded files:` and a row for each set of programs (`Programs`) and each download (`Downloaded file`) with its folder and size. Then `Together they take` the total, `These are kept:` with your projects, your backups, the starting voices you chose and the tool's small notes, and three lines of what it cannot do for itself: the menu entry, the folder of the tool's own files, and the command that removes the programs. The two lines of letters and numbers are the same. Write down the total and whether any row surprised you.

**B. A pretend home with things in it that must survive.** `T` is a new empty folder; nothing in it is yours.

- [ ] Make it, and look:
  ```bash
  T=$(mktemp -d)
  H="$T/ack-voice-studio"
  mkdir -p "$H/projects/anna/recordings" "$H/backups" "$H/state" "$H/tool/downloads/voices/voice-mike" "$H/tool/downloads/models/speech-small-en" "$H/tool/environments/somebody-elses"
  head -c 2000 /dev/zero > "$H/projects/anna/recordings/take.wav"
  head -c 3000 /dev/zero > "$H/backups/anna.tar"
  head -c 100 /dev/zero > "$H/state/consent.json"
  head -c 1000 /dev/zero > "$H/tool/downloads/voices/voice-mike/mike.ckpt"
  head -c 5000 /dev/zero > "$H/tool/downloads/models/speech-small-en/a.bin"
  head -c 700 /dev/zero > "$H/tool/downloads/archive.tar.gz"
  PYTHONPATH=~/ack-tools/tools HOME="$T" python3 -m voice_studio.uninstall show
  echo "exit: $?"
  ```
  → The two downloads (`archive.tar.gz` and `models`) are listed, and nothing else: not the starting voice, not `take.wav`, not the backup, not the note. `These are kept:` names your backups, the starting voices and the small notes. `1 other item in the tool's folders was left alone, because this tool did not make it or is still building it.` is the folder `somebody-elses`. `exit: 0`.

**C. Removing, which asks first.**

- [ ] Ask for the removal and say no, then yes:
  ```bash
  PYTHONPATH=~/ack-tools/tools HOME="$T" python3 -m voice_studio.uninstall remove
  find "$H" -type f -printf '%P\n' | sort
  PYTHONPATH=~/ack-tools/tools HOME="$T" python3 -m voice_studio.uninstall remove
  find "$H" -type f -printf '%P\n' | sort
  ls "$H/tool/environments"
  ```
  → The first shows the same list and asks `Remove these programs and downloaded files, about 5.7 KB, now? Setting them up again means downloading them again. Type yes to delete them.` Type **`no`**: `Nothing was done.` and `find` still lists all six files. With nobody to ask (a pipe, for instance) the command says `There was nobody to ask. To say yes on the command line, add --yes. Nothing was done.` and the exit number is 2. The second, with **`yes`**: `Done. The programs and downloaded files were removed. About 5.7 KB is free again. Nothing of yours was touched.` and `To set the tool up again later, run:` the command. `find` now lists exactly four files: `backups/anna.tar`, `projects/anna/recordings/take.wav`, `state/consent.json` and `tool/downloads/voices/voice-mike/mike.ckpt`. `ls` still shows `somebody-elses`. When you have looked: `rm -r "$T"`.

**D. A task that is running.** Optional, and only with a training round you can start and stop (section I2).

- [ ] While a round is running, ask for the removal:
  ```bash
  PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.uninstall remove
  ```
  → It shows the list, then `A task is running, and it may be using the programs.`, `Nothing was removed.` and `Wait for the task to finish, or stop it, then try again.` It does not ask the question. Write down whether the round carried on.

**E. The real removal, and setting up again.** Real, slow and optional. It removes the programs the tool built (about 6.6 GB for the training programs and the studio programs together) and the listening model, so the setup has to download them again. Do it last, and only on a computer where that is fine.

- [ ] Write down what is in your projects and the starting voices, remove, and look:
  ```bash
  find ~/ack-voice-studio/projects ~/ack-voice-studio/tool/downloads/voices -type f -printf '%p %s %T@\n' | sort | sha256sum
  df -h ~ | tail -1
  PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.uninstall remove
  df -h ~ | tail -1
  find ~/ack-voice-studio/projects ~/ack-voice-studio/tool/downloads/voices -type f -printf '%p %s %T@\n' | sort | sha256sum
  ls ~/ack-voice-studio/tool
  ```
  → Type **`yes`**. `Done.` and how much came back, which should be close to the total in part A. The two lines of letters and numbers are the same: no project and no starting voice changed. `ls` shows only `downloads`, and `df` shows more free room. Write down how long the removal took.
- [ ] Set the tool up again, with the one command the last line told you:
  ```bash
  PYTHONPATH=~/ack-tools/tools python3 -m voice_studio
  ```
  → The guided setup finds nothing built, shows what it will download and asks, as it did the first time (section I0). Say **`yes`** and let it finish. `PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.refresh check` ends `Everything that is here is in order.` Write down how long the setup took and whether your projects still list (`python3 -m voice_studio.projects list`).

**F. The menu entry and the tool's own files.** The command cannot do these for itself.

- [ ] If you made the menu entry (section I5), run the `--remove-launcher` line that `show` printed. It lists what it will remove and asks: `Remove them now? Type yes to remove them.` Type **`no`** unless you mean it. On WSL it also prints the `sudo rm` line for the copy in the system folder; the tool never runs it.
- [ ] The line `This tool's own files are in` names the folder the tool runs from, and the `rm -r` command that removes it. **Do not run it** unless you want the tool gone: it removes the tool, not your projects (they are in `ack-voice-studio`, a different folder). If that folder is a copy you work in, keep it.

## I12. Moving a project's scratch to another place

**New, and not yet run on a real computer.** Scratch is where a project keeps its training sets and each round's working files; it can be inside the project (the default) or on another drive you choose (the plan's decision D24). `scratch` says where it is and moves it. **It never touches a recording, a round or a finished voice file.** `show` only looks. `move` checks the new place with the same rules as a new project, shows what it will do, asks once, copies every file and reads each one back, checks the whole copy again, and only then points the project at the new place. The old place is not touched; it asks about that at the end, with a second typed yes. The first three parts below use a pretend home folder, so nothing of yours is at risk; the last parts are real and optional.

*Built and tried in the build sandbox only, on folders on one disk. Not run on a real computer, and never on a second drive.*

**A. A pretend project with some scratch in it.** `T` is a new empty folder; nothing in it is yours.

- [ ] Make it and look. The last line before `show` is one line of letters and numbers: it stands for every file in the scratch.
  ```bash
  T=$(mktemp -d)
  H="$T/ack-voice-studio"
  PYTHONPATH=~/ack-tools/tools HOME="$T" python3 -m voice_studio.projects new --own --name "Scratch check" --yes
  P="$H/projects/scratch-check"
  mkdir -p "$P/scratch/datasets/d1/wav" "$P/scratch/caches/d1-r001" "$T/drive"
  head -c 4000 /dev/zero > "$P/scratch/datasets/d1/wav/a.wav"
  head -c 3000 /dev/zero > "$P/scratch/datasets/d1/wav/b.wav"
  echo "a.wav|hello" > "$P/scratch/datasets/d1/metadata.csv"
  head -c 9000 /dev/zero > "$P/scratch/caches/d1-r001/mels.bin"
  (cd "$P/scratch" && find . -type f -exec sha256sum {} + | sort -k2 | sha256sum)
  PYTHONPATH=~/ack-tools/tools HOME="$T" python3 -m voice_studio.scratch show
  echo "exit: $?"
  ```
  → `Made the project scratch-check.` and then, from `show`, `The scratch of Scratch check is the folder inside the project: …` with its folder, the number of files and their size (4 files, about 16 KB), how much room that drive has, and `To move it, run: …` the command. `exit: 0`. Write the line of letters and numbers down.

**B. A place that cannot be used.**

- [ ] Ask for a place inside the project, and for a short name instead of a folder:
  ```bash
  PYTHONPATH=~/ack-tools/tools HOME="$T" python3 -m voice_studio.scratch move --to "$P/inside" --yes
  echo "exit: $?"
  PYTHONPATH=~/ack-tools/tools HOME="$T" python3 -m voice_studio.scratch move --to backup --yes
  echo "exit: $?"
  ls -A "$T/drive"
  ```
  → Each says `That place cannot be used:` with the reason (`That folder is inside this project's own folders. Choose somewhere else.` and `Please choose a folder from the list rather than typing a short name.`), then `Nothing was done.` Both are `exit: 2`, and `ls` shows nothing was made in the drive folder.

**C. Moving, which asks first.**

- [ ] Ask for the move and say no, then yes (and then no to the second question):
  ```bash
  PYTHONPATH=~/ack-tools/tools HOME="$T" python3 -m voice_studio.scratch move --to "$T/drive"
  find "$T/drive" -type f | sort
  PYTHONPATH=~/ack-tools/tools HOME="$T" python3 -m voice_studio.scratch move --to "$T/drive"
  (cd "$T/drive/ack-voice-scratch/scratch-check" && find . -type f ! -name .ack-voice-scratch -exec sha256sum {} + | sort -k2 | sha256sum)
  PYTHONPATH=~/ack-tools/tools HOME="$T" python3 -m voice_studio.scratch show
  ```
  → The first shows `Moving the scratch of Scratch check:` with `From:` and `To:`, the size, `This is the same drive as the project, so it will not save any room.` (it is the same disk here), the three sentences of how it works, and `Move the scratch now? Type yes to go on.` Type **`no`**: `Nothing was done.` and `find` lists nothing. With nobody to ask (a pipe, for instance) it says `There was nobody to ask. To say yes on the command line, add --yes. Nothing was done.` and the exit number is 2. The second, with **`yes`**: `Copied 1 of 4 files.` and so on to 4, `The copy is made and checked: 4 files copied now, 0 already there.`, a line saying that Scratch check now uses the new folder for its scratch, `The old place still holds 4 files, about 16 KB: …` and its folder, and `Remove the old place now? It is not used any more. Type yes to delete it.` Type **`no`**: `The old place was kept.` and the command that would remove it. The line of letters and numbers is **the same** as in part A, `show` now says `The scratch of Scratch check is in the place you chose: …` and the new folder, and the old files are all still there.

**D. Moving back, which reuses what is there.**

- [ ] Move it back inside the project:
  ```bash
  PYTHONPATH=~/ack-tools/tools HOME="$T" python3 -m voice_studio.scratch move --default
  (cd "$P/scratch" && find . -type f -exec sha256sum {} + | sort -k2 | sha256sum)
  ```
  → The same plan and question; with **`yes`**, `The copy is made and checked: 0 files copied now, 4 already there.`, because the old files were never removed. Say **`no`** to the second question again. The line of letters and numbers is the same as in part A. When you have looked: `rm -r "$T"`.

**E. A task that is running.** Optional, and only with a training round you can start and stop (section I2).

- [ ] While a round is running, ask for a move of that project:
  ```bash
  PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.scratch move --to /tmp --yes
  ```
  → `A task for this project is running, and it is using the scratch.`, `Nothing was moved.` and `Wait for the task to finish, or stop it, then try again.` It checks this before it looks at the place, and nothing is copied. Write down whether the round carried on.

**F. A real second drive.** Real and slow; it needs a second drive with room for the project's scratch. On WSL a Windows drive is under `/mnt`, for example `/mnt/d`; on Ubuntu itself a USB drive is under `/media`. Use a folder on that drive, not the whole drive.

- [ ] Look, then move, and write down how long it took:
  ```bash
  PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.scratch show
  time PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.scratch move --to /mnt/d/ack-scratch-check
  ```
  → `show` says how much the scratch holds (the training set is a few hundred files; a round's working files are several GB). The move names the drive's warnings in words (a Windows drive under WSL says `This is a Windows drive seen from WSL. It is much slower than Ubuntu's own disk.`; a drive that can be unplugged says so), and checks the room (`There is not enough room there.` if it is not). Answer **`yes`** and note the time, the seconds a file takes, and whether the lines `Copied n of m files.` came steadily. Say **`no`** to the second question.
- [ ] Start a round on the new place (section I2) and let it run a minute, then stop it. → The round starts and its working files appear under `ack-scratch-check` on that drive, not inside the project.
- [ ] Unplug the drive, or rename the folder `ack-scratch-check/ack-voice-scratch` to something else, and look:
  ```bash
  PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.scratch show
  PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.rounds start
  ```
  → `show` says `Its drive does not seem to be plugged in, so no training will start until it is back.` and `rounds start` says `The place chosen for this project's working files is not ready, and nothing was started. If it is a drive, check that it is plugged in.` Put the drive back, or the name back.
- [ ] Move the scratch back inside the project, and remove the old place on the drive:
  ```bash
  PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.scratch move --default
  ```
  → The copy says `0 files copied now` for every file that was already in the project's scratch and copies the rest; then type **`yes`** to `Remove the old place now? It is not used any more. Type yes to delete it.` → `Done. The old place is removed.` The drive's folder `ack-scratch-check` is left (the tool never removes a place you gave it); remove it yourself when you have looked.

## I13. Updating the tool

**New, and not yet run on a real computer.** `update` looks at the releases of this tool and fetches one into a **new folder** beside the copy you run (the plan's decisions D11 and P21). A release is a git tag whose name begins with `voice-studio-` (the phone app's tags, `v1.0-beta.1` and the rest, are a different thing and are left out). It is the one command in this list that contacts the internet when you ask it to: it says first what it will ask github.com and shows the exact commands, then asks (a typed yes, or `--yes`), and with nobody to ask it contacts nothing and does nothing. **It never touches the copy it runs from, your projects, your recordings or your backups.** It cannot switch to the new copy for you, because it cannot replace the folder it is running from: it prints the commands, and you type them. **ACK Voice Studio has no named release yet** (ACK's repository holds only the phone app's tags, which are not releases of this tool), so until someone makes a tag that begins with `voice-studio-` on GitHub, `check` says there is nothing to fetch and `get` cannot be tried on the real address (parts C to F say what to do then).

*Built and tried in the build sandbox only, against a git repository made on the same computer with the tags `voice-studio-v1.0` and `voice-studio-v1.1` (listed as `v1.0` and `v1.1`) and one phone-app tag that was left out. Not run on a real computer, never over a real connection and never against github.com.*

**A. Nothing is contacted.** These ask nothing of the internet, so they are safe to run anywhere.

- [ ] Look at the help, then ask for the list and for a release with nobody to ask, and give a name that cannot be a release:
  ```bash
  PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.update help
  PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.update check </dev/null
  echo "exit: $?"
  PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.update get </dev/null
  echo "exit: $?"
  PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.update get "no good" --yes
  echo "exit: $?"
  ```
  → `help` lists `check` and `get` and ends with `Nothing is contacted unless you say yes, nothing is checked in the background, and --yes answers the one question of that run only. No project, recording or backup is touched.` `check` says `ACK Voice Studio: update`, which version and folder this copy is, `It contacts the internet to ask which releases of ACK Voice Studio exist, and to fetch one when you choose.`, `Like any request on the internet it carries this computer's address and the name of the program asking. Nothing you recorded, typed or made is sent, and nothing is saved.`, the exact command it would run, `Only tags whose names begin with voice-studio- are releases of this tool. ACK's repository also holds the phone app's tags, and those are left out.`, and `There was nobody to ask. To say yes on the command line, add --yes. Nothing was done.` with `exit: 2`. `get` with no name says `Say which release to fetch, for example: …` and `Nothing was done.` (`exit: 2`). The last says `A release name is made of letters, numbers, dots, dashes and underscores only.` and `Nothing was done.` (`exit: 2`). Check the copy was not touched: `git -C ~/ack-tools status --short` prints nothing that you did not change yourself.
- [ ] Ask for a folder that is not a whole path, and for one that exists already:
  ```bash
  PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.update get v1.0 --to relative/folder --yes
  echo "exit: $?"
  PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.update get v1.0 --to /tmp --yes
  echo "exit: $?"
  ```
  → The first says `Give the whole path after --to, starting with a slash. Nothing was done.` The second says `Something is already at the folder the copy would go to.`, `Nothing was downloaded, and what is there was left as it is.` and `Choose another folder with --to, or remove that one yourself.` Both are `exit: 2`, and `ls /tmp` still shows what it showed.

**B. A computer without git.** The tool needs git to fetch a release, and says so before it asks anything.

- [ ] Hide git for one command by giving it a path with nothing in it:
  ```bash
  PATH=/nonexistent PYTHONPATH=~/ack-tools/tools /usr/bin/python3 -m voice_studio.update check --yes
  echo "exit: $?"
  ```
  → `The program that fetches releases, git, is not installed on this computer.`, `Nothing was contacted and nothing was changed.` and `The setup in the installation guide installs it, after asking. Then try again.` With `exit: 2`, and no connection was made (watch the network if you can).

**C. The list, which asks first.** This is the first part that contacts the internet. It sends one request to github.com.

- [ ] Ask for the list and say no, then yes:
  ```bash
  PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.update check
  PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.update check
  ```
  → Both show the same lines as part A, then `Look for new releases now? Type yes to go on.` Type **`no`** the first time: `Nothing was done.` (`exit: 2`, nothing contacted). Type **`yes`** the second time. With no tag that begins with `voice-studio-` on GitHub it says `ACK Voice Studio has no named releases yet, so there is nothing to fetch.` and ends with `exit: 0` (this is what the real address gives today, and none of the phone app's `v1.0-beta` names is listed). With such tags it says `n releases of ACK Voice Studio are listed:` and a row for each (`v1.1: newer than this copy`, `v1.0: this copy`), whether this copy is at a release (`It is the release v1.0.` or a sentence saying it is not at a named release, so it cannot be compared), and `To fetch one into a new folder beside this copy, run: …`. Write down which it was, how long it took, and whether the sentences about what is sent were clear before you typed anything.

**D. A release, when part C listed one.** If it did not, skip to part G.

- [ ] Make a new empty folder to put the copy in, and ask for a release (the one part C marked newer, or any other if none was):
  ```bash
  T=$(mktemp -d)
  PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.update get RELEASE --to "$T/new-copy"
  ls -A "$T"
  PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.update get RELEASE --to "$T/new-copy"
  ```
  → It shows this copy, what is sent, `This downloads the release RELEASE of ACK Voice Studio from github.com into a new folder: …`, the two commands (`First it looks the release up: …` and `Then it fetches it: …`), `This copy, and your projects, recordings and backups, are not touched.`, the room it needs and has (`A copy is usually under 100 MB. 500 MB must be free beside this one, and … is.`), and `Download the release RELEASE now? Type yes to go on.` Type **`no`** the first time: `Nothing was done.` and `ls -A` lists nothing. Type **`yes`** the second time: `Fetched the release …` (with its commit, the folder and the version), `It was checked: it holds the commit the release was listed with, and it is a copy of this tool.`, then `Compared with this copy:` with one row for each area that differs (the lists of programs, what can be downloaded, the words on screen, the recording tool, the tool's own program files, the guides), the names of the files in the first two, and the two commands it prints (`To try it, run: …` and `To use it under the usual name once you are happy with it, run: …`). `exit: 0`. Write down how long the fetch took.
- [ ] Look at what it made, and at your own copy:
  ```bash
  du -sh "$T/new-copy"
  git -C "$T/new-copy" log -1 --format=%H
  git -C ~/ack-tools status --short
  ```
  → The size is a few tens of megabytes (the sentence said usually under 100 MB: write down the real number). The commit is the one the fetch printed (its first ten letters). Your own copy shows nothing you did not change yourself.
- [ ] Ask for the same release into the same folder again, and for a name that is not listed:
  ```bash
  PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.update get RELEASE --to "$T/new-copy" --yes
  echo "exit: $?"
  PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.update get v99.99 --to "$T/other" --yes
  echo "exit: $?"
  ```
  → The first says `Something is already at the folder the copy would go to.` and `exit: 2`, and nothing is fetched. The second contacts github.com once (it has to, to know), then says `That is not one of the releases that are listed.`, `Nothing was downloaded.` and `Run the check command to see the names.` with `exit: 1`, and `ls "$T"` shows no `other` folder.

**E. Trying the new copy, without switching.** Optional, and it changes nothing of yours.

- [ ] Run the first of the two commands the fetch printed (the one that starts `PYTHONPATH=`). → The new copy's guided setup starts; its first screen is the same as the one you know. It lists what it would build and asks before it builds anything. Answer **no** (or press Ctrl+C) to every question. Write down whether anything it said about the lists of programs matched the comparison. Your projects and recordings are not touched: `ls ~/ack-voice-studio/projects` shows what it showed.

**F. Stopping in the middle.** Optional, and it needs a connection that is not too fast.

- [ ] Start a fetch with `--yes` and press **Ctrl+C** within a second or two:
  ```bash
  PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.update get RELEASE --to "$T/stopped" --yes
  echo "exit: $?"
  ls -A "$T"
  ```
  → `Stopped. A copy that was being fetched was removed again, and this copy was not touched.` with `exit: 1`, and `ls -A` shows no `stopped` folder (if the fetch finished before you pressed Ctrl+C, it shows the whole copy instead, which is also right: the command ended normally). Write down whether a half-made folder was ever left.

**G. Switching, which only you can do.** Real and optional. Read the second command the fetch printed (`mv … && mv …`): it renames your folder `ack-tools` to `ack-tools.old` and the new copy to `ack-tools`. The tool prints it and never runs it.

- [ ] Only if you want the new copy to be the one you use, and only after a backup (`python3 -m voice_studio.backup`, section I9), close every window and terminal that runs the tool, then run that command. Run `PYTHONPATH=~/ack-tools/tools python3 -m voice_studio` and `PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.refresh check`. → The tool opens and the check runs; the setup says what it would build and asks first. `ls ~/ack-voice-studio` shows your projects and recordings where they were, and `~/ack-tools.old` still holds the old copy; remove it yourself when you no longer want it. Write down every sentence that left you unsure which folder was which.
- [ ] When you have looked: `rm -r "$T"` (nothing else in this part was made by it).

## I14. The problem report

**New, and not yet run on a real computer.** When a command fails after it began, its last two lines point at `report` (the plan's decisions D22 and P22). `report show` builds a problem report for a helper: the versions, the checks on this computer, the problem you name, how a task ended and, only if you ask, the end of that task's log, with your names and folders blanked and no recordings, no text you made and no phrases. It prints **all** of it and changes nothing. `report save --to FILE` prints the same text, asks once, and writes exactly that text to that one file: it never replaces a file unless you add `--replace`, makes no folder, and sends nothing anywhere. A command that was declined, or could not be asked, gets no such lines.

*Built and tried in the build sandbox only: on a computer with made-up names, and with one real failure made by pointing the proxy at a port nothing listens on. Not run on a real computer, and no helper has read one yet.*

**A. Look at one.** Nothing is saved or sent.

- [ ] Ask for the help, then for a report:
  ```bash
  PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.report help
  PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.report show
  echo "exit: $?"
  ```
  → `help` lists `show` and `save`. `show` prints `ACK Voice Studio: problem report`, then `---- the report starts on the next line ----`, the whole report, and `---- the report ends on the line before this one ----`. Only what is between those two lines is the report. After it: `Nothing was saved and nothing was sent.` and how to keep it as a file, and `exit: 0`. **Read all of it.** Look for your login name, the name of this computer, your project names and the names of the people in them, and any folder under your home. Each should be a marker (`<user>`, `<computer>`, `<person-1>`, `~`, `<voice-studio>`). Write down anything of yours you can still read.

**B. A pretend failure.** It cannot reach the internet, because the proxy it is told to use is a port nothing listens on, so nothing leaves the computer.

- [ ] Make a command fail, and one that is only declined:
  ```bash
  HTTPS_PROXY=http://127.0.0.1:9 https_proxy=http://127.0.0.1:9 PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.update check --yes
  echo "exit: $?"
  PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.update check </dev/null
  echo "exit: $?"
  ```
  → The first says `The place the releases are kept could not be asked, or it did not give the release.` with its Technical detail line and `exit: 1`, and **ends with two more lines**: `A problem report can be made for a helper: …` and `To see it, run: …`, a command with `--step 'update check' --problem update/unreachable` in it. The second only says there was nobody to ask, with `exit: 2` and **no** lines about a report.
- [ ] Run the command the first one printed, and add the Technical detail line it showed:
  ```bash
  PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.report show --step 'update check' --problem update/unreachable --detail "paste the Technical detail line here"
  ```
  → The report has `Step: update check`, `Problem: update / unreachable`, the three sentences for that problem, and a `More detail` line with what you pasted. Any folder or address in what you pasted is blanked. Write down whether the two lines at the end of the failed command were easy to find and to follow.
- [ ] Ask for a problem that does not exist, and for a detail with no problem:
  ```bash
  PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.report show --problem update/nothing_like_it
  PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.report show --detail "something"
  ```
  → The first says `That is not a problem name the tool knows.`, the second `--detail goes with --problem.`; both say `Nothing was built or saved.` and print no report.

**C. Saving, which asks first.** `T` is a new empty folder.

- [ ] Ask to save, say no, then yes:
  ```bash
  T=$(mktemp -d)
  PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.report save --to "$T/problem.txt"
  ls -A "$T"
  PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.report save --to "$T/problem.txt"
  ls -l "$T"
  wc -c "$T/problem.txt"
  ```
  → Each prints the whole report first and then asks `Save exactly this report to … now? Type yes to go on.` Type **`no`** the first time: `Nothing was done.`, and `ls -A` lists nothing. Type **`yes`** the second time: `Saved … bytes to …`, that it holds exactly the text shown and that only you can read it, and `Give the file to the helper yourself. The tool does not send it.` `ls -l` shows `-rw-------`, and `wc -c` gives the number of bytes it said. Open the file and compare it with what was on the screen between the two lines.

**D. Places that cannot be used.**

- [ ] Ask to save over the file, into a folder that does not exist, to a path that is not whole, and with no place:
  ```bash
  PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.report save --to "$T/problem.txt" --yes
  echo "exit: $?"
  PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.report save --to "$T/nowhere/problem.txt" --yes
  echo "exit: $?"
  PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.report save --to problem.txt --yes
  echo "exit: $?"
  PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.report save --yes
  echo "exit: $?"
  ls -A "$T"
  wc -c "$T/problem.txt"
  ```
  → Each says why in three sentences (`There is already a file at that place.`, `The folder for that file does not exist.`, `Give the whole path of the file, starting with a slash or with ~.`, `Say where to save the report.`), none prints a report, every `exit` is 2, `ls -A` lists only `problem.txt`, and its size is what it was.
- [ ] Replace the file, which says so and asks:
  ```bash
  PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.report save --to "$T/problem.txt" --replace
  ```
  → After the report it says `The file … is there already and will be replaced.` and asks the same question. Type **`yes`**: it is replaced (`ls -l` shows `-rw-------` and a new time). When you have looked: `rm -r "$T"`.

**E. A task, and its log.** Optional, and only with a training round you have run (section I2).

- [ ] Add the newest task, then the end of its log:
  ```bash
  PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.report show --job last
  PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.report show --job last --include-log
  ```
  → The first has a section about the task: its kind, how it ended and its exit number, and says the end of the log was left out. The second adds the end of the log (at most the last 60 lines, each cut short) with `These lines may contain words from recordings or names of folders. Names and folders were hidden, but check them before you share this.` Read every line. Write down any word of a recording that appears, and anything of yours that is not blanked. Without `--job`, `--include-log` is refused (`--include-log goes with --job.`).

**F. Your own names.** This is the check that matters most, because only you know which names are yours.

- [ ] Put your own names into the one place a person types words, and look at what comes out:
  ```bash
  PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.report show --step "$USER on $(hostname), folder $HOME/ack-voice-studio, address 192.168.1.20, mail me@example.org"
  ```
  → `Step:` shows `<user>`, `<computer>`, `<voice-studio>`, `<address>` and `<email>` where your login, this computer's name, your data folder, the address and the mail address were, and the last line before the second rule says how many things were hidden. Do the same with the name of one of your projects and the name of the person whose voice it is. Write down any name that was **not** hidden. Known limits: a name of one letter is not hidden, and a name of four letters or fewer is hidden only as a whole word.

## I15. The window's pages for hearing, backup, checking, updates and problem reports

**New, and not yet run on a real computer.** The window gained five pages after the first six: **Hear the voice** (`voicefile listen`, section I8), **Backup** (`backup`, section I9), **Check the tool** (`refresh`, section I10), **Updates** (`update`, section I13) and **Problem report** (`report`, section I14). Each is the window's face for a command you may already have tried: a button hands the command's own words to the same flow, which shows what it will do and asks first, with a Yes and a No button (No is where the keyboard focus starts). So the sentences are the ones you saw in the terminal; **this section is about the buttons, the layout and the way a page leads to the next**. Nothing on these pages starts by itself, nothing reads again on a timer, the window writes no file of its own for them, and the pages that can lead to the internet are Updates and, on Check the tool, the buttons that mend or build fresh (they can download again), each only after the command says what it will ask for and from where and you say yes; Hear the voice, Backup and Problem report never do.

*Built and tried in the build sandbox only: on a virtual screen, under GTK 4.14 and under the exact stack of the floor (Ubuntu 22.04: Python 3.10, python3-gi 3.42, GTK 4.6.9) in a copy of it, by a headless tour that presses every button below and answers every question. Updates was given a stand-in for the network, so nothing was contacted. Not run on WSLg or a native desktop, with a mouse, over a real connection, through a speaker, or with a screen reader. The tour cannot say whether the pages are easy to read or easy to find: that is what you are asked to write down.*

Use the project from section I2 (`voice-check`, with at least two finished rounds). Start the window as in section I5.

**A. The list.**

- [ ] Look at the page list on the left, then scroll it. → Eleven pages: Projects, Recordings, Training rounds, Hear the voice, Voice file, Backup, Free up space, Check the tool, Updates, Problem report and Display. At the window's first size the last ones may be below the edge of the list; the list scrolls, and the keyboard reaches them with Tab and the arrow keys. Write down whether you found Problem report and Display without help, and whether you would rather the pages were in another order.

**B. Hear the voice.** Needs the studio programs and the training programs (section I0 and I8); without them it says so and starts nothing.

- [ ] Open **Hear the voice**. → `Hear the voice for Voice check`, a sentence saying that it plays three short sentences in the voice on this computer, `A voice file you made` (a row for each voice file section I4 made, each with `Hear this voice…`, or `No voice file has been made yet. Make one on the Voice file page, or hear a round straight, below.`) and `Straight from a training round`, with a drop-down of the rounds that have a whole saved point and a settings file. The chosen round is already picked and its line ends `the chosen round`. Pick another and press `Look again` on another page and come back: the one you picked is still picked.
- [ ] Press `Hear this round…` for the chosen round, and say **No**. → The box shows the plan (`Round 3 would be heard like this:` and the lines under it) and asks `Make the sound files and play them now?` with No where the focus starts. `Nothing was done.` and nothing new in the project's `listening` folder.
- [ ] Press it again and say **Yes**. → The same as section I8 part E, in the window: the slow step, then the sounds playing one after another through the speaker, then `Did you hear them all?` with Yes and No buttons, then (for a round) the question about removing the large voice copy. Write down whether the sounds played at all through the window (WSLg and a native desktop differ), and how long it took to start.
- [ ] Press `Show the folder of sound files`. → The folder opens in the file manager (on WSL, Windows File Explorer), or `Last result` says its path.
- [ ] While a round is training (start a short one from section I2 first): open the page. → `Round 4 is training now. Hearing a round waits until it ends.` and no drop-down.

**C. Backup.**

- [ ] Open **Backup**. → `Backup for Voice check`, a sentence saying what a backup is, how the project stands (`Voice check has not been backed up on this computer yet.` the first time), `The next backup goes in …, the tool's own backups folder.`, a tick box (`Leave out the saved points of the training rounds. The backup is much smaller.`), and the buttons `Back up now…`, `Choose another folder…` and `Show the folder`. Click the **words** beside the tick box: it ticks. Click again: it unticks.
- [ ] Press `Back up now…` and say **No**. → The plan (`A backup of Voice check would be made like this:` and what it holds) and the question `Make this backup now?`. `Nothing was done.` and no file in the backups folder.
- [ ] Press it again and say **Yes**. → The backup is made and read back, `Last result` says where, and the page now lists it: a row with its date, size and name, and the buttons `Check it` and `Put it back…`. The sentence about how the project stands now says nothing precious has changed since the last backup.
- [ ] Press `Check it` on that row. → `… is whole. Every file in it matched, and nothing is missing or extra.` and no question.
- [ ] Press `Put it back…` on the same row. → `Nothing needs putting back. Everything in the backup is already in the project.` and no question (nothing is added when everything is there).
- [ ] Tick the box, press `Back up now…`, read the plan, say **No**. → The plan lists `The saved points, because you asked` among what is left out. Untick the box.
- [ ] Make a folder for the next steps, then press `Choose another folder…`:
  ```bash
  T=$(mktemp -d)
  echo "$T"
  ```
  → The system's own chooser opens for **folders** only. Choose `$T`: the page says `The next backup goes in …, the folder you chose.` and shows `Use the usual folder`. Press `Back up now…`, check that the plan names that folder, say **Yes**. → The backup is in `$T`, and the page now says `The next backup goes in …, the folder used last.` (the command remembers it; the page does not). Cancelling the chooser changes nothing and says nothing.
- [ ] Press `Check a backup file…` and `Put back from a backup file…`. → The chooser opens for files, showing only `.tar` files; cancelling it does nothing.

**D. Check the tool.** Nothing here reads anything until a button is pressed (a full look reads every downloaded file, which takes a while).

- [ ] Open **Check the tool**. → `Check the tool`, a sentence saying it never touches a project, a recording, a round, a finished voice or a backup, then `Look at everything`, `Look quickly, without the programs' own check` and `Mend what is broken…`; `Build a fresh copy of the programs` with a drop-down (`Every set that is set up`, then the small set, then the large one) and `Build a fresh copy…`; and `Older copies` with `Show the older copies` and `Remove the older copies…`.
- [ ] Press `Look quickly, without the programs' own check`. → The same lines as `refresh check --quick` in section I10, with no question. Then `Look at everything`: slower, the same kind of lines. Write down how long each took and whether the window felt stuck (it should show the working bar).
- [ ] Press `Mend what is broken…`. → With nothing broken, `Nothing needs repair.`; otherwise the plan and a question.
- [ ] Press `Show the older copies`. → `No old copies of the programs are on the disk.` (or the list). Press `Remove the older copies…`: the same sentence when there are none, a question with the list and its size when there are.
- [ ] Press `Build a fresh copy…` with the drop-down on one set, and say **No** to whatever it asks. → The plan (`A rebuild of … would work like this:`), what is downloaded, and No changes nothing. (Say yes only if you mean to rebuild: section I10 parts E and F.)

**E. Updates.** Needs a connection, and contacts github.com only after you say yes.

- [ ] Open **Updates**. → `Updates`, `This copy is version …, in ….`, `Look for releases…`, `Releases found` with `You have not looked yet. Press Look for releases.`, and a note about the two commands you type yourself after a fetch.
- [ ] Press `Look for releases…` and say **No**. → The box says what will be asked of github.com (`git ls-remote --tags …`) and that only tags beginning with `voice-studio-` count, then asks `Look for new releases now?` `Nothing was done.` Nothing was contacted (watch the network if you can).
- [ ] Press it again and say **Yes**. → One request. While no tag beginning with `voice-studio-` exists: `ACK Voice Studio has no named releases yet, so there is nothing to fetch.` in `Last result` and `The last look found no named releases.` on the page. With releases: a drop-down of them, newest first, and `Fetch this release…`. Write down how long the look took.
- [ ] If there is a release: pick one and press `Fetch this release…`; read the exact commands; say **No**. → `Nothing was done.` Say **Yes** only if you want the new copy beside this one (section I13 parts D to G): the two commands to try it and to switch to it are printed in `Last result`, which you can select and copy; the window never runs them.

**F. Problem report.**

- [ ] Make a task fail on purpose: on **Hear the voice** press `Hear this round…` and say **Yes** on a computer where the training programs are not set up (or any task you know fails). → `It could not finish.`, the reason, then `A problem report can be made for a helper. Open the Problem report page.` and, under `Last result`, a button `Make a problem report…`. Press it: it takes you to the Problem report page, and the button goes away there.
- [ ] Read the page. → `Problem report`, what the report holds and that nothing is sent anywhere, a ticked box `Make the report about the task that just failed: voicefile listen`, a line for your own words, `About which task?` (`No particular task`, `The newest task`, then recent tasks by name and how they ended), a box for the end of that task's log (off until you pick a task), `Show the report` and `Save the report to a file…`, and `No report has been built yet. Press Show the report.`
- [ ] Press `Show the report`. → No question. `The report` appears on the page with **all** of it, and the keyboard focus is on it (so a screen reader starts reading it). Read it: **your computer's name, your user name and your folders must be blanked**, and there must be no recording, no text you made and no phrase. Write down anything that identifies you or the person. `Copy the report` puts it on the clipboard: paste it somewhere to see.
- [ ] Untick the failure box, type a few words of your own and press `Show the report` again. → Your words are the step named in the report, and no problem is named.
- [ ] Press `Save the report to a file…`. → A small form: `Folder` (`No folder chosen yet.`), `Choose a folder…`, `File name` (`problem-report.txt`), and `Show it and ask`. Press `Show it and ask` first: `Please fix these first:` and `Choose the folder to save it in.` and the form stays open. Choose `$T` with the chooser (it offers folders only), then type a name with a slash in it: `A file name has no slashes and is at most 100 characters long.` Fix the name and press `Show it and ask`.
- [ ] → The box shows the whole report again and asks `Save exactly this report to …` Say **No**: `Nothing was done.` and no file in `$T`. Do it again and say **Yes**: `Saved … bytes to …` and the file is there; `ls -l "$T"` shows it owner-only. Do it a third time with the same name: the form says `There is already a file at that place.` and stays open, and the file is not changed. Press Cancel.
- [ ] When you have looked: `rm -r "$T"` (the folder this section made; nothing else in it was made by it except what section I15 saved there).

**G. Everything together.**

- [ ] Use every page with the keyboard only: Tab and Shift+Tab move between controls, the arrow keys move in the page list and in a drop-down, Enter or Space press a button or tick a box. Write down any control the keyboard cannot reach or that is not named when it is focused.
- [ ] Set `Size of the whole window` to 200% on the Display page and look at the five pages again. → Nothing is cut off sideways, and the buttons wrap onto the next line instead. The first drop-down may need the page to scroll.
- [ ] A screen reader, if you use one: visit each page and press each button. Write down what is read for the page heading, the tick boxes, the drop-downs and the shown report. It is fine if the answer is "nothing is read".
- [ ] Write down: any page you could not find, any word you did not understand, any time the window seemed to do nothing, and whether the list of eleven pages is too long.

## I16. Giving the voice file to the phone over Wi-Fi

**New, and not yet run on a real computer or a real phone.** `voicefile send` gives the finished voice file to a phone on the same home network, once, so that no cable is needed (the plan's decision D10, choices P25). It is the one place the tool **listens** for a connection: for up to ten minutes, on one home-network address, over a secure connection, for one file, at an address that holds a random secret, and it stops by itself after the first complete download. Nothing is sent anywhere else, and the computer opens no connection to anything. It needs a voice file from section I4, the `openssl` program that Ubuntu already has, and a phone and this computer on the same Wi-Fi.

*Built and tried in the build sandbox only: with the real `openssl` (a certificate for a home-network address passes, one for a public address or a name is refused by the authority itself) and real clients on this computer's own loopback address (the right address gets the whole file once, anything else gets a short "not found", a device that does not trust the certificate gets nothing, the listener ends by itself). The QR code was read back by a reader written separately from the specification. **Not run on a real network, on WSL's network, through a real phone's browser, or with a phone camera**, and no phone has been shown to honour the certificate's limits to home-network addresses (the authority itself does, by `openssl`). That is what this section is for.*

**A. The certificate file for the phone (the first time only).** Nothing is made until you say yes.

- [ ] Ask, and say no:
  ```bash
  PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.voicefile send --project voice-check
  ```
  → `ACK Voice Studio: sending the voice file to the phone`, then `The phone needs a small certificate file first. Without it, the phone will not take a download from this computer without a warning.` and what will be made, where it is kept and that its secret part stays there. Then the question `Make the certificate file now? Type yes to make it.` Type **`no`**: `Nothing was done.` and no folder `~/ack-voice-studio/state/phone-certificate` exists. (`ls ~/ack-voice-studio/state` shows it is not there.)
- [ ] Run it again and type **`yes`**:
  ```bash
  PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.voicefile send --project voice-check
  ls -la ~/ack-voice-studio/state/phone-certificate
  ```
  → `Put it on the phone once:` and four steps, then `When that is done, run this again to send the voice file: …`. It **stops there and sends nothing**: the phone has to have the file first. `ls` shows exactly two files, `authority.key` (permissions `-rw-------`) and `ack-voice-studio-phone-certificate.crt`, in a folder that is `drwx------`. Write down whether the four steps were clear.
- [ ] Look at what the certificate allows (this only reads the file):
  ```bash
  openssl x509 -in ~/ack-voice-studio/state/phone-certificate/ack-voice-studio-phone-certificate.crt -noout -text | sed -n '/Name Constraints/,/Signature Algorithm/p'
  ```
  → `Name Constraints: critical` and, under `Permitted:`, exactly `IP:10.0.0.0/255.0.0.0`, `IP:172.16.0.0/255.240.0.0`, `IP:192.168.0.0/255.255.0.0` and `DNS:ack-voice-studio.invalid`, and nothing else. The date at the end of `Not After` is about two years away.
- [ ] Run the command a third time with the folder in place and say **no** at the question: it must not ask to make the file again, and it must show the plan (part C) instead. (Do not answer yes yet.)

**B. Put the file on the phone.** This is the part that has never been tried on a phone.

- [ ] Copy `ack-voice-studio-phone-certificate.crt` to the phone the way you copied the zip in section K (on WSL, `explorer.exe "$(wslpath -w ~/ack-voice-studio/state/phone-certificate)"` opens the folder). On the phone, install it as a **CA certificate**. → Write down the phone's make and model, the Android version, the exact words of the menus you followed, whether they matched the four steps the tool showed, the warning the phone gave, and whether it let you install the file. **Do not install it on a phone you do not own.**
- [ ] On the phone, look at the list of user certificates. → The new one is named `ACK Voice Studio phone certificate` with the day it was made.

**C. Send the voice file.** The computer and the phone are on the same Wi-Fi.

- [ ] Find the address the tool would use, and say no:
  ```bash
  PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.voicefile send --project voice-check
  ```
  → `The voice file would be sent like this:` and these lines: the file's name and size (`Nothing else on this computer is offered.`), `It is offered at …, port 8443, over a secure connection, for up to 10 minutes.`, `Only a device that opens the exact address shown next can take it, and only once.`, `It stops by itself when the whole file has been sent, when the time is up, or when you press Ctrl+C.` and `This computer opens no connection to anything. It only waits for the phone to ask.` Then `Offer the voice file to the phone now? Type yes to start.` Type **`no`**: `Nothing was done.` Write down the address it chose, and whether it is the one your router gave this computer.
  If it says `This computer has more than one home-network address:` and lists them, or `No home-network address was found for this computer.`, write down what it listed and choose with `--address` (below).
- [ ] Send it (use your own address in place of `192.168.1.23`, and say **yes**):
  ```bash
  PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.voicefile send --project voice-check --address 192.168.1.23
  ```
  → `Waiting for the phone. Open this address on the phone, or scan the code if one is shown:`, a square code (only in a terminal that can show colour), and the address under it, then `Press Ctrl+C to stop.` Scan the code with the phone's camera, or type the address into the phone's browser. → The phone downloads `….zip` **with no warning page**, and the terminal says `The phone is fetching the file (…).` and then `Sent. The phone has the whole file (…). Nothing is listening any more.` and how to import it, and the command ends with `exit` 0 (check with `echo $?`). Write down: whether the code scanned at the first try, how long the download took for how many megabytes, and exactly what the phone showed.
- [ ] Compare what arrived with what was sent. On the phone find the file in Downloads; on the computer:
  ```bash
  ls -l ~/ack-voice-studio/projects/voice-check/exports/*/*.zip
  ```
  → The size in bytes on the phone is the same as here. Then import it in ACK as in section K.
- [ ] Try the address again after it said `Sent.`. → The phone's browser cannot connect: nothing is listening.

**D. What it must refuse.** Each of these starts the command and ends it with Ctrl+C or by itself; none should show a Python error.

- [ ] A device that was not given the certificate (a second phone or a laptop, or the same phone after you remove the certificate): open the address. → The browser warns that the connection is not private and **does not download the file**. The terminal says `A device connected but did not trust the certificate. If it was the phone, the certificate file has not been put on it yet.` once, however many times you try. (Do not click through the warning.)
- [ ] On the phone, change one letter of the secret part of the address, or open only `https://<address>:8443/`. → `Not found`, and the file is not given. The listener goes on waiting (a request for something else is not announced in the terminal).
- [ ] Open the right address, then stop the phone's download half way (switch Wi-Fi off). → `The transfer stopped part way. The phone can try again.` Then fetch it again properly. → `Sent.`
- [ ] Leave it alone for ten minutes. → `Nobody fetched the file in 10 minutes, so it stopped listening. Nothing was sent.` and `exit` 1.
- [ ] Press Ctrl+C while it waits. → `Stopped. Nothing is listening any more, and nothing more will be sent.` Check that no port stays open: `ss -ltn | grep 8443` prints nothing.
- [ ] Ask for things it must refuse. Each of these must say what is wrong, in three sentences, and start nothing:
  ```bash
  PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.voicefile send --project voice-check --address 8.8.8.8
  PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.voicefile send --project voice-check --port 80
  PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.voicefile send --project voice-check --folder nope
  ```
  → `That address is not a home-network address.`, then `The port must be a whole number from 1024 to 65535. Nothing was done.`, then `There is no voice file called nope in this project. These are the ones that were made:` and the list.
- [ ] Start it twice at once (two terminals; say yes in both). → The second says `Something on this computer already uses that port.` and `Try another port with the port option, for example 8444.` (with the first still waiting).

**E. Ubuntu under Windows (WSL).** The part most likely not to work, and the reason the plan has a later task (VS-3.6) for it. Nothing here changes a Windows setting.

- [ ] Run part C's first step on WSL. → After the plan it adds `This is Ubuntu under Windows. A phone usually cannot reach the address that Ubuntu sees. To see what is needed, run: python3 -m voice_studio.wsl check` (section I17 is that command). Then send anyway. Write down the address Ubuntu chose (WSL's usual default network gives an address like `172.x.x.x` that only Windows can reach), and whether the phone could open it.
- [ ] If it could not: section I17 is the command that explains what to change, changes the one Windows file after you say yes, and prints the firewall command and the restart. Do it there, then come back and repeat part C.

**F. What it left behind.**

- [ ] After a send, a time-out and a Ctrl+C:
  ```bash
  ls -la ~/ack-voice-studio/state/phone-certificate
  ```
  → Still exactly the two files and no folder beginning `send-` (the certificate made for one send is removed afterwards). The voice file in `exports` is unchanged.
- [ ] Make a backup and look inside it (section I9), then:
  ```bash
  tar -tf ~/ack-voice-check-backups/*.tar | grep -c phone-certificate
  ```
  → `0`: the certificate and its secret part are not in a backup.
- [ ] To make a new certificate file (it ends after two years, and the tool says so thirty days before): move the folder aside, **never delete it**: `mv ~/ack-voice-studio/state/phone-certificate ~/ack-voice-studio/state/phone-certificate-old`, run the send command, and put the new file on the phone. The old one on the phone can then be removed in the phone's settings.

## I17. Ubuntu under Windows: the phone and the idle stop

**New, and not yet run on a real Windows computer.** `python3 -m voice_studio.wsl check | phone | idle` (the plan's task VS-3.6, decision D17, choices P26) helps with the two things about Ubuntu inside Windows that get in the way of this tool, both settings in one Windows file, `.wslconfig`, in your Windows home folder: a phone cannot reach Ubuntu in WSL's usual network (`networkingMode=mirrored` in `[wsl2]` shares the Windows network), and Ubuntu stops about a minute after its last window or terminal closes, taking a running round with it (`instanceIdleTimeout=-1` in `[general]`, finding F3). `check` only looks. `phone` and `idle` each show the one change they want to make, ask first, and copy the file as it was before they change it. **They never restart WSL, never run the firewall command (they print it), and change nothing on Windows but that one file.**

*Built and tried in the build sandbox only, against a pretend Windows drive: reading and changing the file without disturbing a line of it (Windows line ends, a byte order mark and comments are kept), finding the home folder with and without a Windows program to ask, the copies, and every refusal. **Not run on a real Windows computer**: not the real `wslinfo`, not the Windows programs it starts, not the firewall command (it is Microsoft's own, copied from their page on WSL networking, and was not tried), not whether `instanceIdleTimeout` does anything on your version of WSL, and not whether a phone can reach Ubuntu afterwards. That is what this section is for.* Use a Windows computer with Ubuntu under WSL 2. Section D's job-survival checks are the ones part C leans on.

**A. Look first.** Nothing is changed.

- [ ] In PowerShell, write down what Windows says: `wsl --version`, `wsl --status` and `type $env:USERPROFILE\.wslconfig` (the last may say the file is not there). Then in Ubuntu:
  ```bash
  ls -l --time=ctime /mnt/c/Users/*/.wslconfig 2>/dev/null
  PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.wsl check
  ls -l --time=ctime /mnt/c/Users/*/.wslconfig 2>/dev/null
  ```
  → `ACK Voice Studio: Ubuntu inside Windows (WSL)`, `What this computer reports:` and then, each indented, whether Windows programs can be started from Ubuntu, the Windows build, your Windows home folder, whether the settings file is there, the networking mode the file asks for (and the one Ubuntu is running with, if `wslinfo` is there), what that means for a phone, and what it means for a long round. The two `ls` lines are the same: looking changed nothing. Write down every line, and whether each is true (the build against `ver`, the mode against `wsl --status`).
- [ ] If your computer has more than one user folder under `C:\Users`, the command says `There is more than one user folder on the C drive, so I cannot tell which one is yours.` unless Windows could be asked; name yours with `--windows-user`:
  ```bash
  PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.wsl check --windows-user YOURNAME
  ```
  → The same report, for that folder. (Skip this step if the first report already found your home.)

**B. What it must refuse.** None of these should show a Python error.

- [ ] Ask for things it must refuse:
  ```bash
  PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.wsl phone --port 80
  PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.wsl check --windows-user nobody-by-that-name
  PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.wsl restart
  ```
  → `The port must be a whole number from 1024 to 65535. Nothing was done.`, then `There is no user folder with that name on the C drive.` with two more sentences, then `I do not know the command restart. Nothing was done. Run it with help to see the commands.`

**C. Keep Ubuntu running when the last window closes.** This is the part the developer already did by hand once (finding F3); here the tool does it.

- [ ] See the notice a round start gives while the setting is missing. Use the project from section I2 and answer **no**:
  ```bash
  PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.rounds start --set dataset-1 --project voice-check
  ```
  → Among the lines before the question: `This is Ubuntu under Windows. If you close the last Ubuntu window while the round runs, Ubuntu can stop and take the round with it. To prevent that, run: python3 -m voice_studio.wsl idle`
- [ ] Ask for the change, and say **no**:
  ```bash
  PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.wsl idle
  ```
  → `Keeping Ubuntu running when the last window closes takes two steps.`, the lines that differ (a `+instanceIdleTimeout=-1` line, under `[general]`), and `Change the file now? Type yes to change it.` Type **`no`**: `Nothing was done.` The file is exactly as it was.
- [ ] Run it again and type **`yes`**:
  ```bash
  PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.wsl idle
  ls -la /mnt/c/Users/*/.wslconfig*
  ```
  → `Changed. The file as it was is kept as …` and `.wslconfig.bak` is there next to `.wslconfig` (if the file did not exist before, `Made the file …` and no copy). Open `.wslconfig` in Notepad: your own lines are unchanged and in the same order, with the new line added. Write down whether Notepad still shows the file normally (line ends, accents in comments).
- [ ] Restart WSL **when no round is running** (the tool says so; it never does this): close every Ubuntu window and in PowerShell run `wsl.exe --shutdown`. Open Ubuntu again and run `python3 -m voice_studio.wsl check`. → `Ubuntu is kept running after the last window closes.` The round start from the first step now prints no such notice.
- [ ] The real test, from section D: start the short job, close every Ubuntu window and wait five minutes. → The job is still going when you open Ubuntu again (the setting worked on your version of WSL). If it was killed, run `wsl.exe --update` in PowerShell, restart WSL and try once more. Write down your WSL version.

**D. Let a phone reach Ubuntu.** Needs Windows 11 version 22H2 or newer.

- [ ] Ask for the change, and say **no**:
  ```bash
  PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.wsl phone
  ```
  → `Letting a phone reach Ubuntu takes three steps.`, the change to `.wslconfig` (a `+networkingMode=mirrored` line under `[wsl2]`), the question, and after your **no**: `Nothing was done.` and none of the commands. (On Windows 10, or Windows 11 older than 22H2, it says `This Windows is older than the version that has mirrored networking (build 22621). Copy the voice file to the phone by hand instead.` and stops: write down your build.)
- [ ] Run it again and type **`yes`**:
  ```bash
  PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.wsl phone
  ```
  → The file is changed and its old copy kept, then step 2 gives one PowerShell command and one to take the rule away again, `This tool never runs it for you.`, and step 3 gives `wsl.exe --shutdown`. If a round is running, `A task is running now. Do not restart WSL until it has finished, because a restart stops it.` is among them.
- [ ] Run the step 2 command yourself, in PowerShell opened as administrator. → Write down whether Windows accepted it as printed. If it refused, write down the whole message and what you changed to make it work. **This command is Microsoft's, copied from their page, and nobody has tried it.**
- [ ] Restart WSL as step 3 says, open Ubuntu, and look:
  ```bash
  wslinfo --networking-mode
  ip -4 -o addr show scope global
  PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.wsl check
  ```
  → `mirrored`; an address that begins like your Wi-Fi address (not `172.x.x.x`); and a report with `A phone on the same Wi-Fi can reach this Ubuntu once the Windows firewall lets the port through.` Write down what `wslinfo` printed (or that it is not there).
- [ ] Send the voice file as in section I16 part C. → `voicefile send` still adds its note about Ubuntu under Windows, then offers an address that begins like your Wi-Fi address, and the phone opens it. Write down whether it did, and what else you had to change.
- [ ] Take the firewall rule away when you are done, with the second command step 2 gave, in an administrator PowerShell. → Write down whether it was accepted.

**E. A file the tool must not touch.** Use a folder that is not your own, so that your real file is never at risk.

- [ ] Make a pretend Windows user folder and a file the tool cannot edit safely:
  ```bash
  mkdir /mnt/c/Users/ack-voice-check-user
  printf '[wsl2]\nnetworkingMode=nat\nnetworkingMode=none\n' > /mnt/c/Users/ack-voice-check-user/.wslconfig
  PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.wsl phone --windows-user ack-voice-check-user --yes
  cat /mnt/c/Users/ack-voice-check-user/.wslconfig
  ```
  → `The settings file gives the same setting twice, so I cannot tell which one counts.` with two more sentences, `Technical detail: networkingMode`, exit 2, and the file exactly as you made it.
- [ ] A file saved by Notepad as UTF-16 (open the pretend file in Notepad, choose Save As and the encoding `UTF-16 LE`), then:
  ```bash
  PYTHONPATH=~/ack-tools/tools python3 -m voice_studio.wsl phone --windows-user ack-voice-check-user --yes
  ```
  → `The settings file is not plain text that this tool can edit safely.` with two more sentences, and the file is as Notepad saved it.

**F. What it left behind.**

- [ ] Look at what is there:
  ```bash
  ls -la /mnt/c/Users/*/.wslconfig*
  ```
  → `.wslconfig`, and one `.wslconfig.bak` for the first change (a later one gets `.wslconfig.bak-` and the time). No file with `.new-` in its name. The tool never replaces or removes a copy.
- [ ] To go back to what you had, close every Ubuntu window, copy the old file over the new one yourself (`cp` the `.bak` to `.wslconfig`), remove the firewall rule (part D) and restart WSL. The tool does not do this for you.

## I18. The Windows setup program

**New, and not yet run on a real Windows computer.** `ACK-Voice-Studio-Setup-<version>.exe` (the plan's task VS-7.4, decision D44, choices P28) is a wizard for **Windows 11 only** that does what the two installation guides do, with no terminal: it looks at the computer, sets up WSL and Ubuntu 24.04 if they are not there, asks you for an **Ubuntu account name and password**, fetches ACK Voice Studio from its source (GitHub) and sets up its programs inside Ubuntu, and puts it in the Start menu. It is **not signed yet**, so Windows will warn you. It has no silent mode.

*Built and tried in the build sandbox only: the wizard compiles, and the PowerShell it runs was run for real against stand-ins for `wsl.exe`. The workflow also ran the engine's questions that change nothing once on GitHub's `windows-latest` runner (2026-10-17: both scripts parse in PowerShell 5.1 and 7; `help`, `validate` and a dry run gave the expected exit codes), a Windows Server image without WSL. **Nothing was run on a real Windows 11 computer: not the wizard's pages, not `wsl --install`, not Ubuntu registering by itself, not the unsigned warning.** The least certain step is Ubuntu registering without asking its own first-run question; write down exactly what you see there.*

Get the file one of two ways: the unsigned file the workflow `voice-studio-installer` keeps for 30 days (the Actions page of the repository, under the run's artifacts), or build it yourself with `tools/voice_studio/installer/build.sh` on Ubuntu (it needs `makensis`). Either way a `.sha256` file sits beside it.

**A. Before you run it.**

- [ ] In PowerShell, compare the file with its checksum: `Get-FileHash .\ACK-Voice-Studio-Setup-*.exe -Algorithm SHA256` and the `.sha256` file's first word. → The two are the same. Write down whether they were.
- [ ] Double-click the file. → Windows warns about an unknown publisher (**SmartScreen**: "Windows protected your PC", then More info, then Run anyway). Write down the exact words and whether Run anyway was easy to find. **If your computer's rules block unsigned programs, write down what it said; do not change the rules for this test.**
- [ ] If you have a Windows 10 computer, run it there. → A message says it works only on Windows 11 for now, names the build it found, and says nothing was changed. Nothing else opens. (Skip this step without one, and say so.)

**B. The pages.** Go slowly; write down anything cut off, anything you could not read, and anything you did not understand.

- [ ] The welcome page, then the licence page. → The licence is the GPL text and Next goes on (there is nothing to tick).
- [ ] **Where everything comes from.** → It says the setup program holds no copy of ACK and names the five places (ACK on GitHub, Ubuntu and WSL from Microsoft, Ubuntu's own programs, the training programs and the starting voice, and that your recordings stay on this computer). Write down whether you could follow it.
- [ ] **Looking at this computer.** → It lists what it found (Windows build, disk room, graphics card, WSL, Ubuntu) and changes nothing. Next is switched off until the look is done, and stays off if the computer cannot be used. Write down how long it took and what it listed.
- [ ] **An account for Ubuntu** (it is skipped when Ubuntu already has an account). → Name, password, password again. Try each of these and write down what each said: nothing typed; two passwords that differ; the name `root`; a password of five characters; a password with an accent in it. **Every one is refused with a message and nothing is changed.**
- [ ] Look at the words on that page about the password. → It says the setup program sees the password, sends it once to Ubuntu and does not save it. Write down whether you were comfortable with that and whether the page made it clear that the command-line installer works differently.

**C. A computer that has never had WSL.**

- [ ] Choose a name and a password and go on. → The details list shows each step in turn: `platform`, `distro`, `user`, `sudo-on`, `setup`, `sudo-off`, `launcher`. **Windows asks once for permission to set up WSL**; choose Yes.
- [ ] If it says the computer must restart, restart it and run the setup program again. → It looks again, finds WSL, and carries on from there without asking for the account twice. Write down what it showed the second time.
- [ ] Wait for the long step (it downloads several gigabytes). → It ends with the Finish page. Write down how long each step took and whether the window looked frozen at any time.
- [ ] Press the checkbox to open ACK Voice Studio and Finish. → The window opens. Write down whether the Start menu now has `ACK Voice Studio (Ubuntu-24.04)`.

**D. What it left behind.** Open Ubuntu from the Start menu.

- [ ] Run `id` and `sudo -v`. → You are the account you named, and `sudo -v` asks for **your password** and accepts it (so the password was set).
- [ ] Run `ls /etc/sudoers.d/`. → `ack-voice-studio-install` is **not** there: the temporary permission was taken away.
- [ ] In PowerShell run `type $env:LOCALAPPDATA\ack-voice-studio\installer.log`. → A line for each step. **The password is not in it** (search the file for it). Write down anything you did not expect.

**E. While it runs.**

- [ ] Open Task Manager, the Details tab, and add the Command line column while the `user` step runs. → No password in any command line.

**F. A failure, then a second try.**

- [ ] On a computer that has gone through C, remove the network cable or turn off Wi-Fi during the long step, wait for it to fail, then reconnect. → A message says which step stopped, that nothing you made is lost, and that you can run it again. Check that `/etc/sudoers.d/ack-voice-studio-install` is **gone** after the failure. Run the setup program again. → It skips what is done and carries on.

**G. A computer that already has Ubuntu and an account.**

- [ ] Run the setup program there. → The account page is **not shown**, the account's password is not asked for or changed (check that your old password still works), and the set-up goes straight to fetching ACK.

**H. Taking it away.**

- [ ] Settings, Apps, Installed apps, ACK Voice Studio, Uninstall. → The page says it leaves Ubuntu, the programs inside it and your recordings and voices alone. Afterwards the Start menu entry is gone and `%LOCALAPPDATA%\ACK Voice Studio` is gone (or holds nothing of the setup program's), and **Ubuntu still starts and the tool is still in it**. Write down anything it left or removed that it should not have.

## J. Making the voice file

- [ ] Export, then give it its settings file with the exact name, then prepare it for the phone:
  ```bash
  TRAIN=$(ls -d ~/ack-voice-studio/tool/environments/training-* | head -1)
  "$TRAIN/venv/bin/python" "$TRAIN/ack_run.py" piper.train.export_onnx \
    --checkpoint ~/piper/voice-check/run/lightning_logs/version_0/checkpoints/last.ckpt \
    --output-file ~/piper/voice-check/my_voice.onnx
  cp ~/piper/voice-check/config.json ~/piper/voice-check/my_voice.onnx.json
  "$TRAIN/venv/bin/python" ~/ack-tools/tools/patch_voice_for_sherpa_onnx.py ~/piper/voice-check/my_voice.onnx ~/piper/voice-check/my_voice.onnx.json
  ls -l ~/piper/voice-check/my_voice.onnx*
  ```
  → `my_voice.onnx`, `my_voice.onnx.json` and `my_voice.onnx.before-patch`. The launcher (`ack_run.py`) applies the guide's `dynamo=False` fix first; if the export still stops with a
  `GuardOnDataDependentSymNode` error or asks for `onnxscript`, copy the error: it decides whether the lock needs another package.
- [ ] Run the patch command again. → "… already has this metadata, so nothing was changed." and `ls -l` shows the same sizes and dates.
- [ ] Make the file for the phone. It checks what ACK would refuse **before** writing, asks nothing, and never replaces a file:
  <!-- snippet: voice-zip -->
  ```bash
  PYTHONPATH=~/ack-tools/tools python3 - ~/piper/voice-check/my_voice.onnx ~/piper/voice-check/my_voice.onnx.json ~/ack-voice-check/my_voice_backup.zip <<'EOF'
  import sys
  from pathlib import Path
  from voice_studio.core import voicezip
  from voice_studio.core.text import load_catalog

  cat = load_catalog("en")
  model, config, dest = (Path(p).expanduser() for p in sys.argv[1:4])
  try:
      report = voicezip.write_voice_zip(model, config, dest)
  except voicezip.VoiceZipError as err:
      for part in ("what", "changed", "next"):
          print(cat.t("voicezip.error.%s.%s" % (err.code, part)))
      for code in err.problems:
          print("   -", cat.t("voicezip.problem." + code))
      print("details:", err.code, err.detail)
      sys.exit(1)
  print("written:", report.path, "(%d bytes)" % report.zip_bytes)
  print("model sha256", report.model_sha256[:16], "| settings sha256", report.config_sha256[:16])
  left = voicezip.verify_voice_zip(dest)
  print("checked again as the phone would:", "no problems" if not left else ", ".join(left))
  EOF
  ```
  → `written: …/my_voice_backup.zip`, then "no problems". `unzip -l ~/ack-voice-check/my_voice_backup.zip` lists exactly `model.onnx` and
  `model.onnx.json`.
- [ ] Run it again. → "A file with that name is already there." and "It was left as it is, and nothing new was written." The exit code is 1
  and the zip is unchanged.
- [ ] Try it on the **unpatched** voice: copy `my_voice.onnx.before-patch` to `~/piper/voice-check/raw.onnx` and the settings file to
  `raw.onnx.json`, and run the snippet on those (with another zip name). → Refused with a sentence that the voice "has not been prepared for the
  phone yet", and **no zip file is left behind**.

## K. On the phone

- [ ] Copy the zip file to the phone (cable or USB drive). It is the `.zip` in the folder section I4 made, under the project's `exports` folder (or, if you made it by hand in section J, `my_voice_backup.zip`). On WSL, this opens that folder in Windows File Explorer
  (it needs Ubuntu to be able to start Windows programs, which the section D check tells you; Explorer may report an error code even when the window opens, which is normal):
  ```bash
  explorer.exe "$(wslpath -w ~/ack-voice-studio/projects/voice-check/exports)"
  ```
  Without that, type `\\wsl.localhost\<distribution>\home\<you>\ack-voice-studio\projects\voice-check\exports` into File Explorer's address bar (this needs no set-up).
- [ ] ACK → Audio Architect → Custom Voice → **IMPORT CUSTOM VOICE** (or RE-IMPORT) → pick **the zip, alone**. → ACK accepts it and restarts by itself. This needs a build of ACK that has the zip import (the branch this
  checklist is on): before that change the picker wanted the two trainer files, and **IMPORT VOICE BACKUP** (the restore button next to EXPORT) appears only once a voice is already installed. On a phone that has a voice,
  either button takes the zip; the picker still takes the two files (`my_voice.onnx` and `my_voice.onnx.json`, together) as before.
  *Confirmed on the developer's phone (2026-10-11): the zip alone imports as expected.*
  If it refuses, note the message on screen (it now names both ways) and, if you can, the lines `adb logcat -s ACK_VOICE_BACKUP ACK_CUSTOM_VOICE` print.
- [ ] A new chip **MY VOICE** appears in the voice profile row. Choose it and say a sentence. → It speaks in the trained voice, and does not
  crash on the first word (the crash the patch step prevents). Short training means it will sound rough; what matters here is that it speaks.
- [ ] Run the listening test on the PC too, if you have `sherpa-onnx` there (the training guide, section 6). → It sounds like what the phone says.

## L. What to send back

For each section: **done**, **done with a difference** (say what) or **stopped here** (say why). Always with:

- The notes from section A, for each computer you used (Ubuntu, WSL).
- Section B: the last line of the test run, and any failure's first red line.
- Section D, **both** computers: what the job said after a minute with every terminal closed, and after a restart.
- Section I1: every sentence of the notes that was hard to follow or sounded like permission, how long the voice took to download, whether the refusals refused, and whether Amy's checkpoint trained.
- Section I2: whether round 2 started from round 1's file (the `--ckpt_path` lines), how long a stop by hand took, every `False` from the saved-file check, the two epochs for each round, and any sentence that was hard to follow.
- Section I: the card, the memory used, the batch size that worked, the seconds per epoch, how long `max_time` took, whether `last.ckpt` was in the folder you started from, the exit code, and how long Ctrl+C took.
- Section I6: whether every `--kind` brought the right files in, what the tool said when a file could not be read, how long listening took for how many minutes of audio, whether the file chooser was easy to use, and any sentence in the projects steps (especially the two delete questions) that left you unsure what would be removed.
- Section I7: for each part (A to D), the exact lines the one command printed, where it stopped or asked something this list did not expect, what you typed, how long each step took, and every sentence in a guide that was unclear or a command that did not work as typed. If the one command is not run on a clean Windows or a plain Ubuntu desktop yet, say so.
- Section I8: part B for each way of playing (heard or not, the exit number, any words it printed, and whether this is WSL or a native desktop), then the seconds `listen` took, which way played, whether the voice was clear, any word said differently on the phone, and whether you want other sentences.
- Section I9: how long a backup took for how big a project, the file's size, whether the reminder in part B was easy to notice, whether `verify` caught the changed byte, what the second restore in part I said, whether the left-out list in part C matched what you know is in the project, which folder you chose and why, and any sentence that was hard to follow.
- Section I10: how long `check` took, every line that was unclear, what each of parts B to D printed (especially the exit numbers and the files `ls` showed), how long the studio rebuild took and how big the two copies were, whether the line of letters and numbers before and after was the same, whether the old copy was ever unusable, and any sentence that was hard to follow.
- Section I11: the total part A listed and whether any row surprised you, whether the sums in parts A and E were the same before and after, what parts B and C printed (especially the exit numbers and what `find` and `ls` showed), what part D said, how long the removal and the setup afterwards took, how much room came back, and whether the lines about the menu entry and the tool's own files were clear.
- Section I12: what parts A to D printed (especially the exit numbers and that the line of letters and numbers was the same three times), how long the move to the real drive took and how big the scratch was, every warning the real drive gave, whether the lines of progress were steady, what the unplugged drive said in both places, and whether the sentences about the old place were clear.
- Section I13: what parts A and B printed (especially the exit numbers), what part C printed and how long it took (and whether any tag beginning with `voice-studio-` existed yet), and if part D was possible: how long the fetch took, how big the new copy was, the rows the comparison printed and whether they matched what you know changed, whether your own copy was untouched, what part F left behind, and for part G which sentence left you unsure which folder was which.
- Section I14: whether the two lines at the end of the failed command in part B were easy to find and follow, what parts A, C and D printed (especially the exit numbers), every name, folder or address of yours that was still readable in a report (parts A, B, E and F) and which kind it was, whether the report was something you would be willing to give a helper, and any sentence that was hard to follow.
- Section I15: for each of the five pages, whether you found it without help and whether the buttons did what their words said; **what the shown problem report held that you did not expect** (the most important line of this section); how long the look for releases took; whether the sounds played through the window in Hear the voice; and anything the keyboard or a screen reader could not reach.
- Section I16: whether the four steps for putting the file on the phone matched what your phone showed (make, model, Android version, the words of the menus, and the warning it gave); whether the code scanned at the first try; the address it chose and whether the phone could open it; how long the download took for how many megabytes; whether a device without the certificate got a warning and no file; what each part of D printed (especially the exit numbers); on WSL, the address, the networking mode and what you changed to make it work; and what was left in the certificate folder.
- Section I17: the report `check` printed against what Windows said (build, networking mode, WSL version), whether the two `ls` lines were the same, whether Notepad showed the changed file normally, whether the idle setting kept the job alive for five minutes (and your WSL version), whether the firewall command was accepted as printed (the whole message if not), what `wslinfo` and `ip` printed after the restart, whether the phone could open the address, and what else you had to change.
- Section I18: the exact words Windows used to warn about the unsigned file and whether Run anyway was easy to find; what each page looked like (anything cut off at your text size); how long the look, the WSL step, Ubuntu and the long step took; **whether Ubuntu registered without asking its own question**, and the exact words if it did ask; whether Windows asked for permission once and what it said; whether a restart was needed and whether the second run carried on; the contents of `installer.log`; whether the password appeared anywhere; whether the temporary permission file was gone after a success and after a failure; whether an existing account was left alone; and what the uninstaller left behind.
- Anything that printed a Python error, with its last five lines. Nothing in these steps should show one: a person should always get a sentence.
- Anything you would have wanted the screen to say differently. These sentences are the ones a helper will read.

## M. Clean up (only the folders this list made)

- [ ] Look first at how much room they take: `du -sh ~/ack-voice-check ~/piper/voice-check ~/piper/voice-check-2 2>/dev/null` (each training round keeps six checkpoints of 846 MB, so a few rounds are several GB).
- [ ] When you are finished and have saved what you want (the zip, your notes): `rm -r ~/ack-voice-check ~/piper/voice-check ~/piper/voice-check-2` (leave out a folder that does not exist on your computer; `voice-check-2` is
  where a second try goes when you do not want to reuse the first). These hold only what this list made. The programs the tool built (`~/ack-voice-studio`) are **not** in them and are not touched; they are meant to stay. The packages in your Downloads folder, your phone, ACK and your real recordings are not in them.
  The one place a copy of a package was kept for this list is `~/ack-voice-check/recordings/_freeform/en-US/incoming/`; if you want to keep
  the recordings you imported, copy that folder first.
- [ ] The pretend homes in sections I10, I11 and I12 are each removed by their own last step (`rm -r "$T"`). The folder section I14 saved a report in is removed by its part D. The folder section I15 made for a backup and a report is removed by that section's part F. The backups section I15 made in the tool's own backups folder stay (the tool never removes a backup; remove them yourself if you want them gone). The folder section I13 fetched a copy into is removed by that section's last step too; a copy you fetched with `--to` anywhere else is yours to remove, and the tool never removes one. The old copy of the programs from section I10 part E is removed by that part, and nothing else in `~/ack-voice-studio/tool` was made by this list except what section I11 part E removed and set up again.
- [ ] The certificate file section I16 made is the folder `~/ack-voice-studio/state/phone-certificate` (the certificate and its secret part, nothing else). Keep it if you will send to the phone again. The tool never removes it. When you are sure: `rm -r ~/ack-voice-studio/state/phone-certificate`, and remove the certificate from the phone in the phone's settings. If you moved it aside in part F, the same goes for `phone-certificate-old`.
- [ ] The pretend Windows user folder section I17 made is `C:\Users\ack-voice-check-user` (one file in it). Remove it yourself: `rm -r /mnt/c/Users/ack-voice-check-user`. The `.wslconfig.bak` copies next to your real `.wslconfig` are real backups: keep them, or remove them yourself when you are sure. The tool never removes one. The firewall rule, if you made it, is taken away with the command part D gave.
- [ ] The backups section I9 made are in `~/ack-voice-check-backups` (and `~/ack-voice-studio/backups` if you ever left the folder out). They are real backups, so keep them if you want them; look first with `du -sh ~/ack-voice-check-backups`, and when you are sure: `rm -r ~/ack-voice-check-backups`. The tool never removes a backup itself, and the project's delete question does not touch them.
- [ ] The small sound files section I8 made are under the project's `listening` folder, a few hundred kilobytes each time (and a large voice copy for each time you kept one in part E). Free up space offers them (section I3); or look with `du -sh ~/ack-voice-studio/projects/voice-check/listening` and remove the folder yourself when you no longer want them.
- [ ] The check project from section I1 is the folder `~/ack-voice-studio/projects/voice-check` (a project file and empty folders, and after section I2 a copy of the training set and every round's saved files, about 4.8 GB a round: look with `du -sh` first; nothing of value if you used it only for this list). To remove just that: `rm -r ~/ack-voice-studio/projects/voice-check`. **Keep the voices in `~/ack-voice-studio/tool/downloads/voices/`**: they are checked copies that cannot be fetched again if their host removes them, and every later project uses them.
