"""Instagram Stories torgi.kz: «Лот дня», мозаика раздела ТОПа, «До торгов N дней» — без лотов из постов.

    uv run --project backend --with pillow python web/scripts/make_stories.py

Лоты — в STORIES ниже (отбор глазами, как для каруселей). Результат — marketing/instagram/<дата>/stories/:
слайды 1080×1920, variants/ — варианты второй истории, stories.md — ссылки для стикера «Ссылка».
Сверху (~250 px) и снизу (~250 px) Instagram закрывает кадр своим интерфейсом — важное держим посередине.
Внизу каждой истории — одна строка о портале, без «как участвовать» и прочих уточнений.
"""

import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps

sys.path.insert(0, str(Path(__file__).resolve().parent))
import make_instagram as ig  # noqa: E402  (шрифты, цвета, фото, плашки — как в каруселях)

W, H = 1080, 1920
ALMATY = timezone(timedelta(hours=5))
OUT = ig.ROOT / "marketing" / "instagram" / date.today().isoformat() / "stories"
SITE = "https://torgi.kz"
UTM = "utm_source=instagram&utm_medium=stories"
MONTHS = ["января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября",
          "ноября", "декабря"]
CATEGORY_WORDS = {"apartment": "квартир", "house": "домов", "commercial": "коммерческих", "land": "участков"}
REGION_CAP = 30  # как в ТОПе сайта: вне Алматы и Астаны — «30%+» вместо точной скидки
# мозаики из разделов ТОПа: раздел, плашка, заголовок (n — сколько объектов), вторая строка
MOSAICS = [
    ("kvartiry-astana", "ТОП недели · Астана", "{n} квартир в Астане", "ниже рынка до {best}%"),
    ("kommercheskaya", "ТОП недели · Бизнес", "{n} помещений для бизнеса", "ниже рынка до {best}%"),
    ("kvartiry-do-30-mln", "ТОП недели · до 30 млн", "Квартиры до 30 млн ₸", "{n} вариантов по Казахстану"),
]

# лот и фото (номера в лоте): главное и ещё два; trim — доля кадра снизу, которую отрезаем (дата съёмки на фото)
# Мозаика не должна повторять пост: разовые совпадения с постами допустимы, но если в мозаике больше
# MAX_REPEATS лотов из одного поста (опубликованного или готовой карусели из make_instagram.PICKS) — она лишняя
POSTS = [{354, 1704, 1280, 2901, 3678},  # «ТОП-5 Алматы» 14.10
         {1583, 1206, 109, 1454, 105}]  # «ТОП-5 квартир с ремонтом в Алматы» 17.10
POSTS += [{x["id"] for x in pick["lots"]} for pick in ig.PICKS]
MAX_REPEATS = 2

STORIES = {
    "lot_of_day": {"id": 1272, "photos": [4, 11, 10], "city": "Алматы"},
    "countdown": {"id": 3812, "photos": [14, 12, 11], "title": "Квартира 130,7 м²"},
    "second": "kvartiry-do-30-mln",  # вторая история — мозаика этого раздела ТОПа (варианты — в variants/)
}


def canvas(bg: str = ig.WHITE) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGB", (W, H), bg)
    return img, ImageDraw.Draw(img)


def paste(img: Image.Image, photo: Image.Image | None, box: tuple[int, int, int, int]):
    x0, y0, x1, y1 = box
    if photo:
        img.paste(ImageOps.fit(photo, (x1 - x0, y1 - y0), Image.LANCZOS), (x0, y0))
    else:
        ImageDraw.Draw(img).rectangle(box, fill=ig.SOFT)


def shade_top(img: Image.Image, height: int = 420, alpha: float = 0.55):
    grad = Image.linear_gradient("L").rotate(180).resize((W, height)).point(lambda v: int(v * alpha))
    img.paste(Image.new("RGB", (W, height), "#000000"), (0, 0), grad)


def header(d: ImageDraw.ImageDraw, kicker: str, dark_bg: bool = True):
    # ниже полосы с именем профиля (≈ 250 px)
    ig.pill(d, (60, 270), kicker, ig.font(ig.BOLD, 40), ig.GREEN, ig.WHITE, pad=(28, 14))
    ig.logo(d, W - 300, 280, size=44, dark=not dark_bg)


def portal_line(d: ImageDraw.ImageDraw, y: int = 1600, dark: bool = False):
    """«Ещё больше лотов — на нашем портале torgi.kz» — одна строка внизу каждой истории."""
    f = ig.font(ig.BOLD, 38)
    text = "Ещё больше лотов — на нашем портале "
    d.text((60, y), text, font=f, fill=ig.WHITE if dark else ig.INK)
    d.text((60 + d.textlength(text, font=f), y), "torgi.kz", font=f, fill="#8aa6ff" if dark else ig.COBALT)


def lot_place(lot: dict) -> str:
    return lot["headline"].partition(" — ")[2] or (lot.get("city") or "")


def photos(lot: dict, idx: list[int], trim: float = 0) -> list[Image.Image | None]:
    out = []
    for i in idx:
        im = ig.fetch_photo(lot["images"][i]) if i < len(lot["images"]) else None
        if im is not None and trim:
            im = im.crop((0, 0, im.width, int(im.height * (1 - trim))))
        out.append(im)
    return out


def discount_text(top: dict) -> str:
    return f"скидка {top['discount_note']}" if top.get("discount_note") else f"−{top['discount_pct']}% к рынку"


# --- истории ---------------------------------------------------------------------------------------------

def story_lot_of_day(lot: dict, top: dict, spec: dict) -> Image.Image:
    img, d = canvas()
    ph = photos(lot, spec["photos"])
    paste(img, ph[0], (0, 0, W, 980))
    paste(img, ph[1], (0, 986, 537, 1306))
    paste(img, ph[2], (543, 986, W, 1306))
    shade_top(img)
    d = ImageDraw.Draw(img)
    header(d, f"Лот дня · {spec['city']}")
    title, place = lot["headline"].partition(" — ")[0], lot_place(lot)
    d.text((60, 1335), title, font=ig.fit_font(d, title, ig.BOLD, 52, W - 120), fill=ig.INK)
    d.text((60, 1405), place, font=ig.fit_font(d, place, ig.REG, 36, W - 120), fill=ig.MUTED)
    d.text((60, 1450), ig.mln(lot["price"]), font=ig.font(ig.BLACK, 96), fill=ig.INK)
    x = ig.pill(d, (60 + d.textlength(ig.mln(lot["price"]), font=ig.font(ig.BLACK, 96)) + 30, 1478),
                discount_text(top), ig.font(ig.BLACK, 36), ig.GREEN, ig.WHITE, pad=(22, 10))
    portal_line(d)
    return img


def story_numbers(meta: dict) -> Image.Image:
    """Вариант 4 — «Сейчас на torgi.kz»: сколько объектов в каталоге по видам."""
    img, d = canvas(ig.COBALT)
    header(d, "Сейчас на torgi.kz")
    ig.house(d, W // 2, 420, 0.8, ig.WHITE, arrow=ig.INK)
    total = f"{meta['total']:,}".replace(",", " ")
    d.text((W // 2, 860), total, font=ig.font(ig.BLACK, 170), fill=ig.WHITE, anchor="mm")
    d.text((W // 2, 990), "объектов с торгов", font=ig.font(ig.BOLD, 52), fill=ig.WHITE, anchor="mm")
    counts = {c["id"]: c["count"] for c in meta["categories"]}
    y = 1110
    for cat, word in CATEGORY_WORDS.items():
        if counts.get(cat):
            line = f"{counts[cat]:,} {word}".replace(",", " ")
            d.text((W // 2, y), line, font=ig.font(ig.REG, 44), fill="#dfe6ff", anchor="mm")
            y += 66
    d.text((W // 2, y + 40), "Арест, госимущество, банкроты, залоги банков", font=ig.font(ig.REG, 34),
           fill="#b9c8ff", anchor="mm")
    portal_line(d, dark=True)
    return img


def story_mosaic(items: list[tuple[dict, dict, Image.Image | None]], kicker: str, title: str, accent: str) -> Image.Image:
    """Мозаика 3×3 из раздела ТОПа: обложки с ценой и скидкой на каждой плитке, крупный заголовок под ней."""
    img, d = canvas(ig.INK)
    gap, top_y = 6, 360
    tile = (W - 2 * gap) // 3
    rows = max(1, min(3, len(items) // 3))  # только полные ряды — без пустых клеток
    items = items[:rows * 3]
    if rows < 3:
        top_y += (3 - rows) * (tile + gap) // 2
    for k, (lot, top, photo) in enumerate(items):
        x, y = (k % 3) * (tile + gap), top_y + (k // 3) * (tile + gap)
        paste(img, photo, (x, y, x + tile, y + tile))
        shade = Image.linear_gradient("L").resize((tile, 120)).point(lambda v: int(v * 0.75))
        img.paste(Image.new("RGB", (tile, 120), "#000000"), (x, y + tile - 120), shade)
        d = ImageDraw.Draw(img)
        d.text((x + 16, y + tile - 16), ig.mln(lot["price"]).replace(" ₸", ""), font=ig.font(ig.BLACK, 34),
               fill=ig.WHITE, anchor="ls")
        chip = f"{REGION_CAP}%+" if top.get("discount_note") else f"−{top['discount_pct']}%"
        ig.pill(d, (x + 12, y + 12), chip, ig.font(ig.BLACK, 28), ig.GREEN, ig.WHITE, pad=(14, 6))
    header(d, kicker)
    y = top_y + rows * (tile + gap) + 40
    d.text((60, y), title, font=ig.fit_font(d, title, ig.BLACK, 70, W - 120), fill=ig.WHITE)
    d.text((60, y + 90), accent, font=ig.fit_font(d, accent, ig.BLACK, 70, W - 120), fill="#3ddc84")
    portal_line(d, y=y + 200, dark=True)
    return img


def story_countdown(lot: dict, top: dict, spec: dict, today: date) -> Image.Image | None:
    start = lot.get("auction_start")
    if not start:
        return None
    when = datetime.fromisoformat(start.replace("Z", "+00:00")).astimezone(ALMATY)
    days = (when.date() - today).days
    if days <= 0:
        return None
    img, d = canvas(ig.INK)
    ph = photos(lot, spec["photos"])
    paste(img, ph[0], (0, 0, W, 860))
    paste(img, ph[1], (0, 866, 537, 1186))
    paste(img, ph[2], (543, 866, W, 1186))
    shade_top(img)
    d = ImageDraw.Draw(img)
    header(d, f"Торги {when.day} {MONTHS[when.month - 1]}")
    word = "день" if days % 10 == 1 and days % 100 != 11 else "дня" if days % 10 in (2, 3, 4) and days % 100 not in (12, 13, 14) else "дней"
    d.text((60, 1220), f"До торгов {days} {word}", font=ig.font(ig.BLACK, 84), fill=ig.WHITE)
    sub = f"{spec['title']} · {lot_place(lot)}"
    d.text((60, 1330), sub, font=ig.fit_font(d, sub, ig.REG, 36, W - 120), fill="#b8c2d6")
    d.text((60, 1390), f"Стартовая цена {ig.mln(lot['price'])}", font=ig.font(ig.BOLD, 48), fill=ig.WHITE)
    ig.pill(d, (60, 1470), discount_text(top), ig.font(ig.BLACK, 40), ig.GREEN, ig.WHITE, pad=(26, 12))
    portal_line(d, dark=True)
    return img


def main():
    (OUT / "variants").mkdir(parents=True, exist_ok=True)
    for old in list(OUT.glob("*.jpg")) + list((OUT / "variants").glob("*.jpg")):
        old.unlink()
    full = {lot["id"]: lot for lot in json.loads((ig.DATA / "lots-full.json").read_text(encoding="utf-8"))}
    tops = {x["id"]: x for s in json.loads((ig.DATA / "top.json").read_text(encoding="utf-8"))["sections"] for x in s["items"]}
    meta = json.loads((ig.DATA / "meta.json").read_text(encoding="utf-8"))
    today = datetime.now(ALMATY).date()
    notes = ["# Stories — порядок публикации\n"]

    s = STORIES["lot_of_day"]
    story_lot_of_day(full[s["id"]], tops[s["id"]], s).save(OUT / "02-lot-dnya.jpg", quality=92)
    notes.append(f"2. `02-lot-dnya.jpg` — стикер «Ссылка»: {SITE}/lots/{s['id']}/?{UTM}")
    s = STORIES["countdown"]
    img = story_countdown(full[s["id"]], tops[s["id"]], s, today)
    if img:
        img.save(OUT / "03-do-torgov.jpg", quality=92)
        notes.append(f"3. `03-do-torgov.jpg` — стикер «Ссылка»: {SITE}/lots/{s['id']}/?{UTM} · дни — на {today:%d.%m}")

    # вторая история — мозаика раздела ТОПа без лотов из постов; остальные разделы — варианты на замену
    story_numbers(meta).save(OUT / "variants" / "cifry.jpg", quality=92)
    sections = {s["slug"]: s for s in json.loads((ig.DATA / "top.json").read_text(encoding="utf-8"))["sections"]}
    for slug, kicker, title, accent in MOSAICS:
        section = sections.get(slug)
        if not section:
            continue
        chosen = [x for x in section["items"] if x["id"] in full][:9]
        repeats = max(len({x["id"] for x in chosen} & post) for post in POSTS)
        if repeats > MAX_REPEATS or len(chosen) < 6:
            print(f"  мозаика {slug}: {repeats} лотов из одного поста — повторяет пост, пропускаем")
            continue
        items = [(full[x["id"]], x, ig.fetch_photo(x.get("image") or (full[x["id"]]["images"] or [None])[0]))
                 for x in chosen]
        best = max(REGION_CAP if x.get("discount_note") else x["discount_pct"] for _, x, _ in items)
        n = len(section["items"])
        img = story_mosaic(items, kicker, title.format(n=n), accent.format(n=n, best=best))
        img.save(OUT / "variants" / f"mozaika-{slug}.jpg", quality=92)
        if slug == STORIES["second"]:
            img.save(OUT / "01-mozaika.jpg", quality=92)
            notes.insert(1, f"1. `01-mozaika.jpg` — стикер «Ссылка»: {SITE}/top/?{UTM}#{slug}")
    (OUT / "stories.md").write_text("\n".join(notes) + "\n", encoding="utf-8")
    print(f"готово: {OUT}")


if __name__ == "__main__":
    main()
