"""Автопостинг новых лотов в Telegram-канал через Bot API.

    uv run python -m torgi.cli post --dry-run          # показать посты, ничего не отправлять
    uv run python -m torgi.cli post --limit 10         # опубликовать до 10 новых лотов
    uv run python -m torgi.cli post --mark-all         # пометить всё текущее как опубликованное (старт канала)
"""

import html
import logging
import re
import time
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from torgi.config import settings
from torgi.models import ChannelPost, Lot, utcnow
from torgi.normalize import CATEGORIES, ORIGINS, SALE_TYPES

log = logging.getLogger(__name__)

KZ_TZ = timezone(timedelta(hours=5))  # с марта 2024 весь Казахстан в UTC+5
CAPTION_LIMIT = 1024

EMOJI = {"apartment": "🏢", "house": "🏡", "commercial": "🏬", "land": "🌾", "parking": "🚗", "industrial": "🏭",
         "other": "📦"}
SOURCE_TITLES = {"adilet": "ЕЭТП Минюста", "halyk": "Halyk Bank", "alatau": "Alatau City Bank", "forte": "ForteBank",
                 "bcc": "Bank CenterCredit", "freedom": "Freedom Bank"}
ORIGIN_TAGS = {"arrested": "арест", "bank_balance": "банк", "bank_pledge": "залог", "court": "суд"}
MONTHS = ["января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября",
          "ноября", "декабря"]


def _money(value: float) -> str:
    return f"{value:,.0f}".replace(",", " ") + " ₸"


def _num(value: float, digits: int = 1) -> str:
    return f"{value:.{digits}f}".rstrip("0").rstrip(".").replace(".", ",")


def _date(value: datetime) -> str:
    local = value.astimezone(KZ_TZ)
    text = f"{local.day} {MONTHS[local.month - 1]}"
    return text if (local.hour, local.minute) == (0, 0) else f"{text}, {local:%H:%M}"


def _hashtag(text: str) -> str:
    return "#" + re.sub(r"[^\wё]", "", text.replace("-", "_").replace(" ", "_"), flags=re.I)


def format_post(lot: Lot) -> str:
    esc = html.escape
    parts = [CATEGORIES.get(lot.category, "Объект")]
    if lot.rooms and lot.category in ("apartment", "house"):
        parts.append(f"{lot.rooms}-комн.")
    if lot.area_m2:
        parts.append(f"{_num(lot.area_m2)} м²")
    if lot.land_area_ha:
        parts.append(f"участок {_num(lot.land_area_ha, 4)} га")
    headline = ", ".join(parts) + (f" — {lot.city}" if lot.city else "")

    lines = [f"{EMOJI.get(lot.category, '📦')} <b>{esc(headline)}</b>", ""]
    price = f"💰 <b>{_money(lot.price)}</b>" if lot.price else "💰 Цена не указана"
    if lot.price_per_m2:
        price += f" ({_money(lot.price_per_m2)}/м²)"
    lines.append(price)
    if lot.address:
        address = lot.address if len(lot.address) <= 160 else lot.address[:157] + "…"
        lines.append(f"📍 {esc(address)}")
    kind = [SALE_TYPES.get(lot.sale_type or "", ""), ORIGINS.get(lot.origin, ""), SOURCE_TITLES.get(lot.source, "")]
    lines.append("🔨 " + " · ".join(esc(k) for k in kind if k))
    if lot.auction_start:
        when = f"🗓 Торги: {_date(lot.auction_start)}"
        if lot.auction_end:
            when += f" — {_date(lot.auction_end)}"
        lines.append(when)
    if lot.applications_deadline:
        lines.append(f"⏳ Заявки до {_date(lot.applications_deadline)}")
    if lot.deposit:
        lines.append(f"💳 Задаток: {_money(lot.deposit)}")

    lines += ["", f'<a href="{settings.site_url}/lots/{lot.id}">Подробнее на torgi.kz</a>']
    tags = [_hashtag(lot.city)] if lot.city else []
    tags += [_hashtag(CATEGORIES.get(lot.category, "").split(" ")[0].lower()), _hashtag(ORIGIN_TAGS.get(lot.origin, ""))]
    lines.append(" ".join(t for t in tags if len(t) > 1))
    return "\n".join(lines)[:CAPTION_LIMIT]


def pending_lots(session: Session, channel: str, limit: int, since_days: int) -> list[Lot]:
    posted = select(ChannelPost.lot_id).where(ChannelPost.channel == channel)
    stmt = (
        select(Lot)
        .where(Lot.status == "active", Lot.price.is_not(None), Lot.id.not_in(posted),
               Lot.first_seen_at >= utcnow() - timedelta(days=since_days))
        .order_by(Lot.first_seen_at, Lot.id)
    )
    # без флагов качества — ошибки ввода источника в канал не несём
    return [lot for lot in session.scalars(stmt) if not lot.flags][:limit]


class TelegramBot:
    def __init__(self, token: str):
        self.base = f"https://api.telegram.org/bot{token}"
        self.client = httpx.Client(timeout=30)

    def call(self, method: str, **params) -> dict:
        for _ in range(3):
            data = self.client.post(f"{self.base}/{method}", json=params).json()
            if data.get("ok"):
                return data["result"]
            retry = (data.get("parameters") or {}).get("retry_after")
            if not retry:
                raise RuntimeError(f"Telegram {method}: {data.get('description')}")
            time.sleep(retry + 1)
        raise RuntimeError(f"Telegram {method}: превышен лимит повторов")

    def post_lot(self, channel: str, lot: Lot, text: str) -> int:
        if lot.images:
            try:
                return self.call("sendPhoto", chat_id=channel, photo=lot.images[0], caption=text,
                                 parse_mode="HTML")["message_id"]
            except RuntimeError as exc:  # фото недоступно для Telegram — публикуем текстом
                log.warning("лот %s: фото не отправилось (%s), пост без фото", lot.id, exc)
        return self.call("sendMessage", chat_id=channel, text=text, parse_mode="HTML",
                         link_preview_options={"is_disabled": True})["message_id"]


def run(session: Session, limit: int = 10, since_days: int = 3, dry_run: bool = False, mark_all: bool = False) -> int:
    channel = settings.telegram_channel or "dry-run"
    if mark_all:
        lots = pending_lots(session, channel, limit=10**9, since_days=10**4)
        session.add_all(ChannelPost(lot_id=lot.id, channel=channel, message_id=None) for lot in lots)
        session.commit()
        log.info("помечено как опубликованное: %d", len(lots))
        return len(lots)

    if not dry_run and session.scalar(select(ChannelPost.id).where(ChannelPost.channel == channel).limit(1)) is None:
        # Первый запуск для канала: текущую базу не выгружаем, публикуем только новое
        log.info("канал %s: первый запуск — текущие лоты помечены опубликованными", channel)
        return run(session, mark_all=True)

    lots = pending_lots(session, channel, limit, since_days)
    if dry_run:
        for lot in lots:
            print(f"--- лот {lot.id} ({lot.source})\n{format_post(lot)}\n")
        return len(lots)
    if not settings.telegram_bot_token or not settings.telegram_channel:
        raise SystemExit("Задайте TORGI_TELEGRAM_BOT_TOKEN и TORGI_TELEGRAM_CHANNEL в backend/.env")

    bot = TelegramBot(settings.telegram_bot_token)
    for i, lot in enumerate(lots):
        if i:
            time.sleep(settings.telegram_post_delay)
        message_id = bot.post_lot(channel, lot, format_post(lot))
        session.add(ChannelPost(lot_id=lot.id, channel=channel, message_id=message_id))
        session.commit()
        log.info("опубликован лот %s → сообщение %s", lot.id, message_id)
    return len(lots)
