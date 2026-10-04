// Каталог в браузере: lots.json грузится один раз на вкладку и переиспользуется.
import type { Lot } from "./api";

let lotsPromise: Promise<Lot[]> | null = null;

export function loadLots(): Promise<Lot[]> {
  lotsPromise ??= fetch("/data/lots.json").then((r) => {
    if (!r.ok) throw new Error(`lots.json: ${r.status}`);
    return r.json();
  });
  lotsPromise.catch(() => (lotsPromise = null)); // при сбое — повторить при следующем вызове
  return lotsPromise;
}
