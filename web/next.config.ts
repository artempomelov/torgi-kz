import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Статический сайт для GitHub Pages: `next build` → папка out/
  output: "export",
  // /lots/12/ → out/lots/12/index.html — так отдаёт GitHub Pages
  trailingSlash: true,
};

export default nextConfig;
