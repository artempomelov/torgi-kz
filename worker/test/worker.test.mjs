// Тесты worker на Node: D1 подменяется встроенной SQLite.  Запуск: node --test worker/test
import assert from "node:assert/strict";
import { createHmac, createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { DatabaseSync } from "node:sqlite";
import { test } from "node:test";

import worker from "../src/index.js";

const BOT_TOKEN = "123456:TEST-token-for-unit-tests-only-000000";

function fakeD1() {
  const db = new DatabaseSync(":memory:");
  db.exec(readFileSync(new URL("../schema.sql", import.meta.url), "utf-8"));
  const stmt = (sql, params = []) => ({
    bind: (...p) => stmt(sql, p),
    first: async () => db.prepare(sql).get(...params) ?? null,
    run: async () => ({ meta: { changes: Number(db.prepare(sql).run(...params).changes) } }),
    all: async () => ({ results: db.prepare(sql).all(...params) }),
  });
  return { prepare: (sql) => stmt(sql), raw: db };
}

function signedTelegramUser(id = 42) {
  const user = { id, first_name: "Тест", username: "tester", auth_date: Math.floor(Date.now() / 1000) };
  const check = Object.keys(user).sort().map((k) => `${k}=${user[k]}`).join("\n");
  const secret = createHash("sha256").update(BOT_TOKEN).digest();
  return { ...user, hash: createHmac("sha256", secret).update(check).digest("hex") };
}

const env = () => ({ DB: fakeD1(), BOT_TOKEN, FREE_PER_DAY: "2", ALLOWED_ORIGINS: "https://torgi.kz" });
const call = (e, path, init = {}) =>
  worker.fetch(new Request(`https://api.test${path}`, { ...init, headers: { Origin: "https://torgi.kz", ...init.headers } }), e);

test("вход, лимит и закрытые данные", async () => {
  const e = env();
  for (const id of [1, 2, 3]) {
    e.DB.raw.prepare("INSERT INTO lots_private (id, data, hash) VALUES (?, ?, 'h')")
      .run(id, JSON.stringify({ address: `ул. ${id}`, contacts: { phone: "+7700" } }));
  }

  assert.equal((await call(e, "/api/lots/1/details")).status, 401);
  const anon = await (await call(e, "/api/me")).json();
  assert.equal(anon.authenticated, false);

  const bad = await call(e, "/api/auth/telegram", { method: "POST", body: JSON.stringify({ ...signedTelegramUser(), hash: "0".repeat(64) }) });
  assert.equal(bad.status, 401);

  const res = await call(e, "/api/auth/telegram", { method: "POST", body: JSON.stringify(signedTelegramUser()) });
  assert.equal(res.status, 200);
  assert.equal(res.headers.get("Access-Control-Allow-Origin"), "https://torgi.kz");
  const { token, me } = await res.json();
  assert.equal(me.name, "Тест");
  assert.equal(me.remaining_today, 2);
  const auth = { headers: { Authorization: `Bearer ${token}` } };

  const d1 = await (await call(e, "/api/lots/1/details", auth)).json();
  assert.equal(d1.address, "ул. 1");
  assert.equal(d1.remaining_today, 1);
  assert.equal((await (await call(e, "/api/lots/1/details", auth)).json()).remaining_today, 1); // повтор — бесплатно
  assert.equal((await (await call(e, "/api/lots/2/details", auth)).json()).remaining_today, 0);
  assert.equal((await call(e, "/api/lots/3/details", auth)).status, 402);
  assert.equal((await call(e, "/api/lots/99/details", auth)).status, 404);

  const forged = { headers: { Authorization: `Bearer ${token.slice(0, -2)}00` } };
  assert.equal((await call(e, "/api/lots/1/details", forged)).status, 401);

  e.DB.raw.prepare("UPDATE users SET subscription_until = '2099-01-01T00:00:00Z'").run();
  const sub = await (await call(e, "/api/lots/3/details", auth)).json();
  assert.equal(sub.remaining_today, null);
});

test("просмотры и избранное", async () => {
  const e = env();
  const post = (path, body, ip = "1.1.1.1") =>
    call(e, path, { method: "POST", body: body && JSON.stringify(body), headers: { "CF-Connecting-IP": ip } });
  await post("/api/hit/5");
  await post("/api/hit/5"); // тот же посетитель — один просмотр за день
  await post("/api/hit/5", null, "2.2.2.2");
  await post("/api/fav/5", { client: "browser-aaaa1111", on: true });
  await post("/api/fav/5", { client: "browser-bbbb2222", on: true });
  await post("/api/fav/5", { client: "browser-bbbb2222", on: false });
  assert.equal((await post("/api/fav/5", { client: "x", on: true })).status, 400);
  const s = await (await call(e, "/api/stats?ids=5,6")).json();
  assert.deepEqual(s, { 5: { views: 2, favs: 1 } });
});

test("CORS preflight", async () => {
  const res = await call(env(), "/api/me", { method: "OPTIONS" });
  assert.equal(res.status, 204);
  assert.match(res.headers.get("Access-Control-Allow-Headers"), /Authorization/);
});

test("подписка по email: письмо, подтверждение, отписка", async () => {
  const e = { ...env(), BREVO_API_KEY: "test-key" };
  const sent = [];
  const realFetch = globalThis.fetch;
  globalThis.fetch = async (url, init) => {
    sent.push({ url, body: JSON.parse(init.body) });
    return new Response("{}", { status: 201 });
  };
  try {
    const post = (body) => worker.fetch(new Request("https://api.test/api/email/subscribe", {
      method: "POST", body: JSON.stringify(body), headers: { "Content-Type": "application/json" },
    }), e);
    assert.equal((await post({ email: "не почта", code: "q-ca" })).status, 400);
    assert.equal((await post({ email: "a@b.kz", code: "lot-1" })).status, 400);
    const res = await post({ email: "Buyer@Mail.kz", code: "q-ca-r0" });
    assert.equal((await res.json()).status, "sent");
    assert.equal(sent.length, 1);
    assert.equal(sent[0].body.to[0].email, "buyer@mail.kz");
    const link = sent[0].body.htmlContent.match(/href="([^"]+confirm[^"]+)"/)[1];
    assert.match(await (await worker.fetch(new Request(link), e)).text(), /подтверждена/);
    const row = e.DB.raw.prepare("SELECT * FROM email_subs").get();
    assert.equal(row.confirmed, 1);
    assert.equal((await (await post({ email: "buyer@mail.kz", code: "q-ca-r0" })).json()).status, "already");
    await worker.fetch(new Request(`https://api.test/api/email/unsubscribe?t=${row.token}`), e);
    assert.equal(e.DB.raw.prepare("SELECT COUNT(*) AS n FROM email_subs").get().n, 0);
    // без ключа Brevo подписка выключена
    assert.equal((await worker.fetch(new Request("https://api.test/api/email/subscribe", {
      method: "POST", body: JSON.stringify({ email: "a@b.kz", code: "q-ca" }),
    }), env())).status, 503);
  } finally {
    globalThis.fetch = realFetch;
  }
});
