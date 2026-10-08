// SEO-подборки /podborki/{slug}/: «Квартиры с торгов в Алматы», «Залоговое имущество Halyk Bank» и т. п.
// Собираются статически; пустые и почти пустые подборки не публикуются.
import type { Lot } from "./api";
import { CATEGORY_PLURAL, ORIGIN_LABELS, SOURCE_LABELS } from "./format";

export type Collection = {
  slug: string;
  title: string; // H1 и <title>
  lead: string; // кому и что — первая фраза описания
  group: "city" | "category" | "district" | "price" | "origin" | "source";
  match: (lot: Lot) => boolean;
  catalogHref: string; // та же выборка в каталоге с фильтрами
};

// Город: slug, именительный (как в данных), предложный («в Алматы»), регион для фильтра каталога
export const CITIES: { slug: string; name: string; inCity: string; region?: string }[] = [
  { slug: "almaty", name: "Алматы", inCity: "в Алматы", region: "Алматы" },
  { slug: "astana", name: "Астана", inCity: "в Астане", region: "Астана" },
  { slug: "shymkent", name: "Шымкент", inCity: "в Шымкенте", region: "Шымкент" },
  { slug: "karaganda", name: "Караганда", inCity: "в Караганде" },
  { slug: "aktobe", name: "Актобе", inCity: "в Актобе" },
  { slug: "atyrau", name: "Атырау", inCity: "в Атырау" },
  { slug: "aktau", name: "Актау", inCity: "в Актау" },
  { slug: "pavlodar", name: "Павлодар", inCity: "в Павлодаре" },
  { slug: "ust-kamenogorsk", name: "Усть-Каменогорск", inCity: "в Усть-Каменогорске" },
  { slug: "kostanay", name: "Костанай", inCity: "в Костанае" },
  { slug: "taraz", name: "Тараз", inCity: "в Таразе" },
  { slug: "uralsk", name: "Уральск", inCity: "в Уральске" },
  { slug: "semey", name: "Семей", inCity: "в Семее" },
  { slug: "kyzylorda", name: "Кызылорда", inCity: "в Кызылорде" },
  { slug: "petropavlovsk", name: "Петропавловск", inCity: "в Петропавловске" },
  { slug: "turkestan", name: "Туркестан", inCity: "в Туркестане" },
  { slug: "kokshetau", name: "Кокшетау", inCity: "в Кокшетау" },
  { slug: "taldykorgan", name: "Талдыкорган", inCity: "в Талдыкоргане" },
  { slug: "ekibastuz", name: "Экибастуз", inCity: "в Экибастузе" },
  { slug: "temirtau", name: "Темиртау", inCity: "в Темиртау" },
  { slug: "konaev", name: "Конаев", inCity: "в Конаеве" },
];

const CATEGORIES: { id: string; slug: string; what: string }[] = [
  { id: "apartment", slug: "kvartiry", what: "Квартиры" },
  { id: "house", slug: "doma", what: "Дома" },
  { id: "commercial", slug: "kommercheskaya-nedvizhimost", what: "Коммерческая недвижимость" },
  { id: "land", slug: "zemelnye-uchastki", what: "Земельные участки" },
  { id: "industrial", slug: "prombazy", what: "Промбазы и производство" },
  { id: "parking", slug: "parkingi-garazhi", what: "Паркинги и гаражи" },
];

const ORIGIN_SLUGS: Record<string, string> = {
  arrested: "arestovannoe-imushchestvo",
  bank_balance: "imushchestvo-bankov",
  bank_pledge: "zalogovoe-imushchestvo-bankov",
  court: "sudebnaya-realizaciya",
  state: "gosimushchestvo-i-privatizaciya",
  bankrupt: "imushchestvo-bankrotov",
  tax_debtor: "imushchestvo-nalogovyh-dolzhnikov",
  confiscated: "konfiskat",
};

// Районы крупных городов: название — как canonical_district в backend/torgi/normalize.py
const DISTRICTS: { city: string; slug: string; name: string; inDistrict: string }[] = [
  { city: "Алматы", slug: "alatauskij", name: "Алатауский район", inDistrict: "в Алатауском районе Алматы" },
  { city: "Алматы", slug: "almalinskij", name: "Алмалинский район", inDistrict: "в Алмалинском районе Алматы" },
  { city: "Алматы", slug: "auezovskij", name: "Ауэзовский район", inDistrict: "в Ауэзовском районе Алматы" },
  { city: "Алматы", slug: "bostandykskij", name: "Бостандыкский район", inDistrict: "в Бостандыкском районе Алматы" },
  { city: "Алматы", slug: "zhetysuskij", name: "Жетысуский район", inDistrict: "в Жетысуском районе Алматы" },
  { city: "Алматы", slug: "medeuskij", name: "Медеуский район", inDistrict: "в Медеуском районе Алматы" },
  { city: "Алматы", slug: "nauryzbajskij", name: "Наурызбайский район", inDistrict: "в Наурызбайском районе Алматы" },
  { city: "Алматы", slug: "turksibskij", name: "Турксибский район", inDistrict: "в Турксибском районе Алматы" },
  { city: "Астана", slug: "almaty", name: "район Алматы", inDistrict: "в районе Алматы (Астана)" },
  { city: "Астана", slug: "bajkonyr", name: "район Байконыр", inDistrict: "в районе Байконыр (Астана)" },
  { city: "Астана", slug: "esil", name: "район Есиль", inDistrict: "в районе Есиль (Астана)" },
  { city: "Астана", slug: "sarajshyk", name: "район Сарайшык", inDistrict: "в районе Сарайшык (Астана)" },
  { city: "Астана", slug: "saryarka", name: "район Сарыарка", inDistrict: "в районе Сарыарка (Астана)" },
  { city: "Астана", slug: "nura", name: "район Нура", inDistrict: "в районе Нура (Астана)" },
  { city: "Шымкент", slug: "abajskij", name: "Абайский район", inDistrict: "в Абайском районе Шымкента" },
  { city: "Шымкент", slug: "al-farabijskij", name: "Аль-Фарабийский район", inDistrict: "в Аль-Фарабийском районе Шымкента" },
  { city: "Шымкент", slug: "enbekshinskij", name: "Енбекшинский район", inDistrict: "в Енбекшинском районе Шымкента" },
  { city: "Шымкент", slug: "karatauskij", name: "Каратауский район", inDistrict: "в Каратауском районе Шымкента" },
  { city: "Шымкент", slug: "turanskij", name: "Туранский район", inDistrict: "в Туранском районе Шымкента" },
];

// Ценовые потолки, млн ₸: по всей стране и для двух крупнейших городов
const PRICE_BANDS: { category: string; caps: number[] }[] = [
  { category: "apartment", caps: [10, 20, 30, 50] },
  { category: "house", caps: [20, 50] },
  { category: "commercial", caps: [50, 100] },
  { category: "land", caps: [5, 10] },
];
const PRICE_CITIES = ["almaty", "astana", "shymkent"];

// Вид продажи × город: «Залоговое имущество банков в Алматы»
const ORIGIN_CITY: Record<string, string> = {
  arrested: "Арестованное имущество",
  bank_pledge: "Залоговое имущество банков",
  bank_balance: "Имущество банков",
  state: "Госимущество и приватизация",
  bankrupt: "Имущество банкротов",
};

const inCity = (lot: Lot, c: (typeof CITIES)[number]) => (c.region ? lot.region === c.region : lot.city === c.name);
const cityHref = (c: (typeof CITIES)[number]) =>
  c.region ? `region=${encodeURIComponent(c.region)}` : `q=${encodeURIComponent(c.name)}`;

export const MIN_LOTS = 3;

function all(): Collection[] {
  const out: Collection[] = [];
  for (const cat of CATEGORIES) {
    out.push({
      slug: cat.slug,
      title: `${cat.what} с торгов в Казахстане`,
      lead: `${cat.what} с аукционов, залоговое и арестованное имущество, имущество банков и госимущество по всему Казахстану`,
      group: "category",
      match: (lot) => lot.category === cat.id,
      catalogHref: `/lots/?category=${cat.id}`,
    });
    for (const city of CITIES) {
      out.push({
        slug: `${cat.slug}-${city.slug}`,
        title: `${cat.what} с торгов ${city.inCity}`,
        lead: `${cat.what} ${city.inCity}: аукционы, залоги и имущество банков, арестованное имущество и госимущество`,
        group: "city",
        match: (lot) => lot.category === cat.id && inCity(lot, city),
        catalogHref: `/lots/?category=${cat.id}&${cityHref(city)}`,
      });
    }
  }
  for (const city of CITIES) {
    out.push({
      slug: `nedvizhimost-${city.slug}`,
      title: `Недвижимость с торгов ${city.inCity}`,
      lead: `Все объекты на торгах ${city.inCity}: квартиры, дома, коммерция и земля — с аукционов, из залогов банков и госимущества`,
      group: "city",
      match: (lot) => inCity(lot, city),
      catalogHref: `/lots/?${cityHref(city)}`,
    });
  }
  for (const d of DISTRICTS) {
    const key = encodeURIComponent(`${d.city}|${d.name}`);
    const region = encodeURIComponent(d.city);
    const citySlug = CITIES.find((c) => c.name === d.city)!.slug;
    const inDistrict = (lot: Lot) => lot.region === d.city && lot.district === d.name;
    out.push({
      slug: `nedvizhimost-${citySlug}-${d.slug}`,
      title: `Недвижимость с торгов ${d.inDistrict}`,
      lead: `Квартиры, дома, коммерция и земля ${d.inDistrict}: аукционы, залоги банков, арестованное и госимущество`,
      group: "district",
      match: inDistrict,
      catalogHref: `/lots/?region=${region}&district=${key}`,
    });
    for (const cat of CATEGORIES.filter((c) => c.id === "apartment" || c.id === "commercial")) {
      out.push({
        slug: `${cat.slug}-${citySlug}-${d.slug}`,
        title: `${cat.what} с торгов ${d.inDistrict}`,
        lead: `${cat.what} ${d.inDistrict}: аукционы, залоги банков, арестованное и госимущество`,
        group: "district",
        match: (lot) => lot.category === cat.id && inDistrict(lot),
        catalogHref: `/lots/?category=${cat.id}&region=${region}&district=${key}`,
      });
    }
  }
  for (const band of PRICE_BANDS) {
    const cat = CATEGORIES.find((c) => c.id === band.category)!;
    for (const cap of band.caps) {
      const max = cap * 1_000_000;
      const cheap = (lot: Lot) => lot.category === cat.id && !!lot.price && lot.price <= max;
      out.push({
        slug: `${cat.slug}-do-${cap}-mln`,
        title: `${cat.what} до ${cap} млн ₸ с торгов`,
        lead: `${cat.what} дешевле ${cap} млн ₸ по всему Казахстану: аукционы, залоги банков, арестованное и госимущество`,
        group: "price",
        match: cheap,
        catalogHref: `/lots/?category=${cat.id}&price_max=${max}&sort=price_asc`,
      });
      for (const city of CITIES.filter((c) => PRICE_CITIES.includes(c.slug))) {
        out.push({
          slug: `${cat.slug}-${city.slug}-do-${cap}-mln`,
          title: `${cat.what} до ${cap} млн ₸ с торгов ${city.inCity}`,
          lead: `${cat.what} ${city.inCity} дешевле ${cap} млн ₸: аукционы, залоги банков, арестованное и госимущество`,
          group: "price",
          match: (lot) => cheap(lot) && inCity(lot, city),
          catalogHref: `/lots/?category=${cat.id}&${cityHref(city)}&price_max=${max}&sort=price_asc`,
        });
      }
    }
  }
  for (const [origin, slug] of Object.entries(ORIGIN_SLUGS)) {
    const label = ORIGIN_LABELS[origin] ?? origin;
    out.push({
      slug,
      title: `${label}: недвижимость в Казахстане`,
      lead: `${label} — квартиры, дома, коммерция и земля`,
      group: "origin",
      match: (lot) => lot.origin === origin,
      catalogHref: `/lots/?origin=${origin}`,
    });
  }
  for (const [origin, label] of Object.entries(ORIGIN_CITY)) {
    for (const city of CITIES) {
      out.push({
        slug: `${ORIGIN_SLUGS[origin]}-${city.slug}`,
        title: `${label} ${city.inCity}`,
        lead: `${label} ${city.inCity} — квартиры, дома, коммерция и земля`,
        group: "origin",
        match: (lot) => lot.origin === origin && inCity(lot, city),
        catalogHref: `/lots/?origin=${origin}&${cityHref(city)}`,
      });
    }
  }
  for (const [source, label] of Object.entries(SOURCE_LABELS)) {
    out.push({
      slug: `istochnik-${source}`,
      title: `${label}: недвижимость на продажу`,
      lead: `Объекты ${label}, собранные с официального сайта: залоги, имущество на балансе и торги`,
      group: "source",
      match: (lot) => lot.source === source,
      catalogHref: `/lots/?source=${source}`,
    });
  }
  return out;
}

/** Подборки, в которых достаточно лотов, — для страниц, карты сайта и перелинковки. */
const cache = new WeakMap<Lot[], (Collection & { count: number })[]>();

export function getCollections(lots: Lot[]): (Collection & { count: number })[] {
  // при сборке вызывается с одним и тем же массивом на каждой странице — считаем один раз
  let result = cache.get(lots);
  if (!result) {
    result = all()
      .map((c) => ({ ...c, count: lots.filter(c.match).length }))
      .filter((c) => c.count >= MIN_LOTS);
    cache.set(lots, result);
  }
  return result;
}

/** Подборки, в которые входит лот, — самые узкие первыми (район, цена, город): перелинковка с карточки. */
export function collectionsForLot(lot: Lot, lots: Lot[], limit = 6): (Collection & { count: number })[] {
  const order: Collection["group"][] = ["district", "price", "city", "origin", "category", "source"];
  return getCollections(lots)
    .filter((c) => c.match(lot))
    .sort((a, b) => order.indexOf(a.group) - order.indexOf(b.group) || a.count - b.count)
    .slice(0, limit);
}

export const CATEGORY_NAMES = Object.fromEntries(CATEGORIES.map((c) => [c.id, CATEGORY_PLURAL[c.id] ?? c.what]));
