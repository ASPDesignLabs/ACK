// SPDX-License-Identifier: GPL-3.0-or-later
import { api, el, fmtClock } from "./api.js";
import { FLAG_TEXT } from "./flags.js";

export function statusInfo(t) {
  switch (t.status) {
    case "recording": return ["Unfinished", ""];
    case "finishing": return ["Processing audio", ""];
    case "queued": return ["Waiting to be transcribed", ""];
    case "transcribing": return [`Transcribing ${Math.round((t.progress || 0) * 100)}%`, ""];
    case "decoded": return ["Audio ready", ""];
    case "ready": return ["Ready to review", "ok"];
    case "error": return ["Problem", "bad"];
    default: return [t.status, ""];
  }
}

export function initTakes() {
  const list = document.getElementById("takes");
  const empty = document.getElementById("takes-empty");
  const open = new Set();
  let last = "";
  let timer = null;

  async function retry(t) {
    const path = t.error_stage === "finish" ? "finish" : "transcribe";
    try { await api(`/api/takes/${t.id}/${path}`, { method: "POST", body: path === "transcribe" ? {} : undefined }); } catch (_) { /* shown on next refresh */ }
    refresh();
  }

  function card(t) {
    const [label, tone] = statusInfo(t);
    const when = new Date(t.created).toLocaleString([], { dateStyle: "medium", timeStyle: "short" });
    const meta = [];
    if (t.duration) meta.push(fmtClock(t.duration));
    if (t.status === "ready" && t.counts) meta.push(`${t.counts.segments} pieces`);
    const details = el("details", { class: "preview" }, el("summary", {}, "What was heard"), el("ol", { class: "segs" }));
    if (open.has(t.id)) details.setAttribute("open", "");
    details.addEventListener("toggle", async () => {
      if (!details.open) { open.delete(t.id); return; }
      open.add(t.id);
      const ol = details.querySelector("ol");
      ol.replaceChildren(el("li", {}, "Loading..."));
      try {
        const edit = await api(`/api/takes/${t.id}/edit`);
        ol.replaceChildren(...edit.segments.map((s) => el("li", {}, s.text || "(nothing)",
          ...s.flags.filter((f) => FLAG_TEXT[f]).map((f) => el("span", { class: "tag" }, FLAG_TEXT[f])))));
      } catch (err) {
        ol.replaceChildren(el("li", {}, `Couldn't load this: ${err.message}`));
      }
    });
    return el("li", { class: "take" },
      el("div", { class: "take-head" }, el("span", { class: "take-when" }, when), el("span", { class: `chip ${tone}` }, label)),
      meta.length ? el("div", { class: "take-meta" }, meta.join(" · ")) : "",
      t.status === "error" ? el("p", { class: "errtext" }, t.error || "Something went wrong.") : "",
      t.status === "error" ? el("button", { type: "button", class: "btn small", onclick: () => retry(t) }, "Try again") : "",
      t.status === "ready" ? details : "",
      t.status === "ready" ? el("p", {}, el("a", { class: "btn small", href: `/review/${t.id}` }, "Review and approve")) : "");
  }

  async function refresh() {
    clearTimeout(timer);
    let takes = [];
    try { takes = (await api("/api/takes")).takes; } catch (_) { /* offline: keep what is shown */ }
    const key = JSON.stringify(takes);
    if (key !== last) {
      last = key;
      list.replaceChildren(...takes.slice(0, 20).map(card));
      empty.hidden = takes.length > 0;
    }
    const active = takes.some((t) => ["finishing", "queued", "transcribing"].includes(t.status));
    timer = setTimeout(refresh, document.hidden ? 20000 : active ? 2000 : 12000);
  }

  document.addEventListener("visibilitychange", () => { if (!document.hidden) refresh(); });
  refresh();
  return { refresh };
}
