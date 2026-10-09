"""sauda.e-qazyna.kz — государственная площадка ИУЦ (бывш. gosreestr): приватизация гос- и коммунального
имущества, имущество банкротов, налоговых должников, конфискат, ФПК, КУВА, банки в ликвидации,
земельные торги акиматов.

Серверный HTML (ASP.NET), без API. Список: /ru/list?searchStatus=ApplicationsAccept&objectType=...&p=N
(20 лотов на страницу), карточка: /ru/list/{id}. Аренда и доверительное управление — не продажа, пропускаем.
"""

import html
import json
import re
from collections.abc import Iterator, Mapping
from datetime import datetime, timedelta, timezone

import httpx
from bs4 import BeautifulSoup, Tag

from torgi import normalize as nz
from torgi.parsers.base import HttpClient, ParsedLot, Parser

BASE = "https://sauda.e-qazyna.kz"
KZ_TZ = timezone(timedelta(hours=5))
OBJECT_TYPES = ["RealEstate", "RealEstateNotFinished", "PropComplex", "Land", "LandAgricultural"]
LAND_TYPES = {"Land", "LandAgricultural"}

_NOT_SALE_RE = re.compile(r"аренд|наем|доверит|закреплени", re.I)
_PHONE_RE = re.compile(r"(?:\+7|8)[\s(-]*\d{3}[\s)-]*\d{3}[\s-]*\d{2}[\s-]*\d{2}")
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


def parse_list(page: str) -> list[dict]:
    """Карточки списка (берём десктопный вариант разметки — он полный)."""
    soup = BeautifulSoup(page, "lxml")
    cards: dict[str, dict] = {}
    for block in soup.select("div.d-none.d-sm-block"):
        link = block.select_one(".name-trade-card a[href^='/ru/list/']")
        if not link:
            continue
        lot_id = link["href"].rsplit("/", 1)[-1]
        title = _text(link)
        kind, _, rest = title.partition(":")
        info = block.select_one(".name-trade-card")
        type_el = info.find_next_sibling("div") if info else None
        date_el = block.select_one(".uil-stopwatch")
        region_el = block.select_one(".mdi-map-marker-outline")
        price_el = block.select_one(".font-21")
        img = block.select_one("img")
        num = block.select_one(".badge")
        cards[lot_id] = {
            "id": lot_id,
            "kind": kind.strip() if rest else "",
            "title": (rest or kind).strip(),
            "auction_type": _text(type_el),
            "start": _text(date_el.parent) if date_el else "",
            "region": _text(region_el.parent) if region_el else "",
            "price": nz.parse_number(_text(price_el).replace("₸", "")),
            "thumb": img["src"] if img and img.get("src") else None,
            "number": _text(num).lstrip("№") or None,
        }
    return list(cards.values())


def _section(soup: BeautifulSoup, label: str) -> str:
    head = soup.find("p", string=re.compile(rf"^\s*{label}\s*$"))
    nxt = head.find_next_sibling("p") if head else None
    return _text(nxt)


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
    soup = BeautifulSoup(page, "lxml")
    seller = _section(soup, "Продавец")
    auction_type = card.get("auction_type") or ""
    origin = origin_for(auction_type, seller)
    if origin is None:
        return None

    obj = _section(soup, "Объект продажи")
    location = _section(soup, "Расположение объекта")
    pairs = object_pairs(obj)
    title = card.get("title") or obj[:200]

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

    photos: list[str] = []
    if m := re.search(r'data-srcs="([^"]+)"', page):
        try:
            photos = [f"{BASE}/image-proxy/1200x900/{u}" for u in json.loads(html.unescape(m.group(1)))]
        except ValueError:
            pass
    if not photos and card.get("thumb"):
        photos = [card["thumb"].replace("/150x110/", "/1200x900/")]

    documents = []
    for a in soup.select("a[href*='MnuFileStoreFileDownload']"):
        name = _text(a)
        documents.append({"title": re.sub(r"\.(pdf|docx?|xlsx?|jpe?g|png|zip|rar)$", "", name, flags=re.I) or "Документ",
                          "url": BASE + a["href"] if a["href"].startswith("/") else a["href"]})

    phone_part = seller.split("Телефон", 1)[1] if "Телефон" in seller else ""
    phones = list(dict.fromkeys(p.strip() for p in _PHONE_RE.findall(phone_part)))
    seller_name = seller.split(";")[0].strip() if seller else None
    city = nz.detect_city(location, title)
    page_text = re.sub(r"\s+", " ", soup.get_text(" ", strip=True))
    deposit = re.search(r"Гарантийный взнос\s*₸?\s*([\d\s]+,\d{2})", page_text)
    min_price = re.search(r"Минимальная цена\s*₸?\s*([\d\s]+,\d{2})", page_text)
    deadline = re.search(r"Дата завершения приема заявок\s*(\d{2}\.\d{2}\.\d{4}\s+\d{1,2}:\d{2})", page_text)
    floor, floors_total = nz.parse_floor(obj)

    return ParsedLot(
        source_id=card["id"],
        url=f"{BASE}/ru/list/{card['id']}",
        title=title,
        origin=origin,
        category=category,
        sale_type=sale_type_for(auction_type),
        description=nz.clean_text(obj),
        region=nz.normalize_region(card.get("region"), location, city=city),
        city=city,
        address=location or None,
        area_m2=None if category == "land" else area,
        land_area_ha=land,
        rooms=nz.parse_rooms(f"{title} {obj}"),
        floor=floor,
        floors_total=floors_total,
        year_built=nz.parse_int(pair("год постройки")) or nz.parse_year(obj),
        cadastral=pair("кадастровый номер") or nz.parse_cadastral(f"{title} {obj}"),
        price=card.get("price"),
        deposit=nz.parse_number(deposit.group(1)) if deposit else None,
        min_price=nz.parse_number(min_price.group(1)) if min_price else None,
        auction_start=_dt(card.get("start")),
        applications_deadline=_dt(deadline.group(1) if deadline else None),
        images=photos,
        documents=documents,
        contacts={k: v for k, v in {"owner": seller_name, "phone": ", ".join(phones[:2]) or None}.items() if v},
        extra={"auction_type": auction_type, "lot_number": card.get("number"), "object_type": object_type,
               "fund": pair("фонд"), "purpose": pair("функциональное назначение")},
    )


class SaudaParser(Parser):
    name = "sauda"
    title = "E-Qazyna (госимущество, банкротство)"
    base_url = BASE

    def fetch(self, http: HttpClient, known: Mapping[str, float | None]) -> Iterator[ParsedLot]:
        for object_type in OBJECT_TYPES:
            page = 1
            while True:
                resp = http.get(f"{BASE}/ru/list", params={
                    "searchStatus": "ApplicationsAccept", "objectType": object_type, "p": page})
                cards = parse_list(resp.text)
                if not cards:
                    break
                for card in cards:
                    if _NOT_SALE_RE.search(card["auction_type"]):
                        continue
                    sid = card["id"]
                    if sid in known and known[sid] == card["price"]:
                        # уже есть в базе с той же ценой — карточку не загружаем
                        yield ParsedLot(source_id=sid, url=f"{BASE}/ru/list/{sid}", title=card["title"],
                                        origin="state", category="other", price=card["price"], partial=True)
                        continue
                    try:
                        detail = http.get(f"{BASE}/ru/list/{sid}").text
                    except httpx.HTTPError:
                        continue
                    if lot := parse_detail(detail, card, object_type):
                        yield lot
                page += 1
                if page > 200:  # страховка от бесконечного цикла
                    break
