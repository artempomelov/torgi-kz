-- База D1 для worker/src/index.js. Применяется при каждом деплое (идемпотентно).
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  telegram_id INTEGER NOT NULL UNIQUE,
  first_name TEXT,
  last_name TEXT,
  username TEXT,
  photo_url TEXT,
  subscription_until TEXT,
  created_at TEXT NOT NULL,
  last_login_at TEXT NOT NULL
);

-- Открытые закрытые карточки: лимит считается по дням (дата по Алматы)
CREATE TABLE IF NOT EXISTS views (
  user_id INTEGER NOT NULL,
  lot_id INTEGER NOT NULL,
  day TEXT NOT NULL,
  created_at TEXT NOT NULL,
  UNIQUE (user_id, lot_id, day)
);
CREATE INDEX IF NOT EXISTS views_user_day ON views (user_id, day);

-- Просмотры карточек (посетитель — хэш IP и браузера за сутки) и избранное (анонимный id браузера)
CREATE TABLE IF NOT EXISTS hits (
  lot_id INTEGER NOT NULL,
  day TEXT NOT NULL,
  visitor TEXT NOT NULL,
  UNIQUE (lot_id, day, visitor)
);
CREATE INDEX IF NOT EXISTS hits_lot_day ON hits (lot_id, day);
CREATE TABLE IF NOT EXISTS favs (
  lot_id INTEGER NOT NULL,
  client TEXT NOT NULL,
  UNIQUE (lot_id, client)
);

-- Закрытые поля лотов (JSON) и их хэш — загружаются только изменившиеся
CREATE TABLE IF NOT EXISTS lots_private (
  id INTEGER PRIMARY KEY,
  data TEXT NOT NULL,
  hash TEXT NOT NULL
);

-- Подписки на поиск по email (Brevo). code — тот же код фильтра, что у Telegram-бота (q-…).
-- Письмо с подтверждением шлёт worker; новые лоты — backend/torgi/email_notify.py из GitHub Actions.
CREATE TABLE IF NOT EXISTS email_subs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  email TEXT NOT NULL,
  code TEXT NOT NULL,
  token TEXT NOT NULL UNIQUE,
  confirmed INTEGER NOT NULL DEFAULT 0,
  ip TEXT,
  created_at TEXT NOT NULL,
  checked_at TEXT,
  UNIQUE (email, code)
);
CREATE INDEX IF NOT EXISTS email_subs_ip ON email_subs (ip, created_at);
