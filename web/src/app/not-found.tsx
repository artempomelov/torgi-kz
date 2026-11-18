import type { Metadata } from "next";
import Link from "next/link";

// Сборка кладёт страницу в out/404.html — GitHub Pages отдаёт её на любой несуществующий адрес
// (лоты, снятые больше 30 дней назад, опечатки в ссылках). Раньше там была английская заглушка Next.js.
export const metadata: Metadata = { title: "Страница не найдена", robots: { index: false } };

const LINKS: [string, string][] = [
  ["/lots/", "Недвижимость"],
  ["/avto/", "Автомобили"],
  ["/top/", "ТОП ниже рынка"],
];

export default function NotFound() {
  return (
    <div className="mx-auto max-w-3xl px-4 py-16 text-center">
      <h1 className="text-2xl font-bold md:text-3xl">Страница не найдена</h1>
      <p className="mt-3 text-muted">Возможно, лот уже снят с торгов. Актуальные объекты — в каталоге.</p>
      <div className="mt-6 flex flex-wrap justify-center gap-3">
        {LINKS.map(([href, title], i) => (
          <Link key={href} href={href}
                className={i === 0
                  ? "rounded-lg bg-brand px-4 py-2.5 font-semibold text-white hover:bg-brand-hover"
                  : "rounded-lg border border-border bg-surface px-4 py-2.5 font-semibold hover:border-brand-ink"}>
            {title}
          </Link>
        ))}
      </div>
    </div>
  );
}
