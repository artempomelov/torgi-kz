// torgi.kz API на Cloudflare Workers: вход через Telegram и закрытые данные лотов с дневным лимитом.
//
// Статический сайт (GitHub Pages) показывает карточки без точного адреса, контактов, ссылки на источник,
// документов и описания. Эти поля лежат в D1 (таблица lots_private) — их загружает
// backend/torgi/cloudflare.py при каждом обновлении базы. Сюда же пишутся пользователи и просмотры.
//
// Маршруты (как у backend/torgi/api.py, чтобы сайт работал и с VPS):
//   POST /api/auth/telegram     данные Telegram Login Widget → {token, me}
//   GET  /api/me                кто я и сколько бесплатных просмотров осталось
//   GET  /api/lots/:id/details  закрытые поля лота; 401 — не вошёл, 402 — лимит исчерпан
//
// Сессия — подписанный токен в заголовке Authorization (сайт и API на разных доменах — cookie не подходят).
// Ключ подписи выводится из токена бота, отдельный секрет не нужен.

const KZ_OFFSET_MS = 5 * 3600 * 1000; // весь Казахстан в UTC+5
const SESSION_DAYS = 90;
const AUTH_MAX_AGE_S = 86400; // данные виджета Telegram старше суток не принимаем

const enc = new TextEncoder();
const hex = (buf) => [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, "0")).join("");
const b64url = (s) => btoa(s).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
const unb64url = (s) => atob(s.replace(/-/g, "+").replace(/_/g, "/"));

async function hmac(keyBytes, message) {
  const key = await crypto.subtle.importKey("raw", keyBytes, { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  return crypto.subtle.sign("HMAC", key, enc.encode(message));
}

function safeEqual(a, b) {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

/** Проверка подписи Telegram Login Widget: https://core.telegram.org/widgets/login#checking-authorization */
async function checkTelegramAuth(data, botToken) {
  const { hash, ...fields } = data;
  if (typeof hash !== "string" || !fields.id || !fields.auth_date) return false;
  const checkString = Object.keys(fields)
    .filter((k) => fields[k] !== undefined && fields[k] !== null)
    .sort()
    .map((k) => `${k}=${fields[k]}`)
    .join("\n");
  const secret = await crypto.subtle.digest("SHA-256", enc.encode(botToken));
  const expected = hex(await hmac(secret, checkString));
  const fresh = Date.now() / 1000 - Number(fields.auth_date) < AUTH_MAX_AGE_S;
  return fresh && safeEqual(expected, hash);
}

const sessionKey = (env) => enc.encode(`torgi-session:${env.BOT_TOKEN}`);

async function makeToken(env, userId) {
  const payload = b64url(JSON.stringify({ uid: userId, exp: Date.now() + SESSION_DAYS * 86400_000 }));
  return `${payload}.${hex(await hmac(sessionKey(env), payload))}`;
}

async function readToken(env, request) {
  const auth = request.headers.get("Authorization") ?? "";
  const token = auth.startsWith("Bearer ") ? auth.slice(7) : "";
  const [payload, sig] = token.split(".");
  if (!payload || !sig) return null;
  if (!safeEqual(hex(await hmac(sessionKey(env), payload)), sig)) return null;
  try {
    const { uid, exp } = JSON.parse(unb64url(payload));
    return exp > Date.now() ? uid : null;
  } catch {
    return null;
  }
}

const todayKz = () => new Date(Date.now() + KZ_OFFSET_MS).toISOString().slice(0, 10);
const freePerDay = (env) => Number(env.FREE_PER_DAY ?? 5);
const hasSubscription = (user) => !!user.subscription_until && Date.parse(user.subscription_until) > Date.now();

async function usedToday(env, userId, day) {
  const row = await env.DB.prepare("SELECT COUNT(*) AS n FROM views WHERE user_id = ? AND day = ?").bind(userId, day).first();
  return row?.n ?? 0;
}

async function meFor(env, user) {
  const limit = freePerDay(env);
  if (!user) {
    return { authenticated: false, name: null, username: null, photo_url: null, subscription_until: null,
             free_per_day: limit, remaining_today: null };
  }
  const sub = hasSubscription(user);
  return {
    authenticated: true,
    name: [user.first_name, user.last_name].filter(Boolean).join(" ") || user.username,
    username: user.username,
    photo_url: user.photo_url,
    subscription_until: sub ? user.subscription_until : null,
    free_per_day: limit,
    remaining_today: sub ? null : Math.max(0, limit - (await usedToday(env, user.id, todayKz()))),
  };
}

const getUser = (env, id) => env.DB.prepare("SELECT * FROM users WHERE id = ?").bind(id).first();

async function login(env, request) {
  let data;
  try {
    data = await request.json();
  } catch {
    return json({ detail: "Некорректный запрос" }, 400);
  }
  if (!(await checkTelegramAuth(data, env.BOT_TOKEN))) {
    return json({ detail: "Не удалось подтвердить вход через Telegram. Попробуйте ещё раз." }, 401);
  }
  const now = new Date().toISOString();
  await env.DB.prepare(
    `INSERT INTO users (telegram_id, first_name, last_name, username, photo_url, created_at, last_login_at)
     VALUES (?, ?, ?, ?, ?, ?, ?)
     ON CONFLICT(telegram_id) DO UPDATE SET first_name = excluded.first_name, last_name = excluded.last_name,
       username = excluded.username, photo_url = excluded.photo_url, last_login_at = excluded.last_login_at`,
  ).bind(Number(data.id), data.first_name ?? null, data.last_name ?? null, data.username ?? null,
         data.photo_url ?? null, now, now).run();
  const user = await env.DB.prepare("SELECT * FROM users WHERE telegram_id = ?").bind(Number(data.id)).first();
  return json({ token: await makeToken(env, user.id), me: await meFor(env, user) });
}

async function details(env, userId, lotId) {
  const user = userId ? await getUser(env, userId) : null;
  if (!user) return json({ detail: "Войдите через Telegram" }, 401);
  const row = await env.DB.prepare("SELECT data FROM lots_private WHERE id = ?").bind(lotId).first();
  if (!row) return json({ detail: "Лот не найден" }, 404);

  const limit = freePerDay(env);
  const day = todayKz();
  let remaining = null;
  if (!hasSubscription(user)) {
    const used = await usedToday(env, user.id, day);
    const already = await env.DB.prepare("SELECT 1 FROM views WHERE user_id = ? AND lot_id = ? AND day = ?")
      .bind(user.id, lotId, day).first();
    if (already) {
      remaining = Math.max(0, limit - used); // повторное открытие того же лота лимит не тратит
    } else if (used >= limit) {
      return json({ detail: "Бесплатные просмотры на сегодня закончились" }, 402);
    } else {
      await env.DB.prepare("INSERT OR IGNORE INTO views (user_id, lot_id, day, created_at) VALUES (?, ?, ?, ?)")
        .bind(user.id, lotId, day, new Date().toISOString()).run();
      remaining = limit - used - 1;
    }
  }
  return json({ ...JSON.parse(row.data), remaining_today: remaining });
}

function json(body, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store" },
  });
}

async function route(request, env) {
  const { pathname } = new URL(request.url);
  if (pathname === "/api/health") return json({ ok: true });
  if (pathname === "/api/auth/telegram" && request.method === "POST") return login(env, request);
  const userId = await readToken(env, request);
  if (pathname === "/api/me") return json(await meFor(env, userId ? await getUser(env, userId) : null));
  const m = pathname.match(/^\/api\/lots\/(\d+)\/details\/?$/);
  if (m) return details(env, userId, Number(m[1]));
  return json({ detail: "Не найдено" }, 404);
}

export default {
  async fetch(request, env) {
    const origin = request.headers.get("Origin") ?? "";
    const allowed = (env.ALLOWED_ORIGINS ?? "https://torgi.kz").split(",").map((s) => s.trim());
    const corsOrigin = allowed.includes(origin) ? origin : allowed[0];
    if (request.method === "OPTIONS") {
      return new Response(null, {
        status: 204,
        headers: {
          "Access-Control-Allow-Origin": corsOrigin,
          "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
          "Access-Control-Allow-Headers": "Authorization, Content-Type",
          "Access-Control-Max-Age": "86400",
          Vary: "Origin",
        },
      });
    }

    let response;
    try {
      response = await route(request, env);
    } catch (e) {
      console.error(e);
      response = json({ detail: "Ошибка сервера" }, 500);
    }
    response.headers.set("Access-Control-Allow-Origin", corsOrigin);
    response.headers.set("Vary", "Origin");
    return response;
  },
};
