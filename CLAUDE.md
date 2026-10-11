# ACK — Project Memory

ACK is an Android AAC (augmentative and alternative communication) app.
This file accumulates durable, cross-session knowledge about subsystems
that are easy to re-break if reimplemented from a shallow read. Add to it
rather than replacing it.

## The HELP System — deep analysis

HELP is ACK's in-context walkthrough system: guided, stepped tutorials
that run *over* the real UI (highlighting real controls, waiting for real
taps) rather than a static help document. Everything lives under
`app/src/main/java/com/example/besu/help/`, plus one top-level file,
`app/src/main/java/com/example/besu/AckTags.kt`.

### Core data model — `help/HelpCore.kt`

- **`HelpCategory`** — enum of module families, constants only. Its words
  are string resources named `help_cat_<constant in lower case>_title` /
  `_chip` / `_subtitle`, read through `core/HelpMenuText.kt`. Drives the
  chip row in `HelpMenuDialog` (`HelpCategory.values().forEach { ... }`).
  **Adding a case needs those three strings in `values/strings.xml` and
  all five translations**; `HelpMenuTextTest` fails otherwise.
- **`HelpDestination`** — enum wrapping a `viewMode` string
  (`"MATRIX"`, `"SETTINGS"`, `"TYPE"`, `"TERMINAL"`, `"AUDIO"`,
  `"TARGETS"`, `"GEO"`). This is what a module/step asks MainActivity to
  navigate to before showing that step. `"MATRIX"` is the view mode for
  *any* deck-shaped screen — Matrix, Quick Actions, Emergency, Emoji,
  GIF — the actual deck **type** shown is whatever `currentDeckType()`
  currently is; switching `viewMode` to `"MATRIX"` does not by itself
  change which deck is active.
- **`HelpAction` / `HelpEvent`** — a deliberately mirrored pair of sealed
  interfaces. `HelpAction` describes what a *step* is waiting for
  (`Read`, `Interact(targetTag)`, `CommitText(targetTag)`,
  `CommitFile(targetTag)`, `OverlayCleared(targetTag)`,
  `WatchEvent(eventType)`, `DeckSelected(targetTag)`,
  `ProfileSelected(targetTag)`, `KeyboardDismissed(targetTag)`).
  `HelpEvent` is what real UI code *reports happened*
  (`Interacted`, `TextCommitted`, `FileCommitted`, `OverlayWasCleared`,
  `WatchInput`, `DeckWasSelected`, `ProfileWasSelected`,
  `KeyboardWasDismissed`). `HelpManager.matches()` pairs them up by type
  + exact `targetTag`/`eventType` string equality — nothing fuzzy.
- **`HelpStep`** — `id` (unique *within its module only* — `"intro"` and
  `"complete"` are reused by nearly every module, that's normal),
  `title`, `body`, `action` (defaults to `HelpAction.Read`), `targetTag`
  (optional — drives the *visual* pulse highlight, independent of
  `action`), `destination` (optional per-step override), `coachPlacement`
  (`TOP`/`BOTTOM`, defaults `BOTTOM`).
- **`HelpModule`** — `id` (must be **globally unique** — this is the
  registry lookup key), `category`, `title`, `summary`, `steps`,
  `destination` (module-level fallback), `requiresMatrixDeck` (see
  below).
- **`LocalHelpManager`** — a `staticCompositionLocalOf<HelpManager?> { null }`,
  provided once at the very root in `MainActivity.kt`
  (`CompositionLocalProvider(LocalHelpManager provides helpManager)`
  wrapping the whole `Scaffold`). Because of this, **`LocalHelpManager.current`
  is available in every composable in the app with zero prop-threading** —
  any screen, dialog, or shared component can read the current step or
  dispatch an event just by calling `LocalHelpManager.current`.

### State machine — `help/HelpManager.kt`

A single `HelpManager(modules: List<HelpModule>)` instance, created once
via `remember { HelpManager(HelpRegistry.modules) }` in MainActivity.
Exposes `activeModule`, `currentStepIndex`, `currentStep`, `isActive`,
`destinationRequest`, `completedCategory` — all `mutableStateOf`, so
Compose recomposes anything reading them.

- `start(moduleId)` — looks the module up by id in its fixed list; if
  found, resets to step 0 and sets `destinationRequest` from the first
  step's destination, falling back to the module's.
- `advanceReadStep()` — only moves forward if the current step's action
  is exactly `HelpAction.Read`. This is what the coach panel's
  "ACKNOWLEDGE // CONTINUE" button calls.
- `onEvent(event)` — if `matches(currentStep.action, event)`, advance.
  Real UI code calls this on every relevant tap/commit; it's a no-op if
  the event doesn't match what the active step is waiting for (including
  when no module is active at all — always safe to call unconditionally
  via `helpManager?.onEvent(...)`).
- `next()` — advances the index, or calls `complete()` if it was the
  last step. Also updates `destinationRequest` for the new step.
- `abort()` — hard reset (used by the coach panel's `[ABORT]` and by
  MainActivity when intercepting a module id for bespoke UI instead of
  running it as steps).
- `destinationHandled(destination)` / `completionHandled()` — consumed
  by MainActivity's effects below to clear one-shot state.

### Visual targeting — `help/HelpTarget.kt`

`AckHelpShape` (a shared `CutCornerShape`, reused everywhere in the app
as the house corner-cut aesthetic, not just for HELP) and
`Modifier.helpTarget(tag, primaryColor)`: a **`@Composable` extension
function**. It reads `LocalHelpManager.current?.currentStep?.targetTag`;
if it doesn't equal `tag`, it returns `this` completely unchanged (true
no-op, no recomposition cost when HELP isn't running). If it matches, it
adds an infinitely-repeating pulsing background+border in `primaryColor`.

Because it's `@Composable`, it can only be called from composable
context — always chained directly on a `Modifier` argument, e.g.
`Modifier.weight(1f).testTag(AckTags.X).helpTarget(AckTags.X, primaryColor)`.
The convention is always `.testTag(tag)` immediately followed by
`.helpTarget(tag, primaryColor)` — `testTag` for prospective UI testing,
`helpTarget` for the live highlight — both keyed off the *same* constant.

**Important: `targetTag` and `action`'s tag are independent.** A step can
set `targetTag` for a highlight without gating on it (action stays
`Read`, e.g. the `identity_root` step in `MatrixDeckHelp` just highlights
`MATRIX_ROOT_IDENTITY` while explaining it) — or gate on interaction
without necessarily being the only thing highlighted. In practice nearly
every gating step also sets the same tag as both `action`'s payload and
`targetTag`, but they don't have to match.

**A tag can be shared by multiple simultaneous on-screen instances** —
e.g. every leaf card in ManageRecordingsDialog's tree carries the same
`AckTags.VOICE_REC_MANAGE_LEAF` tag, so a Read step targeting it pulses
*all* visible leaves at once ("here's what these look like"), and an
Interact-gated step on a list-item action tag is satisfied by tapping
*any* matching instance ("try this on any row"). This is a deliberate,
useful pattern for list/tree UIs, not a bug to avoid.

### Tag registry — `AckTags.kt`

One flat `object AckTags` in the **top-level** `com.example.besu` package
(not `com.example.besu.help`), all `const val NAME = "NAME"`,
`SCREAMING_SNAKE_CASE`, string value identical to the constant name.
Single source of truth — every `.helpTarget()`/`HelpAction`/`HelpEvent`
call across the whole app references a constant from here, never a raw
string literal. Because it's top-level, most feature packages import it
either explicitly (`import com.example.besu.AckTags`) or transitively via
a wildcard `import com.example.besu.*` — **check which one a file already
has before adding new `AckTags.X` references to it**; several files
(e.g. `ManageRecordingsDialog.kt` before this session) had neither and
needed the explicit import added. `MainActivity.kt` itself needs no
import (same package).

**Key insight for shared composables**: if a reusable composable (e.g.
`output/VoiceRecordingPanel.kt`, embedded identically inside a Quick
Actions slot editor, a Quick-Access key dialog, a Matrix node editor, and
MANAGE RECORDINGS' RE-RECORD flow) tags its own internal buttons once,
*every* embed site inherits that tagging and event dispatch for free —
no per-call-site wiring needed. Tag at the lowest shared level, not at
each call site.

### Dispatching events from real UI

Two conventions coexist, pick based on what's already in the file:

1. **A per-screen `reportHelpInteraction(tag)` / `reportTextCommit(tag)`
   local helper**, declared once near the top of a screen-level
   composable (`val helpManager = LocalHelpManager.current` then `fun
   reportHelpInteraction(tag: String) { helpManager?.onEvent(HelpEvent.Interacted(tag)) }`),
   then called from various `onClick`/`onValueChange` handlers throughout
   that file. Used in `SettingsView.kt`, `QuickActionsDeck.kt`,
   `TargetView.kt`, `GeoProtocolView.kt`, `EmergencyDeck.kt`,
   `GifDeck.kt`, `EmojiDeck.kt`, `AudioView.kt`, `DesignSystem.kt`.
2. **Inline `helpManager?.onEvent(HelpEvent.Interacted(AckTags.X))`**
   directly in a button's `onClick`, when there's no natural single
   "screen" owner (e.g. a shared leaf composable, or a one-off dialog).
   Used in `VoiceRecordingPanel.kt`, and for a couple of one-off calls
   inside `DesignSystem.kt`'s Matrix node editor.

Either way, `helpManager?.onEvent(...)` is always safe to call
unconditionally on every relevant interaction — it's a no-op unless
HELP is actively running and that exact step is waiting for that exact
tag/event.

### Module registration — `help/HelpRegistry.kt`

One `object HelpRegistry { val modules: List<HelpModule> = ... }`,
assembled by `+`-concatenating each feature area's module(s):
`SomeFeatureHelp.module` (single) or `SomeFeatureHelp.modules` (list),
plus a couple of small modules defined inline. **Every new `HelpModule`,
including ones meant to stay hidden from the menu (see chooser pattern
below), must be appended here** — this is the only place `HelpManager`
can look a module up by id from.

### Menu UI — `help/HelpMenuDialog.kt`

`HelpMenuDialog(modules, context: HelpContext, primaryColor,
initialCategory, onDismiss, onLaunch)`. Renders a category chip row
(auto from the enum) and, for the selected category, a `LazyColumn` of
`modules.filter { it.category == selectedCategory }`. Tapping a card
calls `onLaunch(module)` — **it does not call `helpManager.start()`
itself**; that's entirely the caller's (MainActivity's) job, which is
what makes the interception pattern below possible.
`defaultHelpCategory(context)` picks which chip is pre-selected based on
`context.deckType` when no `initialCategory` is given.

### Coach overlay — `help/HelpCoachDialog.kt`

`HelpCoachPanel(manager, primaryColor, modifier)` is rendered **once,
globally**, floating over the entire screen in `MainActivity.kt` (inside
the root `Box`, positioned by `coachPlacement` via
`Alignment.TopCenter`/`BottomCenter`), gated on `helpManager.isActive`.
It needs no per-screen wiring — every module, on every screen, gets the
same floating panel automatically. Shows title/body, a progress bar
(`currentStepIndex` / `steps.size`), and either an "ACKNOWLEDGE //
CONTINUE" button (Read steps) or an "AWAITING LIVE INPUT" indicator with
action-specific instruction text (interactive steps). `[ABORT]` calls
`helpManager.abort()`.

### Navigation — how a module gets you to the right screen

In `MainActivity.kt`:
```kotlin
LaunchedEffect(helpManager.destinationRequest) {
    val destination = helpManager.destinationRequest ?: return@LaunchedEffect
    val module = helpManager.activeModule
    if (destination == HelpDestination.MATRIX &&
        module?.requiresMatrixDeck == true &&
        currentDeckType() != DeckType.MATRIX) {
        activateDeck(id = "DEFAULT", colorIdx = 0)
    }
    viewMode = destination.viewMode
    helpManager.destinationHandled(destination)
}
```
- If a module sets `destination` (module- or step-level) but **not**
  `requiresMatrixDeck`, starting it only ever changes `viewMode` — it
  never switches which deck is active. This is correct for a module
  anchored in a deck-type-agnostic screen, or one that's fine running
  against *whatever* deck is currently active (e.g.
  `QuickActionsDeckHelp` — it assumes a Quick Actions deck is already
  active, see the interception pattern below for how that's guaranteed).
- If a module sets `requiresMatrixDeck = true`, the effect force-switches
  to the always-present `"DEFAULT"` deck (assumed to be of type
  `DeckType.MATRIX`) whenever the currently active deck isn't already
  *some* Matrix deck. It does **not** care which non-default Matrix deck
  is active — only forces a switch when the current deck type isn't
  Matrix at all. Used by `MatrixDeckHelp`'s three modules and
  `VoiceRecordingsHelp.matrixModule`.
- **Pitfall**: forcing `viewMode` away from wherever the user currently
  is can silently unmount screen-scoped dialogs. A dialog owned by
  `SettingsView` (e.g. a Quick-Access key's recording panel) only exists
  while `viewMode == "SETTINGS"`; calling `helpManager.start()` on a
  module whose destination is `"MATRIX"` from *inside* that dialog would
  yank `viewMode` to `"MATRIX"` and close it out from under the user.
  This is why the first-use HELP offer (see below) is designed to never
  call `helpManager.start()` from deep inside an already-open,
  screen-scoped dialog — it only ever points the user at the permanent
  HELP entry, never auto-navigates.

### The "chooser fans out to hidden real modules" pattern

Established by `FieldOpsHelp` (three real per-pose modules +
`trainingGroundModule` + `deckTrainerModule`, all real; plus
`poseTrainingEntryModule`, which is *not* a real walkthrough), reused
verbatim by `VoiceRecordingsHelp` (`recordingModule`, `matrixModule`,
`manageModule` are real; `entryModule` is the chooser). Shape:

1. Define N real `HelpModule`s normally.
2. Define one more "entry" `HelpModule` with a single placeholder Read
   step (e.g. `body = "Choose a topic."`) and, critically, **no
   `destination`** — it's never actually run as a stepped walkthrough.
3. Keep a `Set<String>` of the real modules' ids (`pacedModuleIds` /
   `hiddenModuleIds`).
4. `HelpRegistry.modules` includes **all** of them (real + entry) — the
   real ones need to be registered so `helpManager.start(id)` can find
   them later; they're just not meant to be *listed*.
5. Where `HelpMenuDialog` is invoked in `MainActivity.kt`, filter the
   `modules` list passed in: `.filterNot { it.id in
   FieldOpsHelp.pacedModuleIds || it.id in
   VoiceRecordingsHelp.hiddenModuleIds }`. Only the entry module shows up
   under its category.
6. In `HelpMenuDialog`'s `onLaunch` callback in `MainActivity.kt`, special-case
   the entry module's id in the `when (module.id)` block: instead of
   `helpManager.start(module.id)`, flip a local `showXSelectorDialog`
   state var to `true`.
7. Build a small bespoke chooser dialog (`PoseSelectorDialog.kt` /
   `VoiceRecordingsHelpSelectorDialog.kt`) — a `Dialog` with a
   `LazyColumn` of option cards, each card's `onClick` calling
   `onSelect(realModuleId)`. The dialog itself is dumb/generic; **the
   `onSelect` callback's logic lives at the MainActivity call site**, not
   inside the dialog file, because that's the only place with access to
   `helpManager`, `decks`, `activateDeck()`, etc.
8. That `onSelect` callback is also where any per-module deck-existence
   checks belong (see next section) before finally calling
   `helpManager.start(realModuleId)`.

### Deferred start when a required deck doesn't exist yet

Some modules assume a specific deck **type** is already active
(`QuickActionsDeckHelp`, `VoiceRecordingsHelp.recordingModule` — both
anchored in a Quick Actions slot editor) but, unlike the
`requiresMatrixDeck` mechanism, there's no guaranteed always-present
Quick Actions deck to force-switch to. Pattern (in `MainActivity.kt`):

```kotlin
val existingDeck = decks.firstOrNull { it.type == DeckType.QUICK_ACTIONS }
if (existingDeck != null) {
    activateDeck(id = existingDeck.id, colorIdx = existingDeck.colorIndex)
    helpManager.start(moduleId)
} else {
    pendingHelpModuleId = moduleId
    showCreateDeckDialog = true
}
```
`pendingHelpModuleId` is a `mutableStateOf<String?>` read back inside
`CreateDeckDialog`'s `onCreate` callback, *after* the new deck is created
and activated: `if (pendingId == X.id && type == DeckType.QUICK_ACTIONS)
{ helpManager.start(pendingId) }` — gated on the user actually having
created the needed type (if they changed the type in the dialog, the
pending tutorial is silently dropped rather than force-started against
the wrong deck type). **Note**: `pendingId == SomeModule.id` inside an
`if` does narrow `pendingId` to non-null for Kotlin's smart-cast
purposes in this codebase's proven-compiling shape — don't refactor this
into an intermediate `Boolean` + `!!`, the direct `if (pendingId == X.id
&& ...) { helpManager.start(pendingId) } else if (pendingId == Y.id &&
...) { helpManager.start(pendingId) }` shape is what's already relied on
elsewhere.

### First-use onboarding offers — no engine precedent, pattern established for voice recordings

Before the VOICE RECORDINGS category, **nothing in this codebase
auto-offered a HELP walkthrough on first feature use** — every existing
trigger was a manual HELP-menu tap, or (for `FieldOpsHelp`) a manual
chooser selection. The pattern established for voice recordings
(`help/HelpOfferBanner.kt`, wired into `VoiceRecordingPanel.kt` and
`ManageRecordingsDialog.kt`, flag in
`VoiceRecordingRepository.hasSeenHelpOffer`/`markHelpOfferSeen`, its own
small prefs file `ack_voice_recordings`, key `seen_help_offer`):

- A single shared boolean flag, checked at each trigger site via
  `remember { mutableStateOf(Repository.hasSeenX(context)) }`.
- Rendered as a small dismissible inline banner (not a modal), shown at
  *every* trigger site until dismissed once, anywhere.
- Dismissing it **only** flips the flag — it never auto-launches
  `helpManager.start()` or navigates. This is intentional (see the
  navigation pitfall above): the offer is a pointer to the always-present
  permanent HELP entry, not a shortcut around it. Follow this shape for
  any future first-use offer rather than trying to auto-launch a module
  inline — auto-launching is only safe from the top-level menu/chooser
  flow in MainActivity, which owns deck-activation and viewMode.

### File map

| File | Owns |
|---|---|
| `help/HelpCore.kt` | Data model: `HelpCategory`, `HelpDestination`, `HelpAction`/`HelpEvent`, `HelpStep`/`HelpModule`/`HelpContext`, `LocalHelpManager` |
| `help/HelpManager.kt` | The state machine |
| `help/HelpTarget.kt` | `AckHelpShape`, `Modifier.helpTarget()` |
| `AckTags.kt` (top-level package) | Every tag constant, single source of truth |
| `help/HelpRegistry.kt` | Flat list of every registered module |
| `help/HelpMenuDialog.kt` | The category-tabbed browse UI |
| `core/HelpWalkthroughText.kt` | The naming rule for walkthrough strings and the rule for when the translated step may be spoken |
| `help/HelpCoachDialog.kt` | The global floating step overlay |
| `help/*Help.kt` (one per feature area) | Module definitions for that feature |
| `help/PoseSelectorDialog.kt`, `help/VoiceRecordingsHelpSelectorDialog.kt` | Chooser dialogs for the "fan out" pattern |
| `help/HelpOfferBanner.kt` | Generic dismissible first-use tip banner |
| `MainActivity.kt` | Owns the single `HelpManager` instance, the `CompositionLocalProvider`, the destination/deck-activation effect, `HelpMenuDialog`'s `onLaunch` interception `when` block, and all chooser/pending-module state |

## The BACKUP & RESTORE system — deep analysis

ACK has two independent backup mechanisms, not one. **Full JSON backup**
(`backup/TransferManager.kt`) covers almost everything else in the app —
decks, DSP, root overrides, quick actions, emergency prompts, target
computer entries, voice recordings, autocomplete history, Geo-Protocol,
visual presets, output routing, Terminal/STATUSBOX prefs, shake
sensitivity, Shared Root Variables' collapsed state. **Standalone GIF
deck backup** (`decks/GifBackupManager.kt`) is a separate `.zip` format,
built specifically because GIF binaries don't belong in a JSON blob and
need to be viewable outside the app entirely. They share a philosophy
(merge-by-id, additive restore, aggressive per-field validation logging)
but not code — there is no shared backup engine.

### Core philosophy: restore is additive, never destructive

This is a direct consequence of the user's own standing accessibility
preference — **"Backups should be encouraged, edits need to be
confirmed"** — applied to its logical conclusion: a restore should never
be able to silently delete something the user has since added. Both
backup paths follow the same rule: **an entry with a matching id is
overwritten in place; an entry the backup doesn't mention is left alone;
nothing is ever wiped wholesale first.** Concretely, every repository
function that used to `editor.clear()` or `deleteAll()` before writing
backup data (`applyBackupToStorage`'s matrix editor, `ComputerRepository
.replaceCategories`, `VoiceRecordingRepository.replaceFromBackup`,
`AutocompleteHistoryRepository.restoreFromBackup`) has had that clear
removed and replaced with a read-merge-write pattern: read the existing
`SharedPreferences`/list into a `Map` keyed by id (or name, or index —
whatever the entity's natural stable key is), overwrite with the
backup's entries by that key, write the merged `.values.toList()` back.
`ComputerRepository.replaceCategories` was renamed to `mergeCategories`
specifically so its name stopped lying about what it does. To actually
delete something, the user must use that feature's own dedicated
delete/clear action — restore is not a substitute for it, and the UI
copy in `SettingsView.kt`'s FULL RESTORE confirm dialog says this
explicitly rather than the old (inaccurate) "cannot be undone" framing.

### Full JSON backup — `backup/TransferManager.kt` + `backup/AckBackup.kt`

- `AckBackup` (in `AckBackup.kt`) is the `@Serializable` root data class
  for the whole export. **Every field added for a new settings area is
  nullable** (`geoEngineMode: String?`, `terminalRetentionDays: Int?`,
  etc.) or defaults to an empty collection (`geoZones: List<GeoZone> =
  emptyList()`), never a real default value. This is deliberate schema
  evolution: an *old* backup file, decoded against the *current*
  `AckBackup` shape, naturally decodes missing fields as `null`/empty —
  which `applyBackupToStorage` then correctly reads as "this old backup
  has nothing to say about this field, leave the device's current value
  alone" rather than as "reset this field to some default." A
  non-nullable field with a real default would instead silently stomp
  the field on every restore from an older backup.
- `generateBackupJson` (export) and `validateDataIntegrity` (import gate)
  and `applyBackupToStorage` (import apply) are the three stages, always
  touched together when a new field is added: export reads it from
  storage into the `AckBackup`, validate checks it's within sane bounds
  and logs why if not, apply writes it back into the right repository
  (often gated `if (backup.field != null) { ... }` so a null from an old
  backup is a true no-op).
- **Diagnostic logging discipline**: every single `return false` inside
  `validateDataIntegrity` is preceded by `Log.e("ACK_IMPORT", "<specific
  field, its value or length, and why it failed>")` — never a generic
  "validation failed" message. This was added specifically because a
  generic failure gives the user nothing to act on when a restore is
  silently refused; the specific version is what let the user self
  -diagnose a real bug from their own logcat capture (see next point).
  Any new validation check added to this function must follow the same
  pattern — log the specific offending value before returning false.
- **Validation ceilings are a firewall against a corrupted/hostile file,
  not a practical constraint** — a check must never be able to reject
  something the app's own UI can legitimately produce. `MAX_PHRASE_LENGTH
  = 2000` and `MAX_LABEL_LENGTH = 120` are both deliberately set above
  every real UI input cap in the app (traced per-field, e.g. deck names
  are capped by matching `createDeck`'s real `.take(40)`, not an
  arbitrary rounder number). When a new capped field is added anywhere in
  the app, check its real UI-side `.take(N)`/length limit and set the
  validator's ceiling to match or exceed it — never guess a number.
- **`DECK_CONFIG_KEY_PATTERN`/`MAX_DECK_CONFIG_LENGTH`** exist because the
  sparse `matrixData` map (arbitrary `String` → `String`) stores two very
  different kinds of values under the same map: ordinary short phrases,
  AND a couple of keys (`emoji_deck_*_config`, `quick_actions_*_config`)
  whose value is a *whole serialized deck config* (pages, slots, grid
  size, nested panels) — categorically bigger data, not just a long
  phrase. `validateDataIntegrity` matches the key against
  `Regex("^(emoji_deck_|quick_actions_).*_config$")` and applies
  `MAX_DECK_CONFIG_LENGTH = 50_000` instead of `MAX_PHRASE_LENGTH` only
  for keys matching that pattern. **If a future feature adds another
  "whole-config-blob-in-a-sparse-map" key, extend this pattern rather
  than raising `MAX_PHRASE_LENGTH` again** — the two kinds of data should
  never share one ceiling.
- `MAX_DECOMPRESSED_SIZE = 25MB` — deliberately raised from an original
  1MB because a communication app's real backups (with any meaningful
  history/config) routinely exceed 1MB; this is a decompression-bomb
  guard, not a "your data shouldn't be this big" opinion.

### Standalone GIF deck backup — `decks/GifBackupManager.kt`

A GIF deck's real content (image binaries) cannot live in the JSON
backup above, and per the user's explicit requirement, the backup file
itself needs to be **directly browsable/viewable on another device or
OS without ACK installed at all** — ruling out a base64-in-JSON approach.
The format is a real `.zip`: actual `.gif` files inside real
`<deck name>/<category name>/<title>.gif` folders (sanitized,
collision-deduped), plus an authoritative `manifest.json` carrying the
real ids/ordering/toggles needed to restore faithfully (folder/file
*names* are for human browsing only — restore never parses them back
apart; it trusts the manifest).

- **`fileName` vs `zipPath` are deliberately separate fields** on
  `GifBackupEntry`. `zipPath` is the human-readable archive path, used
  only as a `ZipFile.getEntry()` lookup key — it never touches the real
  filesystem, so it's traversal-safe by construction (worst case is a
  failed lookup). `fileName` is what gets passed to
  `File(destinationDirectory, entry.fileName)` on import — a genuine
  path-traversal vector — so it alone is tightly regex-validated against
  `SAFE_FILENAME_PATTERN = Regex("^[A-Za-z0-9_\\-]{1,100}\\.gif$")`. If
  you ever add a new field derived from user/archive-controlled data that
  ends up in a `File(...)` constructor, treat it like `fileName`: separate
  it from any display-only path string and validate it narrowly.
- **That `fileName` check happens twice, independently**: once in
  `GifBackupManager.validateManifest` (the import gate) and again inside
  `GifRepository.restoreEntry` itself, using the identical regex,
  regardless of whether the caller already validated. This is deliberate
  defense-in-depth — `restoreEntry` doesn't trust its caller.
- **Import reads via `ZipFile` (random access), not `ZipInputStream`**,
  specifically so `manifest.json` can be located and parsed *before* any
  GIF entry is processed, regardless of which order the zip's entries
  were physically written in. The source `Uri` is first copied to a temp
  file (`File.createTempFile`, deleted in a `finally`) because
  `ZipFile`'s random access needs a real file handle, not a stream.
- **Validation mirrors `TransferManager`'s rigor** at a smaller scale: id
  pattern/length checks (`SAFE_ID_PATTERN`), label length caps
  (`MAX_LABEL_LENGTH = 120`, matching the same value used in
  `TransferManager` — not a coincidence, same "don't reject legitimate
  data" reasoning), category/entry count caps (`MAX_CATEGORIES = 500`,
  `MAX_ENTRIES = 5000`), referential integrity (an entry's `categoryId`
  must exist among the manifest's own categories), duplicate-id
  rejection, and a `zipPath` blank/`".."`-containment check. Every
  rejection logs via `Log.e("ACK_GIF_BACKUP", ...)` — same discipline as
  `ACK_IMPORT` above, same reasoning.
- **Import refuses to retype an existing non-GIF deck.** If the
  manifest's `deck.id` collides with an existing deck of a different
  `DeckType` (including the always-present `"DEFAULT"` Matrix deck), the
  import is refused outright rather than silently converting it.
- Merge-by-id on import: `GifRepository.upsertCategory` and
  `GifRepository.restoreEntry` each do the same read-merge-write pattern
  as the JSON side; the deck itself is created via
  `CommandRepository.upsertDeck` only if no deck with that id exists yet.

### The app-restart pattern for post-restore UI staleness

Both backup paths can add a brand-new deck (JSON restore via
`upsertDeck`/matrix import; GIF import always at least conditionally).
`MainActivity`'s deck selector
(`val decks = remember(deckRevision) { CommandRepository.getDecks(context) }`)
only re-reads `SharedPreferences` when `deckRevision` is manually
incremented — and screens outside `MainActivity`'s own composable scope
(`SettingsView`, `GifDeck`) have no clean way to trigger that from
outside. **A first attempt at a targeted fix (a callback threaded back
into `MainActivity` to patch `deckRevision`/`currentDeckId`/etc. by
hand) was tried and explicitly rejected by the user after testing on
their own device** ("I still end up having to restart the app") — so
this is not a design choice to revisit casually; a full process restart
is the deliberate, user-confirmed fix, not a stopgap.

The fix is `fun restartApp(context: Context)`, a **top-level function in
`MainActivity.kt`** (outside the `MainActivity` class, so any file with
`import com.example.besu.*` — which most feature files already have —
can call it with zero new imports):
```kotlin
fun restartApp(context: Context) {
    val intent = Intent(context, MainActivity::class.java).apply {
        flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TASK
    }
    context.startActivity(intent)
    Runtime.getRuntime().exit(0)
}
```
Both `SettingsView.kt` (CREATE DECK from matrix import, FULL RESTORE) and
`GifDeck.kt` (successful GIF `.zip` import) use the identical call
shape: show a short success toast, then set a screen-local
`pending*Restart` boolean, with a top-level (dialog-dismissal-surviving)
`LaunchedEffect(pending*Restart) { if (pending*Restart) { delay(1500);
restartApp(context) } }`. **The 1.5s delay is load-bearing** — calling
`restartApp` synchronously right after `Toast.show()`/before the effect
tick cuts the toast off mid-display; don't collapse this into a direct
call. **Any new import/restore flow that can create a new deck (or
otherwise mutate state `MainActivity` caches via `remember{}`) should
reuse this exact pattern** — toast, delayed flag, shared `restartApp` —
rather than inventing a new targeted-refresh mechanism; that path has
already been tried and rejected once.

### File map

| File | Owns |
|---|---|
| `backup/AckBackup.kt` | The `@Serializable` root data class for the full JSON backup — every new field nullable/empty-default for schema evolution |
| `backup/TransferManager.kt` | `generateBackupJson` (export), `validateDataIntegrity` (import gate, logs every rejection to `ACK_IMPORT`), `applyBackupToStorage` (merge-by-id apply) |
| `decks/GifBackupManager.kt` | Standalone `.zip` GIF deck backup: manifest model, `exportDeck`, `importBackup`, `validateManifest` (logs every rejection to `ACK_GIF_BACKUP`) |
| `decks/GifRepository.kt` | `upsertCategory`, `restoreEntry` (re-validates `fileName` independently of the manifest gate) |
| `data/CommandRepository.kt` | `upsertDeck` — merge-by-id deck creation/update used by both backup paths |
| `MainActivity.kt` | Top-level `restartApp(context)`, shared by every import/restore flow that can create a new deck |
| `settings/SettingsView.kt` | FULL RESTORE FROM JSON + IMPORT MATRIX AS NEW DECK UI, both using the toast → delayed-flag → `restartApp` pattern |
| `decks/GifDeck.kt` | Per-deck BACKUP dropdown (EXPORT/IMPORT DECK (.ZIP)) UI, same restart pattern |

## The CUSTOM TRAINED VOICE system — deep analysis

Lets a user speak arbitrary typed text in their own cloned voice, trained
*outside* the app (a Piper/VITS voice, fine-tuned on a PC from the user's
own recordings) and then run entirely on-device inside ACK — no network
dependency, matching the app's own "must always be able to communicate"
requirement. Only one such voice can be installed at a time.

### Engine: sherpa-onnx, not a bespoke ONNX/espeak-ng integration

The actual neural inference + phonemization runs through
[sherpa-onnx](https://github.com/k2-fsa/sherpa-onnx) (k2-fsa), which
bundles ONNX Runtime and espeak-ng together with a Kotlin API
(`com.k2fsa.sherpa.onnx.OfflineTts`) and native Piper/VITS support. This
was chosen specifically because hand-rolling an espeak-ng Android JNI
build plus onnxruntime-android wiring would have been a much larger,
riskier undertaking — sherpa-onnx already solves exactly that. It is
**not published to Maven Central**: the `.aar` is downloaded manually and
vendored in `app/libs/` (see that folder's `README.md`), and is
deliberately **excluded from git** (`.gitignore`) since it's a large
third-party binary, not source the team wrote. Same treatment for the
shared `espeak-ng-data` phonemization asset (`app/src/main/assets/
espeak-ng-data/`, own `README.md`, also gitignored) — it's identical
across every Piper voice regardless of who trained it, so it ships once
as a bundled asset rather than being re-imported per voice.

**Critical, easy-to-miss fact #1**: sherpa-onnx's VITS/Piper loader
(`OfflineTtsVitsModelConfig`) wants a plain-text `tokens.txt` (`<symbol>
<id>` per line), **not** Piper's own `.onnx.json` training config
directly. `PiperVoiceEngine.generateTokensFile` derives `tokens.txt` from
the installed config's `phoneme_id_map` every time the engine (re)loads,
so it's always regenerated fresh from whatever voice is currently
installed rather than being a one-time conversion step. Two entries get
filtered out while generating it, both required, neither optional:
- The literal `"\n"` symbol key — writing it would embed a real newline
  inside a `tokens.txt` line, corrupting the line-based file format.
  Matches sherpa-onnx's own official conversion script's one quirk
  (`scripts/piper/add_meta_data.py`).
- **Any symbol that isn't exactly one Unicode codepoint**
  (`key.codePointCount(0, key.length) != 1`). sherpa-onnx's tokenizer
  (`sherpa-onnx/csrc/piper-phonemize-lexicon.cc:ReadTokens`) maps a
  single codepoint to an id — it has **no representation at all** for a
  multi-character symbol; this isn't a formatting quirk to work around,
  it's a hard structural limit of its lookup table. piper1-gpl can
  optionally merge diphthongs (e.g. `"eɪ"`, `"aɪ"`) into single compound
  vocabulary entries via `--data.vowel_clusters` (default `None`/off).
  This app's training command never passes that flag, so any such
  entries in a voice's `phoneme_id_map` reflect the *base checkpoint's*
  fixed vocabulary size, not something this voice's own fine-tuning
  actually learned to rely on — skipping them is correct, not a lossy
  compromise, **for a voice trained the way this app's docs instruct**.
  **If a future voice is ever trained with `vowel_clusters` actually
  set, this stops being safe** — skipping would silently mispronounce
  every word containing one of those diphthongs, and would need real
  on-device merge logic instead of a skip.

**Critical, easy-to-miss fact #2 — the .onnx file itself needs patching,
and this cannot be done on-device**: sherpa-onnx's VITS loader
(`sherpa-onnx/csrc/offline-tts-vits-model.cc`) reads several fields —
`sample_rate`, `n_speakers`, `language`, `comment` — as **required ONNX
model metadata (`metadata_props`), with no fallback default**. `comment`
must contain the substring `"piper"` for the model to even be treated as
a Piper-style model at inference time. piper1-gpl's own `export_onnx.py`
does not embed any of this — a voice exported straight from the training
pipeline in this repo's earlier session and imported as-is **crashes the
app** on first synthesis attempt, logging `'sample_rate' does not exist
in the metadata` right before the process dies. This has nothing to do
with ACK's own code; it's a real gap between what piper1-gpl exports and
what sherpa-onnx's loader requires, and there's no way to patch an
already-exported `.onnx`'s embedded metadata from inside the Android app
— it has to happen before import, on the machine that trained the voice.
Fix: `tools/patch_voice_for_sherpa_onnx.py` (mirrors sherpa-onnx's own
official `scripts/piper/add_meta_data.py`) — run it once against the raw
trained `.onnx`, then (re-)import the patched file into ACK. **Any future
change to piper1-gpl's export script, or a switch to a different Piper
training toolkit, should be re-checked against this same requirement**
rather than assumed fixed.

**The patcher is user-facing, so it must be forgiving and must never damage the model** (`tools/patch_voice_for_sherpa_onnx.py`,
tested by `tools/freeform_studio/tests/test_patch_voice.py`). A real failure: the user ran it with the `.onnx` given as *both*
arguments and got a raw `UnicodeDecodeError` from `json.load`. Root cause was the guide: the `<model>.onnx.json` copy of
`config.json` lived only in the *optional* "test locally" step, but the required patch and import steps need it (shell Tab
completion then offers only the `.onnx`). Now: the copy is part of the export step in `docs/VOICE_TRAINING_GUIDE.md` §5; the
script validates its arguments (model given twice, arguments swapped, missing config, non-Piper config, not-an-ONNX file, missing
`onnx` package) with plain messages that print the exact `cp`/run commands, exits 2 with nothing changed; the second argument
is optional (`<model>.json`); it keeps the original as `<model>.onnx.before-patch` (a newer export gets a timestamped backup),
writes to a scratch file and swaps it in with `os.replace`, and is a no-op on an already-patched model. Keep it that way:
the user's standing preference is backups encouraged, edits safe. The script does `import onnx` lazily so argument checks work
(and are tested) without it.

### Storage — `output/CustomVoiceRepository.kt`

Two fixed files, `context.filesDir/custom_voice/model.onnx` and
`.../model.onnx.json` (plus a generated `tokens.txt` sitting alongside,
owned by `PiperVoiceEngine`, not this repository). Deliberately **no
separate "installed" flag** — `hasCustomVoice()` just checks both files
exist on disk, so metadata and files can never disagree, unlike a
prefs-flag-plus-files design. No id/list at all, since only one voice is
ever supported — this is simpler than `VoiceRecordingRepository`'s
multi-entry JSON-list pattern on purpose.

Validates on import: exactly 2 files selected, identified by filename
suffix (`.onnx` / `.onnx.json` — Android's SAF gives these no reliable
MIME type, so this mirrors `GifRepository.importGif`'s tolerance for a
null MIME), size ceilings as a corruption/hostile-file firewall (not a
practical constraint — 300MB comfortably covers even a "high" quality
Piper model), and a light content check on the config
(`looksLikePiperConfig` — must parse as JSON and contain both
`phoneme_id_map` and `audio` keys, which every real Piper config has).
`installFromValidatedFiles` is the shared, independently-re-validating
landing point for **both** the direct-file-picker import path and
`CustomVoiceBackupManager`'s zip-restore path — same defense-in-depth
reasoning as `GifRepository.restoreEntry`.

### Synthesis engine — `output/PiperVoiceEngine.kt`

A singleton wrapping one lazily-loaded `OfflineTts` instance (native model
load is expensive — tens of MB, not instant — so it happens once per
process, not per utterance). `generate(context, text)` is **synchronous
and blocking**, returning `Pair<ShortArray, Int>?` (PCM + sample rate) or
`null` on any failure — deliberately simple compared to system TTS's
async callback dance, since there's no `UtteranceProgressListener`
machinery to hook into for a different engine. `release()` frees the
native session (called from `OutputService.onDestroy()`); a later
`generate()` call rebuilds it lazily. `requestStop()` is a stop-flag
checked right after native generation completes, so `OutputService`'s
phone-shake `KILL_OUTPUT` handler can abort an in-flight custom-voice
utterance the same way it already clears queued/active system-TTS work.

### Integration seam — `OutputService.kt`

The DSP chain (`applyAudioEffects`) and playback (`playPcm`, with its
kill-switch/audio-focus/routing logic) already operate on raw
`ShortArray` PCM + sample rate, completely decoupled from *how* that PCM
was produced — this is what made the whole feature a relatively clean
addition rather than a parallel pipeline. `processSpeech()` branches on
`VoiceProfile.useCustomVoice` right after computing `finalText`: true
spins a `Thread { ... }` (matching the existing `playRecording`/
`previewRecording` off-main-thread pattern — this class has no coroutine
scope) that calls `PiperVoiceEngine.generate()`, then feeds the result
through `applyAudioEffects()` with `modFreq=modDepth=crush=0` (gain-only,
**treated like a recording, not like robotic-overlay-eligible system
TTS** — a cloned voice shouldn't get the robotic/crush character effects)
and the same `playPcm()` everyone else uses. **On synthesis failure, it
falls back to system TTS for that one utterance** rather than going
silent (`speakWithSystemTts`, the extracted original synthesis body) —
non-negotiable for an AAC app. `false` (the default, so old saved
`VoiceProfile`s behave exactly as before) is untouched, unchanged
`speakWithSystemTts` path.

### Backup — `output/CustomVoiceBackupManager.kt`

A standalone `.zip` export/import (`model.onnx` + `model.onnx.json`, no
manifest needed since there's only ever one voice) — same reasoning as
`GifBackupManager`: a trained voice model is a real binary, tens of MB,
which has no business inside `TransferManager`'s JSON blob. Deliberately
separate from EXPORT .JSON / FULL RESTORE FROM JSON, exactly as GIF
backups are separate from it today.

### UI — `settings/AudioView.kt`

"CUSTOM VOICE" section (status line + IMPORT/RE-IMPORT button, plus
EXPORT/IMPORT VOICE BACKUP once one exists) sits between MANAGE PROFILES
and the DSP chain editor button. Import uses
`ActivityResultContracts.OpenMultipleDocuments()` (both files picked in
one go) and reuses the established toast → `pending*Restart` flag →
`LaunchedEffect { delay(1500); restartApp(context) }` pattern from GIF
deck import, since a newly-imported voice is exactly the kind of state
`OutputService`'s `PiperVoiceEngine` singleton needs a clean process
restart to pick up.

**Import takes the two trainer files or the one Voice Studio zip.** `CustomVoiceRepository.importPicked` is the single entry for the IMPORT / RE-IMPORT button: `core/CustomVoiceImport.kindOf(names)` (plain Kotlin,
`CustomVoiceImportTest`) says ONE_ZIP for exactly one picked file whose name ends in `.zip` (any case) and everything else is the original two-file path, which refuses what is not a `.onnx` and a `.onnx.json`. A zip
goes to `CustomVoiceBackupManager.importBackup`, the very restore path (entries `model.onnx` and `model.onnx.json`, the 400 MB zip ceiling, then `installFromValidatedFiles`'s own re-check), so nothing is validated
less than before. This routing only exists because the restore button (IMPORT VOICE BACKUP, next to EXPORT) is shown only once a voice is installed: a phone with no voice could not take the zip ACK Voice Studio writes
(found on the first real phone test). `CustomVoiceImportWiringTest` reads the three Android-only files. The failure toast names both forms in all six languages (drafts for the translations).

**Two ways to actually put the voice on output, not one:**
1. **A fourth fixed preset, `"MY VOICE"`** — a real entry in
   `OutputService`'s `FACTORY_PRESETS` map (id `"MY_VOICE"`,
   `useCustomVoice = true`), given the exact same "select, don't edit"
   treatment as CYBER/MECH/ORGANIC in the main VOICE PROFILE chip row.
   This is the primary, obvious path: import a voice, tap the chip, done
   — no detour through a custom slot's DSP editor. The chip only renders
   when `hasCustomVoice(context)` is true (same "hide rather than show
   disabled" convention the "+ NEW" chip already uses), and the DSP chain
   editor's locked-placeholder box shows a voice-specific message
   ("THIS ENGINE HAS NO DSP CONTROLS OF ITS OWN") when `userProfile ==
   "MY_VOICE"` rather than the generic factory-preset one.
2. **A "USE MY VOICE" toggle inside any custom slot's DSP chain editor**,
   next to "BASE VOICE" (disabled with a "NO VOICE IMPORTED" hint until
   one exists) — for a user who wants a distinctly *named/labeled* slot
   using the trained voice rather than the fixed "MY VOICE" preset.
   Turning it on hides the ROBOTIC OVERLAY and BITCRUSH sections
   entirely, since this engine ignores them by design (PITCH/SPEED are
   left visible but are also inert for this engine — harmless to leave
   alone rather than worth the complexity of hiding them too).

Both paths set the same `VoiceProfile.useCustomVoice = true` flag
`OutputService.processSpeech()` branches on — there is no separate "which
mechanism did you use" state to keep in sync.

### File map

| File | Owns |
|---|---|
| `output/CustomVoiceRepository.kt` | File storage + validation for the one installed voice |
| `output/PiperVoiceEngine.kt` | sherpa-onnx `OfflineTts` wrapper, `tokens.txt` generation, `generate()`/`release()`/`requestStop()` |
| `output/CustomVoiceBackupManager.kt` | Standalone `.zip` export/import, mirrors `GifBackupManager.kt` |
| `output/OutputService.kt` | `processSpeech()`'s `useCustomVoice` branch, `speakWithSystemTts` (extracted fallback path), kill-switch hook, `onDestroy` cleanup |
| `settings/AudioView.kt` | Import/backup UI, "USE MY VOICE" DSP chain editor toggle |
| `data/VoiceProfile.kt` | `useCustomVoice: Boolean = false` |
| `app/libs/README.md`, `app/src/main/assets/espeak-ng-data/README.md` | Manual one-time download steps for the vendored, gitignored sherpa-onnx `.aar` and shared phonemization data |

## DATA SOVEREIGNTY and LICENSING — rules that must stay true

The user's standing requirement (stated while making Freeform Studio usable by casual users and SLPs): **voice recordings,
transcripts, edits, exports, backups, training data and the trained voice stay on devices the person controls, 100%.** And
the project is **GPL-3.0-or-later**. Both are enforced by tests so a later change can't quietly undo them; read these before
adding a dependency, a permission, a network call, a file type, or a new source file.

### Freeform Studio (`tools/freeform_studio/`)
- **The server never goes online.** `FasterWhisperEngine` loads with `local_files_only=True` (`Config.asr_allow_download`
  / `--allow-model-download` is the opt-out) and `privacy.apply_offline_defaults()` sets `HF_HUB_OFFLINE=1`,
  `HF_HUB_DISABLE_TELEMETRY=1`, `DO_NOT_TRACK=1` before the Hugging Face libraries import. Measured: without this every model
  load contacted huggingface.co even when cached (and *failed* behind a 403 proxy). **`models.py` (`python -m
  freeform_studio.models fetch NAME`) is the one place allowed to use the internet, and it asks first.** `asr_smoke` follows
  the same rule. A missing model produces a plain `EngineError` naming the exact fetch command (`explain_load_error`).
- **Owner-only files.** `privacy.private_umask()` wraps `main()` of the server and every file-writing command (backup, export,
  build_dataset, repair, models); the token file is created with `O_EXCL` + mode 0600. `doctor` only *reports* loose
  permissions on older data (and the `chmod -R go-rwx` command) — it never changes a user's files by itself.
- **Browser caching.** Everything under `/api/` is `Cache-Control: private, no-store` (audio, transcripts, waveforms). Opening
  the printed `?token=` link 303-redirects to the same page without the token (`address_without_token`, never `//host`), the
  cookie carries the login; `/api/*?token=` still works for scripts. Tests: `tests/test_privacy.py`.
- **Synced folders.** `privacy.sync_risk()` / `sync_warning()` flag paths inside OneDrive/Dropbox/Google Drive/iCloud/etc. and
  Windows `Documents`/`Desktop`/`Pictures` (OneDrive Known Folder Backup); used by the server banner, `doctor` and the backup
  command. It only ever says "may" (folder names, can't see whether sync is on). Never recommend a `Documents` backup path.
- **No-network regression test.** `tests/test_no_network.py` + `tests/egress_workflow.py` run the whole workflow in a
  loopback-only namespace (`unshare -rn`) with a Python socket-logging hook and `strace`, and fail on any destination that
  isn't this computer; the only allowed oddity is `netcheck.lan_ip()`'s UDP `connect()` to `192.0.2.1:9` (a route probe;
  sending to it fails the test). Another test fails if a web address appears in any shipped file. If you add a feature that
  genuinely needs the network, it must be an explicit, user-confirmed command like `models fetch`, not a background call, and
  needs the user's approval first.
- Not measured in the build sandbox (Hugging Face is blocked there): a real speech-model run end to end, a real training
  run, a real phone. `docs/DATA_SOVEREIGNTY.md` says so and gives the user commands to check themselves.

### ACK Android app
- **No network permission, no network code, no cloud backup.** The manifest must not request `INTERNET` or other network
  permissions; app Kotlin must not use `java.net`/`HttpURLConnection`/`OkHttp`/`WebView`/`android.net` (except `Uri`); both
  `res/xml/data_extraction_rules.xml` (`<cloud-backup>` excludes all nine domains; `<device-transfer>` includes all, so a
  phone-to-phone setup transfer keeps working) and `backup_rules.xml` exclude everything. Enforced by
  `tests/test_sovereignty_policy.py`. Consequence the user was told: restoring from a Google backup no longer brings ACK data;
  ACK's own EXPORT .JSON and the voice/GIF `.zip` backups are the way (consistent with "backups should be encouraged").
  Known open items: the two Google Play Services libraries are proprietary (and `play-services-location` involves Google's
  location services); a built APK's merged manifest was not inspected (no Android SDK in the sandbox).

### Licensing
- **GPL-3.0-or-later.** `LICENSE` is the **byte-identical** FSF text (SHA-256 pinned in `test_license_headers.py`; an earlier
  copy differed from the FSF text in two words). The copyright line lives in `NOTICE`, not in `LICENSE`. **Every source file**
  (`.kt .kts .py .js .mjs .html .css .sh .pro`) carries `SPDX-License-Identifier: GPL-3.0-or-later` in its first lines (after a
  shebang / `<!doctype>`); the test fails for a new file without one. XML resources, docs and images are covered by `NOTICE`.
- `tools/patch_voice_for_sherpa_onnx.py` follows sherpa-onnx's Apache-2.0 `add_meta_data.py` (Xiaomi Corp.): its header is
  `GPL-3.0-or-later AND Apache-2.0` with the attribution and a statement of changes; `LICENSES/Apache-2.0.txt` is the verbatim text.
- **`THIRD_PARTY_NOTICES.md`** lists every outside source with license **and how it was checked** ("not verified" is stated, never
  guessed). A test fails if a binary asset (`.so .otf .ttf .jar .aar`) is committed, or a Freeform Studio requirement is added,
  without being listed. When adding a dependency, read its real license (installed metadata / repo / POM) and add it.
- **Open decisions recorded there (do not "fix" silently):** `app/src/main/res/font/atkinson_hyperlegible_next_regular.otf`
  embeds a *no-derivatives* license while upstream publishes the same version number under SIL OFL as a *different build* (375
  vs 392 glyphs, different outlines in 197) — swapping changes rendering, so it is the user's call; the Play Services
  libraries; the license of whichever Piper base checkpoint a voice is trained from (per-voice `MODEL_CARD`); image provenance.
- Authorship: Freeform Studio was written with an AI assistant; that is stated in `THIRD_PARTY_NOTICES.md`. Keep saying it.

## The STATEMENT COMPOSER system — deep analysis

The statement composer (`composer/StatementComposerView.kt`) is what the
TYPE tab shows now — a screen for building multi-sentence statements out
of Target Computer entries and Shared Root Variables, saving them, and
copying or speaking them. It replaced legacy Manual Override on that tab;
legacy Manual Override still exists verbatim, relocated behind Terminal's
`/m` command (see its own subsection below). This system reuses
`TemplateEngine` and the Target Computer picker composables that already
existed for Matrix/Quick Actions — it introduces almost no new resolution
machinery, just a new place that writes tokens instead of literal text.

### Core model: statements store tokens, never resolved snapshots

A `StatementNode` (`data/StatementRepository.kt`) has a `template: String`
field that holds the raw composed text **with `[COMPUTER:id]`/`{VAR:A}`
tokens still embedded** — never a resolved/frozen copy. COPY and SPEAK
both resolve the template fresh, via `TemplateEngine.resolve()`, at the
moment they're pressed (see `resolveStatementTemplate` in
`StatementComposerView.kt`). This is the same live-reference philosophy
`CommandRepository.getResolvedPhrase`/`resolveQuickAction` already use for
Matrix/Quick Actions phrases — a saved statement is not a snapshot, so
editing the Target Computer entry or Shared Root Variable it references
later changes what the statement produces next time, with no migration
needed. This directly serves the app's own **restore-is-additive/nothing
is ever a frozen copy** philosophy documented in the BACKUP section above
— treat "statements store references, not values" as load-bearing the
same way that section's "merge-by-id, never wipe" rule is.

`StatementNode.variableContext: String` (meaningful only on a `STATEMENT`
leaf) is required and easy to forget why: `{VAR:A}`/`{VAR:B}`/`{VAR:C}`
tags are only unique **within one Shared Root Variables grouping** (a
fixed pose — IDENTITY/DEFEND/CONNECT — or a custom context layer's name),
exactly like a Matrix phrase's `{VAR:A}` always resolves against its own
node's category (`CommandRepository.getResolvedPhrase` looks this up from
`cachedNodes.find{...}?.category`) and a Quick Actions slot resolves
against its own group's `rootCategory`. A statement isn't anchored to a
node or group, so it has to carry its chosen grouping explicitly instead
— resolving `{VAR:A}` against the wrong grouping's `RootOverrideConfig`
would silently produce the wrong value. **If a future field ever lets a
single statement reference more than one grouping, this single-string
field stops being enough — don't just widen its type without also
rethinking how the picker UI decides which grouping is "current."**

### Statements are organized tree > leaf, mirroring Target Computer

`StatementNode` (`data/StatementRepository.kt`) is a single unified tree —
`type` is `FOLDER` (organizational, `children` only) or `STATEMENT` (a
leaf, carrying `template`/`variableContext`/timestamps directly on the
node). This deliberately mirrors `ComputerNode`'s own `CATEGORY`/`ENTRY`
split — leaf-only fields live on the node itself, not nested in a
separate wrapper object — but it's **one tree with one implicit root**
(`StatementRepository.ROOT_ID`), not one-tree-per-category the way
`ComputerCategory` wraps a `root: ComputerNode` per named category.
Statements don't have Target Computer's `[COMPUTER:id]`-binding
requirement that forces multiple independently-addressable root
categories, so a single tree is the more literal read of "tree > leaf"
and there was no reason to carry the extra `Category` wrapper level over.
The root node itself is never rendered as a row anywhere (same convention
as `ComputerCategory.root`) — only its `children`, recursively, are.

`StatementRepository` exposes tree-shaped operations (`getRoot`,
`upsertNode`, `createFolder`, `deleteNode`, `renameNode`, `findNode`,
`listFolders`) rather than a flat CRUD list. `upsertNode(context, node,
parentId)` always removes the node from wherever it currently lives in
the tree first, then reinserts it under `parentId` — this is what makes
re-saving a statement under a different folder in the composer's SAVE
dialog work as a **move**, not a duplicate; no separate "move" operation
exists or is needed. `computer/ComputerTreeWindow.kt`'s
`TreeVisualRow`/`flattenVisibleTree`/`ComputerTreeVisualRow` pieces were
**not** reused for the statement tree browser (`StatementTreeRow`/
`flattenVisibleStatementTree` in `StatementComposerView.kt` instead) —
`StatementNode` and `ComputerNode` are different types with different
per-leaf fields (no contact cards, no legacy strategy; a folder/leaf split
instead of category/entry), so genuine code reuse there would need
generics rather than the two node types coexisting as-is. Two small
parallel tree implementations were judged cheaper than that indirection.
**If a third tree-shaped feature ever shows up, that's the point to
reconsider a shared generic tree component — not before.**

**Migration**: before this tree existed, `StatementRepository` stored a
flat `List<SavedStatement>` under prefs key `saved_statements`.
`StatementRepository.getRoot()` checks for a tree first; if none exists
yet, it reads that old flat key once (`LegacySavedStatement`, kept
private, migration-only), wraps every entry as a direct `STATEMENT` child
of a fresh root, and writes that as the new tree — same "never silently
drop what a tester already created" reasoning as every other migration in
this app. The old key is never deleted, so nothing is destroyed even if
migration logic ever needs revisiting.

**Backup**: `AckBackup.savedStatementTree: StatementNode?` (nullable —
"nothing to say about this field" on an old backup) replaced the earlier
`savedStatements: List<SavedStatement>` field outright, without a
transition period, since this shipped pre-release (the whole system is
still inside `[1.0-beta.8] - Unreleased`). Restore
(`TransferManager.restoreStatementNode`) walks the backup's tree
pre-order and calls `StatementRepository.upsertNode` on every node
individually (folders included), which is what keeps this additive: a
node the backup doesn't mention is left exactly where it is, since
`upsertNode` only ever touches the specific node id it's given, never a
whole folder's contents wholesale.

### Token insertion vs. literal insertion — the rule that's easy to get backwards

Two Target Computer picker composables are shared with legacy Manual
Override (`computer/ManualOverrideTargetBrowser.kt`): `TargetQuickAccessRow`
(the "currently active per category" chip row) and `TargetBrowsePanel`
(the full tree/dropdown browser, reached via BROWSE TARGETS). Both take an
`onInsert: (categoryId, label) -> Unit` callback — the callback, not the
picker, decides what actually lands in the field. The composer's two call
sites deliberately do **different things**, and this is not
inconsistency, it's correctness:

- **`TargetQuickAccessRow` (chips) → insert a `[COMPUTER:id]` token.** A
  chip *is* the category's currently-active entry, which is exactly what
  a `[COMPUTER:id]` token resolves to. Tapping a chip is the one place in
  the composer safe to insert a live reference by default.
- **`TargetBrowsePanel` (BROWSE TARGETS) → insert the literal `label`
  text, never a token.** The browse panel can land on any entry in the
  tree, active or not. A token can only ever mean "whatever's currently
  active in this category" — if the user browses to a *non-active* entry
  and a token were inserted anyway, it would silently resolve to the
  wrong value the next time the statement is used (whatever happens to be
  active then, not what was actually picked). There is no way to make a
  token correctly represent a specific non-active pick, so literal text
  is the only correct choice here.

**If this system is ever extended (a new picker, a new insertion
surface), apply the same test before deciding token vs. literal: does
this specific UI element only ever represent "whatever's currently
active"? Only then does a token belong.** `SharedVariablePicker` (this
file, composer-local, not shared with legacy) inserts `{VAR:tag}` tokens
unconditionally because RootOverrideRepository slots don't have a
"non-active" concept the way Target Computer tree entries do — every slot
shown *is* the live value for that tag.

### Long-press a chip to retarget its category, app-wide

`TargetQuickAccessRow` takes an optional `onLongPress: ((categoryId) ->
Unit)? = null` parameter (default no-op, so legacy Manual Override's two
call sites are unaffected — they simply don't pass it). The composer
supplies it: long-pressing a chip opens `ComputerTreeWindow` — **the
exact same dialog the Target Computer tab itself uses** — for that
category, wired identically to how `computer/TargetView.kt` opens it
(same `onDismiss`/`onChanged`/`onOpenContactCard` shape, including
`ContactCardDialog` for contact-card entries). Picking a new active entry
there calls `ComputerRepository.setActiveEntry` for real, exactly as if
the user had done it from the Target Computer tab — this is a genuine
app-wide state change, not a composer-local copy of "what's active."
`targetRefreshKey` (incremented from `ComputerTreeWindow`'s `onChanged`)
forces both the chip row (via `key(targetRefreshKey) { TargetQuickAccessRow(...) }`
— that composable has no refresh-key parameter of its own, so it has to
be torn down and rebuilt to re-read `ComputerRepository`) and the live
preview (included in `resolvedPreview`'s `remember(...)` keys) to pick up
the change immediately. **Reuse `ComputerTreeWindow`/`ContactCardDialog`
wholesale for any future "retarget from elsewhere" affordance rather than
building a parallel picker** — that's what keeps this a real, single
source of truth for "what's active" instead of a second one that can
drift from the Target Computer tab's own.

### Legacy Manual Override lives behind Terminal's `/m`, not a `Dialog`

Legacy Manual Override (`ui/DesignSystem.kt`'s `TypeView` — unchanged code,
just relocated) is reached by typing `/m` at the Terminal prompt
(`TerminalPromptResult.ShowManualOverride`, parsed in
`parseTerminalCommand`, listed in `/help`). `TerminalView` takes an
`onShowManualOverride: () -> Unit` callback; `MainActivity` sets
`showLegacyManualOverride = true` there and also dispatches
`helpManager.onEvent(HelpEvent.WatchInput("MANUAL_OVERRIDE_OPENED"))` —
the pre-existing `"manual_override"` HELP module (in `HelpRegistry.kt`)
gates a step on that exact `WatchEvent`, having been fixed to route to
`HelpDestination.TERMINAL` instead of `.TYPE` (its destination before
this system existed).

**This is deliberately rendered in place of whatever `viewMode` currently
shows — `if (showLegacyManualOverride) { TypeView(...) } else { when
(viewMode) {...} }` inside MainActivity's main content `Box` — rather
than as a `Dialog`.** A `Compose` `Dialog` renders in its own Android
Window, layered on top of the *entire* screen including MainActivity's
own header. `ManualOverrideHeaderTakeover` (the quick-insert controls
that swap in for MainActivity's header while the keyboard is up) only
works because it's part of the *same* window as the content below it —
put `TypeView` in a separate Dialog window and the header takeover would
still technically "activate" underneath, invisibly, doing nothing
visible. `viewMode` itself is left untouched while the overlay is
showing, so dismissing it (`[CLOSE]`, top-right) returns to exactly
wherever Terminal was. **If a future escape-hatch/overlay screen needs to
share a keyboard-adjacent header takeover (or any other MainActivity-
window-scoped UI) with its content, it has to be rendered the same way —
in-place inside MainActivity's own content tree, never inside a `Dialog`
composable.**

`showComputerHeaderTakeover` is gated on `showLegacyManualOverride &&
isKeyboardVisible`, not `viewMode == "TYPE"` — `TYPE` no longer means
legacy Manual Override, so gating on it would either never fire (correct
by accident) or fire for the composer (wrong, the composer owns its own
local text field state and header takeover would insert into
`manualOverrideText`, which the composer never reads).

### FULL SCREEN hides MainActivity's own chrome, not the OS status bar

The composer's `isFullscreen`/`onToggleFullscreen` params (both optional,
default off/no-op) are hoisted to `MainActivity`'s `composerFullscreen`
state. When on, `MainActivity` removes its header `Column` and bottom-nav
`Row` **from composition entirely** (`if (!composerFullscreen) { ... }`),
not just visually — the content `Box` already has `weight(1f)`, so it
claims the reclaimed space automatically, no extra layout math needed.
`composerFullscreen` resets via `LaunchedEffect(viewMode)` the instant
`viewMode` leaves `"TYPE"`, so no other screen can ever get stuck without
its own chrome. This is scoped to ACK's own header/nav, deliberately not
a true OS-level immersive/edge-to-edge mode (no
`WindowInsetsControllerCompat` calls, status bar untouched) — that's a
bigger, more invasive surface than "more room within the app" asked for.

Inside the composer itself, the title row (with the FULL SCREEN toggle)
is pinned **outside** the scrollable content `Column` — if it scrolled
with everything else, a long statement could scroll the only way back out
of fullscreen off-screen. Any future full-bleed mode in this app should
keep the same rule: whatever toggles it back off must live outside
whatever it makes scrollable.

### File map

| File | Owns |
|---|---|
| `composer/StatementComposerView.kt` | The composer screen: field, variable-context row, live preview, insertion aids, SAVE/COPY/SPEAK, MY STATEMENTS tree browser, FULL SCREEN toggle, the long-press retarget dialogs, `StatementTreeRow`/`flattenVisibleStatementTree`/`FolderPickerColumn` |
| `data/StatementRepository.kt` | `StatementNode` tree model (`FOLDER`/`STATEMENT`, leaf fields on the node), `StatementRepository` (`getRoot` with one-time flat-list migration, `upsertNode`/`createFolder`/`deleteNode`/`renameNode`/`findNode`/`listFolders`) |
| `help/StatementComposerHelp.kt` | The composer's own HELP module, `destination = HelpDestination.TYPE` |
| `computer/ManualOverrideTargetBrowser.kt` | `TargetQuickAccessRow`/`TargetBrowsePanel`/`ManualOverrideHeaderTakeover` — shared with legacy Manual Override, `onInsert`/`onLongPress` let each caller decide token vs. literal and whether retargeting is offered |
| `computer/ComputerTreeWindow.kt`, `computer/ContactCardView.kt` | Reused wholesale (not reimplemented) for the composer's long-press retarget dialog |
| `ui/DesignSystem.kt` | `TypeView` (legacy Manual Override, unchanged), `TerminalView`'s `/m` parsing (`parseTerminalCommand`, `TerminalPromptResult.ShowManualOverride`) |
| `MainActivity.kt` | `showLegacyManualOverride` state, the in-place (non-`Dialog`) overlay render, `showComputerHeaderTakeover` gating, `composerFullscreen` state and the header/nav `if (!composerFullscreen)` guards, the `"TYPE" -> StatementComposerView(...)` dispatch |
| `help/HelpRegistry.kt` | Both HELP modules registered under `HelpCategory.BASICS_MANUAL_OVERRIDE`; the legacy module's destination fixed to `TERMINAL` |
| `backup/AckBackup.kt`, `backup/TransferManager.kt` | `savedStatementTree: StatementNode?` — nullable field, validated recursively (`isStatementNodeValid`/`countStatementNodes`/`collectStatementNodeIds`: node count cap, `SAFE_KEY_PATTERN` id, `MAX_PHRASE_LENGTH` template, `variableContext` checked against `POSE_CATEGORIES`/custom-context-name pattern, tree-wide duplicate-id check), restored node-by-node pre-order (`restoreStatementNode`) so an unmentioned node is never touched |

## The TRAINING DATA CAPTURE system — deep analysis

Lets the person gather voice-model training data **on the phone, away from the computer**: read scripts (or just talk) into ACK, have the
phone cut and note each clip, save a package to a file, move it to the PC yourself, and import it into Freeform Studio. Entered from
AUDIO ARCHITECT → CUSTOM VOICE → RECORD TRAINING DATA. The PC half (`ack_package.py`, `ack_import.py`, `ack_segments.py`, `ack_checks.py`,
`ack_web.py`, and the "Add recordings from ACK" card) is described in `tools/freeform_studio/README.md`; this section is the phone half and
the contract between them.

### The format is an executable specification

`docs/ACK_TRAINING_CAPTURE_FORMAT.md` is the contract (package layout, manifest, measurements, card splitting, hands-free detector, cut
proposer, constants). Its rules are **also running code**: `tools/freeform_studio/tests/ack_capture_reference.py` (Python) and
`app/.../capture/` (Kotlin), both held to the same JSON cases in `tools/freeform_studio/tests/data/ack_capture/` (`cards`, `handsfree`,
`segments`, `metrics`, `manifest_example`, and `fuzz.json`: ~190 seeded random cases for the places two implementations quietly differ).
To change a rule: edit the reference and the document's constants block together, `python tools/freeform_studio/tests/ack_capture_reference.py
--write`, and make the Kotlin pass. A test fails if the document, the reference and the cases disagree, and the Kotlin tests fail if the port
drifts. **Every new rule needs exact-boundary cases** (exactly the limit, one hop under, exactly at the threshold): breaking the Kotlin on
purpose (`>=` for `>`, a dropped abbreviation, one symbol removed) first showed ~10 such comparisons nothing was testing. Two details that
bit: a hop is `sample_rate // 100` samples (441 at 44.1 kHz, not 480), and a word is a letter or number of *any* script split on *any* Unicode white
space (Kotlin's `isWhitespace` includes no-break spaces, Python's `split()` too; U+0085 needs adding by hand).

### Two layers, and the line between them

- **`capture/` is plain Kotlin: no `android.*`, ever.** Models, `LevelMath`, `CardSplitter`, `HandsFreeDetector`, `CutProposer`, `NoiseCheck`,
  `WavFile`/`WavStreamWriter`, `AudioScan` (streams a recording from disk so a 90-minute file never sits in memory), `TrainingStore` (files),
  `ScriptCaptureEngine`, `FreeCaptureEngine`, `PackageWriter`/`PackageVerifier`/`PackagePlanner`. Tested on a JVM: `tools/kotlin_check/run_unit_tests.sh`
  (140 tests; also what `./gradlew :app:testDebugUnitTest` runs). The harness compiles that folder recursively, so one Android import there breaks it.
- **`voicecapture/` is the Android edge** and is kept thin: `TrainingCapture` (paths, prefs, one shared `TrainingStore` so its locks cover every
  screen), `TrainingMicrophone` (AudioRecord, 48 kHz else 44.1 kHz, UNPROCESSED else VOICE_RECOGNITION, a second of headroom), the runners (polled
  `@Volatile` state; a screen reads it ten times a second, never a hundred), and the Compose screens. `tools/kotlin_check/run_typecheck.sh`
  type-checks it against Compose Multiplatform (same `androidx.compose.*` API, on Maven Central) plus stubs of the Android classes: finds Kotlin/Compose
  mistakes, **cannot** find a wrong Android signature or anything about the microphone or layout. Add stubs when you use a new Android API.

### How audio is kept safe (the engines)

- A card is in the notes as `OPEN` **before** its first sample, and every sample goes straight to that card's file. When the detector decides the card
  is finished, the file is cut to the clip (lead-in, speech, tail) and the audio heard after the clip's end is **carried into the next card's file**, so a card
  started promptly loses no words, and a clip never reaches back into the one before. Decided one 10 ms hop at a time, so the clips are identical
  whatever chunk size the microphone delivers (a test feeds 1 to 48000 samples).
- Notes are written to a temp file, fsynced, and moved into place (`ATOMIC_MOVE`): a crash leaves the old notes or the new, never half. After a crash
  `TrainingStore.recoverOpenSessions` repairs the header of any unfinished clip or recording and marks it `RECOVERED`: **held back from packages until the
  person listens and keeps it**. It also looks at *ended* sessions with unfinished audio (a final scan that failed). **Nothing is deleted except a file with
  no audio in it**; a file that isn't ours is left byte-for-byte. A kept clip is never deleted on its own; deleting a session is the caller's job and the UI
  asks twice. Redo sets the old attempt aside (`REDONE`), it stays on disk.
- **Taps.** The app's buttons (`NeonButton`, `TightPanelButton`) give haptic feedback; with the microphone open a buzz or thump lands in the next card. The
  capture screen uses its own haptic-free buttons, makes no sound or vibration, and the engine ignores 0.3 s of audio after a touch-driven (re)start
  (`SETTLE_HOPS`; not written, not listened to, not counted). Don't add sound, vibration or a standard button to that screen.
- **Rotation.** `MainActivity` declares no `configChanges`, so rotating rebuilds the composition (and would end a recording). The capture screen locks
  orientation (`SCREEN_ORIENTATION_LOCKED`) and keeps the screen on while it is up, and pauses on `ON_STOP` (a backgrounded app loses the microphone).
  Anything that tears the screen down ends the session cleanly (kept clips stay kept).
- Disk: needs 300 MB free to start; the engines pause (script) or stop and keep (free) before the last 100 MB. Free speech stops itself at 90 minutes.

### Packages, saving, and the rules that must stay true

`PackageWriter` checks everything the PC's reader checks **before writing a byte** (ids, times, texts, audio headers against file length, sample rate and
length noted), cleans text the person typed rather than refusing it (a line break becomes one space; cut to length without splitting a surrogate pair),
streams each file into the zip while hashing it, writes the manifest last, and produces identical bytes for identical input. A file that changes while
being packed stops the export. `PackageVerifier` reads a saved package back and compares every file's size and checksum; the export screen runs it and
**deletes the half-made file on any failure** (`DocumentsContract.deleteDocument`) and says nothing was lost from the phone. Saving is **only** through
`CreateDocument` (the system file picker): **no share sheet, no network, no Intent that can hand the audio to another app.** Packages are not deleted
because they were saved. Scripts (text only) are in the full JSON backup (`AckBackup.trainingScripts`, validated with specific `ACK_IMPORT` logging, restored
by id, never removing anything); recordings are not (they travel as packages). `tools/freeform_studio/tests/test_kotlin_package_contract.py` opens
Kotlin-written packages with the real Python reader and importer (skipped unless `ACK_KOTLIN_PACKAGES` points at a folder).

### Not verified, and where the risks are

Built and tested without an Android SDK, so **never run on a phone**: the Android build, `AudioRecord` behaviour on real devices (some phones lack an
unprocessed source or refuse 48 kHz), the Compose layout (five mark buttons across a narrow screen, the card text size), the file picker flow, and
`OutputService` previews of clips. `tools/kotlin_check` covers the logic and the Kotlin of the screens, not these. `docs/` has the user-facing steps; the
HELP walkthrough is `help/RecordTrainingDataHelp.kt`, kept in step with the screens by `test_training_capture_wiring.py`.

### File map

| File | Owns |
|---|---|
| `docs/ACK_TRAINING_CAPTURE_FORMAT.md` | The contract: package, manifest, measurements, card splitting, hands-free, cut proposals, constants |
| `tools/freeform_studio/tests/ack_capture_reference.py`, `.../data/ack_capture/*.json` | The executable reference and the shared cases both sides must reproduce |
| `app/.../capture/` | All the portable logic (see above), no `android.*` |
| `app/src/test/.../capture/` | 140 JVM tests; `Vectors.kt` finds the shared cases and the document from any working directory |
| `app/.../voicecapture/` | `TrainingCapture` + `TrainingMicrophone`, `CaptureRunners`, `TrainingCaptureHome` (library, sessions, saving), `ScriptEditor`, `CaptureSessionScreen`, `SessionDetailDialog` |
| `help/RecordTrainingDataHelp.kt`, `AckTags.kt` (`TRAIN_*`) | The walkthrough and its tags |
| `backup/AckBackup.kt`, `backup/TransferManager.kt` | `trainingScripts` in the full backup |
| `tools/kotlin_check/` | The two Gradle projects that test/type-check without the SDK |

## SAFETY DEFAULTS — rules that must stay true

Seven problems were found when ACK was evaluated for use with clients: long messages cut short on screen, a robotic default voice, no check
for the display permission, a silent failure on the watch route, no way to confirm an Emergency tap, and a speech-markup bug. All of them
made the app show or say something different from what the person meant. The fixes are listed here with the rules that keep them fixed.
`docs/SAFETY_DEFAULTS_DEVICE_TEST.md` is the on-device checklist; everything below was built and tested **without an Android SDK**, so the
screens, the sound and the watch were never run (the harness covers `core/` only).

### Seed, don't flip — new defaults reach fresh installs only
- `AckApplication.onCreate` calls `data/InstallState.ensureRecorded` **before any screen touches storage** (MainActivity's first run writes
  `CUSTOM_VOICES` into `ack_prefs`, which would otherwise make every install look existing). It asks `core/InstallClassifier` whether any
  preference file the app owns holds a key other than the seed keys; if not, the install is **fresh**, and only then are the defaults
  written: `USER_VOX_PROFILE = "ORGANIC"` (only if absent) and one `FULL TEXT` visual preset (`bypassTruncation = true`, set active). The
  flags `recorded`/`fresh` go into `ack_install_state` with `commit()`. A seed that was interrupted still reads as fresh next launch, because
  the seed keys are ignored (a test pins `SEED_KEYS`). Add a new preference file to `InstallState.OWNED_PREFS_FILES`; add a new seed key to
  `SEED_KEYS` **and** the seed together.
- **Never change a read-site fallback to make a default "take".** The five `"CYBER"` fallbacks (MainActivity, AudioView, OutputService ×2,
  TransferManager) and `VisualPreset.bypassTruncation = false` stay, so an install that never chose, an older saved preset, and an older backup
  all behave as before. The only all-install change is on error paths: `getProfile`'s unknown id and `deleteProfile` now fall back to ORGANIC.
- An **existing** install is offered the same defaults once (`core/DefaultsOffer`, `settings/DefaultsPrompt.kt`, `defaults_prompt_dismissed`):
  a banner, then a review where every switch starts **off**, BACK UP FIRST, and APPLY. Applying full messages **adds** a new `FULL TEXT` preset
  copied from the active one; it never edits the person's own. It never starts HELP or navigates (see the HELP navigation pitfall above).

### `core/` is plain Kotlin, like `capture/`
No `android.*`, ever; `tools/kotlin_check/run_unit_tests.sh` compiles `capture/` **and** `core/` (195 tests in all when this was written; the "140"
quoted in the capture section is `capture/` alone). It holds the *decisions*: `InstallClassifier`, `DisplayText`, `DefaultsOffer`,
`NoticeRateLimiter`, `RelayAckTracker`/`WatchRelayProtocol`/`RelayMissStreak`. The Android code that calls them stays thin. New rules get boundary
tests; break the code on purpose once and watch a test fail.

### The display-text rule
`core/DisplayText.resolveDisplayText(rawPhrase, targetName, matrixVisualOverride, fullText)`: override, then target name, then (if `fullText`) the
whole phrase, otherwise the **legacy** 5-word rule (`ALERT:` + 3 words). `VisualLogicEngine` is a thin wrapper passing `preset.bypassTruncation`
(the stored name is unchanged so backups and old presets decode; the editor calls it SHOW FULL MESSAGE and warns while it is off). The preset size is
the **largest** size: `VisualPromptService` auto-sizes 24 sp up to it in 2 sp steps, and a message that still does not fit moves into a `ScrollView`
with SCROLL FOR MORE. Autosize throws the text layout away and asks for another pass, so the overflow check waits for the first non-null layout;
the tap/hold handlers go on the text view itself in scroll mode, because a ScrollView swallows touches. `showOverlay(fitText = true)` is for text
prompts only. `index.html` mirrors the new default (whole message, capitals).

### Display permission and Silent Mode
`ui/OverlayPermissionBanner.kt` shows a non-dismissible red banner while `Settings.canDrawOverlays` is false and re-reads it on resume through the
hosting `ComponentActivity`'s lifecycle (the same way `CaptureSessionScreen` does, known to build; do not swap in `LocalLifecycleOwner` without a
compile). `OutputService` logs MESSAGE SPOKEN BUT NOT SHOWN, and for Silent Mode with no permission NOTHING WAS SHOWN OR SPOKEN plus a toast, each
at most once a minute (`NoticeRateLimiter`). **Silent Mode is never overridden.** The old `SetupActivity` was dead code and is gone.

### The watch audio relay: chunk, confirmation, cancel
`core/WatchRelayProtocol` pins the bytes. `/audio/relay_chunk` phone→watch (12-byte header + PCM). `/sys/audio_relay_ack` watch→phone (transfer id, 4
little-endian bytes), sent by `AudioRelay.play` only after `track.play()` returns. `/audio/relay_cancel` phone→watch (same id) after a timeout.
`WatchAudioRelay.sendAndAwait` calls `RelayAckTracker.expect` **before the first chunk is sent** (the ack can beat the wait), waits
`relayTimeoutMs(chunks)`, and `playPcm` returns early **only for DELIVERED**; NO_WATCH and NOT_CONFIRMED play on the phone, with the cause logged. The
watch is a separate module (`com.example.besu.wear`) with its own copy of the bytes: change both together, update the watch manifest path filters, and
release both apps together. Known limits: a late ack can play on both; an un-updated watch never confirms, so each message waits out the timeout.

### Emergency rules
Emergency messages **and their alert tone always play on the phone** (`playPcm(isEmergency)`), speak **with no voice effects** whatever profile is
active (`withoutVoiceEffectsIfEmergency`; base system voice, Master Gain and the boost are kept), and can optionally ask for confirmation before
sending (`EmergencyDeckConfig.confirmBeforeSend`, default **false**, a recorded decision; SEND speaks the phrase that was shown, not a fresh resolve).
Terminal `/e` is typed on purpose and never asks.

### Cadence is retired
`applyCadenceWarp` made each word's speed random and inserted words into SSML unescaped, and the result also reached the Piper voice, which does not
parse SSML. The slider and the speech path are gone; the stored `VOX_CADENCE` value is kept (never deleted) and still travels in EXPORT .JSON
(`dsp.cadence`) so old and new backups restore. **Do not send markup to the custom voice.**

## PRIVACY & DATA PROTECTION — rules that must stay true

Written for the privacy work that followed the client-use review (export warning, DELETE DATA, DELETE CUSTOM VOICE, SAFETY COPIES, the backup reminder,
the free-speech notice). On-device checks are in `docs/PRIVACY_DEVICE_TEST.md`; what each permission is for is in `docs/PERMISSIONS.md`.

- **Export warning.** `core/ExportContents.kt` is the one source for what EXPORT .JSON says it holds and that it is **not encrypted** (the settings
  dialog and the Terminal `/backup`). A test reads `backup/AckBackup.kt` and fails if a field is not in a category, so **map every new backed-up
  field** there. There is no catch-all category on purpose.
- **Per-device state never goes in `AckBackup`.** The last-backup time, a snooze and the reminder on/off (`backup/BackupState.kt`, prefs
  `ack_backup_state`) describe *this phone*; a restored phone has its own history. Restore never marks a backup as made (it merges, so the result is
  not necessarily what any file holds).
- **Storage catalogue.** `core/StorageCatalogue.kt` lists every area DELETE DATA offers and the words its confirmations use; `data/DataWipe.kt` walks
  it. A test scans the app source for every preference file and folder and **fails if one is in no area** (or in `NOT_PERSONAL`, with a reason), so a
  new place that stores data cannot be added without deciding how it is deleted and backed up. `ack_matrix_config` and `ack_prefs` are shared and
  split by key (the Emergency card key; the Terminal log key), with a test that the split has no gap and no overlap.
- **The wipe's side effects.** SAVED LOCATIONS removes Google's geofences and **waits** for it (`GeoEngineController.stopAllAndAwaitGeofenceRemoval`):
  `removeGeofences` is asynchronous and nothing re-runs the teardown at launch, so a restart straight after could leave them registered; if Google mode
  is on and removal is not confirmed, the zones are left alone. PEOPLE AND PLACES re-sends the paired watch empty lists (best effort). SETTINGS and
  EVERYTHING re-seed the new-install defaults (`InstallState.seedDefaultsAfterWipe`). A wipe that needs it ends with the usual toast, a 1.5 s delay and
  `restartApp`; one that fails lists areas by name only and does not restart.
- **Every delete asks twice, CANCEL prominent, a backup named first.** New dialogs use `NeonButton` (12 sp) and `ConfirmBodyText`, **not**
  `TightPanelButton` (10 sp): the 12 sp floor for anything new is a tracked problem.
- **The backup reminder is a reminder only: it never writes a file.** The banner shows on the Terminal and Settings screens only, never on a deck or
  Emergency screen where it could move a button about to be tapped; the header save icon's slot (left of HELP) is always laid out so nothing shifts when
  it appears. The fingerprint is `core/BackupFingerprint.kt` over the no-audio backup (`TransferManager.backupFingerprint`); audio is never read for it.
- **Copied text is plain on the clipboard, on purpose.** The developer wants to see it in the clipboard preview. Do not add the sensitive flag or a
  clearing timer without asking.

## STARTER PHRASES, TYPING and SUGGESTIONS (Section 4, so far) — rules that must stay true

Written for the Language and vocabulary work: neutral starter phrases (L1), one shared insertion rule, and the history chips. What is
**not** built yet (plain-language mode, non-English voices and text, word prediction) is not described here; add those rules when they
exist. The profile-change warning is described in the last subsection. The device checklist is `docs/LANGUAGE_VOCABULARY_DEVICE_TEST.md`; the starter wording for review is
`docs/STARTER_PHRASES.md` (a test keeps it identical to the code).

### Starter phrases: seed, never edit the built-in text
- **`CommandRepository.BASE_TEMPLATE`'s strings are never edited.** A button with no saved value falls back to them (deck+profile value,
  then the same deck's DEFAULT-profile value, then `BASE_TEMPLATE`), so editing them silently changes what an existing person's untouched
  buttons say. `StarterSetsTest.theBuiltInText_isLeftExactlyAsItWas` pins the twelve strings. New defaults are **saved values**
  (`data/StarterSeed.kt`, wording in `core/StarterSets.kt`), written for a **fresh install only** and only where nothing is stored.
- **That fallback chain is per deck, not global.** Seeding only the DEFAULT deck left every other Matrix deck, and a wiped phone, on the old
  wording. So a new Matrix deck on a seeded phone is seeded too (`CommandRepository.createDeck`), and DELETE DATA > MESSAGES AND DECKS
  (so DELETE EVERYTHING) saves the twelve again (`DataWipe.wipe`). The STARTERS Quick Actions deck is only made on a brand-new install.
- **The starter seed is not part of `seedFreshInstallDefaults`.** That function also runs after a SETTINGS wipe; seeding phrases there
  would give an existing person's untouched buttons new phrases. `StarterSeed.seedFreshInstall` is called only from the fresh branch of
  `InstallState.ensureRecorded`. A test guards both.
- **`InstallClassifier.SEED_KEYS` lists every key the seed writes** (the twelve bare paths, `custom_decks_meta`, the STARTERS layout key, and
  the note file's keys), so an interrupted seed still reads as fresh and finishes. The pin test spells the keys out independently.
- **Storage keys come from `core/PhraseKeys.kt`.** `CommandRepository.generateStorageKey` delegates to it, so the repository and the seed
  cannot disagree. Never hand-write a phrase key.
- **The seed's note** (`ack_starter_seed`: `seeded:<path>` to the text it wrote, DEFAULT deck only) is per-phone state: owned by
  `InstallState`, cleared with MESSAGES AND DECKS, never in `AckBackup`. Written before the phrases, so an interruption leaves a note with no
  phrase (harmless) and never the reverse. `StarterSeed.wasSeeded` (read only) decides whether a new Matrix deck is seeded.
- **Restore takes back only untouched starters** (`core/StarterRestore.kt`, called from `TransferManager.applyBackupToStorage` BEFORE the
  file's phrases are written): a starter goes only if the file does not mention it AND it still holds exactly the text the seed wrote. The
  nullable `AckBackup.starterPhrasesSeeded` says where a file came from: **null (older) and false (phone had none) take starters back;
  only an explicit true keeps them.** The field is a format field in `ExportContents` and is on `BackupFingerprint.IGNORED_FIELDS`
  (otherwise every existing phone's fingerprint would change once and the backup reminder would fire). Never restore-delete anything else.

### One insertion rule
- **Every insert button goes through `core/TextInsertion.kt`**: the Composer, the Terminal's `/v` and `/t` (trigger as the replace range),
  Manual Override, and the Matrix and Quick Actions editors. It replaces the selection (ordered, clamped, never inside an emoji), never splits
  a token (`[COMPUTER:..]`, `{VAR}`, `{VAR:A..C}`; the patterns are checked against `TemplateEngine` by a drift test), adds a space only where
  one is needed, and an empty insertion changes nothing. `InsertionDriftGuardTest` scans the whole app source and fails on `replaceRange` or
  appending a token by string outside it. **The token-versus-literal rule is unchanged** (see the STATEMENT COMPOSER section): this rule
  decides where and how much space, never what goes in.
- **{VAR} values and [COMPUTER] fallbacks are stored by position.** Inserting a token mid-text without shifting those lists attaches every later
  value to the wrong token. `core/TokenSlots.kt` shifts them (values of replaced tokens go, a blank goes where the new token sits) and the
  editors call it before saving. Typing a token by hand mid-text still has the old problem (see the report).
- The editors' template fields are `TextFieldValue` so the cursor is known; they start with the cursor at the END (so a fresh editor's first
  insertion still lands last), and a cursor-only change is not a template edit.

### Suggestions: nothing changes without a tap
- `core/WordSuggestions.kt` decides what the history chips show and what is stored: nothing typed gives the old top five; typed text keeps only
  values that start with it (case-insensitive, NFC, a locale-independent lower-case so a Turkish phone is unaffected); "Mum" and "mum" are one
  word (the latest form is shown); what is exactly typed is not offered back; order is count, recency, value. **A suggestion is only a button:
  no auto-correct, no auto-complete on space, nothing inserted without a tap.** Reading never writes; recording touches at most one entry and
  never rewrites older duplicates.
- The chip row keeps a 56 dp height with or without chips (the developer chose a steady layout over hiding an empty row), is 14 sp with
  48 dp chips, shows both ends of a long value (`core/MiddleEllipsis.kt`), and uses no animation or haptics. `ChipRowGuardTest` holds it to this.
  Never use `NeonButton` or `TightPanelButton` for a chip: they vibrate, and a vibration is audible to a microphone that may be open.
- The per-scope cap (20) ranks by use count first, so a value typed for the first time is dropped at once when twenty others are used twice
  or more. Pinned by a test, not endorsed; decide before changing it.

### File map

| File | Owns |
|---|---|
| `core/StarterSets.kt`, `core/StarterSeedPlan.kt`, `core/StarterRestore.kt`, `core/PhraseKeys.kt` | Starter wording, what the seed writes, the restore rule, the phrase key recipe |
| `data/StarterSeed.kt` | The Android edge: seeds, notes, takes back untouched starters, `wasSeeded` |
| `docs/STARTER_PHRASES.md` | The review page (tables checked against `StarterSets`) |
| `core/TextInsertion.kt`, `core/TokenSlots.kt` | The insertion rule; shifting by-position values |
| `core/WordSuggestions.kt`, `core/MiddleEllipsis.kt` | The suggestion rules; shortening a long value in the middle |
| `data/AutocompleteHistoryRepository.kt`, `ui/SharedComponents.kt` | Load and save history through the engine; the chip row |
| `InsertionDriftGuardTest`, `ChipRowGuardTest`, `StarterSeedWiringTest`, `StarterRestoreWiringTest` | Source-reading guards for the Android-only files that cannot be compiled without the SDK |

### Profile-change warning (L7, the warning half) — rules that must stay true
- **The decision is `core/ProfileSwapDiff.kt`** (tested). It compares each Matrix slot's **resolved** phrase under the current and the target
  profile (`CommandRepository.profileSwapSlots`, which calls `getResolvedPhrase` twice). Never re-implement the fall-back to the DEFAULT
  profile, never compare stored keys, and never consume a single-use target. Equality is by `trim()` only, so a different capital letter or
  full stop counts and a space at either end does not. No differences means no warning at all (never interrupt for nothing).
- **Only the in-app PROFILE menu asks** (`MainActivity.requestProfileChange`, then `applyProfileChange`, which holds the unchanged
  `setActiveProfile` / watch / HELP-event steps). The home-screen widget (`OutputService` `CHANGE_PROFILE`) and a backup restore are
  deliberately NOT wired: the widget and watch are remote controls with no screen to ask on, and a restore is already confirmed. Do not put a
  dialog there without asking. The profile lock (D2) was decided against; a test fails if either path gains the warning.
- **Quick Actions, Emoji, GIF and Emergency decks have no profiles**, so their buttons never move. A test fails if `quickActionsKey`,
  `emojiDeckKey` or `emergencyKey` ever gain a profile parameter.
- **The switch (WARN BEFORE PROFILE CHANGES, SETTINGS > PROFILES) lives in `ack_assist_prefs`** (`data/AssistPrefs.kt`, decisions in
  `core/AssistSettings.kt`). Read with nothing stored it is **OFF**, so an existing install is unchanged; a new install and a phone after
  DELETE DATA > SETTINGS are **seeded ON** (this seed IS in `seedFreshInstallDefaults`, unlike the starter phrases, because it changes no
  data the person made); an install with nothing stored is offered it once. It travels in EXPORT .JSON as a nullable `AckBackup` field (null
  leaves the device's own choice alone) and is on `BackupFingerprint.IGNORED_FIELDS`. New person-chosen switches for Section 4 belong in this file.
- **The dialog is quiet and defaults to STAY**: no sound, no animation, nothing starts HELP; back and a tap outside are STAY; its checkbox
  writes the same setting as SETTINGS. A voice recording bound to a slot is not part of the comparison (a known limit).

### Word suggestions (L5) — rules that must stay true
- **Off until the person turns it on, on every install.** `AssistSettings.WORD_SUGGESTIONS_FALLBACK = false`; unlike the profile warning it is **never
  seeded** (`SEED_KEYS` does not hold it) and **never in `AckBackup`** (a restore must not turn a learning feature on). The one-time offer
  (`shouldOfferWordSuggestions`) shows in the Statement Composer; choosing either way in SETTINGS, TURN ON or NOT NOW retires it. Keys live in
  `ack_assist_prefs` with the other switches (`data/AssistPrefs.kt`).
- **The switch is checked inside `LearnedWordsRepository.learn` and `.predict`**, so no screen can forget it. Listing, forgetting and the backup are
  deliberately **not** gated: the words are the person's data whether or not the feature is on.
- **Learning happens in exactly one place: the composer's SAVE, COPY and SPEAK of the text typed there** (`learnFromCommittedText`: background thread,
  the same text counts once, a changed text counts again). Not MY STATEMENTS' own COPY/SPEAK, not the Terminal, Manual Override, the Emergency deck or
  any editor. `WordSuggestionsUiWiringTest.onlyTheComposerEverLearns...` fails if another file calls `LearnedWordsRepository.learn(`.
- **Names from elsewhere are read live and never copied** (`composer/WordSources.kt` → `core/ExtraWords.kt`): only Target Computer ENTRY names (not
  category headings, not contact cards: no phone numbers, addresses or emails) and Shared Root Variable slots that are on and filled in. Renaming or
  deleting a contact changes what is offered with nothing left behind.
- **Nothing typed is ever logged**, not in an error either. Every `Log.` line in `LearnedWordsRepository` must be `Log.x(TAG, "a fixed sentence")` (a test
  checks the shape); `LearnedWordsStore` has no logging; `WordModelData.validate()` reasons hold counts and lengths only, and `TransferManager` logs that
  reason to `ACK_IMPORT` before `return false`.
- **Storage is `filesDir/learned_words/model.json`, in the DELETE DATA > MESSAGES AND DECKS area** (not a thirteenth area: the words are derived from typed
  statements, like the typing history it already holds). `core/LearnedWordsStore.kt` is plain Kotlin and tested on a JVM: atomic save (temp file, fsync,
  `ATOMIC_MOVE`); a file that is not JSON, fails `validate()` or is over 8 MB is **set aside** as `model.json.damaged-<time>`, never overwritten or deleted;
  the file's size and time are compared on every use, so a wipe or restore behind its back is noticed and a wipe is never saved back over; reading never
  creates the folder; text with no word in it writes nothing; `forgetAll` removes every `model.json*` and nothing else.
- **The model** (`WordTokens`, `WordModel`, `WordPrediction`): words are letters of any script with an apostrophe or hyphen inside; anything with a digit,
  an emoji and a tag are never words; a full stop, `?`, `!`, an ellipsis, a line break, a tag or a digit ends a sentence, and words are only linked within one
  sentence. 5,000 words and 20,000 pairs, least used evicted (count, then last used, then key). A word that only ever started a sentence is stored lower
  case; a name in the middle keeps its capital. **Quiet is the rule:** nothing is offered mid-word, inside a tag, after punctuation or a line break, at the
  start, with a digit, or while text is selected.
- **The strip is `AutocompleteChipRow`** (the history chips' row: 14 sp, 48 dp, no animation, no vibration, reserved height while the feature is on), never
  `NeonButton`/`TightPanelButton` (they vibrate). A tapped word goes through `TextInsertion.insert(..., replace = prediction.replace)`. Nothing is inserted,
  corrected or completed without a tap.
- **Backup:** `AckBackup.learnedWords: WordModelData?` is null when nothing was learned; restore **merges** (never lowers a count, never removes a word, drops
  anything broken). It has its own line in `ExportContents` ("WORDS LEARNED FROM WHAT YOU SAVED, SPOKE OR COPIED", chosen by the developer so the export warning
  names it) and is on `BackupFingerprint.IGNORED_FIELDS` (it grows with ordinary use; counting it would make the backup reminder fire after a day).
- **FORGET WORDS** (`settings/WordSuggestionsSection.kt`): REMOVE on one word asks once more; FORGET ALL WORDS asks twice with CANCEL prominent and BACK UP
  FIRST named, the second confirmation being the only place `forgetAll` is called. 12 sp text, `NeonButton`, `ConfirmBodyText`.
- **Test-writing lesson:** a brace-matching `bodyOf(...)` on an *expression-bodied* function (`fun x() = y`) silently reads the NEXT function's body. Use
  `RepoFiles.declarationOf` for those. (`ProfileWarningWiringTest.theSwitchLivesInItsOwnFile...` passed by accident before this was noticed.)

### Voice list and SPEECH LANGUAGE (L3, part 1) — rules that must stay true
- **The picker lists every language, never a voice that needs the network or is not installed** (`core/VoiceListing.usable`, tested): sorted by language
  name (a `Collator` at PRIMARY strength with `Locale.ROOT`, so case and accents are ignored and a Turkish phone is unaffected), then voice name. ACK has no
  network permission and promises local-only speech, so such a voice is never offered. **`MainActivity.onInit` must not filter by `language == "en"` again**
  (a test fails if it does). A voice's **name is never changed** (a profile stores it exactly), and a voice a profile already chose stays chosen even when it is
  no longer listed. `output/VoiceInfoMapping.kt` is the only place an Android `Voice` becomes a `VoiceInfo`.
- **SPEECH LANGUAGE** (`core/SpeechLanguage.kt`, key `speech_language` in `ack_assist_prefs`, set in AUDIO ARCHITECT): THIS PHONE'S LANGUAGE (`DEVICE`) or ENGLISH (US)
  (`ENGLISH_US`). It only affects a profile with **no voice of its own**; a profile's chosen voice and the cloned MY VOICE are separate and untouched.
  **Nothing stored reads as ENGLISH (US)**, so an install that already existed speaks exactly as before (a German phone that always spoke English phrases must not
  start reading them with a German accent). A **new install is seeded DEVICE** (`SEED_KEYS` holds it, so an interrupted seed still reads as fresh), and so is a phone
  after DELETE DATA > SETTINGS, whose confirmation says so. Never change the read-site fallback to make a default "take".
- **A missing language is never silence.** `OutputService.applySpeechLanguage` asks the engine and, whatever it answers, goes on: after `tts?.setLanguage(` nothing
  may `return` or `throw` (a test checks), the engine keeps its own default, and a log line says so at most once a minute. `isTtsReady` is set whatever the
  language result was.
- **The engine keeps the last voice a profile chose**, so `speakWithSystemTts` remembers `voiceSetByProfile` and a profile with no voice re-asks for the language
  (`SpeechLanguagePolicy.needsApplying`: first time, the setting changed, or a profile's voice is still set). It is asked once, not every utterance.
- **Backup:** `AckBackup.speechLanguage: String?` (null = nothing to say, restore leaves the device's own choice alone), validated against the two stored names with a
  specific `ACK_IMPORT` line, mapped in `ExportContents`, an ordinary setting (not on the fingerprint ignore list).
- **No claim the app cannot keep:** `docs/PERMISSIONS.md` says what the system speech engine is and that what it does with text is outside ACK's control.
- **Plain words (L2) are only a proposal so far:** `docs/PLAIN_LANGUAGE.md` lists the jargon labels and the Terminal-only features; no code reads it, and nothing is
  wired in until the developer approves the wording. The developer chose the switch **off for everyone**, with one dismissible offer.
- **A test that bars a function may not bar a whole object:** `ProfileWarningWiringTest` used to fail if `OutputService` mentioned `AssistPrefs` at all; it now bars only the
  profile warning's own functions, because the service legitimately reads other switches in that object.

### PLAIN WORDS (L2) and INTERFACE LANGUAGE (L3, part 2) — rules that must stay true
Wording and decisions: `docs/PLAIN_LANGUAGE.md`, `docs/TRANSLATIONS.md`. Checklist: `docs/LANGUAGE_VOCABULARY_DEVICE_TEST.md` sections J and K.

- **A label is display text only.** The table is string resources (`label_<key>` standard, `label_<key>_plain` everyday) keyed by `core/LabelKey`; a screen asks
  `labelFor(LabelKey.X)` (`ui/PlainWords.kt`). A label never reaches an id, a storage key, a tag, an event, a log line, a token or anything typed: stored pose and
  slot names ("IDENTITY", "Twist 1") are matched exactly and shown through `poseLabel`/`slotLabel`, never rewritten. `PlainWordsScreensWiringTest` enforces this
  (no label inside `putExtra`/`onEvent`/`Log`/`upsert`, nothing but screens reads labels, no `.uppercase()` on one, no wired label also drawn as its English
  literal; the few places an English text is still logic are listed there and checked not to go stale). **A key with no screen yet goes on that test's short
  `notYetWired` list with a reason.** HELP text holds `{{KEY:Original}}` placeholders filled at draw time and for the spoken text (`helpText`, `HelpPlaceholders`).
- **PLAIN WORDS is off for everyone, never seeded** (the developer's decision), flips at once with no restart (Compose state, `PlainWordsState`, provided beside
  `LocalHelpManager`), and its own switch is worded identically in both modes so it can always be found. It is in EXPORT .JSON (nullable) and on the fingerprint ignore list.
- **The Terminal's plain-mode controls call the same code as the typed commands** (`clearHistoryNow`, `repairBackgroundServices`, `showLegacyManualOverride`, the
  `/v` and `/t` triggers); every typed command keeps working. The four send switches (`/q /n /s /e`) **stay on until turned off** (developer's choice), are kept in
  memory only (`TerminalSendSwitches`, nothing stored, wiped or backed up), count **only while PLAIN WORDS is on** (`SendSwitchPolicy`, a hidden switch must never make a
  message silent, unsaved or loud), and are turned off with it. `/e` and its switch never ask for confirmation. The closed SEND OPTIONS row names every switch that is on.
  New controls there: 12 sp or larger, 48 dp, no haptics, no animation, ON/OFF written in words.
- **INTERFACE LANGUAGE: an install that exists stays English, a new one follows the phone.** Read with nothing stored is ENGLISH; `seedFreshInstallDefaults` writes DEVICE
  (a seed key); DELETE DATA > SETTINGS reseeds it and says so. It is applied in `MainActivity.attachBaseContext` (`data/InterfaceLocale.kt`), never fails the launch, and a
  change **asks first and restarts once** (shared delayed `restartApp`). **No `android:localeConfig`**: Android 13's per-app screen would be a second switch the in-app one
  silently overrides (a test fails if it appears). Every `letterSpacing = N.sp` goes through `looseSpacing()` (Arabic joins; spacing pulls it apart); a test fails on a raw one.
- **The five translations (es, pt, hi, ar, af) are DRAFTS written without a native speaker** and must keep saying so (the notice at the top of each file, the control, the
  CHANGELOG, `THIRD_PARTY_NOTICES.md`). `TranslationsTest` checks completeness and safety only (same strings and `%1$s` placeholders, standard ≠ everyday, no two buttons
  sharing an everyday name except the four same-place pairs, capitals for es/pt/af, own script for hi/ar, escaping, the notice), never that the words are right. The options on the two HELP chooser dialogs (`FieldOpsHelp.poseOptions`, `VoiceRecordingsHelp.options`), **the lines other parts of ACK write into the Terminal**
  (the output service, the watch, Geo, the path trace: English text through the `ACK_LOG` broadcast), most dialogs and everything spoken stay English in every language; say so
  wherever the language is offered. HELP's chrome, **the walkthroughs' own text (see "HELP walkthrough text" below)** and the Terminal's own words (see below) are translated.
- **Kotlin the tests cannot compile can still hide a build error.** Two lines of text with nothing joining them are not one sentence: in a `when` branch only the last is used
  (the clear-variables confirmation lost its question this way), in a `listOf(` it is a build error (the `/info` notes did, which is one reason they are string resources
  now). `AdjacentTextLinesTest` reads every source file for it, and `TerminalTextListsShapeTest` fails if a hand-written list of text lines is put back in `ui/DesignSystem.kt`. `tools/kotlin_check/android-typecheck` type-checks `ui/TerminalPlainControls.kt`,
  `settings/InterfaceLanguageSection.kt` and the capture screens against Compose, with `R` generated from the real `strings.xml` (a wrong string name fails it).

### Wording in string resources (INTERFACE LANGUAGE, long tail) — rules that must stay true
Written while the backup and DELETE DATA wording moved into `strings.xml` (docs/TRANSLATIONS.md has the translation side).

- **A decision in `core/` names its words by resource and reads them through `core/TextSource`.** `ExportContents`, `BackupReminderText`, `StorageCatalogue`,
  `SafetyCopyPolicy` stay plain Kotlin; the Android edge is `data/ResourceText.kt` (`ui/rememberText()` in a composable), the tests' is `EnglishText` (the real
  English strings file, plurals by English's rule). A name that is not a resource reads as itself, so a gap shows. Never put `android.*` in `core/` to get a string.
- **A result is carried by id, never by a label.** `DataWipe.Result` holds area ids; screens and the Terminal line turn them into names. Anything that compares a
  displayed word (for example "did SAVED LOCATIONS fail?") breaks the day it is translated.
- **A resource's trailing space is trimmed by Android.** Join sentences in code (`joinToString(" ")`), never with a space at the end of a string.
- **A button or screen name inside a sentence is an argument, not a literal**, when that name is translated (`%1$s` = `label_export_json`), so a note and the
  button it points to read the same in every language. A name that is still a literal English button on its own screen stays English in every translation until
  that screen moves, and `DeleteDataWordingTest.theButtonNamesStillEnglish...` holds it there: change the notes and that test together.
- **A toast, a launcher callback and a `semantics {}` block are not composable lambdas**: read their text with `context.getString(R.string.x)` (or resolve it
  just before). Any file outside `com.example.besu` that uses `R.string` needs `import com.example.besu.R` (`ResourceImportTest`).
- **Every confirmation that deletes keeps its safety sentences in every language** (cannot be undone, back up first, files saved elsewhere are not deleted, the
  restart and watch notes); `DeleteDataWordingTest` fails if one is missing, is still English, or loses a placeholder. `/backup CONFIRM` and `/cls CONFIRM` are
  typed commands and are never translated.
- **Dates and numbers keep Latin digits.** `DateTimeFormatter.ofPattern(pattern, locale)` already does; only `localizedBy` would change that (a test pins it).
  The date's language is `ActiveScript.tag` (the language the words are really in), not the phone's setting.
- **The type-check (`tools/kotlin_check/run_typecheck.sh`) now compiles all of `core/` and the backup and DELETE DATA screens**; `BackupExporter`,
  `BackupReminder` and `DataWipe` are stubs written from their real signatures. Prove a new staged file is covered by breaking it on purpose once.
- **Source-reading tests**: a pattern like `.label` also matches `StorageCatalogue.label(...)`; use `area.label`. A "gone" literal test needs the positive
  assertion beside it (the new call is there), or a swapped argument slips through (found by mutation).
- **Names that are not words stay as they are, in every language, and are handed to a sentence as `%1$s`.** The developer decided (AUDIO ARCHITECT) that CYBER, MECH,
  ORGANIC, MY VOICE and the CUSTOM A, B... name a new slot is saved with are names, like a product name: the chips, the widget, HELP and every sentence agree. A
  sentence passes them in (`CustomVoiceRemoval.MY_VOICE_LABEL`, `DefaultsText.ORGANIC` / `CYBER`) and `AudioScreenWordingTest` / `DefaultsWordingTest` fail if a
  translation retypes one. If they are ever translated for display, do it the way the Emergency button names and the People categories are done (shown translated,
  saved text and ids never changed; `core/EmergencyLabels.kt`, `core/ComputerLabels.kt`) and only after the widget, the watch, HELP and the Terminal can follow.
- **An English name that is still on screen stays English inside a translated sentence**, held by a test (`ALERT:`, `FULL TEXT`, `SHOW FULL MESSAGE` in the defaults
  offer). When that screen is migrated, change the sentence and the test together.
- **A fixed width clips a longer word.** The DSP editor's ON / OFF buttons were `width(60.dp)`; they are `widthIn(min = 60.dp)` so DESACTIVADO fits. New buttons with a
  short English word should not fix their width.
- **A migration test must check that each word sits on the control that does the thing**, not only that the string exists: `AudioScreenWordingTest.everyButtonWordIs...`
  matches a word to the action that follows it. Mutation testing showed a swapped label (SAVE on a DELETE) passes every "string exists / literal gone" check.
- **The type-check stages a screen only if its Android edges are stubbed from their real signatures** (`tools/kotlin_check/android-typecheck/stubs/app/Audio*.kt` for
  AUDIO ARCHITECT). A stub is written from how the real code is used, so check it against the real file when that file changes.

### HELP chrome in string resources — rules that must stay true
Wording and checklist: `docs/TRANSLATIONS.md`, `docs/LANGUAGE_VOCABULARY_DEVICE_TEST.md` section K. Tests: `HelpMenuTextTest` (the decisions, in every language), `HelpWordingTest` (the screens), `PlainWordsWiringTest` (HELP text still goes through `helpText()`).

- **What is translated and what is not.** The header's HELP button (`help_button`), the menu, the nine family chips and headings, the cards' `[RUN]` and step line, the empty state, the two chooser dialogs (title, hint, `[CLOSE]`) and the coach panel (`GUIDANCE // n/m`, `[ABORT]`, `ACKNOWLEDGE // CONTINUE`, the nine "awaiting" instructions). **Not** translated: the choosers' option labels and hints (`FieldOpsHelp.PoseOption`, `VoiceRecordingsHelp.VoiceRecOption`). The walkthroughs' own text is translated (see "HELP walkthrough text" below).
- **A family's chip is its own string**, never cut out of the title at a "// " (a translation must not have to keep a separator). `HelpMenuTextTest` holds the chip to the end of its title, and to the whole title when there is no section.
- **Resource text keeps label placeholders unfilled and bare**: `{{DECKS}}`, never `{{DECKS:DECKS}}` (no English original in a translation) and never the filled word, so `helpText()` swaps in the standard word of the language or the everyday one under PLAIN WORDS. **No article before a placeholder** in a Latin-script draft ("GESTIÓN DE {{DECK}}", not "DEL {{DECK}}"): the everyday word may be the other gender. The walkthrough text (`helpmod_*`) is the one place English keeps its `{{KEY:Original}}` (so English is word for word what it always read); its translations use the bare form (see "HELP walkthrough text" below).
- **`HelpDestination.viewMode` is logic and never changes**; the card's "N STEPS // VIEW" shows a display mapping (`HelpMenuText.viewNameResources`). A destination with no words fails `HelpMenuTextTest`; an unknown mode reads as itself. These are the standard words, not the nav bar's labels (SETTINGS says SETTINGS, where the button is PROTOCOL), and they do not follow PLAIN WORDS: a known gap, kept as it always was.
- **The step count is a plural** (`help_menu_steps`), so one step reads "1 STEP". This is the one deliberate English change: the two chooser entries (one placeholder step each) used to read "1 STEPS".
- **The HELP button's name is an argument wherever a sentence points at it.** `voice_rec_help_offer` takes it twice (`%1$s`), and `TrainingCaptureHome`'s tip is `CaptureText.helpOffer(words, help_button, label)`. A sentence must never type an English "HELP" for a button that is now called AYUDA; `ManageRecordingsWordingTest` fails if one does. Any screen migrated later that mentions the HELP button does the same.
- **`[CLOSE]`, `[RUN]`, `[ABORT]` and `[GOT IT]` keep their brackets inside the resource** (HELP's house style; the shared dialog frame's `common_close` has none). `HelpWordingTest` holds it in every language.
- **Type-check:** `HelpMenuDialog`, `HelpCoachDialog`, `PoseSelectorDialog` and `VoiceRecordingsHelpSelectorDialog` are staged; `stubs/app/HelpModules.kt` gives the two option types they draw and `helpText` is stubbed in `stubs/app/AppUi.kt`. Proved by breaking three names on purpose.
- **A Kotlin KDoc that writes `help/*Help.kt` opens a nested comment** (`/*`) and the whole file fails with "Unclosed comment"; write "the per-feature files in help/".

### SETTINGS wording, plurals with arguments, and the syntax check — rules that must stay true
Tests: `SettingsWordingTest` (the screen's words, parts A to C), `OutputRouteTextTest`, `ProfileWarningTextTest`. Checklist: `docs/LANGUAGE_VOCABULARY_DEVICE_TEST.md` section K.

- **`TextSource.count(name, quantity, vararg args)`** is for a plural sentence that also names something ("2 GESTURES WILL SAY SOMETHING DIFFERENT IF YOU CHANGE TO WORK:"). `%1$d` is the
  quantity and `%2$s` the first of `args`, so the verb can agree with the number in each language. `ResourceText`, `EnglishText` and `FileText` override it; a source that does not
  reads as `count(name, quantity)` and drops the arguments, so a new `TextSource` that carries plurals must override it. `TranslationsTest` accepts `%d` or `%1$d` as the number.
- **`tools/kotlin_check/run_syntax_check.sh File.kt ...` for an Android-only file.** `SettingsView.kt`, `OverlayPermissionBanner.kt` and `SharedComponents.kt` use the SDK and cannot be
  type-checked here; after a wording edit to one of them it must print `syntax errors: 0`. It finds a missing bracket and nothing else (a wrong string name is `SettingsWordingTest`'s job).
- **A stored value is logic and never translated, and a unit is a symbol.** `AUTO`, `BLUETOOTH` and `WATCH` (the output route, read by `OutputService` and checked by the backup),
  `ms`, `s` and `dB` stay as they are; `String.format("%.1f", x)` is left to the phone's own number format and passed in as an argument. A Bluetooth device's own name is shown exactly as the phone gives it.
- **A sentence names a screen or a button as an argument only where its English is already all capitals.** A mixed-case English description that names "Target Computer" or "Quick Actions"
  keeps the standard names (the translation uses the language's own label, checked by a test) and does not follow PLAIN WORDS: a known gap. `REC` and `+REC` on the Quick-Access key
  buttons stay the English abbreviation (the buttons are narrow, and MANAGE RECORDINGS' empty-state sentence names them as REC). `RESOLVE` stays English inside the
  sentence that mentions it (the PATH trace lines are written in English by the data layer); the Terminal's own TYPING word is handed to the sentence as an argument
  (`settings_term_statusbox_desc`).
- **A gesture is named the way the Matrix screen names it** in the profile-change dialog (`slotLabel`, handed to `ProfileSwapText.lines` as `names`); a profile's own name and the person's
  phrases are shown as typed, and the connector "becomes:" stays lower case in every language because it sits between two phrases the person typed.
- **A fixed width clips a longer word** (again): `ThemeOption` (SHARP / CLEAN / SOFT) is `widthIn(min = 60.dp)` with a little side padding.
- **Source-reading tests measure "word then control" in characters, indentation included.** A regex like `R\.string\.x\)[\s\S]{0,260}?Slider\(` fails quietly when the code is indented
  more deeply than the test's author imagined; give a distance with room, and break the code on purpose once to see the test fail.

### Deck screens in string resources — rules that must stay true
Covers CREATE DECK, QUICK ACTIONS, EMOJI and GIF (`decks/CreateDeckDialog.kt`, `QuickActionsDeck.kt`, `EmojiDeck.kt`, `GifDeck.kt`). The decisions are plain Kotlin with tests in every language (`core/QuickActionLabels.kt`, `EmojiLabels.kt`, `GifLabels.kt`, `GifImportFailure.kt`; `QuickActionLabelsTest`, `EmojiLabelsTest`, `GifLabelsTest`); the screens are read by `DeckScreensWordingTest` (parts 1 to 4). `CreateDeckDialog` is type-checked; the other three use the SDK and are syntax-checked only (`run_syntax_check.sh`, listed in `tools/kotlin_check/README.md`).

- **A saved default is shown translated and stored English; a typed name is shown as typed.** A slot is saved `ACTION n`, a group `GROUP n`, a page `PAGE n`, a GIF category `UNCATEGORIZED` (one shared constant, `GifLabels.STORED_DEFAULT_CATEGORY`, which `GifRepository.createCategory` uses too), a new deck its English type name, a nameless GIF `UNTITLED GIF`. The screen compares the stored text for **exact equality** with the default (never `startsWith`, never ignoring case) and only then draws the language's word; the tests pin the source literals so a later "helpful" translation of a saved value fails.
- **Opening an editor and saving without touching the name must not rewrite it.** `QuickActionLabels.labelToSave(typed, shownAtStart, storedAtStart)` returns the stored text when the field still holds what was shown. A new editor over a saved name needs the same three values.
- **The prefilled text of a field that gets saved is saved text.** The import dialog's title (`UNTITLED GIF`) and a new deck's starting name stay English in every language, like CYBER or MY VOICE.
- **Why an import failed is carried by id.** `GifImportFailure` + `GifImportException` (still an `IllegalStateException` whose `message` is the old English text, so logs and callers see no change); `GifLabels.importError` says a known reason in the language, passes any other failure's own text through, and says GIF IMPORT FAILED when there is none. The repository's log-only `error(...)` calls in `restoreEntry` stay English.
- **A plural sentence with a second number: the quantity is `%1$d` and the extra arguments follow it.** `text.count("gif_imported_skipped_toast", imported, skipped)`, never `(imported, imported, skipped)` (that shifts every argument; caught while writing it, and `GifLabelsTest` uses 7 and 3 so a shifted argument shows a number twice). English keeps its exact wording ("3 SKIPPED"); a translation may restructure ("SKIPPED: 3") so no language has to agree a word with a number.
- **Arrows that mean a direction live in the resource, and a mirrored layout flips them.** `◀ PREV` / `NEXT ▶`; Arabic is `▶ السابق` / `التالي ◀` because its Row is mirrored (PREV is first, on the right). The ▲ / ▼ after BACKUP and CATEGORY are a state symbol, added in code.
- **"GIF" in a sentence is the file kind; the deck-type label is the deck.** Sentences about files keep `GIF` (es, pt, af) or the label's own script (hi, ar); only the screen title and the export toast take `label_deck_type_gif` and `label_deck` as arguments so they follow PLAIN WORDS.
- **`labelFor` is composable: capture it (and `rememberText()`) before a launcher callback.** A toast inside `rememberLauncherForActivityResult` uses `words` / `context.getString`, never `stringResource`.
- **Test-writing lessons.** `StringsXml.map` turns a resource's `\n` escape into a real line break, so resource-side tests compare a real newline while source-reading tests of the `.kt` keep the escape. A regex through an indented Compose block needs 700 characters or more between anchors (a 300 limit failed twice on indentation alone). All 64 deliberate breaks of these four screens (swapped labels, a translated saved name, a shifted plural argument, a dropped placeholder) are caught by a test.
- **Known open items:** `GifRepository.importGif` leaves a partly copied file when an oversized GIF is refused, and the import dialog creates its category before the import runs; the zip folder name `UNCATEGORIZED` in `GifBackupManager` is a stored name and stays English.

### Terminal and Manual Override wording — rules that must stay true
Covers `ui/DesignSystem.kt`'s legacy Manual Override screen (TYPE behind `/m`), the Terminal's own words and `/info`. Decisions are plain Kotlin with tests in every language
(`core/ManualOverrideText.kt`, `core/TerminalText.kt`, `core/PatchNotes.kt`; `ManualOverrideTextTest`, `TerminalTextTest`, `PatchNotesTest`); the screen is read by `ManualOverrideWordingTest`
and `TerminalWordingTest`. `ui/DesignSystem.kt` uses the SDK, so it is syntax-checked only.

- **Typed commands are logic and are never translated.** `/help /q /n /s /e /v /t /cls /backup /repair /info /m` and the word `CONFIRM` in `/cls CONFIRM` stay exactly as typed inside every
  translated sentence, and a command that is not known is echoed back exactly as typed (a test feeds it `%`, `$`, quotes and Arabic). `TerminalText.HELP_COMMANDS` holds each command as typed
  beside the resource that says what it does; the `/help` command column is padded to 17 characters **in code** so a description never has to keep the spacing, and the English output is held
  identical to the old list line for line. A check that a typed word survived must look for it **as a whole word**: "/cls CONFIRMAR" contains "/cls CONFIRM" and the parser would not accept it.
- **What the Terminal says is two different things.** Its own words (STATUSBOX, the prompt hint, replies to typed commands, `/help`, `/info`) are translated; lines other parts of ACK send in
  through `ACK_LOG` arrive as English text, are saved as written and stay English (translating them would mean carrying them by id through every sender and the saved log). A reply the Terminal
  writes itself is saved in the language of that moment, so a log kept across a language change shows both. Each reply keeps its log type (`CMD`, `CMD_WARN`, `CMD_ERR`), which decides how it is
  shown and filtered; a test pins each.
- **`/info`'s notes are one string per bullet or heading (`info_*`), listed in `PatchNotes.ENTRIES`.** English keeps its hard-wrapped lines (a bullet's lines joined by a line break) so `/info`
  reveals exactly the lines it always did, and the two-space continuation indent is added **in code**, because Android collapses runs of spaces in a resource (the same trap as a trailing
  space). A translation is one line per note and need not keep the English line breaks. A long line waits one more 2 s step per 71 characters (the longest English line), so a translated bullet
  gets time to be read; shake still stops it.
- **A release's new notes ship in English and are translated later.** `TranslationsTest` does not demand the `info_*` family in every language (Android falls back to the English string per
  string); `PatchNotesTest` fails if a name in `ENTRIES` has no English string, or an `info_*` string is not listed. To add notes: the English strings, their names in `ENTRIES`, CHANGELOG.md
  (which carries the same notes); translations when wanted.
- **A name that is still English on its own screen stays English inside a translated sentence**, so a reader can find it: `RECORD FREE SPEECH` and the capture screens' buttons, Freeform Studio's
  `ADD RECORDINGS FROM ACK`, commands, file names (`DOCS/....MD`), `STARTERS`, `MY VOICE`, `ACK WEAR`. `PatchNotesTest.thingsThatAreNotWordsComeThroughEveryTranslationExactly` holds the list;
  extend it when a note names something new, and when a capture screen is migrated, change the notes and that test together.
- **A saved phrase is a format argument, never part of the format.** The delete confirmation is two strings joined by one space in code (`ManualOverrideText.deleteQuestion`: the question with the
  phrase exactly as saved in straight quotes, then the warning that it cannot be undone and to export a backup first), so a test can check both are said in every language; it is fed a phrase with
  `%s`, `$1`, a quote and a line break. `/cls` has the same shape (`term_cls_question` and `term_cls_warning`, then the typed instruction): one combined string let a translation quietly lose its warning.
- **A shared word pinned in one group is flipped, not forgotten, in the next.** The Terminal's save dialog spells four words like the Manual Override one; the Manual Override change left it literal
  and pinned that with a test, and the Terminal change flipped the pin and read the same strings. Do the same when a later group shares words with an earlier one.
- **A source-reading test that quotes `$name` inside a `"""` raw string needs `[$]`** (the template swallows it); `\$` does not work there.
- **ENCODE and TRANSMIT have no entry in the PLAIN WORDS table**, so they read the same in both modes (a stated gap, like the HELP step names).

### Training Ground and Deck Trainer wording — rules that must stay true
Covers `training/TrainingGroundPanel.kt` and `training/DeckTrainerPanel.kt`. The two controllers (`TrainingGame.kt`, `DeckTrainerGame.kt`) are rules and read no words, labels or resources. Decisions are plain Kotlin in `core/TrainingText.kt` (`TrainingOutcome`, `TrainingStatement`, `TrainingPoses`, `TrainingText`) with `TrainingTextTest` (every language); `TrainingWordingTest` reads the panels and both controllers. The panels use the SDK, so they are syntax-checked only.

- **The watch's words are the watch's.** The state (OFFLINE, IDLE, ARMED, LOCKED, COOLDOWN, CRYO) and the pose codes (ID, DEF, CON, ---) are what the watch sends and what the drills react to (`stateLabel == "COOLDOWN"` is the fire edge). The panels show the state exactly as received, as the header and the watch's own screen do, and translate only the labels beside it (STATE, MOD). The POSE label and every pose a drill names come from the label table (`rememberTrainingPoseWords()` -> `poseLabel`), keyed by the **stored** pose name, so PLAIN WORDS applies; `DeckTrainerTarget.poseLabel` is that stored name (the statement lookup uses it), never a drawn word.
- **Never read logic back from drawn text.** The round outcome ("+10", "-5", "MISS") used to be compared as a string to choose its colour; it is now `TrainingOutcome` (kind + points) and the words are made from it. The Deck Trainer's "(no group bound...)", "(blank slot)" and "(unmapped)" are a `TrainingStatement` turned into words when drawn, so a person's own phrase that happens to read "(blank slot)" is still a phrase. Same lesson as "a result is carried by id, never by a label". Scoring is unchanged and pinned by source-reading tests.
- **A saved enum name is shown through a mapping and never rewritten.** History stores `difficulty.name` (EASY, NORMAL, HARD, EUROPEAN_EXTREME); `TrainingText.difficultyName` maps it to the language's word, and a name this build does not know reads as it always did (underscores as spaces). `GameDifficulty.label` stays the English name and the screens do not draw it. **EUROPEAN EXTREME is a name** (the developer's own, like CYBER and MECH; the developer confirmed it stays as it is) and reads the same in every language. A saved deck name and a profile id are shown as saved.
- **A number that can be negative gets a left-to-right mark in Arabic.** A score can go below zero, and in a right-to-left paragraph a minus sign in front of a bare number is drawn after it ("5-"). Every Arabic string that holds a signed number (`train_number`, `train_outcome_*`, `train_points`, the HARD and EUROPEAN EXTREME descriptions) has U+200E directly before the number, and no other language has one; `TrainingTextTest` pins both. Any new string with a signed number must do the same.
- **A long saved name or a longer word must not push a value off its row.** The history rows, the DECK / PROFILE / DURATION header rows give their text `Modifier.weight(1f)` so the points and [EXPAND] stay on screen; a test fails if one loses it.
- **`PlainWordsScreensWiringTest` names the controllers by prefix** (`training/TrainingGame`, `training/DeckTrainerGame`) instead of the whole `training/` folder, because the two panels in that folder are screens that read labels. A controller that starts reading a label still fails it.
- **`TranslationsTest`'s "same as English" allowlist is by name, not by language**, so `TrainingTextTest.aNameAllowedToMatchEnglish...` holds each such name to the languages that really write it that way. Extend that map when a name is added to the allowlist.

### Deck menu wording (MainActivity) — rules that must stay true
Covers the deck menu in MainActivity's header (the SYSTEM DEFAULT row, a deck's row, MANAGE mode, the edit panel, the two deck-deletion dialogs) and the Manual Override overlay's `[CLOSE]`. Decisions are plain Kotlin in `core/DeckMenuText.kt` with `DeckMenuTextTest` (every language); `DeckMenuWordingTest` reads `MainActivity.kt`, which uses the SDK and is syntax-checked only.

- **Deleting a deck takes two steps and only the second can delete.** The first dialog only marks the deck (CONTINUE opens the second; CANCEL closes); the one `CommandRepository.deleteDeck(` call is in the final dialog's `[DELETE PERMANENTLY]`, and the editor's DELETE button only opens the first dialog. `DeckMenuWordingTest` pins all of this. The final dialog names what is lost, says it cannot be undone and **what to back up first** (the developer asked for this; the other delete confirmations already did), and the GIF-files sentence and the back-up advice are part of the decision (`DeckMenuText.finalConfirmation(..., isGifDeck, words)`): the GIF sentence only for a GIF deck, the advice for every deck. **Every kind of deck's configuration is in EXPORT .JSON, but a GIF deck's files are not**, so a GIF deck is pointed at the GIF screen's own BACKUP menu and EXPORT DECK (.ZIP), worded exactly as that screen words them (`gif_backup`, `gif_export_deck`); the advice is 12 sp white (new text keeps the floor) and sits in the same dialog as `[DELETE PERMANENTLY]`.
- **A deck is chosen by its id and shown by its saved name; only its type's word follows the language.** `ui/deckTypeLabel(DeckType)` maps each type to its label (`DECK_TYPE_*`) in a `when` with no `else`, so a new deck type fails the build until it has a label (a test fails if an `else` is added). The deck name is an argument of the sentence, never part of the format (`%s`, `$1`, quotes and line breaks are tested).
- **Words that name two things can be written in either order.** `deckmenu_locked_title` / `deckmenu_locked_body` take the Matrix word (`%1$s`) and the DECK word (`%2$s`); English reads "MATRIX DECK", Spanish, Portuguese and Arabic write `%2$s %1$s`. The tests count each word once and never check the order; positional arguments exist for this.
- **The profile names (DEFAULT, WORK, HIGH_STRESS, SOCIAL, BUILDER), the deck called DEFAULT and the boot line MainActivity writes to the Terminal log are names or log text and stay English** (the widget and the watch show the same ids). A later change that translates profile names for display must do it the way the Emergency button names and the deck types are done (saved ids never change) and must move the widget, the watch, the Terminal, the Deck Trainer and the profile-change dialog with it.
- **A button that already has a label uses the label.** The create button is `"+ " + labelFor(LabelKey.DECK_CREATE)`, so with PLAIN WORDS on it reads + ADD A PAGE like the dialog it opens; in English standard mode it reads exactly what it always did.

### RECORD TRAINING DATA wording — rules that must stay true
Covers the library, the script editor, a session's details and the recording screen (`voicecapture/TrainingCaptureHome.kt`, `ScriptEditor.kt`, `SessionDetailDialog.kt`, `CaptureSessionScreen.kt`). Decisions are plain Kotlin in `core/CaptureText.kt` with `CaptureTextTest` (every language); `CaptureWordingTest` reads the four screens, the engines, the runners and the microphone; `FreeSpeechNoticeTest` pins the free-speech notices. All four screens are **type-checked** (`tools/kotlin_check/run_typecheck.sh`, with `R` generated from `strings.xml`), so a wrong string name or argument fails there; prove it by breaking one on purpose.

- **The engines and the microphone say no words.** They report a `CaptureNotice` (`capture/CaptureNotice.kt`: a kind, its numbers, and sometimes a technical detail) through `CaptureListener.onPaused(reason, notice?)`, `FreeCaptureListener.onStoppedByItself(reason, notice)`, `TrainingMicrophone.open()` and `.failure`; `CaptureText.notice` words it where it is drawn. A pause the person asked for has a null notice. The limits in a notice are the engine's own constants (`NO_SPEECH_TIMEOUT_HOPS / 100`, `MAX_FREE_SESSION_S / 60`), so a sentence cannot name a limit the engine does not keep. `DiskGuard.describe` and `NoiseCheck.describe` no longer exist (`DiskGuard.room` returns numbers; `CaptureText.noiseVerdict` words the verdict). `CaptureWordingTest.theEnginesTheRunnersAndTheMicrophoneSayNoWords` fails if a sentence is typed back into them. A technical detail (an exception's message, what the storage or package layer says) is shown as it came, inside a sentence that says what it means; only the screens' own fallbacks are translated.
- **Stored words are logic.** A session's mode (`script`/`free`), a script's line setting (`join`/`keep`), a mark's id (`noise`, `unclear`, `laugh`, `cough`, `stumble`, `long`, `short`, `no_end`) and a clip's state are saved and read by the computer; only the word *drawn* follows the language (`markWord`, `clipState`...), a mark or state with no word reads as before (the id in capitals, `UNFINISHED`), and a toggle passes the **id** (`toggleMark(flag)`, never the drawn word). A script's title, a session's name and the person's typed text are shown exactly as typed and are never used as a format.
- **`ClipState` is an object of `String` constants, not a type**: a function that takes a clip's state takes `state: String`. (`state: ClipState` compiles until the first call that passes `clip.state`; the JVM tests found it.)
- **Counts are colon-style in translations** ("SESIONES: 3"), so no language has to agree a word with a number. The six counted sentences (`capture_on_phone`, `capture_script_cards`, `capture_setup_cards`, `capture_setup_cards_skipping`, `capture_cards_typical`, `capture_cards_own`) are `<plurals>` so English says "1 SESSION" and "1 CARD" (read through `text.count(name, quantity, args)`; `%1$d` is the quantity and the other arguments follow); every form of a translation is the same sentence, **except Arabic's `one` and `two`, which are the words ("بطاقة واحدة", "بطاقتان") because `TranslationsTest` forbids a number there**. `CaptureTextTest.theSixCountedSentences...` pins that every form keeps the other arguments. Still imperfect in English, left as it is: "ABOUT 1 MINUTES" in the cards summary (a second number that would need a second plural), and the hedged "(S)" forms ("SESSION(S)", "CLIP(S)") which were always written that way.
- **A number that can be negative has a left-to-right mark in Arabic, and only there** (the room level and the microphone's error code: `capture_room_db`, `capture_noise_good`, `capture_noise_loud`, `capture_n_mic_stopped`); `CaptureTextTest.aNumberThatCanBeNegativeHasALeftToRightMarkInArabicAndNowhereElse` pins exactly those four.
- **A resource's leading and trailing space is trimmed by Android**, so the two spaces before "(TRY 2)" are joined in code (`CaptureText.cardHeading`); a test fails if any `capture_*` string starts or ends with a space.
- **Marks are short words, and a recording button wraps rather than cuts.** The five marks sit across a narrow screen at 9 sp; `CaptureButton` allows two lines (`maxLines = 2`, minimum height unchanged), so a longer translated word wraps instead of being clipped, and no fixed width is used. **Not seen on a phone**: check POCO CLARO / POUCO CLARO / ONDUIDELIK on a 360 dp-wide screen (device checklist section K).
- **The recording screen stays quiet.** No `NeonButton`, toast, haptic, sound or animation (`CaptureWordingTest`, `FreeSpeechNoticeTest`); its buttons are the haptic-free `CaptureButton`. **Known open item**: `ConfirmDialog` (used for END THIS SESSION while the microphone is open) is built from `TightPanelButton`, which vibrates, so tapping KEEP RECORDING can buzz into the card; decide before changing it.
- **The free-speech notices are string resources** (`capture_free_notice_setup` with the engine's minutes, `capture_free_notice_home`); only `FreeSpeechNotice.HELP` (the English of the free-speech step's last sentence, now only a pin held by `FreeSpeechNoticeTest`) is still a constant. They stay text only, 12 sp, no alarm colour, and the setup one sits directly inside `if (free)` before the quiet-check button.
- **The notes that point at these buttons use the translated names**: DELETE DATA's TRAINING DATA note takes SAVE ALL TO A FILE and RECORD TRAINING DATA as arguments (`StorageCatalogue.SAVE_ALL_LABEL`, `RECORD_TRAINING_LABEL`), and `/info`'s notes name RECORD FREE SPEECH, SAVE ALL TO A FILE, REDO LAST, PAUSE and the marks as the buttons read in the language (`PatchNotesTest`); only EXPORT DECK (.ZIP) is still a literal English button in a note.
- **English changes made by these groups**: a session whose size could not be read said "THIS REMOVES ITS OF RECORDINGS" and now says "THIS REMOVES ITS RECORDINGS"; "1 SESSION"/"1 CARD" (see the counts bullet); and the "MB FREE, ROOM FOR ABOUT N MINUTES OF RECORDING" line inside the out-of-room notices is in capitals like the sentences around it (it was the one mixed-case line, so the capitals rule of `TranslationsTest` now applies to its Spanish, Portuguese and Afrikaans too).

### GEO-PROTOCOL wording — rules that must stay true
Covers the GEO-PROTOCOL screen (SYSTEM and engine controls, MAP DATA with its two confirmations, each zone's card, the map overlay), its authorization dialog and the notification a zone sends (`geo/GeoProtocolView.kt`, `geo/PermissionModal.kt`, `geo/GeoBroadcastReceiver.kt`). Decisions are plain Kotlin in `core/GeoText.kt` with `GeoTextTest` (every language); `GeoWordingTest` reads the three files. All three use the SDK, so they are syntax-checked only (`tools/kotlin_check/run_syntax_check.sh`, listed in `tools/kotlin_check/README.md`).

- **A zone saves a deck id, never a word.** `enter/exitDeckId` is `DEFAULT`, `NONE`, `PREVIOUS` or a deck's own id (`GeoText.DEFAULT/NONE/PREVIOUS`, pinned against the repository). `GeoText.enterOptions/exitOptions` pair each id with the word *drawn*; `optionLabel(options, id)` finds the word (first match wins, as it always did) and shows an id it does not know as itself (a deleted deck). Picking an option saves the id (`onUpdate(zone.copy(enterDeckId = id))`, pinned by `GeoWordingTest.aZoneStillSavesDeckIdsAndTheEnginesStillSaveTheirNames`, which also pins the repository's defaults and the ids the receiver compares). A deck's own name and a zone's own name are shown as saved; a typed zone name is saved in capitals as it always was, and a new zone is still saved `NODE n` in English (a stored default, shown as saved).
- **SOVEREIGN and OPTIMIZED are names.** The developer decided they stay in every language (like CYBER and MECH). The engine chips draw `mode.name`, and the privacy notice takes both as `%1$s` / `%2$s` (`GeoText.privacyNotice`), so the chips and the sentence agree; `GeoTextTest.theTwoEngineNamesAreNamesHandedInAsArguments_inEveryLanguage` fails if a translation types one back.
- **Coordinates and sizes keep Latin digits** (`Locale.ROOT`, four decimals for a coordinate, one for the map's megabytes), whatever the phone's number format. The Arabic coordinate line has a left-to-right mark before each coordinate (a longitude is usually negative) and no other language has one; `GeoTextTest` pins both.
- **The notification is built outside any screen.** `GeoBroadcastReceiver.showNotification` wraps its context with `InterfaceLocale.wrap(context)` before it reads words (the same wrap `MainActivity.attachBaseContext` uses), so an install that stayed English sends English and one that chose a language sends that language. The deck it names is `GeoText.notificationDeckName` (system default, previous deck, the deck's saved name, or UNKNOWN when it no longer exists). The engine's own Terminal log lines ("Entering NODE 1. Awaiting User Ack.", the SOVEREIGN/OPTIMIZED engine lines) are written in English and stay English, like every line other parts of ACK send in through `ACK_LOG`.
- **The two map questions still ask first, and only the answer acts.** `GeoText.importAction(hasMap)` chooses REPLACE or IMPORT; REMOVE is its own question. `GeoRepository.importUserMapFile` / `clearUserMapFile` are called only from the dialogs' `onConfirm`. A reason an import failed is shown exactly as the file layer worded it, inside "IMPORT FAILED: ..."; only the screen's own fallback ("Unknown error") is translated.
- **Names that follow PLAIN WORDS are arguments.** The screen title in the authorization dialog (`geo_auth_title`), the grid screen in the "NONE -- ... RENDERS COORDINATES ONLY" line (`geo_map_none`) and the deck word in ENTER DECK / EXIT DECK are passed in from `labelFor`, so they read the same as the screens they name in both modes.
- **STEP 2 quotes Android's own option.** "Allow all the time" is the system's wording, not ACK's. Each translation quotes the phone's language as best a draft can; **these are the words to check first on a real phone** (the option's name differs between Android versions and manufacturers). Not run on a phone: the permission screens, the notification channel's name in system settings, the Arabic mirrored layout of a zone card.

### HELP walkthrough text — rules that must stay true
Covers every HELP module: the 16 `help/*Help.kt` family files and the inline MANUAL OVERRIDE module in `help/HelpRegistry.kt` (27 modules, about 390 strings per language). Decisions are plain Kotlin in `core/HelpWalkthroughText.kt` with `HelpWalkthroughTextTest`; `HelpWalkthroughWordingTest` reads every family file and every language; the English of every string is pinned in `app/src/test/resources/help_walkthrough_english.tsv`.

- **A step holds a resource name, not words.** `HelpStep.title`/`body` and `HelpModule.title`/`summary` are `helpmod_<module id>_title` / `_summary` and `helpmod_<module id>_<step id>_title` / `_body`, written out as literals (greppable; the wording test holds the rule and fails on a name that is missing, unused or defined twice). They are read through `helpWords()` (`ui/PlainWords.kt`: `rememberText()`, then `helpText()` for the placeholders) in the coach panel and the menu card, and through `HelpWalkthroughText.read` where the step is spoken. A text that is not a resource reads as itself, which is how the families moved one commit at a time; the wording test's `moved` / `notYetMoved` lists must name every family file (a new one fails the test until it is on a list). Never draw `step.title` with `helpText()` alone: it would draw the name.
- **English is word for word what it always said.** The extractor read each family's English out of the old source (never retyped), and the pin file holds it: a deliberate copy edit changes the string and its pin line together. English keeps `{{KEY:Original}}` and a mixed-case original may differ from the standard label's case; a translation uses the bare `{{KEY}}`, never an English original, and names the same *set* of labels as English (a sentence may be restructured to name one a different number of times, e.g. to avoid a word that would need a gender).
- **A step that points at something uses that screen's own word.** The walkthrough's word for a button or a heading is taken from the screen's own string in that language, and the wording test keeps two tables: `isExactly` (a title that is exactly a label or heading) and `namesLabelLiterally` (a sentence that holds the word of each control it names). The second is checked for translations only, because English may name a button loosely ("Export", "Full Restore"). **Add a row whenever a step names a control**, so a later change to a screen's word fails until the walkthrough follows. English that differs slightly from the screen ("LIVE SAVE EDITOR" against "LIVE-SAVE EDITOR") stays as it was and is listed as such.
- **Things that are not words stay exactly as they are, in every language**: typed commands (`/m`), the tokens the phrase editor inserts (`{VAR}`, `[COMPUTER:PEOPLE]`, `[COMPUTER:]`), the watch's own state words (OFFLINE, ARMED, LOCKED, FIRE: shown as the watch sends them, with a translated gloss beside), the deck called DEFAULT, Freeform Studio, and a literal lowercase brace token such as `{{tags}}` (not a label placeholder, so it must not be upper-cased into one). **Upper-casing a draft (es, pt, af are capitals) must not reach these**: it turned `/m` into `/M` and `{{tags}}` into a placeholder before the tests that now hold them existed.
- **A raw newline in a string resource is collapsed to a space by Android; write the `\n` escape.** The test XML parser keeps the raw newline and would not notice, so a test reads the raw files, and a paragraph break in English must be a paragraph break in every language.
- **The spoken guide**: the coach panel speaks each step (`MainActivity`, `source = "HELP/<module id>"`). `HelpWalkthroughText.speaksInterfaceLanguage` says the **translated** step is spoken only when SPEECH LANGUAGE follows the phone **and** the screens are in the phone's own language (`Locale.getDefault().language`, never the wrapped context's configuration, which is the chosen interface locale); every other case speaks the English step, read from `EnglishResources.context(context)`, with the labels filled in from that same context. An install that already existed (English (US) voice) hears exactly what it always heard. Not run on a phone: whether a phone with no voice for its own language keeps its default voice.
- **Privacy and safety sentences are kept in every language** and a native speaker should read them first: RECORD TRAINING DATA (nothing is sent anywhere; no sound or vibration while it listens; free speech also records anyone nearby; the phone never deletes a session because it was saved), the word-suggestions step (off until turned on; nothing added without a tap; the path to the switch and the forget button are named), and the DATA PORT step (a restore never deletes what it does not mention). The free-speech step ends, in every language, with the very sentence the home screen shows; English ends with `FreeSpeechNotice.HELP`.
- **No article before a placeholder in es and pt** (the everyday word under PLAIN WORDS may be the other gender); rephrase with a word that does not change (`EN USO`, `ACTUAL`, `CUALQUIER`). Afrikaans has no grammatical gender and is exempt.
- **Still English: the two choosers' option labels and hints.** They are a separate group (`PoseSelectorDialog`, `VoiceRecordingsHelpSelectorDialog`).
- **Drift**: the translations were generated with throwaway scripts that pulled each screen word out of that screen's own strings, so the strings are plain resources with nothing generating them; if a screen's word changes the wording test names the walkthrough string to update by hand.

## CLINICAL USE (Section 5 of the AAC Readiness Tracker) — rules that must stay true

The plan, the decisions and the open questions are in `docs/CLINICAL_USE_PLAN.md`; the phone checklist is `docs/CLINICAL_USE_DEVICE_TEST.md`. Written as the rows
(C1 to C6) are built; only what exists is described here. **The developer decided (DEC2) that ACK's scope is "a personal tool, shared as-is"**, while still building
the opt-in, local-only clinical-review features (C1, C2): nothing in the app or the docs may call ACK a clinical tool, a pilot programme or a medical product, and
nothing may claim an effect (the evaluation found no evidence yet that it helps).

### The limits statement (C4) — `core/LimitsNotice.kt`
- **Three sentences, three resources** (`about_limits_*`), joined with a space in code (Android trims a trailing space). All three are the website's disclaimer
  (`index.html`, the `<p class="disclaimer">`) **word for word**; `LimitsNoticeWebsiteTest` compares them ignoring case (the app is in capitals, the page is not), so
  editing one side alone fails. The developer confirmed the wording and chose to add the third sentence (keep another way to communicate available at all times) to the page.
- **Two places:** a permanent ABOUT ACK section at the end of SETTINGS (`settings/AboutSection.kt`, words only: no switch, button or link), and a one-time banner
  (`ui/LimitsNoticeBanner.kt`) drawn above the header **on the Terminal and Settings screens only** (`LimitsNotice.BANNER_SCREENS`; the Terminal is the screen ACK
  opens on). **Never on a deck, Emergency or Type screen**, where it could move a button about to be tapped. Do not add it elsewhere without asking.
- **It is only a notice.** GOT IT writes one note (`limits_notice_seen`, `AssistPrefs.markLimitsNoticeSeen`, `commit()`) and nothing else: it starts no HELP, navigates
  nowhere, shows no toast and never touches speech. The note is in `ack_assist_prefs`, so it is **never seeded** (every install sees the banner once), **never in
  `AckBackup`**, and cleared by DELETE DATA > SETTINGS (the banner then shows once more, which is wanted). `LimitsNoticeWiringTest` holds all of this.
- **12 sp floor.** `HelpOfferBanner` is 9 sp and was deliberately **not** reused. The banner and the section use `ConfirmBodyText` (12 sp).
- The banner's last line takes the SETTINGS button's name (`labelFor(LabelKey.SETTINGS_ENTRY)`, so it follows PLAIN WORDS) and the section's title as arguments; the
  banner file itself reads no labels.
- The five translations are drafts like the rest; a native speaker should read these sentences first (`docs/TRANSLATIONS.md`). The `/info` note (`info_nr_about_head`,
  `info_nr_about_1`, listed in `PatchNotes.ENTRIES`) is translated too: although the HELP-chrome notes above say a release's new notes may ship in English first, `PatchNotesTest`
  in fact reads every listed note in every language (`getValue`), so an untranslated one fails four tests. It also holds that the note names ABOUT ACK, GOT IT, SETTINGS and the
  Terminal as those screens read in each language. A new note also goes into that test's pinned English list (`oldPatchNotes`).
- Not seen on a phone: how the banner sits at the largest font on a small screen (it can take a lot of room above the Terminal), and the Arabic mirrored layout.

### Saving the Terminal log's messages to a file (C2) — `core/LogExport.kt`, `core/LogExportContents.kt`, `data/LogExporter.kt`, `settings/LogExportDialog.kt`
The developer's decisions: **messages only**, and **a button in SETTINGS only (no typed command, no Terminal button)**.
- **Messages only** (`LogExport.isMessage`): a line is a message when its type is exactly `OUT` or `EMERGENCY` **and** it carries `replayText` (only a real communicated phrase does:
  OutputService leaves it null for tutorial narration). System, path-trace, command and tutorial lines are never written. The message's words come from `replayText`; the log line's own text is
  used only to label where it came from (`LogExport.fromOf`: the tag before ` > "`, or `TERMINAL` plus any `[Q][S][E]` modifiers for a line typed at the prompt). A message's own words are in the file, so the warning says
  names, addresses and numbers are too. Only messages the retention window still keeps are written (`keptSince`; one exactly on the edge is kept), even if the live buffer has not been pruned yet.
- **The log is newest-first** (`logBuffer.add(0, ...)`), so `messages()` reverses it and sorts by time, which keeps equal times in the order they were written.
- **The file is one record per line, by construction.** `escape` writes every line break (CRLF counts once, plus CR, NEL, LS, PS) as `\n`, a tab as `\t`, a backslash as `\\` and any other control character as
  `\uXXXX`; columns are separated by tabs; header lines start with `# ` (a header translation with a line break is flattened). A seeded fuzz test checks no raw break survives and the text reads back.
- **Time is local, with the offset on every line, in Latin digits** (`yyyy-MM-dd HH:mm:ss xxx`, `Locale.ROOT`, `DecimalStyle.STANDARD`): a time-zone or daylight-saving change cannot make two lines ambiguous. The count and
  range are handed to the header text as strings, never as numbers, so an Arabic or Hindi phone cannot print other digits.
- **Warn first, write nothing until a place is chosen.** `LogExportContents` is the one source of the warning (the count, what the file holds, what it does not, not protected, a screenshot is a copy, where to save);
  its two safety sentences are the EXPORT .JSON warning's own constants so the two cannot disagree. The Terminal log's name is an argument (follows PLAIN WORDS). `CreateDocument("text/plain")` only: **no share sheet, no
  `ACTION_SEND`, no network**; cancelling the warning or the picker does nothing; an empty log shows a line and no CHOOSE button.
- **A failed save says nothing was saved and deletes the half-made file** (best effort), through one `failed(...)` path that every `catch` uses; a null output stream is a failure, not a silent success.
- **Nothing said is ever logged**: the exporter's `Log` calls hold a fixed sentence, a reason, a count or a size. **Reading the log changes nothing** (no prune, no persist). **No new storage**: no preference file, folder or key,
  so nothing to register in DELETE DATA or a backup; a file the person saved is theirs and DELETE DATA does not remove it. `LogExportWiringTest` holds all of this.
- **One button, in one place**: under the retention slider in SETTINGS' Terminal section, 12 sp. `rememberLogExportFlow` is used only by `SettingsView`; a test fails if MainActivity, the Terminal or `TerminalText` start it.
- The file's header is in the chosen language; the columns hold stored values (OUT, EMERGENCY, source tags) that are never translated. The five translations are drafts; the warning is safety text, so a native speaker should read it first.
- Not seen on a phone: the picker against different storage providers, the layout at the largest font, a log at its 400-entry cap, the file opened on a PC.

### The usage summary (C1) — `core/UsageTally.kt`, `core/UsageKinds.kt`, `core/UsageSummaryText.kt`, `core/UsageSummaryFile.kt`, `data/UsageTallyRepository.kt`, `settings/UsageSummarySection.kt`
The design is `docs/USAGE_SUMMARY_DESIGN.md` (the developer approved it as written). Their decisions: a kind comes from **where the message came from plus ACK's own starter kinds** (OTHER for anything else);
the switch is **in SETTINGS, with one quiet line on the Terminal while it is on**; kept **90 days, by day and hour of day**; a replay is counted (as REPLAY); **turning it on always asks first**.
- **Counts only, and no text field may ever be added.** A `UsageCell` is a date, an hour (0 to 23, the finest it gets), a channel and a kind, each from a fixed enum, plus a whole-number count. `UsageTallyTest.noTypeThatHoldsCountsHasAField...`
  fails if a type that holds counts gains a field that could hold a word. No message text, deck or button name, person, place, recording id, audio or minute is ever kept, **not in a log line or an error either**
  (`UsageSummaryWiringTest.noWordOfAMessageIsEverKeptOrLogged`). Every `Log.` line in the repository and the exporter is a fixed sentence, a count or a size.
- **The channel is read from the tag the message already carries** (`OutputService`'s `source`) by a closed table (`UsageKinds.channelOf`): every `MTX/...` is just MATRIX (a deck's or button's own name is never kept), `BANK/<tag>` (a saved
  Manual Override phrase; the tag is the person's own) is MANUAL_OVERRIDE, anything unknown is OTHER so a new entry point is counted rather than lost. **`UsageSummaryWiringTest` reads the app's source and fails on a tag
  the app sends that is not in `UsageKinds.KNOWN_SOURCES`**: that is how `BANK/` was found. A new place that calls `OutputService` with its own `source` goes into the table and the test.
- **The kind is by wording, in memory, then thrown away; the one exception is a partner card play.** `UsageKinds.kindOf(source, text)` returns PARTNER_CARD for the `PARTNER/CARD` tag **whatever the words say** (the developer's decision; it also keeps the person's
  own card sentences out of the starter match), and otherwise `UsageKinds.kindOf(text)` compares the words (trimmed, lower-cased with `Locale.ROOT`, so a Turkish phone is unaffected) with every starter phrase in `StarterSets` and gives that
  phrase's kind, else OTHER. It is **computed before the hand-off to the worker**, so the worker only ever receives a cell. Nothing is guessed about the person's own words; an edited starter counts as OTHER (the safe direction).
- **The switch is `ack_assist_prefs` > `usage_summary`**: off when nothing is stored, **on every install, never seeded** (not in `SEED_KEYS`, not in `seedFreshInstallDefaults`), never in `AckBackup` (a restore must not start counting), written with
  `commit()`. DELETE DATA > SETTINGS turns it off again. `UsageSummaryState` (Compose state, shaped like `PlainWordsState`) makes the Terminal line and the section redraw at once.
- **Counting can never change or delay speech.** One call in `OutputService`'s message branch, **after** the message has been handed on: `if (!isRobotic && !skipLog && (phrase or recordingId present))`. `skip_log` is typed `/n` (counting it would undo
  "do not save") and `robotic` is the HELP narration; neither is counted. A normal, Emergency, typed, `/q`, Silent Mode and replayed message all are (they were sent). `UsageTallyRepository.recordMessage` checks the switch first, computes the cell,
  and hands the write to **one background daemon thread**; both the call and the worker `catch (Throwable)` and log a fixed sentence. **Do not move the call before the dispatch, make it synchronous, or let it throw.**
- **Storage is its own preference file, `ack_usage_tally`**: one `Int` per cell under the key `yyyy-MM-dd|HH|CHANNEL|KIND` (Latin digits, `UsageCell.parse` is strict and never throws: a damaged key is simply not a count). The increment saturates at
  `Int.MAX_VALUE` and a negative stored value restarts at one. Once a day (and once per process) `UsageTally.keysToRemove` drops unreadable keys and anything older than the window (**today and the 89 days before it; one day older goes**), then, if
  more than `MAX_ROWS` (20,000) remain, whole oldest days (a day is never cut in half). No in-memory copy of the counts. It is **its own DELETE DATA area** (`StorageCatalogue.ID_USAGE_SUMMARY`, not backed up, no restart; the catalogue scan test forced
  this), is in `InstallState.OWNED_PREFS_FILES`, and is **not in EXPORT .JSON** (so `ExportContents` is unchanged). The literal `"ack_usage_tally"` in the repository is kept equal to `UsageTally.PREFS_FILE` by a test (the storage scan reads literals).
- **The screens** (`settings/UsageSummarySection.kt`, under the message-log button in SETTINGS): the switch (a `NeonButton` saying ON or OFF in words), the plain numbers (by kind, by place, the last 14 days, the hours with a count), SAVE, FORGET. **Turning on
  always asks, with CANCEL prominent** (`TURN ON` is the plainer button); turning off asks nothing and deletes nothing. **FORGET asks twice and names SAVE USAGE SUMMARY TO A FILE first; `UsageTallyRepository.forgetAll` is called from exactly one place, the second
  DELETE PERMANENTLY** (`forgetAllIsCalledFromExactlyOnePlace...`). The Terminal's line (`UsageSummaryTerminalLine`, a `Column` above `TerminalView` in MainActivity, 12 sp, grey, no sound, no animation, nothing to tap) shows **on the Terminal only**, never on a deck,
  Emergency or Type screen, where it could move a button about to be tapped. 12 sp text and `NeonButton` (not `TightPanelButton`); no charts.
- **Saving mirrors C2**: a warning first (the count the file would hold, what it holds, what it does not, **that it still shows when someone communicates so keep it like a diary**, not protected, a screenshot is a copy, where to save), `CreateDocument("text/plain")`
  only (no share sheet, no network), cancelling opens no picker, an empty summary shows a line and no CHOOSE button, a failed save deletes the half-made file and says nothing was saved (`UsageSummaryExporter.write/report`). The two shared safety sentences are the
  EXPORT .JSON warning's own constants. The file (`ack_usage_YYYY-MM-DD_HHMMSS.txt`): `# ` header lines in the chosen language, then tab-separated `DATE HOUR CHANNEL KIND COUNT`, oldest first; the channel and kind are the **fixed English names** (never
  translated), and every digit is Latin.
- **Honest limits, kept in the words**: a count says a message was sent, not that it was heard or helped (it is **not** evidence that ACK works, so nothing may present it as one); the hour buckets shift with a time zone or a wrong clock; it describes the phone, not
  the person; ACK has no app lock, so the Terminal line is for *seeing* that it is on, not protection.
- **Tests**: `UsageTallyTest`, `UsageKindsTest`, `UsageSummaryTextTest`, `UsageSummaryFileTest`, `UsageSummaryWiringTest`, plus the `/info` note's test in `PatchNotesTest` (it names the section and both buttons as each language reads them and the real number of days). Thirteen
  deliberate breaks of the wiring and rules (a counted `/n`, counted narration, a switch ignored, a stored string, seeded on, a 91-day window, a text field, an unmapped tag, a case-sensitive match, a forget at the first question, no turn-on question, a missing
  DELETE DATA area, swapped row arguments) were each caught. **A per-language loop in a test stops at the first failing language**, so break each language on its own to prove the later ones are checked (done for the note).
- **Type-check and syntax check**: `UsageSummarySection`, `UsageSummarySave`, `UsageSummaryState` and `LogExportDialog` are staged in `tools/kotlin_check/android-typecheck/check.sh` (stub `stubs/app/UsageSummary.kt`; the `AssistPrefs` stub gained the switch);
  `MainActivity.kt`, `OutputService.kt`, `SettingsView.kt`, `UsageTallyRepository.kt`, `UsageSummaryExporter.kt` and `AssistPrefs.kt` use the SDK and are syntax-checked only.
- Not seen on a phone: the section and dialogs at the largest font, the Terminal line on a small screen, the Arabic mirrored layout, that speech starts as fast with counting on, the file picker. Part C of `docs/CLINICAL_USE_DEVICE_TEST.md` is the checklist.

### The partner card (C3) — `core/PartnerCard.kt`, `ui/PartnerCardButton.kt`, `output/PartnerCardPlayer.kt`, `docs/PARTNER_CARD.md`
The developer's decisions: a **playable message plus a printable page**; the button is a **header icon in the slot next to HELP, with the backup reminder's save icon moved to its left**; a tap **asks first**; the icon is **about 24 dp like its
neighbours**; it is **always shown (no setting hides it)**; it follows the person's audio routing and **is silent when silent output is on**; the wording is **option C** (five sentences). Later, at the developer's request: **each sentence can be switched on or off, there are two slots for the person's own sentences, and every play is logged with the kind `partner_card`**. Nothing here makes a clinical claim.
- **The five sentences are the developer's, and a draft for a speech-language pathologist.** `PartnerCardTest.theCardIsTheFiveSentencesTheDeveloperChose_inOrder` pins the English. Do not reword, add a sentence or fold in a clinical suggestion
  without asking. The translations are drafts for a native speaker; **Hindi and Arabic avoid verb forms that depend on the speaker's or listener's gender, and Spanish and Portuguese avoid gendered words for the listener**: keep that. They are
  written in **ordinary case, not capitals**, because a speech engine may spell out capital words (the rest of the screens are capitals; this text is spoken).
- **Normal output path, never Emergency.** `PartnerCardPlayer.play` sends an intent with `phrase`, `robotic = false`, `source = PartnerCard.SOURCE` (`PARTNER/CARD`) and `full_text = true`, and nothing else: no `emergency_mode` (the Emergency path
  always speaks on the phone and ignores silent output, which would break the developer's rule), no forced `quiet`, `skip_log` or `sticky` (those are the person's own picks). It is logged and replayable like any message. `PartnerCardWiringTest` fails on
  any "emergency" in the player.
- **A tap only asks.** The header icon's `onClick` only sets `showPartnerCardDialog`; **`PartnerCardPlayer.play` is called from exactly one place, the question's PLAY IT button**. CANCEL, the back gesture and a tap outside are the same: close, do nothing
  else. CANCEL is the prominent button (theme colour, first); PLAY IT is plainer. 12 sp text (`ConfirmBodyText`) and `NeonButton`; the icon has no animation and no haptics of its own.
- **The whole message is shown, only for the card.** The display rule (`core/DisplayText.kt`) cuts a message of more than five words to "ALERT:" and three words for an install whose preset still has SHOW FULL MESSAGE off, while it is spoken in full:
  the failure the SAFETY DEFAULTS section describes. The card asks for `full_text`; `OutputService` carries it through `QueuedSpeech`, **both** ways a request reaches `processSpeech` (straight away and after the queue) and `showVisualPrompt`, which copies
  the active preset with `bypassTruncation = true` **for that message only**. Only `PartnerCardPlayer` sends the extra (a test scans the app); every other message follows the person's preset exactly as before.
- **What is shown is what is spoken, in the language the voice speaks.** `PartnerCardPlayer.words` uses the translated card only under the HELP rule (`PartnerCard.speaksInterfaceLanguage` = `HelpWalkthroughText.speaksInterfaceLanguage`: SPEECH LANGUAGE follows
  the phone **and** the screens are in the phone's own language), otherwise the English card; the question shows the same lines. An install that already existed (English (US) voice) hears and sees English, as before. The silent-mode name inside the
  question is an argument (`labelFor(LabelKey.SILENT_MODE)`), so it follows PLAIN WORDS.
- **The header.** `Row { BackupSaveIndicator (24 dp slot, always laid out), 4 dp, PartnerCardIndicator (24 dp), 4 dp, HELP }`. The save icon needs its own reserved slot so that nothing moves when it appears, so **the header is about 28 dp wider on every screen**
  and the deck and profile text on the left has that much less room. A test pins the order and that the icon is not inside any condition. **Not seen on a small phone**: say so if a name is cut off or the header is crowded.
- **Counting and logging.** It is a normal message: it shows in the Terminal log and the saved log as `PARTNER/CARD`, and the usage summary counts it as its own place, `UsageChannel.PARTNER_CARD` (twelve places now; a new enum value is backward-compatible with
  stored counts), so a reader can ignore it. `usage_channel_partner_card` has the same words as `partner_card_name` (a test holds it).
- **The person chooses what the card says, in the question that asks first** (`PartnerCardDialog`). Seven sentences: slots 0 to 4 are the built-in five, slots 5 and 6 the person's own. Each is a whole-row switch (`toggleable`, `Role.Switch`, at least 48 dp, **ON or OFF
  written in words** from `common_on`/`common_off`, no haptics) and the question shows exactly what will be said. **The choice is remembered** (the developer was not asked and I chose it: a card you have to re-untick every time defeats the point; the question always
  shows it). With every sentence off, **PLAY IT is not offered** and a line says to turn one on (hide, never a disabled button); `PartnerCardPlayer.play` also sends nothing for an empty message. Nothing stored means the card as it always was: five on, no own sentence.
  **A play is one message, however many sentences were on**, and the usage summary counts one.
- **The person's own sentences** (`core/PartnerCardSettings.kt`, rules in `core/PartnerCard.kt`): two slots (the developer said "one or two"), up to **200 characters** (`MAX_OWN_LENGTH`; the backup's check uses the same constant, so it can never reject what the screen allows).
  They are **the person's words: said and shown exactly as written, never translated, never reworded.** Only tidied by `PartnerCard.cleanOwn` (line breaks and runs of white space become one space, **U+0085 included: it is a line break Java does not call white space and the
  first version dropped it, gluing two words together**; control characters go; trimmed; cut at the limit without splitting an emoji) and `PartnerCard.terminated` (a full stop is added when the sentence does not end in `. ! ? …` or the CJK, Devanagari or Arabic equivalents, a
  closing quote or bracket after one does not matter, so the voice pauses between sentences). **A written sentence starts on; a changed one turns on again; an emptied slot is never on and cannot be switched.** Writing needs a tap on SAVE (`PartnerCardEditDialog`, nothing is kept
  while typing, SAVE only offered when something is written, CANCEL prominent and first); **CLEAR THIS SENTENCE asks a second time and only that second question calls `onClear`.** Every change is written with `commit()` **before** it is shown (`PartnerCardState.change`);
  a failed save leaves the shown choice alone and says nothing was changed.
- **Storage is its own preference file, `ack_partner_card`** (`own_1`, `own_2`, `off` as comma-separated slot numbers), read strictly and never throwing. It is **in the DELETE DATA > MESSAGES AND DECKS area** (not a fourteenth: they are the person's messages), in
  `InstallState.OWNED_PREFS_FILES`, and **in EXPORT .JSON** as `AckBackup.partnerCard: PartnerCardBackup?` (null when no sentence is written), **named in the export warning as its own line** (`export_cat_partner_card`, like the learned words: words the person wrote must not hide under "settings").
  **A restore only ADDS: each backed-up sentence the phone does not already have goes into an empty slot, a written slot is never overwritten, a duplicate is not added twice, and the on/off choices are not in the backup** (I chose this over matching by id because the two slots have no ids and an
  overwrite could silently destroy a sentence written since). The backup check logs sizes only, never a sentence. **No sentence is ever logged**, not in an error either (a test pins every `Log` line to a fixed sentence). The fingerprint is **not** told to ignore it, so writing a sentence makes
  the backup reminder due, as it should; adding the field changes every phone's fingerprint once (like `speechLanguage` before it).
- **Logged as the `partner_card` kind** (`UsageKind.PARTNER_CARD`, twelve kinds now) by `UsageKinds.kindOf(source, text)`; the channel is still `PARTNER_CARD` too (twelve places), so a reader sees both and can ignore either. `usage_kind_partner_card` has the same words as
  `partner_card_name`. A play also appears in the Terminal log and the saved log as `PARTNER/CARD`.
- **The printable page** (`docs/PARTNER_CARD.md`) holds all six languages as `> ` lines; `PartnerCardPrintableTest` fails if any sentence differs from `strings.xml`, so a change to one side alone is caught (proved by editing the English, the Spanish and the page alone).
- **Tests**: `PartnerCardTest` (the words in every language), `PartnerCardSettingsTest` (the choice, the own sentences, the boundaries, restore, the backup's shape), `PartnerCardWiringTest` (the Android files, the repository, DELETE DATA and the backup), `PartnerCardPrintableTest`, the `/info` note's test in `PatchNotesTest`, and the usage source-tag scan (which now includes `PartnerCard.SOURCE`). Thirteen deliberate breaks of the first version
  (an emergency flag, a forced quiet, a tap that plays at once, an icon hidden behind a condition, a 48 dp icon, a request lost in the queue, CANCEL no longer prominent, a hide setting, an always-translated card, a changed English sentence, a changed Spanish sentence,
  a dropped usage mapping, a page edited alone) were each caught, and **fifteen more for the choice and own sentences** (a choice shown before it is kept, a sentence in a log line, a restore that overwrites, a kind decided by the words, PLAY IT always offered, a clear with no second question, SAVE offered with nothing written, no limit
  while typing, the file missing from DELETE DATA, an empty card still sending, the export line missing, a lost placeholder, an empty slot that can be toggled, no full stop added, a tap that plays at once) were each caught. `ui/PartnerCardButton.kt` and `ui/PartnerCardState.kt` are staged in the type-check
  (the repository is stubbed in `stubs/app/PartnerCard.kt`); `MainActivity.kt`, `OutputService.kt`, `PartnerCardPlayer.kt`, `PartnerCardRepository.kt` and the backup files are syntax-checked only.
- Not seen on a phone: the question with seven rows and its keyboard dialog on a small screen at the largest font, the switch rows as tap targets, the header on a small screen, the bubble as a tap target, how long the card stays up (it clears after about 10 s like any message; **whether that is long enough to read five sentences is an open question for the phone check**; `/s`-style hold
  is the person's own choice and the card does not force it), the Arabic mirrored header, and the card through Bluetooth or the watch. Part D of `docs/CLINICAL_USE_DEVICE_TEST.md` is the checklist.
