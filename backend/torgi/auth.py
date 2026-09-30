"""Вход через Telegram Login Widget, сессии и дневной лимит бесплатных просмотров.

Проверка данных виджета — по документации Telegram:
    secret = SHA256(bot_token); hash == HMAC_SHA256(secret, "key=value\\n..." по алфавиту, без hash)
"""

import base64
import hashlib
import hmac
import json
import time
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from torgi.config import settings
from torgi.models import DetailView, User, utcnow

KZ_TZ = timezone(timedelta(hours=5))
AUTH_MAX_AGE = 24 * 3600  # данные виджета старше суток не принимаем
COOKIE_NAME = "torgi_session"


class AuthError(Exception):
    pass


# --- Telegram Login Widget ----------------------------------------------------------

def check_telegram_auth(data: dict, bot_token: str, now: float | None = None) -> dict:
    """Проверяет подпись данных виджета; возвращает их без hash или бросает AuthError."""
    fields = {k: str(v) for k, v in data.items() if v is not None}
    received = fields.pop("hash", None)
    if not received:
        raise AuthError("нет подписи")
    check_string = "\n".join(f"{k}={fields[k]}" for k in sorted(fields))
    secret = hashlib.sha256(bot_token.encode()).digest()
    expected = hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, received):
        raise AuthError("неверная подпись")
    if (now or time.time()) - int(fields.get("auth_date", 0)) > AUTH_MAX_AGE:
        raise AuthError("данные входа устарели")
    return fields


def upsert_user(session: Session, tg: dict) -> User:
    user = session.scalar(select(User).where(User.telegram_id == int(tg["id"])))
    if user is None:
        user = User(telegram_id=int(tg["id"]))
        session.add(user)
    user.first_name = tg.get("first_name")
    user.last_name = tg.get("last_name")
    user.username = tg.get("username")
    user.photo_url = tg.get("photo_url")
    user.last_login_at = utcnow()
    session.commit()
    return user


# --- Сессии: подписанный токен "base64(json).подпись" в httpOnly-cookie --------------

def _sign(payload: bytes) -> str:
    return hmac.new(settings.secret_key.encode(), payload, hashlib.sha256).hexdigest()


def make_session_token(user_id: int, now: float | None = None) -> str:
    exp = int((now or time.time()) + settings.session_days * 86400)
    payload = base64.urlsafe_b64encode(json.dumps({"uid": user_id, "exp": exp}).encode())
    return f"{payload.decode()}.{_sign(payload)}"


def read_session_token(token: str | None, now: float | None = None) -> int | None:
    if not token or "." not in token:
        return None
    payload, signature = token.rsplit(".", 1)
    if not hmac.compare_digest(_sign(payload.encode()), signature):
        return None
    try:
        data = json.loads(base64.urlsafe_b64decode(payload))
    except ValueError:
        return None
    if data.get("exp", 0) < (now or time.time()):
        return None
    return int(data["uid"])


# --- Дневной лимит ------------------------------------------------------------------

def today_kz(now: datetime | None = None) -> str:
    return (now or utcnow()).astimezone(KZ_TZ).date().isoformat()


def views_today(session: Session, user: User, day: str | None = None) -> int:
    return session.scalar(
        select(func.count()).select_from(DetailView).where(DetailView.user_id == user.id,
                                                            DetailView.day == (day or today_kz()))
    ) or 0


def grant_details(session: Session, user: User, lot_id: int) -> tuple[bool, int]:
    """Можно ли показать закрытые данные лота. Возвращает (разрешено, осталось бесплатных сегодня).

    Подписка — без ограничений. Повторное открытие того же лота в тот же день лимит не тратит.
    """
    day = today_kz()
    used = views_today(session, user, day)
    limit = settings.free_details_per_day
    if user.has_subscription():
        return True, limit
    already = session.scalar(select(DetailView.id).where(
        DetailView.user_id == user.id, DetailView.lot_id == lot_id, DetailView.day == day))
    if already:
        return True, max(0, limit - used)
    if used >= limit:
        return False, 0
    session.add(DetailView(user_id=user.id, lot_id=lot_id, day=day))
    session.commit()
    return True, limit - used - 1
