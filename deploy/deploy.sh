#!/usr/bin/env bash
# Деплой с локальной машины (Git Bash / Linux / macOS):
#   deploy/deploy.sh root@1.2.3.4                     # обновление кода
#   deploy/deploy.sh root@1.2.3.4 --setup me@mail.kz  # первый запуск: пакеты, БД, SSL, systemd
set -euo pipefail

HOST=${1:?"укажите сервер: root@IP"}
SETUP_EMAIL=""
[ "${2:-}" = "--setup" ] && SETUP_EMAIL=${3:?"укажите email для Let's Encrypt"}
ROOT=$(cd "$(dirname "$0")/.." && pwd)

echo "==> Загрузка кода на $HOST"
tar -C "$ROOT" -czf - \
  --exclude=.git --exclude=node_modules --exclude=.next --exclude=.venv --exclude=__pycache__ \
  --exclude=.pytest_cache --exclude='*.db' --exclude=.env --exclude=backend/tests/fixtures \
  backend web deploy \
  | ssh "$HOST" 'mkdir -p /opt/torgi && tar -xzf - -C /opt/torgi'

if [ -n "$SETUP_EMAIL" ]; then
  ssh "$HOST" "bash /opt/torgi/deploy/setup.sh '$SETUP_EMAIL'"
fi
ssh "$HOST" 'bash /opt/torgi/deploy/update.sh'

if [ -n "$SETUP_EMAIL" ]; then
  echo "==> Первичная загрузка лотов в фоне (Halyk ~20 минут)"
  ssh "$HOST" 'systemctl start --no-block torgi-parse-hourly torgi-parse-daily'
fi
echo "==> Готово: https://torgi.kz"
