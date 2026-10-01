import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

// words.js is plain ES module code with no imports; load it from a data: URL so no package.json is needed.
const src = readFileSync(join(dirname(fileURLToPath(import.meta.url)), "../../static/js/words.js"), "utf8");
const { alignEdit, merge3, joinWords, norm, tokenize } = await import("data:text/javascript;base64," + Buffer.from(src).toString("base64"));

const W = (w, s, e, p = 0.95, extra = {}) => ({ w, s, e, p, ...extra });
const base = () => [W("The", 1.0, 1.3), W("archive", 1.3, 1.9, 0.4), W("keeper", 1.9, 2.4), W("cataloged", 2.4, 3.1), W("everything.", 3.1, 4.0)];
const ordered = (ws) => ws.every((w, i) => w.s < w.e && (i === 0 || ws[i - 1].e <= w.s + 1e-9));

test("unchanged text keeps every word's timing and marks nothing as edited", () => {
  const out = alignEdit(base(), "The archive keeper cataloged everything.");
  assert.deepEqual(out, base());
});

test("replacing one word keeps the time slot, becomes confident, and leaves neighbours alone", () => {
  const out = alignEdit(base(), "The archivist keeper cataloged everything.");
  assert.deepEqual(out[1], { w: "archivist", s: 1.3, e: 1.9, p: 1, ed: true });
  assert.deepEqual([out[0], out[2], out[3], out[4]], [base()[0], base()[2], base()[3], base()[4]]);
});

test("replacing one word with two shares the old time in proportion to length", () => {
  const out = alignEdit(base(), "The arch ive keeper cataloged everything.");
  assert.equal(out.length, 6);
  assert.ok(ordered(out));
  assert.equal(out[1].s, 1.3);
  assert.ok(Math.abs(out[2].e - 1.9) < 0.002);
  assert.ok(out[1].ed && out[2].ed && out[1].p === 1);
});

test("an inserted word fits in the gap without moving the others", () => {
  const w = [W("one", 1.0, 1.4), W("three", 2.0, 2.5)];
  const out = alignEdit(w, "one two three");
  assert.equal(out.length, 3);
  assert.ok(ordered(out));
  assert.deepEqual(out[0], w[0]);
  assert.deepEqual(out[2], w[1]);
  assert.ok(out[1].s >= 1.4 - 1e-9 && out[1].e <= 2.0 + 1e-9 && out[1].ed);
});

test("inserting where there is no gap still gives a valid, ordered result", () => {
  const w = [W("a", 1.0, 1.5), W("c", 1.5, 2.0)];
  const out = alignEdit(w, "a b c");
  assert.ok(ordered(out));
  assert.equal(out.length, 3);
});

test("deleting a word drops it and keeps the rest exactly", () => {
  const out = alignEdit(base(), "The keeper cataloged everything.");
  assert.deepEqual(out, [base()[0], base()[2], base()[3], base()[4]]);
});

test("a punctuation or case change keeps timing and confidence but notes the touch", () => {
  const out = alignEdit(base(), "The Archive keeper cataloged everything!");
  assert.deepEqual(out[1], { w: "Archive", s: 1.3, e: 1.9, p: 0.4, ed: true });
  assert.deepEqual(out[4], { w: "everything!", s: 3.1, e: 4.0, p: 0.95, ed: true });
});

test("retyping everything spreads the new words over the original span", () => {
  const out = alignEdit(base(), "Completely different sentence now");
  assert.equal(out.length, 4);
  assert.ok(ordered(out));
  assert.equal(out[0].s, 1.0);
  assert.ok(Math.abs(out[3].e - 4.0) < 0.002);
  assert.ok(out.every((w) => w.ed && w.p === 1));
});

test("empty text gives no words; no old words falls back to the span", () => {
  assert.deepEqual(alignEdit(base(), "   "), []);
  const out = alignEdit([], "hello there friend", { start: 2, end: 5 });
  assert.equal(out.length, 3);
  assert.ok(ordered(out) && out[0].s === 2 && Math.abs(out[2].e - 5) < 0.002);
});

test("results always stay ordered and inside the span, for many random edits", () => {
  let seed = 7;
  const rnd = () => (seed = (seed * 1664525 + 1013904223) % 4294967296) / 4294967296;
  const vocab = ["alpha", "beta", "gamma", "delta", "eps", "zeta", "eta", "theta"];
  for (let trial = 0; trial < 300; trial++) {
    const n = 1 + Math.floor(rnd() * 12);
    let t = 1;
    const old = Array.from({ length: n }, (_, i) => { const d = 0.1 + rnd() * 0.6; const w = W(vocab[Math.floor(rnd() * vocab.length)], t, t + d); t += d + rnd() * 0.3; return w; });
    const words = old.map((w) => w.w);
    const edits = Math.floor(rnd() * 4);
    for (let k = 0; k < edits; k++) {
      const at = Math.floor(rnd() * (words.length + 1));
      const op = rnd();
      if (op < 0.4) words.splice(at, 0, vocab[Math.floor(rnd() * vocab.length)] + "x");
      else if (op < 0.7 && words.length > 1) words.splice(Math.min(at, words.length - 1), 1);
      else if (words.length) words[Math.min(at, words.length - 1)] = "new" + k;
    }
    const span = { start: 0.5, end: t + 0.5 };
    const out = alignEdit(old, words.join(" "), span);
    assert.equal(out.length, words.length, `trial ${trial}`);
    assert.ok(ordered(out), `trial ${trial}: ${JSON.stringify(out)}`);
    assert.ok(out.every((w) => w.s >= span.start - 1e-9 && w.e <= span.end + 1e-9 + 0.05), `trial ${trial} span`);
  }
});

test("joinWords honours the no-space markers and tokenize/norm behave", () => {
  assert.equal(joinWords([W("cataloged", 0, 1), W("11", 1, 2), W(",000", 2, 3, 1, { j: true }), W("testimonies", 3, 4)]), "cataloged 11,000 testimonies");
  assert.deepEqual(tokenize("  a  b\n c "), ["a", "b", "c"]);
  assert.equal(norm("Kenobi,"), "kenobi");
  assert.equal(norm("don't"), "don't");
  assert.equal(norm("--"), "--");
});

// ---------------------------------------------------------------- merge3
const S = (id, start, text, extra = {}) => ({ id, start, end: start + 2, text, status: "pending", tags: [], note: "", words: [], ...extra });
const baseDoc = () => [S("s001", 0, "one"), S("s002", 3, "two"), S("s003", 6, "three")];

test("edits to different pieces on two devices are both kept", () => {
  const mine = baseDoc(); mine[0].text = "ONE";
  const theirs = baseDoc(); theirs[1].status = "approved";
  const { segments, conflicts } = merge3(baseDoc(), mine, theirs);
  assert.deepEqual(conflicts, []);
  assert.equal(segments[0].text, "ONE");
  assert.equal(segments[1].status, "approved");
  assert.equal(segments[2].text, "three");
});

test("the same piece changed differently: mine wins and it is reported", () => {
  const mine = baseDoc(); mine[1].text = "mine";
  const theirs = baseDoc(); theirs[1].text = "theirs";
  const { segments, conflicts } = merge3(baseDoc(), mine, theirs);
  assert.deepEqual(conflicts, ["s002"]);
  assert.equal(segments[1].text, "mine");
});

test("the same change on both sides is not a conflict", () => {
  const mine = baseDoc(); mine[2].status = "dropped";
  const theirs = baseDoc(); theirs[2].status = "dropped";
  assert.deepEqual(merge3(baseDoc(), mine, theirs).conflicts, []);
});

test("only they changed it: theirs; only I changed it: mine", () => {
  const theirs = baseDoc(); theirs[0].text = "theirs";
  assert.equal(merge3(baseDoc(), baseDoc(), theirs).segments[0].text, "theirs");
  const mine = baseDoc(); mine[0].text = "mine";
  assert.equal(merge3(baseDoc(), mine, baseDoc()).segments[0].text, "mine");
});

test("pieces added or removed elsewhere are carried through, in time order", () => {
  const theirs = baseDoc().filter((s) => s.id !== "s002"); theirs.push(S("s004", 1.5, "added"));
  const mine = baseDoc(); mine[2].text = "THREE";
  const { segments, conflicts } = merge3(baseDoc(), mine, theirs);
  assert.deepEqual(segments.map((s) => s.id), ["s001", "s004", "s003"]);
  assert.equal(segments[2].text, "THREE");
  assert.deepEqual(conflicts, []);
});

test("tags, notes and word lists count as changes too", () => {
  const mine = baseDoc(); mine[0].tags = ["laugh"];
  const theirs = baseDoc(); theirs[0].note = "check at 0:03";
  const { conflicts, segments } = merge3(baseDoc(), mine, theirs);
  assert.deepEqual(conflicts, ["s001"]);              // both touched the same piece in different fields: flagged
  assert.deepEqual(segments[0].tags, ["laugh"]);
});

// ---------------------------------------------------------------- recomputeFlags
const { recomputeFlags } = await import("data:text/javascript;base64," + Buffer.from(src).toString("base64"));

test("flags follow the text: fixing a shaky word clears low_confidence, typing a number adds has_digits", () => {
  const seg = { start: 0, end: 4, text: "Kenobi was here.", flags: ["low_confidence", "possible_hallucination"],
                words: [W("Kenobi", 0, 1, 0.3), W("was", 1, 2), W("here.", 2, 3)] };
  assert.deepEqual(recomputeFlags(seg), ["low_confidence", "possible_hallucination"]);
  const fixed = { ...seg, words: [W("Kenobi", 0, 1, 1, { ed: true }), W("was", 1, 2), W("here.", 2, 3)] };
  assert.deepEqual(recomputeFlags(fixed), ["possible_hallucination"]);  // not text-derived: left for a person to judge
  assert.deepEqual(recomputeFlags({ ...fixed, text: "Kenobi was here 3 times [laughs] & more" }),
    ["possible_hallucination", "has_digits", "bracket_tag", "has_symbols"].sort((a, b) => ["possible_hallucination", "has_digits", "bracket_tag", "has_symbols"].indexOf(a) - ["possible_hallucination", "has_digits", "bracket_tag", "has_symbols"].indexOf(b)));
});

test("length and emptiness flags track the piece", () => {
  assert.deepEqual(recomputeFlags({ start: 0, end: 0.5, text: "Hi.", flags: [], words: [] }), ["too_short"]);
  assert.deepEqual(recomputeFlags({ start: 0, end: 13, text: "Hi.", flags: [], words: [] }), ["too_long"]);
  assert.deepEqual(recomputeFlags({ start: 0, end: 3, text: "  ", flags: [], words: [] }), ["empty"]);
  assert.deepEqual(recomputeFlags({ start: 0, end: 3, text: "Fine.", flags: ["too_short", "empty"], words: [] }), []);
});
