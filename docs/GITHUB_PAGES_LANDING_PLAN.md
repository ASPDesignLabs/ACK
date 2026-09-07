# ACK — GitHub Pages Landing Page: Battle Plan

Goal: a public landing page for ACK with **100% feature coverage** — every
deck, every system, every help module represented honestly — built and
reviewed in confirmable stages, not one big drop.

Everything below was sourced by reading the actual code (deck files, the
`*Help.kt` modules that back the in-app tutorial system, `AndroidManifest.xml`,
`build.gradle.kts`, `README.md`, `docs/GIT_WORKFLOW.md`,
`docs/HELP_TUTORIAL_GUIDE.md`) — not guessed. Where something is uncertain or
needs a real decision, it's called out explicitly rather than assumed.

---

## 0. Ground rules

- **This is an accessibility tool, dogfooded daily.** The landing page has to
  meet the same bar: no motion/flashing hazards, real contrast, keyboard
  navigation, plain language layered over the app's "command console" voice.
- **Backups over destruction.** Nothing gets deleted — the old `index.html`
  gets moved and preserved, not erased. Every phase below produces a
  reviewable commit, never a silent overwrite.
- **Edits get confirmed.** Open decisions are flagged as decisions, not
  quietly resolved. The built page gets shown before it goes live.
- **Honesty over polish.** README already says "heavy work in progress...
  expect bugs" and "I am not a speech language pathologist..." — the landing
  page keeps that framing, not marketing gloss.

---

## 1. Decisions needed before build work starts

1. **Pages hosting source.** Root of `main`, `/docs` folder, or a dedicated
   `gh-pages` branch + Actions workflow? (Recommendation: root of `main` —
   simplest, no build step, no extra branch to keep in sync.)
2. **License.** No `LICENSE` file exists today. Add one before publishing a
   public page (even "all rights reserved, source available for reference")?
3. **Screenshots / media.** None exist in the repo — only the two Play Store
   app icons (`app/src/main/ic_launcher-playstore.png`,
   `wear/src/main/ic_launcher-playstore.png`). Real screenshots/recordings of
   decks, the gesture cycle, and watch pairing need to come from your device.
   Do we launch v1 with icon + text only and add real captures after, or hold
   the page until captures exist?
4. **Tone for the "sharper-edged" features.** Target Computer, Geo-Protocol,
   Field Ops, root/variable overrides read very "command console" in-app
   (by design). For a public page aimed partly at people evaluating ACK for
   themselves, do we keep that voice as the brand, or soften the copy so it
   doesn't read as more technical/intimidating than the feature actually is?
5. **Old `index.html`.** Confirmed: it's the parked visual/mosaic importer
   prototype (paired with `MosaicScannerActivity.kt`). Plan is to move it to
   `legacy/mosaic-importer/index.html` with a one-line note explaining what it
   is — confirm that path works before I move it.

---

## 2. Phase 0 — Housekeeping

- Move `index.html` → `legacy/mosaic-importer/index.html` (pending confirmation
  of path in decision 5). Add a 2-line `legacy/mosaic-importer/README.md`:
  what it was for, that it's inactive, and where the live code
  (`MosaicScannerActivity.kt`) still lives.
- Resolve decision 1 (Pages source) and configure it.
- Add `.nojekyll` at the Pages root if needed (only matters if we ever add
  files/folders starting with `_`; otherwise skip).
- Resolve decision 2 (license).

## 3. Phase 1 — Information architecture (the coverage checklist)

Every section below maps to a verified, real feature. This list *is* the
100%-coverage contract — nothing ships until every row has a section.

**A. Orientation**
- Hero: what ACK is, who it's for ("non-traditional AAC," situational
  mutism framing from the README), the "not a clinician" disclaimer.
- Status banner: solo project, heavy WIP, expect bugs, link to issues.

**B. How you communicate**
- Tap-based control (works without the watch).
- Gesture-based, touch-free playback via the Wear OS companion — works even
  with the phone locked.
- The three-pose gesture system + modifiers (arm → lock pose → modify → fire).
- Full-screen visual + audible prompt playback, with audio routing to phone
  or Bluetooth speaker output.

**C. Decks (the organizing system)**
- Decks vs. profiles, switching decks.
- **Emergency Deck** — high-priority prompts, output overrides, clearing.
- **Emoji Deck** — visual/emoji prompts, library picks, related panels.
- **GIF Deck** — local GIF import, categories, playback (meme-based
  communication).
- **Quick Actions Deck** — 3 poses × 4 fixed actions per group, fast fixed
  output.
- **Manual Override** — memory banks, saved phrases, direct keyboard input
  (the fallback when gestures aren't convenient).
- **Matrix Deck(s)** — multi-deck, root/variable-driven, live template
  editor, node-based prompt construction, per-deck profiles.
- **Target Computer** — configurable target slots, prepend/append text,
  message routing.
- Deck management — create, name, recolor, organize, delete.

**D. Making it sound like you**
- Voice Profile / "Audio Architect": base voice, pitch/speed, robotic
  overlay, bitcrush texture, custom profile slots, output routing, DSP chain.
- Template engine: composable & bridged statements, context-based replies,
  variables.

**E. Location awareness**
- Geo-Protocol: location-based context/zone behavior. Stated plainly and
  accurately: on-device only — the app requests no `INTERNET` permission
  anywhere in the manifest, so this is verifiably local-first, not a cloud
  feature.

**F. Training & confidence-building**
- Training Ground — free-form gesture practice, live telemetry, no real
  output (a safe sandbox).
- Deck Trainer — scored practice against your real Matrix/Quick Actions deck.
- Pose training walkthroughs (the arm/lock/modify/fire cycle, taught safely).

**G. The Wear OS companion**
- Pairing/sync model, what runs on watch vs. phone, background sensor
  service.

**H. Help, onboarding & transparency**
- The in-app guided tutorial system (coach marks that only advance on real
  UI events — worth explaining, it's a genuine differentiator).
- System Logs — read output/watch/system event history.
- Settings — watch audio feedback, hardware/sensor config, shortcuts, and
  "Data Port" (backup/restore/transfer) — this last one dovetails nicely with
  an accessibility-tool ethos of user control over their own data.

**I. Under the hood / for developers**
- Stack: Kotlin, Jetpack Compose, Wear OS, Mapsforge (offline vector maps —
  explains *why* offline maps: geo features keep working with zero network
  dependency).
- Build instructions summary (Android Studio, Gradle, the custom Mapsforge
  map splice into `app/assets`) linking out to a fuller doc.
- Contributing / git workflow, linking `docs/GIT_WORKFLOW.md`.
- Parked/experimental: the visual/mosaic importer, clearly labeled inactive.

**J. Status & disclaimers**
- Roadmap snapshot pulled honestly from `docs/HELP_TUTORIAL_GUIDE.md`'s
  "what's left" list (flagged in the plan as something that will drift and
  needs a periodic re-check against that file, not a one-time copy).
- Creator's disclaimer, license (once decided), links to source & issues.

## 4. Phase 2 — Visual design system

- Reuse ACK's own identity for continuity: Void Black `#050505` / Graphite
  `#121212` base, the cut-corner "terminal/HUD" panel motif, one neon accent
  (default Cyan `#00F3FF`) as the primary accent color — not all 10 in-app
  neon presets, which are a personalization feature, not a marketing device.
- Accessibility guardrails sit *on top of* that identity and win any
  conflict:
  - No animated background noise, no flashing faster than 3Hz — the page
    must never actually recreate the old mosaic-scanner flicker effect.
  - Respect `prefers-reduced-motion` and `prefers-color-scheme`; the page
    works fully with motion off.
  - WCAG AA contrast check on every neon-on-void pairing actually used for
    text — saturated neon reserved for accents/borders, not paragraph copy.
  - No autoplaying audio or video, anywhere — fitting, since the product
    itself is built around deliberate, user-initiated audio playback.
  - Real alt text on every screenshot/icon; captions on any video/gif.
  - Keyboard-navigable nav, visible focus states.
  - Plain-language pass over the app's "command console" copy voice — keep
    the aesthetic, don't let jargon block comprehension.

## 5. Phase 3 — Content assembly

- Draft copy per section in Phase 1, grounded only in verified code/help
  text — nothing invented.
- Asset gaps to fill (see decision 3): real screenshots/recordings of each
  deck, the gesture cycle, and watch pairing. Until those exist, use simple
  illustrative diagrams as placeholders rather than blocking on them.
- Draft the status/roadmap section from `HELP_TUTORIAL_GUIDE.md`, marked in
  a code comment as needing a re-check whenever that file changes.

## 6. Phase 4 — Build the static site

- Plain static HTML/CSS + minimal JS — no framework, no build step, so
  GitHub Pages serves it directly.
- v1 shape: one long, semantically-sectioned page with anchor navigation
  (simplest thing that supports 100% coverage without a CMS).
- New `index.html` lands at the repo root once Phase 0's move is confirmed
  and committed separately.
- Preview locally with a plain static server before anything gets pushed.

## 7. Phase 5 — Review & accessibility QA (confirm before merge)

- Screen-reader pass over the whole page.
- Test with OS-level reduced-motion and high-contrast settings on.
- Lighthouse accessibility + performance pass.
- Show you the built page (local preview or screenshots) for sign-off before
  it goes live.
- The old file's move stays its own separate, reviewable commit — a backup
  in git history — before the new page replaces it at the root.

## 8. Phase 6 — Ship

- Enable Pages in repo settings against the chosen source.
- Verify the live URL renders correctly, hand back the link.

---

## Open questions (blocking Phase 0/1 start)

See section 1 above — hosting source, license, screenshot strategy, and
tone for the advanced-sounding features are the four decisions worth
settling before content gets written, since each one changes what gets
built.
