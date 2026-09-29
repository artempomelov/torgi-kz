// Типы данных лотов (совпадают с JSON, который выгружает backend: `torgi.cli export`).

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

export type Meta = {
  total: number;
  updated_at: string;
  categories: { id: string; title: string; count: number }[];
  origins: { id: string; title: string }[];
  sale_types: { id: string; title: string }[];
  sources: { id: string; title: string; url: string; count: number }[];
  regions: { id: string; count: number }[];
};
