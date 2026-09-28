# Источники данных: торги недвижимостью в Казахстане

Исследование от 28.09.2026. [V] — проверено запросом к сайту, [S] — из поисковой выдачи/СМИ, [I] — вывод.

## Итог

Отдельного агрегатора всех торгов РК (аналога TBankrot) не найдено — ниша свободна.

| Приоритет | Источник | Что | Объём недвижимости | Сложность |
|---|---|---|---|---|
| 1 (MVP) | etp.adilet.gov.kz | арестованное имущество (ЧСИ) | ~74 лота в приёме заявок, ежедневно новые | низкая-средняя |
| 2 (MVP) | Банки: Halyk, Alatau City, Forte, BCC, Freedom — см. [02-banks.md](02-banks.md) | залоговое и балансовое имущество | ~1370 объектов недвижимости | низкая (BCC — средняя) |
| 3 | sauda.e-qazyna.kz | приватизация, банкроты, ФПК, КУВА, ликвид. банки | стратегически главный | средняя-высокая (нестабилен) |
| 4 | berekebank, hcsbk (Отбасы), e-sauda.com | залоги банков, частная ЭТП | сотни | низкая-средняя |

## 1. etp.adilet.gov.kz — арестованное имущество [V]

- Минюст, модуль АИС ОИП, движок «ЛотЭксперт» (AngularJS). С 02.02.2026 торги сопровождает РП ЧСИ.
- `GET /trades?page=sales` + заголовок `X-Requested-With: XMLHttpRequest` → HTML-фрагмент с `window.$UM.stateData = {...}` (JSON).
  - `trades.items[]`, `total`, `limit`, `skipped`; пагинация `&limit=300&skip=N`.
  - Фильтры через query не заработали (вероятно, search document) — не проверено.
- Поля: id, registeredNumber, title, region, procurementClassifiers, initialContractPrice, assuranceAmount (5%), bidSubmissionEndDate, tradeStartDate (epoch ms), processStatus, goodsDescription, images, обременения, метод (в т.ч. на понижение).
- Адрес/площадь/кадастр — свободным текстом в описании → нужен разбор (regex/LLM).
- Карточка `/trades/{id}` (`/trades/{id}/info`): ЧСИ (ФИО, телефон), шаг 3%, реквизиты, PDF оценки, фото.
- Без логина, без капчи, robots.txt нет. Участие — по ЭЦП.
- Риск [S]: ноябрь 2025 — кассация отменила сделку (протокол подписан не тем исполнителем); под угрозой >1000 протоколов. Нужен дисклеймер.

## 2. e-qazyna.kz (бывш. gosreestr.kz) — sauda.e-qazyna.kz

- gosreestr.kz → 503, сертификат на e-qazyna.kz [V].
- Продаётся [S]: приватизация (респ./коммунальная), имущество банкротов (ИУЦ — организатор по правилам КГД), ФПК, КУВА, «Банк Астаны» (с 24.06.2026), аренда.
- Лот: `sauda.e-qazyna.kz/ru/list/{18-значный id}`, список `/ru/list?p=N&searchStatus=ApplicationsAccept` [I].
- Во время проверки `/ru/list` таймаутил (25–90 с) или отдавал 500 [V] — структуру снять не удалось.
- Старый публичный API [V]: `e-auction.e-qazyna.kz/p/ru/api/v1/auction-trades?PageNumber=1&Limit=100&Status=AcceptingApplications` — JSON, но данные старой ЭТП (застыли на дек. 2024 – янв. 2025), лимит 999.
- API v2 с токеном по БИН/ИИН: `/api/v2/auction-trades/token`, описание — e-qazyna.kz/ru/Developer. Отдаёт ли данные sauda — не проверено → **написать в ИУЦ**.

## 3. КГД (kgd.gov.kz) [V]

- Лотов нет. Только процессуальные объявления о банкротстве (.doc/.xlsx по регионам). Годится как ранний сигнал «скоро торги».
- robots.txt: Crawl-delay 10 (местами 180). Сложность высокая.

## 4. Банки

> Подробный разбор Halyk, Alatau City, Forte, BCC, Freedom — в [02-banks.md](02-banks.md). Таблица ниже — первичный обзор.

| Источник | Объём | Формат | Защита |
|---|---|---|---|
| halykzalog.kz [V] | 1073 | серверный HTML, `/catalog/category_id-is-N/{id}`, `?page=N` | reCAPTCHA v3 (листинг не блокирует) |
| alataucitybank.kz/balance [V] | 135 | Next.js `__NEXT_DATA__`, `/balance-property/graphql` | нет |
| berekebank.kz/ru/about/collaterals [V] | ~9 стр. | HTML, `/about/collaterals/{id}` | — |
| hcsbk.kz/ru/collateral (Отбасы) [V] | ? | HTML по регионам | reCAPTCHA v2 |
| bcc.kz/personal/collateral-base [V] | 100+ | одна большая страница | — |
| sale.forte.kz [S] | ? | не проверено | — |

Kaspi, ПКБ — публичной витрины не найдено. ФПК продаёт через e-qazyna (2191 объект за всё время на 01.01.2026) [S].

## 5. Прочее и конкуренты

- e-sauda.com — частная ЭТП (управляющие активами, юрлица), ~744 объявления, `/ru/auction/{n}` [V].
- Telegram: @torgi_kz — мёртв (71 подп., 2023); @e_qazyna / @e_qazyna_news — только новости [V].
- auctionpro.kz — онлайн-школа, не агрегатор.
- **Проверить вручную:** TGStat/Telegram на наличие конкурентов.

## Пробелы рынка (наши фичи)

Единая лента всех источников · нормализованные адрес/площадь/цена за м² · карта и геопоиск · сравнение с рынком (Krisha) · подписки и алерты · история снижения цены на повторных торгах · юридический чек-лист рисков лота.

## Открытые вопросы

- Структура sauda.e-qazyna.kz (повторить проверку).
- Запрос в ИУЦ на API v2 / API новой площадки.
- Фильтры etp.adilet (search document).
- Объёмы Отбасы и Forte.
