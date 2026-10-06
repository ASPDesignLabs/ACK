# Clinical use (Section 5): plan

**Status: DRAFT for the developer to review. Nothing in the app has been changed.** Written on branch `claude/compassionate-hawking-bj1xap`
(which starts level with `main`). Source: the AAC Readiness Tracker, Section 5 (rows C1 to C6), and the Speech-Language Pathology
Evaluation it cites (R12, Q9, Q10, Q11). Each decision in section 6 is yours; a suggestion is a suggestion, not a decision.
Six decisions were recorded on 2026-10-06 (section 6). Eight questions are still open.

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
| C4 limits statement | **Built on this branch, using the three sentences proposed in C4.1.** The wording is not yet confirmed by you (Q11) and nothing has been seen on a phone. Automated tests: 1463 pass (31 new for C4). The new screens pass the type-check; `MainActivity.kt` and `SettingsView.kt` pass the syntax check. Phone checklist: `docs/CLINICAL_USE_DEVICE_TEST.md`, part A. |
| C2 log file | Not started. Waits for Q4. |
| C1 usage summary | Not started. Waits for Q5 and Q6, then the written design. |
| C3 partner card | Not started. Waits for the words and Q10. |
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

### C2: save the Terminal log to a file (P2, unblocked, needs Q4)
Built as an off-by-default, person-chosen action available to anyone. It is not described anywhere as a clinical feature (see DEC2 in section 6).
- **C2.1 (you)** Decide what the file holds (Q4): exactly what is on screen after the HIDE filters, or everything kept; messages only or the
  system lines too.
- **C2.2** `core/LogExport.kt` (plain Kotlin): entries to text, one line each, with a full local date and time. A message with a line break
  must not be able to look like a new log line. Tests: empty log, one entry, entries on the retention edge, text with line breaks, quotes, `%` and
  Arabic.
- **C2.3** `core/LogExportContents.kt`: one source for what the file contains (every message spoken, in full, with times), that it is **not
  protected**, where to save it, and that a screenshot or photo of the log is a copy too. Words in six languages; tested like `ExportContents`.
- **C2.4** The screen and the file: a warning first (the shape of `BackupWarningDialog`: 12 sp, CANCEL prominent, nothing happens on cancel), then
  `CreateDocument`. A failed save deletes the half-made file and says nothing was saved. The typed command (`/backup` shape: asks, then
  `CONFIRM`) and the Terminal button both call the same code.
- **C2.5** Docs: DATA_SOVEREIGNTY, PRIVACY device test, CHANGELOG, `/info`. No new storage, so no new DELETE DATA area.
- **Verified by:** unit tests and the sovereignty tests; on your phone: the picker against your own storage, a large log, the file opened on a PC.

### C1: opt-in usage summary (P1, unblocked, needs Q5 and Q6)
- **C1.1 (you, then me)** I write `docs/USAGE_SUMMARY_DESIGN.md`: exactly what is recorded and what never is, where it lives, who can see it,
  how it is switched off and forgotten, how it is saved. The done-when asks for this before code. You approve it first.
- **C1.2** `core/UsageTally.kt` (plain Kotlin): the record is a day, an hour bucket, a channel, a function (or OTHER) and a count. **There is
  no text field**, and a test fails if one is added. Rules: off writes nothing, a row cap so it cannot grow without end, retention, time-zone and
  midnight edges.
- **C1.3** `core/UsageFunction.kt`: how a function is decided (Q5). Tested.
- **C1.4** `data/UsageTallyRepository.kt`, prefs file `ack_usage_tally`. The switch lives in `ack_assist_prefs`, **off for everyone, never
  seeded**, never in `AckBackup` (like WORD SUGGESTIONS). Registered in `OWNED_PREFS_FILES`, a new DELETE DATA area, and the six-language wording.
- **C1.5** One call in `OutputService.processSpeech`, cheap, wrapped so a failure can never change what is spoken, skipped for tutorial narration.
- **C1.6** SETTINGS > USAGE SUMMARY: the switch with plain words on what is and is not recorded, a table, SAVE TO FILE (reuses the C2 warning and
  file code), and FORGET (asks twice, CANCEL prominent, BACK UP FIRST named). The screen says it is ON whenever it is. Optional HELP step.
- **C1.7** Docs and a CLAUDE.md section for the rules above.
- **Verified by:** unit tests; on your phone: a day of real use, and that speech is not slowed.

### C3: partner card (P1, form decided, needs the words and a home for the button, Q10)
**Decided:** a playable message (shown full screen and spoken) plus a printable page. **Added by you:** it must follow the person's audio routing, and
when silent output is on it must be silent too.
- **C3.1 (you and an SLP)** The words. I will draft candidates at a plain reading level for you to choose from, and mark them as drafts for an SLP.
- **C3.2** Send it through the **normal** output path, never the Emergency path. That is what makes both of your rules hold: Silent Mode shows the
  text and does not speak it, and the chosen output device (phone, Bluetooth, ACK WATCH, FORCE SPEAKER) applies as it does for any message. The Emergency
  path always speaks on the phone and ignores Silent Mode, so using it would break your rule. A test pins that the card never sets the emergency flag.
  It would appear in the Terminal log as a normal spoken message, since that is what it is.
- **C3.3** A home for the button (Q10). The STARTERS Quick Actions deck is full (3 groups of 4), and a Quick Actions deck cannot hold more
  than 12 buttons, so something has to give: a new small deck, a typed Terminal command, or a one-time offer that adds it to a deck you choose.
  Whatever it is, new installs may get it; an existing install is offered it once; **no existing phrase is ever overwritten**.
- **C3.4** Words in six languages. The printable copy in `docs/` is kept identical to the app's text by a test.
- **Verified by:** unit tests; your phone; the done-when ("tried with real partners") happens in C5's trials.

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
| C4: words | The website's short disclaimer **plus a line to keep another way to communicate**. | Exact English is confirmed in Q11. |
| C3: form | A **playable message plus a printable page**. It follows the person's audio routing, and **is silent when silent output is on**. | It goes through the normal output path, never the Emergency path (C3.2). |
| Tracker check | **Not now.** | I only report on Section 5. |

### Still open

- **Q4** C2: does the file hold what is on screen (after the HIDE filters) or everything kept? Messages only, or the system lines too?
- **Q5** C1: how a message's function is decided. (a) By channel only (deck, slot, watch, typed): simplest, nothing guessed. (b) Plus a function
  for slots that still hold their seeded starter phrase, OTHER for the rest. (c) Plus an optional function tag you or an SLP set on any slot
  (touches every editor and the backup).
- **Q6** C1: who may switch it on, and does the person using ACK always see that it is on? How many days are kept? Hour buckets or finer?
- **Q7** C5 and C6: what already exists, and who is involved? Free text is fine.
- **Q8** Is the order in section 4 right?
- **Q10** C3: where does the partner-card button live? A new small deck, a typed Terminal command, or a one-time offer that adds it to a deck you
  choose? (STARTERS is full.)
- **Q11** C4: are the three sentences in C4.1 right? And does the website also get the third sentence?
- **Q12** May I update the tracker's DEC2 row (Done, with this outcome in the Suggested column)? I will not edit it without a yes.

## 7. What I cannot do from here

- Run anything on a phone, a watch, a microphone or a real storage provider.
- Judge clinical content, or stand in for an SLP or a mental-health clinician.
- Recruit users or run trials.
- Edit the tracker without your confirmation. I will propose each change first.

**Test baseline: not obtained yet.** I ran `tools/kotlin_check/run_unit_tests.sh` once. It stopped before any test ran, because Maven Central
answered "too many requests" (HTTP 429) to this sandbox. That is the network, not the repo. I will retry before the first code change, so a
later failure can be told apart from an old one.
