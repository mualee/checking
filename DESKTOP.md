# Desktop app (fully local, offline)

The web app now also ships as a Windows desktop app (Electron). **Everything runs
on the local machine** — the React UI, the FastAPI backend, and all data. No
Firebase, no internet required.

- **Data** lives under the per-user app data dir (`%APPDATA%\Credit Statement Audit`
  in the packaged app; `frontend/.localdata` in dev): `data.json` (the store),
  `storage/` (uploaded PDFs + generated reports), `secret.key` (JWT signing key).
- **Auth** is local: email/password hashed with bcrypt, backend issues a JWT.
  On first run a default admin is created and written to `FIRST_RUN.txt`:
  - Email: `admin@local.app`   Password: `admin1234`  (change it in Settings)

## Architecture

```
Electron main (frontend/electron/main.cjs)
├── single-instance lock (only one copy runs → no data-dir clashes)
├── picks two FREE OS ports at launch (no fixed 8000/5173 → never collides)
├── spawns  backend.exe  (LOCAL_MODE=1, APP_DATA_DIR=<userData>, PORT=<free>)
│            └── FastAPI + uvicorn, disk-backed store, local JWT auth
│               (local mode CORS allows any origin; auth is a Bearer token)
└── serves  dist/ over http://localhost:<free>  →  window loads it
             (preload passes the backend URL to the renderer via --api-base=...)
```

In dev the ports are fixed (backend 8000, Vite 5173); only the packaged app uses
dynamic ports.

Local mode is toggled by `LOCAL_MODE=1`. In that mode `get_firestore_client()`
returns a JSON-persisted `FakeFirestoreClient` and Firebase is never imported.

## Run in development

Needs Python deps installed in `.venv` and Node deps in `frontend/`. One command
starts the backend, the web dev server, and Electron together:

```bash
cd frontend && npm run electron:dev
```

(Backend on :8000, Vite on :5173. Data goes to `frontend/.localdata`.)

## Build the installer (.exe)

Requires **Windows Developer Mode ON** (Settings → System → For developers) so
electron-builder can extract its toolchain — otherwise it fails on a symlink
permission error unrelated to this app.

```bash
cd frontend && npm run electron:build
```

This runs three steps: `backend:build` (PyInstaller → `backend/dist/backend/backend.exe`),
`build:electron` (Vite build pointing at localhost:8000), then electron-builder
(NSIS installer → `frontend/release/`). The backend exe is shipped as an
`extraResources` folder and launched by the app.

To test the packaged layout without making an installer: `npm run electron:pack`.

## Scanned PDFs (OCR)

Digital statement PDFs (with a text layer) are parsed directly by pdfplumber.
Scanned / printer PDFs are image-only, so on upload the pipeline auto-detects the
missing text layer and routes them through offline OCR
(`backend/app/services/ocr_extraction.py`, RapidOCR/onnxruntime — bundled, no
internet):

1. rasterize each page, detect the 6 table columns from the printed grid,
2. OCR the table body and bucket tokens into columns by x-position (isolated
   columns keep printed digits accurate; only `.dd`-shaped tokens count as money),
3. rebuild transactions keyed by the date column.

OCR is ~80% row-accurate on a real BCEL statement, so it is **assisted, not
trusted**: the running-balance check flags every row that doesn't reconcile, and
a review screen (`TransactionReview.tsx`) lets a person correct the highlighted
cells and re-validate (`POST …/revalidate`) before the report is produced. The
extracted rows are always saved first so they can be reviewed even when
validation fails.

## Notes

- The backend exe excludes `firebase_admin` / google-cloud / grpc (unused locally)
  and bundles data files for `pdfplumber`/`pdfminer`/`reportlab`/`python-docx`.
- After building, smoke-test the report pipeline (upload a statement PDF → run →
  download the DOCX) once in the packaged app to confirm the bundled PDF/DOCX
  data files resolve at runtime.
