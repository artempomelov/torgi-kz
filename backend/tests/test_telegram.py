from datetime import datetime, timezone

from torgi.models import Lot
from torgi.telegram import format_post


def test_format_post():
    lot = Lot(
        id=42, source="adilet", category="apartment", origin="arrested", sale_type="auction_down",
        city="Алматы", address="г. Алматы, Алмалинский район, ул. Кашгарская, д.3, кв. 12", rooms=3, area_m2=57.5,
        price=42_596_700, price_per_m2=740_812, deposit=2_129_835,
        auction_start=datetime(2026, 10, 1, 5, 0, tzinfo=timezone.utc),
    )
    text = format_post(lot)
    assert text.startswith("🏢 <b>Квартира, 3-комн., 57,5 м² — Алматы</b>")
    assert "42 596 700 ₸" in text
    assert "📍 Алматы, Алмалинский район" in text and "Кашгарская" not in text  # точный адрес — только на сайте
    assert "🔨 Аукцион на понижение · Арестованное имущество\n" in text
    assert "Минюст" not in text  # источник — только на сайте
    assert "Торги: 1 октября, 10:00" in text  # UTC+5
    assert 'href="https://torgi.kz/lots/42/?utm_source=telegram&amp;utm_medium=channel' in text
    assert "#Алматы #квартира #арест" in text
    assert len(text) <= 1024


def test_benefits_and_channel_rules():
    from torgi.models import PriceChange
    from torgi.telegram import matches_channel

    lot = Lot(id=7, source="sauda", category="apartment", origin="state", sale_type="auction_down", city="Астана",
              region="Астана", price=8_000_000, price_per_m2=200_000, min_price=4_000_000, area_m2=40)
    lot.price_history = [PriceChange(price=10_000_000), PriceChange(price=8_000_000)]
    text = format_post(lot, {("apartment", "Астана"): 400_000}, footer="FOOTER").replace("\xa0", " ")
    assert "📉 <b>Цена снижена на 20%</b> — выгода 2 000 000 ₸" in text
    assert "цена может опуститься до 4 000 000 ₸ (−50%)" in text
    assert "🔥 За м² на 50% дешевле медианы по городу" in text
    assert text.endswith("FOOTER")
    assert matches_channel(lot, {"region": "Астана"}) and not matches_channel(lot, {"region": ["Алматы"]})
    assert matches_channel(lot, {"category": ["apartment", "house"]}) and not matches_channel(lot, {"category": "land"})


def test_about_fits_limits_and_updates_only_changed():
    from torgi import telegram

    about = telegram.channel_about(123_456)  # с самым длинным числом объектов
    assert all(len(text) <= 255 for text in about.values())
    assert len(telegram.BOT_SHORT_ABOUT) <= 120
    assert all(telegram.INSTAGRAM in text and "torgi.kz ·" in text for text in about.values())
    assert "более 123 400 объектов" in about["@torgi_kz_news"] and "@torgi_kz_news" in about["@torgi_kz_biz"]

    class FakeBot:
        def __init__(self):
            self.calls = []

        def call(self, method, **params):
            self.calls.append((method, params))
            if method == "getChat":  # у основного канала описание уже актуальное
                same = params["chat_id"] == "@torgi_kz_news"
                return {"description": about[params["chat_id"]] if same else "старое"}
            if method == "setChatDescription" and params["chat_id"] == "@torgi_kz_biz":
                raise RuntimeError("Telegram setChatDescription: not enough rights")
            if method == "getMyShortDescription":
                return {"short_description": telegram.BOT_SHORT_ABOUT}
            return True

    bot = FakeBot()
    assert telegram.set_about(bot, 123_456) == ["@torgi_kz_auto", "@torgi_kz_almaty", "@torgi_kz_astana"]
    assert not any(m == "setMyShortDescription" for m, _ in bot.calls)


def test_main_channel_mix():
    """Основной канал: 70% квартир Алматы и Астаны (в том числе ещё не опубликованных старых), 20% коммерции,
    10% паркомест и земли; дома и квартиры в регионах не идут; нет квартир — посты не добиваются землёй."""
    from datetime import timedelta

    from sqlalchemy import select

    from torgi import telegram
    from torgi.db import SessionLocal, init_db
    from torgi.models import ChannelPost, utcnow

    init_db()
    ch = "@mix_test"
    with SessionLocal() as session:
        now = utcnow()
        # лоты других тестов в общей базе — «опубликованы давно», в выборку и счёт долей не попадают
        session.add_all(ChannelPost(lot_id=lot_id, channel=ch, message_id=0, posted_at=now - timedelta(days=30))
                        for lot_id in session.scalars(select(Lot.id)))

        def lot(i, category, region="Алматы", days=0, images=("p",), address=None):
            x = Lot(source="mix", source_id=str(i), url="u", origin="bank_pledge", category=category, title="t",
                    city=region, region=region, address=address, price=10_000_000, status="active",
                    images=list(images), flags=[],
                    contacts={}, extra={}, first_seen_at=now - timedelta(days=days), last_seen_at=now, updated_at=now)
            session.add(x)
            return x

        flats = [lot(i, "apartment", "Астана" if i % 2 else "Алматы") for i in range(3)]
        old_flat = lot(10, "apartment", days=30)  # старая, помечена при первом запуске, но не опубликована
        twins = [lot(60 + i, "apartment", "Астана", address=f"Астана, ул. Шамши Калдаякова, д. 11, кв. {i}")
                 for i in range(2)]  # серия банка в одном доме — в день берём одну
        lot(11, "apartment", "Караганда")
        lot(12, "house")
        shops = [lot(20 + i, "commercial") for i in range(5)]
        land = [lot(30 + i, "land", days=1) for i in range(20)]
        session.flush()
        session.add(ChannelPost(lot_id=old_flat.id, channel=ch, message_id=None))
        # за неделю в канал ушла одна земля
        session.add(ChannelPost(lot_id=land[0].id, channel=ch, message_id=1))
        session.commit()

        picked = telegram.mixed_lots(session, ch, 10, since_days=3)
        cats = [x.category for x in picked]
        assert old_flat in picked and set(flats) <= set(picked) and len(set(twins) & set(picked)) == 1
        assert cats.count("apartment") == 5 and all(x.region in ("Алматы", "Астана") for x in picked if x.category == "apartment")
        assert "house" not in cats and cats.count("land") == 0  # земля уже набрала свою долю
        # квартиры кончились — коммерции не больше её доли, остальные слоты пустуют
        assert 1 <= cats.count("commercial") <= 2 and len(picked) < 10
        assert all(x in shops for x in picked if x.category == "commercial")
