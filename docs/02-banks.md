# Банки: залоговое и балансовое имущество

Проверено 28.09.2026: ~120 запросов, ~1 запрос/с, блокировок не было. [V] — проверено запросом, [I] — вывод.
Headless-браузер не нужен ни для одного банка.

## Сводка

| Банк | Источник данных | Запросов на полный обход | Недвижимость | Торги / даты | Сложность |
|---|---|---|---|---|---|
| Halyk | SSR HTML halykzalog.kz | ~45 листинг + ~1000 деталей | **997** | свои онлайн-аукционы с датами и ставками | низкая |
| BCC | HTML, 1 страница | 1 | ~148 | балансовые + судебная реализация, без дат | средняя |
| Alatau City | GraphQL `/balance-property/graphql` | 1 (+N деталей) | 129 | метка «Аукцион» (108), без дат | низкая |
| Forte | Strapi GraphQL `forte-strapi.forte.kz/graphql` | 1 | 87 | «торги на ЭТП» в тексте (61), без дат | низкая |
| Freedom | REST `/api/mortgage/get-filtered-data` | 1 | 7 | нет | низкая |

**Порядок реализации:** Halyk → Alatau → Forte → BCC → Freedom.

Общие правила парсинга: браузерный User-Agent, ~1 запрос/с, опрос раз в сутки (Halyk-аукционы чаще). Историю цен не отдаёт ни один банк — считаем снижения сами по ежедневным снапшотам.

---

## 1. Halyk — halykzalog.kz

- Листинг: `/catalog/category_id-is-{c}[/implementation_id-is-{i}]?page=N`, 24 карточки на страницу (`div.shop-item-container`), счётчик «Найдено N объектов». Вне диапазона — 0 карточек.
- Деталь: `/catalog/category_id-is-{c}/{id}`, напр. `/catalog/category_id-is-1/13635`.
- Категории: 1 Квартиры 290 · 2 Дома 101 · 3 Паркинги 168 · 4 Бизнес 234 · 5 Промбазы 14 · 6 Участки 165 · 8 Прочее 25 · ~~7 Транспорт 76~~.
- Реализация: 1 = имущество банка (761), 3 = залоговое (312), ~~7 = аренда~~.
- Разделы: `/catalog/section-is-auctions` (сейчас 1 объект), `/catalog/section-is-hots` (17).
- Аукцион: «Проводится аукцион с 25.09.2026 по 01.10.2026 18:00», число ставок; участие — после авторизации. Правила: `/uploads/docs/auction_rules.pdf`.
- Стек: Laravel, серверный HTML, JSON API нет. Фильтр — `POST /catalog/filter/encode` → ЧПУ. sitemap.xml заявлен, но 404.
- Поля детали: реализация, владелец, id, комнаты, тип строения, этаж/этажность, год, площади (общая/жилая/кухня), состояние, санузел, газ, «выселен», дата публикации, описание, фото (до ~38), координаты (скрытые input lat/lon). Кадастра и истории цены нет.
- Анти-бот: reCAPTCHA v3 только на формах; Cloudflare нет. robots.txt закрывает `/uploads/*` → храним ссылки на фото, не скачиваем.
- Инкремент: по id и дате публикации.

## 2. Alatau City Bank (бывш. Jusan) — alataucitybank.kz/balance

- Next.js, листинг `/balance`, деталь `/balance/{id}`.
- Открытый GraphQL `POST https://alataucitybank.kz/balance-property/graphql` (без авторизации/CSRF), `pageSize: 500` → все объекты одним запросом:

```graphql
query { allProperties(sellingMethodIds: [], regionId: null, categoryId: null, minPrice: null, maxPrice: null,
  pageDto: {pageNo: 0, pageSize: 500, sortBy: "new"}) {
  items { id title{ru kz en} description{ru} price publishedAt mainPageImage
    propertyImagesList{innerPageBigImage fullScreenImage}
    propertyInfo{title{ru} info{ru} inShowMainType}
    propertySellingMethods{id title{ru}} propertyCategory{id title{ru}} propertyRegion{id title{ru}} }
  itemCount totalPage } }
```

```graphql
query { propertyById(id: 557) { views price description{ru} contactDetails{type title{ru} link}
  propertyMapCoordinate{latitude longitude zoom} propertyDocuments{title{ru} link{ru}} } }
```

- Объём: Квартиры 22 · Дома 14 · Коммерция 79 · Земля 11 · Прочее 3 · ~~Движимое 6~~. Способ: Аукцион 108, Адресная покупка 26 (справочник: 1 Адресная, 2 Конкурс, 3 Аукцион).
- Поля `propertyInfo` (ключ-значение): город, район, улица, дом, общая площадь, этаж, этажность, год, **кадастровый номер** (96), площадь участка, назначение, материал стен, коммуникации, состояние. Ключи нормализовать (двоеточия, регистр). Комнаты — только в title.
- Фото: `/file-server/filename?dir=balance-property/property/{id}&filename=...`.
- Анти-бот нет. robots.txt: Disallow только `/search`.

## 3. ForteBank — sale.forte.kz

- Next.js App Router, список через Apollo на клиенте. Деталь (SSR): `/ru/sale/{slug}`.
- Открытый Strapi v5 GraphQL `POST https://forte-strapi.forte.kz/graphql` (CORS `*`), `pagination: {limit: -1}` → все объекты (~229 КБ):

```graphql
query($l: I18NLocaleCode) {
  sales_connection(locale: $l, pagination: {limit: -1}) {
    pageInfo { total pageCount }
    nodes { documentId slug address price area measurement year city{name} category{title}
      description additionalDescription auctionText isSpecialOffer latitude longitude
      images{url} manager{name phoneNumber} } } }
```

- Объём 87: жилая 28 · коммерческая 23 · земля 19 · нежилые 10 · паркинги 4 · промбазы 2. Алматы 37, Астана 12, Уральск 9.
- 61 из 87 — «аукцион на повышение на ЭТП, цена стартовая», какая ЭТП — не указано; «дата торгов будет сообщена дополнительно». Рассрочка до 36 мес. у 83.
- Этаж/комнаты/кадастр — regex из description.
- Анти-бот нет. Фото в S3.

## 4. Bank CenterCredit — bcc.kz/personal/collateral-base/

- Одна страница ~1,08 МБ (October CMS + Alpine.js), всё в HTML, деталей по URL нет (модалки).
- 158 карточек (`section.constructor-block-description-card`): коммерческая 59 · жилая 88 · «реализация с торгов» 1 · ~~движимое 10~~ → ~148 недвижимости.
- Два шаблона:
  - **балансовые** (~40 с блоком «Характеристики»): этаж, комнаты, площадь, цена, город/адрес, контакт сотрудника;
  - **судебная реализация**: свободный текст — адрес, площадь, иногда кадастр, цена числом и прописью.
- Фото ~55 из 158. Нет ID, координат, дат → дедупликация по хэшу «адрес + площадь».
- F5 BIG-IP WAF (cookie TS…) — не долбить, раз в сутки.

## 5. Freedom Bank — bankffin.kz/ru/mortgage

- React-виджет, открытый REST (GET без CSRF):
  - `/api/mortgage/get-filters` — справочники (mortgage_type 2 = Недвижимость).
  - `/api/mortgage/get-filtered-data?city_id=all&realisation_type_id=all&mortgage_type_id=2&sort=fresh` — все объекты.
  - `/api/mortgage/get-item?id=616` — деталь.
  - ⚠️ `POST /api/mortgage/send-request` — форма заявки, не трогать.
- Объём: 66 всего, недвижимость **7** (квартиры): адресная покупка 5, внесудебная 1, судебная 1.
- Поля: адрес, площади, комнаты, этаж/этажность, год, цена, фото, контакты, условия.
- **Не хранить** номера кредитного договора и договора залога (есть в ответе).
- Валидация цены: у id 616 price = 12 418 543 890 (ошибка ввода).
- Cloudflare Turnstile только на формах.

## Открытые вопросы

- На какой ЭТП проводят торги Forte и Alatau (e-sauda? sauda.e-qazyna?) — узнать у менеджеров.
- Terms of use банковских сайтов не открывались.
