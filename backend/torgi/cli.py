"""Командная строка:

    uv run torgi initdb
    uv run torgi parse                 # все источники
    uv run torgi parse halyk forte     # выбранные
    uv run torgi serve                 # API на http://127.0.0.1:8000
    uv run torgi post --dry-run        # посты для Telegram-канала
"""

import argparse
import logging
import sys

from torgi.db import SessionLocal, init_db
from torgi.parsers import PARSERS


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    ap = argparse.ArgumentParser(prog="torgi")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("initdb", help="создать таблицы")
    p = sub.add_parser("parse", help="запустить парсеры")
    p.add_argument("sources", nargs="*", metavar="source",
                   help=f"источники: {', '.join(PARSERS)} (по умолчанию все)")
    t = sub.add_parser("post", help="опубликовать новые лоты в Telegram-канал")
    t.add_argument("--limit", type=int, default=10)
    t.add_argument("--since-days", type=int, default=3, help="брать лоты, появившиеся за N дней")
    t.add_argument("--dry-run", action="store_true", help="только показать посты")
    t.add_argument("--mark-all", action="store_true", help="пометить все текущие лоты опубликованными")
    e = sub.add_parser("export", help="выгрузить JSON для статического сайта")
    e.add_argument("out_dir", help="каталог, например ../web/data")
    e.add_argument("--gated", action="store_true", help="платный режим: без закрытых полей (адрес, контакты…)")
    s = sub.add_parser("serve", help="запустить API")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=8000)
    s.add_argument("--reload", action="store_true")
    args = ap.parse_args()

    if args.cmd == "initdb":
        init_db()
    elif args.cmd == "parse":
        from torgi.ingest import run_source

        if unknown := [s for s in args.sources if s not in PARSERS]:
            ap.error(f"неизвестные источники: {', '.join(unknown)}; доступны: {', '.join(PARSERS)}")
        init_db()
        failed = []
        for name in args.sources or list(PARSERS):
            with SessionLocal() as session:
                try:
                    run_source(session, name)
                except Exception:
                    failed.append(name)
        if failed:
            logging.error("Ошибки в источниках: %s", ", ".join(failed))
            sys.exit(1)
    elif args.cmd == "post":
        from torgi import telegram

        init_db()
        with SessionLocal() as session:
            telegram.run(session, limit=args.limit, since_days=args.since_days, dry_run=args.dry_run,
                         mark_all=args.mark_all)
    elif args.cmd == "export":
        from pathlib import Path

        from torgi.export import export

        init_db()
        with SessionLocal() as session:
            logging.info("экспорт: %s", export(session, Path(args.out_dir), gated=args.gated))
    elif args.cmd == "serve":
        import uvicorn

        uvicorn.run("torgi.api:app", host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    main()
