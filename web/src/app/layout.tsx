import type { Metadata } from "next";
import { Inter } from "next/font/google";
import Link from "next/link";

import { AccountButton } from "@/components/AccountButton";
import { FavoritesLink } from "@/components/FavoritesLink";
import { LogoMark } from "@/components/LogoMark";
import { YandexMetrika } from "@/components/YandexMetrika";
import { FEATURES } from "@/lib/features";
import "./globals.css";

const inter = Inter({ variable: "--font-inter", subsets: ["latin", "cyrillic"] });

export const metadata: Metadata = {
  metadataBase: new URL("https://torgi.kz"),
  title: {
    default: "torgi.kz — все торги недвижимостью в Казахстане",
    template: "%s — torgi.kz",
  },
  description:
    "Агрегатор торгов недвижимостью в Казахстане: арестованное имущество, госимущество и приватизация, " +
    "имущество банкротов, конфискат, залоги и имущество банков Halyk, Forte, BCC, Freedom, Alatau, Bereke, " +
    "Евразийского, Нурбанка, RBK. Квартиры, дома, коммерция и земля ниже рынка.",
  openGraph: { siteName: "torgi.kz", locale: "ru_KZ", type: "website", images: ["/og/default.png"] },
  twitter: { card: "summary_large_image" },
};

const NAV = [
  { href: "/top/", label: "🔥 ТОП" },
  { href: "/lots/?category=apartment", label: "Квартиры" },
  { href: "/lots/?category=house", label: "Дома" },
  { href: "/lots/?category=commercial", label: "Коммерция" },
  { href: "/lots/?category=land", label: "Земля" },
  { href: "/lots/?with_auction_date=true&sort=deadline", label: "Ближайшие торги" },
  { href: "/lots/?view=map", label: "Карта" },
  { href: "/podborki/", label: "Подборки" },
];

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="ru" className={`${inter.variable} h-full antialiased`}>
      <body className="flex min-h-full flex-col font-sans">
        <header className="border-b border-border bg-surface">
          <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-x-8 gap-y-2 px-4 py-3">
            <Link href="/" className="flex items-center gap-2 text-xl font-bold tracking-tight text-foreground">
              <LogoMark className="h-8 w-8" />
              <span>torgi<span className="text-brand-ink">.kz</span></span>
            </Link>
            <nav className="flex flex-wrap gap-x-5 gap-y-1 text-sm font-medium text-muted">
              {NAV.map((item) => (
                <Link key={item.href} href={item.href} className="hover:text-brand-ink">
                  {item.label}
                </Link>
              ))}
            </nav>
            {/* Место под вход и подписку — появится в платном режиме */}
            <div className="ml-auto flex items-center gap-4 text-sm">
              <FavoritesLink />
              {FEATURES.telegramUrl && (
                <a href={FEATURES.telegramUrl} target="_blank" rel="noopener noreferrer" className="font-medium text-brand-ink">
                  Telegram
                </a>
              )}
              {FEATURES.auth && <AccountButton />}
            </div>
          </div>
        </header>

        <main className="flex-1">{children}</main>
        <YandexMetrika />

        <footer className="mt-16 border-t border-border bg-surface">
          <div className="mx-auto max-w-7xl space-y-3 px-4 py-8 text-sm text-muted">
            <p className="flex items-center gap-2 font-semibold text-foreground">
              <LogoMark className="h-6 w-6" />
              torgi.kz — агрегатор торгов недвижимостью в Казахстане
            </p>
            <p>
              Сведения собираются из открытых источников: электронной торговой площадки Минюста РК, реестра
              госимущества E-Qazyna и сайтов банков.
              torgi.kz не является организатором торгов и продавцом. Условия, цена и статус лота определяются
              первоисточником — перед участием проверяйте информацию на площадке продавца и документы объекта.
            </p>
            <p className="flex flex-wrap gap-x-5 gap-y-1">
              <Link href="/podborki/" className="hover:text-brand-ink">Подборки</Link>
              <Link href="/podborki/kvartiry-almaty/" className="hover:text-brand-ink">Квартиры с торгов в Алматы</Link>
              <Link href="/podborki/kvartiry-astana/" className="hover:text-brand-ink">Квартиры с торгов в Астане</Link>
              <Link href="/podborki/zalogovoe-imushchestvo-bankov/" className="hover:text-brand-ink">Залоговое имущество банков</Link>
              <Link href="/podborki/gosimushchestvo-i-privatizaciya/" className="hover:text-brand-ink">Госимущество</Link>
            </p>
            <p>© {new Date().getFullYear()} torgi.kz</p>
          </div>
        </footer>
      </body>
    </html>
  );
}
