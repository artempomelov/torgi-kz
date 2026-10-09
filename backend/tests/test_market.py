"""Оценка по рынку: разбор выдачи (синтетическая разметка как у krisha.kz) и медианы по сегментам."""

import sqlite3

from torgi import market

CARD = """<div
    data-id="{id}"
    class="a-card">
  <a href="/a/show/{id}" class="a-card__title " target="_blank">{title}</a>
  <div class="a-card__price">
      {price}&nbsp;<span class="currency-sign">₸</span></div>
  <div  class="a-card__subtitle ">
      {subtitle}
  </div>
</div>
"""


def page(*cards):
    return "<section>" + "".join(CARD.format(**c) for c in cards) + "</section>"


def test_parse_page():
    html = page(
        {"id": 1, "title": "2-комнатная квартира · 55.2 м² · 7/8 этаж", "price": "30&nbsp;900&nbsp;000", "subtitle": "Есильский р-н, Е-15 15"},
        {"id": 2, "title": "Отдельный дом · 6 комнат · 255 м² · 7 сот.", "price": "128&nbsp;000&nbsp;000", "subtitle": "Каргалы"},
        {"id": 3, "title": "4-комнатный дом · 200 м²", "price": "от 230&nbsp;000&nbsp;000", "subtitle": "Медеуский р-н"},
    )
    rows = market.parse_page(html, "apartment", "Астана")
    assert [r["id"] for r in rows] == [1, 2]
    assert rows[0] == {"id": 1, "category": "apartment", "city": "Астана", "district": "район Есиль",
                       "rooms": 2, "area": 55.2, "price": 30_900_000}
    assert rows[1]["rooms"] == 6 and rows[1]["district"] is None


def test_index_falls_back_to_wider_segment():
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.executescript(market.SCHEMA)
    rows = [(i, "apartment", "Алматы", "Медеуский район", 2, 50, 50 * (900_000 + i * 1000), "2026-10-09")
            for i in range(10)]
    rows += [(100 + i, "apartment", "Алматы", "Алатауский район", 1, 40, 40 * 500_000, "2026-10-09") for i in range(3)]
    db.executemany("INSERT INTO listings VALUES (?, ?, ?, ?, ?, ?, ?, ?)", rows)
    index = market.MarketIndex(db)
    est = index.estimate("apartment", "Алматы", "Медеуский район", 2, 60)
    assert est.segment == "Алматы · Медеуский район · 2" and est.sample == 10
    assert round(est.ppm) == 904_500 and round(est.value) == 904_500 * 60
    # в Алатауском районе всего 3 объявления — оценка по городу целиком
    assert index.estimate("apartment", "Алматы", "Алатауский район", 1, 40).segment == "Алматы"
    assert index.estimate("land", "Алматы", None, None, 100) is None
