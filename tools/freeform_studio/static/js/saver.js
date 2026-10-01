import { api } from "./api.js";
import { merge3 } from "./words.js";

const clone = (x) => JSON.parse(JSON.stringify(x));
const FIELDS = ["text", "status", "tags", "note", "start", "end", "words"];
export const sameSeg = (a, b) => (!a || !b) ? (!a && !b) : FIELDS.every((f) => JSON.stringify(a[f]) === JSON.stringify(b[f]));

// Saves the edit document a moment after every change, never overwrites someone else's work, and keeps trying
// when the PC can't be reached. `get()` returns the live list of pieces; `onMerged(pieces, conflicts)` is called
// when changes made elsewhere were folded into it.
export class Saver extends EventTarget {
  constructor(takeId, doc, { get, onMerged }) {
    super();
    this.takeId = takeId;
    this.rev = doc.rev;
    this.base = clone(doc.segments);
    this.get = get;
    this.onMerged = onMerged;
    this.dirty = false;
    this.inflight = false;
    this.timer = null;
    this.attempt = 0;
    this.state = "saved";   // saved | pending | saving | offline | error
    this.error = null;
    this.draftKey = `fs.draft.${takeId}`;
    window.addEventListener("online", () => { if (this.dirty) this.flush(); });
    document.addEventListener("visibilitychange", () => { if (document.hidden && this.dirty) this.flush(); });
  }

  _set(state, error = null) {
    this.state = state;
    this.error = error;
    this.dispatchEvent(new Event("state"));
  }

  touch() {
    this.dirty = true;
    this._writeDraft();
    if (this.state !== "error") this._set(this.inflight ? "saving" : "pending");
    clearTimeout(this.timer);
    this.timer = setTimeout(() => this.flush(), 600);
  }

  async flush() {
    clearTimeout(this.timer);
    if (this.inflight || !this.dirty || this.state === "error") return;
    this.inflight = true;
    this.dirty = false;
    this._set("saving");
    const sent = clone(this.get());
    try {
      const res = await api(`/api/takes/${this.takeId}/edit`, { method: "PUT", body: { rev: this.rev, segments: sent } });
      this.rev = res.rev;
      this.base = sent;
      this.attempt = 0;
      if (!this.dirty) { this._clearDraft(); this._set("saved"); }
    } catch (err) {
      this.dirty = true;
      if (err.status === 409 && err.data && err.data.current) {
        this._reconcile(err.data.current);
        this.attempt = 0;
      } else if (err.status === 400) {
        this._set("error", err);
        this.inflight = false;
        return;
      } else {
        this.attempt += 1;
        this._set("offline", err);
        this.inflight = false;
        this.timer = setTimeout(() => this.flush(), Math.min(15000, 1000 * 2 ** Math.min(this.attempt, 4)));
        return;
      }
    }
    this.inflight = false;
    if (this.dirty) { this._set("pending"); this.timer = setTimeout(() => this.flush(), 100); }
  }

  _reconcile(current) {
    const { segments, conflicts } = merge3(this.base, this.get(), current.segments);
    this.rev = current.rev;
    this.base = clone(current.segments);
    this.onMerged(segments, conflicts);
  }

  /** After a refused save: try the same changes again. */
  retry() {
    if (this.state !== "error") return;
    this.state = "pending";
    this.flush();
  }

  /** The reviewer chose to give up on a rejected save and reload from the PC. */
  rebase(doc) {
    this.rev = doc.rev;
    this.base = clone(doc.segments);
    this.dirty = false;
    this._clearDraft();
    this._set("saved");
  }

  // A copy of unsent changes, kept on this device in case the page is closed before they reach the PC.
  _writeDraft() {
    try {
      const mineBy = new Map(this.get().map((s) => [s.id, s]));
      const baseBy = new Map(this.base.map((s) => [s.id, s]));
      const items = [];
      for (const id of new Set([...mineBy.keys(), ...baseBy.keys()])) {
        if (!sameSeg(mineBy.get(id), baseBy.get(id))) items.push({ id, base: baseBy.get(id) || null, mine: mineBy.get(id) || null });
      }
      localStorage.setItem(this.draftKey, JSON.stringify({ baseRev: this.rev, items }));
    } catch (_) { /* storage full or unavailable: the on-screen copy and autosave still protect the work */ }
  }

  _clearDraft() { try { localStorage.removeItem(this.draftKey); } catch (_) { /* nothing to clear */ } }

  static readDraft(takeId) {
    try {
      const d = JSON.parse(localStorage.getItem(`fs.draft.${takeId}`) || "null");
      return d && Array.isArray(d.items) && d.items.length ? d : null;
    } catch (_) { return null; }
  }

  static discardDraft(takeId) { try { localStorage.removeItem(`fs.draft.${takeId}`); } catch (_) { /* nothing */ } }
}
