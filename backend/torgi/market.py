"""Собственная оценка лотов по рынку: цены предложения на krisha.kz → рыночная цена м² → «справедливая» цена лота.

    uv run python -m torgi.cli market collect [--pages 25]   # собрать объявления (≈10–15 минут)
    uv run python -m torgi.cli market report                 # оценить активные лоты → reports/valuation.csv

Пока это внутренний инструмент: объявления и оценки лежат в отдельной базе market.db рядом с torgi.db
и в публичную выгрузку сайта / релиз «data» не попадают. С Крыши берём только цифры (цена, площадь,
комнаты, район) из страниц выдачи — без телефонов, фото и текстов; запросы — не чаще раза в 1,5 секунды.

Оценка — медиана цены м² похожих объявлений: город → район → комнатность (для квартир) или размер
(для коммерции). Если в узком сегменте меньше MIN_SAMPLE объявлений, берём сегмент шире.
Цены предложения обычно выше цен сделок на 5–10% — это учитывается при чтении скидки.
"""

import csv
import logging
import re
import sqlite3
import statistics
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from torgi import normalize as nz
from torgi.export import district as address_district
from torgi.models import Lot

log = logging.getLogger(__name__)

BASE = "https://krisha.kz"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
DELAY_S = 1.5
KEEP_DAYS = 90  # объявления старше — не учитываем и удаляем
MIN_SAMPLE = 8
DB_PATH = Path(__file__).resolve().parents[1] / "market.db"
REPORT_DIR = Path(__file__).resolve().parents[1] / "reports"

# slug города на Крыше → название, как в наших данных
CITIES: dict[str, str] = {
    "almaty": "Алматы", "astana": "Астана", "shymkent": "Шымкент", "karaganda": "Караганда",
    "aktobe": "Актобе", "atyrau": "Атырау", "aktau": "Актау", "pavlodar": "Павлодар",
    "ust-kamenogorsk": "Усть-Каменогорск", "kostanaj": "Костанай", "taraz": "Тараз", "uralsk": "Уральск",
    "semej": "Семей", "kyzylorda": "Кызылорда", "petropavlovsk": "Петропавловск", "turkestan": "Туркестан",
    "kokshetau": "Кокшетау", "taldykorgan": "Талдыкорган", "ekibastuz": "Экибастуз", "temirtau": "Темиртау",
    "konaev": "Конаев",
}
BIG = {"almaty", "astana", "shymkent"}
# раздел Крыши → наша категория
SECTIONS = {"kvartiry": "apartment", "doma-dachi": "house", "kommercheskaya-nedvizhimost": "commercial"}

_CARD_RE = re.compile(r'<div\s+data-id="(\d+)"(.*?)(?=<div\s+data-id="\d+"|\Z)', re.S)
_TITLE_RE = re.compile(r'class="a-card__title[^"]*"[^>]*>([^<]+)<')
_PRICE_RE = re.compile(r'class="a-card__price">\s*([^<]+)<')
_SUBTITLE_RE = re.compile(r'class="a-card__subtitle[^"]*">\s*([^<]+?)\s*<')
_AREA_RE = re.compile(r"([\d.]+)\s*м²")
_ROOMS_RE = re.compile(r"(\d+)-комнатн|(\d+)\s+комнат")

SCHEMA = """
CREATE TABLE IF NOT EXISTS listings (
  id INTEGER PRIMARY KEY,          -- номер объявления на Крыше
  category TEXT NOT NULL,
  city TEXT NOT NULL,
  district TEXT,
  rooms INTEGER,
  area REAL NOT NULL,
  price REAL NOT NULL,
  seen_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS listings_seg ON listings (category, city, district);
"""


def connect(path: Path = DB_PATH) -> sqlite3.Connection:
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    db.executescript(SCHEMA)
    return db


def _number(text: str) -> float | None:
    digits = re.sub(r"[^\d]", "", text.replace("&nbsp;", ""))
    return float(digits) if digits else None


def parse_page(html: str, category: str, city: str) -> list[dict]:
    """Карточки страницы выдачи → цифры объявлений. Цены «от …» и без площади пропускаем."""
    out = []
    for ad_id, block in _CARD_RE.findall(html):
        title, price = _TITLE_RE.search(block), _PRICE_RE.search(block)
        if not title or not price or price.group(1).strip().startswith("от"):
            continue
        area = _AREA_RE.search(title.group(1))
        value = _number(price.group(1))
        if not area or not value:
            continue
        rooms = _ROOMS_RE.search(title.group(1))
        subtitle = _SUBTITLE_RE.search(block)
        district = None
        if subtitle:
            first = subtitle.group(1).split(",")[0].strip()
            if "р-н" in first:
                district = nz.canonical_district(first, city)
        out.append({
            "id": int(ad_id), "category": category, "city": city, "district": district,
            "rooms": int(rooms.group(1) or rooms.group(2)) if rooms else None,
            "area": float(area.group(1)), "price": value,
        })
    return out


def collect(db: sqlite3.Connection, pages: int = 25, cities: list[str] | None = None) -> dict[str, int]:
    """Обойти выдачу Крыши: по городам и разделам, первые N страниц (в крупных городах — вдвое больше)."""
    client = httpx.Client(timeout=30, headers={"User-Agent": UA, "Accept-Language": "ru"}, follow_redirects=True)
    now = datetime.now(timezone.utc).isoformat()
    stats = {"pages": 0, "listings": 0}
    for slug in cities or CITIES:
        city = CITIES[slug]
        for section, category in SECTIONS.items():
            limit = pages * 2 if slug in BIG and category == "apartment" else pages // (1 if slug in BIG else 2)
            for page in range(1, max(limit, 1) + 1):
                url = f"{BASE}/prodazha/{section}/{slug}/" + (f"?page={page}" if page > 1 else "")
                try:
                    res = client.get(url)
                except httpx.HTTPError as e:
                    log.warning("krisha %s: %s", url, e)
                    break
                time.sleep(DELAY_S)
                if res.status_code != 200:
                    log.warning("krisha %s: %s", url, res.status_code)
                    break
                rows = parse_page(res.text, category, city)
                stats["pages"] += 1
                if not rows:
                    break
                db.executemany(
                    "INSERT INTO listings (id, category, city, district, rooms, area, price, seen_at) "
                    "VALUES (:id, :category, :city, :district, :rooms, :area, :price, :seen_at) "
                    "ON CONFLICT(id) DO UPDATE SET price = excluded.price, district = excluded.district, "
                    "seen_at = excluded.seen_at",
                    [{**r, "seen_at": now} for r in rows],
                )
                stats["listings"] += len(rows)
            db.commit()
            log.info("krisha %s / %s: собрано, всего %d", city, section, stats["listings"])
    cutoff = (datetime.now(timezone.utc) - timedelta(days=KEEP_DAYS)).isoformat()
    db.execute("DELETE FROM listings WHERE seen_at < ?", (cutoff,))
    db.commit()
    return stats


# --- оценка ----------------------------------------------------------------------------------------

def _rooms_bucket(rooms: int | None) -> str | None:
    return None if not rooms else str(min(rooms, 4))


def _size_bucket(area: float) -> str:
    return "S" if area < 100 else "M" if area < 500 else "L"


# допустимая цена м² — отсекаем опечатки и «цену за сотку»
PPM_RANGE = {"apartment": (80_000, 5_000_000), "house": (30_000, 5_000_000), "commercial": (30_000, 8_000_000)}


@dataclass
class Estimate:
    ppm: float  # рыночная цена м² (медиана предложения)
    value: float  # оценка лота
    sample: int  # сколько объявлений в сегменте
    segment: str  # по какому сегменту оценили
    spread: float  # разброс: (Q3 − Q1) / медиана — чем меньше, тем надёжнее


class MarketIndex:
    """Медианы цены м² по сегментам из market.db."""

    def __init__(self, db: sqlite3.Connection):
        self.ppm: dict[tuple, list[float]] = {}
        for r in db.execute("SELECT category, city, district, rooms, area, price FROM listings"):
            lo, hi = PPM_RANGE[r["category"]]
            ppm = r["price"] / r["area"]
            if not lo <= ppm <= hi:
                continue
            for key in self._keys(r["category"], r["city"], r["district"], r["rooms"], r["area"]):
                self.ppm.setdefault(key, []).append(ppm)

    @staticmethod
    def _keys(category: str, city: str, district: str | None, rooms: int | None, area: float) -> list[tuple]:
        """Сегменты от узкого к широкому."""
        extra = _rooms_bucket(rooms) if category == "apartment" else _size_bucket(area) if category == "commercial" else None
        keys = []
        if district and extra:
            keys.append((category, city, district, extra))
        if district:
            keys.append((category, city, district, None))
        if extra:
            keys.append((category, city, None, extra))
        keys.append((category, city, None, None))
        return keys

    def estimate(self, category: str, city: str | None, district: str | None, rooms: int | None,
                 area: float | None) -> Estimate | None:
        if category not in PPM_RANGE or not city or not area:
            return None
        for key in self._keys(category, city, district, rooms, area):
            values = self.ppm.get(key, [])
            if len(values) >= MIN_SAMPLE:
                q1, med, q3 = statistics.quantiles(values, n=4)
                segment = " · ".join(str(k) for k in key[1:] if k)
                return Estimate(ppm=med, value=med * area, sample=len(values), segment=segment, spread=(q3 - q1) / med)
        return None


def confidence(est: Estimate, district: str | None) -> str:
    """Надёжность оценки: высокая — район и узкий разброс цен, низкая — разнородный сегмент."""
    if est.spread <= 0.45 and est.sample >= 15 and district and district in est.segment:
        return "высокая"
    if est.spread <= 0.7:
        return "средняя"
    return "низкая"


def report(session: Session, db: sqlite3.Connection, out: Path | None = None) -> dict[str, int]:
    """Оценка всех активных лотов → CSV (по убыванию скидки к рынку)."""
    index = MarketIndex(db)
    rows = []
    lots = session.scalars(select(Lot).where(Lot.status == "active")).all()
    for lot in lots:
        city, _ = nz.reconcile_place(lot.city, lot.region, lot.address, lot.title)
        district = nz.canonical_district(address_district(nz.clean_address(lot.address or "")), city)
        est = index.estimate(lot.category, city, district, lot.rooms, lot.area_m2)
        if not est or not lot.price or lot.flags or nz.deal_flags(lot.title):
            continue
        discount = (1 - lot.price / est.value) * 100
        rows.append({
            "id": lot.id,
            "url": f"https://torgi.kz/lots/{lot.id}/",
            "category": lot.category,
            "city": city,
            "district": district or "",
            "rooms": lot.rooms or "",
            "area_m2": lot.area_m2,
            "price": round(lot.price),
            "price_m2": round(lot.price / lot.area_m2),
            "market_m2": round(est.ppm),
            "estimate": round(est.value),
            "discount_pct": round(discount, 1),
            "confidence": confidence(est, district),
            "note": "проверить вручную" if abs(discount) >= 60 else "",
            "sample": est.sample,
            "segment": est.segment,
            "spread": round(est.spread, 2),
        })
    rows.sort(key=lambda r: -r["discount_pct"])
    out = out or REPORT_DIR / "valuation.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    if rows:
        with out.open("w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]), delimiter=";")
            w.writeheader()
            w.writerows(rows)
    return {"active": len(lots), "estimated": len(rows), "segments": len(index.ppm)}
