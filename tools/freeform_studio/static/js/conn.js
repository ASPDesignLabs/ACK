import { api } from "./api.js";

// Keeps a status line up to date: whether this page can reach the PC, in plain words.
export function watchConnection(node, offlineText, { brief = false } = {}) {
  async function ping() {
    try {
      const s = await api("/api/status");
      node.textContent = brief ? "Connected to your PC." : `Connected to your PC. Speech recognition: ${s.asr.engine === "fake" ? "test mode" : s.asr.model}.`;
    } catch (err) {
      node.textContent = err.status === 401
        ? "Your PC didn't accept this phone. Open the full link printed on your PC once more."
        : offlineText;
    }
    setTimeout(ping, 6000);
  }
  ping();
}
