# Building Out ACK's In-App Help / Tutorial Modules

## What wiring in the first 3 modules taught us
The Help system (`HelpRegistry` -> `HelpManager` -> `HelpMenuDialog` / `HelpCoachDialog`) only advances a step when a real event fires from the actual UI: a tap on a specific tagged element, a committed text field, a cleared overlay, a watch gesture broadcast. That event-driven design is what makes it a genuine walkthrough instead of a slideshow.

It also means a module is only as good as the tags it points at. Several already-written modules (`EmergencyDeckHelp`, `EmojiDeckHelp`, `GifDeckHelp`, `QuickActionsDeckHelp`, and the fuller `DeckManagementHelp` / `ManualOverrideHelp` rewrites) reference `AckTags` constants that exist in `AckTags.kt` but were never applied to any composable. Registering them as-is would strand users mid-module with no way forward except the abort button. That's why only `BasicsNavigationHelp`, `GeoProtocolHelp`, and `LogsHelp` got wired in first — their target tags were already confirmed live in `MainActivity.kt`.

## The checklist, for every module (new or existing)
1. **Find the real UI.** Open the actual Compose screen/dialog for the feature (e.g. `EmergencyDeck.kt` for the Emergency deck). Identify exactly which element each tutorial step should point at.
2. **Confirm the tag, don't assume it.** Check `AckTags.kt` for an existing constant. If a help-content file already references one, that's a claim, not a fact.
3. **Apply the tag to the composable** using whatever pattern the app already uses (`.testTag(AckTags.X)` and/or `.helpTarget(AckTags.X, primaryColor)`) — check a tag that's already proven to work, like `AckTags.DECK_SELECTOR` in `MainActivity.kt`, for the exact convention to copy.
4. **Match the `HelpAction` to how the interaction really happens in code.** `Interact` for a tap, `CommitText`/`CommitFile` for a save action, `OverlayCleared` for a dismiss, `WatchEvent` for a broadcast-driven gesture event. Check where the matching `HelpEvent` is actually dispatched (`grep -rn "helpManager.onEvent\|HelpEvent\." app/src/main/java/com/example/besu`) so the step advances when you expect it to.
5. **Verify before registering:**
   ```
   grep -rn "AckTags.<YOUR_TAG>" app/src/main/java/com/example/besu --include="*.kt"
   ```
   Confirm the tag shows up in a real view file, not only in the help-content file and `AckTags.kt`.
6. **Register in `HelpRegistry.kt`.** Append the module reference. Check its `HelpCategory` lands it somewhere sensible — see `defaultHelpCategory()` in `HelpMenuDialog.kt` if it should be the default landing module for a given deck type.
7. **Smoke-test on device.** Open Help, launch the module, step through every single action to the end. Nothing above substitutes for actually running it once — this is the step that would have caught the current gap.

## What's left, ranked by how much tagging work step 3 needs
- **Watch gesture / pose calibration onboarding** — needs *no* tagging at all. The event plumbing (`HelpEvent.WatchInput("ARMED"/"POSE_ID"/"MODIFIED"/"FIRE")`) already fires from real watch broadcasts in `MainActivity.kt`; it's currently unused by any module. This is just a new `HelpModule` written with `HelpAction.WatchEvent(...)` steps, reusing the narrative the old (dead) `TutorialScript.MOD_SENSORS` already had. Highest value, lowest risk — do this first.
- **Deck Management rewrite** — needs `DECK_CREATE_TYPE`, `DECK_CREATE_COMMIT`, `DECK_MANAGE_BUTTON` tagged wherever deck creation actually happens (`CreateDeckDialog.kt` is the likely home). 3 tags.
- **Manual Override rewrite** — needs `MANUAL_MEMORY_BANKS`, `MANUAL_TEXT_FIELD`, `MANUAL_SEND` tagged in the Manual/TYPE view in `MainActivity.kt`. 3 tags.
- **Emergency / Emoji / GIF / Quick Actions decks** — each deck's view file (`EmergencyDeck.kt`, `EmojiDeck.kt`, `GifDeck.kt`/`GifPlayer.kt`, `QuickActionsDeck.kt`) currently has zero help tags applied. 3-5 tags each.

Suggested build order: watch gesture module first, then Quick Actions and Emergency (likely the simplest deck UIs to tag), then Emoji and GIF, then the two rewrites last.

## Workflow
Do this on its own branch per module (see `docs/GIT_WORKFLOW.md`), e.g. `feature/help-emergency-deck-tags`, so each deck's tagging + content lands as one reviewable, revertible unit instead of one large sweep.
