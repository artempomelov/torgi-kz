"""Instagram Stories torgi.kz: «Лот дня», «Угадайте цену» + ответ, «До торгов N дней».

    uv run --project backend --with pillow python web/scripts/make_stories.py

Лоты — в STORIES ниже (отбор глазами, как для каруселей). Результат — marketing/instagram/<дата>/stories/:
слайды 1080×1920 и stories.md — что добавить в приложении (стикер «Ссылка», порядок публикации).
Сверху (~250 px) и снизу (~250 px) Instagram закрывает кадр своим интерфейсом — важное держим посередине.
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
MONTHS = ["января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября",
          "ноября", "декабря"]

# лот, фото (номера в лоте): главное и ещё два–три
STORIES = {
    "lot_of_day": {"id": 1583, "photos": [5, 2, 4], "city": "Алматы"},
    # trim — доля кадра снизу, которую отрезаем: у этого продавца на фото дата съёмки
    "quiz": {"id": 1102, "photos": [7, 6, 9, 0], "title": "2-комн., 50,2 м²", "options": [18_000_000, None, 32_000_000],
             "trim": 0.08},
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
    d.text((60, 1340), title, font=ig.fit_font(d, title, ig.BOLD, 52, W - 120), fill=ig.INK)
    d.text((60, 1412), place, font=ig.fit_font(d, place, ig.REG, 36, W - 120), fill=ig.MUTED)
    price, pf = ig.mln(lot["price"]), ig.font(ig.BLACK, 100)
    d.text((60, 1462), price, font=pf, fill=ig.INK)
    x = ig.pill(d, (60, 1590), f"−{top['discount_pct']}% к рынку", ig.font(ig.BLACK, 40), ig.GREEN, ig.WHITE, pad=(26, 12))
    d.text((x + 28, 1606), f"рынок ≈ {ig.mln(top['estimate'])}", font=ig.font(ig.REG, 34), fill=ig.MUTED)
    return img


def story_quiz(lot: dict, spec: dict) -> Image.Image:
    img, d = canvas(ig.INK)
    ph = photos(lot, spec["photos"], spec.get("trim", 0))
    cw, ch = (W - 6) // 2, 540
    for k, p in enumerate(ph[:4]):
        paste(img, p, ((k % 2) * (cw + 6), (k // 2) * (ch + 6), (k % 2) * (cw + 6) + cw, (k // 2) * (ch + 6) + ch))
    shade_top(img)
    d = ImageDraw.Draw(img)
    header(d, "Угадайте цену")
    y = 2 * ch + 6 + 50
    d.text((60, y), "Сколько стоит на торгах?", font=ig.font(ig.BLACK, 64), fill=ig.WHITE)
    sub = f"{spec['title']} · {lot_place(lot)}"
    d.text((60, y + 90), sub, font=ig.fit_font(d, sub, ig.REG, 36, W - 120), fill="#b8c2d6")
    options = [o or lot["price"] for o in spec["options"]]
    x = 60
    for letter, value in zip("АБВ", options):
        x = ig.pill(d, (x, y + 170), f"{letter}  {ig.mln(value)}", ig.font(ig.BOLD, 40), "#24324a", ig.WHITE, pad=(26, 16)) + 22
    d.text((60, y + 280), "Ответ — в следующей истории →", font=ig.font(ig.BOLD, 34), fill="#8aa6ff")
    return img


def story_answer(lot: dict, top: dict, spec: dict) -> Image.Image:
    img, d = canvas()
    ph = photos(lot, spec["photos"][:1], spec.get("trim", 0))
    paste(img, ph[0], (0, 0, W, 1060))
    shade_top(img)
    d = ImageDraw.Draw(img)
    header(d, "Правильный ответ")
    d.text((60, 1110), ig.mln(lot["price"]), font=ig.font(ig.BLACK, 120), fill=ig.INK)
    line = f"Рынок ≈ {ig.mln(top['estimate'])} — на {top['discount_pct']}% ниже"
    d.text((60, 1270), line, font=ig.fit_font(d, line, ig.BOLD, 44, W - 120), fill=ig.GREEN)
    sub = f"{spec['title']} · {lot_place(lot)}"
    d.text((60, 1340), sub, font=ig.fit_font(d, sub, ig.REG, 36, W - 120), fill=ig.MUTED)
    tags = [ig.ORIGIN.get(lot["origin"], lot["origin"])] + ([ig.SALE[lot["sale_type"]]] if lot.get("sale_type") in ig.SALE else [])
    ig.pill(d, (60, 1410), " · ".join(tags), ig.font(ig.BOLD, 32), ig.LIGHT, ig.COBALT, pad=(24, 12))
    d.text((60, 1520), "Подробнее — по ссылке ↓", font=ig.font(ig.BOLD, 40), fill=ig.COBALT)
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
    ig.pill(d, (60, 1470), f"−{top['discount_pct']}% к рынку", ig.font(ig.BLACK, 40), ig.GREEN, ig.WHITE, pad=(26, 12))
    d.text((60, 1580), "Как участвовать — подскажем бесплатно", font=ig.font(ig.BOLD, 36), fill="#8aa6ff")
    return img


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("*.jpg"):
        old.unlink()
    full = {lot["id"]: lot for lot in json.loads((ig.DATA / "lots-full.json").read_text(encoding="utf-8"))}
    tops = {x["id"]: x for s in json.loads((ig.DATA / "top.json").read_text(encoding="utf-8"))["sections"] for x in s["items"]}
    today = datetime.now(ALMATY).date()
    notes = ["# Stories — порядок публикации\n"]
    n = 0

    def save(img: Image.Image | None, name: str, note: str):
        nonlocal n
        if img is None:
            return
        n += 1
        img.save(OUT / f"{n:02d}-{name}.jpg", quality=92)
        notes.append(f"{n}. `{n:02d}-{name}.jpg` — {note}")

    s = STORIES["lot_of_day"]
    lot = full[s["id"]]
    save(story_lot_of_day(lot, tops[s["id"]], s), "lot-dnya",
         f"стикер «Ссылка» под ценой: {SITE}/lots/{lot['id']}/?utm_source=instagram&utm_medium=stories")
    s = STORIES["quiz"]
    lot = full[s["id"]]
    save(story_quiz(lot, s), "ugadayte-cenu", "можно добавить стикер «Опрос» с вариантами А / Б / В")
    save(story_answer(lot, tops[s["id"]], s), "otvet",
         f"стикер «Ссылка» под текстом: {SITE}/lots/{lot['id']}/?utm_source=instagram&utm_medium=stories")
    s = STORIES["countdown"]
    lot = full[s["id"]]
    save(story_countdown(lot, tops[s["id"]], s, today), "do-torgov",
         f"стикер «Ссылка»: {SITE}/lots/{lot['id']}/?utm_source=instagram&utm_medium=stories · число дней — на {today:%d.%m}")
    (OUT / "stories.md").write_text("\n".join(notes) + "\n", encoding="utf-8")
    print(f"готово: {OUT} ({n} шт.)")


if __name__ == "__main__":
    main()
