# Usage summary (C1): written design

**Status: DRAFT for the developer to approve. No code for it has been written.** The tracker's "done when" for C1 asks for a written privacy design
before anything is built. This is that design. It follows the decisions made on 2026-10-06 (listed in section 1) and the rules in CLAUDE.md. Where
this page says "tested", the test is described in section 11 and is written with the code, after you approve.

## 1. What it is, and what you decided

An **opt-in, local-only count of how often and when messages are sent**, kept on the phone, shown in SETTINGS, and savable to a file the person chooses.
It never holds a word of any message.

| Decision | Your answer |
|---|---|
| Scope (DEC2) | A personal tool shared as-is. This is an off-by-default feature, never described as clinical. |
| What counts as a "kind" | **Where it came from, plus starter kinds**: a message gets a kind (YES, NO, HELP, REPAIR...) only when its words are one of ACK's own starter phrases. Everything else is OTHER. |
| Who can switch it on, and how visible | In SETTINGS. While it is on, SETTINGS says so in words **and the Terminal screen shows one quiet line**. |
| How long, how fine | **90 days**, by **day and hour of day**. |

## 2. What is recorded

One number per combination of five things. Nothing else.

| Field | Values |
|---|---|
| Date | The phone's local calendar date when the message was sent |
| Hour | 0 to 23, the phone's local hour. No minutes, no seconds |
| Channel | A fixed list (below). Never a deck's or a button's own name |
| Kind | A fixed list (below) |
| Count | How many messages |

**Channels** (read from the tag the message already carries, `OutputService`'s `source`): MATRIX (`MTX/...`, whatever the deck's name), QUICK_ACTIONS,
EMERGENCY, TERMINAL (typed at the Terminal prompt), MANUAL_OVERRIDE (`TERM/INPUT`), COMPOSER (`COMPOSER/...`), REPLAY (`LOG/REPLAY`, `CACHE/REPLAY`), WATCH
(`HW/WATCH`), SHORTCUT (`M-KEY`), PEOPLE (`COMPUTER/CONTACT`), and OTHER for any tag not on this list.

**Kinds**: YES, NO, UNSURE, HELP, REPAIR, TURN_HOLDING, NAME_OR_ID, BREAK, BOUNDARY, SOCIAL (the ten in `core/StarterSets.kt`), and OTHER.

## 3. What is never recorded

- **No message text, ever**, and no part of one. No recording id. No deck, button, profile or person's name: a `MTX/<title>` tag becomes just MATRIX.
- No place, contact, phone number, audio, device name or account. No minutes or seconds.
- **A message sent with `/n` (do not save) is not counted at all.** That switch exists so a message leaves no trace; counting it would undo that.
- Tutorial narration (the HELP guide speaking) is not counted. It is not something the person said.
- Nothing about whether a message was heard, understood or helped. A count is only a count.

## 4. How a kind is decided

When a message is counted, its words are compared **in memory** with the starter phrases ACK seeds (the 12 Matrix phrases and the 12 STARTERS buttons in
`core/StarterSets.kt`). The comparison ignores capital letters and spaces at either end and nothing else. A match gives that phrase's kind; no match gives
OTHER. The words are then thrown away: only the kind is kept.

Things to know about this, so you can say if you disagree:
- It is a match against a **closed list of ACK's own phrases**, not a guess about your words. A phrase you wrote that happens to read exactly "Yes." is counted as YES, which is what it is.
- A message typed at the Terminal that reads "Yes." is counted as YES too, because the match is by wording, not by which button sent it. (The button is not known at that point.)
- If you change a starter phrase's words, it counts as OTHER. That is the safe direction.
- The starter phrases are English. A starter you have kept as it is counts in every language.

## 5. Where it is counted

In `OutputService`, at the one place every message request arrives (both a spoken phrase and a recording bound to a slot). Once per request.

- **Counted:** a normal message, an Emergency message, a Terminal-typed message, a replay, and a message sent quiet (`/q`) or while Silent Mode is on. They were all *sent*, even if not spoken.
- **Not counted:** tutorial narration, and anything sent with `/n`.
- **It can never change what is spoken.** The count is made after the message has been handed on, on a separate background thread. If counting fails for any reason, the failure is swallowed and a fixed sentence is logged (never a message). Speech is not delayed by it.

## 6. Where it is stored

- **Its own small preference file, `ack_usage_tally`**, in ACK's private storage. One whole number per (date, hour, channel, kind). Nothing is written until the switch is on.
- **The switch** is a key in `ack_assist_prefs` (`usage_summary`), **off when nothing is stored, never seeded, never in a backup.** A new install, an existing install and a restored phone all start with it off.
- **The size is bounded.** Rows older than 90 calendar days (today and the 89 before it) are dropped as new ones are added. There is also a hard cap on the number of rows; if it were ever reached, the oldest days go first.
- **Not in EXPORT .JSON, and never restored.** It describes this phone's own use, like the backup reminder's dates. A restore leaves it alone.
- **It gets its own area in DELETE DATA** ("USAGE SUMMARY"), so the existing guard test makes sure it can be deleted and says whether it is backed up (it is not). The file is registered with the install classifier so the rest of ACK knows it is ACK's.

## 7. Turning it on, and what the person sees

- **Turning it on asks first.** A dialog says what is counted, what is never counted, that it stays on this phone, that the Terminal will show it is on, and how to save or forget it. **CANCEL is the prominent button.** Nothing is counted until the person confirms.
- **While it is on:** SETTINGS shows USAGE SUMMARY: ON in words, and the Terminal screen shows one quiet line (12 sp, no sound, no animation, nothing to tap) such as *USAGE SUMMARY IS ON: ACK COUNTS HOW OFTEN AND WHEN MESSAGES ARE SENT, NEVER THE WORDS.* It is not shown on a deck or the Emergency screen, so it can never move a button.
- **Turning it off stops counting and keeps what was counted.** It never deletes anything by itself. SETTINGS then says OFF and how many counts are still saved, with FORGET available.
- **FORGET asks twice,** CANCEL prominent, and names SAVE USAGE SUMMARY TO A FILE as the thing to do first (this data is not in EXPORT .JSON, so "back up first" means saving it to a file).

**An honest limit.** Anyone who has the phone unlocked can switch it on, read it or forget it. ACK has no app lock and the tracker decided not to add one. The line on the Terminal is there so the person using ACK can always *see* that it is on. It is not protection.

## 8. What SETTINGS shows

Plain numbers in 12 sp text, no charts and no animation:
- Totals for the kept period **by kind** and **by channel**.
- **The last 14 days, one line per day** with that day's total.
- **Totals by hour of day** (0 to 23) across the kept period.
- Today's counts are included as the day goes on.

## 9. Saving it to a file

**SAVE USAGE SUMMARY TO A FILE**, built the same way as SAVE MESSAGE LOG TO A FILE (C2): a warning first, nothing written until a place is chosen with the system picker, cancelling opens no picker, a failed save deletes the half-made file and says nothing was saved, no share sheet, no network.

- **The warning says:** what the file holds (counts by date, hour, channel and kind), that it holds **no message text**, that **it still shows when someone communicates, so it is a daily pattern and should be kept like a diary**, that it is not encrypted, that a screenshot is a copy too, and where to save.
- **The file:** header lines starting with `# ` (title, when saved, how many days it covers, what the columns are), then one line per row, oldest first, tab-separated: `DATE  HOUR  CHANNEL  KIND  COUNT`. Dates are `yyyy-MM-dd`, all digits Latin. Every value comes from a fixed list or is a number, so nothing needs escaping.
- Its name: `ack_usage_YYYY-MM-DD_HHMMSS.txt`.

## 10. How this meets the project's rules

| Rule | How it is met |
|---|---|
| No network, no cloud backup | The only way it leaves the phone is a file the person saves with the system picker. No new permission, no network code. The sovereignty tests must stay green. |
| New defaults are for new installs only | Off for everyone. Nothing is seeded or flipped. |
| Anything that changes or deletes data is confirmed first | Turning on asks. FORGET asks twice. Restore never touches it. |
| Restore is additive, never destructive | It is not in a backup, so a restore neither adds to nor removes it. |
| Every storage area is deletable and listed | Its own DELETE DATA area, enforced by the existing guard test. |
| Nothing typed or said is logged | The code writes no log line with a message. The counter has no text field. |
| 12 sp and 48 dp, no haptics near a microphone | New text is 12 sp or larger; new buttons are `NeonButton` (12 sp, not on the recording screen); nothing animates. |
| Words in six languages | String resources in English and the five drafts, with a draft notice kept. |
| Touches screen or sound = tried on a phone before Done | Checklist part C in `docs/CLINICAL_USE_DEVICE_TEST.md`, yours to run. |

## 11. What will be built, after you approve (each step is one commit)

1. **C1.2** `core/UsageTally.kt` (plain Kotlin): the record, adding one message, the 90-day window, the row cap, the hour and date rules. **There is no text field, and a test fails if one is added.** Boundary tests: exactly 90 days, one day over, midnight, the hour edge, a time-zone change, the cap.
2. **C1.3** `core/UsageKind.kt` (plain Kotlin): the channel table and the kind match. Tests: every starter phrase maps to its own kind, no two starters with the same words have different kinds, and every channel tag in the app maps to a channel.
3. **C1.4** `data/UsageTallyRepository.kt`, the switch in `AssistPrefs`/`AssistSettings`, the DELETE DATA area. Wiring tests.
4. **C1.5** One call in `OutputService`, off the speech path, skipping tutorial narration and `/n`. Wiring tests, including that a failure is swallowed.
5. **C1.6** SETTINGS > USAGE SUMMARY: the switch with its first-time dialog, the numbers, SAVE USAGE SUMMARY TO A FILE, FORGET, and the Terminal line.
6. **C1.7** Docs: CHANGELOG, `/info`, DATA_SOVEREIGNTY, TRANSLATIONS, the device checklist and CLAUDE.md.

## 12. Known limits, stated plainly

- A count says a message was sent, not that it was heard, understood or helped. It is not evidence that ACK works.
- A change of time zone, or a phone whose clock is wrong, shifts the hour buckets.
- A kind is decided by wording, so a message that means "yes" in other words is OTHER.
- It describes the phone, not the person: if a phone is shared, the counts are shared.
- It cannot be proven from here that counting never slows speech; that is a phone check.

## 13. Questions for you before I build it

1. **Replays.** The Terminal can replay a past message. Should a replay be counted (as its own channel, REPLAY, so it can be ignored when reading), or not counted at all? **My suggestion: counted as REPLAY.**
2. **The first-time dialog.** Should turning it on always ask first, with CANCEL prominent? **My suggestion: yes.**
3. **This design as a whole.** Anything above you want changed?
