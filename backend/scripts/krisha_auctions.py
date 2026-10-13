"""Разведка: объявления krisha.kz, где продают имущество «с торгов» (перепродажа выигранных лотов, залоги банков).

    uv run python scripts/krisha_auctions.py [--pages 30]

Пока только сбор базы для анализа — на сайт не попадает. Результат: reports/krisha-auctions.db и .csv.
1) Обходим выдачу (города × разделы) и ищем слова в начале описания карточки (~300 символов).
2) Полное описание открываем только у кандидатов: слова уже нашлись или цена м² ниже медианы города на 40%+.
Сохраняем только цифры, район и короткий фрагмент текста вокруг найденного слова — без имён и телефонов.
"""

import argparse
import csv
import re
import sqlite3
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from torgi import normalize as nz  # noqa: E402
from torgi.market import BASE, BIG, CITIES, UA  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "reports"
DELAY_S = 1.5
SECTIONS = {"kvartiry": "apartment", "doma-dachi": "house", "kommercheskaya-nedvizhimost": "commercial",
            "uchastkov": "land"}

# «торги» в смысле аукциона; «торг уместен», «торговый» и каз. «сауда» (торговля) не считаем
STRONG = re.compile(
    r"с\s+торгов\b|на\s+торгах\b|\bторги\b|\bторгов\b(?!…)|аукцион|реализаци\w+\s+(?:с\s+торгов|имущества|залог|банк)"
    r"|залогов\w+\s+имуществ|имуществ\w+\s+банк|от\s+банка|банк\s+продает|банк\s+продаёт|банкрот"
    r"|\bчси\b|судебн\w+\s+исполнител|арестованн|изъят\w+\s+имуществ|[еe]-?qazyna",
    re.I,
)
WEAK = re.compile(r"\bзалог\w*|\bарест\w*", re.I)
NEGATED = re.compile(r"(?:не|без|нет)\s+(?:\w+\s+){0,2}(?:залог|арест)|(?:залог\w*|арест\w*)\s+(?:\w+\s+){0,1}нет", re.I)
PHONE = re.compile(r"(?:\+?7|8)[\s(-]*\d{3}[\s)-]*\d{3}[\s-]*\d{2}[\s-]*\d{2}")

_CARD_RE = re.compile(r'<div\s+data-id="(\d+)"(.*?)(?=<div\s+data-id="\d+"|\Z)', re.S)
_TITLE_RE = re.compile(r'class="a-card__title[^"]*"[^>]*>([^<]+)<')
_PRICE_RE = re.compile(r'class="a-card__price">\s*([^<]+)<')
_SUBTITLE_RE = re.compile(r'class="a-card__subtitle[^"]*">\s*([^<]+?)\s*<')
_PREVIEW_RE = re.compile(r'class="a-card__text-preview"[^>]*>(.*?)</div>', re.S)
_DESCR_RE = re.compile(r'class="js-description[^"]*"[^>]*>(.*?)</div>', re.S)
_AREA_RE = re.compile(r"([\d.]+)\s*м²")
_SOTKI_RE = re.compile(r"([\d.]+)\s*сот")
_ROOMS_RE = re.compile(r"(\d+)-комнатн|(\d+)\s+комнат")
_TAG_RE = re.compile(r"<[^>]+>")

SCHEMA = """
CREATE TABLE IF NOT EXISTS ads (
  id INTEGER PRIMARY KEY, url TEXT, category TEXT, city TEXT, district TEXT, rooms INTEGER,
  area REAL, price REAL, title TEXT, preview TEXT, seen_at TEXT,
  strong TEXT, weak TEXT, checked INTEGER DEFAULT 0, full_strong TEXT, snippet TEXT
);
"""


def clean(html: str) -> str:
    return re.sub(r"\s+", " ", _TAG_RE.sub(" ", html.replace("&nbsp;", " "))).strip()


def matches(text: str) -> tuple[str, str]:
    strong = sorted({m.group().lower() for m in STRONG.finditer(text)})
    neg = NEGATED.sub(" ", text)
    weak = sorted({m.group().lower() for m in WEAK.finditer(neg)})
    return ", ".join(strong), ", ".join(weak)


def snippet(text: str) -> str:
    m = STRONG.search(text) or WEAK.search(NEGATED.sub(" ", text))
    if not m:
        return ""
    return PHONE.sub("[тел.]", text[max(0, m.start() - 120): m.end() + 160]).strip()


def parse(html: str, category: str, city: str) -> list[dict]:
    out = []
    for ad_id, block in _CARD_RE.findall(html):
        title, price = _TITLE_RE.search(block), _PRICE_RE.search(block)
        if not title or not price:
            continue
        digits = re.sub(r"\D", "", price.group(1).replace("&nbsp;", ""))
        if not digits or price.group(1).strip().startswith("от"):
            continue
        t = title.group(1)
        area = _AREA_RE.search(t)
        if category == "land" and (sot := _SOTKI_RE.search(t)):
            area = None
            area_val = float(sot.group(1)) * 100
        else:
            area_val = float(area.group(1)) if area else None
        rooms = _ROOMS_RE.search(t)
        sub = _SUBTITLE_RE.search(block)
        first = sub.group(1).split(",")[0].strip() if sub else ""
        preview = clean(_PREVIEW_RE.search(block).group(1)) if _PREVIEW_RE.search(block) else ""
        strong, weak = matches(f"{t} {preview}")
        out.append({
            "id": int(ad_id), "url": f"{BASE}/a/show/{ad_id}", "category": category, "city": city,
            "district": nz.canonical_district(first, city) if "р-н" in first else None,
            "rooms": int(rooms.group(1) or rooms.group(2)) if rooms else None,
            "area": area_val, "price": float(digits), "title": t,
            "preview": PHONE.sub("[тел.]", preview)[:400], "strong": strong, "weak": weak,
        })
    return out


def crawl(db: sqlite3.Connection, client: httpx.Client, pages: int) -> int:
    now = datetime.now(timezone.utc).isoformat()
    total = 0
    for slug, city in CITIES.items():
        for section, category in SECTIONS.items():
            limit = pages * 3 if slug in BIG else pages
            for page in range(1, limit + 1):
                url = f"{BASE}/prodazha/{section}/{slug}/" + (f"?page={page}" if page > 1 else "")
                try:
                    res = client.get(url)
                except httpx.HTTPError:
                    break
                time.sleep(DELAY_S)
                if res.status_code != 200:
                    break
                rows = parse(res.text, category, city)
                if not rows:
                    break
                db.executemany(
                    "INSERT INTO ads (id,url,category,city,district,rooms,area,price,title,preview,seen_at,strong,weak) "
                    "VALUES (:id,:url,:category,:city,:district,:rooms,:area,:price,:title,:preview,:seen_at,:strong,:weak) "
                    "ON CONFLICT(id) DO UPDATE SET price=excluded.price, preview=excluded.preview, seen_at=excluded.seen_at, "
                    "strong=excluded.strong, weak=excluded.weak",
                    [{**r, "seen_at": now} for r in rows])
                total += len(rows)
            db.commit()
            print(f"{city} / {section}: всего {total}", flush=True)
    return total


def candidates(db: sqlite3.Connection, max_checks: int) -> list[int]:
    """Кого открыть полностью: слова в начале описания или цена м² ниже медианы города на 40%+."""
    # порядок: прямо про торги → сильно дешевле рынка → упоминания залога/ареста (часто «в залоге по ипотеке»)
    ids = [r[0] for r in db.execute("SELECT id FROM ads WHERE checked = 0 AND strong != ''")]
    weak = [r[0] for r in db.execute("SELECT id FROM ads WHERE checked = 0 AND strong = '' AND weak != ''")]
    medians = {}
    for cat, city in db.execute("SELECT DISTINCT category, city FROM ads WHERE area > 0"):
        v = [p / a for p, a in db.execute("SELECT price, area FROM ads WHERE category=? AND city=? AND area > 0",
                                          (cat, city))]
        if len(v) >= 20:
            medians[(cat, city)] = statistics.median(v)
    cheap = []
    for i, cat, city, p, a in db.execute("SELECT id, category, city, price, area FROM ads WHERE checked = 0 AND area > 0"):
        m = medians.get((cat, city))
        if m and p / a < 0.6 * m and i not in ids:
            cheap.append((p / a / m, i))
    cheap.sort()
    cheap_ids = [i for _, i in cheap]
    seen = set(ids) | set(cheap_ids)
    return (ids + cheap_ids + [i for i in weak if i not in seen])[:max_checks]


def check_details(db: sqlite3.Connection, client: httpx.Client, ids: list[int]) -> int:
    found = 0
    for n, ad_id in enumerate(ids, 1):
        try:
            res = client.get(f"{BASE}/a/show/{ad_id}")
        except httpx.HTTPError:
            continue
        time.sleep(DELAY_S)
        if res.status_code != 200:
            db.execute("UPDATE ads SET checked = -1 WHERE id = ?", (ad_id,))
            continue
        m = _DESCR_RE.search(res.text)
        text = clean(m.group(1)) if m else ""
        strong, _ = matches(text)
        found += bool(strong)
        db.execute("UPDATE ads SET checked = 1, full_strong = ?, snippet = ? WHERE id = ?",
                   (strong, snippet(text), ad_id))
        if n % 50 == 0:
            db.commit()
            print(f"детали: {n}/{len(ids)}, со словами про торги: {found}", flush=True)
    db.commit()
    return found


def export_csv(db: sqlite3.Connection, path: Path) -> int:
    rows = db.execute(
        "SELECT id, url, category, city, district, rooms, area, price, ROUND(price / NULLIF(area, 0)) AS ppm, "
        "strong, weak, full_strong, snippet, title FROM ads "
        "WHERE strong != '' OR full_strong != '' ORDER BY city, category").fetchall()
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["id", "url", "тип", "город", "район", "комнат", "площадь", "цена", "цена_м2",
                    "слова_в_карточке", "залог_арест_в_карточке", "слова_в_описании", "фрагмент", "заголовок"])
        w.writerows(rows)
    return len(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pages", type=int, default=30, help="страниц выдачи на город и раздел (крупные города — ×3)")
    ap.add_argument("--checks", type=int, default=700, help="сколько объявлений открыть полностью")
    ap.add_argument("--skip-crawl", action="store_true")
    args = ap.parse_args()
    OUT.mkdir(exist_ok=True)
    db = sqlite3.connect(OUT / "krisha-auctions.db")
    db.executescript(SCHEMA)
    client = httpx.Client(timeout=30, headers={"User-Agent": UA, "Accept-Language": "ru"}, follow_redirects=True)
    if not args.skip_crawl:
        print("выдача:", crawl(db, client, args.pages), flush=True)
    else:  # пересчитать совпадения в карточках после правки словаря
        rows = [(*matches(f"{t} {p}"), i) for i, t, p in db.execute("SELECT id, title, preview FROM ads")]
        db.executemany("UPDATE ads SET strong = ?, weak = ? WHERE id = ?", rows)
        db.commit()
    ids = candidates(db, args.checks)
    print("кандидатов на проверку:", len(ids), flush=True)
    print("со словами в полном описании:", check_details(db, client, ids), flush=True)
    print("в CSV:", export_csv(db, OUT / "krisha-auctions.csv"), flush=True)


if __name__ == "__main__":
    main()
