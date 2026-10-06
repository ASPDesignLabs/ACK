# Clinical use (Section 5): plan

**Status: in progress.** C4, C2, C1 and C3 are built on branch `claude/compassionate-hawking-bj1xap` (none yet tried on a phone); C5 and C6 wait on Q7. Written on that branch
(which started level with `main`). Source: the AAC Readiness Tracker, Section 5 (rows C1 to C6), and the Speech-Language Pathology
Evaluation it cites (R12, Q9, Q10, Q11). Each decision in section 6 is yours; a suggestion is a suggestion, not a decision.
Twenty-three decisions are recorded (section 6). Three questions are still open (Q7, Q8, Q12).

## 1. What Section 5 asks for

| ID | Goal | Priority | Tracker status | What the repo says today |
|---|---|---|---|---|
| C1 | Opt-in, local-only usage summary, savable to a file the person chooses | P1 | Needs decision | Nothing exists. No counts of any kind. |
| C2 | Save the Terminal log to a chosen file, with the backup's warning | P2 | Needs decision | Nothing exists. The log cannot leave the app. |
| C3 | Partner card, shown on request | P1 | Not started | Nothing exists. HELP is for the person using ACK, not for the people talking with them. |
| C4 | Limits statement in the app's first-run or About text | P2 | Not started | **Not in the app.** It is on the website, in the README and in the release notes only. There is no About screen and no first-run text. |
| C5 | Outside feedback: two or more users, one an SLP, supervised trials | P1 | In progress | Mostly not code. No trial pack, record sheet or feedback route in the repo. |
| C6 | Guidance on situational or selective mutism (bridge versus avoidance) | P2 | In progress | Not in the repo. Needs an SLP and a mental-health clinician to write it. |

## 2. Findings that shape the plan

1. **C4 is a real task, and the smallest.** The wording already exists in three places (README; `index.html` twice; the beta.8 release
   notes). It has to reach the app, in all six languages, and stay the same as the website.
2. **What the Terminal log holds.** Up to 400 entries, kept 7 days by default (1 to 30), in `ack_prefs`, key `TERMINAL_LOG_ENTRIES`
   (`data/TerminalLogStore.kt`). Every spoken message is in it **in full**, with its time and where it came from. It is *not* in EXPORT
   .JSON (it is its own DELETE DATA area, "not backed up"). So a log file (C2) is a new way for the text of what someone said to leave the
   phone. It needs the same care as the backup, and the person should know that.
3. **A summary (C1) can avoid carrying any message text. A log file (C2) cannot.** That was the real choice between them; you chose to build both (section 6).
4. **There is one place to count from.** Every spoken message goes through `OutputService.processSpeech`, which already receives a source tag
   (`EMERGENCY`, `QUICK_ACTION`, `MTX/<name>`, `M-KEY`, `HW/WATCH`, `LOG/REPLAY`, `COMPUTER/CONTACT`, the composer, the Terminal prompt, and
   `HELP/<id>` for tutorial narration, which must not count). Counting there covers the watch, the lock screen and every deck at once.
5. **"Message functions" are not recorded anywhere.** The evaluation's checklist wants request, refuse, greet, break, repair. ACK only knows
   a function for the seeded starter phrases (`StarterFunction` in `core/StarterSets.kt`). A phrase the person wrote has none, and guessing from
   free text would be wrong too often. This is decision Q5.
6. **Other rows these depend on.** D3 (install guide and one-page SLP handout, Not started) is where C6's note is meant to be published
   and overlaps C5's setup guide. D1 (support policy) decides where feedback goes. The trial rows should not start with a client until
   the P0 rows are done **and tried on a real phone** (your working rule 4). DEC2 (scope) gated C1 and C2; it was answered on 2026-10-06
   (section 6), so both are unblocked.
7. **The tracker looks behind the code.** CLAUDE.md describes S1 to S7, P1, P5, P6, L1, L2, L3, L5 and L7 as built, but the tracker still says
   "Not started" or "Needs decision". I have not checked each against the code. "Built" is not "Done" (no phone check yet). You said not now
   to checking them (section 6); I only report on Section 5.

## 3. Rules that apply to every task below

From CLAUDE.md and the tracker's working rules. If a task seems to need to break one, stop and ask.

- No network permission, no network code, no cloud backup. `tools/freeform_studio/tests/test_sovereignty_policy.py` stays green. Saving a file is **only** through
  the system file picker (`CreateDocument`), never a share sheet.
- Anything that changes a stored default, migrates or deletes data is confirmed first, with a backup step before it. Restore stays additive.
- New defaults reach new installs only. An existing install gets an offer once, never a silent change.
- New stored data is registered where the repo's tests force a decision: `InstallState.OWNED_PREFS_FILES`, `core/StorageCatalogue.kt`
  (DELETE DATA), `core/ExportContents.kt` if it is in EXPORT .JSON, and `BackupFingerprint.IGNORED_FIELDS` if it grows with use.
- Words are string resources in English and the five drafts (es, pt, hi, ar, af), with the draft notice kept. New controls: 12 sp or larger,
  48 dp, no haptics, no animation. A person's own text is never used as a format.
- Decisions go in plain Kotlin in `core/` with boundary tests (exactly the limit, one under, one over). Break the code on purpose once and
  watch a test fail. Android-only files get `tools/kotlin_check/run_syntax_check.sh` (`syntax errors: 0`).
- **Nothing that touches the screen, microphone, watch or sound is Done until it has been tried on a real phone.** I cannot do that from
  here. Every task below says what is left for a device.
- Every GPL source file carries `SPDX-License-Identifier: GPL-3.0-or-later`.
- No clinical claim without evidence. The evaluation says no evidence yet shows ACK helps; nothing we write may say or imply that it does.
- Each task is one reviewable commit. I propose the change and you confirm before I commit or push. When a row is Done, its evidence (commit,
  test or device check) goes after its criterion in the tracker.

## 4. Suggested order and why

1. **C4** first. Small, no dependency, and it states the limits before anything else here exists.
2. **C2** next (your answer: cheaper one first). It stores nothing new. It also writes the warning dialog and the file-saving code that C1 reuses.
3. **C1** after C2. It needs a written design (C1.1) that you approve before any code.
4. **C3** once its words are agreed and its home in the app is chosen (see C3).
5. **C5 and C6** run alongside as document work. They need people, not code, and C5 feeds back into C3 and the tracker.

This order is a suggestion (Q8). Nothing is blocked on a decision any more except where a task below says "you decide".

## Progress

| Task | State |
|---|---|
| C4 limits statement | **Built and pushed. Wording confirmed by you; the website now carries the third sentence too.** Not yet seen on a phone (C4.5 is yours). Phone checklist: `docs/CLINICAL_USE_DEVICE_TEST.md`, part A. |
| C2 log file | **Built on this branch, not yet seen on a phone** (C2.6 is yours). Messages only, saved from a SETTINGS button. 1526 automated tests pass (63 new for C2); the dialog passes the type-check; `SettingsView.kt` and `LogExporter.kt` pass the syntax check. Ten deliberate breaks were each caught by a test. Phone checklist: part B. |
| C1 usage summary | **Built on this branch, not yet seen on a phone** (C1.8 is yours). Design approved as written (`docs/USAGE_SUMMARY_DESIGN.md`). Off for everyone; turning on asks first; counts only, never a word. Phone checklist: part C. |
| C3 partner card | **Built on this branch, not yet seen on a phone** (C3.6 is yours). Words chosen by you (option C), all six languages drafted. Header icon next to HELP, asks first, normal output path, shows in full. Phone checklist: part D. |
| C5, C6 | Not started. Wait for Q7. |

## 5. Tasks

### C4: limits statement in the app (P2)
**Decided:** a permanent ABOUT section in SETTINGS plus a one-time dismissible banner. Words: the website's short disclaimer plus one line to keep
another way to communicate available.
- **C4.1 (you)** Confirm the exact English. My proposal, the website's two sentences unchanged and one new sentence:
  *"Not a substitute for professional AAC evaluation or speech-language therapy. Built by one person as a personal tool, shared as-is.
  Keep another way to communicate available at all times."*
- **C4.2** Add the statement as string resources in English and the five drafts. Add a test that keeps the first two sentences the same as the
  website's disclaimer (the same idea as `StarterPhrasesDocTest`), so the two cannot drift. The third sentence is new, so the website gets it too (a
  separate edit to `index.html` that you confirm).
- **C4.3** Show it. A permanent ABOUT section in SETTINGS, and a one-time dismissible banner in the shape of `HelpOfferBanner`,
  shown on the Terminal and Settings screens only, never on a deck or Emergency screen where it could move a button about to be tapped. Dismissing
  only flips a flag. It never blocks speech and never asks anything. An existing install sees the banner once too (it changes no setting).
- **C4.4** CHANGELOG, a `/info` note (English first), the device-test line, the tracker evidence.
- **Verified by:** unit tests, syntax check, then your phone: read it at large font, check no button moves, check dismissal sticks.

### C2: save the Terminal log to a file (P2, built, waiting on a phone check)
Built as an off-by-default, person-chosen action available to anyone. It is not described anywhere as a clinical feature (see DEC2 in section 6).
**Decided:** messages only (normal and Emergency), and a button in SETTINGS only: no typed command and no Terminal button.
- **C2.1 (you)** Done: the file holds only messages, with date, time and where each was sent from. System, path-trace and command lines are left out.
- **C2.2** `core/LogExport.kt` (plain Kotlin): messages only, oldest first, one line each, four tab-separated columns, the time in this phone's local time with its UTC
  offset on every line and in Latin digits, and every line break, tab and backslash in a message escaped so a message can never look like a new line. Only messages the
  retention window still keeps. 35 tests, including a seeded fuzz of 3,000 strings.
- **C2.3** `core/LogExportContents.kt`: one source for the warning (the count, what the file holds, what it does not, not protected, a screenshot is a copy too, where to save).
  Its two safety sentences are the EXPORT .JSON warning's own. Words in six languages (drafts). 10 tests.
- **C2.4** `data/LogExporter.kt`, `settings/LogExportDialog.kt` and one button under the retention slider in SETTINGS. Warns first, saves nothing until a place is chosen with the
  system picker (`CreateDocument`), cancelling opens no picker, an empty log shows a line and no button, a failed save deletes the half-made file and says nothing was saved,
  nothing said is ever logged, reading the log changes nothing. 17 wiring tests.
- **C2.5** Docs done: DATA_SOVEREIGNTY, CHANGELOG, `/info` (six languages), TRANSLATIONS, CLAUDE.md, device-test part B. No new storage, so no new DELETE DATA area.
- **C2.6 (you)** The phone check: the picker against your own storage, a failed save, a large log, the file opened on a PC.

### C1: opt-in usage summary (P1, built, waiting on a phone check)
**Decided:** a kind is decided by where the message came from plus ACK's own starter kinds (OTHER for anything else); switched on in SETTINGS with a quiet line on the
Terminal while it is on; kept 90 days, by day and hour of day; a replay is counted (as REPLAY); turning it on always asks first. The full design, with what is and is never recorded, is `docs/USAGE_SUMMARY_DESIGN.md`.
- **C1.1** Done: the written design. **Approved by you as written** (its three questions are answered in its section 13).
- **C1.2** `core/UsageTally.kt` (plain Kotlin): the record is a date, an hour, a channel, a kind and a count. **There is no text field**, and a test fails if one is added.
  Off writes nothing; a 90-day window; a row cap; time-zone and midnight edges.
- **C1.3** `core/UsageKinds.kt`: the channel table and the kind match against the starter phrases. A test reads the app's source and fails on a source tag the table does not know (it found the saved Manual Override phrases' `BANK/...` tag).
- **C1.4** `data/UsageTallyRepository.kt`, prefs file `ack_usage_tally`. The switch lives in `ack_assist_prefs`, **off for everyone, never seeded**, never in `AckBackup`. Registered in
  `OWNED_PREFS_FILES`, a new DELETE DATA area, and the six-language wording.
- **C1.5** One call in `OutputService` where a message request arrives, off the speech path, so a failure can never change what is spoken. **A message sent with `/n` is not counted;
  nor is tutorial narration.**
- **C1.6** SETTINGS > USAGE SUMMARY: the switch with a first-time dialog, the numbers, SAVE USAGE SUMMARY TO A FILE (reuses the C2 flow), FORGET (asks twice), and the Terminal line.
- **C1.7** Docs done: CHANGELOG, `/info` (six languages), DATA_SOVEREIGNTY, TRANSLATIONS, CLAUDE.md, device-test part C. The DELETE DATA list is now thirteen areas.
- **C1.8 (you)** The phone check (part C): turning on and cancelling, the Terminal line, what gets counted and what does not, the saved file opened on a PC, forgetting, and that speech is not slowed.
- **Verified by:** unit tests and thirteen deliberate breaks, each caught by a test; on your phone: a day of real use, and that speech is not slowed.

### C3: partner card (P1, built, waiting on a phone check)
**Decided:** a playable message (shown full screen and spoken) plus a printable page. It follows the person's audio routing, and when silent output is on it is silent too. **The button lives in the header, in the slot next to HELP, with the backup
reminder's save icon moved to its left.** A tap asks first; the icon is about 24 dp; it is always shown. **The words are option C** (your choice from three drafts).
- **C3.1** Done: the words. *I use this app to talk. I can hear you and I understand you. Please wait while I answer. Please do not take my phone. If you are not sure what I need, ask me and I will show you.* They are drafts for a speech-language
  pathologist; the five translations are drafts for a native speaker, written to avoid verb forms and words that depend on anyone's gender.
- **C3.2** `core/PartnerCard.kt` (plain Kotlin) and the six-language words. The card is sent through the **normal** output path, never Emergency (a test fails on the word "emergency" in the sender), so both of your rules hold. 12 tests.
- **C3.3** The header icon (`ui/PartnerCardButton.kt`), the question that asks first (CANCEL prominent, shows the exact words), and `output/PartnerCardPlayer.kt`. The save icon keeps its own reserved slot to the left, so the header is about 28 dp wider on every screen.
- **C3.4** **One engine change you did not ask for, and why:** `OutputService` takes a `full_text` request that makes the screen show the whole message whatever the preset says. Without it, a phone whose preset still cuts long messages would show "ALERT:" and
  three words while speaking all five sentences. Only the card asks for it; every other message is unchanged. It travels through the speech queue too, and a test pins both routes.
- **C3.5** Printable page `docs/PARTNER_CARD.md` (all six languages), kept identical to the app by a test. CHANGELOG, `/info` (six languages), TRANSLATIONS, CLAUDE.md and device-test part D done. The usage summary counts the card as its own place.
- **C3.7** Added at your request: **each sentence can be switched on or off in the question (ON/OFF in words, remembered), there are two slots for sentences of your own (up to 200 characters, said exactly as written, never translated), and every play is logged with the kind
  PARTNER CARD.** This is the first part of the card that stores anything, so it has its own file (`ack_partner_card`), is in EXPORT .JSON (named in its warning), is wiped by DELETE DATA > MESSAGES AND DECKS, and a restore only fills empty slots. Settings and backup rules are
  in `core/PartnerCardSettings.kt`; 27 tests of the rules and 19 wiring tests, and fifteen deliberate breaks each caught. It also found and fixed a real gap (a "next line" character joined two words).
- **C3.6 (you)** The phone check (part D, now longer): the header on your smallest phone, the bubble as a tap target, that PLAY IT shows all five sentences, **whether about 10 seconds on screen is long enough to read them**, Silent Mode, your output devices, Arabic.
- **Verified by:** unit tests and thirteen deliberate breaks, each caught by a test; the type-check covers the icon file. The done-when ("tried with real partners") happens in C5's trials.

### C5: outside feedback (P1, in progress, mostly people)
Because the scope is "personal tool, shared as-is" (DEC2), the pack is framed as *trying ACK with a clinician*: for people who choose to try
a personal tool and give feedback. It is not described as a pilot programme or a clinical service.
- **C5.1 (you)** Tell me what already exists (Q7).
- **C5.2** I draft `docs/TRYING_ACK_WITH_A_CLINICIAN.md`: who it suits (candidacy decided first with the clinician's own tools), when to start (P0
  rows done and device-tested, another way to communicate always available), setup, the eight things the evaluation asks to record, consent notes
  (voice cloning separately), when to stop.
- **C5.3** A one-page record sheet that **stays outside ACK**, with the clinician. "Written reports are kept with each trial's results" is
  met by the clinician keeping them, not by anything in the app.
- **C5.4** A feedback route that never needs client data. GitHub issues are public, so the pack says to never put client details in one. A
  private route is your decision (D1).
- **C5.5 (you)** Recruit, run the trials, collect the reports. I cannot do this.
- **C5.6** Afterwards I turn the findings into new tracker rows and bring DEC2 back to you with what was learned.

### C6: mutism guidance (P2, in progress, needs clinicians)
- **C6.1 (you)** Tell me what exists and who is writing it (Q7).
- **C6.2** I prepare, and you pass on: (a) a **factual** list of what ACK does that bears on bridge versus avoidance, each line checked against the
  code; (b) a question list for the SLP and the mental-health clinician; (c) an empty skeleton marked "clinician to complete".
- **C6.3** The clinical content is written by the clinicians. I will not write treatment advice.
- **C6.4** Publish it with D3's install guide. D3 is not started, so until then it goes in `docs/` and the README points to it.
- **C6.5** Check the wording makes no claim about effect.

## 6. Decisions

### Decided (2026-10-06)

| Topic | Decision | What follows from it |
|---|---|---|
| DEC2: scope | **Personal tool, shared as-is.** C1 and C2 are still built, as off-by-default, local-only features the person chooses. | Nothing in the app or the docs calls ACK a clinical or pilot tool. The tracker's DEC2 row still says "Needs decision" until you confirm an update (Q12). |
| What can leave the phone | **Both**, only when the person chooses to save a file. The cheaper one first. | C2 (message text) is built first, then C1 (counts, no text). |
| C4: where | An **ABOUT section** in SETTINGS plus a **one-time banner**. | Banner on the Terminal and Settings screens only; dismissing only flips a flag. |
| C4: words | The website's short disclaimer **plus a line to keep another way to communicate**. **Confirmed as built.** | The website got the third sentence too, in its own commit. A test keeps the app and the page identical. |
| C2: contents | **Messages only** (normal and Emergency), with date, time and where each was sent from. | System, path-trace and command lines are never written. |
| C2: how it is reached | **A button in SETTINGS only.** | No typed command and no Terminal button. A test fails if either appears. |
| C3: form | A **playable message plus a printable page**. It follows the person's audio routing, and **is silent when silent output is on**. | It goes through the normal output path, never the Emergency path (C3.2). |
| Tracker check | **Not now.** | I only report on Section 5. |
| C1: kinds | **Where it came from, plus ACK's own starter kinds** (YES, NO, HELP, REPAIR...), OTHER for everything else. | A message's words are compared in memory with the starter phrases and thrown away. Nothing is guessed. |
| C1: switching on | **In SETTINGS, plus a quiet line on the Terminal while it is on.** | A person using ACK can always see it is on. The design adds a first-time confirmation. |
| C1: keeping | **90 days, by day and hour of day.** | Old rows are dropped as new ones are added; a hard row cap bounds the size. |
| C3: where the button lives | **The header slot where the backup reminder's save icon shows**, with the save icon moved to its left. | See C3.3: the header gets about 28 dp wider, and a tap target and an accidental tap need deciding (Q13 to Q15). |
| C1: the design | **Approved as written** (`docs/USAGE_SUMMARY_DESIGN.md`). | It was then built. |
| C1: replays | **Counted, as their own channel, REPLAY.** | A reader can ignore them. |
| C1: turning it on | **Always asks first, with CANCEL prominent.** | Nothing is counted until the person confirms, every time it is turned on. |
| C3: a tap | **Asks first** (CANCEL prominent). | An accidental tap cannot speak a long message. |
| C3: tap area | **About 24 dp, like its neighbours.** | The header does not grow taller. Needs a small-screen phone check. |
| C3: hiding the icon | **No switch: it is always shown.** | One less setting; the icon is a normal output, not an alarm. |
| C3: the words | **Option C**: five sentences, with a request not to take the phone and an offer to show what you need. | Drafts for a speech-language pathologist; `docs/PARTNER_CARD.md` holds all six languages. |
| C3: choosing what it says | **Each sentence has its own ON/OFF in the question, so one sentence can be said alone.** I chose to **remember** the choice (otherwise it would have to be re-ticked every time); the question always shows it. | With every sentence off there is no PLAY IT, only a line saying to turn one on. |
| C3: your own sentences | **Two slots**, up to 200 characters, said and shown exactly as written (tidied to one line, with a full stop added if there is no sentence ending). | Never translated or reworded. Starts on when written. Clearing asks a second time. |
| C3: where your sentences live | Their own file, **in EXPORT .JSON** (named in its warning), **wiped with MESSAGES AND DECKS**. A restore **only fills empty slots** (my choice: it can never overwrite a sentence you wrote since). | The ON/OFF choices stay on the phone and are not in the backup. |
| C3: how a play is logged | **The kind is `partner_card`**, set by the tag, never by the words; **one play is one message** however many sentences were on. | The channel is still PARTNER CARD too, so a reader sees both. Say if you want the channel dropped. |

### Still open

- **Q7** C5 and C6: what already exists, and who is involved? Free text is fine.
- **Q8** Is the order in section 4 right?
- **Q12** May I update the tracker's DEC2 row (Done, with this outcome in the Suggested column)? I will not edit it without a yes.

Answered on 2026-10-06 and moved to the table above: Q13 (a tap asks first), Q14 (about 24 dp), Q15 (no hide switch), Q16 (C1 design approved, with its two suggestions).

## 7. What I cannot do from here

- Run anything on a phone, a watch, a microphone or a real storage provider.
- Judge clinical content, or stand in for an SLP or a mental-health clinician.
- Recruit users or run trials.
- Edit the tracker without your confirmation. I will propose each change first.

**Test baseline.** Before any change on this branch, `tools/kotlin_check/run_unit_tests.sh` reported 1431 tests, 0 failed (the first attempt stopped on a Maven Central HTTP 429, which is the sandbox's network, and passed on retry). After C4, C2 and C1 it reports **1612 tests, 0 failed**; `run_typecheck.sh` passes; the Android-only files pass `run_syntax_check.sh`; the license and sovereignty policy tests pass. None of this runs the Android build or a phone.
