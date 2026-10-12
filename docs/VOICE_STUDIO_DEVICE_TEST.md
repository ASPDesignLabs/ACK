# ACK VOICE STUDIO: checking the first slice on your own computers (terminal only)

Everything in ACK Voice Studio's first slice was written and tested **without** the things that matter most in the end: a real graphics card,
a real WSL, a real phone, and a real training run. There is no window yet, so this list uses the terminal. It follows the path a voice takes:
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

**New, and not yet run on a real computer. This is the one section that removes files you made**, so it is written to be done slowly, and the first steps remove nothing. `free` only ever offers two things, and only from rounds
that have ended: a round's spare saved files (every saved file of it except the chosen round's saved point and the one before it), and a round's working files (the training program's scratch folder, which is never read again).
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
- [ ] Write down: how long it took, whether any wording confused you (the lines for a round's files, the question, the `Done.` line), whether you wanted a way to see the files before choosing, and whether the numbers in `--saved` were easy to read off the list.

## I4. Making the voice file with one command

**New, and not yet run on a real computer.** This does what section J does by hand, from the round you chose, in one command: it makes the voice from that round's saved file, gives it that round's own settings file, prepares it for the phone, makes the zip
file ACK takes, and reads the zip back as the phone would. It writes only into **one new folder** under the project's `exports` and never changes, replaces or removes anything that was there. It needs the project from section I2 with at least one finished
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
  → `Step 1 of 5: making the voice from the saved point.`, then steps 2 to 5, then `Done. The file to give to ACK is: …` with the path of the zip file, and the folder it is all in. If a step stops, it says which, what was left (`What was made so far is in …`) and that nothing was deleted;
  **copy the whole output**, and the `ls -l` of that folder. If the export stops with `GuardOnDataDependentSymNode` or asks for `onnxscript`, that decides whether the lock needs another package, as in section J.
- [ ] Look at what it made, and compare the settings file with the round's own:
  ```bash
  ls -l ~/ack-voice-studio/projects/voice-check/exports/*/
  python3 -m zipfile -l ~/ack-voice-studio/projects/voice-check/exports/*/*.zip
  ls ~/ack-voice-studio/projects/voice-check/rounds/config
  ```
  → The folder holds `my_voice.onnx`, `my_voice.onnx.json`, `my_voice.onnx.before-patch` and the zip file. `python3 -m zipfile -l` lists exactly `model.onnx` and `model.onnx.json`. The settings file is a copy of the chosen round's file in `rounds/config`: `cmp` that file with `my_voice.onnx.json`
  (give `cmp` both paths); it prints nothing when they are the same.
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
- [ ] Write down: how long it took, whether any wording confused you (the plan, the five steps, the `Done.` lines), whether you wanted the file somewhere else than the project's `exports` folder, and whether you wanted a name of your own for it.

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
  → A window titled `ACK Voice Studio - Voice check` with six pages on the left (Projects, Recordings, Training rounds, Voice file, Free up space, Display) and `Last result` at the bottom with `Nothing has been done in this window yet.` Write down: **how many seconds until it appeared**, whether anything is garbled, black or flickering,
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
  → `This would remove the project second-check: Second check. It cannot be brought back.` then what is in it (a project file and empty folders), `Before you go on, copy anything you may want later. Nothing here can be brought back.` and `Delete the project Second check for good? Type yes to go on.` Type **`no`**: `Nothing was removed.` and the folder is still there. Run it again, type **`yes`**, and see that it asks
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
- [ ] **Let the computer listen.** This needs the studio programs (section I0 or the guided setup) and the speech model (section E); if one is missing the tool says which, and what to run, and does nothing. The listening model is looked for in two places, in this order: the tool's own folder (`~/ack-voice-studio/tool/downloads/models/speech-small-en`, where the guided setup puts it) and the Hugging Face folder (`~/.cache/huggingface/hub`, where section E's `models fetch small.en` puts it); a copy in the second is used only if every file has exactly the agreed size and checksum, and nothing is copied, moved or changed. If it is in neither the tool says so and names both places: `The listening model is not on this computer yet. The guided setup downloads it after asking you. Run: python3 -m voice_studio`, then `It was looked for in …`. If the tool's own folder holds some of the files, or one that is not what was agreed (for example a download that was cut short), it says `The listening model in ~/ack-voice-studio/tool/downloads/models/speech-small-en is not complete, or a file in it is not what the guided setup agreed to. Nothing was changed or deleted. The guided setup fetches it again after asking you. Run: python3 -m voice_studio` (with the folder's full path):
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

- [ ] Start the window as in section I5. → **Six** pages on the left: Projects, Recordings, Training rounds, Voice file, Free up space and Display. It opens on **Recordings** when a project is opened.
- [ ] **Projects.** Press `New project…`, leave it empty and press `Make this project…`: the form stays open and says `Please fix these first:` with what is missing; what you typed is kept. Make `Second check` again (my own voice). A box shows the project and asks `Make this project?` with **No** where the focus starts. Then, with it chosen in the list, try `Edit details…`, `Put away…` (it leaves the list; tick `Show projects that are put away` and use `Bring back…`),
  `Show the folder`, and `Delete…`: it asks **twice**, and the first box lists what goes. Answer **No** to the second, then do it for real. Write down any button whose purpose was not clear, and whether a box ever left you unsure what would be changed.
- [ ] **Recordings.** Open the Recordings page. → `Recordings in Voice check`, the counts, one sentence on what to do next, and six buttons: `Bring in recordings…`, `Let the computer listen…`, `See what a training set would hold`, `Make a training set…`, `Look again` and `Show the folder`. The two steps that need recordings are greyed out until there are some.
- [ ] Press `Bring in recordings…`. → A form: `What kind of data is it?` with four choices **and none chosen for you**, each with one line on what it is; `Where is it?`. Press `Look at it…` with nothing chosen: the form stays open and says `Choose what kind of data it is.` and `Choose where it is.` Choose **Audio files with one table of sentences**: a box for the table's file name appears (leave it empty).
  Choose **An ACK package**: only one button is left, for the zip file; choose **Audio files, each with a text file** again and the place you picked before is forgotten, so a folder is never taken for a package.
- [ ] Press `Choose the folder…`. → The system's own file chooser, in your Windows or Ubuntu look. Choose `~/ack-voice-check/import-test/pairs` (a folder that was already imported is fine: it will say there is nothing new; try `real` if you made it). The form shows the path. `Choose a zip file instead…` takes a zip of the same files.
  Press `Look at it…`. → The form closes, and the same box as in the terminal appears with what was found, then the terminal's question, `Add 3 files to Voice check? Type yes to go on.`, without its last sentence (the box has Yes and No buttons), with **No** where the focus starts. Press **No**: `Nothing was done.` Press it all again and **Yes**.
- [ ] After a yes the page lists the new recording as `waiting to be listened to` and `Let the computer listen…` is usable. Press it: the same questions as the terminal. While it listens the page says `The computer is listening now. This page looks again by itself every few seconds.` and shows how far it has got; nothing else starts by itself. When it ends, press `See what a training set would hold`, then `Make a training set…`.
  → Same words as the terminal. Open **Training rounds**: the new set is in the list of sets. Write down: whether the file chooser was easy to use, how long the page took to notice the listening had ended, anything that moved or flashed, and whether any word was hard to understand.
- [ ] **A screen reader, if you use one:** move through the form with Tab. Write down what is read for each of the four kinds, `Choose the folder…`, and the problems that appear when the form is not whole.
- [ ] Clean up what this section made: `rm -r ~/ack-voice-check/import-test`. The recordings you imported are inside the project, `~/ack-voice-studio/projects/voice-check/recordings`, and stay until you delete the project or remove them yourself; `second-check` is already gone (section M has the rest).

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
- Anything that printed a Python error, with its last five lines. Nothing in these steps should show one: a person should always get a sentence.
- Anything you would have wanted the screen to say differently. These sentences are the ones a helper will read.

## M. Clean up (only the folders this list made)

- [ ] Look first at how much room they take: `du -sh ~/ack-voice-check ~/piper/voice-check ~/piper/voice-check-2 2>/dev/null` (each training round keeps six checkpoints of 846 MB, so a few rounds are several GB).
- [ ] When you are finished and have saved what you want (the zip, your notes): `rm -r ~/ack-voice-check ~/piper/voice-check ~/piper/voice-check-2` (leave out a folder that does not exist on your computer; `voice-check-2` is
  where a second try goes when you do not want to reuse the first). These hold only what this list made. The programs the tool built (`~/ack-voice-studio`) are **not** in them and are not touched; they are meant to stay. The packages in your Downloads folder, your phone, ACK and your real recordings are not in them.
  The one place a copy of a package was kept for this list is `~/ack-voice-check/recordings/_freeform/en-US/incoming/`; if you want to keep
  the recordings you imported, copy that folder first.
- [ ] The check project from section I1 is the folder `~/ack-voice-studio/projects/voice-check` (a project file and empty folders, and after section I2 a copy of the training set and every round's saved files, about 4.8 GB a round: look with `du -sh` first; nothing of value if you used it only for this list). To remove just that: `rm -r ~/ack-voice-studio/projects/voice-check`. **Keep the voices in `~/ack-voice-studio/tool/downloads/voices/`**: they are checked copies that cannot be fetched again if their host removes them, and every later project uses them.
