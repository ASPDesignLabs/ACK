# Plain words: the label inventory (BUILT, wording still a draft for an SLP)

**Status: built and wired in (the label table is `app/src/main/res/values/strings.xml`, `label_<key>` and `label_<key>_plain`; the keys are
`core/PlainLabels.kt`).** The developer approved the wording as written. It is still a *content* draft: an SLP should edit the plain column, and
every **CHECK** row still needs a yes/no from someone who knows what the control does. The code was built and tested without an Android SDK and
never run on a phone; `docs/LANGUAGE_VOCABULARY_DEVICE_TEST.md` section J is the do-this-expect-that list.

**Decisions made (the developer's answers):** the switch is OFF for everyone; the group names are ABOUT ME / I NEED SPACE / SOCIAL; the Terminal's
send switches stay on until they are turned off (not reset after a send; kept in memory only, so closing ACK turns them off, and they act only while
PLAIN WORDS is on); EMERGENCY still never asks for confirmation. Translations (Spanish, Portuguese, Hindi, Arabic, Afrikaans) are the next step and use
this same table, one standard and one plain text per key per language.

## What this is for

ACK's own words ("Matrix", "Target Computer", "Shared Root Variables", "AUDIO ARCHITECT", "PROTOCOL") are the developer's. A first-time user
or a speech-language pathologist (SLP) without a glossary cannot tell what they do. **PLAIN WORDS** is a switch that shows an everyday
name for each, and adds a visible button for the features that today only exist as Terminal commands. Done when a first-time user can do
the eight core tasks below with no glossary.

**What you chose:** the switch is **OFF for everyone** (a new install too), with one dismissible offer in Settings that says what
changes and starts OFF. The switch sits at the top of SETTINGS, is worded **identically in both modes** so it can always be found, and
takes effect at once with no restart.

## The eight core tasks (the device checklist is measured against these)

1. Speak a saved phrase.
2. Type a statement and speak it.
3. Save a statement and find it again.
4. Change the voice.
5. Make a backup.
6. Open HELP.
7. Send an emergency phrase.
8. Use a person's or place's name inside a statement.

## How it would work (for your approval too)

- **`core/PlainLabels.kt` (plain Kotlin, tested):** a list of keys, each with its standard text and its plain text. A test fails if a key has no plain
  text, or if two different keys share the same plain text (two buttons must stay tellable apart).
- **A Compose-state switch read through a `CompositionLocal`** next to the HELP one in `MainActivity.kt`, so every screen reads it and flipping
  it redraws in place: no restart, no lost screen, no lost typed text. Not the `restartApp` pattern.
- **Display text only.** A plain label never renames an `AckTags` constant, a storage key, a deck or category id, a `[COMPUTER:..]` / `{VAR}` token
  or anything the person typed, and never changes what a button *does*.
- **HELP shows the label the person sees.** Help steps are fixed text, so a step would hold a placeholder such as `{{TARGET_COMPUTER}}` that the coach
  panel fills in from the same table; a test fails if a placeholder is not in the table. The HELP modules are not otherwise rewritten.
- **Storage:** one more preference in `ack_assist_prefs`, a nullable `AckBackup` field (a backup that says nothing leaves your own choice alone),
  mapped in the export warning under SETTINGS AND HISTORY and on the backup-fingerprint ignore list (a switch you can flip back).
- **Not changing:** the all-capitals style (about 50 `.uppercase()` calls, and the full-screen display is capitalised on purpose). All capitals are
  harder for some readers; I am raising it, not changing it.

## Things I found while reading that affect the work

- **The bottom navigation has no visible words.** It is six icons with screen-reader names only ("Matrix", "Logs", "Targets", "Zones",
  "Audio Architect", "Type"). Plain names there would help a screen-reader user but not a sighted first-time user. A visible word under each icon in
  plain mode is the obvious next step; I have **not** proposed it as part of this pass.
- **The settings screen's button is called PROTOCOL** (header, top right). A first-time user will not guess that is Settings.
- **Some of these words are stored data, not code.** The Matrix slot names ("Twist 0 (Default)", "Twist 1", ...) are stored labels, and one screen
  tests `node.label.contains("Twist 0")` (`ui/DesignSystem.kt`). A plain name for them has to be applied when the text is **drawn**, never by
  rewriting the stored label.
- **Some of these words appear in many strings** (DECK 207 times, Matrix about 370, POSE 157). The table lists what is visible on the main screens;
  the long tail (dialogs, toasts, patch notes) would move over in later small steps, the way the guide says.
- **The Terminal's `/help` text and the patch notes are English jargon text** and stay as they are in this pass.

## A. Names (standard to plain)

"Key" is the proposed `LabelKey`. "Appears" is where a person meets it. **Confidence: H** = I am sure what the control does, **CHECK** = I am guessing.

| Key | Standard text | Proposed plain text | Appears | Conf. | Note |
|---|---|---|---|---|---|
| `NAV_MATRIX` | Matrix | PHRASES | Bottom navigation (screen-reader name) | H | The first tab, the deck of phrases |
| `NAV_LOGS` | Logs | HISTORY | Bottom navigation | H | Shows what was said and done |
| `NAV_TARGETS` | Targets | PEOPLE AND PLACES | Bottom navigation | H | DELETE DATA already says PEOPLE AND PLACES for this area |
| `NAV_ZONES` | Zones | LOCATION ALERTS | Bottom navigation | H | Saved map areas that trigger things |
| `NAV_AUDIO` | Audio Architect | VOICE AND SOUND | Bottom navigation | H | |
| `NAV_TYPE` | Type | TYPE | Bottom navigation | H | Already plain; kept the same |
| `SETTINGS_ENTRY` | PROTOCOL | SETTINGS | Header, top right | H | Opens the settings screen |
| `APP_TAGLINE` | AUGMENTED COMM LINK | COMMUNICATION APP | Header | CHECK | A tagline, decorative; could simply stay |
| `DECK` | DECK | PAGE | Deck selector, MANAGE DECKS, CREATE DECK, CONFIRM DECK DELETION, many dialogs | H | "Page of buttons". Quick Actions also has its own "pages", so wording needs a check |
| `DECK_MANAGE` | MANAGE DECKS | MANAGE PAGES | Deck selector | H | |
| `DECK_CREATE` | CREATE DECK | ADD A PAGE | Deck selector, SETTINGS | H | |
| `DECK_NAME` | DECK NAME | PAGE NAME | Create deck dialog | H | |
| `DECK_TYPE_MATRIX` | MATRIX | GESTURE PHRASES | Create deck dialog, deck headers | CHECK | 12 phrases, 4 per group, picked by watch gestures or tiles |
| `DECK_TYPE_QUICK` | QUICK ACTIONS | QUICK BUTTONS | Create deck dialog, deck headers, SETTINGS | H | |
| `DECK_TYPE_EMERGENCY` | EMERGENCY | EMERGENCY | Create deck dialog | H | Already plain |
| `DECK_TYPE_EMOJI` | EMOJI | EMOJI | Create deck dialog | H | Already plain |
| `DECK_TYPE_GIF` | GIF | GIFS | Create deck dialog | H | |
| `POSE` | POSE | GROUP | Matrix and Quick Actions editors | CHECK | A set of four phrases tied to one watch pose |
| `POSE_IDENTITY` | IDENTITY | ABOUT ME | Matrix deck, Shared Variables, composer | CHECK | **Strongest content call.** The starter phrases under this group are "Yes.", "Hello.", "Please say that again.", "I am using a communication device." |
| `POSE_DEFEND` | DEFEND | I NEED SPACE | Matrix deck, Shared Variables, composer | CHECK | Starter phrases: "Stop.", "Please wait, I am typing.", "I need a break.", "I need some space." |
| `POSE_CONNECT` | CONNECT | SOCIAL | Matrix deck, Shared Variables, composer | CHECK | Starter phrases: "No.", "Thank you.", "I need help.", "Nice to meet you." |
| `TWIST_N` | Twist 0 (Default), Twist 1, Twist 2, Twist 3 | GESTURE 1 (MAIN), GESTURE 2, GESTURE 3, GESTURE 4 | Matrix slot names | CHECK | Stored labels (see above): drawn differently, never rewritten. One-based in plain mode, which is a change to confirm |
| `WATCH_POSE` | WATCH POSE | WATCH GESTURE | Quick Actions group editor | CHECK | "Which gesture on the watch fires this group" |
| `TARGET_COMPUTER` | TARGET COMPUTER | PEOPLE AND PLACES | Targets screen, composer, Quick Actions, Terminal `/t`, HELP | H | The same wording DELETE DATA already uses |
| `TARGET_ENTRY` | Target (an entry) | PERSON OR PLACE | Targets screen, pickers | H | |
| `TARGET_CATEGORY` | CATEGORY | GROUP | Targets screen (ADD CATEGORY, CATEGORY OPTIONS) | H | |
| `CONTACT_CARDS` | CONTACT CARDS | CONTACT DETAILS | Targets screen | CHECK | Phone, address, email for a person or place |
| `SHARED_VARIABLES` | SHARED ROOT VARIABLES | SHARED FILL-INS | SETTINGS, composer, Quick Actions, autocomplete manager | CHECK | The A, B and C blanks a phrase can use |
| `VARIABLE` | VARIABLE / VAR A | FILL-IN / FILL-IN A | Composer, Matrix and Quick Actions editors | CHECK | |
| `VARIABLE_CONTEXT` | VARIABLE CONTEXT | WHICH FILL-INS TO USE | Composer | CHECK | |
| `INSERT_TARGET_TAG` | INSERT TARGET TAG | INSERT A PERSON OR PLACE | Quick Actions editor, Matrix editor | H | |
| `INSERT_VARIABLE` | INSERT VARIABLE | INSERT A FILL-IN | Composer | H | |
| `BROWSE_TARGETS` | BROWSE TARGETS | BROWSE PEOPLE AND PLACES | Composer | H | |
| `MEMORY_BANKS` | MEMORY BANKS | SAVED PHRASES | Classic Manual Override | H | |
| `SAVE_TO_MEMORY_BANK` | SAVE TO MEMORY BANK | SAVE THIS PHRASE | Classic Manual Override | H | |
| `MANUAL_OVERRIDE` | MANUAL OVERRIDE | TYPE AND SPEAK (CLASSIC) | Terminal `/m`, HELP | H | See the slash-command table |
| `COMPOSER` | STATEMENT COMPOSER | WRITE A STATEMENT | Type tab | H | |
| `MY_STATEMENTS` | MY STATEMENTS | MY SAVED STATEMENTS | Composer | H | |
| `LIVE_PREVIEW` | LIVE PREVIEW | WHAT IT WILL SAY | Composer | H | |
| `AUDIO_ARCHITECT` | AUDIO ARCHITECT | VOICE AND SOUND | Audio screen, SETTINGS, DELETE CUSTOM VOICE | H | |
| `VOICE_PROFILE` | VOICE PROFILE | VOICE | Audio screen, profile menu | CHECK | A saved voice setup |
| `DSP_CHAIN` | DSP CHAIN (editor) | SOUND EFFECTS | Audio screen | CHECK | Pitch, speed, robotic and crushed effects |
| `ROBOTIC_OVERLAY` | ROBOTIC OVERLAY | ROBOT EFFECT | Audio screen | H | |
| `BITCRUSH` | BITCRUSH | ROUGH SOUND EFFECT | Audio screen | CHECK | |
| `CUSTOM_VOICE` | CUSTOM VOICE | MY OWN VOICE | Audio screen | H | |
| `RECORD_TRAINING` | RECORD TRAINING DATA | RECORD FOR MY OWN VOICE | Audio screen | H | |
| `GEO_PROTOCOL` | GEO-PROTOCOL | LOCATION ALERTS | Zones tab, SETTINGS, DELETE DATA | H | |
| `GEO_NODE` | SECURE NODES / DEPLOY NEW NODE | SAVED PLACES / ADD A PLACE | Zones tab | CHECK | |
| `GEO_GRID` | TACTICAL GRID | MAP | Zones tab | H | |
| `GEO_ENGINE` | COMPUTE ENGINE | HOW LOCATION IS CHECKED | Zones tab | CHECK | The two modes are the app's own and Google's |
| `TERMINAL` | TERMINAL | HISTORY AND TYPING BOX | Logs tab, DELETE DATA, `/help` | CHECK | It is both a log and a place to type commands |
| `TERMINAL_LOG` | TERMINAL LOG | HISTORY | SETTINGS, DELETE DATA | H | |
| `STATUSBOX` | STATUSBOX | STATUS LINE | SETTINGS (STATUSBOX TEXT COLOR), Terminal | CHECK | |
| `DATA_PORT` | DATA PORT | MY DATA | SETTINGS | H | Backup, restore, delete |
| `EXPORT_JSON` | EXPORT .JSON | SAVE A BACKUP | SETTINGS, Terminal `/backup` | H | The plain label cannot drop what the file is: the warning keeps its wording |
| `FULL_RESTORE` | FULL RESTORE FROM JSON | RESTORE FROM A BACKUP | SETTINGS, other restore buttons | H | |
| `IMPORT_MATRIX` | IMPORT MATRIX AS NEW DECK | ADD A PAGE FROM A BACKUP FILE | SETTINGS | H | |
| `SAFETY_COPIES` | SAFETY COPIES | AUTOMATIC BACKUPS | DELETE DATA, SETTINGS | CHECK | ACK makes one before a data upgrade |
| `UPLOAD_PROTOCOL` | UPLOAD PROTOCOL | SEND SETTINGS TO WATCH | SETTINGS (bottom) | H | It sends the deck list and watch settings |
| `VOX` | GUIDE VOX | SPOKEN GUIDE | SETTINGS | CHECK | "Tutorial" speech |
| `CRYO` | AUTO-CRYO | WATCH SLEEP AFTER | SETTINGS | CHECK | Idle sleep of the watch |
| `SHAKE_KILL` | SHAKE KILL SWITCH | SHAKE TO STOP SPEAKING | SETTINGS | H | |
| `ENV_SENSOR` | ENVIRONMENT SENSOR | NOISE METER | SETTINGS | H | |
| `HARDWARE_CONFIG` | HARDWARE CONFIG | WATCH AND PHONE CONTROLS | SETTINGS | CHECK | Twist, pose, crown sensitivities |
| `TWIST_SENS` | TWIST SENSITIVITY | WRIST TWIST SENSITIVITY | SETTINGS | CHECK | |
| `QUICK_ACCESS_KEYS` | QUICK-ACCESS KEYS | QUICK KEYS | SETTINGS, MANAGE RECORDINGS | CHECK | The "M-KEY" source in the log |
| `TRAIN_TEST` | TRAIN / TEST | PRACTISE | SETTINGS | CHECK | The deck trainer |
| `FORCE_SPEAKER` | FORCE SPEAKER | ALWAYS USE THE PHONE SPEAKER | SETTINGS, Emergency | H | |
| `SILENT_MODE` | SILENT MODE | SHOW ONLY, NO SOUND | SETTINGS | CHECK | |

## B. Terminal-command-only features and the visible control each now has

These existed **only** as typed Terminal commands. In plain mode each has a visible button or switch (the "Proposed control" column is what was built);
**the slash commands keep working in both modes**, and `/e` never asks for confirmation, typed or switched (this is not changed). The text on these
controls is in `strings.xml` as `plain_ctl_*` (single strings, because they exist only in plain mode); the code is `ui/TerminalPlainControls.kt`.

| Command | What it does | Already has a visible control? | Proposed control in plain mode |
|---|---|---|---|
| `/m` | Opens classic Manual Override | No | A button on the Type tab: TYPE AND SPEAK (CLASSIC) |
| `/cls` | Clears the log (asks `/cls CONFIRM`) | Partly: DELETE DATA > TERMINAL LOG deletes it, asking twice | A CLEAR HISTORY button on the Logs screen that opens the same two-step confirmation |
| `/repair` | Restarts the two background services, no confirmation | No | A FIX PROBLEMS (RESTART ACK'S BACKGROUND PARTS) button in SETTINGS, no confirmation, as the command |
| `/info` | Shows the patch notes line by line | No | A WHAT'S NEW button on the Logs screen |
| `/b`, `/backup` | Export a backup | **Yes**: EXPORT .JSON in SETTINGS > DATA PORT | None needed; the plain label SAVE A BACKUP |
| `/q` | Send without sound | No | A SEND QUIETLY switch beside the Terminal's text box |
| `/n` | Send without saving to the log | No | A DO NOT SAVE IN HISTORY switch beside the text box |
| `/s` | Send and hold the message until cleared | No | A KEEP ON SCREEN UNTIL I CLEAR IT switch beside the text box |
| `/e` | Send with emergency settings | No | An EMERGENCY switch beside the text box. **It stays on until switched off (your answer), like the other three**; still no confirmation |
| `/v`, `/t` | Browse Shared Variables / Target entries from the Terminal | The composer has INSERT VARIABLE and BROWSE TARGETS; the Terminal does not | Two small buttons beside the Terminal's text box |

Four of these (`/q`, `/n`, `/s`, `/e`) change **how a message goes out**. You chose that they **stay on until switched off**, so the switch is made
visibly on while it is on: ON is written in words and the border is thicker, and the closed SEND OPTIONS row names every switch that is on. They are
kept in memory only (they survive a send and leaving the screen, not closing ACK; nothing is stored, wiped or backed up) and they act only while
PLAIN WORDS is on, because a switch that cannot be seen must not make a message silent, unsaved or loud by accident. Turning PLAIN WORDS off turns
them off.

## C. What I needed from you (answered, except where noted)

- **Open:** edit the **Proposed plain text** column with an SLP. Every **CHECK** row needs a yes/no from someone who knows what the control does.
- **Answered:** the group names are **ABOUT ME / I NEED SPACE / SOCIAL**. **Still open:** the starter phrases were placed by gesture position, so the
  groups do not line up with any plain name (for example "No." sits under CONNECT and "Yes." under IDENTITY). Plain group names make that visible, so the
  group names and the starter placement (docs/STARTER_PHRASES.md) are best decided together.
- **Built as written:** the Matrix slot names are one-based in plain mode (GESTURE 1 (MAIN), GESTURE 2 ... GESTURE 4); the stored names do not change.
  Say if you want them different.
- **Answered:** the switch buttons are built, and they stay on until switched off (see section B).
- **Not built, not proposed in this pass:** a visible word under each bottom-navigation icon. The plain names are the screen-reader names for now.
