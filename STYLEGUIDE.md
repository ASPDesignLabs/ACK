# Portable GitHub Pages Style Guide

## What this is

This is the methodology behind [ACK's landing page](index.html), extracted so
it can be handed to another agent to build a similarly-styled GitHub Pages
site for a *different* app. It is not a skin to paste onto another project —
the specific colors, fonts, and motifs shown here are ACK's own identity,
used throughout as **a worked example**, not a mandate. What *does* carry
over unchanged is everything under **Non-negotiables**: the accessibility
floor and technical constraints that hold regardless of which app this is
for.

If you are the agent building the next one of these: read **Non-negotiables**
and **Process** in full before writing any code. Everything else is
reference material to adapt, not copy.

---

## Non-negotiables

These apply no matter what the target app looks like. They are not
suggestions.

1. **Static, no build step.** A single self-contained `index.html` (plain
   HTML/CSS/vanilla JS) that GitHub Pages can serve directly from the repo
   root. No framework, no bundler, no external font or script CDN unless the
   target app's own brand genuinely requires a licensed webfont — the
   default is zero external requests, matching most personal/accessibility
   projects' own offline-first ethos and keeping the page trivially
   inspectable.

2. **WCAG AA contrast on every color actually used for text or a UI
   boundary** — 4.5:1 for body text, 3:1 for large text (≥24px or ≥19px
   bold) and meaningful non-text UI (borders, icon strokes). Check every
   pairing programmatically, don't eyeball it. Reference implementation
   (relative luminance / WCAG contrast ratio):

   ```python
   def lum(hex):
       hex = hex.lstrip('#')
       r, g, b = int(hex[0:2],16)/255, int(hex[2:4],16)/255, int(hex[4:6],16)/255
       f = lambda c: c/12.92 if c <= 0.03928 else ((c+0.055)/1.055)**2.4
       r, g, b = f(r), f(g), f(b)
       return 0.2126*r + 0.7152*g + 0.0722*b

   def ratio(a, b):
       la, lb = lum(a), lum(b)
       la, lb = max(la, lb), min(la, lb)
       return (la + 0.05) / (lb + 0.05)
   ```

   Run every text/background pair the page actually uses through this
   before shipping. If a brand color fails, keep the pure/bright version for
   decoration only (borders, glows, icons) and derive a slightly
   darkened/lightened "text-safe" variant for anything that carries copy —
   this is exactly why ACK's palette has both `--cyan` (`#00c3cc`, text-safe,
   9.4:1 on black) and `--cyan-bright` (`#00f3ff`, decorative-only, never
   used for text).

3. **Respect `prefers-reduced-motion`.** At minimum, collapse all animation/
   transition durations to near-zero under it, and drop `scroll-behavior:
   smooth` to `auto`:

   ```css
   html { scroll-behavior: smooth; }
   @media (prefers-reduced-motion: reduce) {
     html { scroll-behavior: auto; }
     * { animation-duration: 0.001ms !important; animation-iteration-count: 1 !important; transition-duration: 0.001ms !important; }
   }
   ```

4. **No autoplaying audio or video, ever.**

5. **Keyboard operability and visible focus everywhere.** Every interactive
   element must be reachable and operable by keyboard alone, with a visible
   `:focus-visible` state — don't rely on `:hover` for anything essential.

6. **A skip-to-content link as the first tab stop:**

   ```html
   <a class="skip-link" href="#main">Skip to main content</a>
   ```
   ```css
   .skip-link { position: absolute; left: -999px; }
   .skip-link:focus { left: 1em; top: 1em; }
   ```

7. **Prefer native interactive elements over hand-rolled ARIA widgets.**
   `<details>`/`<summary>` and `<dialog>` give you correct keyboard handling,
   expanded/collapsed and modal semantics, and Escape-to-close for free,
   more robustly than a custom `role="menu"`/`role="dialog"` reimplementation
   will. Reach for them first. The one sharp edge to know about:

   > `<summary>`'s content model does not allow heading elements
   > (`<h1>`–`<h6>`) as its first child. If a collapsible section's header
   > must remain a real heading — which it must, whenever it's one of the
   > page's primary section headings, so screen-reader users can still
   > navigate by heading — use the ARIA APG disclosure pattern instead:
   > `<h2><button aria-expanded aria-controls>Heading text</button></h2>`
   > plus a sibling `<div hidden>` panel. See **Collapsible sections**
   > below for the full pattern, including the `<noscript>` fallback this
   > requires (a hidden `<div>`, unlike `<details>`, has no built-in
   > no-JS escape hatch — content must never become strictly unreachable).

8. **Never permanently hide primary content behind JS alone.** Anything
   that depends on JavaScript to become visible needs a `<noscript>` rule
   that forces it visible if JS never runs.

9. **Real `alt` text on every meaningful image; `aria-hidden="true"` on
   every purely decorative icon/glyph.**

10. **Write display text in normal case; apply visual uppercase via CSS
    `text-transform: uppercase`, not literal caps in the source.** Some
    screen readers will spell out literal all-caps text letter by letter.

11. **Never rewrite or "improve" the app owner's own supplied copy.**
    Structure, navigation, and presentation are yours to design; their
    words are not yours to edit. If you think copy needs a change, ask —
    don't silently reinterpret their voice.

12. **A link to a collapsed section must land the user somewhere useful,
    expanded.** Never leave someone at a heading with hidden content and no
    obvious way in. (In practice this is nearly free: collapsing only ever
    hides content *below* a heading, so the heading's scroll position never
    moves, and the standard hashchange handler in **Collapsible sections**
    handles the rest.)

13. **Every custom interactive component** (a lightbox, a dropdown, an
    accordion) **needs: full keyboard operability, more than one way to
    close/escape it (Escape key at minimum, ideally also an explicit close
    control and a backdrop/outside click), and focus returned to whatever
    triggered it on close.**

14. **Gesture-only controls need a button fallback.** If a component
    supports pinch-zoom or drag-to-pan, also give it explicit on-screen
    +/−/reset buttons. Not everyone can pinch, drag, or scroll-wheel
    precisely, and a real button is unambiguous to operate for keyboard and
    switch-access users alike.

15. **Verify in an actual browser before calling anything done** — desktop
    and mobile widths, keyboard-only pass, the no-JS fallback, and every
    color pairing run through the contrast formula above. Screenshots or
    "should work" reasoning about markup you haven't rendered is not
    verification.

---

## Discovering the target app's own identity

Do not reuse ACK's cyan/void-black palette or cut-corner motif on an
unrelated app. Before writing a single line of the new page, go find that
app's *own* identity, the same way you'd research any other feature:

- **App icon(s)** — usually the single most reliable source of a real
  color palette; extract from the actual launcher icon files, don't guess.
- **In-app theme/design system, if the app has one.** ACK defines its own
  "NEON FLUX" color palette (`ui/theme/Color.kt`) and reuses Jetpack
  Compose's built-in `CutCornerShape` consistently across dozens of its own
  UI components (borders, backgrounds, badges) — the landing page's
  cut-corner panels and neon accent are that exact motif carried onto the
  web, not an invented one. Look for the equivalent in the target codebase:
  a distinctive shape, corner treatment, icon style, or texture already
  used repeatedly in the real product. Reusing something that's *already
  the app's own signature* reads as authentic; inventing a new one for the
  marketing page reads as generic.
- **The app's actual name, tagline, and how its own README/store listing
  describes it** — start from what the owner already wrote about their own
  project, don't draft new marketing copy from scratch.
- **Typography personality.** ACK's monospace "command console" look fits
  *that* app's own in-app voice (`ARM`/`LOCK`/`FIRE`, `TARGET SLOTS`). A
  different app calls for a different typographic personality — don't
  default to monospace-everywhere just because that's what this reference
  implementation used.

If the app genuinely has no distinct visual identity of its own to work
from, adapting this guide's void-black/single-accent palette as a neutral
fallback is reasonable. Confirm that read with the project owner before
assuming it, though — silently reusing another app's brand on this one is
exactly the kind of thing rule 11 is about.

---

## Process

1. **Read the actual codebase before writing any copy.** Every factual claim
   on the page — what a feature does, whether something runs offline, what
   permissions it needs — has to be sourced from the real code (manifest,
   permissions, dependency list, actual source files), not assumed. For
   ACK, "runs fully offline" was verified against the literal absence of an
   `INTERNET` permission in `AndroidManifest.xml`, and that verification
   caught a real gap later (a Play-Services-backed feature *does* send data
   off-device in one of its two modes) that a plausible-sounding assumption
   would have missed. Do the equivalent check for whatever privacy or
   offline claims the new page wants to make.

2. **Draft a short plan before building**, covering at minimum: where
   GitHub Pages will actually serve from (root of `main` is simplest), what
   license (if any) is being added, whether real screenshots exist yet or
   the page ships with placeholders, and what tone the copy should carry.
   Treat each as an explicit decision the project owner signs off on, not a
   silent default — this alone prevents most of the rework in a project
   like this.

3. **Build the information architecture before the visual design.**
   Inventory every feature/section the app actually has, then group them
   into 3-4 categories by *what a visitor is trying to do* (Product /
   Companion features / Project-meta, or similar) — not by how the code
   happens to be organized internally. See **Page architecture** below for
   the full pattern this feeds into.

4. **Build it, verify it in a browser, then ship it** — per non-negotiable
   15. Don't skip the verification pass because the markup "looks right."

5. **Never merge, enable Pages, or delete anything without the project
   owner's explicit go-ahead.** Push to a branch, open a PR, let them
   review and merge on their own timeline.

---

## Page architecture

A single long page, organized as:

1. **Hero** — always visible, no accordion. What the app is, who it's for,
   and any disclaimers the owner wants up front, in their own words.
2. **Status/WIP banner**, if applicable — an honest, visible note about the
   project's actual maturity. Optional; only if it's true.
3. **First content section — always visible, no accordion.** Whatever a
   first-time visitor needs to understand before anything else (ACK uses
   "How it works": tap vs. gesture vs. full-screen output). Everything after
   this collapses by default.
4. **Every other content section collapses behind its own heading** — see
   **Collapsible sections** below. This is what keeps a page with a dozen
   features from reading as an overwhelming wall of scroll, without ever
   actually removing content from the page.
5. **Footer** — license + repo links.

Navigation is a **sticky bar with a brand mark and 3-4 grouped pill
dropdowns**, not a flat row of every section as its own link. A flat list of
8-10 links either wraps unpredictably or forces horizontal scroll on
mobile with no visible cue that there's more off-screen — both read as
dated. Grouped pills give you one interaction pattern that works
identically at every viewport width. See **Grouped nav pills** below for
the full pattern.

---

## Component patterns

Every pattern below is copied down to the exact markup/CSS/JS that shipped
on ACK's page, with the bugs already found and fixed. Adapt class names,
colors, and copy — the mechanics don't need to be re-derived or re-debugged.

### Design tokens

Define the whole palette as CSS custom properties once, at `:root`, so
every other rule below just references them:

```css
:root {
  --void: #050505;         /* page background */
  --graphite: #121212;     /* panel/card background */
  --graphite-2: #1a1a1a;   /* secondary panel background */
  --border: #2a2a2a;
  --text: #e8e8e8;         /* primary body text */
  --text-dim: #a8a8a8;     /* secondary text */
  --text-faint: #808080;   /* tertiary/caption text -- verify this one
                               especially, it's the tone most likely to
                               fail contrast if darkened too far */
  --accent: #00c3cc;       /* text-safe accent -- links, small labels */
  --accent-bright: #00f3ff;/* decorative-only -- borders, glow, icons.
                               never use for text */
  --error: #ff5470;        /* text-safe error/warning tone */
  --font-display: ui-monospace, "SF Mono", "Cascadia Code", "Roboto Mono", Consolas, monospace;
  --font-body: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
}
```

Swap every value except the *relationship* between them (a near-black
background; 2-3 text tones each independently contrast-checked; one
text-safe accent plus one decorative-only bright variant of it) for the
target app's own palette.

### Grouped nav pills

```html
<nav class="top" aria-label="Section navigation">
  <div class="nav-inner">
    <a class="nav-brand" href="#main">APPNAME</a>
    <div class="nav-groups">
      <details class="nav-pill">
        <summary>Group Label <span class="car" aria-hidden="true">&#9662;</span></summary>
        <div class="nav-dropdown">
          <a href="#section-one">Section One</a>
          <a href="#section-two">Section Two</a>
        </div>
      </details>
      <!-- repeat per group -->
    </div>
  </div>
</nav>
```

```css
nav.top { position: sticky; top: 0; z-index: 10; border-bottom: 1px solid var(--border); }
.nav-inner { display: flex; align-items: center; gap: 1.5rem; flex-wrap: wrap; padding: 0.75rem 1.5rem; }
.nav-groups { display: flex; flex-wrap: wrap; gap: 0.6rem; }
details.nav-pill { position: relative; }
details.nav-pill > summary {
  list-style: none; cursor: pointer; text-transform: uppercase;
  color: var(--text-dim); background: var(--graphite); border: 1px solid var(--border);
  padding: 0.5rem 0.9rem; display: inline-flex; align-items: center; gap: 0.4rem;
}
details.nav-pill > summary::-webkit-details-marker { display: none; }
details.nav-pill > summary::marker { content: ""; }
details.nav-pill[open] > summary { color: var(--accent-bright); border-color: var(--accent-bright); }
details.nav-pill > summary .car { transition: transform 0.15s ease; }
details.nav-pill[open] > summary .car { transform: rotate(180deg); }
.nav-dropdown {
  position: absolute; top: calc(100% + 6px); left: 0; min-width: 220px;
  background: var(--graphite); border: 1px solid var(--accent-bright);
  box-shadow: 0 20px 40px rgba(0,0,0,0.6); padding: 0.4rem 0; z-index: 20;
}
.nav-dropdown a { display: block; padding: 0.55rem 1rem; color: var(--text-dim); }
```

```js
var navPills = document.querySelectorAll('details.nav-pill');

// Opening one closes the others.
navPills.forEach(function (d) {
  d.addEventListener('toggle', function () {
    if (d.open) navPills.forEach(function (o) { if (o !== d) o.open = false; });
  });
});

// Click outside any pill closes whichever is open.
document.addEventListener('click', function (e) {
  navPills.forEach(function (d) { if (d.open && !d.contains(e.target)) d.open = false; });
});

// Escape closes and returns focus to that pill's summary.
document.addEventListener('keydown', function (e) {
  if (e.key !== 'Escape') return;
  navPills.forEach(function (d) {
    if (d.open) { d.open = false; var s = d.querySelector('summary'); if (s) s.focus(); }
  });
});
```

### Collapsible sections

Real heading, native disclosure semantics via a button (not `<details>` —
see non-negotiable 7), a hidden panel, and a `<noscript>` fallback declared
once, anywhere in `<head>`:

```html
<noscript><style>.accordion-panel[hidden] { display: block !important; }</style></noscript>
```

Per section:

```html
<section id="feature-x" class="wrap">
  <p class="eyebrow">Category label</p>
  <h2>
    <button type="button" class="accordion-toggle" aria-expanded="false" aria-controls="feature-x-panel">
      The actual heading text
      <span class="chevron" aria-hidden="true">&#9662;</span>
    </button>
  </h2>
  <div id="feature-x-panel" class="accordion-panel" hidden>
    <!-- the section's real content -->
  </div>
</section>
```

```css
.accordion-toggle {
  all: unset; display: flex; align-items: baseline; justify-content: space-between;
  gap: 0.6rem; width: 100%; cursor: pointer; font: inherit; color: inherit;
}
.accordion-toggle:hover { color: var(--accent-bright); }
.accordion-toggle:focus-visible { outline: 2px solid var(--accent-bright); outline-offset: 3px; }
.accordion-toggle .chevron { transition: transform 0.15s ease; }
.accordion-toggle[aria-expanded="true"] .chevron { transform: rotate(180deg); }
```

```js
function setExpanded(btn, expanded) {
  btn.setAttribute('aria-expanded', String(expanded));
  var panel = document.getElementById(btn.getAttribute('aria-controls'));
  if (panel) panel.hidden = !expanded;
}
document.querySelectorAll('.accordion-toggle').forEach(function (btn) {
  btn.addEventListener('click', function () {
    setExpanded(btn, btn.getAttribute('aria-expanded') !== 'true');
  });
});

// A direct link/bookmark into a collapsed section auto-expands it.
// Collapsing never moves the heading above it, so the browser's own
// anchor scroll already lands correctly -- no manual scroll correction needed.
function expandSectionById(id) {
  var el = document.getElementById(id);
  if (!el) return;
  var btn = el.querySelector('.accordion-toggle');
  if (btn && btn.getAttribute('aria-expanded') !== 'true') setExpanded(btn, true);
}
function expandFromHash() { if (location.hash) expandSectionById(location.hash.slice(1)); }
expandFromHash();
window.addEventListener('hashchange', expandFromHash);
```

Wire your nav-dropdown links to call `expandSectionById` too (see the full
`index.html` for the exact click handler) so picking a link expands its
target before the browser's native anchor jump scrolls to it.

**Which sections should start collapsed** is a judgment call, not a rule —
ACK collapsed everything except its first content section. A shorter page
might not need this pattern at all; a page with one dominant feature and
several minor ones might collapse only the minor ones. Ask the project
owner rather than defaulting to "collapse everything."

### Screenshot/GIF lightbox

A small square thumbnail, center-cropped for free via `background-position:
center` (no JS math), that opens a shared `<dialog>` at the image's real
aspect ratio with zoom and pan. The same markup handles animated GIFs with
**no special-casing** — both `background-image` and `<img>` keep a GIF
animating under CSS transforms natively, cropped or zoomed. Verify that
claim yourself before trusting it (hash two frames of the rendered
thumbnail 500ms apart and confirm they differ) rather than taking this
guide's word for it.

Thumbnail, one per item:

```html
<button type="button" class="shot-thumb" data-shot-name="Feature Name" data-shot-src="">
  <span class="shot-thumb-sr">View Feature Name screenshot, full size</span>
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7"/></svg>
</button>
```

Shared dialog, once per page:

```html
<dialog class="shot-dialog" id="shotDialog">
  <button type="button" class="shot-dialog-close" data-shot-close aria-label="Close screenshot preview">&#10005;</button>
  <div class="shot-stage" id="shotStage">
    <div class="shot-stage-placeholder" id="shotPlaceholder" hidden><span id="shotPlaceholderText">Screenshot coming soon</span></div>
    <img id="shotImage" class="shot-image" alt="" draggable="false" hidden>
  </div>
  <div class="shot-controls">
    <button type="button" data-shot-zoom-out aria-label="Zoom out">&minus;</button>
    <button type="button" data-shot-zoom-reset aria-label="Reset zoom">1:1</button>
    <button type="button" data-shot-zoom-in aria-label="Zoom in">+</button>
  </div>
  <p class="shot-hint">Double-click, pinch, or scroll to zoom &middot; drag to pan while zoomed &middot; Esc to close</p>
</dialog>
```

Full CSS and JS (pointer-based drag/pinch, wheel zoom, arrow-key panning,
mutual-exclusion-free open/close via native `<dialog>`, and a `data-shot-src`
auto-wiring loop that also paints the thumbnail's own cropped background)
are copied verbatim from **`index.html`** in this repo — pull the
`.shot-*`/`dialog.shot-dialog` CSS block and the corresponding `<script>`
wholesale rather than retyping it. Two bugs were found and fixed there
during testing, worth knowing about if you're tempted to write this from
scratch instead of reusing it:

- Zooming back out to 1x has to explicitly reset the pan offset to `(0,0)`,
  or the image sits stuck off-center at "normal" zoom.
- The dialog needs `overflow-y: auto` as a safety net, or its content can
  visually overflow past its own `max-height` on very short viewports.

### Social preview card

Add Open Graph + Twitter/X card meta tags to `<head>`, pointing at a
**1200×630** image by absolute URL (both platforms fetch the image
directly; a relative path won't resolve for their crawlers):

```html
<meta property="og:type" content="website" />
<meta property="og:site_name" content="APPNAME" />
<meta property="og:url" content="https://YOUR-ORG.github.io/YOUR-REPO/" />
<meta property="og:title" content="..." />
<meta property="og:description" content="..." />
<meta property="og:image" content="https://YOUR-ORG.github.io/YOUR-REPO/assets/social/og-card.png" />
<meta property="og:image:width" content="1200" />
<meta property="og:image:height" content="630" />
<meta property="og:image:alt" content="..." />
<meta name="twitter:card" content="summary_large_image" />
<meta name="twitter:title" content="..." />
<meta name="twitter:description" content="..." />
<meta name="twitter:image" content="https://YOUR-ORG.github.io/YOUR-REPO/assets/social/og-card.png" />
<meta name="twitter:image:alt" content="..." />
```

Build the card itself from the same design tokens as the page (not a
generic template) — brand mark, tagline, and a real screenshot in a simple
CSS-drawn device frame reads as far more intentional than stock social-card
layouts. Keep the card's *source* HTML in the repo alongside the rendered
PNG (`assets/social/og-card.source.html`), not just the exported image — a
screenshot-derived asset with no editable source is a dead end the next
time copy or the hero screenshot changes. Render it at 2x scale and
downscale to 1200×630 for crisp antialiased text; a plain 1x capture looks
visibly softer.

After the page goes live, run the URL through [Facebook's Sharing
Debugger](https://developers.facebook.com/tools/debug/) and [Twitter's Card
Validator](https://cards-dev.twitter.com/validator) once — both cache
preview images aggressively, and that's how you force the first crawl (or
force a re-crawl after changing the image later).

---

## Assets folder convention

Create this at the **root of the target repo** (not nested under an
existing app-source `assets/` folder the app itself might already have for
unrelated purposes — check for a collision first):

```
assets/
  screenshots/   -- static images, 9:16 (or whatever the app's actual
                    device screenshots are) to match the lightbox frame
  gifs/          -- short recordings
  social/        -- the OG/Twitter card PNG + its editable HTML source
```

Ship `screenshots/` and `gifs/` with a placeholder-friendly `.gitkeep` so
the folders exist in git before any real capture lands, and drop a
`README.md` inside `assets/` — adapt this template directly:

```markdown
# Landing page assets

Drop real screenshots and GIFs of [APP NAME] here — for `index.html` at
the repo root.

- `screenshots/` — static screenshots, [ASPECT RATIO] to match the
  lightbox's frame.
- `gifs/` — short recordings.
- `social/` — the Open Graph / X card and its source.

Dropping a file in here doesn't wire it up by itself — `index.html` still
needs `data-shot-src="assets/screenshots/<filename>"` set on that item's
`.shot-thumb` button. [List each current placeholder slot and its expected
filename here, table format, so it's obvious what's missing at a glance.]
```

Every screenshot placeholder on the page should render clearly as a
placeholder (a striped pattern + "Screenshot coming soon" label), never a
broken-image icon, until a real file is dropped in and wired up. Never
block shipping the page on having every screenshot ready.

---

## Verification checklist before calling it done

- [ ] Every text/background color pairing actually used passes WCAG AA via
      the contrast formula above
- [ ] Rendered and screenshotted at a desktop width (~1280px) and a mobile
      width (~375px) — no overflow, no clipped text, nav wraps sensibly
- [ ] Keyboard-only pass: skip link is the first tab stop and visibly
      focused; every nav pill, accordion toggle, and lightbox control is
      reachable and operable without a mouse
- [ ] `prefers-reduced-motion: reduce` leaves the page fully usable with
      near-zero animation
- [ ] JavaScript disabled: nothing is permanently invisible (accordions,
      collapsed sections)
- [ ] Every custom interactive widget closes at least two ways and returns
      focus to its trigger
- [ ] A direct link to any collapsed section's anchor lands already
      expanded
- [ ] No prose was rewritten from what the project owner actually supplied
- [ ] No console errors (a browser's own automatic `favicon.ico` 404 is not
      a real error)
- [ ] OG/Twitter meta tags resolve to a real, absolute image URL at
      1200×630

---

## Reference implementation

This repository's [`index.html`](index.html) is the live, working version
everything above was extracted from — when in doubt about how a pattern
actually fits together end to end, read it directly rather than
reconstructing it from this guide's excerpts.
