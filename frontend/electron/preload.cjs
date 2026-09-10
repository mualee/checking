// Minimal, secure preload. Exposes a small flag + the backend API base (the main
// process picks a free port at launch and passes it via --api-base=...), without
// granting the renderer any Node access.
const { contextBridge } = require("electron");

const arg = process.argv.find((a) => a.startsWith("--api-base="));
const apiBase = arg ? arg.slice("--api-base=".length) : null;

contextBridge.exposeInMainWorld("desktop", {
  isElectron: true,
  platform: process.platform,
  apiBase, // e.g. "http://localhost:52344"; null in the plain web build
});
