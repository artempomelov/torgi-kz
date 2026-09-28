"""bcc.kz — залоговая база Bank CenterCredit. Одна HTML-страница, карточки двух шаблонов:
балансовые (с полями «Цена:», «Этаж:», ...) и судебная реализация (свободный текст).
Стабильного ID нет — используем хэш «заголовок + адрес + площадь».
"""

import hashlib
import re
from collections.abc import Iterator, Mapping

from bs4 import BeautifulSoup, Tag

from torgi import normalize as nz
from torgi.parsers.base import HttpClient, ParsedLot, Parser

URL = "https://www.bcc.kz/personal/collateral-base/"

# Вкладки страницы: 1 — коммерческая, 2 — жилая, 3 — реализация с торгов, 4 — движимое (пропускаем)
SKIP_TABS = {"4"}

_CARD_ID_RE = re.compile(r"description-card-(\d+)-(\d+)")
_LABEL_RE = re.compile(r"^([^:]{2,60}):\s*(.+)$")
_PRICE_RE = re.compile(r"(?:стоимост\w*|цена)[^\d]{0,60}?(\d{1,3}(?:[  ]\d{3})+|\d{5,})", re.I)
_ADDRESS_RE = re.compile(r"по адресу[:\s]+(.+?)(?:\.\s|\s+Продажн|\s+Цена|$)", re.I | re.S)
_BG_RE = re.compile(r"url\(([^)]+)\)")
_COURT_RE = re.compile(r"решени\w* суда|определени\w* суда|суд\w* реализац", re.I)


def _lines(el: Tag | None) -> list[str]:
    if el is None:
        return []
    # Переносы только по <br> и блочным тегам: «<strong>Этаж:</strong> 5/5» — одна строка
    for br in el.find_all("br"):
        br.replace_with("\n")
    for block in el.find_all(["p", "div", "li", "tr", "h1", "h2", "h3", "h4"]):
        block.append("\n")
    text = el.get_text("")
    return [ln.strip() for ln in (nz.clean_text(text) or "").split("\n") if ln.strip()]


def _labels(lines: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for ln in lines:
        if m := _LABEL_RE.match(ln):
            out.setdefault(m.group(1).strip().lower(), m.group(2).strip())
    return out


def _label(labels: dict[str, str], *prefixes: str) -> str | None:
    for p in prefixes:
        for k, v in labels.items():
            if k.startswith(p):
                return v
    return None


def parse_card(section: Tag) -> ParsedLot | None:
    m = _CARD_ID_RE.search(section.get("id", ""))
    if not m or m.group(2) in SKIP_TABS:
        return None
    tab = m.group(2)
    title = (el.get_text(" ", strip=True) if (el := section.select_one(".description-card-title")) else "").strip()
    short = _lines(section.select_one(".description-card-desc"))
    popup_el = section.select_one(".dialog")
    popup = _lines(popup_el)
    full_text = " ".join(short + popup)
    labels = _labels(short)

    address = _label(labels, "местоположение")
    if not address and (am := _ADDRESS_RE.search(full_text)):
        address = am.group(1).strip(" ,.")
    if not address:
        # у жилых карточек вторая строка — «Город / улица, дом»
        address = next((ln for ln in short if ":" not in ln and "/" in ln), None)

    price_raw = _label(labels, "цена")
    price = nz.parse_number(price_raw) if price_raw else None
    if price is None and (pm := _PRICE_RE.search(full_text)):
        price = nz.parse_number(pm.group(1))

    area = nz.parse_number(_label(labels, "площадь помещения", "общая площадь")) or nz.parse_area_m2(full_text)
    # Этаж — только из поля: в тексте судебных карточек «этаж» встречается в адресе офиса банка
    floor, floors_total = nz.parse_floor(f"Этаж: {_label(labels, 'этаж')}") if _label(labels, "этаж") else (None, None)
    category = nz.classify_category(_label(labels, "вид объекта"), title, full_text)
    if tab == "2" and category not in ("apartment", "house"):
        category = "apartment" if "квартир" in full_text.lower() else "house"
    city = nz.detect_city(address, full_text)

    images = []
    if media := section.select_one(".description-card-bg"):
        if bg := _BG_RE.search(media.get("style", "")):
            images.append(bg.group(1).strip("'\""))

    contact = _label(labels, "контактная информация")
    email = re.search(r"[\w.+-]+@bcc\.kz", full_text)

    key = f"{title}|{address}|{area}".lower()
    return ParsedLot(
        source_id=hashlib.sha1(key.encode()).hexdigest()[:16],
        url=URL,
        title=f"{title}, {address}" if address and address not in title else title,
        origin="court" if _COURT_RE.search(full_text) else "bank_balance",
        category=category,
        sale_type="auction" if tab == "3" else "direct",
        description=nz.clean_text("\n".join(popup or short)),
        region=nz.normalize_region(address, full_text, city=city),
        city=city,
        address=address,
        area_m2=None if category == "land" else area,
        land_area_ha=nz.parse_land_ha(full_text),
        rooms=nz.parse_int(_label(labels, "количество комнат")) or nz.parse_rooms(title),
        floor=floor,
        floors_total=floors_total,
        year_built=nz.parse_year(full_text),
        cadastral=nz.parse_cadastral(full_text),
        price=price,
        images=images,
        contacts={k: v for k, v in {"contact": contact, "email": email.group(0) if email else None}.items() if v},
        extra={"tab": tab, "card_id": section.get("id")},
    )


def parse_page(html: str) -> list[ParsedLot]:
    soup = BeautifulSoup(html, "lxml")
    lots: dict[str, ParsedLot] = {}
    for section in soup.select("section.constructor-block-description-card"):
        if (lot := parse_card(section)) and lot.source_id not in lots:
            lots[lot.source_id] = lot
    return list(lots.values())


class BccParser(Parser):
    name = "bcc"
    title = "Bank CenterCredit"
    base_url = URL

    def fetch(self, http: HttpClient, known: Mapping[str, float | None]) -> Iterator[ParsedLot]:
        yield from parse_page(http.get(URL).text)
