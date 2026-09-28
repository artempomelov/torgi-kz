"""alataucitybank.kz/balance — балансовое имущество Alatau City Bank (бывш. Jusan).

Открытый GraphQL: POST /balance-property/graphql, все объекты одним запросом.
"""

from collections.abc import Iterator, Mapping
from datetime import datetime, timedelta, timezone
from typing import Any

from torgi import normalize as nz
from torgi.parsers.base import HttpClient, ParsedLot, Parser

BASE = "https://alataucitybank.kz"
GRAPHQL = f"{BASE}/balance-property/graphql"
KZ_TZ = timezone(timedelta(hours=5))

CATEGORIES = {
    "1": "apartment",
    "2": "house",
    "3": "commercial",
    "4": "land",
    "5": "other",
}
SKIP_CATEGORY_TITLES = {"движимое имущество"}

SALE_TYPES = {"1": "direct", "2": "tender", "3": "auction"}

LIST_QUERY = """
query {
  allProperties(sellingMethodIds: [], regionId: null, categoryId: null, minPrice: null, maxPrice: null,
                pageDto: {pageNo: 0, pageSize: 1000, sortBy: "new"}) {
    items {
      id title { ru } description { ru } price publishedAt mainPageImage
      propertyImagesList { fullScreenImage }
      propertyInfo { title { ru } info { ru } }
      propertySellingMethods { id title { ru } }
      propertyCategory { id title { ru } }
      propertyRegion { title { ru } }
    }
    itemCount
  }
}
"""

DETAIL_QUERY = """
query {
  propertyById(id: $id) {
    contactDetails { type title { ru } link }
    propertyMapCoordinate { latitude longitude }
  }
}
"""


def _ru(value: Any) -> str | None:
    if isinstance(value, dict):
        value = value.get("ru")
    return value.strip() if isinstance(value, str) and value.strip() else None


def _image_url(ref: str | None) -> str | None:
    if not ref:
        return None
    # фронтенд банка дописывает расширение: FILE_SERVER + ref + ".png"
    return ref if ref.startswith("http") else f"{BASE}/file-server/filename?{ref}.png"


def property_info(item: dict) -> dict[str, str]:
    """propertyInfo → {'город': '...', 'общая площадь, кв.м.': '...'} (ключи без двоеточия, в нижнем регистре)."""
    info: dict[str, str] = {}
    for row in item.get("propertyInfo") or []:
        key, value = _ru(row.get("title")), _ru(row.get("info"))
        if key and value:
            info[key.rstrip(": ").lower()] = value
    return info


def _find(info: dict[str, str], *prefixes: str) -> str | None:
    for prefix in prefixes:
        for key, value in info.items():
            if key.startswith(prefix):
                return value
    return None


def parse_item(item: dict) -> ParsedLot | None:
    cat = item.get("propertyCategory") or {}
    cat_title = (_ru(cat.get("title")) or "").lower()
    if cat_title in SKIP_CATEGORY_TITLES:
        return None
    title = _ru(item.get("title")) or ""
    description = nz.clean_text(_ru(item.get("description")))
    info = property_info(item)

    category = CATEGORIES.get(str(cat.get("id")))
    if category in (None, "other", "commercial"):
        guessed = nz.classify_category(title, cat_title)
        category = guessed if guessed != "other" or category is None else category

    methods = item.get("propertySellingMethods") or []
    sale_type = SALE_TYPES.get(str(methods[0]["id"])) if methods else None

    city_raw = _find(info, "город")
    city = nz.detect_city(city_raw, title)
    region_raw = _ru((item.get("propertyRegion") or {}).get("title"))
    floor = nz.parse_int(_find(info, "занимаемый этаж", "этаж"))
    total_area = nz.parse_number(_find(info, "общая площадь", "площадь, в кв.м")) or nz.parse_area_m2(
        f"{title}\n{description or ''}")
    land = _find(info, "площадь зем", "площадь з/у")

    images = [u for img in item.get("propertyImagesList") or [] if (u := _image_url(img.get("fullScreenImage")))]
    if not images and (main := _image_url(item.get("mainPageImage"))):
        images = [main]

    published = None
    if item.get("publishedAt"):
        published = datetime.fromisoformat(item["publishedAt"]).replace(tzinfo=KZ_TZ)

    skip = {"город", "район", "улица", "номер дома", "общая площадь", "занимаемый этаж", "количество этажей",
            "год постройки", "кадастровый номер", "площадь зем"}
    return ParsedLot(
        source_id=str(item["id"]),
        url=f"{BASE}/balance/{item['id']}",
        title=title,
        origin="bank_balance",
        category=category,
        sale_type=sale_type,
        description=description,
        region=nz.normalize_region(region_raw, city_raw, title, city=city),
        city=city,
        address=title,
        area_m2=None if category == "land" else total_area,
        land_area_ha=nz.parse_land_ha(land) if land else (total_area if category == "land" else None),
        rooms=nz.parse_rooms(title) or nz.parse_int(_find(info, "количество комнат")),
        floor=floor,
        floors_total=nz.parse_int(_find(info, "количество этажей")),
        year_built=nz.parse_int(_find(info, "год постройки")),
        cadastral=_find(info, "кадастровый номер"),
        price=nz.parse_number(item.get("price")),
        published_at=published,
        images=images,
        extra={k: v for k, v in info.items() if not any(k.startswith(s) for s in skip)},
    )


def apply_detail(lot: ParsedLot, detail: dict) -> None:
    coords = detail.get("propertyMapCoordinate") or {}
    lot.lat = nz.parse_number(coords.get("latitude"))
    lot.lon = nz.parse_number(coords.get("longitude"))
    contacts = {}
    for c in detail.get("contactDetails") or []:
        if c.get("link"):
            contacts[c.get("type") or _ru(c.get("title")) or "contact"] = c["link"]
    lot.contacts = contacts


class AlatauParser(Parser):
    name = "alatau"
    title = "Alatau City Bank"
    base_url = BASE

    def fetch(self, http: HttpClient, known: Mapping[str, float | None]) -> Iterator[ParsedLot]:
        data = http.post(GRAPHQL, json={"query": LIST_QUERY}).json()
        if data.get("errors"):
            raise RuntimeError(f"alatau graphql: {data['errors']}")
        for item in data["data"]["allProperties"]["items"]:
            lot = parse_item(item)
            if lot is None:
                continue
            # Координаты и контакты — отдельным запросом, только для новых/изменившихся;
            # у известных лотов ingest сохранит ранее загруженные значения.
            if lot.source_id not in known or known[lot.source_id] != lot.price:
                query = DETAIL_QUERY.replace("$id", str(int(lot.source_id)))
                detail = (http.post(GRAPHQL, json={"query": query}).json().get("data") or {}).get("propertyById")
                if detail:
                    apply_detail(lot, detail)
            yield lot
