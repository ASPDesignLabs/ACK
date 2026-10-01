import { initCapture } from "./capture.js";
import { initTakes } from "./takes.js";
import { watchConnection } from "./conn.js";

const takes = initTakes();
initCapture({ onChange: () => takes.refresh() });
watchConnection(document.getElementById("conn"),
  "Can't reach your PC. Recording still works if it was already started; sending resumes when you're back.");
