from __future__ import annotations

import html
from datetime import datetime

from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

from .config import Settings
from .database import Database
from .monitor import FeedMonitor


def build_router(settings: Settings, database: Database, monitor: FeedMonitor) -> Router:
    router = Router()

    def is_owner(message: Message) -> bool:
        return bool(
            settings.telegram_user_id
            and message.from_user
            and message.from_user.id == settings.telegram_user_id
        )

    async def deny_or_show_id(message: Message) -> None:
        user_id = message.from_user.id if message.from_user else message.chat.id
        if settings.telegram_user_id is None:
            await message.answer(
                "Бот пока не привязан к владельцу.\n\n"
                f"Ваш Telegram ID: <code>{user_id}</code>\n\n"
                "Впишите его в <code>TELEGRAM_USER_ID</code> файла <code>.env</code> "
                "и перезапустите бота."
            )
        else:
            await message.answer("⛔️ У вас нет доступа к этому боту.")

    @router.message(CommandStart())
    async def start(message: Message) -> None:
        if not is_owner(message):
            await deny_or_show_id(message)
            return
        await message.answer(
            "👋 <b>Монитор заказов FL.ru запущен</b>\n\n"
            "Я отслеживаю все новые заказы в категории «Программирование» на FL.ru и присылаю их сюда.\n\n"
            "Команды:\n"
            "/status — состояние бота\n"
            "/check — проверить ленту сейчас\n"
            "/pause — остановить уведомления\n"
            "/resume — возобновить уведомления"
        )

    @router.message(Command("status"))
    async def status(message: Message) -> None:
        if not is_owner(message):
            await deny_or_show_id(message)
            return

        last_check = _format_iso(database.get_state("last_check"), settings)
        last_error = database.get_state("last_error") or "нет"
        state = "⏸ приостановлен" if monitor.is_paused else "✅ работает"
        initialized = "да" if database.get_bool("feed_initialized") else "нет"

        await message.answer(
            f"<b>Статус:</b> {state}\n"
            f"<b>Интервал:</b> {settings.check_interval_seconds} сек.\n"
            f"<b>RSS:</b> <code>{html.escape(settings.rss_url)}</code>\n"
            f"<b>Лента инициализирована:</b> {initialized}\n"
            f"<b>Сохранено заказов:</b> {database.seen_count()}\n"
            f"<b>Последняя проверка:</b> {last_check}\n"
            f"<b>Последняя ошибка:</b> {html.escape(last_error[:500])}"
        )

    @router.message(Command("pause"))
    async def pause(message: Message) -> None:
        if not is_owner(message):
            await deny_or_show_id(message)
            return
        monitor.pause()
        await message.answer("⏸ Уведомления приостановлены.")

    @router.message(Command("resume"))
    async def resume(message: Message) -> None:
        if not is_owner(message):
            await deny_or_show_id(message)
            return
        monitor.resume()
        await message.answer("▶️ Уведомления возобновлены.")

    @router.message(Command("check"))
    async def check(message: Message) -> None:
        if not is_owner(message):
            await deny_or_show_id(message)
            return
        waiting = await message.answer("🔄 Проверяю RSS-ленту…")
        try:
            result = await monitor.check_once()
        except Exception as exc:  # noqa: BLE001
            database.set_state("last_error", str(exc)[:1000])
            await waiting.edit_text(f"❌ Ошибка проверки: {html.escape(str(exc))}")
            return

        if result.initialized:
            text = (
                f"✅ Лента инициализирована. Запомнено записей: {result.fetched}.\n"
                "Старые заказы не отправлены; дальше придут только новые.\n"
                "Это также происходит один раз после смены RSS-адреса."
            )
        elif result.sent:
            text = f"✅ Проверено записей: {result.fetched}. Отправлено новых: {result.sent}."
        else:
            text = f"✅ Проверено записей: {result.fetched}. Новых заказов нет."
        await waiting.edit_text(text)

    return router


def _format_iso(value: str | None, settings: Settings) -> str:
    if not value:
        return "ещё не выполнялась"
    try:
        parsed = datetime.fromisoformat(value)
        return parsed.astimezone(settings.timezone).strftime("%d.%m.%Y в %H:%M:%S")
    except ValueError:
        return value
