import type { Metadata } from "next";
import { Suspense } from "react";

import { Catalog } from "@/components/Catalog";
import { Faq } from "@/components/Faq";
import { getLots, getMeta } from "@/lib/data";
import { PAGE_SIZE, applyFilters, parseFilters } from "@/lib/filter";

export const metadata: Metadata = {
  title: "Каталог объектов на торгах",
  description: "Квартиры, дома, коммерческая недвижимость и земля на торгах в Казахстане: арест, залоги и имущество банков.",
  alternates: { canonical: "/lots/" },
};

export default function LotsPage() {
  // Фильтры читаются из адреса в браузере — страница собирается статически
  return (
    <>
      <Suspense>
        {/* первая страница «новых» — в HTML, чтобы каталог показывался до загрузки lots.json */}
        <Catalog meta={getMeta()} initial={applyFilters(getLots(), parseFilters(new URLSearchParams())).slice(0, PAGE_SIZE)} />
      </Suspense>
      <Faq className="pb-4" />
    </>
  );
}
