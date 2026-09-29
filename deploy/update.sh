#!/usr/bin/env bash
# Сборка и перезапуск после загрузки нового кода (запускается deploy.sh от root).
set -euo pipefail
APP=/opt/torgi
chown -R torgi:torgi "$APP"
as_torgi() { sudo -u torgi -H bash -c "set -a; source /etc/torgi/torgi.env; set +a; $*"; }

echo "==> Backend"
as_torgi "cd $APP/backend && uv sync --frozen --extra postgres --no-dev"
as_torgi "cd $APP/backend && .venv/bin/python -m torgi.cli initdb"
systemctl restart torgi-api

echo "==> Web (статическая сборка из базы)"
as_torgi "cd $APP/web && npm ci --no-audit --no-fund"
as_torgi "bash $APP/deploy/rebuild-site.sh"

echo "==> Проверка"
for _ in $(seq 1 30); do curl -fsS http://127.0.0.1:8000/api/health >/dev/null && break; sleep 1; done
curl -fsS http://127.0.0.1:8000/api/health | head -c 300; echo
systemctl --no-pager --lines=0 status torgi-api | grep -E 'Active:|●'
