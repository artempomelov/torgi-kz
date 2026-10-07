"use client";

// «Где искать»: несколько регионов, городов и районов галочками.
// Районы показываются для выбранных мест и привязаны к городу («Ауэзовский район» есть в Алматы и Шымкенте).
import { useMemo, useState } from "react";

import type { Lot, Meta } from "@/lib/api";
import { districtKey, type Filters } from "@/lib/filter";

const REPUBLIC = ["Алматы", "Астана", "Шымкент"];

function Box({ name, value, label, count, checked }: { name: string; value: string; label: string; count?: number; checked: boolean }) {
  return (
    <label className="flex items-center gap-2 text-sm">
      <input type="checkbox" name={name} value={value} defaultChecked={checked} />
      <span className="flex-1">{label}</span>
      {count !== undefined && <span className="text-xs text-muted">{count}</span>}
    </label>
  );
}

export function LocationFilter({ meta, lots, f }: { meta: Meta; lots: Lot[] | null; f: Filters }) {
  const [showAll, setShowAll] = useState(f.region.some((r) => !REPUBLIC.includes(r)) || f.city.length > 0);
  const regionCount = new Map(meta.regions.map((r) => [r.id, r.count]));

  // Города внутри областей (Караганда, Актобе…) — из лотов, по частоте
  const cities = useMemo(() => {
    const count = new Map<string, number>();
    for (const l of lots ?? []) {
      if (l.city && !REPUBLIC.includes(l.city)) count.set(l.city, (count.get(l.city) ?? 0) + 1);
    }
    return [...count.entries()].filter(([, n]) => n >= 2).sort((a, b) => b[1] - a[1]);
  }, [lots]);

  // Районы выбранных мест: «Бостандыкский район» + город, если мест несколько
  const districts = useMemo(() => {
    if (!lots || (!f.region.length && !f.city.length)) return [];
    const count = new Map<string, { label: string; place: string; n: number }>();
    for (const l of lots) {
      const place = l.city ?? l.region;
      if (!l.district || !place) continue;
      if (!f.region.includes(l.region ?? "") && !f.city.includes(l.city ?? "")) continue;
      const key = districtKey(l)!;
      const item = count.get(key) ?? { label: l.district, place, n: 0 };
      item.n += 1;
      count.set(key, item);
    }
    return [...count.entries()].sort((a, b) => a[1].place.localeCompare(b[1].place) || b[1].n - a[1].n);
  }, [lots, f.region, f.city]);
  const severalPlaces = new Set(districts.map(([, d]) => d.place)).size > 1;

  const oblasts = meta.regions.filter((r) => r.count > 0 && !REPUBLIC.includes(r.id));

  return (
    <fieldset className="space-y-3">
      <legend className="label">Где искать</legend>
      <div className="space-y-1">
        {REPUBLIC.map((r) => (
          <Box key={r} name="region" value={r} label={r} count={regionCount.get(r)} checked={f.region.includes(r)} />
        ))}
      </div>

      {showAll ? (
        <>
          {cities.length > 0 && (
            <div>
              <div className="mb-1 text-xs text-muted">Города</div>
              <div className="max-h-44 space-y-1 overflow-y-auto pr-1">
                {cities.map(([c, n]) => <Box key={c} name="city" value={c} label={c} count={n} checked={f.city.includes(c)} />)}
              </div>
            </div>
          )}
          <div>
            <div className="mb-1 text-xs text-muted">Области</div>
            <div className="max-h-44 space-y-1 overflow-y-auto pr-1">
              {oblasts.map((r) => <Box key={r.id} name="region" value={r.id} label={r.id} count={r.count} checked={f.region.includes(r.id)} />)}
            </div>
          </div>
        </>
      ) : (
        <button type="button" onClick={() => setShowAll(true)} className="text-sm font-medium text-brand-ink hover:underline">
          Другие города и области
        </button>
      )}

      {districts.length > 0 && (
        <div>
          <div className="mb-1 text-xs text-muted">Районы</div>
          <div className="max-h-48 space-y-1 overflow-y-auto pr-1">
            {districts.map(([key, d]) => (
              <Box key={key} name="district" value={key} label={severalPlaces ? `${d.label} (${d.place})` : d.label}
                   count={d.n} checked={f.district.includes(key)} />
            ))}
          </div>
        </div>
      )}
      {(f.region.length > 0 || f.city.length > 0) && districts.length === 0 && lots && (
        <p className="text-xs text-muted">Районы появятся, когда источники их указывают.</p>
      )}
    </fieldset>
  );
}
