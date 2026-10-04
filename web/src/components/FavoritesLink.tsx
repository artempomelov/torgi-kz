"use client";

import Link from "next/link";

import { useFavorites } from "@/lib/favorites";

export function FavoritesLink() {
  const n = useFavorites().length;
  return (
    <Link href="/izbrannoe/" className="font-medium text-muted hover:text-brand-ink">
      ♡ Избранное{n > 0 && <span className="ml-1 rounded-full bg-accent px-1.5 text-xs font-semibold text-white">{n}</span>}
    </Link>
  );
}
