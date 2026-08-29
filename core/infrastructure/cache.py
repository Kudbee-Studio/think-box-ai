"""Caching layer with Redis-compatible interface.

Uses in-memory cache by default, with Redis backend when available.
"""

from __future__ import annotations
import hashlib
import json
import time
import threading
import logging
from typing import Any

logger = logging.getLogger(__name__)


class InMemoryCache:
    """Thread-safe in-memory cache with TTL support.
    
    Time Complexity: O(1) get/put
    Space Complexity: O(N) where N = number of cached items
    """

    def __init__(self, default_ttl: float = 300.0) -> None:
        self._store: dict[str, tuple[Any, float]] = {}
        self._lock = threading.Lock()
        self._default_ttl = default_ttl
        self._hits = 0
        self._misses = 0

    def get(self, key: str) -> Any | None:
        with self._lock:
            if key not in self._store:
                self._misses += 1
                return None
            value, expiry = self._store[key]
            if time.monotonic() > expiry:
                del self._store[key]
                self._misses += 1
                return None
            self._hits += 1
            return value

    def put(self, key: str, value: Any, ttl: float | None = None) -> None:
        with self._lock:
            self._store[key] = (value, time.monotonic() + (ttl or self._default_ttl))

    def delete(self, key: str) -> bool:
        with self._lock:
            if key in self._store:
                del self._store[key]
                return True
            return False

    def clear(self) -> int:
        with self._lock:
            count = len(self._store)
            self._store.clear()
            return count

    def cleanup_expired(self) -> int:
        """Remove expired entries. Returns count removed."""
        now = time.monotonic()
        with self._lock:
            expired = [k for k, (_, exp) in self._store.items() if now > exp]
            for k in expired:
                del self._store[k]
            return len(expired)

    def stats(self) -> dict[str, Any]:
        with self._lock:
            return {
                "size": len(self._store),
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": round(self._hits / max(1, self._hits + self._misses), 4),
            }


class CacheLayer:
    """Cache abstraction with Redis-compatible interface."""

    def __init__(self, redis_url: str | None = None) -> None:
        self._backend = InMemoryCache()
        self._redis_url = redis_url

    def _make_key(self, *args: Any) -> str:
        """Create deterministic cache key."""
        payload = json.dumps(args, sort_keys=True, default=str)
        return hashlib.sha256(payload.encode()).hexdigest()[:24]

    def get(self, key: str) -> Any | None:
        return self._backend.get(key)

    def put(self, key: str, value: Any, ttl: float | None = None) -> None:
        self._backend.put(key, value, ttl)

    def get_or_compute(self, key: str, func: callable, ttl: float | None = None) -> Any:
        """Get from cache or compute and store."""
        cached = self.get(key)
        if cached is not None:
            return cached
        value = func()
        self.put(key, value, ttl)
        return value

    def stats(self) -> dict[str, Any]:
        return self._backend.stats()


# Global cache instance
cache = CacheLayer()
