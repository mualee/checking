# Deploy backend ຂຶ້ນ Render (ໄວທີ່ສຸດ ສຳລັບ demo)

Render ໃຫ້ HTTPS ອັດຕະໂນມັດ (`https://<name>.onrender.com`) — **ບໍ່ຕ້ອງ domain, nginx, ຫຼື TLS**.
Deploy ຈາກ GitHub ໂດຍກົງ. ໃຊ້ Docker (`backend/Dockerfile`).

## ກ່ອນເລີ່ມ
- Code ຕ້ອງຢູ່ **GitHub** ແລ້ວ (Render deploy ຈາກ repo)
- ມີໄຟລ໌ Firebase **service-account.json** (ເນື້ອຫາ JSON key)

---

## ຂັ້ນຕອນ

### 1️⃣ ສະໝັກ Render
[render.com](https://render.com) → Sign up ດ້ວຍ **GitHub** (ໃຫ້ສິດເຂົ້າ repo)

### 2️⃣ ສ້າງ service ຈາກ Blueprint
- Dashboard → **New +** → **Blueprint**
- ເລືອກ repo `mualee/<repo>` → Render ອ່ານ `render.yaml` ໃຫ້ເອງ
- ກົດ **Apply** → ມັນຈະສ້າງ service ຊື່ `credit-audit-api`

> ຫຼື ຖ້າບໍ່ໃຊ້ Blueprint: **New + → Web Service** → ເລືອກ repo → ຕັ້ງ
> Root Directory = `backend`, Runtime = **Docker**, Health Check Path = `/health`, Plan = **Free**

### 3️⃣ ເພີ່ມ Firebase key ເປັນ Secret File (ສຳຄັນ)
ໃນ service → **Environment** → ພາກ **Secret Files** → **Add Secret File**:
- **Filename:** `service-account.json`
- **Contents:** paste ເນື້ອຫາ JSON key ຂອງທ່ານໃສ່
- Save

> Render mount ໄຟລ໌ນີ້ໄວ້ທີ່ `/etc/secrets/service-account.json` — ຕົງກັບ
> `GOOGLE_APPLICATION_CREDENTIALS` ໃນ `render.yaml` ແລ້ວ.

### 4️⃣ ກວດ Environment variables
`render.yaml` ຕັ້ງໃຫ້ແລ້ວ (ENV=prod, project, bucket, CORS). ກວດຄືນວ່າມີ:
| key | value |
|---|---|
| `ENV` | `prod` |
| `GCP_PROJECT_ID` | `checking-734d6` |
| `STORAGE_BUCKET` | `checking-734d6.firebasestorage.app` |
| `GOOGLE_APPLICATION_CREDENTIALS` | `/etc/secrets/service-account.json` |
| `CORS_ORIGINS` | `https://checking.ssmilaos.com,http://localhost:5173` |

### 5️⃣ Deploy
Render build + deploy ອັດຕະໂນມັດ (2-4 ນາທີ). ໄດ້ URL ເຊັ່ນ:
```
https://credit-audit-api.onrender.com
```
ທົດສອບ:
```
https://credit-audit-api.onrender.com/health   ->  {"status":"ok"}
```

### 6️⃣ ບອກ frontend ໃຫ້ໃຊ້ URL ນີ້
- **Vercel:** ຕັ້ງ `VITE_API_BASE=https://credit-audit-api.onrender.com` → redeploy
- **ຫຼື demo ໃນເຄື່ອງ:** ໃນ `frontend/.env` ຕັ້ງ `VITE_API_BASE=https://credit-audit-api.onrender.com` → `npm run dev`

---

## ⚠️ ສຳລັບ demo — ຈື່ໄວ້
- **Free tier ຫຼັບຫຼັງ 15 ນາທີ ບໍ່ໃຊ້ງານ** → request ທຳອິດ cold start ~30-60 ວິນາທີ.
  **ກ່ອນ demo 2-3 ນາທີ, ເປີດ `/health` ໜຶ່ງເທື່ອ** ໃຫ້ມັນຕື່ນກ່ອນ.
- ຖ້າ demo ສຳຄັນ ຫຼື ບໍ່ຢາກ cold start → upgrade ເປັນ **Starter ($7/ເດືອນ)** ບໍ່ຫຼັບ.
- Log: service → **Logs** tab (ເບິ່ງ error realtime)
- Deploy ໃໝ່: push ຂຶ້ນ GitHub → Render auto-deploy (autoDeploy: true)

## admin user
ໃຊ້ admin ທີ່ມີ: **`mualee072@gmail.com`** (ຢູ່ Firebase project ຈິງແລ້ວ). Login ໄດ້ເລີຍ.

## ⚠️ ຄວາມປອດໄພ
ຢ່າລືມ **ປ່ຽນ service account key ໃໝ່** ກ່ອນໃຊ້ຈິງ (ອັນເກົ່າ paste ໃນ chat ແລ້ວ).
