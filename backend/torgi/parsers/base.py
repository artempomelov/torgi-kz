import logging
import time
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from urllib.parse import urlparse

import httpx

from torgi.config import settings

log = logging.getLogger(__name__)


@dataclass
class ParsedLot:
    source_id: str
    url: str
    title: str
    origin: str
    category: str
    sale_type: str | None = None
    description: str | None = None
    region: str | None = None
    city: str | None = None
    address: str | None = None
    lat: float | None = None
    lon: float | None = None
    area_m2: float | None = None
    land_area_ha: float | None = None
    rooms: int | None = None
    floor: int | None = None
    floors_total: int | None = None
    year_built: int | None = None
    cadastral: str | None = None
    price: float | None = None
    deposit: float | None = None
    min_price: float | None = None  # аукцион на понижение: ниже этой цены не опустится
    auction_start: datetime | None = None
    auction_end: datetime | None = None
    applications_deadline: datetime | None = None
    published_at: datetime | None = None
    images: list[str] = field(default_factory=list)
    documents: list[dict[str, Any]] = field(default_factory=list)  # {"title", "url", "size"?}
    contacts: dict[str, Any] = field(default_factory=dict)
    extra: dict[str, Any] = field(default_factory=dict)
    # partial=True: деталь не загружалась (лот уже известен, цена та же) —
    # обновляем только цену и last_seen_at.
    partial: bool = False


class HttpClient:
    """httpx-клиент с паузой между запросами к одному хосту и повторами."""

    def __init__(self, delay: float | None = None, retries: int = 3):
        self.delay = settings.request_delay if delay is None else delay
        self.retries = retries
        self._last: dict[str, float] = {}
        self.client = httpx.Client(
            headers={"User-Agent": settings.user_agent, "Accept-Language": "ru-RU,ru;q=0.9"},
            timeout=settings.request_timeout,
            follow_redirects=True,
        )

    def _wait(self, url: str) -> None:
        host = urlparse(url).netloc
        elapsed = time.monotonic() - self._last.get(host, 0)
        if elapsed < self.delay:
            time.sleep(self.delay - elapsed)
        self._last[host] = time.monotonic()

    def request(self, method: str, url: str, **kwargs) -> httpx.Response:
        for attempt in range(1, self.retries + 1):
            self._wait(url)
            try:
                resp = self.client.request(method, url, **kwargs)
                if resp.status_code >= 500 or resp.status_code == 429:
                    raise httpx.HTTPStatusError(f"HTTP {resp.status_code}", request=resp.request, response=resp)
                resp.raise_for_status()
                return resp
            except (httpx.TransportError, httpx.HTTPStatusError) as exc:
                if attempt == self.retries or (
                    isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code < 500
                    and exc.response.status_code != 429
                ):
                    raise
                log.warning("%s %s: %s, повтор %d", method, url, exc, attempt)
                time.sleep(5 * attempt)
        raise RuntimeError("unreachable")

    def get(self, url: str, **kwargs) -> httpx.Response:
        return self.request("GET", url, **kwargs)

    def post(self, url: str, **kwargs) -> httpx.Response:
        return self.request("POST", url, **kwargs)

    def close(self) -> None:
        self.client.close()


class Parser:
    name: str = ""
    title: str = ""
    base_url: str = ""

    def fetch(self, http: HttpClient, known: Mapping[str, float | None]) -> Iterator[ParsedLot]:
        """Все актуальные лоты недвижимости источника.

        known — {source_id: цена} уже известных активных лотов; парсеры с дорогими
        детальными страницами используют его, чтобы не загружать их повторно.
        """
        raise NotImplementedError
