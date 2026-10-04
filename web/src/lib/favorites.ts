"use client";

// Избранное без регистрации: id лотов в localStorage этого браузера.
import { useSyncExternalStore } from "react";

const KEY = "torgi:favorites";
const EVENT = "torgi:favorites";
const EMPTY: number[] = [];

let cache: { raw: string | null; ids: number[] } = { raw: null, ids: EMPTY };

function read(): number[] {
  let raw: string | null = null;
  try {
    raw = localStorage.getItem(KEY);
  } catch {
    return EMPTY;
  }
  if (raw !== cache.raw) {
    try {
      const parsed = raw ? JSON.parse(raw) : [];
      cache = { raw, ids: Array.isArray(parsed) ? parsed.filter((x) => typeof x === "number") : EMPTY };
    } catch {
      cache = { raw, ids: EMPTY };
    }
  }
  return cache.ids;
}

function subscribe(cb: () => void) {
  window.addEventListener("storage", cb);
  window.addEventListener(EVENT, cb);
  return () => {
    window.removeEventListener("storage", cb);
    window.removeEventListener(EVENT, cb);
  };
}

export function useFavorites(): number[] {
  return useSyncExternalStore(subscribe, read, () => EMPTY);
}

export function toggleFavorite(id: number) {
  const ids = read();
  const next = ids.includes(id) ? ids.filter((x) => x !== id) : [id, ...ids];
  try {
    localStorage.setItem(KEY, JSON.stringify(next));
  } catch {
    return; // приватный режим — избранное не сохранится
  }
  window.dispatchEvent(new Event(EVENT));
}
