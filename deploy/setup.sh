#!/usr/bin/env bash
# Первичная настройка сервера Ubuntu 24.04 под torgi.kz (запускается deploy.sh один раз, от root).
#   bash /opt/torgi/deploy/setup.sh admin@example.com
set -euo pipefail

EMAIL=${1:?"укажите email для Let's Encrypt"}
APP=/opt/torgi
ENV_FILE=/etc/torgi/torgi.env
ALL_DOMAINS=(torgi.kz www.torgi.kz vsetorgi.kz www.vsetorgi.kz torgi-nedvizhimost.kz www.torgi-nedvizhimost.kz)

echo "==> Пакеты"
export DEBIAN_FRONTEND=noninteractive
apt-get update -q
apt-get install -yq nginx postgresql certbot python3.12 python3.12-venv curl ufw dnsutils openssl
if ! command -v node >/dev/null || [ "$(node -p 'process.versions.node.split(".")[0]')" -lt 20 ]; then
  curl -fsSL https://deb.nodesource.com/setup_22.x | bash -
  apt-get install -yq nodejs
fi
command -v uv >/dev/null || curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR=/usr/local/bin UV_NO_MODIFY_PATH=1 sh
timedatectl set-timezone Asia/Almaty

echo "==> Пользователь и каталоги"
id torgi >/dev/null 2>&1 || useradd --system --create-home --home-dir /home/torgi --shell /usr/sbin/nologin torgi
chown -R torgi:torgi "$APP"
mkdir -p /etc/torgi /var/www/certbot

echo "==> PostgreSQL"
if [ ! -f "$ENV_FILE" ]; then
  DB_PASS=$(openssl rand -hex 24)
  sudo -u postgres psql -qtc "select 1 from pg_roles where rolname='torgi'" | grep -q 1 \
    && sudo -u postgres psql -qc "alter user torgi password '$DB_PASS'" \
    || sudo -u postgres psql -qc "create user torgi password '$DB_PASS'"
  sudo -u postgres psql -qtc "select 1 from pg_database where datname='torgi'" | grep -q 1 \
    || sudo -u postgres createdb -O torgi torgi
  cat > "$ENV_FILE" <<EOF
TORGI_DATABASE_URL=postgresql+psycopg://torgi:${DB_PASS}@127.0.0.1/torgi
TORGI_SITE_URL=https://torgi.kz
# Telegram: заполните и выполните  systemctl start torgi-post
TORGI_TELEGRAM_BOT_TOKEN=
TORGI_TELEGRAM_CHANNEL=
EOF
  chown root:torgi "$ENV_FILE"
  chmod 640 "$ENV_FILE"
fi

echo "==> Firewall"
ufw allow OpenSSH >/dev/null
ufw allow 'Nginx Full' >/dev/null
ufw --force enable >/dev/null

echo "==> Сертификаты"
SERVER_IP=$(curl -fsS https://api.ipify.org)
DOMAINS=()
for d in "${ALL_DOMAINS[@]}"; do
  if dig +short A "$d" @8.8.8.8 | grep -qx "$SERVER_IP"; then DOMAINS+=("$d"); else echo "   ! $d не указывает на $SERVER_IP — пропускаю"; fi
done
[ ${#DOMAINS[@]} -gt 0 ] || { echo "Ни один домен не указывает на сервер ($SERVER_IP). Настройте A-записи и повторите."; exit 1; }

# временный HTTP-конфиг для проверки домена Let's Encrypt
cat > /etc/nginx/sites-available/torgi <<'EOF'
server {
    listen 80 default_server;
    location /.well-known/acme-challenge/ { root /var/www/certbot; }
    location / { return 503; }
}
EOF
ln -sf /etc/nginx/sites-available/torgi /etc/nginx/sites-enabled/torgi
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx
certbot certonly --webroot -w /var/www/certbot --cert-name torgi.kz --expand --non-interactive --agree-tos \
  -m "$EMAIL" $(printf -- '-d %s ' "${DOMAINS[@]}")
cat > /etc/letsencrypt/renewal-hooks/deploy/reload-nginx.sh <<'EOF'
#!/bin/sh
systemctl reload nginx
EOF
chmod +x /etc/letsencrypt/renewal-hooks/deploy/reload-nginx.sh

cp "$APP/deploy/nginx/torgi.conf" /etc/nginx/sites-available/torgi
nginx -t && systemctl reload nginx

echo "==> systemd"
cp "$APP"/deploy/systemd/*.service "$APP"/deploy/systemd/*.timer /etc/systemd/system/
systemctl daemon-reload
systemctl enable torgi-api torgi-web torgi-parse-hourly.timer torgi-parse-daily.timer torgi-post.timer

echo "==> Готово. Сертификат на: ${DOMAINS[*]}"
