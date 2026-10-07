"""Аватарки Telegram-канала и бота (640×640, Telegram обрезает в круг).

    uv run --with pillow python web/scripts/make_avatar.py
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parent.parent.parent / "docs" / "brand"
FONTS = Path("C:/Windows/Fonts")
BOLD = FONTS / "segoeuib.ttf"
BLACK = FONTS / "seguibl.ttf" if (FONTS / "seguibl.ttf").exists() else BOLD

INK, COBALT, WHITE, SOFT = "#0f1115", "#2450d6", "#ffffff", "#e8eefc"
S = 640


def canvas(bg: str) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGB", (S, S), bg)
    return img, ImageDraw.Draw(img)


def centered(d: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, y: float, fill: str, x: float = S / 2):
    d.text((x, y), text, font=font, fill=fill, anchor="mm")


def roof(d: ImageDraw.ImageDraw, cx: float, top: float, half: float, height: float, color: str, width: int):
    d.line([(cx - half, top + height), (cx, top), (cx + half, top + height)], fill=color, width=width, joint="curve")


def v1_roof_t():
    """Кобальт, белая крыша над буквой t — «торги + дом»."""
    img, d = canvas(COBALT)
    roof(d, S / 2, 150, 170, 120, WHITE, 42)
    centered(d, "t", ImageFont.truetype(str(BLACK), 330), 385, WHITE)
    return img


def v2_wordmark():
    """Почти чёрный, «torgi» белым и «.kz» кобальтом — как логотип сайта."""
    img, d = canvas(INK)
    f = ImageFont.truetype(str(BOLD), 150)
    w1 = d.textlength("torgi", font=f)
    w2 = d.textlength(".kz", font=f)
    x = (S - w1 - w2) / 2
    d.text((x, S / 2), "torgi", font=f, fill=WHITE, anchor="lm")
    d.text((x + w1, S / 2), ".kz", font=f, fill="#5b82f0", anchor="lm")
    return img


def v3_house_drop():
    """Почти чёрный, белый домик со стрелкой вниз кобальтом — «цена ниже рынка»."""
    img, d = canvas(INK)
    cx, base = S / 2, 470
    roof(d, cx, 140, 190, 140, WHITE, 40)
    d.line([(cx - 135, 250), (cx - 135, base), (cx + 135, base), (cx + 135, 250)], fill=WHITE, width=40, joint="curve")
    # стрелка вниз
    d.rectangle([cx - 22, 260, cx + 22, 370], fill=COBALT)
    d.polygon([(cx - 70, 360), (cx + 70, 360), (cx, 430)], fill=COBALT)
    return img


def v4_tk_badge():
    """Белый фон, кобальтовый круг с «tk» — читается даже в самом маленьком размере."""
    img, d = canvas(WHITE)
    d.ellipse([60, 60, S - 60, S - 60], fill=COBALT)
    roof(d, S / 2, 150, 120, 80, WHITE, 30)
    centered(d, "tk", ImageFont.truetype(str(BLACK), 250), 360, WHITE)
    return img


def _house(d: ImageDraw.ImageDraw, cx: float, top: float, scale: float):
    """Домик со стрелкой вниз; top — верх крыши, scale — размер относительно v3."""
    k = scale
    base = top + 330 * k
    roof(d, cx, top, 190 * k, 140 * k, WHITE, round(40 * k))
    d.line([(cx - 135 * k, top + 110 * k), (cx - 135 * k, base), (cx + 135 * k, base), (cx + 135 * k, top + 110 * k)],
           fill=WHITE, width=round(40 * k), joint="curve")
    d.rectangle([cx - 22 * k, top + 120 * k, cx + 22 * k, top + 230 * k], fill="#5b82f0")
    d.polygon([(cx - 70 * k, top + 220 * k), (cx + 70 * k, top + 220 * k), (cx, top + 290 * k)], fill="#5b82f0")


def _wordmark(d: ImageDraw.ImageDraw, y: float, size: int):
    f = ImageFont.truetype(str(BOLD), size)
    w1, w2 = d.textlength("torgi", font=f), d.textlength(".kz", font=f)
    x = (S - w1 - w2) / 2
    d.text((x, y), "torgi", font=f, fill=WHITE, anchor="lm")
    d.text((x + w1, y), ".kz", font=f, fill="#5b82f0", anchor="lm")


def v5_word_over_house():
    """Гибрид 2+3: «torgi.kz» над домиком со стрелкой."""
    img, d = canvas(INK)
    _wordmark(d, 165, 96)
    _house(d, S / 2, 268, 0.66)
    return img


def v6_house_over_word():
    """Гибрид 2+3: домик со стрелкой над «torgi.kz»."""
    img, d = canvas(INK)
    _house(d, S / 2, 112, 0.68)
    _wordmark(d, 470, 96)
    return img


VARIANTS = {"1-roof-t": v1_roof_t, "2-wordmark": v2_wordmark, "3-house-drop": v3_house_drop, "4-tk-badge": v4_tk_badge,
            "5-word-over-house": v5_word_over_house, "6-house-over-word": v6_house_over_word}


def preview(images: dict[str, Image.Image]) -> Image.Image:
    """Все варианты рядом: большой круг и маленький (как в списке чатов)."""
    pad, big, small = 40, 300, 56
    sheet = Image.new("RGB", (pad + len(images) * (big + pad), big + small + pad * 3), "#f6f7f9")
    d = ImageDraw.Draw(sheet)
    label = ImageFont.truetype(str(BOLD), 26)
    for i, (name, img) in enumerate(images.items()):
        x = pad + i * (big + pad)
        for size, y in ((big, pad), (small, pad * 2 + big)):
            mask = Image.new("L", (size, size), 0)
            ImageDraw.Draw(mask).ellipse([0, 0, size, size], fill=255)
            sheet.paste(img.resize((size, size), Image.LANCZOS), (x if size == big else x + 20, y), mask)
        d.text((x + small + 40, pad * 2 + big + small / 2), f"Вариант {name[0]}", font=label, fill=INK, anchor="lm")
    return sheet


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    images = {name: fn() for name, fn in VARIANTS.items()}
    for name, img in images.items():
        img.save(OUT / f"avatar-{name}.png", optimize=True)
    preview(images).save(OUT / "avatar-preview.png", optimize=True)
    print("ok", OUT)


def site_icons():
    """Значки сайта: домик со стрелкой на тёмном скруглённом квадрате (надпись в 16–32 px не читается)."""
    web = Path(__file__).resolve().parent.parent
    big = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(big)
    d.rounded_rectangle([0, 0, S - 1, S - 1], radius=140, fill=INK)
    _house(d, S / 2, 152, 1.0)
    big.save(web / "src" / "app" / "icon.png")                       # 640 — браузеры и Яндекс
    big.convert("RGB").resize((180, 180), Image.LANCZOS).save(web / "src" / "app" / "apple-icon.png")
    big.save(web / "src" / "app" / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)])


if __name__ == "__main__" and "--site" in __import__("sys").argv:
    site_icons()
    print("site icons ok")
