"""Context window management for Think Box AI.

Implements sliding window context management to handle large conversations
within model token limits. Production-grade with LRU caching.
"""

from __future__ import annotations

import collections
import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Any

# Note: We avoid importing from core.providers to prevent layer violations.
# Message is a simple dataclass defined locally for context management.
@dataclass
class Message:
    role: str
    content: str


@dataclass
class ContextWindow:
    """Sliding window context for a conversation session."""

    session_id: str
    max_tokens: int = 4096
    messages: list[Message] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def add_message(self, role: str, content: str) -> None:
        """Add a message, evicting oldest if over limit."""
        self.messages.append(Message(role=role, content=content))
        self.updated_at = time.time()
        self._trim_to_limit()

    def _trim_to_limit(self) -> None:
        """Trim messages to stay within token budget."""
        while self._estimate_tokens() > self.max_tokens and len(self.messages) > 1:
            self.messages.pop(0)

    def _estimate_tokens(self) -> int:
        """Rough token estimation (4 chars per token)."""
        total_chars = sum(len(m.content) for m in self.messages)
        return total_chars // 4

    def to_messages(self) -> list[Message]:
        """Return current messages."""
        return list(self.messages)

    def summary(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "message_count": len(self.messages),
            "estimated_tokens": self._estimate_tokens(),
            "max_tokens": self.max_tokens,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class LRUCache:
    """Least Recently Used cache with TTL support."""

    def __init__(self, max_size: int = 128, ttl_seconds: float = 300.0) -> None:
        self._max_size = max_size
        self._ttl = ttl_seconds
        self._cache: dict[str, tuple[Any, float]] = {}
        self._access_order: collections.deque[str] = collections.deque()

    def get(self, key: str) -> Any | None:
        """Get value from cache. Returns None if expired or missing."""
        if key not in self._cache:
            return None
        value, timestamp = self._cache[key]
        if time.time() - timestamp > self._ttl:
            del self._cache[key]
            return None
        # Update access order
        if key in self._access_order:
            self._access_order.remove(key)
        self._access_order.append(key)
        return value

    def put(self, key: str, value: Any) -> None:
        """Put value in cache, evicting LRU if at capacity."""
        if key in self._cache:
            self._access_order.remove(key)
        elif len(self._cache) >= self._max_size:
            # Evict least recently used
            if self._access_order:
                evict_key = self._access_order.popleft()
                self._cache.pop(evict_key, None)

        self._cache[key] = (value, time.time())
        self._access_order.append(key)

    def invalidate(self, key: str) -> None:
        """Remove key from cache."""
        self._cache.pop(key, None)
        if key in self._access_order:
            self._access_order.remove(key)

    def clear(self) -> None:
        """Clear all cached values."""
        self._cache.clear()
        self._access_order.clear()

    @property
    def size(self) -> int:
        return len(self._cache)


class ContextManager:
    """Manages multiple context windows with caching."""

    def __init__(self, max_sessions: int = 100, window_size: int = 4096) -> None:
        self._windows: dict[str, ContextWindow] = {}
        self._max_sessions = max_sessions
        self._window_size = window_size
        self._response_cache = LRUCache(max_size=256, ttl_seconds=600)

    def get_or_create(self, session_id: str) -> ContextWindow:
        """Get existing context or create new one."""
        if session_id not in self._windows:
            self._evict_if_needed()
            self._windows[session_id] = ContextWindow(
                session_id=session_id,
                max_tokens=self._window_size,
            )
        return self._windows[session_id]

    def add_message(self, session_id: str, role: str, content: str) -> ContextWindow:
        """Add message to a session's context window."""
        window = self.get_or_create(session_id)
        window.add_message(role, content)
        return window

    def get_cached_response(self, prompt_hash: str) -> Any | None:
        """Check if a response is cached."""
        return self._response_cache.get(prompt_hash)

    def cache_response(self, prompt_hash: str, response: Any) -> None:
        """Cache a response."""
        self._response_cache.put(prompt_hash, response)

    def _evict_if_needed(self) -> None:
        """Evict oldest session if at capacity."""
        if len(self._windows) >= self._max_sessions:
            oldest_key = min(self._windows, key=lambda k: self._windows[k].updated_at)
            del self._windows[oldest_key]

    def hash_prompt(self, messages: list[Message]) -> str:
        """Create deterministic hash for prompt caching."""
        payload = json.dumps(
            [{"role": m.role, "content": m.content} for m in messages],
            sort_keys=True,
        )
        return hashlib.sha256(payload.encode()).hexdigest()[:16]

    def stats(self) -> dict[str, Any]:
        """Return manager statistics."""
        return {
            "active_sessions": len(self._windows),
            "max_sessions": self._max_sessions,
            "cache_size": self._response_cache.size,
            "total_messages": sum(len(w.messages) for w in self._windows.values()),
        }


# Global instance
_context_manager: ContextManager | None = None


def get_context_manager() -> ContextManager:
    """Get or create global context manager."""
    global _context_manager
    if _context_manager is None:
        _context_manager = ContextManager()
    return _context_manager
