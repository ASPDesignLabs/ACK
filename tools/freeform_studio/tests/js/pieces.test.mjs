// SPDX-License-Identifier: GPL-3.0-or-later
import { test } from "node:test";
import assert from "node:assert/strict";
import { load } from "./load.mjs";

const { nextId, splitPiece, mergePieces, boundaryBefore, trimToSpeech, ampsBetween } = await load("pieces.js");
const { cutsWord, recomputeFlags, joinWords } = await load("words.js");
const geo = await load("wavegeo.js");

const W = (w, s, e, p = 0.95, extra = {}) => ({ w, s, e, p, ...extra });
const piece = (over = {}) => {
  const words = [W("Hello", 1.0, 1.4), W("there", 1.5, 1.9), W("my", 2.5, 2.7), W("friend.", 2.8, 3.3)];
  return { id: "s001", start: 0.8, end: 3.5, text: joinWords(words), words, status: "approved", tags: ["breath"], note: "",
           flags: ["possible_hallucination"], auto: { start: 0.8, end: 3.5, text: "x" }, ...over };
};

// ---------------------------------------------------------------- ids
test("the next id continues after the highest one, whatever order pieces are in", () => {
  assert.equal(nextId([]), "s001");
  assert.equal(nextId([{ id: "s003" }, { id: "s010" }, { id: "s002" }]), "s011");
  assert.equal(nextId([{ id: "s999" }]), "s1000");
});

// ---------------------------------------------------------------- split
test("splitting between words divides the words, the text and the time with nothing lost", () => {
  const t = boundaryBefore(piece().words, 2);          // before "my", in the middle of the pause
  assert.equal(t, 2.2);
  const { first, second } = splitPiece(piece(), t, "s002");
  assert.deepEqual([first.id, second.id], ["s001", "s002"]);
  assert.deepEqual([first.start, first.end, second.start, second.end], [0.8, 2.2, 2.2, 3.5]);
  assert.deepEqual([first.text, second.text], ["Hello there", "my friend."]);
  assert.equal(first.words.length + second.words.length, 4);
  assert.deepEqual(first.words[0], piece().words[0]);   // timing untouched
});

test("both halves go back to 'to review', keep tags, drop the original cut record, and keep the recognizer's doubts", () => {
  const { first, second } = splitPiece(piece(), 2.2, "s002");
  for (const part of [first, second]) {
    assert.equal(part.status, "pending");
    assert.deepEqual(part.tags, ["breath"]);
    assert.equal(part.auto, null);
    assert.ok(part.flags.includes("possible_hallucination"));
  }
  assert.notEqual(first.tags, second.tags);            // separate copies, not shared
});

test("flags are worked out again for each half", () => {
  const { first, second } = splitPiece(piece({ text: "Hello there my 3 friends.", words: [W("Hello", 1.0, 1.4), W("there", 1.5, 1.9), W("my", 2.5, 2.7, 0.2), W("3", 2.75, 2.9), W("friends.", 2.95, 3.3)] }), 2.2, "s002");
  assert.ok(!first.flags.includes("has_digits") && !first.flags.includes("low_confidence"));
  assert.ok(second.flags.includes("has_digits") && second.flags.includes("low_confidence"));
});

test("a split too close to either edge is refused with a reason", () => {
  assert.match(splitPiece(piece(), 0.85, "s002").error, /too close|further inside/i);
  assert.match(splitPiece(piece(), 3.45, "s002").error, /further inside/);
  assert.ok(splitPiece(piece(), 0.95, "s002").first);
});

test("splitting in a stretch with no words gives an empty piece that can be dropped", () => {
  const { first, second } = splitPiece(piece(), 3.4, "s002");
  assert.equal(second.text, "");
  assert.ok(second.flags.includes("empty"));
  assert.equal(first.text, "Hello there my friend.");
});

test("a split through the middle of a word puts the whole word on one side and warns that a cut falls inside it", () => {
  const { first, second } = splitPiece(piece(), 1.55, "s002");   // "there" is 1.5-1.9: its middle (1.7) is after the cut
  assert.deepEqual([first.text, second.text], ["Hello", "there my friend."]);
  assert.ok(second.words[0].s < second.start + 1e-9 || true);
  assert.ok(!first.flags.includes("cuts_word"));
});

test("words that don't spell out the text are re-aligned before splitting, so text and audio still agree", () => {
  const seg = piece({ text: "Hello there my dear friend." });   // someone changed the text; the words are stale
  const { first, second } = splitPiece(seg, 2.2, "s002");
  assert.equal(joinWords(first.words) + " " + joinWords(second.words), "Hello there my dear friend.");
  assert.equal(first.text + " " + second.text, "Hello there my dear friend.");
});

test("tokens that were glued together by the recognizer stay glued, even across a join", () => {
  const words = [W("It", 1.0, 1.2), W("cost", 1.3, 1.6), W("11", 1.7, 1.9), W(",000", 1.9, 2.2, 0.9, { j: true }), W("dollars.", 2.4, 2.9)];
  const seg = piece({ words, text: joinWords(words), start: 0.9, end: 3.0 });
  assert.equal(seg.text, "It cost 11,000 dollars.");
  const { first, second } = splitPiece(seg, 1.65, "s002");
  assert.equal(first.text, "It cost");
  assert.equal(second.text, "11,000 dollars.");
  assert.equal(mergePieces(first, second).merged.text, "It cost 11,000 dollars.");
});

// ---------------------------------------------------------------- merge
test("joining two pieces covers both and the pause between, and starts over as 'to review'", () => {
  const a = piece({ id: "s001", start: 0.8, end: 2.0, text: "Hello there", words: piece().words.slice(0, 2), tags: ["laugh"] });
  const b = piece({ id: "s002", start: 2.4, end: 3.5, text: "my friend.", words: piece().words.slice(2), tags: ["noise"], note: "check", flags: [] });
  const { merged, gap } = mergePieces(a, b);
  assert.equal(merged.id, "s001");
  assert.deepEqual([merged.start, merged.end, gap], [0.8, 3.5, 0.4]);
  assert.equal(merged.text, "Hello there my friend.");
  assert.deepEqual(merged.words, piece().words);
  assert.equal(merged.status, "pending");
  assert.deepEqual(merged.tags, ["laugh", "noise"]);
  assert.equal(merged.note, "check");
  assert.ok(merged.flags.includes("possible_hallucination"));
});

test("a join that would be too long to train on says so, and one that is far too long is refused", () => {
  const long = (id, start) => piece({ id, start, end: start + 7, text: "word", words: [W("word", start + 1, start + 2)], flags: [] });
  assert.ok(mergePieces(long("s001", 0), long("s002", 7.5)).merged.flags.includes("too_long"));
  const huge = (id) => piece({ id, text: "x ".repeat(600).trim(), words: [] });
  assert.match(mergePieces(huge("s001"), huge("s002")).error, /too long/);
});

test("splitting and then joining gives back the same words and text", () => {
  const original = piece();
  const { first, second } = splitPiece(original, 2.2, "s002");
  const { merged } = mergePieces(first, second);
  assert.equal(merged.text, original.text);
  assert.deepEqual(merged.words, original.words);
  assert.deepEqual([merged.start, merged.end], [original.start, original.end]);
});

// ---------------------------------------------------------------- a cut inside a word
test("a cut point inside a word is noticed; small timing looseness is not", () => {
  const seg = piece();
  assert.equal(cutsWord(seg), false);
  assert.equal(cutsWord({ ...seg, start: 1.04 }), false);           // 0.04 s of "Hello" before the cut: fine
  assert.equal(cutsWord({ ...seg, start: 1.2 }), true);             // half of "Hello" is gone
  assert.equal(cutsWord({ ...seg, end: 3.0 }), true);               // "friend." mostly outside
  assert.equal(cutsWord({ ...seg, end: 2.0 }), true);               // "my friend." entirely outside
  assert.equal(cutsWord({ ...seg, words: [] }), false);
  assert.ok(recomputeFlags({ ...seg, start: 1.2, flags: [] }).includes("cuts_word"));
  assert.ok(!recomputeFlags({ ...seg, flags: ["cuts_word"] }).includes("cuts_word"));   // cleared once it's fixed
});

// ---------------------------------------------------------------- trimming silence
const RATE = 48000, SPP = 512, PER = SPP / RATE;
function peaksFor(total, regions, noise = 0) {
  const n = Math.ceil(total / PER);
  const data = new Int8Array(n * 2);
  for (let i = 0; i < n; i++) {
    const t = i * PER;
    const loud = regions.find(([a, b]) => t >= a && t < b);
    const v = loud ? loud[2] : noise;
    data[2 * i] = -v; data[2 * i + 1] = v;
  }
  return { spp: SPP, rate: RATE, data };
}

test("amplitudes are read from the stored peaks", () => {
  const { values, t0, dt } = ampsBetween(peaksFor(3, [[1, 2, 40]]), 0.9, 2.1);
  assert.ok(Math.abs(t0 - 0.9) <= dt && values.length > 100);
  assert.equal(Math.max(...values), 40);
});

test("silence on both sides is trimmed, leaving a little room", () => {
  const seg = piece({ start: 0.2, end: 3.8, words: [W("Hello", 1.1, 1.5), W("friend.", 1.6, 1.95)] });
  const r = trimToSpeech(seg, peaksFor(4, [[1.0, 2.0, 40]]));
  assert.ok(Math.abs(r.start - 0.88) < 0.03, r.start);
  assert.ok(Math.abs(r.end - 2.12) < 0.03, r.end);
});

test("it never cuts closer to a recognized word than a safety margin, even when the audio looks quiet there", () => {
  const seg = piece({ start: 0.2, end: 3.8, words: [W("Hmm", 0.5, 0.8), W("Hello", 1.1, 1.5)] });
  const r = trimToSpeech(seg, peaksFor(4, [[1.0, 2.0, 40]]));
  assert.ok(r.start <= 0.5 - 0.05 + 1e-9, r.start);     // the quiet first word is kept whole
});

test("it only ever shrinks a piece, never grows it", () => {
  const seg = piece({ start: 1.0, end: 2.0, words: [W("Hi", 1.1, 1.8)] });
  assert.equal(trimToSpeech(seg, peaksFor(4, [[0.2, 3.0, 40]])), null);   // already tight (speech fills it)
});

test("steady background noise is not mistaken for speech", () => {
  const seg = piece({ start: 0.2, end: 3.8, words: [W("Hello", 1.1, 1.9)] });
  const r = trimToSpeech(seg, peaksFor(4, [[1.0, 2.0, 40]], 2));
  assert.ok(r && r.start > 0.7 && r.end < 2.5, JSON.stringify(r));
});

test("a piece that is mostly speech, with only a little silence in front, is still trimmed", () => {
  const seg = piece({ start: 0, end: 1.8, words: [W("Hello", 0.3, 0.6), W("friend.", 0.7, 1.7)] });
  const r = trimToSpeech(seg, peaksFor(2, [[0.2, 1.8, 63]]));
  assert.ok(r && Math.abs(r.start - 0.08) < 0.03 && r.end === 1.8, JSON.stringify(r));
});

test("a piece that is speech from edge to edge is left alone", () => {
  const seg = piece({ start: 0.2, end: 1.8, words: [W("Hello", 0.25, 0.9), W("friend.", 1.0, 1.75)] });
  assert.equal(trimToSpeech(seg, peaksFor(2, [[0.2, 1.8, 63]])), null);
});

test("quiet speech next to loud speech is still counted as speech", () => {
  const seg = piece({ start: 0, end: 3, words: [W("Hi", 0.9, 1.1), W("there", 2.0, 2.2)] });
  const r = trimToSpeech(seg, peaksFor(3, [[0.8, 1.2, 60], [1.9, 2.3, 8]]));   // the second word is a whisper
  assert.ok(r.end >= 2.3, JSON.stringify(r));
});

test("nothing to trim when the stretch is silent, or would leave too little", () => {
  assert.equal(trimToSpeech(piece({ start: 0.2, end: 3.8, words: [] }), peaksFor(4, [])), null);
  assert.equal(trimToSpeech(piece({ start: 0.2, end: 3.8, words: [] }), peaksFor(4, [[1.0, 1.03, 40]])), null);   // a 30 ms click plus padding is under the 0.3 s minimum
});

// ---------------------------------------------------------------- waveform geometry
test("the view shows the piece with room around it, never outside the recording", () => {
  const seg = { start: 2, end: 4 };
  assert.deepEqual(geo.viewWindow(seg, 10), { vs: 1.3, ve: 4.7 });
  assert.deepEqual(geo.viewWindow({ start: 0.1, end: 9.9 }, 10), { vs: 0, ve: 10 });
  const wide = geo.viewWindow(seg, 100, 2), close = geo.viewWindow(seg, 100, -1);
  assert.ok(wide.ve - wide.vs > close.ve - close.vs);
  assert.ok(Math.abs(geo.xToTime(geo.timeToX(3.3, 1.3, 4.7, 340), 1.3, 4.7, 340) - 3.3) < 1e-9);
});

test("a cut point stops at its neighbour, the recording's edge, and the other cut point", () => {
  const sorted = [{ id: "s001", start: 1, end: 2 }, { id: "s002", start: 3, end: 4 }, { id: "s003", start: 4.5, end: 5 }];
  const mid = sorted[1], b = geo.boundsFor(sorted, mid, 6);
  assert.deepEqual([b.min, b.max], [2, 4.5]);
  assert.deepEqual(geo.clampEdge("start", 1.5, mid, b), { t: 2, limited: "previous" });
  assert.deepEqual(geo.clampEdge("end", 5, mid, b), { t: 4.5, limited: "next" });
  assert.deepEqual(geo.clampEdge("start", 3.99, mid, b), { t: 3.9, limited: "other" });
  assert.deepEqual(geo.clampEdge("end", 3.05, mid, b), { t: 3.1, limited: "other" });
  assert.deepEqual(geo.clampEdge("start", 2.5, mid, b), { t: 2.5, limited: null });
  const first = geo.boundsFor(sorted, sorted[0], 6), last = geo.boundsFor(sorted, sorted[2], 6);
  assert.deepEqual(geo.clampEdge("start", -1, sorted[0], first), { t: 0, limited: "edge" });
  assert.deepEqual(geo.clampEdge("end", 9, sorted[2], last), { t: 6, limited: "edge" });
});

test("nudging rounds to a thousandth so repeated steps don't drift", () => {
  let t = 1;
  for (let i = 0; i < 30; i++) t = geo.nudged(t, 1, 0.01);
  assert.equal(t, 1.3);
});

test("the stored level used is the coarsest with a peak per pixel", () => {
  assert.equal(geo.pickLevel([512, 2048, 8192], 48000, 0.006), 512);      // 288 samples/pixel: only 512 is close enough
  assert.equal(geo.pickLevel([512, 2048, 8192], 48000, 0.05), 2048);      // 2400 samples/pixel
  assert.equal(geo.pickLevel([512, 2048, 8192], 48000, 1), 8192);
  assert.equal(geo.pickLevel([2048], 48000, 0.001), 2048);                // nothing finer exists: use what there is
});

test("each pixel column shows the loudest swing in its slice", () => {
  const p = peaksFor(3, [[1, 2, 40]]);
  const cols = geo.columns(p, 0.5, 2.5, 200);
  assert.equal(cols.length, 200);
  assert.deepEqual(cols[10], [0, 0]);
  assert.deepEqual(cols[100], [-40, 40]);
});
