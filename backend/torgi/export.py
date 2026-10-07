"""Выгрузка базы в JSON для статического сайта (GitHub Pages).

    uv run python -m torgi.cli export ../web/data            # всё открыто (сейчас)
    uv run python -m torgi.cli export ../web/data --gated    # платный режим: закрытые поля не попадают в статику

Создаёт:
    lots.json         — активные лоты для каталога (короткий формат, грузится браузером)
    lots-full.json    — все лоты с деталями и историей цен (только для сборки страниц лотов)
    meta.json         — справочники и счётчики
"""

import hashlib
import json
import re
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
    "cadastral",
    "url",            # ссылка на первоисточник
    "contacts",
    "description",
    "extra",
    "price_history",
    "documents",      # отчёты об оценке, техпаспорта, госакты
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
    area = district(lot.get("address"))  # «— Алматы, Бостандыкский район»: человечнее и полезнее для поиска
    if place and area:
        place = f"{place}, {area}"
    return ", ".join(parts) + (f" — {place}" if place else "")


# Если один объект продают на двух площадках, в каталоге оставляем один — источник с лучшими данными
SOURCE_PRIORITY = ["adilet", "sauda", "halyk", "forte", "bcc", "alatau", "freedom", "eurasian", "nurbank", "bereke", "rbk"]


def find_duplicates(lots: list[Lot]) -> dict[int, int]:
    """id дубля → id основного лота. Совпадение — по кадастровому номеру между разными источниками."""
    groups: dict[str, list[Lot]] = {}
    for lot in lots:
        key = nz.valid_cadastral(lot.cadastral)
        if key and lot.status == "active":
            groups.setdefault(re.sub(r"\W", "", key).lower(), []).append(lot)
    rank = {s: i for i, s in enumerate(SOURCE_PRIORITY)}
    dups: dict[int, int] = {}
    for group in groups.values():
        if len({lot.source for lot in group}) < 2:
            continue  # внутри одного источника один номер у разных помещений — не дубли
        main = min(group, key=lambda lot: (-len(lot.images or []), rank.get(lot.source, 99)))
        for lot in group:
            if lot.source != main.source:
                dups[lot.id] = main.id
    return dups


# Район из адреса: «р-н Есиль», «Бостандыкский район» — публичный ориентир вместо точного адреса
_DISTRICT_RE = re.compile(r"(?:р-н|район)\s+([А-ЯЁӘІҢҒҮҰҚӨҺ][\w-]+)|([А-ЯЁӘІҢҒҮҰҚӨҺ][\w-]+)\s+(?:р-н|район)\b")
# «..., ул. Ақмешіт, зд. 19Б, п.м. 78» → «..., ул. Ақмешіт, зд. 19Б» (как groupParkings в web/src/lib/filter.ts)
_PLACE_RE = re.compile(
    r",?\s*(?:п\.\s?м\.?|м/м|машино[\s-]*мест\w*|парковочн\w+\s+мест\w*|паркинг\w*|№)\s*№?\s*[\w/-]+.*$", re.I
)
APPROX_DIGITS = 2  # в закрытом режиме координаты публично — до ~1 км


def district(address: str | None) -> str | None:
    m = _DISTRICT_RE.search(address or "")
    if not m:
        return None
    return f"район {m.group(1)}" if m.group(1) else f"{m.group(2)} район"


def group_key(item: dict) -> str | None:
    """Ключ здания для паркингов: одинаковые места одного источника сворачиваются в одну карточку."""
    if item.get("category") != "parking" or not item.get("address"):
        return None
    base = _PLACE_RE.sub("", item["address"]).strip()
    if not base or base == item["address"]:
        return None
    return hashlib.sha1(f"{item['source']}|{base}".encode()).hexdigest()[:12]


def _prepare(item: dict, gated: bool, private: dict | None = None) -> dict:
    for field in ("address", "title"):
        if item.get(field):
            item[field] = nz.clean_address(item[field])
    if "cadastral" in item:
        item["cadastral"] = nz.valid_cadastral(item["cadastral"])
    item["city"], item["region"] = nz.reconcile_place(item.get("city"), item.get("region"),
                                                      item.get("address"), item.get("title"))
    item["headline"] = headline(item)
    item["district"] = district(item.get("address"))
    item["group_key"] = group_key(item)
    if gated:
        if private is not None:
            private[str(item["id"])] = {f: item.get(f) for f in GATED_FIELDS | {"lat", "lon"} if f in item}
        for field in GATED_FIELDS:
            item.pop(field, None)
        for field in ("lat", "lon"):
            if item.get(field) is not None:
                item[field] = round(item[field], APPROX_DIGITS)
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

    dups = find_duplicates(lots)
    short = [
        _prepare(_short(lot).model_dump(mode="json"), gated)
        for lot in lots
        if lot.status == "active" and lot.id not in dups
    ]
    full = []
    private: dict[str, dict] = {}  # закрытые поля → D1 (Cloudflare), в статику не попадают
    for lot in lots:
        item = LotFull.model_validate(lot)
        item.image = lot.images[0] if lot.images else None
        item.price_drop_pct = _drop_pct(lot)
        item.listed_at = lot.published_at or lot.first_seen_at
        data = _prepare(item.model_dump(mode="json"), gated, private)
        data["duplicate_of"] = dups.get(lot.id)
        full.append(data)

    _dump(out_dir / "lots.json", short)
    _dump(out_dir / "lots-full.json", full)
    _dump(out_dir / "meta.json", {**meta(session), "updated_at": utcnow().isoformat(), "gated": gated})
    if gated:
        # кладём рядом с выгрузкой, но не в web/public — файл не публикуется
        _dump(out_dir / "private.json", private)
    return {"active": len(short), "pages": len(full), "private": len(private)}
