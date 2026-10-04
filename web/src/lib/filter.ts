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
  region: string;
  price_min: string;
  price_max: string;
  area_min: string;
  area_max: string;
  ppm_min: string; // цена за м² — квартиры и коммерция
  ppm_max: string;
  with_auction_date: boolean;
  drop: boolean; // только подешевевшие
  sort: string;
  page: number;
};

export function parseFilters(params: URLSearchParams): Filters {
  return {
    q: params.get("q") ?? "",
    category: params.getAll("category"),
    source: params.getAll("source"),
    origin: params.getAll("origin"),
    region: params.get("region") ?? "",
    price_min: params.get("price_min") ?? "",
    price_max: params.get("price_max") ?? "",
    area_min: params.get("area_min") ?? "",
    area_max: params.get("area_max") ?? "",
    ppm_min: params.get("ppm_min") ?? "",
    ppm_max: params.get("ppm_max") ?? "",
    with_auction_date: params.get("with_auction_date") === "true",
    drop: params.get("drop") === "true",
    sort: params.get("sort") ?? "new",
    page: Math.max(1, Number(params.get("page")) || 1),
  };
}

export function isUpcoming(lot: Lot, now = Date.now()): boolean {
  const end = lot.auction_end ?? lot.auction_start;
  return !!lot.auction_start && !!end && Date.parse(end) >= now;
}

const num = (v: string) => (v.trim() === "" ? null : Number(v));

export function applyFilters(lots: Lot[], f: Filters): Lot[] {
  const q = f.q.trim().toLowerCase();
  const [pMin, pMax, aMin, aMax] = [num(f.price_min), num(f.price_max), num(f.area_min), num(f.area_max)];
  const [mMin, mMax] = [num(f.ppm_min), num(f.ppm_max)];
  const now = Date.now();
  const onlyAuctions = f.with_auction_date || f.sort === "deadline";

  const result = lots.filter((lot) => {
    if (f.category.length && !f.category.includes(lot.category)) return false;
    if (f.source.length && !f.source.includes(lot.source)) return false;
    if (f.origin.length && !f.origin.includes(lot.origin)) return false;
    if (f.region && lot.region !== f.region) return false;
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
    if (q && ![lot.title, lot.address, lot.city].some((s) => s?.toLowerCase().includes(q))) return false;
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

export type ParkingGroup = { kind: "group"; key: string; base: string; lots: Lot[] };
export type CatalogItem = { kind: "lot"; lot: Lot } | ParkingGroup;

// «..., ул. Ақмешіт, зд. 19Б, п.м. 78» → «..., ул. Ақмешіт, зд. 19Б»
const PLACE_RE = /,?\s*(?:п\.\s?м\.?|м\/м|машино[\s-]*мест[\p{L}]*|парковочн\p{L}+\s+мест\p{L}*|паркинг\p{L}*|№)\s*№?\s*[\p{L}\d/-]+.*$/iu;

/** Подряд идущие паркинги одного источника в одном здании (от 3 шт.) сворачиваются в одну карточку. */
export function groupParkings(lots: Lot[]): CatalogItem[] {
  const groups = new Map<string, ParkingGroup>();
  for (const lot of lots) {
    if (lot.category !== "parking" || !lot.address) continue;
    const base = lot.address.replace(PLACE_RE, "").trim();
    if (!base || base === lot.address) continue;
    const key = `${lot.source}|${base}`;
    const g = groups.get(key) ?? { kind: "group" as const, key, base, lots: [] };
    g.lots.push(lot);
    groups.set(key, g);
  }
  const out: CatalogItem[] = [];
  const emitted = new Set<string>();
  for (const lot of lots) {
    const base = lot.category === "parking" && lot.address ? lot.address.replace(PLACE_RE, "").trim() : "";
    const g = base ? groups.get(`${lot.source}|${base}`) : undefined;
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
