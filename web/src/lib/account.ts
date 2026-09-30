// Клиентские запросы к API: вход, «кто я», закрытые данные лота. Работают только в браузере.
import type { LotDetailsData } from "./api";
import { FEATURES } from "./features";

export type Me = {
  authenticated: boolean;
  name: string | null;
  username: string | null;
  photo_url: string | null;
  subscription_until: string | null;
  free_per_day: number;
  remaining_today: number | null;
};

export type TelegramUser = {
  id: number;
  first_name?: string;
  last_name?: string;
  username?: string;
  photo_url?: string;
  auth_date: number;
  hash: string;
};

export type DetailsResult =
  | { status: "ok"; details: LotDetailsData & { remaining_today: number | null } }
  | { status: "anonymous" }
  | { status: "limit" }
  | { status: "error" };

const api = (path: string) => `${FEATURES.apiUrl}${path}`;
const opts: RequestInit = { credentials: "include" };

export async function fetchMe(): Promise<Me | null> {
  try {
    const res = await fetch(api("/api/me"), opts);
    return res.ok ? res.json() : null;
  } catch {
    return null;
  }
}

export async function loginWithTelegram(user: TelegramUser): Promise<Me> {
  const res = await fetch(api("/api/auth/telegram"), {
    ...opts,
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(user),
  });
  if (!res.ok) throw new Error((await res.json().catch(() => null))?.detail ?? "Не удалось войти");
  return res.json();
}

export async function logout(): Promise<void> {
  await fetch(api("/api/auth/logout"), { ...opts, method: "POST" });
}

export async function fetchLotDetails(lotId: number): Promise<DetailsResult> {
  try {
    const res = await fetch(api(`/api/lots/${lotId}/details`), opts);
    if (res.status === 401) return { status: "anonymous" };
    if (res.status === 402) return { status: "limit" };
    if (!res.ok) return { status: "error" };
    return { status: "ok", details: await res.json() };
  } catch {
    return { status: "error" };
  }
}
