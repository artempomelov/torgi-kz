"use client";

// Личный кабинет: вход через Telegram, остаток бесплатных просмотров, подписка.
import { useCallback, useEffect, useState } from "react";

import { fetchMe, logout, type Me } from "@/lib/account";
import { formatDate, plural } from "@/lib/format";

import { TelegramLogin } from "./TelegramLogin";

export function AccountPanel() {
  const [me, setMe] = useState<Me | null | undefined>(undefined);
  const reload = useCallback(() => {
    fetchMe().then(setMe);
  }, []);
  useEffect(reload, [reload]);

  if (me === undefined) return <p className="text-muted">Загружаем…</p>;
  if (me === null) return <p className="text-muted">Сервис временно недоступен. Попробуйте позже.</p>;

  if (!me.authenticated) {
    return (
      <div className="rounded-xl border border-border bg-surface p-6 text-center">
        <p className="mb-4">
          Войдите через Telegram — это бесплатно. Каждый день вам доступны полные данные{" "}
          <b>{me.free_per_day} {plural(me.free_per_day, ["объекта", "объектов", "объектов"])}</b>: точный адрес,
          контакты продавца, ссылка на торги и история цены.
        </p>
        <TelegramLogin onLogin={setMe} />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-4 rounded-xl border border-border bg-surface p-6">
        {/* eslint-disable-next-line @next/next/no-img-element -- аватар из Telegram */}
        {me.photo_url && <img src={me.photo_url} alt="" className="h-14 w-14 rounded-full" />}
        <div className="flex-1">
          <div className="text-lg font-semibold">{me.name}</div>
          {me.username && <div className="text-sm text-muted">@{me.username}</div>}
        </div>
        <button type="button" onClick={() => logout().then(reload)} className="text-sm text-muted hover:text-foreground">
          Выйти
        </button>
      </div>

      <div className="rounded-xl border border-border bg-surface p-6">
        {me.subscription_until ? (
          <p>Подписка активна до <b>{formatDate(me.subscription_until)}</b> — полные данные всех объектов без ограничений.</p>
        ) : (
          <>
            <p>
              Сегодня осталось бесплатных просмотров: <b>{me.remaining_today}</b> из {me.free_per_day}.
              Лимит обновляется каждый день в 00:00 по Алматы.
            </p>
            <div className="mt-4 rounded-lg bg-brand/5 p-4">
              <div className="font-semibold text-brand-ink">Подписка torgi.kz</div>
              <ul className="mt-2 list-inside list-disc text-sm text-muted">
                <li>полные данные всех объектов без дневного лимита</li>
                <li>уведомления о новых лотах по вашим фильтрам в Telegram</li>
                <li>ранний доступ к новым объектам и история снижения цен</li>
              </ul>
              <p className="mt-3 text-sm">Оформление подписки скоро откроется.</p>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
