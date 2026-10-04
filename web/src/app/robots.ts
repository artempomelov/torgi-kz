import type { MetadataRoute } from "next";

export const dynamic = "force-static";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: { userAgent: "*", allow: "/", disallow: ["/account/", "/data/"] },
    sitemap: "https://torgi.kz/sitemap.xml",
    host: "https://torgi.kz",
  };
}
