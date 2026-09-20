/**
 * Pure URL + offline-page helpers for ILLA desktop (testable without Electron).
 */
"use strict";

const DEFAULT_SELF_HOST = "http://127.0.0.1:3000/";
const CLOUD_URL = "https://cloud.illacloud.com/";
const PIN = "26.16.1";
const APP_ID = "com.afidurko.illa-builder";

function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function targetUrl(env) {
  const e = env || process.env;
  const mode = String(e.ILLA_DESKTOP_MODE || "self").trim().toLowerCase();
  if (mode === "cloud") return CLOUD_URL;

  const raw = String(e.ILLA_DESKTOP_URL || DEFAULT_SELF_HOST).trim();
  try {
    const u = new URL(raw);
    if (u.protocol !== "http:" && u.protocol !== "https:") {
      throw new Error("unsupported protocol");
    }
    return u.toString();
  } catch {
    return DEFAULT_SELF_HOST;
  }
}

function offlineHtml(url, detail) {
  const safeUrl = escapeHtml(url);
  const safeDetail = escapeHtml(detail);
  return `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>ILLA Builder — offline</title>
  <style>
    :root { color-scheme: light; }
    body { font: 16px/1.45 system-ui, sans-serif; margin: 0; min-height: 100vh;
      display: grid; place-items: center; background: #f4f6f8; color: #1a1d21; }
    main { max-width: 36rem; padding: 2rem; }
    h1 { font-size: 1.35rem; margin: 0 0 .5rem; }
    code { background: #e8ecf0; padding: .1rem .35rem; border-radius: 4px; }
    p { margin: .6rem 0; color: #3a4149; }
  </style>
</head>
<body>
  <main>
    <h1>ILLA Builder is not reachable</h1>
    <p>Tried <code>${safeUrl}</code>.</p>
    <p>${safeDetail}</p>
    <p>Start the web app (<code>pnpm dev</code> on port 3000), or set
      <code>ILLA_DESKTOP_URL</code> / <code>ILLA_DESKTOP_MODE=cloud</code>.</p>
  </main>
</body>
</html>`;
}

function assertPackageContract(pkg) {
  const errors = [];
  const eb = (pkg.devDependencies || {})["electron-builder"];
  if (eb !== PIN) errors.push(`electron-builder pin ${eb} != ${PIN}`);
  if ((pkg.build || {}).appId !== APP_ID) errors.push(`appId ${(pkg.build || {}).appId}`);
  const author = pkg.author;
  const email = typeof author === "object" ? author && author.email : null;
  if (!email || !String(email).includes("@")) errors.push("author.email required for .deb");
  const maintainer = ((pkg.build || {}).linux || {}).maintainer;
  if (!maintainer || !String(maintainer).includes("@")) {
    errors.push("build.linux.maintainer required for .deb");
  }
  return errors;
}

module.exports = {
  DEFAULT_SELF_HOST,
  CLOUD_URL,
  PIN,
  APP_ID,
  escapeHtml,
  targetUrl,
  offlineHtml,
  assertPackageContract,
};
