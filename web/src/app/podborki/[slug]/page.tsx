import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { Faq } from "@/components/Faq";
import { LotCard } from "@/components/LotCard";
import { getCollections } from "@/lib/collections";
import { getLots, getMeta } from "@/lib/data";
import { isUpcoming } from "@/lib/filter";
import { formatDate, formatPrice, plural } from "@/lib/format";

export const dynamicParams = false;
const SHOWN = 48;

export function generateStaticParams() {
  return getCollections(getLots()).map((c) => ({ slug: c.slug }));
}

function load(slug: string) {
  const lots = getLots();
  const collections = getCollections(lots);
  const c = collections.find((x) => x.slug === slug);
  if (!c) return null;
  const items = lots.filter(c.match);
  const prices = items.map((l) => l.price).filter((p): p is number => !!p);
  const ppm = items
    .filter((l) => l.category === "apartment" || l.category === "commercial")
    .map((l) => l.price_per_m2)
    .filter((p): p is number => !!p)
    .sort((a, b) => a - b);
  return {
    c,
    collections,
    items,
    minPrice: prices.length ? Math.min(...prices) : null,
    medianPpm: ppm.length >= 3 ? ppm[Math.floor(ppm.length / 2)] : null,
    upcoming: items.filter((l) => isUpcoming(l)).length,
  };
}

export async function generateMetadata({ params }: PageProps<"/podborki/[slug]">): Promise<Metadata> {
  const data = load((await params).slug);
  if (!data) return {};
  const { c, items, minPrice } = data;
  const count = `${items.length} ${plural(items.length, ["объект", "объекта", "объектов"])}`;
  return {
    title: c.title,
    description: `${c.lead}. ${count}${minPrice ? ` от ${formatPrice(minPrice)}` : ""}. Обновляется ежедневно.`,
    alternates: { canonical: `/podborki/${c.slug}/` },
  };
}

export default async function CollectionPage({ params }: PageProps<"/podborki/[slug]">) {
  const data = load((await params).slug);
  if (!data) notFound();
  const { c, collections, items, minPrice, medianPpm, upcoming } = data;
  // Сначала объекты с фото, внутри — новые
  const shown = [...items]
    .sort((a, b) => Number(!!b.image) - Number(!!a.image) || Date.parse(b.first_seen_at) - Date.parse(a.first_seen_at))
    .slice(0, SHOWN);
  const related = collections.filter((x) => x.slug !== c.slug && x.group === c.group).slice(0, 24);

  return (
    <div className="mx-auto max-w-7xl px-4 py-8">
      <nav className="mb-4 text-sm text-muted">
        <Link href="/" className="hover:text-brand-ink">Главная</Link> /{" "}
        <Link href="/podborki/" className="hover:text-brand-ink">Подборки</Link>
      </nav>
      <h1 className="text-3xl font-bold leading-tight md:text-4xl">{c.title}</h1>
      <p className="mt-3 max-w-3xl text-muted">
        {c.lead}. Сейчас в продаже {items.length} {plural(items.length, ["объект", "объекта", "объектов"])}
        {minPrice ? <>, цены от {formatPrice(minPrice)}</> : null}
        {medianPpm ? <>, типичная цена — {formatPrice(medianPpm)} за м²</> : null}
        {upcoming ? <>; торги назначены по {upcoming} {plural(upcoming, ["лоту", "лотам", "лотам"])}</> : null}.
        Данные собираются с площадок и сайтов банков каждый день, последнее обновление —{" "}
        {formatDate(getMeta().updated_at)}
      </p>
      <Link
        href={c.catalogHref}
        className="mt-5 inline-block rounded-[10px] bg-brand px-5 py-2.5 font-semibold text-white hover:bg-brand-hover"
      >
        Открыть в каталоге с фильтрами
      </Link>

      <div className="mt-8 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {shown.map((lot) => (
          <LotCard key={lot.id} lot={lot} />
        ))}
      </div>
      {items.length > SHOWN && (
        <p className="mt-6 text-center">
          <Link href={c.catalogHref} className="font-medium text-brand-ink">
            Ещё {items.length - SHOWN} в каталоге →
          </Link>
        </p>
      )}

      {related.length > 0 && (
        <section className="mt-12">
          <h2 className="mb-3 text-xl font-bold">Похожие подборки</h2>
          <div className="flex flex-wrap gap-2">
            {related.map((x) => (
              <Link
                key={x.slug}
                href={`/podborki/${x.slug}/`}
                className="rounded-full border border-border bg-surface px-3 py-1 text-sm hover:border-brand-ink hover:text-brand-ink"
              >
                {x.title} <span className="text-muted">{x.count}</span>
              </Link>
            ))}
          </div>
        </section>
      )}
      <Faq className="mt-12 !px-0" />
    </div>
  );
}
