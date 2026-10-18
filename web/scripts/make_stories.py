"""Instagram Stories torgi.kz: «Лот дня», вторая история на выбор (подборка, экономия, новый пост, цифры),
«До торгов N дней».

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

# лот и фото (номера в лоте): главное и ещё два; trim — доля кадра снизу, которую отрезаем (дата съёмки на фото)
STORIES = {
    "lot_of_day": {"id": 1583, "photos": [5, 2, 4], "city": "Алматы"},
    "selection": {"city": "Астана", "lots": [{"id": 98, "photo": 10}, {"id": 99, "photo": 11},
                                             {"id": 189, "photo": 5}]},
    "savings": {"id": 1102, "photo": 7, "title": "2-комн., 50,2 м²", "trim": 0.08},
    "new_post": {"title": "ТОП-5 квартир с ремонтом в Алматы", "lots": [{"id": 1583, "photo": 5}, {"id": 109, "photo": 8},
                                                                        {"id": 1454, "photo": 7}, {"id": 105, "photo": 14}]},
    "countdown": {"id": 3812, "photos": [14, 12, 11], "title": "Квартира 130,7 м²"},
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


def story_selection(lots: list[tuple[dict, dict, Image.Image | None]], city: str) -> Image.Image:
    """Вариант 1 — «Подборка дня»: три объекта одного города, у каждого фото, цена и скидка."""
    img, d = canvas(ig.LIGHT)
    header(d, f"Подборка дня · {city}", dark_bg=False)
    y, row_h = 380, 380
    for lot, top, photo in lots:
        d.rounded_rectangle([40, y, W - 40, y + row_h - 24], 28, fill=ig.WHITE)
        tile = ImageOps.fit(photo, (430, row_h - 24), Image.LANCZOS) if photo else Image.new("RGB", (430, row_h - 24), ig.SOFT)
        mask = Image.new("L", tile.size, 0)
        ImageDraw.Draw(mask).rounded_rectangle([0, 0, tile.width - 1, tile.height - 1], 28, fill=255)
        img.paste(tile, (40, y), mask)
        tx, title = 500, lot["headline"].partition(" — ")[0].replace("Квартира, ", "")
        d.text((tx, y + 30), title, font=ig.fit_font(d, title, ig.BOLD, 40, W - 40 - tx - 30), fill=ig.INK)
        place = lot_place(lot).replace(f"{city}, ", "")
        d.text((tx, y + 84), place, font=ig.fit_font(d, place, ig.REG, 30, W - 40 - tx - 30), fill=ig.MUTED)
        d.text((tx, y + 140), ig.mln(lot["price"]), font=ig.font(ig.BLACK, 64), fill=ig.INK)
        ig.pill(d, (tx, y + 240), discount_text(top), ig.font(ig.BLACK, 32), ig.GREEN, ig.WHITE, pad=(20, 10))
        y += row_h
    portal_line(d, y=y + 40)
    return img


def story_savings(lot: dict, top: dict, spec: dict) -> Image.Image:
    """Вариант 2 — «Экономия на торгах»: фото, цена против рынка полосами и сумма экономии."""
    img, d = canvas()
    ph = photos(lot, [spec["photo"]], spec.get("trim", 0))
    paste(img, ph[0], (0, 0, W, 900))
    shade_top(img)
    d = ImageDraw.Draw(img)
    header(d, "Экономия на торгах")
    sub = f"{spec['title']} · {lot_place(lot)}"
    d.text((60, 940), sub, font=ig.fit_font(d, sub, ig.BOLD, 40, W - 120), fill=ig.INK)
    full_w = W - 120
    d.rounded_rectangle([60, 1020, 60 + full_w, 1110], 18, fill="#e3e8f0")
    d.text((90, 1065), f"Рынок ≈ {ig.mln(top['estimate'])}", font=ig.font(ig.BOLD, 40), fill=ig.MUTED, anchor="lm")
    lot_w = int(full_w * lot["price"] / top["estimate"])
    d.rounded_rectangle([60, 1130, 60 + lot_w, 1240], 20, fill=ig.GREEN)
    d.text((90, 1185), f"На торгах {ig.mln(lot['price'])}", font=ig.font(ig.BLACK, 46), fill=ig.WHITE, anchor="lm")
    d.text((60, 1290), "Экономия", font=ig.font(ig.BOLD, 40), fill=ig.MUTED)
    d.text((60, 1340), f"≈ {ig.mln(top['estimate'] - lot['price'])}", font=ig.font(ig.BLACK, 110), fill=ig.GREEN)
    portal_line(d)
    return img


def story_new_post(items: list[tuple[dict, Image.Image | None]], title: str, best: int) -> Image.Image:
    """Вариант 3 — «Новый пост»: мозаика квартир из свежей карусели и её заголовок."""
    img, d = canvas(ig.INK)
    cw, ch = (W - 6) // 2, 560
    for k, (_, p) in enumerate(items[:4]):
        paste(img, p, ((k % 2) * (cw + 6), (k // 2) * (ch + 6), (k % 2) * (cw + 6) + cw, (k // 2) * (ch + 6) + ch))
    shade_top(img)
    d = ImageDraw.Draw(img)
    header(d, "Новый пост")
    y = 2 * ch + 6 + 50
    y = ig.text_block(d, (60, y), title, ig.font(ig.BLACK, 66), ig.WHITE, W - 120, 1.12) + 10
    d.text((60, y), f"ниже рынка до {best}%", font=ig.font(ig.BLACK, 66), fill="#3ddc84")
    portal_line(d, dark=True)
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
    story_lot_of_day(full[s["id"]], tops[s["id"]], s).save(OUT / "01-lot-dnya.jpg", quality=92)
    notes.append(f"1. `01-lot-dnya.jpg` — стикер «Ссылка»: {SITE}/lots/{s['id']}/?{UTM}")
    notes.append("2. вторая история — один из вариантов в `variants/`")
    s = STORIES["countdown"]
    img = story_countdown(full[s["id"]], tops[s["id"]], s, today)
    if img:
        img.save(OUT / "03-do-torgov.jpg", quality=92)
        notes.append(f"3. `03-do-torgov.jpg` — стикер «Ссылка»: {SITE}/lots/{s['id']}/?{UTM} · дни — на {today:%d.%m}")

    # варианты второй истории
    s = STORIES["selection"]
    rows = [(full[x["id"]], tops[x["id"]], photos(full[x["id"]], [x["photo"]])[0]) for x in s["lots"]]
    story_selection(rows, s["city"]).save(OUT / "variants" / "1-podborka-dnya.jpg", quality=92)
    s = STORIES["savings"]
    story_savings(full[s["id"]], tops[s["id"]], s).save(OUT / "variants" / "2-ekonomiya.jpg", quality=92)
    s = STORIES["new_post"]
    items = [(full[x["id"]], photos(full[x["id"]], [x["photo"]])[0]) for x in s["lots"]]
    best = max(tops[x["id"]]["discount_pct"] for x in s["lots"] if x["id"] in tops)
    story_new_post(items, s["title"], best).save(OUT / "variants" / "3-novyj-post.jpg", quality=92)
    story_numbers(meta).save(OUT / "variants" / "4-cifry.jpg", quality=92)
    notes.append(f"\nСсылки для вариантов: подборка — {SITE}/top/?{UTM}#kvartiry-astana; экономия — "
                 f"{SITE}/lots/{STORIES['savings']['id']}/?{UTM}; новый пост — репост поста; цифры — {SITE}/?{UTM}")
    (OUT / "stories.md").write_text("\n".join(notes) + "\n", encoding="utf-8")
    print(f"готово: {OUT}")


if __name__ == "__main__":
    main()
