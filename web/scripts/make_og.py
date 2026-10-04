"""Картинки превью ссылок (Open Graph, 1200×630) для WhatsApp, Telegram и соцсетей.

Используются для главной и для лотов без фото. Перегенерировать при смене бренда:
    uv run --with pillow python web/scripts/make_og.py
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parent.parent / "public" / "og"
FONTS = Path("C:/Windows/Fonts")
BOLD, REGULAR = FONTS / "segoeuib.ttf", FONTS / "segoeui.ttf"

INK, BRAND, BRAND_INK, ACCENT, MUTED = "#0f1115", "#2450d6", "#2450d6", "#0f1115", "#5b6270"

CARDS = {
    "default": ("Все торги недвижимостью\nКазахстана в одном месте", "Арест · залоги банков · госимущество · банкроты"),
    "apartment": ("Квартира\nс торгов", "Аукционы, залоги и имущество банков"),
    "house": ("Дом\nс торгов", "Аукционы, залоги и имущество банков"),
    "commercial": ("Коммерческая\nнедвижимость с торгов", "Офисы, магазины, склады, здания"),
    "land": ("Земельный участок\nс торгов", "Аукционы, госимущество и залоги"),
    "parking": ("Паркинг или гараж\nс торгов", "Аукционы, госимущество и залоги"),
    "industrial": ("Промбаза\nс торгов", "Производство, склады, комплексы"),
    "other": ("Объект\nс торгов", "Аукционы, залоги и имущество банков"),
}


def card(title: str, subtitle: str) -> Image.Image:
    img = Image.new("RGB", (1200, 630), "#ffffff")
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, 1200, 14], fill=BRAND)
    d.rectangle([0, 616, 1200, 630], fill=ACCENT)
    logo = ImageFont.truetype(str(BOLD), 64)
    d.text((80, 70), "torgi", font=logo, fill=INK)
    d.text((80 + d.textlength("torgi", font=logo), 70), ".kz", font=logo, fill=BRAND)
    d.multiline_text((80, 210), title, font=ImageFont.truetype(str(BOLD), 76), fill=INK, spacing=10)
    d.text((80, 470), subtitle, font=ImageFont.truetype(str(REGULAR), 38), fill=MUTED)
    d.text((80, 535), "Новые лоты каждый день", font=ImageFont.truetype(str(BOLD), 34), fill=BRAND_INK)
    return img


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    for name, (title, subtitle) in CARDS.items():
        card(title, subtitle).save(OUT / f"{name}.png", optimize=True)
        print("ok", name)
