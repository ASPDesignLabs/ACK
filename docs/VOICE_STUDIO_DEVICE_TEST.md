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
| The trainer and its environment (from the training guide) | `~/piper1-gpl` (with `.venv`) |
| The base checkpoint (from the training guide) | `~/piper/checkpoints/base.ckpt` |
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

- [ ] `python -m freeform_studio.build_dataset --output ~/ack-voice-check/recordings --out ~/ack-voice-check/dataset-1 --dry-run`. →
  A report with what would go in, what would be left out and why. `ls ~/ack-voice-check` shows **no** `dataset-1`.
- [ ] The same without `--dry-run`. → `~/ack-voice-check/dataset-1/` holds `wav/`, `metadata.csv`, `manifest.json`, `excluded.txt`. A few
  cards are enough to check the plumbing; they are far too little for a good voice, and the advice about length will say so.
- [ ] The same command again. → Refused, exit code 2, "never overwrites a dataset"; nothing in `dataset-1` changed.
- [ ] `… --json | python3 -m json.tool` (with `--dry-run`). → Valid JSON with `result`, `included`, `left_out`.

## I. One short training round, on the graphics card

**This is the part nobody has been able to check.** It uses the graphics card and can take several minutes to load. Close other programs
that use it. The numbers you write down here replace the guesses in the code (batch size 12, 4 workers, check every 10 epochs, a 25-minute
round).

- [ ] In a **second terminal**, leave this running: `nvidia-smi --query-gpu=memory.used,memory.total --format=csv -l 5`.
- [ ] Start a round that stops itself after five minutes. It runs from a **new, empty folder**, because the tool will start it that way:
  ```bash
  mkdir -p ~/piper/voice-check/run && cd ~/piper/voice-check/run
  source ~/piper1-gpl/.venv/bin/activate
  python3 -m piper.train fit \
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
    --ckpt_path ~/piper/checkpoints/base.ckpt
  echo "exit code: $?"
  ```
  → It starts, prints progress, and **stops by itself** about five minutes after it started (not counting loading). Then `exit code: 0`.
  The findings, each of which decides something:
  - Did `--trainer.max_time` stop it by itself? How long after five minutes?
  - Is there a file `~/piper/voice-check/run/lightning_logs/version_0/checkpoints/last.ckpt`? (`ls -l` it.) It should be **there, in the
    folder you started from**, and about a gigabyte.
  - Was the exit code 0?
  - The highest `memory.used` the second terminal showed, the card's name and total memory, and the seconds per epoch the trainer printed.
  - If it ran out of memory, try `--data.batch_size 8` and write that down. If steps took tens of seconds, the batch is too big for the card.
  - If it says `No module named piper`, it was not installed so that other folders can find it; write that down.
- [ ] Start the same round again without `--trainer.max_time` and press **Ctrl+C once** after about a minute, then wait. → It shuts down on its
  own and leaves a `last.ckpt` in `lightning_logs/version_1/checkpoints/`. Write down how long the wait was and whether it did.
- [ ] Resume from the newest checkpoint, as the tool will (the highest `version_N`): the same command with
  `--ckpt_path ~/piper/voice-check/run/lightning_logs/version_1/checkpoints/last.ckpt` and a **new** `--data.cache_dir
  ~/piper/voice-check/cache-2`. → It starts from that file (the log says so), not from the base voice.

## J. Making the voice file

- [ ] Export, then give it its settings file with the exact name, then prepare it for the phone:
  ```bash
  python3 -m piper.train.export_onnx \
    --checkpoint ~/piper/voice-check/run/lightning_logs/version_0/checkpoints/last.ckpt \
    --output-file ~/piper/voice-check/my_voice.onnx
  cp ~/piper/voice-check/config.json ~/piper/voice-check/my_voice.onnx.json
  pip install onnx
  python3 ~/ack-tools/tools/patch_voice_for_sherpa_onnx.py ~/piper/voice-check/my_voice.onnx ~/piper/voice-check/my_voice.onnx.json
  ls -l ~/piper/voice-check/my_voice.onnx*
  ```
  → `my_voice.onnx`, `my_voice.onnx.json` and `my_voice.onnx.before-patch`. If the export stops with a `GuardOnDataDependentSymNode` error,
  the training guide says what to add (`dynamo=False`); write down that it happened, since the tool's launcher will carry that fix.
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

- [ ] Copy `my_voice_backup.zip` to the phone (cable or USB drive). On WSL, open `\\wsl.localhost\<distribution>\home\<you>\ack-voice-check` in Windows File Explorer's address bar (this needs no set-up;
  `explorer.exe ~/ack-voice-check` does the same when Ubuntu can start Windows programs, which the section D check tells you).
- [ ] ACK → Audio Architect → Custom Voice → **IMPORT VOICE BACKUP** → pick the zip. → ACK accepts it and restarts by itself.
  If it refuses, note the message on screen and, if you can, the lines `adb logcat -s ACK_VOICE_BACKUP ACK_CUSTOM_VOICE` print.
- [ ] A new chip **MY VOICE** appears in the voice profile row. Choose it and say a sentence. → It speaks in the trained voice, and does not
  crash on the first word (the crash the patch step prevents). Short training means it will sound rough; what matters here is that it speaks.
- [ ] Run the listening test on the PC too, if you have `sherpa-onnx` there (the training guide, section 6). → It sounds like what the phone says.

## L. What to send back

For each section: **done**, **done with a difference** (say what) or **stopped here** (say why). Always with:

- The notes from section A, for each computer you used (Ubuntu, WSL).
- Section B: the last line of the test run, and any failure's first red line.
- Section D, **both** computers: what the job said after a minute with every terminal closed, and after a restart.
- Section I: the card, the memory used, the batch size that worked, the seconds per epoch, how long `max_time` took, whether `last.ckpt` was in the folder you started from, the exit code, and how long Ctrl+C took.
- Anything that printed a Python error, with its last five lines. Nothing in these steps should show one: a person should always get a sentence.
- Anything you would have wanted the screen to say differently. These sentences are the ones a helper will read.

## M. Clean up (only the two folders this list made)

- [ ] When you are finished and have saved what you want (the zip, your notes): `rm -r ~/ack-voice-check ~/piper/voice-check`. These
  hold only what this list made. The packages in your Downloads folder, your phone, ACK and your real recordings are not in them.
  The one place a copy of a package was kept for this list is `~/ack-voice-check/recordings/_freeform/en-US/incoming/`; if you want to keep
  the recordings you imported, copy that folder first.
