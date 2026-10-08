"""Письма о новых лотах по сохранённому поиску (Brevo).

    uv run python -m torgi.cli email [--dry-run]

Подписки лежат в Cloudflare D1 (таблица email_subs): их оформляет и подтверждает worker/src/index.js.
Код фильтра — тот же, что у Telegram-бота (q-…), поэтому подбор лотов общий: bot.SearchFilter.
Нужны CLOUDFLARE_API_TOKEN, CLOUDFLARE_ACCOUNT_ID, CF_D1_DATABASE_ID, BREVO_API_KEY и TORGI_API_URL
(адрес worker — для ссылки «отписаться»).
"""

import html
import logging
import os
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from torgi.bot import SearchFilter, parse_code
from torgi.cloudflare import D1
from torgi.config import settings
from torgi.models import Lot, utcnow
from torgi.normalize import CATEGORIES
from torgi.telegram import _money

log = logging.getLogger(__name__)

BREVO_URL = "https://api.brevo.com/v3/smtp/email"
MIN_INTERVAL = timedelta(hours=3)  # не чаще одного письма на подписку раз в 3 часа — новые лоты копятся
PER_EMAIL = 10  # лотов в письме, остальные — ссылкой на каталог
MAX_PER_RUN = 100  # бесплатный тариф Brevo — 300 писем в день, запусков дважды в час


def _utc(dt: datetime) -> datetime:
    """Время с часовым поясом UTC — так его хранит модель."""
    return dt.astimezone(timezone.utc) if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _lot_row(lot: Lot) -> str:
    title = CATEGORIES.get(lot.category, "Объект")
    if lot.area_m2:
        title += f", {lot.area_m2:g} м²".replace(".", ",")
    place = lot.city or lot.region or ""
    price = _money(lot.price) if lot.price else "цена не указана"
    url = f"{settings.site_url}/lots/{lot.id}/?utm_source=email&utm_medium=search"
    img = (f'<img src="{html.escape(lot.images[0])}" width="96" height="72" '
           f'style="object-fit:cover;border-radius:6px;display:block" alt="">' if lot.images else "")
    return (f'<tr><td style="padding:8px 12px 8px 0;vertical-align:top">{img}</td>'
            f'<td style="padding:8px 0;vertical-align:top"><a href="{html.escape(url)}" style="color:#1f3fd1;font-weight:600">'
            f'{html.escape(title)}</a><br><span style="color:#5b6b73">{html.escape(place)}</span><br><b>{price}</b></td></tr>')


def render(f: SearchFilter, lots: list[Lot], unsubscribe: str) -> tuple[str, str]:
    n = len(lots)
    subject = f"Новые объекты на торгах: {f.describe()}"
    catalog = f.catalog_url().replace("utm_source=telegram", "utm_source=email").replace("utm_medium=bot", "utm_medium=search")
    more = (f'<p><a href="{html.escape(catalog)}" style="color:#1f3fd1">Ещё {n - PER_EMAIL} в каталоге →</a></p>'
            if n > PER_EMAIL else "")
    body = f"""<div style="font-family:system-ui,sans-serif;max-width:560px;color:#111">
<p style="font-size:13px;color:#5b6b73">torgi.kz — недвижимость с торгов Казахстана</p>
<h2 style="font-size:18px;margin:0 0 8px">{html.escape(f.describe())}</h2>
<p>Новых объектов по вашему поиску: <b>{n}</b></p>
<table cellpadding="0" cellspacing="0">{''.join(_lot_row(lot) for lot in lots[:PER_EMAIL])}</table>
{more}
<p style="margin-top:24px"><a href="{html.escape(catalog)}" style="display:inline-block;background:#1f3fd1;color:#fff;padding:10px 18px;border-radius:8px;text-decoration:none">Открыть поиск в каталоге</a></p>
<p style="font-size:12px;color:#5b6b73;margin-top:24px">Вы получили письмо, потому что подписались на поиск на torgi.kz.
<a href="{html.escape(unsubscribe)}" style="color:#5b6b73">Отписаться</a></p></div>"""
    return subject, body


def run(session: Session, d1: D1, api_key: str, api_url: str, dry_run: bool = False) -> dict[str, int]:
    now = utcnow()
    subs = d1.query("SELECT id, email, code, token, checked_at FROM email_subs WHERE confirmed = 1")
    due = []
    for sub in subs:
        checked = _utc(datetime.fromisoformat(sub["checked_at"])) if sub["checked_at"] else now
        if now - checked >= MIN_INTERVAL:
            due.append((sub, checked))
    stats = {"subscriptions": len(subs), "due": len(due), "sent": 0}
    if not due:
        return stats
    oldest = min(checked for _, checked in due)
    fresh = session.scalars(
        select(Lot).where(Lot.status == "active", Lot.first_seen_at > oldest).order_by(Lot.first_seen_at.desc())
    ).all()
    client = httpx.Client(timeout=30, headers={"api-key": api_key, "Accept": "application/json"})
    for sub, checked in due:
        f = parse_code(sub["code"])
        if not isinstance(f, SearchFilter):
            continue
        new = [lot for lot in fresh if _utc(lot.first_seen_at) > checked and f.matches(lot)]
        if new:
            if stats["sent"] >= MAX_PER_RUN:
                break  # остальные — в следующий запуск, checked_at не трогаем
            subject, body = render(f, new, f"{api_url}/api/email/unsubscribe?t={sub['token']}")
            if dry_run:
                log.info("письмо %s: %s (%d)", sub["email"], subject, len(new))
            else:
                res = client.post(BREVO_URL, json={
                    "sender": {"name": "torgi.kz", "email": os.environ.get("EMAIL_FROM", "noreply@torgi.kz")},
                    "to": [{"email": sub["email"]}],
                    "subject": subject,
                    "htmlContent": body,
                })
                if res.status_code >= 300:
                    log.warning("Brevo %s: %s", res.status_code, res.text[:200])
                    continue
            stats["sent"] += 1
        if not dry_run:
            d1.query("UPDATE email_subs SET checked_at = ? WHERE id = ?", [now.isoformat(), sub["id"]])
    return stats


def run_from_env(session: Session, dry_run: bool = False) -> dict[str, int]:
    keys = ("CLOUDFLARE_API_TOKEN", "CLOUDFLARE_ACCOUNT_ID", "CF_D1_DATABASE_ID", "BREVO_API_KEY", "TORGI_API_URL")
    env = {k: os.environ.get(k) for k in keys}
    if missing := [k for k, v in env.items() if not v]:
        raise SystemExit(f"Не заданы: {', '.join(missing)}")
    d1 = D1(env["CLOUDFLARE_API_TOKEN"], env["CLOUDFLARE_ACCOUNT_ID"], env["CF_D1_DATABASE_ID"])
    return run(session, d1, env["BREVO_API_KEY"], env["TORGI_API_URL"].rstrip("/"), dry_run)
