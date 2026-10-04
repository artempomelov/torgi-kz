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
  unitPrice,
} from "@/lib/format";

import { FavoriteButton } from "./FavoriteButton";
import { LotImage } from "./LotImage";

export function Badge({ children, tone = "neutral" }: { children: React.ReactNode; tone?: "neutral" | "brand" | "accent" | "success" }) {
  const tones = {
    neutral: "bg-background text-muted",
    brand: "bg-brand/10 text-brand-ink",
    accent: "bg-accent/15 text-accent-ink",
    success: "bg-success/10 text-success",
  };
  return <span className={`rounded-md px-2 py-0.5 text-xs font-medium ${tones[tone]}`}>{children}</span>;
}

export function LotCard({ lot }: { lot: Lot }) {
  const isAuction = lot.sale_type === "auction" || lot.sale_type === "auction_down";
  const subtitle = lotSubtitle(lot);
  return (
    <Link
      href={`/lots/${lot.id}/`}
      className="group flex flex-col overflow-hidden rounded-xl border border-border bg-surface transition hover:border-brand/50 hover:shadow-card"
    >
      <div className="relative aspect-[4/3] bg-background">
        <LotImage src={lot.image} category={lot.category} alt={lot.headline} className="h-full w-full object-cover" />
        <div className="absolute left-2 top-2 flex flex-wrap gap-1">
          <span className="rounded-md bg-surface/95 px-2 py-0.5 text-xs font-medium text-foreground">
            {CATEGORY_LABELS[lot.category] ?? lot.category}
          </span>
          {lot.price_drop_pct ? (
            <span className="rounded-md bg-accent px-2 py-0.5 text-xs font-semibold text-foreground">
              −{lot.price_drop_pct}%
            </span>
          ) : null}
        </div>
        <div className="absolute right-2 top-2">
          <FavoriteButton id={lot.id} />
        </div>
      </div>

      <div className="flex flex-1 flex-col gap-2 p-4">
        <div className="text-lg font-semibold" title={formatPrice(lot.price)}>
          {formatPriceShort(lot.price)}
          {unitPrice(lot) && <span className="ml-2 text-xs font-normal text-muted">{unitPrice(lot)!.label}</span>}
        </div>
        {subtitle && <div className="text-sm text-foreground">{subtitle}</div>}
        <div className="line-clamp-2 text-sm text-muted group-hover:text-foreground">
          {/* в платном режиме точного адреса в каталоге нет — только город/регион */}
          {lot.address ?? lot.title ?? [lot.city, lot.region !== lot.city ? lot.region : null].filter(Boolean).join(", ")}
        </div>

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
