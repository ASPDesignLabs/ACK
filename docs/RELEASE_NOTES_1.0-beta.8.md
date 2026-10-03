# ACK v1.0-beta.8 — Your Own Voice

*Released 2026-10-03*

This is the release where ACK can speak in **your** voice, and where the whole path to get there stays on devices you control. Record your voice on your phone, clean it up and cut it on your own computer, train a Piper voice there, and bring it back into ACK, where it runs on the phone with no network and no cloud service in between.

Around that sit the other big changes: a **Statement Composer** that replaces the TYPE tab, **Target Computer** syncing and relaying through ACK Wear to OVERSEER, **sharing a GIF** out of the GIF deck, and a change to **how Android's cloud backup treats ACK's data** that you should read before you update.

---

## The short version

- 🎙️ **Speak in a voice trained from your own recordings**, on the phone, with no network. A **MY VOICE** chip in the voice profile row puts it on every prompt.
- 📱 **RECORD TRAINING DATA** (new, in AUDIO ARCHITECT): write or paste a script and read it hands-free, or just talk. The phone cuts the clips, notes how each went, and saves everything to a file you move to your computer yourself.
- 🖥️ **Freeform Studio** (a desktop tool in this repository): imports those recordings, transcribes them on your own computer, lets you review and cut them into training clips, and builds a Piper training dataset. It never goes online.
- ✍️ **STATEMENT COMPOSER** replaces the TYPE tab: build multi-sentence statements from Target Computer entries and Shared Root Variables, preview them, save them in folders, **COPY them to the clipboard** for any other app, or speak them.
- ⌚ **Target Computer on the watch and OVERSEER**: the watch's copy now re-syncs after every pick, and ACK Wear relays it to OVERSEER.
- 🖼️ **SHARE** a GIF from the GIF deck through Android's share sheet.
- 🔒 **ACK's data is no longer part of Google's cloud backup.** Use the backups inside ACK. Details in *Before you update*.
- ⚖️ ACK is now explicitly **GPL-3.0-or-later**.

---

## ⚠️ Before you update

1. **Make a backup first.** It takes a minute and protects everything you've built.
   - Decks, phrases, statements, settings, your recorded voice prompts (audio included) and training scripts: PROTOCOL → DATA PORT → **EXPORT .JSON** (or type `/b` in the TERMINAL and confirm).
   - Any GIF deck: the deck's BACKUP menu → **EXPORT DECK (.ZIP)**.
   - A custom voice, if you already have one: AUDIO ARCHITECT → CUSTOM VOICE → **EXPORT VOICE BACKUP**.
   Copy those files off the phone.
2. **Install over your current version, as an update.** Don't uninstall first.
3. **Google's cloud backup no longer carries ACK's data.** ACK holds your phrases, voice recordings, a trained voice, saved places and settings, so none of it is uploaded now, whatever the phone's backup switch says. Updating in place is not affected. What changes is that **restoring a new or reset phone from a Google backup will not bring ACK's data back**; use the backup files above (FULL RESTORE FROM JSON, IMPORT DECK, IMPORT VOICE BACKUP). Direct phone-to-phone transfer during Android setup still works, because it doesn't go through the cloud.
4. **The watch app updates separately.** Installing ACK Wear needs ADB to sideload to a compatible watch, same as earlier betas. Update it too for the Target Computer changes below.

---

## What this update offers, piece by piece

| Piece | Where it runs | What it does | What it needs |
|---|---|---|---|
| **ACK** (phone app) | Your Android phone | Speak with your trained voice; record training data; the Statement Composer; GIF SHARE; everything else in ACK | The beta.8 phone APK |
| **ACK Wear** | Your Wear OS watch | Gestures, the Target Computer flyout, and now the OVERSEER relay | The beta.8 Wear APK, sideloaded with ADB |
| **Freeform Studio** | Your computer (Linux, or Windows through WSL2) | Imports ACK's packages, transcribes and cuts recordings, exports clips, builds a training dataset, backs itself up | Python 3.10+, ffmpeg, a one-time speech model download (about 480 MB) |
| **Voice training** (Piper, third-party) | Your computer, ideally with an NVIDIA GPU | Fine-tunes a voice from your clips | `piper1-gpl`, a base checkpoint. Not shipped with ACK; the guide walks through it |
| **Voice patcher** | Your computer | Adds the metadata ACK's engine needs to the trained `.onnx` | Python and the `onnx` package. In the repository: `tools/patch_voice_for_sherpa_onnx.py` |

Nothing here sends your voice anywhere. ACK has no network permission. The only step in the whole path that is allowed to use the internet is the one-time speech-model download, and it asks first.

---

## 🎙️ Speak in your own voice

- **IMPORT CUSTOM VOICE** in AUDIO ARCHITECT takes the voice's two files together (`.onnx` and `.onnx.json`), checks and installs them, and restarts ACK once so every screen sees the new voice. It runs on the phone through sherpa-onnx.
- **Two ways to use it.** A **MY VOICE** chip appears in the VOICE PROFILE row once a voice is installed: one tap and every prompt uses it. Or switch on **USE MY VOICE** in any custom slot's DSP chain editor, for a separately named slot.
- **Master Gain applies**, the way it does to a recording. ROBOTIC OVERLAY and BITCRUSH don't (the editor hides them with USE MY VOICE on, and the MY VOICE preset says *THIS ENGINE HAS NO DSP CONTROLS OF ITS OWN*). Pitch and speed have no effect on this voice.
- **It never leaves you silent.** If the custom voice fails to produce an utterance, ACK speaks that one with the phone's normal voice. Shake-to-kill stops a custom-voice utterance the same way it stops any other.
- **One voice at a time.** Importing another replaces the installed one.
- **Its own backup.** A trained voice is tens of megabytes, so **EXPORT VOICE BACKUP / IMPORT VOICE BACKUP** use a standalone `.zip`, separate from EXPORT .JSON. Restoring one restarts ACK once.
- **A voice straight from the Piper trainer needs patching first.** The trainer doesn't write the metadata sherpa-onnx requires, and an unpatched voice crashes on its first word. `tools/patch_voice_for_sherpa_onnx.py` fixes that. It keeps your original as `…onnx.before-patch`, writes the new file beside it and swaps it in only at the end, does nothing if the model is already patched, and explains any mistake (wrong file given twice, config missing) in plain words before changing anything.
- **Check the base voice's license.** A voice fine-tuned from a base checkpoint is a derivative of it. Read the base voice's `MODEL_CARD` before you share the result, and if the voice isn't yours, read `docs/DATA_SOVEREIGNTY.md` first.

---

## 📱 Record training data on your phone

**AUDIO ARCHITECT → CUSTOM VOICE → RECORD TRAINING DATA** turns the phone into the recording half of voice training, so you can gather clips wherever you are instead of sitting at a computer.

**Scripts, hands-free**
- Write or paste a script. ACK splits it into **cards** sized to read in one go (about ten seconds each) and shows the card count and rough minutes as you type. It warns about cards containing digits or symbols, because a voice learns the words you actually say.
- Read a card aloud. ACK hears you finish, **keeps the clip, and shows the next card**. You never touch the phone between cards.
- A long script can be read over **several sessions**; each starts at the first card not yet recorded.
- **REDO LAST** sets a bad clip aside and shows that card again. **PAUSE** stops listening. If nothing is heard for 20 seconds it pauses itself.
- **Marks** (NOISE, UNCLEAR, LAUGH, COUGH, STUMBLE) flag a clip so the review stage on your computer treats it carefully.
- The **end-of-card wait** (how long a pause counts as "finished") is adjustable from 0.8 to 2.5 seconds.
- Editing or deleting a script **asks first**.

**Free speech**
- **RECORD FREE SPEECH** keeps up to 90 minutes in one recording. The phone only *suggests* cut points; **the raw audio is never cut on the phone.**

**Recording quality**
- A **two-second quiet check** comes first. It tells you if the room is loud, the microphone is covered or muted, or something interrupted it.
- Audio is written straight to the phone's storage as it arrives, at **48 kHz** when the phone allows it (otherwise 44.1 kHz), 16-bit mono, from the microphone source with **no phone-side processing** where the phone offers one.

**Safeguards while the microphone is open**
- **No sound and no vibration**, because a button thump would land in the recording.
- The screen **stays on and doesn't rotate**, and leaving the app **pauses** recording.
- It needs **300 MB free** to start, and pauses (script) or stops and keeps what it has (free speech) before the last 100 MB.
- **If ACK closes in the middle of a card**, the unfinished recording is repaired the next time you open RECORD TRAINING DATA and **held back** until you've listened to it and chosen to keep it.

**Listen, then save**
- Play any clip back through ACK's normal audio output. **Keep** or **set aside** a repaired clip. A kept clip has no delete button, and deleting a whole session asks twice.
- **SAVE ALL TO A FILE** (or one session's own **SAVE TO A FILE**) writes a package, one `.zip`, **through Android's own save screen**, then **reads it back and checks every recording in it**. If the check fails, the half-made file is deleted and you're told nothing was lost.
- **There is no share sheet and no network.** You move the file to your computer yourself, by cable or USB drive. ACK never deletes a session just because you saved it.
- **Your scripts are included in EXPORT .JSON** (text only; restore adds or updates by id and removes nothing). Recordings are far larger and travel as the packages.
- A **RECORD TRAINING DATA walkthrough** is in HELP, under BASICS // PERSONALIZATION.

---

## 🖥️ Freeform Studio: install and use

**What it is.** A tool that runs on **your computer**, in this repository under `tools/freeform_studio/`. It isn't part of the Android app. It takes recordings, transcribes them with word timings on your own machine, lets you review and cut them into training clips on your phone's browser or your computer, and prepares them for Piper training.

**What it is not.** It doesn't train the voice itself (that's Piper's trainer), and it doesn't need an account or the internet to work.

### Install it (once)

You need a Linux machine, or Windows with WSL2 (the guides are written around Ubuntu under WSL2), plus Python 3.10 or newer and `ffmpeg`. The installer checks both and prints the exact `apt` command if something is missing, before it changes anything.

```bash
git clone --depth 1 https://github.com/ASPDesignLabs/ACK.git ~/ack-tools
~/ack-tools/tools/freeform_studio/install.sh
```

The installer makes its own virtual environment (`~/freeform-studio-venv`) so it can't disturb anything else on the machine, and it's safe to run again. `install.sh --check` only looks and reports; `--dry-run` prints every command it would run.

Then fetch the speech model, **once**. This is the one command in the whole workflow that is allowed to use the internet, and it asks before doing anything:

```bash
cd ~/ack-tools/tools && source ~/freeform-studio-venv/bin/activate
python -m freeform_studio.models fetch small.en
```

**Already have an older ACK tools folder?** Move it aside and clone again (`mv ~/ack-tools ~/ack-tools.old`, or clone into a new folder name). The folder holds only the program: your recordings, access token, backups and `~/freeform-studio-venv` live elsewhere and aren't touched.

### Bring your recordings in

```bash
cd ~/ack-tools/tools && source ~/freeform-studio-venv/bin/activate
python -m freeform_studio.ack_import ack-training-….zip --dry-run   # looks and checks; writes nothing
python -m freeform_studio.ack_import ack-training-….zip             # shows the plan, then asks
```

Or start the server with `~/ack-tools/tools/freeform_studio/start.sh`, open the link it prints, and use the Review page's **Add recordings from ACK** card.

- A package that fails any check **changes nothing** and tells you why in plain words. Importing **only adds**; a session you already added is recognised and skipped, so running it twice is harmless.
- Each session becomes **one recording**. A script session's clips are joined in order with a short gap, and **the phone's clip boundaries are kept as cuts**. Each card's words travel along as the **reference text**, so the Review page can compare what was heard with what you meant to say.
- Your computer **listens again** and adds warnings for you to look at: *no speech*, *distorted*, *very quiet*, *background noise*, *speech touches the edge*, *differs from the card*, *you marked a slip*, and *phone and computer disagree*. Marks you set on the phone as noise, unclear, laugh or cough keep a piece out of training until you clear them. Nothing is dropped or edited for you.

### From recordings to a voice: the whole path

1. **Record** on the phone (RECORD TRAINING DATA), or from your phone's browser through Freeform Studio.
2. **Move** the package to your computer and **import** it (above).
3. **Back up** before you change anything: `python -m freeform_studio.backup` (it reads the archive back and checks it).
4. **Review** on the Review page: correct the text, approve good pieces, split or join, fix numbers and symbols with the *Say it in words* buttons.
5. **Build a dataset:** `python -m freeform_studio.build_dataset --dry-run` to see what goes in and what's left out and why, then without `--dry-run`. It writes a **new** dataset folder (never overwrites one) and prints the exact `piper.train fit` command to run.
6. **Train** with Piper's trainer, in short chunks, listening as you go. `docs/VOICE_TRAINING_GUIDE.md` has every step, including the settings that worked on an 8 GB graphics card.
7. **Export** to `.onnx`, **patch** it with `tools/patch_voice_for_sherpa_onnx.py`.
8. **Import** into ACK (AUDIO ARCHITECT → IMPORT CUSTOM VOICE, both files at once).
9. **Tap MY VOICE**, then **EXPORT VOICE BACKUP** once you're happy with it.

### What Freeform Studio keeps private

- **The server never goes online.** The speech model loads from your computer only, and a missing model produces a plain message naming the exact fetch command. A test runs the whole workflow with no network and fails on any outside connection.
- Files are readable by you alone; everything under `/api/` is sent with `no-store` so audio and transcripts aren't cached by a browser; the access token is stored in a private file.
- It warns when your data folder looks like it's inside OneDrive, Dropbox, Google Drive or iCloud, and it never recommends a Documents folder for backups.
- Backups (every 6 hours while the server runs, when something changed) carry checksums and are checked by reading them back; restoring only ever adds.
- Guides: `docs/VOICE_TRAINING_GUIDE.md`, `docs/VOICE_DATA_WSL_GUIDE.md`, `docs/DATA_SOVEREIGNTY.md`, and the package format in `docs/ACK_TRAINING_CAPTURE_FORMAT.md`.

---

## ✍️ Statement Composer

The **TYPE** tab is now the Statement Composer, a screen for building longer, structured statements, not just a single phrase.

- Build multi-sentence statements out of **Target Computer entries** and **Shared Root Variables**, with a **live preview** of exactly what it will say before you commit to anything.
- **SAVE keeps references live.** A saved statement stores its Target Computer and variable references, not their current values, so it reflects any later change to the entries or variables it points at.
- **COPY puts the finished text on the clipboard**, so a statement built in ACK can be pasted into Messages, a chat app, an email or any other app. **SPEAK** sends it straight to output. Both work out every reference at the moment you press them.
- **Tap a Target Computer chip** to insert a *live* reference to that category's currently active entry. **BROWSE TARGETS** inserts a specific entry as *plain text* instead, since a browsed pick that isn't the active one can't be represented as a live reference. **Long-press a chip** to change which entry is active for that category; that's a real, app-wide change, the same as doing it from the Target Computer tab.
- **MY STATEMENTS** keeps saved statements in **folders** (tree → leaf, the same shape as Target Computer). Create nested folders, save into any of them, move a statement by saving it into another folder, and reload, copy, speak or delete from the list. Deleting a folder asks first. Included in EXPORT .JSON.
- **FULL SCREEN** hides ACK's header and bottom navigation while you compose. The toggle is pinned at the top so it's always reachable, and it turns itself off if you switch away from TYPE.
- **Classic Manual Override moved to `/m`** in the TERMINAL, unchanged (MEMORY BANKS, saved phrases, direct text output).
- **HELP has a STATEMENT COMPOSER walkthrough** (11 steps), and the MANUAL OVERRIDE walkthrough now starts from `/m`.

---

## ⌚ ACK Wear and OVERSEER

- The watch's **Target Computer copy is re-synced after every pick or clear**, from any screen, instead of only when a deck is activated. The synced data now also carries each category's active entry.
- **ACK Wear relays Target Computer to OVERSEER**: both the deck-scoped list and a new all-categories list (for OVERSEER's ALL TARGETS browser). A pick made on OVERSEER is passed back to the phone through the existing pick request.
- Additive: the watch's Target Computer flyout (from beta.7) and the legacy 8-slot picker are unchanged.
- **Fixed:** ACK Wear could miss Target Computer updates while its app wasn't on screen. Its manifest now declares the sync paths for background delivery.

---

## 🖼️ GIF deck: SHARE

A **SHARE** button next to DISPLAY FULL SCREEN sends the GIF itself through Android's share sheet (Messages, chat apps, social media). It uses a narrowly scoped file provider that exposes only the GIF library and gives the app you pick temporary read access to that one file. **No new permission**, and ACK still has no network permission: the file goes to the app *you* choose, never anywhere ACK sends it itself.

---

## 💾 Backups at a glance

| What | How | Where |
|---|---|---|
| Decks, phrases, statements, settings, your recorded voice prompts (audio included), training scripts, autocomplete history, Geo-Protocol, presets, routing, Terminal prefs | **EXPORT .JSON** / **FULL RESTORE FROM JSON** | PROTOCOL → DATA PORT, or `/b` in the TERMINAL |
| One matrix deck's phrases into a *new* deck | **IMPORT MATRIX AS NEW DECK** | PROTOCOL → DATA PORT |
| A GIF deck (real image files in real folders, viewable without ACK) | **EXPORT DECK (.ZIP)** / **IMPORT DECK (.ZIP)** | The GIF deck's BACKUP menu |
| Your trained voice | **EXPORT VOICE BACKUP** / **IMPORT VOICE BACKUP** | AUDIO ARCHITECT → CUSTOM VOICE |
| Training recordings | **SAVE ALL TO A FILE** (a checked package) | RECORD TRAINING DATA |
| Freeform Studio's recordings | `python -m freeform_studio.backup` (also automatic) | Your computer |

**Restore is additive everywhere.** An entry with a matching id is overwritten in place; anything the backup doesn't mention is left exactly as it is; nothing is wiped first. To remove something, use that feature's own delete or clear action. Importing a GIF `.zip` or a full restore that adds a deck restarts ACK once so every screen sees it.

---

## 🔒 Privacy and licensing

- **No network permission and no network code.** Permissions are unchanged from beta.7 (this release adds none), on both the phone and the watch. A test fails if ACK ever requests one or uses a network API.
- **No Google cloud backup** of ACK's data (see *Before you update*).
- **Recordings, transcripts, training data and the trained voice stay on devices you control**, end to end.
- **GPL-3.0-or-later.** `LICENSE` is the unmodified FSF text, the copyright line is in `NOTICE`, and every source file carries an `SPDX-License-Identifier` line. `THIRD_PARTY_NOTICES.md` lists every outside component with its license and how that was checked, **including the questions still open**.

---

## 🐛 Fixed

- ACK Wear could miss Target Computer updates while its app wasn't on screen. Its manifest now declares the Target Computer sync paths for background delivery.

---

## ✅ What has been proven, and what hasn't

Being straightforward about this matters for an app people rely on to communicate.

- **Proven end to end on one setup:** training a voice on a PC (an RTX 4060 with 8 GB, under WSL2), patching it, importing it into ACK, and speaking with it.
- **Tested without a phone, thoroughly:** everything that decides what RECORD TRAINING DATA records, cuts, keeps and writes (140 automated tests, plus shared test cases that the phone and the computer must both reproduce), and the packages it writes, which are opened by the same reader Freeform Studio uses.
- **The least-proven parts are the ones that need a real phone:** the microphone behaviour across different phones (some lack an unprocessed source or a 48 kHz mode, and ACK falls back and records which it used), the exact layout of the screens (the five mark buttons are the tightest), and the file picker against different storage providers. `docs/TRAINING_CAPTURE_DEVICE_TEST.md` is a do-this-expect-that checklist. If something doesn't match, the `ACK_TRAIN` lines in logcat carry counts, sample rates and reasons only, **never audio and never what a script says**.
- **ACK is a beta.** It's one person's personal tool, shared as-is. It isn't a substitute for professional AAC evaluation or speech-language therapy.

---

## 📚 Everything ACK does

This is the whole app, not only what's new. *(beta.N)* marks when something arrived, where it's recent.

### Playing a prompt
- **Full-screen visual and audible playback** of prompts, with audio to the phone speaker or a connected Bluetooth speaker. It works with the phone locked, so gestures get through completely touch-free.
- **OUTPUT DEVICE** (beta.6): pick a connected Bluetooth device or **ACK WATCH** to receive every prompt; FORCE SPEAKER always overrides it, and ACK falls back to the phone rather than go silent.
- **Silent Mode** (beta.2): show prompts without speaking them (emergency messages and tutorial narration still speak).
- **REPLAY** (beta.2): a chip stays 20 seconds after a prompt clears; replayed prompts are sticky. Every phrase you've said can be replayed from the TERMINAL log.
- **Audio focus for Android Auto** (beta.7) and a **media-volume floor** (beta.6) so output isn't lost to outside volume changes.

### Decks
- **MATRIX**: the core deck. Three poses (IDENTITY, DEFEND, CONNECT) with four phrases each, **profiles** that hot-swap whole sets of replies, and custom **context layers**.
- **Quick Actions**: twelve slots, three poses, no profile switching, so a gesture always means the same thing.
- **Emergency**: prompts stay on screen until deliberately cleared with a long tap-and-hold, can play a **beaconing tone** first, force the speaker, and the deck carries an **EMERGENCY INFO** card.
- **Emoji**: a built-in library grouped by feelings, needs and boundaries, or any emoji on your device; add text, make a prompt sticky.
- **GIF**: store and organize GIFs, modifiers for different aspect ratios, text on a GIF prompt, **SHARE** (beta.8), and **standalone .zip export/import** (beta.7).
- Create, rename, recolor and remove decks from the DECK label.

### Building what you say
- **Statement Composer** (beta.8) and **Manual Override** (`/m`).
- **Variables**: `{VAR}` for a local value; `{VAR:A}`, `{VAR:B}`, `{VAR:C}` for targeted ones that a **Root Override** can replace across a whole category at once.
- **Target Computer**: a category tree you organize yourself (People, Places, Food/Drink, Actions, and your own), **contact cards** for people and places (tap to call, map, email, or speak a name), per-category pick lifetime, `[COMPUTER:X]` tags in Matrix and Quick Actions phrases (beta.7), and `/t` to browse while typing.
- **Autocomplete** (beta.7): ACK remembers what you've typed into variable fields and offers your most-used entries back as chips, scoped to the exact field; **MANAGE AUTOCOMPLETE** in PROTOCOL browses and removes them.

### Your voice
- **AUDIO ARCHITECT**: Master Gain, Global Cadence, Force Speaker, Guide Vox; ready-made factory voices; three fully editable custom slots, each with a base voice from any TTS engine on your device plus pitch, speed, an optional robotic overlay and a bitcrush texture.
- **Voice recordings** (beta.5): record your own voice for any Quick Action, Quick-Access key or Matrix entry, with noise reduction, silence trimming and loudness normalization, previews, an overlay-on-play option, and **MANAGE RECORDINGS** as a drill-down tree.
- **Your own trained voice** and **RECORD TRAINING DATA** (beta.8, above).

### The watch and gestures
- **ACK Wear** (Wear OS): a gesture state machine, **ARM → LOCK POSE → MODIFY → FIRE**, across three poses, woken by a triple wrist twist, working with the phone locked and the screen off.
- **Safety on the watch** (beta.2): tap to cancel a locked pose, a warning buzz and a grace window before anything speaks, harder-to-trigger-by-accident poses, and **Shaky Hands** mode for steadier tolerance.
- **Target Computer flyout** (beta.7): a radial menu on the watch face for Quick Actions decks, browsed with the crown, confirmed with a double tap, with an adjustable timeout.
- **Training Ground** and **Deck Trainer**: practice gestures with live telemetry, nothing plays out loud, optionally scored against your own deck.

### Safety and recovery
- **Shake Kill Switch**: shake the phone to stop whatever is playing or on screen, with tunable sensitivity and a live test panel.
- **Confirmations** before deleting a phrase, clearing the log, or restoring a backup.

### The TERMINAL and HELP
- A timestamped, color-coded log that survives a restart (adjustable 1–30 day retention), long-press to save a phrase to a Memory Bank, and an optional monospace mode.
- Slash commands: `/help`, `/q`, `/n`, `/s`, `/e`, `/cls`, `/b`, `/repair`, `/info`, `/v`, `/t`, `/m`. `/info` reads these patch notes in the app.
- **HELP**: walkthroughs that only advance when you really do the thing, across navigation, deck management, settings, personalization, Manual Override, using decks, Target Computer / Geo-Protocol / logs, gesture training, voice recordings, record training data and the statement composer.

### Places
- **Geo-Protocol**: a Tactical Grid that works by coordinate with no map at all, zones, and optional offline maps from a Mapsforge `.map` file you import yourself. Nothing is fetched over the network.

### Your data
- **PROTOCOL → DATA PORT** and the standalone backups above, additive restore everywhere, no cloud, no network.

### The website and desktop tools
- A **GitHub Pages site** with a no-install **Deck Simulator** in the browser.
- **Freeform Studio**, the voice-training guides and the patcher (this release), all running on your own computer.

---

## 📦 Install

- **Phone:** download the beta.8 phone APK from this release's assets and install it as an update over your current version. Make a backup first (see above).
- **Watch:** install the beta.8 ACK Wear APK with ADB, same as earlier betas.
- **Desktop tools:** see *Freeform Studio: install and use* above, or `tools/freeform_studio/README.md`.

This is still a beta. Expect bugs, and please open an issue if something breaks.

---

*Full notes: [`CHANGELOG.md`](https://github.com/ASPDesignLabs/ACK/blob/main/CHANGELOG.md) (the same text is in the app: type `/info` in the TERMINAL). Full diff since beta.7: [`v1.0-beta.7...v1.0-beta.8`](https://github.com/ASPDesignLabs/ACK/compare/v1.0-beta.7...v1.0-beta.8). Full history: [GitHub Releases](https://github.com/ASPDesignLabs/ACK/releases).*
