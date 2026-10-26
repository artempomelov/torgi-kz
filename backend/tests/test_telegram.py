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
    text = format_post(lot, footer="FOOTER").replace("\xa0", " ")
    assert "📉 <b>Цена снижена на 20%</b> — выгода 2 000 000 ₸" in text
    assert "цена может опуститься до 4 000 000 ₸ (−50%)" in text
    assert "🔥" not in text  # без оценки рынка — без строки о скидке (сравнения с медианой торгов больше нет)
    badge = {"pct": 34, "over": False, "where": "в районе Сарыарка"}
    with_badge = format_post(lot, badge=badge)
    assert "🔥 Цена на 34% ниже рынка\n" in with_badge and "Сарыарка" not in with_badge.split("🔥")[1].split("\n")[0]
    assert "🔥 Цена более чем на 30% ниже рынка" in format_post(lot, badge={"pct": 30, "over": True, "where": "в г. Актау"})
    assert text.endswith("FOOTER")
    assert matches_channel(lot, {"region": "Астана"}) and not matches_channel(lot, {"region": ["Алматы"]})
    assert matches_channel(lot, {"category": ["apartment", "house"]}) and not matches_channel(lot, {"category": "land"})


def test_about_fits_limits_and_updates_only_changed():
    from torgi import telegram

    about = telegram.channel_about(123_456)  # с самым длинным числом объектов
    assert all(len(text) <= 255 for text in about.values())
    assert len(telegram.BOT_SHORT_ABOUT) <= 120
    assert all(telegram.INSTAGRAM in text and "torgi.kz ·" in text for text in about.values())
    assert "3 000+ объектов" in about["@torgi_kz_news"] and "@torgi_kz_news" in about["@torgi_kz_biz"]

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
    """Основной канал: из 6 постов 4 квартиры Алматы и Астаны, 1 машина, 1 коммерция или квартира в регионах;
    дома и земля не идут; внутри категории — сначала лоты с плашкой «−N% к рынку». Городской канал — тоже сначала
    с плашкой, потом остальные; ещё не опубликованные старые лоты — тоже кандидаты."""
    from datetime import timedelta

    from sqlalchemy import select

    from torgi import telegram
    from torgi.db import SessionLocal, init_db
    from torgi.models import ChannelPost, utcnow

    init_db()
    ch, city = "@mix_test", "@mix_city_test"
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
        plain = lot(13, "apartment")  # без оценки рынка — без плашки, идёт после лотов с плашкой
        regional = lot(11, "apartment", "Караганда")
        house = lot(12, "house")
        shops = [lot(20 + i, "commercial") for i in range(5)]
        land = [lot(30 + i, "land", days=1) for i in range(20)]
        cars = [lot(80 + i, "vehicle", days=i, images=("p",) * 3) for i in range(3)]
        for car in cars:
            car.extra = {"vehicle_type": "car", "year": now.year - 2}
        cars[0].extra = {**cars[0].extra, "note": "имеются обременения"}  # в основной канал не идёт
        session.flush()
        session.add(ChannelPost(lot_id=old_flat.id, channel=ch, message_id=None))
        # сегодня в канал уже ушла земля — по новой смеси она не считается
        session.add(ChannelPost(lot_id=land[0].id, channel=ch, message_id=1))
        session.commit()
        badge = {"pct": 20, "over": False, "where": "в г. Алматы"}
        badges = {x.id: badge for x in (*flats, old_flat, *twins, regional, house, shops[0])}

        picked = telegram.mixed_lots(session, ch, 6, badges)
        cats = [x.category for x in picked]
        city_flats = [x for x in picked if x.category == "apartment" and x.region in ("Алматы", "Астана")]
        assert len(city_flats) == 4 and all(x.id in badges for x in city_flats) and len(set(twins) & set(picked)) == 1
        assert house not in picked and "land" not in cats
        assert cats.count("vehicle") == 1 and picked[cats.index("vehicle")] == cars[1]  # свежая машина без обременений
        assert shops[0] in picked and len(picked) == 6  # коммерция с плашкой — раньше коммерции без неё
        assert old_flat in telegram.candidate_lots(session, ch, badges)  # помечена при первом запуске, не опубликована

        in_city = telegram.channel_lots(session, city, 50, {"region": "Алматы"}, badges)
        assert plain in in_city and not set(cars) & set(in_city) and all(x.region == "Алматы" for x in in_city)
        first_plain = next(i for i, x in enumerate(in_city) if x.id not in badges)
        assert all(x.id in badges for x in in_city[:first_plain]) and house in in_city[:first_plain]
        assert not any(x.id in badges for x in in_city[first_plain:])


def test_market_badge_on_photo(tmp_path):
    """Плашка «−N% к рынку» на главном фото: из выгрузки сайта, цвет как на сайте, рисуется в левом верхнем углу."""
    import json

    import pytest
    from PIL import Image

    from torgi import badge

    path = tmp_path / "lots.json"
    path.write_text(json.dumps([{"id": 1, "market": {"pct": 14, "over": False, "where": "в г. Актау"}},
                                {"id": 2, "market": None}]), encoding="utf-8")
    badges = badge.load_badges(path)
    assert badges == {1: {"pct": 14, "over": False, "where": "в г. Актау"}}
    assert badge.load_badges(tmp_path / "нет.json") == {}
    assert badge.label(badges[1]) == "−14% к рынку" and badge.colors(badges[1])[0] == badge.YELLOW
    assert badge.label({"pct": 30, "over": True}) == "более −30% к рынку"
    assert badge.colors({"pct": 16, "over": False})[0] == badge.RED
    if badge._font(20) is None:
        pytest.skip("нет шрифта")
    img = badge.draw(Image.new("RGB", (800, 600), "white"), {"pct": 34, "over": False})
    assert img.getpixel((40, 40)) == (225, 29, 72)  # красная плашка у левого верхнего угла


def test_three_batches_a_day():
    """По 2 поста в канал в 10:00, 14:00 и 19:00 по Алматы (UTC+5)."""
    from torgi.telegram import slot_quota

    def at(hour):
        return datetime(2026, 10, 21, hour - 5, 15, tzinfo=timezone.utc)

    assert [slot_quota(at(h)) for h in (9, 10, 13, 14, 18, 19, 20)] == [0, 2, 2, 4, 4, 6, 6]


def test_bank_slide_goes_last(monkeypatch):
    """Рекламный слайд банка первой картинкой уходит в конец: обложка и плашка — на фото объекта."""
    from PIL import Image, ImageDraw

    from torgi import promo

    slide = Image.new("RGB", (800, 600), "#0b2a1f")
    ImageDraw.Draw(slide).rectangle((0, 0, 400, 120), fill="white")
    photo = Image.effect_noise((800, 600), 80).convert("RGB")  # «фото» с деталями — не похоже на слайд
    monkeypatch.setattr(promo, "SLIDES", {promo.dhash(slide): "тест"})
    pictures = {"slide.jpg": slide.resize((1200, 900)), "room.jpg": photo, "kitchen.jpg": photo.rotate(90)}
    monkeypatch.setattr(promo, "_download", lambda url, client: pictures[url])

    lot = Lot(images=["slide.jpg", "room.jpg", "kitchen.jpg"], extra={"note": "x"})
    assert promo.check_cover(lot, None)
    assert lot.images == ["room.jpg", "kitchen.jpg", "slide.jpg"]
    assert lot.extra == {"note": "x", "promo_images": ["slide.jpg"], "cover_checked": "room.jpg"}
    assert not promo.check_cover(lot, None)  # уже проверено — фото больше не скачиваем
    # источник прислал фото в старом порядке — известный слайд снова в конце
    assert promo.promo_last(["slide.jpg", "room.jpg"], set(lot.extra["promo_images"])) == ["room.jpg", "slide.jpg"]
