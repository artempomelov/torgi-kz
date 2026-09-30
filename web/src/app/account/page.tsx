import type { Metadata } from "next";

import { notFound } from "next/navigation";

import { AccountPanel } from "@/components/AccountPanel";
import { FEATURES } from "@/lib/features";

export const metadata: Metadata = {
  title: "Личный кабинет",
  robots: { index: false },
};

export default function AccountPage() {
  // Кабинет нужен только с входом (платный режим, сервер с API); на бесплатном сайте — 404
  if (!FEATURES.auth) notFound();
  return (
    <div className="mx-auto max-w-2xl px-4 py-10">
      <h1 className="mb-6 text-2xl font-bold md:text-3xl">Личный кабинет</h1>
      <AccountPanel />
    </div>
  );
}
