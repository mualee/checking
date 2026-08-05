# Deploy backend ໃສ່ AWS EC2 (t3.micro, ຟຣີ) + nginx + TLS

Backend FastAPI ຣັນຢູ່ EC2 ຫຼັງ nginx (HTTPS), frontend ຢູ່ Vercel, ຂໍ້ມູນຢູ່ Firebase.

## ຕ້ອງມີກ່ອນ
- ບັນຊີ AWS + ບັດສາກົນ
- **ຊື່ domain** ຊີ້ໄປ EC2 (ຈຳເປັນສຳລັບ TLS — Let's Encrypt ບໍ່ອອກ cert ໃຫ້ IP ເປົ່າ)
  - ຖ້າຍັງບໍ່ມີ: ໃຊ້ **DuckDNS** ຟຣີ ([duckdns.org](https://www.duckdns.org)) ໄດ້ subdomain ເຊັ່ນ `myapp.duckdns.org`

---

## 1️⃣ ສ້າງ EC2 instance
1. AWS Console → **EC2 → Launch instance**
2. **AMI:** Ubuntu Server 24.04 LTS
3. **Type:** `t3.micro` (ຫຼື `t2.micro`) — Free tier
4. **Key pair:** ສ້າງໃໝ່, ດາວໂຫລດ `.pem` (ໄວ້ SSH)
5. **Security group** — ເປີດ:
   - SSH (22) — ຈາກ IP ຂອງທ່ານ
   - HTTP (80) — Anywhere
   - HTTPS (443) — Anywhere
6. Launch

## 2️⃣ Elastic IP (ໃຫ້ IP ບໍ່ປ່ຽນ)
1. EC2 → **Elastic IPs → Allocate** → **Associate** ໃສ່ instance
2. ຈື່ IP ນີ້ (ເຊັ່ນ `13.212.x.x`)

## 3️⃣ ຊີ້ domain ໄປ IP
- ໃນ DNS ຂອງ domain (ຫຼື DuckDNS): ຕັ້ງ **A record** `api.yourdomain.com` → Elastic IP
- ລໍ 2-5 ນາທີໃຫ້ DNS ອັບເດດ

## 4️⃣ SSH ເຂົ້າ server
```powershell
ssh -i "path\to\key.pem" ubuntu@<Elastic-IP>
```

## 5️⃣ ເອົາ code ຂຶ້ນ server
ວິທີງ່າຍ (repo private → ໃຊ້ Personal Access Token ຫຼື deploy key):
```bash
sudo apt-get update && sudo apt-get install -y git
git clone https://github.com/mualee/<repo>.git
cd <repo>/deploy
```

## 6️⃣ ສ້າງ 2 ໄຟລ໌ລັບ ຢູ່ server (ບໍ່ໄດ້ມາຈາກ git)
```bash
# (ກ) env
cp .env.example .env
nano .env          # ແກ້ CORS_ORIGINS ໃຫ້ເປັນ domain Vercel ຂອງທ່ານ

# (ຂ) Firebase service account
nano service-account.json   # paste ເນື້ອຫາ JSON key ໃສ່ ແລ້ວ save
```

## 7️⃣ ຣັນ script ຕິດຕັ້ງ (ອັດຕະໂນມັດ)
```bash
chmod +x setup-ec2.sh
./setup-ec2.sh api.yourdomain.com you@email.com
```
Script ນີ້: ຕິດຕັ້ງ Docker+nginx+certbot → build & run backend → ຕັ້ງ nginx → ຂໍ TLS cert.

## 8️⃣ ທົດສອບ
```bash
curl https://api.yourdomain.com/health
# {"status":"ok"}
```

## 9️⃣ ຕໍ່ frontend (Vercel) ເຂົ້າ backend
ໃນ Vercel → project → Settings → Environment Variables:
- `VITE_API_BASE=https://api.yourdomain.com`
- (`VITE_FIREBASE_*` ຄືເກົ່າ, `VITE_AUTH_EMULATOR_HOST` ວ່າງ)

ແລ້ວ **Redeploy** frontend ຢູ່ Vercel.

## 🔟 admin user
ທ່ານ**ມີ admin ຢູ່ແລ້ວ**: `mualee072@gmail.com` — login ໄດ້ເລີຍ.

ຖ້າຢາກເພີ່ມ admin ໃໝ່, ຣັນ script **ຢູ່ເຄື່ອງ dev ຂອງທ່ານ** (ບ່ອນທີ່ມີ `.venv` + service account), ບໍ່ແມ່ນຢູ່ EC2:
```powershell
cd D:\not_me\backend
..\.venv\Scripts\python.exe ..\scripts\seed_prod_admin.py new@email.com "password" "Name"
```
> ຈື່: doc `users/` ຕ້ອງໃຊ້ **ID = Auth UID** (script ຈັດການໃຫ້ຖືກອັດຕະໂນມັດ).

---

## ບຳລຸງຮັກສາ
| ຄຳສັ່ງ | ໜ້າທີ່ |
|---|---|
| `sudo docker compose logs -f api` | ເບິ່ງ log backend |
| `sudo docker compose up -d --build` | deploy ໃໝ່ຫຼັງ `git pull` |
| `sudo docker compose restart api` | restart backend |
| `sudo certbot renew` | ຕໍ່ອາຍຸ TLS (ອັດຕະໂນມັດຢູ່ແລ້ວ) |

## ⚠️ ຄວາມປອດໄພ
- `deploy/.env` ແລະ `deploy/service-account.json` — **ຢູ່ server ເທົ່ານັ້ນ**, ບໍ່ commit (gitignored ✅)
- ຢ່າລືມ **ປ່ຽນ service account key ໃໝ່** (ອັນເກົ່າ paste ໃນ chat ແລ້ວ)
- t3.micro ພຽງພໍສຳລັບ traffic ຕ່ຳ; ຖ້າ PDF ໃຫຍ່/ຫຼາຍ ໃຫ້ຂຶ້ນ t3.small
