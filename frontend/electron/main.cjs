// Electron main process. Wraps the built Vite/React app in a desktop window and
// runs the bundled FastAPI backend as a local child process — everything runs on
// the user's machine, offline.
//
// Ports: in the packaged app both the backend and the internal static server bind
// to OS-assigned free ports (never fixed 8000/5173), so multiple copies or other
// dev servers never collide. The chosen backend URL is handed to the renderer via
// the preload (--api-base=...). A single-instance lock prevents two copies writing
// the same data dir at once.
const { app, BrowserWindow, shell, dialog } = require("electron");
const path = require("node:path");
const http = require("node:http");
const net = require("node:net");
const fs = require("node:fs");
const { spawn } = require("node:child_process");

const DEV_APP_PORT = 5173; // vite dev server
const DEV_API_PORT = 8000; // dev backend (npm run dev:backend)
const DEV_SERVER_URL = process.env.VITE_DEV_SERVER_URL || `http://localhost:${DEV_APP_PORT}`;
const isDev = !app.isPackaged;

let backendProc = null;
let mainWindow = null;

const MIME = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".mjs": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".svg": "image/svg+xml",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".gif": "image/gif",
  ".ico": "image/x-icon",
  ".webp": "image/webp",
  ".woff": "font/woff",
  ".woff2": "font/woff2",
  ".ttf": "font/ttf",
  ".map": "application/json; charset=utf-8",
};

// Ask the OS for a free loopback port.
function getFreePort() {
  return new Promise((resolve, reject) => {
    const srv = net.createServer();
    srv.on("error", reject);
    srv.listen(0, "127.0.0.1", () => {
      const { port } = srv.address();
      srv.close(() => resolve(port));
    });
  });
}

// Serve the built SPA with index.html fallback so client-side routes resolve.
function startStaticServer(port) {
  const root = path.join(__dirname, "..", "dist");
  return new Promise((resolve, reject) => {
    const server = http.createServer((req, res) => {
      const urlPath = decodeURIComponent((req.url || "/").split("?")[0]);
      let filePath = path.join(root, urlPath);
      if (!filePath.startsWith(root)) {
        res.writeHead(403);
        res.end("Forbidden");
        return;
      }
      fs.stat(filePath, (err, stat) => {
        if (err || stat.isDirectory()) filePath = path.join(root, "index.html");
        fs.readFile(filePath, (readErr, data) => {
          if (readErr) {
            res.writeHead(404);
            res.end("Not found");
            return;
          }
          const type = MIME[path.extname(filePath).toLowerCase()] || "application/octet-stream";
          res.writeHead(200, { "Content-Type": type });
          res.end(data);
        });
      });
    });
    server.on("error", reject);
    server.listen(port, "127.0.0.1", () => resolve(server));
  });
}

// Poll GET /health until the backend answers or we time out.
function waitForBackend(port, timeoutMs = 30000) {
  const start = Date.now();
  return new Promise((resolve, reject) => {
    const tick = () => {
      const req = http.get(
        { host: "127.0.0.1", port, path: "/health", timeout: 1500 },
        (res) => {
          res.resume();
          if (res.statusCode && res.statusCode < 500) resolve();
          else retry();
        },
      );
      req.on("error", retry);
      req.on("timeout", () => {
        req.destroy();
        retry();
      });
    };
    const retry = () => {
      if (Date.now() - start > timeoutMs) reject(new Error("backend did not become ready"));
      else setTimeout(tick, 400);
    };
    tick();
  });
}

function startBackend(port) {
  const exe = path.join(process.resourcesPath, "backend", "backend.exe");
  backendProc = spawn(exe, [], {
    env: {
      ...process.env,
      LOCAL_MODE: "1",
      APP_DATA_DIR: app.getPath("userData"),
      PORT: String(port),
    },
    stdio: "ignore",
    windowsHide: true,
  });
  backendProc.on("error", (err) => {
    dialog.showErrorBox("Backend failed to start", String(err));
  });
}

function stopBackend() {
  if (backendProc && !backendProc.killed) {
    backendProc.kill();
    backendProc = null;
  }
}

function createWindow(startUrl, apiBase) {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 800,
    minWidth: 900,
    minHeight: 600,
    show: false,
    webPreferences: {
      preload: path.join(__dirname, "preload.cjs"),
      contextIsolation: true,
      nodeIntegration: false,
      additionalArguments: [`--api-base=${apiBase}`],
    },
  });
  mainWindow.once("ready-to-show", () => mainWindow.show());
  mainWindow.on("closed", () => {
    mainWindow = null;
  });
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    if (url.startsWith("http:") || url.startsWith("https:")) {
      shell.openExternal(url);
      return { action: "deny" };
    }
    return { action: "allow" };
  });
  mainWindow.loadURL(startUrl);
  if (isDev) mainWindow.webContents.openDevTools({ mode: "detach" });
}

async function bootstrap() {
  let startUrl = DEV_SERVER_URL;
  let apiBase = `http://localhost:${DEV_API_PORT}`;

  if (!isDev) {
    const apiPort = await getFreePort();
    apiBase = `http://localhost:${apiPort}`;
    startBackend(apiPort);
    try {
      await waitForBackend(apiPort);
    } catch (err) {
      dialog.showErrorBox("Startup error", "The local backend did not start.\n" + String(err));
    }
    try {
      const appPort = await getFreePort();
      await startStaticServer(appPort);
      startUrl = `http://localhost:${appPort}`;
    } catch (err) {
      startUrl = `file://${path.join(__dirname, "..", "dist", "index.html")}`;
    }
  }

  createWindow(startUrl, apiBase);
}

// Single instance: focus the existing window instead of launching a second copy
// (two copies would fight over the same data dir).
if (!app.requestSingleInstanceLock()) {
  app.quit();
} else {
  app.on("second-instance", () => {
    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore();
      mainWindow.focus();
    }
  });

  app.whenReady().then(() => {
    bootstrap();
    app.on("activate", () => {
      if (BrowserWindow.getAllWindows().length === 0) bootstrap();
    });
  });

  app.on("window-all-closed", () => {
    stopBackend();
    if (process.platform !== "darwin") app.quit();
  });
  app.on("before-quit", stopBackend);
  app.on("will-quit", stopBackend);
}
