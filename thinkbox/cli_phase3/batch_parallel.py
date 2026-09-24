"""Bounded batch / parallel hermetic operators (PR #180 F18)."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class BatchItemResult:
    key: str
    ok: bool
    value: Any


@dataclass(frozen=True)
class BatchRunResult:
    results: tuple[BatchItemResult, ...]
    ok_count: int
    fail_count: int


def run_batch_bounded(
    items: dict[str, str],
    worker: Callable[[str], Any],
    max_workers: int,
) -> BatchRunResult:
    if max_workers < 1:
        max_workers = 1
    if max_workers > 16:
        max_workers = 16
    results: list[BatchItemResult] = []
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(worker, v): k for k, v in items.items()}
        for fut in as_completed(futures):
            key = futures[fut]
            try:
                val = fut.result()
                results.append(BatchItemResult(key=key, ok=True, value=val))
            except Exception as exc:  # noqa: BLE001
                results.append(BatchItemResult(key=key, ok=False, value=str(exc)))
    ok_count = sum(1 for r in results if r.ok)
    return BatchRunResult(
        results=tuple(sorted(results, key=lambda r: r.key)),
        ok_count=ok_count,
        fail_count=len(results) - ok_count,
    )
