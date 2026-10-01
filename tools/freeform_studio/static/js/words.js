// Pure logic with no page code, so it can be tested on its own.
//  - alignEdit: after the reviewer retypes part of a piece, keep the timing of the words they didn't touch
//  - merge3:    combine two people's (or two devices') edits of the same take without losing either

const NON_WORD = /[^\p{L}\p{N}']+/gu;
const MIN_WORD = 0.03;
const r3 = (x) => Math.round(x * 1000) / 1000;

export const norm = (token) => token.toLowerCase().replace(NON_WORD, "") || token.toLowerCase();
export const tokenize = (text) => text.split(/\s+/).filter(Boolean);

export function joinWords(words) {
  let out = "";
  words.forEach((w, i) => { if (i && !w.j) out += " "; out += w.w; });
  return out;
}

// Longest common subsequence of two token lists, as [oldIndex, newIndex] pairs.
function lcsPairs(a, b) {
  const n = a.length, m = b.length;
  const dp = Array.from({ length: n + 1 }, () => new Uint16Array(m + 1));
  for (let i = n - 1; i >= 0; i--) {
    for (let j = m - 1; j >= 0; j--) {
      dp[i][j] = a[i] === b[j] ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1]);
    }
  }
  const pairs = [];
  let i = 0, j = 0;
  while (i < n && j < m) {
    if (a[i] === b[j]) { pairs.push([i, j]); i++; j++; }
    else if (dp[i + 1][j] >= dp[i][j + 1]) i++;
    else j++;
  }
  return pairs;
}

// Spread `tokens` across [s0, s1], each taking time in proportion to its length.
function spread(tokens, s0, s1, extra) {
  const weights = tokens.map((t) => t.length + 1);
  const total = weights.reduce((x, y) => x + y, 0);
  let t = s0;
  return tokens.map((tok, k) => {
    const dur = (s1 - s0) * weights[k] / total;
    const w = { w: tok, s: t, e: t + dur, p: 1, ed: true, ...extra };
    t += dur;
    return w;
  });
}

function settle(words, span) {
  for (let i = 0; i < words.length; i++) {
    const w = words[i];
    if (span) { w.s = Math.max(span.start, w.s); w.e = Math.min(span.end, w.e); }
    if (w.e < w.s + MIN_WORD) w.e = w.s + MIN_WORD;
    if (i > 0) {
      const p = words[i - 1];
      if (w.s < p.e) {
        if (w.s - p.s >= 2 * MIN_WORD) p.e = w.s - 0.001;   // trim the earlier word to make room
        else { w.s = p.e; if (w.e < w.s + MIN_WORD) w.e = w.s + MIN_WORD; }
      }
    }
  }
  return words.map((w) => ({ ...w, s: r3(w.s), e: r3(w.e) }));
}

/**
 * New word list for `newText`, reusing the timing of words that were left alone.
 * Words that were changed or added are marked ed:true and treated as confident (a person has looked at them).
 * `span` ({start,end}) bounds everything and is the fallback when there were no words to begin with.
 */
export function alignEdit(oldWords, newText, span = null) {
  const toks = tokenize(newText);
  if (!toks.length) return [];
  const oldN = oldWords.map((w) => norm(w.w));
  const newN = toks.map(norm);
  const out = new Array(toks.length);

  const gap = (i1, i2, j1, j2) => {
    const k = j2 - j1;
    if (!k) return;                                   // words were deleted: nothing to place
    if (i2 > i1) {                                    // replaced: the new words share the old words' time
      spread(toks.slice(j1, j2), oldWords[i1].s, oldWords[i2 - 1].e, {}).forEach((w, n) => { out[j1 + n] = w; });
      return;
    }
    // inserted with nothing to replace: sit in the gap between the neighbours
    const prev = j1 > 0 ? out[j1 - 1] : null;
    const next = i1 < oldWords.length ? oldWords[i1] : null;
    const from = prev ? prev.e : (span ? span.start : (next ? Math.max(0, next.s - 0.1 * k) : 0));
    const to = next ? next.s : (span ? span.end : from + 0.1 * k);
    spread(toks.slice(j1, j2), from, from + Math.max(to - from, 0.05 * k), {}).forEach((w, n) => { out[j1 + n] = w; });
  };

  let pi = 0, pj = 0;
  for (const [i, j] of [...lcsPairs(oldN, newN), [oldWords.length, toks.length]]) {
    gap(pi, i, pj, j);
    if (i < oldWords.length) {
      const o = oldWords[i];
      const w = { w: toks[j], s: o.s, e: o.e, p: o.p };
      if (toks[j] !== o.w) w.ed = true;               // same word, different punctuation or case: touched, not re-heard
      if (o.ed) w.ed = true;
      if (o.m) w.m = true;
      out[j] = w;
    }
    pi = i + 1;
    pj = j + 1;
  }
  return settle(out, span);
}

// ---------------------------------------------------------------- three-way merge of edit documents
const FIELDS = ["text", "status", "tags", "note", "start", "end", "words"];
const same = (x, y) => {
  if (!x || !y) return !x && !y;
  return FIELDS.every((f) => JSON.stringify(x[f]) === JSON.stringify(y[f]));
};

/**
 * `base` is the version both sides started from, `mine` my edits, `theirs` the latest on the server.
 * For each piece: only one side changed it -> take that side; both changed it the same way -> either; both changed
 * it differently -> mine wins and the piece's id is returned in `conflicts` (their version stays in the server's
 * history, so nothing is ever truly lost).
 */
export function merge3(base, mine, theirs) {
  const index = (list) => new Map(list.map((s) => [s.id, s]));
  const B = index(base), M = index(mine), T = index(theirs);
  const ids = new Set([...B.keys(), ...M.keys(), ...T.keys()]);
  const segments = [];
  const conflicts = [];
  for (const id of ids) {
    const b = B.get(id), m = M.get(id), t = T.get(id);
    let pick;
    if (same(m, t)) pick = m;
    else if (same(m, b)) pick = t;
    else if (same(t, b)) pick = m;
    else { pick = m; conflicts.push(id); }
    if (pick) segments.push(pick);
  }
  segments.sort((a, c) => a.start - c.start || a.end - c.end);
  return { segments, conflicts };
}

// ---------------------------------------------------------------- flags that follow from the text and words
const FLAG_ORDER = ["empty", "too_short", "too_long", "cuts_word", "low_confidence", "possible_hallucination", "repetitive",
                    "has_digits", "bracket_tag", "has_symbols"];

/**
 * True when a cut point falls inside a word, so the audio no longer holds all of what the text says (or the reverse).
 * A word counts as cut when less than 70% of it lies inside the piece. Recognizer timings are loose by a few
 * hundredths of a second, which that margin absorbs.
 */
export function cutsWord(seg) {
  return (seg.words || []).some((w) => {
    const len = Math.max(w.e - w.s, 0.02);
    const inside = Math.min(w.e, seg.end) - Math.max(w.s, seg.start);
    return inside < 0.7 * len - 1e-9 && !(w.e === w.s && w.s >= seg.start && w.s <= seg.end);
  });
}

/** Warning flags for a piece after the reviewer has changed it (mirrors the server's own rules). */
export function recomputeFlags(seg, min = 1.0, max = 11.5) {
  const flags = new Set(seg.flags || []);
  const text = seg.text || "";
  const set = (name, on) => { if (on) flags.add(name); else flags.delete(name); };
  const dur = seg.end - seg.start;
  set("empty", !text.trim());
  set("too_short", dur < min);
  set("too_long", dur > max);
  set("has_digits", /\d/.test(text));
  set("bracket_tag", /\[[^\]]*\]|\([^)]*\)/.test(text));
  set("has_symbols", /[&@#%*_=+<>{}\\/|]/.test(text));
  if ((seg.words || []).length) {
    set("low_confidence", seg.words.some((w) => w.p < 0.5));
    set("cuts_word", cutsWord(seg));
  }
  return [...flags].sort((a, b) => FLAG_ORDER.indexOf(a) - FLAG_ORDER.indexOf(b));
}
