"""Telegram-бот подписок (@torgi_kz_bot): «сообщать о новых объектах по поиску» и «следить за ценой лота».

Сайт даёт ссылки вида t.me/<бот>?start=<код>; бот работает без сервера — раз в час в GitHub Actions:
забирает входящие (getUpdates), оформляет подписки и рассылает уведомления.

    uv run python -m torgi.cli bot             # обработать входящие и разослать уведомления
    uv run python -m torgi.cli bot --dry-run   # только показать уведомления, ничего не отправлять

Формат кода — как web/src/lib/subscribe.ts (меняйте вместе):
    q-ca-r0-x30   квартиры (c=категории), Алматы (r=индекс региона), до 30 млн (x), от (n) млн,
                  m=цена за м² до, тыс., s=площадь от, м², o=виды продажи
    lot-123       слежение за лотом 123
"""

import html
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from urllib.parse import urlencode

from sqlalchemy import select
from sqlalchemy.orm import Session

from torgi.config import settings
from torgi.models import BotState, Lot, Subscription, utcnow
from torgi.normalize import CATEGORIES, ORIGINS, REGIONS
from torgi.telegram import TelegramBot, _money

log = logging.getLogger(__name__)

CAT = {"a": "apartment", "h": "house", "c": "commercial", "l": "land", "p": "parking", "i": "industrial", "o": "other"}
ORG = {"a": "arrested", "b": "bank_balance", "z": "bank_pledge", "s": "court",
       "g": "state", "k": "bankrupt", "t": "tax_debtor", "f": "confiscated"}
CATEGORY_PLURAL = {"apartment": "Квартиры", "house": "Дома", "commercial": "Коммерция", "land": "Земля",
                   "parking": "Паркинги", "industrial": "Промбазы", "other": "Прочее"}
PER_SUBSCRIPTION = 5  # лотов в одном уведомлении по поиску, остальные — ссылкой на сайт
MAX_SUBSCRIPTIONS = 20  # на один чат

BOT_DESCRIPTION = (
    "Бот torgi.kz присылает новые объекты с торгов по вашему поиску и сообщает об изменении цены лота.\n\n"
    "Подписка оформляется на сайте torgi.kz кнопками «Сообщать о новых» и «Следить за ценой». "
    "Бот отвечает в течение часа."
)
HELP = (
    "Я присылаю новые объекты с торгов по вашему поиску и сообщаю, когда меняется цена лота.\n\n"
    "Как подписаться: на {site} настройте фильтры в каталоге и нажмите «🔔 Сообщать о новых в Telegram» "
    "или «Следить за ценой» на странице объекта.\n\n"
    "/list — мои подписки\n/stop — отписаться от всего\n/stop 2 — отписаться от подписки №2"
)


@dataclass
class SearchFilter:
    categories: list[str] = field(default_factory=list)
    region: str | None = None
    price_min: float | None = None
    price_max: float | None = None
    ppm_max: float | None = None
    area_min: float | None = None
    origins: list[str] = field(default_factory=list)

    def matches(self, lot: Lot) -> bool:
        if self.categories and lot.category not in self.categories:
            return False
        if self.region and lot.region != self.region:
            return False
        if self.price_min and (lot.price or 0) < self.price_min:
            return False
        if self.price_max and (lot.price is None or lot.price > self.price_max):
            return False
        if self.ppm_max and (lot.price_per_m2 is None or lot.price_per_m2 > self.ppm_max):
            return False
        if self.area_min and (lot.area_m2 or 0) < self.area_min:
            return False
        if self.origins and lot.origin not in self.origins:
            return False
        return not lot.flags

    def describe(self) -> str:
        parts = [", ".join(CATEGORY_PLURAL[c] for c in self.categories) or "Все объекты"]
        parts.append(self.region or "весь Казахстан")
        if self.price_min or self.price_max:
            lo = f"от {self.price_min / 1e6:g}" if self.price_min else ""
            hi = f"до {self.price_max / 1e6:g}" if self.price_max else ""
            parts.append(f"{lo} {hi} млн ₸".strip())
        if self.ppm_max:
            parts.append(f"до {self.ppm_max / 1000:g} тыс. ₸/м²")
        if self.area_min:
            parts.append(f"от {self.area_min:g} м²")
        if self.origins:
            parts.append(", ".join(ORIGINS[o].lower() for o in self.origins))
        return " · ".join(parts)

    def catalog_url(self) -> str:
        q: list[tuple[str, str]] = [("category", c) for c in self.categories]
        if self.region:
            q.append(("region", self.region))
        for key, value in (("price_min", self.price_min), ("price_max", self.price_max),
                           ("ppm_max", self.ppm_max), ("area_min", self.area_min)):
            if value:
                q.append((key, f"{value:.0f}"))
        q += [("origin", o) for o in self.origins]
        return f"{settings.site_url}/lots/?{urlencode(q)}"


_CODE_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def parse_code(code: str) -> SearchFilter | int | None:
    """SearchFilter для подписки на поиск, id лота для слежения, None — код не распознан."""
    if not _CODE_RE.match(code):
        return None
    if m := re.fullmatch(r"lot-(\d+)", code):
        return int(m.group(1))
    if not code.startswith("q-"):
        return None
    f = SearchFilter()
    for part in code[2:].split("-"):
        if not part:
            continue
        key, value = part[0], part[1:]
        try:
            if key == "c":
                f.categories = [CAT[ch] for ch in value if ch in CAT]
            elif key == "r":
                f.region = REGIONS[int(value)]
            elif key == "n":
                f.price_min = int(value) * 1_000_000
            elif key == "x":
                f.price_max = int(value) * 1_000_000
            elif key == "m":
                f.ppm_max = int(value) * 1000
            elif key == "s":
                f.area_min = float(value)
            elif key == "o":
                f.origins = [ORG[ch] for ch in value if ch in ORG]
        except (ValueError, IndexError):
            return None
    return f


def _lot_line(lot: Lot) -> str:
    title = CATEGORIES.get(lot.category, "Объект")
    if lot.area_m2:
        title += f", {lot.area_m2:g} м²".replace(".", ",")
    place = lot.city or lot.region or ""
    price = _money(lot.price) if lot.price else "цена не указана"
    return (f'• <a href="{settings.site_url}/lots/{lot.id}/">{html.escape(title)}</a> — {html.escape(place)}, '
            f"<b>{price}</b>")


class Bot:
    """Обёртка над Bot API с режимом dry-run."""

    def __init__(self, dry_run: bool):
        self.dry_run = dry_run
        self.api = None if dry_run else TelegramBot(settings.telegram_bot_token)

    def send(self, chat_id: int, text: str) -> bool:
        """False — пользователь заблокировал бота (подписки чата отключаются)."""
        if self.dry_run:
            print(f"--> {chat_id}\n{text}\n")
            return True
        try:
            self.api.call("sendMessage", chat_id=chat_id, text=text, parse_mode="HTML",
                          link_preview_options={"is_disabled": True})
            return True
        except RuntimeError as exc:
            if "blocked" in str(exc) or "deactivated" in str(exc) or "chat not found" in str(exc):
                return False
            raise


def _state(session: Session, key: str) -> str | None:
    row = session.get(BotState, key)
    return row.value if row else None


def _set_state(session: Session, key: str, value: str) -> None:
    row = session.get(BotState, key) or BotState(key=key, value=value)
    row.value = value
    session.add(row)


def subscribe(session: Session, bot: Bot, chat_id: int, code: str, now: datetime) -> None:
    parsed = parse_code(code)
    if parsed is None:
        bot.send(chat_id, HELP.format(site=settings.site_url))
        return
    active = session.scalars(select(Subscription).where(Subscription.chat_id == chat_id, Subscription.active)).all()
    existing = session.scalar(select(Subscription).where(Subscription.chat_id == chat_id, Subscription.code == code))
    if not existing and len(active) >= MAX_SUBSCRIPTIONS:
        bot.send(chat_id, f"У вас уже {MAX_SUBSCRIPTIONS} подписок — удалите лишние командой /stop N (список: /list).")
        return
    sub = existing or Subscription(chat_id=chat_id, code=code)
    sub.active, sub.checked_at = True, now

    if isinstance(parsed, int):
        lot = session.get(Lot, parsed)
        if lot is None:
            bot.send(chat_id, "Этот объект не найден — возможно, его уже сняли с продажи.")
            return
        sub.lot_id, sub.last_price = lot.id, lot.price
        session.add(sub)
        bot.send(chat_id, f"🔔 Слежу за ценой:\n{_lot_line(lot)}\n\nСообщу, если цена изменится или объект снимут "
                          "с продажи. /list — все подписки.")
        return

    session.add(sub)
    current = [lot for lot in session.scalars(select(Lot).where(Lot.status == "active")) if parsed.matches(lot)]
    bot.send(chat_id, (
        f"🔔 Подписка оформлена: <b>{html.escape(parsed.describe())}</b>\n\n"
        f"Сейчас таких объектов {len(current)} — "
        f'<a href="{html.escape(parsed.catalog_url())}">смотреть на сайте</a>. '
        "Новые буду присылать сюда, как только они появятся.\n\n/list — все подписки, /stop — отписаться."
    ))


def _describe(sub: Subscription, session: Session) -> str:
    parsed = parse_code(sub.code)
    if isinstance(parsed, SearchFilter):
        return parsed.describe()
    lot = session.get(Lot, sub.lot_id) if sub.lot_id else None
    return f"цена лота: {CATEGORIES.get(lot.category, 'объект')}, {lot.city or ''}" if lot else "лот"


def handle_message(session: Session, bot: Bot, chat_id: int, text: str, now: datetime) -> None:
    text = text.strip()
    subs = session.scalars(
        select(Subscription).where(Subscription.chat_id == chat_id, Subscription.active).order_by(Subscription.id)
    ).all()
    if text.startswith("/start"):
        code = text[len("/start"):].strip()
        if code:
            subscribe(session, bot, chat_id, code, now)
        else:
            bot.send(chat_id, HELP.format(site=settings.site_url))
    elif text.startswith("/list"):
        if not subs:
            bot.send(chat_id, f"Подписок нет. Оформить можно на {settings.site_url}")
        else:
            lines = [f"{i}. {html.escape(_describe(s, session))}" for i, s in enumerate(subs, 1)]
            bot.send(chat_id, "Ваши подписки:\n" + "\n".join(lines) + "\n\n/stop N — отписаться от №N")
    elif text.startswith("/stop"):
        arg = text[len("/stop"):].strip()
        if arg.isdigit() and 1 <= int(arg) <= len(subs):
            subs[int(arg) - 1].active = False
            bot.send(chat_id, f"Подписка №{arg} отключена.")
        else:
            for s in subs:
                s.active = False
            bot.send(chat_id, "Все подписки отключены. Вернуться можно в любой момент на сайте.")
    else:
        bot.send(chat_id, HELP.format(site=settings.site_url))


def process_updates(session: Session, bot: Bot, now: datetime) -> int:
    if bot.dry_run:
        return 0
    offset = int(_state(session, "updates_offset") or 0)
    updates = bot.api.call("getUpdates", offset=offset, timeout=0, allowed_updates=["message"])
    for upd in updates:
        offset = max(offset, upd["update_id"] + 1)
        msg = upd.get("message") or {}
        chat, text = msg.get("chat") or {}, msg.get("text")
        if chat.get("type") == "private" and text:
            try:
                handle_message(session, bot, chat["id"], text, now)
            except Exception:  # одно сообщение не должно ронять всю обработку
                log.exception("бот: ошибка обработки сообщения от %s", chat.get("id"))
        _set_state(session, "updates_offset", str(offset))
        session.commit()
    return len(updates)


def notify(session: Session, bot: Bot, now: datetime) -> int:
    sent = 0
    subs = session.scalars(select(Subscription).where(Subscription.active)).all()
    blocked: set[int] = set()
    searches = [s for s in subs if not s.lot_id]
    if searches:
        oldest = min(s.checked_at for s in searches)
        fresh = session.scalars(
            select(Lot).where(Lot.status == "active", Lot.first_seen_at > oldest).order_by(Lot.first_seen_at.desc())
        ).all()
    for sub in subs:
        if sub.chat_id in blocked:
            continue
        text = None
        if sub.lot_id:
            lot = session.get(Lot, sub.lot_id)
            if lot is None or lot.status != "active":
                text = "Объект, за которым вы следили, снят с продажи у источника."
                if lot:
                    text += f"\n{_lot_line(lot)}"
                sub.active = False
            elif lot.price and sub.last_price and lot.price != sub.last_price:
                arrow = "📉 Цена снижена" if lot.price < sub.last_price else "📈 Цена повышена"
                pct = abs(lot.price - sub.last_price) / sub.last_price * 100
                text = f"{arrow} на {pct:.0f}%: {_money(sub.last_price)} → <b>{_money(lot.price)}</b>\n{_lot_line(lot)}"
                sub.last_price = lot.price
        else:
            f = parse_code(sub.code)
            if isinstance(f, SearchFilter):
                new = [lot for lot in fresh if lot.first_seen_at > sub.checked_at and f.matches(lot)]
                if new:
                    text = f"🆕 Новые объекты: <b>{html.escape(f.describe())}</b>\n\n"
                    text += "\n".join(_lot_line(lot) for lot in new[:PER_SUBSCRIPTION])
                    if len(new) > PER_SUBSCRIPTION:
                        text += f'\n\n<a href="{html.escape(f.catalog_url())}">Ещё {len(new) - PER_SUBSCRIPTION} на сайте</a>'
            sub.checked_at = now
        if text:
            if bot.send(sub.chat_id, text):
                sent += 1
            else:
                blocked.add(sub.chat_id)
    for sub in subs:
        if sub.chat_id in blocked:
            sub.active = False
    if not bot.dry_run:
        session.commit()
    return sent


def setup(bot: Bot, session: Session) -> None:
    """Описание бота и меню команд — один раз (повторно — при смене текста)."""
    if bot.dry_run or _state(session, "description") == BOT_DESCRIPTION:
        return
    bot.api.call("setMyDescription", description=BOT_DESCRIPTION)
    bot.api.call("setMyShortDescription", short_description="Новые объекты с торгов по вашему поиску — torgi.kz")
    bot.api.call("setMyCommands", commands=[
        {"command": "list", "description": "Мои подписки"},
        {"command": "stop", "description": "Отписаться"},
    ])
    _set_state(session, "description", BOT_DESCRIPTION)
    session.commit()


def run(session: Session, dry_run: bool = False) -> dict[str, int]:
    if not dry_run and not settings.telegram_bot_token:
        raise SystemExit("Задайте TORGI_TELEGRAM_BOT_TOKEN")
    bot = Bot(dry_run)
    now = utcnow()
    setup(bot, session)
    updates = process_updates(session, bot, now)
    sent = notify(session, bot, now)
    log.info("бот: входящих %d, уведомлений %d", updates, sent)
    return {"updates": updates, "sent": sent}
