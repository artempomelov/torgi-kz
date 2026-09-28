import Link from "next/link";

import type { Lot } from "@/lib/api";
import {
  CATEGORY_LABELS,
  ORIGIN_LABELS,
  SALE_TYPE_LABELS,
  SOURCE_LABELS,
  formatDate,
  formatPrice,
  formatPriceShort,
  lotSubtitle,
} from "@/lib/format";

export function Badge({ children, tone = "neutral" }: { children: React.ReactNode; tone?: "neutral" | "brand" | "accent" | "success" }) {
  const tones = {
    neutral: "bg-background text-muted",
    brand: "bg-brand/10 text-brand",
    accent: "bg-accent/10 text-accent",
    success: "bg-success/10 text-success",
  };
  return <span className={`rounded-md px-2 py-0.5 text-xs font-medium ${tones[tone]}`}>{children}</span>;
}

export function LotCard({ lot }: { lot: Lot }) {
  const isAuction = lot.sale_type === "auction" || lot.sale_type === "auction_down";
  const subtitle = lotSubtitle(lot);
  return (
    <Link
      href={`/lots/${lot.id}`}
      className="group flex flex-col overflow-hidden rounded-xl border border-border bg-surface transition hover:border-brand/40 hover:shadow-md"
    >
      <div className="relative aspect-[4/3] bg-background">
        {lot.image ? (
          // eslint-disable-next-line @next/next/no-img-element -- фото с десятка внешних доменов
          <img src={lot.image} alt={lot.title} loading="lazy" className="h-full w-full object-cover" />
        ) : (
          <div className="flex h-full items-center justify-center text-sm text-muted">Нет фото</div>
        )}
        <div className="absolute left-2 top-2 flex flex-wrap gap-1">
          <span className="rounded-md bg-surface/95 px-2 py-0.5 text-xs font-medium text-foreground">
            {CATEGORY_LABELS[lot.category] ?? lot.category}
          </span>
          {lot.price_drop_pct ? (
            <span className="rounded-md bg-accent px-2 py-0.5 text-xs font-semibold text-white">
              −{lot.price_drop_pct}%
            </span>
          ) : null}
        </div>
      </div>

      <div className="flex flex-1 flex-col gap-2 p-4">
        <div className="text-lg font-semibold" title={formatPrice(lot.price)}>
          {formatPriceShort(lot.price)}
          {lot.price_per_m2 ? (
            <span className="ml-2 text-xs font-normal text-muted">
              {Math.round(lot.price_per_m2).toLocaleString("ru-RU")} ₸/м²
            </span>
          ) : null}
        </div>
        {subtitle && <div className="text-sm text-foreground">{subtitle}</div>}
        <div className="line-clamp-2 text-sm text-muted group-hover:text-foreground">{lot.address ?? lot.title}</div>

        <div className="mt-auto flex flex-wrap gap-1 pt-2">
          {isAuction ? (
            <Badge tone="success">{SALE_TYPE_LABELS[lot.sale_type!]}</Badge>
          ) : lot.sale_type ? (
            <Badge>{SALE_TYPE_LABELS[lot.sale_type] ?? lot.sale_type}</Badge>
          ) : null}
          <Badge tone="brand">{ORIGIN_LABELS[lot.origin] ?? lot.origin}</Badge>
          <Badge>{SOURCE_LABELS[lot.source] ?? lot.source}</Badge>
        </div>
        {lot.auction_start && (
          <div className="text-xs text-muted">
            {lot.auction_end && new Date(lot.auction_start) <= new Date()
              ? `Торги идут до ${formatDate(lot.auction_end, true)}`
              : `Торги: ${formatDate(lot.auction_start, true)}`}
          </div>
        )}
      </div>
    </Link>
  );
}
