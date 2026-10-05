"use client";

// Карта лотов с координатами (Leaflet + OpenStreetMap). Грузится только при переключении на «Карту».
import "leaflet/dist/leaflet.css";
import "leaflet.markercluster/dist/MarkerCluster.css";
import "leaflet.markercluster/dist/MarkerCluster.Default.css";
import { useEffect, useMemo, useRef } from "react";

import type { Lot } from "@/lib/api";
import { FEATURES } from "@/lib/features";
import { CATEGORY_LABELS, formatPriceShort } from "@/lib/format";

const COLORS: Record<string, string> = {
  apartment: "#0092aa", house: "#2e9e5b", commercial: "#957200", land: "#7a5c3e",
  parking: "#6b7280", industrial: "#8b3a62", other: "#6b7280",
};

const esc = (s: string) => s.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]!);

export function CatalogMap({ lots }: { lots: Lot[] }) {
  const ref = useRef<HTMLDivElement>(null);
  // точки вне Казахстана — ошибки координат у источника (или объект за рубежом), карту не растягиваем
  const withCoords = useMemo(
    () => lots.filter((l) => l.lat && l.lon && l.lat > 40.5 && l.lat < 55.6 && l.lon > 46.4 && l.lon < 87.4),
    [lots],
  );

  useEffect(() => {
    let map: import("leaflet").Map | null = null;
    let cancelled = false;
    (async () => {
      const L = (await import("leaflet")).default;
      // плагин кластеров ждёт глобальный L
      (window as unknown as { L: typeof L }).L = L;
      await import("leaflet.markercluster");
      if (cancelled || !ref.current) return;
      map = L.map(ref.current, { scrollWheelZoom: true }).setView([48.0, 67.0], 5);
      L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 18,
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
      }).addTo(map);
      const markers = withCoords.map((lot) =>
        L.circleMarker([lot.lat!, lot.lon!], {
          radius: 7, color: "#fff", weight: 1.5, fillColor: COLORS[lot.category] ?? "#0092aa", fillOpacity: 0.9,
        }).bindPopup(
          `<a href="/lots/${lot.id}/" style="font-weight:600">${esc(formatPriceShort(lot.price))}</a><br>` +
            `${esc(CATEGORY_LABELS[lot.category] ?? "")}${lot.area_m2 ? `, ${lot.area_m2} м²` : ""}<br>` +
            `<span style="color:#5b6b73">${esc(lot.address ?? lot.city ?? "")}</span>`,
        ),
      );
      const group = L.markerClusterGroup({ showCoverageOnHover: false, maxClusterRadius: 45, chunkedLoading: true });
      group.addLayers(markers);
      map.addLayer(group);
      if (markers.length) map.fitBounds(group.getBounds(), { padding: [30, 30], maxZoom: 14 });
    })();
    return () => {
      cancelled = true;
      map?.remove();
    };
  }, [withCoords]);

  return (
    <div>
      <div ref={ref} className="h-[70vh] min-h-[420px] w-full overflow-hidden rounded-xl border border-border" />
      <p className="mt-2 text-xs text-muted">
        На карте {withCoords.length} из {lots.length} объектов — у остальных источник не указал координаты.
        {FEATURES.paywall && " Расположение примерное (до ~1 км), точный адрес — в карточке объекта после входа."}
      </p>
    </div>
  );
}
