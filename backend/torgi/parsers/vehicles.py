"""Автотранспорт с торгов: ЕЭТП Минюста (арест), Freedom Bank и Halyk (залоги, имущество банка).

Машины хранятся как лоты категории «vehicle» (источники adilet_auto, freedom_auto, halyk_auto — отдельно от
недвижимости, чтобы снятие исчезнувших лотов работало по каждому разделу); марка, модель, год и характеристики —
в extra. В каталог недвижимости, ТОП, основной канал и подписки бота машины не попадают — у них свой раздел /avto/.

Персональные данные не сохраняем: VIN, госномера, ФИО и ИИН (в комментариях ЧСИ), номера кредитных договоров.
"""

import re
from collections.abc import Iterator, Mapping
from datetime import datetime

from torgi import normalize as nz
from torgi.parsers import adilet, freedom, halyk
from torgi.parsers.base import HttpClient, ParsedLot, Parser

CATEGORY = "vehicle"
MAX_PRICE = 1_000_000_000  # опечатки источников: «Toyota Matrix за 4,2 млрд ₸»

# --- марки и модели ---------------------------------------------------------------------------------------

BRANDS: list[tuple[str, str]] = [  # (название, варианты написания) — многословные раньше однословных
    ("Mercedes-Benz", r"mercedes[\s-]*benz|mercedes|мерседес"), ("Land Rover", r"land\s*rover|range\s*rover"),
    ("Great Wall", r"great\s*wall"), ("Lada", r"lada|лада|ваз|vaz|жигули"),
    ("ГАЗ", r"газ(?=[\s\-]*\d|\s*[«\"]|\s*$|\s*,)|gaz(?=[\s\-]*\d)"), ("УАЗ", r"уаз|uaz"), ("КамАЗ", r"камаз|kamaz"),
    ("ЗИЛ", r"зил|zil"), ("ПАЗ", r"паз(?=[\s\-]*\d)"), ("МАЗ", r"маз(?=[\s\-]*\d)"), ("Москвич", r"(?:иж[\s-]*)?москвич"),
    ("Беларус", r"беларус|мтз|belarus"), ("Toyota", r"toyota|тойота"), ("Lexus", r"lexus|лексус"),
    ("Hyundai", r"hyundai|хендай|хундай|хёндай"), ("Kia", r"kia|киа"), ("Chevrolet", r"chevrolet|шевроле"),
    ("Daewoo", r"daewoo|дэу"), ("Ravon", r"ravon"), ("Nissan", r"nissan|ниссан"), ("Infiniti", r"infiniti|infinity|nfiniti"),
    ("Mitsubishi", r"mitsubishi|мицубиси"), ("Mazda", r"mazda|мазда"), ("Subaru", r"subaru|субару"),
    ("Honda", r"honda|хонда"), ("Suzuki", r"suzuki"), ("Volkswagen", r"volkswagen|фольксваген|\bvw\b"),
    ("Skoda", r"skoda|шкода"), ("Audi", r"audi|ауди"), ("BMW", r"bmw|бмв"), ("Renault", r"renault|рено"),
    ("Peugeot", r"peugeot|пежо"), ("Citroen", r"citro[eë]n"), ("Opel", r"opel|опель"), ("Ford", r"ford|форд"),
    ("Haval", r"haval|хавал"), ("Geely", r"geely|джили"), ("Chery", r"chery|чери"), ("Changan", r"changan|чанган"),
    ("JAC", r"jac"), ("Jetour", r"jetour"), ("Omoda", r"omoda"), ("GAC", r"gac"), ("BYD", r"byd"), ("Kaiyi", r"kaiyi"),
    ("Exeed", r"exeed"), ("Tank", r"\btank\b"), ("Hongqi", r"hongqi"), ("Li Auto", r"li\s*auto|lixiang"),
    ("Zeekr", r"zeekr"), ("Tesla", r"tesla"), ("Porsche", r"porsche|порше"), ("Jeep", r"jeep"), ("Hummer", r"hummer"),
    ("ZAZ", r"zaz|заз"), ("Shacman", r"shacman|шакман"), ("Isuzu", r"isuzu|исузу"), ("Iveco", r"iveco|ивеко"),
    ("DAF", r"daf"), ("Scania", r"scania"), ("Volvo", r"volvo"), ("MAN", r"\bman\b"), ("Howo", r"howo|sinotruk"),
    ("Foton", r"foton"), ("XCMG", r"xcmg"), ("Shantui", r"shantui"), ("Енисей", r"енисей"),
    ("New Holland", r"new\s*holland"), ("John Deere", r"john\s*deere"), ("Claas", r"claas"),
]
_BRAND_RES = [(canon, re.compile(rf"(?<![\w])(?:{pat})(?![a-zа-яё])", re.I)) for canon, pat in BRANDS]
_LADA_MODELS = [(r"^219[0-9]", "Granta"), (r"^217[0-3]", "Priora"), (r"^111[7-9]", "Kalina"),
                (r"^2121|^2131|^21213|^21214", "Niva"), (r"^210[4-7]", "2107"), (r"^2114", "2114"), (r"^2123", "Niva")]
_STOP = re.compile(r"\s*(?:\n|,|;|\(|«|»|\"|/|\.\s|г\.в|г/в|года|год|(?<!\d)(?:19|20)\d{2}(?!\d)|\b\d\.\d\b|turbo|4wd|awd|"
                   r"р/н|рег\.|гос\.|госномер|грнз|vin|цвет|\d{3}\s?[A-ZА-Я]{2,3}\s?\d{2}\b).*", re.I | re.S)


def find_brand(*texts: str | None) -> tuple[str | None, str | None]:
    """(марка, модель) из первого текста, где встретилась марка."""
    for text in texts:
        if not text:
            continue
        text = text.replace("ё", "е")
        best = None
        for canon, rx in _BRAND_RES:
            m = rx.search(text)
            if m and (best is None or m.start() < best[1].start()):
                best = (canon, m)
        if best:
            canon, m = best
            tail = re.sub(r"^[\s\-–:«\"']*(?:марки|модель[:\s]*)?\s*", "", text[m.end():], flags=re.I)
            return canon, clean_model(canon, _STOP.sub("", tail).strip(" -.\"«»"))
    return None, None


def clean_model(brand: str, model: str | None) -> str | None:
    if not model:
        return None
    model = re.split(r"\s+(?:на|с|в|за|для|автомат|механика|робот|вариатор|бензин|дизель|черн|бел|сер)\b",
                     re.sub(r"\s+", " ", model).strip(), flags=re.I)[0]
    words = model.split(" ")[:4]
    if brand == "Lada" and words:
        for rx, name in _LADA_MODELS:
            if re.match(rx, words[0]):
                return name
    out = []
    for w in words:
        if re.fullmatch(r"[A-Za-zА-Яа-я]{4,}", w) and (w.isupper() or w.islower()) or re.fullmatch(r"(?i)plus|pro|max|hybrid", w):
            out.append(w.capitalize())
        elif m := re.fullmatch(r"([A-Za-z]+\d+)(plus|pro|max)", w, re.I):
            out.append(f"{m.group(1).upper()} {m.group(2).capitalize()}")  # X90PLUS → X90 Plus
        elif re.fullmatch(r"[A-Za-z]{4,}\d+", w):
            out.append(w.capitalize())  # TIGGO4 → Tiggo4
        elif re.fullmatch(r"[A-Za-z]+-[A-Za-z]{4,}", w):
            out.append("-".join(x.capitalize() if len(x) >= 4 else x.upper() for x in w.split("-")))  # X-TRAIL → X-Trail
        else:  # «cs75» → CS75, «gle» → GLE; «Rio» как написан
            out.append(w.upper() if re.search(r"\d", w) or (len(w) <= 3 and not w.istitle()) else w)
    return " ".join(out).strip(" -.,") or None


# --- характеристики -------------------------------------------------------------------------------------------

_TRANS = [(r"\bакпп\b|автомат", "АКПП"), (r"\bмкпп\b|механик", "МКПП"), (r"робот", "робот"), (r"вариатор|cvt", "вариатор")]
_COLORS = ["белый металлик", "светло-серый", "темно-серый", "черный", "белый", "серый", "серебристый", "синий", "красный",
           "зеленый", "желтый", "оранжевый", "коричневый", "бежевый", "голубой", "бордовый", "золотистый", "фиолетовый"]


def transmission(text: str | None) -> str | None:
    return next((name for rx, name in _TRANS if text and re.search(rx, text, re.I)), None)


def mileage(text: str | None) -> int | None:
    m = re.search(r"пробег\w*[\s:\-–]*(?:около\s*)?(\d{1,3}(?:[\s  ]\d{3})+|\d{1,7})\s*(?:км)?", text or "", re.I)
    v = int(re.sub(r"\D", "", m.group(1))) if m else 0
    return v if 0 < v < 2_000_000 else None


def color(text: str | None) -> str | None:
    if not text:
        return None
    m = re.search(r"цвет\w*[\s:\-–«\"]*([а-яё\- ]{3,30})", text, re.I)
    cand = (m.group(1) if m else text).lower().replace("ё", "е")
    return next((c for c in _COLORS if c in cand), None)


def engine(volume: float | None, fuel: str | None) -> str | None:
    if volume is not None:
        volume = volume / 1000 if volume > 50 else volume  # кубические сантиметры → литры
    parts = [f"{volume:.1f}" if volume else None, (fuel or "").lower() or None]
    return " ".join(p for p in parts if p) or None


def body_norm(text: str | None) -> str | None:
    if not text:
        return None
    t = nz.fix_homoglyphs(text).lower().strip()
    return {"хэтчбэк/лифтбэк": "хэтчбек", "иное": None, "кросовер": "кроссовер"}.get(t, t)


def vehicle_title(brand: str | None, model: str | None, year: int | None, fallback: str = "Транспорт") -> str:
    head = " ".join(p for p in (brand, model) if p) or fallback
    return f"{head}, {year} г." if year else head


def _vehicle(**fields) -> dict:
    """extra лота: марка, модель, год, характеристики (без пустых)."""
    return {k: v for k, v in fields.items() if v not in (None, "")}


def _price(value) -> float | None:
    p = nz.parse_number(value)
    return p if p and p < MAX_PRICE else None


# --- Freedom Bank ---------------------------------------------------------------------------------------------

FREEDOM_VEHICLE_TYPE_ID = 1


class FreedomAutoParser(Parser):
    name = "freedom_auto"
    title = "Freedom Bank — автомобили"
    base_url = f"{freedom.BASE}/ru/mortgage"

    def fetch(self, http: HttpClient, known: Mapping[str, float | None]) -> Iterator[ParsedLot]:
        headers = {"Accept": "application/json", "X-Requested-With": "XMLHttpRequest"}
        filters = http.get(f"{freedom.BASE}/api/mortgage/get-filters", headers=headers).json()["data"]
        dic = {k: {x["id"]: x["name_ru"] for x in filters.get(k) or []}
               for k in ("fuel_types", "drive_types", "gearbox_types")}
        resp = http.get(f"{freedom.BASE}/api/mortgage/get-filtered-data", headers=headers,
                        params={"city_id": "all", "realisation_type_id": "all",
                                "mortgage_type_id": FREEDOM_VEHICLE_TYPE_ID, "sort": "fresh"})
        for item in resp.json()["data"]["data"]:
            if item.get("mortgage_type_id") != FREEDOM_VEHICLE_TYPE_ID:
                continue
            v = item.get("mortgage_vehicle") or {}
            brand, model = find_brand(item.get("name_ru"))
            year = nz.parse_int(item.get("year"))
            city_name = (item.get("city") or {}).get("name_ru")
            city = nz.detect_city(city_name) or city_name
            km = v.get("mileage") or 0
            gear = dic["gearbox_types"].get(v.get("gearbox_type_id"))
            published = item.get("created_at")
            yield ParsedLot(
                source_id=str(item["id"]),
                url=f"{freedom.BASE}/ru/mortgage/{item['id']}",
                title=vehicle_title(brand, model, year, (item.get("name_ru") or "").strip(" ;")),
                origin=freedom.ORIGINS.get(item.get("realisation_type_id"), "bank_pledge"),
                category=CATEGORY,
                sale_type="direct",
                description=nz.clean_text(item.get("additional_data_ru")),
                region=nz.normalize_region(city_name, city=city),
                city=city,
                price=_price(item.get("price")),
                published_at=datetime.fromisoformat(published.replace("Z", "+00:00")) if published else None,
                images=[freedom.BASE + p if p.startswith("/") else p for p in item.get("images") or []],
                extra=_vehicle(
                    vehicle_type="car", brand=brand, model=model, year=year,
                    # «10 км», «100 км» у машин 2013–2017 годов — заглушки, а не пробег
                    mileage_km=km if km >= 1000 or (year or 0) >= 2025 else None,
                    engine=engine(nz.parse_number((v.get("volume") or "").replace(",", ".")),
                                  dic["fuel_types"].get(v.get("fuel_type_id"))),
                    transmission={"механика": "МКПП"}.get(gear, gear), body=body_norm(v.get("body_type_ru")),
                    color=(v.get("body_color_ru") or "").lower() or None, drive=dic["drive_types"].get(v.get("drive_type_id")),
                    realisation_type=(item.get("realisation_type") or {}).get("name_ru"),
                ),
            )


# --- Halyk (halykzalog.kz, раздел «Транспорт») --------------------------------------------------------------

HALYK_TRANSPORT = 7
_HALYK_KIND = {"легковая": "car", "грузовая": "truck"}


def halyk_vehicle(lot: ParsedLot) -> ParsedLot:
    """Лот недвижимости из halyk.parse_detail → лот автотранспорта (марка и модель — из полей или текста)."""
    e = lot.extra
    desc = re.sub(r"К моменту принятия.*?недвижимости\.\s*", "", lot.description or "", flags=re.S)
    if m := re.search(r"Марка:\s*([^,]+),\s*Модель:\s*([^,]+)", desc):
        brand = find_brand(m.group(1))[0]
        model = clean_model(brand or "", m.group(2))
    else:
        field = e.get("Марка") if e.get("Марка") not in (None, "Иное") else None
        field_brand = (find_brand(field)[0] or field) if field else None
        brand, model = find_brand(desc)
        if field_brand and brand != field_brand:  # поле надёжнее текста; модель — только если марка совпала
            brand, model = field_brand, None
    kind = (e.get("Тип") or "").lower()
    year = nz.parse_int(e.get("Год выпуска"))
    owner = lot.contacts.get("owner") or ""
    note = ("возврат из лизинга (Халык-Лизинг)" if "Лизинг" in owner
            else "после страхового случая (СК «Халык»)" if "Страхов" in owner else None)
    lot.category = CATEGORY
    lot.title = vehicle_title(brand, model, year)
    lot.address = None  # адрес стоянки не нужен, город остаётся
    lot.area_m2 = lot.rooms = lot.floor = lot.floors_total = lot.year_built = lot.land_area_ha = None
    lot.cadastral = None
    lot.price = lot.price if lot.price and lot.price < MAX_PRICE else None
    lot.extra = _vehicle(
        vehicle_type=_HALYK_KIND.get(kind, "special" if kind else "other"), brand=brand, model=model, year=year,
        mileage_km=mileage(desc), engine=engine(nz.parse_number(e.get("Объем двигателя")), e.get("Тип топлива")),
        transmission=transmission(desc), body=body_norm(e.get("Тип кузова")), color=color(desc),
        drive=e.get("Тип привода"), note=note, realization=e.get("realization"), bids=e.get("bids"),
    )
    return lot


class HalykAutoParser(Parser):
    name = "halyk_auto"
    title = "Halyk Bank — транспорт"
    base_url = halyk.BASE

    def fetch(self, http: HttpClient, known: Mapping[str, float | None]) -> Iterator[ParsedLot]:
        seen: set[str] = set()
        page = 1
        while True:
            cards = halyk.parse_listing(http.get(f"{halyk.BASE}/catalog/category_id-is-{HALYK_TRANSPORT}",
                                                 params={"page": page}).text)
            if not cards:
                break
            for card in cards:
                sid = card["id"]
                if sid in seen:
                    continue
                seen.add(sid)
                if sid in known and known[sid] == card["price"]:
                    yield ParsedLot(source_id=sid, url=card["url"], title="", origin="bank_balance",
                                    category=CATEGORY, price=card["price"], partial=True)
                else:
                    yield halyk_vehicle(halyk.parse_detail(http.get(card["url"]).text, card["url"], "other"))
            page += 1


# --- ЕЭТП Минюста (арест) -------------------------------------------------------------------------------------

ADILET_CLASSIFIERS = {"легковые автомобили": "car", "грузовые автомобили": "truck", "сельхоз техника": "special",
                      "тракторная техника": "special", "дорожная техника": "special", "автобусы": "other",
                      "мототехника": "moto", "спецтехника": "special"}
_UNIT_RE = re.compile(r"^\s*\d+\.\d{3}\s*(?:ШТУКА|ЭКЗЕМПЛЯР|ОБЪЕКТ|АМПУЛА|ШТ|ЕДИНИЦА|КОМПЛЕКТ)?\s*", re.I)


def adilet_vehicle(item: dict) -> ParsedLot | None:
    classifier = (item.get("procurementClassifiers") or [{}])[0].get("title", "").strip().lower()
    vtype = ADILET_CLASSIFIERS.get(classifier)
    if not vtype:
        return None
    lot = (item.get("lots") or [{}])[0]
    desc = lot.get("goodsDescription") or ""
    # «Объект: Легковой автомобиль, 1.000 ШТУКА, TOYOTA CAMRY, 2020, VIN…, госномер…, черный» — берём только
    # наименование, год и цвет; комментарий ЧСИ (там бывают ФИО и ИИН должника) не сохраняем
    fields = [x.strip() for x in adilet._object_line(desc).split(",")][1:]
    if fields:
        fields[0] = _UNIT_RE.sub("", fields[0])
    fields = [x for x in fields if x]
    year_idx = next((i for i, x in enumerate(fields) if re.fullmatch(r"(?:19|20)\d{2}", x)), None)
    name = fields[0] if fields else (item.get("title") or "")
    comment = adilet._comment(desc)
    year = int(fields[year_idx]) if year_idx is not None else nz.parse_year(comment)
    col = fields[-1].lower() if year_idx is not None and len(fields) > year_idx + 2 else color(comment)
    brand, model = find_brand(name, comment)
    if brand is None and name:  # «опрыскиватель AVAGRO TT30», «Енисей-1200»
        toks = [t for t in re.split(r"[\s-]+", name) if t and not re.fullmatch(r"[а-яё]+", t)]
        if toks:
            brand, model = toks[0].title(), clean_model("", " ".join(toks[1:]))
    low = comment.lower()
    notes = [text for rx, text in [(r"аварийн", "аварийный"), (r"не\s*исправн|неисправн", "технически неисправен"),
                                   (r"ключ\w*.*отсутств|отсутств\w*.*ключ", "нет ключей или техпаспорта"),
                                   (r"1/2\s*дол", "продаётся 1/2 доли")] if re.search(rx, low)]
    if "Имеются обременения" in desc:
        notes.append("имеются обременения")
    region_raw = item.get("region")
    city = nz.detect_city(region_raw)
    price = _price(item.get("initialContractPrice"))
    return ParsedLot(
        source_id=str(item["id"]),
        url=f"{adilet.BASE}/trades/{item['id']}",
        title=vehicle_title(brand, model, year, name.title() or "Транспорт"),
        origin="arrested",
        category=CATEGORY,
        sale_type="auction_down" if lot.get("methodAucDown") else "auction",
        description="Арестованное имущество, торги частного судебного исполнителя"
                    + (" (аукцион на понижение)" if lot.get("methodAucDown") else "")
                    + (". " + ", ".join(notes).capitalize() if notes else "") + ".",
        region=nz.normalize_region(region_raw, city=city) if region_raw != "Республика Казахстан" else None,
        city=city,
        price=price,
        deposit=nz.parse_number(item.get("assuranceAmount")),
        auction_start=adilet._ms_to_dt(item.get("tradeStartDate")),
        applications_deadline=adilet._ms_to_dt(item.get("bidSubmissionEndDate")),
        images=[adilet.BASE + img["href"] for img in item.get("images") or [] if img.get("href")],
        extra=_vehicle(vehicle_type=vtype, brand=brand, model=model, year=year, color=col,
                       note=", ".join(notes) or None),
    )


class AdiletAutoParser(Parser):
    name = "adilet_auto"
    title = "ЕЭТП Минюста — транспорт"
    base_url = adilet.BASE

    def fetch(self, http: HttpClient, known: Mapping[str, float | None]) -> Iterator[ParsedLot]:
        skip = 0
        while True:
            resp = http.get(f"{adilet.BASE}/trades", params={"page": "sales", "limit": adilet.PAGE_SIZE, "skip": skip},
                            headers={"X-Requested-With": "XMLHttpRequest"})
            trades = adilet.extract_state(resp.text)["$top"]["trades"]
            items = trades.get("items") or []
            for item in items:
                if parsed := adilet_vehicle(item):
                    yield parsed
            skip += len(items)
            if not items or skip >= int(trades.get("total") or 0):
                break
