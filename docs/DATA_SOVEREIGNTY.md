<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
# Keeping your voice data on your own computer

This is for anyone using Freeform Studio and the training steps to make a voice for their own AAC, and for speech-language
pathologists (SLPs) helping someone else do it. It says where the data is, when anything touches the internet, how to check
that yourself, and what to think about when the voice isn't yours.

**The rule this project follows:** recordings, what the PC heard, your edits, exports, backups, the training data and the
trained voice stay on devices you control. Nothing is uploaded, and nothing is sent anywhere, unless you do it.

This is not legal advice. It records what the software does, how that was checked, and the questions to ask.

## 1. Where everything lives

| What | Where (default) |
|---|---|
| Raw recordings, transcripts, your edits | `~/piper-recording-studio/output/_freeform/<code>/takes/` |
| Pieces you exported for training | `~/piper-recording-studio/output/<code>/freeform/`, and `output/_freeform/<code>/retired/` for what was replaced |
| Backups | `~/backups/freeform-studio` (or the folder you chose with `--backup-dir`) |
| Training dataset | `~/piper/freeform-dataset-<date>/` |
| Training cache, checkpoints, logs | `~/piper/my-training/`, `~/piper/checkpoints/`, `~/piper1-gpl/lightning_logs/` |
| The trained voice | the `.onnx` and `.onnx.json` files you exported, then inside the ACK app's private storage |
| On your phone, while recording | the browser keeps each audio part until the PC confirms it, then deletes it; unsent edits are kept as a draft |

## 2. When anything uses the internet

| When | Who is contacted | What is sent | How to avoid it |
|---|---|---|---|
| Installing (`install.sh`, `pip`) | PyPI | package names, your address | install once, then work offline |
| `python -m freeform_studio.models fetch` | huggingface.co | the model name, your address, library versions. **Asks first. No audio, no text.** | skip it by copying a model folder and using `--asr-model /path` |
| The server, review pages, export, backup, dataset building, `doctor` | **nobody** | nothing | (nothing to avoid) |
| The first training run | github.com, to fetch the `val_mos` quality scorer's code and weights, **and run that code** (`torch.hub`, `trust_repo=True`). Nothing of yours is sent. | the request itself | run it once online, then it works from its cache; or turn the scorer off (`--model.mos_metric none`, read in the trainer's source, not tried here) |
| Downloading a base voice checkpoint (training guide, step 3) | huggingface.co | the request | it is a step you take yourself |
| **Pasting recordings, transcripts or datasets into a hosted AI assistant or any website** | whoever runs it | **everything you paste** | don't. This is the easiest way to lose control of this data, and nothing here can stop it. |

**The server never goes online.** It loads the speech model from disk only (`--allow-model-download` is the opt-out, off by
default), and it switches Hugging Face's libraries to offline mode so they don't even ask whether a newer version exists.
Without that, each model load contacted huggingface.co, which was measured on 2026-10-01.

## 3. How to check it yourself

You don't have to take any of this on trust.

**The simplest test (no tools needed).** Disconnect your router from the internet (unplug its internet cable), keep Wi-Fi on so
your phone can still reach the PC, and record, review, edit, export and back up a take. Everything should work. If something
doesn't, tell the project: that means something needed the internet.

**Watch every connection a program makes** (Linux or WSL):

```bash
cd ~/ack-tools/tools && source ~/freeform-studio-venv/bin/activate
strace -f -qq -e trace=connect,sendto -o /tmp/net.log python -m freeform_studio --host 0.0.0.0 --asr-engine fake
# use it, press Ctrl+C, then:
grep -E 'AF_INET6?' /tmp/net.log | grep -v -E '127\.0\.0\.1|::1'
```
Expect nothing, or only a `connect` to `192.0.2.1:9` and to your own computer's address. The first is a UDP "connect" the
program uses to find which local address to put in the link; nothing is sent to it. The test suite checks that this
address is never sent anything.

**Run the project's own check.** `python -m pytest freeform_studio/tests/test_no_network.py -v` runs the whole workflow inside a
network namespace that has *only* the loopback interface (when your system allows it), logs every connection made by any
program, including `ffmpeg`, and fails on anything that isn't this computer. It first proves that `1.1.1.1` and a web address
are unreachable, so a pass shows nothing *needs* the network, not only that nothing used it.

**Check your own training.** Training is a separate program and was not run under these checks:

```bash
strace -f -qq -e trace=connect,sendto -o /tmp/train.log python3 -m piper.train fit ...your usual options...
grep -E 'AF_INET6?' /tmp/train.log | grep -v -E '127\.0\.0\.1|::1'
```
The first run will show connections to GitHub's servers (the scorer's download; strace shows addresses, not names). After that it should show nothing but this computer.

**Ask the doctor:** `python -m freeform_studio.doctor` also says whether the speech model is on this computer, whether other
accounts can read your recordings, and whether your recordings or backups are in a folder a cloud service may be uploading.

What was verified, and what was not, when this was written (2026-10-01):

* Verified by measurement: the server, the command-line tools and `ffmpeg`, driven through the full workflow with a stand-in
  speech engine, made no connection to anything but this computer, and the whole workflow passed with no network at all.
  The speech model loader makes zero connections in local-only mode. The Android app declares no network permission, has
  cloud backup switched off, and its code uses no network APIs.
* **Not measured:** a real speech model run end to end (the network where it was built blocks Hugging Face), a real training
  run, and a real phone. Those are covered by reading the code and by the checks above that you can run.

## 4. Phones and shared computers

* **Phone browser.** Browser sync can upload your history, and the link you open was once in the address bar with the access
  token in it. (The server now moves you to a clean address on the first visit, but the first visit happened.) Use a browser
  profile with sync off, or a browser without an account, for this page. If the phone is shared, clear the site's data in the
  browser's settings when you finish. The phone's keyboard, voice typing and any screen-recording or backup apps are outside
  this project's control.
* **The start-up message prints the access link.** Don't share a screenshot of the terminal. The token only works on your own
  network, but it opens your recordings.
* **Your network.** `--host 0.0.0.0` lets other devices on your network reach the server. Keep the access token on (the
  default), use `https` (the phone microphone needs it anyway), and don't run it on a public or shared Wi-Fi.
* **Shared computers.** New files are readable by your account only, but older files keep the permissions they had (`doctor`
  tells you). On a computer others use, use your own Windows account or WSL distribution, and turn on disk encryption
  (BitLocker on Windows). Nothing here can protect a recording from someone with your logged-in session.
* **Cloud-synced folders.** Don't keep recordings or backups in OneDrive, Dropbox, Google Drive, iCloud, or your Windows
  `Documents` or `Desktop` folders. `/mnt/c/Users/<you>/freeform-backups` is a reasonable place; check it isn't synced.

## 5. If the voice isn't yours (SLPs, family, support workers)

A voice recording can identify a person, and what they say may be health information. Depending on where you work, rules such
as HIPAA (US), or GDPR and UK GDPR (where a voice recording used to identify someone can be treated as biometric data), may
apply. Ask your organization's privacy officer. Some things to settle with the person (or their guardian) *before* you record:

1. **Consent, in a form they can understand.** What is recorded, that it trains a synthetic copy of their voice, where it is
   kept, who can hear it, how long it is kept, and that they can stop and ask for it to be deleted. Offer it in the person's
   own communication mode.
2. **What the finished voice could be used for.** A voice model can imitate the person. Say who may have the file and under
   what conditions. Treat the `.onnx` file as sensitive as the recordings.
3. **One person, one set of folders.** Use a separate `--output` folder (or Windows user or WSL distribution) per client, so
   recordings, backups and training data are never mixed.
4. **What "delete" means here.** The tool never deletes your recordings, and only prunes its own old backups by a stated rule.
   So deleting a person's data is a job to do on purpose, and it spans several places:
   * the recordings: `output/_freeform/<code>/takes/` and `retired/`, and `output/<code>/freeform/`
   * every backup: `python -m freeform_studio.backup --list`, then delete those files from the backup folder
   * the training data: `~/piper/freeform-dataset-*` and `~/piper/my-training/` (its `cache-*` folders hold processed audio)
   * the checkpoints (`~/piper/checkpoints/`, `lightning_logs/`) and the exported `.onnx`/`.onnx.json`. **A checkpoint contains
     what the model learned about the voice, and it cannot be "un-trained", so delete them if consent is withdrawn.**
   * copies on phones, USB drives and other computers, and the voice imported into the ACK app
5. **Handing over.** Give the person their recordings and voice, then delete your copies of everything above.
6. **The base voice's license.** A voice trained from a base checkpoint is a derivative of it, and base voices come with their
   own conditions. Read the base voice's `MODEL_CARD` (Piper's documentation says some voices have restrictive licenses) and
   note which base you used next to the finished voice. See `THIRD_PARTY_NOTICES.md`.

## 6. What this does not protect against

* Malware, or anyone using your logged-in computer. Recordings are ordinary files.
* Copies you make yourself (a USB stick, an email, a cloud drive, a chat window).
* Hosted AI tools and websites you paste data into.
* The phone's own operating system and apps.
* A synced folder this software can't recognise: the sync check looks at folder names, and only ever says "may".

## 7. How these rules are kept

They are checked by tests, so a change that breaks one fails before it ships: `test_no_network.py` (no connections, no web
addresses in shipped files), `test_privacy.py` (offline model loading, owner-only files, browser caching, the clean link,
synced folders), `test_sovereignty_policy.py` (the Android app: no network permission, no cloud backup, no network code) and
`test_license_headers.py` (licensing). The Android app's cloud backup is off for everything it stores; to keep a copy, or to
move to a new phone without a cable, use ACK's own export (Settings, EXPORT .JSON, and the voice and GIF `.zip` backups),
which stay under your control. The rules still allow a direct phone-to-phone transfer during setup (which does not go through the cloud), but that has not been tried on a real phone.
