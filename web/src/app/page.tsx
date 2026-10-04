import Link from "next/link";

import { LotCard } from "@/components/LotCard";
import type { Lot } from "@/lib/api";
import { getLots, getMeta, getUpcomingAuctions } from "@/lib/data";
import { applyFilters, parseFilters } from "@/lib/filter";
import { CATEGORY_PLURAL, formatDate, plural } from "@/lib/format";
import { pickShowcase } from "@/lib/insights";

// Готовые подборки на главной: ссылка в каталог с фильтрами и число объектов в ней
const QUICK = [
  { title: "Квартиры дешевле 350 тыс. ₸ за м²", query: "category=apartment&ppm_max=350000&sort=price_m2_asc" },
  { title: "Подешевели с момента публикации", query: "drop=true&sort=drop" },
  { title: "Торги в ближайшие 7 дней", query: "with_auction_date=true&sort=deadline", week: true },
  { title: "Дома до 20 млн ₸", query: "category=house&price_max=20000000&sort=price_asc" },
  { title: "Залоги и имущество банков в Алматы", query: "origin=bank_pledge&origin=bank_balance&region=Алматы" },
  { title: "Коммерческая недвижимость в Астане", query: "category=commercial&region=Астана" },
];

function quickCount(lots: Lot[], q: (typeof QUICK)[number]): number {
  const found = applyFilters(lots, parseFilters(new URLSearchParams(q.query)));
  if (!q.week) return found.length;
  const weekAhead = Date.now() + 7 * 86_400_000;
  return found.filter((l) => Date.parse(l.auction_start!) <= weekAhead).length;
}

export default function Home() {
  const meta = getMeta();
  const lots = getLots();
  // lots.json уже отсортирован: новые первыми. В витрину — объекты с фото, жильё и коммерция
  const latest = { items: pickShowcase(lots.slice(0, 300), 8) };
  const upcoming = getUpcomingAuctions(Infinity);
  const auctions = { total: upcoming.total, items: pickShowcase(upcoming.items.slice(0, 200), 4) };
  const quick = QUICK.map((q) => ({ ...q, count: quickCount(lots, q) })).filter((q) => q.count > 0);
  const categories = meta.categories.filter((c) => c.count > 0);

  return (
    <div>
      <section className="hero-bg border-b border-border">
        <div className="mx-auto max-w-7xl px-4 py-12 md:py-16">
          <h1 className="max-w-3xl text-3xl font-bold leading-tight text-foreground md:text-5xl">
            Все торги недвижимостью Казахстана в одном месте
          </h1>
          <p className="mt-4 max-w-2xl text-base text-muted md:text-lg">
            {meta.total.toLocaleString("ru-RU")} {plural(meta.total, ["объект", "объекта", "объектов"])}: арестованное
            имущество с площадки Минюста, госимущество и приватизация, имущество банкротов и конфискат с
            E-Qazyna, залоги и имущество банков. Обновлено {formatDate(meta.updated_at, true)}.
          </p>
          <form action="/lots/" className="mt-8 flex max-w-2xl flex-col gap-2 sm:flex-row">
            <input
              name="q"
              placeholder="Город или улица"
              className="flex-1 rounded-[10px] border border-border bg-white px-4 py-3 text-foreground shadow-card outline-none placeholder:text-muted focus:border-brand-ink focus:ring-2 focus:ring-brand-ink/20"
            />
            <button className="rounded-[10px] bg-brand px-6 py-3 font-semibold text-white hover:bg-brand-hover">
              Найти
            </button>
          </form>
          <div className="mt-6 flex flex-wrap gap-2">
            {categories.map((c) => (
              <Link
                key={c.id}
                href={`/lots/?category=${c.id}`}
                className="rounded-full border border-border bg-white px-4 py-1.5 text-sm text-foreground hover:border-brand-ink hover:text-brand-ink"
              >
                {CATEGORY_PLURAL[c.id] ?? c.title} <span className="text-muted">{c.count}</span>
              </Link>
            ))}
          </div>
        </div>
      </section>

      {quick.length > 0 && (
        <section className="mx-auto max-w-7xl px-4 pt-10">
          <div className="mb-4 flex items-baseline justify-between">
            <h2 className="text-2xl font-bold">Подборки</h2>
            <Link href="/podborki/" className="text-sm font-medium text-brand-ink">Все подборки →</Link>
          </div>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {quick.map((q) => (
              <Link key={q.query} href={`/lots/?${q.query}`}
                    className="flex items-center justify-between gap-3 rounded-xl border border-border bg-surface p-4 hover:border-brand-ink/40">
                <span className="font-medium">{q.title}</span>
                <span className="rounded-full bg-brand-ink/10 px-2.5 py-0.5 text-sm font-semibold text-brand-ink">{q.count}</span>
              </Link>
            ))}
          </div>
        </section>
      )}

      {auctions.items.length > 0 && (
        <section className="mx-auto max-w-7xl px-4 pt-10">
          <div className="mb-4 flex items-baseline justify-between">
            <h2 className="text-2xl font-bold">Ближайшие торги</h2>
            <Link href="/lots/?with_auction_date=true&sort=deadline" className="text-sm font-medium text-brand-ink">
              Все {auctions.total} →
            </Link>
          </div>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {auctions.items.map((lot) => (
              <LotCard key={lot.id} lot={lot} />
            ))}
          </div>
        </section>
      )}

      <section className="mx-auto max-w-7xl px-4 pt-10">
        <div className="mb-4 flex items-baseline justify-between">
          <h2 className="text-2xl font-bold">Новые объекты</h2>
          <Link href="/lots/" className="text-sm font-medium text-brand-ink">
            Весь каталог →
          </Link>
        </div>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {latest.items.map((lot) => (
            <LotCard key={lot.id} lot={lot} />
          ))}
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-4 pt-12">
        <h2 className="mb-4 text-2xl font-bold">Источники</h2>
        <div className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-6">
          {meta.sources.map((s) => (
            <Link
              key={s.id}
              href={`/lots/?source=${s.id}`}
              className="rounded-xl border border-border bg-surface p-4 hover:border-brand-ink/40"
            >
              <div className="text-sm font-semibold">{s.title}</div>
              <div className="mt-1 text-2xl font-bold text-brand-ink">{s.count}</div>
            </Link>
          ))}
        </div>
      </section>
    </div>
  );
}
