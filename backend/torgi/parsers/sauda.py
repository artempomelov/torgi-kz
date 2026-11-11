"""sauda.e-qazyna.kz — государственная площадка ИУЦ (бывш. gosreestr): приватизация гос- и коммунального
имущества, имущество банкротов, налоговых должников, конфискат, ФПК, КУВА, банки в ликвидации,
земельные торги акиматов.

С 24.10.2026 сайт грузит список лотов скриптом. Для клиентов без JavaScript у него есть серверная версия
/ru/list-fb?flObjectType=...&flCoarseStatus=Active&p=N — таблица по 15 лотов: номер, название, адрес, дата торгов,
начальная цена, статус. Карточка /ru/list/{id} отдаёт данные лота JSON-ом в атрибуте data-config: тип торгов,
цены, гарантийный взнос, сроки, объект, продавец, фото, документы. Аренда и доверительное управление — не продажа,
пропускаем.
"""

import json
import re
from collections.abc import Iterator, Mapping
from datetime import datetime, timedelta, timezone

import httpx
from bs4 import BeautifulSoup, Tag

from torgi import normalize as nz
from torgi.parsers.base import HttpClient, ParsedLot, Parser

BASE = "https://sauda.e-qazyna.kz"
LIST_URL = f"{BASE}/ru/list-fb"
KZ_TZ = timezone(timedelta(hours=5))
OBJECT_TYPES = ["RealEstate", "RealEstateNotFinished", "PropComplex", "Land", "LandAgricultural"]
LAND_TYPES = {"Land", "LandAgricultural"}

_NOT_SALE_RE = re.compile(r"аренд|наем|доверит|закреплени", re.I)
_PAIR_RE = re.compile(r"([А-Яа-яЁёA-Za-z0-9 ,./()c]{3,60}?)\s+-\s+([^;]+)")


def _text(el: Tag | None) -> str:
    return re.sub(r"\s+", " ", el.get_text(" ", strip=True)).strip() if el else ""


def _dt(value: str | None) -> datetime | None:
    if not value:
        return None
    m = re.search(r"(\d{2}\.\d{2}\.\d{4})(?:\s+(\d{1,2}:\d{2}))?", value)
    if not m:
        return None
    return datetime.strptime(f"{m.group(1)} {m.group(2) or '00:00'}", "%d.%m.%Y %H:%M").replace(tzinfo=KZ_TZ)


def origin_for(auction_type: str, seller: str) -> str | None:
    """Вид продажи по типу торгов и продавцу. None — не продажа (аренда, доверительное управление)."""
    t, s = auction_type.lower(), seller.lower()
    if _NOT_SALE_RE.search(t):
        return None
    if "банкрот" in t:
        return "bankrupt"
    if "налогоплательщик" in t:
        return "tax_debtor"
    if "конфискат" in t:
        return "confiscated"
    if "фонд проблемных кредитов" in s or ("банк" in s and "ликвидац" in s) or re.search(r"bank\b", s):
        return "bank_balance"
    return "state"


def sale_type_for(auction_type: str) -> str:
    t = auction_type.lower()
    if "понижени" in t:
        return "auction_down"
    if "тендер" in t:
        return "tender"
    return "auction"


_LIST_COLUMNS = {"Номер аукциона": "number", "Наименование объекта": "title", "Адрес объекта": "address",
                 "Дата начала торгов": "start", "Начальная цена": "price", "Статус": "status"}


def parse_list(page: str) -> list[dict]:
    """Строки таблицы /ru/list-fb. Столбцы ищем по заголовкам, а не по порядку."""
    soup = BeautifulSoup(page, "lxml")
    cards: dict[str, dict] = {}
    for table in soup.select("table"):
        heads = [_text(th) for th in table.select("thead th")]
        keys = [next((v for k, v in _LIST_COLUMNS.items() if h.startswith(k)), None) for h in heads]
        for tr in table.select("tbody tr"):
            link = tr.select_one("a[href^='/ru/list/']")
            if not link:
                continue
            row = {k: _text(td) for k, td in zip(keys, tr.find_all("td", recursive=False)) if k}
            lot_id = link["href"].rstrip("/").rsplit("/", 1)[-1]
            cards[lot_id] = {
                "id": lot_id,
                "title": row.get("title", ""),
                "address": row.get("address", ""),
                "start": row.get("start", ""),
                "price": nz.parse_number(row.get("price")),
                "number": row.get("number") or None,
                "status": row.get("status", ""),
            }
    return list(cards.values())


def detail_config(page: str) -> dict:
    """JSON лота из data-config карточки (тот, где есть «obj» — объект продажи)."""
    soup = BeautifulSoup(page, "lxml")
    for el in soup.select("[data-config]"):
        try:
            cfg = json.loads(el["data-config"])
        except ValueError:
            continue
        if isinstance(cfg, dict) and isinstance(cfg.get("obj"), dict):
            return cfg
    return {}


def phones(seller: str) -> list[str]:
    """«Телефоны для справок: +7 (7262) 45-53-11, 43-69-30; …» — номера с кодом (10–11 цифр), короткие городские — нет."""
    if "Телефон" not in seller:
        return []
    part = seller.split("Телефон", 1)[1].split(":", 1)[-1].split(";", 1)[0]
    found = []
    for piece in part.split(","):
        piece = piece.strip()
        digits = re.sub(r"\D", "", piece)
        if len(digits) == 10:
            found.append(f"+7 {piece}")
        elif len(digits) == 11 and digits[0] in "78":
            found.append(piece)
    return list(dict.fromkeys(found))


def object_pairs(text: str) -> dict[str, str]:
    """«Кадаcтровый номер - 14:218:001:203; Общая площадь, кв.м. - 834.8; …» → словарь.
    На сайте в ключах встречается латинская «c» вместо кириллической — нормализуем."""
    pairs: dict[str, str] = {}
    for chunk in text.split(";"):
        m = _PAIR_RE.search(chunk.strip())
        if m:
            key = m.group(1).strip().lower().replace("c", "с")
            pairs.setdefault(key, m.group(2).strip())
    return pairs


def parse_detail(page: str, card: dict, object_type: str) -> ParsedLot | None:
    cfg = detail_config(page)
    if not cfg:
        return None
    o = cfg["obj"]
    seller = o.get("sellerInfo") or ""
    auction_type = cfg.get("typeText") or ""
    origin = origin_for(auction_type, seller)
    if origin is None or _NOT_SALE_RE.search(o.get("title") or ""):  # «Объект аренды»
        return None

    obj = o.get("info") or ""
    location = o.get("address") or card.get("address") or ""
    title = cfg.get("title") or card.get("title") or obj[:200]
    pairs = object_pairs(obj)

    def pair(*prefixes: str) -> str | None:
        for p in prefixes:
            for k, v in pairs.items():
                if k.startswith(p):
                    return v
        return None

    if object_type in LAND_TYPES:
        category = "land"
    else:
        category = nz.classify_category(pair("тип недвижимости"), pair("функциональное назначение"), title, obj)
        if category == "land":  # «здание … с земельным участком» — не земля
            category = nz.classify_category(title.split(",")[0]) if "здани" in title.lower() else category
        # «Нежилой фонд» — не квартира и не дом, даже если «тип недвижимости» указан неверно
        if category in ("apartment", "house") and "не жил" in (pair("фонд") or "").lower():
            category = nz.classify_category(pair("функциональное назначение"), title)
            if category in ("apartment", "house", "other"):
                category = "commercial"
    area = nz.parse_number(pair("общая площадь")) or nz.parse_area_m2(f"{title} {obj}")
    land = nz.parse_number(pair("площадь земельного")) or nz.parse_land_ha(f"{title} {obj}")

    photos = [f"{BASE}/image-proxy/1200x900/{u}" for u in cfg.get("images") or [] if isinstance(u, str)]
    documents = []
    for f in cfg.get("files") or []:
        url = f.get("url") or ""
        if not url:
            continue
        name = (f.get("name") or "").strip()
        documents.append({"title": re.sub(r"\.(pdf|docx?|xlsx?|jpe?g|png|zip|rar)$", "", name, flags=re.I) or "Документ",
                          "url": BASE + url if url.startswith("/") else url})

    seller_name = seller.split(";")[0].strip() if seller else None
    city = nz.detect_city(location, title)
    floor, floors_total = nz.parse_floor(obj)

    return ParsedLot(
        source_id=card["id"],
        url=f"{BASE}/ru/list/{card['id']}",
        title=title,
        origin=origin,
        category=category,
        sale_type=sale_type_for(auction_type),
        description=nz.clean_text(obj),
        region=nz.normalize_region(location, title, city=city),
        city=city,
        address=location or None,
        area_m2=None if category == "land" else area,
        land_area_ha=land,
        rooms=nz.parse_rooms(f"{title} {obj}"),
        floor=floor,
        floors_total=floors_total,
        year_built=nz.parse_int(pair("год постройки")) or nz.parse_year(obj),
        cadastral=pair("кадастровый номер") or nz.parse_cadastral(f"{title} {obj}"),
        price=card.get("price") or cfg.get("startPrice"),
        deposit=cfg.get("guarantee") or None,
        min_price=cfg.get("minPrice") or None,
        auction_start=_dt(cfg.get("startAt") or card.get("start")),
        applications_deadline=_dt(cfg.get("acceptAppsTill")),
        images=photos,
        documents=documents,
        contacts={k: v for k, v in {"owner": seller_name, "phone": ", ".join(phones(seller)[:2]) or None}.items() if v},
        extra={"auction_type": auction_type, "lot_number": cfg.get("number") or card.get("number"),
               "object_type": object_type, "fund": pair("фонд"), "purpose": pair("функциональное назначение")},
    )


class SaudaParser(Parser):
    name = "sauda"
    title = "E-Qazyna (госимущество, банкротство)"
    base_url = BASE

    def fetch(self, http: HttpClient, known: Mapping[str, float | None]) -> Iterator[ParsedLot]:
        for object_type in OBJECT_TYPES:
            page = 1
            while True:
                resp = http.get(LIST_URL, params={"flObjectType": object_type, "flCoarseStatus": "Active", "p": page})
                cards = parse_list(resp.text)
                if not cards:
                    break
                for card in cards:
                    sid = card["id"]
                    if sid in known and known[sid] == card["price"]:
                        # уже есть в базе с той же ценой — карточку не загружаем, но дату торгов из списка передаём:
                        # перенос торгов не должен снять лот как прошедший
                        yield ParsedLot(source_id=sid, url=f"{BASE}/ru/list/{sid}", title=card["title"],
                                        origin="state", category="other", price=card["price"],
                                        auction_start=_dt(card["start"]), partial=True)
                        continue
                    try:
                        detail = http.get(f"{BASE}/ru/list/{sid}").text
                    except httpx.HTTPError:
                        continue
                    if lot := parse_detail(detail, card, object_type):
                        yield lot
                page += 1
                if page > 400:  # страховка от бесконечного цикла (11.11.2026 у недвижимости 85 страниц)
                    break
