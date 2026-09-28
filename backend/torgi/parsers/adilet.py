"""etp.adilet.gov.kz — ЕЭТП Минюста: арестованное имущество (торги ЧСИ).

Список отдаётся HTML-фрагментом, внутри которого лежит JSON:
    window.$UM.stateData = {"$top": {"trades": {"items": [...], "total": N}}, ...};
"""

import json
import re
from collections.abc import Iterator, Mapping
from datetime import datetime, timezone
from typing import Any

from torgi import normalize as nz
from torgi.parsers.base import HttpClient, ParsedLot, Parser

BASE = "https://etp.adilet.gov.kz"
PAGE_SIZE = 300

# Классификатор площадки → наша категория (None — определить по тексту)
REAL_ESTATE_CLASSIFIERS: dict[str, str | None] = {
    "жилые помещения": None,
    "земельные участки": "land",
    "нежилые помещения": "commercial",
    "здания и сооружения": None,
    "прочая недвижимость": None,
    "промышленный комплекс": "industrial",
    "гаражи": "parking",
}

_STATE_RE = re.compile(r"window\.\$UM\.stateData\s*=\s*(\{.*?\});\s*$", re.S | re.M)
# "89.500" — площадь в описании идёт отдельным полем с тремя знаками после точки
_AREA_FIELD_RE = re.compile(r"\d+\.\d{3}")
_ADDRESS_RE = re.compile(r"(?:по адресу|расположенн\w* по адресу|адрес)\s*[:\-]?\s*([^\n]+)", re.I)


def extract_state(html: str) -> dict[str, Any]:
    m = _STATE_RE.search(html)
    if not m:
        raise ValueError("etp.adilet: не найден window.$UM.stateData")
    return json.loads(m.group(1))


def _ms_to_dt(value: int | None) -> datetime | None:
    return datetime.fromtimestamp(value / 1000, tz=timezone.utc) if value else None


def _object_line(description: str) -> str:
    for line in description.splitlines():
        if line.startswith("Объект:"):
            return line.removeprefix("Объект:").strip()
    return ""


def _comment(description: str) -> str:
    for line in description.splitlines():
        if line.startswith("Комментарий:"):
            return line.removeprefix("Комментарий:").strip().rstrip(",").strip()
    return ""


def parse_trade(item: dict[str, Any]) -> ParsedLot | None:
    classifier = (item.get("procurementClassifiers") or [{}])[0].get("title", "").strip().lower()
    if classifier not in REAL_ESTATE_CLASSIFIERS:
        return None

    lot = (item.get("lots") or [{}])[0]
    description = lot.get("goodsDescription") or ""
    title = (item.get("title") or lot.get("title") or "").strip()
    obj = _object_line(description)
    comment = _comment(description)

    category = REAL_ESTATE_CLASSIFIERS[classifier] or nz.classify_category(title, obj, comment)
    if classifier == "жилые помещения" and category not in ("apartment", "house"):
        category = "house" if re.search(r"дом|үй|ижс", f"{title} {obj}", re.I) else "apartment"

    # "класс, 1.000 ШТУКА, ..., 89.500, Карагандинская, Казыбек Би Район, ..., 16/9, н.п.2,"
    # Второе поле — количество (1.000), дальше — площадь числом с тремя знаками и адрес.
    fields = [f.strip() for f in obj.split(",")]
    area_value = address = None
    for i, f in enumerate(fields[2:], start=2):
        if _AREA_FIELD_RE.fullmatch(f):
            area_value = float(f)
            address = ", ".join(x for x in fields[i + 1:] if x) or None
            break
    if not address and (m := _ADDRESS_RE.search(comment)):
        address = m.group(1).strip(" ,")
    if not address:
        # адрес начинается с поля-региона/города: "..., индивидуальный жилой дом, Алматы, Алматы, Есенжанова Х, 33"
        for i, f in enumerate(fields[2:], start=2):
            if len(f) < 40 and (nz.detect_city(f) or nz.normalize_region(f)):
                tail = [x for j, x in enumerate(fields[i:]) if x and (j == 0 or x != fields[i + j - 1])]
                address = ", ".join(tail) or None
                break

    area_m2 = land_ha = None
    if category == "land":
        land_ha = nz.parse_land_ha(comment) or area_value
    else:
        area_m2 = nz.parse_area_m2(comment) or nz.parse_area_m2(title) or area_value
        land_ha = nz.parse_land_ha(comment)

    region_raw = item.get("region")
    city = nz.detect_city(region_raw, address, comment)
    region = nz.normalize_region(region_raw, address, city=city)
    floor, floors_total = nz.parse_floor(comment)

    images = [BASE + img["href"] for img in item.get("images") or [] if img.get("href")]

    return ParsedLot(
        source_id=str(item["id"]),
        url=f"{BASE}/trades/{item['id']}",
        title=title,
        origin="arrested",
        category=category,
        sale_type="auction_down" if lot.get("methodAucDown") else "auction",
        description=nz.clean_text(description),
        region=region,
        city=city,
        address=address,
        area_m2=area_m2,
        land_area_ha=land_ha,
        rooms=nz.parse_rooms(f"{title} {obj} {comment}") if category == "apartment" else None,
        floor=floor,
        floors_total=floors_total,
        cadastral=nz.parse_cadastral(f"{title} {obj}"),
        price=nz.parse_number(item.get("initialContractPrice") or lot.get("initialContractPrice")),
        deposit=nz.parse_number(item.get("assuranceAmount")),
        auction_start=_ms_to_dt(item.get("tradeStartDate")),
        applications_deadline=_ms_to_dt(item.get("bidSubmissionEndDate")),
        published_at=_ms_to_dt(item.get("registeredDate")),
        images=images,
        extra={
            "registered_number": item.get("registeredNumber"),
            "classifier": classifier,
            "procurement_method": item.get("procurementMethodTitle"),
            "status": (item.get("processStatus") or {}).get("title"),
            "deposit_percent": item.get("assurancePercents"),
            "encumbrance": "Имеются обременения" in description,
            "organizer": (item.get("owner") or {}).get("title"),
        },
    )


class AdiletParser(Parser):
    name = "adilet"
    title = "ЕЭТП Минюста (арестованное имущество)"
    base_url = BASE

    def fetch(self, http: HttpClient, known: Mapping[str, float | None]) -> Iterator[ParsedLot]:
        skip = 0
        while True:
            resp = http.get(
                f"{BASE}/trades",
                params={"page": "sales", "limit": PAGE_SIZE, "skip": skip},
                headers={"X-Requested-With": "XMLHttpRequest"},
            )
            trades = extract_state(resp.text)["$top"]["trades"]
            items = trades.get("items") or []
            for item in items:
                if parsed := parse_trade(item):
                    yield parsed
            skip += len(items)
            if not items or skip >= int(trades.get("total") or 0):
                break
