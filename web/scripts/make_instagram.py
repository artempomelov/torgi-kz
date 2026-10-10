"""Instagram torgi.kz: оформление профиля и готовые посты-карусели из раздела «ТОП».

    uv run --with pillow --with httpx python web/scripts/make_instagram.py

Данные — web/data (выгрузка `torgi.cli export --market …`). Результат — marketing/instagram/<дата>/:
  profile/      аватар, обложки «Актуального», тексты профиля (profile.md)
  posts/NN-*/   слайды 1080×1350 (формат 4:5) — загружать по порядку как карусель
  captions.md   подписи с хештегами к каждому посту
Папка marketing/ в git не попадает: на слайдах фото с сайтов продавцов.
"""

import io
import json
from datetime import date
from pathlib import Path

import httpx
from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "web" / "data"
OUT = ROOT / "marketing" / "instagram" / date.today().isoformat()

FONTS = Path("C:/Windows/Fonts")
REG, BOLD = FONTS / "segoeui.ttf", FONTS / "segoeuib.ttf"
BLACK = FONTS / "seguibl.ttf" if (FONTS / "seguibl.ttf").exists() else BOLD

INK, COBALT, WHITE, SOFT, MUTED = "#0f1115", "#2450d6", "#ffffff", "#e8eefc", "#5b6b73"
GREEN, LIGHT = "#1f9d55", "#f4f6fa"
W, H = 1080, 1350

ORIGIN = {
    "arrested": "Арестованное имущество", "bank_balance": "Имущество банка", "bank_pledge": "Залог банка",
    "court": "Судебная реализация", "state": "Госимущество", "bankrupt": "Имущество банкрота",
    "tax_debtor": "Имущество налогового должника", "confiscated": "Конфискат",
}
SALE = {"auction": "аукцион", "auction_down": "аукцион на понижение", "direct": "прямая продажа", "tender": "тендер"}


def font(path: Path, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(path), size)


def mln(v: float) -> str:
    return f"{v / 1e6:.1f}".replace(".", ",").replace(",0", "") + " млн ₸"


def wrap(d: ImageDraw.ImageDraw, text: str, f: ImageFont.FreeTypeFont, width: int) -> list[str]:
    lines, line = [], ""
    for word in text.split():
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


def pill(d, xy, text, f, bg, fg, pad=(26, 12)):
    x, y = xy
    tw = d.textlength(text, font=f)
    d.rounded_rectangle([x, y, x + tw + 2 * pad[0], y + f.size + 2 * pad[1]], radius=(f.size + 2 * pad[1]) // 2, fill=bg)
    d.text((x + pad[0], y + pad[1] - f.size * 0.12), text, font=f, fill=fg)
    return x + tw + 2 * pad[0]


def fetch_photo(url: str | None) -> Image.Image | None:
    if not url:
        return None
    try:
        res = httpx.get(url, timeout=20, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0"})
        res.raise_for_status()
        return Image.open(io.BytesIO(res.content)).convert("RGB")
    except Exception:
        return None


# --- слайды -----------------------------------------------------------------------------------------

def cover_slide(title: str, subtitle: str, kicker: str) -> Image.Image:
    img = Image.new("RGB", (W, H), INK)
    d = ImageDraw.Draw(img)
    logo(d, 80, 80)
    house(d, W // 2, 210, 0.95, WHITE)
    y = 640
    pill(d, (80, y), kicker, font(BOLD, 34), COBALT, WHITE)
    y = text_block(d, (80, y + 95), title, font(BLACK, 84), WHITE, W - 160, 1.1)
    text_block(d, (80, y + 25), subtitle, font(REG, 38), "#b8c2d6", W - 160)
    d.text((W - 80, H - 80), "листайте →", font=font(BOLD, 36), fill="#8aa6ff", anchor="rs")
    return img


def lot_slide(lot: dict, top: dict, rank: int) -> Image.Image:
    img = Image.new("RGB", (W, H), WHITE)
    d = ImageDraw.Draw(img)
    photo_h = 760
    images = lot.get("images") or [None]
    # фото продавца иногда с людьми или документами — номер другого фото можно задать в PHOTO_INDEX
    photo = fetch_photo(images[min(PHOTO_INDEX.get(lot["id"], 0), len(images) - 1)])
    if photo:
        img.paste(ImageOps.fit(photo, (W, photo_h), Image.LANCZOS), (0, 0))
        # затемнение сверху — чтобы читался номер
        grad = Image.linear_gradient("L").rotate(180).resize((W, 200))
        img.paste(Image.new("RGB", (W, 200), "#000000"), (0, 0), grad.point(lambda v: int(v * 0.45)))
    else:
        d.rectangle([0, 0, W, photo_h], fill=SOFT)
        house(d, W // 2, 190, 1.1, COBALT, arrow=None)
        d.text((W // 2, 650), "фото нет у продавца", font=font(REG, 34), fill=MUTED, anchor="mm")
    d = ImageDraw.Draw(img)
    # номер места
    d.ellipse([50, 50, 150, 150], fill=GREEN)
    d.text((100, 100), str(rank), font=font(BLACK, 56), fill=WHITE, anchor="mm")
    pill(d, (50, photo_h - 100), f"−{top['discount_pct']}% к рынку", font(BLACK, 44), GREEN, WHITE)

    y = photo_h + 40
    title, _, place = lot["headline"].partition(" — ")
    d.text((70, y), title, font=font(BOLD, 46), fill=INK)
    y += 66
    d.text((70, y), place, font=font(REG, 36), fill=MUTED)
    y += 80
    d.text((70, y), mln(lot["price"]), font=font(BLACK, 88), fill=INK)
    x = 70 + d.textlength(mln(lot["price"]), font=font(BLACK, 88)) + 30
    market = f"рынок ≈ {mln(top['estimate'])}"
    mf = font(REG, 38)
    d.text((x, y + 38), market, font=mf, fill=MUTED)
    y += 130
    tags = [ORIGIN.get(lot["origin"], lot["origin"])]
    if lot.get("sale_type") in SALE:
        tags.append(SALE[lot["sale_type"]])
    pill(d, (70, y), " · ".join(tags), font(BOLD, 30), LIGHT, COBALT)
    d.text((W - 70, H - 70), "torgi.kz/top", font=font(BOLD, 32), fill=COBALT, anchor="rs")
    d.text((70, H - 70), "оценка torgi.kz по объявлениям", font=font(REG, 26), fill=MUTED, anchor="ls")
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


# лот → номер фото (с нуля), если первое не подходит для соцсетей
PHOTO_INDEX: dict[int, int] = {1704: 1}

HASHTAGS = {
    "Алматы": "#недвижимостьалматы #квартираалматы #алматы #купитьквартирувалматы",
    "Астана": "#недвижимостьастана #квартираастана #астана #купитьквартирувастане",
    "common": "#торги #недвижимостьказахстан #залоговоеимущество #аукцион #инвестициивнедвижимость "
              "#квартиранижерынка #torgikz",
}


def top_post(section: dict, full: dict, city: str, folder: str, kicker: str) -> str:
    items = [x for x in section["items"] if full.get(x["id"], {}).get("price")]
    # в соцсетях без фото карточка не работает: сначала лоты с фото, без фото — только если не хватает
    items = ([x for x in items if full[x["id"]].get("images")] + [x for x in items if not full[x["id"]].get("images")])[:5]
    items.sort(key=lambda x: -x["discount_pct"])
    best = items[0]["discount_pct"]
    slides = [cover_slide(f"ТОП-5 квартир {city} ниже рынка",
                          f"Торги и залоги банков: цены на {items[-1]['discount_pct']}–{best}% ниже объявлений "
                          f"о продаже похожих квартир", kicker)]
    slides += [lot_slide(full[x["id"]], x, i) for i, x in enumerate(items, 1)]
    slides.append(cta_slide("Ещё 3 000+ объектов с торгов", [
        "Полный ТОП-10 и карточки лотов — на torgi.kz/top",
        "Новые лоты каждый день — в Telegram @torgi_kz_news",
        "Бесплатно проверим документы по любому лоту",
    ]))
    save_post(folder, slides)
    lines = "\n".join(f"{i}. {full[x['id']]['headline']} — {mln(full[x['id']]['price'])} "
                      f"(рынок ≈ {mln(x['estimate'])}, −{x['discount_pct']}%)" for i, x in enumerate(items, 1))
    tag = HASHTAGS["Алматы"] if "Алмат" in city else HASHTAGS["Астана"] if "Астан" in city else ""
    return (f"ТОП-5 квартир {city} с торгов — ниже рынка до {best}% 🔥\n\n{lines}\n\n"
            "Как считаем: сравниваем цену лота с объявлениями о продаже похожих квартир в том же городе и районе. "
            "Это ориентир, а не отчёт об оценке — перед покупкой проверяйте документы и состояние объекта.\n\n"
            "Сохраните, чтобы не потерять 📌 Полный ТОП-10 — по ссылке в шапке профиля.\n\n"
            f"{tag} {HASHTAGS['common']}")


def main():
    # папки не удаляем (OneDrive держит их во время синхронизации) — только старые слайды
    for old in OUT.rglob("*.jpg") if OUT.exists() else []:
        old.unlink()
    top = json.loads((DATA / "top.json").read_text(encoding="utf-8"))
    full = {lot["id"]: lot for lot in json.loads((DATA / "lots-full.json").read_text(encoding="utf-8"))}
    meta = json.loads((DATA / "meta.json").read_text(encoding="utf-8"))
    sections = {s["slug"]: s for s in top["sections"]}
    total = f"{meta['total']:,}".replace(",", " ")

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
                   "Бесплатно проверим документы и обременения по лоту, подскажем, как участвовать в торгах. "
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
        "✅ Бесплатная проверка документов по лоту\n\n"
        "Подписывайтесь — каждую неделю публикуем ТОП объектов ниже рынка. Каталог — по ссылке в шапке профиля.\n\n"
        f"{HASHTAGS['common']} #недвижимость #казахстан")))

    # 2–3. ТОП Алматы и Астаны
    if "kvartiry-almaty" in sections:
        captions.append(("02-top-almaty", top_post(sections["kvartiry-almaty"], full, "Алматы", "02-top-almaty",
                                                     "ТОП недели · Алматы")))
    if "kvartiry-astana" in sections:
        captions.append(("03-top-astana", top_post(sections["kvartiry-astana"], full, "Астаны", "03-top-astana",
                                                     "ТОП недели · Астана")))

    # 4. как купить
    steps = [
        ("Найдите объект", "В каталоге torgi.kz — лоты всех площадок и банков. Фильтры по городу, району, цене и типу."),
        ("Проверьте документы", "Правоустанавливающие документы, обременения, кто прописан и проживает. "
                                "Закажите справку о зарегистрированных правах через eGov. Мы проверим бесплатно."),
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
        + "\n\nПодробно — в карточках, листайте →\n\nСохраните пост 📌 и отправьте тому, кто ищет квартиру.\n\n"
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
        + f"\n\nВсе виды — в каталоге torgi.kz (ссылка в шапке профиля).\n\n{HASHTAGS['common']}")))

    # 6. до 30 млн
    if "kvartiry-do-30-mln" in sections:
        captions.append(("06-top-do-30-mln", top_post(sections["kvartiry-do-30-mln"], full, "до 30 млн ₸",
                                                        "06-top-do-30-mln", "ТОП · бюджет до 30 млн")))

    md = ["# Подписи к постам\n"] + [f"## {name}\n\n```\n{text}\n```\n" for name, text in captions]
    (OUT / "captions.md").write_text("\n".join(md), encoding="utf-8")
    print(f"готово: {OUT}")


if __name__ == "__main__":
    main()
