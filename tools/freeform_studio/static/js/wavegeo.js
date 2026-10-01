// SPDX-License-Identifier: GPL-3.0-or-later
// Geometry for the waveform view: which stretch of the recording is shown, how times map to pixels, how far a cut
// point may move, and which stored peak level to draw. Pure, so it can be tested on its own.
const r3 = (x) => Math.round(x * 1000) / 1000;
export const MIN_LEN = 0.1;

/** The stretch shown: the piece plus some room around it. `widen` doubles that room per step (negative: closer). */
export function viewWindow(seg, duration, widen = 0) {
  const len = seg.end - seg.start;
  const room = Math.max(0.6, len * 0.35) * 2 ** widen;
  return { vs: Math.max(0, seg.start - room), ve: Math.min(duration, seg.end + room) };
}

export const timeToX = (t, vs, ve, width) => ((t - vs) / (ve - vs)) * width;
export const xToTime = (x, vs, ve, width) => vs + (x / width) * (ve - vs);

/** Where a piece's edges may go: not into the neighbouring pieces, not outside the recording. `sorted` is all pieces by time. */
export function boundsFor(sorted, seg, duration) {
  const i = sorted.findIndex((s) => s.id === seg.id);
  const prev = i > 0 ? sorted[i - 1] : null;
  const next = i >= 0 && i < sorted.length - 1 ? sorted[i + 1] : null;
  return { min: prev ? prev.end : 0, max: next ? next.start : duration, prevId: prev && prev.id, nextId: next && next.id };
}

/** Clamp a proposed new start or end. Returns { t, limited } where `limited` says what stopped it, if anything. */
export function clampEdge(which, t, seg, bounds) {
  if (which === "start") {
    const hi = seg.end - MIN_LEN;
    if (t < bounds.min) return { t: r3(bounds.min), limited: bounds.prevId ? "previous" : "edge" };
    if (t > hi) return { t: r3(hi), limited: "other" };
  } else {
    const lo = seg.start + MIN_LEN;
    if (t > bounds.max) return { t: r3(bounds.max), limited: bounds.nextId ? "next" : "edge" };
    if (t < lo) return { t: r3(lo), limited: "other" };
  }
  return { t: r3(t), limited: null };
}

export const nudged = (t, direction, step) => r3(t + direction * step);

/** Of the stored levels (samples per peak), the coarsest one that still has at least a peak per pixel. */
export function pickLevel(levels, rate, secondsPerPixel) {
  const need = secondsPerPixel * rate;
  const fine = [...levels].sort((a, b) => a - b).filter((spp) => spp <= need);
  return fine.length ? fine[fine.length - 1] : Math.min(...levels);
}

/** One [min, max] (each -128..127) per pixel column across [vs, ve], from interleaved min/max peak data. */
export function columns(peaks, vs, ve, width) {
  const per = peaks.spp / peaks.rate;
  const n = peaks.data.length >> 1;
  const out = new Array(width);
  for (let x = 0; x < width; x++) {
    const a = vs + ((ve - vs) * x) / width, b = vs + ((ve - vs) * (x + 1)) / width;
    const i0 = Math.max(0, Math.min(n - 1, Math.floor(a / per)));
    const i1 = Math.max(i0, Math.min(n - 1, Math.ceil(b / per) - 1));
    let lo = 127, hi = -128;
    for (let i = i0; i <= i1; i++) {
      if (peaks.data[2 * i] < lo) lo = peaks.data[2 * i];
      if (peaks.data[2 * i + 1] > hi) hi = peaks.data[2 * i + 1];
    }
    out[x] = [lo, hi];
  }
  return out;
}
