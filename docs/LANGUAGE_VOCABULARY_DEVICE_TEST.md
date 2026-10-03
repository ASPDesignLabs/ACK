# Language and vocabulary: checking it on a real phone

This covers the parts of Section 4 that are built so far: the **neutral starter phrases** (L1), **typing, inserting and the history
chips** (the work behind them, B1 to B4), the **profile-change warning** (L7, the warning half), and **word suggestions** (L5, in the
Statement Composer), and the **voice list and SPEECH LANGUAGE** (L3, part 1). **Not built yet, so not here:** plain-language mode (L2, the
wording is proposed in `docs/PLAIN_LANGUAGE.md`), translated interface text (L3, part 2), the profile lock (decided against for now), and the
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

## What to send back

- For a **build failure**: the first red error.
- For a **wrong phrase, space or position**: the screen, what you typed, where the cursor was, what you tapped, what you got, and what you
  expected.
- For the **{VAR} / fallback shifting** step: the template, the values, where you inserted, and where each value ended up.
- For the **chips at a large font**: a screenshot, if you can.
- Anything that feels worse to use than before, even if it is "correct".
