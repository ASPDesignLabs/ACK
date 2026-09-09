# ACK's In-App Help / Tutorial Modules

## How it works
The Help system (`HelpRegistry` -> `HelpManager` -> `HelpMenuDialog` / `HelpCoachDialog`) only advances a step when a real event fires from the actual UI: a tap on a specific tagged element, a committed text field, a cleared overlay, a watch gesture broadcast. That event-driven design is what makes it a genuine walkthrough instead of a slideshow.

A step's coach mark only pulses if the target composable carries both `.testTag(AckTags.X)` (semantic identity) and `.helpTarget(AckTags.X, someColor)` (the actual pulsing border/background, defined in `HelpTarget.kt` — a no-op unless `LocalHelpManager.current?.currentStep?.targetTag == tag`). The matching `HelpEvent` (usually dispatched via a local `reportHelpInteraction(tag)` / `reportTextCommit(tag)` helper) is what actually advances the step.

## Current state
Every module is registered in `HelpRegistry.kt` — `BasicsNavigationHelp`, `DeckManagementHelp`, the inline `manual_override` module, `GeoProtocolHelp`, `LogsHelp`, `QuickActionsDeckHelp`, `EmergencyDeckHelp`, `EmojiDeckHelp`, `GifDeckHelp`, `MatrixDeckHelp`, `PersonalizationHelp`, `SettingsManagementHelp`, `TargetComputerHelp`, and `FieldOpsHelp` — and their target tags are applied and wired in the real composables.

**Manual Override** is intentionally the short inline 2-step version defined directly in `HelpRegistry.kt` (intro + `AckTags.MANUAL_INPUT_BTN`), not a fuller multi-step walkthrough of memory banks / text field / send. An earlier draft (`ManualOverrideHelp.kt`) sketched that fuller version but was never registered — its tags were never applied to any composable — and has been removed as dead code.

The old pre-`HelpModule` tutorial system (`TutorialManager`, `TutorialScript`, the `TacticalOverlay` composable, and the `Modifier.tutorialTarget` extension in `DesignSystem.kt`) has also been removed. It was never instantiated anywhere; the current `HelpModule`/`HelpManager` system fully replaced it.

## What's genuinely still open
`PersonalizationHelp.kt` has three steps (`pitch_speed`, `robotic_overlay`, `bitcrush`) with their `action`/`targetTag` deliberately commented out — they describe DSP controls (`AckTags.AUDIO_PITCH_SPEED`, `AUDIO_ROBOTIC_OVERLAY`, `AUDIO_BITCRUSH`) that don't exist as distinct controls in `AudioView.kt` yet. Those steps currently render as read-only info with no coach-mark target. Wire them up (or drop them) once that UI exists.

## The checklist, for any new module or new step
1. **Find the real UI.** Open the actual Compose screen/dialog for the feature. Identify exactly which element the step should point at.
2. **Confirm the tag, don't assume it.** Check `AckTags.kt` for an existing constant. If a help-content file already references one, that's a claim, not a fact — verify it's actually applied somewhere.
3. **Apply the tag to the composable**: `.testTag(AckTags.X)` and `.helpTarget(AckTags.X, primaryColor)`, in that order so visual modifiers (background/border) still render on top. Copy the convention from a working example, e.g. `AckTags.DECK_SELECTOR` in `MainActivity.kt`.
4. **Match the `HelpAction` to how the interaction really happens.** `Interact` for a tap, `CommitText`/`CommitFile` for a save action, `OverlayCleared` for a dismiss, `WatchEvent` for a broadcast-driven gesture. Check where the matching `HelpEvent` is actually dispatched (`grep -rn "helpManager.onEvent\|HelpEvent\." app/src/main/java/com/example/besu`) so the step advances when expected.
5. **Verify before registering:**
   ```
   grep -rn "AckTags.<YOUR_TAG>" app/src/main/java/com/example/besu --include="*.kt"
   ```
   Confirm the tag shows up in a real view file, not only in the help-content file and `AckTags.kt`.
6. **Register in `HelpRegistry.kt`** if it's a new module, and check its `HelpCategory` lands it somewhere sensible — see `defaultHelpCategory()` in `HelpMenuDialog.kt` if it should be the default landing module for a given deck type.
7. **Smoke-test on device.** Open Help, launch the module, step through every action to the end. A tag that compiles but was never applied to a composable is the most common way this silently breaks.

## Workflow
Do larger changes on their own branch per module (see `docs/GIT_WORKFLOW.md`) so each deck's tagging + content lands as one reviewable, revertible unit.
