# Landing page assets

Drop real screenshots and GIFs of ACK here — for `index.html` at the repo
root, not the Android app's own `app/src/main/assets/` (that one's map data
for Mapsforge, unrelated to this).

- `screenshots/` — static phone screenshots, **9:16 aspect ratio** to match
  the lightbox's frame. Any resolution is fine as long as the ratio holds;
  the page center-crops for the small thumbnail and shows the full image in
  the zoomable preview.
- `gifs/` — short recordings (e.g. the gesture arm/lock/modify/fire cycle,
  watch pairing, a deck in use).

Dropping a file in here doesn't wire it up by itself — `index.html` still
needs to point at it. There are ten image slots in the page right now, seven
of them already built as clickable lightbox thumbnails (the deck screenshots)
and three as simpler static placeholders (full-screen playback and the two
Wear OS shots). Suggested filenames, matching what each slot already expects:

| Slot | Suggested filename | Wiring |
|---|---|---|
| MATRIX Deck | `screenshots/matrix-deck.png` | `data-shot-src` on that deck's `.shot-thumb` button |
| Quick Actions Deck | `screenshots/quick-actions-deck.png` | same |
| Emergency Deck | `screenshots/emergency-deck.png` | same |
| Emoji Deck | `screenshots/emoji-deck.png` | same |
| GIF Deck | `screenshots/gif-deck.png` | same |
| Manual Override | `screenshots/manual-override.png` | same |
| Target Computer | `screenshots/target-computer.png` | same |
| Full-screen prompt playback | `screenshots/fullscreen-playback.png` | static placeholder in `#how-it-works` |
| Watch gesture cycle (ARM/LOCK/FIRE) | `gifs/watch-gesture-cycle.gif` | static placeholder in `#how-it-works` |
| Watch pairing / pose selector | `screenshots/watch-pairing.png` | static placeholder in `#watch` |

For the seven deck slots: once a file lands here, set
`data-shot-src="assets/screenshots/<filename>"` on that deck's `.shot-thumb`
button in `index.html` and the thumbnail + lightbox pick it up automatically
— no other markup changes needed. The three static placeholders need their
`.placeholder-shot` block swapped for a real `<img>` (or a `<video>`/`<img>`
for the GIF) — ask and I'll wire whichever ones you've captured.
