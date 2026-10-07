// Фильтрация и сортировка каталога в браузере (повторяет логику /api/lots бэкенда).
import type { Lot } from "./api";

export const PAGE_SIZE = 24;

export const PPM_CATEGORIES = new Set(["apartment", "commercial"]);

export const SORTS = [
  ["new", "Сначала новые"],
  ["price_asc", "Сначала дешёвые"],
  ["price_desc", "Сначала дорогие"],
  ["price_m2_asc", "Дешевле за м²"],
  ["deadline", "По дате торгов"],
  ["drop", "Сильнее подешевели"],
] as const;

export type Filters = {
  q: string;
  category: string[];
  source: string[];
  origin: string[];
  region: string[]; // несколько: «Алматы» и «Астана»
  city: string[]; // города внутри областей: «Караганда»
  district: string[]; // «Алматы|Бостандыкский район» — район привязан к городу
  price_min: string;
  price_max: string;
  area_min: string;
  area_max: string;
  ppm_min: string; // цена за м² — квартиры и коммерция
  ppm_max: string;
  with_auction_date: boolean;
  drop: boolean; // только подешевевшие
  group: string; // паркинги одного здания (group_key)
  sort: string;
  page: number;
};

export function parseFilters(params: URLSearchParams): Filters {
  return {
    q: params.get("q") ?? "",
    category: params.getAll("category"),
    source: params.getAll("source"),
    origin: params.getAll("origin"),
    region: params.getAll("region").filter(Boolean),
    city: params.getAll("city").filter(Boolean),
    district: params.getAll("district").filter(Boolean),
    price_min: params.get("price_min") ?? "",
    price_max: params.get("price_max") ?? "",
    area_min: params.get("area_min") ?? "",
    area_max: params.get("area_max") ?? "",
    ppm_min: params.get("ppm_min") ?? "",
    ppm_max: params.get("ppm_max") ?? "",
    with_auction_date: params.get("with_auction_date") === "true",
    drop: params.get("drop") === "true",
    group: params.get("group") ?? "",
    sort: params.get("sort") ?? "new",
    page: Math.max(1, Number(params.get("page")) || 1),
  };
}

/** Район вместе с городом: одинаковые названия районов есть в разных городах. */
export function districtKey(lot: Lot): string | null {
  const place = lot.city ?? lot.region;
  return lot.district && place ? `${place}|${lot.district}` : null;
}

export function isUpcoming(lot: Lot, now = Date.now()): boolean {
  const end = lot.auction_end ?? lot.auction_start;
  return !!lot.auction_start && !!end && Date.parse(end) >= now;
}

const num = (v: string) => (v.trim() === "" ? null : Number(v));

// Поиск: части через запятую («Ауэзовский район, Алматы») — все должны совпасть.
// Если часть — название города («Алматы», «г. Астана»), сравниваем город лота, а не текст адреса:
// иначе «Алматы» находит «район Алматы» в Астане, а «Ауэзовский район» — во всех городах сразу.
const CITY_ALIASES: Record<string, string> = { "нур-султан": "астана", "алма-ата": "алматы" };

function searchTerms(q: string, cities: Set<string>): { cities: string[]; texts: string[] } {
  const out = { cities: [] as string[], texts: [] as string[] };
  for (const raw of q.toLowerCase().split(",")) {
    const term = raw.replace(/^\s*(?:г\.|город)\s*/, "").trim();
    if (!term) continue;
    const city = CITY_ALIASES[term] ?? term;
    if (cities.has(city)) out.cities.push(city);
    else out.texts.push(term);
  }
  return out;
}

export function applyFilters(lots: Lot[], f: Filters): Lot[] {
  const cities = new Set(lots.flatMap((l) => [l.city?.toLowerCase(), l.region?.toLowerCase()]).filter((s): s is string => !!s));
  const terms = searchTerms(f.q, cities);
  const [pMin, pMax, aMin, aMax] = [num(f.price_min), num(f.price_max), num(f.area_min), num(f.area_max)];
  const [mMin, mMax] = [num(f.ppm_min), num(f.ppm_max)];
  const now = Date.now();
  const onlyAuctions = f.with_auction_date || f.sort === "deadline";

  const result = lots.filter((lot) => {
    if (f.category.length && !f.category.includes(lot.category)) return false;
    if (f.source.length && !f.source.includes(lot.source)) return false;
    if (f.origin.length && !f.origin.includes(lot.origin)) return false;
    if ((f.region.length || f.city.length) && !f.region.includes(lot.region ?? "") && !f.city.includes(lot.city ?? "")) {
      return false;
    }
    if (f.district.length && !f.district.includes(districtKey(lot) ?? "")) return false;
    if (pMin !== null && (lot.price ?? -1) < pMin) return false;
    if (pMax !== null && (lot.price == null || lot.price > pMax)) return false;
    if (aMin !== null && (lot.area_m2 ?? -1) < aMin) return false;
    if (aMax !== null && (lot.area_m2 == null || lot.area_m2 > aMax)) return false;
    if (mMin !== null || mMax !== null) {
      // цена за м² считается только для квартир и коммерции (как на карточках)
      const ppm = PPM_CATEGORIES.has(lot.category) ? lot.price_per_m2 : null;
      if (ppm == null || (mMin !== null && ppm < mMin) || (mMax !== null && ppm > mMax)) return false;
    }
    if (onlyAuctions && !isUpcoming(lot, now)) return false;
    if ((f.drop || f.sort === "drop") && !lot.price_drop_pct) return false;
    if (f.group && lot.group_key !== f.group) return false;
    if (terms.cities.length && !terms.cities.some((c) => lot.city?.toLowerCase() === c || lot.region?.toLowerCase() === c)) {
      return false;
    }
    if (terms.texts.length) {
      const haystack = [lot.title, lot.address, lot.city, lot.district, lot.headline].filter(Boolean).join(" | ").toLowerCase();
      if (!terms.texts.every((t) => haystack.includes(t))) return false;
    }
    return true;
  });

  const nullsLast = (a: number | null, b: number | null, dir: 1 | -1) =>
    a == null ? (b == null ? 0 : 1) : b == null ? -1 : (a - b) * dir;
  const sorters: Record<string, (a: Lot, b: Lot) => number> = {
    new: (a, b) => Date.parse(b.first_seen_at) - Date.parse(a.first_seen_at) || b.id - a.id,
    price_asc: (a, b) => nullsLast(a.price, b.price, 1),
    price_desc: (a, b) => nullsLast(a.price, b.price, -1),
    price_m2_asc: (a, b) => nullsLast(a.price_per_m2, b.price_per_m2, 1),
    deadline: (a, b) => Date.parse(a.auction_start!) - Date.parse(b.auction_start!),
    drop: (a, b) => (b.price_drop_pct ?? 0) - (a.price_drop_pct ?? 0),
  };
  return result.sort(sorters[f.sort] ?? sorters.new);
}

// --- одинаковые паркинги одной карточкой -------------------------------------------------

export type ParkingGroup = { kind: "group"; key: string; base: string; lots: Lot[]; groupKey: string | null };
export type CatalogItem = { kind: "lot"; lot: Lot } | ParkingGroup;

// «..., ул. Ақмешіт, зд. 19Б, п.м. 78» → «..., ул. Ақмешіт, зд. 19Б»
const PLACE_RE = /,?\s*(?:п\.\s?м\.?|м\/м|машино[\s-]*мест[\p{L}]*|парковочн\p{L}+\s+мест\p{L}*|паркинг\p{L}*|№)\s*№?\s*[\p{L}\d/-]+.*$/iu;

// Ключ здания: из выгрузки (group_key — работает и когда адрес закрыт) или из адреса
function parkingKey(lot: Lot): { key: string; base: string } | null {
  if (lot.category !== "parking") return null;
  const label = [lot.city, lot.district].filter(Boolean).join(", ") || lot.headline;
  if (lot.group_key) {
    const base = lot.address ? lot.address.replace(PLACE_RE, "").trim() : label;
    return { key: lot.group_key, base };
  }
  if (!lot.address) return null;
  const base = lot.address.replace(PLACE_RE, "").trim();
  return base && base !== lot.address ? { key: `${lot.source}|${base}`, base } : null;
}

/** Паркинги одного источника в одном здании (от 3 шт.) сворачиваются в одну карточку. */
export function groupParkings(lots: Lot[]): CatalogItem[] {
  const groups = new Map<string, ParkingGroup>();
  for (const lot of lots) {
    const k = parkingKey(lot);
    if (!k) continue;
    const g = groups.get(k.key) ?? { kind: "group" as const, key: k.key, base: k.base, lots: [], groupKey: lot.group_key ?? null };
    g.lots.push(lot);
    groups.set(k.key, g);
  }
  const out: CatalogItem[] = [];
  const emitted = new Set<string>();
  for (const lot of lots) {
    const k = parkingKey(lot);
    const g = k ? groups.get(k.key) : undefined;
    if (g && g.lots.length >= 3) {
      if (!emitted.has(g.key)) {
        emitted.add(g.key);
        out.push(g);
      }
    } else {
      out.push({ kind: "lot", lot });
    }
  }
  return out;
}
