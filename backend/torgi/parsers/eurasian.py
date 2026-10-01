"""eubank.kz — имущество Евразийского банка. Открытый JSON (Payload CMS), все лоты одним запросом."""

import re
from collections.abc import Iterator, Mapping
from datetime import datetime

from torgi import normalize as nz
from torgi.parsers.base import HttpClient, ParsedLot, Parser

SITE = "https://eubank.kz"
API = f"{SITE}/api/marketplace_items"
LIST_URL = f"{SITE}/ru/property-for-sale"  # у лотов нет отдельных страниц — открываются окном на списке

CATEGORIES = {
    "Коммерческая недвижимость": "commercial",
    "Земельные участки": "land",
    "Комплексы, заводы": "industrial",
    "Дома, квартиры": None,  # квартира или дом — по тексту
}


def _ru(obj: dict | None, key: str) -> str | None:
    value = (obj or {}).get(key)
    return value.strip() if isinstance(value, str) and value.strip() else None


def parse_item(item: dict) -> ParsedLot | None:
    if item.get("isDraft"):
        return None
    cat_label = _ru((item.get("category") or {}).get("category"), "labelRu")
    if cat_label not in CATEGORIES:
        return None  # авто, спецтехника, оборудование
    title = _ru(item.get("title"), "titleRu") or "Объект"
    description = nz.clean_text(_ru(item.get("description"), "descriptionRu"))
    category = CATEGORIES[cat_label]
    if category is None:
        category = "apartment" if nz.classify_category(title, description) == "apartment" else "house"

    chars = {}
    for c in item.get("characteristics") or []:
        k, v = _ru(c.get("key"), "keyRu"), _ru(c.get("value"), "valueRu")
        if k and v:
            chars[k.lower().rstrip(":")] = v

    def char(*prefixes: str) -> str | None:
        return next((v for p in prefixes for k, v in chars.items() if k.startswith(p)), None)

    regions = [_ru(r.get("regions"), "labelRu") for r in item.get("regions") or []]
    region_raw = next((r for r in regions if r), None)
    text = f"{title}\n{description or ''}"
    m = re.search(r"Адрес:\s*(?:Казахстан,\s*)?(.+)", description or "")
    address = char("адрес", "местоположение") or (m.group(1).strip() if m else None)
    city = nz.detect_city(address, region_raw, text)
    floor, floors_total = nz.parse_floor(f"Этаж: {char('этаж')}") if char("этаж") else (None, None)
    area = nz.parse_number(char("общая площадь", "площадь")) or nz.parse_area_m2(text)

    images = []
    for img in item.get("images") or []:
        url = (img.get("image") or {}).get("url")
        if url:
            images.append(SITE + url if url.startswith("/") else url)
    documents = []
    for info in item.get("additionalInfo") or []:
        f = info.get("labelRu") or {}
        if f.get("url"):
            documents.append({"title": (f.get("fileLabels") or {}).get("labelRu") or f.get("originalFilename") or "Документ",
                              "url": SITE + f["url"] if f["url"].startswith("/") else f["url"], "size": f.get("filesize")})
    coords = item.get("coords") or {}
    created = item.get("createdAt")

    return ParsedLot(
        source_id=str(item["id"]),
        url=LIST_URL,
        title=title,
        origin="bank_balance",
        category=category,
        sale_type="direct",
        description=description,
        region=nz.normalize_region(region_raw, text, city=city),
        city=city,
        address=address,
        lat=nz.parse_number(coords.get("latitude")),
        lon=nz.parse_number(coords.get("longitude")),
        area_m2=None if category == "land" else area,
        land_area_ha=nz.parse_land_ha(text) or (nz.parse_number(char("площадь участка")) if char("площадь участка") else None),
        rooms=nz.parse_int(char("количество комнат", "комнат")) or nz.parse_rooms(text),
        floor=floor,
        floors_total=floors_total or nz.parse_int(char("этажность")),
        year_built=nz.parse_int(char("год постройки")),
        cadastral=nz.parse_cadastral(text),
        price=nz.parse_number(item.get("price")),
        published_at=datetime.fromisoformat(created.replace("Z", "+00:00")) if created else None,
        images=images,
        documents=documents,
        contacts={"phone": c} if (c := _ru(item.get("contacts"), "phone")) else {},
        extra={"category_title": cat_label, **{k: v for k, v in chars.items() if not k.startswith(("этаж", "общая площадь"))}},
    )


class EurasianParser(Parser):
    name = "eurasian"
    title = "Евразийский банк"
    base_url = LIST_URL

    def fetch(self, http: HttpClient, known: Mapping[str, float | None]) -> Iterator[ParsedLot]:
        data = http.get(API, params={"limit": 0, "depth": 1}).json()
        for item in data.get("docs") or []:
            if lot := parse_item(item):
                yield lot
