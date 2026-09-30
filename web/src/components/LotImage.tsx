"use client";

// Фото лота с заглушкой: если фото нет или оно не загрузилось у источника —
// показываем картинку-заглушку по типу объекта с надписью «Нет фото».
import { useState } from "react";

const PLACEHOLDER_CATEGORIES = new Set(["apartment", "house", "land", "commercial", "parking", "industrial"]);

export function placeholderFor(category: string): string {
  return `/placeholders/${PLACEHOLDER_CATEGORIES.has(category) ? category : "other"}.svg`;
}

export function LotImage({
  src,
  category,
  alt,
  className,
  eager = false,
}: {
  src: string | null | undefined;
  category: string;
  alt: string;
  className?: string;
  eager?: boolean;
}) {
  const [failed, setFailed] = useState(false);
  const url = src && !failed ? src : placeholderFor(category);
  return (
    // eslint-disable-next-line @next/next/no-img-element -- фото с десятка внешних доменов источников
    <img
      src={url}
      alt={url === src ? alt : `${alt} — нет фото`}
      loading={eager ? "eager" : "lazy"}
      className={className}
      onError={() => setFailed(true)}
    />
  );
}
