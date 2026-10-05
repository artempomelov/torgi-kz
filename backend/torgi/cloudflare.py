"""Загрузка закрытых полей лотов в Cloudflare D1 — их отдаёт worker/src/index.js после входа на сайт.

    uv run python -m torgi.cli sync-private ../web/data/private.json

Нужны переменные окружения CLOUDFLARE_API_TOKEN, CLOUDFLARE_ACCOUNT_ID и CF_D1_DATABASE_ID.
Загружаются только изменившиеся лоты (сравнение по хэшу), удалённые из выгрузки — удаляются.
"""

import hashlib
import json
import logging
import os
from pathlib import Path

import httpx

log = logging.getLogger(__name__)

API = "https://api.cloudflare.com/client/v4"
ROWS_PER_QUERY = 30  # D1 принимает до 100 параметров в запросе, у строки их 3


class D1:
    def __init__(self, token: str, account_id: str, database_id: str):
        self.url = f"{API}/accounts/{account_id}/d1/database/{database_id}/query"
        self.client = httpx.Client(timeout=60, headers={"Authorization": f"Bearer {token}"})

    def query(self, sql: str, params: list | None = None) -> list[dict]:
        res = self.client.post(self.url, json={"sql": sql, "params": params or []})
        data = res.json()
        if not data.get("success"):
            raise RuntimeError(f"D1: {data.get('errors')}")
        return data["result"][0].get("results", [])


def _hash(data: dict) -> str:
    return hashlib.sha1(json.dumps(data, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def sync(private_file: Path, d1: D1) -> dict[str, int]:
    private: dict[str, dict] = json.loads(private_file.read_text(encoding="utf-8"))
    current = {str(row["id"]): row["hash"] for row in d1.query("SELECT id, hash FROM lots_private")}

    rows = [(int(lot_id), json.dumps(data, ensure_ascii=False), _hash(data))
            for lot_id, data in private.items() if current.get(lot_id) != _hash(data)]
    for i in range(0, len(rows), ROWS_PER_QUERY):
        chunk = rows[i:i + ROWS_PER_QUERY]
        d1.query(
            "INSERT OR REPLACE INTO lots_private (id, data, hash) VALUES " + ", ".join(["(?, ?, ?)"] * len(chunk)),
            [value for row in chunk for value in row],
        )

    gone = [int(lot_id) for lot_id in current if lot_id not in private]
    for i in range(0, len(gone), 90):
        chunk = gone[i:i + 90]
        d1.query(f"DELETE FROM lots_private WHERE id IN ({', '.join('?' * len(chunk))})", chunk)

    stats = {"total": len(private), "uploaded": len(rows), "deleted": len(gone)}
    log.info("D1: %s", stats)
    return stats


def sync_from_env(private_file: Path) -> dict[str, int]:
    env = {k: os.environ.get(k) for k in ("CLOUDFLARE_API_TOKEN", "CLOUDFLARE_ACCOUNT_ID", "CF_D1_DATABASE_ID")}
    if missing := [k for k, v in env.items() if not v]:
        raise SystemExit(f"Не заданы: {', '.join(missing)}")
    return sync(private_file, D1(env["CLOUDFLARE_API_TOKEN"], env["CLOUDFLARE_ACCOUNT_ID"], env["CF_D1_DATABASE_ID"]))
