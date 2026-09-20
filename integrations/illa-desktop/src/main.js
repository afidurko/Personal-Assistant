const { app, BrowserWindow, shell } = require("electron");
const path = require("path");

const DEFAULT_URL = "http://127.0.0.1:48080";

function targetUrl() {
  const raw = (process.env.ILLA_DESKTOP_URL || DEFAULT_URL).trim();
  try {
    const u = new URL(raw);
    if (u.protocol !== "http:" && u.protocol !== "https:") {
      throw new Error("unsupported protocol");
    }
    return u.toString();
  } catch {
    console.error(`[illa-desktop] invalid ILLA_DESKTOP_URL=${raw}; falling back to ${DEFAULT_URL}`);
    return DEFAULT_URL;
  }
}

function createWindow() {
  const win = new BrowserWindow({
    width: 1440,
    height: 900,
    minWidth: 960,
    minHeight: 640,
    title: "ILLA Builder",
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });

  win.loadURL(targetUrl());

  win.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
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
