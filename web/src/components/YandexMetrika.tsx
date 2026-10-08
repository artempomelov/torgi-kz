"use client";

// Яндекс.Метрика: включается, когда задан NEXT_PUBLIC_YM_ID (номер счётчика).
// Первый просмотр засчитывает сам счётчик при загрузке; переходы внутри сайта (без перезагрузки
// страницы) отправляем вручную через ym(id, "hit"), иначе Метрика их не увидит.
import { usePathname, useSearchParams } from "next/navigation";
import Script from "next/script";
import { Suspense, useEffect, useRef } from "react";

import { FEATURES } from "@/lib/features";
import { type Goal, goalFromHref, reachGoal } from "@/lib/goals";

declare global {
  interface Window {
    ym?: (id: number, method: string, ...args: unknown[]) => void;
  }
}

function PageViews({ id }: { id: number }) {
  const pathname = usePathname();
  const search = useSearchParams();
  const first = useRef(true);

  useEffect(() => {
    if (first.current) {
      first.current = false; // первый хит уже отправлен при инициализации
      return;
    }
    const qs = search.toString();
    window.ym?.(id, "hit", `${location.origin}${pathname}${qs ? `?${qs}` : ""}`, { referer: document.referrer });
  }, [id, pathname, search]);

  return null;
}

/** Цели по кликам: ссылки распознаются по адресу, прочие кнопки — по data-goal; отправка формы каталога. */
function Goals() {
  useEffect(() => {
    const onClick = (e: MouseEvent) => {
      const el = (e.target as Element | null)?.closest<HTMLElement>("[data-goal], a[href]");
      if (!el) return;
      const goal = (el.dataset.goal as Goal | undefined) ?? goalFromHref(el.getAttribute("href") ?? "");
      if (goal) reachGoal(goal);
    };
    const onSubmit = (e: SubmitEvent) => {
      if ((e.target as HTMLFormElement).getAttribute("action") === "/lots/") reachGoal("filter_apply");
    };
    document.addEventListener("click", onClick, true);
    document.addEventListener("submit", onSubmit, true);
    return () => {
      document.removeEventListener("click", onClick, true);
      document.removeEventListener("submit", onSubmit, true);
    };
  }, []);
  return null;
}

export function YandexMetrika() {
  const raw = FEATURES.yandexMetrikaId;
  if (!raw) return null;
  const id = Number(raw);
  return (
    <>
      <Script id="yandex-metrika" strategy="afterInteractive">{`
        (function(m,e,t,r,i,k,a){m[i]=m[i]||function(){(m[i].a=m[i].a||[]).push(arguments)};
        m[i].l=1*new Date();for (var j = 0; j < document.scripts.length; j++) {if (document.scripts[j].src === r) { return; }}
        k=e.createElement(t),a=e.getElementsByTagName(t)[0],k.async=1,k.src=r,a.parentNode.insertBefore(k,a)})
        (window, document, "script", "https://mc.yandex.ru/metrika/tag.js", "ym");
        ym(${id}, "init", { clickmap: true, trackLinks: true, accurateTrackBounce: true, webvisor: true });
      `}</Script>
      <noscript>
        {/* eslint-disable-next-line @next/next/no-img-element -- пиксель Метрики для браузеров без JS */}
        <img src={`https://mc.yandex.ru/watch/${id}`} style={{ position: "absolute", left: "-9999px" }} alt="" />
      </noscript>
      <Suspense>
        <PageViews id={id} />
      </Suspense>
      <Goals />
    </>
  );
}
