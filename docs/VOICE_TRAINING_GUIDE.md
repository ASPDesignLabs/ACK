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

- Aim for more than a token sample — a few hundred sentences (an hour+)
  gets noticeably closer to "actually sounds like you" than 10 minutes.
  Quiet room, consistent mic distance, no clipping.
- It produces a `metadata.csv` (pipe-delimited: `filename.wav|Text.`) and
  a folder of `.wav` files — copy these somewhere under your training
  workspace, e.g. `~/piper/my-dataset/`.

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
2. Start the server bound to all interfaces, not just localhost:
   ```bash
   python3 -m piper_recording_studio --host 0.0.0.0
   ```
   Allow it through the Windows Defender Firewall prompt if one appears.
3. Find your PC's LAN IP (`ipconfig` in PowerShell, the Wi-Fi adapter's
   IPv4 address), and visit `http://<that-ip>:8000` in your phone's
   browser.
4. Record using your **phone's built-in mic** — not Bluetooth headphones
   connected to the phone, which would just move the same class of
   problem rather than remove it.

---

## 3. Get a base checkpoint

Fine-tune from an existing voice rather than training from scratch — far
less data and time needed to get a recognizable result. Grab one from
[`rhasspy/piper-checkpoints`](https://huggingface.co/datasets/rhasspy/piper-checkpoints)
on Hugging Face, matching quality tier (e.g. `medium`) and sample rate
(22050 Hz) to what you'll train with. Put it somewhere stable, e.g.
`~/piper/checkpoints/base.ckpt`.

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
  --data.batch_size 32 \
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

### One-time source patch this repo's training script needs

`piper1-gpl`'s default trainer callbacks include one that monitors
`val_mos` (a perceptual-quality score from an auto-downloaded MOS
predictor). If that predictor fails to load (common — it needs
`torchaudio`, which lags several versions behind current `torch`
releases and may simply not install cleanly), training crashes at
checkpoint-save time with a `MisconfigurationException`. Fix once, by
editing `~/piper1-gpl/src/piper/train/__main__.py` and deleting the
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

If this fails with a `torch.export`/`GuardOnDataDependentSymNode` error
(recent `torch` versions default `torch.onnx.export` to a new exporter
that's stricter than this code expects): edit
`~/piper1-gpl/src/piper/train/export_onnx.py`, and add `dynamo=False,` as
an argument to the `torch.onnx.export(...)` call. You'll also need
`pip install onnxscript` if you haven't already.

---

## 6. Testing locally on your PC (optional, but worth doing before ACK)

```bash
pip install piper-tts
cp ~/piper/my-training/config.json ~/piper/my-training/my_voice.onnx.json  # exact naming matters: <model>.onnx.json
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

Patches the `.onnx` in place. Only needs to run once per exported
checkpoint (re-run it again if you export a newer checkpoint later).

---

## 8. Importing into ACK

Settings → Audio Architect → **IMPORT CUSTOM VOICE** (or **RE-IMPORT**
if replacing an existing one) → pick both `my_voice.onnx` and
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
| `cythonize: command not found` (even after installing Cython) | Ran the build script with `sudo` — resets `PATH`, drops your venv | Drop `sudo`, just run `bash build_monotonic_align.sh` |
| `ModuleNotFoundError: No module named 'piper_train'` | Following an old rhasspy/piper tutorial — `piper1-gpl`'s module is `piper.train`, not `piper_train`, and has no separate preprocess step | Use `python3 -m piper.train fit ...` directly |
| `ModuleNotFoundError: No module named 'skbuild'` | `setup.py`'s own build-time deps aren't auto-installed when running it directly | `pip install scikit-build cmake ninja` |
| CMake error referencing a `/tmp/pip-build-env-.../ninja` path that no longer exists | Stale build cache from an earlier pip-isolated build | `rm -rf _skbuild build`, retry |
| `ModuleNotFoundError: No module named 'pkg_resources'` | `setuptools` 82+ removed it; `torchmetrics` still imports it | `pip install "setuptools<82"` |
| `MisconfigurationException: ModelCheckpoint(monitor='val_mos')` | MOS predictor needs `torchaudio`, which lags current `torch` | Delete the `val_mos` `ModelCheckpoint` entry in `train/__main__.py` (see §4) |
| `ValueError: num_samples should be a positive integer... num_samples=0` | `--data.audio_dir` doesn't match where the `.wav` files actually are | Fix the path so it points at the exact folder `metadata.csv`'s filenames resolve against |
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
  --data.batch_size 32 \
  --ckpt_path ~/piper1-gpl/lightning_logs/version_N/checkpoints/last.ckpt

# ...let it run a while, then Ctrl+C once...

# export + patch for ACK
python3 -m piper.train.export_onnx \
  --checkpoint ~/piper1-gpl/lightning_logs/version_N+1/checkpoints/last.ckpt \
  --output-file ~/piper/my-training/my_voice.onnx
python3 /path/to/ACK/tools/patch_voice_for_sherpa_onnx.py \
  ~/piper/my-training/my_voice.onnx ~/piper/my-training/my_voice.onnx.json

# then: ACK → Settings → Audio Architect → RE-IMPORT CUSTOM VOICE
```
