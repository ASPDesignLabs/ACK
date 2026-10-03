# Language and vocabulary: checking it on a real phone

This covers the parts of Section 4 that are built so far: the **neutral starter phrases** (L1) and **typing, inserting and the history
chips** (the work behind them, B1 to B4). **Not built yet, so not here:** plain-language mode (L2), non-English voices and text (L3),
word prediction (L5), the profile-change warning (L7), and the pictures and core-vocabulary decisions (L4, L6). Their steps will be added
when they are built.

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

## What to send back

- For a **build failure**: the first red error.
- For a **wrong phrase, space or position**: the screen, what you typed, where the cursor was, what you tapped, what you got, and what you
  expected.
- For the **{VAR} / fallback shifting** step: the template, the values, where you inserted, and where each value ended up.
- For the **chips at a large font**: a screenshot, if you can.
- Anything that feels worse to use than before, even if it is "correct".
