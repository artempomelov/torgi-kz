#!/usr/bin/env bash
# База в релизе «data» репозитория — публичная. Лоты храним открыто (torgi.db.gz),
# а данные людей — подписки бота, служебное состояние бота (chat id администраторов, заявки),
# аккаунты сайта — только в зашифрованном файле private.sql.enc.
#
#   db-release.sh load   — скачать базу и вернуть в неё зашифрованные таблицы
#   db-release.sh save   — выгрузить: публичная копия без личных данных + шифрованный дамп
#
# Ключ: секрет TORGI_DB_KEY, если задан, иначе токен бота (уже есть в секретах).
# Если ключ сменился и расшифровать не удалось — таблицы пользователей начинаются заново,
# лоты и история цен не страдают.
set -euo pipefail

DB=torgi.db
PRIVATE_TABLES="subscriptions bot_state users detail_views"
KEY="${TORGI_DB_KEY:-${TORGI_TELEGRAM_BOT_TOKEN:-}}"
enc() { openssl enc -aes-256-cbc -pbkdf2 -iter 200000 -salt -pass env:KEY "$@"; }
export KEY

case "${1:-}" in
  load)
    if gh release download data --pattern torgi.db.gz --dir . --clobber 2>/dev/null; then
      gunzip -f torgi.db.gz && ls -la "$DB"
    else
      echo "Базы ещё нет — будет первый полный парсинг"
      exit 0
    fi
    if [ -n "$KEY" ] && gh release download data --pattern private.sql.enc --dir . --clobber 2>/dev/null; then
      if enc -d -in private.sql.enc -out private.sql 2>/dev/null; then
        for t in $PRIVATE_TABLES; do sqlite3 "$DB" "DROP TABLE IF EXISTS $t;"; done
        sqlite3 "$DB" < private.sql
        echo "Данные пользователей восстановлены"
      else
        echo "::warning::Не удалось расшифровать данные пользователей (сменился ключ?) — начинаем заново"
      fi
      rm -f private.sql private.sql.enc
    fi
    ;;
  save)
    [ -n "$KEY" ] || { echo "::error::Нет ключа шифрования (TORGI_DB_KEY или токен бота)"; exit 1; }
    tables=$(for t in $PRIVATE_TABLES; do sqlite3 "$DB" "SELECT name FROM sqlite_master WHERE type='table' AND name='$t';"; done)
    sqlite3 "$DB" ".dump $tables" > private.sql
    enc -in private.sql -out private.sql.enc
    rm -f private.sql
    cp "$DB" public.db
    for t in $tables; do sqlite3 public.db "DELETE FROM $t;"; done
    sqlite3 public.db "VACUUM;"
    gzip -c public.db > torgi.db.gz
    rm -f public.db
    gh release view data >/dev/null 2>&1 || gh release create data --title "База данных" \
      --notes "SQLite-база лотов (без данных пользователей), обновляется автоматически." --latest=false
    gh release upload data torgi.db.gz private.sql.enc --clobber
    rm -f private.sql.enc
    ;;
  *)
    echo "usage: $0 load|save" >&2
    exit 2
    ;;
esac
