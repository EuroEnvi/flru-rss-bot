from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from aiogram import Bot
from aiogram.exceptions import TelegramRetryAfter
from aiogram.types import LinkPreviewOptions

from .config import Settings
from .database import Database
from .feed import FeedClient
from .formatter import format_item, item_keyboard
from .models import CheckResult, FeedItem

logger = logging.getLogger(__name__)


class FeedMonitor:
    def __init__(
        self,
        bot: Bot,
        settings: Settings,
        database: Database,
        feed_client: FeedClient,
    ) -> None:
        self.bot = bot
        self.settings = settings
        self.database = database
        self.feed_client = feed_client
        self._stop_event = asyncio.Event()
        self._wake_event = asyncio.Event()
        self._check_lock = asyncio.Lock()

    async def run(self) -> None:
        logger.info("Монитор RSS запущен")
        while not self._stop_event.is_set():
            if self.settings.telegram_user_id and not self.is_paused:
                try:
                    await self.check_once()
                except Exception as exc:  # noqa: BLE001
                    logger.exception("Ошибка фоновой проверки RSS")
                    self.database.set_state("last_error", str(exc)[:1000])

            self._wake_event.clear()
            try:
                await asyncio.wait_for(
                    self._wake_event.wait(),
                    timeout=self.settings.check_interval_seconds,
                )
            except TimeoutError:
                pass

        logger.info("Монитор RSS остановлен")

    @property
    def is_paused(self) -> bool:
        return self.database.get_bool("paused", default=False)

    def pause(self) -> None:
        self.database.set_bool("paused", True)

    def resume(self) -> None:
        self.database.set_bool("paused", False)
        self._wake_event.set()

    def stop(self) -> None:
        self._stop_event.set()
        self._wake_event.set()

    async def check_once(self) -> CheckResult:
        if not self.settings.telegram_user_id:
            raise RuntimeError("Не задан TELEGRAM_USER_ID")

        async with self._check_lock:
            items = await self.feed_client.fetch()
            self.database.set_state("last_check", datetime.now(timezone.utc).isoformat())
            self.database.set_state("last_error", "")

            initialized = self.database.get_bool("feed_initialized", default=False)
            initialized_url = self.database.get_state("initialized_rss_url")
            feed_changed = initialized_url is not None and initialized_url != self.settings.rss_url
            legacy_database = initialized and initialized_url is None

            if not initialized or feed_changed or legacy_database:
                self.database.mark_many_seen(items)
                self.database.set_bool("feed_initialized", True)
                self.database.set_state("initialized_rss_url", self.settings.rss_url)
                self.database.set_state("last_new_count", "0")
                reason = "смена RSS-ленты" if feed_changed or legacy_database else "первичная инициализация"
                logger.info("%s: сохранено %s записей", reason.capitalize(), len(items))
                return CheckResult(fetched=len(items), sent=0, initialized=True)

            new_items = [item for item in items if not self.database.has_seen(item.uid)]
            new_items.sort(key=lambda item: item.published_at or datetime.min.replace(tzinfo=timezone.utc))

            sent = 0
            for item in new_items:
                await self._send_item(item)
                self.database.mark_seen(item)
                sent += 1
                await asyncio.sleep(0.35)

            self.database.set_state("last_new_count", str(sent))
            if sent:
                logger.info("Отправлено новых заказов: %s", sent)
            return CheckResult(fetched=len(items), sent=sent)

    async def _send_item(self, item: FeedItem) -> None:
        assert self.settings.telegram_user_id is not None
        text = format_item(
            item,
            timezone=self.settings.timezone,
            description_limit=self.settings.max_description_length,
        )
        kwargs = {
            "chat_id": self.settings.telegram_user_id,
            "text": text,
            "reply_markup": item_keyboard(item),
            "link_preview_options": LinkPreviewOptions(is_disabled=True),
        }
        try:
            await self.bot.send_message(**kwargs)
        except TelegramRetryAfter as exc:
            logger.warning("Telegram FloodWait: ждём %s сек.", exc.retry_after)
            await asyncio.sleep(exc.retry_after + 1)
            await self.bot.send_message(**kwargs)
