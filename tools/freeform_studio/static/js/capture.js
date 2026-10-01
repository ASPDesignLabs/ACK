// SPDX-License-Identifier: GPL-3.0-or-later
import { api, fmtBytes, fmtClock } from "./api.js";
import * as store from "./store.js";
import { Uploader } from "./uploader.js";

const $ = (id) => document.getElementById(id);
const lsGet = (k, d) => { try { return localStorage.getItem(k) ?? d; } catch (_) { return d; } };
const lsSet = (k, v) => { try { localStorage.setItem(k, v); } catch (_) { /* not available: fine */ } };

function pickMime() {
  if (!window.MediaRecorder) return undefined;
  for (const m of ["audio/webm;codecs=opus", "audio/webm", "audio/ogg;codecs=opus", "audio/mp4"]) {
    if (MediaRecorder.isTypeSupported(m)) return m;
  }
  return undefined;
}

function micProblem(err) {
  switch (err && err.name) {
    case "NotAllowedError": return "The microphone is blocked. Allow it for this site in the browser's settings, then try again.";
    case "NotFoundError": return "No microphone was found on this device.";
    case "NotReadableError": return "Another app is using the microphone. Close it and try again.";
    default: return `The microphone could not be started (${(err && err.name) || "unknown error"}).`;
  }
}

export function initCapture({ onChange }) {
  const ui = {
    state: $("state"), timer: $("timer"), bar: $("meterbar"), hint: $("levelhint"), sent: $("sent"),
    waiting: $("waiting"), mic: $("micinfo"), start: $("start"), pause: $("pause"), stop: $("stop"),
    notice: $("notice"), ref: $("ref"), autostop: $("autostop"), resume: $("resume"), resumeText: $("resume-text"),
    resumeGo: $("resume-go"),
  };
  let session = null;

  ui.ref.value = lsGet("fs.ref", "");
  ui.ref.addEventListener("input", () => lsSet("fs.ref", ui.ref.value));
  ui.autostop.value = lsGet("fs.autostop", "0");
  ui.autostop.addEventListener("change", () => lsSet("fs.autostop", ui.autostop.value));

  const setState = (t) => { ui.state.textContent = t; };
  const setNotice = (t) => { ui.notice.textContent = t || ""; ui.notice.hidden = !t; };
  const busy = () => session !== null;

  // ---------------------------------------------------------------- start
  async function start() {
    if (busy()) return;
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia || !window.MediaRecorder) {
      setNotice("This page needs a secure (https) connection to use the microphone. Open the link printed on your PC, which starts with https.");
      return;
    }
    setNotice("");
    ui.start.disabled = true;
    setState("Asking for the microphone...");
    let stream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: false, noiseSuppression: false, autoGainControl: false, channelCount: 1 },
      });
    } catch (err) {
      setNotice(micProblem(err));
      setState("Not recording.");
      ui.start.disabled = false;
      return;
    }
    const track = stream.getAudioTracks()[0];
    const settings = track.getSettings ? track.getSettings() : {};
    const mime = pickMime();
    const rec = new MediaRecorder(stream, mime ? { mimeType: mime } : undefined);

    let take;
    try {
      take = await api("/api/takes", {
        method: "POST",
        body: {
          reference_text: ui.ref.value, mime: rec.mimeType || mime || "audio/webm",
          client: { ua: navigator.userAgent, echoCancellation: settings.echoCancellation, noiseSuppression: settings.noiseSuppression,
                    autoGainControl: settings.autoGainControl, sampleRate: settings.sampleRate },
        },
      });
    } catch (err) {
      stream.getTracks().forEach((t) => t.stop());
      setNotice(err.status === 401 ? "Your PC didn't accept this phone. Open the full link printed on your PC once more."
                                   : "Can't reach your PC. Check that both are on the same Wi-Fi, then try again.");
      setState("Not recording.");
      ui.start.disabled = false;
      return;
    }

    const s = session = {
      takeId: take.id, rec, stream, track, uploader: new Uploader(take.id), chain: Promise.resolve(), nextIndex: 0,
      startedAt: performance.now(), pausedAt: null, pausedTotal: 0, stopping: false, mime: rec.mimeType,
      wake: null, timers: [], audioCtx: null, quietSince: null, lastHint: 0, hintText: "",
    };
    await store.putTake({ takeId: take.id, mime: s.mime, startedAt: Date.now(), stopped: false }).catch(() => {});

    s.uploader.addEventListener("change", () => renderUploader(s));
    rec.ondataavailable = (e) => {
      if (!e.data || !e.data.size) return;
      const index = s.nextIndex++;
      s.chain = s.chain.then(async () => {
        await store.putChunk(s.takeId, index, e.data).catch(() => {}); // safety copy first, then send
        s.uploader.enqueue(index, e.data);
      });
    };
    rec.onerror = () => { setNotice("The recorder reported an error. What was recorded so far is being saved."); stop(); };
    track.addEventListener("ended", () => {
      if (!s.stopping) { setNotice("The phone took the microphone away. What was recorded so far is being saved."); stop(); }
    });

    rec.start(1000);
    s.wake = await keepAwake(s);
    startMeter(s);
    s.timers.push(setInterval(() => tick(s), 250));
    const bits = [];
    bits.push(settings.echoCancellation === false ? "echo cancel off" : "echo cancel ON");
    bits.push(settings.noiseSuppression === false ? "noise suppression off" : "noise suppression ON");
    bits.push(settings.autoGainControl === false ? "auto gain off" : "auto gain ON");
    ui.mic.textContent = bits.join(", ");
    setState("Recording. Talk or read whenever you like. Everything is being saved to your PC as you go.");
    ui.start.hidden = true; ui.pause.hidden = false; ui.stop.hidden = false;
    ui.pause.textContent = "Pause";
    ui.stop.focus();
    if (!s.wake) setNotice("Couldn't keep the screen awake. Keep the phone unlocked and this page in front while recording.");
    renderUploader(s);
    onChange();
  }

  // ---------------------------------------------------------------- while recording
  async function keepAwake(s) {
    try {
      if ("wakeLock" in navigator) {
        const lock = await navigator.wakeLock.request("screen");
        return lock;
      }
    } catch (_) { /* refused (low battery, not visible): handled by the notice */ }
    return null;
  }

  document.addEventListener("visibilitychange", async () => {
    if (!session || session.stopping) return;
    if (document.visibilityState === "visible") {
      if (!session.wake || session.wake.released) session.wake = await keepAwake(session);
      if (session.wake) setNotice("");
    } else {
      setNotice("This page went to the background. Bring it back to the front, or the phone may stop the microphone.");
    }
  });

  window.addEventListener("beforeunload", (e) => {
    if (session && !session.stopping) { e.preventDefault(); e.returnValue = ""; }
  });

  function elapsed(s) {
    const now = performance.now();
    const paused = s.pausedAt !== null ? now - s.pausedAt : 0;
    return (now - s.startedAt - s.pausedTotal - paused) / 1000;
  }

  function tick(s) {
    const secs = elapsed(s);
    ui.timer.textContent = fmtClock(secs);
    const limit = Number(ui.autostop.value) * 60;
    if (limit && secs >= limit && !s.stopping) {
      setNotice(`Stopped automatically after ${ui.autostop.value} minutes, as you asked.`);
      stop();
    }
  }

  function renderUploader(s) {
    const u = s.uploader;
    ui.sent.textContent = u.sent ? `${u.sent} parts (${fmtBytes(u.bytes)})` : "nothing yet";
    if (u.fatal) ui.waiting.textContent = `${u.pending} (stopped: ${u.fatal.message})`;
    else if (u.attempt > 0) {
      ui.waiting.textContent = u.lastStatus === 507 ? `${u.pending} (your PC is out of disk space; sending carries on once there is room)`
        : u.lastStatus ? `${u.pending} (your PC reported a problem, retrying)` : `${u.pending} (can't reach your PC, retrying)`;
    }
    else ui.waiting.textContent = String(u.pending);
  }

  function startMeter(s) {
    try {
      const Ctx = window.AudioContext || window.webkitAudioContext;
      s.audioCtx = new Ctx();
      const src = s.audioCtx.createMediaStreamSource(s.stream);
      const an = s.audioCtx.createAnalyser();
      an.fftSize = 2048;
      src.connect(an); // not connected to speakers, so no feedback
      const buf = new Float32Array(an.fftSize);
      s.timers.push(setInterval(() => {
        an.getFloatTimeDomainData(buf);
        let sum = 0, peak = 0;
        for (const v of buf) { sum += v * v; peak = Math.max(peak, Math.abs(v)); }
        const rms = Math.sqrt(sum / buf.length);
        const db = 20 * Math.log10(Math.max(rms, 1e-6));
        ui.bar.style.width = `${Math.round(Math.min(1, Math.max(0, (db + 60) / 60)) * 100)}%`;
        const now = performance.now();
        if (db > -50) s.quietSince = null; else if (s.quietSince === null) s.quietSince = now;
        let hint;
        if (peak >= 0.98) hint = "Too loud: hold the phone a little farther away.";
        else if (s.quietSince !== null && now - s.quietSince > 4000) hint = "Very quiet: check that nothing is covering the microphone.";
        else if (db > -40) hint = "Level looks good.";
        else hint = s.hintText;
        if (hint !== s.hintText && now - s.lastHint > 1000) { s.hintText = hint; s.lastHint = now; ui.hint.textContent = hint; }
      }, 100));
    } catch (_) { /* meter is a nicety; recording does not depend on it */ }
  }

  function pauseResume() {
    if (!session || session.stopping) return;
    const s = session;
    if (s.rec.state === "recording") {
      s.rec.pause(); s.pausedAt = performance.now();
      ui.pause.textContent = "Resume";
      setState("Paused. Nothing is being recorded. Tap Resume to continue.");
    } else if (s.rec.state === "paused") {
      s.rec.resume(); s.pausedTotal += performance.now() - s.pausedAt; s.pausedAt = null;
      ui.pause.textContent = "Pause";
      setState("Recording. Talk or read whenever you like. Everything is being saved to your PC as you go.");
    }
  }

  // ---------------------------------------------------------------- stop
  async function stop() {
    if (!session || session.stopping) return;
    const s = session;
    s.stopping = true;
    ui.pause.hidden = true; ui.stop.disabled = true;
    setState("Finishing the recording...");
    const stopped = new Promise((resolve) => { s.rec.onstop = resolve; });
    if (s.rec.state !== "inactive") s.rec.stop();
    await stopped; // the final chunk arrives just before this
    s.stream.getTracks().forEach((t) => t.stop());
    s.timers.forEach(clearInterval);
    try { if (s.audioCtx) s.audioCtx.close(); } catch (_) { /* already closed */ }
    try { if (s.wake && !s.wake.released) s.wake.release(); } catch (_) { /* already released */ }
    ui.bar.style.width = "0%";
    ui.hint.textContent = " ";
    await s.chain;
    await store.putTake({ takeId: s.takeId, mime: s.mime, startedAt: Date.now(), stopped: true }).catch(() => {});

    setState("Sending the last part to your PC. Keep this page open until it says saved.");
    try {
      await s.uploader.drain();
      await finishTake(s.takeId);
      setState("Saved. Your PC is processing it now; it will show under Recent recordings.");
    } catch (err) {
      setNotice(`Sending stopped: ${err.message}. The recording is kept on this phone; reload this page and use "Send it now".`);
      setState("Not fully sent yet.");
    }
    session = null;
    ui.start.hidden = false; ui.start.disabled = false; ui.stop.hidden = true; ui.stop.disabled = false;
    ui.start.textContent = "Start another recording";
    onChange();
  }

  async function finishTake(takeId) {
    for (let attempt = 0; ; attempt++) {
      try {
        await api(`/api/takes/${takeId}/finish`, { method: "POST" });
        await store.deleteTake(takeId).catch(() => {});
        return;
      } catch (err) {
        if (err.status) throw err; // the PC answered with a refusal: retrying won't help
        await new Promise((r) => setTimeout(r, Math.min(15000, 1000 * 2 ** Math.min(attempt, 4))));
      }
    }
  }

  // ---------------------------------------------------------------- recovery after a crash / refresh
  async function checkUnfinished() {
    const takes = await store.listTakes();
    if (!takes.length) { ui.resume.hidden = true; return; }
    const counts = await Promise.all(takes.map(async (t) => (await store.listChunks(t.takeId)).length));
    const waiting = counts.reduce((a, b) => a + b, 0);
    ui.resumeText.textContent = takes.length === 1
      ? `A recording from earlier didn't finish sending (${waiting} part${waiting === 1 ? "" : "s"} still on this phone). Nothing is lost.`
      : `${takes.length} recordings from earlier didn't finish sending (${waiting} parts still on this phone). Nothing is lost.`;
    ui.resume.hidden = false;
    ui.resumeGo.onclick = async () => {
      ui.resumeGo.disabled = true;
      ui.resumeText.textContent = "Sending...";
      try {
        for (const t of takes) {
          const up = new Uploader(t.takeId);
          for (const c of await store.listChunks(t.takeId)) up.enqueue(c.index, c.blob);
          await up.drain();
          await finishTake(t.takeId);
        }
        ui.resume.hidden = true;
        setState("Saved. Your PC is processing the earlier recording now.");
      } catch (err) {
        ui.resumeText.textContent = `Sending stopped: ${err.message}. It is still kept on this phone.`;
      }
      ui.resumeGo.disabled = false;
      onChange();
    };
  }

  ui.start.addEventListener("click", start);
  ui.pause.addEventListener("click", pauseResume);
  ui.stop.addEventListener("click", stop);
  checkUnfinished();
  return { busy };
}
