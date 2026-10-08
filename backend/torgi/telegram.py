"""Автопостинг новых лотов в Telegram-канал через Bot API.

    uv run python -m torgi.cli post --dry-run          # показать посты, ничего не отправлять
    uv run python -m torgi.cli post --limit 10         # опубликовать до 10 новых лотов
    uv run python -m torgi.cli post --mark-all         # пометить всё текущее как опубликованное (старт канала)
"""

import html
import json
import logging
import re
import time
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from torgi.config import settings
from torgi.export import district
from torgi.models import ChannelPost, Lot, utcnow
from torgi.normalize import CATEGORIES, ORIGINS, SALE_TYPES, canonical_district, real_price_history

log = logging.getLogger(__name__)

KZ_TZ = timezone(timedelta(hours=5))  # с марта 2024 весь Казахстан в UTC+5
CAPTION_LIMIT = 1024

EMOJI = {"apartment": "🏢", "house": "🏡", "commercial": "🏬", "land": "🌾", "parking": "🚗", "industrial": "🏭",
         "other": "📦"}
SOURCE_TITLES = {"adilet": "ЕЭТП Минюста", "sauda": "E-Qazyna", "halyk": "Halyk Bank", "alatau": "Alatau City Bank",
                 "forte": "ForteBank", "bcc": "Bank CenterCredit", "freedom": "Freedom Bank",
                 "eurasian": "Евразийский банк", "nurbank": "Нурбанк", "bereke": "Bereke Bank", "rbk": "Bank RBK"}
ORIGIN_TAGS = {"arrested": "арест", "bank_balance": "банк", "bank_pledge": "залог", "court": "суд",
               "state": "госимущество", "bankrupt": "банкрот", "tax_debtor": "налоговый_должник",
               "confiscated": "конфискат"}
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


# --- выгода: снижение цены и сравнение с медианой по городу ----------------------------------

PPM_CATEGORIES = ("apartment", "commercial")


def market_medians(session: Session) -> dict[tuple[str, str], float]:
    """Медиана цены за м² по (категория, город) среди активных лотов — для «ниже рынка на N%»."""
    values: dict[tuple[str, str], list[float]] = {}
    rows = session.execute(select(Lot.category, Lot.city, Lot.region, Lot.price_per_m2).where(
        Lot.status == "active", Lot.price_per_m2.is_not(None), Lot.category.in_(PPM_CATEGORIES)))
    for category, city, region, ppm in rows:
        values.setdefault((category, city or region or ""), []).append(ppm)
    return {k: sorted(v)[len(v) // 2] for k, v in values.items() if len(v) >= 5}


def benefit_lines(lot: Lot, medians: dict | None = None) -> list[str]:
    lines = []
    prices = [p.price for p in real_price_history(lot.price_history)]
    if lot.price and prices and prices[0] > lot.price:
        drop = prices[0] - lot.price
        lines.append(f"📉 <b>Цена снижена на {drop / prices[0] * 100:.0f}%</b> — выгода {_money(drop)}")
    if lot.min_price and lot.price and lot.min_price < lot.price:
        lines.append(f"⬇️ Аукцион на понижение: цена может опуститься до {_money(lot.min_price)} "
                     f"(−{(1 - lot.min_price / lot.price) * 100:.0f}%)")
    median = (medians or {}).get((lot.category, lot.city or lot.region or ""))
    if median and lot.price_per_m2 and lot.price_per_m2 < median * 0.9:
        lines.append(f"🔥 За м² на {(1 - lot.price_per_m2 / median) * 100:.0f}% дешевле медианы по городу")
    return lines


def utm(channel: str | None) -> str:
    """Метки для Метрики: переходы из Telegram не передают источник и иначе считаются прямыми заходами."""
    campaign = (channel or "channel").lstrip("@")
    # «&» внутри HTML-разметки Telegram — как &amp;
    return f"?utm_source=telegram&amp;utm_medium=channel&amp;utm_campaign={campaign}"


def format_post(lot: Lot, medians: dict | None = None, footer: str = "", channel: str | None = None) -> str:
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
    lines += benefit_lines(lot, medians)
    # точный адрес — только на сайте после входа; в канале — город и район
    area = canonical_district(district(lot.address), lot.city or lot.region)
    place = ", ".join(p for p in (lot.city or lot.region, area) if p)
    if place:
        lines.append(f"📍 {esc(place)}")
    # источник (площадку или банк) в канале не называем — он открывается на сайте после входа
    kind = [SALE_TYPES.get(lot.sale_type or "", ""), ORIGINS.get(lot.origin, "")]
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

    lines += ["", f'<a href="{settings.site_url}/lots/{lot.id}/{utm(channel or settings.telegram_channel)}">Подробнее на torgi.kz</a>']
    tags = [_hashtag(lot.city)] if lot.city else []
    tags += [_hashtag(CATEGORIES.get(lot.category, "").split(" ")[0].lower()), _hashtag(ORIGIN_TAGS.get(lot.origin, ""))]
    lines.append(" ".join(t for t in tags if len(t) > 1))
    if footer:
        lines += ["", footer]
    return "\n".join(lines)[:CAPTION_LIMIT]


# Подпись под постом: основной канал зовёт в бота подписок, дополнительные — в основной канал
MAIN_FOOTER = '🔔 Новые объекты по вашему поиску присылает <a href="https://t.me/torgi_kz_bot">@torgi_kz_bot</a>'
HUB_FOOTER = '📢 Все торги Казахстана — <a href="https://t.me/{hub}">@{hub}</a>'


def matches_channel(lot: Lot, rule: dict | None) -> bool:
    """Фильтр дополнительного канала: {"region": "Алматы"}, {"category": ["commercial", "industrial"]}."""
    if not rule:
        return True
    regions = rule.get("region")
    if regions and lot.region not in ([regions] if isinstance(regions, str) else regions):
        return False
    categories = rule.get("category")
    if categories and lot.category not in ([categories] if isinstance(categories, str) else categories):
        return False
    return True


def pending_lots(session: Session, channel: str, limit: int, since_days: int, rule: dict | None = None) -> list[Lot]:
    posted = select(ChannelPost.lot_id).where(ChannelPost.channel == channel)
    stmt = (
        select(Lot)
        .where(Lot.status == "active", Lot.price.is_not(None), Lot.id.not_in(posted),
               Lot.first_seen_at >= utcnow() - timedelta(days=since_days))
        .order_by(Lot.first_seen_at.desc(), Lot.id.desc())
    )
    # без флагов качества — ошибки ввода источника в канал не несём; с фото — в первую очередь
    lots = [lot for lot in session.scalars(stmt) if not lot.flags and matches_channel(lot, rule)]
    lots.sort(key=lambda lot: not lot.images)
    return lots[:limit]


def posted_today(session: Session, channel: str, now: datetime | None = None) -> int:
    start = (now or utcnow()).astimezone(KZ_TZ).replace(hour=0, minute=0, second=0, microsecond=0)
    return session.scalar(select(func.count()).select_from(ChannelPost).where(
        ChannelPost.channel == channel, ChannelPost.message_id.is_not(None), ChannelPost.posted_at >= start)) or 0


class TelegramBot:
    def __init__(self, token: str):
        # при вставке в секрет легко захватить пробел, перенос строки или кавычки
        token = token.strip().strip("'\"").strip()
        token = token.removeprefix("bot") if re.match(r"bot\d+:", token) else token
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
        if len(lot.images) >= 2:
            # альбом из 3–5 фото, подпись — у первого
            media = [{"type": "photo", "media": url} for url in lot.images[:5]]
            media[0].update(caption=text, parse_mode="HTML")
            try:
                return self.call("sendMediaGroup", chat_id=channel, media=media)[0]["message_id"]
            except RuntimeError as exc:
                log.warning("лот %s: альбом не отправился (%s), пробуем одно фото", lot.id, exc)
        if lot.images:
            try:
                return self.call("sendPhoto", chat_id=channel, photo=lot.images[0], caption=text,
                                 parse_mode="HTML")["message_id"]
            except RuntimeError as exc:  # фото недоступно для Telegram — публикуем текстом
                log.warning("лот %s: фото не отправилось (%s), пост без фото", lot.id, exc)
        return self.call("sendMessage", chat_id=channel, text=text, parse_mode="HTML",
                         link_preview_options={"is_disabled": True})["message_id"]


def refresh(session: Session) -> int:
    """Переписать уже опубликованные посты по текущему шаблону (например, после смены формата)."""
    if not settings.telegram_bot_token or not settings.telegram_channel:
        raise SystemExit("Задайте TORGI_TELEGRAM_BOT_TOKEN и TORGI_TELEGRAM_CHANNEL")
    bot = TelegramBot(settings.telegram_bot_token)
    rules = {name: rule for name, rule, _ in channels()}
    hub = (settings.telegram_channel or "").lstrip("@")
    medians = market_medians(session)
    posts = session.scalars(select(ChannelPost).where(
        ChannelPost.channel.in_(list(rules)), ChannelPost.message_id.is_not(None))).all()
    edited = 0
    for post in posts:
        lot = session.get(Lot, post.lot_id)
        if lot is None:
            continue
        footer = MAIN_FOOTER if rules.get(post.channel) is None else HUB_FOOTER.format(hub=hub)
        text = format_post(lot, medians, footer, post.channel)
        common = {"chat_id": post.channel, "message_id": post.message_id, "parse_mode": "HTML"}
        for method, extra in (("editMessageCaption", {"caption": text}),
                              ("editMessageText", {"text": text, "link_preview_options": {"is_disabled": True}})):
            try:
                bot.call(method, **common, **extra)
                edited += 1
                break
            except RuntimeError as exc:
                if "not modified" in str(exc):
                    break
                # пост без фото — у него нет подписи, правим текст; иначе пробуем следующий способ
        time.sleep(1)
    log.info("переписано постов: %d из %d", edited, len(posts))
    return edited


def channels() -> list[tuple[str, dict | None, int]]:
    """Основной канал (все лоты) и дополнительные — региональные и тематические."""
    out: list[tuple[str, dict | None, int]] = []
    if settings.telegram_channel:
        out.append((settings.telegram_channel, None, settings.telegram_daily_limit))
    if settings.telegram_channels.strip():
        for name, rule in json.loads(settings.telegram_channels).items():
            out.append((name, rule or None, settings.telegram_channel_daily_limit))
    return out


def run_channel(session: Session, bot: "TelegramBot | None", channel: str, rule: dict | None, daily: int,
                limit: int, since_days: int, medians: dict, dry_run: bool) -> int:
    if not dry_run and session.scalar(select(ChannelPost.id).where(ChannelPost.channel == channel).limit(1)) is None:
        # Первый запуск для канала: текущую базу не выгружаем, публикуем только новое
        lots = pending_lots(session, channel, 10**9, 10**4, rule)
        session.add_all(ChannelPost(lot_id=lot.id, channel=channel, message_id=None) for lot in lots)
        session.commit()
        log.info("канал %s: первый запуск — %d текущих лотов помечены опубликованными", channel, len(lots))
        return 0
    if not dry_run:
        limit = min(limit, daily - posted_today(session, channel))
        if limit <= 0:
            log.info("канал %s: дневной лимит (%s) исчерпан", channel, daily)
            return 0
    lots = pending_lots(session, channel, limit, since_days, rule)
    hub = (settings.telegram_channel or "").lstrip("@")
    footer = MAIN_FOOTER if rule is None else HUB_FOOTER.format(hub=hub) if hub else ""
    for i, lot in enumerate(lots):
        text = format_post(lot, medians, footer, channel)
        if dry_run:
            print(f"--- {channel}: лот {lot.id} ({lot.source})\n{text}\n")
            continue
        if i:
            time.sleep(settings.telegram_post_delay)
        message_id = bot.post_lot(channel, lot, text)
        session.add(ChannelPost(lot_id=lot.id, channel=channel, message_id=message_id))
        session.commit()
        log.info("канал %s: опубликован лот %s → сообщение %s", channel, lot.id, message_id)
    return len(lots)


def run(session: Session, limit: int = 5, since_days: int = 3, dry_run: bool = False, mark_all: bool = False) -> int:
    targets = channels() or [("dry-run", None, settings.telegram_daily_limit)]
    if mark_all:
        for channel, rule, _ in targets:
            lots = pending_lots(session, channel, 10**9, 10**4, rule)
            session.add_all(ChannelPost(lot_id=lot.id, channel=channel, message_id=None) for lot in lots)
            session.commit()
            log.info("канал %s: помечено как опубликованное: %d", channel, len(lots))
        return 0
    if not dry_run:
        if not settings.telegram_bot_token or not settings.telegram_channel:
            raise SystemExit("Задайте TORGI_TELEGRAM_BOT_TOKEN и TORGI_TELEGRAM_CHANNEL в backend/.env")
        hour = utcnow().astimezone(KZ_TZ).hour
        start, end = settings.telegram_hours
        if not start <= hour < end:
            log.info("вне часов публикации (%s–%s по Алматы)", start, end)
            return 0
    bot = None if dry_run else TelegramBot(settings.telegram_bot_token)
    medians = market_medians(session)
    total = 0
    for channel, rule, daily in targets:
        try:
            total += run_channel(session, bot, channel, rule, daily, limit, since_days, medians, dry_run)
        except RuntimeError:
            log.exception("канал %s: ошибка публикации", channel)
    return total
