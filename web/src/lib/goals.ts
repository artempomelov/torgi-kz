"use client";

// Цели Яндекс.Метрики: что люди делают на сайте (а не только сколько их).
// Большинство целей определяется по ссылке, на которую нажали; остальным кнопкам ставим data-goal="…".
// В Метрике у каждой цели тип «JavaScript-событие» с тем же идентификатором.
import { FEATURES } from "./features";

export const GOALS = {
  phone_click: "Звонок: нажали на телефон продавца",
  source_click: "Перешли к источнику (площадка или сайт банка)",
  save_search: "Сохранили поиск в Telegram-боте",
  price_alert: "Подписались на снижение цены лота",
  consult: "Заявка на консультацию",
  check_lot: "Заявка на бесплатную проверку лота",
  tg_channel: "Перешли в Telegram-канал",
  share: "Поделились лотом",
  favorite: "Добавили в избранное",
  map_view: "Открыли карту",
  filter_apply: "Применили фильтры каталога",
  details_open: "Открыли адрес и контакты продавца",
} as const;

export type Goal = keyof typeof GOALS;

export function reachGoal(goal: Goal, params?: Record<string, unknown>) {
  const id = Number(FEATURES.yandexMetrikaId);
  if (id && typeof window !== "undefined") window.ym?.(id, "reachGoal", goal, params);
}

const BOT = /t\.me\/\w+_bot\?start=([\w-]+)/;

/** Цель по адресу ссылки — без правок в каждом компоненте. */
export function goalFromHref(href: string): Goal | null {
  if (href.startsWith("tel:")) return "phone_click";
  if (href.includes("wa.me/") || href.includes("t.me/share/")) return "share";
  const bot = href.match(BOT);
  if (bot) {
    const code = bot[1];
    if (code.startsWith("q-")) return "save_search";
    if (code.startsWith("lot-")) return "price_alert";
    if (code.startsWith("check-")) return "check_lot";
    if (code === "c" || code.startsWith("c-")) return "consult";
    return null;
  }
  if (/t\.me\/torgi_kz_\w+/.test(href)) return "tg_channel";
  if (href.includes("view=map")) return "map_view";
  return null;
}
