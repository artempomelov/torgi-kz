"""Публикация Reels в Instagram и постов в Threads через официальный API Meta — без браузера.

Запуск из корня репозитория:
    PYTHONIOENCODING=utf-8 uv run -q --project backend --with httpx python web/scripts/publish_meta.py check
    ... publish_meta.py refresh                 # продлить оба токена ещё на 60 дней
    ... publish_meta.py reels 180 --dry-run     # показать, что уйдёт, без публикации
    ... publish_meta.py reels 180               # опубликовать Reels
    ... publish_meta.py threads 199 --topic "Квартира в Алматы"

Публикуем только по команде владельца («ставь»), как и через браузер. После успешной публикации
скрипт сам отмечает лот в reels-used.json / threads/used.json и пишет ссылку в marketing/meta-published.jsonl.

Токены хранятся вне репозитория (он публичный): %USERPROFILE%\\.torgi\\meta.env
    IG_TOKEN=        долгоживущий токен Instagram API (вход через Instagram), 60 дней
    THREADS_TOKEN=   долгоживущий токен Threads API, 60 дней
Значения токенов скрипт не печатает: все сообщения проходят через say(), которая их вырезает.

Файлы берутся из marketing/ (их готовят make_reels.py / make_threads.py, берётся последняя дата).
Видео Reels загружается напрямую (resumable upload). Обложку Reels и фото Threads Meta скачивает сама
по публичной ссылке — скрипт кладёт их в отдельную ветку social-media этого репозитория и отдаёт
ссылки raw.githubusercontent.com. Ветка каждый раз перезаписывается (в ней только файлы последней
публикации), сайт и update.yml это не задевает: push в main запустил бы пересборку сайта и мог вытеснить
плановый запуск из очереди.

Ограничения API: музыку из библиотеки Instagram и тему из подсказок не выбрать (тема Threads — только
текстом через --topic), отложенной публикации нет — пост выходит сразу.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
MARKETING = ROOT / "marketing"
ENV_FILE = Path(os.environ.get("TORGI_META_ENV", Path.home() / ".torgi" / "meta.env"))
IG_VERSION = os.environ.get("META_IG_VERSION", "v23.0")
IG_API = f"https://graph.instagram.com/{IG_VERSION}"
TH_API = "https://graph.threads.net/v1.0"
REPO = "artempomelov/torgi-kz"
BRANCH = "social-media"
LOG = MARKETING / "meta-published.jsonl"
REELS_USED = MARKETING / "instagram" / "reels-used.json"
THREADS_USED = MARKETING / "threads" / "used.json"

_SECRETS: list[str] = []


class MetaError(Exception):
    pass


def say(*parts) -> None:
    text = " ".join(str(p) for p in parts)
    for secret in _SECRETS:
        text = text.replace(secret, "***")
    print(text, flush=True)


# ---------- токены ----------

def load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8-sig").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            env[key.strip()] = value.strip().strip('"').strip("'")
    _SECRETS.extend(v for k, v in env.items() if k.endswith("_TOKEN") and len(v) > 8)
    return env


def save_env(updates: dict[str, str]) -> None:
    """Меняет только переданные ключи, остальные строки файла (и комментарии) сохраняет."""
    lines = ENV_FILE.read_text(encoding="utf-8-sig").splitlines() if ENV_FILE.exists() else []
    left = dict(updates)
    for i, line in enumerate(lines):
        key = line.split("=", 1)[0].strip()
        if "=" in line and not line.lstrip().startswith("#") and key in left:
            lines[i] = f"{key}={left.pop(key)}"
    lines += [f"{k}={v}" for k, v in left.items()]
    ENV_FILE.parent.mkdir(parents=True, exist_ok=True)
    ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    _SECRETS.extend(v for k, v in updates.items() if k.endswith("_TOKEN"))


def need(env: dict[str, str], key: str) -> str:
    value = env.get(key, "")
    if not value:
        raise MetaError(f"нет {key} в {ENV_FILE} — как получить токен, см. docs/meta-api.md")
    return value


# ---------- запросы ----------

def call(method: str, url: str, token: str, **params) -> dict:
    params["access_token"] = token
    try:
        if method == "GET":
            r = httpx.get(url, params=params, timeout=120)
        else:
            r = httpx.post(url, data=params, timeout=120)
    except httpx.HTTPError as e:  # текст исключения содержит адрес с токеном — не выводим его
        raise MetaError(f"сеть: {type(e).__name__}") from None
    try:
        data = r.json()
    except ValueError:
        data = {"error": {"message": r.text[:300]}}
    if r.status_code >= 400 or (isinstance(data, dict) and "error" in data):
        err = data.get("error", {}) if isinstance(data, dict) else {}
        msg = err.get("error_user_msg") or err.get("message") or str(data)[:300]
        raise MetaError(f"HTTP {r.status_code}: {msg} (code {err.get('code')}, subcode {err.get('error_subcode')})")
    return data


def wait_ready(api: str, cid: str, token: str, field: str, limit_s: int) -> None:
    """Ждёт, пока Meta обработает контейнер (FINISHED), иначе — ошибка."""
    fields = "status_code,status" if field == "status_code" else "status,error_message"
    deadline = time.monotonic() + limit_s
    while True:
        info = call("GET", f"{api}/{cid}", token, fields=fields)
        state = info.get(field)
        if state == "FINISHED":
            return
        if state in ("ERROR", "EXPIRED"):
            raise MetaError(f"контейнер {cid}: {state} — {info.get('status') or info.get('error_message')}")
        if time.monotonic() > deadline:
            raise MetaError(f"контейнер {cid} не готов за {limit_s} с (статус {state})")
        time.sleep(5)


# ---------- публичные ссылки на файлы ----------

def git(*args: str, stdin: str | None = None) -> str:
    # байты, а не текст: в текстовом режиме Windows превращает \n в \r\n, и mktree дописывает \r к именам
    out = subprocess.run(["git", *args], cwd=ROOT, input=stdin.encode() if stdin else None,
                         capture_output=True, check=False)
    if out.returncode:
        raise MetaError(f"git {args[0]}: {out.stderr.decode(errors='replace').strip()[:300]}")
    return out.stdout.decode(errors="replace").strip()


def host(files: list[Path], label: str) -> list[str]:
    """Кладёт файлы в ветку social-media (одна новая фиксация без истории) и возвращает raw-ссылки.

    Рабочую папку и индекс не трогает: объекты создаются через hash-object/mktree/commit-tree.
    """
    names = [f"{label}-{p.name}" for p in files]
    blobs = [git("hash-object", "-w", str(p)) for p in files]
    tree = git("mktree", stdin="".join(f"100644 blob {b}\t{n}\n" for b, n in zip(blobs, names)))
    commit = git("commit-tree", tree, "-m", f"Файлы для публикации {label} (ветка перезаписывается)")
    git("push", "--force", "--quiet", "origin", f"{commit}:refs/heads/{BRANCH}")
    urls = [f"https://raw.githubusercontent.com/{REPO}/{commit}/{n}" for n in names]
    for url in urls:  # Meta скачивает сразу — убеждаемся, что ссылка уже отдаёт картинку
        for _ in range(12):
            r = httpx.head(url, timeout=30, follow_redirects=False)
            if r.status_code == 200 and r.headers.get("content-type", "").startswith("image/"):
                break
            time.sleep(5)
        else:
            raise MetaError(f"файл не открывается по ссылке: {url} (HTTP {r.status_code})")
    say(f"файлы выложены: {len(urls)} шт., ветка {BRANCH}, фиксация {commit[:8]}")
    return urls


# ---------- поиск подготовленных файлов ----------

def latest(paths: list[Path], what: str) -> Path:
    if not paths:
        raise MetaError(f"не нашёл {what} в marketing/ — сначала подготовьте генератором")
    return sorted(paths)[-1]  # папки по датам ГГГГ-ММ-ДД: последняя — самая свежая


def find_reel(lot: int) -> tuple[Path, Path, str]:
    mp4 = latest(list(MARKETING.glob(f"instagram/*/reels/{lot}.mp4")), f"ролик {lot}.mp4")
    cover = mp4.with_name(f"{lot}-cover.jpg")
    caption = mp4.with_name(f"{lot}-caption.txt").read_text(encoding="utf-8").strip()
    if not cover.exists():
        raise MetaError(f"нет обложки {cover}")
    return mp4, cover, caption


def find_thread(lot: int) -> tuple[list[Path], str]:
    folder = latest([p for p in MARKETING.glob(f"threads/*/{lot}") if p.is_dir()], f"папку Threads {lot}")
    photos = sorted(folder.glob("[0-9][0-9].jpg"))
    text = (folder / "post.txt").read_text(encoding="utf-8").strip()
    return photos, text


# ---------- учёт ----------

def mark_used(path: Path, lot: int) -> None:
    ids = set(json.loads(path.read_text(encoding="utf-8"))) if path.exists() else set()
    path.write_text(json.dumps(sorted(ids | {lot})), encoding="utf-8")


def log(kind: str, lot: int, media_id: str, permalink: str) -> None:
    row = {"time": datetime.now(timezone.utc).isoformat(timespec="seconds"), "kind": kind,
           "lot": lot, "id": media_id, "permalink": permalink}
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


# ---------- команды ----------

def cmd_check(env: dict[str, str]) -> None:
    say(f"файл токенов: {ENV_FILE}" + ("" if ENV_FILE.exists() else " — не найден"))
    for key, api, fields, name in (("IG_TOKEN", IG_API, "user_id,username,account_type", "Instagram"),
                                   ("THREADS_TOKEN", TH_API, "id,username", "Threads")):
        token = env.get(key, "")
        if not token:
            say(f"{name}: токена нет ({key} пуст)")
            continue
        try:
            me = call("GET", f"{api}/me", token, fields=fields)
        except MetaError as e:
            say(f"{name}: токен не работает — {e}")
            continue
        expires = env.get(key + "_EXPIRES", "")
        left = ""
        if expires:
            days = (datetime.fromisoformat(expires) - datetime.now(timezone.utc)).days
            left = f", действует до {expires[:10]} (осталось {days} дн.)" + ("  ← пора refresh" if days < 14 else "")
        else:
            left = ", срок неизвестен — через сутки после получения запустите refresh"
        extra = f", тип {me['account_type']}" if me.get("account_type") else ""
        say(f"{name}: @{me.get('username')}{extra}{left}")
        if name == "Instagram":
            try:
                lim = call("GET", f"{IG_API}/me/content_publishing_limit", token, fields="quota_usage,config")
                q = (lim.get("data") or [{}])[0]
                say(f"  публикаций за сутки: {q.get('quota_usage')} из {q.get('config', {}).get('quota_total')}")
            except MetaError as e:
                say(f"  лимит публикаций не прочитан — {e}")


def cmd_refresh(env: dict[str, str]) -> None:
    for key, url, grant, name in (
            ("IG_TOKEN", "https://graph.instagram.com/refresh_access_token", "ig_refresh_token", "Instagram"),
            ("THREADS_TOKEN", "https://graph.threads.net/refresh_access_token", "th_refresh_token", "Threads")):
        token = env.get(key, "")
        if not token:
            say(f"{name}: токена нет — пропускаю")
            continue
        try:
            data = call("GET", url, token, grant_type=grant)
        except MetaError as e:
            say(f"{name}: не продлён — {e}")
            continue
        until = datetime.now(timezone.utc) + timedelta(seconds=int(data.get("expires_in", 0)))
        save_env({key: data["access_token"], key + "_EXPIRES": until.isoformat(timespec="seconds")})
        say(f"{name}: продлён до {until:%d.%m.%Y}")


def cmd_reels(env: dict[str, str], lot: int, dry: bool) -> None:
    mp4, cover, caption = find_reel(lot)
    tags = caption.count("#")
    say(f"Reels {lot}: {mp4.relative_to(ROOT)} ({mp4.stat().st_size / 1e6:.1f} МБ), обложка {cover.name}")
    say(f"подпись: {len(caption)} знаков, хэштегов {tags}; первая строка: {caption.splitlines()[0]}")
    if len(caption) > 2200 or tags > 30:
        raise MetaError("подпись длиннее 2200 знаков или больше 30 хэштегов — Instagram не примет")
    if dry:
        say("--dry-run: ничего не опубликовано")
        return
    token = need(env, "IG_TOKEN")
    cover_url = host([cover], f"reel-{lot}")[0]
    box = call("POST", f"{IG_API}/me/media", token, media_type="REELS", upload_type="resumable",
               caption=caption, share_to_feed="true", cover_url=cover_url)
    cid = box["id"]
    uri = box.get("uri") or f"https://rupload.facebook.com/ig-api-upload/{IG_VERSION}/{cid}"
    size = mp4.stat().st_size
    try:
        r = httpx.post(uri, content=mp4.read_bytes(), timeout=900,
                       headers={"Authorization": f"OAuth {token}", "offset": "0", "file_size": str(size)})
    except httpx.HTTPError as e:
        raise MetaError(f"загрузка видео: {type(e).__name__}") from None
    if r.status_code >= 400:
        raise MetaError(f"загрузка видео: HTTP {r.status_code} {r.text[:300]}")
    say("видео загружено, Instagram обрабатывает…")
    wait_ready(IG_API, cid, token, "status_code", limit_s=900)
    pub = call("POST", f"{IG_API}/me/media_publish", token, creation_id=cid)
    info = call("GET", f"{IG_API}/{pub['id']}", token, fields="permalink,shortcode")
    mark_used(REELS_USED, lot)
    log("reels", lot, pub["id"], info.get("permalink", ""))
    say(f"опубликовано: {info.get('permalink')}  (лот {lot} отмечен в reels-used.json)")


def cmd_threads(env: dict[str, str], lot: int, topic: str | None, dry: bool) -> None:
    photos, text = find_thread(lot)
    say(f"Threads {lot}: фото {len(photos)} ({', '.join(p.name for p in photos)}), текст {len(text)} знаков"
        + (f", тема «{topic}»" if topic else ", без темы"))
    if len(text) > 500:
        raise MetaError("текст длиннее 500 знаков — Threads не примет")
    if not 1 <= len(photos) <= 20:
        raise MetaError("нужно от 1 до 20 фото")
    if topic and (len(topic) > 50 or "." in topic or "&" in topic):
        raise MetaError("тема: до 50 знаков, без точек и «&»")
    if dry:
        say("--dry-run: ничего не опубликовано")
        return
    token = need(env, "THREADS_TOKEN")
    urls = host(photos, f"threads-{lot}")
    extra = {"topic_tag": topic} if topic else {}
    if len(urls) == 1:
        cid = call("POST", f"{TH_API}/me/threads", token, media_type="IMAGE", image_url=urls[0],
                   text=text, **extra)["id"]
    else:
        children = []
        for url in urls:
            child = call("POST", f"{TH_API}/me/threads", token, media_type="IMAGE", image_url=url,
                         is_carousel_item="true")["id"]
            children.append(child)
        for child in children:
            wait_ready(TH_API, child, token, "status", limit_s=180)
        cid = call("POST", f"{TH_API}/me/threads", token, media_type="CAROUSEL",
                   children=",".join(children), text=text, **extra)["id"]
    wait_ready(TH_API, cid, token, "status", limit_s=180)
    pub = call("POST", f"{TH_API}/me/threads_publish", token, creation_id=cid)
    info = call("GET", f"{TH_API}/{pub['id']}", token, fields="permalink")
    mark_used(THREADS_USED, lot)
    log("threads", lot, pub["id"], info.get("permalink", ""))
    say(f"опубликовано: {info.get('permalink')}  (лот {lot} отмечен в threads/used.json)")


def main() -> int:
    parser = argparse.ArgumentParser(description="Публикация в Instagram и Threads через API Meta")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check", help="проверить токены (значения не выводятся)")
    sub.add_parser("refresh", help="продлить токены на 60 дней")
    p = sub.add_parser("reels", help="опубликовать Reels лота")
    p.add_argument("lot", type=int)
    p.add_argument("--dry-run", action="store_true")
    p = sub.add_parser("threads", help="опубликовать пост Threads лота")
    p.add_argument("lot", type=int)
    p.add_argument("--topic", help="тема поста, например «Квартира в Алматы»")
    p.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    env = load_env()
    try:
        if args.cmd == "check":
            cmd_check(env)
        elif args.cmd == "refresh":
            cmd_refresh(env)
        elif args.cmd == "reels":
            cmd_reels(env, args.lot, args.dry_run)
        else:
            cmd_threads(env, args.lot, args.topic, args.dry_run)
    except MetaError as e:
        say(f"ошибка: {e}")
        return 1
    except Exception as e:  # noqa: BLE001 — любое сообщение пропускаем через say(), чтобы не вывести токен
        say(f"ошибка: {type(e).__name__}: {e}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
