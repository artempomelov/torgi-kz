// Перед сборкой: каталог лотов → public/data (грузится браузером), CNAME для GitHub Pages.
import { existsSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";

import { CATALOG_FILE, packCatalog } from "./pack-catalog.mjs";

const dataDir = process.env.TORGI_DATA_DIR ?? "data";
for (const file of ["lots.json", "meta.json", "lots-full.json"]) {
  if (!existsSync(`${dataDir}/${file}`)) {
    console.error(`Нет ${dataDir}/${file}. Выполните: cd backend && uv run python -m torgi.cli export ../web/data`);
    process.exit(1);
  }
}
mkdirSync("public/data", { recursive: true });
const lots = JSON.parse(readFileSync(`${dataDir}/lots.json`, "utf-8"));
writeFileSync(`public/data/${CATALOG_FILE}`, JSON.stringify(packCatalog(lots)));
rmSync("public/data/lots.json", { force: true }); // прежний формат больше не публикуем
writeFileSync("public/CNAME", `${process.env.SITE_DOMAIN ?? "torgi.kz"}\n`);
