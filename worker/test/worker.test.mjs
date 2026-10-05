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
    run: async () => db.prepare(sql).run(...params),
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

test("CORS preflight", async () => {
  const res = await call(env(), "/api/me", { method: "OPTIONS" });
  assert.equal(res.status, 204);
  assert.match(res.headers.get("Access-Control-Allow-Headers"), /Authorization/);
});
