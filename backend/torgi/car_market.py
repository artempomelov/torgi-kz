"""Оценка машин по рынку: объявления aster.kz о продаже машин с пробегом → медиана цены той же модели того же года.

    uv run python -m torgi.cli market cars --out car-market-index.json   # собрать и сохранить сводку (≈45 минут)

Как и с krisha.kz: берём только цифры из страниц выдачи (модель, год, цена, пробег) — без фото, телефонов и
текстов; запросы — не чаще раза в 1,5 секунды. Объявления лежат в market.db, наружу — только медианы.
kolesa.kz программам данные не отдаёт; медианы aster.kz сошлись с ручной сверкой по kolesa.kz (20–21.10.2026):
Changan CS55 Plus 2025 — 9,6 против 9,7 млн, CS75 Plus 2025 — 11,2 против 11,5, Tiggo 2 Pro 2025 — 5,8 против 5,7.
"""

import html
import json
import logging
import re
import sqlite3
import statistics
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

from torgi.market import DELAY_S, KEEP_DAYS, UA

log = logging.getLogger(__name__)

BASE = "https://aster.kz/cars/used"
MAX_PAGES = 1600  # ~32 тыс. объявлений по 24 на странице
MIN_SAMPLE = 5
MIN_DISCOUNT, MAX_DISCOUNT = 5, 40
# на фото и в описании проблемы — плашку не ставим: цена ниже из-за них (обременение при аресте снимается продажей)
PROBLEM_RE = re.compile(r"неисправ|ключ|аварийн|дол[ия]|страхов|битая|после дтп", re.I)

_CARD_RE = re.compile(r'<li class="rd-ad-card[^"]*" id="(\d+)"(.*?)(?=<li class="rd-ad-card|\Z)', re.S)
_NAME_RE = re.compile(r'rd-ad-card__name">([^<]+)<')
_PRICE_RE = re.compile(r'rd-ad-card__price">([^<]+)<')
_MILEAGE_RE = re.compile(r"пробегом\s*([\d\s ]+)\s*км")

SCHEMA = """
CREATE TABLE IF NOT EXISTS car_listings (
  id INTEGER PRIMARY KEY,          -- номер объявления на aster.kz
  model TEXT NOT NULL,             -- model_key: «CHANGANCS55PLUS»
  year INTEGER NOT NULL,
  mileage INTEGER,
  price REAL NOT NULL,
  seen_at TEXT NOT NULL
);
"""


def model_key(name: str) -> str:
    """«LADA (ВАЗ) Granta», «Lada» + «Granta», «Changan CS55 Plus» → «LADAGRANTA», «CHANGANCS55PLUS»."""
    name = re.sub(r"\(.*?\)", "", name)
    return re.sub(r"[\s\-_.]", "", name).upper()


def _number(text: str) -> int:
    return int(re.sub(r"\D", "", html.unescape(text)) or 0)


def parse_page(text: str) -> list[dict]:
    out = []
    for ad_id, block in _CARD_RE.findall(text):
        name, price = _NAME_RE.search(block), _PRICE_RE.search(block)
        if not name or not price:
            continue
        m = re.match(r"(.+?)\s+(\d{4})$", html.unescape(name.group(1)).strip())
        value = _number(price.group(1))
        if not m or not value:
            continue
        mileage = _MILEAGE_RE.search(html.unescape(block))
        out.append({"id": int(ad_id), "model": model_key(m.group(1)), "year": int(m.group(2)),
                    "mileage": _number(mileage.group(1)) if mileage else None, "price": value})
    return out


def collect(db: sqlite3.Connection, max_pages: int = MAX_PAGES) -> dict[str, int]:
    """Обойти выдачу «с пробегом» целиком. За последней страницей сайт повторяет её же — там и останавливаемся."""
    db.executescript(SCHEMA)
    client = httpx.Client(timeout=30, headers={"User-Agent": UA, "Accept-Language": "ru"}, follow_redirects=True)
    now = datetime.now(timezone.utc).isoformat()
    stats, seen = {"pages": 0, "listings": 0}, set()
    for page in range(1, max_pages + 1):
        try:
            res = client.get(BASE + (f"?page={page}" if page > 1 else ""))
        except httpx.HTTPError as e:
            log.warning("aster стр. %d: %s", page, e)
            break
        time.sleep(DELAY_S)
        if res.status_code != 200:
            log.warning("aster стр. %d: %s", page, res.status_code)
            break
        rows = [r for r in parse_page(res.text) if r["id"] not in seen]
        if not rows:
            break
        seen.update(r["id"] for r in rows)
        db.executemany(
            "INSERT INTO car_listings (id, model, year, mileage, price, seen_at) "
            "VALUES (:id, :model, :year, :mileage, :price, :seen_at) "
            "ON CONFLICT(id) DO UPDATE SET price = excluded.price, mileage = excluded.mileage, seen_at = excluded.seen_at",
            [{**r, "seen_at": now} for r in rows],
        )
        stats["pages"] += 1
        stats["listings"] += len(rows)
        if page % 100 == 0:
            db.commit()
            log.info("aster: %d страниц, %d объявлений", page, stats["listings"])
    cutoff = (datetime.now(timezone.utc) - timedelta(days=KEEP_DAYS)).isoformat()
    db.execute("DELETE FROM car_listings WHERE seen_at < ?", (cutoff,))
    db.commit()
    return stats


@dataclass
class CarEstimate:
    price: float  # медиана цены предложения
    sample: int
    spread: float  # (Q3 − Q1) / медиана
    mileage: float | None  # медиана пробега в сегменте


class CarIndex:
    """Медианы цен по (модель, год): {"CHANGANCS55PLUS|2025": [Q1, медиана, Q3, n, медиана пробега]}."""

    def __init__(self, stats: dict[str, list], updated_at: str | None = None):
        self.stats = stats
        self.updated_at = updated_at

    @classmethod
    def from_db(cls, db: sqlite3.Connection) -> "CarIndex":
        groups: dict[str, list[tuple]] = {}
        for model, year, mileage, price in db.execute("SELECT model, year, mileage, price FROM car_listings"):
            groups.setdefault(f"{model}|{year}", []).append((price, mileage))
        stats = {}
        for key, rows in groups.items():
            if len(rows) >= MIN_SAMPLE:
                q1, med, q3 = statistics.quantiles([p for p, _ in rows], n=4)
                km = [m for _, m in rows if m]
                stats[key] = [round(q1), round(med), round(q3), len(rows), round(statistics.median(km)) if km else None]
        updated = db.execute("SELECT MAX(seen_at) FROM car_listings").fetchone()[0]
        return cls(stats, updated)

    def to_json(self, path: Path) -> None:
        data = {"updated_at": self.updated_at, "source": "aster.kz, цены предложения", "segments": dict(sorted(self.stats.items()))}
        path.write_text(json.dumps(data, ensure_ascii=False, indent=0), encoding="utf-8")

    @classmethod
    def from_json(cls, path: Path) -> "CarIndex":
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls(data["segments"], data.get("updated_at"))

    def estimate(self, brand: str | None, model: str | None, year: int | None) -> CarEstimate | None:
        if not brand or not model or not year:
            return None
        row = self.stats.get(f"{model_key(f'{brand} {model}')}|{year}")
        if not row:
            return None
        q1, med, q3, n, km = row
        return CarEstimate(price=med, sample=n, spread=(q3 - q1) / med, mileage=km)


def car_badge(car: dict, index: CarIndex) -> dict | None:
    """Плашка «−N% к рынку» для легковой машины (решение владельца сайта от 21.10.2026): цена против медианы
    объявлений той же модели того же года. Без плашки: повреждения, «нет ключей», доля; пробег намного больше
    обычного для сегмента (дешевизна объяснима); разнородный сегмент; скидка вне 5–40%."""
    if car.get("vehicle_type") != "car" or not car.get("price") or PROBLEM_RE.search(car.get("note") or ""):
        return None
    est = index.estimate(car.get("brand"), car.get("model"), car.get("year"))
    if est is None or est.spread > 0.6:
        return None
    if car.get("mileage_km") and est.mileage and car["mileage_km"] > est.mileage * 1.5 + 20_000:
        return None
    pct = round((1 - car["price"] / est.price) * 100)
    if not MIN_DISCOUNT <= pct < MAX_DISCOUNT:
        return None
    return {"pct": pct, "over": False, "where": "таких же машин в объявлениях"}
