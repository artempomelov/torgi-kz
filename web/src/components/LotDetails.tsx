// «Закрытая» часть карточки лота: точный адрес, контакты, первоисточник, история цены, описание.
// Сейчас сайт бесплатный — блок показывается всем. В платном режиме (FEATURES.paywall) вместо данных
// рендерится <LockedDetails>, а сами данные придут из API после входа (см. lib/features.ts).
import type { LotDetailsData } from "@/lib/api";
import { FEATURES } from "@/lib/features";
import { formatDate, formatPrice, plural } from "@/lib/format";

const CONTACT_LABELS: Record<string, string> = {
  name: "Контактное лицо",
  phone: "Телефон",
  contact: "Контакты",
  email: "Email",
  owner: "Продавец",
  position: "Должность",
};

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex justify-between gap-4 border-b border-border/60 py-1.5">
      <dt className="text-muted">{label}</dt>
      <dd className="text-right font-medium">{children}</dd>
    </div>
  );
}

export function LotDetails({ details, isAuction }: { details: LotDetailsData; isAuction: boolean }) {
  if (FEATURES.paywall && !details.url) return <LockedDetails />;

  const contacts = Object.entries(details.contacts ?? {}).filter(([, v]) => v);
  const history = (details.price_history ?? []).filter((p) => p.price != null);

  return (
    <section className="rounded-xl border border-border bg-surface p-5" aria-labelledby="lot-details">
      <h2 id="lot-details" className="mb-3 text-lg font-semibold">Адрес, контакты и источник</h2>
      <dl className="text-sm">
        {details.address && <Row label="Адрес">{details.address}</Row>}
        {details.cadastral && <Row label="Кадастровый номер">{details.cadastral}</Row>}
        {contacts.map(([k, v]) => (
          <Row key={k} label={CONTACT_LABELS[k] ?? k}>
            {k === "phone" ? <a href={`tel:${v}`} className="text-brand">{v}</a> : v}
          </Row>
        ))}
      </dl>

      <div className="mt-4 flex flex-col gap-2 sm:flex-row">
        {details.url && (
          <a href={details.url} target="_blank" rel="noopener noreferrer"
             className="flex-1 rounded-lg bg-brand px-4 py-3 text-center font-semibold text-white hover:bg-brand-hover">
            {isAuction ? "Перейти к торгам у источника" : "Открыть у источника"}
          </a>
        )}
        {details.lat && details.lon ? (
          <a href={`https://2gis.kz/geo/${details.lon},${details.lat}`} target="_blank" rel="noopener noreferrer"
             className="flex-1 rounded-lg border border-border px-4 py-3 text-center text-sm font-medium hover:border-brand/40">
            Показать на карте 2ГИС
          </a>
        ) : null}
      </div>

      {history.length > 1 && (
        <div className="mt-5">
          <h3 className="mb-2 text-sm font-semibold">История цены</h3>
          <ul className="space-y-1 text-sm">
            {history.map((p) => (
              <li key={p.seen_at} className="flex justify-between">
                <span className="text-muted">{formatDate(p.seen_at)}</span>
                <span className="font-medium">{formatPrice(p.price)}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {details.description && (
        <div className="mt-5">
          <h3 className="mb-2 text-sm font-semibold">Описание от продавца</h3>
          <p className="whitespace-pre-line text-sm leading-6">{details.description}</p>
        </div>
      )}
    </section>
  );
}

/** Заглушка для платного режима: те же разделы, но размытые, и призыв войти/оформить подписку. */
export function LockedDetails() {
  const n = FEATURES.freeDetailsPerDay;
  return (
    <section className="relative overflow-hidden rounded-xl border border-border bg-surface p-5" aria-labelledby="lot-details">
      <h2 id="lot-details" className="mb-3 text-lg font-semibold">Адрес, контакты и источник</h2>
      <div aria-hidden className="select-none space-y-2 text-sm blur-sm">
        <div className="h-4 w-3/4 rounded bg-border" />
        <div className="h-4 w-1/2 rounded bg-border" />
        <div className="h-4 w-2/3 rounded bg-border" />
        <div className="h-10 w-full rounded-lg bg-brand/30" />
        <div className="h-4 w-5/6 rounded bg-border" />
      </div>
      <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 bg-surface/70 p-6 text-center">
        <p className="max-w-sm text-sm">
          Точный адрес, контакты продавца, ссылка на торги и история цены —{" "}
          <b>бесплатно {n} {plural(n, ["объект", "объекта", "объектов"])} в день</b> после входа, без ограничений по подписке.
        </p>
        <button type="button" className="rounded-lg bg-brand px-5 py-2.5 text-sm font-semibold text-white hover:bg-brand-hover">
          Войти через Telegram
        </button>
      </div>
    </section>
  );
}
