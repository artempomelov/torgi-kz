#!/usr/bin/env bash
# Выгрузка базы в JSON и пересборка статического сайта (от пользователя torgi; вызывается после парсинга).
set -euo pipefail
cd /opt/torgi/backend && .venv/bin/python -m torgi.cli export ../web/data
cd /opt/torgi/web && npm run build --silent
