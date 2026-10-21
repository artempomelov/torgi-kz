"""Выгрузка базы в JSON для статического сайта (GitHub Pages).

    uv run python -m torgi.cli export ../web/data            # всё открыто (сейчас)
    uv run python -m torgi.cli export ../web/data --gated    # платный режим: закрытые поля не попадают в статику

Создаёт:
    lots.json         — активные лоты для каталога (короткий формат, грузится браузером)
    lots-full.json    — все лоты с деталями и историей цен (только для сборки страниц лотов)
    meta.json         — справочники и счётчики
    cars.json         — машины с торгов (раздел /avto/)
"""

import hashlib
import json
import re
from datetime import timedelta
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from torgi import normalize as nz
from torgi.api import LotFull, PricePoint, _drop_pct, _short, meta
from torgi.models import Lot, utcnow
from torgi.parsers.vehicles import CATEGORY as VEHICLE
from torgi.parsers.vehicles import scrub_ids

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
    # «— Алматы, Бостандыкский район»: человечнее и полезнее для поиска
    area = lot.get("district")
    if place and area:
        place = f"{place}, {area}"
    return ", ".join(parts) + (f" — {place}" if place else "")


# Если один объект продают на двух площадках, в каталоге оставляем один — источник с лучшими данными
SOURCE_PRIORITY = ["adilet", "sauda", "halyk", "forte", "bcc", "alatau", "freedom", "eurasian", "nurbank", "bereke", "rbk", "krisha"]


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


# Район из адреса: «р-н Есиль», «р-он Сарыарка», «район "Сарыарка"», «Бостандыкский Район», «в Наурызбайском районе» —
# публичный ориентир вместо точного адреса. Не район: «микрорайон Левый Берег», «район Новоальджанского элеватора».
_DISTRICT_RE = re.compile(
    r"(?<![\w-])(?:р-о?н|[Рр]айон)\.?\s+[\"«]?([А-ЯЁӘІҢҒҮҰҚӨҺ][\w-]+)(?<!ого)(?<!его)(?![\w-])"
    r"|([А-ЯЁӘІҢҒҮҰҚӨҺ][\w-]+(?:\s+[Бб]и)?)\s+(?:р-о?н|[Рр]айон[еа]?)\b"  # «Казыбек Би Район» в Караганде
)
# «..., ул. Ақмешіт, зд. 19Б, п.м. 78» → «..., ул. Ақмешіт, зд. 19Б» (как groupParkings в web/src/lib/filter.ts)
_PLACE_RE = re.compile(
    r",?\s*(?:п\.\s?м\.?|м/м|машино[\s-]*мест\w*|парковочн\w+\s+мест\w*|паркинг\w*|№)\s*№?\s*[\w/-]+.*$", re.I
)
APPROX_DIGITS = 2  # в закрытом режиме координаты публично — до ~1 км


def _district_name(m: re.Match) -> str:
    if m.group(1):
        return f"район {m.group(1)}"
    name = re.sub(r"([сц]к)(?:ом|ого|ому)$", r"\1ий", m.group(2))  # «Наурызбайском» → «Наурызбайский»
    return f"{name} район"


def district(address: str | None) -> str | None:
    m = _DISTRICT_RE.search(address or "")
    return _district_name(m) if m else None


def lot_district(address: str | None, city: str | None, title: str | None = None,
                 description: str | None = None) -> str | None:
    """Район лота: явный из адреса, заголовка или описания; только если его нет — по известному микрорайону."""
    for text in (address, title):
        if found := nz.canonical_district(district(text), city):
            return found
    # в описании бывает и «район Мега» — оттуда берём только официальные районы города: «район Нұра», «Сарыаркинский»
    known = nz.city_districts(city)
    for m in _DISTRICT_RE.finditer(nz.fix_homoglyphs(description)):
        if (found := nz.canonical_district(_district_name(m), city)) in known:
            return found
    return nz.infer_district(city, address, title)


def group_key(item: dict) -> str | None:
    """Ключ здания для паркингов: одинаковые места одного источника сворачиваются в одну карточку."""
    if item.get("category") != "parking" or not item.get("address"):
        return None
    base = _PLACE_RE.sub("", item["address"]).strip()
    if not base or base == item["address"]:
        return None
    return hashlib.sha1(f"{item['source']}|{base}".encode()).hexdigest()[:12]


def _prepare(item: dict, gated: bool, private: dict | None = None, description: str | None = None) -> dict:
    # ФИО владельцев и ИИН из лотов ЧСИ — не публикуем (и у лотов, сохранённых до очистки в ingest)
    for field in ("address", "title", "description"):
        if item.get(field):
            item[field] = nz.scrub_personal(item[field])
    description = nz.scrub_personal(description)
    for field in ("address", "title"):
        if item.get(field):
            item[field] = nz.clean_address(item[field])
    if "cadastral" in item:
        item["cadastral"] = nz.valid_cadastral(item["cadastral"])
    item["city"], item["region"] = nz.reconcile_place(item.get("city"), item.get("region"),
                                                      item.get("address"), item.get("title"))
    # описания в коротком формате нет — передаём отдельно
    item["district"] = lot_district(item.get("address"), item.get("city") or item.get("region"), item.get("title"),
                                    description)
    item["headline"] = headline(item)
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


CAR_FIELDS = ("vehicle_type", "brand", "model", "year", "mileage_km", "engine", "transmission", "body", "color", "drive",
              "note")


def car_item(lot: Lot) -> dict:
    """Машина для раздела /avto/: общие поля лота + марка, модель, год и характеристики из extra."""
    extra = lot.extra or {}
    when = lot.auction_start or lot.auction_end  # у Halyk известен только конец онлайн-аукциона
    return {
        "id": lot.id, "source": lot.source.removesuffix("_auto"), "url": lot.url, "title": lot.title,
        **{k: extra.get(k) for k in CAR_FIELDS},
        "vehicle_type": extra.get("vehicle_type") or "other",
        "price": lot.price, "min_price": lot.min_price, "deposit": lot.deposit,
        "city": lot.city, "region": lot.region, "origin": lot.origin, "sale_type": lot.sale_type,
        "auction_date": when.isoformat() if when else None,
        "applications_deadline": lot.applications_deadline.isoformat() if lot.applications_deadline else None,
        "listed_at": (lot.published_at or lot.first_seen_at).isoformat(),
        "price_drop_pct": _drop_pct(lot),
        "images": lot.images or [],
        "description": scrub_ids(lot.description),  # и у уже сохранённых описаний
    }


def _dump(path: Path, data) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":"), default=str), encoding="utf-8")


def export(session: Session, out_dir: Path, gated: bool = False, market_index: Path | None = None,
           car_market_index: Path | None = None) -> dict[str, int]:
    out_dir.mkdir(parents=True, exist_ok=True)
    cutoff = utcnow() - timedelta(days=REMOVED_KEEP_DAYS)
    lots = session.scalars(
        select(Lot)
        .where((Lot.status == "active") | (Lot.removed_at >= cutoff))
        .options(selectinload(Lot.price_history))
        .order_by(Lot.first_seen_at.desc(), Lot.id.desc())
    ).all()
    # машины — отдельный раздел /avto/ со своим файлом; плашка «−N% к рынку» — по объявлениям aster.kz
    vehicles = [lot for lot in lots if lot.category == VEHICLE and lot.status == "active"]
    lots = [lot for lot in lots if lot.category != VEHICLE]
    cars = [car_item(lot) for lot in vehicles]
    if car_market_index and car_market_index.exists():
        from torgi.car_market import CarIndex, car_badge

        car_index = CarIndex.from_json(car_market_index)
        for car in cars:
            car["market"] = car_badge(car, car_index)
    _dump(out_dir / "cars.json", {"generated_at": utcnow().isoformat(), "items": cars})

    dups = find_duplicates(lots)
    short = [
        _prepare(_short(lot).model_dump(mode="json"), gated, description=lot.description)
        for lot in lots
        if lot.status == "active" and lot.id not in dups
    ]
    full = []
    private: dict[str, dict] = {}  # закрытые поля → D1 (Cloudflare), в статику не попадают
    for lot in lots:
        item = LotFull.model_validate(lot)
        # график на карточке — без опечаток источника (161 млн → 16 млн — не скидка 90%)
        item.price_history = [PricePoint.model_validate(p) for p in nz.real_price_history(lot.price_history)]
        item.image = lot.images[0] if lot.images else None
        item.price_drop_pct = _drop_pct(lot)
        item.listed_at = lot.published_at or lot.first_seen_at
        raw = item.model_dump(mode="json")
        # номер лота у продавца — публичный: отличает одинаковые лоты (серии участков) для поисковиков
        raw["source_lot"] = (raw.get("extra") or {}).get("lot_number")
        data = _prepare(raw, gated, private, lot.description)
        data["duplicate_of"] = dups.get(lot.id)
        full.append(data)

    # раздел «ТОП» и плашки «−N% к рынку»: оценка по рынку (сводные цены м² — market-index.json из `market index`)
    top: dict = {"sections": []}
    if market_index and market_index.exists():
        from torgi.market import MarketIndex  # market импортирует export — избегаем цикла
        from torgi.top import build as build_top
        from torgi.top import load_picks, market_badge

        index = MarketIndex.from_json(market_index)
        by_id = {lot.id: lot for lot in lots}
        top = build_top(short, by_id, index, load_picks())
        badges = {x["id"]: badge for x in short if (badge := market_badge(x, by_id[x["id"]], index))}
        for item in (*short, *full):
            item["market"] = badges.get(item["id"])
    _dump(out_dir / "top.json", top)

    _dump(out_dir / "lots.json", short)
    _dump(out_dir / "lots-full.json", full)
    _dump(out_dir / "meta.json", {**meta(session), "updated_at": utcnow().isoformat(), "gated": gated})
    if gated:
        # кладём рядом с выгрузкой, но не в web/public — файл не публикуется
        _dump(out_dir / "private.json", private)
    return {"active": len(short), "pages": len(full), "private": len(private),
            "top": sum(len(s["items"]) for s in top["sections"])}
