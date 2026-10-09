"""Telegram-бот подписок (@torgi_kz_bot): «сообщать о новых объектах по поиску» и «следить за ценой лота».

Сайт даёт ссылки вида t.me/<бот>?start=<код>; бот работает без сервера — раз в час в GitHub Actions:
забирает входящие (getUpdates), оформляет подписки и рассылает уведомления.

    uv run python -m torgi.cli bot             # обработать входящие и разослать уведомления
    uv run python -m torgi.cli bot --dry-run   # только показать уведомления, ничего не отправлять

Формат кода — как web/src/lib/subscribe.ts (меняйте вместе):
    q-ca-r0_1-x30 квартиры (c=категории), Алматы и Астана (r=индексы регионов через _), до 30 млн (x), от (n) млн,
                  m=цена за м² до, тыс., s=площадь от, м², o=виды продажи
    lot-123       слежение за лотом 123 (любое изменение цены)
    lot-123-t5000 сообщить, когда цена опустится до 5 000 тыс. ₸
    c-123         заявка на консультацию по лоту 123 («c» — без лота)
    check-123     бесплатная проверка лота 123

Заявки и вопросы пересылаются администраторам (TORGI_TELEGRAM_ADMINS — их username через запятую);
администратор должен один раз написать боту /start, чтобы бот узнал его чат.
"""

import html
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

from sqlalchemy import select
from sqlalchemy.orm import Session

from torgi.config import settings
from torgi.models import BotState, Lot, Subscription, utcnow
from torgi.normalize import CATEGORIES, ORIGINS, REGIONS
from torgi.telegram import TelegramBot, _money, channels, matches_channel

log = logging.getLogger(__name__)

CAT = {"a": "apartment", "h": "house", "c": "commercial", "l": "land", "p": "parking", "i": "industrial", "o": "other"}
ORG = {"a": "arrested", "b": "bank_balance", "z": "bank_pledge", "s": "court",
       "g": "state", "k": "bankrupt", "t": "tax_debtor", "f": "confiscated"}
CATEGORY_PLURAL = {"apartment": "Квартиры", "house": "Дома", "commercial": "Коммерция", "land": "Земля",
                   "parking": "Паркинги", "industrial": "Промбазы", "other": "Прочее"}
ALMATY = timezone(timedelta(hours=5))  # весь Казахстан в UTC+5
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
    regions: list[str] = field(default_factory=list)
    price_min: float | None = None
    price_max: float | None = None
    ppm_max: float | None = None
    area_min: float | None = None
    origins: list[str] = field(default_factory=list)

    def matches(self, lot: Lot) -> bool:
        if self.categories and lot.category not in self.categories:
            return False
        if self.regions and lot.region not in self.regions:
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
        parts.append(", ".join(self.regions) or "весь Казахстан")
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
        q += [("region", r) for r in self.regions]
        for key, value in (("price_min", self.price_min), ("price_max", self.price_max),
                           ("ppm_max", self.ppm_max), ("area_min", self.area_min)):
            if value:
                q.append((key, f"{value:.0f}"))
        q += [("origin", o) for o in self.origins]
        q += [("utm_source", "telegram"), ("utm_medium", "bot")]
        return f"{settings.site_url}/lots/?{urlencode(q)}"


_CODE_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


@dataclass
class LotWatch:
    lot_id: int
    target: float | None = None  # None — сообщать о любом изменении цены


@dataclass
class Lead:
    kind: str  # consult | check
    lot_id: int | None = None


def parse_code(code: str) -> SearchFilter | LotWatch | Lead | None:
    """Разбор параметра /start; None — код не распознан."""
    if not _CODE_RE.match(code):
        return None
    if m := re.fullmatch(r"lot-(\d+)(?:-t(\d+))?", code):
        return LotWatch(int(m.group(1)), int(m.group(2)) * 1000 if m.group(2) else None)
    if m := re.fullmatch(r"(c|check)(?:-(\d+))?", code):
        return Lead("check" if m.group(1) == "check" else "consult", int(m.group(2)) if m.group(2) else None)
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
                f.regions = [REGIONS[int(i)] for i in value.split("_") if i]
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
    return (f'• <a href="{settings.site_url}/lots/{lot.id}/?utm_source=telegram&amp;utm_medium=bot">{html.escape(title)}</a> — {html.escape(place)}, '
            f"<b>{price}</b>")


class Bot:
    """Обёртка над Bot API с режимом dry-run."""

    def __init__(self, dry_run: bool):
        self.dry_run = dry_run
        self.api = None if dry_run else TelegramBot(settings.telegram_bot_token)
        self._fake_id = 0

    def send(self, chat_id: int, text: str) -> int:
        """Номер отправленного сообщения; 0 — пользователь заблокировал бота (подписки чата отключаются)."""
        if self.dry_run:
            print(f"--> {chat_id}\n{text}\n")
            self._fake_id += 1
            return self._fake_id
        try:
            result = self.api.call("sendMessage", chat_id=chat_id, text=text, parse_mode="HTML",
                                   link_preview_options={"is_disabled": True})
            return result["message_id"]
        except RuntimeError as exc:
            if "blocked" in str(exc) or "deactivated" in str(exc) or "chat not found" in str(exc):
                return 0
            raise


def _state(session: Session, key: str) -> str | None:
    row = session.get(BotState, key)
    return row.value if row else None


def _set_state(session: Session, key: str, value: str) -> None:
    row = session.get(BotState, key) or BotState(key=key, value=value)
    row.value = value
    session.add(row)


LEAD_TITLES = {"consult": "консультация", "check": "бесплатная проверка лота"}


def _admin_chats(session: Session) -> list[int]:
    return json.loads(_state(session, "admin_chats") or "[]")


def _who(user: dict) -> str:
    name = html.escape(" ".join(p for p in (user.get("first_name"), user.get("last_name")) if p) or "Пользователь")
    link = f'<a href="tg://user?id={user["id"]}">{name}</a>'
    return link + (f" @{html.escape(user['username'])}" if user.get("username") else "")


MAX_THREADS = 300  # сколько последних заявок/вопросов помнить для ответа через бота
REPLY_HINT = "\n\n<i>Ответьте на это сообщение (Reply) — бот перешлёт ответ клиенту. /info в ответе — сводка по лоту.</i>"


def _remember_thread(session: Session, admin_chat: int, message_id: int, thread: dict) -> None:
    threads = json.loads(_state(session, "threads") or "{}")
    threads[f"{admin_chat}:{message_id}"] = thread
    _set_state(session, "threads", json.dumps(dict(list(threads.items())[-MAX_THREADS:])))


def _send_to_admin(session: Session, bot: Bot, chat: int, text: str, thread: dict | None) -> None:
    message_id = bot.send(chat, text + (REPLY_HINT if thread else ""))
    if message_id and thread:
        _remember_thread(session, chat, message_id, thread)


def notify_admins(session: Session, bot: Bot, text: str, thread: dict | None = None) -> None:
    """Заявки — администраторам; пока ни один не написал боту, копятся в очереди.

    thread — кому отвечать: {"chat": id клиента, "lot": id лота или None}.
    """
    chats = _admin_chats(session)
    if not chats:
        queue = json.loads(_state(session, "pending_leads") or "[]")
        item = {"text": text, "thread": thread}
        _set_state(session, "pending_leads", json.dumps((queue + [item])[-20:], ensure_ascii=False))
        return
    for chat in chats:
        _send_to_admin(session, bot, chat, text, thread)


def register_admin(session: Session, bot: Bot, chat_id: int, user: dict) -> bool:
    admins = {u.strip().lstrip("@").lower() for u in settings.telegram_admins.split(",") if u.strip()}
    if (user.get("username") or "").lower() not in admins:
        return False
    chats = _admin_chats(session)
    if chat_id not in chats:
        _set_state(session, "admin_chats", json.dumps(chats + [chat_id]))
        bot.send(chat_id, "Вы — администратор torgi.kz: сюда будут приходить заявки и вопросы пользователей.")
        for item in json.loads(_state(session, "pending_leads") or "[]"):
            item = item if isinstance(item, dict) else {"text": item, "thread": None}
            _send_to_admin(session, bot, chat_id, item["text"], item["thread"])
        _set_state(session, "pending_leads", "[]")
    return True


def lead(session: Session, bot: Bot, chat_id: int, user: dict, parsed: Lead) -> None:
    lot = session.get(Lot, parsed.lot_id) if parsed.lot_id else None
    about = f"\n{_lot_line(lot)}" if lot else ""
    notify_admins(session, bot, f"📩 Заявка: <b>{LEAD_TITLES[parsed.kind]}</b> от {_who(user)}{about}",
                  {"chat": chat_id, "lot": parsed.lot_id})
    if parsed.kind == "check":
        reply = ("Заявка на бесплатную проверку принята. Проверим документы, обременения и риски по объекту "
                 "и напишем вам здесь в Telegram.")
    else:
        reply = "Заявка на консультацию принята — напишем вам здесь в Telegram."
    bot.send(chat_id, reply + about + "\n\nМожете сразу написать вопрос следующим сообщением — мы его получим." + channel_invite(lot))


def subscribe(session: Session, bot: Bot, chat_id: int, code: str, now: datetime, user: dict | None = None) -> None:
    parsed = parse_code(code)
    if parsed is None:
        bot.send(chat_id, HELP.format(site=settings.site_url))
        return
    if isinstance(parsed, Lead):
        lead(session, bot, chat_id, user or {"id": chat_id}, parsed)
        return
    active = session.scalars(select(Subscription).where(Subscription.chat_id == chat_id, Subscription.active)).all()
    existing = session.scalar(select(Subscription).where(Subscription.chat_id == chat_id, Subscription.code == code))
    if not existing and len(active) >= MAX_SUBSCRIPTIONS:
        bot.send(chat_id, f"У вас уже {MAX_SUBSCRIPTIONS} подписок — удалите лишние командой /stop N (список: /list).")
        return
    sub = existing or Subscription(chat_id=chat_id, code=code)
    sub.active, sub.checked_at = True, now

    if isinstance(parsed, LotWatch):
        lot = session.get(Lot, parsed.lot_id)
        if lot is None:
            bot.send(chat_id, "Этот объект не найден — возможно, его уже сняли с продажи.")
            return
        sub.lot_id, sub.last_price = lot.id, lot.price
        session.add(sub)
        when = (f"когда цена опустится до {_money(parsed.target)}" if parsed.target
                else "если цена изменится")
        bot.send(chat_id, f"🔔 Слежу за ценой:\n{_lot_line(lot)}\n\nСообщу, {when} или если объект снимут "
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
    target = f" — до {_money(parsed.target)}" if isinstance(parsed, LotWatch) and parsed.target else ""
    return f"цена лота: {CATEGORIES.get(lot.category, 'объект')}, {lot.city or ''}{target}" if lot else "лот"


def _last_lot(session: Session, client_chat: int) -> int | None:
    """Лот из последней заявки клиента — чтобы /info работал и в ответ на его вопрос."""
    for thread in reversed(list(json.loads(_state(session, "threads") or "{}").values())):
        if thread.get("chat") == client_chat and thread.get("lot"):
            return thread["lot"]
    return None


def lot_info(lot: Lot) -> str:
    """Сводка по лоту для клиента (по команде администратора /info)."""
    rows = [f"<b>{html.escape(CATEGORIES.get(lot.category, 'Объект'))}</b>"
            + (f", {lot.area_m2:g} м²".replace(".", ",") if lot.area_m2 else "")]
    if lot.address:
        rows.append(f"Адрес: {html.escape(lot.address)}")
    if lot.price:
        label = "Стартовая цена" if lot.sale_type in ("auction", "auction_down") else "Цена"
        rows.append(f"{label}: <b>{_money(lot.price)}</b>")
    if lot.min_price:
        rows.append(f"Минимальная цена на понижении: {_money(lot.min_price)}")
    if lot.deposit:
        rows.append(f"Гарантийный взнос (задаток): {_money(lot.deposit)}")
    for label, value in (("Приём заявок до", lot.applications_deadline), ("Начало торгов", lot.auction_start)):
        if value:
            rows.append(f"{label}: {value.astimezone(ALMATY):%d.%m.%Y %H:%M}")
    rows.append(f"Вид продажи: {html.escape(ORIGINS.get(lot.origin, lot.origin))}")
    if lot.url:
        rows.append(f'<a href="{html.escape(lot.url)}">Страница лота у продавца</a>')
    rows.append(f'<a href="{settings.site_url}/lots/{lot.id}/?utm_source=telegram&amp;utm_medium=bot">Карточка на torgi.kz</a>')
    return ("Здравствуйте! Вы оставляли заявку на сайте torgi.kz. Информация по лоту:\n\n" + "\n".join(rows)
            + channel_invite(lot))


def channel_invite(lot: Lot | None = None) -> str:
    """Приглашение в каналы: основной и тот, куда попадает этот лот (Алматы, Астана, бизнес)."""
    names = [name for name, rule, _ in channels() if rule is None or (lot is not None and matches_channel(lot, rule))]
    if not names:
        return ""
    links = ", ".join(f'<a href="https://t.me/{n.lstrip("@")}">{html.escape(n)}</a>' for n in names[:2])
    return f"\n\n📢 Подписывайтесь на {links} — новые выгодные лоты каждый день, чтобы не пропустить интересное."


def admin_reply(session: Session, bot: Bot, chat_id: int, text: str, reply_to: int) -> None:
    """Администратор ответил (Reply) на заявку или вопрос — пересылаем клиенту от имени бота."""
    thread = json.loads(_state(session, "threads") or "{}").get(f"{chat_id}:{reply_to}")
    if not thread:
        bot.send(chat_id, "Не нашёл, кому ответить: нажмите «Ответить» (Reply) на сообщении с заявкой или вопросом.")
        return
    if text.split()[0] in ("/info", "/lot"):
        lot = session.get(Lot, thread["lot"]) if thread.get("lot") else None
        if lot is None:
            bot.send(chat_id, "К этой заявке не привязан лот — напишите ответ текстом.")
            return
        message = lot_info(lot)
    else:
        message = html.escape(text)
    delivered = bot.send(thread["chat"], message)
    bot.send(chat_id, "✅ Отправлено клиенту." if delivered else "⚠️ Не доставлено: клиент заблокировал бота.")


def handle_message(session: Session, bot: Bot, chat_id: int, text: str, now: datetime,
                   user: dict | None = None, reply_to: int | None = None) -> None:
    text = text.strip()
    user = user or {"id": chat_id}
    is_admin = register_admin(session, bot, chat_id, user)
    if is_admin and reply_to:
        admin_reply(session, bot, chat_id, text, reply_to)
        return
    subs = session.scalars(
        select(Subscription).where(Subscription.chat_id == chat_id, Subscription.active).order_by(Subscription.id)
    ).all()
    if text.startswith("/start"):
        code = text[len("/start"):].strip()
        if code:
            subscribe(session, bot, chat_id, code, now, user)
        elif not is_admin:
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
    elif text.startswith("/"):
        bot.send(chat_id, HELP.format(site=settings.site_url))
    elif not is_admin:
        # вопрос пользователя — администраторам
        notify_admins(session, bot, f"💬 Вопрос от {_who(user)}:\n{html.escape(text[:1500])}",
                      {"chat": chat_id, "lot": _last_lot(session, chat_id)})
        bot.send(chat_id, "Спасибо, вопрос передан — ответим здесь в Telegram.")


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
                handle_message(session, bot, chat["id"], text, now, msg.get("from") or {"id": chat["id"]},
                               (msg.get("reply_to_message") or {}).get("message_id"))
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
            elif isinstance(target := parse_code(sub.code), LotWatch) and target.target:
                if lot.price and lot.price <= target.target and lot.price != sub.last_price:
                    text = f"🎯 Цена опустилась до <b>{_money(lot.price)}</b> (ваш порог — {_money(target.target)})\n{_lot_line(lot)}"
                    sub.active = False
                sub.last_price = lot.price
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
