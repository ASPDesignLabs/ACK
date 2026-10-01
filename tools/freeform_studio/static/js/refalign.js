// SPDX-License-Identifier: GPL-3.0-or-later
// Matches what was heard against the text the person was reading, and proposes the reference's wording where the two
// agree closely. It only ever proposes; the person decides. Three promises are built into how a proposal is made:
//   - every word that was spoken stays (a proposal has exactly one word per spoken word, so nothing is dropped);
//   - reference words that were never spoken are never added;
//   - digits and symbols in the reference never replace spoken words ("twenty dollars" stays, "$20" does not come over).
// Pure, so it can be tested on its own.
import { suggestSpoken } from "./spoken.js";

const NEEDS_SPOKEN = /[\d&@#%+=<>/\\_*~^|{}$£€¥°]/;
const LOOKAHEAD = 800;       // how far past the previous match to look first (in words)
// Costs, in tenths of an "edit". A word that is only misspelled is cheap to fix; an unrelated word in the same place costs
// more than keeping what was spoken, so a spoken word is never swapped for a stranger just because the counts tie.
const COST_EXTRA = 10, COST_SKIP = 10, COST_SIMILAR = 6, COST_DIFFERENT = 15;

export const normTok = (t) => t.toLowerCase().replace(/[‘’]/g, "'").replace(/[^\p{L}\p{N}']+/gu, "");

/** The reference split into words, with numbers and symbols expanded into the words they would be spoken as (for matching only). */
export function prepareReference(text) {
  const raw = (text || "").replace(/—/g, " ").split(/\s+/).filter(Boolean);
  const toks = [];
  raw.forEach((r, ref) => {
    if (NEEDS_SPOKEN.test(r)) {
      const options = suggestSpoken(r);
      const words = options.length ? options[0].text.split(/\s+/) : [r];
      for (const w of words) { const norm = normTok(w); if (norm) toks.push({ norm, raw: w, ref, numeric: true }); }
      return;
    }
    const norm = normTok(r);
    if (norm) toks.push({ norm, raw: r, ref, numeric: false });
  });
  const known = new Set(toks.map((t) => t.norm));
  return { raw, toks, known };
}

// Reused between calls: this runs once per cell of the alignment table, so it must not allocate.
const ROW_A = new Int32Array(66), ROW_B = new Int32Array(66);

/** Whether two words are close enough in spelling that one is plausibly a mishearing or misspelling of the other. */
export function similarWords(a, b) {
  if (a === b) return true;
  const m = a.length, n = b.length;
  if (!m || !n || m > 64 || n > 64) return false;
  const k = Math.max(1, Math.floor(Math.max(m, n) * 0.4));
  if (Math.abs(m - n) > k) return false;
  let prev = ROW_A, cur = ROW_B;
  for (let j = 0; j <= n; j++) prev[j] = j;
  for (let i = 1; i <= m; i++) {
    cur[0] = i;
    let rowMin = i;
    const ca = a.charCodeAt(i - 1);
    for (let j = 1; j <= n; j++) {
      let v = prev[j - 1] + (ca === b.charCodeAt(j - 1) ? 0 : 1);
      if (prev[j] + 1 < v) v = prev[j] + 1;
      if (cur[j - 1] + 1 < v) v = cur[j - 1] + 1;
      cur[j] = v;
      if (v < rowMin) rowMin = v;
    }
    if (rowMin > k) return false;           // can only get worse from here
    const t = prev; prev = cur; cur = t;
  }
  return prev[n] <= k;
}

/** How many words were spoken: the number of whitespace-separated words in the text. */
export const spokenWordCount = (text) => (text || "").split(/\s+/).filter(Boolean).length;

// A piece's words for matching. Numbers and symbols are expanded to the words they would be said as, exactly as the
// reference's are, so "$20", "20 dollars" and "twenty dollars" all line up with one another. `k` says which of the
// piece's own words each one came from.
export function pieceTokens(text) {
  const words = (text || "").split(/\s+/).filter(Boolean);
  const toks = [];
  words.forEach((raw, k) => {
    if (NEEDS_SPOKEN.test(raw)) {
      const options = suggestSpoken(raw);
      if (options.length) {
        for (const w of options[0].text.split(/\s+/)) { const norm = normTok(w); if (norm) toks.push({ raw, norm, k, numeric: true }); }
        return;
      }
    }
    toks.push({ raw, norm: normTok(raw), k, numeric: false });
  });
  return { words, toks };
}

// Approximate substring matching (Sellers): the cheapest way to line every spoken word up with some stretch of the
// reference, where a wrong word costs 1, a spoken word that isn't in the reference costs 1, and a reference word that
// wasn't spoken costs 1. The stretch may start and end anywhere.
function alignWindow(toks, ref, lo, hi) {
  const n = toks.length, w = hi - lo, stride = w + 1;
  if (w <= 0) return null;
  const D = new Uint16Array((n + 1) * stride);
  const B = new Uint8Array((n + 1) * stride);     // 1 = matched or replaced, 2 = spoken word not in the reference, 3 = reference word skipped
  for (let i = 1; i <= n; i++) { D[i * stride] = i * COST_EXTRA; B[i * stride] = 2; }
  for (let i = 1; i <= n; i++) {
    const a = toks[i - 1].norm;
    for (let j = 1; j <= w; j++) {
      const b = ref.toks[lo + j - 1].norm;
      const pair = a !== "" && a === b ? 0 : a !== "" && similarWords(a, b) ? COST_SIMILAR : COST_DIFFERENT;
      let cost = D[(i - 1) * stride + j - 1] + pair, from = 1;
      const up = D[(i - 1) * stride + j] + COST_EXTRA;
      if (up < cost) { cost = up; from = 2; }
      const left = D[i * stride + j - 1] + COST_SKIP;
      if (left < cost) { cost = left; from = 3; }
      D[i * stride + j] = cost;
      B[i * stride + j] = from;
    }
  }
  let end = 1;
  for (let j = 1; j <= w; j++) if (D[n * stride + j] < D[n * stride + end]) end = j;
  const cost = D[n * stride + end];
  const ops = [];
  let i = n, j = end;
  while (i > 0) {
    const from = B[i * stride + j];
    if (from === 1) { ops.push({ t: toks[i - 1].norm !== "" && toks[i - 1].norm === ref.toks[lo + j - 1].norm ? "match" : "sub", p: i - 1, r: lo + j - 1 }); i--; j--; }
    else if (from === 2) { ops.push({ t: "extra", p: i - 1 }); i--; }
    else { ops.push({ t: "skip", r: lo + j - 1 }); j--; }
  }
  ops.reverse();
  const matches = ops.filter((o) => o.t === "match").length;
  const span = end - j;
  return { cost, ops, matches, start: lo + j, end: lo + end, similarity: 1 - cost / (10 * Math.max(n, span, 1)) };
}

// Good enough to propose: at least half the spoken words match exactly, and no more than 40% of the work is fixing things.
const acceptable = (m, n, strict) => m && m.matches >= Math.max(2, Math.ceil(n * (strict ? 0.7 : 0.5))) && m.similarity >= (strict ? 0.75 : 0.6);

function suggestionFrom(piece, ref, match) {
  const toks = piece.toks;
  const out = [], marks = [], changes = [];
  const emitted = new Set();         // the piece's own words already written out (a number may stand for several matching words)
  let style = 0, kept = 0;
  for (const op of match.ops) {
    if (op.t === "skip") continue;                                   // never add words that weren't spoken
    const spoken = toks[op.p];
    if (spoken.numeric) {                                             // numbers and symbols stay exactly as they were
      if (!emitted.has(spoken.k)) { emitted.add(spoken.k); out.push(spoken.raw); marks.push("kept"); }
      continue;
    }
    emitted.add(spoken.k);
    if (op.t === "extra") { out.push(spoken.raw); marks.push("kept"); kept++; continue; }
    const r = ref.toks[op.r];
    if (r.numeric) { out.push(spoken.raw); marks.push("kept"); continue; }   // the spoken words stay; digits don't come over
    out.push(r.raw);
    if (op.t === "match") { marks.push(r.raw === spoken.raw ? "same" : "style"); if (r.raw !== spoken.raw) style++; }
    else { marks.push("changed"); changes.push({ from: spoken.raw, to: r.raw, similar: similarWords(spoken.norm, r.norm) }); }
  }
  const text = out.join(" ");
  const current = piece.words.join(" ");
  const kind = text === current ? "same" : changes.length ? "words" : "style";
  return { kind, text, tokens: out, marks, changes, style, kept, similarity: match.similarity, from: ref.toks[match.start].ref, to: ref.toks[match.end - 1].ref };
}

// One piece at a time, so a caller can hand control back to the page between pieces.
function* alignSteps(pieces, referenceText) {
  const ref = prepareReference(referenceText);
  const byId = new Map();
  const stats = { same: 0, style: 0, words: 0, none: 0 };
  if (!ref.toks.length) return { byId, stats: { ...stats, none: pieces.filter((p) => p.status !== "dropped").length }, ref };
  let cursor = 0;
  for (const piece of pieces) {
    yield;
    if (piece.status === "dropped") continue;
    const pt = pieceTokens(piece.text);
    const toks = pt.toks;
    const longWords = toks.filter((t) => t.norm.length >= 4);
    const seen = longWords.filter((t) => ref.known.has(t.norm)).length;
    if (toks.length < 3 || (longWords.length >= 2 && seen < longWords.length * 0.4)) { stats.none++; continue; }   // too short to tell, or clearly not read from the text
    let match = alignWindow(toks, ref, cursor, Math.min(ref.toks.length, cursor + LOOKAHEAD));
    if (!acceptable(match, toks.length, false)) {
      match = alignWindow(toks, ref, 0, ref.toks.length);                // maybe it was read out of order or twice
      if (!acceptable(match, toks.length, true)) { stats.none++; continue; }
    }
    const s = suggestionFrom(pt, ref, match);
    s.basis = piece.text;                                               // the text this proposal was made for
    byId.set(piece.id, s);
    stats[s.kind]++;
    cursor = match.end;
  }
  return { byId, stats, ref };
}

/**
 * Compare every piece with the reference text. `pieces` must be in time order. Returns { byId, stats }:
 * byId maps a piece id to { kind: "same" | "style" | "words", text, tokens, marks, changes, similarity, basis, ... } for the
 * pieces that line up with the reference, and has no entry for the rest (free speech, or too short to tell).
 */
export function alignAll(pieces, referenceText) {
  const run = alignSteps(pieces, referenceText);
  for (;;) { const step = run.next(); if (step.done) return step.value; }
}

/** The same, but gives the page a turn every few milliseconds. Resolves to null if `isCancelled()` becomes true. */
export async function alignAllAsync(pieces, referenceText, isCancelled = () => false) {
  const run = alignSteps(pieces, referenceText);
  let slice = Date.now();
  for (;;) {
    const step = run.next();
    if (step.done) return step.value;
    if (Date.now() - slice > 8) {
      await new Promise((resolve) => setTimeout(resolve, 0));
      if (isCancelled()) return null;
      slice = Date.now();
    }
  }
}

// ---------------------------------------------------------------- hints for the recognizer
const COMMON_STARTS = new Set(["the", "a", "an", "and", "but", "or", "so", "then", "it", "he", "she", "they", "we", "you", "i", "this", "that",
  "there", "what", "when", "where", "who", "why", "how", "if", "in", "on", "at", "for", "with", "as", "is", "was", "are", "be", "my", "your",
  "his", "her", "its", "our", "their", "not", "no", "yes", "one", "all", "some", "now", "here", "after", "before", "because", "while", "to", "of"]);

/** Names and unusual terms from the reference, most useful first, as a comma-separated list that fits `maxChars`. */
export function extractHotwords(referenceText, maxChars = 480) {
  const raw = (referenceText || "").replace(/—/g, " ").split(/\s+/).filter(Boolean);
  const found = new Map();       // word -> { count, first, rank }
  raw.forEach((token, i) => {
    const core = token.replace(/^[^\p{L}\p{N}]+|[^\p{L}\p{N}]+$/gu, "");
    if (core.length < 2 || /\d/.test(core)) return;
    const base = core.replace(/['’].*$/, "");
    const upperStart = /^\p{Lu}/u.test(core);
    const allCaps = core.length >= 2 && core === core.toUpperCase() && /\p{L}/u.test(core);
    const inner = /\p{Ll}.*\p{Lu}/u.test(core);
    if (!upperStart && !inner) return;
    const prev = raw[i - 1] || "";
    const initial = i === 0 || /[.!?…:]["'”’)\]]*$/.test(prev);
    if (!allCaps && !inner && COMMON_STARTS.has(base.toLowerCase())) return;   // "The", "It", "I'm"...
    const rank = allCaps || inner ? 1 : initial ? 2 : 0;       // names in mid-sentence are the strongest signal
    const entry = found.get(core) || { count: 0, first: i, rank };
    entry.count++;
    entry.rank = Math.min(entry.rank, rank);
    found.set(core, entry);
  });
  const sorted = [...found.entries()].sort((a, b) => a[1].rank - b[1].rank || b[1].count - a[1].count || a[1].first - b[1].first);
  let out = "";
  for (const [word] of sorted) {
    const next = out ? `${out}, ${word}` : word;
    if (next.length > maxChars) break;
    out = next;
  }
  return out;
}

/** The start of the reference, cut at a sentence or word boundary, as context for the recognizer. */
export function buildPrompt(referenceText, maxChars = 600) {
  const text = (referenceText || "").replace(/\s+/g, " ").trim();
  if (text.length <= maxChars) return text;
  const cut = text.slice(0, maxChars);
  const stop = Math.max(cut.lastIndexOf(". "), cut.lastIndexOf("? "), cut.lastIndexOf("! "));
  if (stop > maxChars * 0.5) return cut.slice(0, stop + 1);
  const space = cut.lastIndexOf(" ");
  return (space > 0 ? cut.slice(0, space) : cut).trim();
}
