"use client";

// Кнопка в шапке (платный режим): «Войти» или имя пользователя со ссылкой в кабинет.
import Link from "next/link";
import { useEffect, useState } from "react";

import { fetchMe, type Me } from "@/lib/account";

export function AccountButton() {
  const [me, setMe] = useState<Me | null>(null);
  useEffect(() => {
    fetchMe().then(setMe);
  }, []);

  if (me?.authenticated) {
    return (
      <Link href="/account/" className="font-medium text-foreground hover:text-brand">
        {me.name ?? "Кабинет"}
      </Link>
    );
  }
  return (
    <Link href="/account/" className="rounded-lg bg-brand px-3 py-1.5 font-semibold text-white hover:bg-brand-hover">
      Войти
    </Link>
  );
}
