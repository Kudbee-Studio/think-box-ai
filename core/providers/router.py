"""Provider router with multi-provider routing and failover."""

from __future__ import annotations

import asyncio
from typing import Any

from core.providers.base import CompletionResponse, Message, ProviderRegistry
from core.providers.snapshot import snapshot_hash


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

        last_error: Exception | None = None
        for name in self._order:
            try:
                provider = self._get_provider(name)
                result = await provider.complete(messages, **kwargs)
                if self._snapshot_cache:
                    self._cache[key] = result
                return result
            except Exception as e:
                last_error = e
                continue

        raise RuntimeError(f"All providers failed: {last_error}") from last_error

    def list_available(self) -> list[str]:
        return [n for n in self._order if ProviderRegistry.get(n) is not None]

    def clear_cache(self) -> None:
        self._cache.clear()
