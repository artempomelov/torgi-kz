"use client";

// Платный режим: закрытые данные лота загружаются из API после входа, с учётом дневного лимита.
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { fetchLotDetails, type DetailsResult } from "@/lib/account";
import { plural } from "@/lib/format";

import { LockedDetails, LotDetailsView } from "./DetailsView";
import { TelegramLogin } from "./TelegramLogin";

export function GatedDetails({ lotId, isAuction }: { lotId: number; isAuction: boolean }) {
  const [result, setResult] = useState<DetailsResult | null>(null);

  const load = useCallback(() => {
    fetchLotDetails(lotId).then(setResult);
  }, [lotId]);

  useEffect(load, [load]);

  if (result === null) {
    return <LockedDetails message="Загружаем…" />;
  }
  if (result.status === "anonymous") {
    return (
      <LockedDetails>
        <TelegramLogin onLogin={load} />
      </LockedDetails>
    );
  }
  if (result.status === "limit") {
    return (
      <LockedDetails message={<>Бесплатные просмотры на сегодня закончились — лимит обновится в 00:00 по Алматы.
        Объекты, открытые сегодня, остаются доступны. Подписка без ограничений скоро появится.</>}>
        <Link href="/account/" className="rounded-lg border border-border px-5 py-2.5 text-sm font-semibold hover:border-brand-ink/40">
          Личный кабинет
        </Link>
      </LockedDetails>
    );
  }
  if (result.status === "error") {
    return <LockedDetails message="Не удалось загрузить данные. Обновите страницу." />;
  }

  const left = result.details.remaining_today;
  return (
    <LotDetailsView
      details={result.details}
      isAuction={isAuction}
      note={left === null ? "Подписка активна — без ограничений." : (
        <>Бесплатно сегодня осталось: {left} {plural(left, ["объект", "объекта", "объектов"])}.{" "}
          <Link href="/account/" className="text-brand-ink">Личный кабинет</Link></>
      )}
    />
  );
}
