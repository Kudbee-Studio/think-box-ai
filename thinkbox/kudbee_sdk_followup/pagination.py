"""Cursor pagination helpers (PR #179 F09)."""

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


def filter_items(page: Page, predicate: Any) -> Page:
    kept = tuple(item for item in page.items if predicate(item))
    return Page(items=kept, next_cursor=page.next_cursor)


def batch_collect(fetch_page: Any, *, max_items: int = 500, max_pages: int = 50) -> tuple[Any, ...]:
    out: list[Any] = []
    for page in iter_pages(fetch_page, max_pages=max_pages):
        out.extend(page.items)
        if len(out) >= max_items:
            return tuple(out[:max_items])
    return tuple(out)
