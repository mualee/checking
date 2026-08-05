#!/usr/bin/env bash
# One-shot EC2 setup: Docker + nginx + Let's Encrypt TLS for the FastAPI backend.
# Run ON the EC2 instance (Ubuntu 22.04/24.04), from the deploy/ folder:
#
#   ./setup-ec2.sh api.yourdomain.com you@email.com
#
# Prerequisites already done:
#   - deploy/.env               (copied from .env.example, filled in)
#   - deploy/service-account.json  (your Firebase key)
#   - DNS A record: api.yourdomain.com -> this instance's public (Elastic) IP
set -euo pipefail

DOMAIN="${1:?usage: setup-ec2.sh <domain> <email>}"
EMAIL="${2:?usage: setup-ec2.sh <domain> <email>}"
HERE="$(cd "$(dirname "$0")" && pwd)"

echo "==> Installing Docker, nginx, certbot ..."
sudo apt-get update -y
sudo apt-get install -y docker.io docker-compose-v2 nginx certbot python3-certbot-nginx

echo "==> Building & starting the API container ..."
cd "$HERE"
[ -f .env ] || { echo "ERROR: deploy/.env missing (copy .env.example)"; exit 1; }
[ -f service-account.json ] || { echo "ERROR: deploy/service-account.json missing"; exit 1; }
sudo docker compose up -d --build

echo "==> Configuring nginx reverse proxy for ${DOMAIN} ..."
sudo tee /etc/nginx/sites-available/credit-audit >/dev/null <<NGINX
server {
    listen 80;
    server_name ${DOMAIN};
    client_max_body_size 25M;          # allow PDF uploads
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 120s;        # the processing pipeline can take time
    }
}
NGINX
sudo ln -sf /etc/nginx/sites-available/credit-audit /etc/nginx/sites-enabled/credit-audit
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx

echo "==> Requesting TLS certificate (Let's Encrypt) ..."
sudo certbot --nginx -d "${DOMAIN}" --non-interactive --agree-tos -m "${EMAIL}" --redirect

echo ""
echo "DONE ✅  API is live at: https://${DOMAIN}"
echo "Test:  curl https://${DOMAIN}/health"
