"""Загрузка лотов источника в базу: upsert, история цен, снятие исчезнувших."""

import logging
from dataclasses import asdict, dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from torgi import normalize as nz
from torgi.config import settings
from torgi.models import Lot, ParseRun, PriceChange, utcnow
from torgi.parsers import PARSERS
from torgi.parsers.base import HttpClient, ParsedLot

log = logging.getLogger(__name__)

# Поля, которые partial-обновление (без детальной страницы) не трогает
_SERVICE_FIELDS = {"source_id", "partial"}


@dataclass
class Stats:
    found: int = 0
    created: int = 0
    updated: int = 0
    price_changed: int = 0
    removed: int = 0


def _is_empty(value) -> bool:
    return value is None or value == [] or value == {} or value == ""


def apply(session: Session, source: str, parsed: ParsedLot, existing: Lot | None, stats: Stats) -> Lot:
    now = utcnow()
    if existing is None:
        data = {k: v for k, v in asdict(parsed).items() if k not in _SERVICE_FIELDS}
        lot = Lot(source=source, source_id=parsed.source_id, first_seen_at=now, last_seen_at=now, updated_at=now,
                  status="active", **data)
        lot.price_history.append(PriceChange(price=parsed.price, seen_at=now))
        session.add(lot)
        stats.created += 1
    else:
        lot = existing
        if lot.status != "active":
            lot.status, lot.removed_at = "active", None
        if parsed.price != lot.price and parsed.price is not None:
            lot.price_history.append(PriceChange(price=parsed.price, seen_at=now))
            lot.price = parsed.price
            stats.price_changed += 1
        if not parsed.partial:
            # Пустые значения не затирают ранее полученные (например, координаты из детали)
            for key, value in asdict(parsed).items():
                if key in _SERVICE_FIELDS or key == "price" or _is_empty(value):
                    continue
                if getattr(lot, key) != value:
                    setattr(lot, key, value)
        lot.last_seen_at = now
        lot.updated_at = now
        stats.updated += 1

    lot.address = nz.clean_address(lot.address)
    lot.city, lot.region = nz.reconcile_place(lot.city, lot.region, lot.address, lot.title)
    lot.cadastral = nz.valid_cadastral(lot.cadastral)
    deal = nz.deal_flags(lot.title, lot.description)
    # у аренды стартовая цена бывает в несколько тысяч ₸ — это не ошибка ввода
    quality = [] if "rent" in deal else nz.quality_flags(lot.category, lot.price, lot.area_m2)
    lot.flags = quality + deal
    lot.price_per_m2 = (
        round(lot.price / lot.area_m2)
        if lot.price and lot.area_m2 and lot.category != "land" and not lot.flags else None
    )
    return lot


def run_source(session: Session, source: str, http: HttpClient | None = None, full: bool = False) -> Stats:
    """full=True — заново загрузить детальные данные всех лотов (документы, координаты, контакты)."""
    parser = PARSERS[source]()
    run = ParseRun(source=source)
    session.add(run)
    session.commit()

    existing = {lot.source_id: lot for lot in session.scalars(select(Lot).where(Lot.source == source))}
    known = {sid: lot.price for sid, lot in existing.items() if lot.status == "active"}
    stats = Stats()
    seen: set[str] = set()
    own_http = http is None
    http = http or HttpClient()
    try:
        for parsed in parser.fetch(http, {} if full else known):
            if parsed.source_id in seen:
                continue
            seen.add(parsed.source_id)
            stats.found += 1
            if parsed.partial and parsed.source_id not in existing:
                continue  # теоретически невозможно: partial бывает только для известных
            existing[parsed.source_id] = apply(session, source, parsed, existing.get(parsed.source_id), stats)
            if stats.found % 50 == 0:
                session.commit()
                log.info("%s: обработано %d", source, stats.found)

        # Снимаем исчезнувшие — только если парсинг правдоподобен
        active_before = len(known)
        if active_before and stats.found < active_before * settings.removal_guard_ratio:
            log.warning("%s: найдено %d при %d активных — снятие пропущено", source, stats.found, active_before)
        else:
            now = utcnow()
            for sid, lot in existing.items():
                if lot.status == "active" and sid not in seen:
                    lot.status, lot.removed_at = "removed", now
                    stats.removed += 1

        run.status = "ok"
    except Exception as exc:
        session.rollback()
        run = session.merge(run)
        run.status, run.error = "error", repr(exc)
        log.exception("%s: ошибка парсинга", source)
        raise
    finally:
        run.finished_at = utcnow()
        for key, value in asdict(stats).items():
            setattr(run, key, value)
        session.commit()
        if own_http:
            http.close()
    log.info("%s: %s", source, stats)
    return stats
