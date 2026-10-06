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
| On your phone, while recording in the browser | the browser keeps each audio part until the PC confirms it, then deletes it; unsent edits are kept as a draft |
| On your phone, while recording with the ACK app | inside ACK's own private storage, until you save a package; ACK has no network permission and its cloud backup is switched off |
| Packages saved by the ACK app | wherever you put the `.zip` file, then `~/piper-recording-studio/output/_freeform/<code>/incoming/` once you add it in Freeform Studio. Copies of what is on your phone; **not** included in backups; never deleted by the program |
| A backup you export from ACK (EXPORT .JSON) | wherever you choose to save it. It can hold the Emergency info card, Target Computer entries with phone numbers and addresses, saved locations, every voice recording (the audio itself), your messages, statements and settings. **It is not encrypted and has no password: anyone who opens it can read all of it.** ACK says this before it opens the file picker |
| The private safety copy ACK makes before a data upgrade | `files/auto_backups` in ACK's private storage: a full backup (recordings and Emergency card included), **not encrypted**, made once before an old Target Computer list is upgraded. PROTOCOL → DATA PORT lists it (SAFETY COPIES) and lets you delete it |
| The Terminal log | ACK's private storage. Kept for 7 days by default (you can choose 1 to 30). **Not** in any backup |
| A message log you save from ACK (SETTINGS > SAVE MESSAGE LOG TO A FILE) | wherever you choose to save it, as a plain text file. It holds **only the messages** the Terminal log still keeps (what was said or typed to be said, in full, with date, time and where it was sent from) and nothing else: no system or command lines, no people or places, no audio, no settings. **A message's own words are in it, so any name, address or number you said is too. It is not encrypted and has no password**, and a screenshot of the log is a copy as well. ACK warns first, writes nothing until you pick a place with the system file picker, never shares the file with another app and has no network code to send it. It is a copy: DELETE DATA does not remove it, and nothing in ACK tracks where you put it |
| A usage summary kept on this phone (SETTINGS > USAGE SUMMARY, off until you turn it on) | ACK's private storage, in a small file of its own (`ack_usage_tally`): one whole number per hour of each day, per place a message came from and per kind, for the last 90 days. **It never holds the words of a message,** a deck, button, person or place name, a recording or an exact time; a message's words are compared in memory with ACK's own starter phrases to choose its kind and then dropped. A message sent with `/n` and the HELP narration are not counted. It is **not in EXPORT .JSON** and a restore never changes it. ACK has no app lock, so anyone with the phone unlocked can switch it on, read it or forget it; while it is on the Terminal shows a line saying so. It can leave the phone only as a file you save with SAVE USAGE SUMMARY TO A FILE (warned first, system file picker, no share sheet, no network code). That file is not encrypted and still shows **when** someone communicates, so keep it like a diary. FORGET USAGE SUMMARY and DELETE DATA > USAGE SUMMARY remove the counts (each asks twice); a file you saved is not removed |
| The partner card's own sentences, and which of its sentences are on (the speech-bubble icon in the header) | ACK's private storage, in a small file of its own (`ack_partner_card`): up to two sentences the person wrote (200 characters each) and the list of sentences they turned off. **The sentences are the person's own words,** so any name, address or number they write is in it. It is in **EXPORT .JSON** (which names it in its warning and is **not encrypted**); a restore only fills an empty slot and never overwrites a sentence, and the on/off choices are not in the file. DELETE DATA > MESSAGES AND DECKS removes it. ACK never sends it anywhere: it is spoken through the phone's speech engine and shown on the screen like any message, and a play appears in the Terminal log (and the saved log) as a message from `PARTNER/CARD`. The built-in sentences are in the app and on `docs/PARTNER_CARD.md`; nothing about them is stored |
| What you copy with COPY (a composed statement, or a contact card's name, number, address or email) | the phone's clipboard, as plain text. ACK does not mark it as sensitive (you can see what was copied in the clipboard preview) and never clears it, so a keyboard's clipboard history, or any app allowed to read the clipboard, may keep it |
| The paired watch's copy of Target Computer names | inside the ACK Wear app on the watch (names only, not numbers or addresses). Deleting PEOPLE AND PLACES on the phone sends the watch an empty list, but a watch that is out of reach keeps the old names until it next connects. See section 8 |

## 2. When anything uses the internet

| When | Who is contacted | What is sent | How to avoid it |
|---|---|---|---|
| Installing (`install.sh`, `pip`) | PyPI | package names, your address | install once, then work offline |
| `python -m freeform_studio.models fetch` | huggingface.co | the model name, your address, library versions. **Asks first. No audio, no text.** | skip it by copying a model folder and using `--asr-model /path` |
| The server, review pages, export, backup, dataset building, `doctor` | **nobody** | nothing | (nothing to avoid) |
| Bringing a package from the ACK app into Freeform Studio (`ack_import` or the Review page's *Add recordings from ACK*) | **nobody** | nothing | (nothing to avoid). The package moves by cable or USB drive; ACK has no way to send it anywhere |
| Using the ACK Wear watch app | Google, through Google Play services (not through ACK), **only when Bluetooth between the phone and the watch is unavailable** | deck and Target Computer names, settings, and, if the watch audio relay is on, the speech audio. Google says it is end-to-end encrypted while it travels. **Not yet tested on a real phone and watch** | don't use the watch app. See section 8 |
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

**Run the project's own check.** `python -m pytest freeform_studio/tests/test_no_network.py -v` runs the whole workflow (including bringing in a package from the ACK app and processing it) inside a
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
* **Speech on the phone (the ACK app).** ACK speaks through Android's own text-to-speech engine, a separate app. ACK itself has no network permission, and
  its voice list shows only voices the engine reports as installed and not needing the internet. What the engine does with the text is outside this
  project's control; see `docs/PERMISSIONS.md`.
* **The start-up message prints the access link.** Don't share a screenshot of the terminal. The token only works on your own
  network, but it opens your recordings.
* **Your network.** `--host 0.0.0.0` lets other devices on your network reach the server. Keep the access token on (the
  default), use `https` (the phone microphone needs it anyway), and don't run it on a public or shared Wi-Fi.
* **Packages from the ACK app.** A package is a recording of a voice, so treat the `.zip` like the recordings themselves: carry it by cable or
  USB drive, keep it out of cloud-synced folders, and delete your copies when you no longer need them (the program never does). ACK's *save*
  button writes the file where you choose and offers it to no other app, on purpose.
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
   * **on the phone, in ACK:** PROTOCOL → DATA PORT → **DELETE DATA** (twelve areas: messages and decks (with the words learned for word suggestions), the Emergency info card, people and
     places, saved locations, the Terminal log, message recordings, training data, the trained voice, the GIF library, safety copies,
     temporary files, and settings, plus DELETE EVERYTHING). Each asks twice and says how to save the data first. Also **DELETE CUSTOM VOICE**
     (AUDIO ARCHITECT), **MANAGE RECORDINGS** for single voice recordings, and deleting a **training session** (it asks twice).
     Android's own **Clear storage** (Settings, Apps, ACK, Storage; the wording varies by phone) is the complete route and returns ACK to a new install
   * **the watch** may keep Target Computer names until it next connects (section 8)
   * nothing in ACK removes a file you saved elsewhere (an export, a package, a backup, a GIF or voice `.zip`) or anything you copied to
     another app. Delete those yourself
5. **Handing over.** Give the person their recordings and voice, then delete your copies of everything above.
6. **The base voice's license.** A voice trained from a base checkpoint is a derivative of it, and base voices come with their
   own conditions. Read the base voice's `MODEL_CARD` (Piper's documentation says some voices have restrictive licenses) and
   note which base you used next to the finished voice. See `THIRD_PARTY_NOTICES.md`.

## 6. What this does not protect against

* Malware, or anyone using your logged-in computer. Recordings are ordinary files.
* Copies you make yourself (a USB stick, an email, a cloud drive, a chat window).
* Hosted AI tools and websites you paste data into.
* The phone's own operating system and apps.
* **ACK's own storage is not encrypted and ACK has no app lock.** The phone's lock screen is the only barrier: anyone who can unlock the
  phone, or read its storage with the right tool, can read what ACK holds.
* An **EXPORT .JSON** file, a **safety copy**, a voice or GIF `.zip`, or a **training package** can be read by anyone who gets the file.
  None of them has a password.
* Anything you **copy** out of ACK sits in plain text on the phone's clipboard, where a keyboard's clipboard history or an app allowed to
  read the clipboard may keep it.
* The watch link: see section 8.
* A synced folder this software can't recognise: the sync check looks at folder names, and only ever says "may".

## 7. How these rules are kept

They are checked by tests, so a change that breaks one fails before it ships: `test_no_network.py` (no connections, no web
addresses in shipped files), `test_privacy.py` (offline model loading, owner-only files, browser caching, the clean link, synced
folders), `test_sovereignty_policy.py` (the Android app: no network permission, no cloud backup, no network code) and
`test_license_headers.py` (licensing). Inside the Android app's own tests, two guards keep the warnings honest: every field of
EXPORT .JSON must be described by the warning that says what the file contains (`ExportContentsTest`), and every preference file
or folder the app writes must be covered by DELETE DATA (`StorageCatalogueTest`), so a new place that stores data cannot be added
without deciding how it is described and deleted. The Android app's cloud backup is off for everything it stores; to keep a copy,
or to move to a new phone without a cable, use ACK's own export (Settings, EXPORT .JSON, and the voice and GIF `.zip` backups),
which stay under your control. The rules still allow a direct phone-to-phone transfer during setup (which does not go through the
cloud), but that has not been tried on a real phone.

## 8. Can the watch link leave your devices? (ACK Wear)

**Short answer: yes, it can, and ACK does not control it.** ACK itself has no network permission and no network code. But ACK talks to
the ACK Wear watch app through Google Play services (the Wearable Data Layer), a separate program with its own network access. Google's
own documentation says that when Bluetooth between the phone and the watch is not available, Data Layer messages can travel over
the internet, through Google's servers, and that Google encrypts them end to end while they do. Google Play services decides which route a
message takes, not ACK.

**What ACK sends over that link:** deck names and lists, Target Computer category and entry **names** (the labels only: not phone numbers,
addresses, emails or contact cards), the target list names, settings values (volume, sensitivity, timings), status, and, when the watch
audio relay is on, **the speech audio of what the phone says**, sent in pieces to play on the watch.

**What Google says, word for word** (the Wearable Data Layer overview, "Options for communication" and "Cloud"):

> Data is transferred in one of the following ways: Directly, when there is an established Bluetooth connection between the Wear OS device
> and another device. Over an available network, such as LTE or Wi-Fi, using a network node on Google's servers as an intermediary. All
> Data Layer clients may exchange data either using Bluetooth or using the cloud, depending on connections available to the devices.
> Assume that data transmitted using Data Layer may at some point use Google-owned servers.
>
> Data is automatically routed through Google Cloud when Bluetooth is unavailable. All data transferred through Google Cloud is end-to-end
> encrypted.

* **Source:** `https://developer.android.com/training/wearables/data/overview`, which said "Last updated 2026-09-28 UTC". It was read
  (the page itself, not a summary) on **2026-10-03**.
* The page does not say which route is used when both are available, and it makes no promise that the direct one is always preferred.
* It also says the Data Layer only shares data between the same app, with the same package name and signature, on the two devices, and that no
  other app can read it. That is about other apps on your devices; it is not a promise that Google's servers never carry it.

**What was not checked.**

* **Nothing was tested on a real phone or watch.** Whether, on your devices, a message really takes the internet route when Bluetooth is off
  has not been seen. The steps to see it yourself are in `docs/PRIVACY_DEVICE_TEST.md`, section I.
* The reference pages for `Node.isNearby()` and `MessageClient` (on `developers.google.com`) could not be opened from the session that wrote
  this, so **what `isNearby()` means exactly is not confirmed here.** A search result described `NodeClient.getConnectedNodes()` as nodes "to
  which this device is currently connected, either directly or indirectly via a directly connected node". ACK's own code asks for exactly that
  list before it sends (`watch/WatchSync.kt`, `output/OutputService.kt`), and does not look at `isNearby`.

**What you can do today.** If this data must never reach Google's servers, do not use ACK Wear (unpair the watch, or do not install the
watch app). If you do use it, the direct Bluetooth route is the one that stays between your two devices, so keep the phone's Bluetooth on and
the watch near it; Google's page does not guarantee that is the only route used.

**Open decision, not built (do not change this silently):** make ACK send to the watch only when `Node.isNearby` is true, at the two places it
sends (`WatchSync.sendMessage` and `OutputService.relayToWatchIfReachable`). That would keep ACK's own messages off the internet route. The
cost: a watch that is reachable only over the internet (for example, you left the phone at home) would stop working with ACK. It also depends
on `isNearby()` meaning what its name suggests, which still has to be confirmed (see above). The developer decides.
