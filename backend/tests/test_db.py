"""Автомиграция: новые колонки моделей добавляются в старую базу."""

import sqlite3
import tempfile
from pathlib import Path

from sqlalchemy import create_engine, inspect

from torgi import db


def test_add_missing_columns(monkeypatch):
    path = Path(tempfile.mkdtemp()) / "old.db"
    with sqlite3.connect(path) as conn:  # «старая» таблица без колонки documents
        conn.execute("CREATE TABLE lots (id INTEGER PRIMARY KEY, source VARCHAR(32))")
    engine = create_engine(f"sqlite:///{path}")
    monkeypatch.setattr(db, "engine", engine)
    db.init_db()
    columns = {c["name"] for c in inspect(engine).get_columns("lots")}
    assert {"documents", "price_per_m2", "status"} <= columns
    db.init_db()  # повторный запуск ничего не ломает
