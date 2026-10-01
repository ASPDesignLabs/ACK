import { clampEdge, columns, pickLevel, timeToX, viewWindow, xToTime, MIN_LEN } from "./wavegeo.js";

const fmt = (t) => { const m = Math.floor(t / 60); return `${m}:${(t - m * 60).toFixed(2).padStart(5, "0")}`; };
const HEIGHT = 112;

// The waveform of one piece with room around it. The picture is a canvas (decorative); the cut points are real
// elements with role="slider" so they can be dragged with a finger or mouse, moved with the arrow keys, and read by a
// screen reader. Events: "preview" (while dragging), "commit" ({which, t, fromKey}), "marker" ({t}).
export class WaveView extends EventTarget {
  constructor({ box, canvas, start, end, marker, getStep }) {
    super();
    this.box = box; this.canvas = canvas; this.getStep = getStep;
    this.h = { start, end, marker };
    this.meta = null;
    this.levels = new Map();          // samples per peak -> Promise<Int8Array>
    this.seg = null; this.bounds = null; this.duration = 0; this.widen = 0; this.marker = null; this.playhead = null;
    this.drag = null;
    this.cols = null; this.colsKey = "";
    this.error = null;
    new ResizeObserver(() => this.draw()).observe(box);
    matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => this.draw());
    for (const which of ["start", "end", "marker"]) this._wireHandle(which);
    this._wireTap();
  }

  async load(takeId) {
    this.takeId = takeId;
    try { this.meta = await (await fetch(`/api/takes/${takeId}/peaks`, { credentials: "same-origin" })).json(); } catch (_) { this.meta = null; }
    if (!this.meta || !this.meta.levels) this.meta = null;
  }

  _level(spp) {
    if (!this.levels.has(spp)) {
      this.levels.set(spp, fetch(`/api/takes/${this.takeId}/peaks/${spp}`, { credentials: "same-origin" })
        .then((r) => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.arrayBuffer(); })
        .then((buf) => new Int8Array(buf))
        .catch((err) => { this.levels.delete(spp); throw err; }));
    }
    return this.levels.get(spp);
  }

  /** The finest stored detail, for measuring silence. Resolves to { spp, rate, data } or null if there is none. */
  async finest() {
    if (!this.meta) return null;
    const spp = Math.min(...this.meta.levels);
    try { return { spp, rate: this.meta.sample_rate, data: await this._level(spp) }; } catch (_) { return null; }
  }

  show({ seg, bounds, duration, marker, widen }) {
    this.seg = seg; this.bounds = bounds; this.duration = duration; this.marker = marker; this.widen = widen;
    this.draw();
  }

  setPlayhead(t) { this.playhead = t; this.draw(); }

  // What each cut point is right now, including while it is being dragged.
  value(which) {
    if (this.drag && this.drag.which === which) return this.drag.t;
    if (which === "marker") return this.marker;
    return this.seg ? this.seg[which] : 0;
  }

  async draw() {
    const { seg } = this;
    const w = Math.floor(this.box.clientWidth);
    if (!seg || !w) return;
    const { vs, ve } = viewWindow(seg, this.duration, this.widen);
    this.win = { vs, ve, w };
    this._placeHandles();
    let peaks = null;
    if (this.meta) {
      const spp = pickLevel(this.meta.levels, this.meta.sample_rate, (ve - vs) / w);
      try { peaks = { spp, rate: this.meta.sample_rate, data: await this._level(spp) }; this.error = null; } catch (err) { this.error = err; }
    }
    if (seg !== this.seg || w !== Math.floor(this.box.clientWidth)) return;   // the piece changed while the data loaded
    this._paint(peaks);
  }

  _paint(peaks) {
    this._lastPeaks = peaks;
    const { vs, ve, w } = this.win;
    const dpr = window.devicePixelRatio || 1;
    const c = this.canvas;
    if (c.width !== Math.round(w * dpr) || c.height !== Math.round(HEIGHT * dpr)) {
      c.width = Math.round(w * dpr); c.height = Math.round(HEIGHT * dpr);
      c.style.width = `${w}px`; c.style.height = `${HEIGHT}px`;
    }
    const ctx = c.getContext("2d");
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, w, HEIGHT);
    const css = getComputedStyle(document.documentElement);
    const color = (name) => css.getPropertyValue(name).trim();
    const s = this.value("start"), e = this.value("end");
    const x0 = timeToX(s, vs, ve, w), x1 = timeToX(e, vs, ve, w);
    const mid = HEIGHT / 2;

    ctx.globalAlpha = 0.16; ctx.fillStyle = color("--accent");        // the part that will be kept
    ctx.fillRect(x0, 0, x1 - x0, HEIGHT);
    ctx.globalAlpha = 1;
    ctx.fillStyle = color("--line");
    ctx.fillRect(0, mid, w, 1);

    if (peaks) {
      const cols = columns(peaks, vs, ve, w);
      for (let x = 0; x < w; x++) {
        const [lo, hi] = cols[x];
        if (hi < lo) continue;
        const top = mid - (hi / 128) * (mid - 4), bottom = mid - (lo / 128) * (mid - 4);
        ctx.fillStyle = x >= x0 && x <= x1 ? color("--text") : color("--muted");
        ctx.fillRect(x, top, 1, Math.max(1, bottom - top));
      }
    } else {
      ctx.fillStyle = color("--muted"); ctx.font = "14px system-ui, sans-serif"; ctx.textAlign = "center";
      ctx.fillText(this.meta ? "Loading the waveform..." : "No waveform is available for this recording", w / 2, mid - 8);
    }

    ctx.fillStyle = color("--muted"); ctx.globalAlpha = 0.7;            // where each recognized word starts
    for (const word of this.seg.words || []) {
      if (word.s < vs || word.s > ve) continue;
      ctx.fillRect(Math.round(timeToX(word.s, vs, ve, w)), HEIGHT - 10, 1, 10);
    }
    ctx.globalAlpha = 1;

    if (this.marker !== null) {                                          // the split marker: dashed
      const x = timeToX(this.value("marker"), vs, ve, w);
      ctx.strokeStyle = color("--text"); ctx.lineWidth = 2; ctx.setLineDash([5, 4]);
      ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, HEIGHT); ctx.stroke(); ctx.setLineDash([]);
    }
    if (this.playhead !== null && this.playhead >= vs && this.playhead <= ve) {
      ctx.fillStyle = color("--accent");
      ctx.fillRect(Math.round(timeToX(this.playhead, vs, ve, w)) - 1, 0, 2, HEIGHT);
    }
  }

  _placeHandles() {
    const { vs, ve, w } = this.win;
    const range = { start: [this.bounds.min, this.seg.end - MIN_LEN], end: [this.seg.start + MIN_LEN, this.bounds.max],
                    marker: [this.seg.start + MIN_LEN, this.seg.end - MIN_LEN] };
    for (const which of ["start", "end", "marker"]) {
      const node = this.h[which];
      node.hidden = which === "marker" && this.marker === null;
      if (node.hidden) continue;
      const t = this.value(which);
      node.style.left = `${timeToX(t, vs, ve, w)}px`;
      node.setAttribute("aria-valuemin", String(Math.max(0, range[which][0]).toFixed(2)));
      node.setAttribute("aria-valuemax", String(range[which][1].toFixed(2)));
      node.setAttribute("aria-valuenow", t.toFixed(2));
      node.setAttribute("aria-valuetext", `${fmt(t)} seconds`);
    }
  }

  _proposal(which, t) {
    if (which === "marker") return { t: Math.min(this.seg.end - MIN_LEN, Math.max(this.seg.start + MIN_LEN, t)), limited: null };
    return clampEdge(which, t, this.seg, this.bounds);
  }

  _wireHandle(which) {
    const node = this.h[which];
    node.addEventListener("pointerdown", (e) => {
      if (!this.seg || (e.pointerType === "mouse" && e.button !== 0)) return;
      e.preventDefault();
      node.setPointerCapture(e.pointerId);
      node.focus();
      this.drag = { which, t: this.value(which), limited: null };
      node.classList.add("drag");
    });
    node.addEventListener("pointermove", (e) => {
      if (!this.drag || this.drag.which !== which) return;
      const { vs, ve, w } = this.win;
      const rect = this.box.getBoundingClientRect();
      const next = this._proposal(which, xToTime(e.clientX - rect.left, vs, ve, w));
      this.drag.t = next.t; this.drag.limited = next.limited;
      this._placeHandles(); this._paint(this._lastPeaks);
      this.dispatchEvent(new CustomEvent("preview", { detail: { which, t: next.t } }));
    });
    const finish = (commit) => {
      if (!this.drag || this.drag.which !== which) return;
      const { t, limited } = this.drag;
      this.drag = null;
      node.classList.remove("drag");
      if (commit) this.dispatchEvent(new CustomEvent(which === "marker" ? "marker" : "commit", { detail: { which, t, limited, fromKey: false } }));
      else this.draw();
    };
    node.addEventListener("pointerup", () => finish(true));
    node.addEventListener("pointercancel", () => finish(false));
    node.addEventListener("keydown", (e) => {
      const dir = { ArrowRight: 1, ArrowUp: 1, ArrowLeft: -1, ArrowDown: -1 }[e.key];
      const big = { PageUp: 1, PageDown: -1 }[e.key];
      if (!dir && !big) return;
      e.preventDefault();
      e.stopPropagation();
      const step = big ? 0.5 * big : dir * this.getStep() * (e.shiftKey ? 5 : 1);
      const next = this._proposal(which, this.value(which) + step);
      this.dispatchEvent(new CustomEvent(which === "marker" ? "marker" : "commit", { detail: { which, t: next.t, limited: next.limited, fromKey: true } }));
    });
  }

  // A tap on the picture itself (not on a handle) places the split marker there.
  _wireTap() {
    let down = null;
    this.canvas.addEventListener("pointerdown", (e) => { down = { x: e.clientX, y: e.clientY }; });
    this.canvas.addEventListener("pointerup", (e) => {
      if (!down || !this.seg) return;
      const moved = Math.hypot(e.clientX - down.x, e.clientY - down.y);
      down = null;
      if (moved > 8) return;
      const { vs, ve, w } = this.win;
      const rect = this.box.getBoundingClientRect();
      const t = xToTime(e.clientX - rect.left, vs, ve, w);
      if (t < this.seg.start + MIN_LEN || t > this.seg.end - MIN_LEN) {
        this.dispatchEvent(new CustomEvent("outside"));
        return;
      }
      this.dispatchEvent(new CustomEvent("marker", { detail: { which: "marker", t: Math.round(t * 1000) / 1000, fromKey: false } }));
    });
  }
}
