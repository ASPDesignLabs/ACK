# Changelog

All notable changes to ACK are logged here. These same notes are available in-app from the TERMINAL view — type `/info` and send it.

## [1.0-beta.7] - Unreleased

### Fixed
- Output could go quiet or fail to reach the car's speakers at all when connected to Android Auto. ACK never requested audio focus on any playback path -- fine on a phone with nothing else competing, but Android Auto is strict about the standard Android focus handshake while it's juggling navigation, music, and calls, and an app that never asks has no standing in that negotiation. Every dispatch now briefly requests audio focus before playing (and releases it right after), the same signal every well-behaved Android app sends to say "let this through."

## [1.0-beta.6] - 2026-09-22

### Added
- **Pick which device ACK's audio goes to.** A new OUTPUT DEVICE section in PROTOCOL, right below FORCE SPEAKER, lists your currently-connected Bluetooth devices plus ACK WATCH -- tap one to route every spoken prompt there instead of leaving it to whatever the phone's system audio route happens to be. No OS-level settings involved: this only ever reads which devices are already connected, never touches anything outside ACK. FORCE SPEAKER always overrides whatever's picked here. If your selected device disconnects, ACK falls back to the phone's normal output rather than going silent.
- **ACK WATCH as an output device.** Selecting it relays the fully-processed prompt (already gain-adjusted, already effects-applied) to the paired ACK Wear app for playback right there, using the same WATCH AUDIO FEEDBACK volume already in PROTOCOL. Falls back to the phone automatically if the watch isn't reachable when a prompt fires.

### Fixed
- Recorded voice prompts didn't consistently follow AUDIO ARCHITECT's Master Gain the way synthesized speech does. Master Gain was always being applied correctly — the real problem was that a raw recording's starting loudness depends entirely on how loud you spoke and how close to the mic you were, so multiplying two different recordings by the same gain produced two different results. Every recording is now loudness-normalized to a consistent baseline (right after noise reduction and silence trimming, alongside the existing processing step), so Master Gain multiplies from the same starting point every time — the same way it already does for synthesized speech. Existing recordings are normalized automatically, once, the next time you open the app.
- Every spoken prompt — synthesized or recorded, Emergency included — now always nudges the device's media volume up to an audible floor before it plays, rather than only doing so once Master Gain was boosted above a threshold. Output could previously go quiet if something outside ACK (a Bluetooth headset's own volume control, the notification volume rocker, anything else touching the same volume stream) had turned system volume down since the last time that threshold was crossed. This never lowers volume you've deliberately set high — only raises a stream that's sitting below the floor.

## [1.0-beta.5] - 2026-09-21

### Added
- **Voice recordings for Quick Actions, Quick-Access keys, and Matrix entries.** Record your own voice for any prompt instead of relying on synthesized speech — mic capture with automatic noise reduction and silence trimming, a preview before you accept it, and an adjustable recording-only playback gain in PROTOCOL.
- **Visual prompt override for recorded Matrix entries.** A Matrix node with a recording bound to it can also set what shows on the overlay while it plays, instead of falling back to raw template text. Nothing about the underlying template or variable setup is touched — remove the recording and everything reverts exactly as it was.
- **MANAGE RECORDINGS rebuilt as a drill-down tree.** Browse by Deck > Profile > Pose > Slot (Matrix), Deck > Group > Slot (Quick Actions), or a flat list (Quick-Access keys). Each entry shows its overlay text, play time, and file size, with re-record, play, and delete right there.
- **Overlay-on-play toggle in MANAGE RECORDINGS.** A persisted switch next to CLOSE — when on, tapping PLAY also shows the recording's own text on the overlay, a second way to confirm you've found the right one.
- **`/info` in the TERMINAL.** Type `/info` and send it to read these patch notes line-by-line right in the app. While the command bar reads exactly `/info`, the STATUSBOX's TYPING indicator is replaced by a one-tap `INFO` shortcut. Shake to stop the readout early.
- **One-tap confirmation for `/cls` and `/backup`.** Both commands still require confirming before they run, but you no longer have to retype the whole command with `confirm` added — while the bar holds the bare (unconfirmed) form of either, the STATUSBOX shows "THIS COMMAND REQUIRES CONFIRMATION" and a one-tap `CONFIRM` shortcut.
- **A VOICE RECORDINGS category in HELP.** Three walkthroughs — recording a prompt, Matrix-specific caveats (variables, the visual override, re-enabling after an edit), and MANAGE RECORDINGS' tree browser — reachable from HELP's new VOICE RECORDINGS tab at any time. A small, dismissible one-time tip also points you there the first time you tap RECORD or open MANAGE RECORDINGS.

### Changed
- The Matrix Live-Save Editor's DESTRUCTIVE CONTROLS section is now collapsed by default, cutting the scroll distance to COMMIT/CLOSE.

### Fixed
- Recording preview playback (the PLAY button in the EDIT QUICK ACTIONS UI and MANAGE RECORDINGS) could go silent when the device's media volume was low. Preview now routes through the same volume-enforced pipeline every other prompt in the app already uses.
- Leading silence wasn't being trimmed from voice recordings (only trailing silence was). Speech onset now requires several consecutive above-threshold windows rather than just one, so a brief capture-start transient can't be mistaken for the start of speech.

## [1.0-beta.3] and earlier

See [GitHub Releases](https://github.com/ASPDesignLabs/ACK/releases) for prior beta notes.
