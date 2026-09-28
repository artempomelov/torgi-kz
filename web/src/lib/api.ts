// Клиент API бэкенда (FastAPI). На сервере Next.js ходит к нему напрямую.
const API_URL = process.env.TORGI_API_URL ?? "http://127.0.0.1:8000";

export type Lot = {
  id: number;
  source: string;
  url: string;
  origin: string;
  sale_type: string | null;
  category: string;
  title: string;
  region: string | null;
  city: string | null;
  address: string | null;
  lat: number | null;
  lon: number | null;
  area_m2: number | null;
  land_area_ha: number | null;
  rooms: number | null;
  floor: number | null;
  floors_total: number | null;
  price: number | null;
  price_per_m2: number | null;
  auction_start: string | null;
  auction_end: string | null;
  applications_deadline: string | null;
  image: string | null;
  flags: string[];
  status: string;
  first_seen_at: string;
  price_drop_pct: number | null;
};

export type LotFull = Lot & {
  description: string | null;
  year_built: number | null;
  cadastral: string | null;
  deposit: number | null;
  images: string[];
  contacts: Record<string, string>;
  extra: Record<string, unknown>;
  published_at: string | null;
  last_seen_at: string;
  price_history: { price: number | null; seen_at: string }[];
};

export type LotPage = { total: number; page: number; page_size: number; items: Lot[] };

export type Meta = {
  total: number;
  categories: { id: string; title: string; count: number }[];
  origins: { id: string; title: string }[];
  sale_types: { id: string; title: string }[];
  sources: { id: string; title: string; url: string; count: number }[];
  regions: { id: string; count: number }[];
};

export type SearchParams = Record<string, string | string[] | undefined>;

async function get<T>(path: string, revalidate = 300): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, { next: { revalidate } });
  if (!res.ok) throw new Error(`API ${path}: ${res.status}`);
  return res.json() as Promise<T>;
}

/** Параметры каталога, которые пробрасываем в API как есть. */
export const LOT_FILTERS = [
  "q", "category", "source", "origin", "sale_type", "region", "city",
  "price_min", "price_max", "area_min", "area_max", "rooms", "with_auction_date", "sort", "page",
] as const;

export function toQuery(params: SearchParams, overrides: Record<string, string | null> = {}): string {
  const qs = new URLSearchParams();
  for (const key of LOT_FILTERS) {
    const value = params[key];
    for (const v of Array.isArray(value) ? value : value ? [value] : []) {
      if (v !== "") qs.append(key, v);
    }
  }
  for (const [key, value] of Object.entries(overrides)) {
    qs.delete(key);
    if (value !== null) qs.set(key, value);
  }
  return qs.toString();
}

export function getLots(params: SearchParams, pageSize = 24): Promise<LotPage> {
  return get<LotPage>(`/api/lots?${toQuery(params, { page_size: String(pageSize) })}`, 120);
}

export async function getLot(id: string): Promise<LotFull | null> {
  const res = await fetch(`${API_URL}/api/lots/${encodeURIComponent(id)}`, { next: { revalidate: 300 } });
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`API lot ${id}: ${res.status}`);
  return res.json();
}

export function getMeta(): Promise<Meta> {
  return get<Meta>("/api/meta", 300);
}
