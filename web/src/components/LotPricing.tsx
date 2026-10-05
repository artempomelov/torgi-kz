// Блоки цены на странице лота: аукцион на понижение (старт → минимум), уведомление о снижении до порога.
import type { LotFull } from "@/lib/api";
import { formatPrice, formatPriceShort } from "@/lib/format";
import { watchLotLink } from "@/lib/subscribe";

/** Аукцион на понижение: в Казахстане цена снижается шагами прямо на торгах, до минимальной. */
export function DescendingAuction({ lot }: { lot: LotFull }) {
  if (lot.sale_type !== "auction_down" || !lot.price) return null;
  const min = lot.min_price && lot.min_price < lot.price ? lot.min_price : null;
  const pct = min ? Math.round((1 - min / lot.price) * 100) : null;
  // ориентиры: −10%, −20%, … до минимальной цены
  const marks = min ? Array.from({ length: Math.floor((pct ?? 0) / 10) }, (_, i) => (i + 1) * 10) : [];

  return (
    <section className="rounded-xl border border-border bg-surface p-5">
      <h2 className="text-lg font-semibold">Аукцион на понижение</h2>
      <p className="mt-1 text-sm text-muted">
        На торгах цена снижается шагами от стартовой. Побеждает тот, кто первым согласится на текущую цену —
        можно ждать снижения, но объект могут забрать раньше.
      </p>
      {min ? (
        <>
          <div className="mt-4 flex items-end justify-between text-sm">
            <div>
              <div className="text-muted">Старт</div>
              <div className="font-semibold">{formatPrice(lot.price)}</div>
            </div>
            <div className="text-right">
              <div className="text-muted">Минимальная цена</div>
              <div className="font-semibold text-success">{formatPrice(min)}</div>
            </div>
          </div>
          <div className="relative mt-3 h-2 rounded-full bg-gradient-to-r from-foreground/80 to-success">
            {marks.map((m) => (
              <span key={m} className="absolute top-0 h-2 w-px bg-surface" style={{ left: `${(m / (pct ?? 100)) * 100}%` }} />
            ))}
          </div>
          <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted">
            {marks.map((m) => (
              <span key={m}>−{m}%: {formatPriceShort(lot.price! * (1 - m / 100))}</span>
            ))}
          </div>
          <div className="mt-3 rounded-lg bg-success/10 p-3 text-sm text-success">
            Максимальная выгода — <b>{formatPrice(lot.price - min)}</b> (−{pct}% от старта), если никто не согласится раньше.
          </div>
        </>
      ) : (
        <p className="mt-3 text-sm text-muted">Минимальную цену площадка не публикует — уточняйте в условиях торгов.</p>
      )}
    </section>
  );
}

/** «Сообщить, когда цена опустится до …» — пороги: −10/−20/−30% и минимальная цена. */
export function PriceAlerts({ lot }: { lot: LotFull }) {
  if (!lot.price || lot.status !== "active") return null;
  const targets = [10, 20, 30].map((p) => ({ label: `−${p}%`, value: lot.price! * (1 - p / 100) }));
  if (lot.min_price && lot.min_price < lot.price * 0.7) {
    targets.push({ label: "минимум", value: lot.min_price });
  }
  return (
    <div>
      <div className="mb-2 text-sm text-muted">🔔 Сообщить в Telegram, когда цена опустится до:</div>
      <div className="grid grid-cols-2 gap-2">
        {targets.map((t) => (
          <a key={t.label} href={watchLotLink(lot.id, t.value)} target="_blank" rel="noopener noreferrer"
             className="rounded-lg border border-border px-2 py-2 text-center text-sm hover:border-brand-ink/40">
            <span className="font-medium">{formatPriceShort(t.value)}</span>{" "}
            <span className="text-xs text-muted">{t.label}</span>
          </a>
        ))}
      </div>
      <a href={watchLotLink(lot.id)} target="_blank" rel="noopener noreferrer"
         className="mt-2 block text-center text-xs text-brand-ink hover:underline">
        или при любом изменении цены
      </a>
    </div>
  );
}
