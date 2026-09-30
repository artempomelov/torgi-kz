// Отображение закрытой части карточки лота и заглушка платного режима (без логики загрузки).
import type { LotDetailsData } from "@/lib/api";
import { FEATURES } from "@/lib/features";
import { formatDate, formatFileSize, formatPrice, plural } from "@/lib/format";

const CONTACT_LABELS: Record<string, string> = {
  name: "Контактное лицо",
  phone: "Телефон",
  contact: "Контакты",
  email: "Email",
  owner: "Продавец",
  position: "Должность",
  officer: "Судебный исполнитель",
};

export const DETAILS_TITLE = "Адрес, контакты и источник";


function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex justify-between gap-4 border-b border-border/60 py-1.5">
      <dt className="text-muted">{label}</dt>
      <dd className="text-right font-medium">{children}</dd>
    </div>
  );
}

export function LotDetailsView({ details, isAuction, note }: {
  details: LotDetailsData;
  isAuction: boolean;
  note?: React.ReactNode;
}) {
  const contacts = Object.entries(details.contacts ?? {}).filter(([, v]) => v);
  const history = (details.price_history ?? []).filter((p) => p.price != null);
  const documents = details.documents ?? [];

  return (
    <section id="lot-details" className="scroll-mt-4 rounded-xl border border-border bg-surface p-5">
      <h2 className="mb-3 text-lg font-semibold">{DETAILS_TITLE}</h2>
      <dl className="text-sm">
        {details.address && <Row label="Адрес">{details.address}</Row>}
        {details.cadastral && <Row label="Кадастровый номер">{details.cadastral}</Row>}
        {contacts.map(([k, v]) => (
          <Row key={k} label={CONTACT_LABELS[k] ?? k}>
            {k === "phone" ? <a href={`tel:${v}`} className="text-brand-ink">{v}</a> : v}
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
      {note && <p className="mt-3 text-xs text-muted">{note}</p>}

      {documents.length > 0 && (
        <div className="mt-5">
          <h3 className="mb-2 text-sm font-semibold">Документы от источника</h3>
          <ul className="space-y-1.5 text-sm">
            {documents.map((doc) => (
              <li key={doc.url}>
                <a href={doc.url} target="_blank" rel="noopener noreferrer"
                   className="group flex items-start gap-2 rounded-lg border border-border px-3 py-2 hover:border-brand/50">
                  <svg aria-hidden viewBox="0 0 24 24" className="mt-0.5 h-4 w-4 flex-none text-brand" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z" /><path d="M14 3v5h5" />
                  </svg>
                  <span className="flex-1 group-hover:text-brand-ink">{doc.title}</span>
                  {formatFileSize(doc.size) && <span className="text-xs text-muted">{formatFileSize(doc.size)}</span>}
                </a>
              </li>
            ))}
          </ul>
        </div>
      )}

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

/** Заглушка платного режима: размытый блок, пояснение и действие (вход / подписка). */
export function LockedDetails({ message, children }: { message?: React.ReactNode; children?: React.ReactNode }) {
  const n = FEATURES.freeDetailsPerDay;
  return (
    <section id="lot-details" className="relative scroll-mt-4 overflow-hidden rounded-xl border border-border bg-surface p-5">
      <h2 className="mb-3 text-lg font-semibold">{DETAILS_TITLE}</h2>
      <div aria-hidden className="select-none space-y-2 text-sm blur-sm">
        <div className="h-4 w-3/4 rounded bg-border" />
        <div className="h-4 w-1/2 rounded bg-border" />
        <div className="h-4 w-2/3 rounded bg-border" />
        <div className="h-10 w-full rounded-lg bg-brand/30" />
        <div className="h-4 w-5/6 rounded bg-border" />
        <div className="h-4 w-3/5 rounded bg-border" />
      </div>
      <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 bg-surface/75 p-6 text-center">
        <p className="max-w-sm text-sm">
          {message ?? (
            <>
              Точный адрес, контакты продавца, ссылка на торги и история цены —{" "}
              <b>бесплатно {n} {plural(n, ["объект", "объекта", "объектов"])} в день</b> после входа,
              без ограничений — по подписке.
            </>
          )}
        </p>
        {children}
      </div>
    </section>
  );
}
