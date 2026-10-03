// SPDX-License-Identifier: GPL-3.0-or-later
import { api, el, fmtClock } from "./api.js";
import { FLAG_HELP } from "./flags.js";
import { statusInfo } from "./takes.js";
import { alignEdit, recomputeFlags } from "./words.js";
import { boundaryBefore, mergePieces, nextId, splitPiece, trimToSpeech } from "./pieces.js";
import { boundsFor, clampEdge, nudged } from "./wavegeo.js";
import { WaveView } from "./wave.js";
import { alignAllAsync, buildPrompt, extractHotwords } from "./refalign.js";
import { replaceToken, spokenTokens } from "./spoken.js";
import { initExportCard } from "./exportcard.js";
import { initStatusCard } from "./statuscard.js";
import { initAckCard } from "./ackcard.js";
import { Player } from "./player.js";
import { Saver, sameSeg } from "./saver.js";
import { watchConnection } from "./conn.js";

const $ = (id) => document.getElementById(id);
const clone = (x) => JSON.parse(JSON.stringify(x));
const TAGS = ["laugh", "cough", "noise", "unclear"];
const LEFT_OUT = new Set(TAGS);            // build_dataset skips these by default
const STATUS_TEXT = { pending: "To review", approved: "Approved", dropped: "Dropped" };
const STATUS_TONE = { pending: "", approved: "ok", dropped: "bad" };
const when = (iso) => new Date(iso).toLocaleString([], { dateStyle: "medium", timeStyle: "short" });
const fmtT = (t) => { const m = Math.floor(t / 60); return `${m}:${(t - m * 60).toFixed(1).padStart(4, "0")}`; };
const plural = (n, one, many) => `${n} ${n === 1 ? one : many}`;

function pref(key, fallback) { try { const v = localStorage.getItem(key); return v === null ? fallback : v; } catch (_) { return fallback; } }
function setPref(key, value) { try { localStorage.setItem(key, value); } catch (_) { /* a remembered setting is a convenience only */ } }

const announceNode = $("announce");
function announce(message) {
  announceNode.textContent = "";
  setTimeout(() => { announceNode.textContent = message; }, 40);
}

function showNotice(message, { retry = null, sticky = false } = {}) {
  const n = $("notice");
  n.replaceChildren(el("p", {}, message));
  const row = el("div", { class: "row wrap" });
  if (retry) row.append(el("button", { type: "button", class: "btn small", onclick: retry }, "Try again"));
  if (!sticky) row.append(el("button", { type: "button", class: "btn small", onclick: () => { n.hidden = true; } }, "Dismiss"));
  if (row.children.length) n.append(row);
  n.hidden = false;
}

// Rebuilds a container's children but keeps keyboard focus on the same control, found by its data-key.
function rebuild(container, children) {
  const active = document.activeElement;
  const key = active && container.contains(active) ? active.dataset.key : null;
  container.replaceChildren(...children);
  if (key) {
    const again = [...container.querySelectorAll("[data-key]")].find((n) => n.dataset.key === key);
    if (again) again.focus();
  }
}

function confirmDialog({ title, body, ok }) {
  const d = $("confirm");
  if (typeof d.showModal !== "function") return Promise.resolve(window.confirm(`${title}\n\n${body}`));
  $("confirm-title").textContent = title;
  $("confirm-body").textContent = body;
  $("confirm-ok").textContent = ok;
  d.returnValue = "";
  return new Promise((resolve) => {
    d.addEventListener("close", () => resolve(d.returnValue === "ok"), { once: true });
    d.showModal();
  });
}

watchConnection($("conn"), "Can't reach your PC. Anything you change is kept on this device and sent when it's back.", { brief: true });
const route = location.pathname.match(/^\/review\/([^/]+)\/?$/);
if (route) openEditor(route[1]); else openInbox();

// ============================================================================================ inbox
function openInbox() {
  $("inbox").hidden = false;
  initExportCard({ takeId: null, ensureSaved: async () => true, confirmDialog, announce });
  initStatusCard({ announce });
  initAckCard({ confirmDialog, announce, onImported: () => refresh() });
  const list = $("inbox-list"), empty = $("inbox-empty");
  let timer = null;

  function card(t) {
    const [label, tone] = statusInfo(t);
    const c = t.counts || { segments: 0, approved: 0, dropped: 0 };
    const meta = [];
    if (t.duration) meta.push(fmtClock(t.duration));
    if (t.status === "ready") {
      meta.push(plural(c.segments, "piece", "pieces"), `${c.approved} approved`, `${c.dropped} dropped`,
                `${c.segments - c.approved - c.dropped} to review`);
    }
    return el("li", { class: "take" },
      el("div", { class: "take-head" }, el("span", { class: "take-when" }, when(t.created)), el("span", { class: `chip ${tone}` }, label)),
      meta.length ? el("div", { class: "take-meta" }, meta.join(" · ")) : "",
      t.status === "error" ? el("p", { class: "errtext" }, t.error || "Something went wrong. Open Record to try again.") : "",
      t.status === "ready"
        ? el("p", {}, el("a", { class: "btn small primary", href: `/review/${t.id}`, "aria-label": `Review the recording from ${when(t.created)}` }, "Review"))
        : "");
  }

  async function refresh() {
    clearTimeout(timer);
    let takes = null;
    try {
      takes = (await api("/api/takes")).takes;
    } catch (_) {
      if (!list.children.length) empty.textContent = "Can't reach your PC yet. This list fills in when it's back.";
    }
    if (takes) {
      list.replaceChildren(...takes.map(card));
      empty.hidden = takes.length > 0;
      empty.textContent = "Nothing recorded yet. Use Record to make one.";
    }
    const busy = takes && takes.some((t) => ["finishing", "queued", "transcribing"].includes(t.status));
    timer = setTimeout(refresh, document.hidden ? 20000 : busy ? 2500 : 15000);
  }
  document.addEventListener("visibilitychange", () => { if (!document.hidden) refresh(); });
  refresh();
}

// ============================================================================================ editor
async function openEditor(takeId) {
  $("editor").hidden = false;
  const fail = (message) => showNotice(message, { retry: () => location.reload(), sticky: true });
  let take;
  try {
    take = await api(`/api/takes/${takeId}`);
  } catch (err) {
    return fail(err.status === 404 ? "That recording wasn't found on your PC." : `Couldn't load this recording: ${err.message}`);
  }
  $("take-title").textContent = `Recording from ${when(take.created)}${take.duration ? ` (${fmtClock(take.duration)})` : ""}`;
  document.title = `Review ${when(take.created)} - Freeform Studio`;
  if (take.status !== "ready") {
    return showNotice(`This recording isn't ready to review yet (${statusInfo(take)[0].toLowerCase()}). Open Record to follow its progress.`, { sticky: true });
  }
  let doc;
  try {
    doc = await api(`/api/takes/${takeId}/edit`);
  } catch (err) {
    return fail(`Couldn't load the pieces for this recording: ${err.message}`);
  }
  $("work").hidden = false;
  startEditor(takeId, doc, take);
}

function startEditor(takeId, doc, take) {
  let pieces = doc.segments;
  const undoStack = [];
  const redoStack = [];
  let session = null;          // text being typed right now: { id, base, dirty }
  let curId = null;
  let filter = pieces.some((s) => s.status === "pending") ? "todo" : "all";
  let listLimit = 50;
  let draftPending = false;
  let nowIdx = -1;
  let rove = 0;                // which word button is reachable by Tab
  let renderedId = null;
  let prevSave = "saved";
  let keysOn = pref("fs.keys", "1") === "1";
  const duration = take.duration || 0;
  let marker = null;           // where a split would happen, in seconds
  let lastWord = -1;           // the word most recently tapped, for "split before this word"
  let widen = 0;               // how much room the waveform shows around the piece
  let reference = take.reference_text || "";   // the text that was being read, if any
  let align = null;            // { key, result } from comparing the pieces with the reference
  let alignTimer = null;
  let alignRun = 0;
  let skipped = new Set();     // proposals the person declined, so they aren't offered again
  try { skipped = new Set(JSON.parse(pref(`fs.refskip.${takeId}`, "[]"))); } catch (_) { /* start fresh */ }
  const posKey = `fs.pos.${takeId}`;

  const FILTERS = [
    ["todo", "To review", (s) => s.status === "pending"],
    ["warn", "Needs a look", (s) => s.status === "pending" && s.flags.length > 0],
    ["approved", "Approved", (s) => s.status === "approved"],
    ["dropped", "Dropped", (s) => s.status === "dropped"],
    ["all", "All", () => true],
  ];
  const filterFn = (key) => FILTERS.find((f) => f[0] === key)[2];
  const filtered = () => pieces.filter(filterFn(filter));
  const byId = (id) => pieces.find((s) => s.id === id) || null;
  const cur = () => byId(curId);
  const at = (s) => `the piece at ${fmtClock(s.start)}`;
  const isClean = (s) => s.status === "pending" && !s.flags.length && s.text.trim() && !s.tags.some((t) => LEFT_OUT.has(t));
  const cleanIds = () => pieces.filter(isClean).map((s) => s.id);
  const sortPieces = () => pieces.sort((a, b) => a.start - b.start || a.end - b.end);

  // ------------------------------------------------------------------ audio
  const player = new Player($("audio"));
  player.load(`/api/takes/${takeId}/audio`);
  player.addEventListener("fail", () => hint("The audio couldn't be loaded from your PC."));
  player.addEventListener("stopped", () => { setNow(-1); $("play").textContent = "Play"; renderTime(); wave.setPlayhead(null); });
  player.addEventListener("time", (e) => {
    const s = cur();
    if (!s) return;
    let idx = -1;
    s.words.forEach((w, i) => { if (w.s <= e.detail + 0.02) idx = i; });
    setNow(idx);
    renderTime(e.detail);
    if ($("timing").open) wave.setPlayhead(e.detail);
  });

  async function playPiece(from, to) {
    const s = cur();
    if (!s) return;
    try {
      await player.playRange(from === undefined ? s.start : from, to === undefined ? s.end : to);
      $("play").textContent = "Stop";
    } catch (err) {
      $("play").textContent = "Play";
      if (err && err.name === "AbortError") return;   // moved to another piece before this one started
      hint(err && err.name === "NotAllowedError" ? "The browser wouldn't start the audio. Tap Play again." : "The audio couldn't be played.");
    }
  }
  const togglePlay = () => { if (player.playing) player.stop(); else playPiece(); };

  function setNow(idx) {
    if (idx === nowIdx) return;
    const words = $("p-words").children;
    if (words[nowIdx]) { words[nowIdx].classList.remove("now"); words[nowIdx].removeAttribute("aria-current"); }
    nowIdx = idx;
    if (words[idx]) { words[idx].classList.add("now"); words[idx].setAttribute("aria-current", "true"); }
  }

  let lastTime = "";
  function renderTime(t) {
    const s = cur();
    if (!s) return;
    const text = t !== undefined && player.playing
      ? `Playing ${fmtT(Math.max(0, t - s.start))} of ${fmtT(s.end - s.start)}`
      : `${fmtT(s.start)} to ${fmtT(s.end)}, ${(s.end - s.start).toFixed(1)} seconds long`;
    if (text !== lastTime) { lastTime = text; $("p-time").textContent = text; }
  }

  // ------------------------------------------------------------------ small messages next to the controls
  function hint(message) { $("p-hint").textContent = message; }

  // ------------------------------------------------------------------ saving
  const saver = new Saver(takeId, doc, { get: () => pieces, onMerged });
  saver.addEventListener("state", renderSave);

  function renderSave() {
    const st = saver.state;
    const kids = [];
    if (st === "saved") kids.push(el("span", {}, "All changes are saved on your PC."));
    else if (st === "pending" || st === "saving") kids.push(el("span", {}, "Saving..."));
    else if (st === "offline") kids.push(el("span", {}, "Can't reach your PC. Your changes are kept on this device and will be sent when it's back."));
    else {
      const err = saver.error;
      const why = err && err.data && Array.isArray(err.data.details) ? err.data.details.slice(0, 3).join("; ") : (err && err.message) || "";
      kids.push(el("span", {}, `Your PC refused the last save${why ? `: ${why}` : ""}. Your changes are still on screen and on this device.`),
        el("button", { type: "button", class: "btn small", onclick: () => saver.retry() }, "Try saving again"),
        el("button", { type: "button", class: "btn small", onclick: reloadFromPc }, "Reload from my PC"));
    }
    $("savestate").replaceChildren(...kids);
    if (st !== prevSave) {
      if (st === "offline" || st === "error") announce(st === "offline" ? "Can't reach your PC. Changes are kept on this device." : "Your PC refused the last save.");
      else if (st === "saved" && (prevSave === "offline" || prevSave === "error")) announce("Your changes reached your PC. All saved.");
      prevSave = st;
    }
  }

  async function reloadFromPc() {
    const ok = await confirmDialog({
      title: "Reload from your PC?",
      body: "This drops the changes that couldn't be saved and shows what your PC has. Your PC's copy is not touched.", ok: "Reload",
    });
    if (!ok) return;
    try {
      const fresh = await api(`/api/takes/${takeId}/edit`);
      pieces = fresh.segments;
      saver.rebase(fresh);
      undoStack.length = 0; redoStack.length = 0;
      session = null;
      setLast("Reloaded what your PC has.");
      settle(curId, null);
    } catch (err) {
      showNotice(`Couldn't reach your PC to reload: ${err.message}`);
    }
  }

  // Changes made on another device or tab were folded in; my own edits were kept where they clashed.
  function onMerged(list, conflicts) {
    pieces = list;
    session = null;
    settle(curId, null, { force: true });
    if (conflicts.length) {
      showNotice(`Changes made somewhere else clashed with yours on ${plural(conflicts.length, "piece", "pieces")}. Yours were kept. The other versions are in "Earlier versions" below.`);
    }
  }

  window.addEventListener("beforeunload", (e) => {
    if (saver.state !== "saved") { e.preventDefault(); e.returnValue = ""; }
  });

  // ------------------------------------------------------------------ the one way anything is changed (so it can be undone)
  const snap = (ids) => new Map(ids.map((id) => [id, byId(id) ? clone(byId(id)) : null]));
  function applySnap(map) {
    for (const [id, seg] of map) {
      const i = pieces.findIndex((s) => s.id === id);
      if (seg === null) { if (i >= 0) pieces.splice(i, 1); } else if (i >= 0) pieces[i] = clone(seg); else pieces.push(clone(seg));
    }
    sortPieces();
  }
  const differs = (a, b) => [...a.keys()].some((id) => !sameSeg(a.get(id), b.get(id)));

  function guard() {
    if (!draftPending) return false;
    hint("Choose Restore or Discard on the banner at the top first.");
    waveHint("Choose Restore or Discard on the banner at the top first.");
    return true;
  }

  function setLast(message) { $("lastchange").textContent = message; renderUndo(); }

  // `coalesce` names a kind of adjustment; repeats of it within two seconds become one undo step.
  function change(label, ids, mutate, { coalesce = null } = {}) {
    if (guard()) return false;
    commitSession();
    const before = snap(ids);
    mutate();
    const after = snap(ids);
    if (!differs(before, after)) return false;
    const last = undoStack[undoStack.length - 1];
    if (coalesce && last && last.key === coalesce && Date.now() - last.at < 2000 && redoStack.length === 0) {
      last.after = after; last.label = label; last.at = Date.now();
    } else {
      undoStack.push({ label, before, after, ids, key: coalesce, at: Date.now() });
      if (undoStack.length > 200) undoStack.shift();
    }
    redoStack.length = 0;
    saver.touch();
    setLast(label);
    return true;
  }

  function undo() { stepHistory(undoStack, redoStack, "before", "Undid"); }
  function redo() { stepHistory(redoStack, undoStack, "after", "Redid"); }
  function stepHistory(from, to, side, verb) {
    if (guard()) return;
    commitSession();
    const entry = from.pop();
    if (!entry) return;
    applySnap(entry[side]);
    to.push(entry);
    saver.touch();
    const target = entry.ids.find((id) => byId(id));
    if (target) reveal(target); else settle(curId, null);
    setLast(`${verb}: ${entry.label}`);
  }

  function renderUndo() {
    const u = undoStack[undoStack.length - 1], r = redoStack[redoStack.length - 1];
    $("undo").disabled = !u;
    $("redo").disabled = !r;
    $("undo").setAttribute("aria-label", u ? `Undo: ${u.label}` : "Undo");
    $("redo").setAttribute("aria-label", r ? `Redo: ${r.label}` : "Redo");
  }

  // ------------------------------------------------------------------ typing
  const ta = $("p-text");
  function sanitize(value) {
    return value.replace(/[\r\n\t|]+/g, " ").replace(/[\x00-\x08\x0b-\x1f\x7f]/g, "");
  }

  ta.addEventListener("input", () => {
    const s = cur();
    if (!s || guard()) return;
    const raw = ta.value;
    const clean = sanitize(raw);
    if (clean !== raw) {
      const pos = Math.min(ta.selectionStart, clean.length);
      ta.value = clean;
      ta.setSelectionRange(pos, pos);
      if (raw.includes("|")) hint("The | symbol can't be used (it separates the columns of the training file), so it was replaced with a space.");
    }
    if (!session || session.id !== s.id) session = { id: s.id, base: clone(s), dirty: false };
    const text = clean.trim().replace(/\s+/g, " ");
    s.text = text;
    s.words = alignEdit(session.base.words, text, { start: s.start, end: s.end });
    s.flags = recomputeFlags(s);
    session.dirty = true;
    saver.touch();
    renderAfterText(s);
  });
  ta.addEventListener("blur", () => commitSession());

  // Ends a stretch of typing: it becomes one undo step, and the box shows the tidied text.
  function commitSession() {
    if (!session) return;
    const done = session;
    session = null;
    const now = byId(done.id);
    if (done.dirty && now && !sameSeg(now, done.base)) {
      const label = `Edited the text of ${at(now)}`;
      undoStack.push({ label, before: new Map([[done.id, done.base]]), after: new Map([[done.id, clone(now)]]), ids: [done.id] });
      redoStack.length = 0;
      setLast(label);
    }
    if (now && ta.value !== now.text) ta.value = now.text;
    renderSuggestions();
    scheduleAlign();
  }

  function renderAfterText(s) {
    renderFlags(s);
    renderWords(s);
    renderBar();
    renderSummary();
    updateFilters();
    const li = $("list").querySelector(`[data-key="${s.id}"] .ptext`);
    if (li) li.textContent = s.text || "(no words)";
    lastTime = "";
    renderTime();
    lastWord = -1;
    renderTiming();
  }

  // ------------------------------------------------------------------ actions
  function approve() {
    const s = cur();
    if (!s || guard()) return;
    commitSession();
    if (s.status === "approved") return goNext();
    if (!s.text.trim()) { hint("This piece has no words, so it can't be approved. Type what was said, or drop it."); return; }
    const next = neighbour(s.id, 1);
    if (change(`Approved ${at(s)}`, [s.id], () => { byId(s.id).status = "approved"; })) leave(s.id, next && next.id);
  }

  function drop() {
    const s = cur();
    if (!s || guard()) return;
    commitSession();
    if (s.status === "dropped") {
      if (change(`Restored ${at(s)} to "to review"`, [s.id], () => { byId(s.id).status = "pending"; })) leave(s.id, null);
      return;
    }
    const next = neighbour(s.id, 1);
    if (change(`Dropped ${at(s)}`, [s.id], () => { byId(s.id).status = "dropped"; })) leave(s.id, next && next.id);
  }

  function takeBackApproval() {
    const s = cur();
    if (!s) return;
    if (change(`Took back approval for ${at(s)}`, [s.id], () => { byId(s.id).status = "pending"; })) leave(s.id, null);
  }

  function toggleTag(tag) {
    const s = cur();
    if (!s) return;
    const on = !s.tags.includes(tag);
    if (change(`${on ? "Tagged" : "Removed the tag from"} ${at(s)}${on ? ` as ${tag}` : ` (${tag})`}`, [s.id], () => {
      const live = byId(s.id);
      live.tags = on ? [...live.tags, tag].sort() : live.tags.filter((t) => t !== tag);
    })) renderAll();
  }

  async function bulkApprove() {
    if (guard()) return;
    commitSession();
    const ids = cleanIds();
    if (!ids.length) { hint("No piece is clean right now."); return; }
    const ok = await confirmDialog({
      title: `Approve ${plural(ids.length, "piece", "pieces")}?`,
      body: "These have no warnings. That doesn't mean you checked them, so only go ahead if you're happy to trust the recognizer on them. Pieces with warnings and pieces you dropped are left alone. You can undo this.",
      ok: `Approve ${ids.length}`,
    });
    if (!ok) return;
    if (change(`Approved ${plural(ids.length, "clean piece", "clean pieces")}`, ids, () => { ids.forEach((id) => { byId(id).status = "approved"; }); })) {
      settle(curId, null);
      announce(`Approved ${plural(ids.length, "piece", "pieces")}.`);
    }
  }

  // ------------------------------------------------------------------ moving around
  function neighbour(id, step) {
    const list = filtered();
    const i = list.findIndex((s) => s.id === id);
    return i < 0 ? null : (list[i + step] || null);
  }

  function nearest(list, id) {
    const s = byId(id);
    if (!list.length) return null;
    if (!s) return list[0];
    return list.find((x) => x.start >= s.start) || list[list.length - 1];
  }

  // After a change that may have taken the piece out of the current view, land on `prefer` (the one that follows it).
  function leave(leavingId, preferId) {
    const list = filtered();
    let target = preferId && list.some((s) => s.id === preferId) ? preferId : null;
    if (!target && list.some((s) => s.id === leavingId)) target = leavingId;
    if (!target) { const n = nearest(list, leavingId); target = n && n.id; }
    select(target);
  }

  // Keep the current piece if it is still in view, otherwise the nearest one, then redraw everything.
  function settle(id, prefer, { force = false } = {}) {
    const list = filtered();
    let target = id && list.some((s) => s.id === id) ? id : null;
    if (!target) { const n = nearest(list, id); target = n && n.id; }
    if (target === curId) { renderAll({ force }); return; }
    select(target);
  }

  function select(id, { focus = false, quiet = false } = {}) {
    commitSession();
    player.stop();
    curId = id;
    if (id) setPref(posKey, id);
    nowIdx = -1;
    rove = 0;
    marker = null;
    lastWord = -1;
    hint("");
    waveHint("");
    renderAll();
    if (!id) { announce("Nothing left in this view."); return; }
    if (focus) { $("piece-title").focus(); $("piece").scrollIntoView({ block: "start" }); }
    if (!quiet) {
      const list = filtered();
      announce(`Piece ${list.findIndex((s) => s.id === id) + 1} of ${list.length}. ${byId(id).text || "No words."}`);
    }
    if ($("autoplay").checked) playPiece();
  }

  function goNext() {
    const n = neighbour(curId, 1);
    if (n) select(n.id); else hint("That was the last piece in this view.");
  }
  function goPrev() {
    const n = neighbour(curId, -1);
    if (n) select(n.id); else hint("This is the first piece in this view.");
  }

  // Shows a piece even if the current view would hide it.
  function reveal(id) {
    if (!filtered().some((s) => s.id === id)) filter = "all";
    select(id);
  }

  function nextToCheck() {
    const i = pieces.findIndex((s) => s.id === curId);
    const pending = (s) => s.status === "pending" && s.id !== curId;
    const later = pieces.slice(i + 1).find(pending);
    const target = later || pieces.find(pending);
    if (!target) { hint("Nothing left to check. Every piece is approved or dropped."); return; }
    reveal(target.id);
    if (!later) hint("Nothing later needs checking, so this went back to the start.");
  }

  function setFilter(key) {
    commitSession();
    filter = key;
    listLimit = 50;
    settle(curId, null);
    const n = filtered().length;
    announce(`Showing ${FILTERS.find((f) => f[0] === key)[1]}: ${plural(n, "piece", "pieces")}.`);
  }

  // ------------------------------------------------------------------ drawing
  const filterBox = $("filter");
  filterBox.replaceChildren(...FILTERS.map(([key, label]) => el("option", { value: key }, label)));
  filterBox.addEventListener("change", () => setFilter(filterBox.value));

  function updateFilters() {
    FILTERS.forEach(([key, label, fn], i) => { filterBox.options[i].textContent = `${label} (${pieces.filter(fn).length})`; });
    filterBox.value = filter;
  }

  function renderSummary() {
    const c = { approved: 0, dropped: 0, todo: 0 };
    pieces.forEach((s) => { c[s.status === "approved" ? "approved" : s.status === "dropped" ? "dropped" : "todo"] += 1; });
    $("summary").textContent = pieces.length
      ? `${plural(pieces.length, "piece", "pieces")}: ${c.approved} approved, ${c.dropped} dropped, ${c.todo} to review.${c.todo === 0 ? " Nothing left to review." : ""}`
      : "No speech was found in this recording.";
    const clean = cleanIds().length;
    $("bulk").textContent = `Approve all clean pieces (${clean})`;
    $("bulk").disabled = clean === 0;
  }

  function renderFlags(s) {
    const items = s.flags.filter((f) => FLAG_HELP[f]).map((f) => el("li", {}, FLAG_HELP[f]));
    $("p-flags").replaceChildren(...items);
    $("p-flags").hidden = items.length === 0;
  }

  function renderWords(s) {
    const words = s.words || [];
    rove = Math.min(rove, Math.max(0, words.length - 1));
    $("p-words").replaceChildren(...words.map((w, i) => {
      const low = w.p < 0.5 && !w.ed;
      const attrs = { type: "button", class: `w${low ? " low" : ""}`, tabindex: i === rove ? "0" : "-1", "data-i": String(i) };
      if (low) attrs["aria-label"] = `${w.w} (unsure)`;
      return el("button", attrs, w.w);
    }));
    $("p-words").hidden = words.length === 0;
    nowIdx = -1;
  }

  function renderTags(s) {
    const names = [...TAGS, ...s.tags.filter((t) => !TAGS.includes(t))];
    rebuild($("p-tags"), [el("span", { class: "lead" }, "Tag:"),
      ...names.map((t) => el("button", { type: "button", class: "fchip", "data-key": t, "aria-pressed": String(s.tags.includes(t)), onclick: () => toggleTag(t) }, t))]);
  }

  function renderBar() {
    const s = cur();
    $("bar").hidden = !s;
    if (!s) return;
    $("drop").textContent = s.status === "dropped" ? "Restore" : "Drop";
    $("approve").textContent = s.status === "approved" ? "Next piece" : "Approve and next";
    $("approve").disabled = s.status !== "approved" && !s.text.trim();
    $("play").textContent = player.playing ? "Stop" : "Play";
    $("reset").hidden = s.status !== "approved";
    const list = filtered();
    const i = list.findIndex((x) => x.id === s.id);
    $("prev").disabled = i <= 0;
    $("next").disabled = i < 0 || i >= list.length - 1;
  }

  function renderPiece({ force = false } = {}) {
    const s = cur();
    $("piece-empty").hidden = !!s;
    $("piece-body").hidden = !s;
    if (!s) {
      $("piece-empty-text").textContent = pieces.length
        ? (filter === "todo" ? "Every piece has been approved or dropped. Choose All to look back over them."
          : filter === "all" ? "There is nothing in this view." : "Nothing in this view. Choose another one above, such as All.")
        : "No speech was found in this recording.";
      renderedId = null;
      return;
    }
    const list = filtered();
    $("piece-title").textContent = `Piece ${list.findIndex((x) => x.id === s.id) + 1} of ${list.length}`;
    const chip = $("p-status");
    chip.textContent = STATUS_TEXT[s.status];
    chip.className = `chip ${STATUS_TONE[s.status]}`;
    renderFlags(s);
    renderWords(s);
    renderTags(s);
    if (renderedId !== s.id || force || document.activeElement !== ta) ta.value = s.text;
    ta.readOnly = draftPending;
    renderedId = s.id;
    lastTime = "";
    renderTime();
    renderTiming();
    renderSuggestions();
  }

  function renderList() {
    const list = filtered();
    const idx = list.findIndex((s) => s.id === curId);
    if (idx >= listLimit) listLimit = idx + 25;
    const rows = list.slice(0, listLimit).map((s, k) => el("li", {},
      el("button", { type: "button", class: "pitem", "data-key": s.id, "aria-current": s.id === curId ? "true" : false, onclick: () => select(s.id, { focus: true }) },
        el("span", { class: "pnum" }, `${k + 1}.`), el("span", { class: "ptime" }, fmtClock(s.start)),
        el("span", { class: `chip ${STATUS_TONE[s.status]}` }, STATUS_TEXT[s.status]),
        s.tags.length ? el("span", { class: "tag" }, s.tags.join(", ")) : "",
        el("span", { class: "ptext" }, s.text || "(no words)"))));
    if (list.length > listLimit) {
      rows.push(el("li", {}, el("button", { type: "button", class: "btn small", "data-key": "more", onclick: () => { listLimit += 50; renderList(); } },
        `Show ${Math.min(50, list.length - listLimit)} more`)));
    }
    if (!list.length) rows.push(el("li", { class: "hint" }, "Nothing here."));
    rebuild($("list"), rows);
  }

  function renderAll({ force = false } = {}) {
    renderSummary();
    updateFilters();
    renderPiece({ force });
    renderList();
    renderBar();
    renderUndo();
    scheduleAlign();
    renderReferenceCard();
  }

  // ------------------------------------------------------------------ cut points, split and join
  const timing = $("timing");
  const waveHint = (message) => { $("wave-hint").textContent = message; };
  const fmtP = (t) => { const m = Math.floor(t / 60); return `${m}:${(t - m * 60).toFixed(2).padStart(5, "0")}`; };
  const wave = new WaveView({ box: $("wave"), canvas: $("wave-canvas"), start: $("h-start"), end: $("h-end"), marker: $("h-marker"),
    getStep: () => Number($("step").value) });
  wave.load(takeId);
  timing.open = pref("fs.timing", "0") === "1";
  $("step").value = pref("fs.step", "0.05");
  $("audition").checked = pref("fs.audition", "0") === "1";
  timing.addEventListener("toggle", () => { setPref("fs.timing", timing.open ? "1" : "0"); renderTiming(); });
  $("step").addEventListener("change", () => setPref("fs.step", $("step").value));
  $("audition").addEventListener("change", () => setPref("fs.audition", $("audition").checked ? "1" : "0"));

  function renderTiming() {
    const s = cur();
    if (!s) return;
    if (marker !== null && (marker < s.start + 0.1 || marker > s.end - 0.1)) marker = null;
    const at0 = pieces.indexOf(s);
    $("join-prev").disabled = at0 <= 0;
    $("join-next").disabled = at0 < 0 || at0 >= pieces.length - 1;
    $("split-marker").disabled = marker === null;
    $("hear-marker").disabled = marker === null;
    $("split-marker").textContent = marker === null ? "Split at the marker" : `Split at ${fmtP(marker)}`;
    const w = lastWord >= 0 ? s.words[lastWord] : null;
    $("split-word").disabled = !w;
    $("split-word").textContent = w ? `Split before “${w.w}”` : "Split before a word";
    $("wave-read").textContent = `Starts at ${fmtP(s.start)}, ends at ${fmtP(s.end)}, ${(s.end - s.start).toFixed(2)} seconds long.`;
    if (timing.open) wave.show({ seg: s, bounds: boundsFor(pieces, s, duration), duration, marker, widen });
  }

  const EDGE_LIMIT = {
    previous: "That's as far as it goes: the previous piece ends there. Trim or join that piece first.",
    next: "That's as far as it goes: the next piece starts there.",
    edge: "That's the edge of the recording.",
  };

  function setEdge(which, t) {
    const s = cur();
    if (!s) return;
    if (guard()) { renderTiming(); return; }
    const { t: to, limited } = clampEdge(which, t, s, boundsFor(pieces, s, duration));
    const note = limited === "other" ? (which === "start" ? "The start can't pass the end." : "The end can't go before the start.") : limited ? EDGE_LIMIT[limited] : "";
    waveHint(note);
    if (to === s[which]) { renderTiming(); return; }
    const changed = change(`Moved the ${which} of ${at(s)} to ${fmtP(to)}`, [s.id], () => {
      const live = byId(s.id);
      live[which] = to;
      live.flags = recomputeFlags(live);
    }, { coalesce: `${which}:${s.id}` });
    if (!changed) return;
    renderAll();
    if (byId(s.id).flags.includes("cuts_word")) {
      waveHint(`${note} A cut point falls inside a word, so the audio may not match the text. Move it, or change the text.`.trim());
    }
    if ($("audition").checked) hear(which);
  }

  function hear(which) {
    const s = cur();
    if (!s) return;
    if (which === "start") playPiece(s.start, Math.min(s.end, s.start + 0.8));
    else playPiece(Math.max(s.start, s.end - 0.8), s.end);
  }

  async function trimSilence() {
    const s = cur();
    if (!s || guard()) return;
    const peaks = await wave.finest();
    if (!peaks) { waveHint("The waveform isn't available for this recording, so silence can't be measured."); return; }
    const r = trimToSpeech(cur(), peaks);
    if (!r) { waveHint("Nothing to trim: this piece is already close to the speech."); return; }
    const lead = r.start - s.start, tail = s.end - r.end;
    if (change(`Trimmed the silence around ${at(s)}`, [s.id], () => {
      const live = byId(s.id);
      live.start = r.start; live.end = r.end;
      live.flags = recomputeFlags(live);
    })) {
      renderAll();
      waveHint(`Trimmed ${lead.toFixed(2)} s from the start and ${tail.toFixed(2)} s from the end, leaving room around the speech. Undo puts it back.`);
    }
  }

  function doSplit(t) {
    const s = cur();
    if (!s || guard()) return;
    commitSession();
    const id = nextId(pieces);
    const r = splitPiece(s, t, id);
    if (r.error) { waveHint(r.error); return; }
    player.stop();
    const label = `Split ${at(s)} at ${fmtP(t)}`;
    if (!change(label, [s.id, id], () => {
      pieces[pieces.findIndex((p) => p.id === s.id)] = r.first;
      pieces.push(r.second);
      sortPieces();
    })) return;
    reveal(s.id);
    waveHint(`Split in two. The second piece starts at ${fmtP(t)}. Both are back to "to review". Undo puts it back as one.`);
    announce(`Split in two. You are on the first piece: ${r.first.text || "no words"}.`);
  }

  function joinWith(direction) {
    const s = cur();
    if (!s || guard()) return;
    commitSession();
    const i = pieces.findIndex((p) => p.id === s.id);
    const other = pieces[i + direction];
    if (!other) { waveHint("There is no piece there to join with."); return; }
    const [a, b] = direction < 0 ? [other, s] : [s, other];
    const r = mergePieces(a, b);
    if (r.error) { waveHint(r.error); return; }
    player.stop();
    if (!change(`Joined ${at(a)} with the piece after it`, [a.id, b.id], () => {
      pieces[pieces.findIndex((p) => p.id === a.id)] = r.merged;
      pieces.splice(pieces.findIndex((p) => p.id === b.id), 1);
    })) return;
    reveal(a.id);
    waveHint(`Joined. ${r.gap >= 1 ? `The ${r.gap.toFixed(1)} second pause between them is now part of the piece. ` : ""}It is back to "to review". Undo splits it again.`);
    announce("Joined the two pieces.");
  }

  wave.addEventListener("commit", (e) => setEdge(e.detail.which, e.detail.t));
  wave.addEventListener("marker", (e) => {
    marker = e.detail.t;
    renderTiming();
    waveHint(`Marker at ${fmtP(marker)}. Use "Split at the marker" to cut here, or "Hear around the marker" to check it.`);
  });
  wave.addEventListener("outside", () => waveHint("Tap inside the shaded part to place a marker."));
  wave.addEventListener("preview", () => {
    $("wave-read").textContent = `Starts at ${fmtP(wave.value("start"))}, ends at ${fmtP(wave.value("end"))}, ${(wave.value("end") - wave.value("start")).toFixed(2)} seconds long.`;
  });
  for (const b of document.querySelectorAll("[data-nudge]")) {
    b.addEventListener("click", () => { const s = cur(); if (s) setEdge(b.dataset.nudge, nudged(s[b.dataset.nudge], Number(b.dataset.dir), Number($("step").value))); });
  }
  $("hear-start").addEventListener("click", () => hear("start"));
  $("hear-end").addEventListener("click", () => hear("end"));
  $("hear-marker").addEventListener("click", () => {
    const s = cur();
    if (s && marker !== null) playPiece(Math.max(s.start, marker - 0.6), Math.min(s.end, marker + 0.6));
  });
  $("trim").addEventListener("click", trimSilence);
  $("wider").addEventListener("click", () => { widen = Math.min(3, widen + 1); renderTiming(); });
  $("closer").addEventListener("click", () => { widen = Math.max(-2, widen - 1); renderTiming(); });
  $("split-marker").addEventListener("click", () => { if (marker !== null) doSplit(marker); });
  $("split-word").addEventListener("click", () => { const s = cur(); if (s && lastWord >= 0) doSplit(boundaryBefore(s.words, lastWord)); });
  $("join-prev").addEventListener("click", () => joinWith(-1));
  $("join-next").addEventListener("click", () => joinWith(1));

  // ------------------------------------------------------------------ the text that was read, and spoken forms
  const skipKeyOf = (s) => `${s.id}:${s.text}`;
  const refKey = () => `${reference.length}|${pieces.map((p) => (p.status === "dropped" ? `~${p.id}` : `${p.id}:${p.text}`)).join("\n")}`;

  // Compares the pieces with the reference a moment after things settle, in small slices so the page stays responsive.
  function scheduleAlign() {
    clearTimeout(alignTimer);
    if (!reference.trim()) { align = null; return; }
    if (align && align.key === refKey()) return;
    alignRun++;
    const run = alignRun;
    alignTimer = setTimeout(async () => {
      const key = refKey();
      const snapshot = pieces.map((p) => ({ id: p.id, text: p.text, status: p.status }));
      const result = await alignAllAsync(snapshot, reference, () => run !== alignRun);
      if (!result || run !== alignRun) return;
      align = { key, result };
      renderSuggestions();
      renderReferenceCard();
    }, 400);
  }

  // A proposal is only shown for the exact text it was made for, so it can never overwrite what was typed since.
  function suggestionFor(s) {
    const a = align && align.result.byId.get(s.id);
    return a && a.basis === s.text ? a : null;
  }

  function applyText(id, text, label) {
    if (guard()) return false;
    commitSession();
    const ok = change(label, [id], () => {
      const live = byId(id);
      live.text = text;
      live.words = alignEdit(live.words, text, { start: live.start, end: live.end });
      live.flags = recomputeFlags(live);
    });
    if (ok) renderAll({ force: true });
    return ok;
  }

  function useSpoken(id, index, token, replacement) {
    const s = byId(id);
    if (!s || guard()) return;
    commitSession();
    if (s.text.split(/\s+/).filter(Boolean)[index] !== token) { renderSuggestions(); return; }   // the text changed since it was offered
    applyText(id, replaceToken(s.text, index, replacement), `Wrote “${token}” as “${replacement}” in ${at(s)}`);
  }

  // ------------------------------------------------------------------ what the phone noted (recordings that came from ACK)
  let ackInfo = null;
  const plainWords = (text) => text.toLowerCase().replace(/[^a-z0-9' ]+/g, " ").split(/\s+/).filter(Boolean).join(" ");

  // The clip ACK recorded this piece from, and how many pieces that clip became (more than one when it ran long).
  function ackClipFor(s) {
    if (!ackInfo || !ackInfo.notes || ackInfo.notes.mode !== "script") return null;
    const mid = (s.start + s.end) / 2;
    const inside = (p, c) => { const m = (p.start + p.end) / 2; return m >= c.start_s && m <= c.end_s; };
    const clip = ackInfo.notes.clips.find((c) => mid >= c.start_s && mid <= c.end_s);
    return clip ? { clip, pieces: pieces.filter((p) => inside(p, clip)).length } : null;
  }

  function renderAck() {
    const s = cur();
    const hit = s && ackClipFor(s);
    $("p-ack").hidden = !hit;
    if (!hit) return;
    const { clip, pieces: n } = hit;
    $("p-ack-text").textContent = clip.text;
    const facts = [`Card ${clip.card}${clip.attempt > 1 ? `, attempt ${clip.attempt}` : ""}`];
    if (clip.metrics) {
      facts.push(`loudest point ${clip.metrics.peak_dbfs} dB`);
      if (clip.metrics.clipped_samples) facts.push(`${plural(clip.metrics.clipped_samples, "sample", "samples")} at the maximum level`);
    }
    const checked = ackInfo.checks && ackInfo.checks.pieces
      ? Object.values(ackInfo.checks.pieces).find((c) => c.clip === clip.index && Math.abs(c.start - s.start) < 0.5) : null;
    if (checked && typeof checked.snr_db === "number") facts.push(`voice ${Math.round(checked.snr_db)} dB above the room`);
    if (clip.flags && clip.flags.length) facts.push(`you marked it: ${clip.flags.join(", ")}`);
    if (n > 1) facts.push(`this card became ${n} pieces, so compare it with all of them`);
    $("p-ack-facts").textContent = facts.join(" · ");
    $("ack-use").hidden = n > 1 || plainWords(clip.text) === plainWords(s.text);
  }

  $("ack-use").addEventListener("click", () => {
    const s = cur();
    const hit = s && ackClipFor(s);
    if (!hit || hit.pieces > 1) return;
    applyText(s.id, hit.clip.text, `Used the words from the card for ${at(s)}`);
  });

  if (take.client && take.client.source === "ack") {
    api(`/api/takes/${takeId}/ack`).then((info) => { ackInfo = info; renderAck(); }).catch(() => { /* no phone notes: the piece view works without them */ });
  }

  function renderSuggestions() {
    renderAck();
    const s = cur();
    if (!s) { $("p-ref").hidden = true; $("p-spoken").hidden = true; return; }
    const a = suggestionFor(s);
    if (a && a.kind !== "same" && !skipped.has(skipKeyOf(s))) {
      const nodes = [];
      a.tokens.forEach((tok, i) => {
        if (i) nodes.push(" ");
        nodes.push(a.marks[i] === "changed" ? el("mark", {}, tok) : a.marks[i] === "kept" ? el("span", { class: "kept" }, tok) : tok);
      });
      $("p-ref-text").replaceChildren(...nodes);
      const lines = a.changes.map((c) => el("li", {}, `“${c.from}” would become “${c.to}”${c.similar ? "" : ". That is a different word, so listen before you accept it."}`));
      if (a.style) lines.push(el("li", {}, `${plural(a.style, "word gets", "words get")} the reference's capital letters or punctuation.`));
      $("p-ref-changes").replaceChildren(...lines);
      $("p-ref-note").textContent = a.kept ? `${plural(a.kept, "word you said isn't", "words you said aren't")} in the text, so ${a.kept === 1 ? "it was" : "they were"} kept (shown in italics).` : "";
      $("p-ref").hidden = false;
    } else {
      $("p-ref").hidden = true;
    }
    const found = spokenTokens(s.text);
    $("p-spoken").hidden = found.length === 0;
    rebuild($("p-spoken-list"), found.map(({ index, token, options }) => el("li", { role: "group", "aria-label": `Ways to say ${token}` },
      el("span", { class: "tok" }, token),
      el("span", { class: "opts" }, ...options.map((o, n) => el("button", { type: "button", class: "btn small", "data-key": `${index}:${n}`, onclick: () => useSpoken(s.id, index, token, o.text) },
        o.text, el("span", { class: "note" }, o.note)))))));
  }

  // Pieces that can safely take the reference's wording in one go: still waiting, a close match, and only small spelling differences.
  const closeMatches = () => pieces.filter((p) => {
    const a = p.status === "pending" && suggestionFor(p);
    return a && a.kind !== "same" && a.similarity >= 0.85 && a.changes.every((c) => c.similar) && !skipped.has(skipKeyOf(p));
  });

  function renderReferenceCard() {
    const bulk = $("ref-bulk");
    if (!reference.trim()) {
      $("ref-summary").textContent = "No reference text is saved with this recording. If you read from a document, paste it below and the pieces that match it will be offered its wording.";
      bulk.disabled = true;
      bulk.textContent = "Use its wording on close matches";
      return;
    }
    if (!align) { $("ref-summary").textContent = "Comparing the pieces with the text you read..."; bulk.disabled = true; return; }
    const st = align.result.stats;
    $("ref-summary").textContent = `${st.same} ${st.same === 1 ? "piece matches" : "pieces match"} it exactly, ${st.style} differ only in capital letters or punctuation, ${st.words} differ in wording, and ${st.none} don't line up with it (free speech, or too short to tell).`;
    const n = closeMatches().length;
    bulk.textContent = `Use its wording on ${n} close ${n === 1 ? "match" : "matches"}`;
    bulk.disabled = n === 0;
  }

  async function bulkReference() {
    if (guard()) return;
    commitSession();
    const ids = closeMatches().map((p) => p.id);
    if (!ids.length) return;
    const ok = await confirmDialog({
      title: `Use the reference wording on ${plural(ids.length, "piece", "pieces")}?`,
      body: "Each of these lines up closely with the text you read, and any word that changes is only a small spelling difference. Words you said that aren't in the text are kept, and nothing is added that you didn't say. Undo puts them all back in one step.",
      ok: `Use it on ${ids.length}`,
    });
    if (!ok) return;
    const texts = new Map(ids.map((id) => [id, suggestionFor(byId(id))]).filter(([, a]) => a).map(([id, a]) => [id, a.text]));
    if (change(`Used the reference wording on ${plural(texts.size, "piece", "pieces")}`, [...texts.keys()], () => {
      for (const [id, text] of texts) {
        const live = byId(id);
        live.text = text;
        live.words = alignEdit(live.words, text, { start: live.start, end: live.end });
        live.flags = recomputeFlags(live);
      }
    })) {
      renderAll({ force: true });
      announce(`Used the reference wording on ${plural(texts.size, "piece", "pieces")}.`);
    }
  }

  $("ref-use").addEventListener("click", () => {
    const s = cur();
    const a = s && suggestionFor(s);
    if (a) applyText(s.id, a.text, `Used the reference wording for ${at(s)}`);
  });
  $("ref-skip").addEventListener("click", () => {
    const s = cur();
    if (!s) return;
    skipped.add(skipKeyOf(s));
    setPref(`fs.refskip.${takeId}`, JSON.stringify([...skipped].slice(-500)));
    renderSuggestions();
    renderReferenceCard();
    announce("Kept what you have.");
  });
  $("ref-bulk").addEventListener("click", bulkReference);

  const refEdit = $("ref-edit");
  refEdit.value = reference;
  refEdit.addEventListener("input", () => { $("ref-save").disabled = refEdit.value === reference; });
  $("ref-save").addEventListener("click", async () => {
    const text = refEdit.value;
    if (text === reference) return;
    if (reference.trim()) {
      const ok = await confirmDialog({
        title: text.trim() ? "Replace the reference text?" : "Clear the reference text?",
        body: "The text that is saved now is kept on your PC, in this recording's reference_history folder, in case you need it back.", ok: text.trim() ? "Replace it" : "Clear it",
      });
      if (!ok) return;
    }
    try {
      const res = await api(`/api/takes/${takeId}/reference`, { method: "PUT", body: { text } });
      reference = res.reference_text;
      refEdit.value = reference;
      $("ref-save").disabled = true;
      $("ref-save-hint").textContent = "Saved. The text it replaced, if any, is kept on your PC.";
      align = null;
      hintDefaults();
      renderSuggestions();
      renderReferenceCard();
      scheduleAlign();
      announce("Reference text saved.");
    } catch (err) {
      $("ref-save-hint").textContent = `Couldn't save it: ${err.message}. What you typed is still here.`;
    }
  });

  // Hints for listening again: names from the reference, and the start of it as context.
  let hintsTouched = false;
  function hintDefaults() {
    if (hintsTouched) return;
    $("hint-words").value = extractHotwords(reference);
    $("hint-prompt").value = buildPrompt(reference);
  }
  $("hint-words").addEventListener("input", () => { hintsTouched = true; });
  $("hint-prompt").addEventListener("input", () => { hintsTouched = true; });
  hintDefaults();

  $("retranscribe").addEventListener("click", async () => {
    if (guard()) return;
    commitSession();
    const count = (f) => pieces.filter(f).length;
    const approved = count((p) => p.status === "approved"), dropped = count((p) => p.status === "dropped");
    const edited = count((p) => p.auto && p.auto.text !== p.text);
    const ok = await confirmDialog({
      title: "Listen to the whole recording again?",
      body: `This takes a few minutes and cuts the recording into new pieces. Your current pieces (${approved} approved, ${dropped} dropped, ${edited} with text you changed) are kept in Earlier versions and can be brought back, but they won't be mixed with the new ones. This page goes back to the list of recordings while it works.`,
      ok: "Listen again",
    });
    if (!ok) return;
    if (!(await waitSaved())) {
      showNotice("Your latest changes haven't reached your PC yet, so nothing was started. Try again when it says all changes are saved.");
      return;
    }
    try {
      await api(`/api/takes/${takeId}/transcribe`, { method: "POST", body: { initial_prompt: $("hint-prompt").value, hotwords: $("hint-words").value, regenerate: true, force: true } });
      location.href = "/review";
    } catch (err) {
      showNotice(`Couldn't start it: ${err.message}`);
    }
  });

  // ------------------------------------------------------------------ export of approved pieces as training clips
  $("export-slot").append($("exportcard"));
  initExportCard({ takeId, ensureSaved: async () => { commitSession(); return waitSaved(); }, confirmDialog, announce });

  // ------------------------------------------------------------------ word strip: tap to hear from a word
  const strip = $("p-words");
  strip.addEventListener("click", (e) => {
    const b = e.target.closest("button.w");
    const s = cur();
    if (!b || !s) return;
    const w = s.words[Number(b.dataset.i)];
    lastWord = Number(b.dataset.i);
    renderTiming();
    playPiece(Math.max(s.start, w.s - 0.12));
  });
  strip.addEventListener("keydown", (e) => {
    const buttons = [...strip.querySelectorAll("button.w")];
    const i = buttons.indexOf(document.activeElement);
    if (i < 0) return;
    const to = { ArrowRight: i + 1, ArrowLeft: i - 1, Home: 0, End: buttons.length - 1 }[e.key];
    if (to === undefined) return;
    e.preventDefault();
    const n = Math.max(0, Math.min(buttons.length - 1, to));
    buttons.forEach((b, k) => b.setAttribute("tabindex", k === n ? "0" : "-1"));
    rove = n;
    buttons[n].focus();
  });

  // ------------------------------------------------------------------ version history
  async function loadHistory() {
    const ul = $("history-list");
    ul.replaceChildren(el("li", { class: "hint" }, "Loading..."));
    try {
      const { history } = await api(`/api/takes/${takeId}/edit/history`);
      if (!history.length) { ul.replaceChildren(el("li", { class: "hint" }, "No earlier versions yet. One is kept each time your changes save.")); return; }
      ul.replaceChildren(...history.map((h) => el("li", { class: "take" },
        el("div", { class: "take-head" }, el("span", { class: "take-when" }, when(h.time)), el("span", { class: "chip" }, h.name.startsWith("edit-before-restore") ? "kept before a restore" : `version ${h.rev}`)),
        el("div", { class: "take-meta" }, `${plural(h.counts.segments, "piece", "pieces")} · ${h.counts.approved} approved · ${h.counts.dropped} dropped`),
        el("p", {}, el("button", { type: "button", class: "btn small", "aria-label": `Restore this version from ${when(h.time)}`, onclick: () => restoreVersion(h) }, "Restore this version")))));
    } catch (err) {
      ul.replaceChildren(el("li", { class: "errtext" }, `Couldn't load the earlier versions: ${err.message}`));
    }
  }
  $("history").addEventListener("toggle", () => { if ($("history").open) loadHistory(); });

  async function waitSaved(ms = 8000) {
    saver.flush();
    for (let waited = 0; waited < ms && saver.state !== "saved"; waited += 100) {
      if (saver.state === "error") break;
      await new Promise((r) => setTimeout(r, 100));
      if (!saver.inflight && saver.dirty) saver.flush();
    }
    return saver.state === "saved";
  }

  async function restoreVersion(h) {
    if (guard()) return;
    commitSession();
    const ok = await confirmDialog({
      title: "Go back to this version?",
      body: `This replaces what you see now with the version from ${when(h.time)} (${h.counts.approved} approved, ${h.counts.dropped} dropped). What you have now is kept in the list, so you can come back to it.`,
      ok: "Go back to it",
    });
    if (!ok) return;
    if (!(await waitSaved())) {
      showNotice("Your latest changes haven't reached your PC yet, so nothing was restored. Try again when it says all changes are saved.");
      return;
    }
    try {
      const fresh = await api(`/api/takes/${takeId}/edit/restore`, { method: "POST", body: { name: h.name, rev: saver.rev } });
      pieces = fresh.segments;
      saver.rebase(fresh);
      undoStack.length = 0; redoStack.length = 0;
      session = null;
      settle(curId, null);
      setLast(`Went back to the version from ${when(h.time)}.`);
      announce(`Went back to the version from ${when(h.time)}.`);
      loadHistory();
    } catch (err) {
      showNotice(err.status === 409
        ? "Something changed on your PC while you were restoring, so nothing was restored. Try again."
        : `Couldn't restore that version: ${err.message}`);
    }
  }

  // ------------------------------------------------------------------ changes that were never saved last time
  const draft = Saver.readDraft(takeId);
  if (draft) {
    const real = draft.items.filter((it) => (it.mine ? !sameSeg(it.mine, byId(it.id)) : !!byId(it.id)));
    if (!real.length) {
      Saver.discardDraft(takeId);
    } else {
      draftPending = true;
      $("draft-text").textContent = `${plural(real.length, "change", "changes")} from earlier never reached your PC, because the page was closed first. ${real.length === 1 ? "It is" : "They are"} still kept on this device.`;
      $("draft").hidden = false;
      $("draft-restore").addEventListener("click", () => {
        draftPending = false;
        const usable = real.filter((it) => !it.mine || (typeof it.mine.id === "string" && typeof it.mine.text === "string" && Number.isFinite(it.mine.start) && Number.isFinite(it.mine.end)));
        change(`Restored ${plural(usable.length, "unsaved change", "unsaved changes")}`, usable.map((it) => it.id), () => {
          for (const it of usable) {
            const i = pieces.findIndex((s) => s.id === it.id);
            if (!it.mine) { if (i >= 0) pieces.splice(i, 1); } else if (i >= 0) pieces[i] = it.mine; else pieces.push(it.mine);
          }
          sortPieces();
        });
        $("draft").hidden = true;
        settle(curId, null, { force: true });
      });
      $("draft-discard").addEventListener("click", () => {
        draftPending = false;
        Saver.discardDraft(takeId);
        $("draft").hidden = true;
        ta.readOnly = false;
      });
    }
  }

  // ------------------------------------------------------------------ wiring
  $("approve").addEventListener("click", approve);
  $("drop").addEventListener("click", drop);
  $("play").addEventListener("click", togglePlay);
  $("reset").addEventListener("click", takeBackApproval);
  $("prev").addEventListener("click", goPrev);
  $("next").addEventListener("click", goNext);
  $("next-check").addEventListener("click", nextToCheck);
  $("undo").addEventListener("click", undo);
  $("redo").addEventListener("click", redo);
  $("bulk").addEventListener("click", bulkApprove);
  $("autoplay").checked = pref("fs.autoplay", "0") === "1";
  $("autoplay").addEventListener("change", () => setPref("fs.autoplay", $("autoplay").checked ? "1" : "0"));
  $("keys-on").checked = keysOn;
  $("keys-on").addEventListener("change", () => { keysOn = $("keys-on").checked; setPref("fs.keys", keysOn ? "1" : "0"); });

  document.addEventListener("keydown", (e) => {
    if ($("confirm").open || e.repeat) return;
    const t = e.target;
    const typing = t instanceof HTMLTextAreaElement || t instanceof HTMLInputElement || t instanceof HTMLSelectElement || t.isContentEditable;
    const mod = e.ctrlKey || e.metaKey;
    if (mod && !e.altKey && e.key === "Enter") { e.preventDefault(); approve(); return; }
    if (mod && !e.altKey && !typing) {
      const k = e.key.toLowerCase();
      if (k === "z") { e.preventDefault(); if (e.shiftKey) redo(); else undo(); }
      else if (k === "y") { e.preventDefault(); redo(); }
      return;
    }
    if (mod || e.altKey || typing || !keysOn) return;
    if (t.getAttribute && t.getAttribute("role") === "slider") return;   // arrow keys belong to the cut points
    const onControl = t instanceof HTMLButtonElement || t instanceof HTMLAnchorElement || t.tagName === "SUMMARY";
    const inWords = !!t.closest && !!t.closest("#p-words");
    switch (e.key) {
      case " ": if (onControl) return; e.preventDefault(); togglePlay(); break;
      case "a": case "A": approve(); break;
      case "d": case "D": drop(); break;
      case "j": case "J": goNext(); break;
      case "k": case "K": goPrev(); break;
      case "n": case "N": nextToCheck(); break;
      case "e": case "E": e.preventDefault(); ta.focus(); break;
      case "ArrowRight": if (!inWords && !onControl) goNext(); break;
      case "ArrowLeft": if (!inWords && !onControl) goPrev(); break;
      default: break;
    }
  });

  curId = (() => {
    const list = filtered();
    if (!list.length) return null;
    const left = byId(pref(posKey, ""));
    const hit = left ? list.find((s) => s.start >= left.start) : null;
    return (hit || list[0]).id;
  })();
  renderSave();
  select(curId, { quiet: true });
  renderReferenceCard();
  scheduleAlign();
}
