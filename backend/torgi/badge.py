"""Плашка «−N% к рынку» на главном фото поста в Telegram — как на карточках сайта.

Скидку не считаем заново: берём из выгрузки сайта (web/data/lots.json, поле market — torgi.top.market_badge),
чтобы в канале и на сайте были одни и те же цифры. Цвет — как на сайте: до 15% жёлтая, больше — красная.
"""

import io
import json
import logging
from pathlib import Path

import httpx
from PIL import Image, ImageDraw, ImageFont, ImageOps

log = logging.getLogger(__name__)

YELLOW, RED, INK, WHITE = "#facc15", "#e11d48", "#0f1115", "#ffffff"
FONTS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",  # Ubuntu (GitHub Actions)
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "C:/Windows/Fonts/segoeuib.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
]


def load_badges(path: Path) -> dict[int, dict]:
    """{id лота: {"pct", "over", "where"}} из выгрузки сайта (lots.json и cars.json рядом); нет файла — без плашек."""
    try:
        lots = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        log.info("плашки к рынку: нет %s — посты без плашек", path)
        return {}
    try:
        lots += json.loads(path.with_name("cars.json").read_text(encoding="utf-8"))["items"]
    except (OSError, ValueError, KeyError):
        pass
    return {x["id"]: x["market"] for x in lots if x.get("market")}


def label(badge: dict) -> str:
    return f"{'более ' if badge.get('over') else ''}−{badge['pct']}% к рынку"


def colors(badge: dict) -> tuple[str, str]:
    return (YELLOW, INK) if badge["pct"] <= 15 and not badge.get("over") else (RED, WHITE)


def _font(size: int) -> ImageFont.FreeTypeFont | None:
    for path in FONTS:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return None


def draw(img: Image.Image, badge: dict) -> Image.Image:
    """Плашка в левом верхнем углу: размер — от ширины фото, чтобы читалась и в превью канала."""
    img = ImageOps.exif_transpose(img).convert("RGB")
    w = img.width
    font = _font(max(18, round(w * 0.05)))
    if font is None:
        raise RuntimeError("нет шрифта для плашки")
    d = ImageDraw.Draw(img)
    text = label(badge)
    pad_x, pad_y, margin = round(font.size * 0.55), round(font.size * 0.3), round(w * 0.03)
    left, top, right, bottom = d.textbbox((0, 0), text, font=font)
    box = (margin, margin, margin + right - left + 2 * pad_x, margin + bottom - top + 2 * pad_y)
    bg, fg = colors(badge)
    d.rounded_rectangle(box, radius=round(font.size * 0.35), fill=bg)
    d.text((box[0] + pad_x - left, box[1] + pad_y - top), text, font=font, fill=fg)
    return img


def badged_photo(url: str, badge: dict, client: httpx.Client | None = None) -> bytes | None:
    """Главное фото лота с плашкой (JPEG) или None — тогда пост уходит с исходной ссылкой на фото."""
    try:
        res = (client or httpx).get(url, timeout=25, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0"})
        res.raise_for_status()
        img = draw(Image.open(io.BytesIO(res.content)), badge)
        if max(img.size) > 2560:  # лимит Telegram для фото — 10 МБ и сумма сторон до 10 000
            img.thumbnail((2560, 2560))
        out = io.BytesIO()
        img.save(out, "JPEG", quality=90)
        return out.getvalue()
    except Exception as exc:  # фото недоступно или битое — публикуем как раньше
        log.warning("плашка к рынку: фото %s не обработано (%s)", url, exc)
        return None
