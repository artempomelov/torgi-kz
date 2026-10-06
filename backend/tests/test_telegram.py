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
