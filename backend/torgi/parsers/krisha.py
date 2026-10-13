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
from datetime import date, timedelta
from pathlib import Path

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
}
# Страницы объявлений закрыты от серверов (403/468) — данные берём из снимка, снятого в обычном браузере.
# Снимок действует SNAPSHOT_DAYS дней: не обновили — лоты уходят с сайта, чтобы не показывать снятые объявления.
SNAPSHOT = Path(__file__).with_name("krisha_snapshot.json")
SNAPSHOT_DAYS = 21

_DATA_RE = re.compile(r"window\.data = (\{.*?\});\s*\n", re.S)


def parse_ad(html: str, ad_id: str, meta: dict) -> ParsedLot | None:
    m = _DATA_RE.search(html)
    if not m:
        return None
    ad = json.loads(m.group(1)).get("advert") or {}
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
    ad["photos"] = [p["src"] for p in ad.get("photos") or [] if p.get("src")]
    return build_lot(ad, info, description, ad_id, meta)


def build_lot(ad: dict, info: dict, description: str | None, ad_id: str, meta: dict) -> ParsedLot | None:
    if ad.get("status") not in (None, "live"):
        return None  # снято или в архиве
    place = info.get("Город", "")  # «Алматы, Алатауский р-н»
    if place == "Казахстан":
        place = ""
    title = ad.get("title") or "Объект"
    address = ", ".join(p for p in (place, ad.get("addressTitle")) if p) or None
    category = CATEGORIES.get(ad.get("categoryAlias") or "", None) or nz.classify_category(title, description)
    text = f"{title}\n{address or ''}\n{description or ''}"
    city = nz.detect_city(place, address)
    land_ha = nz.parse_land_ha(title) or nz.parse_land_ha(text)
    if not land_ha and (sot := re.search(r"([\d.]+)\s*сот", title)):
        land_ha = float(sot.group(1)) / 100
    area = nz.parse_number(str(ad["square"])) if ad.get("square") else nz.parse_area_m2(title)
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
        images=list(ad.get("photos") or [])[:15],
        extra={"note": meta.get("note")},
    )


class KrishaParser(Parser):
    name = "krisha"
    title = "Крыша (krisha.kz)"
    base_url = SITE

    def fetch(self, http: HttpClient, known: Mapping[str, float | None]) -> Iterator[ParsedLot]:
        snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
        fresh = date.today() - date.fromisoformat(snapshot["captured_at"]) <= timedelta(days=SNAPSHOT_DAYS)
        for ad_id, meta in CURATED.items():
            url = f"{SITE}/a/show/{ad_id}"
            http._wait(url)
            resp = http.client.get(url)
            if resp.status_code == 404:
                continue  # объявление удалено — лот снимется с сайта
            if resp.status_code == 200 and (lot := parse_ad(resp.text, ad_id, meta)):
                yield lot
            elif fresh and (ad := snapshot["ads"].get(ad_id)):
                # страница закрыта защитой — берём снимок
                photos = [f"{ad['photos_base']}/{i}-full.jpg" for i in range(1, ad["photos_n"] + 1)] if ad.get("photos_base") else []
                if lot := build_lot({**ad, "photos": photos}, ad["info"], ad.get("description"), ad_id, meta):
                    yield lot
