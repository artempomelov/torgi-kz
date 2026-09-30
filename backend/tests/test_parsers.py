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
