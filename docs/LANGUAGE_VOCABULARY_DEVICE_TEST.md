# Language and vocabulary: checking it on a real phone

This covers the parts of Section 4 that are built so far: the **neutral starter phrases** (L1), **typing, inserting and the history
chips** (the work behind them, B1 to B4), the **profile-change warning** (L7, the warning half), and **word suggestions** (L5, in the
Statement Composer), and the **voice list and SPEECH LANGUAGE** (L3, part 1). **PLAIN WORDS** (L2, section J) and **INTERFACE LANGUAGE** with five draft translations (L3, part 2, section K) are built too. **Not built yet, so not here:**
the profile lock (decided against for now), and the
pictures and core-vocabulary decisions (L4, L6). Their steps will be added when they are built.

The rules are covered by automated tests (480 in `tools/kotlin_check`, run with `./run_unit_tests.sh`), and the repository policy tests
pass. **What was never run anywhere is the Android part:** the build itself, every screen, the layout, the keyboard and the file
picker. This list is for you to work through once, in order, on a **debug build** with sample data. Each line is *do this → you should
see this*. If something does not match, the note at the end says what to send back.

**Take a backup first** (SETTINGS → DATA PORT → EXPORT .JSON). Several steps below change or delete data on purpose, and they say so.

## A. Build

- [ ] Build **both** modules in Android Studio, `:app` and `:wear`, and run `./gradlew :app:testDebugUnitTest`. → Both build and the unit tests
  pass. If the build fails, copy the **first** red error. (Most likely a small typo or wrong import: these files were edited by hand and
  never compiled against the real Android libraries: `InstallState`, `DataWipe`, `CommandRepository`, `StarterSeed`, `TransferManager`,
  `AckBackup`, `SettingsView`, `DesignSystem`, `QuickActionsDeck`, `MainActivity`, `StatementComposerView`, `SharedComponents`.)
- [ ] Compare the two manifests with the branch point. → No permission was added.

## B. A fresh install gets the starter phrases

You need a phone with no ACK data: **uninstall ACK, then install the new build.** (Your own phone is an existing install and is left
alone on purpose; see section C.)

- [ ] Open ACK and look at the MATRIX deck (DEFAULT). → The twelve slots say what `docs/STARTER_PHRASES.md` lists, in the same positions:
  IDENTITY: Yes. / Hello. / Please say that again. / I am using a communication device. DEFEND: Stop. / Please wait, I am typing. /
  I need a break. / I need some space. CONNECT: No. / Thank you. / I need help. / Nice to meet you.
- [ ] Look for anything personal. → "Snakesan", "Systems Online", "Identify yourself", "Leave me alone" appear **nowhere** in the app.
- [ ] Open the deck selector. → A deck called **STARTERS** is listed. Open it: three groups (ANSWERS, REPAIR, SOCIAL) of four buttons, labelled
  YES, NO, DON'T KNOW, MAYBE / AGAIN, SLOWER, DON'T UNDERSTAND, I'M TYPING / HELLO, THANK YOU, SORRY, HELP.
- [ ] Tap a Matrix slot and a STARTERS button. → Each speaks exactly its phrase.
- [ ] Switch the profile (for example to WORK) without editing anything, and look at the Matrix. → Still the starter phrases (a profile with
  nothing of its own falls back to DEFAULT).
- [ ] Make a **new Matrix deck**. → Its twelve slots show the starter phrases too (not the old wording).
- [ ] Edit one Matrix slot to something of your own, then open DATA PORT → DELETE DATA → **MESSAGES AND DECKS**. → The first confirmation says
  AFTERWARDS THE MATRIX DECK SHOWS ACK'S NEUTRAL STARTER PHRASES. After the restart the twelve starters are back (your edit is gone, as
  deleting that area means), and the STARTERS deck is **not** made again.

## C. An existing install must change nothing

Install the **previous** build, put some personal data in it (change a few Matrix slots, leave others untouched), export a backup, then
update **in place** (`adb install -r`).

- [ ] Look at the Matrix. → The slots you changed say what you set; the slots you never touched still say the **old built-in wording**
  ("Acknowledged.", "Systems Online.", and so on). Nothing was swapped for a starter.
- [ ] Open the deck selector. → There is **no** STARTERS deck.
- [ ] Optional, with `adb`: compare `shared_prefs/ack_matrix_config.xml` before and after the update. → No change. There is **no** new
  `ack_starter_seed.xml`.
- [ ] Make a new Matrix deck. → Its untouched slots show the **old** wording, like the rest of this phone (not the starters).
- [ ] DATA PORT → DELETE DATA → **SETTINGS** (cancel at the second confirmation if you would rather not). If you do it: → your Matrix phrases
  are exactly as they were. (A settings wipe must never change a phrase.)
- [ ] Open TERMINAL and SETTINGS in the days after the update. → No backup reminder appears **because of** the update itself.

## D. Restoring a backup onto a phone that has the starters

On a fresh install (section B), use SETTINGS → FULL RESTORE FROM JSON with the file you exported from the **old** build in section C.

- [ ] Read the confirmation. → Besides the usual text, it says that starter phrases you never edited go back to the wording the file's phone
  showed, and that edited ones are never touched.
- [ ] Restore, let ACK restart, and look at the Matrix. → Slots the old phone **left untouched** show the **old wording** again; slots it
  **edited** show those edits. The STARTERS deck is still there.
- [ ] Now export from the fresh (starter) phone and restore **that** file onto another fresh install. → The starters stay (nothing is taken
  back, because that file came from a phone that had them).

## E. Typing and inserting

Use the Statement Composer (TYPE tab) unless a step says otherwise. "Chip" means a Target Computer chip.

- [ ] Type "Hello", leave the cursor at the end, tap a chip. → "Hello [COMPUTER:...]" with **one** space before it and a space after, and
  the cursor after that space.
- [ ] Put the cursor between two words, tap a chip. → One space each side; **no double space**.
- [ ] Put the cursor just before a full stop, tap a chip. → **No space** before the full stop.
- [ ] Put the cursor right after an opening bracket, tap a chip. → No space between the bracket and the tag.
- [ ] Put the cursor in the **middle of an existing tag**, tap a chip. → The new tag goes **after** it; the old one is whole.
- [ ] Select some words (long-press, drag), tap a chip. → The selected words are **replaced**.
- [ ] Select part of a tag only, tap a chip. → The **whole** tag is replaced, never a broken half.
- [ ] Put the cursor next to an emoji and tap a chip. → The emoji is never cut in half.
- [ ] BROWSE TARGETS → pick an entry; and INSERT VARIABLE → pick a slot. → Both follow the same spacing. BROWSE TARGETS inserts the **plain
  label**; INSERT VARIABLE inserts a `{VAR:...}` tag, as before.
- [ ] Manual Override: type `/m` in the TERMINAL, type a word, tap a chip. → The chip's text goes in **with a space after it** (the one
  visible change here; check it reads well).
- [ ] TERMINAL: type `/v`, pick a variable. → Its value replaces the `/v`, with a space; the rest of the line is untouched. Try it in
  the middle of a line: no double space.
- [ ] Matrix editor, a node whose template has text: put the cursor in the **middle** and tap `+ VAR`, then an INSERT TARGET TAG button. → Each
  goes **at the cursor**. Open a different node's editor fresh and tap one straight away. → It goes at the **end** (a freshly opened
  editor starts with the cursor at the end).
- [ ] **The important one.** Matrix editor: make a template like `Hi {VAR} and {VAR}`, type values "Ann" and "Bob" into the two VARIABLE fields,
  then put the cursor at the very start and tap `+ A`. → There are now **three** fields. "Ann" and "Bob" are still on the **same two tags
  they were on** (now the second and third), and the new first one is empty. Repeat with a `[COMPUTER:...]` tag and its fallback.
- [ ] Quick Actions slot editor: the same, with INSERT TARGET TAG and a TARGET TAG FALLBACK already typed. → The fallbacks stay with their tags.
- [ ] HELP: run the Statement Composer walkthrough and the Target Computer one. → Their steps still advance when you tap the chip /
  INSERT TARGET TAG (they wait on those taps), and the new wording about the cursor is shown.

## F. The history chips

You need a variable field with some history: type a few values into one (for example "Mum", "Mum and Dad", "Dad", "mum", "Grandma"), and
move away from the field or tap UPDATE so each is recorded.

- [ ] Open the field with **nothing typed**. → Your most-used values, as before (up to five).
- [ ] Type one letter. → Only values that **start with** it remain, whatever the capitals.
- [ ] Keep typing. → The chips narrow with every letter. The fields below the chips **do not move**, and there is **no animation**.
- [ ] Type something that matches nothing. → No chips, but the **blank band stays** (nothing below it moves).
- [ ] Type a value exactly as it is saved. → That value is **not** offered back; longer ones that start with it still are.
- [ ] "Mum" and "mum" were both recorded. → They show as **one** chip (the most recently typed form).
- [ ] Look at the chips. → The text is **easy to read** (14 sp), each chip is easy to tap, a long value wraps to two lines and the row scrolls
  sideways. Two long values that start alike can be **told apart by their ends**.
- [ ] Turn the phone's font size to its **largest** and open the field. → Note whether the chips still fit in the band, and whether anything
  moves when chips appear or disappear. (Send back what you see; this is the one place the reserved height might not be enough.)
- [ ] Tap a chip. → It **replaces the whole field**.
- [ ] TalkBack, if you use it, on a long value. → It reads the **full** value, not the shortened one.
- [ ] Note how the blank band under every variable field **feels** (you chose a steady layout over hiding an empty row). → Tell me if it is
  too tall; reserving it only for fields that have history is a small change.

## G. The profile-change warning

Use the MATRIX deck (DEFAULT). To make a difference you can see, on the **WORK** profile edit one slot (for example IDENTITY, the wave
gesture) so it says something other than the DEFAULT profile's phrase for that slot, then switch back to DEFAULT.

- [ ] **Fresh install.** SETTINGS → PROFILES. → The switch reads WARN BEFORE PROFILE CHANGES: ON, with a grey explanation under it, and there is
  **no** offer banner.
- [ ] **Existing install, updated in place.** SETTINGS → PROFILES. → A bordered offer says the warning is OFF for you and nothing changes unless
  you turn it on, with TURN ON and NOT NOW buttons, and the switch reads OFF. Change profile from the PROFILE menu before touching anything. →
  It changes **straight away** with no dialog.
- [ ] Tap **NOT NOW**. → The offer disappears. Leave SETTINGS and come back: it does **not** return, and the switch is still OFF.
- [ ] On another updated install, tap **TURN ON**. → The switch reads ON, the offer disappears and does not return. Nothing else changed.
- [ ] Warning ON, DEFAULT profile: open PROFILE and pick **WORK**. → A dialog says 1 GESTURE WILL SAY SOMETHING DIFFERENT IF YOU CHANGE TO WORK and lists
  "IDENTITY / TWIST …: old phrase, becomes: new phrase". Nothing was spoken, there was no sound, and the phone did not vibrate when it appeared.
- [ ] Tap **STAY**. → You are still on DEFAULT. Open it again and press the **back button**, then tap **outside** the dialog. → Both also STAY.
- [ ] Open it again and tap **CHANGE PROFILE**. → You are on WORK, and the watch (if paired) follows.
- [ ] From WORK pick **HIGH_STRESS** (nothing edited in it, so it falls back to DEFAULT). → The dialog still appears, because WORK's slot differs from
  what HIGH_STRESS would say. Then from DEFAULT pick **HIGH_STRESS** (or any profile with nothing of its own). → **No dialog**: nothing would change.
- [ ] Change that WORK slot by **only a capital letter** or a full stop. → The warning lists it. Change it by **only a space at the end**. → No warning.
- [ ] Make a custom context slot (MANAGE CONTEXT) differ between two profiles. → It is listed too.
- [ ] Make **more than four** gestures differ. → The first four are listed, then AND N MORE.
- [ ] Tick **DO NOT SHOW THIS WARNING AGAIN** and tap CHANGE PROFILE. → SETTINGS → PROFILES now reads OFF, and the next profile change has no dialog.
  Switch it back ON in SETTINGS. → The dialog appears again.
- [ ] Change profile with the **home-screen widget**. → It switches **immediately**, with no warning, and says "Profile Engaged." as before.
- [ ] FULL RESTORE a backup. → No profile warning (a restore is already a confirmed action).
- [ ] Open a **Quick Actions** deck. → There is no profile menu. Note where its buttons are before and after changing profile on a Matrix deck. →
  The buttons are in the **same places**.
- [ ] HELP: run the walkthrough that has you select a profile, with a slot that differs. → The step waits, the dialog appears, and it advances
  only after CHANGE PROFILE.
- [ ] Set the switch OFF, export a backup, set it ON, then FULL RESTORE that file. → It reads OFF again. Restore a file made by an **older build**.
  → The switch is unchanged.
- [ ] DATA PORT → DELETE DATA → **SETTINGS**. → Afterwards the switch reads ON (the new-install default) and no offer is shown.

## H. Word suggestions (the Statement Composer)

Off until you turn it on. It learns only from statements you SAVE, SPEAK or COPY in the composer, and offers words only as buttons.

- [ ] On an **updated install**, open the TYPE tab (the Statement Composer). → A box at the top says WORD SUGGESTIONS is OFF and nothing is learned
  unless you turn it on, with **TURN ON** and **NOT NOW**. The rest of the screen is exactly as before. Type some words. → Nothing is offered.
- [ ] Tap **NOT NOW**. → The box goes and does not come back (leave the screen and return to check). The switch in SETTINGS → WORD SUGGESTIONS still
  reads OFF.
- [ ] On another install (or after clearing the app's data), tap **TURN ON** in the box. → The box goes, a **blank band** appears under the text box
  and stays the same height whether or not it holds anything, and SETTINGS → WORD SUGGESTIONS reads ON with WORDS LEARNED: NONE YET.
- [ ] Type *Hello there, I would like some tea please* and tap SPEAK. → It speaks as before and nothing on the screen changes or moves.
  SETTINGS → WORD SUGGESTIONS now says WORDS LEARNED with a number, and FORGET WORDS lists them with how often each was used.
- [ ] Back in the composer, type **te**. → The band offers **tea**. Tap it. → *te* becomes *tea*, a space follows, and the cursor is after it.
  Nothing is inserted until you tap: type **te** again and do nothing. → The text stays *te*.
- [ ] Type **I would** and a space. → The band offers a word that usually follows ("like"). Type a full stop after some text and then a space. → The band
  is empty: a sentence end starts again. Learn a name in the middle of a sentence (for example *I called Sarah today*) and type **Sa**. → It is offered with
  its capital.
- [ ] Type in the **middle of a word**, inside a tag such as [COMPUTER:…], after a full stop, after a line break, and with text **selected**. → The
  band is empty each time. Type a number such as 07700. → It is never offered.
- [ ] Tap SAVE, then COPY, then SPEAK on the **same** text. → The word counts go up **once**, not three times. Change a word and SPEAK. → They go up again.
- [ ] From MY STATEMENTS tap [SPEAK] on a saved statement. → It speaks and **nothing is learned** (the counts do not change).
- [ ] Add a Target Computer entry named something unusual (for example *Zuzanna*) and a Shared Root Variable value, then type **Zu** in the composer. → The
  band offers *Zuzanna*, and FORGET WORDS does **not** list it. Rename or delete the entry. → It stops being offered.
- [ ] Use an **Emergency** deck, the **Terminal** (including `/v`, `/t` and `/m`) and a Matrix or Quick Actions editor. → Nothing is learned from any of them
  (the count in FORGET WORDS does not change).
- [ ] SETTINGS → WORD SUGGESTIONS → **OFF**. → The band disappears from the composer; SPEAK learns nothing; the words already learned are still listed
  in FORGET WORDS. Turn it ON again. → They are offered again.
- [ ] FORGET WORDS → **REMOVE** on one word. → Nothing is removed yet; a question says it can be learned again, with **KEEP** and **REMOVE**. Tap KEEP. → It
  stays. Tap REMOVE and REMOVE again. → It goes, and the count drops by one.
- [ ] FORGET ALL WORDS → the first box names how many, says they are in EXPORT .JSON, offers **BACK UP FIRST**, and says nothing from Target Computer or
  Shared Variables is affected. **CONTINUE** → the second box says THIS CANNOT BE UNDONE with **CANCEL** first. Tap CANCEL. → Nothing is removed. Do it
  again and confirm. → The list is empty and the composer offers nothing.
- [ ] EXPORT .JSON. → The warning lists WORDS LEARNED FROM WHAT YOU SAVED, SPOKE OR COPIED. Export, then FORGET ALL WORDS, then FULL RESTORE that file. → The
  words are back. The WORD SUGGESTIONS switch is **unchanged** by the restore (it is not in the file). Restore a file made by an **older build**. → Nothing
  is lost and no error appears.
- [ ] After learning some words, check the **backup reminder** (it only appears after seven days with changes). → Learning words alone never makes it appear.
- [ ] DATA PORT → DELETE DATA → MESSAGES AND DECKS. → Its first box mentions the learned words; after it, WORDS LEARNED reads NONE YET.
- [ ] Turn on a **large font** and a screen reader. → The chips stay tappable at least 48 dp tall, none of the new text is smaller than the text around it,
  and each chip is read as its word.
- [ ] HELP: run STATEMENT COMPOSER. → A step called WORD SUGGESTIONS (OPTIONAL) says where to turn it on; it simply asks you to continue.
- [ ] With airplane mode off and a network monitor running (or just the permission list), confirm nothing was sent anywhere and ACK still declares **no**
  network permission.

## I. The voice list and SPEECH LANGUAGE

Take a backup first. This needs a phone with at least one non-English voice **installed** in its speech engine (Settings, System, Languages, Text-to-speech).

- [ ] AUDIO ARCHITECT → open a custom profile → BASE VOICE. → The list now shows voices in **more than English**, sorted by language, with the language
  written out under each voice ("German (Germany)"). A note under the list says voices needing the internet or not installed are not shown.
- [ ] Compare with the engine's own voice list in the phone's settings. → Every installed voice is there. A voice the engine only offers to **download** is not.
  A voice marked as needing the internet is not.
- [ ] Choose a non-English voice and tap the preview/test. → It speaks, through ACK's normal output (so the DSP chain and master gain apply).
- [ ] Put an **English profile** (a voice chosen, or none) on the same phone and speak. → It sounds as before.
- [ ] A profile chose an English voice earlier; now speak with a profile that has **no** voice. → It uses the language setting, not the earlier profile's voice
  (this used to inherit it).
- [ ] SPEECH LANGUAGE reads **THIS PHONE'S LANGUAGE** on a fresh install and **ENGLISH (US)** on an install that already existed. On the existing one, set the phone to a
  non-English language and speak with a profile with no voice chosen. → It still speaks English, as before.
- [ ] Tap SPEECH LANGUAGE to switch it and speak a message at once. → The next message uses the new language (no restart).
- [ ] With the setting on THIS PHONE'S LANGUAGE and the phone language set to one the speech engine does not have, speak. → It still speaks (the engine's own
  default), never silence, and the Terminal log says SPEECH LANGUAGE NOT AVAILABLE once.
- [ ] MY VOICE (the cloned voice), if imported. → Unchanged.
- [ ] EXPORT .JSON, change SPEECH LANGUAGE, FULL RESTORE that file. → The setting returns to what the file held. Restore a file from an **older build**. → The setting is unchanged.
- [ ] DATA PORT → DELETE DATA → SETTINGS. → The first box says speech will be in this phone's own language afterwards; after it, SPEECH LANGUAGE reads THIS PHONE'S LANGUAGE.
- [ ] Screen reader and a large font on the voice list. → Each row is readable and every line is at least as large as the body text.
- [ ] Confirm ACK still declares no network permission.

## J. PLAIN WORDS (L2)

Wording and decisions are in `docs/PLAIN_LANGUAGE.md`. Do the steps with PLAIN WORDS **off** first, then on. Nothing here should change what a
button *does* or what is stored: only what it is called, plus the new buttons.

**The switch**
- [ ] Open SETTINGS (the header button says PROTOCOL while it is off). → **PLAIN WORDS: OFF** is the first item, with a short explanation. On an
  install that never answered the offer, a box above it offers TURN ON and NOT NOW. NOT NOW changes nothing and does not come back.
- [ ] Tap **PLAIN WORDS: OFF**. → It reads **PLAIN WORDS: ON** at once, in the same place, with no restart. The header button now says
  **SETTINGS**, and the settings headings change (for example DATA PORT → MY DATA, AUDIO ARCHITECT → VOICE AND SOUND, EXPORT .JSON → SAVE A BACKUP). The switch's own wording is the same in both modes.
- [ ] Turn it off and on again a few times. → It always flips at once and never loses your place.

**Names change, nothing else does**
- [ ] Open the MATRIX deck. → With it on, the group headings read ABOUT ME / I NEED SPACE / SOCIAL and the rows GESTURE 1 (MAIN), GESTURE 2 ...
  Off: IDENTITY / DEFEND / CONNECT and Twist 0 (Default), Twist 1 ... Tap ACTIVATE on a group in either mode. → The Terminal's log line still says
  CONTEXT FOCUS: IDENTITY (the stored name), and tapping a row speaks the same phrase as before.
- [ ] Turn it on and off, then EXPORT .JSON before and after (or compare the Matrix phrases by eye). → Nothing stored changed.
- [ ] With TalkBack on, move across the bottom bar. → On: PHRASES, HISTORY, PEOPLE AND PLACES, LOCATION ALERTS, VOICE AND SOUND, TYPE. Off: Matrix,
  Logs, Targets, Zones, Audio Architect, Type.
- [ ] Open HELP and start a walkthrough (for example TARGET COMPUTER). → The coach text uses the same names as the screen (PEOPLE AND PLACES with it
  on, TARGET COMPUTER off), and when it reads aloud you hear no curly brackets.
- [ ] Walk through the **eight core tasks** in `docs/PLAIN_LANGUAGE.md` with it on, as someone who has never seen ACK. → You can find each one
  without knowing ACK's own words. Write down every place you got stuck.

**The Terminal screen (HISTORY)**
- [ ] With it on, open the Terminal screen. → **WHAT'S NEW** and **CLEAR HISTORY** across the top; a **SEND OPTIONS** row above the typing box. With it
  off, none of these show and the screen is exactly as before.
- [ ] Tap **WHAT'S NEW**. → The patch notes appear line by line, the same as typing `/info`. Shake stops it.
- [ ] Tap **CLEAR HISTORY**. → A box asks, with **CANCEL** first and large, and a red **CLEAR HISTORY** below it. Tap outside the box. → Nothing is
  cleared. Tap CLEAR HISTORY, then the red one. → The history clears and says LOG CLEARED. Typing `/cls` then `/cls confirm` still works.
- [ ] Tap **SEND OPTIONS**. → Four rows open: SEND QUIETLY, DO NOT SAVE IN HISTORY, KEEP ON SCREEN UNTIL I CLEAR IT, EMERGENCY, each reading OFF, and
  two buttons below (INSERT A FILL-IN, BROWSE PEOPLE AND PLACES). A line says they stay on until you turn them off and that closing ACK turns them off.
- [ ] Turn **SEND QUIETLY** on. → Its row shows ON in words and a thicker border, and the **closed** row now reads SEND OPTIONS ON: SEND QUIETLY, so a
  switch that is on is never hidden. Send a phrase. → No sound. Send another. → Still no sound (it stays on). Leave the screen and come back. →
  Still on.
- [ ] Turn it off and send. → It speaks. Then try DO NOT SAVE IN HISTORY (the message is not in the history) and KEEP ON SCREEN UNTIL I CLEAR IT (it
  stays on the display until you clear it).
- [ ] With an **Emergency deck active**, turn **EMERGENCY** on and send. → It uses the Emergency deck's settings, with **no** confirmation question.
  With another deck active. → It is sent normally and a warning line says no Emergency deck is active.
- [ ] Turn one switch on, then turn PLAIN WORDS **off** in SETTINGS and send from the Terminal. → It goes out normally (a hidden switch must not act).
  Turn PLAIN WORDS on again. → All four read OFF.
- [ ] Turn one on, close ACK completely (swipe it away) and open it again. → All four are OFF.
- [ ] Type `/q hello` with PLAIN WORDS on or off. → The typed commands still work in both modes.
- [ ] Tap **INSERT A FILL-IN**. → `/v` appears at the cursor and the status box shows the Shared Variable groupings, exactly as if you had typed it. Tap it
  again. → No second `/v`. Tap **BROWSE PEOPLE AND PLACES**. → The same for `/t`.

**The other two buttons**
- [ ] Open the TYPE tab with PLAIN WORDS on. → A **TYPE AND SPEAK (CLASSIC)** button is at the top. Tap it. → Classic Manual Override opens, and its CLOSE
  returns to the Type tab. Do it again from FULL SCREEN. → It leaves full screen first and the quick-insert header works.
- [ ] Open SETTINGS with it on. → Below the switch, a **FIX PROBLEMS** button with a short line about what it does. Tap it. → A message says the background
  parts were restarted, a line appears in the Terminal history, and speaking still works. It asked no question (as the typed `/repair`).

**Feel**
- [ ] Look at every new control. → Text is readable (never tiny), every button is easy to hit, and **nothing buzzes or moves** when you tap them.
- [ ] TalkBack on the four switches. → Each is announced as a switch, on or off.

## K. INTERFACE LANGUAGE (L3, part 2): five DRAFT translations

Rules and limits are in `docs/TRANSLATIONS.md`. **The translations are drafts written without a native speaker**: this list checks that they *work*, not that
they are right. If you read one of the languages (or know someone who does), write down every word that is wrong or odd, with the screen it is on.
Take a **backup first** (EXPORT .JSON); nothing here deletes anything.

**The control, and an existing install staying English**
- [ ] On a phone that already had ACK (set to Spanish, Portuguese, Hindi, Arabic or Afrikaans in the system settings), update and open ACK. → Everything is still
  **English**. (An existing install must not change language by itself.)
- [ ] Open SETTINGS. → Just under PLAIN WORDS is a **LANGUAGE · IDIOMA · भाषा · اللغة · TAAL** heading, a short explanation that says the translations are drafts and that
  the walkthroughs inside HELP, the Terminal and many dialogs stay English, and choices: THIS PHONE'S LANGUAGE, ENGLISH, ESPAÑOL, PORTUGUÊS, हिन्दी, العربية, AFRIKAANS. The current one has a tick and a thicker border.
- [ ] Tap **ESPAÑOL**. → A box says ACK will restart once, that nothing is deleted, and that you can change it back. **CANCEL** is first and large. Tap outside the box. → Nothing changes.
- [ ] Tap ESPAÑOL again, then **CHANGE AND RESTART**. → A message says ACK is restarting, then ACK reopens (the screen you were on is not kept).

**A translated language**
- [ ] Look at the bottom bar (with TalkBack on, listen to it), the header button, the Matrix group headings and the SETTINGS headings. → Spanish names. Turn **PLAIN WORDS on**. → The everyday Spanish names
  (FRASES, HISTORIAL, PERSONAS Y LUGARES, AJUSTES, SOBRE MÍ / NECESITO ESPACIO / SOCIAL ...). Anything not in `docs/TRANSLATIONS.md`'s list is still English: that is expected.
- [ ] On the **Matrix deck** and the header row, in each language. → ACTIVATE / ACTIVE, the shared-value strip (EXPAND, ON / OFF, EDIT, NO SHARED VALUE SET, and the hint with its `{VAR:A}` tags unchanged),
  the SEQUENCE and ROOT headings, the "recorded" badge and the DECK / PROFILE / COMPUTER words are translated; open a shared value's EDIT box and check its title, ABORT and COMMIT. With PLAIN WORDS on, the header's DECK reads PAGE (or its translation).
  Tap a Matrix row's EDIT: the editor dialog (template, INSERT VARIABLE TOKEN, voice recording, visual override, local variable data, target tag fallbacks, DESTRUCTIVE CONTROLS)
  is translated; try CLEAR VARS, CLEAR PROMPT and CLEAR ALL and check each confirmation shows **both** sentences. MANAGE CONTEXT's own dialog is still English: that is expected.
- [ ] Open the **TYPE tab** (the Statement composer) in each language. → FULL SCREEN, the hint in the text box, the preview line, SAVE / COPY / SPEAK, the SAVE dialog (name, folder, example, STATEMENT SAVED), NEW FOLDER, MY STATEMENTS (the empty
  sentence, and each row's YES / NO / COPY / SPEAK / DELETE) and the shared-variable list ("… VARIABLES", "(NOT SET)") are translated. A folder or statement **you named** is shown as you typed it. The word-suggestion offer is still English: expected.
- [ ] Open **SETTINGS → EXPORT .JSON** in each language. → The warning is translated: what the file can contain (seven lines), that it is not encrypted and has no password, and where not to save it (Google Drive, OneDrive); CHOOSE WHERE TO SAVE and CANCEL are translated; CANCEL still opens no picker.
  In the **Terminal**, type `/backup`. → The same facts in the chosen language, and the last line still tells you to type **/backup CONFIRM**; type exactly that and the export starts, as in English.
  Turn the backup reminder on and, if one is due, check it reads naturally with the number of days (1 day and several days; in Arabic also 2 days).
  Check FULL RESTORE's confirmation (it says nothing on the phone is deleted, and the starter-phrase exception), IMPORT MATRIX AS NEW DECK's colour prompt, and the toasts. **With PLAIN WORDS on**, the sentence under the two buttons names them with their everyday names.
- [ ] Open **PEOPLE AND PLACES** (the Targets tab) in each language. → The tabs (CATEGORIES | VISUALS), [GUIDE ME], the category tiles with their small names, EMPTY, + ADD CATEGORY and, if any contact card exists, the CONTACT CARDS panel with NAMES and PLACES are translated. **A category still named PEOPLE, PLACES, FOOD/DRINK or ACTIONS shows its name in the language** ("PERSONAS"); one you renamed or made yourself shows exactly as typed. Long-press a category: the options dialog starts with the shown name; **save without touching it, then switch to ENGLISH**: the category reads "PEOPLE" again (nothing saved changed). Rename one and check it keeps your name in every language. Open a category: TREE / DROPDOWN, ADD TO, + CATEGORY, + ENTRY, LEVEL, SELECT..., [CARD], ACTIVE; long-press an entry (EDIT ENTRY, PERSON / PLACE, DELETE asks twice: CONFIRM DELETE and CANCEL, and the warning counts nested items). Tap [GUIDE ME] and walk through GUIDED SETUP. Tap the COMPUTER indicator in the header: TARGET COMPUTER STATUS, CLEAR (asks first), UNDO. In the TYPE tab's target chips and BROWSE TARGETS and under `/m`'s quick-insert header, the words are translated but **what is inserted into your text is the entry's own name, as you typed it**. Open a **contact card** (long-press an entry, tick PERSON or PLACE, OPEN CONTACT CARD): the title, [EDIT] / [DONE EDITING], the field names and their examples, HOURS with the day names (MON... in the language; the saved day never changes: tick one, switch to ENGLISH and the same day is ticked), and the OPEN / CLOSE boxes are translated. X, FACEBOOK and LINKEDIN stay as they are. Tap a phone, address or email with no app that can open it: the toast is translated; long-press a value: COPIED is translated.
- [ ] Open an **Emergency deck** (make one if there is none) in each language. → The title, the hint ("TAP: EXECUTE  //  HOLD: CONFIGURE" in the language), the overrides line, READY / HOLD TO SET and the buttons' default names ("EMERGENCIA 1") are translated. **Tap a configured button**: it speaks as before. Hold one: the editor opens with the default name in the language; **save without touching the name**, then switch to ENGLISH: the button reads "EMERGENCY 1" again (nothing saved changed). Open CONFIGURE OVERRIDES and turn CONFIRM BEFORE SENDING on: tapping a button now opens CONFIRM EMERGENCY with **SEND** and **CANCEL** as two large, clearly different buttons; CANCEL speaks nothing. Turn it off again if it was off.
  Open **EMERGENCY INFO**: each label reads like "NOMBRE // NAME" (the language, then English); fill in a name and a condition and check they are shown exactly as typed. Tap EDIT: the form uses the language only. The saved **communication note** is still the English sentence (on purpose). In Arabic check the mixed Arabic and English label line reads sensibly and is not cut off. Check a long label does not push the value off screen.
- [ ] Open **SETTINGS → DELETE DATA** in each language, **without deleting anything**. → The twelve areas show their names, what they hold, and how much is stored ("3 ITEMS, 12 KB" in the language; a one-item area says one item). Tap DELETE on a small area such as TEMPORARY FILES: the first confirmation says what is deleted, how much, how it is backed up, and that files saved elsewhere are not deleted; **CANCEL** (the large button) leaves without deleting; CONTINUE opens the second, which says it cannot be undone with CANCEL as the large button. Cancel there too. Check a long area name does not cut a title off. In the notes under TRAINING DATA and GIF LIBRARY, the buttons **SAVE ALL TO A FILE** and **EXPORT DECK (.ZIP)** are still in English on purpose; the TRAINED VOICE note names **EXPORT VOICE BACKUP** the way the button on the AUDIO ARCHITECT screen reads in that language.
  If a phone has a safety copy, its row and its delete dialogs read in the language and the date shows the language's month name with ordinary digits. In AUDIO ARCHITECT, DELETE CUSTOM VOICE's two dialogs are translated (cancel them). Digits: in Arabic check whether the counts show Western or Eastern Arabic digits and note it (both are legible; the choice is Android's).
- [ ] Open **AUDIO ARCHITECT** in each language. → MASTER GAIN with its percentage, the VOICE PROFILE chips, MANAGE PROFILES, the SPEECH LANGUAGE button and its explanation, CUSTOM VOICE with STATUS, and (if a voice is imported) the EXPORT / IMPORT VOICE BACKUP buttons and the note that the backup is not encrypted are translated. **CYBER, MECH, ORGANIC, MY VOICE and a new slot's CUSTOM A are the same in every language on purpose.** Tap the SPEECH LANGUAGE button: it switches between THIS PHONE'S LANGUAGE and ENGLISH (US) as before. Tap a custom chip, then EDIT DSP CHAIN: UNSAVED CHANGES* / UP TO DATE, BASE VOICE, USE MY VOICE (with the name unchanged), PITCH, SPEED, RESET TO HUMAN, the robotic and bitcrush sliders, PREVIEW, DISCARD, COMMIT and CLOSE are translated and **the ON / OFF buttons are not clipped** (Spanish: DESACTIVADO). Tap BASE VOICE: the picker's title, each voice's language name and the note are translated; CANCEL closes it. In MANAGE PROFILES: RENAME, SAVE, DELETE (the question names the profile and has CANCEL and DELETE), + NEW SLOT, and SLOT LIMIT REACHED after eight. After an import or a restore of a voice, the toast is translated (then the app restarts). In **Arabic** check the mixed Arabic and English chip row, the slider labels, and that the profile name is not cut off.
  If a phone that already existed still has the older defaults (CYBER as the voice, or a display preset that cuts messages), the **NEWER DEFAULTS banner** appears at the top: it is translated, and its sentence names only what is on offer (the voice, the full message, or both). [REVIEW] opens the review: both switches start **off**, APPLY is greyed until one is on, the two sentences about the unprocessed voice and the full message are translated (ALERT:, FULL TEXT and SHOW FULL MESSAGE stay English), BACK UP FIRST starts a save and then says BACKUP SAVED with nothing changed yet. CANCEL changes nothing. Do not tap APPLY on a phone you want to keep as it is; if you do, check the SETTINGS UPDATED toast.
- [ ] Open the Matrix screen and tap **[MANAGE CONTEXT]** in each language. → The title, the sentence about the three permanent poses, the three permanent rows ("ROOT :: IDENTITY" with the pose's name in the language, and [IMMUTABLE]), and, if a custom layer exists, its name **as you typed it** with BASED ON and the pose's name, ▲ ▼, REASSIGN, RENAME and DELETE. Tap **+ ADD CONTEXT**: CONTEXT NAME with an example, ASSIGN TO POSE with the three pose buttons (their names in the language), CREATE stays greyed until the name is new and not a pose name, CANCEL closes. Tap RENAME on a layer (CONFIRM RENAME) and REASSIGN (CONFIRM). Tap **DELETE** on a layer: nothing is deleted yet; the question (CONFIRM DELETE, ABORT) names the layer, says everything saved under it is deleted across every deck and profile and that it cannot be undone, and offers DELETE PERMANENTLY and CANCEL. Cancel it. Check the three pose buttons in Arabic and Hindi are not cut off.
- [ ] Open **SETTINGS → MANAGE RECORDINGS** in each language (record something first in a Quick Actions slot, a Quick-Access key or a Matrix node if there is nothing). → The title, the count (1 RECORDING, then several; in Arabic also 2), the [OVERLAY: ON] / [OVERLAY: OFF] switch (ON and OFF in the language), the first-use tip with [GOT IT] (it says HELP in English on purpose), and with nothing recorded the note (it says REC in English on purpose). The tree shows QUICK ACTIONS, QUICK-ACCESS KEYS and MATRIX with counts, pose names in the language, and your deck, profile, group and key names **as you typed them**. A recording's card shows the text it plays in quotes, 0:07 / 12.5 KB, PLAY, RE-RECORD and DELETE. With **[OVERLAY: ON]** tap PLAY on a recording whose phrase is empty: the on-screen overlay still says **(EMPTY PROMPT) in English**, while the card in the list says it in the language. DELETE only asks: the question says what stays and that it cannot be undone, with DELETE and CANCEL. RE-RECORD opens the panel: RECORD, STOP (while recording), the noise-reduction message, PREVIEW with the time, PLAY, DISCARD, ACCEPT, REMOVE. Do not accept or delete anything you want to keep.
- [ ] Open **SETTINGS → AUTOCOMPLETE** in each language. → The heading, the sentence about what ACK remembers (it names MATRIX, QUICK ACTIONS and SHARED ROOT VARIABLES, and the EXPORT .JSON button as it reads in that language) and MANAGE AUTOCOMPLETE are translated. Open it: the subtitle counts the fields (1 FIELD REMEMBERED, then several; in Arabic also 2); with nothing remembered the note is translated; otherwise the three kinds show with their counts, a branch opens to show deck, profile, pose (IDENTITY, DEFEND, CONNECT in the language), node and VARIABLE 1 // ROOT A; **deck, profile, layer, group and slot names read exactly as you typed them**, and each remembered value is as typed. Tap [X] on a value (it goes at once, as before). Tap CLEAR THIS FIELD'S HISTORY: the question says only that field is cleared; CLEAR clears it, CANCEL does not. Tap CLEAR ALL AUTOCOMPLETE HISTORY: the question names the three kinds; CANCEL leaves everything. Do not confirm either on a phone whose history you want to keep.
- [ ] Open **SETTINGS → WORD SUGGESTIONS** in each language. → The heading, the switch (ON or OFF in words), the five-sentence explanation (it names TARGET COMPUTER, SHARED VARIABLES, EXPORT .JSON and FORGET WORDS the way those screens and buttons read in that language) and the count (NONE YET, then a number) are translated. Turn it on, save a statement in the composer, come back and open **FORGET WORDS**: each word shows "USED n TIMES" (check one time and several; in Arabic also 2), REMOVE asks once more (REMOVE and KEEP are different words), **FORGET ALL WORDS** asks twice (the first names the count, EXPORT .JSON and BACK UP FIRST, CANCEL is the large button; the second says it cannot be undone). Cancel both. On a phone that has not answered it, the composer's one-time offer (TURN ON, NOT NOW) is translated.
- [ ] Open **SETTINGS** in each language and look at **AUDIO OUTPUT ROUTING**. → The heading, the three switch descriptions (FORCE SPEAKER, GUIDE VOX, SILENT MODE; their titles follow PLAIN WORDS), and OUTPUT DEVICE with its summary line are translated. Switch FORCE SPEAKER on: the summary says OVERRIDDEN BY (the switch's name) ABOVE and the picker cannot be opened. Switch it off and open OUTPUT DEVICE: AUTO (SYSTEM DEFAULT) with its hint, ACK WATCH (CONNECTED, or NOT CURRENTLY CONNECTED and falls back to AUTO), and each connected Bluetooth device (CONNECTED); a device's name is **exactly as the phone shows it**. With no Bluetooth device connected the picker says so. Pick each and check the summary changes and the sound still goes there. Turn SILENT MODE on with *Display over other apps* off in the phone's settings: the red line under it names SILENT MODE and says nothing would be spoken or shown, and the red banner above the header reads in the language with an ALLOW button that opens that page.
- [ ] Under **WATCH AUDIO FEEDBACK** in each language. → SHARP, CLEAN and SOFT are in the language and a longer word makes its button wider rather than cut off; WATCH VOLUME shows the percentage. Under **VISUAL PROMPT DISPLAY**: the sentence, FORCE DEVICE ROTATION and its OFF / ON explanation use the same words as the switch's own ON and OFF.
- [ ] Under **HARDWARE CONFIG** in each language. → Each slider's line is in the language with its number (CROWN RESISTANCE level, TWIST SENSITIVITY with one decimal, GRAVITY LOCK, FIRE GRACE WINDOW in ms, WAKE GESTURE WINDOW in ms, TARGET FLYOUT TIMEOUT in s, AUTO-CRYO in minutes) and the three explanations read naturally; moving a slider still changes its number. **SHAKE KILL SWITCH**: the sentence, SENSITIVITY with its number, and [TEST] / [STOP]: in the test box ARMED, then DETECTED with a count after a real shake. **ENVIRONMENT SENSOR**: without the microphone permission AUTHORIZE MIC SCAN and OPEN SETTINGS; with it [SCAN] / [STOP], the dB reading and one of CRITICAL / WARNING / OPTIMAL (above 80 dB, above 65 dB, otherwise), and MONITOR OFFLINE when it is off. **QUICK-ACCESS KEYS**: the two field hints (the label field holds four letters at most). The key buttons still say REC and +REC in every language: expected. Check that nothing is cut off in the longest words (Afrikaans and Hindi) or in the narrow buttons.
- [ ] Under **TERMINAL LOG** in each language. → The three switch titles and sentences, the STATUSBOX text colour line (it names STATUSBOX the way that label reads, and follows PLAIN WORDS) and LOG RETENTION: set the slider to 1 and then to 7 and 30: 1 DAY, then the plural (in Arabic also two days: check 2, 3 and 11). RESOLVE and TYPING stay English in the sentences, as the Terminal prints them. Under **VOICE RECORDINGS**: the sentence, the MANAGE RECORDINGS button (the same words as that dialog's title) and RECORDING PLAYBACK GAIN with its percentage; under **PROFILES**: the heading.
- [ ] Open **SETTINGS → PROFILES** in each language. → The heading, the switch (ON or OFF in words), and the three-sentence explanation (it names the MATRIX deck and the other four deck types the way those decks are named on their own screens). If the one-time offer is showing: its sentence, TURN ON and NOT NOW. Then, with the switch ON and two profiles that have different phrases, change profile from the header's menu: the **CHANGE PROFILE?** dialog shows the count (1 GESTURE, then several; in Arabic also 2), the profile's name as typed, a line per gesture (the gesture's name the way the Matrix screen names it, then the old phrase, "becomes:" in the language, and the new phrase, both as you typed them), AND N MORE after four, and (BLANK) for an empty phrase. **STAY** (do not change) is first and the highlighted button; CHANGE PROFILE is the other; the box DO NOT SHOW THIS WARNING AGAIN says it can be turned back on. Nothing is spoken and nothing starts HELP.
- [ ] Tap **HELP** in the header in each language (the button reads AYUDA, AJUDA, मदद, مساعدة or HULP). → The menu's title, subtitle, SELECT MODULE FAMILY and the nine family chips are translated; tap each chip and check the heading and the sentence under it. With **PLAIN WORDS on**, the DECKS / DECK words in the family names are the everyday ones. Each card has [RUN] in the language and a line like "5 STEPS // MATRIX" (the count, then the screen: MATRIZ, TERMINAL, AJUSTES, ESCRIBIR, AUDIO, OBJETIVOS, GEO or CURRENT VIEW in the language). The two entries with one step now say **1 STEP** (they used to say 1 STEPS). **The card titles and summaries are still English: expected.** Open FIELD OPS → the pose entry and VOICE RECORDINGS → the topic entry: the chooser dialogs' title, hint and [CLOSE] are translated, their options are English. Start a walkthrough: the panel says GUIDANCE // 2/7 in the language, with [ABORT], and on a reading step ACKNOWLEDGE // CONTINUE; on a step that waits for a tap, text, file or the keyboard it says AWAITING LIVE INPUT and what to do. **The step text is still English.** The first-use tips in MANAGE RECORDINGS and RECORD TRAINING DATA (each shows until it is dismissed once, so use a phone where they have not been dismissed) name the HELP button as it reads in the language. Arabic: check the bracketed words, the "//" and the step number do not jumble.
- [ ] Repeat for **PORTUGUÊS**, **हिन्दी** and **AFRIKAANS**. → Each shows its own script and words. Write down any text that is cut off, overlaps, or runs over a button
  (longer words in a 48 dp button are the likeliest problem).
- [ ] Switch back to **ENGLISH** from the same control. → Everything English again after the restart.
- [ ] Switch to **THIS PHONE'S LANGUAGE** on a phone set to a language ACK has. → That language. On a phone set to another language (for example German). → English.

**Arabic (right to left)**
- [ ] Choose **العربية**. → After the restart the screens are **mirrored**: the bottom bar, buttons and text start on the right. The words are **joined** (not spaced apart letter by letter).
- [ ] Open the Matrix, the composer, SETTINGS and a dialog. → Nothing is cut off at an edge, no icon or toggle is in the wrong place or points the wrong way, and typing in the composer still works.
  Write down every screen that looks wrong.
- [ ] Choose **ENGLISH** again. → Left to right again.

**Backup, restore and wipe**
- [ ] Choose a language, then EXPORT .JSON and look at the warning. → It still lists SETTINGS AND HISTORY (the language is part of that). Restore that file after choosing English. → ACK restarts (the usual restore restart) and shows the saved language.
- [ ] DELETE DATA → SETTINGS. → The first confirmation says ACK'S OWN WORDS WILL BE IN THIS PHONE'S LANGUAGE afterwards. After it, a phone set to Spanish shows Spanish.
- [ ] A **brand-new install** on a phone set to Spanish. → Spanish from the first screen, with **PLAIN WORDS still off**.

## What to send back

- For a **build failure**: the first red error.
- For a **wrong phrase, space or position**: the screen, what you typed, where the cursor was, what you tapped, what you got, and what you
  expected.
- For the **{VAR} / fallback shifting** step: the template, the values, where you inserted, and where each value ended up.
- For the **chips at a large font**: a screenshot, if you can.
- Anything that feels worse to use than before, even if it is "correct".
