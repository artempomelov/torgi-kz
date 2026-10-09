// Данные для сборки статического сайта: читаются из web/data во время `next build` (только сервер).
import { readFileSync } from "node:fs";
import path from "node:path";

import type { Lot, LotFull, Meta, TopData, TopItem } from "./api";
import { isUpcoming } from "./filter";

const DATA_DIR = process.env.TORGI_DATA_DIR ?? path.join(process.cwd(), "data");

const cache = new Map<string, unknown>();
function read<T>(name: string): T {
  if (!cache.has(name)) {
    cache.set(name, JSON.parse(readFileSync(path.join(DATA_DIR, name), "utf-8")));
  }
  return cache.get(name) as T;
}

export const getMeta = () => read<Meta>("meta.json");
export const getLots = () => read<Lot[]>("lots.json");
export const getAllLotsFull = () => read<LotFull[]>("lots-full.json");

/** Раздел «ТОП»; без файла (старая выгрузка) — пустой. */
export function getTop(): TopData {
  try {
    return read<TopData>("top.json");
  } catch {
    return { sections: [] };
  }
}

/** Оценка лота, если он в ТОПе (на карточке лота показываем её только для них). */
export function getTopItem(id: number): (TopItem & { section: string; slug: string; rank: number }) | null {
  for (const s of getTop().sections) {
    const i = s.items.findIndex((x) => x.id === id);
    if (i >= 0) return { ...s.items[i], section: s.title, slug: s.slug, rank: i + 1 };
  }
  return null;
}

export function getLot(id: string): LotFull | undefined {
  return getAllLotsFull().find((lot) => String(lot.id) === id);
}

export function getUpcomingAuctions(limit: number): { total: number; items: Lot[] } {
  const now = Date.now();
  const all = getLots()
    .filter((lot) => isUpcoming(lot, now))
    .sort((a, b) => Date.parse(a.auction_start!) - Date.parse(b.auction_start!));
  return { total: all.length, items: all.slice(0, limit) };
}
