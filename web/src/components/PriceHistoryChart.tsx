// График истории цены на карточке лота: ступеньки по датам, когда мы видели новую цену у источника.
// Статичный SVG без библиотек — рисуется при сборке, виден поисковикам и без JavaScript.
import { formatDate, formatPrice } from "@/lib/format";

type Point = { price: number | null; seen_at: string };

const W = 640;
const H = 180;
const PAD = { left: 8, right: 8, top: 16, bottom: 24 };

/** Только смены цены: подряд одинаковые значения схлопываем. */
function changes(history: Point[]): { price: number; t: number }[] {
  const out: { price: number; t: number }[] = [];
  for (const p of [...history].sort((a, b) => Date.parse(a.seen_at) - Date.parse(b.seen_at))) {
    if (p.price == null || out.at(-1)?.price === p.price) continue;
    out.push({ price: p.price, t: Date.parse(p.seen_at) });
  }
  return out;
}

export function PriceHistoryChart({ history, until, isAuction }: { history: Point[]; until: string; isAuction: boolean }) {
  const pts = changes(history);
  if (pts.length < 2) return null;

  const first = pts[0];
  const last = pts.at(-1)!;
  const t0 = first.t;
  const t1 = Math.max(Date.parse(until), last.t + 1);
  const prices = pts.map((p) => p.price);
  const lo = Math.min(...prices);
  const hi = Math.max(...prices);
  const span = hi - lo || hi * 0.1;
  const yMin = lo - span * 0.15;
  const yMax = hi + span * 0.15;

  const x = (t: number) => PAD.left + ((t - t0) / (t1 - t0)) * (W - PAD.left - PAD.right);
  const y = (v: number) => PAD.top + (1 - (v - yMin) / (yMax - yMin)) * (H - PAD.top - PAD.bottom);

  // ступенчатая линия: цена держится до следующей смены
  let d = `M${x(first.t)},${y(first.price)}`;
  for (const p of pts.slice(1)) d += ` H${x(p.t)} V${y(p.price)}`;
  d += ` H${x(t1)}`;
  const area = `${d} V${H - PAD.bottom} H${x(first.t)} Z`;

  const diff = last.price - first.price;
  const pct = Math.round((diff / first.price) * 100);

  return (
    <section className="rounded-xl border border-border bg-surface p-5">
      <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-lg font-semibold">История цены</h2>
        <span className={`text-sm font-medium ${diff < 0 ? "text-success" : "text-accent-ink"}`}>
          {diff < 0 ? "−" : "+"}
          {formatPrice(Math.abs(diff))} ({diff < 0 ? "−" : "+"}{Math.abs(pct)}%) с {formatDate(new Date(first.t).toISOString())}
        </span>
      </div>

      <svg viewBox={`0 0 ${W} ${H}`} className="h-auto w-full text-brand-ink" role="img"
           aria-label={`Цена менялась ${pts.length - 1} раз: с ${formatPrice(first.price)} до ${formatPrice(last.price)}`}>
        <path d={area} fill="currentColor" opacity={0.08} />
        <path d={d} fill="none" stroke="currentColor" strokeWidth={2.5} strokeLinejoin="round" />
        {pts.map((p) => (
          <circle key={p.t} cx={x(p.t)} cy={y(p.price)} r={4} fill="var(--color-surface)" stroke="currentColor" strokeWidth={2} />
        ))}
        <text x={PAD.left} y={H - 6} fontSize={12} className="fill-muted">{formatDate(new Date(t0).toISOString())}</text>
        <text x={W - PAD.right} y={H - 6} fontSize={12} textAnchor="end" className="fill-muted">{formatDate(until)}</text>
      </svg>

      <ul className="mt-3 space-y-1 text-sm">
        {pts.map((p, i) => (
          <li key={p.t} className="flex justify-between gap-4">
            <span className="text-muted">{formatDate(new Date(p.t).toISOString())}</span>
            <span className="font-medium">
              {formatPrice(p.price)}
              {i > 0 && (
                <span className={`ml-2 text-xs ${p.price < pts[i - 1].price ? "text-success" : "text-accent-ink"}`}>
                  {p.price < pts[i - 1].price ? "↓" : "↑"}{" "}
                  {Math.abs(Math.round(((p.price - pts[i - 1].price) / pts[i - 1].price) * 100))}%
                </span>
              )}
            </span>
          </li>
        ))}
      </ul>
      {isAuction && (
        <p className="mt-2 text-xs text-muted">Для торгов снижение — это обычно новый этап после несостоявшегося аукциона.</p>
      )}
    </section>
  );
}
