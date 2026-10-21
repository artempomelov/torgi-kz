"""Stories о наших Telegram-каналах: Алматы, Астана, Авто — мозаика объектов и «подписывайтесь» со ссылкой на канал.

    uv run --project backend --with pillow --with httpx python web/scripts/make_stories_channels.py

Объекты — из ТОПа (фото уже отобраны вручную) и из карусели «ТОП-5 машин» (номера размыты).
Результат — marketing/instagram/<дата>/stories-channels/ и stories.md со ссылками для стикера «Ссылка».
"""

import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
import make_instagram as ig  # noqa: E402
import make_instagram_cars as cars_top  # noqa: E402
import make_stories as st  # noqa: E402

OUT = st.OUT.parent / "stories-channels"
UTM = "utm_source=instagram&utm_medium=stories"
# другое фото лота вместо выбранного для ТОПа — на том в кадре человек
PHOTO = {1454: 4}

CHANNELS = [
    {"file": "01-kanal-almaty.jpg", "handle": "torgi_kz_almaty", "kicker": "Telegram · Алматы",
     "title": "Квартиры Алматы с торгов", "top": "kvartiry-almaty"},
    {"file": "02-kanal-astana.jpg", "handle": "torgi_kz_astana", "kicker": "Telegram · Астана",
     "title": "Квартиры Астаны с торгов", "top": "kvartiry-astana"},
    {"file": "03-kanal-avto.jpg", "handle": "torgi_kz_auto", "kicker": "Telegram · Авто",
     "title": "Машины с торгов", "cars": True},
]


def tile_grid(img: Image.Image, tiles: list[tuple[Image.Image | None, str, tuple[str, str, str] | None]], top_y: int) -> int:
    """Сетка 2×3: фото, цена внизу слева, плашка (текст, фон, цвет) — в левом верхнем углу. Возвращает низ сетки."""
    gap, cols = 6, 2
    tw = (st.W - gap) // cols
    th = 340
    for k, (photo, price, chip) in enumerate(tiles[:6]):
        x, y = (k % cols) * (tw + gap), top_y + (k // cols) * (th + gap)
        st.paste(img, photo, (x, y, x + tw, y + th))
        shade = Image.linear_gradient("L").resize((tw, 130)).point(lambda v: int(v * 0.8))
        img.paste(Image.new("RGB", (tw, 130), "#000000"), (x, y + th - 130), shade)
        d = ImageDraw.Draw(img)
        d.text((x + 22, y + th - 22), price, font=ig.font(ig.BLACK, 46), fill=ig.WHITE, anchor="ls")
        if chip:
            text, bg, fg = chip
            ig.pill(d, (x + 16, y + 16), text, ig.font(ig.BLACK, 32), bg, fg, pad=(16, 8))
    return top_y + 3 * (th + gap)


def story(spec: dict, tiles: list) -> Image.Image:
    img, d = st.canvas(ig.INK)
    bottom = tile_grid(img, tiles, 345)
    d = ImageDraw.Draw(img)
    st.header(d, spec["kicker"])
    y = bottom + 24
    d.text((60, y), spec["title"], font=ig.fit_font(d, spec["title"], ig.BLACK, 68, st.W - 120), fill=ig.WHITE)
    d.text((60, y + 84), "каждый день в Telegram", font=ig.font(ig.BLACK, 64), fill="#3ddc84")
    d.text((60, y + 176), f"@{spec['handle']}", font=ig.font(ig.BOLD, 52), fill="#8aa6ff")
    d.text((60, y + 250), "Подписывайтесь — ссылка ниже", font=ig.font(ig.REG, 40), fill="#b8c2d6")
    return img


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    full = {lot["id"]: lot for lot in json.loads((ig.DATA / "lots-full.json").read_text(encoding="utf-8"))}
    sections = {s["slug"]: s for s in json.loads((ig.DATA / "top.json").read_text(encoding="utf-8"))["sections"]}
    cars = {c["id"]: c for c in json.loads((ig.DATA / "cars.json").read_text(encoding="utf-8"))["items"]}
    notes = ["# Stories — наши Telegram-каналы, порядок публикации\n"]
    for n, spec in enumerate(CHANNELS, 1):
        tiles = []
        if spec.get("cars"):
            for p in cars_top.PICKS:
                car = cars.get(p["id"])
                if not car:
                    continue
                i, _, boxes = p["photos"][0]
                photo = cars_top.blurred(ig.fetch_photo(car["images"][i]), boxes)
                discount = round((1 - car["price"] / p["market"]) * 100)
                bg, fg = ig.discount_colors(discount)
                tiles.append((photo, ig.mln(car["price"]).replace(" ₸", ""), (f"−{discount}% к рынку", bg, fg)))
            for cid, k in ((4890, 2),):  # шестая плитка — без оценки, только год
                car = cars.get(cid)
                if car:
                    tiles.append((ig.fetch_photo(car["images"][k]), ig.mln(car["price"]).replace(" ₸", ""),
                                  (str(car["year"]), ig.GREEN, ig.WHITE)))
        else:
            for x in sections[spec["top"]]["items"]:
                lot = full.get(x["id"])
                if not lot:
                    continue
                url = lot["images"][PHOTO[x["id"]]] if x["id"] in PHOTO else x.get("image") or (lot["images"] or [None])[0]
                photo = ig.fetch_photo(url)
                capped = bool(x.get("discount_note"))
                bg, fg = ig.discount_colors(x["discount_pct"], capped)
                chip = f"−{st.REGION_CAP}%+" if capped else f"−{x['discount_pct']}% к рынку"
                tiles.append((photo, ig.mln(lot["price"]).replace(" ₸", ""), (chip, bg, fg)))
        story(spec, tiles[:6]).save(OUT / spec["file"], quality=92)
        notes.append(f"{n}. `{spec['file']}` — стикер «Ссылка»: https://t.me/{spec['handle']} (текст «Подписаться»)")
    (OUT / "stories.md").write_text("\n".join(notes) + "\n", encoding="utf-8")
    print(OUT)


if __name__ == "__main__":
    main()
