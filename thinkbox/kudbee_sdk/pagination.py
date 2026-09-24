"""Cursor pagination helpers (PR #177 F09)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterator


@dataclass(frozen=True)
class Page:
    items: tuple[Any, ...]
    next_cursor: str | None


def iter_pages(
    fetch_page: Any,
    *,
    start_cursor: str | None = None,
    max_pages: int = 100,
) -> Iterator[Page]:
    cursor = start_cursor
    for _ in range(max_pages):
        page: Page = fetch_page(cursor)
        yield page
        if not page.next_cursor:
            break
        cursor = page.next_cursor
