# Voice Training Guide — Piper → ACK

A personal runbook for training (or resuming training on) your own cloned
voice and getting it working as ACK's custom trained voice. Written from
the actual setup that got a working voice running end to end — every
gotcha below is a real thing that happened, not a hypothetical.

Environment this was built against: Windows 11, WSL2 (Ubuntu), an RTX
4060 GPU, training toolkit [`piper1-gpl`](https://github.com/OHF-Voice/piper1-gpl)
(the current maintained Piper fork), on-device engine
[`sherpa-onnx`](https://github.com/k2-fsa/sherpa-onnx) inside ACK.

---

## 0. The pipeline, end to end

```
record your voice  →  train (fine-tune from a base checkpoint)  →
export to .onnx  →  patch metadata for sherpa-onnx  →  import into ACK
```

Everything up through "export to .onnx" happens on your PC, in WSL2.
The metadata patch also happens on your PC (it can't be done on the
phone/in the app). Only the final import is on-device.

---

## 1. One-time PC environment setup

Use **WSL2**, not native Windows Python — this toolchain leans on
Linux-native build tooling (Cython, CMake/Ninja, espeak-ng) that's far
less painful there.

```powershell
# In an admin PowerShell, if WSL2/Ubuntu isn't already set up:
wsl --install -d Ubuntu-22.04
```
Only install the normal **Windows** NVIDIA driver — WSL2 passes your GPU
through automatically; don't install a separate Linux driver. Verify with
`nvidia-smi` inside WSL.

Inside WSL (Ubuntu), pick one clean directory for everything — don't nest
clones inside each other, that caused real confusion in this project's
own history:

```bash
sudo apt-get update && sudo apt-get install -y build-essential cmake ninja-build

git clone https://github.com/OHF-Voice/piper1-gpl.git ~/piper1-gpl
cd ~/piper1-gpl
python3 -m venv .venv
source .venv/bin/activate

python3 -m pip install -e '.[train]'
python3 -m pip install scikit-build cmake ninja   # setup.py's own build deps aren't auto-installed
python3 -m pip install "setuptools<82"             # pkg_resources was removed in setuptools 82+; torchmetrics still needs it

./build_monotonic_align.sh          # NEVER run this with sudo -- see Troubleshooting
python3 setup.py build_ext --inplace
```

**Never use `sudo`** for anything in this venv. `sudo` resets `PATH` and
drops your active venv, which silently breaks tool discovery (`cythonize`,
`ninja`, etc.) in ways that look like missing-dependency errors.

---

## 2. Recording your voice

Use [`piper-recording-studio`](https://github.com/rhasspy/piper-recording-studio)
— a local web app that prompts you with sentences and records/labels each
one at the right format (22050 Hz mono WAV) automatically.

**This is a completely separate tool from `piper1-gpl`** — its own repo,
its own venv, its own dependencies (`quart`, `hypercorn`, ...). It does
not live inside `piper1-gpl`'s environment, and trying to run it from
there fails with `No module named piper_recording_studio`. Give it its
own directory, e.g. `~/piper-recording-studio`, entirely separate from
`~/piper1-gpl`:

```bash
cd ~
git clone https://github.com/rhasspy/piper-recording-studio.git
cd piper-recording-studio
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt

python3 -m piper_recording_studio
```
Visit `http://localhost:8000` (or see the phone-recording section below
to reach it from your phone instead).

- Aim for more than a token sample — a few hundred sentences (an hour+)
  gets noticeably closer to "actually sounds like you" than 10 minutes.
  Quiet room, consistent mic distance, no clipping.
- It produces a `metadata.csv` (pipe-delimited: `filename.wav|Text.`) and
  a folder of `.wav` files, both under `output/<language>/` inside
  `~/piper-recording-studio` — copy these somewhere under your training
  workspace, e.g. `~/piper/my-dataset/`, before training (see §4).

### Recording from your phone instead (avoiding Windows Bluetooth headset quality)

Windows force-switches a Bluetooth headset from A2DP (clean, output-only)
down to HFP/mSBC (narrowband, bidirectional) the instant any app touches
the mic, to allow a return channel — this tanks quality on both ends
(recording *and* playback), independent of which recording app is used,
and there's no real fix for it on the Windows side. A phone's own
built-in mic sidesteps the problem entirely since there's no Bluetooth
codec switch involved at all.

`piper-recording-studio` is just a local web server, so you can run it
exactly as above but reach it from your phone's browser over Wi-Fi —
recordings still land in the same `output/` folder on your PC, no
separate transfer step:

1. One-time: since this runs inside WSL2, which has its own virtual
   network by default (invisible to other devices on your LAN), enable
   WSL2's **mirrored networking mode** (Windows 11 22H2+, a stable
   feature, not experimental). Create/edit `%UserProfile%\.wslconfig` on
   the Windows side:
   ```
   [wsl2]
   networkingMode=mirrored
   ```
   Then, in PowerShell: `wsl --shutdown`, then reopen your WSL terminal.
   (If your build reports mirrored mode as unsupported, the fallback is
   a manual `netsh interface portproxy` rule forwarding a port from
   Windows to WSL's internal IP — more fragile since that IP can change
   across reboots, but works everywhere.)
2. From `~/piper-recording-studio` (its own venv active — **not**
   `~/piper1-gpl`, a separate environment entirely), start the server
   bound to all interfaces, not just localhost:
   ```bash
   cd ~/piper-recording-studio
   source .venv/bin/activate
   python3 -m piper_recording_studio --host 0.0.0.0
   ```
   Allow it through the Windows Defender Firewall prompt if one appears.
3. Find your PC's LAN IP (`ipconfig` in PowerShell, the Wi-Fi adapter's
   IPv4 address), and visit `http://<that-ip>:8000` in your phone's
   browser.
4. Record using your **phone's built-in mic** — not Bluetooth headphones
   connected to the phone, which would just move the same class of
   problem rather than remove it.

### "getUserMedia is not implemented" on the phone's browser

This isn't a Chrome bug or something a different Android browser would
avoid — every modern mobile browser refuses to expose microphone access
at all (not just deny the permission prompt, the API itself is absent)
on an **insecure origin**: plain HTTP to anything other than
`localhost`. `http://<your-PC's-LAN-IP>:8000` is exactly that, so this
was always going to hit this wall once you got the phone actually
talking to the server.

**Fix used here: a locally-trusted HTTPS certificate via `mkcert`**,
fully wireless, one-time setup. (An alternative exists — USB port
forwarding through Chrome's remote-debugging tools, tunneling the
phone's `localhost` to the PC's — if you'd rather not touch
`piper-recording-studio`'s source; ask if you want that version
instead. The steps below are the one actually in use.)

1. Install `mkcert` in WSL:
   ```bash
   sudo apt install libnss3-tools
   curl -JLO "https://dl.filippo.io/mkcert/latest?for=linux/amd64"
   chmod +x mkcert-v*-linux-amd64
   sudo cp mkcert-v*-linux-amd64 /usr/local/bin/mkcert
   mkcert -install
   ```
2. Generate a certificate covering your PC's LAN IP (adjust the IP if
   it's changed since `ipconfig`):
   ```bash
   mkdir -p ~/piper-recording-studio/certs && cd ~/piper-recording-studio/certs
   mkcert 192.168.1.2 localhost 127.0.0.1
   ```
   Produces `192.168.1.2+2.pem` (certificate) and
   `192.168.1.2+2-key.pem` (private key) in that folder.
3. **Trust mkcert's root CA on the phone, once.** `mkcert -CAROOT`
   prints the folder containing `rootCA.pem` — get just that file onto
   the phone (email it to yourself, a cloud-synced folder, whatever's
   easiest for one small file — no need for any network setup for
   this single transfer). Open it on the phone; Android prompts to
   install it: Settings → Security (wording varies by device) →
   **Install a certificate → CA certificate**.

   Once installed, Android shows a persistent "Network may be
   monitored" notification — expected and benign here, it's just
   Android's standard warning for any manually-trusted CA regardless of
   who issued it.
4. **Patch `piper-recording-studio` to actually serve HTTPS** — it
   doesn't expose this by default. Back up
   `~/piper-recording-studio/piper_recording_studio/__main__.py` first,
   then add two arguments right after the existing `--port` one:
   ```python
       parser.add_argument("--certfile", help="Path to TLS certificate file (enables HTTPS)")
       parser.add_argument("--keyfile", help="Path to TLS private key file (enables HTTPS)")
   ```
   and, right before `asyncio.run(hypercorn.asyncio.serve(app, hyp_config))`, add:
   ```python
       if args.certfile and args.keyfile:
           hyp_config.certfile = args.certfile
           hyp_config.keyfile = args.keyfile
   ```
5. Run with HTTPS enabled:
   ```bash
   cd ~/piper-recording-studio
   source .venv/bin/activate
   python3 -m piper_recording_studio --host 0.0.0.0 \
     --certfile certs/192.168.1.2+2.pem \
     --keyfile certs/192.168.1.2+2-key.pem
   ```
6. From the phone, visit `https://192.168.1.2:8000` — **https**, same
   IP and port as before. Should load with a valid padlock (the phone
   trusts mkcert's CA now) and `getUserMedia` works, fully wireless.

### Splitting longer takes back into training-sized pieces

If you're recording the longer, paragraph-style prompts (multiple
sentences per take, read in one comfortable pass rather than one
sentence at a time), don't feed the resulting long audio files to the
trainer as single utterances — see `tools/split_long_takes.py`.
Longer recordings are great for your hands, but VITS training's
memory use scales roughly with the *product* of text length and audio
length per utterance, not the sum, so a handful of 30-second takes
mixed into training at the usual batch size can risk an out-of-memory
crash on an 8GB card. The script splits each long take back into
individual sentence-level (wav, text) pairs using silence detection
between sentences, so you get both: comfortable long reads, and
short, VRAM-safe training examples.

```bash
pip install pydub   # requires ffmpeg on PATH, per §6's export step

python3 /path/to/ACK/tools/split_long_takes.py \
  --input-dir ~/piper-recording-studio/output/en-US \
  --output-dir ~/piper/my-dataset-split
```
Point `--data.audio_dir` at `~/piper/my-dataset-split/wav` and
`--data.csv_path` at `~/piper/my-dataset-split/metadata.csv` for
training. Anything the silence detector couldn't confidently split
(sentence count didn't match detected pause count) lands in
`needs_review/` instead of being silently mismatched — see the
script's `--dry-run` flag and `--silence-thresh`/`--min-silence-len`
options if a lot of takes end up there on the first pass.

### Recording with the ACK app, away from your computer

If you would rather gather recordings wherever you are, ACK can do the recording on the phone and hand the result to Freeform
Studio later. In ACK open **Audio Architect → CUSTOM VOICE → RECORD TRAINING DATA** (the in-app HELP has a walkthrough under
BASICS // PERSONALIZATION).

1. **Write a script**, or paste one: any text you want to read. Write numbers and symbols the way you will say them. ACK splits the
   text into cards sized to read in one go (about ten seconds), and shows you how many cards it made.
2. **Set up the phone**: put it where it will stay, keep your mouth the same distance from it for the whole session, and run the
   two-second quiet check. It tells you if the room is loud or the microphone is covered.
3. **Read**. One card is shown at a time, large. Read it when ready; ACK hears when you finish, keeps the clip, and shows the next
   card, so you never touch the phone. It makes no sound or vibration while listening. *REDO LAST* sets a bad clip aside and shows
   that card again; *PAUSE* stops listening. A long script can be read over several sessions: each one starts at the first card
   not yet recorded.
4. **Or talk freely** with *RECORD FREE SPEECH* (up to 90 minutes in one go). The audio is kept whole and the phone only suggests cuts.
5. **Save to a file**: *SAVE ALL TO A FILE* writes a package (a `.zip`) where you choose, then reads it back and checks every
   recording in it. Move the file to your computer by cable or USB drive.
6. **Add it in Freeform Studio**: *Add recordings from ACK* on the Review page, or
   `python -m freeform_studio.ack_import <the file>.zip` (see the Freeform Studio README, *Recordings made with the ACK app*).
   Then review, approve and export as usual (below).

Keep the package on the computer until you have checked it, and only then delete the session on the phone: the phone never
deletes a session because you saved it. Recordings stay on your devices throughout; see `docs/DATA_SOVEREIGNTY.md`.

### Training on free-speech recordings (Freeform Studio)

Recordings made with Freeform Studio (`tools/freeform_studio/`) can be corrected and approved on your phone first (open
the **Review** page; see the Freeform Studio README). Numbers, symbols and abbreviations should be written the way you said
them ("twenty dollars", not "$20") because the training text is what the voice learns to pronounce; the Review page's *Say it in
words* buttons do this one tap at a time. Pieces that still have digits are accepted by default (the phonemizer reads digits
its own way, which may not be how you said them); pass `--allow none` to hold them back until you've fixed them. They live under
`~/piper-recording-studio/output/_freeform/en-US/takes/`, not in the folders the recorder and the splitter use, so they
need their own step to become a dataset. **Back up first** (the raw recordings are the one thing you can't regenerate). The
server already backs up by itself while it runs (every 6 hours, when something has changed), but make sure you have a fresh,
checked one right now:

```bash
cd ~/ack-tools/tools && source ~/freeform-studio-venv/bin/activate
python -m freeform_studio.backup        # says where it went, and reads the archive back to check it
```

By default it goes to `~/backups/freeform-studio`, which is inside WSL: copy the newest `freeform-backup-*.tar.gz` somewhere
outside it too (see section 8 of the WSL data guide), or start the server with `FREEFORM_BACKUPS=/mnt/c/Users/<you>/freeform-backups`
(a folder that is **not** synced by OneDrive or similar: these are recordings of a voice).
The Freeform Studio README's *Backups and safety* explains what is kept and how to restore (restoring only ever adds), and
*Your recordings stay on this computer* explains what does and doesn't use the internet. The first training run does fetch the
`val_mos` scorer from GitHub (see [DATA_SOVEREIGNTY.md](DATA_SOVEREIGNTY.md) section 2).

**Easiest route once you've reviewed:** export the approved pieces into the recorder's own folder layout, then run the same
split step you always do (the clips pass straight through it, alongside your prompted recordings):

```bash
cd ~/ack-tools/tools && source ~/freeform-studio-venv/bin/activate
python -m freeform_studio.export --dry-run     # what would be written, and which approved pieces are left out and why
python -m freeform_studio.export               # shows the same, then asks before writing
cp ~/ack-tools/tools/split_long_takes.py ~/tools/    # optional: the updated splitter understands the export's .presplit marker
python3 ~/tools/split_long_takes.py --input-dir ~/piper-recording-studio/output/en-US --output-dir ~/piper/my-dataset-split-2
```

(The Review page has the same export under *Training clips*.) Use a **new** `--output-dir` for the split, since re-running into
an old one leaves stale `.wav` files. Nothing the export replaces or stops exporting is deleted: it is moved to
`~/piper-recording-studio/output/_freeform/en-US/retired/`. Then train as usual, with a new `--data.cache_dir`.

**Or build straight from the recordings**, which can also include confident pieces you haven't reviewed:

From `~/ack-tools/tools`, with the Freeform Studio venv active:

```bash
python -m freeform_studio.build_dataset --dry-run      # preview: what goes in, what is left out and why. Writes nothing.
python -m freeform_studio.build_dataset                # build a NEW dataset folder (~/piper/freeform-dataset-<date-time>)
```

It prints the exact `piper.train fit` command to run, with a **new `--data.cache_dir`** (the trainer caches each clip
under its row number plus the start of its text, so reusing a cache after the audio changes silently trains on stale
audio). Useful options: `--also ~/piper/my-dataset-split` mixes in your earlier prompted recordings;
`--allow low_confidence` brings back pieces the recognizer was unsure about (read `excluded.txt` in the dataset folder
first); `--include approved` uses only pieces you approved in the Review page (the strictest and best choice once you have
reviewed enough); pieces you tagged `laugh`, `cough`, `noise` or `unclear` are always left out unless you pass
`--exclude-tags none`; pieces whose cut point lands inside a word (flagged "cuts a word" in Review) are left out too, even if
approved, because the text and audio disagree (`--allow cuts_word` overrides); `--no-normalize` keeps original loudness.
It never changes your takes and never overwrites an existing dataset folder.

What it does to each piece: cuts it from the take, brings it to a consistent level (peak about -3 dB), adds a
few-millisecond fade so cuts never click, and converts to 22050 Hz mono 16-bit. It leaves out pieces shorter than
1 s or longer than 11.5 s (long ones can run an 8 GB card out of memory), pieces that are too quiet or repeatedly clip,
and anything whose text would break the training file. Training itself trims leading and trailing silence, so none is
trimmed here.

---

## 3. Get a base checkpoint

**Check the base voice's license first.** A voice you train from a base checkpoint is a derivative of it, and each Piper voice
comes with its own conditions in its `MODEL_CARD` file; Piper's own documentation warns that "some voices may have restrictive
licenses". Read it before you share or distribute the result, and note which base you used next to the finished voice. If the
voice you are training is someone else's, read [DATA_SOVEREIGNTY.md](DATA_SOVEREIGNTY.md) first (consent, keeping the data local,
and what deleting it involves).

Fine-tune from an existing voice rather than training from scratch — far
less data and time needed to get a recognizable result. Grab one from
[`rhasspy/piper-checkpoints`](https://huggingface.co/datasets/rhasspy/piper-checkpoints)
on Hugging Face, matching quality tier (e.g. `medium`) and sample rate
(22050 Hz) to what you'll train with. Put it somewhere stable, e.g.
`~/piper/checkpoints/base.ckpt`.

**Not every checkpoint in that repo works with `piper1-gpl`'s current
trainer.** The oldest entries (e.g. `en/en_US/lessac/medium`) predate
the piper1-gpl rewrite and were saved by an older training codebase —
their embedded hyperparameters include fields the current model class
doesn't accept (`sample_bytes`) and long-removed PyTorch Lightning
Trainer args (`resume_from_checkpoint`, `auto_select_gpus`, `tpu_cores`,
`amp_backend`, ...), plus the original author's own machine paths. Using
one as `--ckpt_path` fails with `Subcommand 'fit' does not accept option
'model.sample_bytes'` / `Parsing of ckpt_path hyperparameters failed`
([reported upstream too](https://github.com/OHF-Voice/piper1-gpl/discussions/138)).
`en/en_US/hfc_male/medium` (added October 2023, after the rewrite) has
been confirmed by other users to work as a base instead. To check any
candidate before committing to a full run:

```bash
python3 -c "
import torch
ckpt = torch.load('/path/to/candidate.ckpt', map_location='cpu', weights_only=False)
print(ckpt.get('hyper_parameters'))
"
```
Old-format ones show original-author paths like `/home/hansenm/larynx2/...`
and Lightning args that no longer exist; a compatible one won't.

---

## 4. Training

```bash
cd ~/piper1-gpl
source .venv/bin/activate

python3 -m piper.train fit \
  --data.voice_name "my_voice" \
  --data.csv_path ~/piper/my-dataset/metadata.csv \
  --data.audio_dir ~/piper/my-dataset/wav \
  --model.sample_rate 22050 \
  --data.espeak_voice "en-us" \
  --data.cache_dir ~/piper/my-training/cache \
  --data.config_path ~/piper/my-training/config.json \
  --data.batch_size 12 \
  --data.num_workers 4 \
  --trainer.check_val_every_n_epoch 10 \
  --trainer.log_every_n_steps 1 \
  --ckpt_path ~/piper/checkpoints/base.ckpt
```

Notes:
- `--data.audio_dir` must point at the actual folder holding the `.wav`
  files referenced by `metadata.csv` — a mismatch here (e.g. pointing at
  a parent folder instead of the exact `wav/` subfolder) silently drops
  every sample and crashes later with `num_samples=0`.
- Checkpoints land in `~/piper1-gpl/lightning_logs/version_N/checkpoints/`
  (`N` auto-increments every time you run `fit`) — **not** wherever
  `--data.cache_dir` points.
- **Batch size 12 and checking every 10 epochs are for a small dataset on an 8 GB card.** One real run on an RTX 4060 (8 GB)
  with batch 32 crawled at about 0.02-0.04 steps per second (tens of seconds per step); after dropping to batch 12 and
  validating every 10 epochs, an epoch of a few steps took 4-5 seconds. Both were changed together, so which mattered more
  isn't known; the likely cause of the batch-32 slowness is the model not fitting in 8 GB and spilling into system memory. On a
  bigger card try 16 or more, and if steps suddenly take tens of seconds, go back down. If it runs out of memory, try 8.
- **Why `--trainer.check_val_every_n_epoch 10`:** with a small dataset an epoch is only a few steps, and the trainer's default
  is to validate after *every* epoch. Each validation synthesizes five test sentences, scores them with the MOS predictor
  (which runs on the CPU), writes five audio clips to TensorBoard and saves checkpoints (each about a gigabyte, by estimate), so
  most of the time went there. Checkpoints, `val_mos` and the audio samples now arrive every 10 epochs, and Ctrl+C can lose up
  to the epochs since the last one. `--trainer.log_every_n_steps 1` is because epochs have fewer than the default 50 steps,
  which otherwise leaves the training-loss curves nearly empty. `--data.num_workers 4` replaces the default of 1. If your
  trainer rejects any of these options, check with `python3 -m piper.train fit --help` and leave that one out.
- **Disk space:** each run keeps up to about eleven checkpoints and `lightning_logs/version_N` folders pile up. Check with
  `df -h .` and `du -sh lightning_logs/*`, and decide for yourself what to remove.
- If you used the GPU for Freeform Studio's speech recognition, free it before you train (8 GB is not enough for both): on the
  Review page, **Status and safety → Free memory now**, or just wait; the model frees itself after 5 minutes idle. Confirm with
  `nvidia-smi` that the memory really went back (this was not measurable where the feature was built); if it didn't, stop the
  server, and restart it without `--asr-device cuda` (the default is the CPU) while training runs.

### One-time source patch older checkouts of this training script needed

Older versions of `piper1-gpl`'s default trainer callbacks include one that monitors
`val_mos` (a perceptual-quality score from an auto-downloaded MOS
predictor). If that predictor fails to load (common — it needs
`torchaudio`, which lags several versions behind current `torch`
releases and may simply not install cleanly), training crashes at
checkpoint-save time with a `MisconfigurationException`.

**You may not need this at all.** The current upstream source (checked at commit `efffbfb`, 2026-10-01) says a `val_mos` that
can't be logged is skipped with a one-time warning and doesn't affect the other checkpoints. If your training starts and logs
`val_mos` (it shows in the progress bar) there is nothing to do. If you do hit the error, your checkout is older: either update
it (back up any file you've edited first, since an update can clash with it) or apply the old fix, once, by editing
`~/piper1-gpl/src/piper/train/__main__.py` and deleting the
*second* `ModelCheckpoint(...)` entry (the one with `monitor="val_mos"`)
from `_DEFAULT_CALLBACKS`, leaving only the `val_mel`-monitoring one.
Back up the file first (`cp __main__.py __main__.py.bak`) — it's a
straight deletion, not a subtle edit.

### Resuming a later session

**Always point `--ckpt_path` at your own latest checkpoint, not the
original base checkpoint**, or you'll silently discard all your
progress and restart from the base voice every time:

```bash
--ckpt_path ~/piper1-gpl/lightning_logs/version_N/checkpoints/last.ckpt
```
(use the highest `version_N` you have).

### Switching to a different/bigger dataset partway through

Resuming with a different `--data.csv_path`/`--data.audio_dir` than a
previous run (e.g. moving from your original recordings to a
newly-split batch from `split_long_takes.py`) is a normal, supported
thing to do — the checkpoint is just model weights, and it doesn't
care that the data changed between runs.

**Use a fresh `--data.cache_dir` whenever the *audio* changes.** The
trainer caches each utterance's processed audio and spectrogram under a
name built only from the **row number in `metadata.csv` plus the first
~45 characters of that row's text** (`get_cache_id` in piper1-gpl's
`vits/utils.py`), and if a cache file already exists it is used as-is —
your audio file is not read again. So if a row keeps the same position
and opening words but you re-recorded, re-trimmed, or re-split its
audio, training silently keeps using the old cached version. A
brand-new set of sentences is mostly safe (different text gives
different cache names), but "safe mostly" is not something to debug at
epoch 3000: give each distinct audio state its own cache folder (e.g.
`cache-marathon` vs the original `cache`, or a dated name).
`--data.config_path` and everything else can stay put. Commands for
checking and rotating the cache are in
[VOICE_DATA_WSL_GUIDE.md](VOICE_DATA_WSL_GUIDE.md) §9.

Also worth knowing (read from the same source): training reads
`metadata.csv` with Python's `csv.reader` (`|` delimiter), loads and
resamples any audio you give it itself, and **trims leading/trailing
silence with a voice-activity detector, keeping 0.25 s on each side** —
so hand-trimming silence at clip edges is unnecessary.

For inspecting, checking, and backing up your recordings and datasets
from the terminal (with sample output), see
[VOICE_DATA_WSL_GUIDE.md](VOICE_DATA_WSL_GUIDE.md).

### How long to train, and how to stop

There's no fixed answer — with a small personal dataset fine-tuned onto
an already-strong base voice, you're more likely to overfit from
training *too long* than not long enough. Each "epoch" here is only a
couple of gradient steps (tiny dataset), so think in wall-clock chunks,
not epoch count:

1. Let it run ~20–30 minutes.
2. `Ctrl+C` **once** in the terminal and wait — Lightning catches it and
   shuts down cleanly. Don't mash it or close the window.
3. Export the latest checkpoint and listen (see below).
4. If it's not there yet, resume (pointing at your own `last.ckpt`, per
   above) for another chunk. Repeat.
5. If a later export sounds *worse* — noisier, more strained — that's
   overfitting starting to show; more training won't fix it, more/better
   recordings will.

Optional: watch `val_mel` trend live instead of squinting at log text —
`tensorboard --logdir ~/piper1-gpl/lightning_logs` from another terminal,
then open the printed URL (WSL2 forwards localhost to Windows
automatically).

---

## 5. Exporting to ONNX

```bash
python3 -m piper.train.export_onnx \
  --checkpoint ~/piper1-gpl/lightning_logs/version_N/checkpoints/last.ckpt \
  --output-file ~/piper/my-training/my_voice.onnx
```

**Then make the voice's config file, now.** Training wrote it to whatever `--data.config_path` pointed at (`config.json` in the
commands above). It has to sit next to the model with exactly this name, and **steps 6 (testing), 7 (patching) and 8
(importing) all need it**:

```bash
cp ~/piper/my-training/config.json ~/piper/my-training/my_voice.onnx.json   # <model>.onnx.json, exact naming matters
ls -l ~/piper/my-training/my_voice.onnx*     # you should see both my_voice.onnx and my_voice.onnx.json
```
(If you named your voice something else, say `Snakesan2.onnx`, the config is `Snakesan2.onnx.json`.)

If the export fails with a `torch.export`/`GuardOnDataDependentSymNode` error
(recent `torch` versions default `torch.onnx.export` to a new exporter
that's stricter than this code expects): edit
`~/piper1-gpl/src/piper/train/export_onnx.py`, and add `dynamo=False,` as
an argument to the `torch.onnx.export(...)` call. You'll also need
`pip install onnxscript` if you haven't already.

---

## 6. Testing locally on your PC (optional, but worth doing before ACK)

```bash
pip install piper-tts
# uses my_voice.onnx.json, the config you copied next to the model in step 5
python3 -m piper -m ~/piper/my-training/my_voice.onnx -f test.wav -- 'A sentence you never recorded.'
```
Copy `test.wav` to your Windows filesystem (e.g. `/mnt/c/Users/<you>/Desktop/`)
to play it if WSL audio passthrough isn't set up.

---

## 7. Patching for ACK (sherpa-onnx metadata) — required, PC-side only

ACK's on-device engine (sherpa-onnx) needs metadata embedded directly in
the `.onnx` file that piper1-gpl's export never writes. Skipping this
step is the #1 cause of an immediate crash on first synthesis in ACK.
This repo already has the fix as a script:

```bash
pip install onnx
python3 /path/to/ACK/tools/patch_voice_for_sherpa_onnx.py \
  ~/piper/my-training/my_voice.onnx \
  ~/piper/my-training/my_voice.onnx.json
```

The **first** file is the model (`.onnx`) and the **second** is its config (`.onnx.json`, from step 5): two different files.
(If you leave the second one out, `<model>.onnx.json` next to it is assumed.)

Patches the `.onnx` in place, **after keeping a copy of the original** beside it as `my_voice.onnx.before-patch` (you don't
import that one). The new file is written next to the model and swapped in only at the end, so if anything goes wrong your
model is left exactly as it was. Running it again on a patched model changes nothing. Only needs to run once per exported
checkpoint (re-run it if you export a newer checkpoint later; that gets its own backup).

If the script says something is wrong with the files, it explains what and prints the exact command to fix it; nothing has
been changed when it does. Use the copy of the script in your ACK checkout (`git pull` first), not an old copy you made
earlier: older copies show a Python error instead of that explanation.

---

## 8. Importing into ACK

Settings → Audio Architect → **IMPORT CUSTOM VOICE** (or **RE-IMPORT**
if replacing an existing one) → pick both `my_voice.onnx` (the patched one) and
`my_voice.onnx.json` together in one file-picker selection. The app
restarts automatically after a successful import.

Then, in the main VOICE PROFILE chip row, tap the **MY VOICE** chip
(only appears once a voice is imported) to actually put it on output.

Back up the installed voice from inside ACK (Settings → Audio Architect
→ EXPORT VOICE BACKUP) once you're happy with it — a `.zip` you can
re-import later without redoing the PC-side steps, including after a
reinstall.

---

## 9. Troubleshooting quick reference

| Symptom | Cause | Fix |
|---|---|---|
| Patching fails with `UnicodeDecodeError: 'utf-8' codec can't decode byte ... invalid start byte` (or a `JSONDecodeError`) coming from `json.load` | The second argument was the model (`my_voice.onnx`) instead of its config (`my_voice.onnx.json`), usually because that file didn't exist yet (the shell's Tab completion only offers what exists) | Make the config: `cp ~/piper/my-training/config.json ~/piper/my-training/my_voice.onnx.json`, then run the patch again. The current script explains this itself; nothing was changed, the failure happens before the model is touched |
| `cythonize: command not found` (even after installing Cython) | Ran the build script with `sudo` — resets `PATH`, drops your venv | Drop `sudo`, just run `bash build_monotonic_align.sh` |
| `ModuleNotFoundError: No module named 'piper_train'` | Following an old rhasspy/piper tutorial — `piper1-gpl`'s module is `piper.train`, not `piper_train`, and has no separate preprocess step | Use `python3 -m piper.train fit ...` directly |
| `ModuleNotFoundError: No module named 'skbuild'` | `setup.py`'s own build-time deps aren't auto-installed when running it directly | `pip install scikit-build cmake ninja` |
| CMake error referencing a `/tmp/pip-build-env-.../ninja` path that no longer exists | Stale build cache from an earlier pip-isolated build | `rm -rf _skbuild build`, retry |
| `ModuleNotFoundError: No module named 'pkg_resources'` | `setuptools` 82+ removed it; `torchmetrics` still imports it | `pip install "setuptools<82"` |
| `MisconfigurationException: ModelCheckpoint(monitor='val_mos')` | MOS predictor needs `torchaudio`, which lags current `torch` | Older checkouts only: delete the `val_mos` `ModelCheckpoint` entry in `train/__main__.py`, or update (see §4) |
| `ValueError: num_samples should be a positive integer... num_samples=0` | `--data.audio_dir` doesn't match where the `.wav` files actually are | Fix the path so it points at the exact folder `metadata.csv`'s filenames resolve against |
| `_pickle.UnpicklingError: Weights only load failed` / mentions `pathlib.PosixPath was not an allowed global` when starting `fit` with `--ckpt_path` | PyTorch 2.6 changed `torch.load`'s default to `weights_only=True`; Lightning's own checkpoint-path parsing calls `torch.load` on your base/resume checkpoint before training starts, and the checkpoint's saved hyperparameters include a `pathlib.PosixPath` that isn't on the new default allowlist | In `~/piper1-gpl/src/piper/train/__main__.py`, directly above the `_cli = VitsLightningCLI(` line, add: `import torch`, `import pathlib`, `torch.serialization.add_safe_globals([pathlib.PosixPath])` (back this file up first, to a name that doesn't clobber your existing `val_mos` patch backup) |
| `ModuleNotFoundError: piper.train.vits.monotonic_align.monotonic_align.core` | `build_monotonic_align.sh` never completed (often from the `sudo` issue above), so the nested `monotonic_align/monotonic_align/core.so` was never created | Re-run `./build_monotonic_align.sh` (no sudo); if a stray `.so` exists un-nested, `mkdir monotonic_align && mv core*.so monotonic_align/` inside `src/piper/train/vits/monotonic_align/` |
| `torch.export`/`GuardOnDataDependentSymNode` during export | Newer `torch` defaults `torch.onnx.export` to a stricter exporter this code wasn't written for | Add `dynamo=False,` to the `torch.onnx.export(...)` call in `export_onnx.py` |
| ACK crashes instantly on first synthesis; logcat shows `'sample_rate' does not exist in the metadata` | `.onnx` was imported without the sherpa-onnx metadata patch | Run `tools/patch_voice_for_sherpa_onnx.py`, re-import |
| ACK crashes; logcat shows `piper-phonemize-lexicon.cc:ReadTokens` / `size: 2` | A multi-character phoneme symbol (e.g. a merged diphthong) in `phoneme_id_map` — sherpa-onnx can only represent single-codepoint symbols | Already handled on ACK's side (`PiperVoiceEngine` skips these) — rebuild/reinstall the app, no PC-side action needed |

---

## Appendix: cheat sheet (once the environment is already set up)

```bash
cd ~/piper1-gpl && source .venv/bin/activate

# resume training (adjust version_N to your latest)
python3 -m piper.train fit \
  --data.voice_name "my_voice" \
  --data.csv_path ~/piper/my-dataset/metadata.csv \
  --data.audio_dir ~/piper/my-dataset/wav \
  --model.sample_rate 22050 \
  --data.espeak_voice "en-us" \
  --data.cache_dir ~/piper/my-training/cache \
  --data.config_path ~/piper/my-training/config.json \
  --data.batch_size 12 \
  --data.num_workers 4 \
  --trainer.check_val_every_n_epoch 10 \
  --trainer.log_every_n_steps 1 \
  --ckpt_path ~/piper1-gpl/lightning_logs/version_N/checkpoints/last.ckpt

# ...let it run a while, then Ctrl+C once...

# export + patch for ACK
python3 -m piper.train.export_onnx \
  --checkpoint ~/piper1-gpl/lightning_logs/version_N+1/checkpoints/last.ckpt \
  --output-file ~/piper/my-training/my_voice.onnx
cp ~/piper/my-training/config.json ~/piper/my-training/my_voice.onnx.json    # the config, next to the model
python3 /path/to/ACK/tools/patch_voice_for_sherpa_onnx.py \
  ~/piper/my-training/my_voice.onnx ~/piper/my-training/my_voice.onnx.json

# then: ACK → Settings → Audio Architect → RE-IMPORT CUSTOM VOICE
```
