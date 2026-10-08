"""Письма по подпискам с сайта: подбор новых лотов, интервал, отписка (без обращения к D1 и Brevo)."""

from datetime import timedelta

from torgi import email_notify
from torgi.db import SessionLocal, init_db
from torgi.models import utcnow
from tests.test_bot import _lot


class FakeD1:
    def __init__(self, rows):
        self.rows = rows
        self.updates = []

    def query(self, sql, params=None):
        if sql.startswith("SELECT"):
            return self.rows
        self.updates.append(params)
        return []


class FakeClient:
    sent: list = []

    def __init__(self, **kw):
        pass

    def post(self, url, json):
        FakeClient.sent.append(json)
        return type("R", (), {"status_code": 201, "text": ""})()


def test_email_digest(monkeypatch):
    init_db()
    monkeypatch.setattr(email_notify.httpx, "Client", FakeClient)
    FakeClient.sent = []
    with SessionLocal() as session:
        now = utcnow()
        old = (now - timedelta(hours=5)).isoformat()
        recent = (now - timedelta(hours=1)).isoformat()
        _lot(session, "e1", price=15_000_000, region="Астана", city="Астана", first_seen_at=now - timedelta(hours=2))
        _lot(session, "e2", price=90_000_000, region="Астана", city="Астана", first_seen_at=now - timedelta(hours=2))
        rows = [
            {"id": 1, "email": "a@b.kz", "code": "q-ca-r1-x30", "token": "tok1", "checked_at": old},
            {"id": 2, "email": "c@d.kz", "code": "q-ca-r1", "token": "tok2", "checked_at": recent},  # рано
        ]
        d1 = FakeD1(rows)
        stats = email_notify.run(session, d1, "key", "https://api.test")
        session.rollback()

    assert stats == {"subscriptions": 2, "due": 1, "sent": 1}
    assert len(FakeClient.sent) == 1
    mail = FakeClient.sent[0]
    assert mail["to"] == [{"email": "a@b.kz"}]
    assert "Астана" in mail["subject"]
    assert "15 000 000" in mail["htmlContent"].replace("\xa0", " ") and "90 000 000" not in mail["htmlContent"]
    assert "https://api.test/api/email/unsubscribe?t=tok1" in mail["htmlContent"]
    assert "utm_source=email" in mail["htmlContent"]
    assert [p[1] for p in d1.updates] == [1]
