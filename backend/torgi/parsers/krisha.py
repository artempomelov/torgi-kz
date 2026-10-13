"""krisha.kz — отобранные вручную объявления о продаже с торгов и залогов банков, которых нет у других источников.

Крыша — доска объявлений, а не площадка торгов: большинство банковских залогов там дублирует halykzalog,
BCC, Alatau и другие наши источники (сверка 13.10.2026: 362 объявления совпали с 250 нашими лотами).
Поэтому берём не всю выдачу, а только список CURATED — проверенные объявления, которых у нас больше нигде нет
(отбор — backend/scripts/krisha_auctions.py). Объявление сняли с Крыши — лот уходит с сайта, как у остальных.
Контакты продавца не берём: телефон на Крыше открывается по кнопке — ведём на страницу объявления.
"""

import json
import re
from collections.abc import Iterator, Mapping

from bs4 import BeautifulSoup

from torgi import normalize as nz
from torgi.parsers.base import HttpClient, ParsedLot, Parser

SITE = "https://krisha.kz"
CATEGORIES = {"kvartiry": "apartment", "doma-dachi": "house", "kommercheskaya-nedvizhimost": "commercial",
              "uchastkov": "land", "prombazy": "industrial"}

# id объявления → вид продажи (определён по тексту объявления при отборе)
CURATED: dict[str, dict] = {
    "47919177": {"origin": "bank_pledge", "sale_type": "direct", "note": "залог АО Kaspi Bank"},
    "1012117198": {"origin": "bank_pledge", "sale_type": "direct", "note": "адресная реализация залога банка"},
    "1015060721": {"origin": "arrested", "sale_type": "auction", "note": "торги ЧСИ"},
}

_DATA_RE = re.compile(r"window\.data = (\{.*?\});\s*\n", re.S)


def parse_ad(html: str, ad_id: str, meta: dict) -> ParsedLot | None:
    m = _DATA_RE.search(html)
    if not m:
        return None
    ad = json.loads(m.group(1)).get("advert") or {}
    if ad.get("status") not in (None, "live"):
        return None  # снято или в архиве
    soup = BeautifulSoup(html, "lxml")
    descr_el = soup.select_one(".js-description")
    description = nz.clean_text(descr_el.get_text("\n", strip=True)) if descr_el else None
    info = {}
    for item in soup.select(".offer__info-item"):
        name, value = item.select_one(".offer__info-title"), item.select_one(".offer__advert-short-info")
        if name and value:
            for a in value.select("a.btm-map"):
                a.decompose()  # «показать на карте»
            info[name.get_text(strip=True)] = value.get_text(" ", strip=True)
    place = info.get("Город", "")  # «Алматы, Алатауский р-н»
    title = ad.get("title") or "Объект"
    address = ", ".join(p for p in (place, ad.get("addressTitle")) if p) or None
    category = CATEGORIES.get(ad.get("categoryAlias") or "", None) or nz.classify_category(title, description)
    text = f"{title}\n{address or ''}\n{description or ''}"
    city = nz.detect_city(place, address)
    land_ha = nz.parse_land_ha(title) or nz.parse_land_ha(text)
    if not land_ha and (sot := re.search(r"([\d.]+)\s*сот", title)):
        land_ha = float(sot.group(1)) / 100
    area = nz.parse_number(ad.get("square"))
    return ParsedLot(
        source_id=ad_id,
        url=f"{SITE}/a/show/{ad_id}",
        title=f"{title}, {address}" if address else title,
        origin=meta["origin"],
        category=category,
        sale_type=meta.get("sale_type"),
        description=description,
        region=nz.normalize_region(place, address, city=city),
        city=city,
        address=address,
        lat=nz.parse_number((ad.get("map") or {}).get("lat")),
        lon=nz.parse_number((ad.get("map") or {}).get("lon")),
        area_m2=None if category == "land" else area,
        land_area_ha=land_ha,
        rooms=nz.parse_int(ad.get("rooms")),
        cadastral=nz.parse_cadastral(text),
        price=nz.parse_number(ad.get("price")),
        images=[p["src"] for p in ad.get("photos") or [] if p.get("src")][:15],
        extra={"note": meta.get("note")},
    )


class KrishaParser(Parser):
    name = "krisha"
    title = "Крыша (krisha.kz)"
    base_url = SITE

    def fetch(self, http: HttpClient, known: Mapping[str, float | None]) -> Iterator[ParsedLot]:
        for ad_id, meta in CURATED.items():
            url = f"{SITE}/a/show/{ad_id}"
            http._wait(url)
            resp = http.client.get(url)
            if resp.status_code == 404:
                continue  # объявление удалено — лот снимется с сайта
            if resp.status_code != 200:
                # 468 — защита Крыши от ботов: прерываем запуск, чтобы не снять все лоты по ошибке
                raise RuntimeError(f"krisha.kz {ad_id}: HTTP {resp.status_code}")
            if lot := parse_ad(resp.text, ad_id, meta):
                yield lot
