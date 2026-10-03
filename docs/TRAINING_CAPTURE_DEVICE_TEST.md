# RECORD TRAINING DATA: checking it on a real phone

Everything that decides what is recorded, cut, kept and written was tested without a phone (140 unit tests, and the packages it writes
are opened by Freeform Studio's real reader). **What was not run anywhere is the Android part**: the build itself, the microphone, the
screens, the file picker. This list is for you to work through once, in order, on the phone. Each line is *do this → expect that*. If
something does not match, the note at the end says what to send back.

Take your time; none of it is timed. Stop any time; nothing here can damage anything that is already on the phone, and the only
deleting steps say so.

## A. Build and first look

- [ ] Build and install the app from the branch `claude/training-capture` in Android Studio. → It **builds**. If it does not, copy the
  first red error (it is most likely a small typo or a missing import in `voicecapture/`; the Kotlin was type-checked, but not against
  the real Android libraries).
- [ ] Open **Audio Architect**. → The CUSTOM VOICE section has a new button, **RECORD TRAINING DATA**, and the page scrolls if your
  screen is small.
- [ ] Tap it. → A screen titled RECORD TRAINING DATA with a one-line promise that nothing is sent anywhere, the free space on the phone,
  a first-use tip about HELP, **SCRIPTS** (none yet), **FREE SPEECH**, **RECORDED SESSIONS** (none yet).
- [ ] Dismiss the tip, close and reopen the screen. → The tip does not come back.
- [ ] Open **HELP**. → Under BASICS // PERSONALIZATION there is **RECORD TRAINING DATA**. Run it once to the end. → Each step highlights
  the control it talks about when that control is on screen, and the two tapping steps wait for the tap.

## B. Scripts (editing asks before it changes anything)

- [ ] **+ NEW SCRIPT**, give it a title, paste about 10 sentences, one paragraph with a number in it ("in 2026") and one with a `%`.
  → The card count and minutes appear a moment after you stop typing; a red line warns about the cards with digits or symbols.
- [ ] **SAVE** (a new script saves straight away). → Back at the list: the script shows "N CARDS, 0 RECORDED".
- [ ] **EDIT** it, change a word, **SAVE**. → A box asks "SAVE THESE CHANGES?" with KEEP EDITING as the first choice.
- [ ] **EDIT**, change a word, press **[BACK]**. → "LEAVE WITHOUT SAVING?"; choosing KEEP EDITING returns you to your text.
- [ ] **EDIT → DELETE THIS SCRIPT**. → Two separate confirmations; choose KEEP IT at the second, and the script is still there.
- [ ] Paste a very long text (50,000+ characters). → Typing stays responsive; the card count appears after a short wait.

## C. The quiet check

Open a script and tap **RECORD**. Note the setup screen: name, wait slider, the "BEFORE YOU START" advice.

- [ ] Tap **START QUIET CHECK** the first time. → The phone asks to allow the microphone. Allow it; the check starts, "STAY QUIET...", a bar
  fills over two seconds.
- [ ] Stay quiet. → "ROOM LEVEL … dB: GOOD." with CHECK AGAIN and START RECORDING.
- [ ] Check again while **covering the microphone completely** with your thumb. → Probably "NOTHING WAS HEARD. IS
  THE MICROPHONE COVERED OR MUTED?" and START RECORDING is dimmed. (Some phones add a tiny noise even when covered; then you will see GOOD.
  Tell me the dB shown.)
- [ ] Check again while **clapping once**. → "A SOUND INTERRUPTED THE QUIET CHECK" and START RECORDING is dimmed.
- [ ] Check again with **a TV or music on** (or in a noisy place). → "LOUD" with a warning, but START RECORDING still works.

## D. Hands-free recording (the main thing)

Prop the phone up somewhere it will stay. Start recording.

- [ ] → One card shows in large text, "LISTENING. READ THE CARD WHEN YOU ARE READY."; a level bar moves with the room.
- [ ] Read the first card aloud, normally, then stay quiet. → While you speak: "HEARING YOU..."; about a second after you stop, the next card
  appears by itself and "1 KEPT" shows.
- [ ] Read four more cards, **starting the next one straight away** each time (do not wait). → Each is kept; none loses its first words
  (listen in section G).
- [ ] Mid-card, **pause for a breath** (under a second) and carry on. → Still one clip.
- [ ] **Pause for 2 seconds** in the middle of a card. → The phone waits 1.2 seconds of quiet (the default) and decides the card is finished:
  what you read before the pause is kept as that card, and what you say after it is heard as the start of the *next* card. This is the
  end-of-card wait. If it happens to you a lot, raise the slider on the setup screen next time (up to 2.5 seconds).
- [ ] Read a card, then tap **REDO LAST** straight away. → The previous card is shown again as "TRY 2"; the old attempt is not
  in a saved file (see G).
- [ ] Tap **PAUSE**, wait, tap **RESUME**, read. → While paused it shows PAUSED and nothing is recorded; after RESUME it listens again.
- [ ] Leave it silent for 25 seconds. → It pauses itself ("NOTHING HEARD FOR 20 SECONDS"); RESUME carries on.
- [ ] After a clip is kept, tap **NOISE** under "MARK IT IF NEEDED", tap it again. → It lights, then clears.
- [ ] Tap **END SESSION**. → A box asks first; choose KEEP RECORDING, then try again and choose END SESSION → "SESSION ENDED", with the number kept.

## E. Things that must NOT happen

- [ ] During recording, **listen for sound or feel for vibration** when a clip is kept or a button is tapped. → None. (The app's other buttons
  vibrate; these must not.)
- [ ] Try to **rotate** the phone while recording. → The screen does not rotate and the recording is not interrupted.
- [ ] Let the screen sit for a minute. → It does not dim or lock while the recording screen is up.
- [ ] While listening, press **Home** (or switch to another app) and come back. → It is **PAUSED**. Tap RESUME.
- [ ] Receive a phone call or an alarm during a card if you can. → It pauses or the card is simply not kept; nothing crashes.

## F. The app closing in the middle (recovery)

- [ ] Start a session, read two cards, then say half a sentence and **swipe the app away** from recent apps in the middle of the third card.
- [ ] Open the app again, go to RECORD TRAINING DATA. → A notice: "THE APP CLOSED BEFORE 1 SESSION(S) WERE ENDED. 1 UNFINISHED RECORDING(S) WERE
  REPAIRED…". The session in the list is outlined and says "1 RECORDING(S) WAITING FOR YOU TO LISTEN AND DECIDE".

## G. Looking inside a session

Open the session (tap it).

- [ ] Tap **PLAY** on a kept clip. → You hear it through the app's normal audio output. Check: **is the first word whole?** Is the end clean? Is
  there any thump, click or buzz anywhere (especially at the start of a clip after you tapped something)?
- [ ] The repaired clip says "REPAIRED: LISTEN AND DECIDE". **PLAY** it, then **KEEP** or **SET ASIDE**. → It changes to KEPT or SET ASIDE.
- [ ] A set-aside or redone clip has **DELETE** (asks once). Try it on one. → It is gone from the list.
- [ ] A kept clip has **no** delete button, only marks (NOISE, UNCLEAR, LAUGH, COUGH, STUMBLE). Tap a couple. → They light and stay lit if you close and reopen.

## H. Free speech

- [ ] **RECORD FREE SPEECH**, name it, quiet check, start, talk for two minutes with some pauses. → A big timer counts, the bar moves, "RECORDING. HEARING YOU…".
- [ ] **PAUSE**, wait, **RESUME**. → The timer stops and resumes; the gap is not in the recording.
- [ ] **STOP AND KEEP**. → "FINISHING THE RECORDING…" for a moment, then "SESSION ENDED" with the length and "THE PHONE SUGGESTS N PIECE(S)".

## I. Saving to a file

- [ ] On the main screen, **SAVE ALL TO A FILE**. → The system "save as" screen, with a name like `ack-training-20261002-183000.zip`. **Cancel it.**
  → "SAVE CANCELLED. NOTHING WAS WRITTEN."
- [ ] Do it again and save to Downloads (or a USB drive). → A progress box ("SAVING FILE 1 OF 1… THEN CHECKING IT"), then "SAVED AND CHECKED.
  MOVE THE FILE TO YOUR COMPUTER."
- [ ] Open a session and use its own **SAVE TO A FILE**. → Same, for just that session.
- [ ] There is **no** share sheet anywhere, and nothing offers to send the file to another app. → Right.
- [ ] Delete a session you do not need. → Two confirmations; the second says LAST CHANCE; KEEP IT cancels.

## J. On the computer

Move the `.zip` over.

- [ ] `python -m freeform_studio.ack_import <the file>.zip --dry-run` → It lists the sessions, minutes, and "enough room"; nothing is written.
- [ ] Without `--dry-run`, or with the Review page's **Add recordings from ACK**. → One recording per session appears; a script session's cards are
  its reference text.
- [ ] Run it again. → Every session is "already" there; nothing doubles.
- [ ] Review one piece from a script session. → The **From ACK** panel shows the card's words, the card number and attempt, and any mark you set on
  the phone. Pieces you marked NOISE/UNCLEAR/LAUGH/COUGH carry that tag.

## K. Backup

- [ ] Settings → **EXPORT .JSON**, then (after changing one script) **FULL RESTORE FROM JSON** with that file. → Your scripts are all still there; the
  one you changed is back to the exported text; nothing was removed. Check that RECORD TRAINING DATA still opens afterwards.

## What to send back

Whatever does not match, with: the phone model and Android version, and the lines from logcat filtered by `ACK_TRAIN` (and `ACK_IMPORT` for
backup problems). Those lines only carry counts, sample rates, the microphone source chosen and the reason for a pause or a failed save. They never
carry audio or the text of a script. Particularly useful:

- the `microphone open:` line (the sample rate and source your phone gave us; some phones have no unprocessed source or no 48 kHz),
- anything that sounds wrong in section G, with which section it was in,
- anything that looks cramped on your screen (the five mark buttons are the tightest part).

## What was not run anywhere, and so is most likely to need a fix

The Android build; `AudioRecord` on a real phone (rate and source fallbacks); keeping the screen awake and locking its orientation; the file
picker and the read-back check against a real storage provider; playback of a clip through the app's audio output; the exact look of the screens
(text size, button sizes, the mark buttons on a narrow phone); how long the screens take to open with hundreds of sessions.
