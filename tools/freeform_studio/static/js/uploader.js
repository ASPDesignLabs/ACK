// SPDX-License-Identifier: GPL-3.0-or-later
import { api } from "./api.js";
import * as store from "./store.js";

const FATAL = new Set([400, 401, 403, 404, 409, 413]);

// Sends chunks one at a time, in order, retrying forever on network trouble. Chunk PUTs are idempotent on the
// server, so a repeat after a lost reply is harmless.
export class Uploader extends EventTarget {
  constructor(takeId) {
    super();
    this.takeId = takeId;
    this.queue = [];
    this.sent = 0;
    this.bytes = 0;
    this.attempt = 0;
    this.fatal = null;
    this.lastStatus = 0;       // the PC's last refusal while retrying (0: it couldn't be reached at all)
    this._running = false;
    this._waiters = [];
  }

  get pending() { return this.queue.length; }

  enqueue(index, blob) {
    this.queue.push({ index, blob });
    this.queue.sort((a, b) => a.index - b.index);
    this._emit();
    this._pump();
  }

  drain() {
    if (this.fatal) return Promise.reject(this.fatal);
    if (!this.queue.length && !this._running) return Promise.resolve();
    return new Promise((resolve, reject) => this._waiters.push({ resolve, reject }));
  }

  _emit() { this.dispatchEvent(new Event("change")); }

  _settle(err) {
    const waiters = this._waiters.splice(0);
    for (const w of waiters) (err ? w.reject(err) : w.resolve());
  }

  async _pump() {
    if (this._running) return;
    this._running = true;
    try {
      while (this.queue.length && !this.fatal) {
        const item = this.queue[0];
        try {
          await api(`/api/takes/${this.takeId}/chunks/${item.index}`, { method: "PUT", body: item.blob });
          this.queue.shift();
          this.sent += 1;
          this.bytes += item.blob.size;
          this.attempt = 0;
          await store.deleteChunk(this.takeId, item.index).catch(() => {});
          this._emit();
        } catch (err) {
          if (err.status && FATAL.has(err.status)) {
            this.fatal = err;
            this._emit();
            break;
          }
          this.attempt += 1;
          this.lastStatus = err.status || 0;
          this._emit();
          await new Promise((resolve) => {
            const t = setTimeout(done, Math.min(15000, 1000 * 2 ** Math.min(this.attempt, 4)));
            function done() { clearTimeout(t); window.removeEventListener("online", done); resolve(); }
            window.addEventListener("online", done, { once: true });
          });
        }
      }
    } finally {
      this._running = false;
      this._settle(this.fatal);
    }
  }
}
