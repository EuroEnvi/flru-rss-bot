from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dotenv import load_dotenv

DEFAULT_RSS_URL = "https://www.fl.ru/rss/?category=5"


@dataclass(frozen=True, slots=True)
class Settings:
    bot_token: str
    telegram_user_id: int | None
    rss_url: str
    check_interval_seconds: int
    database_path: Path
    timezone: ZoneInfo
    max_description_length: int
    request_timeout_seconds: float
    log_level: str


def _optional_int(value: str | None) -> int | None:
    if value is None or not value.strip():
        return None
    parsed = int(value.strip())
    return parsed if parsed > 0 else None


def load_settings() -> Settings:
    load_dotenv()

    bot_token = os.getenv("BOT_TOKEN", "").strip()
    if not bot_token:
        raise RuntimeError("Не задан BOT_TOKEN в файле .env")

    interval = int(os.getenv("CHECK_INTERVAL_SECONDS", "120"))
    if interval < 30:
        raise RuntimeError("CHECK_INTERVAL_SECONDS не должен быть меньше 30 секунд")

    max_description_length = int(os.getenv("MAX_DESCRIPTION_LENGTH", "1400"))
    if not 200 <= max_description_length <= 3000:
        raise RuntimeError("MAX_DESCRIPTION_LENGTH должен быть от 200 до 3000")

    timezone_name = os.getenv("TIMEZONE", "Europe/Moscow").strip() or "Europe/Moscow"
    try:
        timezone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc:
        raise RuntimeError(f"Неизвестный часовой пояс: {timezone_name}") from exc

    database_path = Path(os.getenv("DATABASE_PATH", "data/bot.db")).expanduser()

    return Settings(
        bot_token=bot_token,
        telegram_user_id=_optional_int(os.getenv("TELEGRAM_USER_ID")),
        rss_url=os.getenv("RSS_URL", DEFAULT_RSS_URL).strip() or DEFAULT_RSS_URL,
        check_interval_seconds=interval,
        database_path=database_path,
        timezone=timezone,
        max_description_length=max_description_length,
        request_timeout_seconds=float(os.getenv("REQUEST_TIMEOUT_SECONDS", "25")),
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
    )
