// Призыв подписаться на Telegram-канал с новыми лотами — будущая база подписчиков.
// Показывается, только когда задан NEXT_PUBLIC_TELEGRAM_URL.
import { FEATURES } from "@/lib/features";

export function TelegramCta({ compact = false }: { compact?: boolean }) {
  if (!FEATURES.telegramUrl) return null;
  return (
    <a
      href={FEATURES.telegramUrl}
      target="_blank"
      rel="noopener noreferrer"
      className={`block rounded-xl border border-brand/20 bg-brand/5 hover:border-brand/40 ${compact ? "p-4" : "p-5"}`}
    >
      <div className="font-semibold text-brand">Новые лоты — в Telegram</div>
      <p className="mt-1 text-sm text-muted">
        Каждый день публикуем свежие объекты с торгов и залогов банков. Подпишитесь, чтобы не пропустить.
      </p>
    </a>
  );
}
