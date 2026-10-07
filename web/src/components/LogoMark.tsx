// Символ torgi.kz: домик со стрелкой вниз — «недвижимость дешевле рынка».
// Тот же, что на аватарке Telegram-канала и в значке сайта (web/scripts/make_avatar.py).
export function LogoMark({ className = "h-8 w-8" }: { className?: string }) {
  return (
    <svg viewBox="0 0 64 64" className={className} aria-hidden>
      <rect width="64" height="64" rx="14" fill="#0f1115" />
      <path d="M13 26 32 12l19 14" fill="none" stroke="#fff" strokeWidth="4.5" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M18.5 23v23h27V23" fill="none" stroke="#fff" strokeWidth="4.5" strokeLinejoin="round" />
      <rect x="29.8" y="24" width="4.4" height="11" fill="#5b82f0" />
      <path d="M25 34h14l-7 7z" fill="#5b82f0" />
    </svg>
  );
}
