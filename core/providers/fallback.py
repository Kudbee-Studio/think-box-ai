"""Provider fallback chain with circuit breaker protection."""

from __future__ import annotations
import logging
from typing import AsyncGenerator, Any, List, Tuple
from core.providers.base import ModelProvider, CompletionResponse, Message, ProviderRegistry
from core.providers.circuit_breaker import CircuitBreakerRegistry
from core.foundation.error_codes import ErrorCode, format_error_response
from core.foundation.errors import ProviderError, ProviderUnavailableError

logger = logging.getLogger(__name__)


class FallbackProvider(ModelProvider):
    """Executes provider requests sequentially across a fallback hierarchy with circuit breaker.
    
    Time Complexity: O(P) where P is the number of initialized providers.
    Space Complexity: O(P) for circuit breaker instances.
    """

    def __init__(self, provider_names: List[str], config: dict[str, Any]) -> None:
        super().__init__(config)
        self._providers: List[Tuple[str, ModelProvider]] = []
        self._breakers: dict[str, Any] = {}
        
        for name in provider_names:
            provider_cls = ProviderRegistry.get(name)
            if provider_cls is None:
                logger.warning("Provider '%s' missing from ProviderRegistry; skipping.", name)
                continue
            self._providers.append((name, provider_cls(config)))
            self._breakers[name] = CircuitBreakerRegistry.get(name)
            
        if not self._providers:
            raise ProviderError(
                format_error_response(
                    ErrorCode.PROVIDER_NOT_FOUND,
                    "No valid providers available in fallback sequence."
                )["message"]
            )

    async def complete(self, messages: List[Message], **kwargs: Any) -> CompletionResponse:
        """Iterates through providers with circuit breaker protection."""
        last_exception: Exception | None = None
        
        for name, provider in self._providers:
            breaker = self._breakers[name]
            try:
                logger.info("Routing request to provider: %s (circuit: %s)", name, breaker.state.value)
                return await breaker.call(provider.complete, messages, **kwargs)
            except Exception as exc:
                logger.warning("Provider '%s' failed: %s", name, str(exc))
                last_exception = exc
                continue
        
        raise ProviderUnavailableError(
            format_error_response(
                ErrorCode.PROVIDER_UNAVAILABLE,
                f"All providers failed. Last error: {last_exception}",
                providers=[name for name, _ in self._providers],
                circuits=CircuitBreakerRegistry.get_all(),
            )["message"]
        )

    async def stream(self, messages: List[Message], **kwargs: Any) -> AsyncGenerator[str, None]:
        """Streams from first available provider with circuit breaker."""
        for name, provider in self._providers:
            breaker = self._breakers[name]
            try:
                if not breaker.allow_request():
                    logger.info("Circuit open for '%s', skipping.", name)
                    continue
                async for token in provider.stream(messages, **kwargs):
                    yield token
                breaker.record_success()
                return
            except Exception as exc:
                breaker.record_failure()
                logger.warning("Provider '%s' stream failed: %s", name, str(exc))
                continue
        
        raise ProviderUnavailableError("All providers failed to stream")

    def get_circuit_status(self) -> dict[str, Any]:
        """Return circuit breaker status for all providers."""
        return CircuitBreakerRegistry.get_all()
