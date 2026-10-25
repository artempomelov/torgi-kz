"""Threads @torgi.kz: пост «лот с цифрами» — текст и 4 фото 4:5 (плашка «−N% к рынку» на первом).

    uv run --project backend --with pillow --with httpx python web/scripts/make_threads.py candidates
    uv run --project backend --with pillow --with httpx python web/scripts/make_threads.py 189 5,3,6,7

candidates — те же кандидаты, что для Reels (недорогие квартиры Алматы и Астаны со скидкой от 30% — первыми),
без лотов, которые уже были в Threads; в один день с Reels берём другой лот. Второй вызов — marketing/threads/<дата>/: 01–04.jpg, post.txt
и preview.jpg; лот записывается в marketing/threads/used.json. Публикуем с веба: «Что нового?» → тема
(«Квартира в Алматы» / «Квартира в Астане») → текст → 4 фото. Только скидка — без рыночных цен (решение от 23.10.2026).
"""

import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from PIL import Image, ImageOps

sys.path.insert(0, str(Path(__file__).resolve().parent))
import make_instagram as ig  # noqa: E402
import make_reels as reels  # noqa: E402

sys.path.insert(0, str(ig.ROOT / "backend"))
from torgi.badge import draw  # noqa: E402

OUT = ig.ROOT / "marketing" / "threads" / date.today().isoformat()
USED = ig.ROOT / "marketing" / "threads" / "used.json"
ORIGINS = {"bank_balance": "Имущество банка", "bank_pledge": "Залог банка", "arrested": "Арестованное имущество",
           "court": "Судебная реализация", "state": "Госимущество", "bankrupt": "Имущество банкрота"}
SALE = {"direct": "прямая продажа", "auction": "аукцион", "auction_down": "аукцион на понижение", "tender": "конкурс"}
MONTHS = ["января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября",
          "ноября", "декабря"]
ALMATY = timezone(timedelta(hours=5))


def used() -> set[int]:
    return set(json.loads(USED.read_text(encoding="utf-8"))) if USED.exists() else set()


def text(lot: dict) -> str:
    m = lot["market"]
    pct = f"более чем на {m['pct']}%" if m["over"] else f"на {m['pct']}%"
    facts = ", ".join(x for x in (f"{lot['area_m2']:g} м²".replace(".", ",") if lot.get("area_m2") else None,
                                  f"{lot['floor']} этаж" if lot.get("floor") else None,
                                  f"дом {lot['year_built']} года" if lot.get("year_built") else None) if x)
    sale = SALE.get(lot.get("sale_type"), "")
    if lot.get("auction_start") and lot.get("sale_type") in ("auction", "auction_down"):
        day = datetime.fromisoformat(lot["auction_start"].replace("Z", "+00:00")).astimezone(ALMATY)
        sale += f", торги {day.day} {MONTHS[day.month - 1]}"
    lines = [f"{reels.title(lot)} за {ig.mln(lot['price'])} — {pct} ниже рынка",
             f"📍 {(lot.get('district') or lot['city'])[:1].upper()}{(lot.get('district') or lot['city'])[1:]}",
             f"🏢 {facts}" if facts else None,
             f"🏦 {ORIGINS.get(lot['origin'], '')}, {sale}".strip(", ") if lot.get("origin") in ORIGINS else None,
             "",
             f"Все фото и детали: torgi.kz/lots/{lot['id']}",
             "📲 Новые лоты каждый день: t.me/torgi_kz_news"]
    return "\n".join(x for x in lines if x is not None)


def render(lot_id: int, idx: list[int]):
    lot = {x["id"]: x for x in json.loads((ig.DATA / "lots-full.json").read_text(encoding="utf-8"))}[lot_id]
    OUT.mkdir(parents=True, exist_ok=True)
    frames = []
    for n, i in enumerate(idx, 1):
        # лента Threads обрезает широкие фото — кадр 4:5, чтобы плашка слева не срезалась
        img = ImageOps.fit(ig.fetch_photo(lot["images"][i]).convert("RGB"), (1080, 1350), Image.LANCZOS)
        if n == 1:
            img = draw(img, lot["market"])
        img.save(OUT / f"{n:02}.jpg", quality=92)
        frames.append(img)
    h = 440
    strip = [f.resize((round(f.width * h / f.height), h)) for f in frames]
    sheet = Image.new("RGB", (sum(s.width for s in strip) + 10 * (len(strip) - 1), h), "white")
    x = 0
    for s in strip:
        sheet.paste(s, (x, 0))
        x += s.width + 10
    sheet.save(OUT / "preview.jpg", quality=88)
    post = text(lot)
    (OUT / "post.txt").write_text(post, encoding="utf-8")
    USED.write_text(json.dumps(sorted(used() | {lot_id})), encoding="utf-8")
    print(OUT)
    print(post)


def main():
    args = sys.argv[1:]
    if not args or args[0] == "candidates":
        reels.sheets(reels.pool(used())[:8], OUT / "candidates")
    else:
        render(int(args[0]), [int(i) for i in args[1].split(",")])


if __name__ == "__main__":
    main()
