"""Бот подписок: разбор кодов со ссылок сайта, оформление подписок и уведомления (без обращения к Telegram)."""

from datetime import timedelta

from torgi import bot
from torgi.bot import Lead, LotWatch, SearchFilter, parse_code
from torgi.db import SessionLocal, init_db
from torgi.models import Lot, PriceChange, Subscription, utcnow


def test_parse_code():
    f = parse_code("q-cah-r0-x30-m400-oz")
    assert isinstance(f, SearchFilter)
    assert f.categories == ["apartment", "house"] and f.regions == ["Алматы"]
    assert (f.price_max, f.ppm_max, f.origins) == (30_000_000, 400_000, ["bank_pledge"])
    assert f.describe() == "Квартиры, Дома · Алматы · до 30 млн ₸ · до 400 тыс. ₸/м² · залоговое имущество"
    assert "category=apartment&category=house&region=" in f.catalog_url()
    assert parse_code("lot-123") == LotWatch(123)
    assert parse_code("lot-123-t5000") == LotWatch(123, 5_000_000)
    assert parse_code("c-7") == Lead("consult", 7) and parse_code("check-7") == Lead("check", 7)
    assert parse_code("c") == Lead("consult")
    assert parse_code("q-r0_1").regions == ["Алматы", "Астана"]
    down = parse_code("q-ca-tdp")
    assert down.sale_types == ["auction_down", "direct"] and down.describe().endswith("аукцион на понижение, прямая продажа")
    assert "sale_type=auction_down&sale_type=direct" in down.catalog_url()
    assert not down.matches(Lot(category="apartment", sale_type="auction", flags=[]))
    assert down.matches(Lot(category="apartment", sale_type="direct", flags=[]))
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


def test_leads_and_target_price(capsys, monkeypatch):
    from torgi.config import settings

    monkeypatch.setattr(settings, "telegram_admins", "boss")
    init_db()
    with SessionLocal() as session:
        b = bot.Bot(dry_run=True)
        lot = _lot(session, "lead1", price=10_000_000)
        user = {"id": 2002, "first_name": "Покупатель", "username": "buyer"}
        # заявка до того, как админ написал боту, — ждёт в очереди
        bot.handle_message(session, b, 2002, f"/start check-{lot.id}", utcnow(), user)
        out = capsys.readouterr().out
        assert "--> 2002" in out and "бесплатную консультацию" in out
        bot.handle_message(session, b, 3003, "/start", utcnow(), {"id": 3003, "username": "Boss"})
        out = capsys.readouterr().out
        assert "--> 3003" in out and "📩 Заявка: <b>консультация по лоту</b>" in out and "@buyer" in out
        # вопрос пользователя — сразу админу
        bot.handle_message(session, b, 2002, "Есть ли обременения?", utcnow(), user)
        out = capsys.readouterr().out
        assert "--> 3003" in out and "Есть ли обременения?" in out

        # порог цены: о снижении до 9 млн не сообщаем, о 7 млн — сообщаем и отключаем
        bot.handle_message(session, b, 2002, f"/start lot-{lot.id}-t8000", utcnow(), user)
        lot.price = 9_000_000
        capsys.readouterr()
        bot.notify(session, b, utcnow())
        assert "🎯" not in capsys.readouterr().out
        lot.price = 7_000_000
        bot.notify(session, b, utcnow())
        assert "🎯 Цена опустилась до" in capsys.readouterr().out.replace(" ", " ")
        session.rollback()


def test_admin_replies_through_bot(capsys, monkeypatch):
    from torgi.config import settings

    monkeypatch.setattr(settings, "telegram_admins", "boss")
    monkeypatch.setattr(settings, "telegram_channel", "@torgi_kz_news")
    monkeypatch.setattr(settings, "telegram_channels", '{"@torgi_kz_almaty": {"region": "Алматы"}}')
    init_db()
    with SessionLocal() as session:
        b = bot.Bot(dry_run=True)
        lot = _lot(session, "reply1", price=5_405, address="г. Актобе, ул. Бопай ханым", deposit=216_250)
        admin = {"id": 3003, "username": "boss"}
        bot.handle_message(session, b, 3003, "/start", utcnow(), admin)
        capsys.readouterr()
        bot.handle_message(session, b, 2002, f"/start check-{lot.id}", utcnow(), {"id": 2002, "username": "ken"})
        out = capsys.readouterr().out
        # сообщения в dry-run нумеруются: 1 — приветствие админу, 2 — заявка админу, 3 — ответ клиенту
        assert "Ответьте на это сообщение" in out
        bot.handle_message(session, b, 3003, "Добрый вечер! Посмотрели лот.", utcnow(), admin, reply_to=2)
        out = capsys.readouterr().out
        assert "--> 2002\nДобрый вечер! Посмотрели лот." in out and "✅ Отправлено" in out
        bot.handle_message(session, b, 3003, "/info", utcnow(), admin, reply_to=2)
        out = capsys.readouterr().out.replace("\xa0", " ")
        assert "--> 2002\nЗдравствуйте! Вы оставляли заявку на сайте torgi.kz" in out
        assert "Бопай ханым" in out and "216 250" in out
        assert "Подписывайтесь на" in out and "t.me/torgi_kz_news" in out and "t.me/torgi_kz_almaty" in out
        bot.handle_message(session, b, 3003, "текст", utcnow(), admin, reply_to=999)
        assert "Не нашёл, кому ответить" in capsys.readouterr().out
        session.rollback()


def test_lead_without_lot_and_info2(capsys, monkeypatch):
    """Заявка без лота: администратор отвечает /info2 — клиенту уходит стандартный ответ о сайте;
    клиент присылает номер лота у продавца — лот привязывается к переписке, /info работает."""
    from torgi.config import settings

    monkeypatch.setattr(settings, "telegram_admins", "boss")
    monkeypatch.setattr(settings, "telegram_channel", "@torgi_kz_news")
    init_db()
    with SessionLocal() as session:
        b = bot.Bot(dry_run=True)
        lot = _lot(session, "info2", extra={"lot_number": "778899"}, address="г. Астана, ул. Сыганак, 12")
        admin = {"id": 3003, "username": "boss"}
        bot.handle_message(session, b, 3003, "/start", utcnow(), admin)
        capsys.readouterr()
        bot.handle_message(session, b, 4004, "/start c", utcnow(), {"id": 4004, "first_name": "Айгерим"})
        out = capsys.readouterr().out
        # 1 — приветствие админу, 2 — заявка админу, 3 — «заявка принята» клиенту (без стандартного ответа)
        assert "общая консультация (без лота)" in out and "Ответьте /info2" in out
        assert "--> 4004\nЗаявка на бесплатную консультацию принята" in out and "спасибо за обращение" not in out
        bot.handle_message(session, b, 3003, "/info", utcnow(), admin, reply_to=2)
        assert "не привязан лот — ответьте /info2" in capsys.readouterr().out
        bot.handle_message(session, b, 3003, "/info2", utcnow(), admin, reply_to=2)
        out = capsys.readouterr().out.replace("\xa0", " ")
        assert "--> 4004\nЗдравствуйте, спасибо за обращение!" in out and "«Сохранить поиск»" in out
        assert "пришлите ссылку на него или номер" in out and "✅ Отправлено" in out

        bot.handle_message(session, b, 4004, "Интересует лот № 778899", utcnow(), {"id": 4004, "first_name": "Айгерим"})
        out = capsys.readouterr().out
        assert "Похоже, речь о лоте" in out and f"/lots/{lot.id}/" in out and "Ответьте /info" in out
        # 4 — «не привязан лот», 5–6 — стандартный ответ и «отправлено», 7 — вопрос клиента администратору
        bot.handle_message(session, b, 3003, "/info", utcnow(), admin, reply_to=7)
        assert "--> 4004\nЗдравствуйте! Вы оставляли заявку" in capsys.readouterr().out
        session.rollback()


def test_admin_reply_to_old_lead(capsys, monkeypatch):
    """Старая заявка (до сохранения переписок): клиент и лот — из ссылок в самом сообщении."""
    from torgi.config import settings

    monkeypatch.setattr(settings, "telegram_admins", "boss")
    init_db()
    with SessionLocal() as session:
        b = bot.Bot(dry_run=True)
        lot = _lot(session, "old1", price=5_405)
        admin = {"id": 3003, "username": "boss"}
        bot.handle_message(session, b, 3003, "/start", utcnow(), admin)
        capsys.readouterr()
        old = {"message_id": 777, "text": "📩 Заявка: бесплатная проверка лота от Ken @kendevelopment",
               "entities": [{"type": "text_link", "offset": 0, "length": 3, "url": "tg://user?id=5551234"},
                            {"type": "text_link", "offset": 5, "length": 5,
                             "url": f"https://torgi.kz/lots/{lot.id}/?utm_source=telegram&utm_medium=bot"}]}
        bot.handle_message(session, b, 3003, "/info", utcnow(), admin, reply_to=old)
        out = capsys.readouterr().out
        assert "--> 5551234\nЗдравствуйте! Вы оставляли заявку" in out and "✅ Отправлено" in out
        session.rollback()


def test_thread_from_plain_client_id():
    # ссылку на профиль Telegram убрал (приватность клиента) — ID берём из текста
    msg = {"text": "📩 Заявка: бесплатная проверка лота от Ken @kendevelopment · ID 5551234\n• Участок",
           "entities": [{"type": "text_link", "offset": 0, "length": 5, "url": "https://torgi.kz/lots/3763/?utm_source=telegram"}]}
    assert bot.thread_from_message(msg) == {"chat": 5551234, "lot": 3763}


def test_channel_member_report(capsys, monkeypatch):
    from datetime import datetime, timezone

    from torgi.config import settings

    monkeypatch.setattr(settings, "telegram_admins", "boss")
    init_db()
    with SessionLocal() as session:
        b = bot.Bot(dry_run=True)
        bot.handle_message(session, b, 3003, "/start", utcnow(), {"id": 3003, "username": "boss"})
        chat = {"id": -100, "type": "channel", "username": "torgi_kz_news", "title": "torgi.kz"}

        def upd(old, new, uid, name):
            return {"chat": chat, "date": 1, "old_chat_member": {"status": old},
                    "new_chat_member": {"status": new, "user": {"id": uid, "first_name": name, "username": name.lower()}}}

        bot.record_member_event(session, upd("left", "member", 1, "Aru"))
        bot.record_member_event(session, upd("member", "left", 2, "Ken"))
        bot.record_member_event(session, upd("member", "administrator", 3, "Admin"))  # не подписка
        capsys.readouterr()
        # до 9:00 по Алматы сводки нет, после — одна в день
        assert not bot.member_report(session, b, datetime(2026, 10, 16, 2, 0, tzinfo=timezone.utc))
        assert bot.member_report(session, b, datetime(2026, 10, 16, 5, 0, tzinfo=timezone.utc))
        out = capsys.readouterr().out
        assert "@torgi_kz_news</b>: +1 / −1" in out and "➕ Aru @aru" in out and "➖ Ken @ken" in out
        assert "Admin" not in out
        assert not bot.member_report(session, b, datetime(2026, 10, 16, 8, 0, tzinfo=timezone.utc))
        session.rollback()
