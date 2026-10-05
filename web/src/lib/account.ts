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

// Сессия — подписанный токен от API (worker на Cloudflare): сайт и API на разных доменах,
// поэтому cookie не годятся. Хранится в этом браузере.
const TOKEN_KEY = "torgi:session";
function getToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}
function setToken(token: string | null) {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* приватный режим — вход продержится до закрытия вкладки */
  }
}
function opts(): RequestInit {
  const token = getToken();
  return { credentials: "include", headers: token ? { Authorization: `Bearer ${token}` } : {} };
}

export async function fetchMe(): Promise<Me | null> {
  try {
    const res = await fetch(api("/api/me"), opts());
    return res.ok ? res.json() : null;
  } catch {
    return null;
  }
}

export async function loginWithTelegram(user: TelegramUser): Promise<Me> {
  const res = await fetch(api("/api/auth/telegram"), {
    credentials: "include",
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(user),
  });
  if (!res.ok) throw new Error((await res.json().catch(() => null))?.detail ?? "Не удалось войти");
  const data = await res.json();
  // worker отвечает {token, me}; backend на VPS — сразу me (сессия в cookie)
  if (data.token) {
    setToken(data.token);
    return data.me;
  }
  return data;
}

export async function logout(): Promise<void> {
  setToken(null);
  await fetch(api("/api/auth/logout"), { ...opts(), method: "POST" }).catch(() => undefined);
}

export async function fetchLotDetails(lotId: number): Promise<DetailsResult> {
  try {
    const res = await fetch(api(`/api/lots/${lotId}/details`), opts());
    if (res.status === 401) return { status: "anonymous" };
    if (res.status === 402) return { status: "limit" };
    if (!res.ok) return { status: "error" };
    return { status: "ok", details: await res.json() };
  } catch {
    return { status: "error" };
  }
}
