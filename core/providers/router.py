"""Provider router with multi-provider routing and failover."""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any

from core.providers.base import CompletionResponse, Message, ProviderRegistry
from core.providers.snapshot import snapshot_hash


class SnapshotCache:
    """Persistent snapshot cache using SQLite for cross-process dedup."""

    def __init__(self, db_path: str, ttl: float = 3600.0) -> None:
        import sqlite3
        self._db_path = db_path
        self._ttl = ttl
        self._init_db()

    def _init_db(self) -> None:
        import sqlite3
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS snapshot_cache (
                    key TEXT PRIMARY KEY,
                    response TEXT NOT NULL,
                    created_at REAL NOT NULL
                )
            """)

    def get(self, key: str) -> CompletionResponse | None:
        import sqlite3
        with sqlite3.connect(self._db_path) as conn:
            row = conn.execute(
                "SELECT response, created_at FROM snapshot_cache WHERE key = ?",
                (key,),
            ).fetchone()
            if row is None:
                return None
            if time.time() - row[1] > self._ttl:
                conn.execute("DELETE FROM snapshot_cache WHERE key = ?", (key,))
                conn.commit()
                return None
            data = json.loads(row[0])
            return CompletionResponse(**data)

    def put(self, key: str, response: CompletionResponse) -> None:
        import sqlite3
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO snapshot_cache (key, response, created_at) VALUES (?, ?, ?)",
                (key, json.dumps(response.__dict__), time.time()),
            )
            conn.commit()

    def clear(self) -> None:
        import sqlite3
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("DELETE FROM snapshot_cache")


class ProviderRouter:
    """Routes completion requests across multiple providers with failover.

    Configuration:
        providers: list of {name, api_key, model, base_url}
        order: priority order (first wins on success)
        snapshot_cache: if True, skip model call when input unchanged
    """

    def __init__(self, config: dict[str, Any]) -> None:
        self._providers: list[dict[str, Any]] = config.get("providers", [])
        self._order: list[str] = config.get("order", [p["name"] for p in self._providers])
        self._snapshot_cache: bool = config.get("snapshot_cache", False)
        self._cache: dict[str, CompletionResponse] = {}
        self._persistent_cache: SnapshotCache | None = None
        if config.get("persistent_cache_path"):
            self._persistent_cache = SnapshotCache(
                config["persistent_cache_path"],
                ttl=config.get("cache_ttl", 3600.0),
            )

    def _get_provider(self, name: str):
        cls = ProviderRegistry.get(name)
        if cls is None:
            raise ValueError(f"Unknown provider: {name}")
        provider_config = next(
            (p for p in self._providers if p["name"] == name), {}
        )
        return cls(provider_config)

    async def complete(self, messages: list[Message], **kwargs: Any) -> CompletionResponse:
        key = snapshot_hash(
            [{"role": m.role, "content": m.content} for m in messages],
            **kwargs,
        )

        if self._snapshot_cache and key in self._cache:
            return self._cache[key]

        if self._persistent_cache is not None:
            cached = self._persistent_cache.get(key)
            if cached is not None:
                return cached

        last_error: Exception | None = None
        for name in self._order:
            try:
                provider = self._get_provider(name)
                result = await provider.complete(messages, **kwargs)
                if self._snapshot_cache:
                    self._cache[key] = result
                if self._persistent_cache is not None:
                    self._persistent_cache.put(key, result)
                return result
            except Exception as e:
                last_error = e
                continue

        raise RuntimeError(f"All providers failed: {last_error}") from last_error

    def list_available(self) -> list[str]:
        return [n for n in self._order if ProviderRegistry.get(n) is not None]

    def clear_cache(self) -> None:
        self._cache.clear()
        if self._persistent_cache is not None:
            self._persistent_cache.clear()
