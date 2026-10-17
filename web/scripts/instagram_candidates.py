"""Кандидаты для ТОП-постов Instagram: лоты ниже рынка с фото — контактные листы, чтобы отобрать глазами.

    uv run --project backend --with pillow python web/scripts/instagram_candidates.py apartment Алматы
    uv run --project backend --with pillow python web/scripts/instagram_candidates.py commercial

Данные — web/data (выгрузка `torgi.cli export --market …` и market-index.json). Результат —
marketing/instagram/<дата>/candidates/: строка листа — лот (номер, скидка, цена) и все его фото с номерами;
номера фото — для PICKS в make_instagram.py. Один дом/ЖК — одна строка (лучшая по скидке).
"""

import hashlib
import io
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

import httpx
from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
from torgi import normalize as nz  # noqa: E402
from torgi import top  # noqa: E402
from torgi.market import MarketIndex, confidence  # noqa: E402

DATA = ROOT / "web" / "data"
OUT = ROOT / "marketing" / "instagram" / date.today().isoformat() / "candidates"
CACHE = ROOT / "marketing" / "instagram" / "photo-cache"
COLS, MAX_PHOTOS, TW, TH, LABEL_W, PER_SHEET = 6, 12, 230, 172, 290, 6


def photo(url: str) -> Path | None:
    path = CACHE / (hashlib.md5(url.encode()).hexdigest() + ".jpg")
    if not path.exists():
        try:
            res = httpx.get(url, timeout=25, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0"})
            res.raise_for_status()
            ImageOps.exif_transpose(Image.open(io.BytesIO(res.content))).convert("RGB").save(path, quality=92)
        except Exception:
            return None
    return path


def candidates(category: str, city: str | None) -> list[dict]:
    index = MarketIndex.from_json(DATA / "market-index.json")
    lo, hi = top.AREA_RANGE[category]
    best: dict[str, dict] = {}
    for x in json.loads((DATA / "lots-full.json").read_text(encoding="utf-8")):
        if x.get("category") != category or (city and x.get("city") != city) or not x.get("images"):
            continue
        if not x.get("price") or x.get("flags") or nz.deal_flags(x.get("title"), x.get("description")):
            continue
        if not x.get("area_m2") or not lo <= x["area_m2"] <= hi:
            continue
        if top.EXCLUDED_RE.search(f"{x.get('address') or ''} {x.get('title') or ''}"):
            continue
        est = index.estimate(category, x.get("city") or x.get("region"), x.get("district"), x.get("rooms"), x["area_m2"])
        if est is None or confidence(est, x.get("district")) == "низкая":
            continue
        discount = round((1 - x["price"] / est.value) * 100)
        if not top.MIN_DISCOUNT <= discount < top.MAX_DISCOUNT:
            continue
        key = top.building_key(x, x.get("address"), x.get("title"))
        if key not in best or discount > best[key]["discount"]:
            best[key] = {**x, "discount": discount, "district_known": bool(x.get("district"))}
    return sorted(best.values(), key=lambda c: -c["discount"])


def sheet(rows: list[dict], path: Path):
    f = ImageFont.truetype("C:/Windows/Fonts/segoeuib.ttf", 21)
    heights = [(min(len(r["images"]), MAX_PHOTOS) + COLS - 1) // COLS for r in rows]
    img = Image.new("RGB", (LABEL_W + COLS * (TW + 4), sum(heights) * (TH + 4) + 8 * len(rows)), "white")
    d = ImageDraw.Draw(img)
    y = 0
    for r, h in zip(rows, heights):
        note = "" if r["district_known"] else "\n⚠ район не указан"
        d.multiline_text((6, y + 4), f"#{r['id']} −{r['discount']}%\n{r['price'] / 1e6:.1f} млн · {r['source']}\n"
                                     f"{r['headline'][:26]}\n{r['headline'][26:52]}{note}", font=f, fill="black")
        with ThreadPoolExecutor(12) as ex:
            paths = list(ex.map(photo, r["images"][:MAX_PHOTOS]))
        for k, p in enumerate(paths):
            x, yy = LABEL_W + (k % COLS) * (TW + 4), y + (k // COLS) * (TH + 4)
            if p:
                img.paste(ImageOps.fit(Image.open(p), (TW, TH)), (x, yy))
            d.text((x + 4, yy + 2), str(k), font=f, fill="yellow", stroke_width=2, stroke_fill="black")
        y += h * (TH + 4) + 8
    img.save(path, quality=80)


def main():
    category, city = sys.argv[1], (sys.argv[2] if len(sys.argv) > 2 else None)
    limit = int(sys.argv[3]) if len(sys.argv) > 3 else 30
    OUT.mkdir(parents=True, exist_ok=True)
    CACHE.mkdir(parents=True, exist_ok=True)
    rows = candidates(category, city)[:limit]
    name = f"{category}-{city or 'all'}"
    for n in range(0, len(rows), PER_SHEET):
        sheet(rows[n:n + PER_SHEET], OUT / f"{name}-{n // PER_SHEET + 1}.jpg")
    print(f"{len(rows)} кандидатов → {OUT}")


if __name__ == "__main__":
    main()
