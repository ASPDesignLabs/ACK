// SPDX-License-Identifier: GPL-3.0-or-later
import { api, fmtBytes } from "./api.js";

const plural = (n, one, many) => `${n} ${n === 1 ? one : many}`;
const gb = (mb) => (mb / 1024).toFixed(mb >= 10240 ? 0 : 1);

function ago(hours) {
  if (hours < 0.05) return "just now";
  if (hours < 1) return `${plural(Math.round(hours * 60), "minute", "minutes")} ago`;
  if (hours < 48) return `${plural(Math.round(hours), "hour", "hours")} ago`;
  return `${plural(Math.round(hours / 24), "day", "days")} ago`;
}

// "Status and safety": disk space, backups, and the speech model's memory, in plain words, with the two things you can do about them.
export function initStatusCard({ announce }) {
  const $ = (id) => document.getElementById(id);
  let timer = null;
  let busy = false;

  function renderDisk(d) {
    if (!d || !d.known) { $("st-disk").textContent = "Free space couldn't be measured."; return; }
    const base = `${gb(d.free_mb)} GB free of ${gb(d.total_mb)} GB. About ${d.hours_left} hours of recording fit.`;
    $("st-disk").textContent = d.critical ? `Almost full: new audio is being refused until there is room. ${base}`
      : d.low ? `Getting low: free some space soon. ${base}` : base;
  }

  function renderBackup(b) {
    const go = $("st-backup-go");
    if (!b.enabled) {
      $("st-backup").textContent = "Backups aren't set up. Start the server with --backup-dir to choose where they go.";
      $("st-backup-where").textContent = "";
      go.disabled = true;
      return;
    }
    go.disabled = busy || b.running;
    if (b.last) {
      const old = b.age_hours > 168 && b.takes_present;
      $("st-backup").textContent = `Last backup ${ago(b.age_hours)} (${fmtBytes(b.last.size)}, ${plural(b.last.takes ?? 0, "recording", "recordings")}).` +
        `${old ? " That is more than a week ago, so a fresh one is a good idea." : ""}`;
    } else {
      $("st-backup").textContent = b.takes_present ? "No backup yet. Your recordings exist only on this PC, so back them up when you can."
        : "Nothing to back up yet.";
    }
    const auto = b.auto.enabled ? `Automatic: every ${b.auto.every_hours} hours, only when something has changed.` : "Automatic backups are off.";
    $("st-backup-where").textContent = `Kept in ${b.dir}. ${auto}${b.error ? ` The last attempt failed: ${b.error}` : ""}`;
  }

  function renderModel(a) {
    $("st-model").textContent = `${a.model} on ${a.device}${a.engine === "fake" ? " (test mode)" : ""}: ${a.loaded ? "loaded in memory." : "not in memory right now."}`;
    $("st-model-free").disabled = busy || !a.loaded;
  }

  async function refresh() {
    clearTimeout(timer);
    try {
      const [status, backup] = await Promise.all([api("/api/status"), api("/api/backup")]);
      renderDisk(status.disk);
      renderBackup(backup);
      renderModel(status.asr);
    } catch (err) {
      $("st-disk").textContent = err.status === 401 ? "Your PC didn't accept this phone." : "Can't reach your PC right now.";
    }
    timer = setTimeout(refresh, document.hidden ? 60000 : 15000);
  }

  $("st-backup-go").addEventListener("click", async () => {
    busy = true;
    $("st-backup-go").disabled = true;
    $("st-backup-result").textContent = "Backing up and then checking the copy...";
    try {
      const r = await api("/api/backup", { method: "POST" });
      $("st-backup-result").textContent = r.skipped ? r.reason
        : `Backed up ${plural(r.takes, "recording", "recordings")} (${fmtBytes(r.archive_bytes)}), then read the copy back to check it.` +
          `${r.pruned.length ? ` ${plural(r.pruned.length, "older backup was", "older backups were")} removed by the keep rule.` : ""}`;
      announce(r.skipped ? "Nothing has changed since the last backup." : "Backup finished and checked.");
    } catch (err) {
      $("st-backup-result").textContent = `Nothing was backed up: ${err.message}`;
    } finally {
      busy = false;
      refresh();
    }
  });

  $("st-model-free").addEventListener("click", async () => {
    busy = true;
    $("st-model-free").disabled = true;
    try {
      await api("/api/asr/release", { method: "POST" });
      $("st-model-result").textContent = "Freed. It loads again by itself the next time a recording needs it.";
      announce("Speech recognition memory freed.");
    } catch (err) {
      $("st-model-result").textContent = err.status === 409 ? "A recording is being processed right now. Try again when it finishes." : `Couldn't free it: ${err.message}`;
    } finally {
      busy = false;
      refresh();
    }
  });

  document.addEventListener("visibilitychange", () => { if (!document.hidden) refresh(); });
  refresh();
  return { refresh };
}
