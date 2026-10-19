import type { Metadata } from "next";
import Link from "next/link";

import { LotCard } from "@/components/LotCard";
import { getLots } from "@/lib/data";
import { latestLots } from "@/lib/insights";

export const metadata: Metadata = {
  title: "Новое на торгах",
  description: "Последние объекты, добавленные на torgi.kz: квартиры, дома, коммерция и земля с торгов и из залогов банков.",
  alternates: { canonical: "/novoe/" },
};

const day = new Intl.DateTimeFormat("ru-RU", { day: "numeric", month: "long", timeZone: "Asia/Almaty" });

export default function NewPage() {
  const lots = latestLots(getLots(), 10);
  // по дням добавления: «19 октября», «17 октября»…
  const days = new Map<string, typeof lots>();
  for (const lot of lots) {
    const d = day.format(new Date(lot.first_seen_at));
    days.set(d, [...(days.get(d) ?? []), lot]);
  }

  return (
    <div className="mx-auto max-w-7xl px-4 py-8">
      <h1 className="text-3xl font-bold md:text-4xl">Новое на торгах</h1>
      <p className="mt-3 max-w-3xl text-muted">Последние объекты, добавленные на torgi.kz.</p>

      {[...days].map(([d, items]) => (
        <section key={d} className="mt-8">
          <h2 className="text-xl font-bold">{d}</h2>
          <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {items.map((lot) => <LotCard key={lot.id} lot={lot} />)}
          </div>
        </section>
      ))}

      <Link href="/lots/?sort=new" className="mt-10 inline-block font-medium text-brand-ink">
        Весь каталог — сначала новые →
      </Link>
    </div>
  );
}
