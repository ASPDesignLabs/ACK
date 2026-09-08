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
- `social/` — the Open Graph / X (Twitter) card and its source, see below.

Dropping a file in here doesn't wire it up by itself — `index.html` still
needs to point at it. There are ten image slots in the page. Status:

| Slot | Filename | Status |
|---|---|---|
| MATRIX Deck | `screenshots/matrix-deck.png` | ✅ wired |
| Quick Actions Deck | `screenshots/quick-actions-deck.png` | ✅ wired |
| Emergency Deck | `screenshots/emergency-deck.png` | Not yet captured |
| Emoji Deck | `screenshots/emoji-deck.png` | ✅ wired |
| GIF Deck | `gifs/gif-deck.gif` | ✅ wired (animates in the thumbnail crop and the zoomed lightbox) |
| Manual Override | `screenshots/manual-override.png` | ✅ wired |
| Target Computer | `screenshots/target-computer.png` | ✅ wired |
| Full-screen prompt playback | `screenshots/fullscreen-playback.png` | ✅ wired (static, in `#how-it-works`) |
| Watch gesture cycle (ARM/LOCK/FIRE) | `gifs/watch-gesture-cycle.gif` | Not yet captured |
| Watch pairing / pose selector | `screenshots/watch-pairing.png` | Not yet captured |

For the seven deck slots: dropping a file in here and setting
`data-shot-src="assets/screenshots/<filename>"` on that deck's `.shot-thumb`
button in `index.html` is all it takes — the thumbnail crop and lightbox
pick it up automatically, GIFs included. The three static placeholders need
their `.placeholder-shot` block swapped for a real `<img>` — ask and I'll
wire whichever ones you've captured.

## `social/` — Open Graph / X card

`og-card.png` (1200×630, the standard size both Facebook and X read) is what
renders when a link to this page gets shared. `og-card.source.html` is its
actual source — a standalone page laid out at exactly 1200×630, screenshotted
rather than hand-exported, so it's fully editable.

To regenerate after changing the source (new hero screenshot, copy tweaks,
etc.): render it at 2x scale (2400×1260) with a headless browser and
downscale to 1200×630 for crisp antialiased text — a plain 1x screenshot
looks noticeably softer. Ask and I'll do this end-to-end again.

`index.html`'s `<head>` references this image by an **absolute URL**
(`https://aspdesignlabs.github.io/ACK/assets/social/og-card.png`) — both
platforms fetch it directly rather than resolving it relative to the page,
and both cache it aggressively. After changing it post-launch, use
[Facebook's Sharing Debugger](https://developers.facebook.com/tools/debug/)
and [Twitter's Card Validator](https://cards-dev.twitter.com/validator) to
force a re-scrape — otherwise stale previews can linger for days.
