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
from pathlib import Path

import httpx
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from torgi.badge import badged_photo, load_badges
from torgi.badge import label as badge_label
from torgi.config import settings
from torgi.export import lot_district
from torgi.models import ChannelPost, Lot, utcnow
from torgi.normalize import CATEGORIES, ORIGINS, SALE_TYPES, real_price_history

log = logging.getLogger(__name__)

KZ_TZ = timezone(timedelta(hours=5))  # с марта 2024 весь Казахстан в UTC+5
CAPTION_LIMIT = 1024

EMOJI = {"apartment": "🏢", "house": "🏡", "commercial": "🏬", "land": "🌾", "parking": "🚗", "industrial": "🏭",
         "other": "📦"}
SOURCE_TITLES = {"adilet": "ЕЭТП Минюста", "sauda": "E-Qazyna", "halyk": "Halyk Bank", "alatau": "Alatau City Bank",
                 "forte": "ForteBank", "bcc": "Bank CenterCredit", "freedom": "Freedom Bank",
                 "eurasian": "Евразийский банк", "nurbank": "Нурбанк", "bereke": "Bereke Bank", "rbk": "Bank RBK", "krisha": "Крыша"}
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


# --- выгода: снижение цены и скидка к рынку ----------------------------------------------------

def benefit_lines(lot: Lot, badge: dict | None = None) -> list[str]:
    """Выгода: снижение цены, нижняя цена аукциона и скидка к рынку — только «Цена на N% ниже рынка», без рыночных
    цен и пояснений (решение владельца сайта от 23.10.2026); badge — плашка сайта «−N% к рынку»."""
    lines = []
    prices = [p.price for p in real_price_history(lot.price_history)]
    if lot.price and prices and prices[0] > lot.price:
        drop = prices[0] - lot.price
        lines.append(f"📉 <b>Цена снижена на {drop / prices[0] * 100:.0f}%</b> — выгода {_money(drop)}")
    if lot.min_price and lot.price and lot.min_price < lot.price:
        lines.append(f"⬇️ Аукцион на понижение: цена может опуститься до {_money(lot.min_price)} "
                     f"(−{(1 - lot.min_price / lot.price) * 100:.0f}%)")
    if badge:
        how = f"более чем на {badge['pct']}%" if badge.get("over") else f"на {badge['pct']}%"
        lines.append(f"🔥 Цена {how} ниже рынка")
    return lines


def utm(channel: str | None) -> str:
    """Метки для Метрики: переходы из Telegram не передают источник и иначе считаются прямыми заходами."""
    campaign = (channel or "channel").lstrip("@")
    # «&» внутри HTML-разметки Telegram — как &amp;
    return f"?utm_source=telegram&amp;utm_medium=channel&amp;utm_campaign={campaign}"


def format_vehicle_post(lot: Lot, footer: str = "", channel: str | None = None, badge: dict | None = None) -> str:
    """Пост о машине: марка, модель, год, характеристики, цена, город, вид продажи и дата торгов."""
    esc, extra = html.escape, lot.extra or {}
    specs = [f"{extra['mileage_km']:,} км".replace(",", " ") if extra.get("mileage_km") else None,
             extra.get("engine"), extra.get("transmission"), extra.get("body"), extra.get("color")]
    lines = [f"🚗 <b>{esc(lot.title)}</b>" + (f" — {esc(lot.city)}" if lot.city else ""), ""]
    lines.append(f"💰 <b>{_money(lot.price)}</b>" if lot.price else "💰 Цена не указана")
    lines += benefit_lines(lot, badge=badge)
    if any(specs):
        lines.append("⚙️ " + esc(" · ".join(s for s in specs if s)))
    if not lot.city and lot.region:
        lines.append(f"📍 {esc(lot.region)}")
    kind = [SALE_TYPES.get(lot.sale_type or "", ""), ORIGINS.get(lot.origin, "")]
    lines.append("🔨 " + " · ".join(esc(k) for k in kind if k))
    if extra.get("note"):
        lines.append(f"⚠️ {esc(extra['note'].capitalize())}")
    if lot.auction_start or lot.auction_end:
        lines.append(f"🗓 Торги: {_date(lot.auction_start or lot.auction_end)}")
    if lot.applications_deadline:
        lines.append(f"⏳ Заявки до {_date(lot.applications_deadline)}")
    lines += ["", f'<a href="{settings.site_url}/avto/{lot.id}/{utm(channel)}">Подробнее на torgi.kz</a>']
    tags = [_hashtag(lot.city)] if lot.city else []
    tags += [_hashtag(extra.get("brand") or ""), _hashtag(ORIGIN_TAGS.get(lot.origin, ""))]
    lines.append(" ".join(t for t in tags if len(t) > 1))
    if footer:
        lines += ["", footer]
    return "\n".join(lines)[:CAPTION_LIMIT]


def format_post(lot: Lot, footer: str = "", channel: str | None = None, badge: dict | None = None) -> str:
    if lot.category == "vehicle":
        return format_vehicle_post(lot, footer, channel, badge)
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
    lines += benefit_lines(lot, badge)
    # точный адрес — только на сайте после входа; в канале — город и район
    area = lot_district(lot.address, lot.city or lot.region, lot.title, lot.description)
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
    """Фильтр дополнительного канала: {"region": "Алматы"}, {"category": ["commercial", "industrial"]}.
    Машины попадают только в канал, где категория «vehicle» указана явно (в основной — по MAIN_MIX)."""
    categories = (rule or {}).get("category")
    categories = [categories] if isinstance(categories, str) else categories or []
    if lot.category == "vehicle" and "vehicle" not in categories:
        return False
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


VEHICLE = "vehicle"


def _big_city(lot: Lot) -> bool:
    return bool({lot.region, lot.city} & {"Алматы", "Астана"})


# машина для основного канала — легковая, не старше 10 лет, без обременений, повреждений и долей, с 3+ фото
CAR_PROBLEM_RE = re.compile(r"обремен|неисправ|ключ|аварийн|дол[ия]|страхов", re.I)


def _presentable_car(lot: Lot) -> bool:
    extra = lot.extra or {}
    return (lot.category == VEHICLE and extra.get("vehicle_type") == "car" and len(lot.images or []) >= 3
            and (extra.get("year") or 0) >= utcnow().year - 10 and not CAR_PROBLEM_RE.search(extra.get("note") or ""))


# Основной канал — не все новые лоты подряд (на 80% это паркоместа и земля), а смесь по долям (решение владельца
# сайта от 21.10.2026): из 6 постов в день 4–5 квартир Алматы и Астаны, остальное — машина и коммерческое помещение
# (по всему Казахстану) или квартира в регионах. Квартиры Алматы и Астаны дублируются с городскими каналами — так
# и задумано. Дома, земля, паркоместа и промышленные объекты в основной канал не идут.
MAIN_MIX = [
    ("квартиры Алматы и Астаны", 0.7, lambda lot: lot.category == "apartment" and _big_city(lot)),
    ("машина", 0.15, _presentable_car),
    ("коммерция или квартира в регионах", 0.15,
     lambda lot: lot.category == "commercial" or lot.category == "apartment" and not _big_city(lot)),
]


def candidate_lots(session: Session, channel: str, badges: dict[int, dict]) -> list[Lot]:
    """Кандидаты в канал: активные лоты с фото, без флагов качества, ещё не опубликованные в канале (в том числе
    помеченные при первом запуске). Сначала — с плашкой «−N% к рынку», потом остальные (решение владельца сайта
    от 21.10.2026: публикуем все, плашку — везде, где есть оценка); внутри — новые первыми."""
    published = select(ChannelPost.lot_id).where(ChannelPost.channel == channel, ChannelPost.message_id.is_not(None))
    stmt = (select(Lot).where(Lot.status == "active", Lot.price.is_not(None), Lot.id.not_in(published))
            .order_by(Lot.first_seen_at.desc(), Lot.id.desc()))
    lots = [lot for lot in session.scalars(stmt) if lot.images and not lot.flags]
    lots.sort(key=lambda lot: lot.id not in badges)
    return lots


def _today(session: Session, channel: str) -> list[Lot]:
    start = utcnow().astimezone(KZ_TZ).replace(hour=0, minute=0, second=0, microsecond=0)
    return list(session.scalars(
        select(Lot).join(ChannelPost, ChannelPost.lot_id == Lot.id)
        .where(ChannelPost.channel == channel, ChannelPost.message_id.is_not(None), ChannelPost.posted_at >= start)
    ))


class _Buildings:
    """Из одного дома или ЖК — один лот в день: у банков бывают серии по 8 квартир в одном доме."""

    def __init__(self, recent: list[Lot]):
        self.seen = {self.key(lot) for lot in recent}

    @staticmethod
    def key(lot: Lot) -> str:
        from torgi.top import building_key

        if lot.category == VEHICLE:  # машины с одной стоянки — разные лоты
            return f"id|{lot.id}"
        return building_key({"city": lot.city or lot.region, "id": lot.id}, lot.address, lot.title)

    def take(self, lot: Lot) -> bool:
        key = self.key(lot)
        if key in self.seen:
            return False
        self.seen.add(key)
        return True


def channel_lots(session: Session, channel: str, limit: int, rule: dict | None, badges: dict[int, dict]) -> list[Lot]:
    """Лоты городского или тематического канала по его фильтру: сначала с плашкой, потом остальные."""
    buildings = _Buildings(_today(session, channel))
    picked: list[Lot] = []
    for lot in candidate_lots(session, channel, badges):
        if len(picked) >= limit:
            break
        if matches_channel(lot, rule) and buildings.take(lot):
            picked.append(lot)
    return picked


def mixed_lots(session: Session, channel: str, limit: int, badges: dict[int, dict]) -> list[Lot]:
    """Лоты основного канала по долям MAIN_MIX: в каждый слот — категория, сильнее всех отстающая от своей доли
    среди сегодняшних постов; внутри категории — сначала лоты с плашкой. Нет подходящих лотов — слот пустует."""
    candidates = candidate_lots(session, channel, badges)
    queues = [[lot for lot in candidates if match(lot)] for _, _, match in MAIN_MIX]
    recent = _today(session, channel)
    counts = [sum(1 for lot in recent if match(lot)) for _, _, match in MAIN_MIX]
    buildings = _Buildings(recent)
    picked: list[Lot] = []
    while len(picked) < limit:
        total = sum(counts) + 1
        # недобор доли после ещё одного поста; при равенстве — категория выше в списке
        gaps = [(round(share * total - counts[i], 6), -i) for i, (_, share, _) in enumerate(MAIN_MIX) if queues[i]]
        if not gaps or max(gaps)[0] <= 0:
            break
        i = -max(gaps)[1]
        lot = queues[i].pop(0)
        if not buildings.take(lot):
            continue  # из этого дома сегодня уже был пост — слот не тратим
        picked.append(lot)
        counts[i] += 1
    return picked


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

    def call_files(self, method: str, files: dict[str, bytes], **params) -> dict:
        """Как call, но с загрузкой файлов (multipart): фото с плашкой отправляем файлом, а не ссылкой."""
        data = {k: json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v for k, v in params.items()}
        for _ in range(3):
            upload = {name: (f"{name}.jpg", content, "image/jpeg") for name, content in files.items()}
            res = self.client.post(f"{self.base}/{method}", data=data, files=upload, timeout=60).json()
            if res.get("ok"):
                return res["result"]
            retry = (res.get("parameters") or {}).get("retry_after")
            if not retry:
                raise RuntimeError(f"Telegram {method}: {res.get('description')}")
            time.sleep(retry + 1)
        raise RuntimeError(f"Telegram {method}: превышен лимит повторов")

    def post_lot(self, channel: str, lot: Lot, text: str, badge: dict | None = None) -> int:
        # главное фото — с плашкой «−N% к рынку», как на карточке сайта (остальные фото альбома — как есть)
        main = badged_photo(lot.images[0], badge, self.client) if badge and lot.images else None
        if len(lot.images) >= 2:
            # альбом из 3–5 фото, подпись — у первого
            media = [{"type": "photo", "media": url} for url in lot.images[:5]]
            media[0].update(caption=text, parse_mode="HTML")
            try:
                if main:
                    media[0]["media"] = "attach://main"
                    return self.call_files("sendMediaGroup", {"main": main}, chat_id=channel, media=media)[0]["message_id"]
                return self.call("sendMediaGroup", chat_id=channel, media=media)[0]["message_id"]
            except RuntimeError as exc:
                log.warning("лот %s: альбом не отправился (%s), пробуем одно фото", lot.id, exc)
        if lot.images:
            try:
                if main:
                    return self.call_files("sendPhoto", {"photo": main}, chat_id=channel, caption=text,
                                           parse_mode="HTML")["message_id"]
                return self.call("sendPhoto", chat_id=channel, photo=lot.images[0], caption=text,
                                 parse_mode="HTML")["message_id"]
            except RuntimeError as exc:  # фото недоступно для Telegram — публикуем текстом
                log.warning("лот %s: фото не отправилось (%s), пост без фото", lot.id, exc)
        return self.call("sendMessage", chat_id=channel, text=text, parse_mode="HTML",
                         link_preview_options={"is_disabled": True})["message_id"]


def _refresh_post(bot: TelegramBot, post: ChannelPost, lot: Lot, text: str, badge: dict | None) -> int:
    """Один пост: с плашкой — заменяем главное фото вместе с подписью, иначе правим подпись или текст."""
    main = badged_photo(lot.images[0], badge, bot.client) if badge and lot.images else None
    if main:
        try:
            bot.call_files("editMessageMedia", {"main": main}, chat_id=post.channel, message_id=post.message_id,
                           media={"type": "photo", "media": "attach://main", "caption": text, "parse_mode": "HTML"})
            return 1
        except RuntimeError as exc:  # пост без фото (ушёл текстом) — правим только текст
            log.warning("пост %s/%s: фото не заменено (%s)", post.channel, post.message_id, exc)
    common = {"chat_id": post.channel, "message_id": post.message_id, "parse_mode": "HTML"}
    for method, extra in (("editMessageCaption", {"caption": text}),
                          ("editMessageText", {"text": text, "link_preview_options": {"is_disabled": True}})):
        try:
            bot.call(method, **common, **extra)
            return 1
        except RuntimeError as exc:
            if "not modified" in str(exc):
                return 0
            # пост без фото — у него нет подписи, правим текст; иначе пробуем следующий способ
    return 0


def refresh(session: Session) -> int:
    """Переписать уже опубликованные посты по текущему шаблону (например, после смены формата)."""
    if not settings.telegram_bot_token or not settings.telegram_channel:
        raise SystemExit("Задайте TORGI_TELEGRAM_BOT_TOKEN и TORGI_TELEGRAM_CHANNEL")
    bot = TelegramBot(settings.telegram_bot_token)
    rules = {name: rule for name, rule, _ in channels()}
    hub = (settings.telegram_channel or "").lstrip("@")
    badges = load_badges(Path(settings.telegram_badges))
    posts = session.scalars(select(ChannelPost).where(
        ChannelPost.channel.in_(list(rules)), ChannelPost.message_id.is_not(None))).all()
    edited = 0
    for post in posts:
        lot = session.get(Lot, post.lot_id)
        if lot is None:
            continue
        footer = MAIN_FOOTER if rules.get(post.channel) is None else HUB_FOOTER.format(hub=hub)
        try:
            edited += _refresh_post(bot, post, lot, format_post(lot, footer, post.channel, badges.get(lot.id)),
                                    badges.get(lot.id))
        except (RuntimeError, httpx.HTTPError) as exc:  # обрыв связи на одном посте не останавливает остальные
            log.warning("пост %s/%s: не переписан (%s)", post.channel, post.message_id, exc)
        time.sleep(1)
    log.info("переписано постов: %d из %d", edited, len(posts))
    return edited


# Описания каналов и бота живут здесь, а не только в Telegram: `torgi post --about` выставляет их, если в Telegram
# другой текст. Лимиты Telegram: описание канала — 255 символов, короткое описание бота — 120.
# Коротко и одинаково на всех площадках (сайт, Telegram, Instagram); ссылки — на другие площадки, не на себя.
INSTAGRAM = "instagram.com/torgi.kz"
KINDS = "Арест, госимущество, банкроты, залоги банков."
LINKS = f"torgi.kz · {INSTAGRAM}"
HUB_LINE = "Все торги Казахстана → @torgi_kz_news"
AUTO_CHANNEL = "@torgi_kz_auto"
# первые две строки — как на сайте и в Instagram (решение владельца от 20.10.2026)
HEADLINE = "Недвижимость и автотранспорт с торгов Казахстана"
AI_LINE = "✨ Первый агрегатор торгов с использованием AI"
BOT_SHORT_ABOUT = f"{HEADLINE}\n{AI_LINE}\ntorgi.kz"


# число лотов в публичных текстах — везде одно и то же «3 000+» и не обновляется (решение владельца от 22–24.10.2026)
PUBLIC_TOTAL = "3 000+"


def total_phrase(total: int | None = None) -> str:
    """Число лотов для описаний и ответов бота: фиксированное «3 000+», а не живой счётчик."""
    return PUBLIC_TOTAL


def channel_about(total: int | None = None) -> dict[str, str]:
    return {
        "@torgi_kz_news": f"{HEADLINE}\n{AI_LINE}\n{total_phrase(total)} объектов: жильё, "
                          f"коммерция, земля, авто. {KINDS}\nАвто → {AUTO_CHANNEL}\n{LINKS}",
        AUTO_CHANNEL: f"Автомобили и спецтехника с торгов Казахстана: марка, год, цена и фото.\n{AI_LINE}\n"
                      f"{HUB_LINE}\n{LINKS}",
        "@torgi_kz_almaty": f"Недвижимость Алматы с торгов: квартиры, дома, коммерция и земля. {KINDS}\n{AI_LINE}\n"
                            f"{HUB_LINE}\n{LINKS}",
        "@torgi_kz_astana": f"Недвижимость Астаны с торгов: квартиры, дома, коммерция и земля. {KINDS}\n{AI_LINE}\n"
                            f"{HUB_LINE}\n{LINKS}",
        "@torgi_kz_biz": f"Коммерческая недвижимость с торгов Казахстана: офисы, магазины, склады и здания. {KINDS}\n"
                         f"{AI_LINE}\n{HUB_LINE}\n{LINKS}",
    }


def set_about(bot: TelegramBot, total: int | None = None) -> list[str]:
    """Описания каналов (channel_about) и короткое описание бота. Возвращает, что изменилось;
    канал, где у бота нет права «Изменение профиля канала», пропускается с предупреждением."""
    changed = []
    for chat, text in channel_about(total).items():
        try:
            if (bot.call("getChat", chat_id=chat).get("description") or "") != text:
                bot.call("setChatDescription", chat_id=chat, description=text)
                changed.append(chat)
        except RuntimeError as exc:
            log.warning("%s: описание не обновлено (%s)", chat, exc)
    if bot.call("getMyShortDescription").get("short_description") != BOT_SHORT_ABOUT:
        bot.call("setMyShortDescription", short_description=BOT_SHORT_ABOUT)
        changed.append("бот")
    log.info("описания: %s", ", ".join(changed) or "без изменений")
    return changed


def channels() -> list[tuple[str, dict | None, int]]:
    """Основной канал (все лоты) и дополнительные — региональные и тематические."""
    out: list[tuple[str, dict | None, int]] = []
    daily = settings.telegram_batch * len(settings.telegram_slots)
    if settings.telegram_channel:
        out.append((settings.telegram_channel, None, daily))
    if settings.telegram_channels.strip():
        for name, rule in json.loads(settings.telegram_channels).items():
            out.append((name, rule or None, daily))
    return out


def slot_quota(now: datetime | None = None) -> int:
    """Сколько постов в канал положено к этому часу: по telegram_batch за каждый наступивший выпуск."""
    hour = (now or utcnow()).astimezone(KZ_TZ).hour
    return settings.telegram_batch * sum(1 for slot in settings.telegram_slots if hour >= slot)


def run_channel(session: Session, bot: "TelegramBot | None", channel: str, rule: dict | None, daily: int,
                limit: int, dry_run: bool, badges: dict | None = None) -> int:
    # канал машин открыт позже раздела — уже собранные машины в нём тоже публикуем
    cars = "vehicle" in ((rule or {}).get("category") or [])
    if not cars and not dry_run and session.scalar(select(ChannelPost.id).where(ChannelPost.channel == channel).limit(1)) is None:
        # Первый запуск для канала: текущую базу не выгружаем, публикуем только новое
        lots = pending_lots(session, channel, 10**9, 10**4, rule)
        session.add_all(ChannelPost(lot_id=lot.id, channel=channel, message_id=None) for lot in lots)
        session.commit()
        log.info("канал %s: первый запуск — %d текущих лотов помечены опубликованными", channel, len(lots))
        return 0
    if not dry_run:
        # выпуск: не больше telegram_batch постов за запуск и не больше положенного к этому часу
        limit = min(limit, settings.telegram_batch, slot_quota() - posted_today(session, channel), daily)
        if limit <= 0:
            log.info("канал %s: выпуск уже был, следующий — по расписанию %s", channel,
                     ", ".join(f"{h}:00" for h in settings.telegram_slots))
            return 0
    if rule is None and channel == settings.telegram_channel:
        lots = mixed_lots(session, channel, limit, badges or {})
    else:
        lots = channel_lots(session, channel, limit, rule, badges or {})
    hub = (settings.telegram_channel or "").lstrip("@")
    footer = MAIN_FOOTER if rule is None else HUB_FOOTER.format(hub=hub) if hub else ""
    for i, lot in enumerate(lots):
        badge = (badges or {}).get(lot.id)
        text = format_post(lot, footer, channel, badge)
        if dry_run:
            print(f"--- {channel}: лот {lot.id} ({lot.source}){' · плашка ' + badge_label(badge) if badge else ''}\n{text}\n")
            continue
        if i:
            time.sleep(settings.telegram_post_delay)
        message_id = bot.post_lot(channel, lot, text, badge)
        # квартира из основного канала могла быть помечена без публикации при первом запуске — обновляем отметку
        post = session.scalar(select(ChannelPost).where(ChannelPost.lot_id == lot.id, ChannelPost.channel == channel))
        if post:
            post.message_id, post.posted_at = message_id, utcnow()
        else:
            session.add(ChannelPost(lot_id=lot.id, channel=channel, message_id=message_id))
        session.commit()
        log.info("канал %s: опубликован лот %s → сообщение %s", channel, lot.id, message_id)
    return len(lots)


def run(session: Session, limit: int = 5, dry_run: bool = False, mark_all: bool = False) -> int:
    targets = channels() or [("dry-run", None, settings.telegram_batch * len(settings.telegram_slots))]
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
    badges = load_badges(Path(settings.telegram_badges))
    total = 0
    for channel, rule, daily in targets:
        try:
            total += run_channel(session, bot, channel, rule, daily, limit, dry_run, badges)
        except RuntimeError:
            log.exception("канал %s: ошибка публикации", channel)
    return total
