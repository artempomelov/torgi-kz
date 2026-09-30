"""Вход через Telegram, сессии и дневной лимит закрытых данных."""

import hashlib
import hmac
import time
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from torgi import auth
from torgi.api import app
from torgi.config import settings
from torgi.db import SessionLocal, init_db
from torgi.models import Lot, User, utcnow


def signed(data: dict, token: str = "123456:TEST-TOKEN") -> dict:
    check = "\n".join(f"{k}={data[k]}" for k in sorted(data))
    secret = hashlib.sha256(token.encode()).digest()
    return {**data, "hash": hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()}


def tg_user(uid: int = 777, **kw) -> dict:
    return signed({"id": uid, "first_name": "Артем", "username": "artem", "auth_date": int(time.time()), **kw})


def test_check_telegram_auth():
    data = tg_user()
    assert auth.check_telegram_auth(data, "123456:TEST-TOKEN")["id"] == "777"
    with pytest.raises(auth.AuthError):
        auth.check_telegram_auth({**data, "first_name": "Подмена"}, "123456:TEST-TOKEN")
    with pytest.raises(auth.AuthError):
        auth.check_telegram_auth(data, "999:OTHER")
    old = signed({"id": 1, "auth_date": int(time.time()) - 2 * 86400})
    with pytest.raises(auth.AuthError, match="устарели"):
        auth.check_telegram_auth(old, "123456:TEST-TOKEN")


def test_session_token():
    token = auth.make_session_token(42)
    assert auth.read_session_token(token) == 42
    payload, sig = token.rsplit(".", 1)
    assert auth.read_session_token(f"{payload}.{'0' * len(sig)}") is None
    assert auth.read_session_token(token, now=time.time() + (settings.session_days + 1) * 86400) is None
    assert auth.read_session_token("мусор") is None


def _make_lots(n: int) -> list[int]:
    init_db()
    ids = []
    with SessionLocal() as session:
        for i in range(n):
            lot = Lot(source="authtest", source_id=f"a{i}-{time.time_ns()}", url=f"https://example.kz/{i}",
                      title=f"Квартира {i}, ул. Секретная", origin="bank_balance", category="apartment",
                      address=f"ул. Секретная, {i}", contacts={"phone": "+7 700 000 00 00"}, price=10_000_000)
            session.add(lot)
            session.flush()
            ids.append(lot.id)
        session.commit()
    return ids


def test_details_limit_flow():
    ids = _make_lots(settings.free_details_per_day + 2)
    client = TestClient(app)

    assert client.get("/api/me").json()["authenticated"] is False
    assert client.get(f"/api/lots/{ids[0]}/details").status_code == 401
    assert client.post("/api/auth/telegram", json={**tg_user(), "hash": "bad"}).status_code == 401

    me = client.post("/api/auth/telegram", json=tg_user(uid=1001)).json()
    assert me["authenticated"] and me["name"] == "Артем" and me["remaining_today"] == settings.free_details_per_day

    limit = settings.free_details_per_day
    for i in range(limit):
        r = client.get(f"/api/lots/{ids[i]}/details")
        assert r.status_code == 200, r.text
        assert r.json()["address"].startswith("ул. Секретная")
        assert r.json()["remaining_today"] == limit - i - 1

    # повторное открытие того же лота лимит не тратит, новый лот — уже нельзя
    assert client.get(f"/api/lots/{ids[0]}/details").status_code == 200
    assert client.get(f"/api/lots/{ids[limit]}/details").status_code == 402
    assert client.get("/api/me").json()["remaining_today"] == 0

    # с подпиской — без ограничений
    with SessionLocal() as session:
        user = session.query(User).filter_by(telegram_id=1001).one()
        user.subscription_until = utcnow() + timedelta(days=30)
        session.commit()
    r = client.get(f"/api/lots/{ids[limit + 1]}/details")
    assert r.status_code == 200 and r.json()["remaining_today"] is None

    client.post("/api/auth/logout")
    assert client.get("/api/me").json()["authenticated"] is False
