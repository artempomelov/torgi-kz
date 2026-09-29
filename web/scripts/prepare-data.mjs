// Перед сборкой: каталог лотов → public/data (грузится браузером), CNAME для GitHub Pages.
import { copyFileSync, existsSync, mkdirSync, writeFileSync } from "node:fs";

const dataDir = process.env.TORGI_DATA_DIR ?? "data";
for (const file of ["lots.json", "meta.json", "lots-full.json"]) {
  if (!existsSync(`${dataDir}/${file}`)) {
    console.error(`Нет ${dataDir}/${file}. Выполните: cd backend && uv run python -m torgi.cli export ../web/data`);
    process.exit(1);
  }
}
mkdirSync("public/data", { recursive: true });
copyFileSync(`${dataDir}/lots.json`, "public/data/lots.json");
writeFileSync("public/CNAME", `${process.env.SITE_DOMAIN ?? "torgi.kz"}\n`);
