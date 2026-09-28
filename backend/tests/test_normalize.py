import pytest

from torgi import normalize as nz


@pytest.mark.parametrize(("text", "expected"), [
    ("29 596 000 ₸", 29_596_000),
    ("75,3", 75.3),
    ("41 000 000 ТГ.", 41_000_000),
    ("12418543890.00", 12_418_543_890),
    (None, None),
    ("нет", None),
])
def test_parse_number(text, expected):
    assert nz.parse_number(text) == expected


@pytest.mark.parametrize(("text", "expected"), [
    ("Нежилое помещение общей площадью – 525,40 кв.м., с правом", 525.4),
    ("жалпы алаңы 172 ш.м., тұрғын алаңы 129,2 ш.м.", 172),
    ("Продается жилой дом общей площадью 239,8 м2 кв.м.", 239.8),
    ("Коммерческий объект 773,5 кв.м с земельным участком", 773.5),
    ("Животноводческая база, общей площадью – 1 387,0 кв.м. с участком", 1387),
    ("общей площадью - 553, 8 кв. м.", 553.8),
    ("без площади", None),
])
def test_parse_area(text, expected):
    assert nz.parse_area_m2(text) == expected


@pytest.mark.parametrize(("text", "expected"), [
    ("земельный участок площадью 0,1 га", 0.1),
    ("общей площадью 54,3860 га", 54.386),
    ("участок 6 соток", 0.06),
    ("участком 0,0584 соток", None),  # ошибка единиц у источника
])
def test_parse_land(text, expected):
    assert nz.parse_land_ha(text) == (pytest.approx(expected) if expected else None)


@pytest.mark.parametrize(("text", "expected"), [
    ("Жилые помещения, 20:315:032:150:35/А. ИЖС", "20:315:032:150:35/А"),
    ("кадастровый №19-303-003742/А, расположенный", "19-303-003742/А"),
    ("09:142:183:521:1:1002/А , встроенное", "09:142:183:521:1:1002/А"),
    ("Кадастровый номер: 15-167-032-255", "15-167-032-255"),
    ("телефон 8 701 176 47 55", None),
])
def test_parse_cadastral(text, expected):
    assert nz.parse_cadastral(text) == expected


@pytest.mark.parametrize(("text", "expected"), [
    ("Этаж: 5/5", (5, 5)),
    ("Этаж: 2 этажа", (2, None)),
    ("расположено на 1 этаже двадцатиэтажного дома", (1, None)),
    ("в 9-этажном доме", (None, 9)),
])
def test_parse_floor(text, expected):
    assert nz.parse_floor(text) == expected


@pytest.mark.parametrize(("text", "expected"), [
    ("3-х комнатная квартира", 3),
    ("17-комнатный жилой дом", 17),
    ("трехкомнатной квартиры, общей площадью 55,10", 3),
    ("двухкомнатная квартира, расположенная", 2),
    ("квартира", None),
])
def test_parse_rooms(text, expected):
    assert nz.parse_rooms(text) == expected


@pytest.mark.parametrize(("texts", "expected"), [
    (("3-х комнатная квартира",), "apartment"),
    (("Жилой дом с земельным участком",), "house"),
    (("ремонтная мастерская с прилегающим земельным участком",), "commercial"),
    (("Земельный участок сельскохозяйственного назначения",), "land"),
    (("Прочая ком.недвижимость", "склады, общепит"), "commercial"),
    (("Паркинг",), "parking"),
    (("Промбаза",), "industrial"),
    (("что-то непонятное",), "other"),
])
def test_classify(texts, expected):
    assert nz.classify_category(*texts) == expected


@pytest.mark.parametrize(("texts", "city", "region"), [
    (("Абайская обл, Семей, Мәңгілік ел, д. 10",), "Семей", "Абайская область"),
    (("ЗКО, г. Уральск ул. Соколиная д.9/1",), "Уральск", "Западно-Казахстанская область"),
    (("Алматы, р-н Алмалы, ул. Кашгарская",), "Алматы", "Алматы"),
    (("Шымкент қаласы, Абай ауданы",), "Шымкент", "Шымкент"),
    (("г. Кызылорда, ул. А. Ыдырысова",), "Кызылорда", "Кызылординская область"),
])
def test_city_region(texts, city, region):
    detected = nz.detect_city(*texts)
    assert detected == city
    assert nz.normalize_region(*texts, city=detected) == region


def test_quality_flags():
    assert nz.quality_flags("apartment", 12_418_543_890, 75.3) == ["suspicious_price"]
    assert nz.quality_flags("apartment", 37_000_000, 76.9) == []
    assert nz.quality_flags("land", 300_000_000, None) == []
    assert nz.quality_flags("commercial", 137_300_000, 0.1581) == ["suspicious_area"]  # гектары в поле «кв.м»
    assert nz.quality_flags("parking", 3_000_000, 5) == []
