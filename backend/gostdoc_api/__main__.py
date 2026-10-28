"""Запуск: python -m gostdoc_api serve|worker|cleanup|migrate."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
from pathlib import Path

from .config import get_settings


def _serve(args: argparse.Namespace) -> None:
    import uvicorn

    from .app import create_app

    uvicorn.run(create_app(), host=args.host, port=args.port)


def _worker(args: argparse.Namespace) -> None:
    from redis import Redis
    from rq import Queue, Worker

    from .queue import QUEUE_NAME

    connection = Redis.from_url(get_settings().redis_url)
    Worker([Queue(QUEUE_NAME, connection=connection)], connection=connection).work()


def _extract_worker(args: argparse.Namespace) -> None:
    from redis import Redis
    from rq import Queue, Worker

    from .queue import EXTRACTION_QUEUE_NAME

    # Ровно один процесс и одна очередь: параллельные запросы к модели не превышают 1.
    connection = Redis.from_url(get_settings().redis_url)
    Worker([Queue(EXTRACTION_QUEUE_NAME, connection=connection)], connection=connection).work()


def _cleanup(args: argparse.Namespace) -> None:
    from .cleanup import cleanup_expired
    from .db import make_engine, make_sessionmaker

    settings = get_settings()
    with make_sessionmaker(make_engine(settings.database_url))() as db:
        count = cleanup_expired(db, settings, now=datetime.now(UTC))
    print(f"Просрочено задач: {count}")


def _migrate(args: argparse.Namespace) -> None:
    from alembic import command
    from alembic.config import Config

    cfg = Config(str(Path(__file__).resolve().parent.parent / "alembic.ini"))
    cfg.set_main_option("script_location", str(Path(__file__).resolve().parent / "migrations"))
    cfg.set_main_option("sqlalchemy.url", get_settings().database_url.replace("%", "%%"))
    command.upgrade(cfg, "head")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m gostdoc_api")
    sub = parser.add_subparsers(dest="command", required=True)
    serve = sub.add_parser("serve", help="запустить HTTP-сервер")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    serve.set_defaults(func=_serve)
    sub.add_parser("worker", help="запустить RQ-воркер").set_defaults(func=_worker)
    sub.add_parser(
        "extract-worker", help="запустить RQ-воркер извлечений (один процесс)"
    ).set_defaults(func=_extract_worker)
    sub.add_parser("cleanup", help="удалить просроченные файлы и сессии").set_defaults(
        func=_cleanup
    )
    sub.add_parser("migrate", help="применить миграции БД").set_defaults(func=_migrate)
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
