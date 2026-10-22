"""Раздел «ТОП» сайта: выгодные и презентабельные объекты относительно рынка (оценка — torgi.market.MarketIndex).

Основа — ручной отбор (top_picks.json): лоты, отобранные по фото — нормальное состояние, реальные фото интерьера,
для карточки выбрано лучшее фото. Самая большая «скидка» обычно у недостроев, черновой отделки и разрухи —
такие объекты никому не интересны, поэтому автоматический рейтинг по скидке — только запасной вариант для раздела
без ручного списка. Его правила: оценка надёжная (не «низкая»), ниже рынка на 10–45%, не меньше 4 фото, без
недостроя и черновой отделки, без пометок об ошибках, аренды и долей; из одного дома или ЖК — не больше двух.
В Алматы и Астане — только с известным районом: оценка по всему городу завышает скидку окраин.
"""

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from torgi import normalize as nz
from torgi.market import SHELL, MarketIndex, confidence
from torgi.models import Lot, utcnow

TOP_SIZE = 10
MIN_DISCOUNT, MAX_DISCOUNT = 10, 45
MIN_PHOTOS = 4
# объекты с проблемами: их «скидка» — плата за проблемы (решение владельца сайта от 18.10.2026)
PROBLEM_RE = re.compile(r"недостро|незаверш|чернов|без отделки|предчистов|капремонт|аварийн|под снос|котлован", re.I)
# вне Алматы и Астаны оценка грубее — скидку больше 30% показываем как «более 30%»
REGION_DISCOUNT_CAP = 30
PICKS_FILE = Path(__file__).with_name("top_picks.json")
# правдоподобная площадь: «квартира» 463 м² — обычно несколько квартир или целый этаж одним лотом
AREA_RANGE = {"apartment": (20, 200), "house": (40, 400), "commercial": (15, 1500)}
PER_BUILDING = 2
BIG_CITIES = ("Алматы", "Астана")
# ЖК, которые в ТОП не берём (в каталоге они остаются): «Европолис» — сотня однотипных лотов Halyk в черновой
# отделке, решение владельца сайта от 17.10.2026
EXCLUDED_RE = re.compile(r"европолис", re.I)


@dataclass
class Section:
    slug: str
    title: str
    subtitle: str
    match: Callable[[dict], bool]


# порядок — как на сайте (решение владельца): Алматы, Астана, коммерция, регионы, дома, до 30 млн;
# {n} в названии — сколько объектов в разделе на самом деле
SECTIONS = [
    Section("kvartiry-almaty", "ТОП-{n} квартир в Алматы", "Самые выгодные квартиры с торгов и из залогов в Алматы",
            lambda x: x["category"] == "apartment" and x["city"] == "Алматы"),
    Section("kvartiry-astana", "ТОП-{n} квартир в Астане", "Самые выгодные квартиры с торгов и из залогов в Астане",
            lambda x: x["category"] == "apartment" and x["city"] == "Астана"),
    Section("kommercheskaya", "ТОП-{n} коммерческой недвижимости",
            "Офисы, салоны, помещения и готовый бизнес ниже рынка — оценка приблизительная: назначение помещений разное",
            lambda x: x["category"] == "commercial"),
    Section("kvartiry-regiony", "ТОП-{n} квартир в регионах", "Караганда, Шымкент, Уральск, Актау и другие города",
            lambda x: x["category"] == "apartment" and x["city"] not in BIG_CITIES),
    Section("doma", "ТОП-{n} домов", "Частные дома ниже рынка",
            lambda x: x["category"] == "house"),
    Section("kvartiry-do-30-mln", "ТОП-{n} квартир до 30 млн ₸", "Лучшие предложения для небольшого бюджета по всей стране",
            lambda x: x["category"] == "apartment" and x["price"] <= 30_000_000),
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


def load_picks(path: Path = PICKS_FILE) -> dict[str, list[dict]]:
    """Ручной отбор: {раздел: [{"id": лот, "photo": номер фото для карточки, "district": район, если его нет в данных}]}."""
    return json.loads(path.read_text(encoding="utf-8"))["sections"] if path.exists() else {}


def _estimate(x: dict, index: MarketIndex, district: str | None = None, shell: bool = False) -> dict | None:
    """Оценка лота для ТОПа; вне Алматы и Астаны большую скидку показываем как «более 30%».
    shell — черновая отделка: сравниваем только с черновыми объявлениями."""
    district = district or x.get("district")
    category = x["category"] + SHELL if shell else x["category"]
    est = index.estimate(category, x.get("city") or x.get("region"), district, x.get("rooms"), x.get("area_m2"))
    if est is None:
        return None
    discount = round((1 - x["price"] / est.value) * 100)
    top = {
        "id": x["id"],
        "estimate": round(est.value, -4),
        "market_m2": round(est.ppm, -2),
        "discount_pct": discount,
        "segment": est.segment,
        "sample": est.sample,
        "confidence": confidence(est, district),
    }
    if x.get("city") not in BIG_CITIES and discount > REGION_DISCOUNT_CAP:
        top["discount_note"] = f"более {REGION_DISCOUNT_CAP}%"
    top["where"] = where_phrase(x.get("city") or x.get("region"), district if district and district in est.segment else None)
    return top


BADGE_CATEGORIES = ("apartment", "house", "commercial")
FINISHED_RE = re.compile(r"ремонт|(?<!пред)чистов", re.I)
# плашка — от −5% (решение владельца сайта от 21.10.2026), в ТОП — от −10%
BADGE_MIN_DISCOUNT = 5
# черновую отделку в Алматы и Астане оцениваем по черновым аналогам, в регионах — нет (решение от 21.10.2026);
# настоящие проблемы (недострой, аварийность) — без плашки везде
SHELL_TEXT_RE = re.compile(r"чернов|без отделки|предчистов", re.I)
DEFECT_RE = re.compile(r"недостро|незаверш|капремонт|аварийн|под снос|котлован", re.I)


def where_phrase(city: str | None, district: str | None) -> str:
    """«в Бостандыкском районе», «в районе Есиль», «в г. Караганда»."""
    if district:
        if m := re.fullmatch(r"(.+?)(?:ий|ый|ой) район", district):
            return f"в {m.group(1)}ом районе"
        return f"в районе {district.removeprefix('район ')}"
    return f"в г. {city}"


def market_badge(x: dict, lot: Lot, index: MarketIndex) -> dict | None:
    """Плашка «−N% к рынку» на карточке лота (решение владельца сайта от 20.10.2026): текущая цена против средней
    цены м² похожих объектов в районе (вне районов — в городе). Предохранители: без недостроя, долей и аренды,
    с правдоподобной площадью, надёжной оценкой и скидкой 5–45%; черновая отделка — только в Алматы и Астане
    и только против черновых объявлений."""
    if x["category"] not in BADGE_CATEGORIES or not x.get("price") or x.get("flags"):
        return None
    text = f"{lot.title or ''} {lot.description or ''} {' '.join(str(v) for v in (lot.extra or {}).values())}"
    if nz.deal_flags(lot.title, lot.description) or DEFECT_RE.search(text) or EXCLUDED_RE.search(f"{lot.address or ''} {text}"):
        return None
    # новостройки последних лет на торгах обычно без отделки (голый бетон), если ремонт не назван: квартиры
    # госимущества 2023–2024 гг. в Астане на фото — бетон, а в тексте об отделке ни слова
    new_build = (lot.year_built or 0) >= utcnow().year - 3 and not FINISHED_RE.search(text)
    shell = bool(SHELL_TEXT_RE.search(text)) or new_build
    city, district = x.get("city") or x.get("region"), x.get("district")
    if shell and city not in BIG_CITIES:
        return None
    lo, hi = AREA_RANGE[x["category"]]
    if not x.get("area_m2") or not lo <= x["area_m2"] <= hi:
        return None
    if city in BIG_CITIES and not district:
        return None  # оценка по всему городу завышает скидку окраин
    est = _estimate(x, index, shell=shell)
    if est is None or est["confidence"] == "низкая" or not BADGE_MIN_DISCOUNT <= est["discount_pct"] < MAX_DISCOUNT:
        return None
    capped = "discount_note" in est
    where = where_phrase(city, district if district and district in est["segment"] else None)
    return {"pct": REGION_DISCOUNT_CAP if capped else est["discount_pct"], "over": capped,
            "where": f"{where} (черновая отделка)" if shell else where}


def _auto_candidates(items: list[dict], lots: dict[int, Lot], index: MarketIndex) -> list[dict]:
    """Запасной рейтинг по скидке — для раздела без ручного списка."""
    candidates = []
    for x in items:
        lot = lots.get(x["id"])
        if lot is None or not x.get("price") or x.get("flags") or nz.deal_flags(lot.title, lot.description):
            continue
        if EXCLUDED_RE.search(f"{lot.address or ''} {lot.title or ''}"):
            continue
        if PROBLEM_RE.search(f"{lot.title or ''} {lot.description or ''}") or len(getattr(lot, "images", None) or []) < MIN_PHOTOS:
            continue
        # решение владельца сайта от 17.10.2026: без района в Алматы и Астане в ТОП не берём (в каталоге остаются)
        if x.get("city") in BIG_CITIES and not x.get("district"):
            continue
        lo, hi = AREA_RANGE.get(x["category"], (0, 0))
        if not x.get("area_m2") or not lo <= x["area_m2"] <= hi:
            continue
        top = _estimate(x, index)
        if top is None or top["confidence"] == "низкая" or not MIN_DISCOUNT <= top["discount_pct"] < MAX_DISCOUNT:
            continue
        candidates.append({
            "item": x,
            "building": building_key(x, lot.address, lot.title),
            # однотипные лоты одного продавца (офисы одного ЖК с разными адресами) — тоже не больше двух
            "series": f"{x['source']}|{x.get('city')}|{x.get('district')}|{round(x['price'] / x['area_m2'], -4)}",
            "top": top,
        })
    candidates.sort(key=lambda c: -c["top"]["discount_pct"])
    return candidates


def _from_picks(picks: list[dict], by_id: dict[int, dict], lots: dict[int, Lot], index: MarketIndex) -> list[dict]:
    """Отобранные вручную лоты, которые ещё в продаже и всё ещё ниже рынка; карточка — с выбранным фото."""
    picked = []
    for p in picks:
        x, lot = by_id.get(p["id"]), lots.get(p["id"])
        if x is None or lot is None or not x.get("price"):
            continue  # снят с торгов
        top = _estimate(x, index, p.get("district"))
        if top is None or top["discount_pct"] < MIN_DISCOUNT:
            continue
        images = getattr(lot, "images", None) or []
        if p.get("photo") is not None and p["photo"] < len(images):
            top["image"] = images[p["photo"]]
        picked.append(top)
    return sorted(picked, key=lambda t: -t["discount_pct"])


def build(items: list[dict], lots: dict[int, Lot], index: MarketIndex, picks: dict[str, list[dict]] | None = None) -> dict:
    """items — публичные лоты выгрузки (город и район уже сверены), lots — те же лоты из базы (адрес, заголовок, фото),
    picks — ручной отбор по разделам (load_picks); раздел без него собирается автоматически."""
    picks = picks or {}
    by_id = {x["id"]: x for x in items}
    candidates = None
    sections = []
    for section in SECTIONS:
        if picks.get(section.slug):
            picked = _from_picks(picks[section.slug], by_id, lots, index)[:TOP_SIZE]
        else:
            candidates = candidates if candidates is not None else _auto_candidates(items, lots, index)
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
            sections.append({"slug": section.slug, "title": section.title.format(n=len(picked)),
                             "subtitle": section.subtitle, "items": picked})
    return {"market_updated_at": index.updated_at, "sections": sections}
