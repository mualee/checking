# Credit Statement Audit System — Backend

Backend for auditing customer bank-statement PDFs: extract transactions, **mandatorily
re-validate the running balance chain**, compute three summary tables (monthly summary,
top-3 income months, and recurring fixed obligations), generate a Lao-language Word
report, and route to a manager/admin for approval. All actions are audit-logged.

**Table 3 (recurring obligations):** groups debits by exact amount, keeps months with
exactly one such debit (a month with duplicates is excluded as a coincidental round
number), finds runs of consecutive months, and reports runs of ≥3 months (top 10 by
length). Logic in `app/services/calculations.py::build_table3`.

**Stack:** FastAPI + firebase-admin, Firestore, Firebase Storage, pdfplumber, python-docx.
Runs on Cloud Run in prod; the Firebase Emulator Suite for local dev.

The React SPA frontend lives in [`frontend/`](frontend/README.md) (11 pages, TanStack
Router/Query, Zustand, Firebase Auth, shadcn-style UI). It proxies `/api/*` to this backend.

---

## Project layout

```
firebase.json .firebaserc firestore.rules storage.rules firestore.indexes.json
backend/app/
  core/        config.py firebase.py constants.py
  models/      user customer statement transaction approval audit_log
  dependencies/ auth.py access.py
  routers/     health customers statements users audit_logs
  services/    calculations pdf_extraction docx_report storage_service
               pipeline statement_service customer_service user_service audit_service
  utils/       money.py lao_dates.py
backend/Dockerfile backend/requirements.txt
tests/  unit/ (no emulator) integration/ (needs emulator) fixtures/*.pdf conftest.py
scripts/ build_fixtures.py seed_emulator_users.py prove_emulator_wiring.py
         smoke_test_pipeline.py start_emulators.ps1
```

## Endpoints

`GET /health` · `GET/POST /customers` · `GET/PUT /customers/{id}` ·
`GET/POST /customers/{id}/statements` · `GET /customers/{id}/statements/{sid}` ·
`.../transactions` · `.../report` · `POST .../approve` (manager/admin) ·
`GET /audit-logs` (manager/admin) · `GET/POST /users` · `PATCH /users/{uid}` (admin).

**Access rules:** officer sees a customer/statement if `createdBy == uid` OR
`uploadedBy == uid`; manager/admin see all. Customer create/edit allowed for
officer(own)/manager/admin. Approvals: manager/admin only.

---

## Setup

```bash
py -3.13 -m venv .venv
.venv/Scripts/python.exe -m pip install -r backend/requirements.txt
cp backend/.env.example backend/.env      # defaults already target the emulators
```

## Run the tests

Unit tests need **no** emulator (calculations, extraction, Word report, access logic):

```bash
.venv/Scripts/python.exe -m pytest tests/unit -q      # 40 passing
```

Integration tests need the Emulator Suite running (see caveat below); they **skip**
cleanly when it is not reachable:

```bash
./scripts/start_emulators.ps1                          # terminal 1
.venv/Scripts/python.exe scripts/seed_emulator_users.py
.venv/Scripts/python.exe -m pytest tests/integration -q
```

## Run the app + end-to-end smoke test

```bash
# terminal 1: emulators
firebase emulators:start --only auth,firestore,storage
# terminal 2: API
cd backend && ../.venv/Scripts/uvicorn app.main:app --port 8000
# terminal 3: full flow (login→customer→upload→poll→report→approve→audit)
.venv/Scripts/python.exe scripts/seed_emulator_users.py
.venv/Scripts/python.exe scripts/smoke_test_pipeline.py
```

Regenerate the fixture PDFs (also prints the ground-truth table values):

```bash
.venv/Scripts/python.exe scripts/build_fixtures.py
```

---

## Running the full stack locally on THIS machine (Firestore-emulator-free)

The Java Firestore emulator can't start here (see the loopback note below), so dev mode
supports **emulator-free backends**, and the whole stack has been verified end-to-end
this way: login → dashboard → create customer → upload PDF → process → Table 1/2 →
download Word → approve → audit logs.

`backend/.env` for this host:
```
ENV=dev
FIRESTORE_BACKEND=memory      # in-process Firestore shim (app/core/fake_firestore.py)
STORAGE_BACKEND=local         # writes to backend/.devstorage instead of the Storage emulator
SEED_DEMO_USERS=true          # seeds officer/manager/admin on startup
FIREBASE_AUTH_EMULATOR_HOST=localhost:9099
```

Start it (three terminals):
```bash
firebase emulators:start --only auth        # Node-based, starts fine (Firestore/Storage are Java → skip)
cd backend && ../.venv/Scripts/uvicorn app.main:app --port 8000
cd frontend && npm run dev                  # http://localhost:5173
```
Sign in as `officer@example.com` / `manager@example.com` / `admin@example.com`, password
`Passw0rd!`. Data lives in memory (reset on backend restart); reports/JSON under
`backend/.devstorage/`.

For a real deployment, set `ENV=prod` with real Firebase credentials — `firestore_backend`
and `storage_backend` are ignored in prod, which uses real Firestore + GCS + signed URLs.

## ⚠️ Underlying host issue: the Java Firebase emulators won't start (loopback)

The Firestore emulator (and **any** Java NIO service) crashes on this host with:

```
java.io.IOException: Unable to establish loopback connection
Caused by: java.net.SocketException: Invalid argument: connect
    at sun.nio.ch.PipeImpl$Initializer$LoopbackConnector.run
```

**This is a machine-wide OS/JVM networking issue, not a project bug.** Confirmed:

- A trivial Java program that only calls `Selector.open()` fails identically.
- Reproduces on both Android Studio's JBR 21 and a fresh Temurin 21 (and 17).
- Python loopback on 127.0.0.1 works fine, so the FastAPI app itself is unaffected.

The JDK's Windows selector (`WEPollSelectorImpl`) cannot create its loopback self-pipe.
Typical causes and fixes (need a local admin / host owner):

1. **Endpoint-security / firewall software** blocking localhost self-connections —
   whitelist `java.exe` for loopback, or temporarily disable to confirm.
2. **Corrupted Winsock / loopback**: run `netsh winsock reset` in an elevated prompt,
   then reboot.
3. Ensure IPv6 loopback `::1` and IPv4 `127.0.0.1` both accept local connections.

Once `java -version` machines can run `Selector.open()` (verify with the snippet above),
`firebase emulators:start` will boot and the integration + smoke tests will run as-is.
firebase-tools requires **JDK 21+** (Temurin 21 is installed at
`C:\Program Files\Eclipse Adoptium\jdk-21.0.11.10-hotspot`).

### Alternative if the host can't be fixed
Point the backend at a **real** Firebase project instead of the emulator: set
`ENV=prod`, `GCP_PROJECT_ID`, `STORAGE_BUCKET`, and `GOOGLE_APPLICATION_CREDENTIALS`
in `backend/.env`. No application code changes are needed — `core/firebase.py`
branches on `ENV`.

---

## Verification status

| Area | Status |
|---|---|
| Calculations (validation gate, Table 1/2) | ✅ unit-tested (fixture ground truth) |
| PDF extraction incl. wrapped descriptions | ✅ unit-tested against fixtures |
| Word report (Phetsarath rFonts, shading, total-row) | ✅ unit-tested (structure/attrs) |
| Access control (officer/manager/admin) | ✅ unit-tested (mocked Firestore) |
| Routing + auth guards (401 without token) | ✅ verified via TestClient |
| Full API integration (auth, CRUD, pipeline, approve, audit) | ✅ verified live — memory Firestore + Auth emulator + local storage |
| Frontend ↔ backend end-to-end (login → dashboard → upload → report) | ✅ verified in-browser |
| Real Firestore/Storage Java emulators | ⛔ can't start on this host (Java loopback issue below) |
| Dockerfile | ⚠️ written, unverified (no Docker locally) |
