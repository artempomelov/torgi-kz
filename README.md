# torgi.kz — агрегатор торгов недвижимостью в Казахстане

Сайт **torgi.kz** (+ 301-редиректы с vsetorgi.kz и torgi-nedvizhimost.kz), Telegram-канал и мобильное приложение
на общем API.

```
backend/   Python: парсеры источников, база (SQLite локально / PostgreSQL на сервере), REST API (FastAPI)
web/       Сайт: Next.js 16 (App Router, Tailwind)
deploy/    nginx: основной домен и редиректы
docs/      Исследование источников
```

## Источники

| id | Источник | Что | Способ |
|---|---|---|---|
| `adilet` | etp.adilet.gov.kz | арестованное имущество (ЧСИ) | JSON внутри HTML |
| `halyk` | halykzalog.kz | имущество и залоги Halyk | HTML (листинг + детали) |
| `alatau` | alataucitybank.kz/balance | баланс Alatau City Bank | GraphQL |
| `forte` | sale.forte.kz | имущество ForteBank | GraphQL (Strapi) |
| `bcc` | bcc.kz/personal/collateral-base | залоговая база BCC | HTML, одна страница |
| `freedom` | bankffin.kz/ru/mortgage | имущество Freedom Bank | REST JSON |

Подробности — [docs/01-sources-research.md](docs/01-sources-research.md), [docs/02-banks.md](docs/02-banks.md).

## Локальный запуск (Windows)

Нужны: [uv](https://docs.astral.sh/uv/), официальный Python 3.12 (python.org — Smart App Control блокирует
портативные сборки), Node.js 20+.

```bash
cd backend
uv sync
uv run python -m torgi.cli parse            # все источники (Halyk ~20 минут: ~1000 страниц с паузой 1 с)
uv run python -m torgi.cli parse forte bcc  # выбранные
uv run python -m torgi.cli serve            # API: http://127.0.0.1:8000/docs
uv run python -m pytest                     # тесты на сохранённых ответах источников
```

```bash
cd web
npm install
npm run dev                                 # сайт: http://localhost:3000 (API берёт из TORGI_API_URL)
```

## Как устроена загрузка

- Каждый парсер отдаёт нормализованные `ParsedLot` (категория, регион, город, площадь, цена, даты торгов…).
- `ingest.run_source` делает upsert по `(source, source_id)`, пишет **историю цен** при каждом изменении,
  снимает исчезнувшие лоты (`status=removed`) — но только если источник вернул не меньше 50% прежнего объёма.
- Флаги качества: `suspicious_price`, `suspicious_area` (у источников бывают ошибки ввода: гектары в поле «м²»,
  лишние цифры в цене). Для таких лотов цена за м² не считается.
- Журнал запусков — таблица `parse_runs`, сводка — `GET /api/health`.

## Telegram-канал

1. Создать бота у @BotFather, создать канал и добавить бота администратором с правом публикации.
2. В `backend/.env`:
   ```
   TORGI_TELEGRAM_BOT_TOKEN=...
   TORGI_TELEGRAM_CHANNEL=@имя_канала
   ```
3. Один раз пометить текущую базу как опубликованную, чтобы не выгрузить в канал 1400 постов:
   `uv run python -m torgi.cli post --mark-all`
4. Дальше по расписанию после парсинга: `uv run python -m torgi.cli post --limit 10`
   (`--dry-run` — показать посты без отправки). Лоты с флагами качества в канал не попадают.

## API

- `GET /api/lots` — каталог: `q, category, source, origin, sale_type, region, city, price_min/max, area_min/max,
  rooms, with_auction_date, sort (new|price_asc|price_desc|price_m2_asc|deadline), page, page_size`
- `GET /api/lots/{id}` — карточка с историей цены
- `GET /api/meta` — справочники и счётчики для фильтров
- `GET /api/health` — состояние парсеров

## Деплой

Сервер: VPS с Ubuntu 24.04, от 2 ГБ RAM (сборке Next.js нужно ~1,5 ГБ), root-доступ по SSH-ключу.
DNS: A-записи `torgi.kz`, `www.torgi.kz`, `vsetorgi.kz`, `www.vsetorgi.kz`, `torgi-nedvizhimost.kz`,
`www.torgi-nedvizhimost.kz` → IP сервера.

```bash
deploy/deploy.sh root@IP --setup admin@почта.kz   # первый раз: пакеты, PostgreSQL, SSL, systemd, первичный парсинг
deploy/deploy.sh root@IP                          # обновления
```

На сервере:
- код — `/opt/torgi`, настройки и пароль БД — `/etc/torgi/torgi.env`;
- `torgi-api` (uvicorn :8000) и `torgi-web` (next start :3000) за nginx;
- таймеры: `torgi-parse-hourly` (etp.adilet, каждый час), `torgi-parse-daily` (банки, 04:00 по Алматы),
  `torgi-post` (Telegram, каждые 30 минут с 8 до 22 — работает, когда заданы токен и канал);
- логи: `journalctl -u torgi-parse-daily -n 100`, состояние парсеров: `https://torgi.kz/api/health`.

Домены, которые ещё не указывают на сервер, `setup.sh` пропускает при выпуске сертификата — после настройки DNS
повторите `deploy/deploy.sh root@IP --setup ...`.
