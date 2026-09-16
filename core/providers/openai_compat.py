"""OpenAI-compatible provider for THINK BOX AI."""

from __future__ import annotations

import json
from typing import Any

from core.providers.base import CompletionResponse, Message, ModelProvider, ProviderCapabilities, ProviderRegistry


@ProviderRegistry.register("openai_compat")
class OpenAICompatProvider:
    def __init__(self, config: dict[str, Any]) -> None:
        self._api_key = config.get("api_key", "")
        self._model = config.get("model", "gpt-4o-mini")
        self._base_url = config.get("base_url", "https://api.openai.com/v1")
        self.capabilities = ProviderCapabilities(
            completion=True,
            streaming=config.get("streaming", False),
            embedding=False,
            supports_system_prompt=True,
        )

    async def complete(self, messages: list[Message], **kwargs: Any) -> CompletionResponse:
        import asyncio

        payload = {
            "model": self._model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": False,
            "temperature": kwargs.get("temperature", 0.7),
            "max_tokens": kwargs.get("max_tokens", 4096),
        }

        def _fetch() -> CompletionResponse:
            import urllib.request
            import urllib.error

            req = urllib.request.Request(
                f"{self._base_url}/chat/completions",
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self._api_key}",
                },
            )
            try:
                with urllib.request.urlopen(req, timeout=60) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    choice = data["choices"][0]["message"]
                    return CompletionResponse(
                        content=choice.get("content", ""),
                        model=data.get("model", self._model),
                        usage=data.get("usage", {}),
                    )
            except urllib.error.HTTPError as e:
                from core.foundation.errors import ProviderError, ProviderRateLimitError, ProviderUnavailableError
                body = e.read().decode() if hasattr(e, "read") else ""
                if e.code == 429:
                    raise ProviderRateLimitError(f"OpenAI-compatible HTTP {e.code}: {body}") from e
                if e.code == 401:
                    raise ProviderUnavailableError(f"OpenAI-compatible HTTP {e.code}: {body}") from e
                raise ProviderError(f"OpenAI-compatible HTTP {e.code}: {body}") from e

        return await asyncio.to_thread(_fetch)

    async def stream(self, messages: list[Message], **kwargs: Any):
        raise NotImplementedError("Streaming not implemented for OpenAICompatProvider")

    async def embed(self, texts: list[str], **kwargs: Any) -> list[list[float]]:
        import json
        import urllib.error
        import urllib.request

        if not self._api_key:
            raise NotImplementedError("No API key configured for embeddings")
        if not texts:
            return []

        payload = {
            "model": self._model,
            "input": texts,
        }

        def _fetch() -> list[list[float]]:
            req = urllib.request.Request(
                f"{self._base_url}/embeddings",
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self._api_key}",
                },
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=60) as resp:
                    body = json.loads(resp.read().decode("utf-8"))
                    results = body.get("data", [])
                    return [item["embedding"] for item in results]
            except urllib.error.HTTPError as e:
                body = e.read().decode() if hasattr(e, "read") else ""
                raise NotImplementedError(
                    f"Embedding not supported by provider (HTTP {e.code}): {body}"
                ) from e

        return await asyncio.to_thread(_fetch)
