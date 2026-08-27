from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand

from .config import load_settings
from .database import Database
from .feed import FeedClient
from .handlers import build_router
from .monitor import FeedMonitor


async def main() -> None:
    settings = load_settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level, logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    database = Database(settings.database_path)
    database.initialize()

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dispatcher = Dispatcher()
    feed_client = FeedClient(
        url=settings.rss_url,
        timeout_seconds=settings.request_timeout_seconds,
    )
    monitor = FeedMonitor(bot, settings, database, feed_client)
    dispatcher.include_router(build_router(settings, database, monitor))

    await bot.set_my_commands(
        [
            BotCommand(command="start", description="Запустить и показать помощь"),
            BotCommand(command="status", description="Статус мониторинга"),
            BotCommand(command="check", description="Проверить RSS сейчас"),
            BotCommand(command="pause", description="Приостановить уведомления"),
            BotCommand(command="resume", description="Возобновить уведомления"),
        ]
    )

    monitor_task = asyncio.create_task(monitor.run(), name="rss-monitor")
    try:
        await dispatcher.start_polling(bot, allowed_updates=dispatcher.resolve_used_update_types())
    finally:
        monitor.stop()
        await monitor_task
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
