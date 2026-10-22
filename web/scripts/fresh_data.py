"""Свежие данные для генераторов Instagram/Reels: база и сводки цен из релиза «data» → выгрузка в web/data.

    uv run --project backend python web/scripts/fresh_data.py

Скачивает torgi.db.gz, market-index.json и car-market-index.json в marketing/data-cache/ (backend/torgi.db не
трогает) и запускает `torgi.cli export` с оценкой по рынку — как на сайте, с плашками «−N% к рынку».
"""

import gzip
import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / "marketing" / "data-cache"


def main():
    CACHE.mkdir(parents=True, exist_ok=True)
    subprocess.run(["gh", "release", "download", "data", "--pattern", "torgi.db.gz", "--pattern", "market-index.json",
                    "--pattern", "car-market-index.json", "--dir", str(CACHE), "--clobber"], check=True, cwd=ROOT)
    with gzip.open(CACHE / "torgi.db.gz", "rb") as src, (CACHE / "torgi.db").open("wb") as dst:
        shutil.copyfileobj(src, dst)
    env = {**os.environ, "TORGI_DATABASE_URL": f"sqlite:///{(CACHE / 'torgi.db').as_posix()}", "PYTHONIOENCODING": "utf-8"}
    subprocess.run(["uv", "run", "python", "-m", "torgi.cli", "export", str(ROOT / "web" / "data"),
                    "--market", str(CACHE / "market-index.json"), "--car-market", str(CACHE / "car-market-index.json")],
                   check=True, cwd=ROOT / "backend", env=env)


if __name__ == "__main__":
    main()
