# Clinical use (Section 5): checking it on a real phone

This list grows with each task in `docs/CLINICAL_USE_PLAN.md`. Today it holds three parts: **A. The limits statement (C4)**, **B. Saving the message log to a file (C2)** and **C. The usage summary (C1)**.

The limits statement, the message-log save and the usage summary were built and tested **without an Android SDK or a phone**. What is tested is the plain-Kotlin part: the words in all six
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

## C. USAGE SUMMARY (counts of when messages are sent, never the words)

Setup: a debug build with sample data. It is **off** until you turn it on, so start with it off. Make a backup first anyway (PROTOCOL → DATA PORT → EXPORT .JSON).
The summary is **not** in that backup (it describes this phone), so to keep one you would save it to a file (below).

**Counting must never slow or change speech.** Watch for that throughout: if a message ever starts later, or does not speak, write down which line you were on.

- [ ] PROTOCOL → scroll below SAVE MESSAGE LOG TO A FILE and above DATA PORT. → A **USAGE SUMMARY** section: a grey line saying it counts how often and when messages are sent, kept
  on this phone for 90 days, never the words, off until you turn it on; a switch button reading **USAGE SUMMARY: OFF**; **NOTHING HAS BEEN COUNTED YET.** Everything is easy to read at the
  largest font, and the buttons are comfortable to tap.
- [ ] Open the Terminal. → **No** usage line. Send a message from a Matrix gesture, then look at SETTINGS again. → Still nothing counted (it is off).
- [ ] Tap the switch. → A dialog **TURN ON USAGE SUMMARY?** says what it will count (messages per hour of each day, by where they came from and by kind), that it never keeps the words of a
  message, a name, a place or audio, that a message sent with `/n` is not counted, that the counts stay on this phone for 90 days and are in no backup, and that the Terminal will show a line
  while it is on. **CANCEL is the prominent button; TURN ON is plainer.** Press **CANCEL**. → The dialog closes, the switch still says OFF, and the Terminal still has no line. Try the system
  back gesture and a tap outside the dialog too. → Same: nothing turned on.
- [ ] Tap the switch again and press **TURN ON**. → The switch now says **USAGE SUMMARY: ON**. Open the Terminal. → **One quiet grey line** at the top: *USAGE SUMMARY IS ON: ACK COUNTS HOW OFTEN AND
  WHEN MESSAGES ARE SENT, NEVER THE WORDS.* It has no sound, no animation and nothing to tap.
- [ ] Visit a Matrix deck, a Quick Actions deck, the Emergency screen and the TYPE tab. → **The line is not on any of them**, and no button on them has moved.
- [ ] Send these, in this order, noting each: a Matrix gesture that still has its **starter wording** (for example the YES one); a Quick Actions starter button; a line typed at the
  Terminal prompt; the same with `/q ` first (quiet); one with `/n ` first (do not save); an Emergency tile; a saved phrase played from Manual Override (`/m`); something spoken from the
  Statement Composer; a replay of an earlier message from the Terminal log; a message with words that are not a starter (for example "Hello there"). If you have the watch, send one from it.
  → Each speaks and shows as it always did, and **starts as quickly as before**.
- [ ] Start a HELP walkthrough and let it speak a step or two. → It speaks as before.
- [ ] Back in SETTINGS → USAGE SUMMARY. → **MESSAGES COUNTED: n**, where n is the number you sent **minus** the `/n` one and the HELP narration (so the `/q` one **is** counted: it was sent,
  even if not spoken). Under **BY KIND**: YES (and the other starter kinds you used) and OTHER (the typed line and "Hello there"). Under **BY WHERE IT CAME FROM**: MATRIX DECK, QUICK ACTIONS DECK,
  TYPED AT THE TERMINAL, EMERGENCY, MANUAL OVERRIDE, STATEMENT COMPOSER, REPLAYED (and WATCH if you used it). Under **THE LAST 14 DAYS**: today's date with n. Under **BY HOUR OF THE DAY**: only this
  hour's line, with n. **No deck name, button name or word of any message appears anywhere.**
- [ ] Edit a starter phrase's wording slightly (add a word), send it, and look again. → It is counted under OTHER, not its starter kind. Put the wording back.
- [ ] Turn Silent Mode on (or choose silent output) and send a message. → It is shown and not spoken, as before, and the count goes up by one.
- [ ] Tap **SAVE USAGE SUMMARY TO A FILE**. → A warning opens: **MESSAGES THE FILE WOULD COUNT: n**; that the file holds counts by hour of each day, by where they came from and by kind;
  **NOT IN THE FILE: ANY WORDS, NAMES, PLACES OR AUDIO**; that it **still shows when someone communicates, which is a daily pattern, so keep it like a diary**; that it is **not encrypted and has no
  password**; that a screenshot or photo of the screen is a copy too; where to save. Nothing else has happened. Press **CANCEL**. → It closes, **no file picker opened**, no toast.
- [ ] Tap it again, then **CHOOSE WHERE TO SAVE**. → The system picker opens with a suggested name like `ack_usage_2026-10-06_140302.txt`. Save it to the phone's own storage. → A toast says
  **USAGE SUMMARY SAVED** and the Terminal gets a line saying so.
- [ ] Open the file on the phone, then on a PC after copying it by cable. → Header lines start with `# ` (a title, when it was saved, days, messages, first and last date, that it is not encrypted,
  and the column names). Then one line per row, **oldest first**, five columns separated by tabs: DATE, HOUR, CHANNEL, KIND, COUNT. **Search the file for a word you typed: it must not be there.** The
  counts add up to the number the warning showed.
- [ ] With the phone set to Arabic (and then Hindi), open the section and save again. → The words are in that language; the dates, hours and counts, in the screen and in the file, are still **Latin digits**.
  (Look at the mirrored Arabic layout of the section and the dialogs.)
- [ ] Try saving to a place that refuses writes (a read-only location, or a storage provider you have switched off). → A toast and a Terminal line say the save failed and that **NOTHING WAS SAVED**,
  and no half-made file is left behind. Back out of the system picker itself. → Nothing happens: no toast, no file.
- [ ] Tap the switch to turn it **OFF**. → It says OFF, the Terminal line goes away, and the section still shows what was counted. Send a message. → The numbers do not change. **Nothing was deleted by
  turning it off.**
- [ ] Turn it **ON** again. → The dialog **asks again** (it always asks first). CANCEL it, and check the switch still says OFF.
- [ ] Tap **FORGET USAGE SUMMARY**. → A first question says it deletes every count, that it cannot be undone and is in no backup, and **names SAVE USAGE SUMMARY TO A FILE as the thing to use first**.
  CANCEL is prominent. Press **CANCEL**. → Nothing is deleted. Open it again, press **CONTINUE**. → A second question says how many messages will be deleted, and that a file you saved earlier is **not**
  deleted. Press **CANCEL**. → Nothing is deleted. Open it a third time, go through both, and press **DELETE PERMANENTLY**. → A toast says **USAGE SUMMARY FORGOTTEN**, and the section says **NOTHING HAS
  BEEN COUNTED YET.** The file you saved is still where you put it.
- [ ] PROTOCOL → DATA PORT → DELETE DATA. → The list has **thirteen** areas, including **USAGE SUMMARY**, which says it holds counts only and is **not backed up anywhere**. Open it and press CANCEL at each
  step. → Nothing is deleted. (Delete it only if you are finished.)
- [ ] With the switch ON and some counts kept, EXPORT .JSON, then FULL RESTORE FROM JSON with that file. → Counts and the switch are exactly as they were: **a restore neither adds counts nor turns the
  switch on or off.**
- [ ] DELETE DATA → SETTINGS (and only that). → The switch is **OFF** afterwards. The counts are still there (they are their own area).
- [ ] At the largest font, on the smallest phone you have, look at the section, both dialogs and the Terminal line. → Nothing is cut off or overlaps, and the line does not push the Terminal's buttons
  off the screen.
- [ ] Optional: leave it on for a day of real use. → Speech never feels slower; the day's total is plausible; the hours match when you actually used ACK.
- [ ] Optional: change the phone's time zone and send a message. → It is counted in the new local hour (a changed zone shifts the hour buckets: that is a stated limit).

### Optional: look at what ACK logs (debug build only; written from the code, not run)

- [ ] `adb logcat -s ACK_USAGE ACK_USAGE_EXPORT` while using it. → Only fixed sentences such as `a count could not be saved` and `usage summary written: 14 rows, 560 bytes`. **Never any message text.**
- [ ] `adb shell run-as <the debug app id> ls shared_prefs` before turning it on. → **No** `ack_usage_tally.xml` yet. After a message is counted it exists, and holds only names like
  `2026-10-06|14|MATRIX|YES` with a number each (open it to check: no words).
