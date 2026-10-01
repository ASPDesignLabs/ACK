import { api, el } from "./api.js";

const plural = (n, one, many) => `${n} ${n === 1 ? one : many}`;

// The "Training clips" card: shows what exporting the approved pieces would do, asks, then does it. `takeId` limits it
// to one recording (null means every recording). `ensureSaved()` resolves true once the latest edits are on the PC.
export function initExportCard({ takeId, ensureSaved, confirmDialog, announce }) {
  const $ = (id) => document.getElementById(id);
  const path = takeId ? `/api/takes/${takeId}/export` : "/api/export";
  const card = $("exportcard");
  let plan = null;
  let busy = false;

  function setBusy(on) {
    busy = on;
    $("export-check").disabled = on;
    $("export-go").disabled = on || !plan || plan.changes === 0;
  }

  function describe(p) {
    const c = p.counts;
    const changes = c.new + c.updated + c.retired;
    const parts = [];
    if (c.new) parts.push(`${plural(c.new, "new clip", "new clips")} to write`);
    if (c.updated) parts.push(`${plural(c.updated, "clip", "clips")} to replace with a newer version`);
    if (c.retired) parts.push(`${plural(c.retired, "clip", "clips")} that no longer qualify, to move aside`);
    if (c.unchanged) parts.push(`${plural(c.unchanged, "clip", "clips")} already up to date`);
    let text = parts.length ? `${parts.join(", ")}.` : "Nothing is approved yet that could be exported.";
    if (!changes && c.unchanged) text = `Everything approved is already exported (${plural(c.unchanged, "clip", "clips")}).`;
    const secs = p.seconds_after;
    const amount = secs < 60 ? plural(Math.round(secs), "second", "seconds") : `${(secs / 60).toFixed(1)} minutes`;
    return { changes, text: secs > 0 ? `${text} The folder would hold ${amount} of speech.` : text };
  }

  function render(p) {
    const d = describe(p);
    plan = { ...p, changes: d.changes };
    $("export-summary").textContent = d.text;
    const c = p.counts;
    $("export-go").textContent = d.changes ? `Export (${c.new} new, ${c.updated} replaced, ${c.retired} moved aside)` : "Nothing to export";
    $("export-go").disabled = d.changes === 0;
    const items = [];
    if (c.left_out) {
      items.push(el("p", { class: "hint" }, `${plural(c.left_out, "approved piece is", "approved pieces are")} not included:`));
      items.push(el("ul", { class: "reasons" }, ...Object.entries(p.left_out_by_reason).map(([reason, n]) => el("li", {}, el("strong", {}, String(n)), ` ${reason}`))));
      items.push(el("details", {}, el("summary", {}, "Show those pieces"),
        el("ul", { class: "reasons" }, ...p.left_out.map((e) => el("li", {}, `[${e.reason}] ${e.text || "(no text)"}`)))));
    }
    if (c.retired) {
      items.push(el("details", {}, el("summary", {}, `Show the ${plural(c.retired, "clip", "clips")} to move aside`),
        el("ul", { class: "reasons" }, ...p.retire.map((r) => el("li", {}, `[${r.why}] ${r.text || r.stem}`)))));
    }
    for (const t of p.skipped_takes) items.push(el("p", { class: "hint" }, `A recording (${t.take}) is ${t.status}, so it was skipped: only finished recordings are exported.`));
    $("export-details").replaceChildren(...items);
  }

  async function check({ quiet = false } = {}) {
    if (busy) return;
    setBusy(true);
    if (!quiet) $("export-summary").textContent = "Checking what can be exported...";
    $("export-result").textContent = quiet ? $("export-result").textContent : "";
    try {
      if (!(await ensureSaved())) {
        plan = null;
        $("export-summary").textContent = "Your latest changes haven't reached your PC yet, so this can't be checked. Try again when it says all changes are saved.";
        return;
      }
      render(await api(path));
    } catch (err) {
      plan = null;
      $("export-summary").textContent = err.status === 401 ? "Your PC didn't accept this phone." : `Couldn't check: ${err.message}`;
      $("export-go").textContent = "Export";
    } finally {
      setBusy(false);
    }
  }

  async function go() {
    if (busy || !plan || !plan.changes) return;
    const c = plan.counts;
    const aside = c.updated + c.retired;
    const ok = await confirmDialog({
      title: "Write these training clips?",
      body: `This writes ${plural(c.new + c.updated, "clip", "clips")} into ${plan.folder_name.replace(/-/g, "\u2011")}` +
        `${aside ? `, and moves ${plural(aside, "older clip", "older clips")} aside into a "retired" folder next to your recordings. Nothing is deleted` : ""}. ` +
        `Your recordings are never changed. You can run it again whenever you like. Full path: ${plan.folder}`,
      ok: "Export",
    });
    if (!ok) return;
    setBusy(true);
    $("export-summary").textContent = "Writing the clips...";
    try {
      if (!(await ensureSaved())) throw new Error("your latest changes haven't reached your PC yet");
      const done = await api(path, { method: "POST" });
      const d = done.counts;
      const message = `Wrote ${plural(d.new, "new clip", "new clips")}, replaced ${d.updated}, moved ${d.retired} aside` +
        `${done.retired_into ? ` (kept in ${done.retired_into})` : ""}. Folder: ${done.folder}`;
      $("export-result").textContent = message;
      announce(`Export finished. ${plural(d.new, "new clip", "new clips")} written.`);
    } catch (err) {
      $("export-result").textContent = `Nothing more was written: ${err.message}`;
    } finally {
      setBusy(false);
    }
    await check({ quiet: true });
  }

  $("export-check").addEventListener("click", () => check());
  $("export-go").addEventListener("click", go);
  card.addEventListener("toggle", () => { if (card.open && !plan) check(); });
  return { check };
}
