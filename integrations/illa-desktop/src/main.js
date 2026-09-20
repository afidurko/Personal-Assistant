const { app, BrowserWindow, shell } = require("electron");
const path = require("path");
const { targetUrl, offlineHtml } = require("./url-contract");

function createWindow() {
  const url = targetUrl(process.env);
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
