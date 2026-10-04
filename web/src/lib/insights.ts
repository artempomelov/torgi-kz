// Выборки по каталогу на этапе сборки: витрина главной, похожие объекты, сравнение цены с рынком.
import type { Lot } from "./api";
import { PPM_CATEGORIES } from "./filter";

const MAIN_CATEGORIES = new Set(["apartment", "house", "commercial"]);

/** Насколько лот хорош для витрины: фото, жильё/коммерция, не копеечный участок. */
export function showcaseScore(lot: Lot): number {
  return (
    (lot.image ? 4 : 0) +
    (MAIN_CATEGORIES.has(lot.category) ? 3 : lot.category === "land" || lot.category === "industrial" ? 1 : 0) +
    ((lot.price ?? 0) >= 5_000_000 ? 1 : 0) -
    (lot.flags.length ? 5 : 0)
  );
}

/** Лучшие для витрины, при равенстве — исходный порядок (новые / ближайшие торги). */
export function pickShowcase(lots: Lot[], limit: number): Lot[] {
  return lots
    .map((lot, i) => ({ lot, i, s: showcaseScore(lot) }))
    .sort((a, b) => b.s - a.s || a.i - b.i)
    .slice(0, limit)
    .map((x) => x.lot);
}

const place = (lot: Lot) => lot.city ?? lot.region;
// одно место — совпадают и регион, и город (иначе «Алматы» смешивается с пригородами области)
const samePlace = (a: Lot, b: Lot) => a.region === b.region && place(a) === place(b);

/** Похожие: тот же тип и город (или регион), цена в пределах ±30%. */
export function similarLots(lot: Lot, lots: Lot[], limit = 4): Lot[] {
  if (!lot.price) return [];
  const [lo, hi] = [lot.price * 0.7, lot.price * 1.3];
  return pickShowcase(
    lots.filter(
      (x) => x.id !== lot.id && x.category === lot.category && samePlace(x, lot) && x.price && x.price >= lo && x.price <= hi,
    ),
    limit,
  );
}

export type MarketCompare = { median: number; diffPct: number; sample: number; where: string };

/** Цена за м² против медианы по таким же объектам в том же городе (по нашей базе торгов и залогов). */
export function compareToMarket(lot: Lot, lots: Lot[]): MarketCompare | null {
  if (!PPM_CATEGORIES.has(lot.category) || !lot.price_per_m2) return null;
  const where = place(lot);
  if (!where) return null;
  const values = lots
    .filter((x) => x.id !== lot.id && x.category === lot.category && samePlace(x, lot) && x.price_per_m2 && !x.flags.length)
    .map((x) => x.price_per_m2!)
    .sort((a, b) => a - b);
  if (values.length < 5) return null;
  const median = values[Math.floor(values.length / 2)];
  return { median, diffPct: Math.round(((lot.price_per_m2 - median) / median) * 100), sample: values.length, where };
}

/** Объявление висит давно — уместен торг. */
export const STALE_DAYS = 180;
export function isStale(listedAt: string | null | undefined, now = Date.now()): boolean {
  return !!listedAt && now - Date.parse(listedAt) > STALE_DAYS * 86_400_000;
}
