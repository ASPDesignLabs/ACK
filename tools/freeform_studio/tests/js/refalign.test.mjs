import { test } from "node:test";
import assert from "node:assert/strict";
import { load } from "./load.mjs";

const refalign = await load("refalign.js");
const { alignAll, prepareReference, pieceTokens, spokenWordCount, extractHotwords, buildPrompt, normTok } = refalign;

const piece = (id, text, status = "pending") => ({ id, text, status });
const one = (text, reference) => alignAll([piece("s001", text)], reference).byId.get("s001");

// ---------------------------------------------------------------- what a proposal looks like
test("a read sentence gets the reference's capitals and punctuation, and says so", () => {
  const s = one("hello there my friend", "Hello there, my friend. I paid twenty dollars for it.");
  assert.equal(s.kind, "style");
  assert.equal(s.text, "Hello there, my friend.");
  assert.deepEqual(s.changes, []);
  assert.deepEqual(s.marks, ["style", "style", "same", "style"]);
});

test("spelling closeness: mishearings count as similar, strangers do not", () => {
  const { similarWords } = refalign;
  for (const [a, b] of [["archive", "archivist"], ["anakin", "annikin"], ["color", "colour"], ["hello", "helo"], ["their", "there"], ["same", "same"]]) assert.ok(similarWords(a, b), `${a} ${b}`);
  for (const [a, b] of [["the", "dusty"], ["big", "large"], ["cat", "dog"], ["", "x"], ["x", ""]]) assert.ok(!similarWords(a, b), `${a} ${b}`);
  assert.ok(!similarWords("a".repeat(70), "a".repeat(69)));      // absurdly long: never similar, never slow
});

test("a heard word that differs from the reference is listed as a change", () => {
  const s = one("The archive keeper cataloged everything", "The archivist keeper cataloged everything. Then she left.");
  assert.equal(s.kind, "words");
  assert.deepEqual(s.changes, [{ from: "archive", to: "archivist", similar: true }]);
  assert.equal(s.text, "The archivist keeper cataloged everything.");
});

test("nothing is proposed when the text already matches the reference exactly", () => {
  const s = one("Hello there, my friend.", "Hello there, my friend. I paid twenty dollars for it.");
  assert.equal(s.kind, "same");
});

// ---------------------------------------------------------------- the three promises
test("words that were spoken but are not in the reference are kept, in place", () => {
  const s = one("um so the archive keeper cataloged everything yeah", "The archive keeper cataloged everything.");
  assert.equal(s.text, "um so The archive keeper cataloged everything. yeah");   // nothing dropped; "everything." gets the stop
  assert.equal(s.tokens.length, 8);
  assert.equal(s.kept, 3);
  assert.deepEqual(s.marks.filter((m) => m === "kept").length, 3);
});

test("reference words that were never spoken are not added", () => {
  const s = one("The archive keeper cataloged everything", "The old dusty archive keeper cataloged everything.");
  assert.ok(!/old|dusty/.test(s.text));
  assert.equal(s.text, "The archive keeper cataloged everything.");
});

test("a spoken word is never swapped for an unrelated reference word just because the counts tie", () => {
  const s = one("The archive keeper cataloged everything", "The old dusty archive keeper cataloged everything.");
  assert.ok(!s.text.includes("dusty"), s.text);
  assert.equal(s.text, "The archive keeper cataloged everything.");
  assert.deepEqual(s.changes, []);
  // in the middle, with matches on both sides, a different word is shown as a change but flagged as not similar
  const m = one("the big dog barked loudly today", "The large dog barked loudly today.");
  assert.deepEqual(m.changes, [{ from: "big", to: "large", similar: false }]);
});

test("digits and symbols in the reference never replace the spoken words", () => {
  const s = one("she paid twenty dollars for three apples on", "She paid $20 for 3 apples on 5/12. Then she left.");
  assert.ok(s, "should line up despite the numbers");
  assert.ok(!/[\d$/]/.test(s.text), s.text);
  assert.ok(s.text.includes("twenty dollars") && s.text.includes("three apples"));
  assert.equal(s.tokens.length, 8);
});

test("a piece with digits already in it is not made worse", () => {
  const s = one("She paid 20 dollars for it", "She paid twenty dollars for it, she said.");
  assert.ok(s);
  assert.equal(s.text, "She paid 20 dollars for it,");
  assert.equal(s.tokens.length, 6);
});

test("digits and spelled-out numbers line up with each other, whichever way each side wrote them", () => {
  const reference = "She paid $20 for three apples on 5/12. Then she left.";
  for (const said of ["she paid $20 for three apples on", "she paid 20 dollars for three apples on", "she paid twenty dollars for three apples on"]) {
    const s = one(said, reference);
    assert.ok(s && s.changes.length === 0 && s.similarity > 0.9, `${said}: ${JSON.stringify(s)}`);
    assert.equal(s.tokens.length, spokenWordCount(said), said);
  }
  const t = one("it cost 5% more", "It cost 5% more, he said.");
  assert.equal(t.text, "It cost 5% more,");
});

test("every spoken word yields exactly one word in a proposal (property test on random readings)", () => {
  let seed = 7;
  const rnd = () => { seed = (seed * 1664525 + 1013904223) % 4294967296; return seed / 4294967296; };
  const vocab = "archive keeper river stone window silver harvest lantern meadow thunder copper orchard velvet marble anchor".split(" ");
  for (let trial = 0; trial < 150; trial++) {
    const refWords = Array.from({ length: 60 }, () => vocab[Math.floor(rnd() * vocab.length)]);
    if (trial % 3 === 0) refWords.splice(10, 0, "$20", "5%", "3rd");
    const reference = refWords.map((w, i) => (i % 7 === 6 ? `${w}.` : i % 11 === 0 ? w[0].toUpperCase() + w.slice(1) : w)).join(" ");
    const a = Math.floor(rnd() * 40), len = 4 + Math.floor(rnd() * 12);
    const spoken = refWords.slice(a, a + len).map((w) => w.replace(/[$%]|\d+/g, "twenty"));
    for (let k = 0; k < 3; k++) {                                              // a few mishearings and ad-libs
      const r = rnd();
      if (r < 0.34) spoken[Math.floor(rnd() * spoken.length)] = "banana";
      else if (r < 0.67) spoken.splice(Math.floor(rnd() * spoken.length), 0, "um");
      else spoken.splice(Math.floor(rnd() * spoken.length), 1);
    }
    const text = spoken.join(" ");
    const s = alignAll([piece("s001", text)], reference).byId.get("s001");
    if (!s) continue;                                                          // not lining up is always allowed
    const n = spokenWordCount(text);
    assert.equal(s.tokens.length, n, `${text} -> ${s.text}`);                  // none dropped, none added
    if (!/\d/.test(text)) assert.ok(!/\d|[$%]/.test(s.text), `${text} -> ${s.text}`);
    // each word is either one that was spoken, or one the reference has
    const spokenSet = new Set(pieceTokens(text).words);
    const refSet = new Set(prepareReference(reference).toks.map((t) => t.raw));
    for (const w of s.tokens) assert.ok(spokenSet.has(w) || refSet.has(w), w);
  }
});

// ---------------------------------------------------------------- finding the right place
test("pieces are matched in reading order, so a repeated sentence finds its own occurrence", () => {
  const reference = "Open the door slowly. Then wait. Open the door slowly. Then run away fast.";
  const { byId } = alignAll([piece("s001", "open the door slowly"), piece("s002", "then wait"), piece("s003", "open the door slowly"), piece("s004", "then run away fast")], reference);
  assert.equal(byId.get("s001").from, 0);
  assert.equal(byId.get("s003").from, 6);        // the second time, not the first
  assert.equal(byId.get("s004").text, "Then run away fast.");
  assert.equal(byId.get("s002"), undefined);     // two words: too short to tell
});

test("free speech between the readings is left alone and does not lose the place", () => {
  const reference = "The archive keeper cataloged everything. The river ran quietly past the old mill and the meadow beyond it.";
  const { byId, stats } = alignAll([
    piece("s001", "the archive keeper cataloged everything"),
    piece("s002", "honestly I think that was a pretty good reading to be fair"),
    piece("s003", "the river ran quietly past the old mill and the meadow beyond it"),
  ], reference);
  assert.ok(byId.has("s001") && byId.has("s003") && !byId.has("s002"));
  assert.equal(byId.get("s003").text, "The river ran quietly past the old mill and the meadow beyond it.");
  assert.equal(stats.none, 1);
});

test("a piece read out of order is still found", () => {
  const reference = "Alpha beta gamma delta epsilon zeta. Eta theta iota kappa lambda mu.";
  const { byId } = alignAll([piece("s001", "eta theta iota kappa lambda mu"), piece("s002", "alpha beta gamma delta epsilon zeta")], reference);
  assert.equal(byId.get("s001").from, 6);
  assert.equal(byId.get("s002").from, 0);
});

test("dropped pieces are ignored, one- and two-word pieces are too short to tell, and an empty reference proposes nothing", () => {
  const r = "The archive keeper cataloged everything.";
  assert.equal(alignAll([piece("s001", "the archive keeper cataloged everything", "dropped")], r).byId.size, 0);
  assert.equal(alignAll([piece("s001", "everything")], r).byId.size, 0);
  assert.equal(alignAll([piece("s001", "the archive keeper")], "").byId.size, 0);
  assert.equal(alignAll([piece("s001", "")], r).byId.size, 0);
});

test("curly apostrophes and punctuation do not stop words matching", () => {
  assert.equal(normTok("Don\u2019t,"), "don't");
  const s = one("don't stop believing", "Don\u2019t stop believing, hold on to that feeling.");
  assert.equal(s.text, "Don\u2019t stop believing,");
});

test("something that is plainly not from the reference is not forced to match it", () => {
  assert.equal(one("completely unrelated chatter about the weather today", "The archive keeper cataloged everything."), undefined);
});

test("a long reading is matched quickly", () => {
  const words = Array.from({ length: 3500 }, (_, i) => `w${(i * 7919) % 997}x`);
  const reference = words.join(" ");
  const pieces = Array.from({ length: 300 }, (_, k) => piece(`s${String(k + 1).padStart(3, "0")}`, words.slice(k * 10, k * 10 + 12).join(" ")));
  const t0 = Date.now();
  const { byId } = alignAll(pieces, reference);
  assert.ok(Date.now() - t0 < 3000, `took ${Date.now() - t0} ms`);
  assert.ok(byId.size > 250);
});

// ---------------------------------------------------------------- hints for the recognizer
test("names, acronyms and unusual terms are pulled from the reference, strongest first", () => {
  const hot = extractHotwords("Then Obi-Wan Kenobi met Anakin on Tatooine. The Jedi and the NASA team said nothing. It was McDonald's fault, and Kenobi knew.");
  const list = hot.split(", ");
  for (const w of ["Kenobi", "Anakin", "Tatooine", "Jedi", "NASA", "McDonald's"]) assert.ok(list.includes(w), `${w} in ${hot}`);
  assert.ok(!list.includes("The") && !list.includes("It") && !list.includes("and"));
  assert.equal(list[0], "Kenobi");                // appears twice mid-sentence
});

test("the hint list is capped, and numbers are never hints", () => {
  const many = Array.from({ length: 400 }, (_, i) => `a Name${String.fromCharCode(65 + (i % 26))}${i} went`).join(" ");
  assert.ok(extractHotwords(many, 100).length <= 100);
  assert.equal(extractHotwords("It cost 20 dollars in 2026."), "");
  assert.equal(extractHotwords(""), "");
});

test("the prompt is the start of the reference, cut at a sentence end where it can", () => {
  const text = "First sentence here. Second sentence follows. Third one is long enough to be cut somewhere in the middle of it.";
  assert.equal(buildPrompt(text, 60), "First sentence here. Second sentence follows.");
  assert.equal(buildPrompt("short", 60), "short");
  assert.equal(buildPrompt("  spaced   out \n text ", 60), "spaced out text");
  assert.ok(buildPrompt("word ".repeat(300), 100).length <= 100);
});

test("the cooperative version gives the same answer, and stops when asked", async () => {
  const words = Array.from({ length: 400 }, (_, i) => `w${(i * 7919) % 997}x`);
  const pieces = Array.from({ length: 30 }, (_, k) => ({ id: `s${String(k + 1).padStart(3, "0")}`, status: "pending", text: words.slice(k * 10, k * 10 + 12).join(" ") }));
  const sync = alignAll(pieces, words.join(" "));
  const async_ = await refalign.alignAllAsync(pieces, words.join(" "));
  assert.deepEqual([...async_.byId.entries()], [...sync.byId.entries()]);
  assert.deepEqual(async_.stats, sync.stats);
  let calls = 0;
  const stopped = await refalign.alignAllAsync(pieces, words.join(" "), () => ++calls > 0);
  assert.ok(stopped === null || stopped.byId.size === sync.byId.size);   // either it noticed, or it finished first: never a half answer
});

test("each proposal remembers the text it was made for", () => {
  const s = one("the archive keeper cataloged everything", "The archive keeper cataloged everything.");
  assert.equal(s.basis, "the archive keeper cataloged everything");
});
