"""Выгрузка базы в JSON для статического сайта (GitHub Pages).

    uv run python -m torgi.cli export ../web/data            # всё открыто (сейчас)
    uv run python -m torgi.cli export ../web/data --gated    # платный режим: закрытые поля не попадают в статику

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

from torgi import normalize as nz
from torgi.api import LotFull, _drop_pct, _short, meta
from torgi.models import Lot, utcnow

# Снятые лоты держим на сайте ещё 30 дней: ссылки из Telegram и поисковиков не ломаются
REMOVED_KEEP_DAYS = 30

# Поля, которые в платном режиме будут доступны только после входа/по подписке (через API).
# Всё остальное — публичная «витрина»: её индексируют поисковики и видят все посетители.
# Единый список: сайт (web/src/lib/features.ts) опирается на те же имена.
GATED_FIELDS = frozenset({
    "title",          # у многих источников в заголовке точный адрес — публично показываем headline
    "address",
    "lat",
    "lon",
    "cadastral",
    "url",            # ссылка на первоисточник
    "contacts",
    "description",
    "extra",
    "price_history",
})


def headline(lot: dict) -> str:
    """Публичный заголовок без точного адреса: «Квартира, 3-комн., 57,5 м² — Алматы»."""
    parts = [nz.CATEGORIES.get(lot["category"], "Объект")]
    if lot.get("rooms") and lot["category"] in ("apartment", "house"):
        parts.append(f"{lot['rooms']}-комн.")
    if lot.get("area_m2"):
        parts.append(f"{lot['area_m2']:g} м²".replace(".", ","))
    elif lot.get("land_area_ha"):
        parts.append(f"{lot['land_area_ha']:g} га".replace(".", ","))
    place = lot.get("city") or lot.get("region")
    return ", ".join(parts) + (f" — {place}" if place else "")


def _prepare(item: dict, gated: bool) -> dict:
    item["headline"] = headline(item)
    if gated:
        for field in GATED_FIELDS:
            item.pop(field, None)
    return item


def _dump(path: Path, data) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":"), default=str), encoding="utf-8")


def export(session: Session, out_dir: Path, gated: bool = False) -> dict[str, int]:
    out_dir.mkdir(parents=True, exist_ok=True)
    cutoff = utcnow() - timedelta(days=REMOVED_KEEP_DAYS)
    lots = session.scalars(
        select(Lot)
        .where((Lot.status == "active") | (Lot.removed_at >= cutoff))
        .options(selectinload(Lot.price_history))
        .order_by(Lot.first_seen_at.desc(), Lot.id.desc())
    ).all()

    short = [_prepare(_short(lot).model_dump(mode="json"), gated) for lot in lots if lot.status == "active"]
    full = []
    for lot in lots:
        item = LotFull.model_validate(lot)
        item.image = lot.images[0] if lot.images else None
        item.price_drop_pct = _drop_pct(lot)
        full.append(_prepare(item.model_dump(mode="json"), gated))

    _dump(out_dir / "lots.json", short)
    _dump(out_dir / "lots-full.json", full)
    _dump(out_dir / "meta.json", {**meta(session), "updated_at": utcnow().isoformat(), "gated": gated})
    return {"active": len(short), "pages": len(full)}
