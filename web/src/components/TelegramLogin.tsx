"use client";

// Кнопка «Войти через Telegram» (официальный Telegram Login Widget).
// Бот задаётся NEXT_PUBLIC_TELEGRAM_BOT; в @BotFather у бота должен быть /setdomain torgi.kz.
import { useEffect, useRef, useState } from "react";

import { loginWithTelegram, type Me, type TelegramUser } from "@/lib/account";
import { FEATURES } from "@/lib/features";

declare global {
  interface Window {
    onTorgiTelegramAuth?: (user: TelegramUser) => void;
  }
}

export function TelegramLogin({ onLogin }: { onLogin: (me: Me) => void }) {
  const ref = useRef<HTMLDivElement>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const container = ref.current;
    if (!container || !FEATURES.telegramBot) return;
    window.onTorgiTelegramAuth = (user) => {
      setError(null);
      loginWithTelegram(user).then(onLogin, (e: Error) => setError(e.message));
    };
    const script = document.createElement("script");
    script.src = "https://telegram.org/js/telegram-widget.js?22";
    script.async = true;
    script.dataset.telegramLogin = FEATURES.telegramBot;
    script.dataset.size = "large";
    script.dataset.radius = "8";
    script.dataset.userpic = "false";
    script.dataset.requestAccess = "write";
    script.dataset.onauth = "onTorgiTelegramAuth(user)";
    container.replaceChildren(script);
    return () => {
      container.replaceChildren();
      delete window.onTorgiTelegramAuth;
    };
  }, [onLogin]);

  if (!FEATURES.telegramBot) {
    return <p className="text-sm text-muted">Вход скоро будет доступен.</p>;
  }
  return (
    <div className="flex flex-col items-center gap-2">
      <div ref={ref} />
      {error && <p className="text-sm text-accent-ink">{error}</p>}
    </div>
  );
}
