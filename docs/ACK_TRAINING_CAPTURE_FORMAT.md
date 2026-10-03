<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
# ACK training capture: package format 1

This is the contract between two programs that never talk to each other directly:

* **ACK on the phone** records training clips away from your network and writes a package (a `.zip` file).
* **Freeform Studio on the PC** reads that package and turns it into recordings to review.

The file is the only thing that moves between them. You carry it yourself (cable, USB drive, local copy). Nothing in this format needs, or allows for, a network connection.

The words MUST, SHOULD and MAY are used in their usual specification sense. "Writer" means ACK. "Reader" means Freeform Studio.

An executable version of every rule marked **[reference]** lives in `tools/freeform_studio/tests/ack_capture_reference.py`, with shared test cases in `tools/freeform_studio/tests/data/ack_capture/`. The Kotlin code in ACK and the Python code in Freeform Studio MUST both reproduce those cases. If this document and the reference code disagree, that is a bug: fix both and say which was right.

## 1. Decisions this format rests on

| Decision | Consequence |
|---|---|
| Moves as a file you carry; no network code | Container is a plain `.zip` saved through the phone's file picker. No share sheet, no upload. |
| Phone never destroys audio | Script mode keeps every clip as recorded. Free mode keeps ONE whole recording and only *proposes* where to cut. The PC does the cutting, non-destructively, with word timings. |
| Hands-free capture | The phone listens for you to start and finish each card. Rules in section 7. |
| One recording per session on the PC | Freeform joins a session's clips into one recording, so review is one list. |
| Raw audio | No noise reduction, gain control, normalization or trimming on the phone. The PC export does its own levelling. |

## 2. The container

A package is a standard ZIP file, suggested name `ack-training-<YYYYMMDD>-<HHMMSS>.zip`.

Allowed entries, and nothing else:

| Entry | Meaning |
|---|---|
| `manifest.json` | UTF-8 JSON, described in section 4. Exactly one. |
| `sessions/<session_id>/clips/<NNNN>.wav` | A script-mode clip. `NNNN` is the clip's `index`, zero-padded to at least 4 digits. |
| `sessions/<session_id>/session.wav` | A free-mode recording. |
| `README.txt` | Optional, human only. Readers ignore its content. |

Folder entries for `sessions/`, `sessions/<session_id>/` and `sessions/<session_id>/clips/` MAY be present (some zip tools add them) and are ignored.

* `session_id` matches `^s\d{8}-\d{6}-[0-9a-f]{4}$` (for example `s20261002-180411-a3f9`).
* A reader MUST refuse the whole package, before writing anything, if it contains any other entry name, an absolute path, a `..` component, a backslash, a duplicate name, or a name that does not match the patterns above.
* Entries MAY be stored or deflated. A writer SHOULD deflate at level 1 (audio barely compresses and the phone should stay fast). A reader MUST accept both.
* A writer MUST keep one package under `MAX_PACKAGE_BYTES` (below 2^31, so no ZIP64 is needed) and under `MAX_ENTRIES` entries, starting another package for the remaining sessions. A reader MUST refuse more than `MAX_ENTRIES` entries, a manifest over `MAX_MANIFEST_BYTES`, or entries whose declared total size exceeds a limit it chooses (default 16 GiB), and MUST read entries as streams rather than trusting declared sizes.

## 3. Audio files

* RIFF/WAVE, PCM, 16-bit little endian, **mono**, a standard 44-byte header (no extra chunks required).
* Sample rate: `16000` to `96000` allowed. ACK records at **48000** when the phone allows it, otherwise **44100**. (Freeform decodes everything to 48000 for its own work; training later uses 22050.)
* The header's data length MUST match the file. A writer MUST repair or discard an interrupted clip before packaging. A reader MUST reject a file whose header lies about its length, naming the file.
* No processing: the samples are what the microphone delivered. The microphone source is recorded in the manifest (section 4.2), because on some phones `UNPROCESSED` is unavailable and the system may apply its own processing.

## 4. `manifest.json`

The manifest is authoritative. File and folder names exist for people browsing the zip; a reader MUST NOT parse meaning out of them beyond the checks in section 2.

### 4.1 Top level

```json
{
  "schema": "ack-training-capture/1",
  "created": "2026-10-02T18:30:00Z",
  "app": {"name": "ACK", "version": "1.0-beta.9"},
  "sessions": [ ],
  "files": [ ]
}
```

| Field | Rules |
|---|---|
| `schema` | Exactly `ack-training-capture/1`. A reader MUST refuse a different major number and say which version it understands. Unknown extra fields MUST be ignored (a later `/1` writer may add them). |
| `created` | UTC time, `YYYY-MM-DDTHH:MM:SSZ`. |
| `app.version` | Text, at most 40 characters. Shown to the user, never parsed. |
| `files` | One entry per audio file in the zip: `{"path": "...", "bytes": 1234, "sha256": "<64 lowercase hex>"}`. `path` is the zip entry name. Every audio entry MUST be listed exactly once, and every listed path MUST exist. A reader MUST verify `bytes` and `sha256` for every file **before importing anything**. |
| `sessions` | 1 to `MAX_SESSIONS` sessions. Session ids are unique. |

### 4.2 A session (both modes)

| Field | Rules |
|---|---|
| `id` | See section 2. |
| `mode` | `"script"` or `"free"`. |
| `label` | Optional text, at most 120 characters. For example `closet, phone on stand, 30 cm`. Shown as the recording's name on the PC. |
| `started`, `ended` | UTC times, as above. |
| `language` | Language code, for example `en-US`. |
| `audio` | `{"sample_rate": 48000, "source": "UNPROCESSED", "source_requested": "UNPROCESSED"}`. `source` is the microphone source actually in use (a short upper-case word); if it differs from `source_requested` the PC notes it. |
| `noise_floor_dbfs` | Number or `null`. Average level of the quiet check taken before the first clip (section 5). |
| `threshold_dbfs` | The speech threshold the phone used (section 5.2). |
| `device` | Optional `{"model": "...", "sdk": 35}`, model at most 60 characters. A writer MUST NOT put anything else about the person or phone here: no account names, no identifiers, no location, no installed apps. |

### 4.3 Script session (`"mode": "script"`)

Extra fields:

| Field | Rules |
|---|---|
| `script` | `{"id": "<1-40 of A-Z a-z 0-9 _ ->", "title": "<=120 chars", "cards_total": 120}` |
| `clips` | 1 to `MAX_CLIPS_PER_SESSION` clips, in recording order. |

Each clip:

```json
{
  "index": 14,
  "card": 14,
  "attempt": 1,
  "file": "sessions/s20261002-180411-a3f9/clips/0014.wav",
  "text": "The card text exactly as it was shown.",
  "recorded": "2026-10-02T18:09:41Z",
  "duration_s": 8.42,
  "speech": {"start_s": 0.41, "end_s": 7.96},
  "metrics": {"peak_dbfs": -4.2, "rms_dbfs": -23.1, "clipped_samples": 0},
  "flags": ["stumble"]
}
```

| Field | Rules |
|---|---|
| `index` | 1-based, unique, strictly increasing in list order. Defines the order clips are joined on the PC. |
| `card` | 1-based number of the script card the clip was recorded for. |
| `attempt` | 1-based. Greater than 1 means the person redid the card. Only the clip to keep is packaged, so a package never holds two clips for one card unless the person chose to keep both. |
| `file` | Path of the clip's WAV; must be in `files`. |
| `text` | What the card said. At most `MAX_CARD_CHARS` characters, no line breaks or control characters. This is the reference text for the clip. |
| `duration_s` | Length of the WAV in seconds, to 3 decimals. A reader compares it with the file and refuses a clip that differs by more than 0.05 s. |
| `speech` | `{"start_s", "end_s"}` as measured by section 5.3, or `null` if no speech was found. |
| `metrics` | Section 5.1. |
| `flags` | Zero or more of the words in section 4.5. |

### 4.4 Free session (`"mode": "free"`)

Extra fields:

| Field | Rules |
|---|---|
| `topic` | Optional text, at most 200 characters, what the person talked about. |
| `recording` | `{"file": "sessions/<id>/session.wav", "duration_s": 612.4, "metrics": {...}, "proposed_segments": [...]}` |

`recording.duration_s` is at most `MAX_FREE_SESSION_S`; a longer recording is stored as several sessions.

`proposed_segments` is the phone's suggestion for where this recording could be cut, from section 8. It is a **hint only**. The audio is whole, and the reader decides:

```json
{"start_s": 0.26, "end_s": 9.91, "end_kind": "pause", "metrics": {"peak_dbfs": -6.0, "rms_dbfs": -24.5, "clipped_samples": 0}}
```

Segments are in time order, do not overlap, lie inside the recording, and none is longer than `MAX_CLIP_S`. `end_kind` is `"pause"`, `"forced"` or `"end"`.

### 4.5 Flags

Optional, short, lower case. A reader MUST ignore a flag it does not know.

| Flag | Set by | Meaning |
|---|---|---|
| `noise`, `unclear`, `laugh`, `cough` | the person | Same words as Freeform's review tags. The PC turns these into review tags, which exclude the piece from training unless the reviewer clears them. |
| `stumble` | the person | Misread or false start. Shown as a warning, not an exclusion. |
| `long` | the phone | The clip is longer than `MAX_CLIP_S`. |
| `short` | the phone | The clip is shorter than `MIN_CLIP_S`. |
| `no_end` | the phone | The clip was closed because it reached `HARD_CLIP_S`, not because speech ended. |

## 5. Measurements **[reference]**

Both sides compute levels the same way, so the PC can check the phone's notes and the phone's notes mean the same as the PC's.

* **Rounding.** Wherever a number is rounded, it is rounded half away from zero (2.5 becomes 3, −2.5 becomes −3), never to the nearest even number. Negative zero is written as `0.0`.
* **Hop.** `HOP_S` = 0.010 s, which is `sample_rate` divided by 100, rounded down, in samples (480 at 48000 Hz, 441 at 44100 Hz). The last, partial hop is kept and measured over the samples it has.
* **Level of a hop**, in dB relative to full scale: `20 * log10(max(rms, 1e-9) / 32768)`, where `rms` is the root-mean-square of the hop's 16-bit samples. This is the formula Freeform's `audio.rms_envelope` uses.

### 5.1 Clip metrics

* `peak_dbfs` = `20 * log10(max(peak, 1e-9) / 32768)`, `peak` = largest absolute sample value.
* `rms_dbfs` = the same formula applied to the root-mean-square of **all** the clip's samples.
* `clipped_samples` = number of samples whose absolute value is 32767 or more.
* All three are rounded to 1 decimal (`clipped_samples` is an integer) and never below −120.0.

### 5.2 Speech threshold

`threshold_dbfs` = `THRESH_DEFAULT_DB` (−45) when `noise_floor_dbfs` is `null`, otherwise `noise_floor_dbfs + THRESH_OFFSET_DB`, limited to the range `THRESH_MIN_DB` to `THRESH_MAX_DB`.

`noise_floor_dbfs` = the level (formula above, over all samples) of a `NOISE_CHECK_S`-second stretch recorded while the person stayed quiet.

### 5.3 Speech regions and the `speech` note

A hop is "voiced" when its level is greater than the threshold. Voiced hops form runs; runs separated by fewer than `REGION_MIN_SILENCE_S` of quiet are joined; joined runs shorter than `REGION_MIN_LEN_S` are dropped. This is exactly Freeform's `audio.voiced_regions(db, HOP_S, threshold, REGION_MIN_SILENCE_S, REGION_MIN_LEN_S)`. A clip's `speech.start_s` is the start of the first region and `speech.end_s` the end of the last, to 3 decimals, or `null` if there are none.

## 6. Cutting a script into cards **[reference]**

The phone sizes the cards so that no audio ever needs cutting in script mode: one card, one clip.

Inputs: the script text, `pace_wps` (words per second; `DEFAULT_PACE_WPS` until the phone has measured the person's own pace from kept clips, then that measured pace limited to `PACE_MIN_WPS`..`PACE_MAX_WPS`), and `lines` (`"join"`, the default: a single line break is just a space and a blank line ends a paragraph; or `"keep"`: every non-empty line is its own paragraph).

1. Treat a tab as a space, then remove control characters other than line breaks. A **word** is a space-separated token (split on any Unicode white space) that contains at least one letter or number (a character whose Unicode general category starts with L or N).
2. `budget_words` = `floor(pace_wps * TARGET_S)` and `max_words` = `floor(pace_wps * MAX_EST_S)`.
3. Split each paragraph into sentences. A token ends a sentence when it ends in `.`, `!`, `?` or `…` (optionally followed by closing quotes or brackets), is not one of `mr. mrs. ms. dr. st. vs. etc. e.g. i.e. no. jr. sr. prof. gen. col.`, and the next token starts with a capital letter `A`–`Z` or a digit (optionally after an opening quote or bracket), or there is no next token.
4. A sentence of more than `max_words` words is split. Candidate cuts are after any token that leaves at least `MIN_SPLIT_WORDS` words on both sides. Prefer, in order: a token ending in `;` `:` `—` or `–`; then one ending in `,`; then any. Among equals, the cut closest to the middle; among those, the earlier. Split both halves again if they are still longer than `max_words`.
5. Pack the units in order into cards: add the next unit to the current card while the card stays within `budget_words`, otherwise start a new card. A unit longer than `budget_words` (but not more than `max_words`) becomes a card on its own. A paragraph end always ends a card.
6. A card of fewer than `MIN_CARD_WORDS` words is joined to the previous card in the same paragraph, or else the next, when the joined card stays within `max_words`.
7. A card longer than `MAX_CARD_CHARS` characters is cut at the last space at or before that length, repeatedly.
8. Each card has `text` (tokens joined by single spaces), `words`, `est_s` = `words / pace_wps` to 1 decimal (with the pace limited as in the inputs above), and warnings: `digits` if it contains a digit, `symbols` if it contains any of `& @ # % * _ = + < > { } \ / |`, `long` if `est_s` is more than `MAX_EST_S`. Cards are built within that limit for the pace they were made at, so `long` appears when the person's pace is later measured to be slower than it was assumed to be: the phone works out a card's numbers again with the same rule (`describe` in the test cases) whenever the pace changes. A person should write digits and symbols the way they will say them, because the recording's text becomes what a voice learns to pronounce.

**Measuring the person's pace.** Once at least `PACE_MIN_CLIPS` kept clips have a `speech` span, the phone's pace is the total number of words on those cards divided by the total seconds of speech in them (`end_s - start_s`), limited to `PACE_MIN_WPS`..`PACE_MAX_WPS`. Until then the default pace is used. (Phone-only; nothing on the PC depends on it.)

## 7. Hands-free capture **[reference]**

The phone stays where it is. It listens, and each card is recorded when the person starts talking and finished when they stop. The detector sees one level per hop (section 5) and works in whole hops, so there is no rounding to disagree about. Its settings are in section 11: `PRE_ROLL_HOPS` (50, which is 0.5 s), `START_RUN_HOPS` (10), `END_SILENCE_HOPS` (120), `TAIL_HOPS` (40), `NO_SPEECH_TIMEOUT_HOPS` (2000) and `HARD_CLIP_HOPS` (3000).

* **Listening.** Counts consecutive voiced hops. When the count reaches `START_RUN_HOPS`, speech has started at the first hop of that run. The clip starts `PRE_ROLL_HOPS` before that, but never before listening began (so the end of the previous clip is never included).
* **In speech.** Each voiced hop is remembered as the last voiced hop. When `END_SILENCE_HOPS` quiet hops pass after it, the clip ends `TAIL_HOPS` after the last voiced hop. If the clip reaches `HARD_CLIP_HOPS` first, it ends there with reason `max` (the clip gets the `no_end` flag).
* **After a clip,** the detector listens again at once, starting at the end of the clip. The hops between the clip's end and the moment it was closed were all quiet, so nothing is lost if the next card is started straight away, and the next clip's pre-roll can reach back no earlier than the end of the previous clip. (An earlier draft paused listening for half a second after every clip; that cut the first words off a card started promptly, so it was removed.)
* **No speech.** If `NO_SPEECH_TIMEOUT_HOPS` hops pass while listening with no speech started, the session pauses. It never spins forever.

The person can lengthen the end-of-speech wait (0.8 to 2.5 s, which is 80 to 250 hops) if they pause a lot mid-sentence. This changes only the phone's behaviour, not the package.

**Touching the phone.** The phone's buttons (REDO LAST, PAUSE, RESUME) are used while the microphone is open, and a fingertip makes a thump. After the detector is started or restarted because of a touch, the phone ignores the first 0.3 s (30 hops) of audio: it is not written, not listened to and not counted, so the card's file and the detector both begin after it. A card that follows the previous one by itself is not delayed. The phone also makes no sound and no vibration while it is listening. This is phone-only behaviour; nothing in the package or on the PC depends on it.

## 8. Proposing cuts in free speech **[reference]**

The recording is never cut on the phone. The phone computes `proposed_segments` from the speech regions of the whole recording (section 5.3) so the PC has a starting point.

* Walk the regions in order. A segment starts at the start of a region (`seg_start`).
* **Normal cut.** At the end of a region, if the segment has run at least `CUT_AFTER_S` since `seg_start` and a later region exists, end the segment there, `end_kind` = `"pause"`. The next segment starts at the next region.
* **Overshoot.** If a region would carry the segment past `FORCE_AT_S` from `seg_start`:
  1. If an earlier pause in this segment comes at least `MIN_SEG_S` after `seg_start` (measured to the end of the region before the pause), end at the **latest** such pause (`"pause"`).
  2. Otherwise cut inside the region at the **start** of the quietest hop (earliest on a tie) in the window `FORCE_AT_S − FORCE_WINDOW_S` to `FORCE_AT_S` after `seg_start`, limited to the region (`"forced"`). Cuts are always on a hop boundary, so everything stays in whole hops. The next segment starts at the cut and carries on with the rest of that region.
  3. If that window lies wholly before the region starts, end at the previous region's end instead (`"pause"`).
* The last segment ends at the last region's end, `end_kind` = `"end"`.
* **Padding.** A segment's audio runs from `PAD_LEAD_S` before its first speech to `PAD_TAIL_S` after its last, but never past the midpoint of the quiet gap to the neighbouring region, and never outside the recording. A forced cut is exact: the earlier segment ends and the later one begins at the cut time.

All times are rounded to 3 decimals. By construction no segment is longer than `FORCE_AT_S + PAD_LEAD_S + PAD_TAIL_S`, which is below `MAX_CLIP_S`.

## 9. What Freeform Studio does with it (informative)

This section describes intent. It can change without a new format version.

* Verify every checksum first. If anything is wrong, say what and change nothing.
* One recording per session. The session's clips are joined in `index` order with `GAP_S` of silence between them into one audio file, and handed to the same pipeline as a phone recording made in the browser: decode, listen for speech, transcribe, propose pieces, review, export. Free sessions use `session.wav` as is.
* Script sessions: the recording's reference text is the clips' `text` in order, so the reference-text matching in review has the card text to compare against. Each clip becomes one piece, because it was recorded on its own.
* Free sessions: `proposed_segments` are hints. The PC's own word timings decide, and its 11.5 s limit still applies.
* The PC listens again (Freeform's own level and voice checks) and compares with the phone's `speech`, `metrics` and `flags`. Disagreements become review flags rather than silent corrections.
* Importing is additive and repeatable: a session that was already imported is recognised by its `id` and skipped.
* The PC never writes anything back to the phone, and the phone never deletes a session just because it was exported.

## 10. Privacy and safety rules

* A package holds recordings of a person's voice and what they said. Treat it like the recordings themselves: `docs/DATA_SOVEREIGNTY.md` applies.
* No network address, account, location, contact or device identifier appears anywhere in a package. `device` is limited to model and Android version.
* A reader MUST NOT execute, import as code, or follow a path or URL found in a package.

## 11. Constants

These are the values both sides use. A test compares this block with the reference code, so edit them together.

```json
{
  "HOP_S": 0.01,
  "MAX_CLIP_S": 11.5,
  "MIN_CLIP_S": 1.0,
  "THRESH_DEFAULT_DB": -45.0,
  "THRESH_OFFSET_DB": 10.0,
  "THRESH_MIN_DB": -55.0,
  "THRESH_MAX_DB": -30.0,
  "NOISE_CHECK_S": 2.0,
  "REGION_MIN_SILENCE_S": 0.3,
  "REGION_MIN_LEN_S": 0.1,
  "DEFAULT_PACE_WPS": 2.6,
  "PACE_MIN_WPS": 1.5,
  "PACE_MAX_WPS": 4.0,
  "PACE_MIN_CLIPS": 5,
  "TARGET_S": 9.5,
  "MAX_EST_S": 11.0,
  "MIN_CARD_WORDS": 3,
  "MIN_SPLIT_WORDS": 4,
  "MAX_CARD_CHARS": 600,
  "PRE_ROLL_HOPS": 50,
  "START_RUN_HOPS": 10,
  "END_SILENCE_HOPS": 120,
  "TAIL_HOPS": 40,
  "NO_SPEECH_TIMEOUT_HOPS": 2000,
  "HARD_CLIP_HOPS": 3000,
  "CUT_AFTER_S": 8.0,
  "FORCE_AT_S": 11.0,
  "FORCE_WINDOW_S": 2.0,
  "MIN_SEG_S": 1.0,
  "PAD_LEAD_S": 0.15,
  "PAD_TAIL_S": 0.25,
  "GAP_S": 0.4,
  "MAX_PACKAGE_BYTES": 2000000000,
  "MAX_ENTRIES": 20000,
  "MAX_MANIFEST_BYTES": 8388608,
  "MAX_SESSIONS": 200,
  "MAX_CLIPS_PER_SESSION": 5000,
  "MAX_FREE_SESSION_S": 5400
}
```

## 12. Shared test cases

`tools/freeform_studio/tests/data/ack_capture/` holds JSON cases that both implementations must reproduce exactly:

| File | Checks |
|---|---|
| `cards.json` | `split`: script text to cards; `describe`: one card's words, estimate and warnings at a given pace (section 6) |
| `handsfree.json` | a level stream to clip boundaries (section 7) |
| `segments.json` | a level stream to proposed segments (section 8) |
| `metrics.json` | synthetic samples to metrics and speech span (section 5) |
| `manifest_example.json` | a complete, valid manifest (checksums are placeholders) |
| `fuzz.json` | about 190 generated cases (fixed seed): tricky text to cards, random level streams to clips and to proposed segments. Hand-written cases show the rules; these catch the places two implementations quietly disagree (Unicode, rounding, ties) |

Level streams are written as runs, `[seconds, level_dbfs]`, so a case is readable at a glance. Regenerate the expected values from the reference code with `python tools/freeform_studio/tests/ack_capture_reference.py --write`; the test suite fails if the files and the reference code disagree, so a change to a rule can never go unnoticed.
