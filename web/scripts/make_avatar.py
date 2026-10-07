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


VARIANTS = {"1-roof-t": v1_roof_t, "2-wordmark": v2_wordmark, "3-house-drop": v3_house_drop, "4-tk-badge": v4_tk_badge}


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
