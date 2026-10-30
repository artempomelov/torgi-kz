"""Instagram torgi.kz: оформление профиля и готовые посты-карусели с подборками недели.

    uv run --project backend --with pillow python web/scripts/make_instagram.py

Данные — web/data (выгрузка `torgi.cli export --market …`; скидка — с плашки сайта). Лоты для подборок
отбираем глазами по контактным листам web/scripts/instagram_candidates.py и вписываем в PICKS.
Результат — marketing/instagram/<дата>/:
  profile/      аватар, обложки «Актуального», тексты профиля (profile.md)
  posts/NN-*/   слайды 1080×1350 (формат 4:5) — загружать по порядку как карусель
  captions.md   подписи с хештегами к каждому посту
Папка marketing/ в git не попадает: на слайдах фото с сайтов продавцов.
"""

import hashlib
import io
import json
import sys
from datetime import date
from pathlib import Path

import httpx
from PIL import Image, ImageDraw, ImageEnhance, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
from torgi.top import REGION_DISCOUNT_CAP  # noqa: E402

DATA = ROOT / "web" / "data"
OUT = ROOT / "marketing" / "instagram" / date.today().isoformat()
CACHE = ROOT / "marketing" / "instagram" / "photo-cache"

FONTS = Path("C:/Windows/Fonts")
REG, BOLD = FONTS / "segoeui.ttf", FONTS / "segoeuib.ttf"
BLACK = FONTS / "seguibl.ttf" if (FONTS / "seguibl.ttf").exists() else BOLD

INK, COBALT, WHITE, SOFT, MUTED = "#0f1115", "#2450d6", "#ffffff", "#e8eefc", "#5b6b73"
GREEN, LIGHT = "#1f9d55", "#f4f6fa"
YELLOW, RED = "#facc15", "#e11d48"


def discount_colors(pct: int, capped: bool = False) -> tuple[str, str]:
    """Плашка скидки к рынку — как на сайте: до 15% жёлтая, больше — красная (фон, текст)."""
    return (YELLOW, INK) if pct <= 15 and not capped else (RED, WHITE)
W, H = 1080, 1350

ORIGIN = {
    "arrested": "Арестованное имущество", "bank_balance": "Имущество банка", "bank_pledge": "Залог банка",
    "court": "Судебная реализация", "state": "Госимущество", "bankrupt": "Имущество банкрота",
    "tax_debtor": "Имущество налогового должника", "confiscated": "Конфискат",
}
SALE = {"auction": "аукцион", "auction_down": "аукцион на понижение", "direct": "прямая продажа", "tender": "тендер"}
# подписи ячеек коллажа по умолчанию: главное фото без подписи
CELL_LABELS = {"apartment": ["", "кухня", "санузел", "дом"], "house": ["", "кухня", "санузел", "дом"],
               "commercial": ["", "", "", "здание"]}


def font(path: Path, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(path), size)


def fit_font(d: ImageDraw.ImageDraw, text: str, path: Path, size: int, width: int) -> ImageFont.FreeTypeFont:
    """Самый крупный шрифт не больше size, с которым строка влезает в width."""
    while size > 20 and d.textlength(text, font=font(path, size)) > width:
        size -= 2
    return font(path, size)


def mln(v: float) -> str:
    return f"{v / 1e6:.1f}".replace(".", ",").replace(",0", "") + " млн ₸"


def wrap(d: ImageDraw.ImageDraw, text: str, f: ImageFont.FreeTypeFont, width: int) -> list[str]:
    # неразрывные группы: предлог или союз — со следующим словом, тире — с предыдущим, «3 314» — целиком;
    # неразрывный пробел («30 млн ₸») строку не делит
    units: list[str] = []
    for word in (w for w in text.split(" ") if w):
        prev = units[-1].split()[-1] if units else ""
        if units and (word in ("—", "–") or (len(prev) <= 2 and prev.isalpha()) or (prev.isdigit() and word.isdigit())):
            units[-1] += " " + word
        else:
            units.append(word)
    lines, line = [], ""
    for word in units:
        test = f"{line} {word}".strip()
        if d.textlength(test, font=f) <= width:
            line = test
        else:
            lines.append(line)
            line = word
    return lines + ([line] if line else [])


def text_block(d, xy, text, f, fill, width, gap=1.25) -> int:
    x, y = xy
    for line in wrap(d, text, f, width):
        d.text((x, y), line, font=f, fill=fill)
        y += int(f.size * gap)
    return y


def logo(d: ImageDraw.ImageDraw, x: int, y: int, size: int = 40, dark: bool = False):
    f = font(BOLD, size)
    d.text((x, y), "torgi", font=f, fill=INK if dark else WHITE)
    d.text((x + d.textlength("torgi", font=f), y), ".kz", font=f, fill=COBALT if dark else "#8aa6ff")


def house(d: ImageDraw.ImageDraw, cx: int, top: int, scale: float, color: str, arrow: str | None = COBALT):
    """Домик со стрелкой вниз — символ бренда («цена ниже рынка»)."""
    w = int(40 * scale)
    half, h = 190 * scale, 140 * scale
    d.line([(cx - half, top + h), (cx, top), (cx + half, top + h)], fill=color, width=w, joint="curve")
    base = top + 330 * scale
    side = 135 * scale
    d.line([(cx - side, top + 110 * scale), (cx - side, base), (cx + side, base), (cx + side, top + 110 * scale)],
           fill=color, width=w, joint="curve")
    if arrow:
        d.rectangle([cx - 22 * scale, top + 120 * scale, cx + 22 * scale, top + 230 * scale], fill=arrow)
        d.polygon([(cx - 70 * scale, top + 220 * scale), (cx + 70 * scale, top + 220 * scale), (cx, top + 290 * scale)],
                  fill=arrow)


def car(d: ImageDraw.ImageDraw, cx: int, top: int, scale: float, color: str, arrow: str = COBALT):
    """Машина со стрелкой вниз — знак раздела «Авто» (как на аватарке @torgi_kz_auto); top — верх крыши."""
    k, w = scale, round(40 * scale)

    def p(x, y):
        return cx + x * k, top + y * k

    d.line([p(-200, 215), p(-200, 150), p(-150, 128), p(-95, 122), p(-55, 0), p(70, 0), p(115, 122), p(180, 135),
            p(205, 165), p(205, 215)], fill=color, width=w, joint="curve")
    for x in (-200, 205):  # скруглённые концы бамперов
        bx, by = p(x, 215)
        d.ellipse([bx - w / 2, by - w / 2, bx + w / 2, by + w / 2], fill=color)
    for a, b in ((-200, -165), (-55, 75), (180, 205)):  # днище между колёсами
        d.line([p(a, 215), p(b, 215)], fill=color, width=w)
    for x in (-110, 128):  # колёса: обод цвета кузова, середина — цвета фона
        wx, wy = p(x, 225)
        d.ellipse([wx - 58 * k, wy - 58 * k, wx + 58 * k, wy + 58 * k], fill=color)
        d.ellipse([wx - 24 * k, wy - 24 * k, wx + 24 * k, wy + 24 * k], fill=INK)
    d.rectangle([*p(-22, 48), *p(22, 125)], fill=arrow)
    d.polygon([p(-66, 118), p(66, 118), p(0, 186)], fill=arrow)


def pill(d, xy, text, f, bg, fg, pad=(26, 12)):
    x, y = xy
    tw = d.textlength(text, font=f)
    d.rounded_rectangle([x, y, x + tw + 2 * pad[0], y + f.size + 2 * pad[1]], radius=(f.size + 2 * pad[1]) // 2, fill=bg)
    d.text((x + pad[0], y + pad[1] - f.size * 0.12), text, font=f, fill=fg)
    return x + tw + 2 * pad[0]


def fetch_photo(url: str | None) -> Image.Image | None:
    """Фото продавца: поворот по EXIF и одна обработка для всех — автоконтраст, чуть ярче и сочнее
    (фото у продавцов часто тёмные и серые, а в одной карусели должны смотреться ровно)."""
    if not url:
        return None
    path = CACHE / (hashlib.md5(url.encode()).hexdigest() + ".jpg")
    try:
        if not path.exists():
            res = httpx.get(url, timeout=25, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0"})
            res.raise_for_status()
            CACHE.mkdir(parents=True, exist_ok=True)
            ImageOps.exif_transpose(Image.open(io.BytesIO(res.content))).convert("RGB").save(path, quality=94)
        img = ImageOps.autocontrast(Image.open(path).convert("RGB"), cutoff=0.6)
    except Exception:
        return None
    return ImageEnhance.Color(ImageEnhance.Brightness(img).enhance(1.05)).enhance(1.1)


# --- слайды -----------------------------------------------------------------------------------------

def cover_slide(title: str, subtitle: str, kicker: str, icon: str = "house") -> Image.Image:
    img = Image.new("RGB", (W, H), INK)
    d = ImageDraw.Draw(img)
    logo(d, 80, 80)
    if icon == "car":
        car(d, W // 2, 250, 1.05, WHITE)
    else:
        house(d, W // 2, 210, 0.95, WHITE)
    y = 640
    pill(d, (80, y), kicker, font(BOLD, 34), COBALT, WHITE)
    y = text_block(d, (80, y + 95), title, font(BLACK, 84), WHITE, W - 160, 1.1)
    text_block(d, (80, y + 25), subtitle, font(REG, 38), "#b8c2d6", W - 160)
    d.text((W - 80, H - 80), "листайте →", font=font(BOLD, 36), fill="#8aa6ff", anchor="rs")
    return img


def mosaic_cover(kicker: str, title: str, accent: str, subtitle: str, photos: list[Image.Image | None]) -> Image.Image:
    """Обложка подборки: главные фото пяти объектов (2 сверху, 3 снизу) и заголовок."""
    img = Image.new("RGB", (W, H), WHITE)
    gap, mosaic_h = 6, 760
    row_h = (mosaic_h - gap) // 2
    for r, row in enumerate([photos[:2], photos[2:5]]):
        cell_w = (W - gap * (len(row) - 1)) // len(row)
        for k, photo in enumerate(row):
            if photo:
                img.paste(ImageOps.fit(photo, (cell_w, row_h), Image.LANCZOS), (k * (cell_w + gap), r * (row_h + gap)))
    d = ImageDraw.Draw(img)
    y = mosaic_h + 50
    pill(d, (64, y), kicker, font(BOLD, 32), GREEN, WHITE)
    d.text((64, y + 80), title, font=fit_font(d, title, BLACK, 76, W - 128), fill=INK)
    d.text((64, y + 172), accent, font=fit_font(d, accent, BLACK, 76, W - 128), fill=GREEN)
    d.text((64, y + 280), subtitle, font=fit_font(d, subtitle, REG, 32, W - 128), fill=MUTED)
    d.text((W - 64, H - 50), "листайте →", font=font(BOLD, 34), fill=COBALT, anchor="rs")
    return img


def collage_slide(lot: dict, title: str, place: str, photos: list[tuple[Image.Image | None, str]],
                  estimate: float | None, discount: int, rank: int, note: str | None = None,
                  link: str = "torgi.kz/top") -> Image.Image:
    """Объект подборки: коллаж 2×2 (по умолчанию комната, кухня, санузел, дом) и белая плашка с ценой.
    note — «более 30%» вместо точной скидки (вне Алматы и Астаны оценка грубее, как в ТОПе на сайте)."""
    img = Image.new("RGB", (W, H), WHITE)
    d = ImageDraw.Draw(img)
    gap, grid_h = 6, 820
    cell_w, cell_h = (W - gap) // 2, (grid_h - gap) // 2
    for k, (photo, label) in enumerate(photos[:4]):
        x, y = (k % 2) * (cell_w + gap), (k // 2) * (cell_h + gap)
        if photo:
            img.paste(ImageOps.fit(photo, (cell_w, cell_h), Image.LANCZOS), (x, y))
        else:
            d.rectangle([x, y, x + cell_w, y + cell_h], fill=SOFT)
        if label:
            pill(d, (x + 18, y + cell_h - 52), label, font(BOLD, 24), INK, WHITE, pad=(14, 6))
    d.ellipse([36, 36, 126, 126], fill=GREEN)
    d.text((81, 81), str(rank), font=font(BLACK, 52), fill=WHITE, anchor="mm")
    # плашка скидки — в левом верхнем углу (фото коллажа равнозначные), рядом с номером
    badge, bf = (f"скидка {note}" if note else f"−{discount}% к рынку"), font(BLACK, 40)
    pill(d, (144, 49), badge, bf, *discount_colors(discount, bool(note)))

    y = grid_h + 34
    d.text((64, y), title, font=fit_font(d, title, BOLD, 44, W - 128), fill=INK)
    d.text((64, y + 62), place, font=fit_font(d, place, REG, 32, W - 128), fill=MUTED)
    y += 128
    # только цена и скидка на плашке — без «рынок ≈ …» и пояснений об оценке (решение владельца от 23.10.2026)
    d.text((64, y), mln(lot["price"]), font=font(BLACK, 84), fill=INK)
    tags = [ORIGIN.get(lot["origin"], lot["origin"])]
    if lot.get("sale_type") in SALE:
        tags.append(SALE[lot["sale_type"]])
    pill(d, (64, y + 128), " · ".join(tags), font(BOLD, 28), LIGHT, COBALT)
    d.text((W - 64, H - 50), link, font=font(BOLD, 30), fill=COBALT, anchor="rs")
    return img


def cta_slide(title: str, lines: list[str]) -> Image.Image:
    img = Image.new("RGB", (W, H), COBALT)
    d = ImageDraw.Draw(img)
    logo(d, 80, 80)
    y = text_block(d, (80, 300), title, font(BLACK, 84), WHITE, W - 160, 1.1) + 50
    for line in lines:
        d.text((80, y), "→", font=font(BOLD, 44), fill=WHITE)
        y = text_block(d, (150, y), line, font(REG, 42), WHITE, W - 240) + 26
    pill(d, (80, H - 230), "Ссылка — в шапке профиля", font(BOLD, 38), WHITE, COBALT)
    return img


def text_slide(n: int, total: int, title: str, body: str, dark: bool = False) -> Image.Image:
    bg, fg, sub = (INK, WHITE, "#b8c2d6") if dark else (WHITE, INK, "#3b4652")
    img = Image.new("RGB", (W, H), bg)
    d = ImageDraw.Draw(img)
    logo(d, 80, 80, dark=not dark)
    d.text((W - 80, 92), f"{n}/{total}", font=font(BOLD, 34), fill=MUTED, anchor="ra")
    d.ellipse([80, 260, 200, 380], fill=COBALT)
    d.text((140, 320), str(n), font=font(BLACK, 64), fill=WHITE, anchor="mm")
    y = text_block(d, (80, 440), title, font(BLACK, 70), fg, W - 160, 1.12) + 30
    text_block(d, (80, y), body, font(REG, 40), sub, W - 160, 1.4)
    return img


# --- профиль -------------------------------------------------------------------------------------------

def highlight_cover(label: str, draw_icon) -> Image.Image:
    """Обложка «Актуального»: Instagram показывает центр в круге — значок в центре, подпись — в самой истории."""
    img = Image.new("RGB", (1080, 1920), COBALT)
    d = ImageDraw.Draw(img)
    draw_icon(d, 540, 960)
    d.text((540, 1400), label, font=font(BOLD, 64), fill=WHITE, anchor="mm")
    return img


def icon_top(d, cx, cy):
    d.text((cx, cy), "ТОП", font=font(BLACK, 190), fill=WHITE, anchor="mm")


def icon_steps(d, cx, cy):
    for i in range(3):
        d.rounded_rectangle([cx - 200 + i * 140, cy + 120 - i * 110, cx - 80 + i * 140, cy + 160], radius=16, fill=WHITE)


def icon_pin(text):
    def draw(d, cx, cy):
        d.ellipse([cx - 160, cy - 230, cx + 160, cy + 90], fill=WHITE)
        d.polygon([(cx - 120, cy + 20), (cx + 120, cy + 20), (cx, cy + 230)], fill=WHITE)
        d.text((cx, cy - 70), text, font=font(BLACK, 110), fill=COBALT, anchor="mm")
    return draw


def icon_question(d, cx, cy):
    d.text((cx, cy), "?", font=font(BLACK, 300), fill=WHITE, anchor="mm")


def icon_house(d, cx, cy):
    house(d, cx, cy - 200, 1.0, WHITE, arrow=INK)


# --- сборка ---------------------------------------------------------------------------------------------

def save_post(folder: str, slides: list[Image.Image]):
    path = OUT / "posts" / folder
    path.mkdir(parents=True, exist_ok=True)
    for i, s in enumerate(slides, 1):
        s.save(path / f"{i:02d}.jpg", quality=92)


# ссылки в подписях Instagram не кликабельны, а «@канал» стал бы ссылкой на чужой Instagram — пишем адрес
# адрес t.me в подписи Instagram не кликабелен — кликабельные ссылки (сайт и основной канал) стоят в шапке профиля
TG_LINE = "📲 Новые лоты каждый день — в Telegram, ссылка в шапке профиля"

HASHTAGS = {
    "Алматы": "#недвижимостьалматы #квартираалматы #алматы #купитьквартирувалматы #квартиранижерынка",
    "Астана": "#недвижимостьастана #квартираастана #астана #купитьквартирувастане #квартиранижерынка",
    "бизнес": "#коммерческаянедвижимость #готовыйбизнес #помещение #офис #бизнесказахстан",
    "до30": "#квартиранижерынка #недорогиеквартиры #купитьквартиру #квартиразалог #первоежильё",
    "common": "#торги #недвижимостьказахстан #залоговоеимущество #аукцион #инвестициивнедвижимость #torgikz",
}

# Подборки недели. Лоты отбираем глазами (web/scripts/instagram_candidates.py): с нормальными фото ремонта,
# не стройка и не захламлённые комнаты. photos — четыре фото коллажа по номеру в лоте (с нуля), по умолчанию
# комната, кухня, санузел, дом; (номер, "подпись") — своя подпись ячейки. title — вместо «Коммерческая, N м²»,
# district — если у лота не указан район (иначе оценка по городу в целом и скидка завышена).
# cover: "house" — обложка как у самого охватного поста (тёмный фон, знак раздела с домиком, «ТОП-N … ниже рынка»),
# иначе — мозаика фото; cover_title — заголовок такой обложки ({n} — число объектов).
PICKS = [
    {"folder": "02-top-almaty", "kicker": "ТОП недели · Алматы", "title": "5 квартир с ремонтом",
     "headline": "ТОП-5 квартир Алматы с торгов", "hashtags": "Алматы", "cover": "house",
     "cover_title": "ТОП-{n} квартир Алматы ниже рынка", "lots": [
         {"id": 1583, "photos": [5, 2, (4, "спальня"), 0]},
         {"id": 1272, "photos": [4, 11, 10, 8]},
         {"id": 109, "photos": [8, 9, 6, 0]},
         {"id": 1454, "photos": [6, 7, 5, 0], "district": "Наурызбайский район, мкр. Шугыла"},
         # тот же ЖК, что у 1272, — фото дома не повторяем
         {"id": 1302, "photos": [2, (9, "спальня"), (1, "прихожая"), (8, "кабинет")]},
     ]},
    # «до 30 млн» — по Казахстану: в Алматы таких квартир с оценкой рынка всего 6 и почти у всех фото только фасадов
    {"folder": "08-top-do-30-mln", "kicker": "ТОП недели · до 30 млн", "title": "5 квартир до 30 млн ₸",
     "headline": "ТОП-5 квартир до 30 млн ₸ с торгов", "hashtags": "до30", "cover": "house",
     "cover_title": "ТОП-{n} квартир до 30 млн ₸ ниже рынка", "lots": [
         {"id": 98, "photos": [10, (11, "комната"), (6, "прихожая"), 0]},
         {"id": 1102, "title": "Квартира, 2-комн., 50,2 м²", "photos": [7, 6, 9, 0]},
         {"id": 164, "photos": [3, 2, (4, "гостиная"), (5, "спальня")]},
         {"id": 100, "photos": [0, 2, 3, (1, "спальня")]},
         {"id": 1141, "photos": [8, 5, 6, (4, "прихожая")]},
     ]},
    {"folder": "03-top-astana", "kicker": "ТОП недели · Астана", "title": "5 квартир с ремонтом",
     "headline": "ТОП-5 квартир с ремонтом в Астане", "hashtags": "Астана", "lots": [
         {"id": 193, "photos": [5, 3, (9, "вид из окна"), 0]},
         {"id": 1102, "title": "Квартира, 2-комн., 50,2 м²", "photos": [7, 6, 9, 0]},
         {"id": 99, "photos": [11, 8, 7, 0]},
         {"id": 165, "photos": [20, 22, (14, "спальня"), (5, "вид из окна")]},
         {"id": 138, "photos": [9, 6, (8, "спальня"), 0]},
     ]},
    {"folder": "06-top-biznes", "kicker": "ТОП недели · Бизнес", "title": "5 помещений для бизнеса",
     "headline": "ТОП-5 коммерческих объектов с торгов", "hashtags": "бизнес",
     "subtitle": "Офис, салон, детский сад, баня — торги и залоги банков", "lots": [
         {"id": 802, "title": "Офис, 313,7 м²", "photos": [2, (1, "кабинет"), (4, "кабинет"), (3, "кабинет")]},
         {"id": 784, "title": "Помещение свободного назначения, 207,6 м²",
          "photos": [1, (3, "зал"), (6, "кухня"), 7]},
         {"id": 3339, "title": "Здание детского сада, 667 м² с участком",
          "photos": [3, (0, "фасад"), (2, "площадка"), (1, "двор")]},
         {"id": 736, "title": "Помещение под салон, 58,8 м²", "photos": [0, (2, "кабинет"), (4, "санузел"), 7]},
         {"id": 699, "title": "Банный комплекс с бассейном, 875,7 м²",
          "photos": [4, (1, "зона отдыха"), (7, "бильярд"), (0, "территория")]},
     ]},
]


def pick_post(pick: dict, full: dict, total: str) -> str:
    rows = []
    for p in pick["lots"]:
        lot = full.get(p["id"])
        if not lot or not lot.get("price"):
            print(f"  {pick['folder']}: лота {p['id']} нет в выгрузке (снят с торгов?) — пропускаем")
            continue
        # скидка — с плашки сайта (lot["market"]), как в Reels и Threads: перейдя по ссылке, человек видит ту же цифру
        market = lot.get("market")
        if not market:
            print(f"  {pick['folder']}: у лота {p['id']} на сайте нет плашки скидки — пропускаем")
            continue
        city = lot.get("city") or lot.get("region")
        head, _, place = lot["headline"].partition(" — ")
        labels = CELL_LABELS.get(lot["category"], CELL_LABELS["commercial"])
        photos = []
        for k, spec in enumerate(p["photos"]):
            i, label = spec if isinstance(spec, tuple) else (spec, labels[k])
            photos.append((fetch_photo(lot["images"][i]), label))
        discount, capped = market["pct"], market["over"]
        rows.append({"lot": lot, "title": p.get("title") or head, "photos": photos, "estimate": None,
                     "place": f"{city}, {p['district']}" if p.get("district") else place, "discount": discount,
                     "note": f"более {REGION_DISCOUNT_CAP}%" if capped else None,
                     "shown": REGION_DISCOUNT_CAP if capped else discount})
    rows.sort(key=lambda r: -r["discount"])
    lo, hi = min(r["shown"] for r in rows), max(r["shown"] for r in rows)
    if pick.get("cover") == "house":
        slides = [cover_slide(pick["cover_title"].format(n=len(rows)),
                              f"Торги и залоги банков: ниже рынка на {lo}–{hi}%", pick["kicker"])]
    else:
        slides = [mosaic_cover(pick["kicker"], pick["title"], f"ниже рынка на {lo}–{hi}%",
                               pick.get("subtitle", "Торги и залоги банков"),
                               [r["photos"][0][0] for r in rows])]
    slides += [collage_slide(r["lot"], r["title"], r["place"], r["photos"], r["estimate"], r["discount"], i, r["note"])
               for i, r in enumerate(rows, 1)]
    slides.append(cta_slide(f"Ещё {total} лотов с торгов", [
        "Больше объектов ниже рынка — в разделе «ТОП» на torgi.kz",
        "Новые лоты каждый день — в Telegram @torgi_kz_news",
        "Бесплатная консультация по любому лоту",
    ]))
    save_post(pick["folder"], slides)

    # подпись только привлекает: без списка лотов и «Как считаем» — детали на слайдах и на сайте
    # (решение владельца сайта от 21.10.2026)
    return (f"{pick['headline']} — ниже рынка до {hi}% 🔥\n\n"
            f"Сохраните, чтобы не потерять 📌 Все лоты — на сайте torgi.kz.\n{TG_LINE}\n\n"
            f"{HASHTAGS[pick['hashtags']]} {HASHTAGS['common']}")


def main():
    # папки не удаляем (OneDrive держит их во время синхронизации) — только старые слайды постов и профиля;
    # stories/ ведёт make_stories.py
    for old in [p for sub in ("posts", "profile") if (OUT / sub).exists() for p in (OUT / sub).rglob("*.jpg")]:
        old.unlink()
    full = {lot["id"]: lot for lot in json.loads((DATA / "lots-full.json").read_text(encoding="utf-8"))}
    meta = json.loads((DATA / "meta.json").read_text(encoding="utf-8"))
    # число лотов в публичных текстах — «3 000+», как в шапке профиля; не обновляем (решение владельца от 22.10.2026)
    total = "3 000+"

    # профиль
    prof = OUT / "profile"
    prof.mkdir(parents=True, exist_ok=True)
    Image.open(ROOT / "docs" / "brand" / "avatar-5-word-over-house.png").convert("RGB").resize((1080, 1080), Image.LANCZOS) \
        .save(prof / "avatar.jpg", quality=95)
    for name, label, icon in [("1-top", "ТОП", icon_top), ("2-kak-kupit", "Как купить", icon_steps),
                              ("3-almaty", "Алматы", icon_pin("ALA")), ("4-astana", "Астана", icon_pin("AST")),
                              ("5-voprosy", "Вопросы", icon_question), ("6-o-nas", "О нас", icon_house)]:
        highlight_cover(label, icon).save(prof / f"highlight-{name}.jpg", quality=92)

    captions = []
    # 1. знакомство
    save_post("01-o-proekte", [
        cover_slide("Недвижимость с торгов Казахстана — в одном месте",
                    f"{total} объектов: аресты, залоги банков, госимущество и банкроты", "torgi.kz"),
        text_slide(1, 3, "Собираем лоты со всех площадок",
                   "ЕЭТП Минюста, E-Qazyna и 9 банков: Halyk, Нурбанк, BCC, Forte, Bereke, Евразийский и другие. "
                   "Обновление дважды в час — не нужно сидеть на десяти сайтах."),
        text_slide(2, 3, "Показываем, где цена ниже рынка",
                   "Сравниваем цену лота с объявлениями о продаже похожих объектов в том же районе. "
                   "Лучшие — в разделе «ТОП»."),
        text_slide(3, 3, "Помогаем купить",
                   "Бесплатно проконсультируем по любому лоту: что проверить, как участвовать в торгах. "
                   "Пишите в Telegram-бот @torgi_kz_bot.", dark=True),
        cta_slide("Подписывайтесь, чтобы не пропустить выгодные лоты", [
            "Каждую неделю — ТОП квартир Алматы и Астаны ниже рынка",
            "Разборы: как купить с торгов и не ошибиться",
        ]),
    ])
    captions.append(("01-o-proekte", (
        f"Привет! Мы — torgi.kz 👋\n\nСобираем недвижимость с торгов по всему Казахстану: {total} объектов — "
        "арестованное имущество, залоги банков, госимущество и банкроты. Квартиры, дома, коммерция и земля.\n\n"
        "✅ 11 источников в одном каталоге — ЕЭТП Минюста, E-Qazyna и 9 банков\n"
        "✅ Обновление дважды в час\n"
        "✅ Оценка: насколько цена ниже рынка\n"
        "✅ Бесплатная консультация по лоту\n\n"
        f"Подписывайтесь — каждую неделю публикуем ТОП объектов ниже рынка. Каталог — по ссылке в шапке профиля.\n{TG_LINE}\n\n"
        f"{HASHTAGS['common']} #недвижимость #казахстан")))

    # 2, 3, 6. подборки недели: Алматы, Астана, бизнес
    for pick in PICKS:
        captions.append((pick["folder"], pick_post(pick, full, total)))

    # 4. как купить
    steps = [
        ("Найдите объект", "В каталоге torgi.kz — лоты всех площадок и банков. Фильтры по городу, району, цене и типу."),
        ("Проверьте документы", "Правоустанавливающие документы, обременения, кто прописан и проживает. "
                                "Закажите справку о зарегистрированных правах через eGov. Подскажем бесплатно, на что смотреть."),
        ("Подготовьте ЭЦП и деньги", "Для торгов на E-Qazyna и ЕЭТП Минюста нужна ЭЦП. "
                                     "Банки продают и напрямую — по заявке. Проверьте сроки оплаты по условиям лота."),
        ("Внесите гарантийный взнос", "Обычно до окончания приёма заявок. Если не выиграете — взнос возвращают."),
        ("Участвуйте и оформляйте", "Выигравший подписывает протокол и договор, оплачивает в срок "
                                    "и регистрирует право собственности."),
    ]
    save_post("04-kak-kupit", [cover_slide("Как купить квартиру с торгов: 5 шагов",
                                           "Сохраните — пригодится перед первой покупкой", "Инструкция")]
              + [text_slide(i, len(steps), t, b, dark=(i == len(steps))) for i, (t, b) in enumerate(steps, 1)]
              + [cta_slide("Остались вопросы?", ["Напишите в Telegram-бот @torgi_kz_bot — ответим",
                                                  "Каталог лотов — по ссылке в шапке профиля"])])
    captions.append(("04-kak-kupit", (
        "Как купить недвижимость с торгов: 5 шагов 🏠\n\n"
        + "\n".join(f"{i}️⃣ {t}" for i, (t, _) in enumerate(steps, 1))
        + f"\n\nПодробно — в карточках, листайте →\n\nСохраните пост 📌 и отправьте тому, кто ищет квартиру.\n{TG_LINE}\n\n"
        f"{HASHTAGS['common']} #какпокупатьнедвижимость #ипотекаказахстан")))

    # 5. виды имущества
    kinds = [
        ("Залог банка", "Заёмщик не вернул кредит — банк продаёт залог, часто напрямую, без аукциона. "
                        "Цену можно обсуждать."),
        ("Имущество банка", "Объект уже перешёл банку. Банк хочет быстро вернуть деньги — бывают скидки и рассрочка."),
        ("Арестованное имущество", "Продают судебные исполнители на ЕЭТП Минюста. Аукцион, нужна ЭЦП. "
                                   "Внимательно проверяйте проживающих."),
        ("Госимущество и банкроты", "E-Qazyna: приватизация, имущество банкротов и налоговых должников. "
                                    "Есть аукционы на понижение цены."),
    ]
    save_post("05-vidy-imushchestva", [cover_slide("Залог, арест, банкрот — в чём разница?",
                                                   "4 вида недвижимости с торгов и чем они отличаются", "Ликбез")]
              + [text_slide(i, len(kinds), t, b, dark=(i % 2 == 0)) for i, (t, b) in enumerate(kinds, 1)]
              + [cta_slide("Все виды — в одном каталоге", ["Фильтр «Вид продажи» на torgi.kz",
                                                           "Ссылка — в шапке профиля"])])
    captions.append(("05-vidy-imushchestva", (
        "Залог банка, арест, банкрот — в чём разница и что выгоднее? 🤔\n\n"
        + "\n".join(f"• {t} — {b}" for t, b in kinds)
        + f"\n\nВсе виды — в каталоге torgi.kz (ссылка в шапке профиля).\n{TG_LINE}\n\n{HASHTAGS['common']}")))

    md = ["# Подписи к постам\n"] + [f"## {name}\n\n```\n{text}\n```\n" for name, text in sorted(captions)]
    (OUT / "captions.md").write_text("\n".join(md), encoding="utf-8")
    print(f"готово: {OUT}")


if __name__ == "__main__":
    main()
