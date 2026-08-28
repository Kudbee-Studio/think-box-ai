"""Ollama provider using stdlib urllib and async to_thread."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from core.foundation.errors import ProviderError, ProviderRateLimitError, ProviderUnavailableError
from core.providers.base import CompletionResponse, Message, ModelProvider, ProviderCapabilities, ProviderRegistry


@ProviderRegistry.register("ollama")
class OllamaProvider:
    def __init__(self, config: dict[str, Any]) -> None:
        self._base_url = config.get("base_url", "http://localhost:11434")
        self._model = config.get("model", "llama3")
        self.capabilities = ProviderCapabilities(
            completion=True,
            streaming=False,
            embedding=False,
            supports_system_prompt=True,
        )

    async def complete(self, messages: list[Message], **kwargs: Any) -> CompletionResponse:
        payload = {
            "model": self._model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": False,
            "options": {
                "temperature": kwargs.get("temperature", 0.7),
                "num_predict": kwargs.get("max_tokens", 4096),
            },
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{self._base_url}/api/chat",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        def _fetch() -> CompletionResponse:
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    if not 200 <= resp.status < 300:
                        raise ProviderError(message=f"HTTP {resp.status}")
                    body = json.loads(resp.read().decode("utf-8"))
                    msg = body.get("message", {})
                    return CompletionResponse(
                        content=msg.get("content", ""),
                        model=body.get("model", self._model),
                        usage=body.get("usage", {}),
                    )
            except urllib.error.HTTPError as e:
                if e.code == 429:
                    raise ProviderRateLimitError() from e
                elif e.code == 401:
                    raise ProviderUnavailableError() from e
                else:
                    raise ProviderError(message=f"HTTP {e.code}") from e
            except urllib.error.URLError as e:
                raise ProviderUnavailableError() from e

        return await __import__('asyncio').to_thread(_fetch)

    async def list_models(self) -> list[dict[str, Any]]:
        req = urllib.request.Request(
            f"{self._base_url}/api/tags",
            method="GET",
        )

        def _fetch() -> list[dict[str, Any]]:
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    if not 200 <= resp.status < 300:
                        raise ProviderError(message=f"HTTP {resp.status}")
                    data = json.loads(resp.read().decode("utf-8"))
                    return data.get("models", [])
            except urllib.error.HTTPError as e:
                if e.code == 429:
                    raise ProviderRateLimitError() from e
                elif e.code == 401:
                    raise ProviderUnavailableError() from e
                else:
                    raise ProviderError(message=f"HTTP {e.code}") from e
            except urllib.error.URLError as e:
                raise ProviderUnavailableError() from e

        return await __import__('asyncio').to_thread(_fetch)

    async def stream(self, messages: list[Message], **kwargs: Any):
        raise NotImplementedError("Streaming not supported for OllamaProvider")

    async def embed(self, texts: list[str], **kwargs: Any) -> list[list[float]]:
        raise NotImplementedError("Embedding not supported for OllamaProvider")
