"use client";

// Счётчики «смотрят» и «в избранном» (worker на Cloudflare). Без API (FEATURES.apiUrl) — тихо выключены.
import { useEffect, useState } from "react";

import { FEATURES } from "./features";

export type LotStats = { views: number; favs: number };

const api = (path: string) => `${FEATURES.apiUrl}${path}`;
const enabled = () => !!FEATURES.apiUrl;

// Запросы карточек одной страницы собираются в один GET /api/stats?ids=...
const cache = new Map<number, LotStats>();
const waiting = new Map<number, ((s: LotStats) => void)[]>();
let timer: ReturnType<typeof setTimeout> | null = null;

function flush() {
  timer = null;
  const ids = [...waiting.keys()].slice(0, 100);
  const callbacks = ids.map((id) => [id, waiting.get(id)!] as const);
  ids.forEach((id) => waiting.delete(id));
  fetch(api(`/api/stats?ids=${ids.join(",")}`))
    .then((r) => (r.ok ? r.json() : {}))
    .catch(() => ({}))
    .then((data: Record<string, LotStats>) => {
      for (const [id, cbs] of callbacks) {
        const s = data[id] ?? { views: 0, favs: 0 };
        cache.set(id, s);
        cbs.forEach((cb) => cb(s));
      }
    });
  if (waiting.size) timer = setTimeout(flush, 0);
}

export function useLotStats(id: number): LotStats | null {
  const [stats, setStats] = useState<LotStats | null>(() => cache.get(id) ?? null);
  useEffect(() => {
    if (!enabled() || cache.has(id)) return;
    waiting.set(id, [...(waiting.get(id) ?? []), setStats]);
    timer ??= setTimeout(flush, 30);
  }, [id]);
  return stats;
}

export function recordView(id: number) {
  if (enabled()) fetch(api(`/api/hit/${id}`), { method: "POST" }).catch(() => undefined);
}

function clientId(): string {
  try {
    let id = localStorage.getItem("torgi:client");
    if (!id) {
      id = crypto.randomUUID();
      localStorage.setItem("torgi:client", id);
    }
    return id;
  } catch {
    return "";
  }
}

export function syncFavorite(id: number, on: boolean) {
  const client = clientId();
  if (!enabled() || !client) return;
  cache.delete(id);
  fetch(api(`/api/fav/${id}`), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ client, on }),
  }).catch(() => undefined);
}
