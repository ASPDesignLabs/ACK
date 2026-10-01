// SPDX-License-Identifier: GPL-3.0-or-later
// Thin fetch wrapper. Network failures throw a TypeError with no .status (callers treat that as "retry later").
export async function api(path, { method = "GET", body, headers = {} } = {}) {
  const opts = { method, headers: { ...headers }, credentials: "same-origin" };
  if (body !== undefined) {
    if (body instanceof Blob) {
      opts.body = body;
    } else {
      opts.body = JSON.stringify(body);
      opts.headers["content-type"] = "application/json";
    }
  }
  const res = await fetch(path, opts);
  let data = null;
  try { data = await res.json(); } catch (_) { /* no body */ }
  if (!res.ok) {
    const err = new Error((data && data.error) || `HTTP ${res.status}`);
    err.status = res.status;
    err.data = data;
    throw err;
  }
  return data;
}

export function el(tag, attrs = {}, ...kids) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") node.className = v;
    else if (k.startsWith("on")) node.addEventListener(k.slice(2), v);
    else if (v !== false && v != null) node.setAttribute(k, v === true ? "" : v);
  }
  for (const kid of kids.flat()) node.append(kid instanceof Node ? kid : document.createTextNode(String(kid)));
  return node;
}

export function fmtClock(seconds) {
  const s = Math.max(0, Math.floor(seconds));
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), r = s % 60;
  const mm = String(m).padStart(2, "0"), ss = String(r).padStart(2, "0");
  return h ? `${h}:${mm}:${ss}` : `${mm}:${ss}`;
}

export function fmtBytes(n) {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(0)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
}
