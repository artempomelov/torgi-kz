// Подписка на поиск и слежение за ценой через Telegram-бота.
// Фильтр упаковывается в параметр ссылки t.me/<бот>?start=<код> (до 64 символов [A-Za-z0-9_-]).
// Тот же формат разбирает backend/torgi/bot.py — меняйте их вместе.
import type { Filters } from "./filter";

export const BOT_USERNAME = process.env.NEXT_PUBLIC_TELEGRAM_BOT || "torgi_kz_bot";

// Порядок — как normalize.REGIONS в backend
export const REGIONS = [
  "Алматы", "Астана", "Шымкент",
  "Абайская область", "Акмолинская область", "Актюбинская область", "Алматинская область",
  "Атырауская область", "Восточно-Казахстанская область", "Жамбылская область",
  "Жетысуская область", "Западно-Казахстанская область", "Карагандинская область",
  "Костанайская область", "Кызылординская область", "Мангистауская область",
  "Павлодарская область", "Северо-Казахстанская область", "Туркестанская область",
  "Улытауская область",
];
const CAT = { apartment: "a", house: "h", commercial: "c", land: "l", parking: "p", industrial: "i", other: "o" } as const;
const ORG = {
  arrested: "a", bank_balance: "b", bank_pledge: "z", court: "s",
  state: "g", bankrupt: "k", tax_debtor: "t", confiscated: "f",
} as const;

const letters = (ids: string[], map: Record<string, string>) => ids.map((id) => map[id]).filter(Boolean).join("");
const mln = (v: string) => (v ? Math.round(Number(v) / 1_000_000) : 0);

/** Код подписки на поиск, либо null — если фильтр пустой (подписка «на всё» бессмысленна). */
export function searchCode(f: Filters): string | null {
  const parts: string[] = [];
  const cats = letters(f.category, CAT);
  if (cats) parts.push(`c${cats}`);
  const region = REGIONS.indexOf(f.region);
  if (region >= 0) parts.push(`r${region}`);
  if (mln(f.price_min)) parts.push(`n${mln(f.price_min)}`);
  if (mln(f.price_max)) parts.push(`x${mln(f.price_max)}`);
  if (f.ppm_max) parts.push(`m${Math.round(Number(f.ppm_max) / 1000)}`);
  if (f.area_min) parts.push(`s${Math.round(Number(f.area_min))}`);
  const origins = letters(f.origin, ORG);
  if (origins) parts.push(`o${origins}`);
  if (!parts.length) return null;
  return `q-${parts.join("-")}`.slice(0, 64);
}

export const botLink = (code: string) => `https://t.me/${BOT_USERNAME}?start=${code}`;
export const watchLotLink = (id: number, target?: number) =>
  botLink(target ? `lot-${id}-t${Math.floor(target / 1000)}` : `lot-${id}`);
export const consultLink = (id?: number) => botLink(id ? `c-${id}` : "c");
export const checkLink = (id: number) => botLink(`check-${id}`);
