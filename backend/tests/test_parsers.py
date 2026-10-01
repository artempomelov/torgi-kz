"""Парсеры на реальных ответах источников (сохранены 28.09.2026 в tests/fixtures)."""

import json
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

from torgi.parsers import adilet, alatau, bcc, forte, freedom, halyk

FIXTURES = Path(__file__).parent / "fixtures"
KZ = timezone(timedelta(hours=5))


def text(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def fill_rate(lots, attr: str) -> float:
    return sum(getattr(lot, attr) not in (None, "", []) for lot in lots) / len(lots)


def test_adilet():
    items = adilet.extract_state(text("adilet_list.html"))["$top"]["trades"]["items"]
    assert len(items) == 223
    lots = [lot for item in items if (lot := adilet.parse_trade(item))]
    assert len(lots) == 78  # только недвижимость, авто и техника отброшены
    assert all(lot.origin == "arrested" and lot.price for lot in lots)
    assert fill_rate(lots, "region") > 0.95
    assert fill_rate(lots, "cadastral") > 0.9

    office = next(lot for lot in lots if lot.source_id == "113513781")
    assert office.category == "commercial"
    assert office.area_m2 == 89.5
    assert office.city == "Караганда"
    assert office.region == "Карагандинская область"
    assert office.cadastral == "09:142:183:521:1:1002/А"
    assert office.url == "https://etp.adilet.gov.kz/trades/113513781"
    assert office.auction_start and office.applications_deadline and office.deposit

    land = next(lot for lot in lots if lot.source_id == "113513653")
    assert land.category == "land"
    assert land.land_area_ha == 54.386
    assert land.area_m2 is None

    workshop = next(lot for lot in lots if "мастерская" in lot.title)
    assert workshop.category == "commercial"

    house = next(lot for lot in lots if lot.source_id == "113513796")
    assert house.address == "Алматы, Есенжанова Х, 33"
    assert fill_rate(lots, "address") > 0.9


def test_halyk_listing():
    cards = halyk.parse_listing(text("halyk_list.html"))
    assert len(cards) == 24
    assert cards[0] == {
        "id": "15215",
        "url": "https://halykzalog.kz/catalog/category_id-is-1/15215",
        "address": "Абайская обл, Семей, Мәңгілік ел, д. 10, кв. 28",
        "price": 29_596_000,
        "kind": "Квартира",
    }


def test_halyk_detail():
    lot = halyk.parse_detail(text("halyk_detail.html"), "https://halykzalog.kz/catalog/category_id-is-1/13635",
                             "apartment")
    assert lot.source_id == "13635"
    assert lot.origin == "bank_balance"
    assert lot.sale_type == "direct"
    assert (lot.price, lot.area_m2, lot.rooms, lot.floor, lot.floors_total, lot.year_built) == (
        42_596_700, 57.5, 3, 3, 5, 1974)
    assert (lot.city, lot.region) == ("Алматы", "Алматы")
    assert (lot.lat, lot.lon) == (43.241604, 76.928338)
    assert lot.images and all("thumbnail_" not in u for u in lot.images)


def test_halyk_auction():
    lot = halyk.parse_detail(text("halyk_detail_auction.html"),
                             "https://halykzalog.kz/catalog/category_id-is-4/15117", "commercial")
    assert lot.sale_type == "auction"
    assert lot.auction_start == datetime(2026, 9, 25, tzinfo=KZ)
    assert lot.auction_end == datetime(2026, 10, 1, 18, 0, tzinfo=KZ)
    assert lot.extra["bids"] == 1
    assert lot.price == 253_642_800


def test_alatau():
    data = json.loads(text("alatau_all.json"))
    lots = [lot for item in data["data"]["allProperties"]["items"] if (lot := alatau.parse_item(item))]
    assert len(lots) == 129  # 135 минус движимое
    assert all(lot.price and lot.region for lot in lots)

    house = next(lot for lot in lots if lot.source_id == "557")
    assert house.category == "house"
    assert house.sale_type == "direct"
    assert house.area_m2 == 129.9
    assert house.land_area_ha == 0.2232
    assert house.cadastral == "15-167-032-255"
    assert house.region == "Северо-Казахстанская область"
    assert house.url == "https://alataucitybank.kz/balance/557"

    assert Counter(lot.sale_type for lot in lots)["auction"] > 100


def test_forte():
    data = json.loads(text("forte_all.json"))
    lots = [forte.parse_node(node) for node in data["data"]["sales_connection"]["nodes"]]
    assert len(lots) == 87
    assert fill_rate(lots, "city") == 1
    first = lots[0]
    assert first.url == "https://sale.forte.kz/ru/sale/zko-g-uralsk-ul-sokolinaya-d-9-1"
    assert first.category == "house"
    assert (first.price, first.area_m2, first.year_built) == (42_500_000, 239, 1996)
    assert first.region == "Западно-Казахстанская область"
    assert first.sale_type == "auction"
    assert first.contacts["phone"] == "+77028887712"
    assert all(lot.land_area_ha for lot in lots if lot.category == "land")


def test_bcc():
    lots = bcc.parse_page(text("bcc.html"))
    assert 130 <= len(lots) <= 148  # движимое отброшено, дубли схлопнуты
    assert len({lot.source_id for lot in lots}) == len(lots)
    assert fill_rate(lots, "price") > 0.8
    assert fill_rate(lots, "city") > 0.9

    court = next(lot for lot in lots if "Бозарык" in (lot.address or ""))
    assert court.origin == "court"
    assert court.price == 140_456_939
    assert court.area_m2 == 525.4
    assert court.floor is None  # «1 этаж» — из адреса офиса банка, не объекта

    flat = next(lot for lot in lots if "Момышулы" in (lot.address or ""))
    assert flat.category == "apartment"
    assert (flat.rooms, flat.floor, flat.floors_total, flat.price) == (3, 5, 5, 25_460_019)


def test_freedom():
    data = json.loads(text("freedom_all.json"))
    lots = [lot for item in data["data"]["data"] if (lot := freedom.parse_item(item))]
    assert len(lots) == 7  # только недвижимость
    taraz = next(lot for lot in lots if lot.source_id == "616")
    assert taraz.origin == "bank_pledge"
    assert (taraz.rooms, taraz.floor, taraz.floors_total, taraz.area_m2) == (4, 5, 5, 75.3)
    assert taraz.region == "Жамбылская область"
    for lot in lots:
        dumped = json.dumps(lot.extra, ensure_ascii=False) + json.dumps(lot.contacts, ensure_ascii=False)
        assert "contract" not in dumped and "collateral" not in dumped


def test_adilet_trade_info():
    info = json.loads(text("adilet_info_113513781.json"))
    documents, contacts = adilet.parse_trade_info(info)
    titles = [d["title"] for d in documents]
    assert "ФОТО" in titles
    assert any(t.startswith("Отчет №2932026 об оценке") for t in titles)
    assert all(d["url"].startswith("https://etp.adilet.gov.kz/files/get/") for d in documents)
    assert all(not d["url"].endswith(".png") for d in documents)  # картинки — в галерее, не в документах
    assert contacts == {"officer": "Карпеков Ерик Серикулы", "phone": "+77054002626"}


def test_alatau_documents():
    lot = alatau.parse_item(json.loads(text("alatau_all.json"))["data"]["allProperties"]["items"][0])
    alatau.apply_detail(lot, {"propertyDocuments": [
        {"title": {"ru": "госакт"}, "link": {"ru": "dir=balance-property/property/280&filename=gosakt-ru.pdf"}},
        {"title": {"ru": "пусто"}, "link": {"ru": None}},
    ]})
    assert lot.documents == [{
        "title": "госакт",
        "url": "https://alataucitybank.kz/file-server/filename?dir=balance-property/property/280&filename=gosakt-ru.pdf",
    }]


def test_sauda_list_and_detail():
    from torgi.parsers import sauda

    cards = sauda.parse_list(text("sauda_list.html"))
    assert len(cards) == 20
    card = cards[0]
    assert card["id"] == "337778617530000000" and card["price"] == 171_545_853
    assert card["region"] == "Павлодарская область" and card["start"] == "01.10.2026 12:00"

    lot = sauda.parse_detail(text("sauda_detail.html"), card, "RealEstate")
    assert lot.origin == "state" and lot.category == "commercial" and lot.sale_type == "auction"
    assert (lot.area_m2, lot.land_area_ha, lot.cadastral) == (834.8, 0.0603, "14:218:001:203")
    assert (lot.city, lot.deposit) == ("Павлодар", 25_731_878)
    assert lot.applications_deadline == datetime(2026, 10, 1, 11, 55, tzinfo=KZ)
    assert lot.contacts["phone"] == "+7 778 700 28 99, +7 778 870 11 04"
    assert len(lot.images) == 6 and all("/image-proxy/1200x900/" in u for u in lot.images)
    assert [d["title"] for d in lot.documents][:1] == ["Справка Ф2 г. Павлодар, Баян Батыра 4 (11.09.2026)"]


def test_sauda_origin():
    from torgi.parsers.sauda import origin_for, sale_type_for

    assert origin_for("Аукцион по продаже имущества должника (банкрота)", "") == "bankrupt"
    assert origin_for("Аукцион по продаже имущества налогоплательщика", "") == "tax_debtor"
    assert origin_for("Аукцион на понижение цены (конфискат)", "") == "confiscated"
    assert origin_for("Аукцион на повышение цены", "Акционерное общество \"Фонд проблемных кредитов\"") == "bank_balance"
    assert origin_for("Тендер по передаче объекта в имущественный наем (аренду)", "") is None
    assert origin_for("Аукцион на повышение цены (зем. ресурсы)", "ГУ Отдел земельных отношений") == "state"
    assert sale_type_for("Аукцион на понижение цены (с 17.01.2021 года)") == "auction_down"


def test_eurasian():
    from torgi.parsers import eurasian

    docs = json.loads(text("eurasian_all.json"))["docs"]
    lots = [lot for item in docs if (lot := eurasian.parse_item(item))]
    assert len(lots) == 39  # без авто, спецтехники и оборудования
    assert all(lot.origin == "bank_balance" and lot.price and lot.images for lot in lots)
    tl = next(lot for lot in lots if lot.source_id == "57")
    assert (tl.category, tl.city, tl.area_m2, tl.floors_total) == ("commercial", "Астана", 162.1, 10)
    assert tl.address == "г.Астана, р-н Сарыарка, пр. Нұрғиса Тілендиев, д. 36"
    assert tl.images[0].startswith("https://eubank.kz/media/")
    assert tl.documents and tl.documents[0]["url"].startswith("https://eubank.kz/")


def test_rbk():
    from torgi.parsers import rbk

    items = json.loads(text("rbk_p1.json"))[0]["data"]
    lots = [rbk.parse_item(item) for item in items]
    office = lots[0]
    assert (office.category, office.city, office.area_m2, office.price) == ("commercial", "Алматы", 577.6, 720_000_000)
    assert (office.lat, office.lon) == (43.2518903, 76.9670429)
    assert len(office.images) == 4 and office.contacts == {"phone": "87779899771"}
    assert lots[1].category == "apartment" and lots[1].rooms == 2


def test_nurbank():
    from torgi.parsers import nurbank

    cards = nurbank.parse_list(text("nurbank_list.html"))
    assert len(cards) == 248
    assert cards[0]["id"] == "519" and cards[0]["price"] == 231_500_000 and cards[0]["date"] == "21.08.2026"
    lot = nurbank.build_lot(cards[0], nurbank.parse_detail(text("nurbank_detail.html")))
    assert lot.category == "industrial"  # нефтебаза, «гараж» в описании — лишь одно из строений
    assert lot.address.startswith("Акмолинская область, Астраханский район")
    assert lot.region == "Акмолинская область"
    assert (lot.area_m2, lot.land_area_ha, lot.cadastral) == (1456.3, 5.0535, "01-002-015-004")
    assert lot.contacts == {"phone": "+77056622006, +77015858863"}
    assert len(lot.images) == 8 and "Нурбанк" not in lot.description
    kept = [c for c in cards if nurbank.build_lot(c, None)]
    assert not any("KIA" in c["title"] or "Hummer" in c["title"] for c in kept)


def test_bereke():
    from torgi.parsers import bereke

    cards = bereke.parse_list(text("bereke_list.html"))
    assert cards[0] == {"id": "56", "title": "Нежилое помещение(Актау)", "price": 242_490_708,
                        "summary": "Нежилое помещение общей площадью 1 049,6 кв.м."}
    lot = bereke.build_lot(cards[0], bereke.parse_detail(text("bereke_detail.html")))
    assert (lot.category, lot.city, lot.region, lot.area_m2) == ("commercial", "Актау", "Мангистауская область", 1049.6)
    assert lot.contacts == {"phone": "+77017706071"}
    assert len(lot.images) == 7 and all("/Collaterals/242%20490%20708/" in u for u in lot.images)
