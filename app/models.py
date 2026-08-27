from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class FeedItem:
    uid: str
    title: str
    link: str
    description: str
    budget: str | None
    published_at: datetime | None


@dataclass(frozen=True, slots=True)
class CheckResult:
    fetched: int
    sent: int
    initialized: bool = False
