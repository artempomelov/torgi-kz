"use client";

// Фото лота с заглушкой. Фото грузим через бесплатный кэширующий прокси wsrv.nl (уменьшенная копия
// в WebP — быстрее, чем оригинал с сайта банка). Если прокси не отдал — берём оригинал,
// если и он недоступен или фото нет — картинка-заглушка по типу объекта с надписью «Нет фото».
import { useState } from "react";

const PLACEHOLDER_CATEGORIES = new Set(["apartment", "house", "land", "commercial", "parking", "industrial"]);

export function placeholderFor(category: string): string {
  return `/placeholders/${PLACEHOLDER_CATEGORIES.has(category) ? category : "other"}.svg`;
}

export function proxied(src: string, width: number): string {
  return `https://wsrv.nl/?url=${encodeURIComponent(src)}&w=${width}&output=webp&q=78&we`;
}

export function LotImage({
  src,
  category,
  alt,
  className,
  eager = false,
  width = 640,
}: {
  src: string | null | undefined;
  category: string;
  alt: string;
  className?: string;
  eager?: boolean;
  width?: number; // ширина уменьшенной копии; 0 — оригинал
}) {
  // 0 — через прокси, 1 — оригинал, 2 — заглушка
  const [stage, setStage] = useState(src ? (width ? 0 : 1) : 2);
  const url = !src || stage === 2 ? placeholderFor(category) : stage === 0 ? proxied(src, width) : src;
  return (
    // eslint-disable-next-line @next/next/no-img-element -- фото с десятка внешних доменов источников
    <img
      src={url}
      alt={stage === 2 ? `${alt} — нет фото` : alt}
      loading={eager ? "eager" : "lazy"}
      decoding="async"
      referrerPolicy="no-referrer"
      className={className}
      onError={() => setStage((s) => Math.min(s + 1, 2))}
    />
  );
}
