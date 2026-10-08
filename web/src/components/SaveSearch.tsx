"use client";

// «Сохранить поиск» под фильтрами каталога: Telegram-бот, письма на почту и «отправить в WhatsApp».
import { useState } from "react";

import { subscribeEmail } from "@/lib/account";
import { FEATURES } from "@/lib/features";
import { reachGoal } from "@/lib/goals";
import { botLink } from "@/lib/subscribe";

export function SaveSearch({ code, shareUrl, shareText }: { code: string | null; shareUrl: string; shareText: string }) {
  const [email, setEmail] = useState("");
  const [state, setState] = useState<{ ok: boolean; message: string } | null>(null);
  const [busy, setBusy] = useState(false);

  return (
    <div className="space-y-2 rounded-xl border border-border bg-surface p-4 text-sm">
      {code ? (
        <>
          <div className="font-semibold">Сохранить поиск</div>
          <a href={botLink(code)} target="_blank" rel="noopener noreferrer"
             className="block rounded-lg bg-brand-ink/5 px-3 py-2 text-center font-medium text-brand-ink hover:bg-brand-ink/10">
            🔖 Новые лоты в Telegram
          </a>
          {FEATURES.email && (
            <form
              className="flex gap-2"
              onSubmit={async (e) => {
                e.preventDefault();
                setBusy(true);
                const result = await subscribeEmail(email.trim(), code);
                setBusy(false);
                setState(result);
                if (result.ok) reachGoal("email_subscribe");
              }}
            >
              <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)}
                     placeholder="Почта для новых лотов" autoComplete="email"
                     className="min-w-0 flex-1 rounded-lg border border-border bg-background px-3 py-2" />
              <button disabled={busy} className="rounded-lg bg-brand px-3 py-2 font-semibold text-white hover:bg-brand-hover disabled:opacity-60">
                ✉️
              </button>
            </form>
          )}
          {state && <p className={state.ok ? "text-success" : "text-accent-ink"}>{state.message}</p>}
        </>
      ) : (
        <p className="text-muted">Выберите фильтры — и новые лоты по ним будут приходить в Telegram{FEATURES.email ? " или на почту" : ""}.</p>
      )}
      <a href={`https://wa.me/?text=${encodeURIComponent(`${shareText}: ${shareUrl}`)}`} target="_blank" rel="noopener noreferrer"
         className="block text-center font-medium text-muted hover:text-foreground">
        Отправить подборку в WhatsApp
      </a>
    </div>
  );
}
