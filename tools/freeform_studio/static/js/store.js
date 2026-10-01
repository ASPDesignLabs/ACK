// SPDX-License-Identifier: GPL-3.0-or-later
// Phone-side safety net: each audio chunk is written here BEFORE it is sent, and removed only after the PC confirms
// it. If IndexedDB is unavailable (some private modes) everything still works, just without crash recovery.
const DB_NAME = "freeform-studio";
let dbPromise = null;

function open() {
  if (!dbPromise) {
    dbPromise = new Promise((resolve) => {
      if (!("indexedDB" in window)) return resolve(null);
      let req;
      try { req = indexedDB.open(DB_NAME, 1); } catch (_) { return resolve(null); }
      req.onupgradeneeded = () => {
        const db = req.result;
        db.createObjectStore("chunks", { keyPath: ["takeId", "index"] });
        db.createObjectStore("takes", { keyPath: "takeId" });
      };
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => resolve(null);
      req.onblocked = () => resolve(null);
    });
  }
  return dbPromise;
}

async function tx(storeName, mode, fn) {
  const db = await open();
  if (!db) return undefined;
  return new Promise((resolve, reject) => {
    const t = db.transaction(storeName, mode);
    const store = t.objectStore(storeName);
    let result;
    const r = fn(store);
    if (r) r.onsuccess = () => { result = r.result; };
    t.oncomplete = () => resolve(result);
    t.onerror = () => reject(t.error);
    t.onabort = () => reject(t.error);
  });
}

export const available = async () => (await open()) !== null;
export const putChunk = (takeId, index, blob) => tx("chunks", "readwrite", (s) => s.put({ takeId, index, blob }));
export const deleteChunk = (takeId, index) => tx("chunks", "readwrite", (s) => s.delete([takeId, index]));
export const listChunks = async (takeId) => {
  const all = (await tx("chunks", "readonly", (s) => s.getAll())) || [];
  return all.filter((c) => c.takeId === takeId).sort((a, b) => a.index - b.index);
};
export const putTake = (rec) => tx("takes", "readwrite", (s) => s.put(rec));
export const deleteTake = (takeId) => tx("takes", "readwrite", (s) => s.delete(takeId));
export const listTakes = async () => (await tx("takes", "readonly", (s) => s.getAll())) || [];
