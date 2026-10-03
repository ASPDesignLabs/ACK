# Safety and defaults: checking it on a real phone (and a watch)

Seven safety problems were fixed in the code, plus a few things decided along the way. The decisions that can be tested without a phone
are tested (195 unit tests in `tools/kotlin_check`, run with `./run_unit_tests.sh`), and the policy tests for "no network" and the licence
header pass. **What was not run anywhere is the Android part**: the build itself, every screen, the sound, the permission page and the
watch. This list is for you to work through once, in order, on a phone and, for section G, a paired watch. Each line is *do this → expect
that*. If something does not match, the note at the end says what to send back.

Use a **debug build**. Take your time; none of it is timed. Stop any time. Most steps only look; the ones that change a setting say so,
and **a backup first is a good idea** (PROTOCOL → DATA PORT → EXPORT .JSON).

## A. Build

- [ ] Build **both** modules in Android Studio, `:app` and `:wear`, and run `./gradlew :app:testDebugUnitTest`. → Both **build** and the
  unit tests pass. If a build fails, copy the first red error. (Most likely a small typo or a wrong import: the Kotlin for the screens was
  never compiled against the real Android libraries, and the Compose type-check does not cover `settings/`, `decks/` or `ui/`.)
- [ ] `git diff` the two manifests against the branch point. → The phone's changes are only `android:name=".AckApplication"` on
  `<application>`; the watch's is one new `/audio/relay_cancel` path line. **No permission was added.**

## B. Fresh install, and an update that must change nothing

- [ ] **Before** installing the new build over an older one, save the stored settings (debug build):
  `adb shell run-as com.example.besu sh -c 'cd shared_prefs && md5sum *.xml' > before.txt`
- [ ] Update **in place** (`adb install -r`), open ACK once, then run the same command into `after.txt`. → `diff before.txt after.txt` shows
  **no change** to any existing file. One new file, `ack_install_state.xml`, is expected and correct (it says `fresh=false`).
- [ ] In AUDIO ARCHITECT on that updated phone. → The voice is **still what it was** (CYBER if you never chose one), and a message of
  more than 5 words is **still cut** to ALERT: plus 3 words. A banner at the top offers the newer defaults (see section E).
- [ ] **Uninstall**, then install fresh and open the app. → In AUDIO ARCHITECT, **ORGANIC is selected**; in the visual editor a preset
  called **FULL TEXT** is active with SHOW FULL MESSAGE **ON**; no banner offers anything.
- [ ] If you have a **phone-to-phone transfer** of an older install to try. → The new phone behaves like an existing install (old settings
  kept, banner offered), not like a fresh one.

## C. Long messages fit (S1 and S3)

On the fresh install, send each of these from a deck tap, the TYPE tab's SPEAK, and the TERMINAL.

- [ ] 1 word, 12 words, 40 words, 120 words. → Each is shown **in full**, capitalised, with no `ALERT:`; the text is smaller for the longer
  ones and nothing is cut off. A 120-word message may scroll, with **SCROLL FOR MORE** under it.
- [ ] Repeat at preset sizes **40, 120 and 250** (the slider now reads LARGEST SIZE), on a small phone (about 360 × 640 dp) and a large one.
  → Nothing clipped. At 250 a short message is big; a long one is shrunk to fit.
- [ ] Repeat with **PROTOCOL → forced device rotation** on, and off (the default). → Same result in both. (Forced rotation is the one that
  needed the content height changed.)
- [ ] **Tap** to clear a normal message; **hold** to clear an Emergency message; tap **REPLAY**; send a **sticky** (`/s`) message. → All
  behave exactly as before, including on a message long enough to scroll (then a tap or a hold on the text itself clears it).
- [ ] An **emoji** prompt and a **GIF** prompt. → They look exactly as before.
- [ ] In the visual editor, switch SHOW FULL MESSAGE **OFF**. → A red line says THE SCREEN MAY SHOW LESS THAN WAS SPOKEN, and a long
  message is cut again. Switch it back ON.

## D. Display permission, and Silent Mode with nothing to show (S4)

Revoke the permission: `adb shell appops set com.example.besu SYSTEM_ALERT_WINDOW deny`

- [ ] Open the app. → A red banner, **DISPLAY PERMISSION IS OFF. MESSAGES ARE SPOKEN BUT NOT SHOWN ON SCREEN.**, sits above the header on
  every main screen (it is not dismissible).
- [ ] Tap **ALLOW**. → Android's "Display over other apps" page for ACK opens. (On a phone without that page, the app's settings page.)
- [ ] Allow it and press Back. → The banner **disappears without restarting the app**, and the next message appears full screen.
- [ ] Revoke it again, turn **SILENT MODE** on in SETTINGS. → A red line under the switch says a message would be neither spoken nor shown.
  Send a message. → The TERMINAL log shows NOTHING WAS SHOWN OR SPOKEN and a toast appears, **once a minute at most**. Silent Mode is still
  on (it was not overridden).
- [ ] Turn Silent Mode off, send a message with the permission still off. → Spoken, and the log says MESSAGE SPOKEN BUT NOT SHOWN.
- [ ] Allow the permission again (`... SYSTEM_ALERT_WINDOW allow`). → Nothing new appears anywhere.

## E. Voice, and the one-time offer to existing installs (S2, Part C, Emergency)

- [ ] **Fresh install**: speak a normal message, then an Emergency one. → Both **without effects**.
- [ ] Select **CYBER**, speak a normal message. → It sounds as it always did. Speak an **Emergency** message. → It is **unprocessed**
  (normal pitch and speed, no robotic effect) even though CYBER is selected. The alert tone and EMERGENCY VOLUME BOOST still work.
- [ ] Make a custom voice, select it, then **delete** it. → ORGANIC is selected afterwards.
- [ ] **Existing install** (section B's updated phone), AUDIO ARCHITECT. → The banner shows once, naming only what applies, with
  **[REVIEW]** and **[NOT NOW]**.
- [ ] Tap **REVIEW**. → A list of exactly what would change, one switch per change, **all off**, BACK UP FIRST, CANCEL, APPLY (dimmed until
  something is on). Tap **BACK UP FIRST**, save the file. → "BACKUP SAVED"; open the file and check it is a normal ACK backup.
- [ ] Switch **one** change on and tap **APPLY**. → Only that change happens (the voice becomes ORGANIC, or a new **FULL TEXT** preset appears
  and becomes active while your own preset is still in the list); "SETTINGS UPDATED"; the banner is gone for good.
- [ ] On another existing install, tap **NOT NOW**. → The banner goes and does not come back after leaving and reopening AUDIO ARCHITECT.
  Nothing launched HELP or took you to another screen.

## F. Emergency confirmation (S6)

- [ ] In an Emergency deck, **CONFIGURE OVERRIDES**. → A **TAP PROTECTION** section with **CONFIRM BEFORE SENDING**, off.
- [ ] Tap a configured tile with it **off**. → It sends at once, as before.
- [ ] Switch it **on**, save. → The overrides line on the deck shows CONFIRM.
- [ ] Tap a tile. → A dialog shows the label and the **full phrase** in large type, with big **CANCEL** and **SEND** buttons.
- [ ] **CANCEL**, then tap outside the dialog, then Back. → Each speaks and shows **nothing**.
- [ ] **SEND**. → Behaves exactly as an unconfirmed tap did: the same speaker, boost, tone and clearing.
- [ ] Tap a **blank** tile. → No dialog.
- [ ] **EXPORT .JSON**, then **FULL RESTORE** it. → The toggle is still on. Restore an **older** backup file. → It restores with the toggle off.

## G. The watch (S5): needs a paired watch with the new `:wear` app installed

Set PROTOCOL → OUTPUT DEVICE to **ACK WATCH**.

- [ ] Send a normal message. → It plays on the **watch only**, and the log shows WATCH CONFIRMED PLAYING and a time in milliseconds.
- [ ] **Force-stop the watch app** just as you send. → After the wait (a few seconds) the message plays on the **phone**, and the log says
  WATCH DID NOT CONFIRM: PLAYING ON PHONE.
- [ ] Take the watch **out of range**. → The message plays on the phone **at once**.
- [ ] Do a miss three times in a row. → The third also logs NO CONFIRMATION FROM WATCH (IS THE WATCH APP UPDATED?).
- [ ] With an **older watch app** (without this change). → Every message waits out the timeout, then plays on the phone, with that hint.
- [ ] Turn **FORCE SPEAKER** on. → It still wins: the message plays on the phone.
- [ ] Send an **Emergency** message (and one with an alert tone). → Both play on the **phone**, with no wait, even with ACK WATCH selected.
- [ ] Note the confirmation time shown for a normal message and a long (30 s) one. → The wait before falling back is 3 s plus 0.4 s per chunk
  of audio. If it is too short or too long on your watch, those two numbers are the ones to change (`core/RelayAckTracker.kt`).

## H. Things that were removed or changed on purpose

- [ ] AUDIO ARCHITECT. → There is **no GLOBAL CADENCE slider** (it was retired); Master Gain is still there and the MASTER GAIN HELP step
  still completes when you move it.
- [ ] Speak a message containing `Tom & Jerry <3` with the system voice and with a custom voice. → It speaks normally, no tags heard.
- [ ] **EXPORT .JSON**, then **FULL RESTORE** on a fresh install and on an existing one. → The voice, the FULL TEXT preset and the Emergency
  toggle are kept; an older backup file restores cleanly.

## If something does not match

Send the step number and what you saw. The log lines to copy from `adb logcat` are tagged `ACK_INSTALL` (install and seeding),
`ACK_OVERLAY` (the permission page), `ACK_WATCH_RELAY` and `ACK_WEAR` (the watch), `ACK_BACKUP` (BACK UP FIRST) and `ACK_IMPORT`
(restore). They carry reasons and numbers only, never what a message says. A crash: the first red `FATAL EXCEPTION` block.
