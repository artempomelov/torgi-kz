// Данные для сборки статического сайта: читаются из web/data во время `next build` (только сервер).
import { readFileSync } from "node:fs";
import path from "node:path";

import type { Lot, LotFull, Meta } from "./api";
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
