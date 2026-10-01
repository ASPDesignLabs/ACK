// SPDX-License-Identifier: GPL-3.0-or-later
// Loads the page's ES modules for testing. They import each other by relative path, so they are copied to a temporary
// folder with a package.json that says "module", which works on any Node version (no package.json ships with the app).
import { copyFileSync, mkdtempSync, readdirSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const SRC = join(dirname(fileURLToPath(import.meta.url)), "../../static/js");
let dir = null;

export async function load(name) {
  if (!dir) {
    dir = mkdtempSync(join(tmpdir(), "fs-js-"));
    writeFileSync(join(dir, "package.json"), '{"type":"module"}');
    for (const f of readdirSync(SRC)) if (f.endsWith(".js")) copyFileSync(join(SRC, f), join(dir, f));
  }
  return import(pathToFileURL(join(dir, name)).href);
}
