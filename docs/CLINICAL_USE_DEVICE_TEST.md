# Clinical use (Section 5): checking it on a real phone

This list grows with each task in `docs/CLINICAL_USE_PLAN.md`. Today it holds two parts: **A. The limits statement (C4)** and **B. Saving the message log to a file (C2)**.

The limits statement and the message-log save were built and tested **without an Android SDK or a phone**. What is tested is the plain-Kotlin part: the words in all six
languages, that the three sentences match the website, where the banner may and may not appear, and what the saved file holds and how it is escaped (`tools/kotlin_check/run_unit_tests.sh`
passes). The Android files were type-checked and syntax-checked (`run_typecheck.sh`, `run_syntax_check.sh`). **What was never run is the Android
part**: the build, how the banner, the section and the save button look and behave, the file picker, and what a real phone does at a large font. This list is for you to work through
once. Each line is *do this → expect that*. If something does not match, say which line and what you saw.

Use a debug build with sample data. Make a backup first anyway (PROTOCOL → DATA PORT → EXPORT .JSON). Nothing here is timed; stop whenever you like.

## A. The limits statement (ABOUT ACK and the one-time banner)

- [ ] Build `:app` in Android Studio and run `./gradlew :app:testDebugUnitTest`. → Both succeed. If the build fails, copy the first red error: the Kotlin
  for `ui/LimitsNoticeBanner.kt`, `settings/AboutSection.kt` and the two edits in `MainActivity.kt` and `SettingsView.kt` was never compiled against the
  real Android libraries.
- [ ] `git diff` the manifests. → No permission was added.
- [ ] Start from a state where the banner has not been dismissed (a new install, or PROTOCOL → DATA PORT → DELETE DATA → SETTINGS). Open ACK. → It opens
  on the TERMINAL. A bordered banner sits above the header with three sentences (NOT A SUBSTITUTE FOR PROFESSIONAL AAC EVALUATION OR SPEECH-LANGUAGE
  THERAPY. / BUILT BY ONE PERSON AS A PERSONAL TOOL, SHARED AS-IS. / KEEP ANOTHER WAY TO COMMUNICATE AVAILABLE AT ALL TIMES.), a grey line saying where to
  read it again, and a **GOT IT** button.
- [ ] Look at the grey line. → It names the SETTINGS button the way the header does (PROTOCOL; SETTINGS once PLAIN WORDS is on) and says ABOUT ACK.
- [ ] Set the phone's font size and display size to the largest. → All the banner's text can be read and GOT IT can be reached. **Write down if the banner
  leaves too little room for the Terminal below it**; that is a layout question this plan has not answered.
- [ ] Open a deck (Matrix), then Quick Actions, then Emergency, then TYPE, AUDIO and TARGETS. → **No banner on any of them.** Open SETTINGS again. → It is there.
- [ ] With the banner showing, send a message from the Terminal prompt and from a deck button. → It speaks and shows as usual. The banner changes nothing about it.
- [ ] Tap **GOT IT**. → The banner goes. Nothing else changes (no toast, no screen change, no new Terminal line). Close ACK completely and reopen it. → The
  banner stays gone.
- [ ] PROTOCOL → scroll to the very end. → **ABOUT ACK** with the same three sentences and no buttons or switches.
- [ ] Turn PLAIN WORDS on and off. → Nothing in ABOUT ACK changes (it has no labels). The banner's grey line, if you bring the banner back, follows the button name.
- [ ] PROTOCOL → DATA PORT → DELETE DATA → SETTINGS (confirm it). → After ACK restarts, the banner shows once more, and GOT IT hides it again.
- [ ] Choose Spanish, then Arabic, in the LANGUAGE control (and bring the banner back as above). → The three sentences and GOT IT are in that language, in
  capitals for Spanish. In Arabic the layout is mirrored and nothing is clipped. **These are drafts no native speaker has read.** Say what reads wrongly.
- [ ] Lock the phone and play a message with the watch or a widget. → Nothing about the lock-screen or watch behaviour is different.

### Optional: look at the stored note (debug build only; these adb lines were written from the code and have not been run)

- [ ] `adb shell run-as com.example.besu cat shared_prefs/ack_assist_prefs.xml` before tapping GOT IT. → No `limits_notice_seen` line.
- [ ] The same after tapping GOT IT. → `<boolean name="limits_notice_seen" value="true" />`.
- [ ] `adb shell run-as com.example.besu cat shared_prefs/ack_assist_prefs.xml` on a freshly installed build. → The note is not there (nothing seeds it).

## B. SAVE MESSAGE LOG TO A FILE

Setup: send a handful of messages first, so there is something to save. Use a debug build with sample data only (a saved log holds whatever was said).

- [ ] Send: one message from a Matrix gesture or button, one from a Quick Actions button, one typed at the Terminal prompt, one typed with `/q ` first (quiet),
  one from an Emergency tile, one with a line break in it (the Statement Composer or Manual Override), one with an emoji, one in Arabic or another script, and one
  that contains a made-up name and address. → All speak/show as usual and appear in the Terminal log.
- [ ] PROTOCOL → scroll to the Terminal settings (the log's days slider). → Under the slider: a grey line saying it saves the messages in the log (**HISTORY**
  once PLAIN WORDS is on, TERMINAL LOG otherwise) to a file you choose, and a **SAVE MESSAGE LOG TO A FILE** button. Both are easy to read at the largest font.
- [ ] Tap it. → A warning opens: **MESSAGES IN THE LOG NOW: n**, where n is the number of messages you sent (not the number of log lines: system and command lines
  are not counted); what the file will contain; that names, addresses or numbers you said are in it; what is **not** in it; that it is **not encrypted and has no
  password**; that a screenshot or photo of the log is a copy too; where to save. Nothing else has happened yet. Press **CANCEL**. → The warning closes, **no file picker opened**,
  no toast, no new Terminal line.
- [ ] Tap the button, then **CHOOSE WHERE TO SAVE**. → The system picker opens with a suggested name like `ack_messages_2026-10-06_140302.txt`. Save it to the phone's own storage. →
  A toast says **MESSAGE LOG SAVED** and the Terminal gets a line saying so.
- [ ] Open the saved file in a text editor (on the phone, then on a PC after copying it by cable). → Header lines start with `# `: a title, when it was saved, **MESSAGES: n**
  with the first and last times, that the file is not encrypted, what `\n`, `\t` and `\\` mean, and the four column names. Then one line per message, **oldest first**.
- [ ] Look at the message lines. → Four columns separated by tabs (date and time with an offset such as `+02:00` that matches this phone's time zone, type OUT or EMERGENCY, where it was
  sent from such as `MTX/...`, `QUICK_ACTION`, `TERMINAL`, `TERMINAL [Q]`, `EMERGENCY`, and the message). The message with a line break is **one** line with `\n` in it. The emoji and the Arabic
  text are intact. The Emergency one is typed EMERGENCY. **No system, command or path-trace lines.** The count in the header equals the count the warning showed.
- [ ] With the phone set to Arabic (and then Hindi), save again. → The warning and the header are in that language, and the dates, times and counts in the file are still **Latin digits**.
- [ ] Clear the log (PROTOCOL → DATA PORT → DELETE DATA → TERMINAL LOG, or `/cls CONFIRM`), then open the warning again. → It says **THE LOG HAS NO MESSAGES TO SAVE RIGHT NOW** and has **no**
  CHOOSE WHERE TO SAVE button.
- [ ] Try saving to a place that refuses writes (a read-only location, or a storage provider you have switched off). → A toast and a Terminal line say the save failed and that
  **NOTHING WAS SAVED**, and no half-made file is left behind.
- [ ] Cancel the system picker itself (back out of it). → Nothing happens: no toast, no file.
- [ ] Look at the Terminal log and the retention slider after all of this. → Unchanged: saving never edits, prunes or clears the log.
- [ ] Optional, if you have messages older than the window: shorten the log's days so some are older than it, then save. → Messages older than the window are not in the file.
- [ ] Optional: let the log fill to its limit (400 entries) and save. → It saves, in order, with no pause you notice.
- [ ] DELETE DATA → TERMINAL LOG. → It clears the log; **the saved file is still where you put it** (ACK never tracks it). Delete it yourself when you no longer need it.

### Optional: look at what ACK logs (debug build only; written from the code, not run)

- [ ] `adb logcat -s ACK_LOG_EXPORT` while saving. → One line like `message log written: 6 messages, 612 bytes`. **Never any message text.**
