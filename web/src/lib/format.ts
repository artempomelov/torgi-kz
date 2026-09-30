export const CATEGORY_LABELS: Record<string, string> = {
  apartment: "Квартира",
  house: "Дом",
  commercial: "Коммерческая",
  land: "Земельный участок",
  parking: "Паркинг / гараж",
  industrial: "Промбаза",
  other: "Прочее",
};

export const CATEGORY_PLURAL: Record<string, string> = {
  apartment: "Квартиры",
  house: "Дома",
  commercial: "Коммерция",
  land: "Земля",
  parking: "Паркинги и гаражи",
  industrial: "Промбазы",
  other: "Прочее",
};

export const ORIGIN_LABELS: Record<string, string> = {
  arrested: "Арестованное имущество",
  bank_balance: "Имущество банка",
  bank_pledge: "Залог банка",
  court: "Судебная реализация",
};

export const SALE_TYPE_LABELS: Record<string, string> = {
  auction: "Аукцион",
  auction_down: "Аукцион на понижение",
  direct: "Прямая продажа",
  tender: "Конкурс",
};

export const SOURCE_LABELS: Record<string, string> = {
  adilet: "ЕЭТП Минюста",
  halyk: "Halyk Bank",
  alatau: "Alatau City Bank",
  forte: "ForteBank",
  bcc: "Bank CenterCredit",
  freedom: "Freedom Bank",
};

const TZ = "Asia/Almaty";

export function formatPrice(value: number | null | undefined): string {
  if (value == null) return "Цена не указана";
  return `${new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 0 }).format(value)} ₸`;
}

export function formatPriceShort(value: number | null | undefined): string {
  if (value == null) return "—";
  if (value >= 1e9) return `${(value / 1e9).toLocaleString("ru-RU", { maximumFractionDigits: 2 })} млрд ₸`;
  if (value >= 1e6) return `${(value / 1e6).toLocaleString("ru-RU", { maximumFractionDigits: 1 })} млн ₸`;
  return formatPrice(value);
}

export function formatNumber(value: number | null | undefined, digits = 1): string {
  return value == null ? "—" : value.toLocaleString("ru-RU", { maximumFractionDigits: digits });
}

export function formatDate(value: string | null | undefined, withTime = false): string {
  if (!value) return "—";
  return new Intl.DateTimeFormat("ru-RU", {
    day: "numeric",
    month: "long",
    year: "numeric",
    ...(withTime ? { hour: "2-digit", minute: "2-digit" } : {}),
    timeZone: TZ,
  }).format(new Date(value));
}

export function lotSubtitle(lot: {
  category: string;
  area_m2: number | null;
  land_area_ha: number | null;
  rooms: number | null;
  floor: number | null;
  floors_total: number | null;
}): string {
  const parts: string[] = [];
  if (lot.rooms) parts.push(`${lot.rooms}-комн.`);
  if (lot.area_m2) parts.push(`${formatNumber(lot.area_m2)} м²`);
  if (lot.land_area_ha) parts.push(`участок ${formatNumber(lot.land_area_ha, 4)} га`);
  if (lot.floor) parts.push(lot.floors_total ? `${lot.floor}/${lot.floors_total} эт.` : `${lot.floor} эт.`);
  return parts.join(" · ");
}

export function plural(n: number, forms: [string, string, string]): string {
  const mod10 = n % 10;
  const mod100 = n % 100;
  if (mod10 === 1 && mod100 !== 11) return forms[0];
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 10 || mod100 >= 20)) return forms[1];
  return forms[2];
}

/** Цена за единицу площади: за м² — квартиры и коммерция, за сотку — земельные участки. */
export function unitPrice(lot: {
  category: string;
  price: number | null;
  price_per_m2: number | null;
  land_area_ha: number | null;
  flags?: string[];
}): { value: number; unit: "м²" | "сотку"; label: string } | null {
  if (lot.category === "land") {
    if (!lot.price || !lot.land_area_ha || lot.flags?.includes("suspicious_price")) return null;
    const value = lot.price / (lot.land_area_ha * 100); // 1 га = 100 соток
    return { value, unit: "сотку", label: `${formatMoney(value)} ₸/сотка` };
  }
  if ((lot.category === "apartment" || lot.category === "commercial") && lot.price_per_m2) {
    return { value: lot.price_per_m2, unit: "м²", label: `${formatMoney(lot.price_per_m2)} ₸/м²` };
  }
  return null;
}

function formatMoney(value: number): string {
  return Math.round(value).toLocaleString("ru-RU");
}

export function formatFileSize(bytes: number | null | undefined): string | null {
  if (!bytes) return null;
  if (bytes >= 1024 * 1024) return `${(bytes / 1024 / 1024).toLocaleString("ru-RU", { maximumFractionDigits: 1 })} МБ`;
  return `${Math.max(1, Math.round(bytes / 1024))} КБ`;
}
