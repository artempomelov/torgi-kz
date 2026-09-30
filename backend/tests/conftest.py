"""Все тесты работают с временной SQLite — рабочая база backend/torgi.db не затрагивается."""

import os
import tempfile

os.environ["TORGI_DATABASE_URL"] = f"sqlite:///{tempfile.mkdtemp()}/test.db"
os.environ["TORGI_TELEGRAM_BOT_TOKEN"] = "123456:TEST-TOKEN"
os.environ["TORGI_COOKIE_SECURE"] = "false"
os.environ["TORGI_SECRET_KEY"] = "test-secret"
