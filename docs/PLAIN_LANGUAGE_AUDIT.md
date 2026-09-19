# Plain-Terms Audit — `index.html`

A working checklist, not a finished document. `index.html` already carries
a labeled "In Plain Terms" box alongside nearly every flavorful section —
this audits that existing pattern for coverage gaps, rather than proposing
a new one. It's meant to be worked through and checked off, then archived
or deleted once the gaps below are closed.

Companion to `docs/PLAIN_LANGUAGE_GUIDE.md` (the standalone plain-language
guide) — that document is the portable deliverable; this one is just the
punch list for finishing the in-page pattern that already exists.

## Method

Every `<h2>`/`<h3>` section in `index.html` was checked for a
`class="plain-terms"` box in the same section. Findings below are grouped
by status.

## Coverage: sections with an existing "In Plain Terms" box

No action needed — listed for completeness / to confirm nothing was missed
on a future pass.

- Hero / home (situational mutism framing)
- How it works → Tap controls
- How it works → Gesture playback
- How it works → Full-screen output
- Decks (overview)
- MATRIX Deck
- Quick Actions Deck
- Emergency Deck
- Emoji Deck
- GIF Deck
- Manual Override
- Target Computer
- Audio Architect
- Variables & Root Overrides
- Training Ground
- Deck Trainer
- Pairing & Sync (Wear OS companion)
- Shake Kill Switch
- Shaky-Hands Mode
- "A way out before it fires"
- REPLAY
- Help/onboarding intro
- Your Data, Your Rules
- Terminal
- Deck Simulator (try-it-in-browser section)

## Gap 1: Geo-Protocol / Tactical Grid — no plain-language coverage at all

**Status: confirmed gap.**

Unlike every other feature above, Geo-Protocol has no dedicated
user-facing section on `index.html` and no "In Plain Terms" box anywhere.
It's currently mentioned exactly once, in the developer-facing "Build
requirements" section, as a build/setup detail (importing a `.map` file) —
not as a feature a visitor would learn about at all.

It is a real, user-facing feature: the in-app help system
(`GeoProtocolHelp.kt`) describes it as "location-based context and zone
behavior," with its own help module, category, and steps. A first draft of
plain-language wording for it now lives in
`docs/PLAIN_LANGUAGE_GUIDE.md`, but it hasn't been added to `index.html`
itself.

**Suggested next step (not yet done, needs your go-ahead first per
STYLEGUIDE.md's rule against rewriting your own copy unprompted):** add a
proper feature section for Geo-Protocol under the Decks/Comms area of
`index.html`, with its own "In Plain Terms" box, matching the pattern used
for every other feature. This would need your own words for the
non-plain-terms description, the same way every other feature section
carries your voice — I'd only draft the plain-terms half, or a starting
point for you to rewrite.

## Gap 2: "PROTOCOL" — used repeatedly, never itself defined

**Status: confirmed gap, smaller scope.**

The settings/options menu name "PROTOCOL" is used as a navigation
instruction in at least three places ("Configure sensitivity... under
PROTOCOL from any deck," "toggle 'Silent Mode' under PROTOCOL from any
deck," "configured from any deck under PROTOCOL") — but none of the
existing "In Plain Terms" boxes near those mentions ever say what PROTOCOL
itself *is* (a menu? a screen? reached how?). A reader unfamiliar with the
app has no box that resolves this term specifically, even though the
surrounding feature (Silent Mode, Shake Kill Switch, Shaky-Hands Mode) is
otherwise well explained.

**Suggested next step:** either fold one sentence defining PROTOCOL into
the first "In Plain Terms" box that references it (How it works → Full-
screen output, where Silent Mode is first mentioned), or give it a short
standalone mention. Small fix, low effort.

## Gap 3: ARM / LOCK POSE / MODIFY / FIRE — the sequence is explained, the individual words aren't

**Status: partial gap.**

The "Gesture playback" Plain Terms box explains *why* the watch gesture
system exists and roughly how it behaves, but doesn't walk through what
each of the four words (ARM, LOCK POSE, MODIFY, FIRE) individually means.
Someone who only glimpses one of these words on a watch screen — not the
whole flow, not the surrounding explanation — has nothing that maps that
single word back to what's happening. This matters most for "FIRE"
specifically, given how it reads out of context.

**Suggested next step:** a short addition to the existing Gesture playback
Plain Terms box (or a small inline aside near the `ARM → LOCK POSE →
MODIFY → FIRE` diagram itself) that names each step in one clause. Draft
wording for this already exists in `docs/PLAIN_LANGUAGE_GUIDE.md` under
"ARM → LOCK POSE → MODIFY → FIRE" and can be adapted back into the site's
existing first-person voice rather than copied verbatim (that draft is
deliberately neutral-toned for a different audience — see that document's
own tone note).

## Not a gap, but worth a look

- **DUST WARNING** (the work-in-progress status banner on the hero
  section) is project-status messaging, not app-feature jargon a reader
  would encounter on a phone/watch screen — left out of the plain-language
  guide's glossary for that reason. Flagging here only so it's a deliberate
  omission, not a missed one.

## Out of scope for this audit

- Whether `index.html` itself should host a portable/standalone version of
  the plain-language guide (a shareable URL, a printable page) is a
  separate decision the project owner already deferred for a later round.
- Any rewriting of existing "In Plain Terms" boxes that are already
  present and accurate — this audit only looks for gaps, not quality
  issues, in existing coverage.
