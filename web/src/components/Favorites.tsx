"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { LotCard } from "@/components/LotCard";
import type { Lot } from "@/lib/api";
import { loadLots } from "@/lib/catalog-data";
import { useFavorites } from "@/lib/favorites";

export function Favorites() {
  const ids = useFavorites();
  const [lots, setLots] = useState<Lot[] | null>(null);
  useEffect(() => {
    loadLots().then(setLots, () => setLots([]));
  }, []);

  const byId = new Map((lots ?? []).map((l) => [l.id, l]));
  const items = ids.map((id) => byId.get(id)).filter((l): l is Lot => !!l);
  const gone = lots ? ids.length - items.length : 0;

  return (
    <div className="mx-auto max-w-7xl px-4 py-8">
      <h1 className="text-2xl font-bold md:text-3xl">Избранное</h1>
      <p className="mt-1 text-muted">
        Сохраняется в этом браузере, без регистрации.
        {gone > 0 && ` ${gone} из сохранённых объектов уже сняты с продажи.`}
      </p>
      {!lots ? (
        <div className="mt-6 h-40 animate-pulse rounded-xl bg-surface" />
      ) : items.length === 0 ? (
        <div className="mt-6 rounded-xl border border-dashed border-border bg-surface p-10 text-center text-muted">
          Пока пусто. Нажмите ♡ на карточке объекта, чтобы сохранить его здесь.{" "}
          <Link href="/lots/" className="font-medium text-brand-ink">Перейти в каталог</Link>
        </div>
      ) : (
        <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {items.map((lot) => <LotCard key={lot.id} lot={lot} />)}
        </div>
      )}
    </div>
  );
}
