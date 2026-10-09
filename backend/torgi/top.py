"""Раздел «ТОП» сайта: самые выгодные объекты относительно рынка (оценка — torgi.market.MarketIndex).

Отбор: оценка надёжная (не «низкая»), ниже рынка на 10–60% (больше — почти всегда ошибка данных),
без пометок об ошибках, аренды и долей; из одного дома или ЖК — не больше двух объектов,
иначе один застройщик-залогодатель занимает весь список.
"""

import re
from dataclasses import dataclass
from typing import Callable

from torgi import normalize as nz
from torgi.market import MarketIndex, confidence
from torgi.models import Lot

TOP_SIZE = 10
MIN_DISCOUNT, MAX_DISCOUNT = 10, 55
# правдоподобная площадь: «квартира» 463 м² — обычно несколько квартир или целый этаж одним лотом
AREA_RANGE = {"apartment": (20, 200), "house": (40, 400), "commercial": (15, 1500)}
PER_BUILDING = 2
BIG_CITIES = ("Алматы", "Астана")


@dataclass
class Section:
    slug: str
    title: str
    subtitle: str
    match: Callable[[dict], bool]


SECTIONS = [
    Section("kvartiry-almaty", "ТОП-10 квартир в Алматы", "Самые выгодные квартиры с торгов и из залогов в Алматы",
            lambda x: x["category"] == "apartment" and x["city"] == "Алматы"),
    Section("kvartiry-astana", "ТОП-10 квартир в Астане", "Самые выгодные квартиры с торгов и из залогов в Астане",
            lambda x: x["category"] == "apartment" and x["city"] == "Астана"),
    Section("kvartiry-regiony", "ТОП-10 квартир в регионах", "Караганда, Шымкент, Уральск, Актау и другие города",
            lambda x: x["category"] == "apartment" and x["city"] not in BIG_CITIES),
    Section("kvartiry-do-30-mln", "ТОП-10 квартир до 30 млн ₸", "Лучшие предложения для небольшого бюджета по всей стране",
            lambda x: x["category"] == "apartment" and x["price"] <= 30_000_000),
    Section("doma", "ТОП-10 домов", "Частные дома ниже рынка",
            lambda x: x["category"] == "house"),
    Section("kommercheskaya", "ТОП-10 коммерческой недвижимости",
            "Офисы, магазины и помещения ниже рынка — оценка приблизительная: назначение помещений разное",
            lambda x: x["category"] == "commercial"),
]

_ZHK_RE = re.compile(r"\bжк\s*[«\"']?([\w-]+)", re.I)
_HOUSE_RE = re.compile(r"([а-яёәіңғүұқөһa-z]{4,})[\w.]*[\s,]+(?:д\.\s*|дом\s*)?(\d+)[а-яa-z]?(?:/\d+)?\b", re.I)


def building_key(item: dict, address: str | None, title: str | None = None) -> str:
    """Один дом/ЖК: «ЖК Европолис» или «улица + номер дома» (без квартиры и корпуса: 54/25 и 54/30 — один ЖК)."""
    text = re.split(r",?\s*(?:кв\.?|квартира|н\.п\.?|пом\.?|офис)\s*\d", address or "", maxsplit=1, flags=re.I)[0].lower()
    if m := _ZHK_RE.search(f"{text} {title or ''}"):
        return f"{item['city']}|жк {m.group(1)}"
    houses = _HOUSE_RE.findall(text)
    if houses:
        street, number = houses[-1]
        return f"{item['city']}|{street[:6]}|{number}"
    return f"id|{item['id']}"


def build(items: list[dict], lots: dict[int, Lot], index: MarketIndex) -> dict:
    """items — публичные лоты выгрузки (город и район уже сверены), lots — те же лоты из базы (адрес, заголовок)."""
    candidates = []
    for x in items:
        lot = lots.get(x["id"])
        if lot is None or not x.get("price") or x.get("flags") or nz.deal_flags(lot.title):
            continue
        lo, hi = AREA_RANGE.get(x["category"], (0, 0))
        if not x.get("area_m2") or not lo <= x["area_m2"] <= hi:
            continue
        est = index.estimate(x["category"], x.get("city") or x.get("region"), x.get("district"), x.get("rooms"), x.get("area_m2"))
        if est is None:
            continue
        level = confidence(est, x.get("district"))
        discount = (1 - x["price"] / est.value) * 100
        if level == "низкая" or not MIN_DISCOUNT <= discount < MAX_DISCOUNT:
            continue
        candidates.append({
            "item": x,
            "building": building_key(x, lot.address, lot.title),
            # однотипные лоты одного продавца (офисы одного ЖК с разными адресами) — тоже не больше двух
            "series": f"{x['source']}|{x.get('city')}|{x.get('district')}|{round(x['price'] / x['area_m2'], -4)}",
            "top": {
                "id": x["id"],
                "estimate": round(est.value, -4),
                "market_m2": round(est.ppm, -2),
                "discount_pct": round(discount),
                "segment": est.segment,
                "sample": est.sample,
                "confidence": level,
            },
        })
    candidates.sort(key=lambda c: -c["top"]["discount_pct"])

    sections = []
    for section in SECTIONS:
        picked, per_building = [], {}
        for c in candidates:
            if not section.match(c["item"]):
                continue
            if any(per_building.get(k, 0) >= PER_BUILDING for k in (c["building"], c["series"])):
                continue
            for k in (c["building"], c["series"]):
                per_building[k] = per_building.get(k, 0) + 1
            picked.append(c["top"])
            if len(picked) == TOP_SIZE:
                break
        if len(picked) >= 3:
            sections.append({"slug": section.slug, "title": section.title, "subtitle": section.subtitle, "items": picked})
    return {"market_updated_at": index.updated_at, "sections": sections}
