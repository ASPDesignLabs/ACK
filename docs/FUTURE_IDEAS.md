# Future Ideas

Cross-cutting ideas that came up in passing while working on something else,
noted here so they aren't lost, without committing to when (or whether)
they get built. Not a roadmap or a backlog with priority order — just a
parking lot.

## Native app: a tap/hold gesture-mode preference

Surfaced while porting the Emoji deck to the GitHub Pages Deck Simulator
(`index.html`). The simulator ended up with a **Gesture Mode** setting
(Settings dialog, alongside Motion/Contrast): **App Match** mirrors the
real app's own tap-to-fire / hold-to-configure gesture as closely as a
browser reasonably allows (including a keyboard held-Enter/Space
equivalent); **Accessible Click** swaps every tile to a plain
click-to-configure body plus a small, always-visible action button
instead, with no timed hold anywhere.

The real app has no equivalent — every deck's tiles (`EmojiDeck.kt`,
`QuickActionsDeck.kt`, `EmergencyDeck.kt`, Matrix nodes) hard-code the
tap/hold split via `combinedClickable(onClick, onLongClick)`. A held
gesture asks for motor precision some users won't have, and there's
currently no way to opt into a click-only interaction model on-device the
way the simulator now offers.

Worth exploring at some point: a Settings toggle mirroring the simulator's
own Gesture Mode, defaulting to the current tap/hold behavior so nothing
changes for existing users, with a click-only alternative (e.g. tap opens
the editor, a small on-tile control fires the prompt) for anyone who'd
rather not rely on a timed hold. No work started on this — flagged here for
a future session to pick up.
