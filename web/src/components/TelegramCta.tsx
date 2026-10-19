// Призыв подписаться на Telegram-канал с новыми лотами — будущая база подписчиков.
// Недвижимость — основной канал (только когда задан NEXT_PUBLIC_TELEGRAM_URL), машины — канал @torgi_kz_auto.
import { FEATURES } from "@/lib/features";

export function TelegramCta({ compact = false, cars = false }: { compact?: boolean; cars?: boolean }) {
  const url = cars ? FEATURES.telegramAutoUrl : FEATURES.telegramUrl;
  if (!url) return null;
  return (
    <a
      href={url}
      target="_blank"
      rel="noopener noreferrer"
      className={`block rounded-xl border border-brand-ink/20 bg-brand-ink/5 hover:border-brand-ink/40 ${compact ? "p-4" : "p-5"}`}
    >
      <div className="font-semibold text-brand-ink">{cars ? "Новые автомобили — в Telegram" : "Новые лоты — в Telegram"}</div>
      <p className="mt-1 text-sm text-muted">
        {cars
          ? "Каждый день публикуем машины и спецтехнику с торгов. Подпишитесь, чтобы не пропустить."
          : "Каждый день публикуем свежие объекты с торгов и залогов банков. Подпишитесь, чтобы не пропустить."}
      </p>
    </a>
  );
}
