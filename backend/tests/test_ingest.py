"""Загрузка в базу и API на временной SQLite."""

import os
import tempfile

os.environ["TORGI_DATABASE_URL"] = f"sqlite:///{tempfile.mkdtemp()}/test.db"

from fastapi.testclient import TestClient  # noqa: E402

from torgi import ingest  # noqa: E402
from torgi.api import app  # noqa: E402
from torgi.db import SessionLocal, init_db  # noqa: E402
from torgi.models import Lot  # noqa: E402
from torgi.parsers.base import ParsedLot, Parser  # noqa: E402


class FakeParser(Parser):
    name = "fake"
    title = "Fake"
    batches: list[list[ParsedLot]] = []

    def fetch(self, http, known):
        yield from self.batches.pop(0)


def lot(sid: str, price: float, **kw) -> ParsedLot:
    return ParsedLot(source_id=sid, url=f"https://example.kz/{sid}", title=f"Квартира {sid}", origin="bank_balance",
                     category="apartment", price=price, area_m2=50, city="Алматы", region="Алматы", **kw)


def run(batch):
    FakeParser.batches.append(batch)
    with SessionLocal() as session:
        return ingest.run_source(session, "fake", http=object())


def test_ingest_and_api(monkeypatch):
    monkeypatch.setitem(ingest.PARSERS, "fake", FakeParser)
    init_db()

    stats = run([lot("1", 30_000_000, lat=43.2, lon=76.9), lot("2", 20_000_000), lot("3", 10_000_000)])
    assert (stats.created, stats.removed) == (3, 0)

    # цена лота 1 снизилась, координаты не пришли (не должны затереться); лот 3 исчез
    stats = run([lot("1", 27_000_000), lot("2", 20_000_000)])
    assert (stats.created, stats.updated, stats.price_changed, stats.removed) == (0, 2, 1, 1)

    with SessionLocal() as session:
        lot1 = session.query(Lot).filter_by(source="fake", source_id="1").one()
        assert [p.price for p in lot1.price_history] == [30_000_000, 27_000_000]
        assert (lot1.lat, lot1.price_per_m2) == (43.2, 540_000)
        assert session.query(Lot).filter_by(source_id="3").one().status == "removed"

    # защита: источник вернул подозрительно мало — не снимаем остальные
    stats = run([])
    assert stats.removed == 0

    client = TestClient(app)
    page = client.get("/api/lots", params={"source": "fake", "sort": "price_asc"}).json()
    assert page["total"] == 2
    assert [i["price"] for i in page["items"]] == [20_000_000, 27_000_000]
    assert page["items"][1]["price_drop_pct"] == 10.0

    detail = client.get(f"/api/lots/{page['items'][1]['id']}").json()
    assert len(detail["price_history"]) == 2

    assert client.get("/api/lots", params={"price_max": 21_000_000}).json()["total"] == 1
    assert client.get("/api/lots", params={"q": "Квартира 2"}).json()["total"] == 1
    assert client.get("/api/lots/999999").status_code == 404
    meta = client.get("/api/meta").json()
    assert meta["total"] == 2

    # Выгрузка для сайта: открытый режим — всё есть; платный — закрытых полей нет нигде
    import json
    from pathlib import Path

    from torgi.export import GATED_FIELDS, export

    out = Path(tempfile.mkdtemp())
    with SessionLocal() as session:
        export(session, out)
        opened = json.loads((out / "lots-full.json").read_text(encoding="utf-8"))
        assert opened[0]["url"] and opened[0]["headline"].startswith("Квартира, 50 м² — Алматы")

        export(session, out, gated=True)
    for name in ("lots.json", "lots-full.json"):
        items = json.loads((out / name).read_text(encoding="utf-8"))
        assert items and all(not (GATED_FIELDS & item.keys()) for item in items)
        assert all(item["headline"] and item["price"] for item in items)
    assert json.loads((out / "meta.json").read_text(encoding="utf-8"))["gated"] is True
