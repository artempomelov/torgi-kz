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
  <div class="a-card__text-preview">{preview}</div>
</div>
"""


def page(*cards):
    return "<section>" + "".join(CARD.format(**{"preview": "", **c}) for c in cards) + "</section>"


def test_parse_page():
    html = page(
        {"id": 1, "title": "2-комнатная квартира · 55.2 м² · 7/8 этаж", "price": "30&nbsp;900&nbsp;000", "subtitle": "Есильский р-н, Е-15 15",
         "preview": "монолитный дом, 2019 г.п., состояние: свежий ремонт, потолки 3м."},
        {"id": 2, "title": "Отдельный дом · 6 комнат · 255 м² · 7 сот.", "price": "128&nbsp;000&nbsp;000", "subtitle": "Каргалы"},
        {"id": 3, "title": "4-комнатный дом · 200 м²", "price": "от 230&nbsp;000&nbsp;000", "subtitle": "Медеуский р-н"},
        {"id": 4, "title": "1-комнатная квартира · 40 м² · 3/9 этаж", "price": "25&nbsp;000&nbsp;000", "subtitle": "Есильский р-н",
         "preview": "жил. комплекс Arena, монолитный дом, 2026 г.п., состояние: черновая отделка, потолки 3м."},
    )
    rows = market.parse_page(html, "apartment", "Астана")
    assert [r["id"] for r in rows] == [1, 2, 4]
    assert rows[0] == {"id": 1, "category": "apartment", "city": "Астана", "district": "район Есиль",
                       "rooms": 2, "area": 55.2, "price": 30_900_000, "shell": False}
    assert rows[1]["rooms"] == 6 and rows[1]["district"] is None
    assert rows[2]["shell"] is True


def test_index_falls_back_to_wider_segment():
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.executescript(market.SCHEMA)
    rows = [(i, "apartment", "Алматы", "Медеуский район", 2, 50, 50 * (900_000 + i * 1000), "2026-10-09", 0)
            for i in range(10)]
    rows += [(100 + i, "apartment", "Алматы", "Алатауский район", 1, 40, 40 * 500_000, "2026-10-09", 0) for i in range(3)]
    # черновые — в своём сегменте, на оценку квартир с отделкой не влияют
    rows += [(200 + i, "apartment", "Алматы", "Медеуский район", 2, 50, 50 * 700_000, "2026-10-09", 1) for i in range(9)]
    db.executemany("INSERT INTO listings VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", rows)
    index = market.MarketIndex.from_db(db)
    est = index.estimate("apartment", "Алматы", "Медеуский район", 2, 60)
    assert est.segment == "Алматы · Медеуский район · 2" and est.sample == 10
    assert round(est.ppm) == 904_500 and round(est.value) == 904_500 * 60
    shell = index.estimate("apartment:shell", "Алматы", "Медеуский район", 2, 60)
    assert shell.ppm == 700_000 and shell.sample == 9
    # в Алатауском районе всего 3 объявления — оценка по городу целиком
    assert index.estimate("apartment", "Алматы", "Алатауский район", 1, 40).segment == "Алматы"
    assert index.estimate("land", "Алматы", None, None, 100) is None


def test_top_limits_one_building():
    from types import SimpleNamespace

    from torgi import top

    index = market.MarketIndex({("apartment", "Алматы", None, None): (900_000, 1_000_000, 1_100_000, 50)})
    items, lots = [], {}
    for i in range(6):  # шесть квартир одного ЖК и одна в другом доме
        items.append({"id": i, "source": "halyk", "category": "apartment", "city": "Алматы", "district": "Бостандыкский район",
                      "rooms": 2, "area_m2": 60 + i, "price": 36_000_000 + i * 100_000, "flags": []})
        lots[i] = SimpleNamespace(title="Квартира", description=None, address=f"Алматы, ЖК Нурлы Тау, ул. Аль-Фараби 17, кв. {i}")
    items.append({"id": 9, "source": "bcc", "category": "apartment", "city": "Алматы", "district": "Алмалинский район",
                  "rooms": 2, "area_m2": 50, "price": 35_000_000, "flags": []})
    lots[9] = SimpleNamespace(title="Квартира", description=None, address="Алматы, ул. Гоголя, д. 166, кв. 6")
    items.append({"id": 10, "source": "bcc", "category": "apartment", "city": "Алматы", "district": "Медеуский район",
                  "rooms": 9, "area_m2": 463, "price": 60_000_000, "flags": []})  # «квартира» 463 м² — не берём
    lots[10] = SimpleNamespace(title="Квартира", description=None, address="Алматы, ул. Абая, д. 1")
    items.append({"id": 11, "source": "halyk", "category": "apartment", "city": "Алматы", "district": "Медеуский район",
                  "rooms": 2, "area_m2": 90, "price": 40_000_000, "flags": []})  # ЖК из списка исключений
    lots[11] = SimpleNamespace(title="ЖК Европолис, пятно 8", description=None, address="Алматы, ул. Ж. Омаровой 35/1, кв. 147")
    items.append({"id": 12, "source": "rbk", "category": "apartment", "city": "Алматы", "district": None,
                  "rooms": 2, "area_m2": 60, "price": 45_000_000, "flags": []})  # район неизвестен — оценка по городу ненадёжна
    lots[12] = SimpleNamespace(title="Квартиры в ЖК Панорама", description=None, address=None)
    items.append({"id": 13, "source": "bcc", "category": "apartment", "city": "Алматы", "district": "Алмалинский район",
                  "rooms": 2, "area_m2": 70, "price": 45_000_000, "flags": []})  # черновая отделка — в ТОП не берём
    lots[13] = SimpleNamespace(title="Квартира", description="Квартира в черновой отделке", address="Алматы, ул. Сатпаева, д. 5")
    for lot in lots.values():
        lot.images = ["1", "2", "3", "4"]
    data = top.build(items, lots, index)
    almaty = next(s for s in data["sections"] if s["slug"] == "kvartiry-almaty")
    ids = [x["id"] for x in almaty["items"]]
    assert len(ids) == 3 and 9 in ids and 10 not in ids and 11 not in ids and 12 not in ids and 13 not in ids
    assert almaty["items"][0]["discount_pct"] >= almaty["items"][-1]["discount_pct"]
    assert almaty["title"] == "ТОП-3 квартир в Алматы"


def test_top_from_picks():
    """Ручной отбор: порядок по скидке, выбранное фото на карточке, снятые лоты выпадают, название — по числу лотов,
    вне Алматы и Астаны скидка больше 30% — «более 30%»."""
    from types import SimpleNamespace

    from torgi import top

    index = market.MarketIndex({("apartment", "Алматы", None, None): (900_000, 1_000_000, 1_100_000, 50),
                                ("apartment", "Караганда", None, None): (300_000, 400_000, 500_000, 50)})
    items = [
        {"id": 1, "source": "a", "category": "apartment", "city": "Алматы", "district": None, "rooms": 3,
         "area_m2": 70, "price": 59_500_000, "flags": []},  # −15%, района нет в данных — задан в списке
        {"id": 2, "source": "a", "category": "apartment", "city": "Алматы", "district": "Алмалинский район", "rooms": 2,
         "area_m2": 60, "price": 42_000_000, "flags": []},  # −30%
        {"id": 3, "source": "a", "category": "apartment", "city": "Караганда", "district": None, "rooms": 2,
         "area_m2": 50, "price": 12_000_000, "flags": []},  # −40% в регионе
        {"id": 4, "source": "a", "category": "apartment", "city": "Алматы", "district": "Медеуский район", "rooms": 2,
         "area_m2": 60, "price": 48_000_000, "flags": []},  # −20%
    ]
    lots = {i: SimpleNamespace(title="Квартира", description=None, address=None, images=[f"p{i}-{k}" for k in range(6)])
            for i in range(1, 5)}
    picks = {"kvartiry-almaty": [{"id": 1, "photo": 3, "district": "Наурызбайский район"}, {"id": 2, "photo": 0},
                                 {"id": 99, "photo": 0}, {"id": 4, "photo": 5}],
             "kvartiry-regiony": [{"id": 3, "photo": 2}, {"id": 1}, {"id": 2}]}
    data = top.build(items, lots, index, picks)
    almaty = next(s for s in data["sections"] if s["slug"] == "kvartiry-almaty")
    assert [x["id"] for x in almaty["items"]] == [2, 4, 1] and almaty["title"] == "ТОП-3 квартир в Алматы"
    assert almaty["items"][2]["image"] == "p1-3" and almaty["items"][2]["discount_pct"] == 15
    assert "discount_note" not in almaty["items"][0]
    regions = next(s for s in data["sections"] if s["slug"] == "kvartiry-regiony")
    assert regions["items"][0]["id"] == 3 and regions["items"][0]["discount_note"] == "более 30%"


def test_market_badge():
    """Плашка «−N% к рынку»: район в предложном падеже, без района в Алматы нет, черновая отделка — только
    в Алматы и Астане по черновым аналогам, в регионах больше 30% — «более 30%», от −5%, выше рынка или
    подозрительно дёшево (≥45%) — нет."""
    from torgi.models import Lot
    from torgi.top import market_badge, where_phrase

    assert where_phrase("Алматы", "Бостандыкский район") == "в Бостандыкском районе"
    assert where_phrase("Астана", "район Есиль") == "в районе Есиль"
    assert where_phrase("Караганда", "район имени Казыбек би") == "в районе имени Казыбек би"
    assert where_phrase("Актау", None) == "в г. Актау"

    seg = (900_000, 1_000_000, 1_100_000, 50)
    shell = (700_000, 800_000, 900_000, 20)
    index = market.MarketIndex({("apartment", "Алматы", "Бостандыкский район", None): seg,
                                ("apartment", "Алматы", None, None): seg, ("apartment", "Актау", None, None): seg,
                                ("apartment:shell", "Алматы", "Бостандыкский район", None): shell,
                                ("apartment:shell", "Актау", None, None): shell})

    def badge(price, city="Алматы", district="Бостандыкский район", extra=None):
        x = {"id": 1, "category": "apartment", "city": city, "district": district, "rooms": None, "area_m2": 50,
             "price": price, "flags": []}
        return market_badge(x, Lot(title="Квартира", description="", extra=extra or {}), index)

    assert badge(40_000_000) == {"pct": 20, "over": False, "where": "в Бостандыкском районе"}
    assert badge(40_000_000, district=None) is None
    # черновая: 32 млн против 800 тыс. ₸/м² черновых аналогов — −20%; в регионах — без плашки
    assert badge(32_000_000, extra={"Состояние": "черновая отделка"}) == {
        "pct": 20, "over": False, "where": "в Бостандыкском районе (черновая отделка)"}
    assert badge(28_000_000, city="Актау", district=None, extra={"Состояние": "черновая отделка"}) is None
    assert badge(40_000_000, extra={"Состояние": "аварийное"}) is None
    assert badge(47_000_000) == {"pct": 6, "over": False, "where": "в Бостандыкском районе"}
    assert badge(48_000_000) is None and badge(55_000_000) is None and badge(20_000_000) is None
    assert badge(32_000_000, city="Актау", district=None) == {"pct": 30, "over": True, "where": "в г. Актау"}
