"""Карусель Instagram «ТОП машин с торгов» — в том же виде, что ТОП квартир (обложка-мозаика, коллаж 2×2 на машину).

    uv run --project backend --with pillow --with httpx python web/scripts/make_instagram_cars.py

Рыночной оценки машин в базе нет: «рынок» — медиана цен в объявлениях о продаже той же модели того же года
(kolesa.kz, смотрели вручную; дата — в MARKET_CHECKED). Перед публикацией цены перепроверить.
Отбор — глазами по фото: без повреждений, разбора, «нет ключей», ареста; на фото не должно быть людей.
Госномера размываем (blur — доли кадра x0, y0, x1, y1); у Halyk номера часто уже скрыты.
"""

import json
import sys
from pathlib import Path

from PIL import Image, ImageFilter

sys.path.insert(0, str(Path(__file__).parent))
import make_instagram as mi  # noqa: E402

MARKET_CHECKED = "20.10.2026"
FOLDER = "07-top-avto"
LINK = "torgi.kz/avto"

# photos — (номер фото, подпись, [области с номером для размытия])
PICKS = [
    {"id": 4872, "title": "Changan CS55 Plus, 2025", "market": 9_700_000,
     # на фото 1 за машиной — человек
     "photos": [(0, "", [(0.34, 0.74, 0.56, 0.85)]), (1, "", [(0.33, 0.18, 0.38, 0.26)]), (2, "", []), (4, "салон", [])]},
    {"id": 4838, "title": "Changan CS75 Plus, 2025", "market": 11_500_000,
     "photos": [(2, "", [(0.44, 0.72, 0.66, 0.85)]), (4, "", [(0.37, 0.48, 0.70, 0.55)]), (1, "салон", []),
                (6, "задний ряд", [])]},
    {"id": 4917, "title": "Chery Tiggo 2 Pro, 2025", "market": 5_700_000,
     "photos": [(0, "", [(0.62, 0.68, 0.80, 0.85)]), (1, "", [(0.22, 0.55, 0.40, 0.77)]), (2, "салон", []),
                (5, "задний ряд", [])]},
    {"id": 4904, "title": "JAC JS4, 2023", "market": 6_400_000,
     "photos": [(0, "", []), (1, "", []), (4, "салон", []), (3, "", [])]},
    {"id": 4857, "title": "Jetour Dashing, 2024", "market": 9_500_000,
     "photos": [(2, "", []), (3, "", []), (4, "салон", []), (5, "задний ряд", [])]},
]

HASHTAGS = "#автостаргов #авто #машины #автоказахстан #залоговоеимущество #купитьавто #торги #torgikz"


def blurred(img: Image.Image | None, boxes: list[tuple]) -> Image.Image | None:
    if img is None or not boxes:
        return img
    img = img.copy()
    for x0, y0, x1, y1 in boxes:
        box = (round(x0 * img.width), round(y0 * img.height), round(x1 * img.width), round(y1 * img.height))
        img.paste(img.crop(box).filter(ImageFilter.GaussianBlur(max(img.width // 60, 8))), box[:2])
    return img


def km(v: int | None) -> str:
    return f"{round(v / 1000)} тыс. км" if v else ""


def main():
    cars = {c["id"]: c for c in json.loads((mi.DATA / "cars.json").read_text(encoding="utf-8"))["items"]}
    rows = []
    for p in PICKS:
        car = cars.get(p["id"])
        if not car or not car.get("price"):
            print(f"  машины {p['id']} нет в выгрузке (продана?) — пропускаем")
            continue
        photos = [(blurred(mi.fetch_photo(car["images"][i]), boxes), label) for i, label, boxes in p["photos"]]
        discount = round((1 - car["price"] / p["market"]) * 100)
        place = " · ".join(x for x in (car.get("city") or car.get("region"), km(car.get("mileage_km")),
                                       car.get("transmission")) if x)
        rows.append({"car": car, "title": p["title"], "place": place, "photos": photos, "market": p["market"],
                     "discount": discount})
    rows.sort(key=lambda r: -r["discount"])
    lo, hi = min(r["discount"] for r in rows), max(r["discount"] for r in rows)
    n = len(rows)
    # обложка — как у самого охватного поста «ТОП-5 квартир Алматы ниже рынка»: тёмный фон и знак раздела
    slides = [mi.cover_slide(f"ТОП-{n} машин с торгов ниже рынка",
                             f"Залоги и имущество банков: цены на {lo}–{hi}% ниже объявлений о продаже таких же машин",
                             "ТОП недели · Авто", icon="car")]
    slides += [mi.collage_slide(r["car"], r["title"], r["place"], r["photos"], r["market"], r["discount"], i, link=LINK)
               for i, r in enumerate(rows, 1)]
    slides.append(mi.cta_slide(f"Ещё {len(cars)} машин с торгов", [
        "Все автомобили с торгов — в разделе «Авто» на torgi.kz",
        "Новые машины каждый день — в Telegram @torgi_kz_auto",
        "Бесплатная консультация по любому лоту",
    ]))
    mi.save_post(FOLDER, slides)

    # без списка машин и «Как считаем» — всё это на слайдах (решение владельца сайта от 21.10.2026)
    caption = (f"ТОП-{n} машин с торгов — ниже рынка до {hi}% 🚗\n\n"
               # в Instagram — ссылки только на сайт и основной канал (решение владельца сайта от 21.10.2026)
               "Сохраните, чтобы не потерять 📌 Все машины с торгов — на сайте torgi.kz.\n"
               f"{mi.TG_LINE}\n\n"
               f"{HASHTAGS}")
    out = mi.OUT / "posts" / FOLDER
    (out / "caption.txt").write_text(caption, encoding="utf-8")
    print(out)
    print(caption)


if __name__ == "__main__":
    main()
