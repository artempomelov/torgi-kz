import type { Metadata } from "next";
import Link from "next/link";

import { LotCard } from "@/components/LotCard";
import { getLots, getMeta, toQuery, type SearchParams } from "@/lib/api";
import { CATEGORY_PLURAL, ORIGIN_LABELS, SALE_TYPE_LABELS, plural } from "@/lib/format";

const SORTS = [
  ["new", "Сначала новые"],
  ["price_asc", "Сначала дешёвые"],
  ["price_desc", "Сначала дорогие"],
  ["price_m2_asc", "Дешевле за м²"],
  ["deadline", "По дате торгов"],
] as const;

function first(value: string | string[] | undefined): string {
  return (Array.isArray(value) ? value[0] : value) ?? "";
}

function all(value: string | string[] | undefined): string[] {
  return Array.isArray(value) ? value : value ? [value] : [];
}

export async function generateMetadata({ searchParams }: PageProps<"/lots">): Promise<Metadata> {
  const params = await searchParams;
  const category = first(params.category);
  const title = category && CATEGORY_PLURAL[category] ? `${CATEGORY_PLURAL[category]} на торгах` : "Каталог объектов";
  return { title, alternates: { canonical: category ? `/lots?category=${category}` : "/lots" } };
}

export default async function LotsPage({ searchParams }: PageProps<"/lots">) {
  const params: SearchParams = await searchParams;
  const [meta, data] = await Promise.all([getMeta(), getLots(params)]);
  const page = Number(first(params.page)) || 1;
  const pages = Math.max(1, Math.ceil(data.total / data.page_size));
  const selectedCategories = all(params.category);
  const selectedSources = all(params.source);
  const selectedOrigins = all(params.origin);

  const pageHref = (p: number) => `/lots?${toQuery(params, { page: p > 1 ? String(p) : null })}`;

  return (
    <div className="mx-auto max-w-7xl px-4 py-8">
      <h1 className="text-2xl font-bold md:text-3xl">
        {selectedCategories.length === 1 ? `${CATEGORY_PLURAL[selectedCategories[0]]} на торгах` : "Каталог объектов"}
      </h1>
      <p className="mt-1 text-muted">
        Найдено {data.total.toLocaleString("ru-RU")} {plural(data.total, ["объект", "объекта", "объектов"])}
      </p>

      <div className="mt-6 grid gap-6 lg:grid-cols-[280px_1fr]">
        <form action="/lots" className="h-fit space-y-5 rounded-xl border border-border bg-surface p-4">
          <div>
            <label className="label" htmlFor="q">Поиск</label>
            <input id="q" name="q" defaultValue={first(params.q)} placeholder="Адрес, кадастр" className="field" />
          </div>

          <fieldset>
            <legend className="label">Тип объекта</legend>
            <div className="space-y-1">
              {meta.categories.map((c) => (
                <label key={c.id} className="flex items-center gap-2 text-sm">
                  <input type="checkbox" name="category" value={c.id} defaultChecked={selectedCategories.includes(c.id)} />
                  <span className="flex-1">{CATEGORY_PLURAL[c.id] ?? c.title}</span>
                  <span className="text-xs text-muted">{c.count}</span>
                </label>
              ))}
            </div>
          </fieldset>

          <div>
            <label className="label" htmlFor="region">Регион</label>
            <select id="region" name="region" defaultValue={first(params.region)} className="field">
              <option value="">Весь Казахстан</option>
              {meta.regions.filter((r) => r.count > 0).map((r) => (
                <option key={r.id} value={r.id}>{r.id} ({r.count})</option>
              ))}
            </select>
          </div>

          <div>
            <span className="label">Цена, ₸</span>
            <div className="flex gap-2">
              <input name="price_min" type="number" min={0} placeholder="от" defaultValue={first(params.price_min)} className="field" />
              <input name="price_max" type="number" min={0} placeholder="до" defaultValue={first(params.price_max)} className="field" />
            </div>
          </div>

          <div>
            <span className="label">Площадь, м²</span>
            <div className="flex gap-2">
              <input name="area_min" type="number" min={0} placeholder="от" defaultValue={first(params.area_min)} className="field" />
              <input name="area_max" type="number" min={0} placeholder="до" defaultValue={first(params.area_max)} className="field" />
            </div>
          </div>

          <fieldset>
            <legend className="label">Вид продажи</legend>
            <div className="space-y-1">
              {Object.entries(ORIGIN_LABELS).map(([id, title]) => (
                <label key={id} className="flex items-center gap-2 text-sm">
                  <input type="checkbox" name="origin" value={id} defaultChecked={selectedOrigins.includes(id)} />
                  {title}
                </label>
              ))}
            </div>
          </fieldset>

          <fieldset>
            <legend className="label">Источник</legend>
            <div className="space-y-1">
              {meta.sources.map((s) => (
                <label key={s.id} className="flex items-center gap-2 text-sm">
                  <input type="checkbox" name="source" value={s.id} defaultChecked={selectedSources.includes(s.id)} />
                  <span className="flex-1">{s.title}</span>
                  <span className="text-xs text-muted">{s.count}</span>
                </label>
              ))}
            </div>
          </fieldset>

          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" name="with_auction_date" value="true" defaultChecked={first(params.with_auction_date) === "true"} />
            Только с датой торгов
          </label>

          <div>
            <label className="label" htmlFor="sort">Сортировка</label>
            <select id="sort" name="sort" defaultValue={first(params.sort) || "new"} className="field">
              {SORTS.map(([value, title]) => (
                <option key={value} value={value}>{title}</option>
              ))}
            </select>
          </div>

          <div className="flex gap-2">
            <button className="flex-1 rounded-lg bg-brand px-4 py-2 text-sm font-semibold text-white hover:bg-brand-hover">
              Показать
            </button>
            <Link href="/lots" className="rounded-lg border border-border px-4 py-2 text-sm text-muted hover:text-foreground">
              Сбросить
            </Link>
          </div>
        </form>

        <div>
          {data.items.length === 0 ? (
            <div className="rounded-xl border border-dashed border-border bg-surface p-10 text-center text-muted">
              По этим условиям ничего не нашлось. Попробуйте ослабить фильтры.
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
              {data.items.map((lot) => (
                <LotCard key={lot.id} lot={lot} />
              ))}
            </div>
          )}

          {pages > 1 && (
            <nav className="mt-8 flex flex-wrap items-center justify-center gap-2 text-sm" aria-label="Страницы">
              {page > 1 && <Link href={pageHref(page - 1)} className="rounded-lg border border-border bg-surface px-3 py-1.5">← Назад</Link>}
              <span className="px-3 text-muted">Страница {page} из {pages}</span>
              {page < pages && <Link href={pageHref(page + 1)} className="rounded-lg border border-border bg-surface px-3 py-1.5">Вперёд →</Link>}
            </nav>
          )}
        </div>
      </div>

      <p className="mt-10 text-xs text-muted">
        Типы продажи: {Object.values(SALE_TYPE_LABELS).join(", ").toLowerCase()}. Цены — стартовые или объявленные
        продавцом; итоговая цена на аукционе может отличаться.
      </p>
    </div>
  );
}
