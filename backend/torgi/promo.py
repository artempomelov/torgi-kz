"""Рекламные слайды банков среди фото лота — первым фото их не ставим.

С сентября 2026 Halyk добавляет к своим квартирам первой картинкой слайд «Halyk Active — льготная программа
кредитования „Halyk Sale“». Обложка на сайте, главное фото поста в Telegram и плашка «−N% к рынку» должны быть
на фото самого объекта, поэтому слайд переносим в конец списка фото (решение владельца, 26.10.2026).

Слайд узнаём по перцептивному хэшу (dHash 8×8): у копий одной картинки отличаются не больше нескольких бит
из 64, у фотографий квартир — десятки. Проверяем только первое фото и только один раз: проверенная обложка —
в extra["cover_checked"], найденные слайды — в extra["promo_images"] (при обновлении лота они снова уходят в конец).
"""

import io
import logging

from PIL import Image
from sqlalchemy import select
from sqlalchemy.orm import Session

from torgi.models import Lot

log = logging.getLogger(__name__)

SLIDES = {
    # 26.10.2026: у 191 из 955 квартир Halyk первая картинка — этот слайд (расстояние 0–7);
    # ближайшее настоящее фото — 16 бит, так что порог 10 с запасом с обеих сторон
    0x6D29123276072723: "Halyk Active — «Halyk Sale»",
}
MAX_DISTANCE = 10  # из 64 бит
EXTRA_KEYS = ("cover_checked", "promo_images")  # служебные отметки в Lot.extra
SOURCES = {"halyk"}  # у кого слайд встречается первой картинкой
CHECK_PER_RUN = 1000  # первые фото за прогон: первый раз — все лоты Halyk (~20 мин с паузой 1 с), дальше — только новые


def dhash(img: Image.Image, size: int = 8) -> int:
    gray = img.convert("L").resize((size + 1, size), Image.LANCZOS)
    px = gray.tobytes()  # по байту на пиксель
    bits = 0
    for row in range(size):
        for col in range(size):
            left, right = px[row * (size + 1) + col], px[row * (size + 1) + col + 1]
            bits = (bits << 1) | (left > right)
    return bits


def is_slide(img: Image.Image) -> bool:
    h = dhash(img)
    return any(bin(h ^ ref).count("1") <= MAX_DISTANCE for ref in SLIDES)


def promo_last(images: list[str], promo: set[str]) -> list[str]:
    """Известные слайды — в конец, остальной порядок как у источника."""
    return [u for u in images if u not in promo] + [u for u in images if u in promo]


def _download(url: str, client) -> Image.Image | None:
    """client — HttpClient парсеров (с паузами между запросами к сайту) или httpx.Client."""
    try:
        res = client.request("GET", url, timeout=25, follow_redirects=True)
        res.raise_for_status()
        return Image.open(io.BytesIO(res.content))
    except Exception as exc:  # фото недоступно — проверим в следующий раз
        log.warning("обложка: фото %s не загружено (%s)", url, exc)
        return None


def check_cover(lot: Lot, client) -> bool:
    """Проверяет первое фото лота; рекламный слайд переносит в конец. True — порядок фото изменился."""
    extra = dict(lot.extra or {})
    promo = set(extra.get("promo_images") or [])
    images = promo_last(list(lot.images or []), promo)
    for _ in range(3):  # бывает несколько слайдов подряд
        if len(images) < 2 or images[0] == extra.get("cover_checked"):
            break
        img = _download(images[0], client)
        if img is None:
            break
        if not is_slide(img):
            extra["cover_checked"] = images[0]
            break
        promo.add(images[0])
        images = promo_last(images, promo)
    changed = images != list(lot.images or [])
    if promo:
        extra["promo_images"] = sorted(promo)
    if changed:
        lot.images = images
    if extra != (lot.extra or {}):
        lot.extra = extra
    return changed


def fix_covers(session: Session, source: str, client, limit: int = CHECK_PER_RUN) -> int:
    """Проверяет обложки активных лотов источника, которые ещё не проверены. Возвращает число исправленных."""
    if source not in SOURCES:
        return 0
    lots = session.scalars(select(Lot).where(Lot.source == source, Lot.status == "active")).all()
    todo = [x for x in lots if len(x.images or []) > 1 and (x.images[0] != (x.extra or {}).get("cover_checked"))]
    fixed = sum(check_cover(lot, client) for lot in todo[:limit])
    if todo:
        log.info("%s: проверено обложек %d из %d, слайд перенесён в конец у %d", source, min(len(todo), limit),
                 len(todo), fixed)
    return fixed
