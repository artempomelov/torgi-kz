from datetime import datetime, timezone

from sqlalchemy import JSON, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy import DateTime as _DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import TypeDecorator

from torgi.db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class DateTime(TypeDecorator):
    """Время всегда в UTC и всегда с часовым поясом — SQLite сам зону не хранит."""

    impl = _DateTime(timezone=True)
    cache_ok = True

    def __init__(self, timezone: bool = True):  # noqa: ARG002 — совместимость с сигнатурой DateTime
        super().__init__()

    def process_bind_param(self, value: datetime | None, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError(f"naive datetime: {value}")
        return value.astimezone(timezone.utc)

    def process_result_value(self, value: datetime | None, dialect):
        if value is None:
            return None
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


class Lot(Base):
    """Объект на продаже/торгах, нормализованный из любого источника."""

    __tablename__ = "lots"
    __table_args__ = (
        UniqueConstraint("source", "source_id", name="uq_lot_source"),
        Index("ix_lots_filter", "status", "category", "region"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(32), index=True)  # adilet, halyk, alatau, forte, bcc, freedom
    source_id: Mapped[str] = mapped_column(String(128))
    url: Mapped[str] = mapped_column(String(512))

    # arrested — арест (ЧСИ), bank_balance — имущество банка, bank_pledge — залог, court — судебная реализация
    origin: Mapped[str] = mapped_column(String(32))
    # auction, auction_down (голландский), direct (прямая/адресная продажа), tender
    sale_type: Mapped[str | None] = mapped_column(String(32))
    category: Mapped[str] = mapped_column(String(32), index=True)  # см. normalize.CATEGORIES

    title: Mapped[str] = mapped_column(String(512))
    description: Mapped[str | None] = mapped_column(Text)

    region: Mapped[str | None] = mapped_column(String(64))
    city: Mapped[str | None] = mapped_column(String(128), index=True)
    address: Mapped[str | None] = mapped_column(String(512))
    lat: Mapped[float | None] = mapped_column(Float)
    lon: Mapped[float | None] = mapped_column(Float)

    area_m2: Mapped[float | None] = mapped_column(Float)
    land_area_ha: Mapped[float | None] = mapped_column(Float)
    rooms: Mapped[int | None] = mapped_column(Integer)
    floor: Mapped[int | None] = mapped_column(Integer)
    floors_total: Mapped[int | None] = mapped_column(Integer)
    year_built: Mapped[int | None] = mapped_column(Integer)
    cadastral: Mapped[str | None] = mapped_column(String(64))

    price: Mapped[float | None] = mapped_column(Float, index=True)  # тенге
    price_per_m2: Mapped[float | None] = mapped_column(Float)
    deposit: Mapped[float | None] = mapped_column(Float)
    auction_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    auction_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    applications_deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    images: Mapped[list] = mapped_column(JSON, default=list)
    contacts: Mapped[dict] = mapped_column(JSON, default=dict)
    extra: Mapped[dict] = mapped_column(JSON, default=dict)  # прочие характеристики источника
    flags: Mapped[list] = mapped_column(JSON, default=list)  # например, suspicious_price

    status: Mapped[str] = mapped_column(String(16), default="active", index=True)  # active, removed
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    removed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    price_history: Mapped[list["PriceChange"]] = relationship(
        back_populates="lot", order_by="PriceChange.seen_at", cascade="all, delete-orphan"
    )


class PriceChange(Base):
    """История цены: запись при первом появлении и при каждом изменении."""

    __tablename__ = "price_changes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lot_id: Mapped[int] = mapped_column(ForeignKey("lots.id", ondelete="CASCADE"), index=True)
    price: Mapped[float | None] = mapped_column(Float)
    seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    lot: Mapped[Lot] = relationship(back_populates="price_history")


class ChannelPost(Base):
    """Публикации лотов в Telegram-канале (чтобы не постить дважды)."""

    __tablename__ = "channel_posts"
    __table_args__ = (UniqueConstraint("lot_id", "channel", name="uq_channel_post"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lot_id: Mapped[int] = mapped_column(ForeignKey("lots.id", ondelete="CASCADE"), index=True)
    channel: Mapped[str] = mapped_column(String(64))
    message_id: Mapped[int | None] = mapped_column(Integer)  # None — помечен без публикации (бэкфилл)
    posted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ParseRun(Base):
    """Журнал запусков парсеров — для мониторинга."""

    __tablename__ = "parse_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(32), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(16), default="running")  # running, ok, error
    found: Mapped[int] = mapped_column(Integer, default=0)
    created: Mapped[int] = mapped_column(Integer, default=0)
    updated: Mapped[int] = mapped_column(Integer, default=0)
    price_changed: Mapped[int] = mapped_column(Integer, default=0)
    removed: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text)
