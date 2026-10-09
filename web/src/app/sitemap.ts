import type { MetadataRoute } from "next";

import { getCollections } from "@/lib/collections";
import { getLots, getMeta } from "@/lib/data";

export const dynamic = "force-static";

const SITE = "https://torgi.kz";

export default function sitemap(): MetadataRoute.Sitemap {
  const lots = getLots();
  const updated = new Date(getMeta().updated_at);
  return [
    { url: `${SITE}/`, lastModified: updated, changeFrequency: "daily", priority: 1 },
    { url: `${SITE}/lots/`, lastModified: updated, changeFrequency: "daily", priority: 0.9 },
    { url: `${SITE}/top/`, lastModified: updated, changeFrequency: "daily", priority: 0.9 },
    { url: `${SITE}/podborki/`, lastModified: updated, changeFrequency: "daily", priority: 0.8 },
    ...getCollections(lots).map((c) => ({
      url: `${SITE}/podborki/${c.slug}/`,
      lastModified: updated,
      changeFrequency: "daily" as const,
      priority: 0.7,
    })),
    ...lots.map((lot) => ({
      url: `${SITE}/lots/${lot.id}/`,
      lastModified: new Date(lot.first_seen_at),
      changeFrequency: "weekly" as const,
      priority: 0.5,
    })),
  ];
}
