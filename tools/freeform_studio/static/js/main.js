// SPDX-License-Identifier: GPL-3.0-or-later
import { initCapture } from "./capture.js";
import { initTakes } from "./takes.js";
import { watchConnection } from "./conn.js";

const takes = initTakes();
initCapture({ onChange: () => takes.refresh() });
const diskWarn = document.getElementById("diskwarn");
function showDisk(status) {
  const d = status.disk;
  if (!d || !d.known || !d.low) { diskWarn.hidden = true; return; }
  const gb = (d.free_mb / 1024).toFixed(1);
  diskWarn.textContent = d.critical
    ? `Your PC is almost out of disk space (${gb} GB free), so it is refusing new audio. Whatever you record stays on this phone and is sent once you free some space.`
    : `Your PC has about ${gb} GB of disk space left, enough for roughly ${d.hours_left} hours of recording. Free some space soon.`;
  diskWarn.hidden = false;
}
watchConnection(document.getElementById("conn"),
  "Can't reach your PC. Recording still works if it was already started; sending resumes when you're back.", { onStatus: showDisk });
