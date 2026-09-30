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
