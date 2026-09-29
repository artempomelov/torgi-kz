"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { LotCard } from "@/components/LotCard";
import type { Lot, Meta } from "@/lib/api";
import { PAGE_SIZE, SORTS, applyFilters, parseFilters } from "@/lib/filter";
import { CATEGORY_PLURAL, ORIGIN_LABELS, plural } from "@/lib/format";

let lotsPromise: Promise<Lot[]> | null = null;
function loadLots(): Promise<Lot[]> {
  lotsPromise ??= fetch("/data/lots.json").then((r) => {
    if (!r.ok) throw new Error(`lots.json: ${r.status}`);
    return r.json();
  });
  return lotsPromise;
}

export function Catalog({ meta }: { meta: Meta }) {
  const params = useSearchParams();
  const f = useMemo(() => parseFilters(new URLSearchParams(params.toString())), [params]);
  const [lots, setLots] = useState<Lot[] | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    loadLots().then(setLots, () => setError(true));
  }, []);

  const filtered = useMemo(() => (lots ? applyFilters(lots, f) : []), [lots, f]);
  const pages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const page = Math.min(f.page, pages);
  const items = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  const pageHref = (p: number) => {
    const qs = new URLSearchParams(params.toString());
    if (p > 1) qs.set("page", String(p));
    else qs.delete("page");
    return `/lots/?${qs}`;
  };

  const title = f.category.length === 1 ? `${CATEGORY_PLURAL[f.category[0]]} на торгах` : "Каталог объектов";

  return (
    <div className="mx-auto max-w-7xl px-4 py-8">
      <h1 className="text-2xl font-bold md:text-3xl">{title}</h1>
      <p className="mt-1 text-muted">
        {lots
          ? `Найдено ${filtered.length.toLocaleString("ru-RU")} ${plural(filtered.length, ["объект", "объекта", "объектов"])}`
          : "Загружаем объекты…"}
      </p>

      {/* key: при переходе по ссылкам меню форма заново берёт значения из адреса */}
      <div className="mt-6 grid gap-6 lg:grid-cols-[280px_1fr]" key={params.toString()}>
        <form action="/lots/" className="h-fit space-y-5 rounded-xl border border-border bg-surface p-4">
          <div>
            <label className="label" htmlFor="q">Поиск</label>
            <input id="q" name="q" defaultValue={f.q} placeholder="Город, улица" className="field" />
          </div>

          <fieldset>
            <legend className="label">Тип объекта</legend>
            <div className="space-y-1">
              {meta.categories.map((c) => (
                <label key={c.id} className="flex items-center gap-2 text-sm">
                  <input type="checkbox" name="category" value={c.id} defaultChecked={f.category.includes(c.id)} />
                  <span className="flex-1">{CATEGORY_PLURAL[c.id] ?? c.title}</span>
                  <span className="text-xs text-muted">{c.count}</span>
                </label>
              ))}
            </div>
          </fieldset>

          <div>
            <label className="label" htmlFor="region">Регион</label>
            <select id="region" name="region" defaultValue={f.region} className="field">
              <option value="">Весь Казахстан</option>
              {meta.regions.filter((r) => r.count > 0).map((r) => (
                <option key={r.id} value={r.id}>{r.id} ({r.count})</option>
              ))}
            </select>
          </div>

          <div>
            <span className="label">Цена, ₸</span>
            <div className="flex gap-2">
              <input name="price_min" type="number" min={0} placeholder="от" defaultValue={f.price_min} className="field" />
              <input name="price_max" type="number" min={0} placeholder="до" defaultValue={f.price_max} className="field" />
            </div>
          </div>

          <div>
            <span className="label">Площадь, м²</span>
            <div className="flex gap-2">
              <input name="area_min" type="number" min={0} placeholder="от" defaultValue={f.area_min} className="field" />
              <input name="area_max" type="number" min={0} placeholder="до" defaultValue={f.area_max} className="field" />
            </div>
          </div>

          <fieldset>
            <legend className="label">Вид продажи</legend>
            <div className="space-y-1">
              {Object.entries(ORIGIN_LABELS).map(([id, t]) => (
                <label key={id} className="flex items-center gap-2 text-sm">
                  <input type="checkbox" name="origin" value={id} defaultChecked={f.origin.includes(id)} />
                  {t}
                </label>
              ))}
            </div>
          </fieldset>

          <fieldset>
            <legend className="label">Источник</legend>
            <div className="space-y-1">
              {meta.sources.map((s) => (
                <label key={s.id} className="flex items-center gap-2 text-sm">
                  <input type="checkbox" name="source" value={s.id} defaultChecked={f.source.includes(s.id)} />
                  <span className="flex-1">{s.title}</span>
                  <span className="text-xs text-muted">{s.count}</span>
                </label>
              ))}
            </div>
          </fieldset>

          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" name="with_auction_date" value="true" defaultChecked={f.with_auction_date} />
            Только предстоящие торги
          </label>

          <div>
            <label className="label" htmlFor="sort">Сортировка</label>
            <select id="sort" name="sort" defaultValue={f.sort} className="field">
              {SORTS.map(([value, t]) => (
                <option key={value} value={value}>{t}</option>
              ))}
            </select>
          </div>

          <div className="flex gap-2">
            <button className="flex-1 rounded-lg bg-brand px-4 py-2 text-sm font-semibold text-white hover:bg-brand-hover">
              Показать
            </button>
            <Link href="/lots/" className="rounded-lg border border-border px-4 py-2 text-sm text-muted hover:text-foreground">
              Сбросить
            </Link>
          </div>
        </form>

        <div>
          {error ? (
            <div className="rounded-xl border border-dashed border-border bg-surface p-10 text-center text-muted">
              Не удалось загрузить объекты. Обновите страницу.
            </div>
          ) : !lots ? (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
              {Array.from({ length: 6 }, (_, i) => (
                <div key={i} className="h-80 animate-pulse rounded-xl bg-surface" />
              ))}
            </div>
          ) : items.length === 0 ? (
            <div className="rounded-xl border border-dashed border-border bg-surface p-10 text-center text-muted">
              По этим условиям ничего не нашлось. Попробуйте ослабить фильтры.
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
              {items.map((lot) => (
                <LotCard key={lot.id} lot={lot} />
              ))}
            </div>
          )}

          {lots && pages > 1 && (
            <nav className="mt-8 flex flex-wrap items-center justify-center gap-2 text-sm" aria-label="Страницы">
              {page > 1 && <Link href={pageHref(page - 1)} className="rounded-lg border border-border bg-surface px-3 py-1.5">← Назад</Link>}
              <span className="px-3 text-muted">Страница {page} из {pages}</span>
              {page < pages && <Link href={pageHref(page + 1)} className="rounded-lg border border-border bg-surface px-3 py-1.5">Вперёд →</Link>}
            </nav>
          )}
        </div>
      </div>

      <p className="mt-10 text-xs text-muted">
        Цены — стартовые или объявленные продавцом; итоговая цена на аукционе может отличаться.
      </p>
    </div>
  );
}
