# Guided voice setup (ACK Voice Studio): plan

**Status: DRAFT for review.** The question-and-answer session is done (27 decisions, section 6); nothing is built yet. Branch:
`claude/voice-studio-guided-setup` (started from `claude/nice-johnson-38v0sw`). Each decision in section 6 is the developer's; the
"proposed defaults" in section 6 were **not** asked about and are there to be vetoed. Tasks are cut so that one session can finish one
or two of them; the `Where tested` tag says what can be checked from the build sandbox and what only the developer's machines can.

## 1. What is being asked

Make installing and using ACK's custom-voice toolchain something a person with little technical know-how, but who understands what a file
is, can do: set it up, help a client or family member record a voice, run the training, and send the finished voice to a target device.

- Two supported platforms, one solution: **WSL (Ubuntu on Windows)** and **native Ubuntu LTS**.
- The whole experience is **GUI driven**.
- **One command** clones the ACK repository and starts the GUI setup flow.

## 2. Findings that shape the plan (from reading the repo, 2026-10-10)

1. **Three toolchains today, one with a GUI.** Freeform Studio (`tools/freeform_studio/`) is a local web app with a bash installer
   (`install.sh`, `start.sh`) and its own venv. The trainer (`piper1-gpl`) and the recorder it grew from (`piper-recording-studio`) are set up
   by hand from `docs/VOICE_TRAINING_GUIDE.md`. Everything after review is copy-paste terminal work: build dataset, `piper.train fit`,
   `export_onnx`, copy the config, `patch_voice_for_sherpa_onnx.py`, move files to the phone.
2. **The guide records ten-odd real breakages** from upstream moving (setuptools 82, torch 2.6 `weights_only`, `GuardOnDataDependentSymNode`,
   `val_mos`, a Cython build that `sudo` breaks, old checkpoints that no longer load, a stale cache that silently trains on old audio).
   A new installer must pin, not track upstream.
3. **The hardest steps for a non-technical helper:** getting WSL, GPU drivers, phone-microphone access over Wi-Fi (HTTPS certificate,
   trusting a certificate authority on the phone, WSL networking), and moving the finished voice onto the phone.
4. **ACK's IMPORT VOICE BACKUP takes one `.zip`** (`model.onnx` + `model.onnx.json`, `output/CustomVoiceBackupManager.kt`). The export step
   can hand over one file instead of the error-prone two-file pick. No change to the Android app is needed.
5. **The data-sovereignty rules bind this work** (`CLAUDE.md`, `docs/DATA_SOVEREIGNTY.md`): the server never goes online; network use is an
   explicit, ask-first module (today `models.py`); a test fails if a web address appears in a shipped file under `tools/freeform_studio/`;
   files are owner-only; every source file carries a GPL-3.0-or-later SPDX line; every outside dependency is listed in
   `THIRD_PARTY_NOTICES.md` with how its license was checked. Installing is the first time one tool needs *many* downloads (torch, a base
   voice, a speech model), so the rule has to be restated for the new package (task VS-1.3).
6. **The Android side already holds the same engine.** ACK runs sherpa-onnx; a PC-side check with the same engine can catch the
   "crashes on first synthesis" class of failure before the file reaches the phone (task VS-5.2).
7. **GTK 4.6 is the floor** (Ubuntu 22.04). Newer API (`Gtk.FileDialog` is 4.10+, much of libadwaita's newer widgets) cannot be used;
   24.04 has 4.14. The window code is written to the older API on purpose.
8. **Not testable from the build sandbox:** a real GPU, Windows/WSL, WSLg, GTK on a real desktop, a real phone, a screen reader. Every
   stage ends with a device-test checklist (the other `*_DEVICE_TEST.md` files are the model) and results from those come only from the developer.
9. **Training is the biggest disk user, and most of it is easy to miss.** The figures are mostly rough. A starting voice's checkpoint is 846 MB (from the
   Hugging Face listing); the guide says a run keeps up to about eleven of its own, which at that size would be about 9 GB if they match (unmeasured), and `lightning_logs/version_N` folders pile up; Freeform Studio's decoded copies take about 350 MB per hour
   of recording; every distinct audio state wants its own training cache; pip and Hugging Face keep their own download caches (the torch wheels alone
   are large). On WSL the Linux virtual disk grows with use and does not shrink by itself, so the Windows drive that holds it can fill first.
   Freeform Studio already refuses new audio below `--min-free-mb` (500 MB) and ACK's own capture screens stop before the last 100 MB; P11 extends
   the same habit, stop before the write fails, to the whole path.
10. **The starting voices carry a license chain.** Both `mike` and `amy` were fine-tuned from the lessac voice, which was trained on the Blizzard 2013
   Lessac data. A separate review of that data's license (summarised by another session; **not verified here**) says: research and exploration only,
   commercial use excluded, no redistribution, personal to the registered person and not sublicensable, revocable on written notice, Massachusetts
   law. Not hosting the data settles redistribution of the data. The research-only scope, and whether anything reaches a model trained from the data,
   are **unsettled**, and a declaration cannot settle them (D27). This repo holds none of it: no audio or model file has ever been committed on any
   branch (checked 2026-10-10).

## 3. Rules that apply to every task below

- Backups are encouraged and every edit to a person's files is confirmed first (the developer's standing preference). Nothing is moved or
  deleted without a checked copy; "copy in", never "move".
- The window never sees a password. Anything privileged happens once, in the terminal the person already has open (D5).
- Recordings, transcripts, datasets and the trained voice stay on devices the person controls: no cloud GPU, no upload, no telemetry, no
  background update check.
- **Decisions in plain Python, a thin GTK edge** (the pattern `capture/` and `core/` already use for ACK): everything the window decides lives
  in modules that import no GTK, so a plain Python test run covers them in the sandbox. The GTK files stay small.
- Each new source file: SPDX line. Each new dependency: `THIRD_PARTY_NOTICES.md` with how its license was checked. Each new download: in the
  registry (VS-1.3), sized, licensed, asked about first.
- Disk space is observed, never discovered by a failed write (P11): a budget before each big step, a watch while a job runs, and training stops
  before the recorder is ever refused.
- Wording: everyday words, details on demand (D19). A failed step says what happened, **whether anything was changed**, and the next step.
- Accessibility rules in section 6 (P6) apply to every screen.
- Every stage ends with the same four things: tests that pass in the sandbox, the device-test checklist items it adds, the docs it changes,
  and an update to the Progress table below.

## 4. Suggested order and why

**Risk first (D20).** Stage 0 is three small throwaway tests that only the developer can run, because each one could change the design:
GTK 4 under WSLg with a screen reader, a pinned training environment that really trains and exports on the GPU, and the name-restricted
certificate on a real phone. Their results are written into section 6 (and, if one fails, the decision it affects is reopened) before heavy
building starts. Stage 1 needs none of them and can run in parallel with Stage 0: it is all sandbox-testable decisions and scripts.
Stage 2 is the thin end-to-end slice (an ACK package in, one finished `.zip` out) with deliberately plain screens, so the whole path is
proven before any path is widened. Stages 3 to 6 widen it. The Windows helper (Stage 7) is late on purpose: it cannot be tested here, and it
wraps a Linux command that should be stable first. Docs (Stage 8) are written per stage as each lands; Stage 8 is the final pass.

## Progress

| Stage | Name | Status |
|---|---|---|
| 0 | Spikes (developer's machines) | Not started |
| 1 | Foundations (sandbox-testable) | In progress. Done: VS-1.1, VS-1.2, VS-1.3, VS-1.5, VS-1.6, VS-1.10, VS-1.11 |
| 2 | Thin slice: ACK package in, `.zip` out | Not started |
| 3 | Recording paths and helpers | Not started |
| 4 | Training rounds, in full | Not started |
| 5 | Send over Wi-Fi, export hardening | Not started |
| 6 | Safety net: backup, update, uninstall, delete | Not started |
| 7 | Windows helper | Not started |
| 8 | Docs, device test, release | Not started |

## 5. Tasks (stages)

Sizes: **S** under a session, **M** about one session, **L** more than one. `Where tested`: **sandbox** = the build sandbox can prove it;
**dev** = only the developer's computer; **phone** = needs a real phone. `After` = what must be done first.

### Stage 0: Spikes (throwaway code, real findings)

Gate: the findings are written into section 6, and any decision they contradict is reopened before Stage 2.

- **VS-0.1 GTK 4 on the real targets (M, dev, after nothing).** A tiny window with the widgets the app needs (labels, buttons, a progress bar,
  a text view, a file chooser, an image for a QR code, a notification) and a `.desktop` entry. Run it on Ubuntu 22.04 (GTK 4.6), 24.04
  (4.14) and WSLg. Record: does it start from the Windows Start menu; renderer glitches and the workaround; scaling and text size; clipboard;
  opening the Windows browser from inside WSL; playing a `.wav`. **Screen readers:** Orca on native Ubuntu (every control reachable and
  announced); what Narrator or NVDA can and cannot see in a WSLg window. Done when: a findings note says go, go-with-limits or no-go for
  WSLg, and what to tell Windows users who rely on a screen reader.
- **VS-0.2 Pinned training environment on the GPU (L, dev).** Build a venv from a proposed lock (exact torch, setuptools, onnx and friends) and
  a fixed `piper1-gpl` commit on both 22.04 and 24.04. Train a few minutes from each starting voice (Mike first, then Amy; D25) on a small dataset, export,
  patch, synthesize with sherpa-onnx on the PC, import the zip into ACK on the phone. Record exact versions, wheel and disk sizes, the disk cost per hour of recording, per checkpoint and per round (for P11), GPU
  memory used at each batch size, the minimum driver, build time, and which upstream problems needed a wrapper versus a source patch. **Run the trainer with the network off** (for example in a loopback-only namespace) after setup: the trainer fetches its `val_mos` quality scorer from GitHub on the
  first run (`DATA_SOVEREIGNTY.md` section 2), which would break "the server never goes online". If it needs that fetch, the scorer goes into the registry and onto the
  setup consent list, fetched at setup and not at the first training. Also time the training cache and a checkpoint write on the Linux disk, on a
  Windows drive seen from WSL, and on a USB drive, to set D24's slow-drive warning.
  Done when: a lock file, a verdict on each starting voice (does its checkpoint load and train with the pinned trainer; both are expected to, and a replacement is named for any that does not), a batch-size-by-memory table and the wrapper list exist.
- **VS-0.3 Phone HTTPS (M, dev + phone, after nothing).** Generate a CA restricted by name constraints to one LAN address and a leaf for
  that address; install the CA on the developer's Android phone(s); confirm the browser can use the microphone at `https://<ip>:port`;
  change the computer's address and re-issue the leaf without touching the phone. Also try WSL mirrored mode and the firewall allowance.
  Done when: it works (D16 stands) or does not (fall back to mkcert, reopen D16), with phone model and Android version noted.
- **VS-0.4 Gate review (S, with the developer, after 0.1 to 0.3).** Update section 6 with the results; reopen any decision they break.

### Stage 1: Foundations (all sandbox-testable)

- **VS-1.1 Skeleton, licenses, test runner (S, sandbox). Done 2026-10-10.** `tools/voice_studio/` package (name subject to P1), SPDX test for it,
  `run_tests.sh`, `THIRD_PARTY_NOTICES.md` rows for every planned dependency (PyGObject/GTK, a QR library, `cryptography`, sherpa-onnx,
  torch and the training stack) with how each license was read.
- **VS-1.2 Preflight (M, sandbox). Done 2026-10-10.** Pure functions that read command output and say: Ubuntu release (22.04/24.04 or "unsupported, here is
  why"), WSL or native (and WSL version), a display is available, GPU and memory (`nvidia-smi`), free disk (on WSL, both inside Linux and on the Windows drive that holds its virtual disk), RAM, Python and `venv`, git,
  ffmpeg, which system packages are missing, and the drives that could hold scratch (mount point, filesystem, free space, removable or not). Fixtures are written from the documented formats (the sandbox has no GPU or WSL) and are to be replaced with captures from your machines during the spikes; the thresholds marked PROVISIONAL in the code (GPU 7,900 MiB, RAM 7,000 MiB) are guesses until VS-0.2 measures them. Returns a result the bootstrap prints and the window
  shows. No GPU is a *state*, not an error (D4).
- **VS-1.3 Download registry and consent (M, sandbox). Done 2026-10-10.** One file lists every download (name, source, size, checksum, license, why).
  One module is the only code allowed to touch the network and it refuses without a consent record. Tests: no web address anywhere else,
  no socket/urllib/subprocess-to-curl anywhere else, a consent record must name each item, every entry is pinned to a revision and a checksum, and a test fails if any starting-voice or dataset file is committed to the repo (D27). The no-network test style from
  `freeform_studio/tests/test_no_network.py` is the model, extended to this package. **As built:** three kinds of proof. The source of every file is read (only
  `core/fetch.py` imports a network library; only it and `core/system.py` start a program; a web address is allowed only in `data/sources.json` and, later, `get.sh`);
  `System.run` refuses network programs at run time (curl, pip, git, apt, ssh, `python -m pip`, also behind sudo or env); and `fetch` refuses without a
  consent record that covers *exactly* the address, size and checksum that were shown. An entry with no address is listed and sized for the disk estimate but cannot
  be fetched until it is pinned; nothing is half pinned. The two starting voices and the speech model are in the registry unpinned: their addresses, revisions and
  checksums come from VS-0.2 and VS-4.1. The loopback-only egress test (as Freeform Studio has) comes when there is a whole flow to run (VS-2.9).
- **VS-1.4 Bootstrap scripts (M, sandbox).** `setup.sh` (the `git clone ... && run` route) and `get.sh` (the `curl` route, D14): preflight, list
  of `apt` packages with a one-line reason each, ask yes/no, `sudo apt-get install`, then hand over to the window; also `--check` and
  `--dry-run` like `install.sh`. Never edits shell settings. Driven by stand-in commands in tests, as `test_install_scripts.py` does.
  Prints a plain message and stops if no display is available (P7).
- **VS-1.5 Project model (M, sandbox). Done 2026-10-10.** `project.json` (versioned), folder layout (recordings, dataset, checkpoints, rounds, exports,
  backups), the consent note, "whose voice", and a read-only detector for old setups (`~/piper-recording-studio`, `~/piper1-gpl`,
  `~/freeform-studio-venv`, `~/piper`). Schema evolves the way `AckBackup` does: unknown fields are ignored, missing ones are "no change". **As built:** everything lives under `~/ack-voice-studio/`
  (`projects/<id>/` with `recordings/`, `rounds/`, `exports/`, `scratch/`; `tool/` for downloads and environments; `state/` for the consent record: `core/paths.py`). A
  project is `project.json` (schema 1): name, whose voice, the consent note (required to continue for someone else's voice: who agreed, what to, when, how to withdraw, and
  how it was given, which includes spoken, through a guardian and using AAC), planned hours, starting voice, scratch place and the D27 acknowledgments. Fields a newer
  version added are kept when this one saves; a file from a newer version is refused for writing, a damaged one is reported and never touched, and each save keeps the
  version it replaces, byte for byte, as `project.json.previous`. Typed text keeps zero-width joiners (Hindi, Persian, emoji). The folder name comes from the person's
  name (a non-Latin name becomes `person`, a repeat gets `-2`). `core/legacy.py` looks for the old setup and counts what is there without changing anything; the copy-in
  itself is VS-3.4.
- **VS-1.6 Job supervisor (M, sandbox). Done 2026-10-10.** Start a long job detached (training, dataset build, speech recognition), write a pid file and log,
  report status after the window closes or the computer restarts, stop gracefully (the guide's single Ctrl+C), refuse to start a second
  GPU job. Check what `freeform_studio/jobs.py` already offers before writing anything. **Checked:** it is an in-process asyncio queue for transcription takes, so nothing
  in it can run a command that outlives the window; this is new code. **As built** (`core/jobs.py`, `core/jobrunner.py`): a job is a folder under `state/jobs/` of plain files
  (`job.json`, `runner.json`, `log.txt`, `stop.json`, `result.json`), so its state can be read after the window closes or the computer restarts. A small detached runner (started by
  a double fork, so the window holds no child) runs the command in its own process group and writes the result last. Whether the runner is still the runner is decided from its
  pid, its start time and the boot id, so a reused pid or one from before a restart is never mistaken for it, and a zombie does not count. A stop is a file the runner polls: it
  sends **one** Ctrl+C-equivalent however often it is asked, and only an explicit force stop sends terminate and then, after a grace time, kill. A command that dies or fails has
  its leftover workers killed. One GPU job at a time, and a stopping job still holds the GPU. A job gets Hugging Face's libraries in offline mode and network programs are
  refused. `core/jobs.py` and `core/jobrunner.py` joined `system.py` and `fetch.py` as the only files that may start a program (held by the network-rules test).
- **VS-1.7 Text catalog and wording lint (S, sandbox).** All visible text in one catalog (gettext) so translations can follow; a test fails
  on jargon in default labels (checkpoint, epoch, venv, tensor, ONNX... except under Show details) and on a string with no Show-details
  partner where a command runs.
- **VS-1.8 Problem report builder (M, sandbox).** Builds the text the helper sees *before* saving: versions, step names, error text.
  Redacts user name, home folder, project and person names. Tests plant canary strings and fail if one survives. Never includes
  recordings, transcripts or phrases.
- **VS-1.9 Environment builder (L, sandbox with stand-ins, real run in dev).** Creates the venvs from the lock with hashes, builds
  `piper1-gpl`'s native part, runs a self-test, is idempotent and resumable, never touches an existing environment, and writes what it did.
  Applies fixes by wrapper; a source patch (if VS-0.2 found one unavoidable) is shown, backed up and applied only on confirmation.
  After: VS-0.2.

- **VS-1.10 Disk budget (M, sandbox). Done 2026-10-10.** Pure functions for P11: the three kinds of files (precious, rebuildable, disposable), an estimate from the
  planned recording time, the floors, a check before every step that writes a lot, a monitor decision while a job runs (fine, low, stop
  gracefully), and a proposal of what could be freed, with sizes; all of it per drive, since scratch can be elsewhere (D24), and with the start number of D26
  (both starting voices, two people). The numbers come from one table filled in by VS-0.2; until then it carries the
  guides' rough figures marked unmeasured. Boundary tests: exactly at a floor, one MB either side, a drive that fills during a round, a drive that
  reports nothing, and that training always stops before the recorder would refuse new audio. **As built:** `core/diskbudget.py`, with every figure in the size table labelled by
  where it came from (listing, Freeform Studio's own, computed, guess) so the screens can say the estimate is rough until VS-0.2 measures it. The 400 MB per recorded hour
  and the 500 MB recorder floor are Freeform Studio's own, held equal by tests. The start estimate always counts at least two people (D26); three answers (enough, tight,
  not enough) are judged per drive, the worst deciding, so an enormous project drive cannot hide a too-small scratch drive; training's stop floor is the recorder's floor
  plus one checkpoint plus slack, so a full disk can end a round but never costs a recording; the clean-up list can never include precious, protected or tool items.

- **VS-1.11 Scratch location rules (M, sandbox). Done 2026-10-10.** Pure functions for D24: take a candidate place plus captured `/proc/mounts`, `df` and `lsblk`
  output and say accept, accept-with-warning (and which warning) or refuse (and the plain reason), for the filesystem groups, synced folders,
  read-only and unwritable places, the same-device check and the marker file. A quick speed test is a separate function around a stand-in
  writer. Boundary tests: each filesystem name, a mount point that is not mounted, a marker holding another project's id, a path through a
  symbolic link, and a candidate inside another project's folder. **As built** (`core/scratch.py`): the person chooses a *place* and the tool makes
  `<place>/ack-voice-scratch/<project id>/` with a `.ack-voice-scratch` marker naming the project; every job start checks the marker, so an unplugged USB drive (an
  empty folder on the main disk) can never be written into. A place is refused if it is FAT, a network drive, a RAM disk, read-only, unwritable, a system folder or `/`,
  cloud-synced, inside this or another project, a folder under `/media`, `/run/media` or `/mnt` that is really on the main disk (not mounted), or already holds someone
  else's or an unmarked scratch. It is accepted with warnings for NTFS or exFAT, a Windows drive on WSL (slow, loose permissions), an unknown filesystem, a removable
  drive, or the same drive as the project. The slow-drive cutoffs (30 MB/s, 200 small files a second) are provisional until VS-0.2. `System` gained `realpath`, `is_dir`,
  `writable`, `device_of` and `listdir`. The mount tables are written from the documented formats until the spikes capture real ones.

### Stage 2: Thin slice (an ACK package in, one `.zip` out, plain screens)

- **VS-2.1 Window shell (M, dev).** `Gtk.Application`, main window, navigation (Setup, Projects, one project), the accessibility baseline
  (P6), the `.desktop` entry and an icon with no binary-asset problem. The widget code uses GTK 4.6 API only (finding 7). After: VS-0.1.
- **VS-2.2 Setup flow (L, sandbox for logic, dev for the screens).** Preflight results → the disk it will need to start against what is free (P11, D26) → one consent list for every download (sizes, sources,
  licenses) → environment build with progress → self-test → done. Resumable after a closed window or a lost connection; a Show details
  expander with the real commands and log; a GPU-locked state that still lets everything else proceed. After: VS-1.2, 1.3, 1.9, 2.1.
- **VS-2.3 Projects (M, sandbox + dev).** List and create: whose voice (mine, someone else's); for someone else's, the consent note
  (who agreed, what to, when, how it can be withdrawn, how it was given) is required to continue (D21). It also asks roughly how long the recording will be, which sets the project's disk budget (P11). The starting voice is chosen here too (D25; the thin slice has only Mike and VS-4.1 adds the
  choice), and an Advanced section lets the person put scratch on another drive (D24, VS-1.11). After: VS-1.5, 2.1.
- **VS-2.4 Import an ACK package (M, sandbox + dev).** File chooser → `freeform_studio.ack_import` → counts, minutes, any problems in plain
  words. The package is never deleted. After: VS-2.3.
- **VS-2.5 Dataset (M, sandbox + dev).** A friendly wrapper over `build_dataset`: preview, build, show minutes and what was left out and
  why; refuses to overwrite; always a fresh cache folder (the guide's stale-cache rule).
- **VS-2.6 One training round (M, dev).** Start, progress, stop cleanly at the end of the time. One starting voice, Mike (D25), hard-coded.
  After: VS-1.6, 2.5.
- **VS-2.7 Listen (M, dev).** Export the latest checkpoint to a temporary `.onnx`, patch it (reusing `patch_voice_for_sherpa_onnx.py`),
  synthesize three test sentences with sherpa-onnx, play them. What you hear is what the phone will say. After: VS-2.6.
- **VS-2.8 Export and "what now" (M, sandbox for the zip, dev for the screen).** Write `my_voice_backup.zip` in ACK's layout, open its
  folder, show picture-style steps (copy to the phone, ACK → Audio Architect → IMPORT VOICE BACKUP). The screen also says what the voice descends from and that publishing it is a separate decision (D27). After: VS-2.7.
- **VS-2.9 Thin-slice device test (M, dev + phone).** The whole path on the developer's Ubuntu and WSL machines, then in ACK. Written up in
  `docs/VOICE_STUDIO_DEVICE_TEST.md`. Gate: findings reopen decisions before widening.

### Stage 3: Recording paths and helpers

- **VS-3.1 Freeform Studio from the window (M, dev).** Start and stop its server per project (`--output <project>`), with the token and
  certificates, and open the right page in the right browser (in WSL, the Windows one). Reuse its existing start-up refusals and messages.
- **VS-3.2 PC microphone path (S, dev).** Guided: localhost, no certificate. Tells the helper which browser and microphone are used.
- **VS-3.3 Reading material (L, sandbox + dev).** Easy public-domain passages and a phonetically balanced sentence list (D18), each with its
  license read and logged in `THIRD_PARTY_NOTICES.md` before it ships. A loader that puts a chosen passage into the Record page's
  reference-text box (Freeform Studio change, with tests). Pasting your own text and free speech stay as they are.
- **VS-3.4 Copy in an existing setup (M, sandbox + dev).** Detect → show what was found → checked backup → copy into a project → verify →
  leave the originals. Reuse the old training environment only if it matches the lock (D13). After: VS-1.5.
- **VS-3.5 Phone over Wi-Fi: certificates (M, sandbox + phone).** Generate the restricted CA and a leaf for the current address (D16), re-issue
  when the address changes, show Android install steps for the CA file, and a QR code that opens the Record page. Chain verified with
  `openssl` in tests. After: VS-0.3.
- **VS-3.6 WSL network guidance (M, dev).** Detect the networking mode and the firewall state; explain; on a yes write `.wslconfig` (keeping
  `.bak`); show the firewall command to run as administrator; never restart WSL, and warn that training must be paused first (D17).
- **VS-3.7 Recording progress (S, sandbox).** "About X of 60 minutes", quality hints from the existing `ack_checks`, the disk left for the rest of the plan (P11), and what to do next.
- **VS-3.8 Retire the old recorder from the guided path (S).** Not installed or offered; the manual guides keep it (D23).

### Stage 4: Training rounds, in full

- **VS-4.1 Base voice list (M, sandbox + dev).** Mike and Amy (D25), as judged in VS-0.2: each with its license text shown before download (its dataset and license, and that it was itself fine-tuned from lessac, as its model card says) and a consent-gated fetch (both are on the setup
  consent list, and either can be declined and fetched later), the plain male-voice or female-voice choice with one line saying the starting
  voice only gives training a head start,
  checksum, and a compatibility check (the guide's old-checkpoint test) so an unusable file is explained, not crashed on. Never bundled or mirrored. The acknowledgment of D27 is part of the fetch: one click per voice, recorded with the
  date and revision, on a screen that never says or implies that use is permitted. The downloaded file is kept as a checked copy (see P11).
- **VS-4.2 Rounds engine (L, sandbox).** Many rounds; always resume from the person's latest checkpoint, never the base; go back to a
  previous round; rotate the cache folder whenever the audio changes; find `lightning_logs/version_N`. A state machine with boundary tests.
- **VS-4.3 Automatic settings and guards (M, sandbox + dev).** Batch size from the VRAM table (VS-0.2), free the speech model before
  training (the 8 GB rule), the disk guard from P11 (check before a round, watch during it, stop gracefully before a write can fail), refuse a second GPU job.
- **VS-4.4 Survive closing and rebooting (M, dev).** Reopen shows the true state; a silent desktop notification when a round ends
  (no sound, no vibration, no auto-advance: it only tells).
- **VS-4.5 Listening UX (M, dev).** Compare rounds, a note per round, "use this round", "go back".
- **VS-4.6 Plain failure messages (M, sandbox).** Map each failure in the guide's troubleshooting table to a plain message plus the safe next step.

- **VS-4.7 Free up space (M, sandbox + dev).** A screen that lists what could be removed, grouped as in P11 (older rounds' checkpoints, temporary
  listening files, old caches, download caches), with sizes, and one confirmation for exactly what is ticked. It never lists, and cannot remove,
  recordings, transcripts, the consent note, a backup, or the chosen round's checkpoint and the one before it.

### Stage 5: Send over Wi-Fi, export hardening

- **VS-5.1 One-time HTTPS download (M, sandbox + phone).** Serve only the finished zip, once, with a one-time token; QR code; stops by itself.
  The phone saves it to Downloads; the screen then shows the ACK import steps. Reuses the certificates from VS-3.5 (D10, D16).
- **VS-5.2 Export hardening (M, sandbox + dev).** The `dynamo=False` problem handled by wrapper; config copy; patch with its backup; a
  sherpa-onnx round-trip on the PC that mirrors ACK's rules (single-codepoint tokens, metadata present, size ceilings) so a bad file is
  caught before the phone sees it; a model card (base voice, its license and the chain behind it (for example mike, fine-tuned from lessac), the acknowledgment made for it (date and revision), project, date, versions, a consent summary without personal detail).
- **VS-5.3 Zip contract check (S, sandbox).** A test pins the zip's entry names and limits to `CustomVoiceBackupManager` /
  `CustomVoiceRepository` so a change on the Android side fails here.

### Stage 6: Safety net

- **VS-6.1 Backup now (M, sandbox + dev).** A checked archive to a folder outside OneDrive/Documents (on WSL, the Windows side), a hard
  nudge after recording and before training, additive restore. Reuse `freeform_studio/privacy.py`'s sync warnings. Checks there is room, here and at the destination, before it starts, and leaves out the
  rebuildable and disposable kinds (P11).
- **VS-6.2 Update (M, sandbox + dev).** A button that asks before contacting the internet, fetches a tagged release, shows what changes,
  builds the new environment beside the old one and switches only after the self-test passes. Never automatic (P4).
- **VS-6.3 Uninstall and delete (M, sandbox).** Uninstall removes the tool and environments, never a project. Deleting a person's data asks
  twice, names a backup first, covers scratch wherever it lives (naming the drive, and saying what it could not reach if it is not plugged in),
  and is driven by a storage catalogue with a test that fails if a new folder is in no area (the `StorageCatalogue` idea). Each area is also marked precious, rebuildable or disposable (P11).
- **VS-6.4 Problem report everywhere (S, dev).** The button on every failure screen, content shown first, saved only where the helper chooses.

- **VS-6.5 Move scratch (M, sandbox + dev).** Change the scratch location of an existing project (D24): check the new place with VS-1.11 and
  its room, copy, verify, switch, and only then offer to remove the old copy. Refuses while a job is running.

### Stage 7: Windows helper

- **VS-7.1 PowerShell script (L, dev).** Check the Windows build and virtualization, `wsl --install -d Ubuntu-24.04`, handle the reboot and
  pick up afterwards, then run the same Linux command inside it and open the window; nothing is installed on Windows beyond WSL and the distro. Written
  and linted in the sandbox, run only on the developer's Windows.
- **VS-7.2 Windows-side checks (S, dev).** NVIDIA driver version through the Windows side, WSL version, a clear message for each failure.
- **VS-7.3 Clean-Windows device test (M, dev).** On a computer that has never had WSL.

### Stage 8: Docs, device test, release

- **VS-8.1 Beginner guide and helper handout (M).** `docs/VOICE_STUDIO_GUIDE.md`; a one-page handout for a helper; plain words.
- **VS-8.2 Existing guides (S).** `VOICE_TRAINING_GUIDE.md` and `VOICE_DATA_WSL_GUIDE.md` become "the manual route" with a pointer to the guide.
- **VS-8.3 Data sovereignty (S).** New rows in `DATA_SOVEREIGNTY.md` section 2 (setup downloads), the new files in section 1, the test list in section 7.
- **VS-8.4 Notices and changelog (S).** `THIRD_PARTY_NOTICES.md` (the starting voices and the chain behind them are listed there too: fetched, not shipped), `CHANGELOG.md`, and a short section in `CLAUDE.md` once the design is real.
- **VS-8.5 Device-test doc (M).** `docs/VOICE_STUDIO_DEVICE_TEST.md`, grown stage by stage, finished here.
- **VS-8.6 Release and "bump the pin" runbook (S).** How a tag is cut, how the lock and the base-voice list are re-verified (VS-0.2 repeated), how the clone command's tag is updated.
- **VS-8.7 Optional: an ACK HELP pointer (S).** A HELP walkthrough step that says where the desktop tool is. Only if wanted; HELP is translated into five languages, so it is not free.

- **VS-8.8 Read the licenses (S, developer).** Read Amy's license ("See URL") and keep a dated note of each starting voice's license as read. Revisit
  the D27 wording if anything the developer learns, from the licensors or anywhere else, changes it. Nothing else waits on this.

## 6. Decisions

### Decided (2026-10-10)

| # | Topic | Decision |
|---|---|---|
| D1 | GUI shape | **Native desktop window** as a control center. The phone-facing **Record** and **Review** pages stay web pages and open on demand from it. |
| D2 | Native toolkit | **GTK 4** (PyGObject from Ubuntu's packages), proved by Stage 0 on the developer's WSL and Ubuntu machines, including a screen reader. |
| D3 | Windows entry | **A Linux command first**; a PowerShell helper that sets up WSL and then runs the same command comes in Stage 7. |
| D4 | No GPU | **Check first, then guide.** Recording, review and dataset export still work; Train explains why it is locked and offers the dataset on a USB drive for another computer the person owns. No cloud GPU, no CPU training. |
| D5 | Admin rights | **The terminal asks once, up front**: the exact `apt` packages and why, yes/no, password typed in the terminal. The window never sees a password. NVIDIA drivers on Ubuntu are detected and explained, never auto-installed. |
| D6 | Recording paths | **All three**, each with guided setup when chosen: the ACK phone app plus a USB-carried package; the PC microphone at localhost; the phone's browser over Wi-Fi. |
| D7 | Data on WSL | **Linux home**, with a **Backup now** that writes a checked archive to a Windows folder outside OneDrive/Documents, nudged hard. |
| D8 | Ubuntu releases | **24.04 LTS and 22.04 LTS.** (26.04 not supported at first.) |
| D9 | People | **Projects, one per person**: own recordings, dataset, checkpoints, backups and a consent note; delete-this-person's-data asks twice and names a backup first. |
| D10 | Send to phone | **Folder + USB steps** and **Wi-Fi with a QR code**. Not adb. Output is one `my_voice_backup.zip` in ACK's voice-backup layout. |
| D11 | Versions | **Pinned to a tested set** (a fixed `piper1-gpl` commit, exact library versions with hashes). Fix upstream problems by wrapper first; if a source patch is unavoidable it is shown, backed up and applied only after confirmation. Updating is a button that asks first. |
| D12 | Training | **Rounds with listening**: about 25 minutes a round, stops itself cleanly, makes a short test clip from the latest checkpoint; the helper chooses *sounds good*, *another round* or *go back to the previous round*. Settings are chosen from the detected GPU memory and shown read-only. Training keeps running if the window closes. |
| D13 | Existing installs | **Detect, then copy in**, after a checked backup; originals never moved or deleted. Reuse an old training environment only if it matches the lock, otherwise build a new one beside it. |
| D14 | The command | **Both documented**: `git clone` of a tagged release `&& run setup` as the main route; a `curl ... \| bash` route for "no git yet". |
| D15 | Base voice | A **short vetted list**, license text shown before download, fetched only with consent, never bundled. Vetting needs a run on the developer's GPU (VS-0.2). The list is fixed by D25. |
| D16 | Phone certificate | A **wizard-made, name-restricted certificate authority**, re-issuing the certificate when the address changes; install one file on the phone once. mkcert is the fallback if VS-0.3 fails. |
| D17 | Windows-side edits | **Explain, then edit after confirmation**: write `.wslconfig` keeping a `.bak`, show the firewall command to run as administrator. Never restart WSL, and warn that training must be paused first. |
| D18 | Reading material | **Easy public-domain passages and a phonetically balanced sentence list**, plus pasting your own text and free speech. Each shipped text's license is read and logged first. |
| D19 | Wording | **Everyday words, details on demand** (a Show details expander with the real command and log). English first, all text in one catalog so translations can follow. |
| D20 | Order | **Risk-first spikes, then a thin slice**, then widen. |
| D21 | Consent | **Prompt, and keep the note with the project.** New projects ask whose voice it is; for someone else's, a note is needed to continue (who agreed, what to, when, how to withdraw, how it was given: spoken, signed, through a guardian, using AAC). It verifies nothing; it starts the conversation. The note is kept in the project and in the voice's model card. |
| D22 | Failures | **Plain cause, what is safe, a report file**: a message in everyday words saying what happened, whether anything was changed, and the next step. *Save problem report* writes a text file the helper can read first (versions, step names, error text; names and folders blanked; no recordings or text), never sent anywhere. |
| D23 | Old recorder | **Retired from the guided path.** Each project gets its own output folder that Freeform Studio uses; the old guides stay as the manual route. |
| D24 | Scratch location | **Scratch defaults to a folder inside the project, and an Advanced option lets the person choose another drive or folder**, on native Ubuntu and on WSL. A chosen place is checked before it is used, the tool never writes into the empty mount point of an unplugged drive, and the place is covered by backup, clean-up and delete ("Choosing another drive" under P11 in detail; VS-1.11, VS-6.5). |
| D25 | Starting voices | **Mike and Amy** (`rhasspy/piper-checkpoints`, `en/en_US`) are the default install's two starting voices. Both are fetched during setup (each is its own line on the consent list, with its license shown, D15), and the helper chooses **male or female** for each person. The thin slice uses Mike, which the developer has found works best across the voices tried. **Confirmed from the developer's screenshot of `en/en_US` (2026-10-10):** the folders are `mike` ("Add mike (en_US)", about 3 months old) and `amy` (last changed by "Fix model cards", about 2 months old). The developer reports both were trained recently and will work. VS-0.2 still checks that each loads and trains with the pinned trainer, because the guide records that older-format checkpoints fail and the listing shows only each folder's last change, not when its checkpoint was trained. Each voice's own model card license is read before it ships: the dataset's page says MIT, which may not be the voice's own license. **From the model cards (developer's screenshots, 2026-10-10):** each is one speaker, medium quality, 22,050 Hz, and **fine-tuned from the lessac voice**. `mike`'s dataset is OHF-Voice/voice-datasets under CC0; `amy`'s is MycroftAI/mimic3-voices with its license listed only as "See URL". **Each checkpoint is 846 MB**, so about 1.7 GB for both. |
| D26 | Disk needed to start | The number shown before setup, and the check that gates it, **counts both starting voices and a budget for at least two people** (a person's project is the "profile" here), not just the tool. |
| D27 | Starting-voice licensing | **Declare, don't host.** The project hosts, mirrors or sublicenses none of the starting voices or the data behind them. Before each voice is fetched the person sees the chain (mike or amy, then lessac, then the Blizzard 2013 data) and each license as its own page states it, with the plain statement that this project gives no legal advice and that whether their use is allowed is theirs to decide. One click per voice, recorded in the project's model card with the date and the exact revision. The registry points only at the original host, pinned to a revision and a checksum, and a test fails if any starting-voice or dataset file is committed to the repo or put in a release or an exported package. A downloaded starting voice is kept (a checked copy that *Free up space* never offers), because it cannot be re-downloaded if the host removes it; a different base later is a registry entry, not a rewrite. The exported voice is the person's own, and the export screen and model card say what it descends from and that publishing it is a separate decision. No wording anywhere says or implies that use is permitted ("free for personal use" is not used). For now the acknowledgment is the position: the person is made aware of the issue, and nothing in the plan waits on any answer from the licensors. No letter to them is kept in this repo (the developer may write to them separately). |

### Proposed defaults (not asked: veto any of these)

| # | Topic | Proposal |
|---|---|---|
| P1 | Names | The tool is **ACK Voice Studio**, in `tools/voice_studio/`. The clone location stays `~/ack-tools`, as in today's docs. |
| P2 | Launching | A `.desktop` entry (Ubuntu's app grid; on WSL, WSLg adds it to the Windows Start menu), so nothing is typed after setup. |
| P3 | Server lifecycle | The window starts Freeform Studio for a project when Record or Review is opened and stops it when the helper leaves, asking first if a phone is connected. Training is a separate job and is never stopped by this. |
| P4 | Updates | Manual only: a *Check for updates* button that asks before it contacts the internet. No background checks, ever. |
| P5 | Uninstall | Removes the tool and its environments only. A project is never deleted by it. |
| P6 | Accessibility | Every screen: complete keyboard operation; every control has an accessible name and role; the system text size up to 200% and the system contrast theme are respected; no sound, no animation other than a progress bar, no timers that act for the person and no auto-advance (a round *ends* by itself but nothing *starts* without a click); status changes are announced; text 12 pt or larger. A headless check reads every widget's accessible name where GTK allows; the rest is on the device-test list with Orca. |
| P7 | No display | If the bootstrap finds no desktop session it says so in plain words and stops (a native Ubuntu desktop or WSLg is needed). No browser fallback in the first version. |
| P8 | Hardware floor | NVIDIA with at least 8 GB of GPU memory (the size the guide was verified on), plus RAM and disk numbers measured in VS-0.2. Less is "unverified", not "refused". |
| P9 | Python | The window runs on the system Python with Ubuntu's PyGObject; training and Freeform Studio run in their own venvs. The lock must cover Python 3.10 (22.04) and 3.12 (24.04); if torch cannot, VS-0.2 reopens D8. |
| P10 | Windows support | Windows 11 supported; Windows 10 (build 19044+, WSLg) best-effort, and past its standard support. |
| P11 | Disk space | Observed, never discovered by a failed write. A **budget** (an estimate from how long the person plans to record, checked before each big step and watched while a job runs), with all the churn kept in a **scratch** folder (inside the project by default, on another drive as an Advanced option: D24). Details below the table. |

### P11 in detail (disk space)

You offered two ways: a scratch space, or a default minimum plus a recording budget. This proposes both in their simplest form, because
they answer different questions: the **budget** decides *how much room is needed*, the **scratch folder** decides *where the churn goes*.
Letting the person point scratch at another drive is an Advanced option (D24), described under "Choosing another drive" below.

| Kind | What it is | Rule |
|---|---|---|
| Precious | Recordings and ACK packages, transcripts and edits, `project.json` and the consent note, the chosen round's checkpoint and the one before it (going back needs it), finished exports, backups | Never removed by the tool. Counted in the budget. Backed up. |
| Rebuildable | The dataset (`wav/` and `metadata.csv`) and the training caches | Can be made again from the precious files. Removed only through *Free up space*. Not backed up. |
| Disposable | Older rounds' checkpoints, temporary `.onnx` files and listening clips, logs | Removed only through *Free up space*, after one confirmation. Not backed up. |

Rebuildable and disposable files live in the project's scratch folder (`<project>/scratch/` unless another place was chosen, D24), so the clean-up and
budget rules apply to that folder and nothing else. A round's
checkpoint is moved there (a rename on the same disk, not a copy) once it is no longer the chosen round or the one before it. The
tool's own environments and download caches (pip, Hugging Face) are not per person; they are counted once, as "the tool", and the pip cache is
offered for clean-up after a successful build, never removed on its own. The downloaded starting voices belong to the tool too: kept once, never offered by
*Free up space* (they cannot be re-downloaded if the host removes them), left out of project backups, and checked against their checksum before each use (D27).

- **The estimate.** One number, in plain words, shown before setup and again whenever the plan changes: the tool and its environments, the
  recordings (planned hours × the measured cost per hour, including the decoded copy Freeform Studio keeps), the dataset and cache, the
  checkpoints the tool will keep, room for one backup copy of the precious kind, and a safety margin. Three answers: *enough*, *tight* (a
  warning that can be acknowledged and continued past), or *not enough* (that step does not start; nothing is changed; the message says how much
  is missing).
- **The number needed to start (D26).** Shown before setup: the tool and its environments, the speech model, **both starting voices** (Mike and Amy,
  whichever the person later chooses), and a budget for **at least two people**: two projects, each at a default plan of one hour of recording
  (the guides say "an hour or more"; changeable), even if only one is made first. *Enough* covers all of it. *Tight* covers the tool, both
  starting voices and one project, and can be continued past after a warning. *Not enough* is less than the tool, one starting voice and one
  project's smallest plan, and setup stops there with nothing changed. Declining one starting voice on the consent list gives a smaller number.
  The thresholds are proposals. Sizes so far: both starting voices are 846 MB each, 1.69 GB together (from the Hugging Face
  listing); the rest come from VS-0.2.
- **Before each big step** (import a package, build the dataset, start a round, make an export, make a backup) the same check runs against the
  room that step will need, including at a backup's destination.
- **While a job runs** the free space is read on a timer. *Low* shows a quiet banner and a silent notification. *Stop* stops the job
  gracefully (the guide's single Ctrl+C) while there is still room to write whatever a stop keeps, never at the last moment, and says that
  nothing was lost. What a stop keeps is measured in VS-0.2, not assumed.
- **The order of the floors protects the recordings.** Training stops at a higher floor than the one at which Freeform Studio refuses new audio
  (500 MB today), so a full disk can end a training round but never costs a recording.
- **Nothing is deleted automatically.** *Free up space* (VS-4.7) lists disposable items with sizes, removes only what is ticked after one
  confirmation, and never offers the chosen round's checkpoint or the one before it.
- **On WSL** it checks both the Linux disk and the Windows drive that holds its virtual disk, and explains that the virtual disk does not
  shrink by itself when files are deleted. How to reclaim that space is checked on the developer's WSL before it goes into any guide, because
  the right command depends on the WSL version.
- **The numbers** (margin, cost per hour, checkpoint size, the two floors) come from one table that VS-0.2 measures. Until then the guides'
  rough figures are used and are labelled unmeasured on screen.

#### Choosing another drive for scratch (D24, Advanced)

Hidden under *Advanced* when a project is made, and in the project's settings later. Scratch holds the dataset, the caches and the checkpoints,
which are the voice in another form, so the same privacy rules apply as for the recordings. The option itself is decided; the checks below are
my proposals (veto any). Each is a pure function in VS-1.11, tested in the sandbox against captured mount tables.

- **What it offers.** The mounted drives from the preflight, each with its free space, filesystem and whether it is removable, or "choose a folder".
- **A real, writable, private place.** The folder exists or can be made, the person can write to it, it is not read-only, and the tool makes
  `scratch` there with owner-only permission. Filesystems are in three groups: *good* (ext4, xfs, btrfs, f2fs) are accepted; *permissive* (NTFS,
  exFAT, and on WSL a Windows drive) are accepted only after a plain warning that they may be slow and that other accounts on the computer might
  be able to read the files; *FAT* is refused (its file-size limit) and *network* filesystems (NFS, SMB, sshfs) are refused in the first version,
  because a voice should not cross a network.
- **Not a synced folder.** `freeform_studio/privacy.py`'s synced-folder detection is reused, but here it **refuses** rather than warns: scratch is
  voice data that OneDrive, Dropbox or Google Drive would upload.
- **Never into an empty mount point.** Every job start checks a marker file (`.ack-voice-scratch`, holding the project's id) in the chosen
  folder and refuses to run if it is missing, so an unplugged USB drive cannot make the tool quietly fill the system disk through the empty folder
  it was mounted on. If the person says it is another drive but it is the same device as the project's, the tool says so. Nothing falls back to
  another place on its own.
- **Speed.** A short write-and-read test on the chosen place; a slow one gets a warning with the measured speed (the cutoff is measured in
  VS-0.2). On WSL a Windows drive (`/mnt/c` and similar) is allowed but marked slow. It stops the Linux virtual disk growing, at the cost of speed.
- **Unplugging.** A removable drive is allowed with a warning that unplugging during a round stops training. The job supervisor stops gracefully
  if the drive disappears, says what happened, and training resumes when the drive is back.
- **A budget per drive.** The estimate and the floors are worked out for each drive: the precious kinds on the project's drive, scratch on its own.
  The recorder's floor still protects the recordings drive; training stops on whichever drive runs low first.
- **Changing it later.** *Move scratch* (VS-6.5): copy, verify, switch, and only then offer to remove the old copy. It refuses while a job runs and
  checks room at the destination first.
- **Covered everywhere else.** Backups leave scratch out wherever it lives. *Delete this person's data* names the drive, and says what it could
  not reach if the drive is not plugged in. *Free up space* shows where scratch is.

### Still open

- Anything in the proposed defaults you want changed.
- Amy's license ("See URL", the MycroftAI/mimic3-voices repository) is still unread; Mike's dataset is CC0. For now D27's acknowledgment is the
  position; if the developer ever gets an answer from the licensors, the wording in VS-4.1 is revisited.
- Whether Mike is preselected on the male/female choice screen, or neither is.
- Whether the first release needs a translation of the window, or English only until the app's drafts are reviewed (D19 leaves the door open).
- P11 and D26: the real numbers (cost per hour, the size of a checkpoint a run saves, margin, the floors, the slow-drive cutoff) wait for VS-0.2.

## 7. What I cannot do from here

The Linux sandbox has no GPU, no Windows, no WSLg, no desktop session, no screen reader and no phone. Everything in section 3's "plain Python"
rule can be unit tested here (preflight, registry, project model, rounds state machine, bootstrap against stand-in commands, report
redaction, zip contract). The window itself, training quality, listening results, the phone steps, the certificate on Android, WSL
networking, the Windows helper and the screen-reader behaviour can only be checked by the developer, and no stage that depends on them
is called done until the matching device-test items are ticked.
