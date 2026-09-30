import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { Badge } from "@/components/LotCard";
import { LotDetails } from "@/components/LotDetails";
import { TelegramCta } from "@/components/TelegramCta";
import { getAllLotsFull, getLot } from "@/lib/data";
import {
  CATEGORY_LABELS,
  ORIGIN_LABELS,
  SALE_TYPE_LABELS,
  SOURCE_LABELS,
  formatDate,
  formatNumber,
  formatPrice,
  lotSubtitle,
} from "@/lib/format";

// Статическая сборка: страница на каждый лот из выгрузки, остальные адреса — 404
export const dynamicParams = false;

export function generateStaticParams() {
  return getAllLotsFull().map((lot) => ({ id: String(lot.id) }));
}

export async function generateMetadata({ params }: PageProps<"/lots/[id]">): Promise<Metadata> {
  const lot = getLot((await params).id);
  if (!lot) return { title: "Лот не найден" };
  // Только публичные поля — метаданные одинаковы в бесплатном и платном режиме
  return {
    title: `${lot.headline} — ${formatPrice(lot.price)}`,
    description: [lotSubtitle(lot), lot.city ?? lot.region, ORIGIN_LABELS[lot.origin], SOURCE_LABELS[lot.source]]
      .filter(Boolean)
      .join(". "),
    openGraph: lot.images[0] ? { images: [lot.images[0]] } : undefined,
  };
}

export default async function LotPage({ params }: PageProps<"/lots/[id]">) {
  const lot = getLot((await params).id);
  if (!lot) notFound();

  const specs: [string, React.ReactNode][] = (
    [
      ["Тип", CATEGORY_LABELS[lot.category]],
      ["Регион", lot.region],
      ["Город", lot.city],
      ["Площадь", lot.area_m2 ? `${formatNumber(lot.area_m2)} м²` : null],
      ["Участок", lot.land_area_ha ? `${formatNumber(lot.land_area_ha, 4)} га` : null],
      ["Комнат", lot.rooms],
      ["Этаж", lot.floor ? (lot.floors_total ? `${lot.floor} из ${lot.floors_total}` : lot.floor) : null],
      ["Этажность", !lot.floor && lot.floors_total ? lot.floors_total : null],
      ["Год постройки", lot.year_built],
      ["Цена за м²", lot.price_per_m2 ? `${Math.round(lot.price_per_m2).toLocaleString("ru-RU")} ₸` : null],
      ["Задаток", lot.deposit ? formatPrice(lot.deposit) : null],
      ["Приём заявок до", lot.applications_deadline ? formatDate(lot.applications_deadline, true) : null],
      ["Начало торгов", lot.auction_start ? formatDate(lot.auction_start, true) : null],
      ["Окончание торгов", lot.auction_end ? formatDate(lot.auction_end, true) : null],
      ["Опубликовано", lot.published_at ? formatDate(lot.published_at) : null],
      ["На torgi.kz с", formatDate(lot.first_seen_at)],
    ] as [string, React.ReactNode][]
  ).filter(([, v]) => v !== null && v !== undefined && v !== "");

  const isAuction = lot.sale_type === "auction" || lot.sale_type === "auction_down";

  return (
    <div className="mx-auto max-w-7xl px-4 py-8">
      <Link href="/lots/" className="text-sm text-muted hover:text-brand-ink">← Каталог</Link>

      {lot.status !== "active" && (
        <div className="mt-4 rounded-lg border border-accent/40 bg-accent/15 p-3 text-sm text-accent-ink">
          Объект снят с продажи у источника {formatDate(lot.last_seen_at)}.
        </div>
      )}

      <div className="mt-4 flex flex-wrap gap-2">
        {lot.sale_type && <Badge tone={isAuction ? "success" : "neutral"}>{SALE_TYPE_LABELS[lot.sale_type]}</Badge>}
        <Badge tone="brand">{ORIGIN_LABELS[lot.origin]}</Badge>
        <Badge>{SOURCE_LABELS[lot.source] ?? lot.source}</Badge>
      </div>
      <h1 className="mt-3 text-2xl font-bold md:text-3xl">{lot.headline}</h1>

      <div className="mt-6 grid gap-8 lg:grid-cols-[1fr_360px]">
        <div className="space-y-6">
          {lot.images.length > 0 ? (
            <div className="grid grid-cols-2 gap-2 md:grid-cols-3">
              {lot.images.slice(0, 9).map((src, i) => (
                <a key={src} href={src} target="_blank" rel="noopener noreferrer"
                   className={i === 0 ? "col-span-2 row-span-2 md:col-span-2" : ""}>
                  {/* eslint-disable-next-line @next/next/no-img-element -- фото с внешних доменов источников */}
                  <img src={src} alt={`${lot.headline}, фото ${i + 1}`} className="aspect-[4/3] h-full w-full rounded-lg object-cover" />
                </a>
              ))}
            </div>
          ) : (
            <div className="flex aspect-[16/7] items-center justify-center rounded-xl bg-surface text-muted">Нет фото</div>
          )}

          <section className="rounded-xl border border-border bg-surface p-5">
            <h2 className="mb-3 text-lg font-semibold">Характеристики</h2>
            <dl className="grid gap-x-6 gap-y-2 text-sm sm:grid-cols-2">
              {specs.map(([k, v]) => (
                <div key={k} className="flex justify-between gap-4 border-b border-border/60 py-1.5">
                  <dt className="text-muted">{k}</dt>
                  <dd className="text-right font-medium">{v}</dd>
                </div>
              ))}
            </dl>
          </section>

          <LotDetails lotId={lot.id} details={lot} isAuction={isAuction} />
        </div>

        <aside className="space-y-4">
          <div className="rounded-xl border border-border bg-surface p-5">
            <div className="text-sm text-muted">{isAuction ? "Стартовая цена" : "Цена"}</div>
            <div className="mt-1 text-3xl font-bold">{formatPrice(lot.price)}</div>
            {lot.price_drop_pct ? (
              <div className="mt-1 text-sm font-medium text-accent-ink">
                Снижена на {lot.price_drop_pct}% с момента появления
              </div>
            ) : null}
            {lot.flags.length > 0 && (
              <div className="mt-2 text-xs text-accent-ink">
                В данных источника похоже на ошибку ввода — уточняйте цену и площадь у продавца.
              </div>
            )}
            <a
              href="#lot-details"
              className="mt-4 block rounded-lg bg-brand px-4 py-3 text-center font-semibold text-white hover:bg-brand-hover"
            >
              Адрес и контакты продавца
            </a>
          </div>

          <TelegramCta />

          <p className="text-xs leading-5 text-muted">
            torgi.kz собирает данные из открытых источников и не является продавцом. Перед участием в торгах
            проверьте документы, обременения и актуальность лота на площадке продавца.
          </p>
        </aside>
      </div>
    </div>
  );
}
