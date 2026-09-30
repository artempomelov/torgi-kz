// Яндекс.Метрика: включается, когда задан NEXT_PUBLIC_YM_ID (номер счётчика).
import Script from "next/script";

import { FEATURES } from "@/lib/features";

export function YandexMetrika() {
  const id = FEATURES.yandexMetrikaId;
  if (!id) return null;
  return (
    <>
      <Script id="yandex-metrika" strategy="afterInteractive">{`
        (function(m,e,t,r,i,k,a){m[i]=m[i]||function(){(m[i].a=m[i].a||[]).push(arguments)};
        m[i].l=1*new Date();for (var j = 0; j < document.scripts.length; j++) {if (document.scripts[j].src === r) { return; }}
        k=e.createElement(t),a=e.getElementsByTagName(t)[0],k.async=1,k.src=r,a.parentNode.insertBefore(k,a)})
        (window, document, "script", "https://mc.yandex.ru/metrika/tag.js", "ym");
        ym(${Number(id)}, "init", { clickmap: true, trackLinks: true, accurateTrackBounce: true, webvisor: true });
      `}</Script>
      <noscript>
        {/* eslint-disable-next-line @next/next/no-img-element -- пиксель Метрики для браузеров без JS */}
        <img src={`https://mc.yandex.ru/watch/${Number(id)}`} style={{ position: "absolute", left: "-9999px" }} alt="" />
      </noscript>
    </>
  );
}
