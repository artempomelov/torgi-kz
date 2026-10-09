import type { Metadata } from "next";
import Link from "next/link";

import { TopLotCard } from "@/components/TopLotCard";
import { getLots, getTop } from "@/lib/data";
import { formatDate } from "@/lib/format";

export const metadata: Metadata = {
  title: "ТОП выгодных объектов с торгов — ниже рынка",
  description:
    "Рейтинг самых выгодных квартир, домов и коммерческой недвижимости с торгов и из залогов банков: насколько цена ниже рынка по оценке torgi.kz.",
  alternates: { canonical: "/top/" },
};

export default function TopPage() {
  const top = getTop();
  const lots = new Map(getLots().map((l) => [l.id, l]));
  const sections = top.sections
    .map((s) => ({ ...s, items: s.items.filter((x) => lots.has(x.id)) }))
    .filter((s) => s.items.length > 0);

  return (
    <div className="mx-auto max-w-7xl px-4 py-8">
      <h1 className="text-3xl font-bold md:text-4xl">ТОП выгодных объектов</h1>
      <p className="mt-3 max-w-3xl text-muted">
        Объекты с торгов и из залогов банков, цена которых заметно ниже рынка. Рынок — это оценка torgi.kz по
        объявлениям о продаже похожих объектов в том же городе и районе: для квартир — с тем же числом комнат.
        Рейтинг обновляется вместе с каталогом.
      </p>

      {sections.length > 0 ? (
        <nav className="mt-5 flex flex-wrap gap-2" aria-label="Разделы ТОПа">
          {sections.map((s) => (
            <a key={s.slug} href={`#${s.slug}`}
               className="rounded-full border border-border bg-surface px-3 py-1.5 text-sm font-medium hover:border-brand-ink hover:text-brand-ink">
              {s.title}
            </a>
          ))}
        </nav>
      ) : (
        <p className="mt-8 rounded-xl border border-dashed border-border bg-surface p-10 text-center text-muted">
          Рейтинг обновляется — загляните чуть позже или посмотрите <Link href="/lots/" className="text-brand-ink">каталог</Link>.
        </p>
      )}

      {sections.map((s) => (
        <section key={s.slug} id={s.slug} className="mt-12 scroll-mt-4">
          <h2 className="text-2xl font-bold">{s.title}</h2>
          <p className="mt-1 text-sm text-muted">{s.subtitle}</p>
          <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {s.items.map((x, i) => (
              <TopLotCard key={x.id} lot={lots.get(x.id)!} top={x} rank={i + 1} />
            ))}
          </div>
        </section>
      ))}

      <section className="mt-14 max-w-3xl rounded-xl border border-border bg-surface p-5 text-sm leading-6 text-muted">
        <h2 className="mb-2 text-base font-semibold text-foreground">Как мы считаем выгоду</h2>
        <p>
          Для каждого объекта берём медианную цену квадратного метра в объявлениях о продаже похожих объектов: тот же
          город, по возможности тот же район и комнатность. Оценка = эта цена × площадь лота. В рейтинг попадают объекты
          дешевле оценки на 10–55%, с правдоподобной площадью и без признаков ошибки в данных; из одного дома или ЖК —
          не больше двух.
        </p>
        <p className="mt-2">
          Цены в объявлениях обычно на 5–10% выше цен сделок, а состояние объекта, долги, обременения и проживающие
          жильцы в оценке не учтены. Это ориентир, а не отчёт об оценке — перед покупкой проверяйте объект и документы.
          {top.market_updated_at ? <> Рыночные цены обновлены {formatDate(top.market_updated_at)}.</> : null}
        </p>
      </section>
    </div>
  );
}
