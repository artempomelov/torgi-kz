// Раздел «Автомобили с торгов»: данные (web/data/cars.json — выгрузка backend), фильтры и подписи.

export type Car = {
  id: number;
  source: string;
  url: string;
  title: string;
  vehicle_type: "car" | "truck" | "special" | "moto" | "other";
  brand: string | null;
  model: string | null;
  year: number | null;
  mileage_km: number | null;
  engine: string | null;
  transmission: string | null;
  body: string | null;
  color: string | null;
  price: number | null;
  min_price?: number | null; // аукцион на понижение: до какой цены может опуститься
  city: string | null;
  region: string | null;
  origin: string;
  sale_type: string | null;
  auction_date: string | null;
  applications_deadline?: string | null;
  deposit?: number | null;
  listed_at?: string | null;
  price_drop_pct?: number | null;
  drive?: string | null;
  note?: string | null; // «аварийный», «имеются обременения», «после страхового случая»
  images: string[];
  description: string | null;
};

export const VEHICLE_TYPES: Record<string, string> = {
  car: "Легковые",
  truck: "Грузовые и коммерческие",
  special: "Спецтехника",
  moto: "Мототехника",
  other: "Другое",
};

export const CAR_SORTS: [string, string][] = [
  ["new", "Сначала новые"],
  ["price_asc", "Сначала дешевле"],
  ["price_desc", "Сначала дороже"],
  ["year_desc", "Год: новее"],
  ["year_asc", "Год: старше"],
];

export type CarFilters = {
  brand: string;
  model: string;
  type: string[];
  city: string;
  year_min: string;
  year_max: string;
  price_min: string;
  price_max: string;
  transmission: string;
  origin: string[];
  sort: string;
  page: number;
};

export const CAR_PAGE_SIZE = 24;

export function parseCarFilters(p: URLSearchParams): CarFilters {
  return {
    brand: p.get("brand") ?? "",
    model: p.get("model") ?? "",
    type: p.getAll("type"),
    city: p.get("city") ?? "",
    year_min: p.get("year_min") ?? "",
    year_max: p.get("year_max") ?? "",
    price_min: p.get("price_min") ?? "",
    price_max: p.get("price_max") ?? "",
    transmission: p.get("transmission") ?? "",
    origin: p.getAll("origin"),
    sort: p.get("sort") ?? "new",
    page: Math.max(1, Number(p.get("page")) || 1),
  };
}

const num = (s: string) => (s.trim() === "" ? null : Number(s));

export function applyCarFilters(cars: Car[], f: CarFilters): Car[] {
  const yMin = num(f.year_min), yMax = num(f.year_max), pMin = num(f.price_min), pMax = num(f.price_max);
  const out = cars.filter((c) =>
    (!f.brand || c.brand === f.brand) &&
    (!f.model || c.model === f.model) &&
    (!f.type.length || f.type.includes(c.vehicle_type)) &&
    (!f.city || c.city === f.city || c.region === f.city) &&
    (yMin === null || (c.year ?? 0) >= yMin) &&
    (yMax === null || (c.year ?? 9999) <= yMax) &&
    (pMin === null || (c.price ?? 0) >= pMin) &&
    (pMax === null || (c.price ?? Infinity) <= pMax) &&
    (!f.transmission || (c.transmission ?? "").toLowerCase().includes(f.transmission.toLowerCase())) &&
    (!f.origin.length || f.origin.includes(c.origin)),
  );
  const by = {
    price_asc: (a: Car, b: Car) => (a.price ?? Infinity) - (b.price ?? Infinity),
    price_desc: (a: Car, b: Car) => (b.price ?? 0) - (a.price ?? 0),
    year_desc: (a: Car, b: Car) => (b.year ?? 0) - (a.year ?? 0),
    year_asc: (a: Car, b: Car) => (a.year ?? 9999) - (b.year ?? 9999),
  }[f.sort];
  // «новые» — порядок выгрузки; машины с фото — первыми
  return by ? out.sort(by) : out.sort((a, b) => Number(!a.images.length) - Number(!b.images.length));
}

/** Значения для выпадающих списков с числом машин: марки, модели выбранной марки, города. */
export function carOptions(cars: Car[], brand: string) {
  const count = (values: (string | null)[]) => {
    const m = new Map<string, number>();
    for (const v of values) if (v) m.set(v, (m.get(v) ?? 0) + 1);
    return [...m.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0], "ru"));
  };
  return {
    brands: count(cars.map((c) => c.brand)),
    models: count(cars.filter((c) => c.brand === brand).map((c) => c.model)),
    cities: count(cars.map((c) => c.city ?? c.region)),
    years: cars.map((c) => c.year).filter((y): y is number => !!y),
  };
}

export function carName(c: Car): string {
  const name = [c.brand, c.model].filter(Boolean).join(" ") || c.title;
  return c.year ? `${name}, ${c.year}` : name;
}

export function carSpecs(c: Car): string {
  return [
    c.mileage_km != null ? `${c.mileage_km.toLocaleString("ru-RU")} км` : null,
    c.engine,
    c.transmission,
    c.body,
  ].filter(Boolean).join(" · ");
}
