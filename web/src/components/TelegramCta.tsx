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
      className={`block rounded-xl border border-brand-ink/20 bg-brand-ink/5 hover:border-brand-ink/40 ${compact ? "p-4" : "p-5"}`}
    >
      <div className="font-semibold text-brand-ink">Новые лоты — в Telegram</div>
      <p className="mt-1 text-sm text-muted">
        Каждый день публикуем свежие объекты с торгов и залогов банков. Подпишитесь, чтобы не пропустить.
      </p>
    </a>
  );
}
