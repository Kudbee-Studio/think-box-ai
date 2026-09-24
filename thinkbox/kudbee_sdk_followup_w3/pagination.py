"""Pagination helpers for wave 3 SDK (PR #191 F08)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class Page(Generic[T]):
    items: tuple[T, ...]
    next_cursor: str | None


def iter_pages(
    fetch: Callable[[str | None], Page[T]],
    max_pages: int = 50,
) -> tuple[T, ...]:
    out: list[T] = []
    cursor: str | None = None
    for _ in range(max_pages):
        page = fetch(cursor)
        out.extend(page.items)
        if not page.next_cursor:
            break
        cursor = page.next_cursor
    return tuple(out)


def filter_items(page: Page[T], predicate: Callable[[T], bool]) -> Page[T]:
    return Page(items=tuple(i for i in page.items if predicate(i)), next_cursor=page.next_cursor)
