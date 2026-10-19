import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { CarCard } from "@/components/CarCatalog";
import { Badge } from "@/components/LotCard";
import { LotImage } from "@/components/LotImage";
import { ShareButtons } from "@/components/ShareButtons";
import { TelegramCta } from "@/components/TelegramCta";
import { VEHICLE_TYPES, carName, type Car } from "@/lib/cars";
import { getCar, getCars } from "@/lib/data";
import { ORIGIN_LABELS, SALE_TYPE_LABELS, SOURCE_LABELS, formatDate, formatPrice, formatPriceShort } from "@/lib/format";
import { consultLink } from "@/lib/subscribe";

// Статическая сборка: страница на каждую машину из выгрузки
export const dynamicParams = false;

export function generateStaticParams() {
  const cars = getCars();
  // пустой список ломает статическую сборку — тогда одна страница-заглушка (отдаёт 404)
  return cars.length ? cars.map((c) => ({ id: String(c.id) })) : [{ id: "0" }];
}

const place = (c: Car) => [c.city, c.region !== c.city ? c.region : null].filter(Boolean).join(", ");

export async function generateMetadata({ params }: PageProps<"/avto/[id]">): Promise<Metadata> {
  const car = getCar((await params).id);
  if (!car) return { title: "Автомобиль не найден" };
  return {
    title: `${carName(car)} — ${formatPrice(car.price)}${place(car) ? `, ${place(car)}` : ""}`,
    description: [VEHICLE_TYPES[car.vehicle_type], ORIGIN_LABELS[car.origin], car.sale_type && SALE_TYPE_LABELS[car.sale_type],
                  car.auction_date && `торги ${formatDate(car.auction_date, true)}`, SOURCE_LABELS[car.source]]
      .filter(Boolean).join(". "),
    openGraph: car.images[0] ? { images: [car.images[0]] } : undefined,
    alternates: { canonical: `/avto/${car.id}/` },
  };
}

function similarCars(car: Car, cars: Car[]): Car[] {
  const others = cars.filter((c) => c.id !== car.id && c.vehicle_type === car.vehicle_type);
  const same = others.filter((c) => c.brand && c.brand === car.brand);
  const near = others.filter((c) => c.brand !== car.brand && c.price && car.price && Math.abs(c.price / car.price - 1) < 0.3);
  return [...same, ...near].slice(0, 3);
}

export default async function CarPage({ params }: PageProps<"/avto/[id]">) {
  const car = getCar((await params).id);
  if (!car) notFound();
  const isAuction = car.sale_type === "auction" || car.sale_type === "auction_down";
  const name = carName(car);
  const specs: [string, string | number | null | undefined][] = [
    ["Тип", VEHICLE_TYPES[car.vehicle_type]],
    ["Марка", car.brand],
    ["Модель", car.model],
    ["Год выпуска", car.year],
    ["Пробег", car.mileage_km != null ? `${car.mileage_km.toLocaleString("ru-RU")} км` : null],
    ["Двигатель", car.engine],
    ["Коробка передач", car.transmission],
    ["Привод", car.drive],
    ["Кузов", car.body],
    ["Цвет", car.color],
    ["Местоположение", place(car)],
    ["Вид продажи", ORIGIN_LABELS[car.origin]],
    ["Способ продажи", car.sale_type ? SALE_TYPE_LABELS[car.sale_type] : null],
    ["Торги", car.auction_date ? formatDate(car.auction_date, true) : null],
    ["Приём заявок до", car.applications_deadline ? formatDate(car.applications_deadline, true) : null],
    ["Задаток", car.deposit ? formatPrice(car.deposit) : null],
    ["Источник", SOURCE_LABELS[car.source] ?? car.source],
  ];

  return (
    <div className="mx-auto max-w-7xl px-4 py-8">
      <Link href="/avto/" className="text-sm text-muted hover:text-brand-ink">← Все автомобили</Link>

      <div className="mt-4 flex flex-wrap gap-2">
        {car.sale_type && <Badge tone={isAuction ? "success" : "neutral"}>{SALE_TYPE_LABELS[car.sale_type]}</Badge>}
        <Badge tone="brand">{ORIGIN_LABELS[car.origin] ?? car.origin}</Badge>
        <Badge>{SOURCE_LABELS[car.source] ?? car.source}</Badge>
      </div>
      <h1 className="mt-3 text-2xl font-bold md:text-3xl">{name}</h1>
      {place(car) && <p className="mt-1 text-muted">📍 {place(car)}</p>}

      <div className="mt-6 grid gap-8 lg:grid-cols-[1fr_360px]">
        <div className="space-y-6">
          {car.images.length > 0 ? (
            <div className="grid grid-cols-2 gap-2 md:grid-cols-3">
              {car.images.slice(0, 12).map((src, i) => (
                <a key={src} href={src} target="_blank" rel="noopener noreferrer"
                   className={i === 0 ? "col-span-2 row-span-2 md:col-span-2" : ""}>
                  <LotImage src={src} category="other" alt={`${name}, фото ${i + 1}`} eager={i === 0}
                            width={i === 0 ? 1200 : 480} className="aspect-[4/3] h-full w-full rounded-lg object-cover" />
                </a>
              ))}
            </div>
          ) : (
            <LotImage src={null} category="other" alt={name}
                      className="aspect-[4/3] w-full max-w-2xl rounded-xl border border-border object-cover" />
          )}

          <section className="rounded-xl border border-border bg-surface p-5">
            <h2 className="mb-3 text-lg font-semibold">Характеристики</h2>
            <dl className="grid gap-x-6 gap-y-2 text-sm sm:grid-cols-2">
              {specs.filter(([, v]) => v != null && v !== "").map(([k, v]) => (
                <div key={k} className="flex justify-between gap-4 border-b border-border/60 py-1.5">
                  <dt className="text-muted">{k}</dt>
                  <dd className="text-right font-medium">{v}</dd>
                </div>
              ))}
            </dl>
          </section>

          {car.description && (
            <section className="rounded-xl border border-border bg-surface p-5">
              <h2 className="mb-2 text-lg font-semibold">Описание продавца</h2>
              <p className="whitespace-pre-line text-sm leading-6">{car.description}</p>
            </section>
          )}
        </div>

        <aside className="space-y-4">
          <div className="rounded-xl border border-border bg-surface p-5">
            <div className="text-sm text-muted">{isAuction ? "Стартовая цена" : "Цена"}</div>
            <div className="mt-1 text-3xl font-bold">{formatPrice(car.price)}</div>
            {car.min_price && car.price && car.min_price < car.price ? (
              <div className="mt-2 rounded-lg bg-success/10 p-3 text-sm text-success">
                Аукцион на понижение: цена может опуститься до <b>{formatPriceShort(car.min_price)}</b>
              </div>
            ) : null}
            {car.price_drop_pct ? (
              <div className="mt-2 rounded-lg bg-accent/10 p-3 text-sm text-accent-ink">
                Цена снижена на {car.price_drop_pct}% с момента публикации
              </div>
            ) : null}
            {car.note && (
              <div className="mt-2 rounded-lg bg-accent/15 p-3 text-sm text-accent-ink">
                ⚠ {car.note[0].toUpperCase() + car.note.slice(1)}
              </div>
            )}
            <a href={car.url} target="_blank" rel="noopener noreferrer" data-goal="source_click"
               className="mt-4 block rounded-lg bg-brand px-4 py-3 text-center font-semibold text-white hover:bg-brand-hover">
              Лот на сайте продавца
            </a>
          </div>

          <div className="space-y-2 rounded-xl border border-border bg-surface p-4">
            <div className="text-sm font-semibold">Нужна помощь с покупкой?</div>
            <a href={consultLink(car.id)} target="_blank" rel="noopener noreferrer"
               className="block rounded-lg bg-brand-ink px-4 py-2.5 text-center text-sm font-semibold text-white hover:opacity-90">
              Бесплатная консультация по лоту
            </a>
            <p className="text-xs text-muted">Ответим на вопросы и подскажем, что проверить перед покупкой, — в Telegram.</p>
          </div>

          <div className="rounded-xl border border-border bg-surface p-4">
            <ShareButtons url={`https://torgi.kz/avto/${car.id}/`} text={`${name} — ${formatPrice(car.price)}`} />
          </div>

          <TelegramCta />

          <p className="text-xs leading-5 text-muted">
            torgi.kz собирает данные из открытых источников и не является продавцом. Перед покупкой проверьте
            автомобиль, документы и обременения на сайте продавца.
          </p>
        </aside>
      </div>

      {similarCars(car, getCars()).length > 0 && (
        <section className="mt-12">
          <h2 className="mb-4 text-xl font-semibold">Похожие автомобили</h2>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {similarCars(car, getCars()).map((c) => <CarCard key={c.id} car={c} />)}
          </div>
        </section>
      )}
    </div>
  );
}
