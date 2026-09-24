"""Pagination helpers for wave LR-energy deepen SDK (PR #193 F08)."""

from __future__ import annotations

import base64
import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Generic, TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class Page(Generic[T]):
    items: tuple[T, ...]
    next_cursor: str | None


def encode_cursor(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii")


def decode_cursor(cursor: str) -> dict[str, Any]:
    raw = base64.urlsafe_b64decode(cursor.encode("ascii"))
    doc = json.loads(raw.decode("utf-8"))
    if not isinstance(doc, dict):
        raise ValueError("cursor payload must be an object")
    return doc


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
