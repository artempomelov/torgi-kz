// Описание объекта на странице лота — собирается из публичных полей (без точного адреса и источника).
import type { LotFull } from "./api";
import { ORIGIN_LABELS, SALE_TYPE_LABELS, formatDate, formatNumber, formatPrice } from "./format";
import type { MarketCompare } from "./insights";

const WHAT: Record<string, string> = {
  apartment: "Квартира", house: "Дом", commercial: "Коммерческое помещение", land: "Земельный участок",
  parking: "Машино-место или гараж", industrial: "Производственный объект", other: "Объект недвижимости",
};

export function describeLot(lot: LotFull, market: MarketCompare | null): string[] {
  const place = [lot.city ?? lot.region, lot.district].filter(Boolean).join(", ");
  const size = [
    lot.rooms && lot.category === "house" ? `на ${lot.rooms} комн.` : null,
    lot.area_m2 ? `площадью ${formatNumber(lot.area_m2)} м²` : null,
    lot.land_area_ha ? `с участком ${formatNumber(lot.land_area_ha, 4)} га` : null,
    lot.floor ? (lot.floors_total ? `на ${lot.floor} этаже из ${lot.floors_total}` : `на ${lot.floor} этаже`) : null,
    lot.year_built ? `${lot.year_built} года постройки` : null,
  ].filter(Boolean);

  const what = lot.category === "apartment" && lot.rooms ? `${lot.rooms}-комнатная квартира` : WHAT[lot.category] ?? WHAT.other;
  const out = [
    `${what}${size.length ? " " + size.join(", ") : ""}${place ? ` — ${place}` : ""}.`,
  ];
  const how = [
    lot.sale_type ? SALE_TYPE_LABELS[lot.sale_type]?.toLowerCase() : null,
    ORIGIN_LABELS[lot.origin]?.toLowerCase(),
  ].filter(Boolean).join(", ");
  if (lot.price) {
    let sentence = `${lot.sale_type === "auction" || lot.sale_type === "auction_down" ? "Стартовая цена" : "Цена"} — ${formatPrice(lot.price)}`;
    if (lot.price_per_m2 && (lot.category === "apartment" || lot.category === "commercial")) {
      sentence += ` (${formatPrice(lot.price_per_m2)} за м²)`;
    }
    out.push(`${sentence}${how ? `; продажа: ${how}` : ""}.`);
  }
  if (market && market.diffPct <= -10) {
    out.push(`Это на ${-market.diffPct}% дешевле медианы за м² по похожим объектам на торгах и в залогах (${market.where}).`);
  }
  if (lot.auction_start) {
    out.push(`Торги назначены на ${formatDate(lot.auction_start, true)}${
      lot.applications_deadline ? `, заявки принимаются до ${formatDate(lot.applications_deadline, true)}` : ""}${
      lot.deposit ? `, гарантийный взнос — ${formatPrice(lot.deposit)}` : ""}.`);
  }
  return out;
}
