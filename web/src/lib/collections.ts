// SEO-подборки /podborki/{slug}/: «Квартиры с торгов в Алматы», «Залоговое имущество Halyk Bank» и т. п.
// Собираются статически; пустые и почти пустые подборки не публикуются.
import type { Lot } from "./api";
import { CATEGORY_PLURAL, ORIGIN_LABELS, SOURCE_LABELS } from "./format";

export type Collection = {
  slug: string;
  title: string; // H1 и <title>
  lead: string; // кому и что — первая фраза описания
  group: "city" | "category" | "origin" | "source";
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
export function getCollections(lots: Lot[]): (Collection & { count: number })[] {
  return all()
    .map((c) => ({ ...c, count: lots.filter(c.match).length }))
    .filter((c) => c.count >= MIN_LOTS);
}

export const CATEGORY_NAMES = Object.fromEntries(CATEGORIES.map((c) => [c.id, CATEGORY_PLURAL[c.id] ?? c.what]));
