from __future__ import annotations

import html
import re
from html.parser import HTMLParser

_SPACE_RE = re.compile(r"[ \t\r\f\v]+")
_BLANK_LINES_RE = re.compile(r"\n{3,}")
_BUDGET_PATTERNS = (
    re.compile(r"(?im)^(?:бюджет|стоимость|цена)\s*:?\s*(.{1,120})$"),
    re.compile(
        r"(?i)(?:бюджет|стоимость|цена)\s*:?\s*"
        r"((?:до\s+|от\s+)?[\d\s.,]+\s*(?:₽|руб(?:\.|лей|ля)?|RUB))"
    ),
)


class _HTMLToTextParser(HTMLParser):
    BLOCK_TAGS = {
        "br", "p", "div", "li", "ul", "ol", "section", "article",
        "tr", "h1", "h2", "h3", "h4",
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in self.BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in self.BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        self.parts.append(data)

    def get_text(self) -> str:
        return "".join(self.parts)


def html_to_text(value: str | None) -> str:
    if not value:
        return ""
    parser = _HTMLToTextParser()
    try:
        parser.feed(value)
        raw = parser.get_text()
    except Exception:
        raw = re.sub(r"<[^>]+>", " ", value)

    raw = html.unescape(raw).replace("\xa0", " ")
    lines = [_SPACE_RE.sub(" ", line).strip() for line in raw.splitlines()]
    cleaned = "\n".join(line for line in lines if line)
    return _BLANK_LINES_RE.sub("\n\n", cleaned).strip()


def extract_budget(*values: str) -> str | None:
    combined = "\n".join(value for value in values if value)
    for pattern in _BUDGET_PATTERNS:
        match = pattern.search(combined)
        if not match:
            continue
        value = _SPACE_RE.sub(" ", match.group(1)).strip(" .;|-")
        if value:
            return value[:120]
    return None


def truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    shortened = text[: max(0, limit - 1)].rstrip()
    last_space = shortened.rfind(" ")
    if last_space > limit * 0.75:
        shortened = shortened[:last_space]
    return shortened.rstrip(".,;:-") + "…"
