"use client";

import { useEffect } from "react";

import { plural } from "@/lib/format";
import { recordView, useLotStats } from "@/lib/stats";

/** «👁 12 смотрели · ♡ 3 в избранном» — показывается, когда есть хоть одна цифра. */
export function LotStatsBadge({ id, record = false, compact = true, className = "" }: {
  id: number;
  record?: boolean; // засчитать просмотр (страница лота)
  compact?: boolean;
  className?: string;
}) {
  const stats = useLotStats(id);
  useEffect(() => {
    if (record) recordView(id);
  }, [id, record]);
  if (!stats || (!stats.views && !stats.favs)) return null;
  if (compact) {
    return (
      <div className={`flex gap-2 text-xs text-muted ${className}`} title="Просмотры за 7 дней · в избранном">
        {stats.views > 0 && <span>👁 {stats.views}</span>}
        {stats.favs > 0 && <span>♡ {stats.favs}</span>}
      </div>
    );
  }
  return (
    <div className={`flex gap-3 text-xs text-muted ${className}`}>
      {stats.views > 0 && (
        <span title="Уникальные просмотры за 7 дней">
          👁 {stats.views} {plural(stats.views, ["просмотр", "просмотра", "просмотров"])} за неделю
        </span>
      )}
      {stats.favs > 0 && <span>♡ {stats.favs} в избранном</span>}
    </div>
  );
}
