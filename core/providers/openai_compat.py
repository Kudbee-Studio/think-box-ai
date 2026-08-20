"""OpenAI-compatible provider for THINK BOX AI."""

from __future__ import annotations

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
        import json
        import urllib.request
        import urllib.error

        payload = {
            "model": self._model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": False,
        }

        req = urllib.request.Request(
            f"{self._base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._api_key}",
            },
        )

        def _fetch() -> CompletionResponse:
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    choice = data["choices"][0]["message"]
                    return CompletionResponse(
                        content=choice["content"],
                        model=data.get("model", self._model),
                        usage=data.get("usage", {}),
                    )
            except urllib.error.HTTPError as e:
                if e.code == 429:
                    from core.foundation.errors import ProviderRateLimitError
                    raise ProviderRateLimitError() from e
                elif e.code == 401:
                    from core.foundation.errors import ProviderUnavailableError
                    raise ProviderUnavailableError() from e
                else:
                    from core.foundation.errors import ProviderError
                    raise ProviderError() from e

        return await __import__('asyncio').to_thread(_fetch)

    def stream(self, messages: list[Message], **kwargs: Any):
        raise NotImplementedError("Streaming not implemented for OpenAICompatProvider")

    def embed(self, texts: list[str], **kwargs: Any) -> list[list[float]]:
        raise NotImplementedError("Embedding not supported by OpenAICompatProvider")
