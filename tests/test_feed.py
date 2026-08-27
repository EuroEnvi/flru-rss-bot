from __future__ import annotations

import feedparser

from app.feed import FeedClient
from app.text import extract_budget, html_to_text, truncate

SAMPLE_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>FL.ru</title>
    <item>
      <guid>order-123</guid>
      <title><![CDATA[Сделать Telegram-бота]]></title>
      <link>https://www.fl.ru/projects/123/example.html</link>
      <description><![CDATA[
        <p>Нужно собрать бота.</p><p><b>Бюджет: 25 000 руб.</b></p>
      ]]></description>
      <pubDate>Thu, 27 Aug 2026 21:15:00 +0300</pubDate>
    </item>
  </channel>
</rss>
""".encode("utf-8")


def test_html_to_text() -> None:
    assert html_to_text("<p>Первая</p><p>Вторая&nbsp;строка</p>") == "Первая\nВторая строка"


def test_extract_budget() -> None:
    assert extract_budget("", "Бюджет: 25 000 руб.") == "25 000 руб"


def test_parse_entry() -> None:
    parsed = feedparser.parse(SAMPLE_RSS)
    item = FeedClient._parse_entry(parsed.entries[0])
    assert item.uid == "order-123"
    assert item.title == "Сделать Telegram-бота"
    assert item.budget == "25 000 руб"
    assert "Нужно собрать бота" in item.description
    assert item.link.endswith("example.html")
    assert item.published_at is not None


def test_truncate() -> None:
    assert truncate("коротко", 20) == "коротко"
    assert truncate("очень длинная строка для проверки", 15).endswith("…")
