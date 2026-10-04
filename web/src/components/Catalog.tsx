"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { LotCard } from "@/components/LotCard";
import { LotImage } from "@/components/LotImage";
import type { Lot, Meta } from "@/lib/api";
import { loadLots } from "@/lib/catalog-data";
import { PAGE_SIZE, SORTS, applyFilters, groupParkings, parseFilters, type ParkingGroup } from "@/lib/filter";
import { CATEGORY_PLURAL, ORIGIN_LABELS, SOURCE_LABELS, formatPriceShort, plural } from "@/lib/format";
import { botLink, searchCode } from "@/lib/subscribe";

const CatalogMap = dynamic(() => import("@/components/CatalogMap").then((m) => m.CatalogMap), {
  ssr: false,
  loading: () => <div className="h-[70vh] min-h-[420px] animate-pulse rounded-xl bg-surface" />,
});

// Подсказки для поиска: города и районы из адресов, по частоте
const DISTRICT_RE = /(?:р-н|район)\s+([А-ЯЁӘІҢҒҮҰҚӨҺA-Z][\p{L}-]+)|([А-ЯЁӘІҢҒҮҰҚӨҺ][\p{L}-]+)\s+(?:р-н|район)/gu;
function suggestions(lots: Lot[]): string[] {
  const count = new Map<string, number>();
  const add = (s: string) => count.set(s, (count.get(s) ?? 0) + 1);
  for (const lot of lots) {
    if (lot.city) add(lot.city);
    for (const m of (lot.address ?? "").matchAll(DISTRICT_RE)) add(`${m[1] ?? m[2]} район`);
  }
  return [...count.entries()].filter(([, n]) => n >= 2).sort((a, b) => b[1] - a[1]).slice(0, 300).map(([s]) => s);
}

function ParkingGroupCard({ group }: { group: ParkingGroup }) {
  const prices = group.lots.map((l) => l.price).filter((p): p is number => !!p);
  const first = group.lots.find((l) => l.image) ?? group.lots[0];
  const n = group.lots.length;
  return (
    <Link
      href={`/lots/?category=parking&q=${encodeURIComponent(group.base)}`}
      className="group flex flex-col overflow-hidden rounded-xl border border-border bg-surface transition hover:border-brand-ink/50 hover:shadow-card"
    >
      <div className="relative aspect-[4/3] bg-background">
        <LotImage src={first.image} category="parking" alt={group.base} className="h-full w-full object-cover" />
        <span className="absolute left-2 top-2 rounded-md bg-surface/95 px-2 py-0.5 text-xs font-medium">
          {n} {plural(n, ["машино-место", "машино-места", "машино-мест"])}
        </span>
      </div>
      <div className="flex flex-1 flex-col gap-2 p-4">
        <div className="text-lg font-semibold">
          {prices.length ? `от ${formatPriceShort(Math.min(...prices))}` : "Цена не указана"}
        </div>
        <div className="line-clamp-2 text-sm text-muted group-hover:text-foreground">{group.base}</div>
        <div className="mt-auto pt-2 text-sm font-medium text-brand-ink">
          Смотреть все места · {SOURCE_LABELS[first.source] ?? first.source}
        </div>
      </div>
    </Link>
  );
}

export function Catalog({ meta, initial }: { meta: Meta; initial: Lot[] }) {
  const params = useSearchParams();
  const f = useMemo(() => parseFilters(new URLSearchParams(params.toString())), [params]);
  const view = params.get("view") === "map" ? "map" : "list";
  const [lots, setLots] = useState<Lot[] | null>(null);
  const [error, setError] = useState(false);
  const [filtersOpen, setFiltersOpen] = useState(false);

  useEffect(() => {
    loadLots().then(setLots, () => setError(true));
  }, []);

  const filtered = useMemo(() => (lots ? applyFilters(lots, f) : []), [lots, f]);
  // поиск по адресу открывает конкретный паркинг — там места показываем по одному
  const items = useMemo(() => (f.q ? filtered.map((lot) => ({ kind: "lot" as const, lot })) : groupParkings(filtered)), [filtered, f.q]);
  const hints = useMemo(() => (lots ? suggestions(lots) : []), [lots]);
  const pages = Math.max(1, Math.ceil(items.length / PAGE_SIZE));
  const page = Math.min(f.page, pages);
  const pageItems = items.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  // Пока каталог грузится, без фильтров сразу показываем первую страницу из HTML
  const noFilters = [...params.keys()].every((k) => k === "page" || k === "view") && f.page === 1;
  const showInitial = !lots && noFilters && view === "list";

  const hrefWith = (changes: Record<string, string | null>) => {
    const qs = new URLSearchParams(params.toString());
    for (const [k, v] of Object.entries(changes)) {
      if (v === null) qs.delete(k);
      else qs.set(k, v);
    }
    const s = qs.toString();
    return s ? `/lots/?${s}` : "/lots/";
  };
  const pageHref = (p: number) => hrefWith({ page: p > 1 ? String(p) : null });
  const code = searchCode(f);

  const title = f.category.length === 1 ? `${CATEGORY_PLURAL[f.category[0]]} на торгах` : "Каталог объектов";
  const total = lots ? filtered.length : meta.total;

  return (
    <div className="mx-auto max-w-7xl px-4 py-8">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold md:text-3xl">{title}</h1>
          <p className="mt-1 text-muted">
            {lots || showInitial
              ? `Найдено ${total.toLocaleString("ru-RU")} ${plural(total, ["объект", "объекта", "объектов"])}`
              : "Загружаем объекты…"}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {code && (
            <a href={botLink(code)} target="_blank" rel="noopener noreferrer"
               className="rounded-lg border border-brand-ink/40 bg-brand-ink/5 px-3 py-2 text-sm font-medium text-brand-ink hover:bg-brand-ink/10"
               title="Бот пришлёт новые объекты по этим фильтрам">
              🔔 Сообщать о новых в Telegram
            </a>
          )}
          <div className="flex overflow-hidden rounded-lg border border-border text-sm">
            <Link href={hrefWith({ view: null })} className={`px-3 py-2 ${view === "list" ? "bg-brand text-white" : "bg-surface"}`}>
              Список
            </Link>
            <Link href={hrefWith({ view: "map", page: null })} className={`px-3 py-2 ${view === "map" ? "bg-brand text-white" : "bg-surface"}`}>
              Карта
            </Link>
          </div>
        </div>
      </div>

      <button type="button" onClick={() => setFiltersOpen((v) => !v)}
              className="mt-4 w-full rounded-lg border border-border bg-surface px-4 py-2.5 text-sm font-medium lg:hidden">
        {filtersOpen ? "Скрыть фильтры" : "Фильтры и сортировка"}
      </button>

      {/* key: при переходе по ссылкам меню форма заново берёт значения из адреса */}
      <div className="mt-4 grid gap-6 lg:mt-6 lg:grid-cols-[280px_1fr]" key={params.toString()}>
        <form action="/lots/" className={`h-fit space-y-5 rounded-xl border border-border bg-surface p-4 ${filtersOpen ? "" : "hidden lg:block"}`}>
          {view === "map" && <input type="hidden" name="view" value="map" />}
          <div>
            <label className="label" htmlFor="q">Поиск</label>
            <input id="q" name="q" defaultValue={f.q} placeholder="Город, район, улица" className="field" list="q-hints" autoComplete="off" />
            <datalist id="q-hints">
              {hints.map((h) => <option key={h} value={h} />)}
            </datalist>
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

          <div>
            <span className="label">Цена за м², ₸</span>
            <div className="flex gap-2">
              <input name="ppm_min" type="number" min={0} step={1000} placeholder="от" defaultValue={f.ppm_min} className="field" />
              <input name="ppm_max" type="number" min={0} step={1000} placeholder="до" defaultValue={f.ppm_max} className="field" />
            </div>
            <p className="mt-1 text-xs text-muted">Для квартир и коммерции</p>
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

          <div className="space-y-1">
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" name="with_auction_date" value="true" defaultChecked={f.with_auction_date} />
              Только предстоящие торги
            </label>
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" name="drop" value="true" defaultChecked={f.drop} />
              Только подешевевшие
            </label>
          </div>

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
            <Link href={view === "map" ? "/lots/?view=map" : "/lots/"} className="rounded-lg border border-border px-4 py-2 text-sm text-muted hover:text-foreground">
              Сбросить
            </Link>
          </div>
        </form>

        <div>
          {error ? (
            <div className="rounded-xl border border-dashed border-border bg-surface p-10 text-center text-muted">
              Не удалось загрузить объекты. Обновите страницу.
            </div>
          ) : showInitial ? (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
              {initial.map((lot) => <LotCard key={lot.id} lot={lot} />)}
            </div>
          ) : !lots ? (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
              {Array.from({ length: 6 }, (_, i) => (
                <div key={i} className="h-80 animate-pulse rounded-xl bg-surface" />
              ))}
            </div>
          ) : view === "map" ? (
            <CatalogMap lots={filtered} />
          ) : pageItems.length === 0 ? (
            <div className="rounded-xl border border-dashed border-border bg-surface p-10 text-center text-muted">
              По этим условиям ничего не нашлось. Попробуйте ослабить фильтры
              {code && (
                <> или <a href={botLink(code)} target="_blank" rel="noopener noreferrer" className="font-medium text-brand-ink">
                  подпишитесь — бот сообщит, когда такой объект появится</a></>
              )}.
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
              {pageItems.map((item) =>
                item.kind === "group"
                  ? <ParkingGroupCard key={item.key} group={item} />
                  : <LotCard key={item.lot.id} lot={item.lot} />,
              )}
            </div>
          )}

          {lots && view === "list" && pages > 1 && (
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
