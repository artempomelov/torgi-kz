"use client";

// «Консультация» на карточке каталога: карточка целиком — ссылка, поэтому кнопка открывает бота сама.
import { consultLink } from "@/lib/subscribe";

export function ConsultButton({ id }: { id: number }) {
  return (
    <button
      type="button"
      onClick={(e) => {
        e.preventDefault();
        e.stopPropagation();
        window.open(consultLink(id), "_blank", "noopener");
      }}
      className="text-xs font-medium text-brand-ink hover:underline"
    >
      Консультация
    </button>
  );
}
