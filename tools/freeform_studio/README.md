# Freeform Studio

Capture free speech from your phone, have your PC transcribe it with word timings, then review and cut it into
training clips for Piper. It runs next to `piper-recording-studio` (its own port, its own venv) and shares its
`output/` folder.

**Status: all seven phases are in (Phase 7 of 7: backups and safety), plus dataset export.** You can record from your phone,
everything is saved to your PC as you speak, the PC transcribes it, you correct and approve pieces on your phone (or PC), the
approved ones are written straight into the recorder's own folder layout for your usual training steps, and your recordings
are backed up automatically. *Backups and safety* below says what is protected and how to restore; its last part says what has
only been tested without a real phone.

## Install (once)

```bash
git clone --depth 1 --branch claude/quirky-carson-ia01h1 https://github.com/ASPDesignLabs/ACK.git ~/ack-tools
~/ack-tools/tools/freeform_studio/install.sh
```
The installer makes its own virtual environment (`~/freeform-studio-venv`), so nothing here can disturb the recorder or your
training environment, installs the requirements, and then checks that every package loads and that the program starts. It needs
`ffmpeg` and Python 3.10 or newer (Ubuntu 22.04's defaults are fine); if either is missing it says so, with the exact `apt`
command, before changing anything. It is safe to run again: it reuses the environment and only adds what is missing. It writes only to that
folder (plus pip's usual download cache in your home folder); it never edits shell settings or installs system packages.

- `./install.sh --check` only looks and reports what is missing. `--dry-run` prints every command it would run.
- `--gpu` also installs the NVIDIA libraries for GPU speech recognition (see below). `--venv DIR` and `--python CMD` choose another
  environment folder or Python.
- Already cloned it earlier? Update with `git -C ~/ack-tools pull`, then run the installer again.

<details><summary>Prefer to do it by hand?</summary>

```bash
cd ~/ack-tools/tools
python3 -m venv ~/freeform-studio-venv
source ~/freeform-studio-venv/bin/activate
pip install --upgrade pip
pip install -r freeform_studio/requirements.txt
```
Check the Python version with `python3 --version`.
</details>

## Try the speech recognition on your machine (do this first)

Record any 20-60 seconds of yourself talking (a phone voice memo works), put it on the PC, then:

```bash
cd ~/ack-tools/tools && source ~/freeform-studio-venv/bin/activate
python -m freeform_studio.asr_smoke ~/some-recording.m4a --model small.en --device cpu
```
The first run downloads the model, so expect a wait. It prints what was heard, how fast, which words the model was
unsure about, and how the review screen would cut the recording. Add `--prompt "names or jargon you say"` to bias it
toward your vocabulary, or `--prompt "Um, so, uh, yeah."` to make it keep filler words instead of tidying them away.

**GPU (optional).** CPU needs nothing extra and is what to use while training runs. To use the GPU when it is free,
`./install.sh --gpu` installs the libraries and prints the `LD_LIBRARY_PATH` line to use; by hand it is:
```bash
pip install nvidia-cublas-cu12 "nvidia-cudnn-cu12==9.*"
export LD_LIBRARY_PATH=$(python3 -c 'import os, nvidia.cublas.lib, nvidia.cudnn.lib; print(os.path.dirname(nvidia.cublas.lib.__file__) + ":" + os.path.dirname(nvidia.cudnn.lib.__file__))')
python -m freeform_studio.asr_smoke ~/some-recording.m4a --model medium.en --device cuda
```
(`LD_LIBRARY_PATH` must be set before Python starts. This is faster-whisper's documented setup for CUDA 12.)
Don't run it on the GPU while training is running: 8 GB is not enough for both.

## Run the server

```bash
~/ack-tools/tools/freeform_studio/start.sh
```
This starts the server on your network with your mkcert certificate from `~/piper-recording-studio/certs` (if that folder
exists; otherwise it tells you the phone microphone won't work without https). Anything you add goes straight to the program and
wins over the defaults: `start.sh --asr-device cuda`, `start.sh --port 8002`. Settings can also come from the environment:
`FREEFORM_VENV`, `FREEFORM_CERTS`, `FREEFORM_OUTPUT` and `FREEFORM_BACKUPS` (see *Backups and safety*).

By hand, that is:
```bash
cd ~/ack-tools/tools && source ~/freeform-studio-venv/bin/activate
python -m freeform_studio --host 0.0.0.0 --certs-dir ~/piper-recording-studio/certs
```
`--certs-dir` finds your newest mkcert certificate and key in that folder by itself, so there are no file names to
type. (`--certfile` and `--keyfile` still work if you prefer them.) It refuses to start, in plain words, if the
certificate is missing, unreadable, or the port is taken, instead of printing a link that leads nowhere.

It prints two links: one for your phone and one for this PC, each with a private token. Open the phone link once and the
phone remembers it. The token is stored in `output/_freeform/token` (readable only by you). Use `--asr-engine fake` to
run without any speech model (placeholder words, for testing).

## Reviewing what was heard (phone or PC)

Open **Review** (the link at the top of every page, or `/review`). It lists your recordings; tap **Review** on one.

You work on **one piece at a time**, a sentence or two of speech cut at the pauses:

- **Play** plays exactly that piece (the same audio that would go into training) and stops by itself at its end. The word
  being spoken is highlighted. **Tap any word** to hear from there.
- **Fix the words** in the box. Words you leave alone keep their timing; words you change take over the old words' time.
  Words the recognizer was unsure about are underlined with dots, with a plain-language warning above them.
- **Approve and next** (big button, bottom right) or **Drop** (bottom left). Nothing moves on its own: no timers, no
  auto-advance unless you switch on *Play each piece when I move to it*.
- **Tags** `laugh`, `cough`, `noise`, `unclear`: pieces with these are left out of training even if approved.
- The **Show** menu narrows the list to *To review*, *Needs a look* (pending pieces with warnings), *Approved*, *Dropped*
  or *All*. **Next to check** jumps to the next piece still waiting. Where you stopped is remembered.
- **Approve all clean pieces** approves every pending piece with no warnings, after you confirm. It's there for the
  ones the recognizer got completely right; listen to a few first.

**Cut points, splitting and joining** (open *Cut points, split and join* under the text box)

- The **waveform** shows the piece with room around it. The shaded part is what will be kept; the pieces on either side are
  greyed. Small ticks along the bottom are where each recognized word begins. **Wider view / Closer view** change the room.
- **Move a cut point** by dragging its handle (the flag pointing right is the start, the one pointing left is the end), by
  focusing a handle and using the arrow keys (one step; **Shift** five steps; **Page Up/Down** half a second), or with the
  **Start/End earlier/later** buttons. Choose the step: 10 ms, 50 ms or 250 ms. A cut point stops at the neighbouring piece,
  at the edge of the recording, and 0.1 s before the other cut point, and says so.
- A run of nudges within a couple of seconds, or one drag, is **one undo step**.
- **Hear the start / Hear the end** play about 0.8 s at that edge (exactly what training will hear). *Play a short clip after
  each change* does it for you after every move; it is **off** unless you turn it on.
- **Trim silence** tightens a piece to the speech inside it, leaving a little room. It only ever shrinks a piece, and never
  cuts closer than 0.05 s to a word the recognizer found. It tells you how much it took, and Undo puts it back.
- **If a cut point falls inside a word** (less than 70% of the word is left in the piece) the piece gets a *cuts a word*
  warning, because the audio and the text no longer agree. Move the cut point or change the text and it clears itself.
  Pieces with this warning are left out of the training set even if approved, unless you pass `--allow cuts_word`.
- **Split**: tap a word (it also plays from there), then *Split before "word"*. Or tap the waveform to place a dashed
  **marker** (move it with its arrow keys, check it with *Hear around the marker*) and press *Split at the marker*. Splitting
  in the pause between two words is best. Both halves come back as "to review", and Undo makes them one piece again.
- **Join** a piece with the one before or after it. The pause between them becomes part of the clip. The result is "to
  review", and Undo splits it again. Anything that would be too long to train on gets the usual *long* warning.

**Numbers, symbols and abbreviations** (*Say it in words*, under the text box)

Training text should be spelled the way it was spoken. For each number, symbol or abbreviation in a piece you get buttons for
the likely ways to say it, labelled with what they mean: "2026" offers *twenty twenty-six*, *two thousand twenty-six* and
more; "$5.50" offers *five dollars and fifty cents*; "Dr." offers *Doctor* and *Drive*. **It never chooses for you**: a number
can be said several ways, so listen (tap a word) and pick the one you said. One tap replaces just that word, the warning
clears itself, and Undo puts it back. Email and web addresses are left alone.

**The text you read (reference)**

If you read from a document, paste it in the box on the Record page before you start, or later under *Text you read
(reference)* on the Review page. Each piece that lines up with it then shows **The text you read says**, with the words that
would change marked and listed, and two buttons: **Use this wording** or **Keep what I have** (it isn't offered again).

- It only ever proposes. Using it changes one piece, can be undone, and never approves anything.
- **Nothing you said is dropped, and nothing you didn't say is added.** Words you said that aren't in the text stay, shown in
  italics. Words in the text that you skipped don't come over. Digits and symbols in the text ("$20") never replace what
  you said ("twenty dollars"), whichever way you or the recognizer wrote them.
- A different word (not just a spelling difference) is flagged "listen before you accept it".
- Free speech between the readings simply doesn't line up, so it gets no proposal. Pieces are matched in reading order,
  so a sentence you read twice finds its own place. A piece read out of order is still found.
- The card summarises how many pieces match exactly, differ only in capitals or punctuation, differ in wording, or don't line
  up. **Use its wording on N close matches** applies it to every piece still waiting where the reference agrees closely and
  every difference is a small spelling one; it asks first and one Undo reverses all of them.
- Replacing the reference asks first and **keeps the old text** on your PC in the recording's `reference_history/` folder.
- **Ask the recognizer again, with hints** fills in names from your reference and the start of it as context (both editable),
  then listens to the whole recording again. That cuts it into **new pieces**, so it asks first, makes sure your latest
  changes are saved, and keeps your current pieces in *Earlier versions* (restorable, but not mixed with the new ones).
  It takes a few minutes and returns you to the recordings list while it works. If you have the speech model on the GPU, free
  it from training first.

**Your work is protected in layers**

- Every change is **saved to your PC about half a second later**; the line under the title says so in words.
- **Undo and Redo** cover every action (approve, drop, tag, a whole stretch of typing, bulk approve). The line next to them
  always says what the last change was. Reversible actions don't ask "are you sure?"; they can be undone instead.
  Actions that can't simply be undone (bulk approve, going back to an old version, reloading) ask first.
- **Earlier versions** keeps a snapshot every time you save (recent ones all, older ones thinned out). Restoring one keeps
  the version you leave, so a restore can itself be reversed.
- **Offline or the PC asleep?** Keep working. Changes are kept on the phone and sent when the PC is back. If the page was
  closed before they were sent, the next visit offers to restore them (and locks editing until you choose, so the
  saved copy can't be overwritten by accident).
- **Two devices at once?** If another device saved first, the changes are merged piece by piece. If both changed the same
  piece, yours is kept and the other is in *Earlier versions*.
- Your raw recording and the recognizer's original output are never modified.

**On a PC**: Space plays or stops, **A** approves and moves on, **D** drops, **J/K** or the arrow keys move, **N** is next
to check, **E** edits the text, **Ctrl+Enter** approves even while typing, **Ctrl+Z / Ctrl+Shift+Z** undo and redo.
Single-key shortcuts can be turned off (under *Keyboard shortcuts*) if speech input or a switch might press keys by
accident.

The page is built for one hand on a phone (big targets, controls at the bottom), keeps working for screen readers (labelled
controls, status messages announced politely, no information carried by color alone), and meets WCAG AA contrast in light
and dark mode.

## Training clips: export approved pieces into your recorder's folders

Open **Training clips (export)** on the Review page (this recording) or on the recordings list (all recordings), or use the
terminal. It writes each **approved** piece as `<take>_<piece>.wav` plus a matching `.txt` into
`~/piper-recording-studio/output/en-US/freeform/`, exactly like a prompted recording (`<group>/<id>.wav` + `<id>.txt`), so
your checks, your backups of `output/` and `split_long_takes.py` all work on it without special handling.

```bash
cd ~/ack-tools/tools && source ~/freeform-studio-venv/bin/activate
python -m freeform_studio.export --dry-run     # what would change, and which approved pieces are left out and why
python -m freeform_studio.export               # shows the same, then asks before writing
```

- **It only exports what qualifies:** approved, not tagged `laugh`/`cough`/`noise`/`unclear`, no cut point inside a word,
  1 to 11.5 seconds, not too quiet, not clipping. Approved pieces that don't qualify are listed with the reason, so you
  can fix them in Review.
- **Each clip is cut from your recording** (never from a copy), brought to a consistent level (peak about -3 dB, like
  `build_dataset`; `--no-normalize` keeps the original loudness), given a few milliseconds of fade so cuts never click, and
  converted to 22050 Hz mono 16-bit.
- **Nothing is ever deleted.** If you un-approve, drop, tag or re-cut a piece, its clip stops qualifying: the next export
  moves it (and the old version of any clip it replaces) to `output/_freeform/en-US/retired/<date-time>/`, outside the folder
  the splitter reads, with an `index.json` saying why. Run it as often as you like: unchanged clips are left alone, so
  re-exports are quick and the folder stays in step with your review.
- `manifest.json` in the folder says where every clip came from (recording, piece, cut points, text). `.presplit` tells
  `split_long_takes.py` these clips are finished (see below). Files you put in the folder yourself are never touched, but
  everything in it is treated as a finished clip, and it **refuses to use a folder that already holds recordings it didn't
  write** (a prompt group named `freeform`, say) rather than change how they're split.
- Edit in Review, not in the folder: the next export replaces a clip whose piece has changed (keeping the old one).
- Pieces from a recording that is being transcribed again are skipped, not removed.

**Two ways to a training set.** After exporting, the simplest is the step you already know:

```bash
python3 ~/tools/split_long_takes.py --input-dir ~/piper-recording-studio/output/en-US --output-dir ~/piper/my-dataset-split-2
```

which now includes the `freeform` clips beside your prompted recordings (a new `--output-dir`: re-running into an old one
leaves stale `.wav` files behind). Copy the updated `tools/split_long_takes.py` over your copy so it honours the `.presplit`
marker; with its default `--min-duration 12` an older copy already passes these clips (all under 11.5 s) straight through, but
a lower value would try to re-split them. The other way is `build_dataset` below, which reads your recordings directly and can
also include confident pieces you haven't reviewed. If you merge a dataset made from the export into a `build_dataset` run with
`--also`, pieces that are already in it are skipped (and listed in `excluded.txt`) so nothing is counted twice; re-export and
rebuild that dataset to refresh it.

## Turn your takes into a training dataset

```bash
cd ~/ack-tools/tools && source ~/freeform-studio-venv/bin/activate
python -m freeform_studio.build_dataset --dry-run     # preview only; writes nothing
python -m freeform_studio.build_dataset               # builds a NEW folder, never overwrites one
```

It reads the takes (and never changes them), keeps the pieces that are safe to train on, and writes `wav/` plus
`metadata.csv`, exactly what `piper.train fit` reads, along with `manifest.json` (where every clip came from) and
`excluded.txt` (everything left out, with the reason and the text, so you can judge the choices yourself). It then
prints the training command to run, including a fresh cache folder.

| Option | What it does |
|---|---|
| `--include clean` (default) | pieces you approved, plus pieces the recognizer was confident about |
| `--include approved` | only pieces you approved in review (recommended once you have reviewed enough) |
| `--include all` | everything not dropped; flags ignored |
| `--allow low_confidence,has_digits` | accept pieces carrying these flags anyway (`has_digits` is allowed by default; `--allow none` accepts no flagged piece at all; `cuts_word` is never accepted unless you name it) |
| `--also ~/piper/my-dataset-split` | mix in an existing dataset (repeatable) |
| `--exclude-tags laugh,cough` | leave out pieces carrying these tags (default `laugh,cough,noise,unclear`; `none` turns it off) |
| `--min-seconds` / `--max-seconds` | length limits, default 1.0 and 11.5 |
| `--no-normalize` | keep each clip's original loudness |
| `--out DIR` | where to write it (default `~/piper/freeform-dataset-<date-time>`) |

Pieces are also left out when they are too quiet, or clip repeatedly (a single stray full-scale sample is fine).

## Backups and safety

Your raw recordings are the one thing you can't get back, so they are protected in layers. Nothing in this section ever
deletes a recording or overwrites your edits.

**Automatic backups.** While the server runs it makes a backup two minutes after starting and then every 6 hours, **but only if
something has changed since the last one**, so an idle server writes nothing. Backups go to `~/backups/freeform-studio`.

- `--backup-dir DIR` (or `FREEFORM_BACKUPS=DIR` with `start.sh`) chooses the folder. **In WSL the default folder is inside WSL**,
  which is one `wsl --unregister` or disk problem away from gone, so point it at the Windows side
  (`/mnt/c/Users/<you>/freeform-backups`) or copy the newest file out now and then. A backup that lives only on the machine it
  protects isn't much of one.
- `--backup-every HOURS` changes the interval; `--no-auto-backup` turns the timer off (the **Back up now** button and the command
  below still work). The backup folder can't be inside `output/_freeform` (where the recordings live), so a backup can never back itself up.

**What a backup holds.** One `.tar.gz` with, for every recording: the raw audio exactly as received, `take.json`, your decisions
(`edit.json`), what the recognizer heard (`asr.json`), and the saved earlier versions of your edits, transcripts and reference
text. Left out on purpose: the decoded copy and waveforms (rebuilt from the raw audio) and the exported training clips (export
again). Every file is checksummed as it is written, and the finished archive is **read back and checked** before it counts; one
that doesn't read back correctly is thrown away and reported, never kept as if it were good.

**Keeping old backups.** The newest 30 are kept, plus the newest of each week for twelve weeks beyond those. That is the only
thing that ever deletes a backup, and it only touches files this tool named. Automatic backups always use these numbers; on the
command, `--keep N` changes the first one and `--keep 0` never deletes anything.

**By hand** (nothing here needs the server):
```bash
cd ~/ack-tools/tools && source ~/freeform-studio-venv/bin/activate
python -m freeform_studio.backup                      # back up now (does nothing if nothing has changed; --force to back up anyway)
python -m freeform_studio.backup --list               # your backups, newest first
python -m freeform_studio.backup --verify FILE        # re-read one and check every file against its checksum
python -m freeform_studio.backup --restore FILE --dry-run    # show what a restore would do, and write nothing
python -m freeform_studio.backup --restore FILE
```
**Restoring only ever adds.** Recordings you don't have come back; files that are identical are skipped; a file that is
*different* from the backup's is left alone and the backup's copy is put in `output/_freeform/<code>/restored-conflicts/`, so
nothing is lost either way. Afterwards it rebuilds the decoded audio, so restored recordings can be reviewed again. If one
recording's raw audio can't be decoded it says which, with the restore itself still complete and the others rebuilt.
It exits with `1` in that case so a script notices, even though every file is back. To remove something, delete it yourself; a
restore is never a way to do that.

**Status and safety card.** On the Review page's list of recordings, under the recordings and above *Training clips*, in plain words: how much disk is free (and about how many hours of
recording that is), when the last backup was and where backups go, with **Back up now**, and whether the speech model is holding
memory, with **Free memory now**. That last button is for when training needs the GPU: the model also frees itself after 5
minutes idle (`--asr-idle-unload`), and it reloads by itself the next time a recording needs it. It refuses, saying why, while a
recording is being processed.

**If the disk fills up.** Below `--min-free-mb` (500 by default) the server refuses *new* audio. The phone keeps every part it
couldn't send, says "your PC is out of disk space; sending carries on once there is room", and keeps retrying, so nothing you
said is lost; parts it has already sent are still accepted if re-sent. The phone and the Status card warn you well before that
(under 3 GB). The doctor (below) reports it too.

**Rebuilding the derived audio.** If a decoded copy or waveform goes missing (a restore, or you deleted it to save space), the
server rebuilds it from the raw audio when it starts. To do it yourself, or to see which recordings can't be rebuilt:
```bash
python -m freeform_studio.repair              # every finished recording that needs it (--take ID for one)
```
It never touches the raw audio or your edits. A recording that can't be rebuilt is named and left as it was; the others carry on.

**What has and hasn't been tested.** Everything above is covered by automated tests that use real ffmpeg, a real browser at phone
size and real archives, plus a real run of the installer into a fresh environment. What those can't show: a real phone's microphone,
battery and screen-off behaviour; real Whisper accuracy on your voice; Windows Firewall and WSL networking; backups written to
`/mnt/c/...` from WSL (file locking and speed on that file system); what a genuinely full disk does on your machine (the
test replaces the free-space reading rather than filling a disk); and whether **Free memory now** really hands the GPU back (the
button is tested with the stand-in engine; the real one drops its model and runs garbage collection, but the sandbox these were built
in can't download a model to measure it). Check that one yourself: run `nvidia-smi` in another terminal, tap **Free memory now**,
and watch the memory used by the Python process fall. If it doesn't, restart the server before training, which always works.
Also try a restore into a scratch folder with `--dry-run` once, so you know it works for you before you ever need it.

## If the page won't load

Run the checker in a **second terminal** while the server is running. It tests each link between your phone and this
program, changes nothing, and lists every problem with its fix, in order. It also reports free disk space (add
`--min-free-mb N` if you started the server with a different limit), whether you have a recent backup (`--backup-dir DIR` if
yours isn't the default), and any recordings waiting to have their decoded audio rebuilt:

```bash
cd ~/ack-tools/tools && source ~/freeform-studio-venv/bin/activate
python -m freeform_studio.doctor --certs-dir ~/piper-recording-studio/certs --port 8001
```

The usual causes, roughly most to least common:

- **The server isn't actually running.** Look at the first lines in its terminal; a startup problem is now stated plainly.
- **Wrong address.** It must start with `https://` (not `http://`) and include the whole link with `?token=...`. Without
  the token you get a short "unauthorized" message rather than the page.
- **Works on the phone but this PC's browser shows a warning.** Windows doesn't trust mkcert's authority (only WSL and
  your phone do). Click **Advanced**, then **Proceed**; that is safe on your own network.
- **Works on this PC but the phone can't connect.** Windows Firewall is blocking port 8001. You made a rule for port 8000
  earlier; this port needs its own. In an **administrator PowerShell**:
  ```powershell
  New-NetFirewallRule -DisplayName "Freeform Studio 8001" -Direction Inbound -Protocol TCP -LocalPort 8001 -Action Allow -Profile Private
  ```
  If Windows lists your Wi-Fi as a *Public* network, use `-Profile Any`. The doctor also prints a second command for
  WSL's own firewall if that is still not enough.
- **The certificate doesn't cover the address your phone uses.** The doctor says so and prints the `mkcert` command to
  make a new one.

## Using it on your phone

Open the link the server printed (the one with `?token=...`) in Chrome on your phone, once. After that the phone
remembers it. Tap **Start recording** and talk or read for as long as you like; there is no per-line tapping.

- **Everything is saved to your PC as you go**, in one-second parts. Each part is also kept on the phone until the PC
  confirms it, so a dropped Wi-Fi connection, a refresh, or a crash cannot lose what you said. If something didn't finish
  sending, the page offers **Send it now** the next time you open it.
- **Keep the screen on and this page in front.** The page asks the phone to stay awake, and warns you if the phone
  refuses or the page goes to the background (Android can stop the microphone for background pages).
- **The microphone is requested with echo cancellation, noise suppression, and auto gain turned off**, which is better
  for training data. The page shows what your phone actually applied. The recorder you used before asked for the
  browser's defaults, which normally have all three on; compare a take from each by ear.
- **Pause** stops recording without ending the take. **Stop and save** ends it and sends the last part.
- **Text I'm about to read (optional)**: paste a passage before you start; it is saved with the recording and will be
  used in a later phase to correct what the PC hears.
- **Stop automatically after** is off by default. Nothing else ever happens on a timer.
- Under **Recent recordings**, tap **What was heard** to read the transcript. Problems show in plain words with
  **Try again**.

The page loads only its own files (no outside scripts, no tracking), and its colors meet WCAG AA contrast in both light
and dark mode; a test guards that.

## Where things are saved

```
output/_freeform/<code>/takes/<take id>/
  raw.webm        the phone's recording, exactly as received (never modified)
  audio.wav       decoded working copy (48 kHz mono)
  asr.json        what the recognizer heard, with word timings and confidence
  edit.json       your decisions (text, cut points, keep/drop); every save is versioned in edit_history/
  take.json       status and details (including the reference text)
  reference_history/   earlier versions of the reference text, if you replaced it
```
Approved clips are exported to `output/<code>/freeform/` (see *Training clips* above); anything it replaces or stops
exporting is kept in `output/_freeform/<code>/retired/`. Backups are in `~/backups/freeform-studio` (see *Backups and safety*),
and a restore's different-from-backup copies are in `output/_freeform/<code>/restored-conflicts/`.
This folder is deliberately outside `output/<code>/`, so `split_long_takes.py` can never pick up half-reviewed audio.

## API

| | |
|---|---|
| `POST /api/takes` | start a take (optional `reference_text`, `label`) |
| `PUT /api/takes/<id>/chunks/<n>` | upload chunk `n`; safe to repeat or send out of order |
| `GET /api/takes/<id>/chunks` | what has arrived and what is missing (for resuming) |
| `POST /api/takes/<id>/finish` | assemble, decode, and transcribe (`?salvage=1` keeps what arrived before a gap) |
| `GET /api/takes`, `GET /api/takes/<id>` | list, and status of one |
| `GET /api/takes/<id>/audio` | the audio, with Range support so phones can seek |
| `GET /api/takes/<id>/peaks`, `.../peaks/<n>` | waveform data |
| `GET/PUT /api/takes/<id>/edit` | the edit document; a save with a stale `rev` gets `409` instead of overwriting |
| `PUT /api/takes/<id>/reference` | save or replace the text that was read (`text`); the old text is kept in `reference_history/` |
| `GET/POST /api/takes/<id>/export`, `GET/POST /api/export` | preview (GET) or write (POST) the training clips for one recording, or all of them |
| `GET /api/takes/<id>/edit/history` | saved versions of the edit document, newest first |
| `POST /api/takes/<id>/edit/restore` | bring one back (`name`, `rev`); the current version is kept first |
| `POST /api/takes/<id>/transcribe` | run again (`model`, `initial_prompt`, `hotwords`, `regenerate`+`force`) |
| `POST /api/asr/release` | free the speech model's memory (`409` while a recording is being processed) |
| `GET /api/status` | speech engine and whether it is loaded, queue, and `disk` (free MB, `low`, `critical`, hours left) |
| `GET /api/backup`, `POST /api/backup` | backup status; make one now (`{"force": true}` to back up even if nothing changed). `409` if one is already running |

## Tests

```bash
cd ~/ack-tools/tools && source ~/freeform-studio-venv/bin/activate
pip install pytest && python -m pytest freeform_studio/tests -q
```
The screens' pure logic (re-timing words after an edit, merging two devices' edits, splitting, joining, trimming, waveform geometry, spoken forms, matching against the reference, exporting) is also tested with Node, if it is
installed (`node --test` via `test_js_logic.py`; skipped otherwise). Set `FS_SHOTS=/some/dir` to save screenshots from the
browser tests.
The installer and launcher scripts are tested with a stand-in Python (`test_install_scripts.py`, needs only `bash`), so
they never touch the network.
The tests that run the real `split_long_takes.py` need `pip install pydub` and skip themselves without it. The browser tests (`test_capture_ui.py`, `test_review_ui.py` and friends) also need `pip install playwright` and a Chromium; they skip themselves
if either is missing.
