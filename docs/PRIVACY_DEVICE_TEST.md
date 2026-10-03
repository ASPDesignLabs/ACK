# Privacy and data protection: checking it on a real phone

The export warning, the safe export, the delete screens, the safety-copy list and the backup reminder were built and tested **without an
Android SDK or a phone**. What is tested is the plain-Kotlin part: the wording, the rules, the fingerprint, the storage list and its
drift guards (run `tools/kotlin_check/run_unit_tests.sh`; it passes). **What was never run is the Android part**: the build, every
screen and dialog, the file picker, the deleting itself, the geofence call and the watch. This list is for you to work through once, in
order. Each line is *do this → expect that*. If something does not match, say which line and what you saw.

**Use a debug build with sample data only.** Never try a delete on a phone that holds real data, and make a backup first anyway
(PROTOCOL → DATA PORT → EXPORT .JSON). Nothing here is timed; stop whenever you like.

The adb lines assume the app id `com.example.besu` and a **debug** build (`run-as` only works on a debuggable app). They were written
from reading the code and the SharedPreferences file format. **They have not been run**: if one fails, send back the message.

## A. Build

- [ ] Build **both** modules in Android Studio (`:app` and `:wear`) and run `./gradlew :app:testDebugUnitTest`. → Both build; the tests
  pass. If a build fails, copy the first red error: the Kotlin for these screens was never compiled against the real Android libraries.
- [ ] `git diff` the two manifests against the branch point. → **No permission was added** to either.

## B. EXPORT .JSON warns, and says when it fails

- [ ] PROTOCOL → DATA PORT → **EXPORT .JSON**. → A dialog lists what the file can contain, says it is **not encrypted and has no
  password**, and says where to save it. Nothing else happens yet. Press **CANCEL**. → No file picker opened.
- [ ] Tap **EXPORT .JSON** again, then **CHOOSE WHERE TO SAVE**, pick this phone's own storage. → The picker opens, the file saves, a toast
  says **BACKUP EXPORTED**. Open the file in a text editor. → Its contents match the categories the warning listed.
- [ ] Try saving to a place that refuses writes (a read-only location, or turn a storage provider off). → A toast and a Terminal line say
  **BACKUP FAILED: ... NOTHING WAS SAVED.** and no half-made file is left behind.
- [ ] Terminal: type `/backup`. → It prints the same facts, then **TYPE /backup CONFIRM TO PROCEED.** Type `/backup confirm`. → The
  picker opens; the result is logged either way.
- [ ] While the HELP walkthrough for DATA PORT is running, tap EXPORT .JSON. → The step still advances.

## C. The backup reminder

The reminder only reminds. It never writes a file. It is checked **once when ACK starts**, and it shows when all of these hold: it is on,
no snooze is running, 7 days have passed since the last export (or since ACK first ran here, if there has never been one), **and**
what a backup would hold has changed since.

To make a last backup look old, stop the app first (it would otherwise write its remembered value back), then edit the notes:

```
# see what is stored
adb shell run-as com.example.besu cat shared_prefs/ack_backup_state.xml

# make the last export look 8 days old
AGO=$(( ($(date +%s) - 8*24*60*60) * 1000 ))
adb shell am force-stop com.example.besu
adb shell "run-as com.example.besu sed -i 's/name=\"last_backup_at\" value=\"[0-9]*\"/name=\"last_backup_at\" value=\"$AGO\"/' shared_prefs/ack_backup_state.xml"

# a phone that has never exported has no last_backup_at: age first_run_at instead
adb shell "run-as com.example.besu sed -i 's/name=\"first_run_at\" value=\"[0-9]*\"/name=\"first_run_at\" value=\"$AGO\"/' shared_prefs/ack_backup_state.xml"

# end a snooze
adb shell "run-as com.example.besu sed -i 's/name=\"snoozed_until\" value=\"[0-9]*\"/name=\"snoozed_until\" value=\"0\"/' shared_prefs/ack_backup_state.xml"
```

To watch the check, run `adb logcat -s ACK_BACKUP`: it logs the first 8 characters of the data fingerprint and whether it changed, never
content.

- [ ] Open ACK once, then close it, so the notes file exists. Export a backup (section B). Make the last export look 8 days old (above),
  **change nothing in ACK**, and reopen it. → **No reminder** (nothing changed since the export).
- [ ] Do things that must **not** count as a change: switch decks, switch profiles, send some messages, type into a variable field. Age the
  export again and reopen. → **Still no reminder.** (logcat shows the same fingerprint prefix as after the export.)
- [ ] Now do things that **must** count: add a phrase, create a deck, change a setting, add a contact, add a recording. After each, age the
  export and reopen. → **A reminder appears each time** (and the fingerprint prefix differs).
- [ ] With a reminder due, on the **Terminal** screen. → A banner above the header: BACKUP DUE ... with **BACK UP NOW** and **NOT NOW**, text
  at least 12 sp, no sound, vibration or animation. Also a small **save (floppy) icon** appears left of HELP, under PROTOCOL.
- [ ] Look at the header before and after the icon appears. → **Nothing in the header moves** when it appears or disappears. (Its space is
  always kept free, so the header may be a few pixels different from before this build, but never changes afterwards.)
- [ ] Switch to a deck screen, the Emergency deck and TYPE. → **No banner** on any of them; only the small icon in the header.
- [ ] Tap the icon. → A dialog with the same message, **BACK UP NOW** and **NOT NOW**, and CLOSE. CLOSE changes nothing.
- [ ] **NOT NOW** (banner or dialog). → The banner and icon disappear. Reopen ACK. → Still hidden. End the snooze (above) and reopen. →
  Back.
- [ ] **BACK UP NOW**. → The EXPORT .JSON warning shows first. Save. → The banner and icon are gone. Reopen ACK. → Still gone.
- [ ] Make a reminder due, then make the export **fail** (a read-only location). → The banner and icon **stay**.
- [ ] PROTOCOL → DATA PORT → **BACKUP REMINDER: ON**. Tap it. → **BACKUP REMINDER: OFF** (in words, readable), and a showing reminder
  disappears. Age the export, change a phrase, reopen. → No reminder. Switch it back on and reopen. → The reminder is back.
- [ ] **FULL RESTORE** a backup, then age things and reopen. → Restoring does **not** count as having made a backup: the last export time is
  unchanged.

## D. Safety copies

ACK writes a private copy into `files/auto_backups` once, before an old 8-slot target list is upgraded. To see the row without upgrading:

```
NOW=$(( $(date +%s) * 1000 ))
adb shell "run-as com.example.besu sh -c 'mkdir -p files/auto_backups && echo {} > files/auto_backups/pre_migration_$NOW.json'"
```

- [ ] PROTOCOL → DATA PORT. → A **SAFETY COPIES** row: *ACK MADE A PRIVATE SAFETY COPY BEFORE A DATA UPGRADE ON <DATE> (<SIZE>). IT HOLDS THE SAME
  DATA AS AN EXPORT AND IS NOT ENCRYPTED.* with a **DELETE** button, text at least 12 sp. With no file in the folder, **no such row**.
- [ ] **DELETE** when you have **not** exported since the copy was made. → The first confirmation says so and offers **EXPORT FIRST**; the
  forward button reads **DELETE ANYWAY**. Choose EXPORT FIRST and save. → Come back to the dialog: it now says an export has been saved
  and the button reads **CONTINUE**.
- [ ] Press **CANCEL** at the second confirmation (*THIS CANNOT BE UNDONE*). → Nothing deleted, both dialogs gone.
- [ ] Go through both confirmations and **DELETE COPY**. → A toast says **SAFETY COPY DELETED**; the row is gone;
  `adb shell run-as com.example.besu ls files/auto_backups` shows the file is gone.

## E. DELETE CUSTOM VOICE (AUDIO ARCHITECT → CUSTOM VOICE)

You need an imported voice (or any pair of `.onnx` and `.onnx.json` that passes the import checks). Make a copy of the voice first.

- [ ] With a voice installed and **MY VOICE** selected, tap **DELETE CUSTOM VOICE** (red). → The first confirmation says what is removed,
  that the only copy may be on this phone, that **MY VOICE** will switch to a normal voice (**ORGANIC**), and offers **EXPORT VOICE BACKUP
  FIRST**. Use it. → It says whether the backup worked.
- [ ] **CONTINUE**, then **CANCEL** on the second. → Nothing changed. Repeat and **DELETE VOICE**. → A toast says **CUSTOM VOICE DELETED**;
  the **MY VOICE** chip is gone; the active voice is **ORGANIC**; no restart.
- [ ] `adb shell run-as com.example.besu ls -R files/custom_voice`. → No `model.onnx`, `model.onnx.json` or `tokens.txt` (the folder may
  exist but is empty).
- [ ] Send a message. → It speaks with the normal voice and the Terminal shows **no** "CUSTOM VOICE SYNTHESIS FAILED -- FALLING BACK" line.
- [ ] A custom profile that had **USE MY VOICE** on. → It is still there, with its name and settings, and the switch is off.

## F. DELETE DATA (PROTOCOL → DATA PORT → DELETE DATA)

**Debug build with sample data only.** Before each delete, and after, compare what is on the phone:

```
adb shell run-as com.example.besu ls -R files shared_prefs cache > before.txt
# ... delete one area ...
adb shell run-as com.example.besu ls -R files shared_prefs cache > after.txt
diff before.txt after.txt
```

- [ ] Open **DELETE DATA**. → Twelve areas, each with what it holds, how much is stored, and a red **DELETE**; **DELETE EVERYTHING** at the
  bottom. All text at least 12 sp. Nothing was deleted by opening it.
- [ ] Tap one area's **DELETE**. → A first confirmation: what goes, how much, how to save it first, the line about files saved elsewhere, and
  (for areas that restart) that ACK will restart. Areas EXPORT .JSON covers offer **BACK UP FIRST** (it opens the export warning). Areas it
  does not cover (**TRAINING DATA**, **TRAINED VOICE**, **GIF LIBRARY**) **name the backup that does** instead. **CONTINUE**, then
  **CANCEL** at the second. → **Nothing changed** (the two listings are identical).
- [ ] Do it again through to the end for each area, one at a time. → Only that area's files are gone (the diff shows just those); others are
  untouched. **TERMINAL LOG**, **SAFETY COPIES** and **TEMPORARY FILES** do **not** restart ACK; the rest show a toast and restart after
  about a second and a half.
- [ ] After a wipe, the Terminal log. → One line naming the **areas**, never their content.
- [ ] **SETTINGS**, then look at AUDIO ARCHITECT and the visual editor. → ORGANIC is the voice and a **FULL TEXT** preset is active.
- [ ] **PEOPLE AND PLACES** with the watch connected, then again with it out of range. → Its confirmation says *A PAIRED WATCH MAY KEEP NAMES UNTIL
  IT NEXT CONNECTS.* Connected: the watch's target lists empty. Out of range: the old names stay until it reconnects.
- [ ] Set up a saved place in Geo-Protocol's **OPTIMIZED** (Google geofencing) mode, then wipe **SAVED LOCATIONS**, then walk or simulate
  entering the place. → Nothing triggers. If Google's service cannot confirm the geofences are removed, the wipe **stops with that area listed
  and does not clear the zones**. Try again, or turn Geo-Protocol off first.
- [ ] **DELETE EVERYTHING** through both confirmations. → ACK restarts and opens cleanly with its default decks; every area in the list is
  empty (open DELETE DATA again to see). ORGANIC and FULL TEXT are in place.

## G. Free speech says it records anyone nearby

Text only: these screens make no sound and no vibration while the microphone is open, so nothing here is a dialog, toast or standard button.

- [ ] PROTOCOL → AUDIO ARCHITECT → CUSTOM VOICE → **RECORD TRAINING DATA**. → Under the FREE SPEECH description there is one more line,
  **IT ALSO RECORDS ANYONE NEARBY.**, larger and brighter than the text above it (12 sp, white, bold; not red).
- [ ] Tap **RECORD FREE SPEECH**. → The setup screen's BEFORE YOU START block ends with **FREE SPEECH RECORDS EVERYTHING THE MICROPHONE HEARS,
  INCLUDING ANYONE NEARBY, FOR UP TO 90 MINUTES. TELL THEM FIRST, OR RECORD SOMEWHERE ELSE.**, and it is **above** START QUIET CHECK.
- [ ] Go back and open a **script** instead (RECORD on a script). → Its setup screen does **not** show that paragraph; everything else on it is
  unchanged.
- [ ] Nothing on either screen vibrates or makes a sound, including when you tap START QUIET CHECK.
- [ ] HELP → RECORD TRAINING DATA → the FREE SPEECH step. → Its text now ends **It also records anyone nearby.**

## H. Copying text (no change was made; this is the behaviour you chose)

ACK does not mark anything it copies as sensitive: you wanted to see what was copied in the clipboard preview. So:

- [ ] In the statement composer, build a statement and tap **COPY**. → The toast says COPIED and the system clipboard preview **shows the text**.
  Paste it into another app. → It pastes normally.
- [ ] On a contact card, copy a phone number or address. → Same: shown in the preview, pastes normally.
- [ ] Note for yourself: a keyboard's clipboard history (for example Gboard's) may keep what you copied, and so can any app you allow to read
  the clipboard. ACK does not clear it afterwards.

## I. Does the watch link use the internet? (needs a paired watch; dummy data only)

Google's documentation says Data Layer messages may travel through Google's servers when Bluetooth between phone and watch is
unavailable (see `docs/DATA_SOVEREIGNTY.md`, section 8). Nobody has seen it happen on these devices. To see it, add this **temporary**
line, build a debug build, and **remove it afterwards** (`git checkout` the two files). It logs only true or false, never a name or id.

In `watch/WatchSync.kt`, inside `sendMessage`'s `connectedNodes.addOnSuccessListener { nodes -> ... }`, and in `output/OutputService.kt`
right after the `connectedNodes` list is read in `relayToWatchIfReachable`:

```kotlin
nodes.forEach { android.util.Log.i("ACK_NODE_TEST", "node nearby=${it.isNearby}") }
```

- [ ] With the phone's Bluetooth **on** and the watch next to it, switch deck on the phone, and run `adb logcat -s ACK_NODE_TEST`. → One line,
  `nearby=true`, and the watch updates.
- [ ] Turn the phone's Bluetooth **off**, keeping the phone on Wi-Fi and the watch on its own Wi-Fi or LTE (both with internet). Switch deck
  again. → Write down what you see: is there a node line, is it `nearby=false`, and does the watch still update? Any of these is a useful answer.
- [ ] Turn Bluetooth back on and remove the temporary line. → `git diff` shows no change to `WatchSync.kt` or `OutputService.kt`.

Send back the log lines (they contain no names) and whether the watch updated with Bluetooth off.

## What to send back

For any line that did not match: the line, what you saw, and (for a failed build) the first red error. For D and F also the `before.txt`
and `after.txt` difference, which names files only.
