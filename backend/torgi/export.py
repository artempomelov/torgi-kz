"""Выгрузка базы в JSON для статического сайта (GitHub Pages).

    uv run python -m torgi.cli export ../web/data

Создаёт:
    lots.json         — активные лоты для каталога (короткий формат, грузится браузером)
    lots-full.json    — все лоты с деталями и историей цен (только для сборки страниц лотов)
    meta.json         — справочники и счётчики
"""

import json
from datetime import timedelta
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from torgi.api import LotFull, _drop_pct, _short, meta
from torgi.models import Lot, utcnow

# Снятые лоты держим на сайте ещё 30 дней: ссылки из Telegram и поисковиков не ломаются
REMOVED_KEEP_DAYS = 30


def _dump(path: Path, data) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":"), default=str), encoding="utf-8")


def export(session: Session, out_dir: Path) -> dict[str, int]:
    out_dir.mkdir(parents=True, exist_ok=True)
    cutoff = utcnow() - timedelta(days=REMOVED_KEEP_DAYS)
    lots = session.scalars(
        select(Lot)
        .where((Lot.status == "active") | (Lot.removed_at >= cutoff))
        .options(selectinload(Lot.price_history))
        .order_by(Lot.first_seen_at.desc(), Lot.id.desc())
    ).all()

    short = [_short(lot).model_dump(mode="json") for lot in lots if lot.status == "active"]
    full = []
    for lot in lots:
        item = LotFull.model_validate(lot)
        item.image = lot.images[0] if lot.images else None
        item.price_drop_pct = _drop_pct(lot)
        full.append(item.model_dump(mode="json"))

    _dump(out_dir / "lots.json", short)
    _dump(out_dir / "lots-full.json", full)
    _dump(out_dir / "meta.json", {**meta(session), "updated_at": utcnow().isoformat()})
    return {"active": len(short), "pages": len(full)}
