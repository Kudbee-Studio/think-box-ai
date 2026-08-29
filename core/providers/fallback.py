"""Provider fallback chain with automatic failover."""

from __future__ import annotations
import asyncio
import logging
from typing import AsyncGenerator, Any, List, Tuple
from core.providers.base import BaseProvider, CompletionResponse, Message, ProviderRegistry
from core.foundation.error_codes import ErrorCode, format_error_response
from core.foundation.errors import ProviderError, ProviderUnavailableError

logger = logging.getLogger(__name__)


class FallbackProvider(BaseProvider):
    """Executes provider requests sequentially across a fallback hierarchy.
    
    Time Complexity: O(P) where P is the number of initialized providers.
    Space Complexity: O(1) auxiliary overhead.
    """

    def __init__(self, provider_names: List[str], config: dict[str, Any]) -> None:
        super().__init__(config)
        self._providers: List[Tuple[str, BaseProvider]] = []
        
        for name in provider_names:
            provider_cls = ProviderRegistry.get(name)
            if provider_cls is None:
                logger.warning("Provider '%s' missing from ProviderRegistry; skipping.", name)
                continue
            self._providers.append((name, provider_cls(config)))
            
        if not self._providers:
            raise ProviderError(
                format_error_response(
                    ErrorCode.PROVIDER_NOT_FOUND,
                    "No valid providers available in fallback sequence."
                )["message"]
            )

    async def complete(self, messages: List[Message], **kwargs: Any) -> CompletionResponse:
        """Iterates through registered providers until a valid response is returned."""
        last_exception: Exception | None = None
        
        for name, provider in self._providers:
            try:
                logger.info("Routing request to primary/fallback provider: %s", name)
                return await provider.complete(messages, **kwargs)
            except Exception as exc:
                logger.warning("Provider '%s' failed: %s", name, str(exc))
                last_exception = exc
                continue
        
        raise ProviderUnavailableError(
            format_error_response(
                ErrorCode.PROVIDER_UNAVAILABLE,
                f"All providers failed. Last error: {last_exception}",
                providers=[name for name, _ in self._providers]
            )["message"]
        )

    async def stream(self, messages: List[Message], **kwargs: Any) -> AsyncGenerator[str, None]:
        """Streams from first available provider."""
        for name, provider in self._providers:
            try:
                async for token in provider.stream(messages, **kwargs):
                    yield token
                return
            except Exception as exc:
                logger.warning("Provider '%s' stream failed: %s", name, str(exc))
                continue
        
        raise ProviderUnavailableError("All providers failed to stream")
