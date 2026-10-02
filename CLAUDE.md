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
