"use client";

// Раздел «Автомобили с торгов»: фильтры по марке, модели, году, городу и цене, карточки с фото.
// Устроен как каталог недвижимости: фильтры — в адресе страницы, данные отфильтровываются в браузере.
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useMemo, useState } from "react";

import { Badge, marketTone } from "@/components/LotCard";
import { TelegramCta } from "@/components/TelegramCta";
import { LotImage } from "@/components/LotImage";
import {
  CAR_PAGE_SIZE, CAR_SORTS, VEHICLE_TYPES, applyCarFilters, carName, carOptions, carSpecs, parseCarFilters, type Car,
} from "@/lib/cars";
import { ORIGIN_LABELS, SALE_TYPE_LABELS, SOURCE_LABELS, formatDate, formatPrice, formatPriceShort, plural } from "@/lib/format";

export function CarCard({ car }: { car: Car }) {
  const isAuction = car.sale_type === "auction" || car.sale_type === "auction_down";
  const specs = carSpecs(car);
  const place = [car.city, car.region !== car.city ? car.region : null].filter(Boolean).join(", ");
  return (
    <Link
      href={`/avto/${car.id}/`}
      className="group flex flex-col overflow-hidden rounded-xl border border-border bg-surface transition hover:border-brand-ink/50 hover:shadow-card"
    >
      <div className="relative aspect-[4/3] overflow-hidden bg-background">
        <LotImage src={car.images[0]} category="other" alt={carName(car)} className="h-full w-full object-cover" />
        <div className="absolute left-2 top-2 flex flex-wrap gap-1">
          <span className="rounded-md bg-surface/95 px-2 py-0.5 text-xs font-medium text-foreground">
            {VEHICLE_TYPES[car.vehicle_type] ?? car.vehicle_type}
          </span>
          {car.market && (
            <span className={`rounded-md px-2 py-0.5 text-xs font-semibold ${marketTone(car.market)}`}>
              −{car.market.pct}% к рынку
            </span>
          )}
          {car.price_drop_pct ? (
            <span className="rounded-md bg-accent px-2 py-0.5 text-xs font-semibold text-white">−{car.price_drop_pct}%</span>
          ) : null}
          {car.images.length > 1 && (
            <span className="rounded-md bg-foreground/70 px-2 py-0.5 text-xs font-medium text-white">📷 {car.images.length}</span>
          )}
        </div>
      </div>

      <div className="flex flex-1 flex-col gap-2 p-4">
        <div className="text-lg font-semibold" title={formatPrice(car.price)}>{formatPriceShort(car.price)}</div>
        {car.min_price && car.price && car.min_price < car.price ? (
          <div className="-mt-1 text-xs font-medium text-success">
            Может опуститься до {formatPriceShort(car.min_price)} (−{Math.round((1 - car.min_price / car.price) * 100)}%)
          </div>
        ) : null}
        <div className="font-medium text-foreground">{carName(car)}</div>
        {specs && <div className="text-sm text-muted">{specs}</div>}
        {place && <div className="text-sm text-muted group-hover:text-foreground">📍 {place}</div>}

        <div className="mt-auto flex flex-wrap gap-1 pt-2">
          {isAuction ? (
            <Badge tone="success">{SALE_TYPE_LABELS[car.sale_type!]}</Badge>
          ) : car.sale_type ? (
            <Badge>{SALE_TYPE_LABELS[car.sale_type] ?? car.sale_type}</Badge>
          ) : null}
          <Badge tone="brand">{ORIGIN_LABELS[car.origin] ?? car.origin}</Badge>
          <Badge>{SOURCE_LABELS[car.source] ?? car.source}</Badge>
        </div>
        {car.note && <div className="text-xs font-medium text-accent-ink">⚠ {car.note[0].toUpperCase() + car.note.slice(1)}</div>}
        {car.auction_date && <div className="text-xs text-muted">Торги: {formatDate(car.auction_date, true)}</div>}
      </div>
    </Link>
  );
}

export function CarCatalog({ cars }: { cars: Car[] }) {
  const params = useSearchParams();
  const f = useMemo(() => parseCarFilters(new URLSearchParams(params.toString())), [params]);
  const [filtersOpen, setFiltersOpen] = useState(false);
  // марка выбирается в форме до «Показать» — список моделей подстраивается сразу
  const [brand, setBrand] = useState(f.brand);

  const filtered = useMemo(() => applyCarFilters([...cars], f), [cars, f]);
  const opts = useMemo(() => carOptions(cars, brand), [cars, brand]);
  const pages = Math.max(1, Math.ceil(filtered.length / CAR_PAGE_SIZE));
  const page = Math.min(f.page, pages);
  const pageItems = filtered.slice((page - 1) * CAR_PAGE_SIZE, page * CAR_PAGE_SIZE);
  const years = opts.years.length ? [Math.min(...opts.years), Math.max(...opts.years)] : null;

  const hrefWith = (changes: Record<string, string | null>) => {
    const qs = new URLSearchParams(params.toString());
    for (const [k, v] of Object.entries(changes)) {
      if (v === null) qs.delete(k);
      else qs.set(k, v);
    }
    const s = qs.toString();
    return s ? `/avto/?${s}` : "/avto/";
  };

  const title = f.brand ? `${[f.brand, f.model].filter(Boolean).join(" ")} с торгов` : "Автомобили с торгов";

  return (
    <div className="mx-auto max-w-7xl px-4 py-8">
      <div>
        <h1 className="text-2xl font-bold md:text-3xl">{title}</h1>
        <p className="mt-1 text-muted">
          Найдено {filtered.length.toLocaleString("ru-RU")} {plural(filtered.length, ["автомобиль", "автомобиля", "автомобилей"])}
          {" "}— залоги банков, арестованное имущество и госимущество
        </p>
      </div>

      {/* быстрые ссылки на популярные марки */}
      <div className="mt-4 flex flex-wrap gap-2">
        {opts.brands.slice(0, 12).map(([b, n]) => (
          <Link key={b} href={`/avto/?brand=${encodeURIComponent(b)}`}
                className={`rounded-full border px-3 py-1 text-sm ${f.brand === b
                  ? "border-brand bg-brand text-white"
                  : "border-border bg-surface hover:border-brand-ink hover:text-brand-ink"}`}>
            {b} <span className={f.brand === b ? "text-white/80" : "text-muted"}>{n}</span>
          </Link>
        ))}
      </div>

      <button type="button" onClick={() => setFiltersOpen((v) => !v)}
              className="mt-4 w-full rounded-lg border border-border bg-surface px-4 py-2.5 text-sm font-medium lg:hidden">
        {filtersOpen ? "Скрыть фильтры" : "Фильтры и сортировка"}
      </button>

      <div className="mt-4 grid gap-6 lg:mt-6 lg:grid-cols-[280px_1fr]" key={params.toString()}>
        <form action="/avto/" className={`h-fit space-y-5 rounded-xl border border-border bg-surface p-4 ${filtersOpen ? "" : "hidden lg:block"}`}>
          <div>
            <label className="label" htmlFor="brand">Марка</label>
            <select id="brand" name="brand" defaultValue={f.brand} className="field" onChange={(e) => setBrand(e.target.value)}>
              <option value="">Все марки</option>
              {opts.brands.map(([b, n]) => <option key={b} value={b}>{b} ({n})</option>)}
            </select>
          </div>

          <div>
            <label className="label" htmlFor="model">Модель</label>
            <select id="model" name="model" defaultValue={f.model} className="field" disabled={!brand}>
              <option value="">{brand ? "Все модели" : "Сначала выберите марку"}</option>
              {opts.models.map(([m, n]) => <option key={m} value={m}>{m} ({n})</option>)}
            </select>
          </div>

          <div>
            <span className="label">Год выпуска</span>
            <div className="flex gap-2">
              <input name="year_min" type="number" placeholder={years ? `от ${years[0]}` : "от"} defaultValue={f.year_min} className="field" />
              <input name="year_max" type="number" placeholder={years ? `до ${years[1]}` : "до"} defaultValue={f.year_max} className="field" />
            </div>
          </div>

          <div>
            <label className="label" htmlFor="city">Местоположение</label>
            <select id="city" name="city" defaultValue={f.city} className="field">
              <option value="">Весь Казахстан</option>
              {opts.cities.map(([c, n]) => <option key={c} value={c}>{c} ({n})</option>)}
            </select>
          </div>

          <div>
            <span className="label">Цена, ₸</span>
            <div className="flex gap-2">
              <input name="price_min" type="number" min={0} placeholder="от" defaultValue={f.price_min} className="field" />
              <input name="price_max" type="number" min={0} placeholder="до" defaultValue={f.price_max} className="field" />
            </div>
          </div>

          <fieldset>
            <legend className="label">Тип транспорта</legend>
            <div className="space-y-1">
              {Object.entries(VEHICLE_TYPES).map(([id, t]) => {
                const n = cars.filter((c) => c.vehicle_type === id).length;
                return n ? (
                  <label key={id} className="flex items-center gap-2 text-sm">
                    <input type="checkbox" name="type" value={id} defaultChecked={f.type.includes(id)} />
                    <span className="flex-1">{t}</span>
                    <span className="text-xs text-muted">{n}</span>
                  </label>
                ) : null;
              })}
            </div>
          </fieldset>

          <div>
            <label className="label" htmlFor="transmission">Коробка передач</label>
            <select id="transmission" name="transmission" defaultValue={f.transmission} className="field">
              <option value="">Любая</option>
              <option value="АКПП">Автомат</option>
              <option value="МКПП">Механика</option>
              <option value="робот">Робот</option>
              <option value="вариатор">Вариатор</option>
            </select>
          </div>

          <fieldset>
            <legend className="label">Вид продажи</legend>
            <div className="space-y-1">
              {Object.entries(ORIGIN_LABELS).filter(([id]) => cars.some((c) => c.origin === id)).map(([id, t]) => (
                <label key={id} className="flex items-center gap-2 text-sm">
                  <input type="checkbox" name="origin" value={id} defaultChecked={f.origin.includes(id)} />
                  {t}
                </label>
              ))}
            </div>
          </fieldset>

          <div>
            <label className="label" htmlFor="sort">Сортировка</label>
            <select id="sort" name="sort" defaultValue={f.sort} className="field">
              {CAR_SORTS.map(([value, t]) => <option key={value} value={value}>{t}</option>)}
            </select>
          </div>

          <div className="flex gap-2">
            <button className="flex-1 rounded-lg bg-brand px-4 py-2 text-sm font-semibold text-white hover:bg-brand-hover">Показать</button>
            <Link href="/avto/" className="rounded-lg border border-border px-4 py-2 text-sm text-muted hover:text-foreground">Сбросить</Link>
          </div>
        </form>

        <div>
          {pageItems.length === 0 ? (
            <div className="rounded-xl border border-dashed border-border bg-surface p-10 text-center text-muted">
              По этим условиям ничего не нашлось. Попробуйте ослабить фильтры.
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
              {pageItems.map((car) => <CarCard key={car.id} car={car} />)}
            </div>
          )}

          {pages > 1 && (
            <nav className="mt-8 flex flex-wrap items-center justify-center gap-2 text-sm" aria-label="Страницы">
              {page > 1 && <Link href={hrefWith({ page: page > 2 ? String(page - 1) : null })} className="rounded-lg border border-border bg-surface px-3 py-1.5">← Назад</Link>}
              <span className="px-3 text-muted">Страница {page} из {pages}</span>
              {page < pages && <Link href={hrefWith({ page: String(page + 1) })} className="rounded-lg border border-border bg-surface px-3 py-1.5">Вперёд →</Link>}
            </nav>
          )}

          <div className="mt-8">
            <TelegramCta cars compact />
          </div>
        </div>
      </div>

      <p className="mt-10 text-xs text-muted">
        Цены — стартовые или объявленные продавцом. Перед покупкой проверяйте автомобиль, документы и обременения на сайте продавца.
      </p>
    </div>
  );
}
