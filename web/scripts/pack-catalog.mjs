// Компактный каталог для браузера: таблица вместо массива объектов, справочники вместо повторяющихся строк.
// Формат читает src/lib/catalog-data.ts (unpackCatalog) — меняйте вместе.
export const CATALOG_FILE = "catalog-v2.json";

// поля, которые каталогу в браузере не нужны (статус — всегда активные, ссылка — только на карточке)
const SKIP = new Set(["url", "status"]);
// повторяющиеся строки → номер в справочнике
const DICT = new Set(["source", "origin", "sale_type", "category", "region", "city", "district"]);
const DATES = new Set(["first_seen_at", "listed_at", "applications_deadline", "auction_start", "auction_end"]);

const shortDate = (v) => v.replace(/\.\d+/, "").replace(/:00Z$/, "Z");

export function packCatalog(lots) {
  const fields = [...new Set(lots.flatMap((l) => Object.keys(l)))].filter((f) => !SKIP.has(f));
  const dicts = {};
  const index = {};
  for (const f of fields) if (DICT.has(f)) { dicts[f] = []; index[f] = new Map(); }

  const rows = lots.map((lot) => {
    const row = fields.map((f) => {
      let v = lot[f];
      if (v === null || v === undefined || (Array.isArray(v) && !v.length)) return null;
      if (DICT.has(f)) {
        if (!index[f].has(v)) { index[f].set(v, dicts[f].length); dicts[f].push(v); }
        return index[f].get(v);
      }
      if (DATES.has(f)) return shortDate(v);
      if (f === "price_per_m2" || f === "price" || f === "min_price") return Math.round(v);
      if (f === "lat" || f === "lon") return Math.round(v * 1e4) / 1e4;
      return v;
    });
    while (row.length && row[row.length - 1] === null) row.pop();
    return row;
  });
  return { v: 2, fields, dicts, rows };
}
