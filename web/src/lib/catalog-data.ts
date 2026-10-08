// Каталог в браузере: компактный catalog-v2.json грузится один раз на вкладку и переиспользуется.
// Формат пишет scripts/pack-catalog.mjs — меняйте вместе.
import type { Lot } from "./api";

type Packed = {
  v: 2;
  fields: string[];
  dicts: Record<string, string[]>;
  rows: unknown[][];
};

export function unpackCatalog(data: Packed): Lot[] {
  const { fields, dicts, rows } = data;
  return rows.map((row) => {
    const lot: Record<string, unknown> = { status: "active", flags: [] };
    fields.forEach((f, i) => {
      const v = row[i] ?? null;
      if (v === null) {
        if (!(f in lot)) lot[f] = null;
        return;
      }
      lot[f] = dicts[f] ? dicts[f][v as number] : v;
    });
    return lot as Lot;
  });
}

let lotsPromise: Promise<Lot[]> | null = null;

export function loadLots(): Promise<Lot[]> {
  lotsPromise ??= fetch("/data/catalog-v2.json").then(async (r) => {
    if (!r.ok) throw new Error(`catalog: ${r.status}`);
    return unpackCatalog(await r.json());
  });
  lotsPromise.catch(() => (lotsPromise = null)); // при сбое — повторить при следующем вызове
  return lotsPromise;
}
