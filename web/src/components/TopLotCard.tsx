// Карточка в разделе «ТОП»: место в рейтинге и выгода относительно рынка поверх обычной карточки лота.
import type { Lot, TopItem } from "@/lib/api";
import { formatPriceShort } from "@/lib/format";

import { LotCard } from "./LotCard";

export function TopLotCard({ lot, top, rank }: { lot: Lot; top: TopItem; rank: number }) {
  return (
    <div className="flex flex-col">
      <div className="flex items-center gap-3 rounded-t-xl bg-success/10 px-3 py-2">
        <span className="flex h-8 w-8 flex-none items-center justify-center rounded-full bg-success text-sm font-bold text-white">
          {rank}
        </span>
        <div className="min-w-0 leading-tight">
          <div className="text-sm font-bold text-success">−{top.discount_pct}% к рынку</div>
          <div className="truncate text-xs text-muted" title={`Оценка по ${top.sample} объявлениям: ${top.segment}`}>
            рынок ≈ {formatPriceShort(top.estimate)}
          </div>
        </div>
      </div>
      <div className="-mt-px flex-1 [&>a]:h-full [&>a]:rounded-t-none">
        <LotCard lot={lot} />
      </div>
    </div>
  );
}
