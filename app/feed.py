from __future__ import annotations

import calendar
import hashlib
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any

import feedparser
import httpx

from .models import FeedItem
from .text import extract_budget, html_to_text


class FeedError(RuntimeError):
    pass


class FeedClient:
    def __init__(self, url: str, timeout_seconds: float = 25.0) -> None:
        self.url = url
        self.timeout_seconds = timeout_seconds

    async def fetch(self) -> list[FeedItem]:
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; FLruRSSBot/1.0; +https://t.me/)",
            "Accept": "application/rss+xml, application/xml, text/xml, */*",
        }
        timeout = httpx.Timeout(self.timeout_seconds)
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=timeout,
            headers=headers,
        ) as client:
            try:
                response = await client.get(self.url)
                response.raise_for_status()
            except httpx.HTTPError as exc:
                raise FeedError(f"Ошибка загрузки RSS: {exc}") from exc

        parsed = feedparser.parse(response.content)
        entries = list(parsed.entries)
        if parsed.bozo and not entries:
            error = getattr(parsed, "bozo_exception", "неизвестная ошибка XML")
            raise FeedError(f"Не удалось разобрать RSS: {error}")
        if not entries:
            raise FeedError("RSS-лента вернула 0 записей")

        items = [self._parse_entry(entry) for entry in entries]
        return [item for item in items if item.title or item.link]

    @staticmethod
    def _parse_entry(entry: Any) -> FeedItem:
        title = html_to_text(str(entry.get("title", ""))) or "Новый заказ"
        link = str(entry.get("link", "")).strip()

        content = entry.get("content") or []
        content_value = content[0].get("value", "") if content else ""
        raw_description = str(
            entry.get("summary")
            or entry.get("description")
            or content_value
        )
        description = html_to_text(raw_description)
        budget = extract_budget(title, description)
        published_at = _entry_datetime(entry)

        source_uid = str(entry.get("id") or entry.get("guid") or link).strip()
        if not source_uid:
            fingerprint = "\n".join(
                [title, link, description, published_at.isoformat() if published_at else ""]
            )
            source_uid = hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()

        return FeedItem(
            uid=source_uid,
            title=title,
            link=link,
            description=description,
            budget=budget,
            published_at=published_at,
        )


def _entry_datetime(entry: Any) -> datetime | None:
    structured = entry.get("published_parsed") or entry.get("updated_parsed")
    if structured:
        try:
            return datetime.fromtimestamp(calendar.timegm(structured), tz=timezone.utc)
        except (TypeError, ValueError, OverflowError):
            pass

    raw = str(entry.get("published") or entry.get("updated") or "").strip()
    if not raw:
        return None
    try:
        parsed = parsedate_to_datetime(raw)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except (TypeError, ValueError, OverflowError):
        return None
