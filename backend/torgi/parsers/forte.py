"""sale.forte.kz — имущество ForteBank. Открытый Strapi v5 GraphQL, все объекты одним запросом."""

import re
from collections.abc import Iterator, Mapping

from torgi import normalize as nz
from torgi.parsers.base import HttpClient, ParsedLot, Parser

SITE = "https://sale.forte.kz"
GRAPHQL = "https://forte-strapi.forte.kz/graphql"

QUERY = """
query($l: I18NLocaleCode) {
  sales_connection(locale: $l, pagination: {limit: -1}) {
    pageInfo { total }
    nodes {
      documentId slug address price area measurement year
      city { name } category { title }
      description additionalDescription auctionText isSpecialOffer
      latitude longitude images { url } manager { name phoneNumber }
    }
  }
}
"""

CATEGORY_TITLES = {
    "жилая недвижимость": None,  # квартира или дом — по тексту
    "коммерческая недвижимость": "commercial",
    "нежилое помещение": "commercial",
    "земельный участок": "land",
    "паркинг и гаражи": "parking",
    "промбазы и заводы": "industrial",
}

_AUCTION_RE = re.compile(r"аукцион|торг(?:ов|ах|и)\b|электронной торговой площадк", re.I)


def parse_node(node: dict) -> ParsedLot:
    address = (node.get("address") or "").strip()
    description = nz.clean_text(node.get("description"))
    cat_title = ((node.get("category") or {}).get("title") or "").strip().lower()
    category = CATEGORY_TITLES.get(cat_title)
    if category is None:
        category = nz.classify_category(address, description)
        if cat_title == "жилая недвижимость" and category not in ("apartment", "house"):
            category = "apartment" if re.search(r"квартир|кв\.", f"{address} {description}", re.I) else "house"

    area = nz.parse_number(node.get("area"))
    hectares = node.get("measurement") == "hectares"
    city_name = (node.get("city") or {}).get("name")
    city = nz.detect_city(city_name, address) or city_name
    floor, floors_total = nz.parse_floor(description)

    manager = node.get("manager") or {}
    return ParsedLot(
        source_id=node["documentId"],
        url=f"{SITE}/ru/sale/{node['slug']}",
        title=address or cat_title.capitalize(),
        origin="bank_balance",
        category=category,
        sale_type="auction" if _AUCTION_RE.search(description or "") else "direct",
        description=description,
        region=nz.normalize_region(address, city=city),
        city=city,
        address=address,
        lat=nz.parse_number(node.get("latitude")),
        lon=nz.parse_number(node.get("longitude")),
        area_m2=None if hectares else area,
        land_area_ha=area if hectares else nz.parse_land_ha(description),
        rooms=nz.parse_rooms(f"{address} {description}"),
        floor=floor,
        floors_total=floors_total,
        year_built=nz.parse_int(node.get("year")),
        cadastral=nz.parse_cadastral(description),
        price=nz.parse_number(node.get("price")),
        images=[img["url"] for img in node.get("images") or [] if img.get("url")],
        contacts={k: v for k, v in {"name": (manager.get("name") or "").strip(),
                                    "phone": manager.get("phoneNumber")}.items() if v},
        extra={"special_offer": bool(node.get("isSpecialOffer")),
               "installments": bool(re.search(r"рассрочк", description or "", re.I)),
               "category_title": cat_title or None},
    )


class ForteParser(Parser):
    name = "forte"
    title = "ForteBank (sale.forte.kz)"
    base_url = SITE

    def fetch(self, http: HttpClient, known: Mapping[str, float | None]) -> Iterator[ParsedLot]:
        data = http.post(GRAPHQL, json={"query": QUERY, "variables": {"l": "ru"}}).json()
        if data.get("errors"):
            raise RuntimeError(f"forte graphql: {data['errors']}")
        for node in data["data"]["sales_connection"]["nodes"]:
            yield parse_node(node)
