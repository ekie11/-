"""Очередь задач (RQ) и обработчик ошибок очереди."""

from __future__ import annotations

from fastapi import Request
from redis import Redis
from rq import Queue
from rq.timeouts import JobTimeoutException

from .config import Settings

QUEUE_NAME = "gostdoc"


def make_queue(settings: Settings) -> Queue:
    return Queue(QUEUE_NAME, connection=Redis.from_url(settings.redis_url))


def get_queue(request: Request) -> Queue:
    """Зависимость FastAPI; в тестах подменяется через dependency_overrides."""
    return make_queue(request.app.state.settings)


def on_job_failure(job, connection, type_, value, traceback) -> None:
    """RQ вызывает при падении или таймауте задачи: переводит её в error."""
    from .worker import TIMEOUT_MESSAGE, mark_error_if_open

    is_timeout = isinstance(type_, type) and issubclass(type_, JobTimeoutException)
    mark_error_if_open(job.id, TIMEOUT_MESSAGE if is_timeout else None)
