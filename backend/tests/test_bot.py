"""Бот подписок: разбор кодов со ссылок сайта, оформление подписок и уведомления (без обращения к Telegram)."""

from datetime import timedelta

from torgi import bot
from torgi.bot import SearchFilter, parse_code
from torgi.db import SessionLocal, init_db
from torgi.models import Lot, PriceChange, Subscription, utcnow


def test_parse_code():
    f = parse_code("q-cah-r0-x30-m400-oz")
    assert isinstance(f, SearchFilter)
    assert f.categories == ["apartment", "house"] and f.region == "Алматы"
    assert (f.price_max, f.ppm_max, f.origins) == (30_000_000, 400_000, ["bank_pledge"])
    assert f.describe() == "Квартиры, Дома · Алматы · до 30 млн ₸ · до 400 тыс. ₸/м² · залоговое имущество"
    assert "category=apartment&category=house&region=" in f.catalog_url()
    assert parse_code("lot-123") == 123
    assert parse_code("q-r99") is None and parse_code("hello world") is None and parse_code("abc") is None


def _lot(session, source_id: str, **kw) -> Lot:
    now = utcnow()
    data = dict(source="fake", source_id=source_id, url="u", origin="bank_pledge", category="apartment",
                title="t", city="Алматы", region="Алматы", price=20_000_000, status="active",
                first_seen_at=now, last_seen_at=now, updated_at=now, images=[], flags=[], contacts={}, extra={})
    lot = Lot(**{**data, **kw})
    lot.price_history.append(PriceChange(price=lot.price, seen_at=now))
    session.add(lot)
    session.flush()
    return lot


def test_subscribe_and_notify(capsys):
    init_db()
    with SessionLocal() as session:
        b = bot.Bot(dry_run=True)
        t0 = utcnow() - timedelta(hours=2)
        bot.handle_message(session, b, 1001, "/start q-ca-r0-x30", t0)
        watched = _lot(session, "w1", price=25_000_000)
        bot.handle_message(session, b, 1001, f"/start lot-{watched.id}", t0)
        session.flush()
        subs = session.query(Subscription).filter_by(chat_id=1001).all()
        assert len(subs) == 2 and all(s.active for s in subs)

        _lot(session, "n1", price=15_000_000)                      # подходит
        _lot(session, "n2", price=50_000_000)                      # дороже лимита
        _lot(session, "n3", region="Астана", city="Астана")        # другой город
        watched.price = 22_000_000
        capsys.readouterr()
        bot.notify(session, b, utcnow())
        out = capsys.readouterr().out.replace(" ", " ")
        assert out.count("🆕 Новые объекты") == 1 and "15 000 000 ₸" in out and "50 000 000" not in out
        assert "📉 Цена снижена на 12%" in out

        bot.handle_message(session, b, 1001, "/stop", utcnow())
        assert not any(s.active for s in session.query(Subscription).filter_by(chat_id=1001))
        session.rollback()
