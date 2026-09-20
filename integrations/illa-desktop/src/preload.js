const { contextBridge } = require("electron");

contextBridge.exposeInMainWorld("illaDesktop", {
  shell: "illa-desktop",
  packager: "electron-builder@26.16.1",
});
