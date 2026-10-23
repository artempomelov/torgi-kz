// Выборки по каталогу на этапе сборки: витрина главной, похожие объекты.
import type { Lot } from "./api";
import { isLowInterest } from "./filter";

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

/** «Новое»: последние лоты по дате появления на torgi.kz — с фото, без паркингов, копеечной земли и лотов без цены.
 *  Из серии одного продавца (тот же тип и город) — не больше двух, чтобы партия участков не заняла весь раздел. */
export function latestLots(lots: Lot[], limit = 10): Lot[] {
  const series = new Map<string, number>();
  const out: Lot[] = [];
  const byDate = [...lots].sort((a, b) => Date.parse(b.first_seen_at) - Date.parse(a.first_seen_at) || b.id - a.id);
  for (const lot of byDate) {
    if (out.length === limit) break;
    if (!lot.image || isLowInterest(lot)) continue;
    const key = [lot.source, lot.category, lot.city ?? lot.region].join("|");
    const n = series.get(key) ?? 0;
    if (n >= 2) continue;
    series.set(key, n + 1);
    out.push(lot);
  }
  return out;
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

/** Объявление висит давно — уместен торг. */
export const STALE_DAYS = 180;
export function isStale(listedAt: string | null | undefined, now = Date.now()): boolean {
  return !!listedAt && now - Date.parse(listedAt) > STALE_DAYS * 86_400_000;
}
