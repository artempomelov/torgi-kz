import type { Metadata } from "next";

import { Favorites } from "@/components/Favorites";

export const metadata: Metadata = {
  title: "Избранное",
  robots: { index: false },
};

export default function FavoritesPage() {
  return <Favorites />;
}
