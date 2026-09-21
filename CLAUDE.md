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
