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
    assert 'href="https://torgi.kz/lots/42"' in text
    assert "#Алматы #квартира #арест" in text
    assert len(text) <= 1024
