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

- **`HelpCategory`** — enum, each case carries `title`/`subtitle` in a
  fixed `"SECTION // SUBSECTION"` style. Drives the chip row in
  `HelpMenuDialog` (`HelpCategory.values().forEach { ... }` — adding a
  case is enough, no separate registration needed for the chip itself).
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
`Read`, e.g. `MatrixDeckHelpCopy`'s `identity_root` step just highlights
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

A `SavedStatement` (`data/StatementRepository.kt`) has a `template: String`
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

`SavedStatement.variableContext: String` is required and easy to forget
why: `{VAR:A}`/`{VAR:B}`/`{VAR:C}` tags are only unique **within one
Shared Root Variables grouping** (a fixed pose — IDENTITY/DEFEND/CONNECT —
or a custom context layer's name), exactly like a Matrix phrase's
`{VAR:A}` always resolves against its own node's category
(`CommandRepository.getResolvedPhrase` looks this up from
`cachedNodes.find{...}?.category`) and a Quick Actions slot resolves
against its own group's `rootCategory`. A statement isn't anchored to a
node or group, so it has to carry its chosen grouping explicitly instead
— resolving `{VAR:A}` against the wrong grouping's `RootOverrideConfig`
would silently produce the wrong value. **If a future field ever lets a
single statement reference more than one grouping, this single-string
field stops being enough — don't just widen its type without also
rethinking how the picker UI decides which grouping is "current."**

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

### File map

| File | Owns |
|---|---|
| `composer/StatementComposerView.kt` | The composer screen: field, variable-context row, live preview, insertion aids, SAVE/COPY/SPEAK, MY STATEMENTS list, the long-press retarget dialogs |
| `data/StatementRepository.kt` | `SavedStatement` model (`template` raw with tokens, `variableContext`), merge-by-id `StatementRepository` (mirrors `VisualPresetRepository`'s shape) |
| `help/StatementComposerHelp.kt` | The composer's own HELP module, `destination = HelpDestination.TYPE` |
| `computer/ManualOverrideTargetBrowser.kt` | `TargetQuickAccessRow`/`TargetBrowsePanel`/`ManualOverrideHeaderTakeover` — shared with legacy Manual Override, `onInsert`/`onLongPress` let each caller decide token vs. literal and whether retargeting is offered |
| `computer/ComputerTreeWindow.kt`, `computer/ContactCardView.kt` | Reused wholesale (not reimplemented) for the composer's long-press retarget dialog |
| `ui/DesignSystem.kt` | `TypeView` (legacy Manual Override, unchanged), `TerminalView`'s `/m` parsing (`parseTerminalCommand`, `TerminalPromptResult.ShowManualOverride`) |
| `MainActivity.kt` | `showLegacyManualOverride` state, the in-place (non-`Dialog`) overlay render, `showComputerHeaderTakeover` gating, the `"TYPE" -> StatementComposerView(...)` dispatch |
| `help/HelpRegistry.kt` | Both HELP modules registered under `HelpCategory.BASICS_MANUAL_OVERRIDE`; the legacy module's destination fixed to `TERMINAL` |
| `backup/AckBackup.kt`, `backup/TransferManager.kt` | `savedStatements: List<SavedStatement>` — nullable/empty-default field, validated (size cap, `SAFE_KEY_PATTERN` id, `MAX_PHRASE_LENGTH` template, `variableContext` checked against `POSE_CATEGORIES`/custom-context-name pattern), merged by id on restore |
