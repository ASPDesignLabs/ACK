# Freeform Studio

Capture free speech from your phone, have your PC transcribe it with word timings, then review and cut it into
training clips for Piper. It runs next to `piper-recording-studio` (its own port, its own venv) and shares its
`output/` folder.

**Status: Phase 2 of 7 (phone capture works).** You can record from your phone, everything is saved to your PC as you
speak, the PC transcribes it, and you can read what was heard. Cutting, correcting, and exporting clips (the review
screens) come in the next phases.

## Install (once)

A separate venv, so nothing here can disturb the recorder or your training environment:

```bash
git clone --depth 1 --branch claude/quirky-carson-ia01h1 https://github.com/ASPDesignLabs/ACK.git ~/ack-tools
cd ~/ack-tools/tools
python3 -m venv ~/freeform-studio-venv
source ~/freeform-studio-venv/bin/activate
pip install --upgrade pip
pip install -r freeform_studio/requirements.txt
```
Needs `ffmpeg` on the PATH (you already have it) and Python 3.10 or newer (Ubuntu 22.04's default `python3` is fine;
check with `python3 --version`). Already cloned it earlier? Update with `git -C ~/ack-tools pull`.

## Try the speech recognition on your machine (do this first)

Record any 20-60 seconds of yourself talking (a phone voice memo works), put it on the PC, then:

```bash
cd ~/ack-tools/tools && source ~/freeform-studio-venv/bin/activate
python -m freeform_studio.asr_smoke ~/some-recording.m4a --model small.en --device cpu
```
The first run downloads the model, so expect a wait. It prints what was heard, how fast, which words the model was
unsure about, and how the review screen would cut the recording. Add `--prompt "names or jargon you say"` to bias it
toward your vocabulary, or `--prompt "Um, so, uh, yeah."` to make it keep filler words instead of tidying them away.

**GPU (optional).** CPU needs nothing extra and is what to use while training runs. To use the GPU when it is free:
```bash
pip install nvidia-cublas-cu12 "nvidia-cudnn-cu12==9.*"
export LD_LIBRARY_PATH=$(python3 -c 'import os, nvidia.cublas.lib, nvidia.cudnn.lib; print(os.path.dirname(nvidia.cublas.lib.__file__) + ":" + os.path.dirname(nvidia.cudnn.lib.__file__))')
python -m freeform_studio.asr_smoke ~/some-recording.m4a --model medium.en --device cuda
```
(`LD_LIBRARY_PATH` must be set before Python starts. This is faster-whisper's documented setup for CUDA 12.)
Don't run it on the GPU while training is running: 8 GB is not enough for both.

## Run the server

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

## If the page won't load

Run the checker in a **second terminal** while the server is running. It tests each link between your phone and this
program, changes nothing, and lists every problem with its fix, in order:

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
  take.json       status and details
```
This folder is deliberately outside `output/<code>/`, so `split_long_takes.py` can never pick up half-reviewed audio.
Approved clips will be exported into `output/<code>/freeform/` in the same layout as your prompted recordings.

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
| `POST /api/takes/<id>/transcribe` | run again (`model`, `initial_prompt`, `hotwords`, `regenerate`+`force`) |
| `POST /api/asr/release` | free the speech model's memory |

## Tests

```bash
cd ~/ack-tools/tools && source ~/freeform-studio-venv/bin/activate
pip install pytest && python -m pytest freeform_studio/tests -q
```
The browser tests (`test_capture_ui.py`) also need `pip install playwright` and a Chromium; they skip themselves
if either is missing.
