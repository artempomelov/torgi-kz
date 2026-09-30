// «Закрытая» часть карточки лота: точный адрес, контакты, первоисточник, история цены, описание.
// Бесплатный режим: данные уже есть в статике — показываем всем.
// Платный режим (FEATURES.paywall): <GatedDetails> загружает их из API после входа с учётом лимита.
import type { LotDetailsData } from "@/lib/api";
import { FEATURES } from "@/lib/features";

import { LotDetailsView } from "./DetailsView";
import { GatedDetails } from "./GatedDetails";

export function LotDetails({ lotId, details, isAuction }: { lotId: number; details: LotDetailsData; isAuction: boolean }) {
  if (FEATURES.paywall) return <GatedDetails lotId={lotId} isAuction={isAuction} />;
  return <LotDetailsView details={details} isAuction={isAuction} />;
}
