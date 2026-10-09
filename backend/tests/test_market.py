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
    index = market.MarketIndex.from_db(db)
    est = index.estimate("apartment", "Алматы", "Медеуский район", 2, 60)
    assert est.segment == "Алматы · Медеуский район · 2" and est.sample == 10
    assert round(est.ppm) == 904_500 and round(est.value) == 904_500 * 60
    # в Алатауском районе всего 3 объявления — оценка по городу целиком
    assert index.estimate("apartment", "Алматы", "Алатауский район", 1, 40).segment == "Алматы"
    assert index.estimate("land", "Алматы", None, None, 100) is None


def test_top_limits_one_building():
    from types import SimpleNamespace

    from torgi import top

    index = market.MarketIndex({("apartment", "Алматы", None, None): (900_000, 1_000_000, 1_100_000, 50)})
    items, lots = [], {}
    for i in range(6):  # шесть квартир одного ЖК и одна в другом доме
        items.append({"id": i, "source": "halyk", "category": "apartment", "city": "Алматы", "district": None,
                      "rooms": 2, "area_m2": 60 + i, "price": 30_000_000 + i * 100_000, "flags": []})
        lots[i] = SimpleNamespace(title="Квартира", address=f"Алматы, ЖК Европолис, ул. Ж. Омаровой 35/1, кв. {i}")
    items.append({"id": 9, "source": "bcc", "category": "apartment", "city": "Алматы", "district": None,
                  "rooms": 2, "area_m2": 50, "price": 35_000_000, "flags": []})
    lots[9] = SimpleNamespace(title="Квартира", address="Алматы, ул. Гоголя, д. 166, кв. 6")
    items.append({"id": 10, "source": "bcc", "category": "apartment", "city": "Алматы", "district": None,
                  "rooms": 9, "area_m2": 463, "price": 60_000_000, "flags": []})  # «квартира» 463 м² — не берём
    lots[10] = SimpleNamespace(title="Квартира", address="Алматы, ул. Абая, д. 1")
    data = top.build(items, lots, index)
    almaty = next(s for s in data["sections"] if s["slug"] == "kvartiry-almaty")
    ids = [x["id"] for x in almaty["items"]]
    assert len(ids) == 3 and 9 in ids and 10 not in ids
    assert almaty["items"][0]["discount_pct"] >= almaty["items"][-1]["discount_pct"]
