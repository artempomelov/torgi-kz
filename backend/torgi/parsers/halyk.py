"""halykzalog.kz — имущество и залоги Halyk Bank (серверный HTML, Laravel).

Листинг: /catalog/category_id-is-{c}?page=N (24 карточки на страницу).
Деталь:  /catalog/category_id-is-{c}/{id} — таблица характеристик, координаты, фото, аукцион.
"""

import re
from collections.abc import Iterator, Mapping
from datetime import datetime, timedelta, timezone

from bs4 import BeautifulSoup

from torgi import normalize as nz
from torgi.parsers.base import HttpClient, ParsedLot, Parser

BASE = "https://halykzalog.kz"
KZ_TZ = timezone(timedelta(hours=5))

# 7 — транспорт, не берём
CATEGORIES: dict[int, str] = {
    1: "apartment",
    2: "house",
    3: "parking",
    4: "commercial",
    5: "industrial",
    6: "land",
    8: "other",
}

_AUCTION_PERIOD_RE = re.compile(
    r"с\s+(\d{2}\.\d{2}\.\d{4})(?:\s+(\d{1,2}:\d{2}))?\s+по\s+(\d{2}\.\d{2}\.\d{4})(?:\s+(\d{1,2}:\d{2}))?"
)
_BIDS_RE = re.compile(r"произведенных ставок:\s*(\d+)", re.I)


def _dt(date: str | None, time: str | None = None) -> datetime | None:
    if not date:
        return None
    return datetime.strptime(f"{date} {time or '00:00'}", "%d.%m.%Y %H:%M").replace(tzinfo=KZ_TZ)


def parse_listing(html: str) -> list[dict]:
    """Карточки листинга: id, url, цена, адрес."""
    soup = BeautifulSoup(html, "lxml")
    cards = []
    for card in soup.select("div.shop-item-container[data-id]"):
        link = card.select_one("h2.shop-item-title a") or card.select_one("a[href]")
        amount = card.select_one("span.amount")
        cards.append({
            "id": card["data-id"],
            "url": link["href"] if link else f"{BASE}/catalog/{card['data-id']}",
            "address": (link.get("title") or link.get_text(strip=True)) if link else None,
            "price": nz.parse_number(amount.get_text(" ", strip=True)) if amount else None,
            "kind": (el.get_text(strip=True) if (el := card.select_one(".shop-item-category")) else None),
        })
    return cards


def parse_detail(html: str, url: str, category: str) -> ParsedLot:
    soup = BeautifulSoup(html, "lxml")
    specs: dict[str, str] = {}
    for row in soup.select("table#js-table tr"):
        th, td = row.find("th"), row.find("td")
        if th and td:
            specs[th.get_text(" ", strip=True)] = td.get_text(" ", strip=True)

    body = soup.select_one(".shop-item-body")
    kind = address = None
    price = None
    if body:
        if h := body.select_one("h2.shop-item-title"):
            kind = h.get_text(" ", strip=True)
        if a := body.select_one("span.amount"):
            price = nz.parse_number(a.get_text(" ", strip=True))
        if d := body.select_one(".shop-item-description"):
            address = d.get_text(" ", strip=True)

    desc_el = soup.select_one("#description")
    description = None
    if desc_el:
        paragraphs = [p.get_text(" ", strip=True) for p in desc_el.select("p") if "red" not in (p.get("class") or [])]
        description = nz.clean_text("\n".join(p for p in paragraphs if p))

    def coord(name: str) -> float | None:
        el = soup.select_one(f"#coords-map-{name}")
        return nz.parse_number(el.get("value")) if el and el.get("value") else None

    images: list[str] = []
    for src in re.findall(r"(?:https://halykzalog\.kz/)?/?uploads/product_images/[^\"'\s)]+", html):
        full = src if src.startswith("http") else f"{BASE}/{src.lstrip('/')}"
        if "thumbnail_" not in full and full not in images:
            images.append(full)

    text = soup.get_text(" ", strip=True)
    auction_start = auction_end = None
    sale_type = "direct"
    bids = None
    if "Проводится аукцион" in text and (m := _AUCTION_PERIOD_RE.search(text)):
        auction_start, auction_end = _dt(m.group(1), m.group(2)), _dt(m.group(3), m.group(4))
        sale_type = "auction"
        if b := _BIDS_RE.search(text):
            bids = int(b.group(1))

    realization = specs.get("Реализация", "")
    source_id = specs.get("Порядковый номер") or url.rstrip("/").rsplit("/", 1)[-1]
    floor = nz.parse_int(specs.get("Этаж"))
    area = nz.parse_number(specs.get("Общая площадь"))
    city = nz.detect_city(address)
    land_ha = nz.parse_land_ha(specs.get("Площадь участка") or specs.get("Площадь земельного участка"))
    if category == "land" and land_ha is None:
        land_ha = nz.parse_land_ha(description) or nz.parse_land_ha(specs.get("Площадь"))

    known_keys = {"Реализация", "Владелец объявления", "Порядковый номер", "Количество комнат", "Этаж",
                  "Всего этажей", "Общая площадь", "Дата публикации"}
    return ParsedLot(
        source_id=str(source_id),
        url=url,
        title=f"{kind or nz.CATEGORIES[category]}, {address}" if address else (kind or "Объект Halyk"),
        origin="bank_pledge" if "залог" in realization.lower() else "bank_balance",
        category=category,
        sale_type=sale_type,
        description=description,
        region=nz.normalize_region(address, city=city),
        city=city,
        address=address,
        lat=coord("latitude"),
        lon=coord("longitude"),
        area_m2=area,
        land_area_ha=land_ha,
        rooms=nz.parse_int(specs.get("Количество комнат")),
        floor=floor,
        floors_total=nz.parse_int(specs.get("Всего этажей")),
        year_built=nz.parse_int(specs.get("Год постройки (сдачи в эксплуатацию)")),
        cadastral=nz.parse_cadastral(description),
        price=price,
        auction_start=auction_start,
        auction_end=auction_end,
        published_at=_dt(specs.get("Дата публикации")),
        images=images,
        contacts={"owner": specs.get("Владелец объявления")} if specs.get("Владелец объявления") else {},
        extra={"realization": realization or None, "bids": bids,
               **{k: v for k, v in specs.items() if k not in known_keys}},
    )


class HalykParser(Parser):
    name = "halyk"
    title = "Halyk Bank (halykzalog.kz)"
    base_url = BASE

    def fetch(self, http: HttpClient, known: Mapping[str, float | None]) -> Iterator[ParsedLot]:
        auction_ids = {c["id"] for c in parse_listing(http.get(f"{BASE}/catalog/section-is-auctions").text)}
        seen: set[str] = set()
        for cat_id, category in CATEGORIES.items():
            page = 1
            while True:
                cards = parse_listing(http.get(f"{BASE}/catalog/category_id-is-{cat_id}", params={"page": page}).text)
                if not cards:
                    break
                for card in cards:
                    sid = card["id"]
                    if sid in seen:
                        continue
                    seen.add(sid)
                    unchanged = sid in known and known[sid] == card["price"] and sid not in auction_ids
                    if unchanged:
                        yield ParsedLot(source_id=sid, url=card["url"], title=card["address"] or "",
                                        origin="bank_balance", category=category, price=card["price"], partial=True)
                    else:
                        yield parse_detail(http.get(card["url"]).text, card["url"], category)
                page += 1
