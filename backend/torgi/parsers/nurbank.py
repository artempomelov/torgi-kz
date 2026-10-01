"""nurbank.kz — залоговое имущество Нурбанка. Все лоты на одной HTML-странице, детали — /ru/bank/collateral/{id}/."""

import re
from collections.abc import Iterator, Mapping
from datetime import datetime, timedelta, timezone

import httpx
from bs4 import BeautifulSoup

from torgi import normalize as nz
from torgi.parsers.base import HttpClient, ParsedLot, Parser

SITE = "https://www.nurbank.kz"
LIST_URL = f"{SITE}/ru/bank/collateral/"
KZ_TZ = timezone(timedelta(hours=5))
BANK_PHONES = {"2552", "+77272444444"}  # общий колл-центр — не контакт по объекту
_NOT_REALTY_RE = re.compile(r"автомоб|транспорт|спецтехник|оборудован|грузов|прицеп|трактор|комбайн|\bVIN\b|весы|г\.в\.", re.I)


def parse_list(page: str) -> list[dict]:
    soup = BeautifulSoup(page, "lxml")
    out = []
    for item in soup.select(".list .item"):
        link = item.select_one("a[href*='/ru/bank/collateral/']")
        if not link:
            continue
        m = re.search(r"/collateral/(\d+)/", link["href"])
        title = item.select_one(".title")
        date = re.search(r"\d{2}\.\d{2}\.\d{4}", item.select_one(".date").get_text() if item.select_one(".date") else "")
        img = item.select_one("img")
        out.append({
            "id": m.group(1),
            "title": title.get_text(" ", strip=True) if title else "",
            "city": item.select_one(".city").get_text(strip=True) if item.select_one(".city") else None,
            "price": nz.parse_number(item.select_one(".price").get_text()) if item.select_one(".price") else None,
            "date": date.group(0) if date else None,
            "thumb": SITE + img["src"].split("?")[0] if img and img.get("src") else None,
        })
    return out


def parse_detail(page: str) -> dict:
    soup = BeautifulSoup(page, "lxml")
    prop = soup.select_one("#property") or soup
    # секции карточки: адрес (title без ссылки), телефоны (tel:), описание
    address = next((t.get_text(" ", strip=True) for t in prop.select(".sections .title") if not t.select_one("a")), None)
    phones = [a["href"][4:] for a in prop.select("a[href^='tel:']") if a["href"][4:] not in BANK_PHONES]
    description = "\n".join(d.get_text("\n", strip=True) for d in prop.select(".sections .description")) or None
    photos = list(dict.fromkeys(SITE + img["src"].split("?")[0] for img in prop.select(".h-slider img[src]")))
    return {"address": address, "phones": list(dict.fromkeys(phones)), "description": nz.clean_text(description),
            "photos": photos}


def build_lot(card: dict, detail: dict | None) -> ParsedLot | None:
    detail = detail or {}
    title = card["title"]
    text = f"{title}\n{detail.get('description') or ''}"
    category = nz.classify_category(title, detail.get("description"))
    if category == "other" and _NOT_REALTY_RE.search(title):
        return None
    address = detail.get("address")
    city = nz.detect_city(card.get("city"), address, title) or card.get("city")
    floor, floors_total = nz.parse_floor(text)
    return ParsedLot(
        source_id=card["id"],
        url=f"{LIST_URL}{card['id']}/",
        title=f"{title}, {address}" if address else title,
        origin="bank_pledge",
        category=category,
        sale_type="direct",
        description=detail.get("description"),
        region=nz.normalize_region(address, card.get("city"), city=city),
        city=city,
        address=address,
        area_m2=None if category == "land" else nz.parse_area_m2(text),
        land_area_ha=nz.parse_land_ha(text),
        rooms=nz.parse_rooms(text),
        floor=floor,
        floors_total=floors_total,
        cadastral=nz.parse_cadastral(text),
        price=card.get("price"),
        published_at=datetime.strptime(card["date"], "%d.%m.%Y").replace(tzinfo=KZ_TZ) if card.get("date") else None,
        images=detail.get("photos") or ([card["thumb"]] if card.get("thumb") else []),
        contacts={"phone": ", ".join(detail["phones"][:2])} if detail.get("phones") else {},
    )


class NurbankParser(Parser):
    name = "nurbank"
    title = "Нурбанк"
    base_url = LIST_URL

    def fetch(self, http: HttpClient, known: Mapping[str, float | None]) -> Iterator[ParsedLot]:
        for card in parse_list(http.get(LIST_URL).text):
            if _NOT_REALTY_RE.search(card["title"]) and nz.classify_category(card["title"]) == "other":
                continue
            if card["id"] in known and known[card["id"]] == card["price"]:
                yield ParsedLot(source_id=card["id"], url=f"{LIST_URL}{card['id']}/", title=card["title"],
                                origin="bank_pledge", category="other", price=card["price"], partial=True)
                continue
            try:
                detail = parse_detail(http.get(f"{LIST_URL}{card['id']}/").text)
            except httpx.HTTPError:
                detail = None
            if lot := build_lot(card, detail):
                yield lot
