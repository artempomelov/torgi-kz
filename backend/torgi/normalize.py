"""Нормализация: категории, регионы, города, числа из свободного текста."""

import re

CATEGORIES = {
    "apartment": "Квартира",
    "house": "Дом",
    "commercial": "Коммерческая",
    "land": "Земельный участок",
    "parking": "Паркинг / гараж",
    "industrial": "Промбаза / производство",
    "other": "Прочее",
}

ORIGINS = {
    "arrested": "Арестованное имущество",
    "bank_balance": "Имущество банка",
    "bank_pledge": "Залоговое имущество",
    "court": "Судебная реализация",
    "state": "Госимущество и приватизация",
    "bankrupt": "Имущество банкротов",
    "tax_debtor": "Имущество налоговых должников",
    "confiscated": "Конфискат",
}

SALE_TYPES = {
    "auction": "Аукцион",
    "auction_down": "Аукцион на понижение",
    "direct": "Прямая продажа",
    "tender": "Конкурс",
}

# 17 областей + 3 города республиканского значения (на 2026 год)
REGIONS = [
    "Алматы", "Астана", "Шымкент",
    "Абайская область", "Акмолинская область", "Актюбинская область", "Алматинская область",
    "Атырауская область", "Восточно-Казахстанская область", "Жамбылская область",
    "Жетысуская область", "Западно-Казахстанская область", "Карагандинская область",
    "Костанайская область", "Кызылординская область", "Мангистауская область",
    "Павлодарская область", "Северо-Казахстанская область", "Туркестанская область",
    "Улытауская область",
]

# (шаблон, регион) — порядок важен: сначала составные названия
_REGION_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(p, re.I), r)
    for p, r in [
        (r"северо[\s-]*казахстан|\bско\b", "Северо-Казахстанская область"),
        (r"западно[\s-]*казахстан|\bзко\b", "Западно-Казахстанская область"),
        (r"восточно[\s-]*казахстан|\bвко\b", "Восточно-Казахстанская область"),
        (r"алматинск|\bалматинская\b", "Алматинская область"),
        (r"абайск|абай обл", "Абайская область"),
        (r"акмолинск", "Акмолинская область"),
        (r"актюбинск|ақтөбе обл", "Актюбинская область"),
        (r"атырауск", "Атырауская область"),
        (r"жамбылск", "Жамбылская область"),
        (r"жетысуск|жетісу", "Жетысуская область"),
        (r"карагандинск", "Карагандинская область"),
        (r"костанайск", "Костанайская область"),
        (r"кызылординск", "Кызылординская область"),
        (r"мангистауск|мангыстауск", "Мангистауская область"),
        (r"павлодарск", "Павлодарская область"),
        (r"туркестанск", "Туркестанская область"),
        (r"улытауск", "Улытауская область"),
    ]
]

# Крупные города → регион. Порядок: города республиканского значения первыми.
CITY_REGION: dict[str, str] = {
    "Алматы": "Алматы",
    "Астана": "Астана",
    "Шымкент": "Шымкент",
    "Караганда": "Карагандинская область",
    "Темиртау": "Карагандинская область",
    "Балхаш": "Карагандинская область",
    "Актобе": "Актюбинская область",
    "Тараз": "Жамбылская область",
    "Павлодар": "Павлодарская область",
    "Экибастуз": "Павлодарская область",
    "Усть-Каменогорск": "Восточно-Казахстанская область",
    "Риддер": "Восточно-Казахстанская область",
    "Семей": "Абайская область",
    "Атырау": "Атырауская область",
    "Костанай": "Костанайская область",
    "Рудный": "Костанайская область",
    "Кызылорда": "Кызылординская область",
    "Уральск": "Западно-Казахстанская область",
    "Петропавловск": "Северо-Казахстанская область",
    "Актау": "Мангистауская область",
    "Жанаозен": "Мангистауская область",
    "Туркестан": "Туркестанская область",
    "Кокшетау": "Акмолинская область",
    "Талдыкорган": "Жетысуская область",
    "Конаев": "Алматинская область",
    "Каскелен": "Алматинская область",
    "Талгар": "Алматинская область",
    "Есик": "Алматинская область",
    "Жезказган": "Улытауская область",
    "Сатпаев": "Улытауская область",
}

_CITY_ALIASES: dict[str, str] = {
    "алма-ата": "Алматы",
    "нур-султан": "Астана",
    "нұр-сұлтан": "Астана",
    "ақтөбе": "Актобе",
    "өскемен": "Усть-Каменогорск",
    "усть-каменогорск": "Усть-Каменогорск",
    "қарағанды": "Караганда",
    "қызылорда": "Кызылорда",
    "орал": "Уральск",
    "қостанай": "Костанай",
    "капшагай": "Конаев",
    "қонаев": "Конаев",
    "шымкент қаласы": "Шымкент",
}

_CITY_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(rf"(?<![\w-]){re.escape(name.lower())}", re.I), name) for name in CITY_REGION
] + [(re.compile(rf"(?<![\w-]){re.escape(alias)}", re.I), name) for alias, name in _CITY_ALIASES.items()]


def detect_city(*texts: str | None) -> str | None:
    """Первый известный город, встреченный в текстах (по порядку аргументов)."""
    for text in texts:
        if not text:
            continue
        low = text.lower()
        best: tuple[int, str] | None = None
        for pattern, name in _CITY_PATTERNS:
            m = pattern.search(low)
            if m and (best is None or m.start() < best[0]):
                best = (m.start(), name)
        if best:
            return best[1]
    return None


def normalize_region(*texts: str | None, city: str | None = None) -> str | None:
    for text in texts:
        if not text:
            continue
        for pattern, region in _REGION_PATTERNS:
            if pattern.search(text):
                return region
    if city and city in CITY_REGION:
        return CITY_REGION[city]
    for text in texts:
        c = detect_city(text)
        if c in ("Алматы", "Астана", "Шымкент"):
            return c
    return None


# --- категории ---------------------------------------------------------------

_CATEGORY_RULES: list[tuple[str, re.Pattern]] = [
    ("parking", re.compile(r"паркинг|парковоч|машино[\s-]*мест|(?<!\bс )(?<!\bи )гараж", re.I)),
    ("industrial", re.compile(r"промбаз|производствен|промышлен|завод|цех|склад|нефтебаз|комбинат", re.I)),
    ("apartment", re.compile(r"квартир|комнатн\w* кв|пәтер", re.I)),
    ("house", re.compile(r"жил\w* дом|частн\w* дом|\bдом\b|пол(?:овин\w*\s+(?:\w+\s+)?)?дома\b|коттедж|тұрғын үй|\bижс\b|дача", re.I)),
    ("land", re.compile(r"земельн\w* участ|\bучасток\b|жер учаск", re.I)),
    ("commercial", re.compile(
        r"нежил|коммерч|ком\.\s*недвиж|офис|магазин|торгов|административ|здани|помещени|гостиниц|кафе|ресторан|"
        r"мастерск|гостинич|детск\w* сад|клуб|оздоровит|конноспорт|"
        r"баня|сауна|автомойк|сто\b|азс|бутик", re.I)),
]


# «здание с земельным участком», «на земельном участке» — участок здесь не предмет продажи
_ATTACHED_LAND_RE = re.compile(
    r"\b(?:с|на|и)\s+(?:\w+\s+){0,2}(?:земельн\w*\s+участк\w*|з/у)|\b(?:с|на)\s+(?:\w+\s+){0,1}участк\w*", re.I
)


def classify_category(*texts: str | None) -> str:
    """Категория по ключевым словам; тексты — от самого надёжного к менее надёжному."""
    for text in texts:
        if not text:
            continue
        text = _ATTACHED_LAND_RE.sub(" ", text)
        for category, pattern in _CATEGORY_RULES:
            if pattern.search(text):
                return category
    return "other"


# --- числа ---------------------------------------------------------------------

_NBSP = "   "


def parse_number(text: str | float | int | None) -> float | None:
    """'29 596 000 ₸' → 29596000.0; '75,3' → 75.3; '1 234,56' → 1234.56."""
    if text is None:
        return None
    if isinstance(text, (int, float)):
        return float(text)
    s = text
    for ch in _NBSP:
        s = s.replace(ch, " ")
    m = re.search(r"\d[\d ]*(?:[.,]\d+)?", s)
    if not m:
        return None
    num = m.group(0).replace(" ", "").replace(",", ".")
    try:
        return float(num)
    except ValueError:
        return None


def parse_int(text: str | int | None) -> int | None:
    n = parse_number(text) if not isinstance(text, int) else text
    return int(n) if n is not None else None


# «1 387,0», «553, 8», «57.5»
_NUM = r"(\d{1,3}(?:[  ]\d{3})+(?:[.,]\d{1,3})?|\d{1,6}(?:[ ]?[.,][ ]?\d{1,3})?)"
_AREA_RE = re.compile(rf"{_NUM}\s*(?:кв\.?\s*м|м2|м²|м\.?\s*кв|ш\.?\s*м|sq)", re.I)
_TOTAL_AREA_RE = re.compile(rf"(?:общ\w*|жалпы)\s+(?:полезн\w*\s+)?(?:площад\w*|алаңы)[^\d]{{0,25}}{_NUM}", re.I)
_HA_RE = re.compile(r"(?<![\d.,])(\d{1,6}(?:[ ]?[.,][ ]?\d{1,5})?)\s*(?:га\b|гектар)", re.I)
_SOTKA_RE = re.compile(r"(?<![\d.,])(\d{1,4}(?:[.,]\d{1,4})?)\s*сот", re.I)


def _to_float(s: str) -> float | None:
    try:
        return float(s.replace(" ", "").replace(" ", "").replace(",", "."))
    except ValueError:
        return None


def parse_area_m2(text: str | None) -> float | None:
    """Общая площадь в м² из свободного текста."""
    if not text:
        return None
    m = _TOTAL_AREA_RE.search(text) or _AREA_RE.search(text)
    if not m:
        return None
    value = _to_float(m.group(1))
    return value if value and 1 <= value <= 1_000_000 else None


def parse_land_ha(text: str | None) -> float | None:
    if not text:
        return None
    value = None
    if m := _HA_RE.search(text):
        value = _to_float(m.group(1))
    elif m := _SOTKA_RE.search(text):
        value = _to_float(m.group(1))
        value = value / 100 if value is not None else None
    # меньше 10 м² — ошибка единиц у источника («0,0584 соток»)
    return value if value and value >= 0.001 else None


_ROOMS_RE = re.compile(r"(\d{1,2})\s*[-–]?\s*(?:х\s*)?(?:комн|ком\.|бөлмелі)", re.I)
_FLOOR_SLASH_RE = re.compile(r"(\d{1,2})\s*/\s*(\d{1,2})\s*эт", re.I)
_FLOOR_RE = re.compile(r"(?:на\s+)?(\d{1,2})\s*[-–]?\s*(?:м|ом|ем)?\s*этаж(?!н)", re.I)
_FLOOR_LABEL_RE = re.compile(r"этаж\w*\s*[:\-]?\s*(\d{1,2})(?:\s*/\s*(\d{1,2}))?", re.I)
_FLOORS_TOTAL_RE = re.compile(r"(\d{1,2})\s*[-–]?\s*(?:х\s*)?этажн", re.I)


_ROOM_WORDS = {"одно": 1, "двух": 2, "трех": 3, "трёх": 3, "четырех": 4, "четырёх": 4, "пяти": 5, "шести": 6}
_ROOMS_WORD_RE = re.compile(rf"({'|'.join(_ROOM_WORDS)})\s*[-–]?\s*комнат", re.I)


def parse_rooms(text: str | None) -> int | None:
    if not text:
        return None
    if (m := _ROOMS_RE.search(text)) and 0 < int(m.group(1)) < 50:
        return int(m.group(1))
    if m := _ROOMS_WORD_RE.search(text):
        return _ROOM_WORDS[m.group(1).lower()]
    return None


def parse_floor(text: str | None) -> tuple[int | None, int | None]:
    """(этаж, этажность) из '5/5 эт', 'Этаж: 3/9', 'на 2 этаже', '9-этажного'."""
    if not text:
        return None, None
    if m := _FLOOR_SLASH_RE.search(text):
        return int(m.group(1)), int(m.group(2))
    floor = total = None
    if m := _FLOOR_LABEL_RE.search(text):
        floor = int(m.group(1))
        total = int(m.group(2)) if m.group(2) else None
    elif m := _FLOOR_RE.search(text):
        floor = int(m.group(1))
    if total is None and (m := _FLOORS_TOTAL_RE.search(text)):
        total = int(m.group(1))
    return floor, total


# Кадастровый номер РК: 20:315:032:150, 20-311-020-182, 09:142:183:521:1:1002/А, 19-303-003742/А
_CADASTRAL_RE = re.compile(
    r"(?<![\d:\-])(\d{2}[:\-]\d{3}[:\-](?:\d{6}|\d{3}[:\-]\d{2,6})(?:[:\-]\d{1,6})*(?:/[А-ЯA-Zа-яa-z0-9]{1,3})*)"
)


def parse_cadastral(text: str | None) -> str | None:
    if not text:
        return None
    m = _CADASTRAL_RE.search(text)
    return m.group(1) if m else None


_YEAR_RE = re.compile(r"(?:год\w*\s+постройки|постройки|построен\w*)[^\d]{0,20}((?:19|20)\d{2})", re.I)


def parse_year(text: str | None) -> int | None:
    if not text:
        return None
    m = _YEAR_RE.search(text)
    return int(m.group(1)) if m else None


def clean_text(text: str | None) -> str | None:
    if text is None:
        return None
    s = text
    for ch in _NBSP:
        s = s.replace(ch, " ")
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\s*\n\s*", "\n", s)
    return s.strip() or None


def quality_flags(category: str, price: float | None, area_m2: float | None) -> list[str]:
    """Проверки на явные ошибки ввода у источника.

    suspicious_price — цена неправдоподобна сама по себе;
    suspicious_area — площадь неправдоподобна (часто в поле «кв.м» стоят гектары) —
    цену за м² для таких лотов не считаем.
    """
    flags: list[str] = []
    if price is not None and (price < 10_000 or (category in ("apartment", "house") and price > 3_000_000_000)):
        flags.append("suspicious_price")
    if area_m2 is not None and category != "land" and (
        (area_m2 < 8 and category != "parking")
        or (price and "suspicious_price" not in flags and price / area_m2 > 5_000_000)
    ):
        flags.append("suspicious_area")
    return flags
