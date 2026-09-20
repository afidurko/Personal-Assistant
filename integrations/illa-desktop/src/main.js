const { app, BrowserWindow, shell } = require("electron");
const path = require("path");

/** Vite `apps/builder` default (`pnpm/turbo dev`). Override with ILLA_DESKTOP_URL. */
const DEFAULT_SELF_HOST = "http://127.0.0.1:3000";
const CLOUD_URL = "https://cloud.illacloud.com";

function targetUrl() {
  const mode = (process.env.ILLA_DESKTOP_MODE || "self").trim().toLowerCase();
  if (mode === "cloud") return CLOUD_URL;

  const raw = (process.env.ILLA_DESKTOP_URL || DEFAULT_SELF_HOST).trim();
  try {
    const u = new URL(raw);
    if (u.protocol !== "http:" && u.protocol !== "https:") {
      throw new Error("unsupported protocol");
    }
    return u.toString();
  } catch {
    console.error(
      `[illa-desktop] invalid ILLA_DESKTOP_URL=${raw}; falling back to ${DEFAULT_SELF_HOST}`
    );
    return DEFAULT_SELF_HOST;
  }
}

function offlineHtml(url, detail) {
  const safeUrl = String(url).replace(/[<>&"]/g, "");
  const safeDetail = String(detail || "").replace(/[<>&]/g, "");
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

function createWindow() {
  const url = targetUrl();
  const win = new BrowserWindow({
    width: 1440,
    height: 900,
    minWidth: 960,
    minHeight: 640,
    title: "ILLA Builder",
    icon: path.join(__dirname, "..", "build", "icon.png"),
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });

  win.loadURL(url).catch((err) => {
    win.loadURL(
      `data:text/html;charset=utf-8,${encodeURIComponent(
        offlineHtml(url, err && err.message)
      )}`
    );
  });

  win.webContents.on("did-fail-load", (_e, code, desc, validatedURL, isMainFrame) => {
    if (!isMainFrame || code === -3) return; // -3 = aborted
    win.loadURL(
      `data:text/html;charset=utf-8,${encodeURIComponent(
        offlineHtml(validatedURL || url, `${desc} (${code})`)
      )}`
    );
  });

  win.webContents.setWindowOpenHandler(({ url: openUrl }) => {
    shell.openExternal(openUrl);
    return { action: "deny" };
  });
}

app.whenReady().then(() => {
  createWindow();
  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});
