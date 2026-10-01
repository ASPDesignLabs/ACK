// SPDX-License-Identifier: GPL-3.0-or-later
// Pure logic for reshaping pieces: split one in two, join two into one, and find where speech really starts and ends.
// No page code here, so it can be tested on its own.
import { alignEdit, joinWords, recomputeFlags, tokenize } from "./words.js";

const r3 = (x) => Math.round(x * 1000) / 1000;
const SERVER_ONLY_FLAGS = ["possible_hallucination", "repetitive"];   // judged by the recognizer, kept when pieces are joined
export const MIN_PIECE = 0.1;
export const MAX_TEXT = 2000;

/** The next unused piece id, in the form the server accepts (s001 ... s999999). */
export function nextId(pieces) {
  const top = pieces.reduce((m, p) => Math.max(m, Number(String(p.id).slice(1)) || 0), 0);
  return `s${String(top + 1).padStart(3, "0")}`;
}

// The words of a piece, guaranteed to spell out its text. Normally they already do, and are used untouched.
function wordsMatchingText(seg) {
  const words = seg.words || [];
  if (joinWords(words) === seg.text) return words;
  return alignEdit(words, seg.text, { start: seg.start, end: seg.end });
}

/** Where to put a split that goes just before word `i`: in the middle of the pause that precedes it. */
export function boundaryBefore(words, i) {
  const w = words[i];
  const prev = words[i - 1];
  if (!prev) return w.s;
  return r3(prev.e <= w.s ? (prev.e + w.s) / 2 : w.s);
}

/**
 * Cut `seg` at time `t`. Words whose middle falls before `t` stay in the first piece, the rest go to the second.
 * Both come back as "to review" (their content changed). Returns { first, second } or { error }.
 */
export function splitPiece(seg, t, newId) {
  if (!(t >= seg.start + MIN_PIECE && t <= seg.end - MIN_PIECE)) {
    return { error: "A piece can't be split that close to its edge. Place the marker further inside." };
  }
  const words = wordsMatchingText(seg);
  const left = words.filter((w) => (w.s + w.e) / 2 < t);
  const right = words.filter((w) => (w.s + w.e) / 2 >= t);
  const make = (id, start, end, ws) => {
    const part = { ...seg, id, start: r3(start), end: r3(end), words: ws.map((w) => ({ ...w })), text: joinWords(ws),
                   status: "pending", tags: [...seg.tags], note: "", auto: null };
    part.flags = recomputeFlags({ ...part, flags: (seg.flags || []).filter((f) => SERVER_ONLY_FLAGS.includes(f)) });
    return part;
  };
  return { first: make(seg.id, seg.start, t, left), second: make(newId, t, seg.end, right) };
}

/** Join `a` with the piece after it. The pause between them becomes part of the clip. Returns { merged } or { error }. */
export function mergePieces(a, b) {
  const wa = wordsMatchingText(a), wb = wordsMatchingText(b);
  const words = [...wa, ...wb].map((w) => ({ ...w }));
  const text = joinWords(words);
  if (text.length > MAX_TEXT) return { error: "These two are too long to join into one piece." };
  const merged = {
    ...a, end: b.end, words, text, status: "pending", auto: null,
    tags: [...new Set([...a.tags, ...b.tags])].sort(),
    note: [a.note, b.note].filter(Boolean).join(" / ").slice(0, 500),
  };
  const keep = [...(a.flags || []), ...(b.flags || [])].filter((f) => SERVER_ONLY_FLAGS.includes(f));
  merged.flags = recomputeFlags({ ...merged, flags: keep });
  return { merged, gap: Math.max(0, r3(b.start - a.end)) };
}

// ---------------------------------------------------------------- finding where the speech really is
/** Loudness (0-128) of each stored peak between times a and b. `peaks` is { spp, rate, data: Int8Array of min,max pairs }. */
export function ampsBetween(peaks, a, b) {
  const per = peaks.spp / peaks.rate;
  const n = peaks.data.length >> 1;
  const i0 = Math.max(0, Math.floor(a / per));
  const i1 = Math.min(n, Math.ceil(b / per));
  const values = [];
  for (let i = i0; i < i1; i++) values.push(Math.max(Math.abs(peaks.data[2 * i]), Math.abs(peaks.data[2 * i + 1])));
  return { t0: i0 * per, dt: per, values };
}

/**
 * Tighten a piece to the speech inside it, leaving `pad` seconds of room on each side. It only ever shrinks a piece,
 * and never closer than `wordMargin` to a recognized word, so it can't cut speech off. Returns { start, end } or null
 * when there is nothing worth changing.
 */
export function trimToSpeech(seg, peaks, { pad = 0.12, wordMargin = 0.05, floor = 3, minLen = 0.3, worthIt = 0.03 } = {}) {
  const { t0, dt, values } = ampsBetween(peaks, seg.start, seg.end);
  if (!values.length) return null;
  // Speech is anything well above the room's noise, but never judged against a noise level so high that quiet speech
  // vanishes: the threshold is capped relative to the loudest moment, so a piece that is mostly speech still works.
  const sorted = [...values].sort((x, y) => x - y);
  const loud = sorted[sorted.length - 1];
  const noise = sorted[Math.floor(sorted.length * 0.05)];
  const thr = Math.max(floor, loud * 0.06, Math.min(noise * 3, loud * 0.15));
  const first = values.findIndex((v) => v >= thr);
  if (first < 0) return null;
  let last = values.length - 1;
  while (last > first && values[last] < thr) last--;
  let start = t0 + first * dt - pad;
  let end = t0 + (last + 1) * dt + pad;
  const words = seg.words || [];
  if (words.length) {
    start = Math.min(start, words[0].s - wordMargin);
    end = Math.max(end, words[words.length - 1].e + wordMargin);
  }
  start = Math.max(seg.start, start);
  end = Math.min(seg.end, end);
  if (end - start < minLen) return null;
  if (start - seg.start < worthIt && seg.end - end < worthIt) return null;
  return { start: r3(start), end: r3(end) };
}

export { tokenize };
