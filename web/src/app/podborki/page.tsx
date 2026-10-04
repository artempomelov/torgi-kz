import type { Metadata } from "next";
import Link from "next/link";

import { getCollections, type Collection } from "@/lib/collections";
import { getLots } from "@/lib/data";

export const metadata: Metadata = {
  title: "Подборки недвижимости с торгов",
  description:
    "Квартиры, дома, коммерция и земля с торгов по городам Казахстана, залоговое имущество банков, госимущество, банкроты и конфискат.",
  alternates: { canonical: "/podborki/" },
};

const GROUPS: { id: Collection["group"]; title: string }[] = [
  { id: "category", title: "По типу объекта" },
  { id: "city", title: "По городам" },
  { id: "origin", title: "По виду продажи" },
  { id: "source", title: "По источнику" },
];

export default function CollectionsIndex() {
  const collections = getCollections(getLots());
  return (
    <div className="mx-auto max-w-7xl px-4 py-8">
      <h1 className="text-3xl font-bold md:text-4xl">Подборки недвижимости с торгов</h1>
      {GROUPS.map((g) => (
        <section key={g.id} className="mt-8">
          <h2 className="mb-3 text-xl font-bold">{g.title}</h2>
          <div className="grid grid-cols-1 gap-x-6 gap-y-1.5 sm:grid-cols-2 lg:grid-cols-3">
            {collections
              .filter((c) => c.group === g.id)
              .map((c) => (
                <Link key={c.slug} href={`/podborki/${c.slug}/`} className="text-sm hover:text-brand-ink">
                  {c.title} <span className="text-muted">{c.count}</span>
                </Link>
              ))}
          </div>
        </section>
      ))}
    </div>
  );
}
