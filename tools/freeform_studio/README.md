# Freeform Studio

Capture free speech from your phone, have your PC transcribe it with word timings, then review and cut it into
training clips for Piper. It runs next to `piper-recording-studio` (its own port, its own venv) and shares its
`output/` folder.

**Status: Phase 1 of 7 (backend only).** Upload, decoding, waveform data, transcription, segmenting, and safe
edit-saving all work and are tested. The phone pages (capture, review) arrive in the next phases, so for now there is
no screen to tap; this phase gives you the engine and a way to test real speech recognition on your machine.

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
python -m freeform_studio --output ~/piper-recording-studio/output --host 0.0.0.0 \
  --certfile ~/piper-recording-studio/certs/<your-ip>+2.pem --keyfile ~/piper-recording-studio/certs/<your-ip>+2-key.pem
```
It prints a link containing a private token; open that link once on the phone and the phone remembers it. The token
is stored in `output/_freeform/token` (readable only by you). Use `--asr-engine fake` to run without any speech model
(placeholder words, for testing). Everything here reuses the mkcert certificates you already made for the recorder.

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

## API (Phase 1)

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
