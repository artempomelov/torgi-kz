import type { Metadata } from "next";
import { Suspense } from "react";

import { CarCatalog } from "@/components/CarCatalog";
import { getCars } from "@/lib/data";

export const metadata: Metadata = {
  title: "Автомобили с торгов",
  description: "Автомобили и спецтехника с торгов в Казахстане: арестованное имущество, залоги и имущество банков. "
    + "Фильтры по марке, модели, году и городу.",
  alternates: { canonical: "/avto/" },
};

export default function CarsPage() {
  return (
    <Suspense>
      <CarCatalog cars={getCars()} />
    </Suspense>
  );
}
