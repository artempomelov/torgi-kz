"""berekebank.kz — залоговое имущество Bereke Bank. HTML (OctoberCMS): список ?page=N, детали /ru/about/collaterals/{id}."""

import re
from collections.abc import Iterator, Mapping

import httpx
from bs4 import BeautifulSoup

from torgi import normalize as nz
from torgi.parsers.base import HttpClient, ParsedLot, Parser

SITE = "https://berekebank.kz"
LIST_URL = f"{SITE}/ru/about/collaterals"
_ID_RE = re.compile(r"/ru/about/collaterals/(\d+)")


def parse_list(page: str) -> list[dict]:
    soup = BeautifulSoup(page, "lxml")
    out = []
    for card in soup.select("a.property-card[href]"):
        m = _ID_RE.search(card["href"])
        if not m:
            continue
        meta = card.select_one(".meta")
        title = meta.select_one("div > div") if meta else None
        price = card.select_one("span.whitespace-nowrap")
        out.append({
            "id": m.group(1),
            "title": re.sub(r"\s*[\d\s]+₸\s*$", "", title.get_text(" ", strip=True)) if title else "",
            "price": nz.parse_number(price.get_text()) if price else None,
            "summary": card.select_one(".line-clamp-4").get_text(" ", strip=True) if card.select_one(".line-clamp-4") else "",
        })
    return out


def parse_detail(page: str) -> dict:
    soup = BeautifulSoup(page, "lxml")
    lines = soup.get_text("\n", strip=True).split("\n")

    def after(label: str) -> str | None:
        for i, ln in enumerate(lines):
            if ln == label and i + 1 < len(lines):
                return lines[i + 1]
        return None

    about = None
    if "Об имуществе" in lines:
        i = lines.index("Об имуществе")
        end = lines.index("Похожие объявления") if "Похожие объявления" in lines else i + 10
        about = "\n".join(lines[i + 1:end])
    own = page.split("Похожие объявления")[0]  # ниже — карточки других лотов
    photos = list(dict.fromkeys(re.findall(r'(https://site-cdn\.berekebank\.kz/[^"\s]*/media/Collaterals/[^"\s]+)', own)))
    return {"area": nz.parse_number(after("Общая площадь")), "address": after("Адрес"),
            "phone": after("Менеджер по продажам"), "description": nz.clean_text(about), "photos": photos}


def build_lot(card: dict, detail: dict | None) -> ParsedLot | None:
    detail = detail or {}
    title = card["title"]
    description = detail.get("description") or card.get("summary")
    text = f"{title}\n{description or ''}"
    category = nz.classify_category(title, description)
    if category == "other" and re.search(r"авто|транспорт|оборудован|спецтехн", title, re.I):
        return None
    address = detail.get("address")
    city = nz.detect_city(address, title, description)
    floor, floors_total = nz.parse_floor(text)
    return ParsedLot(
        source_id=card["id"],
        url=f"{LIST_URL}/{card['id']}",
        title=f"{title}, {address}" if address else title,
        origin="bank_pledge",
        category=category,
        sale_type="direct",
        description=description,
        region=nz.normalize_region(address, description, city=city),
        city=city,
        address=address,
        area_m2=None if category == "land" else (detail.get("area") or nz.parse_area_m2(text)),
        land_area_ha=nz.parse_land_ha(text),
        rooms=nz.parse_rooms(text),
        floor=floor,
        floors_total=floors_total,
        cadastral=nz.parse_cadastral(text),
        price=card.get("price"),
        images=detail.get("photos") or [],
        contacts={"phone": detail["phone"]} if detail.get("phone") else {},
    )


class BerekeParser(Parser):
    name = "bereke"
    title = "Bereke Bank"
    base_url = LIST_URL

    def fetch(self, http: HttpClient, known: Mapping[str, float | None]) -> Iterator[ParsedLot]:
        seen: set[str] = set()
        for page in range(1, 50):
            cards = [c for c in parse_list(http.get(LIST_URL, params={"page": page}).text) if c["id"] not in seen]
            if not cards:
                break  # страница за последней повторяет уже виденные лоты
            for card in cards:
                seen.add(card["id"])
                if card["id"] in known and known[card["id"]] == card["price"]:
                    yield ParsedLot(source_id=card["id"], url=f"{LIST_URL}/{card['id']}", title=card["title"],
                                    origin="bank_pledge", category="other", price=card["price"], partial=True)
                    continue
                try:
                    detail = parse_detail(http.get(f"{LIST_URL}/{card['id']}").text)
                except httpx.HTTPError:
                    detail = None
                if lot := build_lot(card, detail):
                    yield lot
