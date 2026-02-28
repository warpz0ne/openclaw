#!/usr/bin/env bash
set -euo pipefail

DOMAIN="dudda.cloud"
APP_DIR="/home/manu/.openclaw/workspace/slice"
APP_USER="manu"
APP_PORT="8787"

echo "[1/7] Installing packages..."
sudo apt-get update -y
sudo apt-get install -y nginx certbot python3-certbot-nginx

echo "[2/7] Writing systemd service for Slice app..."
sudo tee /etc/systemd/system/slice.service >/dev/null <<EOF
[Unit]
Description=Slice dashboard web server
After=network.target

[Service]
Type=simple
User=${APP_USER}
WorkingDirectory=${APP_DIR}
EnvironmentFile=-/etc/default/slice
ExecStart=/usr/bin/node ${APP_DIR}/server.js
Restart=always
RestartSec=3
Environment=PORT=${APP_PORT}

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload

if [ ! -f /etc/default/slice ]; then
  echo "[2.5/7] Creating /etc/default/slice (fill OAuth values after install)..."
  sudo tee /etc/default/slice >/dev/null <<'EOF'
# Slice auth env
GOOGLE_CLIENT_ID=
ALLOWED_EMAILS=
SESSION_SECURE=1
EOF
  sudo chmod 600 /etc/default/slice
fi

sudo systemctl enable --now slice.service


echo "[3/7] Writing nginx site config..."
sudo tee /etc/nginx/sites-available/slice >/dev/null <<EOF
server {
    listen 80;
    listen [::]:80;
    server_name ${DOMAIN} www.${DOMAIN};

    location / {
        proxy_pass http://127.0.0.1:${APP_PORT};
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF

sudo ln -sf /etc/nginx/sites-available/slice /etc/nginx/sites-enabled/slice
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl enable --now nginx
sudo systemctl reload nginx

echo "[4/7] Requesting TLS certificate..."
sudo certbot --nginx -d ${DOMAIN} -d www.${DOMAIN} --redirect --agree-tos --register-unsafely-without-email -n

echo "[5/7] Smoke tests..."
curl -I http://127.0.0.1:${APP_PORT} | head -n 1 || true
curl -I http://${DOMAIN} | head -n 1 || true
curl -I https://${DOMAIN} | head -n 1 || true

echo "[6/7] Service status..."
sudo systemctl --no-pager --full status slice.service | sed -n '1,20p' || true
sudo systemctl --no-pager --full status nginx | sed -n '1,20p' || true

echo "[7/7] Done. Visit: https://${DOMAIN}"
