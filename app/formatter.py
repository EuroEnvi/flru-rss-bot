from __future__ import annotations

import html
from zoneinfo import ZoneInfo

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from .models import FeedItem
from .text import truncate


def format_item(item: FeedItem, timezone: ZoneInfo, description_limit: int) -> str:
    parts = ["🆕 <b>Новый заказ на FL.ru</b>", "", f"<b>{html.escape(item.title)}</b>"]

    if item.budget:
        parts.extend(["", f"💰 <b>Бюджет:</b> {html.escape(item.budget)}"])

    if item.published_at:
        local_dt = item.published_at.astimezone(timezone)
        parts.append(f"🕒 <b>Опубликован:</b> {local_dt:%d.%m.%Y в %H:%M}")

    description = truncate(item.description, description_limit)
    if description:
        parts.extend(["", html.escape(description)])

    return "\n".join(parts)


def item_keyboard(item: FeedItem) -> InlineKeyboardMarkup | None:
    if not item.link:
        return None
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Открыть заказ", url=item.link)]
        ]
    )
