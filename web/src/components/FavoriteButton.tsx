"use client";

import { toggleFavorite, useFavorites } from "@/lib/favorites";

export function FavoriteButton({ id, variant = "icon" }: { id: number; variant?: "icon" | "button" }) {
  const active = useFavorites().includes(id);
  const label = active ? "Убрать из избранного" : "В избранное";
  const heart = (
    <svg aria-hidden viewBox="0 0 24 24" className="h-5 w-5" fill={active ? "currentColor" : "none"} stroke="currentColor" strokeWidth="2">
      <path d="M12 21s-7.5-4.6-9.5-9.2C1 8.3 3.2 5 6.6 5c2 0 3.4 1.1 4.4 2.6h2C14 6.1 15.4 5 17.4 5 20.8 5 23 8.3 21.5 11.8 19.5 16.4 12 21 12 21z" />
    </svg>
  );
  const onClick = (e: React.MouseEvent) => {
    e.preventDefault(); // кнопка лежит внутри ссылки-карточки
    e.stopPropagation();
    toggleFavorite(id);
  };

  if (variant === "button") {
    return (
      <button type="button" onClick={onClick} aria-pressed={active}
              className={`flex w-full items-center justify-center gap-2 rounded-lg border px-4 py-2.5 text-sm font-medium ${
                active ? "border-accent bg-accent/15 text-accent-ink" : "border-border hover:border-brand/40"}`}>
        {heart}
        {active ? "В избранном" : "Добавить в избранное"}
      </button>
    );
  }
  return (
    <button type="button" onClick={onClick} aria-pressed={active} aria-label={label} title={label}
            className={`rounded-full bg-surface/95 p-1.5 shadow-sm ${active ? "text-accent-ink" : "text-muted hover:text-foreground"}`}>
      {heart}
    </button>
  );
}
