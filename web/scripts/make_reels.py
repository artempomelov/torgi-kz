"""Instagram Reels «Лот дня»: ролик 1080×1920, ~14 с — фото лота с плавным приближением, цифры и призыв.

    uv run --project backend --with pillow --with httpx --with imageio-ffmpeg python web/scripts/make_reels.py candidates
    uv run --project backend --with pillow --with httpx --with imageio-ffmpeg python web/scripts/make_reels.py 1454 4,1,2,3,5

candidates — контактные листы лучших неопубликованных лотов с плашкой (квартиры Алматы и Астаны, 5+ фото;
сначала недорогие со скидкой от 30%):
по ним глазами выбираем лот и 4–5 фото без людей, номеров и мусора (как для каруселей). Второй вызов — ролик:
marketing/instagram/<дата>/reels/<id>.mp4, обложка cover.jpg и caption.txt. Звука нет: музыку добавляем
в приложении Instagram при публикации (трендовый трек даёт охват). Сверху ~250 px и снизу ~420 px Instagram
закрывает кадр интерфейсом — текст держим посередине. Использованные лоты — в marketing/instagram/reels-used.json.
"""

import json
import subprocess
import sys
from datetime import date
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageOps

sys.path.insert(0, str(Path(__file__).resolve().parent))
import make_instagram as ig  # noqa: E402  (шрифты, цвета, фото, плашки — как в каруселях)

W, H, FPS = 1080, 1920, 30
OUT = ig.ROOT / "marketing" / "instagram" / date.today().isoformat() / "reels"
USED = ig.ROOT / "marketing" / "instagram" / "reels-used.json"
CITY_IN = {"Алматы": "в Алматы", "Астана": "в Астане"}
HASHTAGS = {"Алматы": "#недвижимостьалматы #квартираалматы #алматы", "Астана": "#недвижимостьастана #квартираастана #астана"}
COMMON_TAGS = "#торги #залоговоеимущество #квартиры #недвижимость #torgikz"


def used() -> set[int]:
    return set(json.loads(USED.read_text(encoding="utf-8"))) if USED.exists() else set()


def title(lot: dict) -> str:
    rooms = f"{lot['rooms']}-комнатная" if lot.get("rooms") else "Квартира"
    return f"{rooms} {CITY_IN.get(lot.get('city'), 'в г. ' + str(lot.get('city')))}"


MIN_PCT = 30  # лучше всего заходят недорогие квартиры Алматы и Астаны со скидкой от 30% (владелец, 25.10.2026)


def pool(skip: set[int]) -> list[dict]:
    """Квартиры Алматы и Астаны с плашкой: сначала со скидкой от 30% — от дешёвых к дорогим, потом остальные по скидке."""
    lots = json.loads((ig.DATA / "lots-full.json").read_text(encoding="utf-8"))
    out = [x for x in lots if x.get("market") and x["category"] == "apartment" and x.get("city") in CITY_IN
           and x.get("status", "active") == "active" and len(x.get("images") or []) >= 5 and x["id"] not in skip
           and not x.get("duplicate_of") and "черновая" not in x["market"]["where"]]
    strong = lambda x: x["market"]["over"] or x["market"]["pct"] >= MIN_PCT  # noqa: E731
    return sorted(out, key=lambda x: (not strong(x), x["price"] if strong(x) else -x["market"]["pct"]))


def candidates(n: int = 8):
    """Контактные листы: лучшие лоты с плашкой, которых ещё не было в Reels и в постах/сторис."""
    sheets(pool(used() | {x["id"] for pick in ig.PICKS for x in pick["lots"]})[:n], OUT / "candidates")


def sheets(lots: list[dict], out: Path):
    """Контактный лист на лот: до 12 фото с номерами — по ним глазами выбираем кадры без людей и мусора."""
    out.mkdir(parents=True, exist_ok=True)
    for x in lots:
        thumbs = [ig.fetch_photo(u) for u in x["images"][:12]]
        sheet = Image.new("RGB", (4 * 300, 3 * 250 + 60), "white")
        d = ImageDraw.Draw(sheet)
        d.text((10, 10), f"{x['id']} · {title(x)} · {ig.mln(x['price'])} · −{x['market']['pct']}% {x['market']['where']}",
               font=ig.font(ig.BOLD, 24), fill=ig.INK)
        for k, t in enumerate(thumbs):
            if t:
                sheet.paste(ImageOps.fit(t, (296, 246)), (k % 4 * 300 + 2, 60 + k // 4 * 250 + 2))
            d.text((k % 4 * 300 + 8, 60 + k // 4 * 250 + 6), str(k), font=ig.font(ig.BLACK, 32), fill=ig.RED)
        sheet.save(out / f"{x['id']}.jpg", quality=85)
        print(out / f"{x['id']}.jpg")


def kenburns(photo: Image.Image, t: float, zoom: float = 0.12, pan: int = 1) -> Image.Image:
    """Кадр с плавным приближением: t от 0 до 1."""
    base = ImageOps.fit(photo, (int(W * (1 + zoom)), int(H * (1 + zoom))), Image.LANCZOS)
    scale = 1 + zoom * (1 - t)
    w, h = int(W * scale), int(H * scale)
    left = (base.width - w) // 2 + int(pan * (base.width - w) // 2 * (t - 0.5))
    frame = base.crop((max(left, 0), (base.height - h) // 2, max(left, 0) + w, (base.height - h) // 2 + h))
    return frame.resize((W, H), Image.BILINEAR)


def overlay_text(img: Image.Image, lines: list[tuple[str, int, str]], y: int, chip: tuple[str, str, str] | None = None):
    """Подложка-градиент и строки (текст, размер, цвет) с плашкой сверху."""
    shade = Image.linear_gradient("L").resize((W, 900)).point(lambda v: int(v * 0.85))
    img.paste(Image.new("RGB", (W, 900), "#000000"), (0, y - 300), shade)
    d = ImageDraw.Draw(img)
    if chip:
        ig.pill(d, (60, y), chip[0], ig.font(ig.BLACK, 56), chip[1], chip[2], pad=(30, 14))
        y += 130
    for text, size, color in lines:
        f = ig.fit_font(d, text, ig.BLACK, size, W - 120)
        d.text((60, y), text, font=f, fill=color)
        y += int(size * 1.25)


def card(lot: dict, photo: Image.Image | None) -> Image.Image:
    """Финальный кадр: цифры и призыв на тёмном фоне поверх размытого фото."""
    img = (ImageOps.fit(photo, (W, H)).filter(ImageFilter.GaussianBlur(28)) if photo else Image.new("RGB", (W, H), ig.INK))
    img = Image.blend(img, Image.new("RGB", (W, H), ig.INK), 0.72)
    d = ImageDraw.Draw(img)
    ig.logo(d, 60, 330, size=56, dark=False)
    y = 520
    d.text((60, y), ig.mln(lot["price"]), font=ig.font(ig.BLACK, 120), fill=ig.WHITE)
    y += 160
    bg, fg = ig.discount_colors(lot["market"]["pct"], lot["market"]["over"])
    ig.pill(d, (60, y), f"−{lot['market']['pct']}% к рынку", ig.font(ig.BLACK, 54), bg, fg, pad=(28, 12))
    y += 130
    # только скидка — без «рынок в районе — около …» (решение владельца от 23.10.2026)
    facts = [" · ".join(x for x in (f"{lot['area_m2']:g} м²".replace(".", ",") if lot.get("area_m2") else None,
                                    f"{lot['floor']} этаж" if lot.get("floor") else None,
                                    f"дом {lot['year_built']} г." if lot.get("year_built") else None) if x),
             (lot.get("district") or lot.get("city") or "")]
    for line in facts:
        if line:
            d.text((60, y), line, font=ig.font(ig.REG, 50), fill="#d6dcea")
            y += 72
    y += 60
    d.text((60, y), "Все фото и детали —", font=ig.font(ig.BOLD, 58), fill=ig.WHITE)
    d.text((60, y + 78), "на torgi.kz", font=ig.font(ig.BLACK, 76), fill="#3ddc84")
    d.text((60, y + 190), "Ссылка в шапке профиля", font=ig.font(ig.REG, 44), fill="#b8c2d6")
    return img


def render(lot_id: int, idx: list[int]):
    lots = {x["id"]: x for x in json.loads((ig.DATA / "lots-full.json").read_text(encoding="utf-8"))}
    lot = lots[lot_id]
    photos = [ig.fetch_photo(lot["images"][i]) for i in idx]
    photos = [p for p in photos if p]
    OUT.mkdir(parents=True, exist_ok=True)
    pct = lot["market"]["pct"]
    bg, fg = ig.discount_colors(pct, lot["market"]["over"])
    # сцены: (длительность, функция кадра от t)
    hook_lines = [(title(lot), 84, ig.WHITE), (f"за {ig.mln(lot['price'])}", 84, ig.WHITE)]
    scenes = [(3.0, lambda t, p=photos[0]: _with(kenburns(p, t), hook_lines, 1080, (f"−{pct}% к рынку", bg, fg)))]
    for k, p in enumerate(photos[1:5]):
        scenes.append((1.8, lambda t, p=p, k=k: kenburns(p, t, pan=1 if k % 2 else -1)))
    final = card(lot, photos[0])
    scenes.append((4.0, lambda t: final))
    ffmpeg = __import__("imageio_ffmpeg").get_ffmpeg_exe()
    out = OUT / f"{lot_id}.mp4"
    proc = subprocess.Popen([ffmpeg, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                             "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "medium",
                             "-crf", "20", "-movflags", "+faststart", str(out)], stdin=subprocess.PIPE)
    prev = None
    fade = int(0.35 * FPS)  # перекрёстный переход между сценами
    for dur, make in scenes:
        n = int(dur * FPS)
        for i in range(n):
            frame = make(i / max(n - 1, 1))
            if prev is not None and i < fade:
                frame = Image.blend(prev, frame, (i + 1) / (fade + 1))
            proc.stdin.write(frame.convert("RGB").tobytes())
            last = frame
        prev = last
    proc.stdin.close()
    proc.wait()
    scenes[0][1](0.5).save(OUT / f"{lot_id}-cover.jpg", quality=92)
    city = lot.get("city")
    facts = ", ".join(x for x in (f"{lot['area_m2']:g} м²".replace(".", ",") if lot.get("area_m2") else None,
                                  lot.get("district")) if x)
    caption = (f"{title(lot)} за {ig.mln(lot['price'])} — на {pct}% ниже рынка 🔥\n\n"
               f"{facts}\n\n"
               "Сохраните, чтобы не потерять 📌 Все фото и детали — на сайте torgi.kz, ссылка в шапке профиля.\n"
               f"{ig.TG_LINE}\n\n"
               f"{HASHTAGS.get(city, '')} {COMMON_TAGS}")
    (OUT / f"{lot_id}-caption.txt").write_text(caption, encoding="utf-8")
    USED.write_text(json.dumps(sorted(used() | {lot_id})), encoding="utf-8")
    print(out)
    print(caption)


def _with(frame: Image.Image, lines, y, chip) -> Image.Image:
    overlay_text(frame, lines, y, chip)
    return frame


def main():
    args = sys.argv[1:]
    if not args or args[0] == "candidates":
        candidates()
    else:
        render(int(args[0]), [int(i) for i in args[1].split(",")])


if __name__ == "__main__":
    main()
