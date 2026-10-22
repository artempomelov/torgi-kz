"""Ежедневная статистика torgi.kz: журнал marketing/stats/daily.csv (дата, показатель, значение) и сводка за неделю.

    uv run --project backend python web/scripts/stats.py telegram                  # подписчики и просмотры каналов
    uv run --project backend python web/scripts/stats.py add ig_followers=139 site_visits=206 --date 2026-10-21
    uv run --project backend python web/scripts/stats.py report                    # таблица за 8 дней

Telegram считаем сами (публичные страницы t.me), остальное (Instagram, Threads, Метрика, реклама) вносится
через `add` — эти цифры видны только в браузере под учётной записью владельца. Показатели:
tg_<канал>_subs, tg_<канал>_views (просмотры постов, опубликованных в этот день), ig_followers, ig_views, ig_reach,
ig_link_clicks, ig_profile_visits, ig_follows, threads_followers, threads_views, site_visits, site_visitors,
site_ads, site_search, site_direct, ads_spent_usd, ads_clicks, goal_consult, goal_save_search, goal_tg_channel.
"""

import csv
import re
import statistics
import sys
import time
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
LOG = ROOT / "marketing" / "stats" / "daily.csv"
ALMATY = timezone(timedelta(hours=5))
CHANNELS = ["torgi_kz_news", "torgi_kz_almaty", "torgi_kz_astana", "torgi_kz_biz", "torgi_kz_auto"]


def load() -> dict[tuple[str, str], float]:
    if not LOG.exists():
        return {}
    with LOG.open(encoding="utf-8") as f:
        return {(r["date"], r["metric"]): float(r["value"]) for r in csv.DictReader(f)}


def save(rows: dict[tuple[str, str], float]):
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date", "metric", "value"])
        for (d, m), v in sorted(rows.items()):
            w.writerow([d, m, int(v) if v == int(v) else v])


def _get(client: httpx.Client, url: str) -> str:
    for i in range(5):  # t.me иногда обрывает соединение
        try:
            return client.get(url).text
        except httpx.HTTPError:
            time.sleep(2 + i * 2)
    raise RuntimeError(url)


def _views(v: str) -> float:
    v = v.strip().replace(",", ".")
    return float(v[:-1]) * 1000 if v.endswith("K") else float(v)


def telegram(days: int = 7) -> dict[tuple[str, str], float]:
    """Подписчики сегодня и просмотры постов по дням публикации за `days` дней (просмотры растут — перезаписываем)."""
    client = httpx.Client(timeout=30, headers={"User-Agent": "Mozilla/5.0"})
    today = datetime.now(ALMATY).date()
    since = (today - timedelta(days=days)).isoformat()
    out: dict[tuple[str, str], float] = {}
    for c in CHANNELS:
        subs = re.search(r'tgme_page_extra">([\d\s]+)', _get(client, f"https://t.me/{c}"))
        out[(today.isoformat(), f"tg_{c}_subs")] = float(re.sub(r"\D", "", subs.group(1))) if subs else 0
        posts, before = {}, None
        for _ in range(20):
            page = _get(client, f"https://t.me/s/{c}" + (f"?before={before}" if before else ""))
            found = re.findall(r'data-post="[^/]+/(\d+)"(.*?)(?=data-post="|$)', page, re.S)
            if not found:
                break
            for pid, body in found:
                v = re.search(r'tgme_widget_message_views">([^<]*)<', body)
                d = re.search(r'datetime="([^"]+)"', body)
                if v and d:
                    day = datetime.fromisoformat(d.group(1)).astimezone(ALMATY).date().isoformat()
                    posts[int(pid)] = (_views(v.group(1)), day)
            first = min(int(p) for p, _ in found)
            if posts.get(first, (0, "9999"))[1] < since or first <= 1:
                break
            before = first
            time.sleep(1)
        by_day: dict[str, list[float]] = defaultdict(list)
        for v, d in posts.values():
            if d >= since:
                by_day[d].append(v)
        for d, vs in by_day.items():
            out[(d, f"tg_{c}_views")] = sum(vs)
            out[(d, f"tg_{c}_posts")] = len(vs)
    return out


def report(days: int = 8):
    rows = load()
    dates = sorted({d for d, _ in rows})[-days:]
    metrics = sorted({m for d, m in rows if d in dates})
    width = max(len(m) for m in metrics) if metrics else 10
    print(" " * width + "".join(f"{d[8:]}.{d[5:7]:>3}".rjust(8) for d in dates))
    for m in metrics:
        print(m.ljust(width) + "".join(
            (f"{rows[(d, m)]:.0f}" if (d, m) in rows else "·").rjust(8) for d in dates))


def main():
    args = sys.argv[1:]
    if not args or args[0] == "report":
        report()
        return
    rows = load()
    if args[0] == "telegram":
        new = telegram()
        rows.update(new)
        save(rows)
        today = datetime.now(ALMATY).date().isoformat()
        for c in CHANNELS:
            vs = [rows[(d, f"tg_{c}_views")] / rows[(d, f"tg_{c}_posts")] for d, m in list(rows)
                  if m == f"tg_{c}_posts" and rows[(d, m)] and d >= (date.fromisoformat(today) - timedelta(days=7)).isoformat()]
            print(f"@{c}: {rows[(today, f'tg_{c}_subs')]:.0f} подписчиков, просмотров на пост (среднее по дням за 7 дней): "
                  f"{statistics.median(vs):.0f}" if vs else f"@{c}: {rows[(today, f'tg_{c}_subs')]:.0f} подписчиков")
    elif args[0] == "add":
        day = datetime.now(ALMATY).date().isoformat()
        if "--date" in args:
            day = args[args.index("--date") + 1]
        for pair in args[1:]:
            if "=" in pair:
                k, v = pair.split("=", 1)
                rows[(day, k)] = float(v.replace(",", "."))
        save(rows)
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
