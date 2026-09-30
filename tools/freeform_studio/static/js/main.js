import { api } from "./api.js";
import { initCapture } from "./capture.js";
import { initTakes } from "./takes.js";

const conn = document.getElementById("conn");
const takes = initTakes();
initCapture({ onChange: () => takes.refresh() });

async function ping() {
  try {
    const s = await api("/api/status");
    conn.textContent = `Connected to your PC. Speech recognition: ${s.asr.engine === "fake" ? "test mode" : s.asr.model}.`;
  } catch (err) {
    conn.textContent = err.status === 401
      ? "Your PC didn't accept this phone. Open the full link printed on your PC once more."
      : "Can't reach your PC. Recording still works if it was already started; sending resumes when you're back.";
  }
  setTimeout(ping, 6000);
}
ping();
