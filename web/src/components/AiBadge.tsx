// «Первый агрегатор торгов с использованием AI» — значок «искры» (как у AI-функций в сервисах; иконка Lucide «sparkles»).
export function SparklesIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round"
         strokeLinejoin="round" aria-hidden="true" className={className}>
      <path d="M9.937 15.5A2 2 0 0 0 8.5 14.063l-6.135-1.582a.5.5 0 0 1 0-.962L8.5 9.936A2 2 0 0 0 9.937 8.5l1.582-6.135a.5.5 0 0 1 .963 0L14.063 8.5A2 2 0 0 0 15.5 9.937l6.135 1.581a.5.5 0 0 1 0 .964L15.5 14.063a2 2 0 0 0-1.437 1.437l-1.582 6.135a.5.5 0 0 1-.963 0z" />
      <path d="M20 3v4" />
      <path d="M22 5h-4" />
      <path d="M4 17v2" />
      <path d="M5 18H3" />
    </svg>
  );
}

export function AiBadge() {
  return (
    <span
      className="inline-flex items-center gap-2 rounded-full px-4 py-1.5 text-sm font-semibold text-white shadow-card"
      style={{ background: "linear-gradient(90deg, #7c3aed, #2450d6)" }}
    >
      <SparklesIcon className="h-4 w-4" />
      Первый агрегатор торгов с использованием AI
    </span>
  );
}
