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

### Findings from the developer's own machines (device tests)

These come only from the developer's runs of `docs/VOICE_STUDIO_DEVICE_TEST.md`. Machine: Windows 10.0.26200.9457, WSL 2.7.14.0 (kernel 6.18.33.2, WSLg 1.0.73.2),
Ubuntu 22.04.5, Python 3.10.12, GTK 4.6.9 (from `gir1.2-gtk-4.0`), RTX 4060 with 8188 MiB, driver 596.49.

- **F1 (2026-10-10), the tests pass on the Python 3.10 floor under WSL2:** 1406 passed in 37 s, including the 10 that build real virtual environments.
- **F2 (2026-10-10), the first terminal step behaves as designed on WSL2:** `--check` finds the desktop (WSLg) and the graphics card, lists only the one missing program, `--dry-run` shows
  exactly the two apt commands, a run under `sudo` is refused with the administrator-rights `[FIX]`, and after the developer said yes `--check` reports ready.
- **F3 (2026-10-10), a job does not outlive the last WSL terminal, and the cause is known.** The journal shows `systemd-logind: System is powering down` about a minute after the last terminal
  closed, twice (12:35:10 and 13:06:24 local), and systemd starting again when a new terminal was opened. The virtual machine did not restart (`boot_id` and `uptime -s` unchanged): WSL stopped only
  the Ubuntu instance. `systemd=true`, `Linger=no` and a systemd user service made no difference (the service died too). The shutdown takes about a second, so the runner never wrote a result and
  the supervisor read the job as `interrupted`, which was the truth. **D12's "training keeps running if the window closes" is false on WSL by default.** One job did run its full ten minutes while a
  `wsl.exe … sleep infinity` session was left open in another window (the developer's recollection, to be confirmed), so a session held open from Windows holds the instance up. `.wslconfig`
  held only `networkingMode=mirrored`. **Tested on WSL 2.7.14.0: adding `[general] instanceIdleTimeout=-1` to `.wslconfig` (then `wsl.exe --shutdown`) keeps jobs alive.** A check job was still running after every window had been closed for
  more than five minutes, where the same job had been killed within about a minute every time before (the developer kept a backup, then undid the setting and restarted WSL while a job was running: it read `interrupted`, which is the restart check of section D passing, not a second test of the setting; so the setting has one positive run against three kills without it, and the tool re-checks it on the machine it runs on). Other users report that this
  setting did not always work on 2.5.x, so the tool must re-check it on the machine it runs on (below) rather than assume it.
- **F4 (2026-10-10), Ubuntu starting Windows programs is intermittent.** After the instance had restarted on its own, `powershell.exe` from Ubuntu gave `cannot execute binary file: Exec format error`
  (the interop handler was missing from `binfmt_misc`, a known fault when systemd is on, because its `systemd-binfmt` service can clear the entry). After a later `wsl.exe --shutdown` and restart,
  `cmd.exe /c ver` worked and `WSLInterop` was listed. So the tool must **check at the moment it needs it** (a short, time-limited `cmd.exe /c ver`), say plainly when it does not work, and never depend
  on it: the `.wslconfig` edit (D17) is a file write through `/mnt/c` and does not need interop, and the folder can be opened from Windows through `\\wsl.localhost\<distribution>\…`. The usual
  repair when it is down is a restart of WSL, or a one-line `binfmt.d` file with a restart of `systemd-binfmt` (a change inside Ubuntu that needs `sudo` and the person's yes).

- **F5 (2026-10-10), speech recognition runs on the processor with and without the network; downloads are slow on this connection.** `models list` showed `small.en` already on the machine, so the
  fetch step itself was not run, and `asr_smoke` gave the same result online and offline. The developer's downloads run at roughly 1.5 MB/s (a 150 Mbit carrier line). At that speed the 480 MB speech
  model takes about 5 minutes and one 846 MB starting checkpoint about 10 minutes. (The first version of this note also said the training environment would take about 45 minutes at that speed. **That was wrong:** see F9, the package site's downloads ran several times faster than Hugging Face's.) So the setup
  screens must not promise "a few minutes": show an estimate from the speed actually measured so far, say plainly that it can take a long time, keep every download resumable (it already is) and never
  freeze the window while one runs.

- **F6 (2026-10-10), a real phone package comes in as designed.** A package made by ACK 1.0 (one script session, 54 s) was looked at first with nothing written, copied into the project and checked, added
  only when the command ended with `add`, recognised as already added the next time, and a copy with one byte changed was refused with the three plain sentences, named the damaged clip, left nothing
  in `incoming/` and left the original untouched. The details line repeats part of the third sentence (Freeform Studio's own wording); it sits under Show details, so it stays for now.
- **F7 (2026-10-10), finishing a recording on the processor is fast enough.** `freeform_studio.process` took 6.5 s (about 25 s of processor time across cores) for the 54 s of speech, including loading
  the speech model: roughly an eighth of real time. A missing model folder was refused with exit 3 and a plain sentence before anything started, and a second run found nothing waiting. Listening to
  an hour of recordings should take on the order of ten minutes on this machine, to be confirmed on a longer one.

- **F8 (2026-10-10), a phone's recordings can be far quieter than the training set can fix by default.** Every piece of the developer's first package was flagged `quiet` (peak below -15 dBFS, the most the
  dataset builder would turn up being 12 dB) and left out, although they sounded fine to play. A phone microphone with no automatic gain gives this. The remedy is in the training set, never the recording:
  `build_dataset --max-gain-db N` (0 to 60, default 12) turns clips up further, a `quiet` flag stops blocking once N is above 12 (a `noisy` one still blocks, because turning up noise helps nobody), the "too quiet to use" floor moves down with the extra gain (never below -80 dB; found when the first preview still refused 7 pieces whose average sat just under the old floor), the report
  and the summary say how far clips were turned up, a warning says when some are still softer than full level, and the limit is kept in `manifest.json`. Voice Studio's command builder takes the limit and
  its reader reports the gain. Open: the right limit for the developer's phone (the measured peaks will say), and whether the window should offer it by itself when the only reason pieces were left out is
  `quiet` (it should explain and ask, never change anything silently).

- **F9 (2026-10-10), the trainer environment builds by hand on the developer's machine, and what the lock must therefore hold.** Ubuntu 22.04.5 on WSL2, Python 3.10.12, piper1-gpl at commit
  `5b355b110aecf3de8f4e000ede1ce06831acff35`, `pip install -e '.[train]'` plus the build tools: **6 minutes 17 seconds** from nothing (some wheels may have come from pip's cache, so this is a floor
  on the speed, not a promise: the files total about 3.2 GB, which is at least 8.6 MB/s if none were cached; Hugging Face's 1.5 MB/s was a different host). **94 packages** besides the trainer; the
  environment is **6.1 GiB** installed; pip's cache on that machine was 7.6 GiB afterwards (more than this install's own 3.2 GB of files, so it holds earlier installs too; it is disposable). torch is
  **2.14.1 with CUDA 13** straight from the package site (no separate index needed), the driver (596.49) is new enough, `torch.cuda.is_available()` is true on the RTX 4060 and `piper.train fit --help`
  runs. Facts for the lock: `pip freeze` hides **setuptools** (forced below 82: 81.0.0) and **wheel**, which the build needs (scikit-build depends on wheel), so the lock names them; the trainer itself
  (`piper-tts`, installed editable from the source) is not in the lock; `monotonic_align`'s native part built (`core.cpython-310-x86_64-linux-gnu.so`) and so did `espeakbridge`. `torch.jit.script`
  prints a harmless deprecation warning. The trainer's real requirements are `setup.py`'s `train` extra (torch, lightning, tensorboard, tensorboardX, jsonargparse[signatures], onnx, pysilero-vad,
  cython, librosa<1) plus onnxruntime and pathvalidate; `pyproject.toml` lists only the build tools. **`onnxscript` is not in the tested set**: the export workaround (`dynamo=False`) should not need
  it; if the export in the checklist's section J says otherwise, it is added to the lock.
  **What the same set does on other Pythons** (checked here against the package site's own listings, not on a machine): every one of the 94 releases has a Linux x86_64 wheel for Python 3.10, 3.11
  and 3.12, so one lock serves Ubuntu 22.04 and 24.04 with no change of versions (the 3.10 resolution is the older one: a fresh resolve on 3.11 and later would pick newer numpy, scipy,
  scikit-learn, networkx and onnxruntime, which the lock deliberately does not); with exactly these versions the dependency resolver adds nothing on 3.11 or 3.12. **Python 3.13 is not covered**
  (four more packages are needed: audioop-lts, standard-aifc, standard-chunk, standard-sunau), and **3.14** (which Ubuntu 26.04 is expected to ship) has no wheel for numpy 2.2.6, scipy 1.15.3 or
  onnxruntime 1.23.2: it needs its own lock, made and tried on a machine that has that Python. The entry therefore carries `python_max` (3.12), so a newer Python is refused in plain words instead of
  failing inside pip with a hash message. **Not yet run on 24.04**: the cp312 wheels exist and resolve, but nothing was trained there.

- **F10 (2026-10-11), the source build reaches out to GitHub, so the trainer is installed from its published wheel instead.** The trainer's CMake files (`CMakeLists.txt`, `libpiper/CMakeLists.txt`)
  clone espeak-ng from GitHub with `git` while building (`ExternalProject_Add … GIT_REPOSITORY`). That is a download outside the one agreed place, with no checksum of ours, and it cannot work with the
  builder's no-internet source install. GitHub was also slow from the developer's computer: the 25.4 MB archive of the pinned commit took 5 minutes 14 seconds (about 70 KB/s), where the package site
  delivered 3.2 GB in about six minutes. The package site publishes **`piper-tts 1.8.0` as a ready-made Linux wheel** (`cp39-abi3`, `manylinux_2_28`, 34 MB, so one file serves every Python the lock
  covers): it contains the compiled espeak-ng part and its data and the whole `piper.train` trainer, and it takes a normal hash-checked line in the lock. **Is it the code that was tried?** The
  developer's commit (`5b355b1`, 17 September) is 13 days after the release tag `v1.8.0` (4 September). Compared file by file (33 of 40 Python files byte-identical), the differences are Lithuanian
  voice support (a new phonemizer and its word list, a branch in `dataset.py`, `phonemize_espeak.py`, `infer_torch.py`, `voice.py`) and an alias so a renamed voice downloads under its current name
  (`download_voices.py`, `config.py`); nothing that English training touches. What the wheel lacks is the compiled alignment code and its source (the trainer imports `.monotonic_align.core` and the
  wheel ships neither). That is one 1148-byte Cython file, so **it is shipped with the tool** (`data/native/monotonic_align_core.pyx`, byte for byte the developer's file at the pinned commit, pinned by
  checksum) and **built by the tool** after the install, with the environment's own Cython and the computer's C compiler (both already required by the setup check), into the folder the wheel looks in.
  Checked here: it compiles on Python 3.12 with the pinned Cython and gives the same answers as a plain-Python version on random cases, in a batch, and on a hand-worked one. The lock lost
  `cmake`, `ninja`, `scikit-build` and its `distro` and `tomli` (only the from-source build needed them) and gained `piper-tts` and `setuptools`: 91 packages, and with exactly these versions pip's own
  resolver needs nothing more on 3.11 or 3.12. **Not yet run:** a training round with the wheel-based environment (that is the next device test), and anything on 24.04.

- **F11 (2026-10-11), the tool's own builder built the training environment on the developer's computer, first try.** Ubuntu 22.04 on WSL2, Python 3.10, `python3 -m voice_studio.buildenv training`: space check
  0 s, the separate space 2 s, **installing the 91 locked packages 1 min 17 s** (about 3.2 GB from the package site; it replaced the venv's own old setuptools with the pinned 81.0.0), **compiling the
  alignment part 3 s**, the helper 0 s, the self-test 3 s (the imports, the alignment module and, because no "not tried" line appeared, the graphics-card check); **1 min 25 s in all**, against about
  6 minutes for the hand-built one (it also built espeak-ng from source). The disk line read "about 11 GB free needed, 958 GB free". One thing found and fixed: a quiet step's sign of life showed the
  installer's moving progress bar; it now shows the last line in words. **Still unmeasured:** the installed size (section I0 asks for `du`), a training round with this environment, Ubuntu 24.04, and the
  workaround prelude (`add_safe_globals`, `dynamo=False`), which the export in section J will show to be needed or not.

- **F12 (2026-10-11), the first training round with the tool-built environment: it trained, then stopped at its first check, because of the quality score.** From Mike's checkpoint (epoch 5465, 23 utterances,
  70.4 M parameters) it restored all states (the launcher's `torch.load` line was in place; whether it is *needed* is still unproven), trained epochs 5465 to 5469 at about 1.3 to 1.9 steps a second (one batch an
  epoch with this little data) and, at the first validation (31 seconds after starting), stopped with `MisconfigurationException: ModelCheckpoint(monitor='val_mos') could not find the monitored key`. The trainer
  tried to load its optional quality scorer (code and weights fetched from GitHub through `torch.hub`, which then needs `torchaudio`; the locked programs have neither the library nor, on a fresh computer, the download)
  and logged `val_mos logging disabled`, but both the published 1.8.0 and the developer's commit still register a second `ModelCheckpoint` on `val_mos` that raises when it was never logged: the guide's "older
  checkouts" problem, and the reason the guide told people to delete that callback. What the failed round did leave proves the folder layout the tool assumes: `run/lightning_logs/version_0/checkpoints/` holds
  `last.ckpt` (807 MB) and `epoch=5469-val_mel=0.6043.ckpt` (807 MB), both written before the error. **Peak graphics memory at batch 12 was 7762 MiB of 8188** (about 2.1 GB of that was other programs: that is
  what was in use afterwards), so batch 12 is within about 5 percent of the RTX 4060's limit even with short clips; batch 8 is the next thing to try. The **fix** is in the launcher (D33); see F13 for why the
  first attempt, a command-line switch, did not work.

- **F13 (2026-10-11), the second and third rounds: a full 5-minute round, a resume, and a stop by hand all behave; and a command-line setting is ignored when resuming.** Round 2 (from Mike's checkpoint, no
  ceiling on epochs) ran **21:38:44 to 21:44:02**: `Time limit reached. Elapsed time is 0:05:00. Signaling Trainer to stop.`, **exit code 0**, about 18 seconds of loading and shutdown on top of the five minutes;
  epoch 5469 to 5711, a normal epoch at 1.5 to 2.3 steps a second, one epoch in ten a checkpoint write (up to 4 s); peak graphics memory 7793 MiB of 8188. Its folder
  `run/lightning_logs/version_0/checkpoints/` holds **`last.ckpt` and the five best by mel loss, 807 MiB (846 MB) each: 4.84 GB, however short the round** (the disk budget assumed three per round; it says six now,
  measured). Round 3 **resumed from that `last.ckpt`** (`Restoring states … Restored all states`), trained in a new `version_1`, and a **Ctrl+C was answered in about 2 seconds** with `Detected KeyboardInterrupt,
  attempting graceful shutdown ...` and **exit code 1**; it left no newer `last.ckpt` (the last one is from the last check, at most ten epochs back), which is the cost of a stop by hand. **Found by looking at the
  logs:** round 2 still printed `Using cache found in …/tarepan_SpeechMOS_v1.2.0` and `Could not load MOS predictor`, although it was started with `--model.mos_metric none`, and `hparams.yaml` and `config.yaml` in
  its log folder both said `mos_metric: utmos`. Lightning's command line tool, given a `--ckpt_path`, parses the **settings saved inside the checkpoint and lays them over the command line**
  (`LightningCLI._parse_ckpt_path`, read in the installed 2.6.6): every `--model.*` setting is ignored on a resume, and a round always resumes (from the starting voice at first). So the switch did nothing, the
  skip-the-checkpoint-rule line alone kept the round alive, and on a computer that has never run the scorer the first check would have **downloaded and imported code from GitHub** (this one had the scorer cached
  from earlier hand training). Fix, in the launcher where nothing can override it: one more line replaces the scorer's loader with a no-op, so it is never fetched or run; `train_command` no longer passes the useless
  switch and a test now fails if any `--model.*` option other than the sample rate is added. **To confirm on the developer's computer:** the next round's log has no `SpeechMOS` or `MOS predictor` line.

- **F14 (2026-10-11), a round's time limit is not per round unless the launcher makes it so.** The one-minute round that followed the fix (from the five-minute round's `last.ckpt`) exited 0 with **no scorer line in its
  log** (so the loader fix works) but took **8 seconds** and printed `Time limit reached. Elapsed time is 0:04:57`: Lightning's time-limit callback saves its clock in every checkpoint and restores it on a resume
  (`Timer.load_state_dict` sets an offset), so the new round started at 4:57 of a 1:00 limit. The tool starts every round with a length and resumes from the previous round's `last.ckpt`, so **every round after the
  first would have stopped at once**; the first one only worked because the starting voice's checkpoint has no saved clock. Fix (D34): one more launcher line makes the restore do nothing, so `--trainer.max_time`
  counts from the round's own start. The launcher now has seven one-line workarounds, each found by a real round: the `torch.load` rule, the exporter's `dynamo=False`, the scorer's checkpoint rule, the scorer's loader
  and the saved clock (the first two come from the guide). **To confirm:** the same one-minute round says `Elapsed time is 0:01:00`.

- **F15 (2026-10-11), the first voice file this tool made: exported, patched, zipped, and it spoke on the phone.** Confirmed on the developer's computer after F14's fix: the one-minute round took 1 min 33 s, exit 0, no scorer line,
  `Time limit reached. Elapsed time is 0:01:04`, and `version_0` to `version_3` exist. The export under the launcher exited 0 with **no extra package** (`onnxscript` is not needed): `my_voice.onnx` 63,516,211 bytes after the
  patch (the original, kept as `.before-patch`, is 63,516,051), the settings file 5,036 bytes; the patcher's second run changed nothing; the zip is 63,517,438 bytes holding exactly `model.onnx` and `model.onnx.json`, and
  `verify_voice_zip` said no problems. **On the phone** the two files taken out of the zip and picked together imported and **spoke a full sentence without crashing** (the patch step's whole purpose). The **zip itself was
  refused by IMPORT CUSTOM VOICE**: the zip's contents are what ACK's restore expects, but that picker wanted exactly two files, and the restore button (IMPORT VOICE BACKUP) is only shown once a voice is installed, so a
  phone with no voice had no way to take the zip. Fixed in the app (see VS-5.3's as-built note): IMPORT CUSTOM VOICE takes one `.zip` as well, routed by name to the same restore path. **Still unproven:** whether the
  guide's `torch.load` rule and the exporter's `dynamo=False` line are needed at all (each probe is a minute; the launcher keeps both until they are shown unnecessary).

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
| 1 | Foundations (sandbox-testable) | Done 2026-10-10 (VS-1.1 to VS-1.11). What still needs the developer's machine is listed under VS-0.2: the lock files, the pinned archive and the measured sizes. |
| 2 | Thin slice: ACK package in, `.zip` out | In progress. Built and tested in the sandbox (plain Python, no window): the logic of VS-2.2 (setup plan, agreement, run) and VS-2.3 (new-project form), VS-2.4, VS-2.4b (new), the command builders and readers of VS-2.5, 2.6 and 2.7, VS-2.8, and VS-5.3, with the terminal-only device-test checklist for VS-2.9. Every one was checked by breaking the code on purpose (about 300 deliberate breaks; each real survivor got a test). Found on the way: a file nested far too deep crashed six readers instead of reading as damaged; fixed, with a test each. **Not built:** VS-2.1 (the window; waits for VS-0.1), every screen, the runs on a real GPU (2.6, 2.7), and VS-2.9. |
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
- **VS-0.2 Pinned training environment on the GPU (L, dev).** Build a venv from a proposed lock (exact torch, setuptools, onnx and friends, and the published
  `piper-tts` wheel; F10) on both 22.04 and 24.04. Train a few minutes from each starting voice (Mike first, then Amy; D25) on a small dataset, export,
  patch, synthesize with sherpa-onnx on the PC, import the zip into ACK on the phone. Record exact versions, wheel and disk sizes, the disk cost per hour of recording, per checkpoint and per round (for P11), GPU
  memory used at each batch size, the minimum driver, build time, and which upstream problems needed a wrapper versus a source patch. **Run the trainer with the network off** (for example in a loopback-only namespace) after setup (the scorer part is settled by D33; the rest of a round is still to be checked): the trainer fetches its `val_mos` quality scorer from GitHub on the
  first run (`DATA_SOVEREIGNTY.md` section 2), which would break "the server never goes online". If it needs that fetch, the scorer goes into the registry and onto the
  setup consent list, fetched at setup and not at the first training. Also time the training cache and a checkpoint write on the Linux disk, on a
  Windows drive seen from WSL, and on a USB drive, to set D24's slow-drive warning.
  Done when: a lock file, a verdict on each starting voice (does its checkpoint load and train with the pinned trainer; both are expected to, and a replacement is named for any that does not), a batch-size-by-memory table and the wrapper list exist.
  **Progress (2026-10-11), first half: the lock and the way the trainer is installed (see F9 and F10).** `data/locks/training.lock.txt` (91 packages, 152 checksums, Python 3.10 to 3.12, Linux x86_64)
  is written by `tools/voice_studio_maint/make_lock.py` from `tools/voice_studio_maint/locks/training.versions.txt` (the developer's `pip freeze`, minus the from-source build tools, plus the
  published `piper-tts` and `setuptools`); its checksum is in `data/environments.json`; a dry run in pip's hash-checking mode passes on 3.11 and 3.12 here (3.13 is refused, as it should be). The
  generator is a maintainers' tool outside the app (it reads the package site's public listing, so it needs a network; the app never runs it), writes nothing until every package has a wheel for every
  Python asked for, keeps an old lock beside the new one, and is tested (71 tests, with mutation checks). **The builder grew a `native` part** (`core/envspec.py`, `core/envbuild.py`): a small file
  shipped in `data/native/`, pinned by checksum, compiled with the environment's Cython after the packages are installed and copied to the one place the installed package looks; it is the same
  `native_build` step as before, refused with `native_changed` if the shipped file is not the pinned one, and run again when the Python, the lock or the file changes. The training entry no longer
  names a source archive, so `piper1-gpl-source` is gone from `data/sources.json`, and the setup agreement for the training environment is now a real, offerable line (`pip:training`).
  **A terminal command now builds an environment** (`python3 -m voice_studio.buildenv training [--check] [--yes] [--verbose]`, logic in `core/buildenv_flow.py`): it looks first, says where, how much space and which
  sites, names the Nvidia libraries when the lock holds them, asks once, saves the same `pip:training` agreement the setup plan would, builds with the step lines timed, and shows a three-part error with the end of the
  output when it fails; Ctrl+C stops it cleanly and the same command carries on. Section I0 of the device checklist runs it, and section I now trains with the environment it builds.
  **Still to do for the first half:** (a) ~~the first run of the tool's own builder~~ (done, F11) and then the training round with it (section I); (b) the
  same on Ubuntu 24.04 (a second WSL distribution is enough); (c) `studio.lock.txt` from the Freeform Studio environment; (d) the decision on NVIDIA's licence (below). **Second half (not started):**
  training rounds with that environment, memory by batch size, `--trainer.max_time`, export, whether the workarounds are needed, the network-off run, the slow-drive timings.
  **What VS-1.9 now waits for from this task** (the builder and its rules exist; these are the facts to put into the data files): (1) `data/locks/training.lock.txt` and `studio.lock.txt`, made with a resolver that writes
  hashes for every package including the build tools the trainer's `setup.py` needs (`setuptools<82`, `wheel`, `scikit-build`, `cmake`, `ninja`, `Cython`), and proved to install with `--require-hashes --only-binary=:all: --no-deps`
  from the ordinary package index on both Ubuntu releases (if a dependency has no wheel, say so; the answer is a decision, not a quiet change to the install flags); (2) the checksum of each lock written into `data/environments.json`;
  (3) the chosen `piper1-gpl` commit's archive address, file name, size and SHA-256 written into `data/sources.json` (`piper1-gpl-source`); (4) whether `build_monotonic_align.sh` builds from inside the environment as `native_build` expects and what file proves it
  (`native_artifact` is a guess from the guide); (5) which of the guide's workarounds in the launcher's `prelude` are really needed, and whether any needs a source `patches` entry instead; (6) the real installed sizes, to replace the 8 GiB and 1 GiB guesses.
  **Update 2026-10-11:** (1) is done for the training environment (the lock has `piper-tts` itself and no compile tools besides Cython and setuptools); (3) no longer applies, there is no source
  archive (F10); (4) became the shipped native file (`native_artifact` is now derived: `core.*so` in the package's `monotonic_align/monotonic_align` folder); (2), (5) and (6) wait for the rebuild with
  the tool's own builder.

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
- **VS-1.4 Bootstrap scripts (M, sandbox). Done 2026-10-10.** `setup.sh` (the `git clone ... && run` route) and `get.sh` (the `curl` route, D14): preflight, list
  of `apt` packages with a one-line reason each, ask yes/no, `sudo apt-get install`, then hand over to the window; also `--check` and
  `--dry-run` like `install.sh`. Never edits shell settings. Driven by stand-in commands in tests, as `test_install_scripts.py` does.
  Prints a plain message and stops if no display is available (P7). **As built:** `setup.sh` checks only that Python 3.10 or newer exists, then runs
  `python3 -m voice_studio` (`__main__.py`) with the tools folder on the path; everything else is `core/setup_flow.py`, which is plain Python decided from a `System`
  and an `IO`, so it is tested without a terminal. It looks, shows blockers (including no display, administrator rights, an unsupported Ubuntu) and notes, lists each
  missing program with its reason, explains the password, asks **once** and runs exactly `sudo apt-get update` then `sudo apt-get install -y <the missing ones>`.
  Only a plain `y` or `yes` is a yes; with nobody to ask (input is not a terminal) it does nothing and says to add `--yes`. The agreement it records names `apt:update` and
  each program, and `fetch.run_networked` refuses a command the agreement does not cover; the command runs in the person's own terminal
  (`inherit_stdio`), so `sudo` asks for the password itself and this program never sees it. After installing it looks again and does not call the computer ready if anything
  is still missing. Exit codes: 0 ready, 1 blocked or failed, 2 nothing was done. `--check` changes nothing (0 ready, 1 not), `--dry-run` prints the exact commands.
  `get.sh` needs `ACK_VOICE_TAG` (a release name; **there are no releases yet, so it fetches nothing until one is tagged**), asks before installing git, clones that
  tag with `--depth 1` into `~/ack-tools` (or `ACK_VOICE_DIR`), reuses an existing copy, **never touches a non-empty folder that is not ACK**, reads its answer from
  `/dev/tty` because when piped into bash its own input is the script, and holds the project's one bootstrap web address (`REPO_URL`; the network-rules test allows it
  there and nowhere else). Neither script edits shell settings, removes anything or runs `sudo` for anything but those two commands (tests read the source for it). **Mutation
  testing:** 70 deliberate breaks (a yes that accepts anything, a skipped update, an ignored failure, no recheck, a clone of a moving branch, an unquoted folder name, a Python
  check one minor off, a reply read from the wrong input...) are each caught; one more was equivalent (`>` for `>=` on a version tuple that is always longer than `(3, 10)`).
  One mutant wrote a folder into the repository, so the script tests now run from a scratch folder. Not run for real: `apt` and `sudo` on Ubuntu (stand-ins only), a real
  terminal's password prompt, WSL; the device checks come with VS-0.1.
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
- **VS-1.7 Text catalog and wording lint (S, sandbox). Done 2026-10-10.** All visible text in one catalog so translations can follow; a test fails
  on jargon in default labels (checkpoint, epoch, venv, tensor, ONNX... except under Show details). **As built, with one change from the plan:** the catalog is *keyed*,
  like ACK's own string resources (`data/text/en.json`, names such as `fetch.error.checksum.what`), not gettext with English as the key. A stable name survives a copy edit,
  a plural can carry a second argument, and the same discipline as the Android app applies (a key that is missing reads as itself so a gap shows; a language that lacks
  a key falls back to English for it). A template holds `{name}` placeholders and nothing else, filled by pattern and never by `str.format`, so no text or value can run
  anything. **D22 is held by tests:** every error code any module can raise has three keys, what happened, whether anything was changed and the next step, and the
  middle one must say something about the files. Complete in both directions: every key the code names has words, and a string nothing uses fails. The plain-words
  lint covers jargon (checkpoint, GPU, cache, dataset, sudo, apt...), sentences over 25 words, shouting, web addresses and stray template syntax; text under a `.detail`
  key may be technical. 164 strings so far (preflight, the reasons for each program and download, every failure, every status, every refusal and warning). What is not
  checked by a test: that a `Show details` partner exists wherever a command runs; that is a screen-level rule for Stage 2.
- **VS-1.8 Problem report builder (M, sandbox). Done 2026-10-10.** Builds the text the helper sees *before* saving: versions, step names, error text.
  Redacts user name, home folder, project and person names. Tests plant canary strings and fail if one survives. Never includes
  recordings, transcripts or phrases. **As built** (`core/report.py`): the report has no field that could hold a recording, a transcript, a phrase or a consent note (a test
  pins the input's fields); the end of a job's log is included only if asked for, and is said to possibly contain words from recordings. Everything that comes from the computer or
  the person's data is redacted in one pass with private sentinels, so a login name of "user" cannot damage `<windows-user>`: the login, home folder, data folder, computer name,
  every Windows profile, every person's name and folder name (case-insensitive, NFC and NFD), emails, IP and MAC addresses, access tokens, and the labels of drives under
  `/media` and `/mnt`. What is shown is exactly the file's bytes; saving never replaces an existing file unless told to. **Stated limits:** a one-character name is not hidden (it
  would blank every such letter); names of four letters or fewer are hidden only as whole words (so "Users" survives a login of "user"); the redactor knows only the names it is given,
  which is why the log is opt-in. **Found by testing:** an email pattern that took quadratic time on a long message; the pattern is bounded and every piece is cut to 4,000
  characters before it is read.
- **VS-1.9 Environment builder (L, sandbox with stand-ins, real run in dev). Done 2026-10-10, except the real lock files, which wait for VS-0.2.** Creates the venvs from the lock with hashes, builds
  `piper1-gpl`'s native part, runs a self-test, is idempotent and resumable, never touches an existing environment, and writes what it did.
  Applies fixes by wrapper; a source patch (if VS-0.2 found one unavoidable) is shown, backed up and applied only on confirmation.
  After: VS-0.2. **As built** (`core/envspec.py`, `core/envbuild.py`, `data/environments.json`, `data/locks/`): two environments are listed, `training` (the trainer) and `studio` (Freeform
  Studio's recorder and review tools); anything not listed is not built. **A lock is a file of `name==version` lines, each with at least one `--hash=sha256:`**, and nothing else (no range,
  address, option, editable install or repeat; a test per case), and its own SHA-256 is written in the list, so a changed lock is refused even by one byte. An environment whose lock has no checksum
  yet, or whose source archive is unpinned in the registry, is listed and sized for the disk estimate but **cannot be built** (`not_pinned`): both shipped environments are in that state until VS-0.2
  makes the locks (**update:** the training lock exists now, see VS-0.2; it has no source archive any more, see F10). An entry may carry `python_max`: a Python newer than the lock's checksums cover is refused first as `python_new` ("newer than this part has been tried with"), never left to fail inside pip. The trainer's source is the pinned archive from `data/sources.json` (new kind `source`, entry `piper1-gpl-source`, unpinned), downloaded through the one agreement-checked
  door, unpacked safely (no `..`, absolute, backslash, device, hard link or outward link; a link is judged by where it really lands; size and count caps; one top folder dropped; built as `.part` and renamed), then
  installed editable with `--no-deps --no-build-isolation --no-index`. **Each build lives in its own folder, `environments/<id>-<10 hex of a fingerprint>/`**, where the fingerprint covers the Python
  minor version, the lock, the source archive, the install and native-build settings and the source patches; a new lock or Python makes a new folder beside the old (nothing deleted). A folder with no
  record of ours is refused (`not_ours`), as is one from a newer version or with a damaged record, and none of them is changed. The record (`ack-env.json`, atomic, owner-only) keeps each step with
  the input it was built from; **every step is verified against the folder itself, not the record alone** (the Python reports its own minor version and that it is a virtual environment; the installed packages and
  the trainer's package are compared with the lock, markers and version spelling judged by pip's own vendored rules; the native part must exist; the launcher must be byte for byte what is wanted),
  so a removed piece is rebuilt and a good one kept, and a failed step is the first tried next time. Packages install with `--require-hashes --only-binary=:all: --no-deps`. One build per environment at a time (a lock
  file linked into place whole, owner checked by pid, start time and boot like a job). Room is checked before work starts (the estimate plus 1 GiB; a resume with only small steps left needs less). **Fixes are by wrapper:** `ack_run.py` runs the
  documented workarounds (the `torch.load` safe-globals one and `dynamo=False`, from the guide, unverified until VS-0.2) and then starts a module, so no program file is edited. A **source patch** is
  listed in the environment's data (none now); it is shown with the lines around it, needs a yes (the default answer is no), keeps the original beside the file first (never overwriting an earlier backup), refuses a file
  that something else changed since, and is asked for before anything is installed. The **self-test** runs each probe inside the finished environment with the network off; probes that need a graphics card are skipped, and
  said to be skipped, when there is none. 22 three-part error codes, step names, state words and probe names are in the catalog. `System.run` gained `cwd` and `env`. **Tests:** 164 with stand-ins, 74 for the list and the lock rules, and 10 that
  build a real Python environment (a real native-build script, the real checks inside it, pip's own marker and version rules; only the download is faked). **Mutation testing:** about 135 deliberate breaks over two rounds
  (a missing check, a boundary, a mode, a skipped confirmation...); the first round missed 13, each now has a test, and the survivors are equivalent (a link in the way is also refused by the operating system's rename, a missing
  package makes the checking script crash and so counts as "not good" either way). **Not done, and why:** the real lock files and the real archive address, revision and checksum (VS-0.2, on the developer's machine, to be made with a hash-generating
  resolver and tried with `--only-binary=:all:`, which assumes every dependency has a wheel); the sizes in the list are guesses (8 GiB, 1 GiB); no command line or window starts a build yet (VS-2.x), so nothing calls `build()` outside the tests.
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
  **As built (the logic; the screens wait for VS-2.1):** `core/setupplan.py` makes one list of everything that will be downloaded or built, in the order it is done (the two environments, the listening model, the trainer's source, the two starting voices), with its size, the site it comes from, why, its license, whether the size is exact, and **why it cannot be fetched yet** (today every item is unpinned, so the plan honestly says nothing can start). It judges the disk for the whole path with the P11 table (two people, both voices unless one is declined; only a starting voice can be declined) and builds the single agreement, which names each pinned entry by exact address, size and checksum and each environment's packages by name; an item that cannot be fetched is in no agreement. `core/setuprun.py` refuses to start unless nothing is unavailable, the disk fits (a tight disk needs a yes) and the saved agreement covers this list as it is now (a changed file under the same name is not covered); it then does each item in order, stops at the first failure, reports progress and carries on from the disk next time (there is no "I was here" note to disagree with the disk). `consent.merge_consent` keeps an earlier yes when a longer list is agreed to, and `fetch.is_fetched` lets a finished download be skipped without the network. **Starting voices are listed but not fetched here** (D30): each waits for its own acknowledgment (D27, VS-4.1).
- **VS-2.3 Projects (M, sandbox + dev).** List and create: whose voice (mine, someone else's); for someone else's, the consent note
  (who agreed, what to, when, how it can be withdrawn, how it was given) is required to continue (D21). It also asks roughly how long the recording will be, which sets the project's disk budget (P11). The starting voice is chosen here too (D25; the thin slice has only Mike and VS-4.1 adds the
  choice), and an Advanced section lets the person put scratch on another drive (D24, VS-1.11). After: VS-1.5, 2.1.
  **As built (the logic):** `core/newproject.py`. `evaluate` reports everything wrong with the form at once, in the form's order (name, whose voice, the consent note, hours, starting voice, scratch place), and never cuts what a person typed (a name or note over its limit is a problem to fix, because shortening a consent note would change what they wrote). Hours are read the way people write them (a decimal comma is fine). It gives the P11 estimate for the planned hours, with a chosen scratch drive judged on its own, and the VS-1.11 assessment of a chosen place (refusals are problems, warnings are not). `create` makes the project and only then sets up a chosen place with `scratch.create_scratch`; if the drive stopped working in between, the project still exists on its default place and the result says so. A short disk is information, never a reason to refuse the project.
- **VS-2.4 Import an ACK package (M, sandbox + dev).** File chooser → `freeform_studio.ack_import` → counts, minutes, any problems in plain
  words. The package is never deleted. After: VS-2.3.
  **As built:** `core/ackimport.py`. The chosen file is only read. It is copied into the project's `incoming` folder (the folder the Review page uses, which no backup sweeps and no program deletes), checked byte for byte against the original, and everything after is done from the copy (D31): Freeform Studio's own reader checks every audio file against its checksum, the plan says what is new and what is already in, and adding is additive and repeatable. A package that fails a check leaves nothing but the copy this step made, and removes that; a copy that was already there is never removed. Room is checked before the copy and again before adding.
- **VS-2.4b Finish the imported recordings (M, sandbox). Done 2026-10-10. Added after reading the code.** An imported recording is not ready for a dataset: the server decodes it, listens for speech, transcribes and proposes the pieces, and nothing in the plan said who does that when no server is running. `freeform_studio/process.py` (new, with tests) runs that same job code once for every waiting recording and stops (D28): JSON lines for a program, owner-only files, safe to stop and run again, and it refuses to start (exit 3, nothing begun) when the speech model is not already on the computer, because it never downloads. `core/joblines.py` reads its output (and the dataset builder's) into plain data and was tested against the real programs.
- **VS-2.5 Dataset (M, sandbox + dev).** A friendly wrapper over `build_dataset`: preview, build, show minutes and what was left out and
  why; refuses to overwrite; always a fresh cache folder (the guide's stale-cache rule).
  **As built (builders and readers):** `freeform_studio/build_dataset.py` gained `--json` (the same facts the report prints, as one object, also for a dry run; the printed report is unchanged). `core/commands.py` builds the command for a new training set (always a new folder named from the time; a folder with anything in it is refused before a job starts) or a preview, and `core/joblines.py` turns the result into counts, minutes, the left-out pieces grouped by reason and flag, and Freeform Studio's own length advice (under 10 minutes of speech tends to give an uneven voice; 30 is comfortable).
- **VS-2.6 One training round (M, dev).** Start, progress, stop cleanly at the end of the time. One starting voice, Mike (D25), hard-coded.
  After: VS-1.6, 2.5.
  **As built (the command only):** `core/commands.py::train_command` is the guide's `piper.train fit` line, run through the environment's launcher, with the guide's rules enforced before a job exists: the audio folder is exactly the dataset's `wav/`, the working folder is always new (a cache from other audio trains on the old audio without a word), it starts from a `.ckpt` file that is there, and `--trainer.max_time` ends the round (PROVISIONAL: the guide never used it, so VS-0.2 must show it stops cleanly and saves a usable `last.ckpt`). `find_checkpoints` / `latest_checkpoint` read the highest `lightning_logs/version_N/checkpoints/last.ckpt` of a run (the highest version, not the newest file). The numbers (batch 12, 4 workers, check every 10 epochs, 25 minutes) are the guide's, from one 8 GB card, until VS-0.2. Progress from the trainer's log is not parsed: its format has not been seen here.
- **VS-2.7 Listen (M, dev).** Export the latest checkpoint to a temporary `.onnx`, patch it (reusing `patch_voice_for_sherpa_onnx.py`),
  synthesize three test sentences with sherpa-onnx, play them. What you hear is what the phone will say. After: VS-2.6.
  **As built (the commands only):** `export_command` (the export through the launcher, so the `dynamo=False` workaround lives there), `copy_config` (the settings file next to the model under the exact name `<model>.onnx.json`, never replacing a file), and `patch_command` (the repository's own patcher). Synthesizing the three sentences needs sherpa-onnx on the PC, which is in no lock yet: where it lives (the training environment or one of its own) is an open decision for VS-0.2 and VS-5.2.
- **VS-2.8 Export and "what now" (M, sandbox for the zip, dev for the screen).** Write `my_voice_backup.zip` in ACK's layout, open its
  folder, show picture-style steps (copy to the phone, ACK → Audio Architect → IMPORT VOICE BACKUP). The screen also says what the voice descends from and that publishing it is a separate decision (D27). After: VS-2.7.
  **As built (the zip; the screen waits for VS-2.1) with VS-5.3 done with it:** `core/voicezip.py`. `check_voice` applies ACK's import rules on the PC before anything is written: ACK's size limits, a config that looks like a Piper config, and the model metadata that sherpa-onnx requires and Piper's own export does not write (read from the top of the ONNX file without the onnx library, skipping the weights, and cross-checked against the real library and the real patcher in tests). `write_voice_zip` writes exactly `model.onnx` then `model.onnx.json`, no zip64 fields (the phone's zip reader is not asked to understand them), the same bytes for the same input, owner-only; reads the zip back and compares every byte; refuses to replace a file; removes any half-written one. `verify_voice_zip` applies the phone's rules to a finished zip. **VS-5.3:** `tests/test_vs_voicezip_contract.py` reads ACK's Kotlin source (entry names, the 400 MiB / 300 MiB / 1 MiB limits, the two required config keys, the symbols the phone leaves out) so a change on the phone side fails here.
  **Found on the first real phone (2026-10-11), and fixed in the app:** ACK's IMPORT CUSTOM VOICE accepted only the two trainer files, and the zip restore (IMPORT VOICE BACKUP) was shown only once a voice existed, so this zip could not be the first thing imported. IMPORT CUSTOM VOICE now also takes one `.zip` (`core/CustomVoiceImport.kindOf` routes by name; `CustomVoiceRepository.importPicked` sends it to the same restore path, which checks the two entry names, the sizes and the settings file), and its failure message names both ways. Needs a build of the app that contains it.
- **VS-2.9 Thin-slice device test (M, dev + phone).** The whole path on the developer's Ubuntu and WSL machines, then in ACK. Written up in
  `docs/VOICE_STUDIO_DEVICE_TEST.md`. Gate: findings reopen decisions before widening.
  **As built so far (terminal only):** the checklist exists for the path that can be walked without a window: the machine's facts, the tests on Python 3.10, the first
  step, a job that outlives its terminal (the open WSL question), the speech model, importing a phone package (including a damaged one), finishing the recordings, the
  training set, one five-minute round on the graphics card (the numbers VS-0.2 needs), the voice file, and ACK on the phone. `tests/test_vs_device_test_doc.py` keeps it honest:
  every program and option it names must exist, every path must be there, its training command must match the one the tool builds, and each snippet is run for real in a home
  folder of its own. The window's part is added when VS-2.1 exists.

### Stage 3: Recording paths and helpers

- **VS-3.1 Freeform Studio from the window (M, dev).** Start and stop its server per project (`--output <project>`), with the token and
  certificates, and open the right page in the right browser (in WSL, the Windows one). Reuse its existing start-up refusals and messages.
- **VS-3.2 PC microphone path (S, dev).** Guided: localhost, no certificate. Tells the helper which browser and microphone are used.
- **VS-3.3 Reading material (L, sandbox + dev).** Easy public-domain passages and a phonetically balanced sentence list (D18), each with its
  license read and logged in `THIRD_PARTY_NOTICES.md` before it ships. A loader that puts a chosen passage into the Record page's
  reference-text box (Freeform Studio change, with tests). Pasting your own text and free speech stay as they are.
- **VS-3.4 Copy in an existing setup (M, sandbox + dev).** Detect → show what was found → checked backup → copy into a project → verify →
  leave the originals. Reuse the old training environment only if it matches the lock (D13). After: VS-1.5.
  **As built (the logic; the screens wait for VS-2.1):** `core/copyin.py` brings recordings in from a Freeform Studio folder set up by hand. The order is fixed and only the last two steps write into the project: look (count what a backup would hold, per language), judge the room (the backup and the copy, with the decoded audio the copy will need), make a **checked backup** of the older recordings
  (Freeform Studio's own, read back twice, a fresh one every time, and **no earlier backup is ever pruned**), preview what copying would add, copy **from that backup** (Freeform Studio's own restore, which only adds), then check every file in the backup is in the project byte for byte. A file the project already has in a different form is kept and the older one is put beside it.
  The older folder is never written to: a test compares every name, size, time and checksum before and after the whole flow. A link to the older folder, or a project inside it, is refused. The decoded audio is not in a backup, so a repair job (`commands.repair_command`) follows; the old backup folder defaults to `~/ack-voice-studio/backups`, outside every project.
  **Not done here, on purpose (reopen if you disagree):** old datasets and trained checkpoints are listed by `core/legacy.py` but not copied (a checkpoint is a gigabyte each, and where rounds keep them is decided with the rounds engine, VS-4.2), and the old training environment is reused only when a lock exists to compare it against (VS-0.2).
- **VS-3.5 Phone over Wi-Fi: certificates (M, sandbox + phone).** Generate the restricted CA and a leaf for the current address (D16), re-issue
  when the address changes, show Android install steps for the CA file, and a QR code that opens the Record page. Chain verified with
  `openssl` in tests. After: VS-0.3.
- **VS-3.6 WSL network guidance (M, dev).** Detect the networking mode and the firewall state; explain; on a yes write `.wslconfig` (keeping
  `.bak`); show the firewall command to run as administrator; never restart WSL, and warn that training must be paused first (D17). Also say, in plain words, whether Ubuntu can start Windows programs (finding F4) and what the person can do about it; nothing in the tool depends on it, and the explanation of the idle shutdown (finding F3) belongs here too.
- **VS-3.7 Recording progress (S, sandbox).** "About X of 60 minutes", quality hints from the existing `ack_checks`, the disk left for the rest of the plan (P11), and what to do next.
  **As built (the decisions; the screen waits for VS-2.1):** `core/progress.py` turns the dataset builder's preview (already read by `core/joblines.py`), the project's planned hours and the free room into one picture:
  usable minutes against the target (the planned hours as minutes of usable speech, a guide and never a gate), the recordings still being listened to, failed or still being made, why pieces were left out,
  Freeform Studio's own length advice, whether the rest of the plan fits on the disk (judged with the same floors and edges as every other big step), and **one suggested next step**.
  The order is fixed and proposed (veto any): nothing recorded yet → record the first sentences; recordings still being listened to → let that finish (the count would mislead); under the target → record more;
  at the target with pieces a person can clear by looking (flagged, not approved, tagged, cut inside a word) → look them over; otherwise → make the training set. Nothing starts by itself.
  It reads no audio and runs no program, so Voice Studio's own Python needs no numpy for it; the preview comes from a job (`commands.dataset_command(..., dry_run=True)`).
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
  (no sound, no vibration, no auto-advance: it only tells). **On WSL this is not free (finding F3):** the instance powers down about a minute after the last window or terminal closes, taking every job with it. The fix that
  worked on the developer's machine is `[general] instanceIdleTimeout=-1` in `.wslconfig` (a Windows-side edit through `/mnt/c`, offered with a `.bak` and D17's explain-then-confirm rule; it needs a WSL restart, so never
  while a job runs; the tool says that Ubuntu then keeps running in the background until WSL is shut down). Before a long job starts on WSL the tool checks the setting is in place (and that WSL's version knows it)
  and, if not, says so in plain words and offers the edit; if the person declines, a plain warning when the window closes while a job runs, naming the job's last checkpoint. A session held open from Windows also
  works, but starting one from Ubuntu needs interop, which F4 shows is intermittent.
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
| D28 | Finishing imported recordings | **Headless, by Freeform Studio's own processor.** After an import, recordings are decoded, listened to and cut by `freeform_studio.process`, which runs the server's job code once and stops. No server and no browser are needed for the thin slice. It never downloads the speech model. (Found while building VS-2.4: nothing in the plan said who finishes a recording when no server runs.) |
| D29 | A model made of several files | **Each file is its own registry entry**, pinned by address, size and checksum like any other, and the files of one model share a `folder`; they are fetched through the same agreement-checked door into `downloads/models/<folder>/`, and Freeform Studio is given that folder. So the speech model is not fetched by a library's own download, and its files are checked the way every other download is. The real file list comes from VS-0.2. |
| D30 | Starting voices in the setup run | The setup run **lists** both voices (so the disk estimate and the agreement list are complete) but **fetches none**. Each is fetched when it is chosen, after the person's own acknowledgment (D27, VS-4.1). |
| D31 | The package is copied in | The chosen ACK package is copied into the project's `incoming` folder, checked byte for byte, and everything after is read from the copy. The original is never touched, and a copy this step made is removed only if the package then fails a check. |
| D32 | The trainer's install | **The published `piper-tts` wheel, hash-checked in the training lock, plus one small shipped source file built by the tool** (F10). Not a source archive: the trainer's own build downloads espeak-ng from GitHub (outside the one agreed place, unchecked, slow from the developer's computer). Decided on evidence (files compared, the compile and its answers checked); reopen if the wheel's training differs from the commit's in the first device run. |
| D33 | The trainer's quality score | **Off.** The trainer's optional `val_mos` score fetches and runs code and weights from GitHub at the first check and needs a library the lock does not carry (F12). A command-line switch cannot turn it off on a resume (F13), so the launcher replaces the scorer's loader with a no-op and skips that one checkpoint rule when its score was never logged. Checkpoints are kept by `val_mel` and chosen by listening. Reopen if you want the score back: it would need a pinned registry entry for the scorer's repository and weights, one more line on the agreement, and `torchaudio` in the lock. |
| D34 | A round's length | **A round's time limit counts from the round's own start.** The trainer's checkpoint carries the clock of the run that wrote it and restores it on a resume, which would shorten (or cancel) every later round; the launcher keeps that restore from doing anything (F14). A round's length is therefore exactly the minutes the tool asks for, and the total training time is the sum of rounds. |

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
- Needed from VS-0.2 for Stage 2: the speech model's real files (names, sizes, checksums, revision) for D29; whether `--trainer.max_time` stops a round cleanly and leaves a usable `last.ckpt`; where the training run's `lightning_logs` land; `onnx` and `onnxscript` in the training lock (the export and the patcher need them); and where sherpa-onnx lives for Listen.
- P11 and D26: the real numbers (cost per hour, the size of a checkpoint a run saves, margin, the floors, the slow-drive cutoff) wait for VS-0.2.
- **NVIDIA's licence on the training environment (new, 2026-10-10; your call).** Fifteen of the locked packages are NVIDIA's CUDA libraries (`nvidia-*`: cuBLAS, cuDNN, NCCL and the rest) and `torch` pulls them in. Ten of
  them say **proprietary** in their package metadata (`LicenseRef-NVIDIA-Proprietary` or "NVIDIA Proprietary Software"), one contradicts itself (`nvidia-nvtx` says "Apache 2.0" and carries the
  proprietary classifier), and four state no licence at all (`nvidia-cuda-runtime`, `nvidia-cudnn-cu13`, `nvidia-nccl-cu13`, `nvidia-nvshmem-cu13`; the `cuda-toolkit` meta-package states none either). They are not part of this repository and are
  installed from the package site by the person's own computer, but they are named in the lock and the setup screen's agreement lists `pip:training` as a download. I have **not read NVIDIA's licence
  text** (not reachable from here). Proposal: the agreement line for the training environment says in one sentence that it includes NVIDIA's CUDA libraries under NVIDIA's own licence, and
  `THIRD_PARTY_NOTICES.md` section 7 records it (done). Nothing on the screen has changed yet.
- **A lock for Python 3.13 and 3.14** (Ubuntu 26.04): wanted for "a wider variety of Ubuntu configurations", needs a machine that has that Python (see F9). Until then those Pythons are refused with `python_new`.
- **One small file of someone else's code now ships in this repository** (new, 2026-10-11; veto it if you disagree): `tools/voice_studio/data/native/monotonic_align_core.pyx`, 1148 bytes, the alignment
  code the trainer needs and the published wheel lacks. It is piper1-gpl's file (GPL-3.0-or-later, the same licence as this project), which in turn comes from the VITS project (believed MIT: **not
  checked**, no way to reach it from here); `THIRD_PARTY_NOTICES.md` records it. The alternative is to fetch it at setup from the trainer's repository with an address, size and checksum in
  `data/sources.json` (one more line on the agreement, and the developer's GitHub connection is slow). I chose shipping it because the setup then needs the package site and nothing else.

## 7. What I cannot do from here

The Linux sandbox has no GPU, no Windows, no WSLg, no desktop session, no screen reader and no phone. Everything in section 3's "plain Python"
rule can be unit tested here (preflight, registry, project model, rounds state machine, bootstrap against stand-in commands, report
redaction, zip contract). The window itself, training quality, listening results, the phone steps, the certificate on Android, WSL
networking, the Windows helper and the screen-reader behaviour can only be checked by the developer, and no stage that depends on them
is called done until the matching device-test items are ticked.
