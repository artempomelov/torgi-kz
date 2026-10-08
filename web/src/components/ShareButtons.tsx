"use client";

import { useState } from "react";

export function ShareButtons({ url, text }: { url: string; text: string }) {
  const [copied, setCopied] = useState(false);
  const enc = encodeURIComponent;
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      window.prompt("Скопируйте ссылку", url);
    }
  };
  const btn = "flex-1 rounded-lg border border-border px-3 py-2 text-center text-sm font-medium hover:border-brand-ink/40";
  return (
    <div>
      <div className="mb-2 text-sm text-muted">Поделиться</div>
      <div className="flex gap-2">
        <a className={btn} target="_blank" rel="noopener noreferrer" href={`https://wa.me/?text=${enc(`${text} ${url}`)}`}>
          WhatsApp
        </a>
        <a className={btn} target="_blank" rel="noopener noreferrer" href={`https://t.me/share/url?url=${enc(url)}&text=${enc(text)}`}>
          Telegram
        </a>
        <button type="button" className={btn} onClick={copy} data-goal="share">
          {copied ? "Скопировано" : "Ссылка"}
        </button>
      </div>
    </div>
  );
}
