# Changelog

All notable changes to ACK are logged here. These same notes are available in-app from the TERMINAL view — type `/info` and send it.

## [1.0-beta.5] - 2026-09-21

### Added
- **Voice recordings for Quick Actions, Quick-Access keys, and Matrix entries.** Record your own voice for any prompt instead of relying on synthesized speech — mic capture with automatic noise reduction and silence trimming, a preview before you accept it, and an adjustable recording-only playback gain in PROTOCOL.
- **Visual prompt override for recorded Matrix entries.** A Matrix node with a recording bound to it can also set what shows on the overlay while it plays, instead of falling back to raw template text. Nothing about the underlying template or variable setup is touched — remove the recording and everything reverts exactly as it was.
- **MANAGE RECORDINGS rebuilt as a drill-down tree.** Browse by Deck > Profile > Pose > Slot (Matrix), Deck > Group > Slot (Quick Actions), or a flat list (Quick-Access keys). Each entry shows its overlay text, play time, and file size, with re-record, play, and delete right there.
- **Overlay-on-play toggle in MANAGE RECORDINGS.** A persisted switch next to CLOSE — when on, tapping PLAY also shows the recording's own text on the overlay, a second way to confirm you've found the right one.
- **`/info` in the TERMINAL.** Type `/info` and send it to read these patch notes line-by-line right in the app. While the command bar reads exactly `/info`, the STATUSBOX's TYPING indicator is replaced by a one-tap `INFO` shortcut. Shake to stop the readout early.
- **One-tap confirmation for `/cls` and `/backup`.** Both commands still require confirming before they run, but you no longer have to retype the whole command with `confirm` added — while the bar holds the bare (unconfirmed) form of either, the STATUSBOX shows "THIS COMMAND REQUIRES CONFIRMATION" and a one-tap `CONFIRM` shortcut.

### Changed
- The Matrix Live-Save Editor's DESTRUCTIVE CONTROLS section is now collapsed by default, cutting the scroll distance to COMMIT/CLOSE.

### Fixed
- Recording preview playback (the PLAY button in the EDIT QUICK ACTIONS UI and MANAGE RECORDINGS) could go silent when the device's media volume was low. Preview now routes through the same volume-enforced pipeline every other prompt in the app already uses.

## [1.0-beta.3] and earlier

See [GitHub Releases](https://github.com/ASPDesignLabs/ACK/releases) for prior beta notes.
