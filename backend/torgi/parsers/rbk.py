"""bankrbk.kz — залоговое имущество Bank RBK. Открытый JSON (Laravel), по 3 объекта на страницу."""

import json
from collections.abc import Iterator, Mapping
from datetime import datetime, timedelta, timezone

from torgi import normalize as nz
from torgi.parsers.base import HttpClient, ParsedLot, Parser

API = "https://backend.bankrbk.kz/api/v1/deposit_guarantee/getThreeNextEstates"
SITE = "https://bankrbk.kz/ru"  # отдельных страниц у объектов нет
KZ_TZ = timezone(timedelta(hours=5))
CATEGORIES = {"flat": None, "house": "house", "commercial": "commercial", "land": "land"}


def parse_item(item: dict) -> ParsedLot | None:
    if not item.get("published", 1):
        return None
    title = (item.get("title_ru") or "Объект").strip()
    address = (item.get("address_ru") or "").strip() or None
    description = nz.clean_text(_strip_html(item.get("description_ru") or item.get("preview_description_ru")))
    text = f"{title}\n{address or ''}\n{description or ''}"
    category = CATEGORIES.get(item.get("category") or "", None) or nz.classify_category(title, description)
    if item.get("category") == "flat" and category not in ("apartment", "commercial"):
        category = "apartment"

    images: list[str] = []
    raw = item.get("sliderImg")
    if raw:
        try:
            parsed = json.loads(raw) if isinstance(raw, str) else raw
            images = list(parsed.values()) if isinstance(parsed, dict) else list(parsed)
        except ValueError:
            pass
    city = nz.detect_city(address, title)
    created = item.get("created_at")
    area = nz.parse_number(item.get("totalArea") or item.get("area")) or nz.parse_area_m2(text)

    return ParsedLot(
        source_id=str(item["id"]),
        url=SITE,
        title=f"{title}, {address}" if address else title,
        origin="bank_pledge",
        category=category,
        sale_type="direct",
        description=description,
        region=nz.normalize_region(address, city=city),
        city=city,
        address=address,
        lat=nz.parse_number(item.get("lat")),
        lon=nz.parse_number(item.get("lng")),
        area_m2=None if category == "land" else area,
        land_area_ha=nz.parse_land_ha(text),
        rooms=nz.parse_int(item.get("roomsCount")) or nz.parse_rooms(text),
        cadastral=nz.parse_cadastral(text),
        price=nz.parse_number(item.get("price")),
        published_at=datetime.strptime(created, "%Y-%m-%d %H:%M:%S").replace(tzinfo=KZ_TZ) if created else None,
        images=[u for u in images if isinstance(u, str)],
        contacts={"phone": item["contactNumber"]} if item.get("contactNumber") else {},
        extra={"wall_material": item.get("wallMaterial_ru"), "credit": bool(item.get("credit"))},
    )


def _strip_html(value: str | None) -> str | None:
    if not value:
        return None
    from bs4 import BeautifulSoup

    return BeautifulSoup(value, "lxml").get_text("\n", strip=True)


class RbkParser(Parser):
    name = "rbk"
    title = "Bank RBK"
    base_url = SITE

    def fetch(self, http: HttpClient, known: Mapping[str, float | None]) -> Iterator[ParsedLot]:
        page = 1
        while page <= 100:
            data = http.get(API, params={"page": page}).json()
            for item in data.get("data") or []:
                if lot := parse_item(item):
                    yield lot
            if not data.get("next_page_url"):
                break
            page += 1
