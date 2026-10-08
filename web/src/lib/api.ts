// Типы данных лотов (совпадают с JSON, который выгружает backend: `torgi.cli export`).
// Поля с `?` — «закрытые» (GATED_FIELDS в backend/torgi/export.py): в платном режиме их нет в статике.

export type Lot = {
  id: number;
  headline: string; // публичный заголовок без точного адреса
  source: string;
  url?: string;
  origin: string;
  sale_type: string | null;
  category: string;
  title?: string;
  region: string | null;
  city: string | null;
  address?: string | null;
  lat?: number | null;
  lon?: number | null;
  area_m2: number | null;
  land_area_ha: number | null;
  rooms: number | null;
  floor: number | null;
  floors_total: number | null;
  price: number | null;
  price_per_m2: number | null;
  min_price?: number | null; // аукцион на понижение: ниже этой цены не опустится
  auction_start: string | null;
  auction_end: string | null;
  applications_deadline: string | null;
  image: string | null;
  flags: string[];
  status: string;
  first_seen_at: string;
  price_drop_pct: number | null;
  listed_at?: string | null; // когда объявление появилось у источника
  district?: string | null; // район из адреса — публичный ориентир
  group_key?: string | null; // здание для одинаковых паркингов
};

export type LotDetailsData = {
  title?: string;
  address?: string | null;
  lat?: number | null;
  lon?: number | null;
  cadastral?: string | null;
  url?: string;
  contacts?: Record<string, string>;
  description?: string | null;
  extra?: Record<string, unknown>;
  documents?: { title: string; url: string; size?: number | null }[] | null;
};

export type LotFull = Lot &
  LotDetailsData & {
    year_built: number | null;
    deposit: number | null;
    images: string[];
    price_history?: { price: number | null; seen_at: string }[]; // публично: график на карточке
    published_at: string | null;
    last_seen_at: string;
    duplicate_of?: number | null; // тот же объект у другого источника — основной лот
  };

export type Meta = {
  total: number;
  updated_at: string;
  gated?: boolean;
  categories: { id: string; title: string; count: number }[];
  origins: { id: string; title: string }[];
  sale_types: { id: string; title: string }[];
  sources: { id: string; title: string; url: string; count: number }[];
  regions: { id: string; count: number }[];
};
