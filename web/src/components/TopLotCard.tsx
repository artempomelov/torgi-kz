// Карточка в разделе «ТОП»: место в рейтинге и выгода относительно рынка поверх обычной карточки лота.
import type { Lot, TopItem } from "@/lib/api";

import { LotCard, marketTone } from "./LotCard";

export function TopLotCard({ lot, top, rank }: { lot: Lot; top: TopItem; rank: number }) {
  const badge = { pct: top.discount_pct, over: !!top.discount_note };
  return (
    <div className="flex flex-col">
      <div className="flex items-center gap-3 rounded-t-xl border border-b-0 border-border bg-surface px-3 py-2">
        <span className="flex h-8 w-8 flex-none items-center justify-center rounded-full bg-brand text-sm font-bold text-white">
          {rank}
        </span>
        <div className="flex min-w-0 items-center gap-2 leading-tight">
          <span className={`flex-none rounded-md px-2 py-0.5 text-sm font-bold ${marketTone(badge)}`}>
            {top.discount_note ? `более −30%` : `−${top.discount_pct}%`} к рынку
          </span>
        </div>
      </div>
      <div className="-mt-px flex-1 [&>a]:h-full [&>a]:rounded-t-none">
        {/* скидка уже в шапке — на фото плашку не дублируем */}
        <LotCard lot={{ ...lot, image: top.image ?? lot.image, market: null }} />
      </div>
    </div>
  );
}
