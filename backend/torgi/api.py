"""REST API для сайта, Telegram-бота и приложения."""

from contextlib import asynccontextmanager
from datetime import datetime
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from torgi import auth
from torgi import normalize as nz
from torgi.config import settings
from torgi.db import get_session, init_db
from torgi.models import Lot, ParseRun, User, utcnow
from torgi.parsers import PARSERS

@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="torgi.kz API", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_methods=["GET", "POST"],
                   allow_headers=["*"], allow_credentials=True)

SessionDep = Annotated[Session, Depends(get_session)]


class LotShort(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source: str
    url: str
    origin: str
    sale_type: str | None
    category: str
    title: str
    region: str | None
    city: str | None
    address: str | None
    lat: float | None
    lon: float | None
    area_m2: float | None
    land_area_ha: float | None
    rooms: int | None
    floor: int | None
    floors_total: int | None
    price: float | None
    price_per_m2: float | None
    min_price: float | None = None
    auction_start: datetime | None
    auction_end: datetime | None
    applications_deadline: datetime | None
    image: str | None = None
    flags: list[str]
    status: str
    first_seen_at: datetime
    price_drop_pct: float | None = None
    listed_at: datetime | None = None  # когда объявление появилось у источника (или у нас)


class PricePoint(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    price: float | None
    seen_at: datetime


class LotFull(LotShort):
    documents: list[dict] | None = None
    description: str | None
    year_built: int | None
    cadastral: str | None
    deposit: float | None
    images: list[str]
    contacts: dict
    extra: dict
    published_at: datetime | None
    last_seen_at: datetime
    price_history: list[PricePoint]


class LotPage(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[LotShort]


def _drop_pct(lot: Lot) -> float | None:
    prices = [p.price for p in nz.real_price_history(lot.price_history)]
    if len(prices) < 2 or not lot.price or prices[0] <= lot.price:
        return None
    return round((prices[0] - lot.price) / prices[0] * 100, 1)


def _short(lot: Lot) -> LotShort:
    item = LotShort.model_validate(lot)
    item.image = lot.images[0] if lot.images else None
    item.price_drop_pct = _drop_pct(lot)
    item.listed_at = lot.published_at or lot.first_seen_at
    return item


SORTS = {
    "new": Lot.first_seen_at.desc(),
    "price_asc": Lot.price.asc(),
    "price_desc": Lot.price.desc(),
    "price_m2_asc": Lot.price_per_m2.asc(),
    "deadline": Lot.auction_start.asc(),
}


@app.get("/api/lots", response_model=LotPage)
def list_lots(
    session: SessionDep,
    q: str | None = None,
    category: Annotated[list[str] | None, Query()] = None,
    source: Annotated[list[str] | None, Query()] = None,
    origin: Annotated[list[str] | None, Query()] = None,
    sale_type: Annotated[list[str] | None, Query()] = None,
    region: str | None = None,
    city: str | None = None,
    price_min: float | None = None,
    price_max: float | None = None,
    area_min: float | None = None,
    area_max: float | None = None,
    ppm_min: float | None = None,  # цена за м² — квартиры и коммерция
    ppm_max: float | None = None,
    rooms: Annotated[list[int] | None, Query()] = None,
    with_auction_date: bool = False,
    include_removed: bool = False,
    sort: Literal["new", "price_asc", "price_desc", "price_m2_asc", "deadline"] = "new",
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 24,
):
    stmt = select(Lot)
    if not include_removed:
        stmt = stmt.where(Lot.status == "active")
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(Lot.title.ilike(like), Lot.address.ilike(like), Lot.cadastral.ilike(like)))
    for column, values in ((Lot.category, category), (Lot.source, source), (Lot.origin, origin),
                           (Lot.sale_type, sale_type), (Lot.rooms, rooms)):
        if values:
            stmt = stmt.where(column.in_(values))
    if region:
        stmt = stmt.where(Lot.region == region)
    if city:
        stmt = stmt.where(Lot.city == city)
    if price_min is not None:
        stmt = stmt.where(Lot.price >= price_min)
    if price_max is not None:
        stmt = stmt.where(Lot.price <= price_max)
    if area_min is not None:
        stmt = stmt.where(Lot.area_m2 >= area_min)
    if area_max is not None:
        stmt = stmt.where(Lot.area_m2 <= area_max)
    if ppm_min is not None or ppm_max is not None:
        stmt = stmt.where(Lot.category.in_(("apartment", "commercial")), Lot.price_per_m2.is_not(None))
        if ppm_min is not None:
            stmt = stmt.where(Lot.price_per_m2 >= ppm_min)
        if ppm_max is not None:
            stmt = stmt.where(Lot.price_per_m2 <= ppm_max)
    if with_auction_date or sort == "deadline":
        # только предстоящие или идущие торги
        stmt = stmt.where(func.coalesce(Lot.auction_end, Lot.auction_start) >= utcnow())

    total = session.scalar(select(func.count()).select_from(stmt.subquery()))
    stmt = stmt.order_by(SORTS[sort].nulls_last(), Lot.id.desc()).offset((page - 1) * page_size).limit(page_size)
    lots = session.scalars(stmt.options(selectinload(Lot.price_history))).all()
    return LotPage(total=total or 0, page=page, page_size=page_size, items=[_short(lot) for lot in lots])


@app.get("/api/lots/{lot_id}", response_model=LotFull)
def get_lot(lot_id: int, session: SessionDep):
    lot = session.get(Lot, lot_id, options=[selectinload(Lot.price_history)])
    if lot is None:
        raise HTTPException(404, "Лот не найден")
    item = LotFull.model_validate(lot)
    item.image = lot.images[0] if lot.images else None
    item.price_drop_pct = _drop_pct(lot)
    return item


@app.get("/api/meta")
def meta(session: SessionDep):
    """Справочники для фильтров + счётчики активных лотов."""
    active = Lot.status == "active"

    def counts(column):
        rows = session.execute(select(column, func.count()).where(active).group_by(column)).all()
        return {k: v for k, v in rows if k is not None}

    return {
        "categories": [{"id": k, "title": v, "count": counts(Lot.category).get(k, 0)} for k, v in nz.CATEGORIES.items()],
        "origins": [{"id": k, "title": v} for k, v in nz.ORIGINS.items()],
        "sale_types": [{"id": k, "title": v} for k, v in nz.SALE_TYPES.items()],
        "sources": [{"id": k, "title": p.title, "url": p.base_url, "count": counts(Lot.source).get(k, 0)}
                    for k, p in PARSERS.items()],
        "regions": [{"id": r, "count": counts(Lot.region).get(r, 0)} for r in nz.REGIONS],
        "total": session.scalar(select(func.count()).where(active)),
    }


@app.get("/api/health")
def health(session: SessionDep):
    last = {}
    for name in PARSERS:
        run = session.scalars(
            select(ParseRun).where(ParseRun.source == name).order_by(ParseRun.started_at.desc()).limit(1)
        ).first()
        last[name] = None if run is None else {
            "status": run.status, "started_at": run.started_at, "found": run.found, "error": run.error,
        }
    return {"ok": True, "parsers": last}


# --- Вход и закрытые данные (платный режим) ----------------------------------------


def current_user(request: Request, session: SessionDep) -> User | None:
    uid = auth.read_session_token(request.cookies.get(auth.COOKIE_NAME))
    return session.get(User, uid) if uid else None


UserDep = Annotated[User | None, Depends(current_user)]


class TelegramAuthIn(BaseModel):
    id: int
    first_name: str | None = None
    last_name: str | None = None
    username: str | None = None
    photo_url: str | None = None
    auth_date: int
    hash: str


class MeOut(BaseModel):
    authenticated: bool
    name: str | None = None
    username: str | None = None
    photo_url: str | None = None
    subscription_until: datetime | None = None
    free_per_day: int
    remaining_today: int | None = None


def _me(session: Session, user: User | None) -> MeOut:
    limit = settings.free_details_per_day
    if user is None:
        return MeOut(authenticated=False, free_per_day=limit)
    remaining = limit if user.has_subscription() else max(0, limit - auth.views_today(session, user))
    return MeOut(
        authenticated=True,
        name=" ".join(x for x in (user.first_name, user.last_name) if x) or user.username,
        username=user.username,
        photo_url=user.photo_url,
        subscription_until=user.subscription_until if user.has_subscription() else None,
        free_per_day=limit,
        remaining_today=remaining,
    )


@app.post("/api/auth/telegram", response_model=MeOut)
def auth_telegram(payload: TelegramAuthIn, response: Response, session: SessionDep):
    if not settings.telegram_bot_token:
        raise HTTPException(503, "Вход через Telegram не настроен")
    try:
        tg = auth.check_telegram_auth(payload.model_dump(), settings.telegram_bot_token)
    except auth.AuthError as exc:
        raise HTTPException(401, f"Не удалось войти: {exc}") from exc
    user = auth.upsert_user(session, tg)
    response.set_cookie(
        auth.COOKIE_NAME, auth.make_session_token(user.id), max_age=settings.session_days * 86400,
        httponly=True, secure=settings.cookie_secure, samesite="lax", path="/",
    )
    return _me(session, user)


@app.post("/api/auth/logout")
def auth_logout(response: Response):
    response.delete_cookie(auth.COOKIE_NAME, path="/")
    return {"ok": True}


@app.get("/api/me", response_model=MeOut)
def me(session: SessionDep, user: UserDep):
    return _me(session, user)


class LotDetailsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    title: str
    address: str | None
    lat: float | None
    lon: float | None
    cadastral: str | None
    url: str
    contacts: dict
    description: str | None
    extra: dict
    price_history: list[PricePoint]
    documents: list[dict] | None = None
    remaining_today: int | None = None


@app.get("/api/lots/{lot_id}/details", response_model=LotDetailsOut)
def lot_details(lot_id: int, session: SessionDep, user: UserDep):
    """Закрытые поля лота (GATED_FIELDS): только после входа, бесплатно N лотов в день, по подписке — все."""
    lot = session.get(Lot, lot_id, options=[selectinload(Lot.price_history)])
    if lot is None:
        raise HTTPException(404, "Лот не найден")
    if user is None:
        raise HTTPException(401, "Войдите, чтобы открыть адрес и контакты")
    allowed, remaining = auth.grant_details(session, user, lot.id)
    if not allowed:
        raise HTTPException(402, f"Бесплатный лимит — {settings.free_details_per_day} объектов в день — исчерпан")
    out = LotDetailsOut.model_validate(lot)
    out.remaining_today = None if user.has_subscription() else remaining
    return out
