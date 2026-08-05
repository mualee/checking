# Credit Statement Audit — Frontend

React SPA for the credit-statement audit system.

**Stack:** React 18 + TypeScript + Vite · TanStack Router (code-based) · TanStack Query ·
Zustand · Firebase Auth (Web SDK) · react-hook-form + zod · Tailwind + shadcn-style UI ·
lucide-react. UI copy is in Lao.

## Pages (11)

| Route | Purpose | Access |
|---|---|---|
| `/login` | Firebase email+password sign-in | public |
| `/dashboard` | overview + quick stats | all roles |
| `/customers` | list + search/filter | all (officer scoped) |
| `/customers/new` | create customer | all |
| `/customers/:id` | detail + statements + inline edit | owner/manager/admin |
| `/customers/:id/statements/new` | drag & drop PDF upload | all |
| `/customers/:id/statements/:sid` | Table 1/2/3, status (auto-polls), validation, Word download | owner/manager/admin |
| `/customers/:id/statements/:sid/approve` | approve form + decision history | view: all; decide: manager/admin |
| `/audit-logs` | filterable log viewer | manager/admin |
| `/users` | user CRUD, role, activate/deactivate | admin |
| `/settings` | change password, language | self |

A single `AppShell` (sidebar + header) wraps all authenticated pages and shows/hides
menu items by role from the Zustand store. Role is loaded from `GET /users/me` after
login (Firestore is deny-by-default for clients — all access is backend-mediated).

## Setup & run

```bash
cd frontend
npm install
cp .env.example .env         # defaults target the Auth emulator + Vite proxy to :8000
npm run dev                  # http://localhost:5173
```

`vite.config.ts` proxies `/api/*` → `http://localhost:8000` (the FastAPI backend).
`VITE_AUTH_EMULATOR_HOST` points Firebase Auth at the local emulator; clear it to use
real Firebase.

Full stack locally (all three):
```bash
firebase emulators:start --only auth,firestore,storage   # needs the JDK loopback fix (see ../README.md)
cd backend && ../.venv/Scripts/uvicorn app.main:app --port 8000
cd frontend && npm run dev
```

## Build / typecheck

```bash
npm run typecheck    # tsc -b, passes clean
npm run build        # tsc -b && vite build, passes clean
```

## Verification status

- ✅ `tsc -b` and `vite build` pass with no errors.
- ✅ Dev server renders; `/` redirects to `/login`; login card + Lao UI render; no console errors.
- ✅ react-hook-form + zod validation verified in-browser.
- ⛔ Authenticated flows (dashboard/customers/statements/approve/users/audit-logs) require the
  backend API + Firebase Auth emulator, which is blocked by the host Java-loopback issue
  documented in [../README.md](../README.md). Once emulators run, seed users with
  `scripts/seed_emulator_users.py` and sign in (e.g. `officer@example.com` / `Passw0rd!`).
