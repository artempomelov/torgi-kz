from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="TORGI_", env_file=".env", extra="ignore")

    # Локально — SQLite, на сервере — postgresql+psycopg://user:pass@host/torgi
    database_url: str = "sqlite:///./torgi.db"

    # Вежливый обход источников
    user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/128.0 Safari/537.36"
    )
    request_delay: float = 1.0  # секунд между запросами к одному хосту
    request_timeout: float = 60.0

    # Если источник вернул меньше этой доли от ранее активных лотов,
    # не снимаем «исчезнувшие» лоты — скорее всего, сбой парсинга.
    removal_guard_ratio: float = 0.5

    site_url: str = "https://torgi.kz"

    # Telegram: токен от @BotFather; бот должен быть администратором канала
    telegram_bot_token: str | None = None
    telegram_channel: str | None = None  # "@имя_канала" или числовой id
    telegram_post_delay: float = 4.0  # секунд между постами (лимит Telegram ~20 сообщений/мин в канал)
    # Выпуски (решение владельца от 20.10.2026): в каждый канал по telegram_batch постов в часы telegram_slots
    # по Алматы — 3 × 3 = 9 постов в день; пропущенный выпуск догоняется следующим запуском (не больше одного выпуска)
    telegram_slots: tuple[int, ...] = (10, 14, 19)
    telegram_batch: int = 3
    # Региональные/тематические каналы: JSON {"@канал": {"region": "Алматы"} | {"category": ["commercial"]}, ...}
    telegram_channels: str = ""
    # выгрузка сайта: плашка «−N% к рынку» на главном фото поста берётся из её поля market (torgi/badge.py)
    telegram_badges: str = "../web/data/lots.json"
    telegram_admins: str = ""  # username администраторов через запятую — им приходят заявки и вопросы
    telegram_hours: tuple[int, int] = (9, 21)  # публикуем с 9:00 до 21:00 по Алматы

    # Вход и платный доступ (готово заранее, включается на сайте флагами NEXT_PUBLIC_PAYWALL/AUTH).
    # Вход — Telegram Login Widget того же бота (в @BotFather: /setdomain torgi.kz).
    secret_key: str = "dev-secret-change-me"  # подпись сессий; на сервере — длинная случайная строка
    session_days: int = 30
    free_details_per_day: int = 5
    cookie_secure: bool = True  # локально по http — TORGI_COOKIE_SECURE=false

    cors_origins: list[str] = [
        "http://localhost:3000",
        "https://torgi.kz",
        "https://www.torgi.kz",
    ]


settings = Settings()
