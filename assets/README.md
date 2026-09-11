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
- `favicon/` — the site favicon, generated from the phone app's own
  `app/src/main/ic_launcher-playstore.png` (the neon "ACK" wordmark), see
  below.

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

## `favicon/` — browser tab icon

Generated straight from `app/src/main/ic_launcher-playstore.png` (512×512,
the same neon wordmark used on the Play Store listing) — resized down, no
redesign. `index.html` links all of these from `<head>`:

| File | Size | Used for |
|---|---|---|
| `favicon.ico` | 16/32/48 multi-size | Legacy browsers, bookmarks |
| `favicon-16.png` / `favicon-32.png` / `favicon-48.png` | 16×16 / 32×32 / 48×48 | Browser tab |
| `favicon-192.png` / `favicon-512.png` | 192×192 / 512×512 | Android home-screen / PWA-style icons |
| `apple-touch-icon.png` | 180×180 | iOS home-screen icon |

Heads up on legibility: the wordmark reads fine at 32px and up, but at the
16px size some browser tabs actually render, it's close to an illegible
smudge — that's the wordmark itself (dense multi-letter text doesn't
downscale well), not a rendering bug. Worth a dedicated small-size mark
(just the outline, no letters) if that ever bothers you enough to revisit.

Regenerate any time the source icon changes:
```
python3 -c "
from PIL import Image
src = Image.open('app/src/main/ic_launcher-playstore.png').convert('RGBA')
for name, size in {'favicon-16.png':16,'favicon-32.png':32,'favicon-48.png':48,
                    'apple-touch-icon.png':180,'favicon-192.png':192,'favicon-512.png':512}.items():
    src.resize((size,size), Image.LANCZOS).save(f'assets/favicon/{name}')
src.resize((256,256), Image.LANCZOS).save('assets/favicon/favicon.ico', sizes=[(16,16),(32,32),(48,48)])
"
```

**A missing favicon almost certainly isn't why X/Twitter card rendering is
inconsistent** — Twitter Cards and Open Graph both work purely off the
`twitter:*`/`og:*` meta tags, not the favicon. The far more likely cause:
this repo's build-plan status notes that **enabling GitHub Pages itself is
still an open step** — if Pages isn't live yet, the `og:image` URL these
crawlers fetch 404s. Facebook's scraper can look fine anyway if it's
serving a stale cached result from an earlier check; X's Card Validator
tends to re-fetch live and shows the 404 immediately. Worth checking Pages
is actually enabled and the image URL resolves before chasing anything
else — and re-validating with
[Twitter's Card Validator](https://cards-dev.twitter.com/validator) and
[Facebook's Sharing Debugger](https://developers.facebook.com/tools/debug/)
either way, since both cache aggressively.
