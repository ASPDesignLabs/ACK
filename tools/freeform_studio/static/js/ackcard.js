// SPDX-License-Identifier: GPL-3.0-or-later
import { api, el, fmtBytes } from "./api.js";

const plural = (n, one, many) => `${n} ${n === 1 ? one : many}`;
const PIECE = 8 * 1024 * 1024;   // a package goes up in pieces this big, so a dropped connection loses at most one

function minutes(seconds) {
  if (seconds < 90) return plural(Math.round(seconds), "second", "seconds");
  return `${(seconds / 60).toFixed(1)} minutes`;
}

// "Add recordings from ACK": bring a package saved by the ACK app into this PC, look inside it, and add its recordings.
// Nothing here leaves the PC; the package file itself is never changed or deleted.
export function initAckCard({ confirmDialog, announce, onImported }) {
  const $ = (id) => document.getElementById(id);
  const card = $("ackcard");
  let chosen = null;     // { name, result } for the package being looked at
  let busy = false;

  function setBusy(on) {
    busy = on;
    $("ack-file").disabled = on;
    $("ack-refresh").disabled = on;
    for (const b of document.querySelectorAll("#ack-list button")) b.disabled = on;
    $("ack-go").disabled = on || !chosen || !chosen.result.to_import || !chosen.result.enough_room;
  }

  function sessionLine(s) {
    const what = s.mode === "script" ? plural(s.clips, "clip", "clips") : "free speech";
    const state = s.state === "already" ? "already added, skipped" : s.state === "aborted" ? "an earlier try was cut short, will be redone" : "will be added";
    return el("li", {}, el("strong", {}, s.label || s.id), ` · ${what} · ${minutes(s.seconds)} · ${state}`);
  }

  function renderPlan(name, r) {
    chosen = { name, result: r };
    const total = r.sessions.reduce((n, s) => n + s.seconds, 0);
    $("ack-plan-title").textContent = name;
    $("ack-plan-summary").textContent = `${plural(r.sessions.length, "session", "sessions")}, ${minutes(total)} of audio, made by ACK ${r.package.app_version || ""}. ` +
      "Every file was checked against its checksum, so it arrived complete and unchanged.";
    $("ack-plan-sessions").replaceChildren(...r.sessions.map(sessionLine));
    $("ack-plan-warnings").replaceChildren(...r.warnings.map((w) => el("li", {}, w)));
    $("ack-plan-warnings").hidden = r.warnings.length === 0;
    $("ack-go").textContent = r.to_import ? `Add ${plural(r.to_import, "recording", "recordings")}` : "Nothing new to add";
    $("ack-plan-room").textContent = !r.to_import ? "Everything in this package is already here."
      : r.enough_room ? `Needs about ${r.need_mb} MB while it is processed; ${r.free_mb} MB is free.`
        : `Not enough room: this needs about ${r.need_mb} MB and ${r.min_free_mb} MB is kept spare, but only ${r.free_mb} MB is free. Free some space and look again.`;
    $("ack-plan").hidden = false;
    setBusy(false);
  }

  function renderList(listing) {
    $("ack-where").textContent = `Packages are kept in ${listing.folder}. You can also copy a .zip file into that folder yourself and press Refresh. ` +
      "This program never deletes them.";
    const items = listing.packages.map((p) => el("li", { class: "take" },
      el("div", { class: "take-head" }, el("span", { class: "take-when" }, p.name), el("span", { class: "chip" }, fmtBytes(p.bytes))),
      el("p", {}, el("button", { type: "button", class: "btn small", "aria-label": `Look inside ${p.name}`, onclick: () => look(p.name) }, "Look inside"))));
    for (const p of listing.partial) {
      items.push(el("li", { class: "take" }, el("div", { class: "take-head" }, el("span", { class: "take-when" }, `${p.name} (unfinished upload)`),
        el("span", { class: "chip warn" }, fmtBytes(p.bytes))), el("p", { class: "hint" }, "Choose the same file again to carry on from where it stopped.")));
    }
    $("ack-list").replaceChildren(...items);
    $("ack-empty").hidden = items.length > 0;
  }

  async function refresh() {
    try {
      renderList(await api("/api/ack/incoming"));
    } catch (err) {
      $("ack-empty").hidden = false;
      $("ack-empty").textContent = err.status === 401 ? "Your PC didn't accept this browser." : "Can't reach your PC right now.";
    }
  }

  async function look(name) {
    if (busy) return;
    setBusy(true);
    chosen = null;
    $("ack-plan").hidden = true;
    $("ack-result").textContent = `Checking ${name}. A large package takes a while because every file is read and verified...`;
    try {
      renderPlan(name, await api("/api/ack/check", { method: "POST", body: { name } }));
      $("ack-result").textContent = "";
    } catch (err) {
      $("ack-result").textContent = `${err.message}`;
      setBusy(false);
    }
  }

  async function go() {
    if (busy || !chosen || !chosen.result.to_import) return;
    const { name, result } = chosen;
    const ok = await confirmDialog({
      title: "Add these recordings?",
      body: `This adds ${plural(result.to_import, "recording", "recordings")} from ${name} to your list. They are then decoded and transcribed by this PC, ` +
        "which takes a while. Nothing is deleted or changed: your package file stays exactly as it is, and anything you already added is skipped.",
      ok: "Add them",
    });
    if (!ok) return;
    setBusy(true);
    $("ack-result").textContent = "Adding the recordings...";
    try {
      const done = await api("/api/ack/import", { method: "POST", body: { name } });
      $("ack-result").textContent = done.created.length
        ? `Added ${plural(done.created.length, "recording", "recordings")}. They are being processed now and appear in the list above as they finish.`
        : "There was nothing new to add.";
      announce(done.created.length ? `Added ${plural(done.created.length, "recording", "recordings")} from ACK.` : "Nothing new to add.");
      chosen = null;
      $("ack-plan").hidden = true;
      if (onImported) onImported();
    } catch (err) {
      $("ack-result").textContent = `Nothing was added: ${err.message}`;
    } finally {
      setBusy(false);
    }
  }

  async function sendFile(file) {
    const name = file.name;
    let offset = 0;
    while (offset < file.size) {
      const end = Math.min(file.size, offset + PIECE);
      $("ack-upload").textContent = `Bringing ${name} onto your PC: ${Math.floor((100 * offset) / file.size)}%`;
      try {
        await api(`/api/ack/incoming/${encodeURIComponent(name)}?offset=${offset}`, { method: "PUT", body: file.slice(offset, end) });
        offset = end;
      } catch (err) {
        if (err.status === 409 && err.data && Number.isInteger(err.data.received) && err.data.received !== offset) {
          offset = err.data.received;              // carry on from where the PC says it has got to
          continue;
        }
        throw err;
      }
    }
    await api(`/api/ack/incoming/${encodeURIComponent(name)}/done`, { method: "POST", body: { size: file.size } });
    return name;
  }

  $("ack-file").addEventListener("change", async () => {
    const file = $("ack-file").files[0];
    if (!file || busy) return;
    setBusy(true);
    $("ack-result").textContent = "";
    $("ack-plan").hidden = true;
    let name = null;
    try {
      name = await sendFile(file);
      $("ack-upload").textContent = `${name} is on your PC.`;
    } catch (err) {
      $("ack-upload").textContent = err.status === 409 && /already/.test(err.message)
        ? `A package called ${file.name} is already in the list below. Choose it there, or rename your copy first.`
        : `The file didn't arrive: ${err.message}`;
    } finally {
      $("ack-file").value = "";
      setBusy(false);
    }
    await refresh();
    if (name) look(name);
  });

  $("ack-refresh").addEventListener("click", refresh);
  $("ack-go").addEventListener("click", go);
  card.addEventListener("toggle", () => { if (card.open) refresh(); });
  return { refresh };
}
