"""Сборка диспетчера и запуск бота."""

from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.base import BaseStorage

from .api import ApiClient
from .config import load_config
from .handlers import format as format_handlers
from .handlers import menu

log = logging.getLogger("gostdoc_bot")


def build_dispatcher(
    api: ApiClient,
    storage: BaseStorage,
    poll_interval: float = 2.0,
    site_url: str = "",
) -> Dispatcher:
    dp = Dispatcher(storage=storage, api=api, poll_interval=poll_interval, site_url=site_url)
    main_router, fallback = menu.build_routers()
    dp.include_router(main_router)
    dp.include_router(format_handlers.build_router())
    dp.include_router(fallback)
    return dp


async def _run(cfg) -> None:
    from aiogram.fsm.storage.redis import RedisStorage

    api = ApiClient(cfg.api_url, cfg.api_secret)
    storage = RedisStorage.from_url(cfg.redis_url, state_ttl=3600, data_ttl=3600)
    bot = Bot(cfg.token)
    dp = build_dispatcher(api, storage, site_url=cfg.site_url)
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()
        await storage.close()
        await api.aclose()


def run() -> None:
    logging.basicConfig(level=logging.INFO)
    cfg = load_config()
    if not cfg.token:
        log.error("TELEGRAM_BOT_TOKEN не задан, бот не запускается")
        return
    asyncio.run(_run(cfg))
