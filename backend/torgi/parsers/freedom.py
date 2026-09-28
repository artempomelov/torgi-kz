"""bankffin.kz/ru/mortgage — реализация имущества Freedom Bank. Открытый JSON REST.

В ответе есть номера кредитных договоров и договоров залога — их НЕ сохраняем.
"""

from collections.abc import Iterator, Mapping
from datetime import datetime

from torgi import normalize as nz
from torgi.parsers.base import HttpClient, ParsedLot, Parser

BASE = "https://bankffin.kz"
REALESTATE_TYPE_ID = 2

ORIGINS = {1: "bank_balance", 2: "bank_pledge", 3: "court"}  # адресная, внесудебная, судебная


def parse_item(item: dict) -> ParsedLot | None:
    re_data = item.get("mortgage_realestate")
    if item.get("mortgage_type_id") != REALESTATE_TYPE_ID or not re_data:
        return None
    location = (re_data.get("location") or "").strip()
    city_name = (item.get("city") or {}).get("name_ru")
    city = nz.detect_city(city_name, location) or city_name
    rooms = nz.parse_int(re_data.get("rooms_number"))
    title = f"{rooms}-комн. квартира, {location}" if rooms else location or item.get("name_ru") or "Объект"
    category = nz.classify_category(item.get("name_ru"), location)
    if category == "other":
        category = "apartment" if re_data.get("floor") else "house"
    realisation = item.get("realisation_type") or {}
    published = item.get("created_at")

    return ParsedLot(
        source_id=str(item["id"]),
        url=f"{BASE}/ru/mortgage/{item['id']}",
        title=title,
        origin=ORIGINS.get(item.get("realisation_type_id"), "bank_pledge"),
        category=category,
        sale_type="direct",
        description=nz.clean_text(item.get("additional_data_ru")),
        region=nz.normalize_region(location, city=city),
        city=city,
        address=location or None,
        area_m2=nz.parse_number(re_data.get("total_area")),
        rooms=rooms,
        floor=nz.parse_int(re_data.get("floor")),
        floors_total=nz.parse_int(re_data.get("total_floor")),
        year_built=nz.parse_int(item.get("year")),
        price=nz.parse_number(item.get("price")),
        published_at=datetime.fromisoformat(published.replace("Z", "+00:00")) if published else None,
        images=[BASE + p if p.startswith("/") else p for p in item.get("images") or []],
        contacts={k: v for k, v in {
            "name": item.get("contact_name"), "position": item.get("contact_position"),
            "phone": item.get("mob_phone") or item.get("work_phone"),
        }.items() if v},
        extra={"realisation_type": realisation.get("name_ru"),
               "living_area": nz.parse_number(re_data.get("living_area"))},
    )


class FreedomParser(Parser):
    name = "freedom"
    title = "Freedom Bank"
    base_url = f"{BASE}/ru/mortgage"

    def fetch(self, http: HttpClient, known: Mapping[str, float | None]) -> Iterator[ParsedLot]:
        resp = http.get(
            f"{BASE}/api/mortgage/get-filtered-data",
            params={"city_id": "all", "realisation_type_id": "all", "mortgage_type_id": REALESTATE_TYPE_ID,
                    "sort": "fresh"},
            headers={"Accept": "application/json", "X-Requested-With": "XMLHttpRequest"},
        )
        for item in resp.json()["data"]["data"]:
            if lot := parse_item(item):
                yield lot
