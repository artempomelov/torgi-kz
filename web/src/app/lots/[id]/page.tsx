import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { FavoriteButton } from "@/components/FavoriteButton";
import { HowToBuy } from "@/components/HowToBuy";
import { Badge, LotCard } from "@/components/LotCard";
import { LotDetails } from "@/components/LotDetails";
import { LotImage } from "@/components/LotImage";
import { DescendingAuction, PriceAlerts } from "@/components/LotPricing";
import { LotStatsBadge } from "@/components/LotStatsBadge";
import { ShareButtons } from "@/components/ShareButtons";
import { TelegramCta } from "@/components/TelegramCta";
import { getAllLotsFull, getLot, getLots } from "@/lib/data";
import { describeLot } from "@/lib/describe";
import { compareToMarket, isStale, similarLots } from "@/lib/insights";
import { checkLink, consultLink } from "@/lib/subscribe";
import {
  CATEGORY_LABELS,
  ORIGIN_LABELS,
  SALE_TYPE_LABELS,
  SOURCE_LABELS,
  formatDate,
  formatNumber,
  formatPrice,
  lotSubtitle,
  priceDrop,
  unitPrice,
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
    // своя картинка превью, если у источника нет фото (для WhatsApp, Telegram и соцсетей)
    openGraph: { images: [lot.images[0] ?? `/og/${lot.category}.png`] },
    alternates: { canonical: `/lots/${lot.duplicate_of ?? lot.id}/` },
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
      [`Цена за ${unitPrice(lot)?.unit ?? "м²"}`, unitPrice(lot) ? `${Math.round(unitPrice(lot)!.value).toLocaleString("ru-RU")} ₸` : null],
      ["Задаток", lot.deposit ? formatPrice(lot.deposit) : null],
      ["Приём заявок до", lot.applications_deadline ? formatDate(lot.applications_deadline, true) : null],
      ["Начало торгов", lot.auction_start ? formatDate(lot.auction_start, true) : null],
      ["Окончание торгов", lot.auction_end ? formatDate(lot.auction_end, true) : null],
      ["Опубликовано", lot.published_at ? formatDate(lot.published_at) : null],
      ["На torgi.kz с", formatDate(lot.first_seen_at)],
    ] as [string, React.ReactNode][]
  ).filter(([, v]) => v !== null && v !== undefined && v !== "");

  const isAuction = lot.sale_type === "auction" || lot.sale_type === "auction_down";
  const lots = getLots();
  const similar = similarLots(lot, lots);
  const market = compareToMarket(lot, lots);
  const stale = lot.status === "active" && !isAuction && isStale(lot.listed_at);
  const pageUrl = `https://torgi.kz/lots/${lot.id}/`;

  return (
    <div className="mx-auto max-w-7xl px-4 py-8">
      <Link href="/lots/" className="text-sm text-muted hover:text-brand-ink">← Каталог</Link>

      {lot.status !== "active" && (
        <div className="mt-4 rounded-lg border border-accent/40 bg-accent/15 p-3 text-sm text-accent-ink">
          Объект снят с продажи у источника {formatDate(lot.last_seen_at)}.
        </div>
      )}

      {lot.duplicate_of && (
        <div className="mt-4 rounded-lg border border-brand-ink/30 bg-brand-ink/5 p-3 text-sm">
          Этот же объект (совпадает кадастровый номер) продаётся и у другого источника —{" "}
          <Link href={`/lots/${lot.duplicate_of}/`} className="font-medium text-brand-ink">смотреть основное объявление</Link>.
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
                  <LotImage src={src} category={lot.category} alt={`${lot.headline}, фото ${i + 1}`} eager={i === 0}
                            width={i === 0 ? 1200 : 480}
                            className="aspect-[4/3] h-full w-full rounded-lg object-cover" />
                </a>
              ))}
            </div>
          ) : (
            <LotImage src={null} category={lot.category} alt={lot.headline}
                      className="aspect-[4/3] w-full max-w-2xl rounded-xl border border-border object-cover" />
          )}

          <section className="rounded-xl border border-border bg-surface p-5">
            <h2 className="mb-2 text-lg font-semibold">Об объекте</h2>
            <div className="space-y-1.5 text-sm leading-6">
              {describeLot(lot, market).map((p) => <p key={p}>{p}</p>)}
            </div>
            <LotStatsBadge id={lot.id} record compact={false} className="mt-3" />
          </section>

          <DescendingAuction lot={lot} />

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

          <HowToBuy origin={lot.origin} saleType={lot.sale_type} source={lot.source} />
        </div>

        <aside className="space-y-4">
          <div className="rounded-xl border border-border bg-surface p-5">
            <div className="text-sm text-muted">{isAuction ? "Стартовая цена" : "Цена"}</div>
            <div className="mt-1 text-3xl font-bold">{formatPrice(lot.price)}</div>
            {lot.price_drop_pct ? (
              <div className="mt-2 rounded-lg bg-accent/10 p-3 text-sm text-accent-ink">
                Выгода <b>{formatPrice(priceDrop(lot.price, lot.price_drop_pct))}</b> — цена снижена на {lot.price_drop_pct}%
                с момента публикации
              </div>
            ) : null}
            {market && (
              <div className={`mt-3 rounded-lg p-3 text-sm ${market.diffPct <= -10 ? "bg-success/10 text-success" : "bg-background text-muted"}`}>
                {market.diffPct <= -3
                  ? <>Цена за м² на <b>{-market.diffPct}%</b> ниже</>
                  : market.diffPct >= 3
                    ? <>Цена за м² на <b>{market.diffPct}%</b> выше</>
                    : <>Цена за м² на уровне</>}{" "}
                медианы по {market.sample} похожим объектам на торгах и в залогах ({market.where}):{" "}
                {Math.round(market.median).toLocaleString("ru-RU")} ₸/м².
              </div>
            )}
            {stale && (
              <div className="mt-3 rounded-lg bg-surface-2 p-3 text-sm text-foreground">
                В продаже с {formatDate(lot.listed_at)} — объект давно не продаётся, уместно торговаться.
              </div>
            )}
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
            <div className="mt-2 space-y-2">
              <FavoriteButton id={lot.id} variant="button" />
            </div>
          </div>

          <div className="space-y-2 rounded-xl border border-border bg-surface p-4">
            <div className="text-sm font-semibold">Нужна помощь с покупкой?</div>
            <a href={checkLink(lot.id)} target="_blank" rel="noopener noreferrer"
               className="block rounded-lg bg-brand-ink px-4 py-2.5 text-center text-sm font-semibold text-white hover:opacity-90">
              Бесплатная проверка лота
            </a>
            <p className="text-xs text-muted">Проверим документы, обременения и риски — ответим в Telegram.</p>
            <a href={consultLink(lot.id)} target="_blank" rel="noopener noreferrer"
               className="block rounded-lg border border-border px-4 py-2.5 text-center text-sm font-medium hover:border-brand-ink/40">
              Консультация в Telegram
            </a>
          </div>

          {lot.status === "active" && (
            <div className="rounded-xl border border-border bg-surface p-4">
              <PriceAlerts lot={lot} />
            </div>
          )}

          <div className="rounded-xl border border-border bg-surface p-4">
            <ShareButtons url={pageUrl} text={`${lot.headline} — ${formatPrice(lot.price)}`} />
          </div>

          <TelegramCta />

          <p className="text-xs leading-5 text-muted">
            torgi.kz собирает данные из открытых источников и не является продавцом. Перед участием в торгах
            проверьте документы, обременения и актуальность лота на площадке продавца.
          </p>
        </aside>
      </div>

      {similar.length > 0 && (
        <section className="mt-12">
          <h2 className="mb-4 text-2xl font-bold">Похожие объекты</h2>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {similar.map((x) => <LotCard key={x.id} lot={x} />)}
          </div>
        </section>
      )}
    </div>
  );
}
